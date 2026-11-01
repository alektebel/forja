# Stage 18: Capacity planning — QPS, storage, bandwidth, server estimates

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `capacity_planner.py`
**Tags:** moderate, estimation, arithmetic

## The mechanism

Implement compute_qps (DAU × actions → average + peak), compute_storage (write QPS × payload × replication per day), compute_bandwidth, cache_impact, estimate_servers (Little's Law) and the human_bytes/human_num formatters.

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 18
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 18
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> cache hit ratio goes up 10% — what happens to DB QPS?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- SECONDS_PER_DAY = 86400; peak = average × PEAK_MULTIPLIER
- servers = ceil(peak_qps × avg_latency_ms / 1000 / threads_per_server)
- reduction_percent is (1 - db_qps_after/db_qps_before) × 100

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 19
```
