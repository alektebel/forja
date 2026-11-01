# Stage 16: Idempotency keys — dedup store, single execution, payments

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `idempotency_keys.py`
**Tags:** complex, delivery, transactions

## The mechanism

Implement IdempotencyStore (get_or_create/complete, TTL, purge_expired), IdempotentHandler (concurrent callers → exactly one execution), and PaymentProcessor (idempotent charges).

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 16
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 16
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> five threads POST the same charge key — how many debits happen?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- PENDING holder executes; late arrivals wait on its result event
- is_new must be False while a record is COMPLETE or IN_PROGRESS
- charge() replays the stored transaction_id for the same key

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 17
```
