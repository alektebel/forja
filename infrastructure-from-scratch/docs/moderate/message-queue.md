# Message Queue — Moderate

## 1. What problem does it solve?

Two services communicating synchronously:
```
Client → Service A → Service B → Client
```
If Service B is down, Service A's request fails. The client gets an error.
And the work is lost.

A message queue decouples them:
```
Client → Service A → [Queue] → Service B
```
Service A publishes to the queue and immediately returns.
Service B consumes from the queue at its own pace.
If Service B is down, messages accumulate in the queue. When Service B
recovers, it continues processing.

**The job:** reliably deliver work from producers to consumers, with
guarantees about delivery semantics.

## 2. How does it work?

### Delivery semantics

| Semantic | Guarantee | When to use | How to achieve |
|---|---|---|---|
| **At-most-once** | A message is delivered zero or one time | Metrics, logs where duplicates don't matter | Auto-acknowledge on receive; no retry on failure |
| **At-least-once** | A message is delivered one or more times | Payments, order processing where misses matter | Acknowledge after processing; redeliver unacked messages |
| **Exactly-once** | A message is delivered exactly once | Financial transfers; state machines | Idempotency keys + deduplication + transactional producer |

### Queue model

```
Producer → Queue (topic) → Consumer
```

- **Point-to-point (queue):** one consumer per message (work queue model)
- **Pub/Sub (topic):** one copy per consumer (fan-out model)
- **Stream (log):** persistent, replayable; consumers read from any offset

### Retry and DLQ

When a consumer fails to process a message:
1. Retry N times with exponential backoff
2. After N failures, move to Dead Letter Queue (DLQ)
3. Later, inspect DLQ messages manually or re-process

```
Queue → Consumer → [fail] → Retry 1 (1s) → [fail] → Retry 2 (2s) → [fail] → Retry 3 (4s) → [fail] → DLQ → inspect
```

### Idempotency

At-least-once delivery means messages can be redelivered.
The consumer must be idempotent: processing the same message twice
produces the same result as processing it once.

**Idempotency patterns:**
1. **Unique key:** store processed message IDs; skip duplicates
2. **Upsert:** write with a primary key; second write = same data
3. **State machine:** check current state; only allow valid transitions

```python
def consume(message):
    if message.id in processed_ids:
        return  # duplicate — skip
    result = process(message)
    processed_ids.add(message.id)
    db.save(idempotency_key=message.id, result=result)
```

### Acknowledgements

| Type | When acked | Effect |
|---|---|---|
| **Manual** | After successful processing | Message stays in queue until acked; redelivered on crash |
| **Auto** | Immediately on receive | Message removed from queue on delivery; lost on crash |
| **Conditional** | On success or explicit NACK | Success → removed; failure → redeliver or DLQ |

## 3. Real implementations

| Implementation | Model | Notes |
|---|---|---|
| **Apache Kafka** | Log/stream | Partitioned, persistent, replayable; used for event sourcing, streaming |
| **RabbitMQ** | Queue + pub/sub | AMQP protocol; exchange routing; dead-letter exchanges |
| **Amazon SQS** | Queue (FIFO or standard) | Managed; at-least-once; visibility timeout (retry) |
| **Amazon SNS** | Pub/sub | Fan-out; push notifications |
| **Redis Streams** | Stream | Simple; embedded in Redis; not as durable as Kafka |
| **NATS** | Pub/sub + queue | Ultra-low latency; JetStream for persistence |
| **Apache Pulsar** | Log + pub/sub | Cloud-native; tiered storage; multi-tenancy |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Delivery | At-most-once | At-least-once | Critical work → at-least-once; metrics → at-most-once |
| Acknowledgement | Auto | Manual | Reliability matters → manual ack |
| Ordering | FIFO per partition (Kafka) | No guarantee (SQS standard) | Ordering matters → Kafka/fIFO queue |
| Persistence | Disk (Kafka) | In-memory (Redis Streams) | Durability → disk; temp work → memory |
| Replay | Consumer offset (Kafka) | No replay (RabbitMQ) | Need replay → Kafka; fire-and-forget → RabbitMQ |

## 5. Exercises

1. **Simple queue**: A Python server that accepts messages; consumers pull from it; at-most-once delivery.
2. **At-least-once queue**: Implement manual ack; redeliver unacked messages after a timeout.
3. **Dead letter queue**: After 3 failed deliveries, move to DLQ; separate consumer for DLQ.
4. **Idempotent consumer**: Store processed message IDs in an in-memory set; skip duplicates.
5. **Pub/sub**: Multiple consumers per topic; each receives all messages (fan-out).

## 6. References

- [Apache Kafka documentation](https://kafka.apache.org/documentation/)
- [RabbitMQ documentation](https://www.rabbitmq.com/documentation.html)
- [Amazon SQS documentation](https://docs.aws.amazon.com/sqs/)
- [At-least-once delivery pattern](https://docs.microsoft.com/en-us/azure/architecture/patterns/at-least-once-processing)
- [Idempotent message processing](https://www.baeldung.com/cs/idempotent-message-processing)
- [NATS JetStream documentation](https://docs.nats.io/nats-concepts/jetstream)