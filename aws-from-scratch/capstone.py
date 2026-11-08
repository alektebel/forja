"""
Capstone — a serverless application from the pieces. Starter template.

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
    # Stage 60: subscribe the queue to this topic.
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
    """Stage 59: store an encrypted object, then publish its notification.

    Stage 62 adds authorization before either side effect. Follow the current
    stage guide; the path grows one behavior at a time.
    """
    raise NotImplementedError


def drain(system: Dict[str, Any], now: float = 0.0,
          batch: int = 10) -> Dict[str, int]:
    """Poll the queue and invoke the function — an event source mapping."""
    raise NotImplementedError


def failure_origin(system: Dict[str, Any], outcome: Dict[str, int]) -> Optional[str]:
    """Stage 63: name the root cause from worker and database observations."""
    raise NotImplementedError


def _demo() -> None:
    """Once the checks pass, write a demo that PRINTS the behaviour.

    The solution's demo is the reference — but write yours first and predict
    the numbers before running it. A result that surprises you is a gap in your
    model that passing tests did not reveal.
    """
    raise NotImplementedError


if __name__ == "__main__":
    _demo()
