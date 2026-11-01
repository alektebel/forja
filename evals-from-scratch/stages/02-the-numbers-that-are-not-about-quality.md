# Stage 2: the numbers that are not about quality

**Course:** Evals From Scratch (`evals-from-scratch`)
**File:** `stage_02.py`
**Tags:** metrics, operations

## The mechanism

Implement refusal_rate, latency_summary (nearest-rank percentiles), token_summary and operational_report.

## Tests

The tester runs your code like this:

```bash
forja test evals-from-scratch --stage 2
# same as:
python3 codecraft/cli.py run evals-from-scratch --stage 2
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> 20 latencies, 10..200: what is p95 by nearest rank?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- an errored row is not a refusal — keep it out of that denominator
- p95 is the sample at ceil(0.95 * n) - 1, not an interpolation

## Next

When this stage is green:

```bash
forja stage evals-from-scratch 3
```
