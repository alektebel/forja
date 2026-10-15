# Next session — where everything is

Written at the end of the session that shipped **G4 (`os-from-scratch`)** — an
operating system is what you write after the hardware breaks your last promise:
ten stages on a provided machine, from the boot map's first frame to a capstone
that runs the world's own userland on the kernel you wrote and then cross-checks
the kernel's account of the run against the machine's, key by key — 641 planted
mutations. Everything in *Done* is committed and pushed; the section after it is
the commit that carries this file.

## Done, pushed, on `origin/main`

| Commit | Unit |
|---|---|
| `9332df2` | **Agent Infra**: `AGENT-INFRA.md` (the twelve-item list kept verbatim) and **phase J** registered |
| `68c98bb` | **G3 `cpu-from-scratch`** — 10 stages, provided `isa.py`, 360 mutations |
| `b944541` | **J1 `queue-and-workers-from-scratch`** — provided `fleet.py`, 386 mutations, smoke green |
| `21206f4` | **`profiling-pytorch/`** — the three Hugging Face *Profiling in PyTorch* posts as study notes (the posts themselves gitignored) |
| `bfff13f` | **`DISTRIBUTED.md`** and I9/H1 registered |
| `5c74fbc` | **I9 `interconnects-from-scratch`** — 10 stages, 438 mutations, smoke green, registered |
| `f446db4` | **H1 `distributed-training-from-scratch`** — 10 stages, 554 mutations, smoke green, registered |
| `2dab44e` | **A8 `autograd-from-scratch`** — 10 stages, provided `exact.py` + `fixtures.py`, 504 mutations, smoke green, registered |
| `2ba19e5` | the A8 manifest prose fix: the copied `course_head.py` still described H1's course |
| `13bd3eb` | **J2 `orchestration-from-scratch`** — 10 stages, provided `agents.py` + `graphs.py`, 526 mutations, smoke green, registered |
| `10b361c` | **`AI-ENGINEER.md`** — the user's two lists kept verbatim (25 AI-engineer interview problems, 15 things to build), a per-item coverage table for all 40, and the five surviving gaps registered as **phase K** (`path.py` + `ROADMAP.md`, all five `kind: "author"`, with three items deliberately left with no slot and their reasons stated) |
| `b926158` | **J3 `durable-execution-from-scratch`** — 10 stages, provided `disk.py` + `work.py`, 558 mutations, thesis *a run is not the process that started it; it is the log on disk*, registered |
| `83e7a55` | **J4 `sandbox-capabilities-from-scratch`** — 10 stages, provided `fleet.py` (J1's, byte-identical), `vfs.py` and `tools.py`, 494 mutations, thesis *an agent's power is the intersection of what its tools declare, what its principal granted and what the world will still afford*, registered |
| `0230b92` | **J5 `agent-metrics-from-scratch`** — 10 stages, provided `fleet.py` (J1's, byte-identical) and `telemetry.py`, 510 mutations, thesis *a trace is not a metric*, smoke green, registered |
| `4755f5c` | **G4 `os-from-scratch`** — 10 stages, 641 mutations, the machine provided (`machine.py`, `devices.py`, `userland.py`), thesis *an operating system is what you write after the hardware breaks your last promise*; `linux-from-scratch/` staged beside it as prose; smoke green, registered |
| `bfbdefb` | **`cz stage`, per-stage counts, six registered rows** — the stage page before the run, `codecraft/stats.py` (9,323 asserts and 4,079 caught mutations across the eighteen built courses), the 128 hardcoded repo roots replaced by `__file__`, and G7/G8/H5/H6/H7/L4 registered |

## Done, in the commit that follows this file

**`cz dag` — the registry as a dependency DAG, and the fifteen-item
AI-infrastructure list mapped onto it.**

- **`./cz dag`** prints the whole registry as waves: `60 projects · 87 hard edges ·
  9 waves`, each row once, in the wave its longest path reaches, with what it
  unlocks. **`./cz dag <course>`** zooms on one row — its wave, its direct prereqs,
  everything that must come first *in wave order*, everything it opens,
  transitively, and the advice. Rows resolve by slug, id (`cz dag J3`) or title.
  New: `codecraft/dag.py` (`graph`, `before`, `unlocks`, `advice`, `focus`),
  `render.render_dag`/`render_dag_row`, `cli.cmd_dag` (`cz tree` is an alias).
- **The graph is derived, not written.** `path.PHASES` owns the rows and their
  `prereq` lists; `dag.py` reads them and nothing else, so the plan and the DAG
  cannot drift. `_level` is the longest path from a root, and the module reports
  the only two defects a registry can have — a prereq that names no row, and a
  cycle — instead of hiding them. All six of those invariants are now `cz
  self-test` failures, including "every prereq sits in an earlier wave" and
  "a row's closure is transitive and excludes itself".
- **A second, advisory layer.** `prereq` is the honest dependency; `ADVICE` is
  advice, is never an edge, and holds the nine places where a row's own thesis asks
  for something that nothing forces — A1 after A5 ("makes sqs/dynamodb in A1
  click"), F2 after C1 ("phase C1 owns what to measure"), H5 after A6, I11 after
  A3, I12 after F2, J5 after E1, K5 after J4, C2 after A5, H1 after A8. Every
  entry names the thesis it came from, and the self-test checks that each target is
  a real row.
- **Three more rows, from the list that arrived mid-unit** (I13
  `serving-cluster-from-scratch`, I14 `weight-delivery-from-scratch`, H8
  `failover-from-scratch`). Twelve of the fifteen items were already the subject of
  a registered course; #5 (weight delivery) and #14 (multi-region failover) were
  covered nowhere, and #1 (the cluster) was scattered across I3, I7 and I10 with no
  row of its own. The new ROADMAP section carries the full fifteen-row mapping plus
  the three mechanisms, and the inference-spine table gained its I13/I14 lines.
  `author` rows are **25** now, and the registry is **60 rows**.
- Docs touched: `codecraft/README.md` (the verb, a worked DAG, the two layers
  explained), the root `README.md`, the `cz` shim header, the web page's footer,
  `ROADMAP.md`, and this file.

### The unit before it — `cz stage`, per-stage counts, six registered rows (`bfbdefb`)

**`cz stage`, per-stage counts in the repo, six registered rows** — the
CodeCrafters-shaped surface the CLI was missing, the two defects found while
looking for it, and the plan rows that came out of the same review.

- **`cz stage <course> [n]`** — the page *before* the run: the file, what you
  write in it, how big the tester is, the live status and the ladder. No argument
  lands on the first stage that is not passing. A slug, an id (`G4`) or a title
  (`"OS From Scratch"`) all resolve, and a registered-but-unwritten course prints
  the row, its prerequisites and its thesis instead of "no course named …":
  `cz stage tcp-ip-from-scratch` is L1's plan page today. New:
  `cli.cmd_stage`, `render.render_stage`/`render.render_plan`, and
  `path.find`, the registry lookup the verb needs.
- **`codecraft/stats.py`** — the measured size of every built course's stages,
  recorded *in* the repo because half of it is unrecoverable: `tests` counts the
  `assert`/`raise` sites in a stage's check (recomputable from `course.py` at any
  time), while `mutants` is what that check was *proven* to catch by the
  development harness — which lives outside this repository and is cleaned up once
  a course ships. Eight courses carry both numbers; the other ten say `None`
  rather than a zero, and the page says "not measured" rather than lying.
  `cz stage os-from-scratch 5` → `93 asserts · 69 planted mutations the check must
  catch`; the eighteen built courses total **9,323 assertions** and **4,079
  caught mutations**.
- **The hardcoded repo root is gone.** 128 lines across 14 assembled `course.py`
  files carried `DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"`,
  and five more carried the same path as a `COURSE_REPO` default; all of them now
  derive the root from `__file__`. Verified by running **all fourteen courses from
  `/tmp`** with the templates in place — every stage reported `not implemented
  yet`, which is the proof the check found the repo and reached the stub — and G4
  with the solutions overlaid (`10/10 passing`, templates restored
  byte-for-byte). Two `# --- from /tmp/…` provenance comments were normalised in
  the same pass (they are the only stage separators in `mcp-` and
  `agents-from-scratch`).
- **Six registered rows**, in `path.py` (the authority `./cz path` renders) and in
  a new ROADMAP section that names each one's world, ladder and prerequisite:
  `G7 shell-from-scratch`, `G8 runtime-from-scratch`, `H5
  query-engine-from-scratch`, `H6 consensus-from-scratch`, `H7
  compression-from-scratch`, `L4 git-from-scratch`. `author` rows are **22** now.
  Two candidates were *not* registered, and the ROADMAP says why: a regex engine
  belongs as a stage of G5, and a hand-rolled crypto handshake duplicates the
  `cryptographic-library` project the G6 legacy slot already owns.
- Docs touched: `codecraft/README.md` (quickstart, the `cz` block, a worked stage
  page and what `asserts`/`mutants` mean), the root `README.md`, the `cz` shim's
  header, the web page's footer verb list, `ROADMAP.md`, and this file.

### The unit before it — G4 `os-from-scratch`, shipped in `4755f5c`

**G4 `os-from-scratch`** — ten stages, **641 mutations**, the thesis *an operating
system is what you write after the hardware breaks your last promise*. Provided:
`machine.py` (RAM, the page tables and the `MMU` that walks them, the `PageFault`
a trap carries as data, and the `Timer` the whole course advances by hand),
`devices.py` (a `Console`, and a `Disk` that loses everything it was not told to
sync) and `userland.py` (nine files with owners and modes, and eight programs
written in one op frame). Chain: 1 the map you were handed → 2 the frame allocator
and the bitmap inside it → 3 the address space and the translation you forgot to
invalidate → 4 the trap table and the fault as data → 5 the syscall boundary and
the pointer you did not check → 6 the process and the frame nobody gave back → 7
the scheduler and the wakeup that never came → 8 two CPUs and the critical section
nobody guarded → 9 the format and the write that was not ordered → 10 the
capstone: the userland, and the kernel's own ledger.

- `python3 /home/diego/Desarrollo/.g4-dev/verify_provided.py` → `provided: ALL
  PASS (171 checks)` for the three provided modules.
- `check_NN.py` → PASS for all ten; `run_all.py 01 … 10` → **`FAILED: 0`**;
  `mutate_all.py 01 … 10` → **`TOTAL 641/641`, `MISSED OR BROKEN: 0`**. Per stage:
  35, 49, 59, 62, 69, 81, 62, 60, 113, 51 — the capstone is the densest because
  every number in its report is a comparison with the machine's own records.
- `audit_course.py` → `AUDITED: 10, PROBLEMS: 0`; with no argument the audit
  refuses a `stage_10` that does not exist, which is how the solution's absence
  was caught before it was written.
- `assemble.py` → `assembled 10 checks, 5378 lines, compiles`;
  `probe_manifest.py` → `MANIFEST: 10/10 clean`; `smoke.py` → **`SMOKE: PASS`**
  (the manifest's ten stage entries by title and file name, every check green with
  the solutions overlaid, and every check red on the templates).
- `./cz run os-from-scratch` → `0/10` on the templates (every stage reporting
  `not implemented yet`), `10/10` with the solutions overlaid — *Course complete* —
  and the ten templates restored byte-for-byte (`cmp` clean against
  `.g4-dev/templates/`).
- Registered: `path.py` G4 → `course: "os-from-scratch"`, `kind: "ready"`, a real
  `why`; `ROADMAP.md` → **Twenty-five courses, 281 graded checks**, the
  `os-from-scratch` row right after `cpu-from-scratch`, the "missing entirely"
  paragraph now saying the machine stack's second half is built, and the plan
  paragraph naming G4's thesis with L1 as what comes next; a bullet in the root
  `README.md`; the course's own `README.md` (380 lines, sixty mistake bullets in
  stage order, the provided-world table and the ten-stage ladder).
- The **salvage**: `linux-from-scratch/` — nineteen files, the fifteen phase
  directories of `origin/claude/linux-from-scratch-curriculum-2qokjd`, 176
  exercises, prose left verbatim and staged here. The course is the graded ladder
  of the same idea; the prose is the reading beside it.
- Harness: `/home/diego/Desarrollo/.g4-dev/` (`CONTRACT.md` — frozen first, §0–§7
  with ten stage specs and the amendment rows — `DELEGATE.md`, `course_head.py`,
  `course_tail.py`, ten `check_NN.py`, ten `mutate_NN.py`, `run_all.py`,
  `mutate_all.py`, `audit_course.py`, `assemble.py`, `smoke.py`,
  `probe_manifest.py`, `verify_provided.py`, `templates/`, `STATE.md`). **Never in
  `/tmp`.**

Shapes worth keeping: **a refusal raises, a decision is returned** — a caller's
error (`KernelError`, `SyscallError`, `ProcessError`) is an exception, while the
kernel's own outcomes are data (`ERRNOS`, `ACTIONS`, `CAUSES`, `FAULT_WORDS`, and
the `{"allowed", "reason"}` an admission answers with), so a handler decides from
a value instead of from an exception it has to catch; **a promise is written
before the act it predicts** — one audit line per syscall, written *before* the
work, and the log line after it, so a report that folds both is a comparison of
three parties rather than of a record with itself, and the check can walk every
audit line and find exactly one log line whose value (or errno word) is what the
line promised; **the log line is ten keys with exactly one of `errno` and `value`
set**, and nothing is counted during the run — `report` recomputes every number
from the log and the audit, which is what makes `cross_check` able to disagree;
**the kernel's belief about the disk is computed independently** — `_Ledger` wraps
the device, records every write and mixes the same rolling checksum `Disk` does,
so a sector written straight to the device is caught; **`write` is one call number
with two implementations chosen by fd** — the console through stage 5's boundary,
a pipe through the kernel — which keeps the arity, the pointer check and the
promise identical on both paths; and **a budget is asked for before the work**
(`admit` never moves a frame and never raises for a limit that is spent, while
`apply_limit` raises for a resource this kernel does not have and for a limit that
is not a count).

Four contract amendments the *stages* forced, all recorded in `.g4-dev/CONTRACT.md`
§7 (the course wins over the plan): `machine.PageFault` gained `.user` — the
contract promised it and stage 4's delegate hit the `AttributeError`, with two
checks in `verify_provided.py` pinning it and its error bits; stage 9's `inodes`
argument became a **floor** (`max(inodes, len(files))`) rather than a count,
because a format that cannot hold the directory it is given is not a format; one
directory sector per inode *slot*, so a lookup's arithmetic is the layout's and
not a scan's; and three public names (`SECTOR`, `PROBLEMS`, `checksum`) added to
stage 9 so the format's own vocabulary is readable from outside.

## In flight — nothing

The next unit is **L1, `tcp-ip-from-scratch`** — the stack as data against a
provided lossy `wire.py` — and then phase L's other two series: **L2
`concurrent-servers-from-scratch`** (four models for one server, one workload,
identical answers) and **L3 `mqtt-broker-from-scratch`** (the wire format itself),
all three registered from `NETWORKING.md` and all three `author`. The nine rows
registered in the two units before this one queue behind them, one per slot — G7,
G8, H5, H6, H7, L4, then I13, I14, H8 — each carrying its own thesis in `path.py`,
each with its place in `cz dag`. After those: G5/G6 (phase G's remaining two, which
need checkers, not writing) and phase K's five. The backlog is **25 `author`, 6
`legacy`, 2 `salvage`, 27 `ready` — 60 rows** — `./cz path`, `./cz dag` and the
ROADMAP's own tables are authoritative over this file.

Two questions from earlier sessions are **answered**: the legacy, thin
`distributed-training/` directory stays exactly as it is (the user's call,
2026-10-14) — the roadmap marks it superseded and nothing touches it — and the
two lists in `AI-ENGINEER.md` are handled: 40 items mapped to existing courses,
five gaps registered as phase K.

## The workflow that produced G3, F2, J1, I9, H1, A8, J2, J3, J4, J5 and G4 — keep it

1. **Recon**, then **freeze a contract** in a dev directory beside the repo
   (`/home/diego/Desarrollo/.g4-dev/CONTRACT.md`): thesis, conventions, the
   provided modules, the execution model, and per stage the surface, the frozen
   shapes and the *mistake catalogue*. Freeze it before writing any stage; amend
   it — never silently — the moment a stage's real surface differs, with a table
   recording what the plan said, what the course does and why (J3's §7 has eight
   such rows, J4's nineteen, J5's three, G4's four).
2. **Never `/tmp`.** It was wiped three times and killed four delegates. The
   harness lives beside the repo and is re-synced after every change.
3. **One delegate per stage**, four files each (`stage_NN.py`,
   `solutions/stage_NN.py`, `check_NN.py`, `mutate_NN.py`). **A delegate's verdict
   is not evidence**: the parent re-runs `check_NN.py`, `mutate_NN.py`,
   `run_all.py NN`, `mutate_all.py NN`, `audit_course.py NN` — every time. Forty
   delegates across A8, J2, J3, J4 and J5, forty green; G4 ran the same drill one
   delegate at a time, and the one delegate that died after twenty-six minutes
   with zero files written is why the capstone was written by hand.
4. **Stages that import only stage 1 can be delegated concurrently** — in J5 all
   seven of 2–8 were spawned in one batch while stage 1 was already verified, then
   9 (composing 2–8) and only then the capstone, which imports all nine. G4's
   ladder is a chain (each stage composes the one below it), so the ten stages were
   written in order and the audit's "imports a *later* stage" rule never fired.
5. **Keep delegate briefs short** and point at the contract (G4's `DELEGATE.md` is
   the mechanical part, one page). Long briefs died with length-stops producing no
   files.
6. **The smoke and the acceptance run are where your own expectations get caught,
   not the course.** In G4 the check failed eleven times before it passed and every
   failure was the parent's arithmetic, never the kernel's: a task holding two
   frames inside a limit of four was asked to admit four more, a refused `cat`
   continues after its refused open (so its read, its write and its close are
   refused too), a fork's child inherits the parent's tick budget, and `hog` is
   stopped by its own loop's stop rather than by its next op. Treat a red
   assertion as a claim about *your* expectation until the stage's own behaviour
   proves otherwise.
7. **The `NotImplementedError` rule.** Every check must let it escape (a broad
   handler re-raises it first), or an untouched template reports as `✗` instead of
   `· not implemented yet` in `./cz run`. Verified both ways: `0/10` on the
   templates, `10/10` with the solutions overlaid.
8. **A copied harness carries the old paths — and the old prose.** A8's
   `assemble.py` still had `HERE = ".../.h1-dev"`; A8's `course_head.py` still
   described H1's course. `.g4-dev/` was copied from `.j5-dev/` and swept
   (`grep -Hn 'j5-dev\|metrics\|trace' .g4-dev/*.py`), and **`course_head.py`,
   `course_tail.py` and `audit_course.py`'s title string were rewritten from
   scratch** because the repointed copies still carried the old thesis and the old
   ten titles. Read the copied head's prose before committing, and make the probe
   run the assembled file rather than trusting it.
9. **Mutation hygiene**: rebuild the tree per mutation,
   `PYTHONDONTWRITEBYTECODE=1`, a stale anchor is `BROKEN` not `CAUGHT`, a mutant
   that hangs counts as `[hung  ]` = caught, and a no-op or unreachable mutation is
   worthless — it surfaces later as `MISSED`. A defect invisible in the *values*
   needs a spy, not a comparison. G4's first mutation run came back `42/52` with
   five `BROKEN` (indentation copied by eye) and five `MISSED`; three of the
   misses were fixed by *adding an assertion that reaches the branch* (the frames
   a task holds mid-run, the loop charged ten ticks rather than nine, a task
   stopped at its own tick budget), and the one defect no world program can reach
   was cut rather than kept as a mutation — every program this userland has ends
   with an explicit `exit`, so the "ran out of ops" path is defensive code and not
   a mutation target.
10. **Register, then commit**: `path.py`, `ROADMAP.md` (the count in the header,
    the ready row, the phase table, the plan paragraph), `AGENT-INFRA.md`'s two
    tables when a slot closes a numbered item, the root `README.md` bullet, the
    course's own `README.md`, and this file — after deleting
    `codecraft/{history.jsonl, profile.json, mentor_cache.json}` and every
    `__pycache__`. Then `git pull --rebase --autostash origin main && git push
    origin main`, then `./cz self-test`.

### Five traps worth remembering

- **`solutions/` sorts before `stage_*.py`.** A smoke that walks a directory and
  copies the solutions as it goes gets its overlay overwritten by the templates
  that follow. Copy the templates first, the solutions last — `.g4-dev/smoke.py`
  does exactly that.
- **`ast.get_source_segment` is not a body extractor.** Assemble bodies by line
  range (`statements[0].lineno` … `statements[-1].end_lineno`), verbatim, then
  dedent once; the symptom is an `IndentationError` in a file that looks correctly
  indented.
- **A course directory that is not committed yet has no `git checkout` to fall
  back on.** Overlaying the solutions onto the templates to watch `10/10` is worth
  it — but back the ten templates up to the dev directory first (`cp -a
  stage_*.py .g4-dev/templates/`) and `cmp` them after restoring. `git pull
  --rebase` also refuses with unstaged changes: `--autostash` is the way to push
  around them.
- **A delegate that contradicts the contract is usually right, and a death is not
  a verdict.** Three of J5's four stage-level findings began as a delegate's
  objection, and G4's stage 4 found the provided `PageFault` missing `.user` —
  a contract the world itself did not keep, fixed in the world and pinned by two
  checks. Treat an objection as evidence and re-run the check before overruling
  it; and when a reason, a branch or a mutation cannot be reached, the world or
  the order is wrong — not the check that failed to reach it.
- **A check is worth exactly the mutations it catches.** Fifty-one mutations and a
  check that pins the log act by act, the audit line by line, the report's six
  numbers against the machine's and four tampers that must be *detected* — that
  is the standard. An assertion nobody can break is not a test, and a mutation
  that nothing can catch is a design bug: strengthen the check or cut the rule.

## Ground rules

- **Deterministic, offline, integer-only.** No `time`, `threading`, `asyncio`,
  `random`, `os.environ`, `uuid`, no module-level mutable state, and **no float
  anywhere**: every count is an int, every ratio an exact reduced pair, so a run is
  a function of its inputs and a check can assert a number instead of timing
  something. G4 adds two of its own: a kernel is a *dict of records* rather than an
  object graph, and the only randomness in the whole course is the order the
  scheduler chooses to be fair in.
- **Docs in the repo are English**; the user writes Spanish, so answers are in
  Spanish with paths and identifiers verbatim.
- **The user's twelve-item list in `AGENT-INFRA.md` stays verbatim (Spanish)**,
  and so do the two lists in `AI-ENGINEER.md` and the three in `NETWORKING.md`;
  the analysis around them is English.
- `./cz` is `python3 codecraft/cli.py`. Before committing: no `history.jsonl`, no
  `profile.json`, no `mentor_cache.json`, no `__pycache__`.
- Ask before destructive commands; a course's own templates are the exercise, so
  never "fix" a stub into a solution outside `solutions/`.
