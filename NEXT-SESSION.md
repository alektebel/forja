# Next session — where everything is

Written at the end of the session that shipped **I9
(`interconnects-from-scratch`)** — ten stages, ten graded checks, 438 planted
mutations — and, before it, the `profiling-pytorch/` study notes. Everything in
*Done* is committed and pushed; the one section after it is the commit that
carries this file.

## Done, pushed, on `origin/main`

| Commit | Unit |
|---|---|
| `86724f2` | F1 `benchmark-from-scratch` |
| `4e6c7f2` | F2 `eval-framework-from-scratch` — 272 mutations, `MISSED OR BROKEN: 0` |
| `9332df2` | **Agent Infra**: `AGENT-INFRA.md` (the twelve-item list kept verbatim) and **phase J** registered in `codecraft/path.py` + `ROADMAP.md` |
| `68c98bb` | **G3 `cpu-from-scratch`** — 10 stages, provided `isa.py`, 360 mutations, `MISSED OR BROKEN: 0` |
| `b8c4a3b` | J1 checkpoint: the `queue-and-workers-from-scratch` scaffold and the provided `fleet.py` |
| `3faf26f`, `a769fcc`, `bfff13f` | **`DISTRIBUTED.md`** (the NCCL + LLM-training plan, 212 lines) and I9/H1 registered as the next two courses |
| `b944541` | **J1 `queue-and-workers-from-scratch`** — `ORDER = 17`, provided `fleet.py`, 386 mutations, `MISSED OR BROKEN: 0`, smoke green, registered |
| `21206f4` | **`profiling-pytorch/`** — the three Hugging Face *Profiling in PyTorch* posts saved as this repo's study notes (mechanisms and measured numbers, links, the runnable scripts on the Hub, and how the whole thing ties into I9's cost model). The posts themselves are third-party text without an explicit license: downloaded locally for offline reading, gitignored, not redistributed |

## Done, in the commit that follows this file

**I9 `interconnects-from-scratch`** — phase I, `ORDER = 18`,
`LEVEL = "intermediate"`, 10 stages, stdlib only, offline, deterministic, and
**no float anywhere**: every tick is an int computed from the fabric's
bandwidths and latencies. The provided module is `fabric.py` (links with
bandwidth and latency, four topologies — `ring`, `full`, `tree`, `switch` — an
executor, buffers and the reference reduction); the exercise is the cost model
and the collectives on top of it.

The thesis, one sentence, and every stage's check asserts it: **a collective has
a plan and a price, and the two are independent.** Correctness is decided by
running the plan; cost by counting (`latency + ceil(bytes / bandwidth)` per hop,
a step is its slowest transfer, a plan the sum of its steps).

- `python3 /tmp/i9-checks/run_all.py` → all ten `PASS`, `FAILED: 0`.
- `python3 /tmp/i9-checks/mutate_all.py` → `TOTAL 438/438`,
  `MISSED OR BROKEN: 0`. Per stage: 46, 40, 37, 42, 47, 43, 43, 38, 47, 55.
- `python3 /tmp/i9-checks/audit_course.py` → `AUDITED: 10, PROBLEMS: 0`.
- `python3 /tmp/i9-checks/assemble.py` → `assembled 10 checks, 3941 lines,
  compiles`; the assembled manifest's own `check_1()`…`check_10()` run clean in
  a **fresh subprocess** over a solutions-overlaid tree (returncode 0, ten
  summaries), with the repo root on `PYTHONPATH` because the manifest imports
  `codecraft.api`.
- `python3 /tmp/i9-smoke.py` → `SMOKE PASS — 10 stages, one deterministic step`,
  ten lines: the hop and the plan price, ring vs tree broadcast, the travelling
  accumulator, the chunked ring all-reduce, the crossover on two fabrics, the
  composed all-reduce, the ragged all-to-all, a group launch, the choice against
  the bound, and one step's `max(compute, comms)`.
- `./cz run interconnects-from-scratch` → `0/10 passing` on the templates,
  `10/10 passing` with the solutions copied over them (verified both ways, then
  the templates restored).
- Registered: `codecraft/path.py` I9 → `kind: "ready"`,
  `course: "interconnects-from-scratch"`, `prereq: ["G3", "J1"]` and a real
  `why`; `codecraft/ROADMAP.md` → **Eighteen courses, 211 graded checks**, a
  ready row, the I9/H1 table marking I9 built, and the next-course paragraph now
  naming J2 with H1 as the parallel priority; a bullet in the root `README.md`.
- Harness and smoke mirrored out of `/tmp` to
  `/home/diego/Desarrollo/.i9-dev/` (22 files: `CONTRACT.md` and every
  `check_NN.py` / `mutate_NN.py` / runner).

Four things this course bought, all worth keeping:

1. **The smoke found my expectations wrong three times, not the course.** `r0`
   and `r3` are neighbours on `ring(4)` — the ring closes, so "three hops" is a
   property of the *pair*, not of "two ranks on a ring"; a chunked all-reduce
   gets *cheaper* per step because each step carries less; and `exchange_with`
   answers with the blocks that fill each buffer, not the buffers. Each is now
   an assertion with the arithmetic attached.
2. **Doubling needs one-hop XOR partners, and the honest answer is a refusal.**
   On a ring, and across a two-level switch's spine, the butterfly's step is
   link-illegal; the course refuses with a `FabricError` naming the pair and the
   hops rather than staging the transfer or running the plan with
   `check=False`. This is also why real frameworks butterfly inside an NVLink
   domain and ring across nodes.
3. **SHARP had to become a rank-level plan** (gather to the spine port, reduce
   across the spine, broadcast back) for `choose` to return something the
   executor can run; the interesting part is exactly the rank-level part, and
   the two-level crossover now reads sharp 844 / tree 1520 / ring 1610 at 4096
   on `switch(8, width=4)`, and ring 2070 / tree 2872 / sharp 4224 on
   `switch(16, width=4)` where the spine has to walk.
4. **A deliberately refused candidate is not an error.** `all_reduce_best` and
   `choose` drop a candidate whose preconditions fail (no chunking to divide, a
   two-hop XOR partner, no two-level fabric) instead of raising, so "which
   algorithm" stays a question about ticks — and the fixtures assert which
   candidates were unavailable.

## Next up — H1 `distributed-training-from-scratch`

The two-course plan is in **`DISTRIBUTED.md`** (repo root, committed), and I9 —
its first half — is now built: everything H1 prices is a call into I9's fabric
and stages. H1 provides the shape calculus (parameter/activation/gradient counts
and the memory ledger per rank) and asks for the training-step arithmetic
against I9's cost model:

- **DDP**: `2S` per rank per step, buckets, the `max(compute, comms)` overlap,
  and why the all-reduce is once per step and not once per micro-batch.
- **ZeRO-1/2/3 and FSDP**: what stays replicated, what is sharded, and the
  bytes/step from 16 B/param down to ≈3P.
- **Tensor parallel**: the two all-reduces per block, and where sequence
  parallelism changes the count.
- **Pipeline parallel**: GPipe vs 1F1B, the bubble `(p−1)/(m+p−1)`, and the
  activation memory that decides the micro-batch count.
- **MoE**: the expert all-to-all pair (dispatch and combine), capacity factor,
  and the imbalance that shows up as ticks.
- **Ring attention**: the KV blocks that travel, and the point where the ring
  stops being cheaper than recompute.

Mistakes to guard against, straight from `DISTRIBUTED.md`: comms added to compute
instead of overlapped; one all-reduce per micro-batch; an axis of one still
emitting its collective; one expert exchange instead of two; a bucket size that
makes the all-reduce latency-bound.

Then, in the order the roadmap already has: J2 `orchestration-from-scratch`,
J3 `durable-execution-from-scratch`, J4 `sandbox-capabilities-from-scratch`,
J5 `agent-metrics-from-scratch`, then G4 (an OS course) and G5/G6.

## The workflow that produced G3, F2, J1 and I9 — keep it

1. **Recon** the target directory and anything salvageable, then **freeze a
   contract** in `/tmp/<course>-checks/CONTRACT.md`: thesis, conventions, the
   provided module, the execution model, and per stage the surface, the frozen
   shapes and the *mistake catalogue*. Freeze it before writing any stage.
2. **Mirror it out of `/tmp` the moment it is frozen.** `/tmp` was wiped once
   mid-session and took ten delegates with it. The mirrors are
   `/home/diego/Desarrollo/.j1-dev/` and `.i9-dev/`; re-mirror after **every**
   harness change — including amendments to the contract itself, which is how
   I9's stage 5 and 9 rules were corrected mid-flight.
3. **One delegate per stage**, four files each: `stage_NN.py`,
   `solutions/stage_NN.py`, `check_NN.py`, `mutate_NN.py`. A delegate's own
   verdict is not evidence.
4. **The parent re-runs everything**, every time: `check_NN.py`, `mutate_NN.py`,
   `run_all.py NN`, `mutate_all.py NN`, `audit_course.py NN`. In waves, because
   every check imports the earlier stages' solutions. **Keep delegate briefs
   short** — point at the contract for the surface and the mistake catalogue
   instead of restating them; a long brief produced three consecutive
   length-stop failures and thirty wasted minutes.
5. **Mutation-runner hygiene**: rebuild the tree per mutation,
   `PYTHONDONTWRITEBYTECODE=1`, a stale anchor is `BROKEN` and not `CAUGHT`, and
   a mutant that hangs for 60 s counts as `[hung  ]` = caught. A mutation must
   plant the defect its name describes: a no-op mutation is worthless, and it
   surfaces later as `MISSED`.
6. **A check that only proves the solution passes proves nothing.** Every check
   catches a mistake that is easy to make and hard to notice; its message names
   the mistake, not the symptom, and interpolates the actual.
7. **Assemble and smoke before writing prose.** `assemble.py` splices the ten
   checks into `course.py`; the smoke runs the whole course end to end against
   the solutions in one process. The prose (README, solutions README) quotes the
   numbers the sweep and the smoke produced, verbatim.
8. **Register, then commit**: `codecraft/path.py` (`kind`, `course`, a real
   `why`), `codecraft/ROADMAP.md` (the count in the header, a ready row, the
   plan table), the root `README.md` bullet, and this file — after deleting
   `codecraft/{history.jsonl,profile.json,mentor_cache.json}` and every
   `__pycache__`. Then `git pull --rebase --autostash origin main && git push
   origin main`.

### Three traps worth remembering

- **`ast.get_source_segment` is not a body extractor.** It strips the leading
  indentation of a single-line statement and pads a multi-line one to its
  original column, so a body that mixes the two cannot be `dedent`ed uniformly —
  exactly the shape a `check()` body has. Assemble bodies **by line range**
  (`statements[0].lineno` … `statements[-1].end_lineno`), verbatim, then dedent
  once. The symptom is `IndentationError: unexpected indent` in a generated file
  that looks correctly indented on its first lines.
- **A summary that declares a value instead of deriving it** is the defect class
  this whole line of courses keeps finding. Stage 9 of J1 exists for it, and the
  check for an end-to-end stage has to compare the summary against the log it
  claims to summarise — not just the log by itself. I9's stage 10 has the same
  duty for a step's price: derive it from the axes, never from a remembered
  total.
- **A course directory that is not committed yet has no `git checkout` to fall
  back on.** Overlaying the solutions onto the templates to watch the CLI report
  `10/10` is a good verification — copy the ten templates aside (or commit)
  first, or the working tree's templates are gone and you are rebuilding them
  from delegate transcripts. `git pull --rebase` also refuses to run with
  unstaged changes in the tree: `--autostash` is the way to push around them.

## Ground rules

- **Deterministic, offline, integer-only.** No `time`, `threading`, `asyncio`,
  `random`, `os.environ`, `uuid`, no module-level mutable state, and no float
  anywhere in the J/I family: every count is an int, so a run is a function of
  its inputs and a check can assert a number instead of timing something.
- **Docs in the repo are English**; the user writes Spanish, so answers are in
  Spanish with paths and identifiers verbatim.
- **The user's twelve-item list in `AGENT-INFRA.md` stays verbatim (Spanish)**;
  the analysis around it is English.
- `./cz` is `python3 codecraft/cli.py`. Before committing: no `history.jsonl`,
  no `profile.json`, no `mentor_cache.json`, no `__pycache__`.
- Ask before destructive commands; a course's own templates are the exercise, so
  never "fix" a stub into a solution outside `solutions/`.
