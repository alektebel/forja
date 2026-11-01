# Stage 5: retries, and the effect that must not happen twice

**Course:** Agents From Scratch (`agents-from-scratch`)
**File:** `stage_05.py`
**Tags:** retries, idempotency

## The mechanism

Implement the error taxonomy, classify, backoff, with_retry and Effect.once: retry the condition, never the symptom, and give every effect a key.

## Tests

The tester runs your code like this:

```bash
forja test agents-from-scratch --stage 5
# same as:
python3 codecraft/cli.py run agents-from-scratch --stage 5
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> The tool charged the card and the response was lost, so the caller retries: how many charges?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- a bad argument does not get better by waiting
- sleep is injected, and there is no sleep after the last attempt
- the key is what makes a retry safe, and it has to be canonical

## Next

When this stage is green:

```bash
forja stage agents-from-scratch 6
```
