# Stage 10: cache append and shape

**Course:** LLM From Scratch (`llm-from-scratch`)
**File:** `kv_cache.py`
**Tags:** data-structure

## The mechanism

KVCache stores parallel key/value lists; append, and make len/keys/values reflect exactly what was appended.

## Tests

The tester runs your code like this:

```bash
forja test llm-from-scratch --stage 10
# same as:
python3 codecraft/cli.py run llm-from-scratch --stage 10
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> the length after two appends.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage llm-from-scratch 11
```
