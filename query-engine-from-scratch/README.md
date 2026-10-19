# Query Engine From Scratch

Build a query engine over a provided storage floor — in pure standard-library
Python, with no floats, no clock, and no threads.

A database is a file format plus a promise about what a query returns. The
format is provided; the promise is the exercise. A parse that refuses five
malformations instead of guessing; a resolve against a catalog that may lie; a
predicate pushed where it is earned rather than left where it was written; a
B+tree that splits when the leaf is full; a plan whose arithmetic — matched rows
against a quarter of the table — decides scan versus index, and can explain
itself in one line; an executor of iterators over pages whose answer's order is
part of the answer; a buffer that pins what a join still needs and evicts what
it does not; a commit that is one buffered byte and a barrier, not a hope; a
recovery that redoes the committed, undoes the rest, and counts a torn record
rather than trusting it; and a proof — a hundred queries through the whole
stack, each on a fresh world so the page count is the query's own receipt, with
an audit that re-reads the proof against the world and names the ids that
failed.

The domain is provided (`disk.py`, `pages.py`, `tables.py`, `ops.py`): a disk
whose writes land in a buffer and whose reads see only the durable image, one
barrier for durability, and a `power_fail(tear=…)` that tears the last buffered
write; a pager with a shadow, an allocate/free freelist, and the record format's
law; four tables, one index, a catalog with a fixture where it lies, a hundred
pinned queries, the plan facts, and a crash schedule of four fixtures. The
engine is what you write.

No `open(2)` behind the disk, no real fsync behind the barrier: the crash
schedule is deterministic, the torn write is a record the device keeps, and
`disk.counters()` is the ledger every durability claim has to survive.

## The ten stages

| N | File | Title |
|---|---|---|
| 1 | `stage_01.py` | The parse: words, trees, and the five refusals |
| 2 | `stage_02.py` | The resolve: names against a catalog that may lie |
| 3 | `stage_03.py` | The predicates: conjuncts, and where they go |
| 4 | `stage_04.py` | The index: a B+tree that splits |
| 5 | `stage_05.py` | The plan: pushdown, selectivity, and the earned index |
| 6 | `stage_06.py` | The executor: iterators over pages |
| 7 | `stage_07.py` | The buffer: pinning, eviction, and the page you did not keep |
| 8 | `stage_08.py` | The commit: a log, and a rule |
| 9 | `stage_09.py` | The recovery: redo, undo, discard |
| 10 | `stage_10.py` | The proof: a hundred queries, and the audit |

Stage 6 is the course's integration point — it runs a whole planned query
through the iterators over the world's pages — and stage 10 is the capstone:
the hundred through the whole stack, graded against the world's own reference.

## Measured verification

| What | Command | Result |
|---|---|---|
| the world | `python3 .g5-dev/verify_provided.py` | `PROVIDED: 55, PROBLEMS: 0` |
| the stages | `python3 .g5-dev/check_NN.py` (1..10) | ten `PASS`, and ten exits 2 against the templates |
| the mutations | `python3 .g5-dev/mutate_all.py` | `TOTAL 134/134`, `MISSED OR BROKEN: 0` |
| the ladder and the laws | `python3 .g5-dev/audit_course.py` | `AUDITED: 10, PROBLEMS: 0` |
| the whole course as one module | `python3 .g5-dev/smoke.py`, `run_assembled.py` | `SMOKE: PASS`, `ASSEMBLED: 10/10` |
| the tests the course ships | `python3 .g5-dev/count_tests.py query-engine-from-scratch` | 331, per stage `[53, 38, 33, 31, 34, 29, 30, 22, 29, 32]` |

The provided world is pinned by digest:

| File | sha256 |
|---|---|
| `disk.py` | `2037d57bf8823b6c0b25a53469da1705d541a9f3fc5099c3ccdea99b3633a603` |
| `pages.py` | `7ae23d7f7b8bdb3ba29cdccae3016d9e5786456dd016bbca83fdad36c38a734d` |
| `ops.py` | `80769e0a93a900a23cadf0207a70f7a33cfe2f2c6082c524dbfd794db9fe3d45` |
| `tables.py` | `75ff841a7512a373e351215f31ea22c403364ebfc50418300781d66b4899fbcb` |

## The laws a stage is held to

- Standard library only; no `open(`, no module-level mutable state; constants are
  tuples, strings and ints.
- A stage imports the world and earlier stages only, never a later one.
- The world is never edited to make a stage pass; the four digests are pinned.
- The reference rows are law (a stage answers them exactly), the index is earned (a
  plan's `uses_index` agrees with the costs), and nothing uncommitted survives a crash.
- The first docstring paragraph is the stage's own title line, every public function is
  a docstring plus exactly one `raise NotImplementedError`, and the file carries its
  `DESIGN DECISION` blocks and a `TODO: implement` line.

## Running it

    python3 codecraft/cli.py run query-engine-from-scratch

The ten stages are graded in order; the later ones compose the earlier ones (that is
what the ladder law is for), and stage 6's executor is what stage 7 buffers, stage 8
commits, stage 9 recovers, and stage 10 proves.
