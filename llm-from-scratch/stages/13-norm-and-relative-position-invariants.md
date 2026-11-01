# Stage 13: norm and relative-position invariants

**Course:** LLM From Scratch (`llm-from-scratch`)
**File:** `rope.py`
**Tags:** invariants

## The mechanism

Rotate each (x2i, x2i+1) pair by pos*freq; check the norm is preserved and dot(q@p, k@p+d) ignores p entirely.

## Tests

The tester runs your code like this:

```bash
forja test llm-from-scratch --stage 13
# same as:
python3 codecraft/cli.py run llm-from-scratch --stage 13
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> the relative dot product is identical for every p.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage llm-from-scratch 14
```
