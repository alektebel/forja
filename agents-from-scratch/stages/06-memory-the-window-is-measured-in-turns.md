# Stage 6: memory: the window is measured in turns

**Course:** Agents From Scratch (`agents-from-scratch`)
**File:** `stage_06.py`
**Tags:** memory, multi-turn

## The mechanism

Implement Session: the full transcript, a bounded view in whole turns, pins that ride in the system message, and ask().

## Tests

The tester runs your code like this:

```bash
forja test agents-from-scratch --stage 6
# same as:
python3 codecraft/cli.py run agents-from-scratch --stage 6
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> window=1 and the last turn made a tool call: what exactly does the model receive?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- a turn is a user message plus everything until the next one
- a view that cuts a call from its result is a transcript no API accepts
- view() hands out copies: the caller edits its own list

## Next

When this stage is green:

```bash
forja stage agents-from-scratch 7
```
