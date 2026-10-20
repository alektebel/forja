# Failover From Scratch

Build the replica that earns the right to fail over — two simulated
regions with independent clocks, a link that drops for a chosen window,
clients with pinned sessions — in pure standard-library Python, with no
`time`, no threads, no sockets: the fabric is the only clock, and a node
that reads wall time or counts missing heartbeats has already lost the
exercise.

A replica is not a strategy until you have failed it over. The region
that answers has to be a decision with a rule, not a preference; the
write that arrived late has to be reconciled rather than guessed at; the
session that was redirected must not apply its retried rid twice; and
the RTO you claim has to be a number your own drill produced, never a
constant copied out of a table. Every one of those is a check here. The
interesting failures are quiet ones: a cluster where nothing was ever
said and a naive node declares everyone dead, a sibling pair where each
region answers "my local best" and the union nobody can see, a retry
the fabric re-injects on purpose and a node applies a second time, a
proof that quotes its own expectations instead of running.

The world is provided (`kv.py` — the version grammar: `("v", value,
clock)` over per-node counters, constructors that refuse malformed
clocks by naming the offender; `topology.py` — six nodes, three per
region, `PRIMARY = "east"`, `INITIAL_EPOCH = 1`, `TICK_RATE = 2` so
west's stamps never line up with east's, `LAG_BOUND = 2` making the
health signal servability and not presence; `fabric.py` — the
deterministic driver: scheduled kills, revives, link cuts and client
calls, a watch channel that carries death truth to same-region peers and
ONLY across a live link, one-hop redirects that re-inject the same
`(client, rid)` on purpose; `naive.py` — the foil node, silence-is-death,
local-best, no-ledger; `scenarios.py` — the seven schedules and the
`PINS` table: what the honest probe and the foil actually did on each
one, replayed from real runs, never asserted). The node on top of that
world is what you write.

## The ten stages

| N | File | Title |
|---|---|---|
| 1 | `stage_01.py` | The clock: ordering the versions, not the values |
| 2 | `stage_02.py` | Quorum: serve inside three or refuse entirely |
| 3 | `stage_03.py` | Hints: held for a peer, never served as yours |
| 4 | `stage_04.py` | Anti-entropy: the union over ranges, never a choice |
| 5 | `stage_05.py` | Health: a signal that is not a heartbeat |
| 6 | `stage_06.py` | Sessions: the pinned answer is a table, not a feeling |
| 7 | `stage_07.py` | Promotion: a majority adopted, or no epoch at all |
| 8 | `stage_08.py` | The redirect that does not apply a write twice |
| 9 | `stage_09.py` | Late writes: reconcile, name the lost, price the RPO |
| 10 | `stage_10.py` | The drill: RTO/RPO measured, the foil run, the audit refused |

Stage 10 is the capstone: `init`/`recv`/`tick`/`client` compose the
stage protocols into one node — stage 7's `propose` wholesale on the
tick, stage 7's `tally` on an adopt, stage 8's `apply_once` behind
stage 2's quorum gate, stage 1's `coalesce` on every arriving version —
and then `drill` runs each of the seven schedules through the fabric and
`audit` grades the seven rows against the probe columns AND drives the
foil itself through `Fabric(naive)`, refusing a proof that reports
FAKE_DEATH silent, FLAP deduplicated or DUAL narrowed. `drill` reports
the `rto`/`rpo` this node's run measured, not the ones the pins table
quotes: a report you copy is a report that cannot be wrong, and a report
that cannot be wrong proves nothing.

## Measured verification

| What | Command | Result |
|---|---|---|
| the stages | `python3 .h8-dev/check_NN.py` (1..10) | ten `PASS` (15+8+8+5+5+2+5+5+7+20 = 80 facts), and ten exits 2 against the templates |
| the mutations | `python3 .h8-dev/mutate_all.py` | `TOTAL 129/129`, `MISSED OR BROKEN: 0` |
| the ladder and the laws | `python3 .h8-dev/audit_course.py` | `AUDITED: 10, PROBLEMS: 0` |
| the provided world | `python3 .h8-dev/verify_provided.py` | `PASS — the world is frozen` |
| the whole course as one module | `python3 .h8-dev/smoke.py`, `run_assembled.py` | `SMOKE: PASS`, `ASSEMBLED: 10/10` |
| the tests the course ships | `python3 .h8-dev/count_tests.py failover-from-scratch` | 147, per stage `[15, 17, 18, 13, 14, 14, 11, 13, 21, 11]` |

The pins are the acceptance evidence beside the passes: FLAP promotes
`((12,"west",2),)` with measured `rto 6` (the first served at 13 minus
the first refused at 7 — the outage, in ticks, that the node itself
produced) and `dups ()` where the foil re-applies `("alpha",3,"w1")`
twice; LAG's `lost` names both rids the primary never recovered and the
measured `rpo` is 2, a length of WRITE rows, not of keys; DUAL answers
`("ok",("3","5"))` on both sides where the foil narrows each to one;
FAKE_DEATH promotes nothing for the honest node — its notices are empty
and silence is not death — and splits the brain twice for the foil;
ALL_DIE's surviving `w3` redirects to a dead-home `east` and then
refuses, never absorbing below quorum. The audit refuses every tampered
report these numbers appear in: a `dups` column copied, an `rto` of 99,
a missing drill row.

The provided world is pinned by digest:

| File | sha256 |
|---|---|
| `kv.py` | `c1d41498b254d89aa5730582ff24d01cae7f8dfc11c3ac38ca045fd110f34f17` |
| `topology.py` | `114618e7c85a9dfc6b3d1e9b713f6d152ce86bb4844405b7731d1a6e4ac357aa` |
| `fabric.py` | `09b96dcc34f01d2ea7103da0fc55f7ea9e767782bf2fb0ce41d1a6beb1637dc2` |
| `naive.py` | `b50f54f1c8d44e1961732c7ac5878b65b3631d2064a479c2e01ee9102baa9eaf` |
| `scenarios.py` | `94336705017cfd7d2398cc3c09690643982c131ee0f2f6025fa966996482a2d1` |

## The laws a stage is held to

- Standard library only; no `time`, no `threading`, no `random`, no
  `os`, no sockets, no floats where the contract says ints. The fabric's
  tick is the only clock any state may move on.
- `FailError` (stage 1's, a `ValueError` subclass) refuses by naming the
  offender: a node id off the fleet, a message kind the node does not
  speak, a malformed store, a pins row that is not the world's.
- Silence is not death: health is the watch channel's folded notices,
  `dead` claims and `alive` retracts; no stage counts missing
  heartbeats, and the foil's FAKE_DEATH brain is what that mistake costs.
- A quorum is a promise: `readable`/`writable` answer inside the R/W
  numbers or refuse entirely; a below-quorum node redirects the session
  ACROSS and absorbs nothing.
- Exactly-once is the ledger: a committed `(client, rid)` re-answers the
  recorded verdict and moves no state — including the arrival the fabric
  re-injects after a redirect, which is the same rid ON PURPOSE.
- The epoch fences forever after: a proposal or adopt at or below a
  node's own epoch changes nothing, and promotion happens only when a
  majority of the old primary's region is dead on the record.
- `PINS` is data a stage reads and never recomputes — except when it
  must not be trusted: stage 10's `drill` measures `rto`/`rpo` from its
  own run, and `audit` drives `Fabric(naive)` live rather than quoting
  the naive column as a constant.

## Running it

    python3 codecraft/cli.py run failover-from-scratch

The ten stages are graded in order; the later ones compose the earlier
ones (that is what the ladder law is for): stage 1's `coalesce` is what
stage 4's `repair` returns and stage 10 absorbs on every sync, stage 2's
`writable` is stage 6's gate and stage 7's proposal condition, stage 5's
folded notices are stage 7's majority count and stage 10's `recv`
payload, stage 7's `propose`/`tally` is stage 10's `tick` wholesale,
stage 8's `apply_once` is stage 10's `client`, and stage 9's
`rpo`/`rto` arithmetic is what stage 10 measures against its own run —
the drill that turns nine correct protocols into one node the region
can fail over to.

## Where this stops

Deliberately left out, so you know the boundary:

- **No network, no real machines.** Every message is a tuple the fabric
  routes deterministically; a real partition's messiness (delay,
  reordering, partial sends) is the same notice algebra under a worse
  scheduler, and the laws here are what the scheduler is tested against.
- **No wall clock, no timers.** A real failover waits on leases and
  detection timeouts; here `TICK_RATE` and the scenario's tick list are
  the timing, because a lesson that needs `time.sleep` cannot be graded
  reproducibly.
- **One key space, one store.** No sharding, no replication factors
  beyond three, no cross-key transactions; the interesting failure is
  what a node does with siblings of ONE key, not how it spans many.
- **No client behaviour beyond pinned sessions.** The fabric re-injects
  a redirected rid exactly once; real clients retry on their own clock,
  which is a different (and ledger-adjacent) course.
- **The drill's horizon is fixed.** Seven schedules, each run to its
  pinned 24 ticks, verdicts graded on the four columns the probes
  produce; a wider world of scenarios is a build step, not a lesson.
