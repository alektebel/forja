# Next session — where everything is

Written at the end of the session that shipped **J1
(`queue-and-workers-from-scratch`)** — ten stages, ten graded checks, and the
plan for the distributed-training pair registered ahead of it. Everything in
*Done* is committed and pushed; everything after it is what to pick up next.

## Done, pushed, on `origin/main`

| Commit | Unit |
|---|---|
| `86724f2` | F1 `benchmark-from-scratch` |
| `4e6c7f2` | F2 `eval-framework-from-scratch` — 272 mutations, `MISSED OR BROKEN: 0` |
| `9332df2` | **Agent Infra**: `AGENT-INFRA.md` (the twelve-item list kept verbatim) and **phase J** registered in `codecraft/path.py` + `ROADMAP.md` |
| `68c98bb` | **G3 `cpu-from-scratch`** — 10 stages, provided `isa.py`, 360 mutations, `MISSED OR BROKEN: 0` |
| `b8c4a3b` | J1 checkpoint: the `queue-and-workers-from-scratch` scaffold and the provided `fleet.py` |
| `3faf26f`, `a769fcc`, `bfff13f` | **`DISTRIBUTED.md`** (the NCCL + LLM-training plan, 212 lines) and I9/H1 registered as the next two courses |

## Done, in the commit that follows this file

**J1 `queue-and-workers-from-scratch`** — phase J, `ORDER = 17`,
`LEVEL = "intermediate"`, 10 stages, stdlib only, no threads, no wall clock and
no float anywhere. The provided module is `fleet.py` (the clock, the frozen
specs, and a catalogue of workers that fail in the interesting ways); the
exercise is the queue.

- `python3 /tmp/j1-checks/run_all.py` → all ten `PASS`, `FAILED: 0`.
- `python3 /tmp/j1-checks/mutate_all.py` → every planted mutation caught,
  `MISSED OR BROKEN: 0`. Per stage: 38, 40, 33, 40, 40, 40, 40, 39, 40, 36.
- `python3 /tmp/j1-checks/audit_course.py` → `AUDITED: 10, PROBLEMS: 0`
  (titles, DESIGN DECISION blocks, `TODO: implement` lines, stub errors).
- `python3 /tmp/j1-checks/assemble.py` → `assembled 10 checks, 3551 lines,
  compiles`; the assembled manifest's own `check_1()`…`check_10()` all pass over
  a solutions-overlaid tree (`VCHECK: checks 10, failed 0`).
- `python3 /tmp/j1-smoke.py` → `SMOKE PASS — 10 stages, one deterministic
  queue`, ending with `stuck: a pool whose every attempt dies stops with
  'no_progress', not a hang`.
- `./cz run queue-and-workers-from-scratch` → `0/10 passing` with
  `not implemented yet — stage_01.py:89 in parse_task()`, which is the right
  state for a course whose templates are the exercise.
- Registered: `codecraft/path.py` J1 → `kind: "ready"` with a real `why`,
  `codecraft/ROADMAP.md` → **Seventeen courses, 201 graded checks**, a ready row
  and the J-plan table marking J1 built, and a bullet in the root `README.md`.

Two things the smoke and the mutation sweep bought, both worth keeping:

1. **The record declared a value instead of reading one.** `run_record(queue)`
   with no reason returned `stopped=None` while the queue's log carried
   `{'kind': 'stopped', 'reason': 'no_progress'}`. Stage 9 now derives the stop
   from the log's last `stopped` line; a handed-in reason is written once and
   only when the log carries no stop at all; when both differ, the log wins and
   nothing is written. Two fixtures and the mutations behind them pin it.
2. **The end-to-end check was the weaker one.** The last full sweep reported
   `MUTATION MISSED — stage 10: the record line claimed a clean drain after a
   bound stop`. `check_10.py` pinned the log of a bounded run but not the record
   line's `stopped` field. Fixed by a fixture that runs a bound until it bites
   and compares the record line's `stopped` against the log's own stop — plus
   the drained case, where the record must say `None`.

## Next up — I9 `interconnects-from-scratch`, then H1 `distributed-training-from-scratch`

The two-course plan is in **`DISTRIBUTED.md`** (repo root, committed): NCCL's
model (communicator, ranks, streams, groups; NVLink → PCIe → SHM → IB verbs;
Simple / LL / LL128), the collective cost table (ring all-reduce
`2S(N−1)/N` per rank in `2(N−1)` steps; tree `≈2S` per rank but `≈2S(N−1)` on
the network in `2 log N`; recursive doubling `S log N`), the `S(N−1)/N` lower
bound and SHARP, then DDP (`2S` per rank, bucketing, `max(compute, comms)`,
ZeRO-1/2/3 and FSDP from 16 B/param to ≈3P bytes/step), tensor parallel's two
all-reduces per block, pipeline bubbles (`(p−1)/(m+p−1)`), expert all-to-all and
ring attention. The same file carries the ten-stage spec for each course.

Order: **I9 first**, because every stage of H1 is a byte count that I9 makes
checkable. I9 provides a `fabric.py` (links with bandwidth and latency, a
topology, transfer accounting) and asks for the collectives on top of it; H1
provides the shape calculus and asks for the training-step arithmetic (DDP,
ZeRO, TP, PP, MoE, ring attention) against I9's tables.

Then, in the order the roadmap already has: J2 `orchestration-from-scratch`,
J3 `durable-execution-from-scratch`, J4 `sandbox-capabilities-from-scratch`,
J5 `agent-metrics-from-scratch`, then G4 (an OS course) and G5/G6.

## The workflow that produced G3, F2 and J1 — keep it

1. **Recon** the target directory and anything salvageable, then **freeze a
   contract** in `/tmp/<course>-checks/CONTRACT.md`: thesis, conventions, the
   provided module, the execution model, and per stage the surface, the frozen
   shapes and the *mistake catalogue*. Freeze it before writing any stage.
2. **Mirror it out of `/tmp` the moment it is frozen.** `/tmp` was wiped once
   mid-session and took ten delegates with it. The mirror lives at
   `/home/diego/Desarrollo/.j1-dev/` for J1; make an equivalent for the next
   course and re-mirror after **every** harness change.
3. **One delegate per stage**, four files each: `stage_NN.py`,
   `solutions/stage_NN.py`, `check_NN.py`, `mutate_NN.py`. A delegate's own
   verdict is not evidence.
4. **The parent re-runs everything**, every time: `check_NN.py`, `mutate_NN.py`,
   `run_all.py NN`, `mutate_all.py NN`, `audit_course.py NN`. In waves of three
   stages, because every check imports the earlier stages' solutions.
5. **Mutation-runner hygiene**: rebuild the tree per mutation,
   `PYTHONDONTWRITEBYTECODE=1`, a stale anchor is `BROKEN` and not `CAUGHT`, and
   a mutant that hangs for 60 s counts as `[hung  ]` = caught.
6. **A check that only proves the solution passes proves nothing.** Every check
   catches a mistake that is easy to make and hard to notice; its message names
   the mistake, not the symptom, and interpolates the actual.
7. **Assemble and smoke before writing prose.** `assemble.py` splices the ten
   checks into `course.py`; the smoke runs the whole course end to end against
   the solutions in one process and one clock. The prose (README, solutions
   README) quotes the numbers the sweep and the smoke produced, verbatim.
8. **Register, then commit**: `codecraft/path.py` (`kind`, `course`, a real
   `why`), `codecraft/ROADMAP.md` (the count in the header, a ready row, the
   plan table), the root `README.md` bullet — after deleting
   `codecraft/{history.jsonl,profile.json,mentor_cache.json}` and every
   `__pycache__`. Then `git pull --rebase origin main && git push origin main`.

### Two traps worth remembering

- **`ast.get_source_segment` is not a body extractor.** It strips the leading
  indentation of a single-line statement and pads a multi-line one to its
  original column, so a body that mixes the two cannot be `dedent`ed uniformly —
  exactly the shape a `check()` body has. Assemble bodies **by line range**
  (`statements[0].lineno` … `statements[-1].end_lineno`), verbatim, then dedent
  once. The symptom is `IndentationError: unexpected indent` in the middle of a
  generated file that looks correctly indented on its first lines.
- **A summary that declares a value instead of deriving it** is the defect class
  this whole line of courses keeps finding. Stage 9 of J1 exists for it, and the
  check for the end-to-end stage has to compare the summary against the log it
  claims to summarise — not just the log by itself.

## Ground rules

- **The clock is injected and the course is deterministic.** No `time`,
  `threading`, `asyncio`, `random`, `os.environ`, `uuid`, no module-level
  mutable state, and (in J1 and its family) no float anywhere: every count is an
  int, so a run is a function of its inputs and a check can assert a number
  instead of timing something.
- **Docs in the repo are English**; the user writes Spanish, so answers are in
  Spanish with paths and identifiers verbatim.
- **The user's twelve-item list in `AGENT-INFRA.md` stays verbatim (Spanish)**;
  the analysis around it is English.
- `./cz` is `python3 codecraft/cli.py`. Before committing: no `history.jsonl`,
  no `profile.json`, no `mentor_cache.json`, no `__pycache__`.
- Ask before destructive commands; a course's own templates are the exercise, so
  never "fix" a stub into a solution outside `solutions/`.
