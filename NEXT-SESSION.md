# Next session — where everything is

Written at the end of the session that shipped **J5
(`agent-metrics-from-scratch`)** — a trace is not a metric: ten stages over a
fleet that writes down what happened, from the event to a report whose every
number is recomputed from the lines and cross-checked against the fleet's own
count of the same run, 510 planted mutations. Everything in *Done* is committed
and pushed; the section after it is the commit that carries this file.

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

## Done, in the commit that follows this file

**J5 `agent-metrics-from-scratch`** — ten stages, **510 mutations**, the thesis
*a trace is not a metric*. Provided: `fleet.py` (J1's, byte-identical,
`sha256 12e9dc0d…019ce`) and `telemetry.py` — the fleet's twelve-field event and
the five kinds, `ABSENT` for a field a kind does not carry, a closed and
space-free `ERRORS` vocabulary (the line has no quoting, so no value may contain
a space), E1's six-key `TRACE_KEYS`, the twelve `SUMMARY_KEYS`, `TOKENS` and
`PRICES` (a price is a property of the **pool**), `WINDOWS`, `SLOS` (a target and
a budget in the metric's own unit), and `record()`, which runs the fleet
deterministically and **counts what it did as it goes** — a count deliberately
*not* in the lines it writes, which is why `read()` cannot produce one and why the
report's cross-check against it means something. Chain: 1 the event, and the fact
it records → 2 the window, and the fold → 3 queue depth is a gauge, not a counter
→ 4 the percentile is an index → 5 latency, and where the time went → 6 tokens,
and the cost that was summed first → 7 failures and retries are rates → 8 the
window is the decision → 9 the report, and the fleet's own count → 10 the
capstone: two windows, one answer.

- `python3 /home/diego/Desarrollo/.j5-dev/verify_provided.py` → `provided: ALL
  PASS (82 checks)` for the two provided modules.
- `check_NN.py` → PASS for all ten; `run_all.py 01 … 10` → **`FAILED: 0`**;
  `mutate_all.py 01 … 10` → **`TOTAL 510/510`, `MISSED OR BROKEN: 0`**. Per stage:
  43, 40, 45, 47, 49, 47, 39, 67, 61, 72 — the capstone is the densest (an order
  of questions, a budget spent by the size of an overshoot, and a run that must be
  a pure function of its arguments), and stage 7 is the thinnest because a rate is
  one door with two counts behind it.
- `audit_course.py 01 … 10` → `AUDITED: 10, PROBLEMS: 0`; the audit refuses an
  import of a *later* stage, and stages 2–8 keep to stage 1 on purpose so seven of
  them could be delegated at once.
- `assemble.py` → `assembled 10 checks, 4062 lines, compiles`;
  `probe_manifest.py` → `MANIFEST: 10/10 clean`.
- `smoke.py` (in `.j5-dev/`) → **`smoke: 51 probes PASS`** over one real run of the
  fleet: the header and its twelve fields in order, an absent field spelled `-`,
  a `started` event carrying an outcome refused, the half-open window both ways, a
  tumbling set that covers the run exactly once and a sliding set that deliberately
  does not, depth never negative on a retried run, a percentile that is always a
  sample somebody recorded, `wait + service + gap == total` per task, micros summed
  and divided once, a rate whose denominator is named in its own refusal, a step
  past the width refused as leaving a hole, the report equal to the fleet's own
  count *key by key*, a report the events do not support refused naming the key
  and both numbers, and the capstone: two runs equal field for field, a budget spent by
  the sum of the overshoots rather than by the number of windows that breached, a
  burn that is the same spent number as a share of the budget, a budget of zero
  spent by the first breach with the alert naming that window, and a budget never
  overspent firing nothing.
- `./cz run agent-metrics-from-scratch` → `0/10` on the templates (every stage
  reporting `not implemented yet`), `10/10` with the solutions overlaid, and the
  ten templates restored byte-for-byte (`cmp` clean, backed up in
  `.j5-dev/templates/`).
- Registered: `path.py` J5 → `course: "agent-metrics-from-scratch"`,
  `kind: "ready"`, `prereq ["J1", "A7"]`, a real `why`; `ROADMAP.md` →
  **Twenty-four courses, 271 graded checks**, a ready row, the phase-J table's J5
  row marked built, and the paragraph naming J5's thesis, with G4 and phase L
  named as what comes next; `AGENT-INFRA.md` → item **#11 now yes** with J5 named
  in it, the gaps table's J5 row marked built, and the closing paragraph updated
  (phase J is complete: #3, #4, #5, #8, #10 and #11 taught end to end by J1
  through J5, with item 2 the only part still reached in part); a bullet in the
  root `README.md`; the course's own `README.md`.
- Harness: `/home/diego/Desarrollo/.j5-dev/` (`CONTRACT.md` — frozen before any
  stage, §0–§7 with ten stage specs and three amendment rows — `DELEGATE.md`,
  `course_head.py`, `course_tail.py`, ten `check_NN.py`, ten `mutate_NN.py`,
  `run_all.py`, `mutate_all.py`, `audit_course.py`, `assemble.py`, `smoke.py`,
  `probe_manifest.py`, `verify_provided.py`, `templates/`). **Never in `/tmp`.**

Shapes worth keeping: **a fold takes the events and nothing else** — no function
in the course takes a count, a total or a fleet object alongside the events it is
folding, because a number that arrives from outside is a number the fold cannot be
wrong about; **an unmeasured field is not a zero** (`count([])` is `0` because
nothing was in the window is a fact, while `total`/`mean` over events that never
carried the field *refuse*, because "nobody measured this" and "the measurement was
zero" are different statements and only one is true); **a percentile is an index,
not an interpolation** — `ceil(n·p) − 1`, clamped, always a sample somebody
recorded, and with floats banned there is nothing to interpolate with; **a gauge is
derived, never summed** — depth is a state machine over the kinds in tick order,
where a queue-full drop of a task that never entered is no departure at all and a
depth that would go negative is refused naming the task that left twice; **sum,
then divide** — micros are summed over the events and divided **once** by the tasks
that finished, never a mean of a column of per-event ratios; **a rate names its
denominator** — a failure is an *attempt* and not a task, a retry is a second
attempt, and the refusal says which count it wanted; **the window's ends are the
decision** — `[start, end)` with `tick == end` in the next window, a tumbling set
that partitions a run and a sliding set that deliberately does not (the events in
the overlap are in two folds and summing them would count them twice), a step past
the width refused as leaving a hole, and the last window cut at the end; **the
report is the events or it is wrong** — every cell is recomputed and then compared
against the fleet's own count, naming the key and **both** numbers when they
disagree, with `audit` reporting the same disagreement instead of raising; and the
capstone's **budget is spent by the size of the overshoot**, not by the number of
windows that breached, its `burn` is the same spent number as an exact share, and
its alert names the window that spent the last of it — a budget of zero is spent
by the first breach.

Three contract amendments the *stages* forced, all recorded in `.j5-dev/CONTRACT.md`
§7 (the course wins over the plan): `telemetry.RETRY_BACKOFF = 1` was **added**
because without it every run the world could produce had `task_latency ==
sum(attempt_latency)` exactly, which made stage 5's **gap** unreachable in a real
run — a field, a branch or a mutation no run can reach is a design bug and not a
corner case (J4's lesson, one course later); depth is a **state machine** over the
kinds in tick order rather than the two-counter difference the plan wrote, because
two delegates independently showed the plan's formula drives depth to −1 on a
retried run (a retry is the same task coming back, and the departure that follows
a failure is the retry, not a task leaving); and stage 8 imports **stage 1 only**
and writes its own window arithmetic, because the plan had it composing stage 2's
window and stage 3's gauge, which would have serialized the whole middle of the
ladder behind them — the ladder is what makes seven delegates possible.

## In flight — nothing

The next unit is **G4, the OS course** — a *salvage* on
`origin/claude/linux-from-scratch-curriculum-2qokjd` — and then phase L's three
series: **L1 `tcp-ip-from-scratch`** (the stack as data against a provided lossy
`wire.py`), **L2 `concurrent-servers-from-scratch`** (four models for one server,
one workload, identical answers) and **L3 `mqtt-broker-from-scratch`** (the wire
format itself), all three registered from `NETWORKING.md` and all three `author`.
After those: G5/G6 (phase G's remaining two) and phase K's five. The backlog is
**16 `author`, 6 `legacy`, 3 `salvage`, 26 `ready`** — `./cz path` and the
ROADMAP's own tables are authoritative over this file.

Two questions from earlier sessions are **answered**: the legacy, thin
`distributed-training/` directory stays exactly as it is (the user's call,
2026-10-14) — the roadmap marks it superseded and nothing touches it — and the
two lists in `AI-ENGINEER.md` are handled: 40 items mapped to existing courses,
five gaps registered as phase K.

## The workflow that produced G3, F2, J1, I9, H1, A8, J2, J3, J4 and J5 — keep it

1. **Recon**, then **freeze a contract** in a dev directory beside the repo
   (`/home/diego/Desarrollo/.j5-dev/CONTRACT.md`): thesis, conventions, the
   provided modules, the execution model, and per stage the surface, the frozen
   shapes and the *mistake catalogue*. Freeze it before writing any stage; amend
   it — never silently — the moment a stage's real surface differs, with a table
   recording what the plan said, what the course does and why (J3's §7 has eight
   such rows, J4's nineteen, J5's three).
2. **Never `/tmp`.** It was wiped three times and killed four delegates. The
   harness lives beside the repo and is re-synced after every change.
3. **One delegate per stage**, four files each (`stage_NN.py`,
   `solutions/stage_NN.py`, `check_NN.py`, `mutate_NN.py`). **A delegate's verdict
   is not evidence**: the parent re-runs `check_NN.py`, `mutate_NN.py`,
   `run_all.py NN`, `mutate_all.py NN`, `audit_course.py NN` — every time. Forty
   delegates across A8, J2, J3, J4 and J5, forty green.
4. **Stages that import only stage 1 can be delegated concurrently** — in J5 all
   seven of 2–8 were spawned in one batch while stage 1 was already verified, then
   9 (composing 2–8) and only then the capstone, which imports all nine. The audit
   enforces the rule, so a delegate that reaches for a later stage fails loudly
   instead of silently.
5. **Keep delegate briefs short** and point at the contract (J5's `DELEGATE.md` is
   the mechanical part, one page). Long briefs died with length-stops producing no
   files.
6. **The smoke is where your own expectations get caught, not the course.** In J5
   it caught **four** of the parent's probe expectations and the stages were right
   every time: a `sum(fold["events"] …)` over a **tuple** (use `len`), a chained
   comparison (`s7.failures(events) == summary["failures"] > summary["tasks"]`
   silently means `… == … and … > …`, and `5 > 5` is false), a **reduced** pair
   (`s2.mean` returns `(19, 5)` out of 38 over 10 carriers, so asserting its
   denominator equals the carrier count contradicts the reduction the same probe
   asserts), and a per-window latency computed with `stage_05.attempt_latency` on
   the window's own events, which *refuses* when a window boundary cut an attempt's
   start — an attempt's latency belongs to the tick its **finish** fell in, which
   is stage 9's rule and the only reading a boundary cannot break. Write the smoke
   early, run it against the landed stages even before the capstone exists, and
   treat a red probe as a claim about *your* expectation until the stage's own
   check proves otherwise.
7. **The `NotImplementedError` rule.** Every check must let it escape (a broad
   handler re-raises it first), or an untouched template reports as `✗` instead of
   `· not implemented yet` in `./cz run`. Verified both ways: `0/10` on the
   templates, `10/10` with the solutions overlaid.
8. **A copied harness carries the old paths — and the old prose.** A8's
   `assemble.py` still had `HERE = ".../.h1-dev"`; A8's `course_head.py` still
   described H1's course. `.j5-dev/` was copied from `.j4-dev/` and swept
   (`grep -Hn 'j4-dev\|sandbox\|capability' .j5-dev/*.py`), and **`course_head.py`,
   `course_tail.py` and `audit_course.py`'s title string were rewritten from
   scratch** because the repointed copies still carried the old thesis and the old
   ten titles. Read the copied head's prose before committing, and make the probe
   run the assembled file rather than trusting it.
9. **Mutation hygiene**: rebuild the tree per mutation,
   `PYTHONDONTWRITEBYTECODE=1`, a stale anchor is `BROKEN` not `CAUGHT`, a mutant
   that hangs counts as `[hung  ]` = caught, and a no-op or unreachable mutation is
   worthless — it surfaces later as `MISSED`. A defect invisible in the *values*
   needs a spy, not a comparison.
10. **Register, then commit**: `path.py`, `ROADMAP.md` (the count in the header,
    the ready row, the phase table, the plan paragraph), `AGENT-INFRA.md`'s two
    tables when a slot closes a numbered item, the root `README.md` bullet, the
    course's own `README.md`, and this file — after deleting
    `codecraft/{history.jsonl, profile.json, mentor_cache.json}` and every
    `__pycache__`. Then `git pull --rebase --autostash origin main && git push
    origin main`, then `./cz self-test`.

### Four traps worth remembering

- **`solutions/` sorts before `stage_*.py`.** A smoke that walks a directory and
  copies the solutions as it goes gets its overlay overwritten by the templates
  that follow. Copy the templates first, the solutions last — `.j5-dev/smoke.py`
  does exactly that.
- **`ast.get_source_segment` is not a body extractor.** Assemble bodies by line
  range (`statements[0].lineno` … `statements[-1].end_lineno`), verbatim, then
  dedent once; the symptom is an `IndentationError` in a file that looks correctly
  indented.
- **A course directory that is not committed yet has no `git checkout` to fall
  back on.** Overlaying the solutions onto the templates to watch `10/10` is worth
  it — but back the ten templates up to the dev directory first (`cp -a
  stage_*.py .j5-dev/templates/`) and `cmp` them after restoring. `git pull
  --rebase` also refuses with unstaged changes: `--autostash` is the way to push
  around them.
- **A delegate that contradicts the contract is usually right.** Three of J5's
  four stage-level findings began as a delegate's objection (the depth state
  machine, §4.9's attribution rule, and the per-window metric that stage 9's fold
  answers rather than the window's own events), and the capstone found the three
  bugs in the parent's own smoke. Treat an objection as evidence and re-run the
  check before overruling it; and when a reason, a branch or a mutation cannot be
  reached, the world or the order is wrong — not the check that failed to reach it.
- **The parent's own file can be the moving part.** J5's stage 1 was written and
  verified *before* spawning the other seven, so its surface was frozen while they
  read it; a delegate that edits an already-verified stage's file is the failure
  mode this ordering exists to prevent.

## Ground rules

- **Deterministic, offline, integer-only.** No `time`, `threading`, `asyncio`,
  `random`, `os.environ`, `uuid`, no module-level mutable state, and **no float
  anywhere**: every count is an int, every ratio an exact reduced pair, so a run is
  a function of its inputs and a check can assert a number instead of timing
  something. J5 is the strongest version of this rule short of a theorem prover —
  *no float literal in a stage's template or its solution*, with a float allowed
  only inside `check_NN.py`, where it exists to be refused.
- **Docs in the repo are English**; the user writes Spanish, so answers are in
  Spanish with paths and identifiers verbatim.
- **The user's twelve-item list in `AGENT-INFRA.md` stays verbatim (Spanish)**,
  and so do the two lists in `AI-ENGINEER.md` and the three in `NETWORKING.md`;
  the analysis around them is English.
- `./cz` is `python3 codecraft/cli.py`. Before committing: no `history.jsonl`, no
  `profile.json`, no `mentor_cache.json`, no `__pycache__`.
- Ask before destructive commands; a course's own templates are the exercise, so
  never "fix" a stub into a solution outside `solutions/`.
