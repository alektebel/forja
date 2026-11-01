# Stage 7: Request batching — size/time windows, DataLoader, pipeline

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `request_batching.py`
**Tags:** moderate, throughput, threads

## The mechanism

Implement SizeBatcher, TimeBatcher (window flush thread), DataLoader (dedupe same-window keys into one fetch) and PipelineBatcher.

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 7
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 7
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> three threads ask for key 'user:1' in one window — how many fetches?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- add() returns the flushed batch when len hits batch_size
- DataLoader: one Event per waiter, one dispatch timer per window
- stop() must flush what is still pending in the buffer

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 8
```
