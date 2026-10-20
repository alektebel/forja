# Consensus From Scratch

Build replicated-log consensus — the Raft laws, in pure standard-library
Python, with no floats, no `random`, no clock, and a linearizability judge
that signs the history the fabric itself recorded.

Consensus is the one thing a replicated system cannot fake: a leader is a
number a majority agreed on, and a log entry is committed when a majority
holds it. The world is provided (`wire.py` — the six-message grammar, the
role builders, `majority(n) = n // 2 + 1`; `disk.py` — a byte log that can
lose its last write: `crash` returns everything *except* the final record,
the torn write every protocol must survive; `sim.py` — five nodes on integer
ticks, ordered delivery, links cut and healed by a schedule, and the only
clock a stage may read through `sim.timeout`: `a1` 11, `a2` 7, `a3` 9, `a4`
5, `a5` 13, heartbeat 5; `scenarios.py` — seven fixed schedules; `history.py`
— the linearizability checker; `naive.py` — the foil). The protocol on top
of that world is what you write.

One vote per term; an election where leadership is a majority tally, not a
claim; heartbeats that exercise the leadership and a reply ledger that
repairs it; replication where entries match term by term and a divergent
suffix is overwritten; the commit rule that moves the line only over
current-term entries a majority holds; a stale leader refused, downgraded,
and deposed by its own term's truncation; an image that persists and a heal
from the boundary the disk kept; compaction that can never eat a committed
entry; a membership change with one joint window at a time and a quorum
that sums the two majorities; and the proof — the composed node run through
all seven scenarios, pinned against the probe column, judged by the
linearizer, with the naive foil demonstrably double-committing under the
asymmetric partition.

No clock behind a stage: `time`, `random`, `os` and float literals are
landmines the audit checks for; the timer is an `elapsed` integer the fabric
counts, and every state is a dict rebuilt through `wire`'s builders so a
stage can neither mutate a caller's state nor hide mutable state at module
level.

## The ten stages

| N | File | Title |
|---|---|---|
| 1 | `stage_01.py` | The vote: terms, and one vote per term |
| 2 | `stage_02.py` | The election: a leader is a number a majority agreed on |
| 3 | `stage_03.py` | The heartbeats: leadership is exercised, not claimed |
| 4 | `stage_04.py` | Replication: the entries match term by term |
| 5 | `stage_05.py` | The commit rule: a majority, and the current term |
| 6 | `stage_06.py` | The stale leader: refuse, downgrade, never ignore |
| 7 | `stage_07.py` | The disk that lied: persist and recover |
| 8 | `stage_08.py` | The snapshot: commit without losing a committed entry |
| 9 | `stage_09.py` | The membership change: one at a time |
| 10 | `stage_10.py` | The proof: one history, two verdicts |

Stage 10 is the capstone: `init`/`recv`/`tick`/`client` compose stages 1–9
into the node the fabric drives, `prove` runs every scenario and returns the
result beside the probe's pins and the linearizer's verdict, and `audit`
grades the whole — plus it runs `naive` through ASYMMETRIC and refuses its
own pass unless the foil's `conflicts` come back non-empty, because a stage
that reports the foil behaving correctly is not driving the real world.

## Measured verification

| What | Command | Result |
|---|---|---|
| the stages | `python3 .h6-dev/check_NN.py` (1..10) | ten `PASS` (20+25+44+39+16+44+24+33+30+95 = 370 facts), and ten exits 2 against the templates |
| the mutations | `python3 .h6-dev/mutate_all.py` | `TOTAL 148/148`, `MISSED OR BROKEN: 0` |
| the ladder and the laws | `python3 .h6-dev/audit_course.py` | `AUDITED: 10, PROBLEMS: 0` |
| the provided world | `python3 .h6-dev/verify_provided.py` | `PROVIDED: 84, PROBLEMS: 0` |
| the whole course as one module | `python3 .h6-dev/smoke.py`, `run_assembled.py` | `SMOKE: PASS`, `ASSEMBLED: 10/10` |
| the tests the course ships | `python3 .h6-dev/count_tests.py consensus-from-scratch` | 125, per stage `[10, 11, 14, 12, 8, 13, 16, 18, 15, 8]` |
| the pins | stage 10's `prove` against `scenarios.PINS` | seven scenarios: leaders, first commits, conflicts — all equal to the probe column, all histories linear |

The foil's divergence is the acceptance evidence: under ASYMMETRIC the naive
cluster double-commits slot 0 — `(25, 0, "x=1", "y=2")` — where the real
protocol elects once and commits once; under LAGGARD it promotes a node the
current config cannot hear (leadership at 49) the probe parks until 54;
under JOINT it elects a candidate the union quorum never granted (term 2,
`a5` at 28) while the composed node wins the mid-change election at 35.

The provided world is pinned by digest:

| File | sha256 |
|---|---|
| `wire.py` | `4760fc8177e3c2e2f1defaab768ebbf86de7b4aca42aef0cbca0315c849b689b` |
| `disk.py` | `d353539e16cdd816d8d35e5f4920d96c4569970cfd61e82e767b951d00210fc2` |
| `sim.py` | `ef0683f68656b719e5447d6251df4722d4778ab6b46e17fd20fc417ad47d0871` |
| `history.py` | `7e53788da60addd4f403097685884165bb87c9fa5d24a4be550b876575799aad` |
| `naive.py` | `41aef5c31e20a4840577b778c4cef5ac942252d0d1acdfbf728f056b17b9131c` |
| `scenarios.py` | `a35ac9eb6c54951421a6386c568ead77983f4a715e5aa7cf9dfd465e010d6592` |

## The laws a stage is held to

- Standard library only; no `os`/`time`/`random`/`float` literals, no
  `open(`, no module-level mutable state; quorums are ints through
  `wire.majority` alone.
- A stage imports the world and earlier stages only, never a later one;
  the composed node imports `naive` nowhere except inside `audit`'s body.
- The world is never edited to make a stage pass; the six digests are
  pinned, and the probe node was calibrated against every PINS row before
  the first stage was written.
- Every state crosses a builder: hand-built dicts are refused by name, a
  caller's state is never mutated in place, and messages arrive through
  `wire`'s grammar or raise `ProtocolError` naming the stage.
- The first docstring paragraph is the stage's own title line, every public
  function is a docstring plus exactly one `raise NotImplementedError`, and
  the file carries its `DESIGN DECISION` blocks and a `TODO: implement`
  line.

## Running it

    python3 codecraft/cli.py run consensus-from-scratch

The ten stages are graded in order; the later ones compose the earlier ones
(that is what the ladder law is for): stage 1's vote is what stage 2's
tally counts, stage 4's reply is what stage 3's ledger records and stage 5
commits over, stage 7's image is what stage 8's boundary trims and stage 10
persists through, stage 9's joint window is what decides stage 5's quorum —
and stage 10 is the node the fabric drives, judged by the history checker
the world owns.
