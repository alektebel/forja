"""One focused acceptance check per AWS From Scratch stage.

Setup may use behavior from prior stages. Each assertion introduces only the
behavior named by its stage.
"""

import hashlib


def s01():
    from iam import Decision, evaluate
    result = evaluate([], "s3:GetObject", "arn:aws:s3:::b/k")
    assert isinstance(result, Decision) and not result.allowed, (
        "No matching policy means implicit deny. Return Decision(False, ...).")


def s02():
    from iam import ALLOW, Policy, Statement, evaluate
    policy = Policy([Statement(ALLOW, "s3:Get*", "arn:aws:s3:::a/*")])
    assert evaluate([policy], "s3:GetObject", "arn:aws:s3:::a/k").allowed
    assert not evaluate([policy], "s3:PutObject", "arn:aws:s3:::a/k").allowed
    assert not evaluate([policy], "s3:GetObject", "arn:aws:s3:::b/k").allowed


def s03():
    from iam import ALLOW, DENY, Policy, Statement, evaluate
    allow = Policy([Statement(ALLOW, "*", "*")])
    deny = Policy([Statement(DENY, "s3:Delete*", "*")])
    for order in ([allow, deny], [deny, allow]):
        assert not evaluate(order, "s3:DeleteObject", "x").allowed, (
            "A matching explicit Deny wins in either policy order.")


def s04():
    from iam import ALLOW, Policy, Statement, evaluate
    policy = Policy([Statement(ALLOW, "s3:GetObject", "*", condition={
        "IpAddress": {"aws:SourceIp": "10.0.0.0/8"}})])
    assert evaluate([policy], "s3:GetObject", "x", {"aws:SourceIp": "10.1.1.1"}).allowed
    assert not evaluate([policy], "s3:GetObject", "x", {}).allowed, (
        "A required context key that is missing must not match.")


def s05():
    from iam import ALLOW, Policy, Statement, evaluate
    policy = Policy([Statement(ALLOW, "s3:GetObject", "*", condition={
        "StringEquals": {"env": ["prod", "staging"], "team": "data"}})])
    assert evaluate([policy], "s3:GetObject", "x", {"env": "staging", "team": "data"}).allowed
    assert not evaluate([policy], "s3:GetObject", "x", {"env": "prod", "team": "web"}).allowed


def s06():
    from iam import ALLOW, Policy, Statement, evaluate_with_boundary
    broad = [Policy([Statement(ALLOW, "*", "*")])]
    boundary = Policy([Statement(ALLOW, "s3:*", "*")])
    assert evaluate_with_boundary(broad, boundary, "s3:GetObject", "x").allowed
    assert not evaluate_with_boundary(broad, boundary, "iam:CreateUser", "x").allowed
    assert not evaluate_with_boundary([Policy([])], boundary, "s3:GetObject", "x").allowed


def _role():
    from iam import ALLOW, Policy, Role, Statement
    return Role("arn:aws:iam::111:role/App",
                trust=Policy([Statement(ALLOW, "sts:AssumeRole", "*", condition={
                    "ArnLike": {"aws:PrincipalArn": "arn:aws:iam::111:user/*"}})]),
                permissions=[Policy([Statement(ALLOW, "s3:*", "*")])])


def s07():
    from iam import ALLOW, Credentials, Policy, Statement, assume_role
    outsider = Credentials("arn:aws:iam::999:user/outsider", [
        Policy([Statement(ALLOW, "sts:AssumeRole", "*")])])
    try:
        assume_role(outsider, _role(), "test")
    except PermissionError:
        return
    raise AssertionError("The role trust policy must reject this caller.")


def s08():
    from iam import ALLOW, Credentials, Policy, Statement, assume_role, evaluate
    caller = Credentials("arn:aws:iam::111:user/dev", [
        Policy([Statement(ALLOW, "sts:AssumeRole", "*")])])
    session = assume_role(caller, _role(), "test")
    assert evaluate(session.policies, "s3:GetObject", "x").allowed
    assert not evaluate(session.policies, "iam:CreateUser", "x").allowed


def _s3(versioning=False):
    from s3 import S3
    store = S3()
    store.create_bucket("b", versioning=versioning)
    return store


def s09():
    store = _s3()
    store.put_object("b", "a/b.txt", b"hello")
    assert store.get_object("b", "a/b.txt").body == b"hello"


def s10():
    from s3 import S3Error
    store = _s3()
    store.put_object("b", "empty", b"")
    assert store.get_object("b", "empty").body == b""
    try:
        store.get_object("b", "absent")
    except S3Error as exc:
        assert exc.code == "NoSuchKey"
        return
    raise AssertionError("An absent key must raise NoSuchKey.")


def s11():
    from s3 import compute_etag
    assert compute_etag(b"hello") == hashlib.md5(b"hello").hexdigest()


def s12():
    from s3 import compute_etag
    parts = [b"hello", b"world"]
    tag = compute_etag(b"helloworld", parts=parts)
    assert tag.endswith("-2") and tag != compute_etag(b"helloworld")


def _listed():
    store = _s3()
    for key in ("a/1", "a/2", "top"):
        store.put_object("b", key, b"x")
    return store


def s13():
    assert _listed().list_objects("b")["keys"] == ["a/1", "a/2", "top"]


def s14():
    listing = _listed().list_objects("b", delimiter="/")
    assert listing["keys"] == ["top"]
    assert listing["common_prefixes"] == ["a/"]


def _versioned():
    store = _s3(versioning=True)
    store.put_object("b", "doc", b"old")
    store.put_object("b", "doc", b"new")
    return store


def s15():
    store = _versioned()
    history = store.list_object_versions("b", "doc")
    assert len(history) == 2
    assert store.get_object("b", "doc", history[0].version_id).body == b"old"


def s16():
    from s3 import S3Error
    store = _versioned()
    old_id = store.list_object_versions("b", "doc")[0].version_id
    store.delete_object("b", "doc")
    try:
        store.get_object("b", "doc")
    except S3Error:
        pass
    else:
        raise AssertionError("Plain GET must fail after a delete marker.")
    assert store.get_object("b", "doc", old_id).body == b"old"


def s17():
    store = _versioned()
    first_id = store.list_object_versions("b", "doc")[0].version_id
    store.delete_object("b", "doc", version_id=first_id)
    assert len(store.list_object_versions("b", "doc")) == 1
    assert store.get_object("b", "doc").body == b"new"


def _queue():
    from sqs import Queue
    queue = Queue("q", visibility_timeout=10)
    queue.send("job", now=0)
    return queue


def s18():
    queue = _queue()
    assert len(queue.receive(now=0)) == 1
    assert queue.receive(now=5) == []


def s19():
    queue = _queue()
    queue.receive(now=0)
    assert len(queue.receive(now=11)) == 1


def s20():
    queue = _queue()
    first = queue.receive(now=0)[0]
    second = queue.receive(now=11)[0]
    assert first.receipt_handle != second.receipt_handle


def s21():
    queue = _queue()
    handle = queue.receive(now=0)[0].receipt_handle
    assert queue.delete(handle)
    assert queue.receive(now=11) == []


def s22():
    queue = _queue()
    handle = queue.receive(now=0)[0].receipt_handle
    queue.change_visibility(handle, 60, now=5)
    assert queue.receive(now=11) == []
    assert len(queue.receive(now=66)) == 1


def s23():
    from sqs import Queue
    dead = Queue("dead")
    main = Queue("main", visibility_timeout=1, max_receives=2, dead_letter=dead)
    main.send("poison", now=0)
    for now in (0, 2, 4):
        main.receive(now=now)
    assert main.receive(now=6) == []
    assert len(dead.messages) == 1


def s24():
    from sqs import Queue
    queue = Queue("f.fifo", fifo=True)
    queue.send("A1", group_id="A", now=0)
    queue.send("A2", group_id="A", now=0)
    batch = queue.receive(max_messages=2, now=0)
    assert len(batch) == 1 and batch[0].body == "A1"


def s25():
    from sqs import Queue
    queue = Queue("f.fifo", fifo=True)
    queue.send("A1", group_id="A", now=0)
    queue.send("A2", group_id="A", now=0)
    queue.send("B1", group_id="B", now=0)
    assert {m.group_id for m in queue.receive(max_messages=3, now=0)} == {"A", "B"}


def s26():
    from sqs import Queue
    queue = Queue("f.fifo", fifo=True)
    assert queue.send("pay", group_id="A", dedup_id="order-7", now=0)
    assert queue.send("pay", group_id="A", dedup_id="order-7", now=10) is None
    assert queue.send("pay", group_id="A", dedup_id="order-7", now=400)


def _table(**options):
    from dynamodb import Table
    return Table("t", partition_key="pk", sort_key="sk", read_capacity=1000,
                 write_capacity=1000, num_partitions=4, **options)


def s27():
    table = _table()
    table.put_item({"pk": "alice", "sk": "001", "v": 1}, now=0)
    table.put_item({"pk": "bob", "sk": "001", "v": 2}, now=0)
    assert table.get_item("alice", "001", now=0)["v"] == 1
    assert table.get_item("bob", "001", now=0)["v"] == 2


def s28():
    table = _table()
    for pk in ("alice", "bob"):
        table.put_item({"pk": pk, "sk": "001"}, now=0)
    assert [row["pk"] for row in table.query("alice", now=0)] == ["alice"]


def s29():
    from dynamodb import ConditionalCheckFailed
    table = _table()
    table.put_item({"pk": "a", "sk": "1", "v": 1}, now=0)
    try:
        table.put_item({"pk": "a", "sk": "1", "v": 2},
                       condition=lambda old: old is None, now=0)
    except ConditionalCheckFailed:
        pass
    else:
        raise AssertionError("A failed condition must raise ConditionalCheckFailed.")
    assert table.get_item("a", "1", now=0)["v"] == 1


def s30():
    from dynamodb import Table
    table = Table("t", partition_key="pk", read_capacity=100, num_partitions=1)
    table.put_item({"pk": "x"}, now=0)
    part = table.partitions["p0"]
    part.read_used = 0
    table.get_item("x", consistent=False, now=0)
    eventual = part.read_used
    part.read_used = 0
    table.get_item("x", consistent=True, now=0)
    assert part.read_used == 2 * eventual


def s31():
    from dynamodb import Table, ThroughputExceeded
    table = Table("t", partition_key="pk", sort_key="sk", write_capacity=40,
                  num_partitions=4)
    assert table.per_partition_write == 10
    for n in range(10):
        table.put_item({"pk": "same", "sk": str(n)}, now=0)
    try:
        table.put_item({"pk": "same", "sk": "11"}, now=0)
    except ThroughputExceeded:
        return
    raise AssertionError("The 11th same-partition write must throttle in this toy.")


def s32():
    from dynamodb import Table, ThroughputExceeded
    table = Table("t", partition_key="pk", sort_key="sk", write_capacity=40,
                  num_partitions=4)
    try:
        for n in range(20):
            table.put_item({"pk": f"key-{n}", "sk": "0"}, now=0)
    except ThroughputExceeded:
        raise AssertionError("Distinct keys should spread across partitions.")
    assert len(table.partitions) > 1


def s33():
    table = _table()
    for pk in ("alice", "bob", "carol"):
        table.put_item({"pk": pk, "sk": "1"}, now=0)
    before = table.stats["scanned_items"]
    rows = table.scan(lambda row: row["pk"] == "alice", now=0)
    assert len(rows) == 1
    assert table.stats["scanned_items"] - before == 3


def _lambda(handler=None, **options):
    from lambda_svc import Function, LambdaService
    service = LambdaService(account_concurrency=10)
    service.register(Function("f", handler or (lambda event, context: "ok"),
                              init_ms=800, **options))
    return service


def s34():
    service = _lambda()
    first = service.invoke("f", {}, now=0)
    assert first.cold and first.billed_ms >= 800


def _counter(event, context):
    state = context["env"]
    state["n"] = state.get("n", 0) + 1
    return state["n"]


def s35():
    service = _lambda(_counter)
    service.invoke("f", {}, now=0)
    second = service.invoke("f", {}, now=1)
    assert not second.cold and second.result == 2


def s36():
    service = _lambda(_counter, env_ttl_s=300)
    service.invoke("f", {}, now=0)
    again = service.invoke("f", {}, now=1000)
    assert again.cold and again.result == 1


def s37():
    service = _lambda(timeout_s=1)
    result = service.invoke("f", {}, now=0, duration_ms=2000)
    assert result.error and "timed out" in result.error.lower()
    assert result.billed_ms == 1000


def s38():
    service = _lambda()
    ran, throttled = service.concurrent_invoke("f", [{}] * 15, now=0)
    assert (ran, throttled) == (10, 5)


def s39():
    from lambda_svc import Function
    service = _lambda()
    service.register(Function("critical", lambda event, context: "ok",
                              reserved_concurrency=6))
    assert service.unreserved_capacity() == 4
    ran, _ = service.concurrent_invoke("f", [{}] * 10, now=0)
    assert ran == 4


def _explode(event, context):
    raise ValueError("boom")


def s40():
    service = _lambda(_explode)
    result = service.invoke("f", {}, now=0)
    assert result.error and service.functions["f"].stats["invocations"] == 1


def s41():
    service = _lambda(_explode)
    attempts = service.invoke_async("f", {"job": 1}, now=0)
    assert len(attempts) == 3


def s42():
    dead = []
    service = _lambda(_explode, dead_letter=dead)
    service.invoke_async("f", {"job": 1}, now=0)
    assert dead == [{"job": 1}]


def s43():
    from sns import Topic
    from sqs import Queue
    topic = Topic("t")
    a, b = Queue("a"), Queue("b")
    topic.subscribe("sqs", a, "a")
    topic.subscribe("sqs", b, "b")
    result = topic.publish("hello", now=0)
    assert result["delivered"] == 2
    assert a.receive(now=0)[0].body == "hello"
    assert b.receive(now=0)[0].body == "hello"


def s44():
    from sns import matches_filter
    assert matches_filter({"env": ["prod", "staging"]}, {"env": "staging"})
    assert not matches_filter({"env": ["prod", "staging"]}, {"env": "dev"})


def s45():
    from sns import matches_filter
    policy = {"type": ["pdf"], "env": ["prod"]}
    assert matches_filter(policy, {"type": "pdf", "env": "prod"})
    assert not matches_filter(policy, {"type": "pdf"})


def s46():
    from sns import matches_event_pattern
    pattern = {"detail": {"state": ["terminated"]}}
    assert matches_event_pattern(pattern, {"detail": {"state": "terminated"}})
    assert not matches_event_pattern(pattern, {"detail": {"state": "running"}})


def s47():
    from sns import EventBus
    bus = EventBus()
    first, second = [], []
    bus.add_rule("first", {"source": ["aws.ec2"]}, first.append)
    bus.add_rule("second", {"source": ["aws.ec2"]}, second.append)
    fired = bus.put_event({"source": "aws.ec2"})
    assert set(fired) == {"first", "second"}
    assert len(first) == len(second) == 1


def _kms():
    from kms import KMS
    kms = KMS()
    kms.create_key("k")
    return kms


def s48():
    kms = _kms()
    data_key = kms.generate_data_key("k")
    assert data_key.encrypted.wrapped != data_key.plaintext
    assert kms.decrypt_data_key(data_key.encrypted) == data_key.plaintext


def s49():
    from kms import EnvelopeCipher
    cipher = EnvelopeCipher(_kms(), "k")
    ciphertext, wrapped = cipher.encrypt(b"secret")
    assert ciphertext != b"secret"
    assert cipher.decrypt(ciphertext, wrapped) == b"secret"


def s50():
    from kms import EnvelopeCipher, KMSError
    cipher = EnvelopeCipher(_kms(), "k")
    ciphertext, wrapped = cipher.encrypt(b"tenant A", {"tenant": "A"})
    assert cipher.decrypt(ciphertext, wrapped, {"tenant": "A"}) == b"tenant A"
    try:
        cipher.decrypt(ciphertext, wrapped, {"tenant": "B"})
    except KMSError:
        return
    raise AssertionError("A different context must not unwrap the data key.")


def s51():
    from kms import EnvelopeCipher
    kms = _kms()
    cipher = EnvelopeCipher(kms, "k")
    ciphertext, wrapped = cipher.encrypt(b"before")
    kms.keys["k"].rotate()
    assert cipher.decrypt(ciphertext, wrapped) == b"before"


def s52():
    from vpc import Cidr
    assert Cidr("10.0.0.0/16").contains(Cidr("10.0.1.0/24"))
    assert not Cidr("10.0.0.0/16").contains(Cidr("10.1.0.0/24"))


def s53():
    from vpc import Vpc
    vpc = Vpc("v", "10.0.0.0/16")
    vpc.add_subnet("a", "10.0.1.0/24")
    try:
        vpc.add_subnet("b", "10.0.1.128/25")
    except ValueError:
        return
    raise AssertionError("Overlapping subnets must be rejected.")


def s54():
    from vpc import Cidr
    assert Cidr("10.0.0.0/28").usable_hosts() == 11


def s55():
    from vpc import Vpc
    vpc = Vpc("v", "10.0.0.0/16")
    subnet = vpc.add_subnet("a", "10.0.1.0/24")
    subnet.add_route("0.0.0.0/0", "default")
    subnet.add_route("10.1.0.0/16", "wide")
    subnet.add_route("10.1.5.0/24", "narrow")
    assert subnet.route_for("10.1.5.7") == "narrow"


def s56():
    from vpc import SecurityGroup, test_connection
    group = SecurityGroup("web")
    group.allow_inbound("tcp", 443, 443, "0.0.0.0/0")
    assert test_connection("203.0.113.5", "10.0.1.10", 443,
                           security_group=group)["allowed"]


def s57():
    from vpc import NetworkAcl, test_connection
    acl = NetworkAcl("web")
    acl.add("in", 100, "allow", "tcp", 443, 443, "0.0.0.0/0")
    acl.add("out", 100, "allow", "tcp", 443, 443, "0.0.0.0/0")
    assert not test_connection("203.0.113.5", "10.0.1.10", 443,
                               acl=acl)["allowed"]


def s58():
    from vpc import NetworkAcl
    acl = NetworkAcl("ordered")
    acl.add("in", 200, "allow", "tcp", 22, 22, "10.0.0.0/8")
    acl.add("in", 100, "deny", "tcp", 22, 22, "0.0.0.0/0")
    assert not acl.evaluate("in", "tcp", 22, "10.0.5.5")[0]


def _system():
    from capstone import build
    return build()


def s59():
    from capstone import upload
    system = _system()
    upload(system, system["uploader"], "acme", "doc.pdf", b"x", now=0)
    assert "doc.pdf" in system["cloud"].s3.buckets["uploads"].objects
    assert system["topic"].stats["published"] == 1


def s60():
    from capstone import upload
    system = _system()
    upload(system, system["uploader"], "acme", "doc.pdf", b"x", now=0)
    assert system["queue"].depth(now=0)["visible"] == 1


def s61():
    from capstone import drain, upload
    system = _system()
    upload(system, system["uploader"], "acme", "doc.pdf", b"x", now=0)
    assert drain(system, now=1)["processed"] == 1
    assert len(system["documents"].query("acme", now=2)) == 1


def s62():
    from capstone import AccessDenied, upload
    system = _system()
    try:
        upload(system, system["uploader"], "acme", "private/doc.pdf", b"x", now=0)
    except AccessDenied:
        pass
    else:
        raise AssertionError("The denied upload must raise AccessDenied.")
    assert "private/doc.pdf" not in system["cloud"].s3.buckets["uploads"].objects
    assert system["queue"].depth(now=0)["visible"] == 0


def s63():
    from capstone import drain, failure_origin, upload
    system = _system()
    for n in range(12):
        upload(system, system["uploader"], "acme", f"doc-{n}.pdf", b"x", now=0)
    outcome = drain(system, now=1)
    assert outcome["failed"] > 0
    assert failure_origin(system, outcome) == "dynamodb", (
        "Use the worker failure and the database partition report to name the cause.")


CHECKS = [globals()[f"s{number:02d}"] for number in range(1, 64)]
