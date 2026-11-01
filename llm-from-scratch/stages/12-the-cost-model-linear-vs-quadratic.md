# Stage 12: the cost model: linear vs quadratic

**Course:** LLM From Scratch (`llm-from-scratch`)
**File:** `kv_cache.py`
**Tags:** cost-model

## The mechanism

Count interactions: recompute is O(t*d) per step (quadratic overall), the cache is O(d) plus the append (linear).

## Tests

The tester runs your code like this:

```bash
forja test llm-from-scratch --stage 12
# same as:
python3 codecraft/cli.py run llm-from-scratch --stage 12
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> doubling the prompt multiplies prefill work by ~4.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage llm-from-scratch 13
```
