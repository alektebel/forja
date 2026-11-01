# Stage 1: pair counts and non-overlapping merges

**Course:** LLM From Scratch (`llm-from-scratch`)
**File:** `tokenizer.py`
**Tags:** merging

## The mechanism

Write get_pair_counts as a dict of adjacent pairs, then merge_pair with an index that SKIPS PAST each merge, so [1,1,1] becomes [9,1] and not two overlapping merges.

## Tests

The tester runs your code like this:

```bash
forja test llm-from-scratch --stage 1
# same as:
python3 codecraft/cli.py run llm-from-scratch --stage 1
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> In [1,1,1,2], how many adjacent (1,1) pairs? (two, not three)

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage llm-from-scratch 2
```
