# Next session — where everything is

Written at the end of the session that shipped **J4
(`sandbox-capabilities-from-scratch`)** — an agent's power as the intersection of
what its tools declare, what its principal granted and what the world will still
afford, ten stages on a world made of data (no filesystem, no socket, no float),
494 planted mutations. Everything in *Done* is committed and pushed; the section
after it is the commit that carries this file.

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

## Done, in the commit that follows this file

**J4 `sandbox-capabilities-from-scratch`** — ten stages, 494 mutations, the
thesis *an agent's power is the intersection of what its tools declare, what its
principal granted and what the world will still afford*. Provided: `fleet.py`
(J1's, byte-identical), `vfs.py` (the filesystem as data — nothing normalised, a
`..` refused rather than resolved by a prefix test, a refusal that leaves no log
entry, and a question that is not a touch) and `tools.py` (ten tools that each
declare a demand, a cost and what kind of thing they act on, five hosts, three
secrets, five principals, five plans, four scripted shell commands, and the four
objects that keep their own records: `Meter`, `Wire`, `Vault`, `Audit`). Chain: 1
the capability, and the tool that declares it → 2 the grant, and the intersection
that decides → 3 the path jail, and the escape that is a string test → 4 the
network policy, and the host nobody can read → 5 the limits, and the charge that
is all or nothing → 6 the secret that never reaches the model → 7 the audit line,
and the reason that is a word → 8 the call that never happens (the six questions
in one order, the line written **before** the act) → 9 the report, and the world's
own record → 10 an agent, its policy, and the answer to what it touched.

- `python3 /home/diego/Desarrollo/.j4-dev/verify_provided.py` → `provided: ALL
  PASS (78 checks)` for the three provided modules.
- `check_NN.py` → PASS for all ten; `run_all.py 01 … 10` → **`FAILED: 0`**;
  `mutate_all.py 01 … 10` → **`TOTAL 494/494`, `MISSED OR BROKEN: 0`**. Per stage:
  48, 54, 39, 42, 50, 60, 54, 51, 53, 43 — stage 7's audit line and stage 6's
  encodings are where an off-by-one costs the most (a suggestion one typo away, a
  base64 secret with its padding stripped).
- `audit_course.py 01 … 10` → `AUDITED: 10, PROBLEMS: 0`; the audit refuses an
  import of a *later* stage, and stages 2–7 keep to stages 1 on purpose so six of
  them could be delegated at once.
- `assemble.py` → `assembled 10 checks, 4326 lines, compiles`;
  `probe_manifest.py` → `MANIFEST: 10/10 clean`.
- `smoke.py` (in `.j4-dev/`) → **`SMOKE PASS — 65 probes, the sandbox course
  composed`**: the running arithmetic of a `..` escape, a grant whose answer is
  the difference and never a boolean, a jail that resolves before it judges and
  refuses the sibling root a prefix test hands over, the six questions each
  answering with its own reason and the *first* no winning, a denial that touches
  nothing and spends nothing (proved with a poisoned `VFS`, `Wire` and `Vault`),
  the line present and parsed for a denial, the predicted `bytes` equal to what
  the world then records for a read, a write and a remove, the report recomputed
  from the lines and cross-checked against `VFS.log()`, `Wire.dialled()` and
  `Vault.reads()`, `audit` reporting a disagreement instead of raising, and the
  capstone: two runs of one plan equal field for field, a counter the meter cannot
  pay stopping the run, the call cap stopping it *before* the call is made, an
  `intern` walked past two `capability` denials with the world untouched, and a
  `vaultkeeper` running the deploy plan with no secret's value anywhere in the
  audit, the report or an observation.
- `./cz run sandbox-capabilities-from-scratch` → `0/10` on the templates (every
  stage reporting `not implemented yet`), `10/10` with the solutions overlaid, and
  the ten templates restored byte-for-byte (`cmp` clean, backed up in
  `.j4-dev/templates/`).
- Registered: `path.py` J4 → `course: "sandbox-capabilities-from-scratch"`,
  `kind: "ready"`, `prereq ["C2", "D1"]`, a real `why`; `ROADMAP.md` →
  **Twenty-three courses, 261 graded checks**, a ready row, the phase-J table's J4
  row marked built, and the paragraph naming J5 as the next course (the J3
  paragraph kept, J4's written beside it); `AGENT-INFRA.md` → items 8 and 10 now
  **yes** with J4 named in both, and the gaps table's J4 row marked built; a bullet
  in the root `README.md`; the course's two READMEs.
- Harness: `/home/diego/Desarrollo/.j4-dev/` (`CONTRACT.md` — 42KB, frozen before
  any stage and amended nineteen times, §7 recording what the plan said, what the
  course does and why — `course_head.py`, `course_tail.py`, ten `check_NN.py`, ten
  `mutate_NN.py`, `run_all.py`, `mutate_all.py`, `audit_course.py`, `assemble.py`,
  `smoke.py`, `probe_manifest.py`, `verify_provided.py`, `templates/`). **Never in
  `/tmp`.**

Shapes worth keeping: **a refusal raises and a denial is returned** — anything the
caller got wrong is an error and anything the *policy* decided is data with a word
from a closed vocabulary (`granted`, `unknown`, `capability`, `jail`, `host`,
`limit`, `secret`); **the world is the tie-breaker**, so `VFS.log()`,
`Wire.dialled()` and `Vault.reads()` are the records the report must equal and a
denied call has to be absent from all three; **the line is written before the
act**, and its `bytes` is a *prediction* made at decision time (`stat` is a
question, not a touch) that must equal what the world then records — with `0` for
a listing, a process and a secret, because a directory's shape is not bytes, what
a scripted command will touch is not knowable before it runs, and a secret travels
as a fingerprint; **the six questions are one order**, and the order is the design
(catalogue, grant, jail, host, limit, secret — first no wins); **a process tool's
target is the directory it was allowed to work in**, so everything it touched has
to be inside it, which is how the audit stays true for a shell; **the reports
cross-check by claim** — every handle the vault read is claimed by a line that
demanded it, a dump claiming them all at once; and **the capstone's clock is
logical time** (`fleet.Clock`, advanced by each tool's `cost.ticks`), so two runs
of one plan agree on the tick of every line.

Three contract defects the *stages* found, all of them mine: `/home/agent/../etc/passwd`
resolves to `/home/etc/passwd` (one `..` pops one component; the plan said
`/etc/passwd`); the `secret` reason could never fire, because no tool's target
*was* a handle until a tenth fixture (`get_secret`) gave it one; and §4.9's
`secrets == len(vault.reads())` is false the moment a single call legitimately
reads three handles (`env_dump`), the fix being the claim rule above. There is a
pattern in all three: **a vocabulary word or a rule that no run can reach is a
design bug, not a corner case** — the same argument that kept the capstone from
parsing calls with `parse_call` before deciding them (`unknown` would have become
unreachable too).

## In flight — nothing

The next unit is **J5 (`agent-metrics-from-scratch`)** — queue depth, latency
percentiles, tokens, cost per task, failure and retry rates, and the aggregation
windows that make those numbers stable — then G4 (an OS course; salvage
`origin/claude/linux-from-scratch-curriculum-2qokjd`) and G5/G6. A third
source list also arrived this session — three C/C++ networking series — and
it is now `NETWORKING.md` plus **phase L** (`tcp-ip-from-scratch`,
`concurrent-servers-from-scratch`, `mqtt-broker-from-scratch`, all three
`author`), so the queue after J5 is J5 → G4 → L1 → L2 → L3 → G5/G6, minus
whatever the ROADMAP's own order says.

Two questions from earlier sessions are **answered**: the legacy, thin
`distributed-training/` directory stays exactly as it is (the user's call,
2026-10-14) — the roadmap marks it superseded and nothing touches it — and the
two lists in `AI-ENGINEER.md` are handled: 40 items mapped to existing courses,
five gaps registered as phase K.

## The workflow that produced G3, F2, J1, I9, H1, A8, J2, J3 and J4 — keep it

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
   were right every time. J4's caught four more of the same kind (a secret's
   `env_dump` hands back a tuple of observations, not handles; a secret read's
   *line* bytes is `0` while its observation carries the length; the analyst holds
   **both** of `debug_dump`'s capabilities; a `value` on a read tool is not a
   grant question, and a missing file makes `stat` raise). Write the smoke early,
   run it against the landed stages even before the capstone exists, and expect it
   to teach you the surfaces — and treat a red probe as a claim about *your*
   expectation until the stage's own check proves otherwise.
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
- **A vocabulary word or a rule no run can reach is a design bug, not a corner
  case.** J4's contract had three of them: `secret` as a reason when no tool's
  target *was* a handle (fixed by a tenth fixture), the capstone about to read
  calls with `parse_call` before deciding them (`unknown` would have become
  unreachable), and a cross-check that a dump or a shell could never satisfy.
  When a reason, a branch or a mutation cannot be reached, the world or the
  order is wrong — not the check that failed to reach it.
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
