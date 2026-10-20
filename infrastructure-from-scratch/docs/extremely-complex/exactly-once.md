# Exactly-Once Delivery — Extremely Complex

## 1. What problem does it solve?

At-least-once delivery guarantees that every message is delivered at least once —
but this means duplicates:
```
Producer → [message_id: 123] → Consumer → Process payment of $100
                                    → Process payment of $100   ← DUPLICATE!
```

The duplicate is a real problem when the action is not idempotent:
- Charge a credit card twice
- Send the same notification twice
- Deduct inventory twice

Exactly-once delivery means: every message is processed exactly once.
No duplicates, no losses.

**The job:** ensure that every message has a unique identity,
the consumer can deduplicate, and the system can survive crashes
without double-processing.

## 2. How does it work?

### Idempotency keys (the foundation)

Every message carries a unique ID. The consumer checks: "have I seen this ID before?"

```python
def consume(message):
    if db.exists("processed_ids", message.id):
        return  # duplicate — skip
    db.save("processed_ids", message.id, result=message.result)
    process(message)
```

Without idempotency, exactly-once is impossible.

### Transactional producer (no loss)

When a producer writes to a queue AND updates state:
1. Begin transaction
2. Write message to queue
3. Update producer state (mark as sent)
4. Commit

If the transaction fails, neither the message nor the state is saved.
On retry, the producer checks its state and doesn't re-send.

### Consumer deduplication

| Store | Pros | Cons |
|---|---|---|
| **Database** (unique constraint) | Durable; SQL; transactional | Latency (disk I/O) |
| **Redis** (SET if not exists) | Fast; in-memory | Ephemeral; must persist or tolerate loss |
| **Memory** (set) | Fastest; no I/O | Lost on crash |
| **Message queue** (dedup window) | Built-in (SQS FIFO) | Queue-specific; limited window |

### Exactly-once in Kafka (the hard part)

Kafka supports exactly-once at the **producer-consumer** level:

1. **Transactional producer**: write to multiple partitions in one transaction
2. **Consumer group**: use `isolation.level=read_committed` (only read committed messages)
3. **Idempotent producer**: `enable.idempotence=true` (sequence numbers per partition)
4. **Transactional processing**: read from Kafka → process → write to Kafka (all in one transaction)

Without Kafka transactions, exactly-once means:
- At-least-once delivery + idempotent consumer
- Deduplication on every write

### At-least-once + idempotent consumer (the practical approach)

True exactly-once (Kafka transactions, database transactions) is hard.
The practical solution: at-least-once delivery + idempotent consumer.

```python
def process(message):
    with db.transaction():
        if db.query("SELECT id FROM processed WHERE id = ?", message.id):
            return  # already processed
        db.query("INSERT INTO processed (id) VALUES (?)", message.id)
        # ... actual business logic ...
```

This is "exactly-once semantics" (EOS) — messages may be delivered
multiple times, but the effect is the same as if delivered once.

### End-to-end exactly-once

```
Producer (idempotent) → Queue (dedup window) → Consumer (dedup) → Destination (idempotent)
```

Every step in the pipeline must support deduplication.
If any step loses the dedup state, duplicates can slip through.

## 3. Real implementations

| System | Exactly-once | How |
|---|---|---|
| **Kafka** | Transactions (producer + consumer) | Transactional API; `read_committed` isolation level |
| **SQS FIFO** | Built-in dedup | Content-based deduplication or deduplication ID |
| **RabbitMQ** | Publisher confirms + consumer ack | No native EOS; achieve via idempotent consumer |
| **Pulsar** | Exactly-once processing | Transactional producer + consumer; function framework |
| **Database** | ACID transactions | Primary key uniqueness; INSERT ... ON CONFLICT DO NOTHING |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Approach | Kafka transactions (real EOS) | At-least-once + idempotent consumer | Strong → Kafka transactions; simple → idempotent consumer |
| Dedup store | Database (durable) | Redis (fast) | Durable → database; low-latency → Redis |
| Dedup window | Unlimited | Limited (TTL-based) | Permanent → unlimited; cheap → TTL-based |
| Producer | Idempotent (sequence numbers) | Non-idempotent (no dedup) | Must be reliable → idempotent |
| Consumer | Manual dedup (code) | Built-in (SQS FIFO) | Custom → manual; simple → SQS FIFO |

## 5. Exercises

1. **Idempotent consumer**: Store processed message IDs; skip duplicates.
2. **Dedup window**: Store IDs with TTL (e.g. 24 hours); evict old IDs automatically.
3. **Transactional producer**: Write message + update state in one database transaction.
4. **SQS-style dedup**: Content-based hashing; reject duplicate content within a window.
5. **End-to-end check**: Simulate producer → queue → consumer with retries; verify no duplicates.

## 6. References

- [Kafka exactly-once semantics](https://kafka.apache.org/documentation/#semantics)
- [Idempotent message processing](https://www.baeldung.com/cs/idempotent-message-processing)
- [SQS FIFO deduplication](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/how-dead-letter-queue.html)
- [Pulsar exactly-once](https://pulsar.apache.org/docs/en/next/producer-api/)
- [Exactly-once delivery (Martin Fowler)](https://www.martinfowler.com/articles/201701-event-driven.html)