# Stage 8: Connection pooling — acquire/release, exhaustion, idle eviction

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `connection_pooling.py`
**Tags:** moderate, resources, locking

## The mechanism

Implement ConnectionPool (min/max size, acquire_timeout, idle_timeout eviction), PooledConnection as context manager, PoolExhaustedError naming the pool.

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 8
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 8
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> why does acquire() wait on a condition instead of spinning?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- pre-fill min_size in __init__
- exhaustion: wait until deadline, then raise naming max_size
- release() notifies one waiter; eviction drops idle > timeout

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 9
```
