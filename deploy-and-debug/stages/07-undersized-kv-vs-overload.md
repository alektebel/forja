# Stage 7: undersized KV vs overload

**Course:** Deploy & Debug (`deploy-and-debug`)
**File:** `diagnose.py`
**Tags:** diagnosis

## The mechanism

Undersized KV and overload look similar — separate them by cache-hit rate and memory, not latency alone.

## Tests

The tester runs your code like this:

```bash
forja test deploy-and-debug --stage 7
# same as:
python3 codecraft/cli.py run deploy-and-debug --stage 7
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> which metric distinguishes the two.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage deploy-and-debug 8
```
