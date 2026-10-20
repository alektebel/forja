"""
Message Queue — From Scratch
==============================
Build an async message queue to understand:
- At-least-once delivery semantics
- Exponential backoff with jitter for retries
- Dead-letter queue (DLQ) for poison messages
- Idempotency keys to safely handle redelivery
- Message deduplication with a seen-set + TTL
- Scheduled / delayed message delivery

Learning Path:
1. Implement a basic in-memory queue with enqueue/dequeue
2. Add visibility timeout (message invisible while being processed)
3. Add retry logic: re-enqueue on failure, up to max_attempts
4. Add exponential backoff with jitter between retries
5. Add DLQ: after max_attempts, move to dead-letter queue
6. Add idempotency: track processed message IDs with TTL
7. Add delayed delivery (schedule messages for future processing)
8. Think about: Kafka vs SQS trade-offs
"""

import time
import uuid
import threading
import random
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Message data structure
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """A queue message with delivery metadata."""
    id: str                              # unique message ID (for dedup/idempotency)
    body: Any                            # the payload
    attempts: int = 0                    # number of delivery attempts so far
    max_attempts: int = 5                # give up after this many failed attempts
    enqueued_at: float = field(default_factory=time.time)
    deliver_at: float = field(default_factory=time.time)  # for delayed delivery
    idempotency_key: Optional[str] = None  # caller-supplied key for dedup


# ---------------------------------------------------------------------------
# Step 1: Backoff calculator
# ---------------------------------------------------------------------------

def exponential_backoff(attempt: int, base: float = 1.0, cap: float = 60.0,
                         jitter: bool = True) -> float:
    """Compute exponential backoff delay for a retry attempt.

    Formula: delay = min(cap, base * 2^attempt)
    With full jitter: delay = random(0, min(cap, base * 2^attempt))

    Args:
        attempt: current attempt number (0-indexed)
        base: base delay in seconds
        cap: maximum delay in seconds
        jitter: whether to add random jitter (recommended to prevent thundering herd)

    Returns:
        delay in seconds before next retry

    TODO:
    1. Compute raw_delay = min(cap, base * 2^attempt)
    2. If jitter: return random.uniform(0, raw_delay)
    3. Otherwise: return raw_delay
    """
    # TODO: implement exponential backoff
    raise NotImplementedError("Implement exponential_backoff")


# ---------------------------------------------------------------------------
# Step 2: In-memory Message Queue
# ---------------------------------------------------------------------------

class MessageQueue:
    """Simple in-memory message queue with retry, DLQ, and deduplication.

    TODO:
    - _queue: list of Messages ready for delivery
    - _dlq: list of Messages that exceeded max_attempts
    - _seen_ids: set of recently processed message IDs (for dedup)
    - _in_flight: messages currently being processed (visibility timeout)
    """

    def __init__(self, visibility_timeout: float = 30.0, dedup_ttl: float = 300.0):
        """
        Args:
            visibility_timeout: seconds a message is hidden after dequeue
                                 before being re-enqueued for retry
            dedup_ttl: seconds to remember seen message IDs
        """
        self.visibility_timeout = visibility_timeout
        self.dedup_ttl = dedup_ttl
        self._queue: List[Message] = []
        self._dlq: List[Message] = []
        self._in_flight: Dict[str, tuple] = {}  # msg_id → (message, deadline)
        self._seen_ids: Dict[str, float] = {}   # msg_id → seen_at timestamp
        self._lock = threading.Lock()

    def enqueue(self, body: Any, idempotency_key: Optional[str] = None,
                delay_seconds: float = 0.0) -> str:
        """Add a new message to the queue.

        TODO:
        1. Generate a unique message ID (uuid4)
        2. Check idempotency: if idempotency_key already in _seen_ids, skip (return existing id)
        3. Create a Message with deliver_at = now + delay_seconds
        4. Append to _queue
        5. Return message.id
        """
        # TODO: implement enqueue
        raise NotImplementedError("Implement MessageQueue.enqueue")

    def dequeue(self) -> Optional[Message]:
        """Pop the next ready message from the queue.

        TODO:
        1. Find first message where deliver_at <= now
        2. Remove from _queue
        3. Increment message.attempts
        4. Record in _in_flight with deadline = now + visibility_timeout
        5. Return message (or None if queue is empty / no ready messages)
        """
        # TODO: implement dequeue
        raise NotImplementedError("Implement MessageQueue.dequeue")

    def ack(self, message_id: str) -> None:
        """Acknowledge successful processing of a message.

        TODO:
        1. Remove from _in_flight
        2. Record message_id in _seen_ids (for dedup) with current timestamp
        """
        # TODO: implement ack
        raise NotImplementedError("Implement MessageQueue.ack")

    def nack(self, message_id: str, retry: bool = True) -> None:
        """Negative-acknowledge: message processing failed.

        TODO:
        1. Remove from _in_flight
        2. Get the message back
        3. If retry=True and attempts < max_attempts:
           - Compute backoff delay using exponential_backoff(attempts)
           - Set deliver_at = now + delay
           - Re-enqueue to _queue
        4. Otherwise: move to DLQ
        """
        # TODO: implement nack
        raise NotImplementedError("Implement MessageQueue.nack")

    def requeue_timed_out(self) -> int:
        """Re-enqueue messages whose visibility timeout has expired.

        This simulates what SQS does automatically — messages that weren't
        acked within the visibility timeout become visible again.

        TODO:
        1. Scan _in_flight for messages where deadline < now
        2. For each timed-out message: call nack (which handles retry/DLQ)
        3. Return count of re-enqueued messages
        """
        # TODO: implement requeue_timed_out
        raise NotImplementedError("Implement MessageQueue.requeue_timed_out")

    def _clean_seen_ids(self) -> None:
        """Remove expired entries from _seen_ids (lazy cleanup).

        TODO: remove entries older than dedup_ttl
        """
        # TODO: implement _clean_seen_ids
        pass

    @property
    def queue_depth(self) -> int:
        """Number of messages waiting to be processed."""
        return len(self._queue)

    @property
    def dlq_depth(self) -> int:
        """Number of messages in the dead-letter queue."""
        return len(self._dlq)

    def drain_dlq(self) -> List[Message]:
        """Return and clear all DLQ messages (for inspection/replay)."""
        with self._lock:
            messages = list(self._dlq)
            self._dlq.clear()
            return messages


# ---------------------------------------------------------------------------
# Step 3: Worker (consumer)
# ---------------------------------------------------------------------------

class QueueWorker:
    """A consumer that processes messages from a queue.

    TODO:
    - Run a loop: dequeue → process → ack/nack
    - Periodically call queue.requeue_timed_out()
    - Handle exceptions in handler_fn → nack on failure
    """

    def __init__(self, queue: MessageQueue, handler_fn: Callable[[Message], None],
                 poll_interval: float = 0.1):
        self._queue = queue
        self._handler = handler_fn
        self._poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.processed = 0
        self.failed = 0

    def start(self) -> None:
        """Start the worker in a background thread.

        TODO:
        - Set _running = True
        - Start a daemon thread running _run_loop
        """
        # TODO: implement start
        raise NotImplementedError("Implement QueueWorker.start")

    def stop(self) -> None:
        """Stop the worker."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run_loop(self) -> None:
        """Main processing loop.

        TODO:
        1. While _running:
           a. Call queue.requeue_timed_out()
           b. msg = queue.dequeue()
           c. If msg is None: sleep(poll_interval); continue
           d. Try: handler(msg); ack(msg.id); increment processed
           e. Except: nack(msg.id); increment failed
        """
        # TODO: implement _run_loop
        raise NotImplementedError("Implement QueueWorker._run_loop")


# ---------------------------------------------------------------------------
# Step 4: Scale & Kafka vs SQS (discussion)
# ---------------------------------------------------------------------------

"""
SQS (Queue) vs Kafka (Stream) Trade-offs:

SQS (Queue semantics):
  - Messages are consumed and DELETED after ack
  - Each message processed by ONE consumer (competing consumers)
  - At-least-once delivery (duplicates possible)
  - Simple, managed, pay-per-request
  - Good for: task queues, background jobs, decoupled services

Kafka (Stream semantics):
  - Messages are RETAINED (log-based); consumers track their own offset
  - Same message can be consumed by MULTIPLE consumer groups independently
  - Strong ordering within a partition; parallel via multiple partitions
  - Replay old events by rewinding offset
  - Good for: event sourcing, audit logs, real-time analytics, fan-out

Idempotency Keys:
  - Producer includes a unique key (e.g. order_id + "payment")
  - Consumer checks if key was already processed before acting
  - Prevents double-charging even if message delivered twice

Scheduled Jobs:
  - SQS delay queues: up to 15 min delay
  - Use a "scheduler" service that stores job + run_at in DB, polls, enqueues
  - Distributed lock (Redis SET NX EX) to ensure only one runner executes per job
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing exponential_backoff...")
    d0 = exponential_backoff(0, base=1.0, cap=60.0, jitter=False)
    d1 = exponential_backoff(1, base=1.0, cap=60.0, jitter=False)
    d5 = exponential_backoff(5, base=1.0, cap=60.0, jitter=False)
    assert d0 == 1.0, f"attempt 0 should be 1.0, got {d0}"
    assert d1 == 2.0, f"attempt 1 should be 2.0, got {d1}"
    assert d5 == 32.0, f"attempt 5 should be 32.0, got {d5}"
    d_capped = exponential_backoff(10, base=1.0, cap=60.0, jitter=False)
    assert d_capped == 60.0, f"should be capped at 60.0, got {d_capped}"
    print("  exponential_backoff: OK")

    print("Testing MessageQueue (basic enqueue/dequeue/ack)...")
    q = MessageQueue()
    msg_id = q.enqueue({"task": "send_email", "to": "user@example.com"})
    assert q.queue_depth == 1
    msg = q.dequeue()
    assert msg is not None
    assert msg.body["to"] == "user@example.com"
    assert q.queue_depth == 0
    q.ack(msg.id)
    print("  basic enqueue/dequeue/ack: OK")

    print("Testing idempotency dedup...")
    q2 = MessageQueue()
    id1 = q2.enqueue("task", idempotency_key="idem-1")
    id2 = q2.enqueue("task", idempotency_key="idem-1")  # duplicate!
    assert q2.queue_depth == 1, "duplicate should be deduped"
    m = q2.dequeue()
    q2.ack(m.id)
    print("  idempotency dedup: OK")

    print("Testing retry + DLQ...")
    q3 = MessageQueue()
    q3.enqueue("failing_task")
    msg = q3.dequeue()
    # Simulate failures until DLQ
    for _ in range(msg.max_attempts):
        q3.nack(msg.id, retry=True)
        msg = q3.dequeue()
        if msg is None:
            break
    # If still has a message, do one final nack to exhaust attempts
    if msg:
        while msg.attempts < msg.max_attempts:
            q3.nack(msg.id, retry=True)
            msg = q3.dequeue()
            if msg is None:
                break
        if msg:
            q3.nack(msg.id, retry=False)
    assert q3.dlq_depth >= 1, "message should end up in DLQ"
    print("  retry + DLQ: OK")

    print("\nAll message queue tests passed!")


if __name__ == "__main__":
    _test()
