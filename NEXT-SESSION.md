# Next session — where everything is

Written at the end of the session that shipped **A8 (`autograd-from-scratch`)**
and then **J2 (`orchestration-from-scratch`)** — ten stages between a task that is
too big for one agent and a run you can replay, on J1's clock, a scripted fleet and
nine raw plans, 526 planted mutations, ten stages composed in one process.
Everything in *Done* is committed and pushed; the section after it is the commit
that carries this file.

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

## Done, in the commit that follows this file

**J2 `orchestration-from-scratch`** — ten stages, 526 mutations, the thesis *a big
task is a graph of small ones, and the graph is data*. Provided: `fleet.py` (J1's,
verbatim), `agents.py` (the model as a scripted callable) and `graphs.py` (nine raw
plans, two of them broken on purpose). Chain: 1 the subtask and the graph →
2 the order a dependency forces → 3 the wave is not the schedule → 4 the handoff
that carries its own context → 5 the reviewer that can reject → 6 one failure and
the rest of the graph → 7 the approval and the effect it stops → 8 the budget
checked before the call → 9 the record and the report from it → 10 two runs,
identical bytes.

- `python3 /home/diego/Desarrollo/.j2-dev/verify_provided.py` → `provided: ALL
  PASS (65 checks)` for the three provided modules before a stage was written.
- `python3 /home/diego/Desarrollo/.j2-dev/check_NN.py` → PASS for all ten;
  `run_all.py 01 … 10` → **`FAILED: 0`**.
- `mutate_all.py 01 … 10` → **`TOTAL 526/526`, `MISSED OR BROKEN: 0`**. Per stage:
  51, 47, 46, 70, 49, 40, 48, 49, 64, 62.
- `audit_course.py 01 … 10` → `AUDITED: 10, PROBLEMS: 0` — the audit also enforces
  that a stage imports **only stage 1** plus the provided modules.
- `assemble.py` → `assembled 10 checks, 4660 lines, compiles`;
  `probe_manifest.py` → `MANIFEST: 10/10 clean`.
- `smoke.py` (in `.j2-dev/`) → **`SMOKE PASS — 11 probes, ten stages composed, one
  deterministic run`**: the diamond's four nodes and three waves, the typo that
  names the key it meant, the cycle refused with its path, a skip-level edge that
  runs while an earlier wave is still working, the handoff labelled and sorted and
  cut to the budget each dependency declared, a rejection that reworks up to
  `MAX_REWORK`, a failure that skips its dependent and keeps its sibling, an
  effect held while its approval is unanswered, the budget asked before the call
  with an exact fit affordable, the report recomputed from the record, and the
  capstone: an approved effect runs, a denied one never does, and two runs of one
  fixture are equal value for value.
- `./cz run orchestration-from-scratch` → `0/10` on the templates (every stage
  reporting `not implemented yet`), `Course complete` with the solutions overlaid,
  and the ten templates restored byte-for-byte (`cmp` clean, backed up in
  `.j2-dev/templates/`).
- Registered: `path.py` J2 → `course: "orchestration-from-scratch"`,
  `kind: "ready"`, `prereq ["J1", "C2"]`, a real `why`; `ROADMAP.md` →
  **Twenty-one courses, 241 graded checks**, the ready row, the phase-J table's
  J2 row marked built, and the paragraph naming J3 as the next course;
  `AGENT-INFRA.md` → items 3 and 4 now **yes** (J1 and J2), the gaps table's J1/J2
  rows marked built; a bullet in the root `README.md`;
  `orchestration-from-scratch/README.md` and `solutions/README.md`.
- Harness: `/home/diego/Desarrollo/.j2-dev/` (`CONTRACT.md`, ten `check_NN.py`,
  ten `mutate_NN.py`, `run_all.py`, `mutate_all.py`, `audit_course.py`,
  `assemble.py`, `course_head.py`, `course_tail.py`, `smoke.py`,
  `probe_manifest.py`, `verify_provided.py`, and `templates/` — the ten templates
  backed up before the overlay). **Never in `/tmp`** — it was wiped three times in
  the H1 session and killed four delegates.

Shapes worth keeping: a **token is one character** (a byte count would smuggle in
an encoding), so `budgeted` is `text[:tokens]` and exact; a state table maps a node
to a bare status **or** to `{"status", "text"}`, and a node the table does not name
is `pending`; `accepts(reply)` is the *acceptance predicate* (True only for the
accept verdict) while stage 7's membership test is `answers`; the budget is
`spent + node.tokens <= budget`, asked **before** the call; an effect's approval is
the dependency whose agent label is the approver, and `gate_status` **raises** with
`effect-before-approval` when the dispatch must be held; the record's six fields
never carry text, and `report` refuses a caller-supplied total the record
contradicts.

## In flight — nothing

The next unit is **J3 (`durable-execution-from-scratch`)** — leases and
heartbeats, a write-ahead log, replay, resume and recovery after a worker is
killed holding the lease, exactly-once effects — then J4
`sandbox-capabilities-from-scratch`, J5 `agent-metrics-from-scratch`, then G4 (an
OS course; salvage `origin/claude/linux-from-scratch-curriculum-2qokjd`) and
G5/G6.

One question from the previous session is now **answered**: the legacy, thin
`distributed-training/` directory stays exactly as it is (the user's call,
2026-10-14) — the roadmap marks it superseded and nothing touches it.

A second list arrived mid-session and is registered: **`AI-ENGINEER.md`** keeps
two user lists verbatim (25 AI-engineer interview problems, 15 things to build)
with a coverage table for all 40 items against the existing courses, and the five
gaps it found are **phase K** in `codecraft/ROADMAP.md` and `path.py` (K1
`agentic-retrieval-from-scratch`, K2 `prompt-ops-from-scratch`, K3
`memory-engine-from-scratch`, K4 `fine-tuning-from-scratch`, K5
`agent-privacy-from-scratch`, all `kind: "author"`).

## The workflow that produced G3, F2, J1, I9, H1, A8 and J2 — keep it

1. **Recon**, then **freeze a contract** in a dev directory beside the repo
   (`/home/diego/Desarrollo/.j2-dev/CONTRACT.md`): thesis, conventions, the
   provided modules, and per stage the surface, the frozen shapes and the
   *mistake catalogue*. Freeze it before writing any stage; amend it the moment a
   stage's real signature differs from the plan — the path references inside it
   too.
2. **Never `/tmp`.** It was wiped three times and killed four delegates. The
   harness lives beside the repo and is re-synced after every change.
3. **One delegate per stage**, four files each (`stage_NN.py`,
   `solutions/stage_NN.py`, `check_NN.py`, `mutate_NN.py`). **A delegate's verdict
   is not evidence**: the parent re-runs `check_NN.py`, `mutate_NN.py`,
   `run_all.py NN`, `mutate_all.py NN`, `audit_course.py NN` — every time. Twenty
   delegates across A8 and J2, twenty green.
4. **Stages that import only stage 1 can be delegated concurrently.** In J2 all
   nine of 2–9 ran in parallel with 1 already verified, and only the capstone
   waited — it imports all nine. The audit enforces the rule, so a delegate that
   reaches for a sibling fails loudly instead of silently.
5. **Keep delegate briefs short** and point at the contract. Long briefs died
   with length-stops producing no files.
6. **The smoke is where your own expectations get caught, not the course.** In J2
   it caught **three** of the parent's probe expectations and the stages were
   right every time: `runnable` on a diamond where a sibling is `running` is `()`
   (a wave-rule discriminator needs a *skip-level* edge), `handoff` returns one
   `<id>: <cut>` line per accepted dependency and not a list, and `affordable` is
   `spent + node.tokens <= budget` against *that* fixture's declared tokens. Write
   the smoke early, run it against stubs for the missing stages, and expect it to
   teach you the surfaces. A delegate may also **rename a frozen helper** and be
   right: J2's `accepts` came back as the acceptance predicate (with `answers` as
   the membership test) and stage 8's ledger as `{"spent", "budget"}` — the
   contract was amended, not the stage.
7. **The `NotImplementedError` rule.** Every check must let it escape (a broad
   handler re-raises it first), or an untouched template reports as `✗` instead of
   `· not implemented yet` in `./cz run`. Verified both ways: `0/10` on the
   templates, `10/10` with the solutions overlaid.
8. **A copied harness carries the old paths — and the old prose.** A8's
   `assemble.py` still had `HERE = ".../.h1-dev"` and assembled H1's manifest;
   A8's `course_head.py` still described H1's course and needed a follow-up
   commit; `.j2-dev/` was copied from `.h2-dev/` and had to be swept the same way
   (`grep -Hn 'h1-dev\|h2-dev\|autograd'` catches the leftovers, and the two
   copied `model_*` files were deleted). Repoint every `HERE`/`*_REPO`, read the
   copied `course_head.py` prose before committing, and make the probe run the
   assembled file rather than trusting it.
9. **Mutation hygiene**: rebuild the tree per mutation,
   `PYTHONDONTWRITEBYTECODE=1`, a stale anchor is `BROKEN` not `CAUGHT`, a mutant
   that hangs counts as `[hung  ]` = caught, and a no-op mutation is worthless —
   it surfaces later as `MISSED`. A defect invisible in the *values* (a schedule
   built from the wrong order) needs a spy, not a comparison.
10. **Register, then commit**: `path.py`, `ROADMAP.md` (the count in the header,
    the ready row, the phase table, the plan paragraph), `AGENT-INFRA.md`'s two
    tables when a slot closes a numbered item, the root `README.md` bullet, the
    course's two READMEs, and this file — after deleting `codecraft/{history.jsonl,
    profile.json, mentor_cache.json}` and every `__pycache__`. Then
    `git pull --rebase --autostash origin main && git push origin main`.

### Three traps worth remembering

- **`solutions/` sorts before `stage_*.py`.** A smoke that walks a directory and
  copies the solutions as it goes gets its overlay overwritten by the templates
  that follow. Copy the templates first, the solutions last.
- **`ast.get_source_segment` is not a body extractor.** Assemble bodies by line
  range (`statements[0].lineno` … `statements[-1].end_lineno`), verbatim, then
  dedent once; the symptom is an `IndentationError` in a file that looks correctly
  indented.
- **A course directory that is not committed yet has no `git checkout` to fall
  back on.** Overlaying the solutions onto the templates to watch `10/10` is worth
  it — but back the ten templates up to the dev directory first (`cp -a
  stage_*.py .j2-dev/templates/`) and `cmp` them after restoring. `git pull
  --rebase` also refuses with unstaged changes: `--autostash` is the way to push
  around them.

## Ground rules

- **Deterministic, offline, integer-only.** No `time`, `threading`, `asyncio`,
  `random`, `os.environ`, `uuid`, no module-level mutable state, and **no float
  anywhere**: every count is an int, every ratio an exact reduced pair, so a run
  is a function of its inputs and a check can assert a number instead of timing
  something. J2 is the strongest version of this rule for a *simulator* — the
  clock is injected, the agents are scripts, and two runs of one graph must return
  identical values, which the capstone's check asserts directly.
- **Docs in the repo are English**; the user writes Spanish, so answers are in
  Spanish with paths and identifiers verbatim.
- **The user's twelve-item list in `AGENT-INFRA.md` stays verbatim (Spanish)**;
  the analysis around it is English.
- `./cz` is `python3 codecraft/cli.py`. Before committing: no `history.jsonl`, no
  `profile.json`, no `mentor_cache.json`, no `__pycache__`.
- Ask before destructive commands; a course's own templates are the exercise, so
  never "fix" a stub into a solution outside `solutions/`.
