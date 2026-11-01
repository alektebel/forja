# Stage 4: stable softmax

**Course:** LLM From Scratch (`llm-from-scratch`)
**File:** `attention.py`
**Tags:** numerical-stability

## The mechanism

In softmax, subtract the row max before exp: exp(x - max). The result is identical and can never overflow.

## Tests

The tester runs your code like this:

```bash
forja test llm-from-scratch --stage 4
# same as:
python3 codecraft/cli.py run llm-from-scratch --stage 4
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> softmax([1000,1001]) — finite, and sums to 1.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage llm-from-scratch 5
```
