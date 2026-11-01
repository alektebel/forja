# Stage 5: attention weights and the causal mask

**Course:** LLM From Scratch (`llm-from-scratch`)
**File:** `attention.py`
**Tags:** masking, exactness

## The mechanism

Apply the causal mask as -inf BEFORE the softmax, so each row still sums to 1 and position 0 attends only to itself.

## Tests

The tester runs your code like this:

```bash
forja test llm-from-scratch --stage 5
# same as:
python3 codecraft/cli.py run llm-from-scratch --stage 5
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> the output row for position 0 equals V[0].

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage llm-from-scratch 6
```
