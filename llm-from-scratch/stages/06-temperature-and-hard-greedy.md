# Stage 6: temperature and hard greedy

**Course:** LLM From Scratch (`llm-from-scratch`)
**File:** `sampling.py`
**Tags:** boundary, determinism

## The mechanism

temperature 0 is hard greedy: one-hot at the argmax, -inf everywhere else. Temperature divides the logits.

## Tests

The tester runs your code like this:

```bash
forja test llm-from-scratch --stage 6
# same as:
python3 codecraft/cli.py run llm-from-scratch --stage 6
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> sample(temp=0) is deterministic — the tail can never fire.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage llm-from-scratch 7
```
