# Stage 10: liveness vs readiness probes

**Course:** Deploy & Debug (`deploy-and-debug`)
**File:** `rollout.py`
**Tags:** lifecycle

## The mechanism

Liveness RESTARTS a hung process; readiness REMOVES it from the load balancer. Do not confuse the two.

## Tests

The tester runs your code like this:

```bash
forja test deploy-and-debug --stage 10
# same as:
python3 codecraft/cli.py run deploy-and-debug --stage 10
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> what a failing readiness probe does.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage deploy-and-debug 11
```
