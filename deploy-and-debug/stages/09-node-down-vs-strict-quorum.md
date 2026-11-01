# Stage 9: node down vs strict quorum

**Course:** Deploy & Debug (`deploy-and-debug`)
**File:** `diagnose.py`
**Tags:** diagnosis

## The mechanism

Node down with QUORUM MET (hint backlog) differs from STRICT-quorum failure (write errors).

## Tests

The tester runs your code like this:

```bash
forja test deploy-and-debug --stage 9
# same as:
python3 codecraft/cli.py run deploy-and-debug --stage 9
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> which one still serves reads.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage deploy-and-debug 10
```
