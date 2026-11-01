# Stage 12: budget-based auto-rollback

**Course:** Deploy & Debug (`deploy-and-debug`)
**File:** `rollout.py`
**Tags:** rollout

## The mechanism

Auto-rollback on burn-rate, not a single blip — a 30-second spike must not page.

## Tests

The tester runs your code like this:

```bash
forja test deploy-and-debug --stage 12
# same as:
python3 codecraft/cli.py run deploy-and-debug --stage 12
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> whether a 30s spike trips a 1h-budget alarm.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage deploy-and-debug 13
```
