# Stage 3: deterministic assertions

**Course:** Evals From Scratch (`evals-from-scratch`)
**File:** `stage_03.py`
**Tags:** assertions, error-handling

## The mechanism

Implement check/json_valid/has_fields/run_checks/summarise with three outcome states, and errors that never become passes.

## Tests

The tester runs your code like this:

```bash
forja test evals-from-scratch --stage 3
# same as:
python3 codecraft/cli.py run evals-from-scratch --stage 3
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> A predicate raises on record 1 of 2, with 4 checks: pass rate?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- try/except: pass around the loop is how every broken check turns green
- a truthy non-tuple is not a pass — the report needs the reason

## Next

When this stage is green:

```bash
forja stage evals-from-scratch 4
```
