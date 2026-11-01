# Stage 1: the loop, and the transcript that is the state

**Course:** Agents From Scratch (`agents-from-scratch`)
**File:** `stage_01.py`
**Tags:** agent-loop, state

## The mechanism

Implement run_agent: call the model with the transcript, append the tool call and its result as a pair, stop on a final answer, and count what you showed the model.

## Tests

The tester runs your code like this:

```bash
forja test agents-from-scratch --stage 1
# same as:
python3 codecraft/cli.py run agents-from-scratch --stage 1
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> The model asks for a tool on every turn and never answers, and max_steps is 3: how many times was the model called, and what does the run return?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- the transcript is the state: the next call is built from it, not from the task
- a call and its result are one unit, in that order
- hitting the cap is a result, not the moment to squeeze in one more turn

## Next

When this stage is green:

```bash
forja stage agents-from-scratch 2
```
