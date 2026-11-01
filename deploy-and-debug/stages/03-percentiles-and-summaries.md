# Stage 3: percentiles and summaries

**Course:** Deploy & Debug (`deploy-and-debug`)
**File:** `metrics.py`
**Tags:** observability

## The mechanism

Percentiles are not averages: sort and take the rank. p99 is where the outliers live.

## Tests

The tester runs your code like this:

```bash
forja test deploy-and-debug --stage 3
# same as:
python3 codecraft/cli.py run deploy-and-debug --stage 3
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> p50 and p99 of [1,2,3,4,100].

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage deploy-and-debug 4
```
