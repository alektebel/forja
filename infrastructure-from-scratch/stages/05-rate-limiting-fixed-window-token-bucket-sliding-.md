# Stage 5: Rate limiting — fixed window, token bucket, sliding window

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `rate_limiter.py`
**Tags:** moderate, backpressure, http

## The mechanism

Implement FixedWindow, TokenBucket (capacity + refill_rate), SlidingWindowLog and SlidingWindowCounter limiters.

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 5
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 5
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> why does fixed window allow a 2× burst at the boundary?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- window key: int(now // window_seconds)
- token bucket: refill = (now - last) * rate, cap at capacity
- sliding counter = weighted current + previous window

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 6
```
