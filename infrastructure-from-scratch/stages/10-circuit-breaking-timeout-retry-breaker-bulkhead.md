# Stage 10: Circuit breaking — timeout, retry, breaker, bulkhead

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `circuit_breaker.py`
**Tags:** complex, resilience, threads

## The mechanism

Implement with_timeout and retry decorators, the CLOSED→OPEN→HALF-OPEN CircuitBreaker, per-tenant Bulkhead semaphores, and BoundedQueue backpressure counting rejections.

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 10
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 10
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> what must a half-open breaker do on its first success?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- failure_threshold trips; recovery_timeout admits one probe
- CircuitBreakerOpenError names the breaker state
- bulkhead: one Semaphore per tenant, acquire(timeout=...)

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 11
```
