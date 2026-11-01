# Stage 14: Data locality — shard routing, co-location, denormalized views

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `data_locality.py`
**Tags:** complex, sharding, modelling

## The mechanism

Implement ShardRouter (partition key → shard), CoLocationStore (related entities on one shard), DenormalizedOrderView (pre-joined writes fan out) and LocalityAwareCache.

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 14
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 14
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> which read does denormalization make free — and which write it makes expensive?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- route by hash(partition_key) % num_shards
- get_all(entity, pk) reads the single shard pk maps to
- update_user_name touches every order row holding the copy

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 15
```
