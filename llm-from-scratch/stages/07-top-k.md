# Stage 7: top-k

**Course:** LLM From Scratch (`llm-from-scratch`)
**File:** `sampling.py`
**Tags:** ordering, boundary

## The mechanism

top_k keeps the k largest and breaks ties by smallest index, keeping BOTH tied values.

## Tests

The tester runs your code like this:

```bash
forja test llm-from-scratch --stage 7
# same as:
python3 codecraft/cli.py run llm-from-scratch --stage 7
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> top-2 of [1,3,3,2] keeps indices 1 and 2.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage llm-from-scratch 8
```
