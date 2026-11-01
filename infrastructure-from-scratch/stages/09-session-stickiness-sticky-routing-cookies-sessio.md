# Stage 9: Session stickiness — sticky routing, cookies, session store

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `session_stickiness.py`
**Tags:** moderate, sessions, routing

## The mechanism

Implement StickyRouter (hash → backend, health-aware), StickyLoadBalancer (SERVERID cookie affinity) and SessionStore (create/get/update/delete with TTL).

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 9
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 9
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> a backend dies mid-session — what does the user lose, and when?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- route() skips unhealthy backends and remaps that session
- cookie present → honour it; absent → pick and mint one
- session TTL checked on read, lazily

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 10
```
