# Stage 10: the gate, and the report you can diff

**Course:** Evals From Scratch (`evals-from-scratch`)
**File:** `stage_10.py`
**Tags:** regression, decisions

## The mechanism

Implement gate: match by id, per-slice floors, a paired interval, three decisions with reasons, and a stable JSON.

## Tests

The tester runs your code like this:

```bash
forja test evals-from-scratch --stage 10
# same as:
python3 codecraft/cli.py run evals-from-scratch --stage 10
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> Better overall, one tenant halved: what does the gate say?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- a floor breach decides the run whatever the mean says
- rows without a partner are dropped and counted, never paired by position

## Next

When this stage is green:

```bash
forja stage evals-from-scratch 11
```
