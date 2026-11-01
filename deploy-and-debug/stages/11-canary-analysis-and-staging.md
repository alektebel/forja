# Stage 11: canary analysis and staging

**Course:** Deploy & Debug (`deploy-and-debug`)
**File:** `rollout.py`
**Tags:** rollout

## The mechanism

Canary: compare canary against control on the same traffic, with enough samples to see the effect.

## Tests

The tester runs your code like this:

```bash
forja test deploy-and-debug --stage 11
# same as:
python3 codecraft/cli.py run deploy-and-debug --stage 11
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> whether 90 samples can detect a 2% regression.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage deploy-and-debug 12
```
