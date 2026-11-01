# Stage 8: top-p keeps the crossing token

**Course:** LLM From Scratch (`llm-from-scratch`)
**File:** `sampling.py`
**Tags:** boundary

## The mechanism

top_p keeps the smallest set whose cumulative probability reaches p, INCLUDING the token that crosses it (>= not >).

## Tests

The tester runs your code like this:

```bash
forja test llm-from-scratch --stage 8
# same as:
python3 codecraft/cli.py run llm-from-scratch --stage 8
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> [.5,.3,.15,.05] at p=.9 keeps the .15 token.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage llm-from-scratch 9
```
