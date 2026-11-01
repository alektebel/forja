# Stage 5: SLOs, budgets and burn rate

**Course:** Deploy & Debug (`deploy-and-debug`)
**File:** `metrics.py`
**Tags:** slo

## The mechanism

SLO is an objective over a window; error budget = 1 - SLO; burn rate is how fast you are spending it.

## Tests

The tester runs your code like this:

```bash
forja test deploy-and-debug --stage 5
# same as:
python3 codecraft/cli.py run deploy-and-debug --stage 5
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> the error budget for 99.9% over 30 days.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage deploy-and-debug 6
```
