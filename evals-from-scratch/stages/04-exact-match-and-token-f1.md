# Stage 4: exact match and token F1

**Course:** Evals From Scratch (`evals-from-scratch`)
**File:** `stage_04.py`
**Tags:** metrics, normalisation

## The mechanism

Implement normalize (SQuAD-style), exact_match, token_f1 with a multiset overlap, corpus_f1 pooled and mean_f1 per pair.

## Tests

The tester runs your code like this:

```bash
forja test evals-from-scratch --stage 4
# same as:
python3 codecraft/cli.py run evals-from-scratch --stage 4
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> F1 of prediction 'cat sat' against gold 'cat'?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- normalise both sides, always, in one place
- 0/0 is not a perfect answer; empty scores 0.0

## Next

When this stage is green:

```bash
forja stage evals-from-scratch 5
```
