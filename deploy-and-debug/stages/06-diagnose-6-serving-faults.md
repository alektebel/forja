# Stage 6: diagnose 6 serving faults

**Course:** Deploy & Debug (`deploy-and-debug`)
**File:** `diagnose.py`
**Tags:** diagnosis

## The mechanism

Map each fault to its metric signature: KV full -> cache-miss spike; overload -> queue growth.

## Tests

The tester runs your code like this:

```bash
forja test deploy-and-debug --stage 6
# same as:
python3 codecraft/cli.py run deploy-and-debug --stage 6
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> the signature of a full KV cache.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage deploy-and-debug 7
```
