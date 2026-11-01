# Stage 13: Hot partitions — scattered writes, hot-key detection, buckets

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `hot_partition_mitigation.py`
**Tags:** complex, sharding, time-series

## The mechanism

Implement ScatteredWriter (salted copies across N shards) with ScatterGatherReader, HotKeyDetector (sliding window counts), and TimeBucketedStore (bucketed range reads + aggregation).

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 13
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 13
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> why scatter writes but not reads — what does a reader pay?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- scatter key = f'{key}#{i}' for i in range(num_shards)
- detector keeps per-key timestamp lists; window trims on read
- bucket id = int(timestamp // bucket_size_seconds)

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 14
```
