# Stage 8: diagnose 5 store faults

**Course:** Deploy & Debug (`deploy-and-debug`)
**File:** `diagnose.py`
**Tags:** diagnosis

## The mechanism

Store faults: node down, hint backlog, and gossip disagreement each have a distinct fingerprint.

## Tests

The tester runs your code like this:

```bash
forja test deploy-and-debug --stage 8
# same as:
python3 codecraft/cli.py run deploy-and-debug --stage 8
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> the fingerprint of hinted-handoff backlog.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage deploy-and-debug 9
```
