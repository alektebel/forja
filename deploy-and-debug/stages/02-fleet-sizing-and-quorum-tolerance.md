# Stage 2: fleet sizing and quorum tolerance

**Course:** Deploy & Debug (`deploy-and-debug`)
**File:** `capacity.py`
**Tags:** capacity, availability

## The mechanism

Size the fleet from concurrency and tokens/s, then subtract the failure tolerance R+W>N implies.

## Tests

The tester runs your code like this:

```bash
forja test deploy-and-debug --stage 2
# same as:
python3 codecraft/cli.py run deploy-and-debug --stage 2
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> how many nodes can die and quorum still hold.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage deploy-and-debug 3
```
