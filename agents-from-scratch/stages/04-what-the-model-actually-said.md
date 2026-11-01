# Stage 4: what the model actually said

**Course:** Agents From Scratch (`agents-from-scratch`)
**File:** `stage_04.py`
**Tags:** parsing, robustness

## The mechanism

Implement parse_decision and run_parsed: unwrap a fence, take the first balanced JSON object, normalise the key names, and give the MODEL a bounded number of repairs.

## Tests

The tester runs your code like this:

```bash
forja test agents-from-scratch --stage 4
# same as:
python3 codecraft/cli.py run agents-from-scratch --stage 4
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> The reply is {"tool": "write_file", "args": "path=a.txt text=hi"}: a tool call, or a problem?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- repair the envelope, never the meaning
- the transcript keeps what the model said, verbatim, and the note that follows it is a user message
- a repair loop without a cap waits forever for a model that cannot comply

## Next

When this stage is green:

```bash
forja stage agents-from-scratch 5
```
