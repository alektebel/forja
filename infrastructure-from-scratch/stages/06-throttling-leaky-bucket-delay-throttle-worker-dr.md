# Stage 6: Throttling — leaky bucket, delay throttle, worker drain

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `throttling.py`
**Tags:** moderate, backpressure, scheduling

## The mechanism

Implement LeakyBucket (capacity + drain_rate), DelayThrottler (minimum interval per key) and ThrottledWorker (rate-limited task pool).

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 6
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 6
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> token bucket lets bursts through — which of these never does?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- drain lazily: level -= (now - last_drain) * rate, floor 0
- delay throttle records last slot per key, next slot = last + 1/rate
- worker: one dispatch thread, results keyed by task id

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 7
```
