# Stage 11: Message queue — retries, backoff, DLQ, idempotent delivery

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `message_queue.py`
**Tags:** complex, queues, delivery

## The mechanism

Implement Message, MessageQueue (enqueue/dequeue/ack/nack with visibility, retry+backoff, dead-letter queue, idempotency-key dedup) and exponential_backoff(base, cap, jitter).

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 11
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 11
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> nack with retries left — is the old message id ever seen again?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- backoff: min(cap, base * 2**attempt), jitter optional
- deliver_at gates dequeue; attempts increment on requeue
- max_attempts exhausted → dlq_depth grows, queue_depth shrinks

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 12
```
