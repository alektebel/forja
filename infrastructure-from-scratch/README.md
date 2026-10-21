# Infrastructure From Scratch — Graded Course

Eighteen graded stages, one per building block of distributed systems. Each
stage is one topic module:

- `templates/<module>.py` — stub (methods raise `NotImplementedError`) with a
  working `_test()` that exercises the intended behaviour
- `solutions/<module>.py` — the shipped answer; its `_test()` passes
- `check_NN.py` — the grader, delegating to `course.check_NN`: the module's
  surface, a behaviour probe, and the module's own `_test()`
- `mutate_NN.py` — anchored mutation battery: exact once-occurring solution
  lines replaced with wrong-behaviour variants, each verified caught by the
  shipped grader

## Stages

| # | Module | What you build |
|---|---|---|
| 1 | `url_shortener.py` | base62 codes, TTL store, hit counting |
| 2 | `consistent_hash.py` | hash ring with virtual nodes, rendezvous hashing |
| 3 | `cache.py` | LRU, TTL, cache-aside, stampede protection |
| 4 | `cdn_caching.py` | edge cache, origin shield, key normalisation |
| 5 | `rate_limiter.py` | fixed window, token bucket, sliding log/counter |
| 6 | `throttling.py` | leaky bucket, delay throttler, paced worker |
| 7 | `request_batching.py` | size/time batchers, DataLoader, pipelining |
| 8 | `connection_pooling.py` | pool, exhaustion, idle eviction |
| 9 | `session_stickiness.py` | sticky router, load balancer, session store |
| 10 | `circuit_breaker.py` | breaker states, bulkhead, bounded queue, retry/timeout |
| 11 | `message_queue.py` | enqueue/ack, dedup, retry with backoff, DLQ |
| 12 | `leaderboard.py` | sorted set, ranks, deltas, windowed boards |
| 13 | `hot_partition_mitigation.py` | scattered writes, hot-key detection, time buckets |
| 14 | `data_locality.py` | shard routing, co-located groups, denormalised views |
| 15 | `eventual_consistency.py` | G-Counter, LWW, vector clocks, read-repair |
| 16 | `idempotency_keys.py` | idempotent store/handler, payment processor |
| 17 | `edge_computing.py` | latency routing, middleware pipeline, A/B, edge runtime |
| 18 | `capacity_planner.py` | QPS/storage/bandwidth math, cache impact, server sizing |

## Status

The course is graded: `python3 codecraft/cli.py run infrastructure-from-scratch`
drives `course.py`. The stubs in `templates/` report TODO for all 18 stages;
the solutions in `solutions/` pass all 18 checks and every mutation battery
catches 100% of its mutants (run `python3 mutate_all.py` for the measured
counts).

Difficulty ramps with the list: stages 1–5 are the read/write-path basics,
6–12 the traffic-management layer, 13–18 partitioning, consistency and
capacity. `docs/` holds the tier reading notes (simple → extremely-complex);
they are topic essays, not one-per-stage, and the module docstrings carry the
working spec.

## How grading works

`course._tested(filename, surface, probe)`:

1. loads `templates/<filename>` under a collision-safe module name,
2. asserts every public name the stage title promises (`surface`),
3. runs a small deterministic behaviour `probe`,
4. runs the module's own `_test()`.

A stub hits `NotImplementedError` at step 3 or 4 → the harness classifies
TODO. A renamed-away class fails step 2 → FAIL. The solution passes all four
→ PASS. Exit codes for `check_NN.py`: `0` pass, `2` stub, `1` failure.

## How mutate batteries work

Each `mutate_NN.py` holds `(anchor, replacement, label)` triples where the
anchor is an exact, once-occurring line of `solutions/<module>.py`. The
battery first proves the baseline (unmutated solution) passes the shipped
grader, then replants each mutant into a temp `templates/` copy and re-runs
`course.check_N` with a per-mutant time budget. A survivor, an anchor that
lost its uniqueness, or a hang is reported MISSED/SKIP and the file exits
non-zero — never a silent 100%.

```bash
python3 mutate_all.py        # all 18 batteries
python3 mutate_all.py 6 12   # specific stages
```

## Verification

```bash
cd infrastructure-from-scratch

python3 check.py             # solutions: 18/18 _test() green
python3 run_all.py           # templates: 18/18 graded as stubs (rc 2)
python3 mutate_all.py        # mutation batteries, caught/total per stage
python3 check_01.py          # one stage, exit 0/2/1
```

## Inventory

- `course.py` — the manifest: 18 `stage()` entries, the only grader
- `check_01.py` … `check_18.py` — thin wrappers delegating to `course.check_N`
- `mutate_01.py` … `mutate_18.py` — anchored batteries, one per module
- `run_all.py`, `mutate_all.py`, `check.py` — shell harnesses around the above
- `templates/`, `solutions/` — 18 modules each
- `docs/` — 20 tier reading essays (topic background; titles predate the
  18-module renumbering)
- `contract.md` — course laws
