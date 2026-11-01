# Stage 11: fields, not strings

**Course:** Evals From Scratch (`evals-from-scratch`)
**File:** `stage_11.py`
**Tags:** extraction, structured, metrics

## The mechanism

Implement coerce, compare_extraction (correct/incorrect/missing/extra), micro_scores, macro_f1, schema_valid and extraction_report over a typed schema.

## Tests

The tester runs your code like this:

```bash
forja test evals-from-scratch --stage 11
# same as:
python3 codecraft/cli.py run evals-from-scratch --stage 11
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> Five correct line-item cells and one wrong vendor: micro vs macro F1?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- coerce through the schema before comparing — '100' is 100.0
- incorrect is both FP and FN; extra is FP only; missing is FN only
- macro averages per-field-name F1 with list indices collapsed to [*]

## Next

When this stage is green:

```bash
forja stage evals-from-scratch 12
```
