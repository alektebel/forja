"""
Capstone — a serverless application from the pieces. Complete Solution.

    upload to S3
      -> S3 event notification
        -> SNS topic (fanout, with a filter policy)
          -> SQS queue (durable buffer)
            -> Lambda (concurrency-limited)
              -> DynamoDB (partition-keyed, throttleable)
    with KMS encrypting the payload and IAM gating every single call.

The point is not that it works. It is that the FAILURES compose too, and each
one is a mechanism you built and can now recognise anywhere:

  IAM denies      -> the call never happens, and the error names the statement
  Lambda throttle -> events queue instead of being lost, because SQS buffers
  Dynamo throttle -> a hot partition key, not a capacity shortage
  Poison event    -> retried, then dead-lettered rather than retried forever
"""

from typing import Any, Dict, List, Optional

from dynamodb import Table, ThroughputExceeded
from iam import ALLOW, DENY, Credentials, Policy, Statement, evaluate
from kms import KMS, EnvelopeCipher
from lambda_svc import Function, LambdaService, Throttled
from s3 import S3
from sns import Topic
from sqs import Queue


class AccessDenied(Exception):
    pass


class Cloud:
    """A tiny account: services, plus the IAM check every call goes through."""

    def __init__(self):
        self.s3 = S3()
        self.kms = KMS()
        self.lambda_service = LambdaService(account_concurrency=5)
        self.tables: Dict[str, Table] = {}
        self.topics: Dict[str, Topic] = {}
        self.queues: Dict[str, Queue] = {}
        self.audit: List[str] = []

    def authorize(self, credentials: Credentials, action: str,
                  resource: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Every call goes through this. In a real account it is the ONLY thing
        standing between a bug and someone else's data."""
        decision = evaluate(credentials.policies, action, resource, context)
        self.audit.append(f"{'ALLOW' if decision.allowed else 'DENY '} "
                          f"{credentials.principal} {action} {resource}")
        if not decision.allowed:
            raise AccessDenied(f"{credentials.principal} cannot {action} on "
                               f"{resource}: {decision.reason}")


def build() -> Dict[str, Any]:
    cloud = Cloud()

    cloud.s3.create_bucket("uploads", versioning=True)
    cloud.kms.create_key("alias/uploads")
    cipher = EnvelopeCipher(cloud.kms, "alias/uploads")

    documents = Table("documents", partition_key="tenant", sort_key="doc_id",
                      read_capacity=20, write_capacity=20, num_partitions=4)
    cloud.tables["documents"] = documents

    dlq = Queue("processing-dlq")
    work = Queue("processing", visibility_timeout=30, max_receives=2,
                 dead_letter=dlq)
    cloud.queues["processing"] = work
    cloud.queues["processing-dlq"] = dlq

    topic = Topic("uploads")
    topic.subscribe("sqs", work, "processing",
                    filter_policy={"content_type": ["application/pdf"]})
    cloud.topics["uploads"] = topic

    def process(event, context):
        """The worker. Writes a row per uploaded document."""
        documents.put_item({"tenant": event["tenant"], "doc_id": event["key"],
                            "size": event["size"], "status": "indexed"},
                           now=event.get("now", 0))
        return {"indexed": event["key"]}

    cloud.lambda_service.register(
        Function("indexer", process, init_ms=200, timeout_s=5))

    uploader = Credentials("arn:aws:iam::111:role/Uploader", [
        Policy([Statement(ALLOW, ["s3:PutObject", "kms:GenerateDataKey"],
                          ["arn:aws:s3:::uploads/*", "arn:aws:kms:::alias/uploads"]),
                Statement(DENY, "s3:PutObject", "arn:aws:s3:::uploads/private/*",
                          sid="NoPrivatePrefix")], name="UploaderPolicy")])

    reader = Credentials("arn:aws:iam::111:role/Reader", [
        Policy([Statement(ALLOW, "dynamodb:Query", "arn:aws:dynamodb:::documents")],
               name="ReaderPolicy")])

    return {"cloud": cloud, "cipher": cipher, "topic": topic, "queue": work,
            "dlq": dlq, "documents": documents, "uploader": uploader,
            "reader": reader}


def upload(system: Dict[str, Any], credentials: Credentials, tenant: str,
           key: str, body: bytes, content_type: str = "application/pdf",
           now: float = 0.0) -> Dict[str, Any]:
    """The full write path, with every gate in place."""
    cloud, cipher = system["cloud"], system["cipher"]

    cloud.authorize(credentials, "s3:PutObject", f"arn:aws:s3:::uploads/{key}")
    cloud.authorize(credentials, "kms:GenerateDataKey",
                    "arn:aws:kms:::alias/uploads")

    ciphertext, wrapped = cipher.encrypt(body, {"tenant": tenant})
    cloud.s3.put_object("uploads", key, ciphertext,
                        metadata={"kms_version": str(wrapped.version)})

    # The S3 event notification.
    return system["topic"].publish(
        f"{tenant}/{key}",
        {"content_type": content_type, "tenant": tenant}, now=now)


def drain(system: Dict[str, Any], now: float = 0.0,
          batch: int = 10) -> Dict[str, int]:
    """Poll the queue and invoke the function — an event source mapping."""
    cloud, queue = system["cloud"], system["queue"]
    processed = throttled = failed = 0

    for message in queue.receive(max_messages=batch, now=now):
        tenant, _, key = message.body.partition("/")
        event = {"tenant": tenant, "key": key, "size": 1, "now": now}
        try:
            result = cloud.lambda_service.invoke("indexer", event, now=now)
            if result.error:
                failed += 1        # left in flight: it will be redelivered
                continue
            queue.delete(message.receipt_handle)
            processed += 1
        except Throttled:
            throttled += 1         # NOT lost — the lease expires and it returns
    return {"processed": processed, "throttled": throttled, "failed": failed}


def failure_origin(system: Dict[str, Any], outcome: Dict[str, int]) -> Optional[str]:
    """Name the downstream cause of a worker failure."""
    if outcome["failed"] and any(
        row["throttled"] > 0
        for row in system["documents"].hot_partition_report().values()
    ):
        return "dynamodb"
    return None


def _demo() -> None:
    system = build()
    cloud = system["cloud"]

    print("=" * 68)
    print("A serverless pipeline, assembled from the pieces")
    print("=" * 68)
    print("  S3 -> SNS -> SQS -> Lambda -> DynamoDB, KMS on the payload,")
    print("  IAM on every call.\n")

    print("=== The happy path ===")
    result = upload(system, system["uploader"], "acme", "report.pdf",
                    b"quarterly numbers", now=0)
    print(f"  upload -> SNS {result}")
    print(f"  queue depth: {system['queue'].depth(now=0)['visible']}")
    print(f"  drain -> {drain(system, now=1)}")
    rows = system["documents"].query("acme", now=2)
    print(f"  DynamoDB now holds: {rows}")

    print("\n=== IAM denies before anything happens ===")
    try:
        upload(system, system["uploader"], "acme", "private/salaries.pdf",
               b"do not index", now=3)
    except AccessDenied as exc:
        print(f"  {exc}")
    print("  The explicit Deny on the private/ prefix beat the broad Allow —")
    print("  and nothing was encrypted, stored or published. The whole point of")
    print("  authorising FIRST is that the side effects never start.")

    print("\n=== A filter policy drops what nobody wants ===")
    result = upload(system, system["uploader"], "acme", "photo.png",
                    b"binary", content_type="image/png", now=4)
    print(f"  png upload -> SNS {result}")
    print(f"  queue depth: {system['queue'].depth(now=4)['visible']} "
          "(filtered out at the topic, never billed as a delivery)")

    print("\n=== A failure surfaces one layer away from its cause ===")
    for n in range(12):
        upload(system, system["uploader"], "acme", f"bulk-{n}.pdf",
               b"x", now=5)
    print(f"  12 uploads -> queue depth {system['queue'].depth(now=5)['visible']}")
    outcome = drain(system, now=6)
    print(f"  drain: {outcome}")
    print("\n  Five failed. Read the layers: the Lambda invocations errored, but")
    print("  the CAUSE is DynamoDB — every document has tenant='acme', so they")
    print("  all hash to one partition, which holds a quarter of the table's")
    print("  20 WCU. The alarm fires on Lambda; the fix is in the data model.")
    print("  This mismatch between where a failure is VISIBLE and where it is")
    print("  CAUSED is most of what makes distributed debugging hard.")

    print(f"\n  still queued: {system['queue'].depth(now=6)['visible']}, "
          f"in flight: {system['queue'].depth(now=6)['in_flight']}")
    later = drain(system, now=100)
    print(f"  drain again once the leases expire: {later}")
    print("  Nothing was lost. The failed messages were never deleted, so their")
    print("  visibility timeout returned them — which is exactly why the queue")
    print("  sits between the topic and the function. SNS alone would have")
    print("  pushed once and dropped them.")

    print("\n=== Lambda concurrency sheds a genuine burst ===")
    succeeded, throttled = cloud.lambda_service.concurrent_invoke(
        "indexer", [{"tenant": "t", "key": f"k{i}", "size": 1, "now": 200}
                    for i in range(12)], now=200)
    print(f"  12 simultaneous invocations, account limit "
          f"{cloud.lambda_service.account_concurrency}: "
          f"{succeeded} ran, {throttled} throttled")
    print("  A quota, not a capacity problem — the function's speed is")
    print("  irrelevant. Behind a queue this is back-pressure; behind an API")
    print("  Gateway it is a 429 in a user's face.")

    print("\n=== A hot partition key throttles a table that is 75% idle ===")
    hot = Table("events", partition_key="day", sort_key="seq",
                read_capacity=20, write_capacity=20, num_partitions=4)
    written = 0
    try:
        for n in range(30):
            hot.put_item({"day": "2024-06-01", "seq": f"{n:04d}"}, now=0)
            written += 1
    except ThroughputExceeded as exc:
        print(f"  wrote {written} of 30, then: {str(exc)[:60]}...")
    print(f"  partitions in use: {list(hot.hot_partition_report())}")
    print("  Same lesson as dynamodb.py, now inside an app: raising the table's")
    print("  capacity changes nothing. The key has to spread.")

    print("\n=== A poison event is retried, then set aside ===")
    def explode(event, context):
        raise ValueError("cannot parse this document")
    cloud.lambda_service.register(Function("fragile", explode, init_ms=50))

    poison = Queue("poison", visibility_timeout=1, max_receives=2,
                   dead_letter=system["dlq"])
    poison.send("acme/corrupt.pdf", now=0)
    for attempt in range(4):
        batch = poison.receive(now=attempt * 2)
        if batch:
            cloud.lambda_service.invoke("fragile", {}, now=attempt * 2)
        print(f"  attempt {attempt}: received {len(batch)}")
    print(f"  dead-letter queue: {len(system['dlq'].messages)} message(s)")
    print("  Two failures and it stops consuming throughput forever.")

    print("\n=== The audit trail ===")
    for line in cloud.audit[:3]:
        print(f"  {line}")
    denies = [l for l in cloud.audit if l.startswith("DENY")]
    print(f"  ... {len(cloud.audit)} decisions total, {len(denies)} denied")
    print(f"  {denies[0] if denies else ''}")

    print("\n" + "=" * 68)
    print("""
Every failure above is a mechanism you implemented:

  the explicit Deny that beat a broad Allow          iam.py
  a delete marker hiding an object that still exists  s3.py
  a lease expiring and redelivering a message         sqs.py
  a hot partition throttling an idle table            dynamodb.py
  a concurrency quota shedding a burst                lambda_svc.py
  a filter policy dropping a delivery at the topic    sns.py
  a data key wrapped under a key version              kms.py

That is the point of building them small. In a real account these are log
lines and error codes; here they are code you have already read.
""")


if __name__ == "__main__":
    _demo()
