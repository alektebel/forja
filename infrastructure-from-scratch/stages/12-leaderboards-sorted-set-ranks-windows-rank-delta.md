# Stage 12: Leaderboards — sorted set, ranks, windows, rank delta

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `leaderboard.py`
**Tags:** complex, data-structure, ranking

## The mechanism

Implement SortedSet (zadd/zscore/zincrby/zrevrank/zrevrange/zrangebyscore/zcard), Leaderboard with snapshots and rank delta, and WindowedLeaderboard.

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 12
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 12
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> why does a rank delta need a snapshot at all?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- keep (score, member) pairs sorted; bisect to rank in O(log n)
- ties: same score → earlier member ranks first
- delta = snapshot_rank - current_rank

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 13
```
