# Distributed Transactions (Sagas) — Extremely Complex

## 1. What problem does it solve?

ACID transactions work when a single database controls the data:
```sql
BEGIN TRANSACTION;
  UPDATE accounts SET balance = balance - 100 WHERE id = 1;
  UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;
```

In microservices, each service owns its own database. No distributed ACID:
```
Service A (orders DB)  →  Service B (inventory DB)  →  Service C (payments DB)
```
Service A can't participate in Service B's transaction.

A saga coordinates the business transaction across services without 2PC:
- **Compensating transactions**: if a step fails, undo the work of previous steps
- No global lock; each service operates independently

**The job:** ensure that either all services commit their changes,
or all services undo their changes, with minimal locking and
maximum availability.

## 2. How does it work?

### Choreography (event-driven)

```
OrderService → [order.created] → InventoryService
InventoryService → [items.reserved] → PaymentService
PaymentService → [payment.paid] → OrderService (confirm)
PaymentService → [payment.failed] → InventoryService (release)
```

Each step emits an event that triggers the next step.
If a step fails, it emits a compensating event.

### Orchestrator (central coordinator)

```
                ┌─────────────┐
                │  Orchestrator │
                └──────┬──────┘
           create      │      cancel
              ▼        │        ▲
       ┌──────────┐    │    ┌──────────┐
       │ Create   │    │    │ Cancel   │
       │ Order    │◄───┘    │ Order    │
       └──────────┘         └──────────┘
              │
           reserve
              ▼
       ┌──────────┐
       │ Reserve  │
       │ Items    │
       └──────────┘
              │
           pay
              ▼
       ┌──────────┐
       │ Process  │
       │ Payment  │
       └──────────┘
```

The orchestrator calls each step in order; if a step fails, it calls
compensating actions in reverse.

### Compensation (the key challenge)

Every forward action must have a matching compensating action:

| Forward action | Compensating action |
|---|---|
| Create order | Cancel order |
| Reserve items | Release items |
| Process payment | Refund payment |

Compensating actions must be **idempotent**:
- Running them twice produces the same result
- The orchestrator may retry a compensation if it doesn't know if it succeeded

### States

```
PENDING → INITIATING → IN_PROGRESS → COMPLETED
                     ↘ COMPENSATING → CANCELLED
```

If a step fails during `IN_PROGRESS`, transition to `COMPENSATING`
and run all previous steps' compensations in reverse.

### Retry and persistence

The orchestrator persists its state:
- After each step: record state (which steps succeeded, which failed)
- On restart: resume from the last persisted state
- If compensation fails: retry N times; escalate if still failing

## 3. Real implementations

| Implementation | Pattern | Notes |
|---|---|---|
| **AWS Step Functions** | Orchestrator | Visual workflow; retry and compensation built-in; integrates with Lambda, SQS, DynamoDB |
| **Temporal** | Orchestrator | Go/Java/Python SDK; durable execution; retry, compensation, human-in-the-loop |
| **Azure Durable Functions** | Orchestrator | .NET/JavaScript/Python; Azure-native; actor model |
| **Camunda** | Workflow engine | BPMN; orchestrator pattern; self-hosted or cloud |
| **Sagas (Martin Fowler)** | Pattern | Not an implementation; the reference architecture |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Coordination | Choreography (event-driven) | Orchestrator (central) | Simple → choreography; complex (compensation) → orchestrator |
| Consistency | Eventual | Strong (2PC) | No 2PC → eventual; single DB → ACID |
| Compensation | Manual (code) | Automatic (temporal retries) | Custom → manual; robust → automatic |
| State persistence | In-memory | Durable log (Tempo-ral, Step Functions) | Simple → in-memory; production → durable log |
| Retry strategy | Fixed delay | Exponential backoff + jitter | Avoid thundering herd → exponential backoff |

## 5. Exercises

1. **Saga orchestrator**: Implement an orchestrator that calls steps in order; on failure, calls compensations in reverse.
2. **Idempotent compensation**: Store completed compensation IDs; skip if already compensated.
3. **Durable saga**: Persist saga state on disk; resume on restart.
4. **Retry with backoff**: If a step fails, retry N times with exponential backoff before compensating.
5. **Human-in-the-loop**: Pause the saga; wait for manual approval to continue or abort.

## 6. References

- [Sagas (Martin Fowler)](https://microservices.io/patterns/data/saga.html)
- [Temporal documentation](https://docs.temporal.io/)
- [AWS Step Functions documentation](https://docs.aws.amazon.com/step-functions/)
- [Durable execution (Uber's Cadence/Temporal blog)](https://www.uber.com/en-US/blog/durable-execution/)
- [Saga pattern (Azure documentation)](https://learn.microsoft.com/en-us/azure/architecture/reference-architectures/saga/saga)
- [2PC vs Sagas (Martin Kleppmann)](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)