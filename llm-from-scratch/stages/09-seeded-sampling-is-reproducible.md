# Stage 9: seeded sampling is reproducible

**Course:** LLM From Scratch (`llm-from-scratch`)
**File:** `sampling.py`
**Tags:** determinism

## The mechanism

Thread the Random instance you were handed through every sampling call; never touch the global random module.

## Tests

The tester runs your code like this:

```bash
forja test llm-from-scratch --stage 9
# same as:
python3 codecraft/cli.py run llm-from-scratch --stage 9
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> one seed twice gives the same 50 samples.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage llm-from-scratch 10
```
