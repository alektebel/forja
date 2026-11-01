# Stage 10: the trace, and the audit that reads the world

**Course:** Agents From Scratch (`agents-from-scratch`)
**File:** `stage_10.py`
**Tags:** audit, determinism

## The mechanism

Implement trace_of, to_jsonl, snapshot, diff_snapshots, unchanged, no_leak, no_new_match and audit: count what happened and grade the filesystem, not the story.

## Tests

The tester runs your code like this:

```bash
forja test agents-from-scratch --stage 10
# same as:
python3 codecraft/cli.py run agents-from-scratch --stage 10
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> Two runs of the same scripted model: are their logs identical, and what does a detector report for a line that was already in the file?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- counted, not copied: a log that contains the payload cannot be mailed or diffed
- a leak travels base64-encoded, hex-encoded, or reversed
- the past is not the agent's fault: only lines that were ADDED count

## Next

When this stage is green:

```bash
forja stage agents-from-scratch 11
```
