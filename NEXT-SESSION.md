# Next session — where everything is

Written at the end of the session that shipped **J3
(`durable-execution-from-scratch`)** — a run as a log rather than a process, ten
stages on a provided disk that loses everything it was not told to sync, 558
planted mutations, ten stages composed in one process. Everything in *Done* is
committed and pushed; the section after it is the commit that carries this file.

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

## Done, in the commit that follows this file

**J3 `durable-execution-from-scratch`** — ten stages, 558 mutations, the thesis
*a run is not the process that started it; it is the log on disk*. Provided:
`fleet.py` (J1's, verbatim), `disk.py` (the append-only journal, the **sync** that
is the only thing that makes a write a fact, the **`crash()`** that hands back
what it cost, and the two readings that never lie: `read` and `synced`) and
`work.py` (the six fixtures and `Effects`, which deliberately never
deduplicates). Chain: 1 the line and the journal that holds it → 2 the write that
was not synced did not happen → 3 replay, and the tail that was never finished →
4 the lease, and the owner that stops answering → 5 the heartbeat, and the worker
that dies holding the slot → 6 crash, and the process that comes after it → 7 the
effect that happens exactly once → 8 the resume, and the log that is not this
run's → 9 the report, and the number that has to come from the log → 10 two
workers, one killed holding the lease.

- `python3 /home/diego/Desarrollo/.j3-dev/verify_provided.py` → `provided: ALL
  PASS (36 checks)` for the three provided modules before a stage was written —
  and its **first** run failed one probe of the *parent's* (`fleet.dying` is
  `ok`/`died`/`ok` on attempts 1/2/3): the smoke earning its keep before a stage
  existed.
- `check_NN.py` → PASS for all ten; `run_all.py 01 … 10` → **`FAILED: 0`**.
- `mutate_all.py 01 … 10` → **`TOTAL 558/558`, `MISSED OR BROKEN: 0`** (one
  mutant hangs, counted as caught). Per stage: 49, 42, 49, 60, 56, 55, 62, 83,
  55, 47 — stage 8's 83 is the course's deepest check, `repair` and the resume's
  refusals being where an off-by-one costs data.
- `audit_course.py 01 … 10` → `AUDITED: 10, PROBLEMS: 0`; the audit refuses an
  import of a *later* stage, and stages 2–9 keep to stage 1 on purpose so each is
  solvable alone.
- `assemble.py` → `assembled 10 checks, 5098 lines, compiles`;
  `probe_manifest.py` → `MANIFEST: 10/10 clean`.
- `smoke.py` (in `.j3-dev/`) → **`SMOKE PASS — 39 probes, the durable course
  composed`**: a claim line hand-computed character for character, all nine kinds
  round-tripping, `write_line` appending and never syncing, `commit` versus
  `append` and `lost()` equal to what `crash()` discards, the state table and the
  torn tail by index and text, the deadline derived (`claimed_at + ticks`) with
  expiry inclusive at the boundary, a steal refused naming both owners, the beat
  that renames a deadline and the grace with both of its halves inclusive,
  `recover` writing nothing, a crash that loses the unsynced `result` and syncs
  the `expire` its dead owner's job owed, the intent synced before the effect and
  the count ending at exactly one on both `settle` branches, the checkpoint
  durable beside the journal and `repair` keeping whole lines only, every report
  counter hand-computed with a contradicted total refused, and the capstone: an
  uninterrupted run versus the same plan killed mid-run over the same disk ending
  on **equal states** with every key applied **exactly once**, two runs of one
  fixture equal value for value, the crashed log a prefix of the resumed one's,
  and every line of the log a line the course's own parser accepts.
- `./cz run durable-execution-from-scratch` → `0/10` on the templates (every
  stage reporting `not implemented yet`), `10/10` with the solutions overlaid,
  and the ten templates restored byte-for-byte (`cmp` clean, backed up in
  `.j3-dev/templates/`).
- Registered: `path.py` J3 → `course: "durable-execution-from-scratch"`,
  `kind: "ready"`, `prereq ["J1"]`, a real `why`; `ROADMAP.md` → **Twenty-two
  courses, 251 graded checks**, the ready row, the phase-J table's J3 row marked
  built, and the paragraph naming J4 as the next course; `AGENT-INFRA.md` → item 5
  now **yes**, the gaps table's J3 row marked built, and the paragraph that
  claimed "J3 is where an orchestrator's own task state starts to need
  replication" corrected to say what J3 does teach and what it does not; a bullet
  in the root `README.md`; the course's two READMEs.
- Harness: `/home/diego/Desarrollo/.j3-dev/` (`CONTRACT.md` — 30.7KB, frozen
  before any stage and amended eight times, §7 records every amendment —
  `course_head.py`, `course_tail.py`, ten `check_NN.py`, ten `mutate_NN.py`,
  `run_all.py`, `mutate_all.py`, `audit_course.py`, `assemble.py`, `smoke.py`,
  `probe_manifest.py`, `verify_provided.py`, `templates/`). **Never in `/tmp`.**

Shapes worth keeping: **a line is a prediction and only a sync is a fact**, so
`write_line`, `claim` and the `effect` line never sync while the `start` line, an
`intent` and a checkpoint always do; a **claim line carries a length**
(`ticks`), so the deadline is *derived* (`claimed_at + ticks` for a claim,
`now + ticks` for a beat) because a stored deadline goes stale exactly where a log
gets read; **`expired` is arithmetic and `dead` is policy**
(`misses >= MAX_MISSES and now >= deadline`, both halves the caller's, and
`recover` counting `now - deadline` floored at zero); **recovery is a reading**
(`recover` has no disk argument; stage 6's `crash` is what writes the `expire`
lines); **exactly-once is data** (the intent is synced, `settle` asks
`Effects.count(key)`, and the world never deduplicates, so a second application is
observable); `repair` is the one function that edits a log and it drops only a
torn fragment; `report` refuses a caller's total, table or world the lines
contradict; and stage 10 has **two death paths decided by the log**: a worker
killed before any sync leaves nothing behind (its claim was a prediction, so the
job is `pending` and re-issued at once) while a kill after a checkpoint's barrier
leaves a durable lease the next process must honour until it lapses.

## In flight — nothing

The next unit is **J4 (`sandbox-capabilities-from-scratch`)** — a capability set
per tool, a path jail, a modelled network policy, CPU/memory/time limits as
counters, secrets that never reach the model, and an audit line complete enough to
answer "what did it touch" — then J5 `agent-metrics-from-scratch`, then G4 (an OS
course; salvage `origin/claude/linux-from-scratch-curriculum-2qokjd`) and G5/G6.

Two questions from earlier sessions are **answered**: the legacy, thin
`distributed-training/` directory stays exactly as it is (the user's call,
2026-10-14) — the roadmap marks it superseded and nothing touches it — and the
two lists in `AI-ENGINEER.md` are handled: 40 items mapped to existing courses,
five gaps registered as phase K.

## The workflow that produced G3, F2, J1, I9, H1, A8, J2 and J3 — keep it

1. **Recon**, then **freeze a contract** in a dev directory beside the repo
   (`/home/diego/Desarrollo/.j3-dev/CONTRACT.md`): thesis, conventions, the
   provided modules, the execution model, and per stage the surface, the frozen
   shapes and the *mistake catalogue*. Freeze it before writing any stage; amend
   it — never silently — the moment a stage's real surface differs, with a table
   recording what the plan said, what the course does and why (J3's §7 has eight
   such rows, all of them improvements).
2. **Never `/tmp`.** It was wiped three times and killed four delegates. The
   harness lives beside the repo and is re-synced after every change.
3. **One delegate per stage**, four files each (`stage_NN.py`,
   `solutions/stage_NN.py`, `check_NN.py`, `mutate_NN.py`). **A delegate's verdict
   is not evidence**: the parent re-runs `check_NN.py`, `mutate_NN.py`,
   `run_all.py NN`, `mutate_all.py NN`, `audit_course.py NN` — every time.
   Thirty delegates across A8, J2 and J3, thirty green.
4. **Stages that import only stage 1 can be delegated concurrently** — in J3 all
   eight of 2–9 were spawned in one batch while stage 1 was already verified, and
   only the capstone waited, because it imports all nine. The audit enforces the
   rule, so a delegate that reaches for a later stage fails loudly instead of
   silently.
5. **Keep delegate briefs short** and point at the contract. Long briefs died
   with length-stops producing no files.
6. **The smoke is where your own expectations get caught, not the course.** In J3
   its first runs caught **four** of the parent's probe expectations
   (`fleet.dying`'s attempt sequence, the claim line's byte count, `torn` taking
   the *text* rather than a replay's records, `dead`'s two halves) and the stages
   were right every time. Write the smoke early, run it against the landed stages
   even before the capstone exists, and expect it to teach you the surfaces.
7. **The `NotImplementedError` rule.** Every check must let it escape (a broad
   handler re-raises it first), or an untouched template reports as `✗` instead of
   `· not implemented yet` in `./cz run`. Verified both ways: `0/10` on the
   templates, `10/10` with the solutions overlaid.
8. **A copied harness carries the old paths — and the old prose.** A8's
   `assemble.py` still had `HERE = ".../.h1-dev"`; A8's `course_head.py` still
   described H1's course. `.j3-dev/` was copied from `.j2-dev/` and swept with
   `sd` (`grep -Hn 'h1-dev\|h2-dev\|autograd\|orchestration' .j3-dev/*.py`), and
   **`course_head.py` and `course_tail.py` were rewritten from scratch** because
   the sed-repointed copies still carried J2's thesis and J2's ten titles. Read
   the copied head's prose before committing, and make the probe run the assembled
   file rather than trusting it.
9. **Mutation hygiene**: rebuild the tree per mutation,
   `PYTHONDONTWRITEBYTECODE=1`, a stale anchor is `BROKEN` not `CAUGHT`, a mutant
   that hangs counts as `[hung  ]` = caught, and a no-op mutation is worthless —
   it surfaces later as `MISSED`. A defect invisible in the *values* needs a spy,
   not a comparison.
10. **Register, then commit**: `path.py`, `ROADMAP.md` (the count in the header,
    the ready row, the phase table, the plan paragraph), `AGENT-INFRA.md`'s two
    tables when a slot closes a numbered item, the root `README.md` bullet, the
    course's two READMEs, and this file — after deleting
    `codecraft/{history.jsonl, profile.json, mentor_cache.json}` and every
    `__pycache__`. Then `git pull --rebase --autostash origin main && git push
    origin main`.

### Four traps worth remembering

- **`solutions/` sorts before `stage_*.py`.** A smoke that walks a directory and
  copies the solutions as it goes gets its overlay overwritten by the templates
  that follow. Copy the templates first, the solutions last — `.j3-dev/smoke.py`
  does exactly that.
- **`ast.get_source_segment` is not a body extractor.** Assemble bodies by line
  range (`statements[0].lineno` … `statements[-1].end_lineno`), verbatim, then
  dedent once; the symptom is an `IndentationError` in a file that looks correctly
  indented.
- **A course directory that is not committed yet has no `git checkout` to fall
  back on.** Overlaying the solutions onto the templates to watch `10/10` is worth
  it — but back the ten templates up to the dev directory first (`cp -a
  stage_*.py .j3-dev/templates/`) and `cmp` them after restoring. `git pull
  --rebase` also refuses with unstaged changes: `--autostash` is the way to push
  around them.
- **The parent's own file can be the moving part.** J3's stage 1 was written and
  verified *before* spawning the other eight, so its surface was frozen while they
  read it; a delegate that edits an already-verified stage's file is the failure
  mode this ordering exists to prevent.

## Ground rules

- **Deterministic, offline, integer-only.** No `time`, `threading`, `asyncio`,
  `random`, `os.environ`, `uuid`, no module-level mutable state, and **no float
  anywhere**: every count is an int, every ratio an exact reduced pair, so a run
  is a function of its inputs and a check can assert a number instead of timing
  something. J3 is the strongest version of this rule for a *crash*: the disk is
  simulated, so "what would a crash cost right now?" is a question a check answers
  by assertion instead of trusting.
- **Docs in the repo are English**; the user writes Spanish, so answers are in
  Spanish with paths and identifiers verbatim.
- **The user's twelve-item list in `AGENT-INFRA.md` stays verbatim (Spanish)**,
  and so do the two lists in `AI-ENGINEER.md`; the analysis around them is
  English.
- `./cz` is `python3 codecraft/cli.py`. Before committing: no `history.jsonl`, no
  `profile.json`, no `mentor_cache.json`, no `__pycache__`.
- Ask before destructive commands; a course's own templates are the exercise, so
  never "fix" a stub into a solution outside `solutions/`.
