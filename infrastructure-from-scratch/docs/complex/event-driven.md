# Event-Driven Architecture — Complex

## 1. What problem does it solve?

In a monolithic app, components call each other synchronously:
```
A → B → C → D
```
If C is slow, A waits. If C fails, A fails.
Tight coupling makes change expensive: modify C → test A, B, D.

Event-driven architecture decouples them:
```
A emits event → [Event Bus] → B listens → C listens → D listens
```
A doesn't know who listens. B doesn't know who emitted the event.
They communicate through events (facts about something that happened).

**The job:** publish facts (events) that subscribers react to,
with ordering guarantees and delivery semantics.

## 2. How does it work?

### Events vs Messages

| Aspect | Message | Event |
|---|---|---|
| **Meaning** | "Do X" (instruction) | "X happened" (fact) |
| **Delivery** | Must be consumed to be useful | Should be consumed, but can be replayed |
| **Receiver** | One receiver (queue) or many (topic) | Many receivers (topic) |
| **History** | Transient (consumed and gone) | Persistent (can be replayed) |

### Event flow

```
Producer → Event Bus (topic) → Subscriber 1
                        → Subscriber 2
                        → Subscriber 3
```

- **Producer**: emits an event (e.g. `order.created`)
- **Event Bus**: stores the event (Kafka topic, Redis pub/sub)
- **Subscriber**: reacts to the event (e.g. update inventory, send email, create analytics record)

### Event schema (what's in an event)

```json
{
  "event_id": "abc123",          // unique ID (for deduplication)
  "event_type": "order.created",  // type or topic
  "timestamp": "2024-01-15T10:30:00Z",
  "version": 1,                  // schema version
  "payload": {
    "order_id": 12345,
    "user_id": 67890,
    "total": 99.99,
    "items": [{"sku": "ABC", "qty": 2}]
  },
  "metadata": {
    "source": "checkout-service",
    "correlation_id": "xyz789"   // trace across services
  }
}
```

### Ordering

Events within a single partition can be ordered, but across partitions there's
no global ordering guarantee.

| Ordering type | Guarantee | Example |
|---|---|---|
| **Global** | All events in timestamp order | Only possible with a single partition (bottleneck) |
| **Partition/key** | Events with the same key are in order | `order_id` → same partition → ordered within partition |
| **Causal** | If A happens before B, B sees A | Must use vector clocks or similar |
| **None** | No ordering guarantee | Fire-and-forget metrics |

### Event routing

| Pattern | Description |
|---|---|
| **Pub/sub** | All subscribers get all events |
| **Topic** | Subscribers subscribe to specific topics (e.g. `order.*`, `order.created`) |
| **Content-based** | Route based on event content (e.g. if `total > 1000` → high-priority queue) |
| **Aggregator** | Collect related events, merge into a single update |

### Exactly-once vs At-least-once in event-driven

| Semantic | How to achieve | Cost |
|---|---|---|
| **At-most-once** | Auto-ack; don't store event ID | Simple but lossy |
| **At-least-once** | Store event ID; redeliver unacked; deduplicate on receive | Common; requires consumer dedup |
| **Exactly-once** | Idempotent consumer + transactional producer + dedup | Hard; usually at-least-once with idempotent consumers |

## 3. Real implementations

| Implementation | Type | Notes |
|---|---|---|
| **Apache Kafka** | Event log/streams | Partitioned log; consumer groups; exactly-once semantics |
| **Redis Streams** | Event log | Simple; embedded in Redis; limited durability |
| **NATS JetStream** | Event log + pub/sub | Ultra-low latency; durable streams |
| **Apache Pulsar** | Event log + pub/sub | Multi-tenancy; tiered storage; cloud-native |
| **Amazon SNS + SQS** | Pub/sub + queue | SNS = fan-out; SQS = durable queue behind SNS |
| **RabbitMQ** | Message queue with exchange routing | AMQP; flexible routing; DLQ; TTL |
| **AWS EventBridge** | Event bus | Cloud-native; event filtering; integration with other AWS services |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Delivery | At-least-once | Exactly-once | Financial transfers → exactly-once; logs → at-least-once |
| Ordering | Global (single partition) | Partition (per-key) | Global ordering required → single partition; per-key → partitioned |
| Storage | In-memory (Redis) | Disk-backed (Kafka) | Ephemeral → Redis; replay needed → Kafka |
| Routing | Fan-out (all get all events) | Content-based filter | Need filtering → EventBridge; simple → SNS/Kafka topic |
| Schema evolution | Forward-compatible (additive) | Versioned schemas | Avoid breaking changes → additive; need validation → versioned |

## 5. Exercises

1. **Event bus**: A Python server that accepts events; subscribers subscribe to topics; all subscribers get all events.
2. **Topic filtering**: Subscribers subscribe to patterns (e.g. `order.*`, `order.created`); only matching events delivered.
3. **Consumer group**: Multiple consumers per topic; each message delivered to exactly one consumer in the group.
4. **Event replay**: Store events with offsets; allow a new consumer to start from a specific offset.
5. **Deduplication**: Store consumed event IDs; skip duplicate events (at-least-once → effectively exactly-once).

## 6. References

- [Kafka documentation](https://kafka.apache.org/documentation/)
- [Event-driven architecture patterns (Martin Fowler)](https://www.enterpriseintegrationpatterns.com/patterns/messaging/AsyncRequestReply.html)
- [Domain-driven design: events (Eric Evans)](https://www.infoq.com/articles/domain-model-driven-design/)
- [Event sourcing: "Event Sourcing" (Udi Dahan)](https://cqrs.files.wordpress.com/2010/11/cqrs_documents.pdf)
- [NATS JetStream documentation](https://docs.nats.io/nats-concepts/jetstream)
- [Exactly-once delivery in Kafka](https://www.confluent.io/blog/exactly-once-semantics-are-possible/)