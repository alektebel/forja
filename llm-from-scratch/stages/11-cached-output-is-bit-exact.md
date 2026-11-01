# Stage 11: cached output is bit-exact

**Course:** LLM From Scratch (`llm-from-scratch`)
**File:** `kv_cache.py`
**Tags:** exactness

## The mechanism

cached_step must reproduce recompute_step to <1e-9: append the new K/V and attend over ALL cached rows — read the cache.

## Tests

The tester runs your code like this:

```bash
forja test llm-from-scratch --stage 11
# same as:
python3 codecraft/cli.py run llm-from-scratch --stage 11
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> dropping the last key must change the output.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage llm-from-scratch 12
```
