# Stage 15: Eventual consistency — CRDTs, vector clocks, read repair

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `eventual_consistency.py`
**Tags:** complex, consistency, replication

## The mechanism

Implement GCounter (merge by per-node max), LWWRegister (timestamp wins), VectorClock with happened_before, Replica, and EventuallyConsistentStore with quorum writes and read repair.

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 15
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 15
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> two replicas tick their own clock — is either's write before the other's?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- merge: {k: max(a.get(k,0), b.get(k,0)) for k in a|b}
- happened_before: every component ≤ and at least one <
- read repair: quorum winner written back to lagging replicas

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 16
```
