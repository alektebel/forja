# Stage 6: the judge, and the order you showed it in

**Course:** Evals From Scratch (`evals-from-scratch`)
**File:** `stage_06.py`
**Tags:** judge, bias

## The mechanism

Implement run_pairwise: judge every pair twice, in both orders, and report the debiased win rate and the flip rate.

## Tests

The tester runs your code like this:

```bash
forja test evals-from-scratch --stage 6
# same as:
python3 codecraft/cli.py run evals-from-scratch --stage 6
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> A judge that always answers 'first': what win rate does the swapped run report?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- each judged order contributes half a win to each side
- a flip is the same answer winning in both orders

## Next

When this stage is green:

```bash
forja stage evals-from-scratch 7
```
