# Stage 17: Edge computing — latency routing, middleware, A/B, runtime

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `edge_computing.py`
**Tags:** complex, edge, routing

## The mechanism

Implement LatencyRouter (nearest healthy PoP), EdgeMiddlewarePipeline (auth/geo chain), ABTestRouter (deterministic hashed buckets) and EdgeRuntime (per-function CPU limit, EdgeFunctionError naming the offender).

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 17
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 17
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> why must the A/B bucket hash the user id, not the request?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- route by client latency, skipping mark_unhealthy nodes
- pipeline: middleware calls next_handler or short-circuits a Response
- runtime: run function in a worker, enforce cpu_limit_ms

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 18
```
