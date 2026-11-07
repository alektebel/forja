"""
Progress checker for the AWS-from-scratch templates.

    python3 check.py           # run every check, stop at the first unimplemented step
    python3 check.py 4         # run only step 4
    python3 check.py 4 6       # run steps 4 through 6
    python3 check.py --all     # run everything, do not stop at the first gap

Nothing here imports solutions/. It tests YOUR code.
"""

import math
import pathlib
import shutil
import sys
import traceback

sys.dont_write_bytecode = True
shutil.rmtree(pathlib.Path(__file__).parent / "__pycache__", ignore_errors=True)

from typing import Callable, List, Tuple

PASS, FAIL, TODO, ERROR = "PASS", "FAIL", "TODO", "ERROR"
GREEN, RED, YELLOW, GREY, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[1m", "\033[0m")


# ---------------------------------------------------------------------------
# IAM
# ---------------------------------------------------------------------------

def check_stage_1() -> None:
    from iam import ALLOW, DENY, Policy, Statement, evaluate

    read = Policy([Statement(ALLOW, "s3:Get*", "arn:aws:s3:::reports/*")], name="R")
    assert evaluate([read], "s3:GetObject", "arn:aws:s3:::reports/a.csv").allowed
    assert not evaluate([read], "s3:PutObject", "arn:aws:s3:::reports/a.csv").allowed, \
        "s3:Get* must not match s3:PutObject"
    assert not evaluate([read], "s3:GetObject", "arn:aws:s3:::other/a.csv").allowed, \
        "the resource ARN must be checked, not just the action"
    assert not evaluate([], "s3:GetObject", "arn:aws:s3:::x").allowed, \
        "no policies at all means implicit deny, never allow"

    admin = Policy([Statement(ALLOW, "*", "*")], name="Admin")
    guard = Policy([Statement(DENY, "s3:Delete*", "arn:aws:s3:::reports/*")],
                   name="Guard")
    for order in ([admin, guard], [guard, admin]):
        decision = evaluate(order, "s3:DeleteObject", "arn:aws:s3:::reports/a.csv")
        assert not decision.allowed, (
            "an explicit Deny must beat any Allow, in EITHER order. Policies "
            "are evaluated as a set — collect all denies first, then allows. "
            "If order changed your answer, you are iterating and letting the "
            "last match win, like a firewall.")
    assert evaluate([admin, guard], "s3:GetObject", "arn:aws:s3:::reports/a.csv").allowed


def check_stage_2() -> None:
    from iam import ALLOW, Policy, Statement, evaluate, evaluate_with_boundary

    policy = Policy([Statement(
        ALLOW, "s3:GetObject", "arn:aws:s3:::b/*",
        condition={"IpAddress": {"aws:SourceIp": "10.0.0.0/8"},
                   "Bool": {"aws:SecureTransport": "true"}})], name="C")

    assert evaluate([policy], "s3:GetObject", "arn:aws:s3:::b/k",
                    {"aws:SourceIp": "10.1.1.1",
                     "aws:SecureTransport": True}).allowed
    assert not evaluate([policy], "s3:GetObject", "arn:aws:s3:::b/k",
                        {"aws:SourceIp": "10.1.1.1",
                         "aws:SecureTransport": False}).allowed, (
        "conditions AND across keys — both must hold")
    assert not evaluate([policy], "s3:GetObject", "arn:aws:s3:::b/k",
                        {"aws:SecureTransport": True}).allowed, (
        "a MISSING context key must never match. Conditions fail closed; "
        "treating absent as 'anything goes' is a security bug.")

    multi = Policy([Statement(ALLOW, "s3:*", "*",
                              condition={"StringEquals": {"env": ["prod", "staging"]}})])
    assert evaluate([multi], "s3:GetObject", "x", {"env": "prod"}).allowed
    assert evaluate([multi], "s3:GetObject", "x", {"env": "staging"}).allowed, \
        "values within one key are OR — any listed value may match"
    assert not evaluate([multi], "s3:GetObject", "x", {"env": "dev"}).allowed

    broad = [Policy([Statement(ALLOW, "*", "*")])]
    boundary = Policy([Statement(ALLOW, "s3:*", "*")])
    assert evaluate_with_boundary(broad, boundary, "s3:GetObject", "x").allowed
    assert not evaluate_with_boundary(broad, boundary, "iam:CreateUser", "x").allowed, \
        "a permissions boundary caps what identity policies may grant"
    assert not evaluate_with_boundary([Policy([])], boundary, "s3:GetObject", "x").allowed, \
        "a boundary must never GRANT on its own — it only subtracts"


def check_stage_3() -> None:
    from iam import (ALLOW, Credentials, Policy, Role, Statement, assume_role,
                     evaluate)

    role = Role("arn:aws:iam::111:role/App",
                trust=Policy([Statement(ALLOW, "sts:AssumeRole",
                                        "arn:aws:iam::111:role/App",
                                        condition={"ArnLike": {
                                            "aws:PrincipalArn":
                                            "arn:aws:iam::111:user/*"}})]),
                permissions=[Policy([Statement(ALLOW, "s3:*", "*")])])

    insider = Credentials("arn:aws:iam::111:user/dev", [
        Policy([Statement(ALLOW, "sts:AssumeRole", "*")])])
    session = assume_role(insider, role, "s1")
    assert evaluate(session.policies, "s3:GetObject", "x").allowed, \
        "the session must carry the ROLE's permissions, not the caller's"

    outsider = Credentials("arn:aws:iam::999:user/mallory", [
        Policy([Statement(ALLOW, "sts:AssumeRole", "*")])])
    try:
        assume_role(outsider, role, "s2")
        raise AssertionError(
            "an outsider whose OWN policy allows sts:AssumeRole was let in. The "
            "role's TRUST policy must be checked too — that is the direction "
            "that protects you from another account.")
    except PermissionError:
        pass

    no_permission = Credentials("arn:aws:iam::111:user/intern", [Policy([])])
    try:
        assume_role(no_permission, role, "s3")
        raise AssertionError("the caller's own policy must also allow "
                             "sts:AssumeRole — both directions are required")
    except PermissionError:
        pass


# ---------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------

def check_stage_4() -> None:
    from s3 import S3, S3Error, compute_etag

    s3 = S3()
    s3.create_bucket("b")
    etag = s3.put_object("b", "k", b"hello")
    assert etag == compute_etag(b"hello")
    assert s3.get_object("b", "k").body == b"hello"

    try:
        s3.get_object("b", "missing")
        raise AssertionError("a missing key must raise NoSuchKey")
    except S3Error as exc:
        assert exc.code == "NoSuchKey"

    multi = compute_etag(b"x" * 300, parts=[b"x" * 100] * 3)
    assert multi.endswith("-3"), (
        f"a multipart ETag must end with '-<part count>', got {multi}. It is "
        "the MD5 of the concatenated part MD5s, NOT the MD5 of the object — "
        "which is why you cannot verify a multipart upload against a local md5.")
    assert multi != compute_etag(b"x" * 300)


def check_stage_5() -> None:
    from s3 import S3, S3Error

    s3 = S3()
    s3.create_bucket("b")
    for key in ("a/1.txt", "a/2.txt", "b/1.txt", "top.txt"):
        s3.put_object("b", key, b"x")

    flat = s3.list_objects("b")
    assert flat["keys"] == ["a/1.txt", "a/2.txt", "b/1.txt", "top.txt"], \
        f"without a delimiter every key is returned flat: {flat['keys']}"

    folders = s3.list_objects("b", delimiter="/")
    assert folders["keys"] == ["top.txt"], f"got {folders['keys']}"
    assert sorted(folders["common_prefixes"]) == ["a/", "b/"], (
        f"got {folders['common_prefixes']}. The delimiter is what INVENTS "
        "folders — keys sharing a prefix collapse into a common prefix. There "
        "is no directory object anywhere.")

    scoped = s3.list_objects("b", prefix="a/", delimiter="/")
    assert scoped["keys"] == ["a/1.txt", "a/2.txt"]

    versioned = S3()
    versioned.create_bucket("v", versioning=True)
    versioned.put_object("v", "doc", b"one")
    versioned.put_object("v", "doc", b"two")
    assert versioned.get_object("v", "doc").body == b"two"
    assert len(versioned.list_object_versions("v", "doc")) == 2, \
        "a versioned bucket keeps both versions, it does not overwrite"

    versioned.delete_object("v", "doc")
    try:
        versioned.get_object("v", "doc")
        raise AssertionError("a plain GET must fail once a delete marker is on top")
    except S3Error:
        pass

    history = versioned.list_object_versions("v", "doc")
    assert len(history) == 3, (
        f"after the delete there should be 3 entries (2 versions + a delete "
        f"marker), found {len(history)}. DELETE in a versioned bucket does not "
        "delete — it pushes a marker, and the bytes stay billable.")
    assert history[-1].is_delete_marker
    first = history[0]
    assert versioned.get_object("v", "doc", first.version_id).body == b"one", \
        "a versioned GET must still reach the data under the marker"

    assert versioned.list_objects("v")["keys"] == [], \
        "a key whose latest version is a delete marker must not be listed"


# ---------------------------------------------------------------------------
# SQS
# ---------------------------------------------------------------------------

def check_stage_6() -> None:
    from sqs import Queue

    queue = Queue("q", visibility_timeout=10)
    queue.send("job", now=0)
    assert queue.depth(now=0)["visible"] == 1

    first = queue.receive(now=0)
    assert len(first) == 1 and first[0].receive_count == 1
    assert queue.depth(now=0) == {"visible": 0, "delayed": 0, "in_flight": 1}, \
        "a received message is in flight, not gone — receive is a LEASE"

    assert queue.receive(now=5) == [], \
        "a leased message must stay hidden until the visibility timeout expires"

    second = queue.receive(now=11)
    assert len(second) == 1, (
        "once the lease expires the message MUST come back. That redelivery is "
        "at-least-once semantics working as designed — the queue chose "
        "duplication over loss.")
    assert second[0].receive_count == 2

    assert not queue.delete(first[0].receipt_handle), (
        "the FIRST consumer's receipt handle is now stale and its delete must "
        "fail. If it succeeded, both consumers share one Message object and "
        "the second receive overwrote the first's handle — give each receive "
        "its own view.")
    assert queue.delete(second[0].receipt_handle)
    assert queue.depth(now=12)["visible"] == 0


def check_stage_7() -> None:
    from sqs import Queue

    extended = Queue("e", visibility_timeout=10)
    extended.send("slow", now=0)
    held = extended.receive(now=0)[0]
    extended.change_visibility(held.receipt_handle, 60, now=5)
    assert extended.receive(now=11) == [], \
        "change_visibility must extend the lease — the fix for slow consumers"


def check_stage_8() -> None:
    from sqs import Queue

    dlq = Queue("dlq")
    main = Queue("main", visibility_timeout=1, max_receives=2, dead_letter=dlq)
    main.send("poison", now=0)
    for attempt in range(5):
        main.receive(now=attempt * 2)
    assert len(dlq.messages) == 1, (
        f"after exceeding max_receives the message must move to the DLQ, found "
        f"{len(dlq.messages)}. Without one it is retried forever, consuming "
        "throughput and hiding the messages behind it.")
    assert main.depth(now=100)["visible"] == 0

    aged = Queue("a", visibility_timeout=1)
    aged.send("m", now=0)
    aged.receive(now=0)
    assert aged.oldest_age(now=300) > 250, (
        "oldest_age must count IN-FLIGHT messages too. A message being retried "
        "forever is exactly the case the age alarm exists to catch.")


def check_stage_9() -> None:
    from sqs import Queue

    fifo = Queue("f.fifo", fifo=True, visibility_timeout=30)
    for i in range(3):
        fifo.send(f"A{i}", group_id="A", now=0)
    fifo.send("B0", group_id="B", now=0)

    batch = fifo.receive(max_messages=10, now=0)
    groups = [m.group_id for m in batch]
    assert groups.count("A") == 1, (
        f"a FIFO queue must deliver only ONE in-flight message per group, got "
        f"{groups}. Ordering within a group costs you parallelism within it.")
    assert "B" in groups, "a different group is not blocked"

    dedup = Queue("d.fifo", fifo=True)
    assert dedup.send("pay", "A", "order-7", now=0) is not None
    assert dedup.send("pay", "A", "order-7", now=10) is None, \
        "a duplicate dedup_id within the 5-minute window must be dropped"
    assert dedup.send("pay", "A", "order-7", now=400) is not None, \
        "outside the window it is accepted again"


# ---------------------------------------------------------------------------
# DynamoDB
# ---------------------------------------------------------------------------

def check_stage_10() -> None:
    from dynamodb import ConditionalCheckFailed, DynamoError, Table

    table = Table("t", partition_key="pk", sort_key="sk",
                  read_capacity=100, write_capacity=100, num_partitions=4)
    for pk in ("alice", "bob", "carol"):
        for n in range(2):
            table.put_item({"pk": pk, "sk": f"{n:03d}", "v": n}, now=0)

    assert table.get_item("alice", "000", now=0)["v"] == 0
    assert table.get_item("bob", "000", now=0)["v"] == 0, (
        "alice/000 and bob/000 must be distinct items. If bob's overwrote "
        "alice's, your partition is keyed by the SORT key alone — it must be "
        "keyed by the full composite key.")
    assert table.get_item("nobody", "000", now=0) is None

    rows = table.query("alice", now=0)
    assert len(rows) == 2 and all(r["pk"] == "alice" for r in rows), \
        f"query must return only the requested partition, got {rows}"

    try:
        table.put_item({"sk": "x"}, now=0)
        raise AssertionError("an item without the partition key must raise")
    except DynamoError:
        pass

    table.put_item({"pk": "new", "sk": "1", "v": 1},
                   condition=lambda existing: existing is None, now=0)
    try:
        table.put_item({"pk": "new", "sk": "1", "v": 2},
                       condition=lambda existing: existing is None, now=0)
        raise AssertionError(
            "a failed condition must raise ConditionalCheckFailed. This is how "
            "you get idempotent creates and optimistic locking with no lock "
            "service at all.")
    except ConditionalCheckFailed:
        pass
    assert table.get_item("new", "1", now=0)["v"] == 1, \
        "the failed conditional write must not have changed anything"


def check_stage_11() -> None:
    from dynamodb import Table, ThroughputExceeded

    table = Table("t", partition_key="pk", read_capacity=100, num_partitions=1)
    table.put_item({"pk": "x"}, now=0)
    partition = table.partitions["p0"]

    partition.read_used = 0.0
    table.get_item("x", consistent=False, now=0)
    eventual = partition.read_used
    partition.read_used = 0.0
    table.get_item("x", consistent=True, now=0)
    assert partition.read_used == eventual * 2, (
        f"a strongly consistent read must cost twice an eventually consistent "
        f"one ({partition.read_used} vs {eventual})")

    hot = Table("h", partition_key="day", sort_key="seq",
                read_capacity=40, write_capacity=40, num_partitions=4)
    assert hot.per_partition_write == 10.0, (
        "table capacity is divided ACROSS partitions — that division is the "
        "entire reason a hot key throttles while the table looks idle")
    written = 0
    try:
        for n in range(30):
            hot.put_item({"day": "same-key", "seq": f"{n:04d}"}, now=0)
            written += 1
        raise AssertionError(
            "30 writes to ONE partition key with 10 WCU per partition must "
            "throttle. If it did not, capacity is being checked table-wide "
            "instead of per partition, and the most common DynamoDB surprise "
            "cannot be reproduced.")
    except ThroughputExceeded:
        pass
    assert written == 10, f"expected 10 writes before throttling, got {written}"

    spread = Table("s", partition_key="day", sort_key="seq",
                   read_capacity=40, write_capacity=40, num_partitions=4)
    for n in range(20):
        spread.put_item({"day": f"key-{n}", "seq": "0"}, now=0)   # must not throttle



def check_stage_12() -> None:
    from dynamodb import Table

    counts = Table("c", partition_key="pk", read_capacity=1000,
                   write_capacity=1000, num_partitions=4)
    for pk in ("alice", "bob", "carol"):
        counts.put_item({"pk": pk, "v": 1}, now=0)
    before = counts.stats["scanned_items"]
    counts.query("alice", now=0)
    query_cost = counts.stats["scanned_items"] - before
    before = counts.stats["scanned_items"]
    counts.scan(lambda i: i["pk"] == "alice", now=0)
    scan_cost = counts.stats["scanned_items"] - before
    assert scan_cost > query_cost, (
        f"scan read {scan_cost} items, query read {query_cost}. A scan must "
        "read EVERY item and filter afterwards — that is why a scan returning "
        "3 of a million items still costs a million reads.")


# ---------------------------------------------------------------------------
# Lambda
# ---------------------------------------------------------------------------

def check_stage_13() -> None:
    from lambda_svc import Function, LambdaService

    service = LambdaService(account_concurrency=10)

    def handler(event, context):
        context["env"]["n"] = context["env"].get("n", 0) + 1
        return context["env"]["n"]

    service.register(Function("f", handler, init_ms=800, env_ttl_s=300))

    first = service.invoke("f", {}, now=0)
    assert first.cold, "the first invocation must be a cold start"
    assert first.billed_ms >= 800, \
        f"a cold start must include the init cost, billed {first.billed_ms}"

    second = service.invoke("f", {}, now=1)
    assert not second.cold, "the second invocation must reuse the environment"
    assert second.billed_ms < first.billed_ms
    assert second.result == 2, (
        f"warm state must survive between invocations, got {second.result}. "
        "Anything outside the handler persists — great for a connection pool, "
        "a disaster for a cache you assumed was empty.")

    stale = service.invoke("f", {}, now=1000)
    assert stale.cold, "an environment past its TTL must be replaced"
    assert stale.result == 1, "a fresh environment starts with fresh state"

    timed_out = service.invoke("f", {}, now=2000, duration_ms=99_999)
    assert timed_out.error and "timed out" in timed_out.error.lower()
    assert timed_out.billed_ms > 0, "a timeout is billed in full"


def check_stage_14() -> None:
    from lambda_svc import Function, LambdaService, Throttled

    service = LambdaService(account_concurrency=10)
    service.register(Function("api", lambda e, c: "ok", init_ms=10))

    succeeded, throttled = service.concurrent_invoke(
        "api", [{} for _ in range(15)], now=0)
    assert succeeded == 10 and throttled == 5, (
        f"15 simultaneous events against a limit of 10 must shed 5, got "
        f"{succeeded} ran / {throttled} throttled. Throttling is a QUOTA, not "
        "a speed problem.")

    service.register(Function("critical", lambda e, c: "ok",
                              reserved_concurrency=6))
    assert service.unreserved_capacity() == 4, (
        f"reserving 6 of 10 must leave 4 for everything else, got "
        f"{service.unreserved_capacity()}. Reserved concurrency is carved out "
        "whether it is used or not — which is how one reservation throttles an "
        "unrelated function.")

    succeeded, throttled = service.concurrent_invoke(
        "api", [{} for _ in range(10)], now=100)
    assert succeeded == 4, (
        f"'api' was never changed, yet it can now only run {succeeded}. That "
        "silent reduction is the point of the check.")

    dlq: List[object] = []

    def explode(event, context):
        raise ValueError("nope")

    service.register(Function("bad", explode, init_ms=10, dead_letter=dlq))
    attempts = service.invoke_async("bad", {"job": 1}, now=200)
    assert len(attempts) == 3, (
        f"an async invocation must be retried before giving up, got "
        f"{len(attempts)} attempt(s). A non-idempotent handler runs three "
        "times — three charges, three emails.")
    assert dlq == [{"job": 1}], "the exhausted event must reach the dead letter"

    sync = service.invoke("bad", {"job": 2}, now=300)
    assert sync.error, "a synchronous failure surfaces to the caller immediately"


# ---------------------------------------------------------------------------
# SNS / EventBridge
# ---------------------------------------------------------------------------

def check_stage_15() -> None:
    from sns import Topic
    from sqs import Queue

    topic = Topic("t")
    a, b = Queue("a"), Queue("b")
    seen: List[str] = []
    topic.subscribe("sqs", a, "a")
    topic.subscribe("sqs", b, "b")
    topic.subscribe("lambda", lambda e, c: seen.append(e["Message"]), "fn")

    result = topic.publish("hello", now=0)
    assert result["delivered"] == 3, f"one publish, three deliveries: {result}"
    assert a.depth(now=0)["visible"] == 1 and b.depth(now=0)["visible"] == 1, (
        "SNS must deliver to SQS on the SAME clock it was given. If the queues "
        "look empty, `now` is not being threaded through to the subscriber and "
        "messages landed in the future.")
    assert seen == ["hello"]



def check_stage_16() -> None:
    from sns import matches_filter

    assert matches_filter(None, {"any": "thing"}), "no policy means deliver"
    assert matches_filter({"s": ["a", "b"]}, {"s": "b"}), \
        "values within one key are OR"
    assert not matches_filter({"s": ["a"], "e": ["prod"]}, {"s": "a"}), (
        "keys AND: a policy naming two attributes needs BOTH, and a MISSING "
        "attribute never matches — the same fail-closed rule as IAM conditions")
    assert not matches_filter({"s": ["a"]}, {"s": "z"})
    assert matches_filter({"n": [{"numeric": [">", 100]}]}, {"n": 500})
    assert not matches_filter({"n": [{"numeric": [">", 100]}]}, {"n": 5})
    assert matches_filter({"r": [{"prefix": "us-"}]}, {"r": "us-east-1"})
    assert matches_filter({"x": [{"anything-but": "no"}]}, {"x": "yes"})
    assert matches_filter({"k": [{"exists": False}]}, {"other": 1}), \
        "{'exists': False} matches when the attribute is absent"


def check_stage_17() -> None:
    from sns import EventBus, matches_event_pattern

    assert matches_event_pattern({"source": ["aws.ec2"]}, {"source": "aws.ec2"})
    assert not matches_event_pattern({"source": ["aws.ec2"]}, {"source": "aws.s3"})
    assert not matches_event_pattern({"source": ["aws.ec2"]}, {"other": 1}), \
        "a key absent from the event cannot match"
    assert matches_event_pattern(
        {"detail": {"state": ["terminated"]}},
        {"detail": {"state": "terminated", "id": "i-1"}}), \
        "patterns must nest — EventBridge matches the SHAPE of the event"
    assert not matches_event_pattern(
        {"detail": {"state": ["terminated"]}},
        {"detail": {"state": "running"}})

    bus = EventBus()
    one: List[dict] = []
    two: List[dict] = []
    bus.add_rule("a", {"source": ["aws.ec2"]}, one.append)
    bus.add_rule("b", {"detail": {"status": ["FAILED"]}}, two.append)

    fired = bus.put_event({"source": "aws.ec2",
                           "detail": {"status": "FAILED"}})
    assert set(fired) == {"a", "b"}, (
        f"an event matching two rules must fire BOTH, got {fired}. Nothing "
        "deduplicates that — a good way to double-process an event.")
    assert bus.put_event({"source": "aws.s3"}) == []


# ---------------------------------------------------------------------------
# KMS
# ---------------------------------------------------------------------------

def check_stage_18() -> None:
    from kms import KMS, EnvelopeCipher, KMSError

    kms = KMS()
    key = kms.create_key("k")
    cipher = EnvelopeCipher(kms, "k")

    data_key = kms.generate_data_key("k")
    assert len(data_key.plaintext) == 32
    assert data_key.encrypted.wrapped != data_key.plaintext, \
        "the wrapped copy must not equal the plaintext copy"
    assert kms.decrypt_data_key(data_key.encrypted) == data_key.plaintext, \
        "unwrapping must recover exactly the plaintext data key"

    document = b"secret" * 500
    ciphertext, wrapped = cipher.encrypt(document)
    assert ciphertext != document
    assert cipher.decrypt(ciphertext, wrapped) == document
    assert len(ciphertext) == len(document), \
        "envelope encryption keeps the data with YOU — size is unchanged"

    calls_before = key.stats["data_keys"]
    cipher.encrypt(b"x" * 100_000)
    assert key.stats["data_keys"] == calls_before + 1, (
        "one KMS call per OBJECT, not per byte — that is the whole reason the "
        "4KB KMS payload limit does not constrain you")


def check_stage_19() -> None:
    from kms import KMS, EnvelopeCipher, KMSError

    kms = KMS()
    key = kms.create_key("k")
    cipher = EnvelopeCipher(kms, "k")

    ciphertext, wrapped = cipher.encrypt(b"tenant A", {"tenant": "A"})
    assert cipher.decrypt(ciphertext, wrapped, {"tenant": "A"}) == b"tenant A"
    for wrong in ({"tenant": "B"}, {}, None):
        try:
            cipher.decrypt(ciphertext, wrapped, wrong)
            raise AssertionError(
                f"decrypting with context {wrong} must fail. The encryption "
                "context is authenticated data — not secret, but it must match, "
                "and it is what lets an IAM condition scope a key to a tenant.")
        except KMSError:
            pass



def check_stage_20() -> None:
    from kms import KMS, EnvelopeCipher, KMSError

    kms = KMS()
    key = kms.create_key("k")
    cipher = EnvelopeCipher(kms, "k")

    old_cipher, old_wrapped = cipher.encrypt(b"before")
    assert old_wrapped.version == 1
    assert key.rotate() == 2
    new_cipher, new_wrapped = cipher.encrypt(b"after")
    assert new_wrapped.version == 2, "new encryptions use the new version"
    assert cipher.decrypt(old_cipher, old_wrapped) == b"before", (
        "old ciphertext MUST still decrypt after rotation. Rotation re-encrypts "
        "KEYS, never DATA — one that broke old ciphertext would be an outage.")
    assert cipher.decrypt(new_cipher, new_wrapped) == b"after"

    key.versions = [v for v in key.versions if v.version != 1]
    try:
        cipher.decrypt(old_cipher, old_wrapped)
        raise AssertionError("ciphertext wrapped under a deleted key version "
                             "must be unrecoverable, and say so clearly")
    except KMSError:
        pass


# ---------------------------------------------------------------------------
# VPC
# ---------------------------------------------------------------------------

def check_stage_21() -> None:
    from vpc import Cidr, Vpc

    assert Cidr("10.0.0.0/16").contains(Cidr("10.0.1.0/24"))
    assert not Cidr("10.0.0.0/16").contains(Cidr("10.1.0.0/24"))
    assert Cidr("10.0.1.0/24").overlaps(Cidr("10.0.1.128/25"))
    assert not Cidr("10.0.1.0/24").overlaps(Cidr("10.0.2.0/24"))
    assert Cidr("10.0.0.0/28").usable_hosts() == 11, (
        f"a /28 has 16 addresses but only 11 usable — AWS reserves 5 per "
        f"subnet, got {Cidr('10.0.0.0/28').usable_hosts()}")

    vpc = Vpc("v", "10.0.0.0/16")
    vpc.add_subnet("a", "10.0.1.0/24")
    for bad in ("10.0.1.128/25", "192.168.0.0/24"):
        try:
            vpc.add_subnet("bad", bad)
            raise AssertionError(f"{bad} must be rejected (overlap or outside)")
        except ValueError:
            pass



def check_stage_22() -> None:
    from vpc import Vpc

    vpc = Vpc("v", "10.0.0.0/16")
    vpc.add_subnet("a", "10.0.1.0/24")
    subnet = vpc.subnets["a"]
    subnet.add_route("0.0.0.0/0", "igw")
    subnet.add_route("10.1.0.0/16", "peering")
    subnet.add_route("10.1.5.0/24", "tgw")
    assert subnet.route_for("10.1.5.7") == "tgw", (
        "route tables match the LONGEST PREFIX, not the first entry — "
        "10.1.5.7 matches three routes and must take the /24")
    assert subnet.route_for("10.1.9.9") == "peering"
    assert subnet.route_for("8.8.8.8") == "igw"
    assert subnet.route_for("10.0.1.5") == "local"


def check_stage_23() -> None:
    """The difference that causes the most VPC confusion."""
    from vpc import NetworkAcl, SecurityGroup, test_connection

    sg = SecurityGroup("sg")
    sg.allow_inbound("tcp", 443, 443, "0.0.0.0/0")
    result = test_connection("203.0.113.5", "10.0.1.10", 443, security_group=sg)
    assert result["allowed"], (
        "a security group is STATEFUL: allowing the request in implicitly "
        "allows the reply out. No return rule is ever needed.")

    naive = NetworkAcl("naive")
    naive.add("in", 100, "allow", "tcp", 443, 443, "0.0.0.0/0")
    naive.add("out", 100, "allow", "tcp", 443, 443, "0.0.0.0/0")
    result = test_connection("203.0.113.5", "10.0.1.10", 443, acl=naive)
    assert not result["allowed"], (
        "identical rules on a NACL must FAIL. A NACL is STATELESS: the reply is "
        "a separate packet going to an EPHEMERAL port (49152-65535), and "
        "nothing here allows that. This is the single most common VPC bug, and "
        "if your model does not reproduce it, it is not modelling the "
        "connection — only the request.")

    fixed = NetworkAcl("fixed")
    fixed.add("in", 100, "allow", "tcp", 443, 443, "0.0.0.0/0")
    fixed.add("out", 100, "allow", "tcp", 1024, 65535, "0.0.0.0/0")
    assert test_connection("203.0.113.5", "10.0.1.10", 443,
                           acl=fixed)["allowed"], \
        "with an ephemeral-port outbound rule the connection must work"

    ordered = NetworkAcl("o")
    ordered.add("in", 100, "deny", "tcp", 22, 22, "0.0.0.0/0")
    ordered.add("in", 200, "allow", "tcp", 22, 22, "10.0.0.0/8")
    allowed, why = ordered.evaluate("in", "tcp", 22, "10.0.5.5")
    assert not allowed, (
        "NACL rules are evaluated in NUMBER order, first match wins — the deny "
        f"at 100 must shadow the allow at 200. Got: {why}")
    assert not sg.evaluate("in", "tcp", 22, "10.0.5.5"), \
        "a security group has no deny rules: absence of an allow IS the deny"


# ---------------------------------------------------------------------------
# Capstone
# ---------------------------------------------------------------------------

def check_stage_24() -> None:
    from capstone import AccessDenied, build, drain, upload

    system = build()
    result = upload(system, system["uploader"], "acme", "report.pdf",
                    b"payload", now=0)
    assert result["delivered"] == 1, f"the pdf should reach the queue: {result}"
    assert system["queue"].depth(now=0)["visible"] == 1

    outcome = drain(system, now=1)
    assert outcome["processed"] == 1, f"the worker should index it: {outcome}"
    rows = system["documents"].query("acme", now=2)
    assert len(rows) == 1 and rows[0]["doc_id"] == "report.pdf", \
        f"the pipeline must land a row in DynamoDB, got {rows}"

    try:
        upload(system, system["uploader"], "acme", "private/pay.pdf",
               b"x", now=3)
        raise AssertionError(
            "the explicit Deny on the private/ prefix must block the upload "
            "BEFORE anything is encrypted, stored or published")
    except AccessDenied:
        pass
    assert "private/pay.pdf" not in system["cloud"].s3.buckets["uploads"].objects, \
        "an authorisation failure must leave no side effects behind"

    before = system["queue"].depth(now=4)["visible"]
    result = upload(system, system["uploader"], "acme", "photo.png", b"x",
                    content_type="image/png", now=4)
    assert result["filtered"] == 1 and result["delivered"] == 0, \
        "the filter policy must drop the png at the TOPIC, not at the consumer"
    assert system["queue"].depth(now=4)["visible"] == before

    denied = [line for line in system["cloud"].audit if line.startswith("DENY")]
    assert denied, "the audit trail must record denied calls, not only allowed ones"


CHECKS: List[Tuple[str, str, Callable[[], None]]] = [
    ("iam.py", "explicit deny > allow > implicit deny", check_stage_1),
    ("iam.py", "conditions: AND keys, OR values, fail closed", check_stage_2),
    ("iam.py", "permissions boundaries subtract, never grant", check_stage_2),
    ("iam.py", "assume-role: caller policy AND role trust", check_stage_3),
    ("s3.py", "put/get objects and the NoSuchKey error", check_stage_4),
    ("s3.py", "multipart ETags end in -<part count>", check_stage_4),
    ("s3.py", "delimiter invents folders at list time", check_stage_5),
    ("s3.py", "delete marker hides versions, frees nothing", check_stage_5),
    ("sqs.py", "receive is a lease; expiry redelivers", check_stage_6),
    ("sqs.py", "stale receipt handles must fail to delete", check_stage_6),
    ("sqs.py", "change_visibility extends the lease", check_stage_7),
    ("sqs.py", "poison messages dead-letter after max_receives", check_stage_8),
    ("sqs.py", "oldest_age counts in-flight messages too", check_stage_8),
    ("sqs.py", "FIFO: one in-flight message per group", check_stage_9),
    ("sqs.py", "FIFO dedup window drops duplicate ids", check_stage_9),
    ("dynamodb.py", "composite key = partition + sort", check_stage_10),
    ("dynamodb.py", "query reads one partition; missing key raises", check_stage_10),
    ("dynamodb.py", "conditional writes fail atomically", check_stage_10),
    ("dynamodb.py", "consistent reads cost twice eventual ones", check_stage_11),
    ("dynamodb.py", "capacity divides across partitions; hot key throttles", check_stage_11),
    ("dynamodb.py", "scan reads everything, then filters", check_stage_12),
    ("lambda_svc.py", "cold start once; warm state survives", check_stage_13),
    ("lambda_svc.py", "environment TTL resets state; timeout bills full", check_stage_13),
    ("lambda_svc.py", "concurrency is a quota; reservation steals a floor", check_stage_14),
    ("lambda_svc.py", "async failures retry to 3 attempts, then DLQ", check_stage_14),
    ("sns.py", "one publish fans out to every subscriber", check_stage_15),
    ("sns.py", "filters: AND keys, OR values, missing never matches", check_stage_16),
    ("sns.py", "EventBridge matches nested shape, fires every rule", check_stage_17),
    ("kms.py", "envelope: data key encrypts, CMK wraps the key", check_stage_18),
    ("kms.py", "one KMS call per object, not per byte", check_stage_18),
    ("kms.py", "encryption context must match on decrypt", check_stage_19),
    ("kms.py", "rotation re-encrypts keys, never data", check_stage_20),
    ("vpc.py", "CIDR containment, overlap, 5 reserved IPs", check_stage_21),
    ("vpc.py", "routes pick the longest matching prefix", check_stage_22),
    ("vpc.py", "SG stateful vs NACL stateless, same rules", check_stage_23),
    ("capstone.py", "the pipeline, and failures surfacing a layer away", check_stage_24),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_one(check: Callable[[], None]) -> Tuple[str, str]:
    try:
        check()
        return PASS, ""
    except NotImplementedError as exc:
        where = ""
        for frame in reversed(traceback.extract_tb(sys.exc_info()[2])):
            if frame.filename.endswith(".py") and "check.py" not in frame.filename:
                where = f"{frame.filename.split('/')[-1]}:{frame.lineno} in {frame.name}()"
                break
        return TODO, (str(exc) or where)
    except AssertionError as exc:
        return FAIL, str(exc) or "assertion failed"
    except Exception as exc:                       # noqa: BLE001
        where = ""
        for frame in reversed(traceback.extract_tb(sys.exc_info()[2])):
            if "check.py" not in frame.filename:
                where = (f"\n      at {frame.filename.split('/')[-1]}:"
                         f"{frame.lineno} in {frame.name}()")
                break
        return ERROR, f"{type(exc).__name__}: {exc}{where}"


def main(argv: List[str]) -> int:
    keep_going = "--all" in argv
    wanted = [int(a) for a in argv if a.isdigit()]
    if len(wanted) > 1:
        wanted = list(range(min(wanted), max(wanted) + 1))

    print(f"\n{BOLD}AWS From Scratch — progress check{RESET}")
    print(f"{GREY}implement the templates, re-run this after each step{RESET}\n")

    passed = failed = todo = 0
    first_gap = None

    for index, (filename, title, check) in enumerate(CHECKS, start=1):
        if wanted and index not in wanted:
            continue

        status, detail = run_one(check)
        if status == PASS:
            passed += 1
            print(f"  {GREEN}✓{RESET} {index:>2}. {filename:<20} {title}")
        elif status == TODO:
            todo += 1
            first_gap = first_gap or index
            print(f"  {GREY}·{RESET} {index:>2}. {filename:<20} {title}")
            print(f"      {GREY}not implemented yet"
                  f"{(' — ' + detail) if detail else ''}{RESET}")
            if not keep_going and not wanted:
                remaining = len(CHECKS) - index
                if remaining:
                    print(f"\n  {GREY}({remaining} later checks not run; "
                          f"use --all to run them anyway){RESET}")
                break
        else:
            failed += 1
            first_gap = first_gap or index
            colour = RED if status == FAIL else YELLOW
            print(f"  {colour}✗{RESET} {index:>2}. {filename:<20} {title}")
            for line in detail.splitlines():
                print(f"      {colour}{line}{RESET}")

    total = len(wanted) if wanted else len(CHECKS)
    print(f"\n  {passed}/{total} passing", end="")
    if failed:
        print(f", {RED}{failed} failing{RESET}", end="")
    if todo:
        print(f", {GREY}{todo} to write{RESET}", end="")
    print()

    if passed == len(CHECKS):
        print(f"\n  {GREEN}{BOLD}All checks pass — you built the core of AWS.{RESET}")
        print(f"  {GREY}Now run each file's own demo to see the measurements,{RESET}")
        print(f"  {GREY}then compare your approach with solutions/.{RESET}\n")
    elif first_gap:
        filename, title, _ = CHECKS[first_gap - 1]
        print(f"\n  {BOLD}Next:{RESET} step {first_gap} — {title} ({filename})")
        print(f"  {GREY}The TODO comments in that file walk through it. "
              f"Stuck? solutions/{filename}{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
