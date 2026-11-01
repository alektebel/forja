# Stage 9: budgets, and why the run stopped

**Course:** Agents From Scratch (`agents-from-scratch`)
**File:** `stage_09.py`
**Tags:** budgets, failure

## The mechanism

Implement tokens_for, Budgets, BudgetExhausted and run_budgeted: refuse the call that would exceed a cap, and keep what the agent learned.

## Tests

The tester runs your code like this:

```bash
forja test agents-from-scratch --stage 9
# same as:
python3 codecraft/cli.py run agents-from-scratch --stage 9
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> steps is 3 and the model never answers: how many model calls were made, and what is in the answer?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- stop before the call, or the count reads cap+1
- tokens are charged in both directions, and tool output is the half people forget
- the clock is injected: time.time() makes this untestable and nondeterministic

## Next

When this stage is green:

```bash
forja stage agents-from-scratch 10
```
