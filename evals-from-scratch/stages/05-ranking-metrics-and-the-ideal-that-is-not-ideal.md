# Stage 5: ranking metrics, and the ideal that is not ideal

**Course:** Evals From Scratch (`evals-from-scratch`)
**File:** `stage_05.py`
**Tags:** retrieval, metrics

## The mechanism

Implement recall_at_k, mrr, dcg and ndcg with the IDCG over every judged document, not over the retrieved pool.

## Tests

The tester runs your code like this:

```bash
forja test evals-from-scratch --stage 5
# same as:
python3 codecraft/cli.py run evals-from-scratch --stage 5
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> Retrieved gains [1,1] when a 3-gain document exists: nDCG?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- IDCG sorts ALL keys in the relevance map by gain
- a key the map does not mention has gain 0

## Next

When this stage is green:

```bash
forja stage evals-from-scratch 6
```
