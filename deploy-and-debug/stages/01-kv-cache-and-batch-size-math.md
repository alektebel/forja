# Stage 1: KV cache and batch-size math

**Course:** Deploy & Debug (`deploy-and-debug`)
**File:** `capacity.py`
**Tags:** capacity

## The mechanism

KV cache bytes/token = 2 * layers * KV_HEADS * head_dim * bytes. Using query heads sizes the fleet 4x too large.

## Tests

The tester runs your code like this:

```bash
forja test deploy-and-debug --stage 1
# same as:
python3 codecraft/cli.py run deploy-and-debug --stage 1
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> bytes/token for Llama-3-8B (8 KV heads).

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage deploy-and-debug 2
```
