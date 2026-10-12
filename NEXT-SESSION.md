# Next session — where everything is

Written at the end of the session that shipped **H1
(`distributed-training-from-scratch`)** and then **A8
(`autograd-from-scratch`)** — the user's own autograd, tensors over exact
rationals, ten stages, 504 planted mutations, the whole course running as one
process. Everything in *Done* is committed and pushed; the section after it is
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

## Done, in the commit that follows this file

**H1 `distributed-training-from-scratch`** — ten stages, 554 mutations, the
thesis *one model, many devices, the same math*: a plan is frozen data with three
independent checks (its bytes, its memory ledger, its semantics recomputed
against the reference). Provided: `fabric.py` (I9's, verbatim), `plans.py`,
`model.py`. `run_all.py 1 … 10` → `FAILED: 0`; `mutate_all.py 1 … 10` →
`TOTAL 554/554`, `MISSED OR BROKEN: 0` (49, 57, 60, 54, 54, 46, 46, 59, 45, 84);
`audit_course.py 1 … 10` → `AUDITED: 10, PROBLEMS: 0`; `assemble.py` →
`assembled 10 checks, 4575 lines, compiles`; `probe_manifest.py` →
`MANIFEST: 10/10 clean`; `smoke.py` → `SMOKE PASS — 30 probes, ten stages, one
deterministic step`; `./cz run` → 0 crosses on the templates, `Course complete`
with the solutions overlaid, templates restored byte-for-byte.

**A8 `autograd-from-scratch`** — the user asked for their own autograd,
mid-session, and chose **tensors over exact rationals**: a reverse-mode engine
where the *forward* algebra is provided and every gradient is yours. Registered:
`path.py` **A8** → `kind: "ready"`, `prereq ["A2"]`.

Provided world, verified by its own verifier (`.h2-dev/verify_exact.py` →
`exact: ALL PASS (277 checks)`, zero float literals, `math.gcd` the only import
that matters): `exact.py` (960 lines — `Rational`, `Tensor`, the whole forward
algebra, and `reduce_gradient` as the provided half of broadcasting) and
`fixtures.py` (394 lines — the `AND`/`OR`/`XOR`/`PARITY` datasets, the
`linear`/`mlp`/`deep` models with their parameter names, `LEARNING_RATE = 1/4`,
`STEPS = 200`, `EXPECTED_STEPS = 8`, the frozen `EXPECTED_LOSS` and
`REFERENCE_GRADIENTS`).

- `python3 /home/diego/Desarrollo/.h2-dev/check_NN.py` → PASS for all ten;
  `run_all.py 1 … 10` → **`FAILED: 0`**.
- `mutate_all.py 1 … 10` → **`TOTAL 504/504`, `MISSED OR BROKEN: 0`**. Per stage:
  46, 58, 64, 63, 45, 41, 36, 52, 41, 58.
- `audit_course.py 1 … 10` → `AUDITED: 10, PROBLEMS: 0`.
- `assemble.py` → `assembled 10 checks, 5412 lines, compiles`;
  `probe_manifest.py` runs the assembled manifest's `check_1()`…`check_10()` in
  fresh subprocesses over a solutions-overlaid tree (repo root on `PYTHONPATH`
  for `codecraft.api`, `H2_REPO` set) → `MANIFEST: 10/10 clean`.
- `smoke.py` (in `.h2-dev/`) → **`SMOKE PASS — 23 probes, ten stages composed,
  one exact graph`**: the engine end to end on a hand-computed gradient, a second
  backward doubling, the quotient's pair, the broadcast bias reduced back, the
  mean's exact `1/6`, `shared`'s identity, the freeze dropping the stale gradient,
  `detach` and `no_grad`, the tie going left, the exact central difference at two
  `h` and the cubic off by exactly `h²`, and then the capstone: `sgd` as
  `theta - lr·grad`, the fixture's mlp run starting at exactly `1` and falling
  onto the frozen `EXPECTED_LOSS` step for step, and `reproduce_reference()`'s
  gradients equal to the fixture's.
- `./cz run autograd-from-scratch` → `0/10` on the templates (every stage
  reporting `not implemented yet`), `10/10 passing` and `COURSE COMPLETE` with
  the solutions overlaid, and the ten templates restored byte-for-byte (`cmp`
  clean).
- Registered: `path.py` A8 → `kind: "ready"`, a real `why`; `ROADMAP.md` →
  **Twenty courses, 231 graded checks**, the ready row, and the paragraph marking
  A8 built with J2 as the next course; a bullet in the root `README.md`;
  `autograd-from-scratch/README.md` and `solutions/README.md`.
- Harness: `/home/diego/Desarrollo/.h2-dev/` (`CONTRACT.md`, ten `check_NN.py`,
  ten `mutate_NN.py`, `run_all.py`, `mutate_all.py`, `audit_course.py`,
  `assemble.py`, `course_head.py`, `course_tail.py`, `smoke.py`,
  `probe_manifest.py`, `verify_exact.py`, and `templates/` — the ten templates
  backed up before the overlay). **Never in `/tmp`** — it was wiped three times
  in the H1 session and killed four delegates.

Numbers worth keeping: an exact rational's denominator grows about 3 bits per
step, so the `2→4→1` model carries ~11661-bit denominators by step 8 and each
step multiplies that by `4·D³` — which is why `EXPECTED_STEPS = 8` freezes the
whole trajectory and `STEPS = 200` is the *linear* fixture (under 1200 bits,
learns AND/OR, cannot learn XOR); a tie sends the whole gradient to the **left**
operand, so `relu'(0) = 0` and `abs'(0) = 0`; the bias in `mlp` is rank-1 and
broadcast over the rows, so its gradient is reduced back to `(out,)`; the loss at
the fixture's mlp weights is exactly `1`; `mlp(params, x)` returns the **pre-loss**
output and the composite is `mean(mul(sub(out, y), sub(out, y)))`.

## In flight — nothing

Both threads are closed. The next unit is **J2
(`orchestration-from-scratch`)** — the DAG, the reviewer that can reject, and the
handoff that must carry its own context — then J3 `durable-execution-from-scratch`,
J4 `sandbox-capabilities-from-scratch`, J5 `agent-metrics-from-scratch`, then G4
(an OS course; salvage `origin/claude/linux-from-scratch-curriculum-2qokjd`) and
G5/G6.

One question left with the user, unanswered: whether to delete the legacy, thin
`distributed-training/` directory now that `distributed-training-from-scratch`
supersedes it (the roadmap marks it superseded; the directory is untouched).

## The workflow that produced G3, F2, J1, I9, H1 and A8 — keep it

1. **Recon**, then **freeze a contract** in a dev directory beside the repo
   (`/home/diego/Desarrollo/.h2-dev/CONTRACT.md`): thesis, conventions, the
   provided modules, and per stage the surface, the frozen shapes and the
   *mistake catalogue*. Freeze it before writing any stage; amend it the moment a
   stage's real signature differs from the plan — the path references inside it
   too.
2. **Never `/tmp`.** It was wiped three times and killed four delegates. The
   harness lives beside the repo and is re-synced after every change.
3. **One delegate per stage**, four files each (`stage_NN.py`,
   `solutions/stage_NN.py`, `check_NN.py`, `mutate_NN.py`). **A delegate's verdict
   is not evidence**: the parent re-runs `check_NN.py`, `mutate_NN.py`,
   `run_all.py NN`, `mutate_all.py NN`, `audit_course.py NN` — every time. Ten
   delegates, ten green.
4. **Keep delegate briefs short** and point at the contract. Long briefs died
   with length-stops producing no files.
5. **The smoke is where your own expectations get caught, not the course.** This
   session it caught **eight** of the parent's fixture mistakes and the stages
   were right every time — the nesting of `exact.from_nested` (`((v,),)` is a
   `(1,1)` shape, not `(1,)`), a freeze that drops the stale gradient, a tie's
   expectation that must use the operand's own nesting, `train` returning
   `Rational`s and not tensors, `sum_to_scalar(z²)` being `14` and not `6`, a
   `gradient_check`'s `fn` having to return a rank-0 node. Write the smoke early,
   run it against stubs for the missing stages, and expect it to teach you the
   surfaces.
6. **The `NotImplementedError` rule.** Every check must let it escape (a broad
   handler re-raises it first), or an untouched template reports as `✗` instead of
   `· not implemented yet` in `./cz run`. Verified both ways: `0/10` on the
   templates, `10/10 passing` with the solutions overlaid.
7. **A copied harness carries the old paths.** `assemble.py` still had
   `HERE = "/home/diego/Desarrollo/.h1-dev"` after the copy, so it assembled
   **H1's** manifest into `autograd-from-scratch/course.py` — the symptom was the
   A8 manifest's checks dying with `ModuleNotFoundError: No module named
   'fabric'`. Repoint every `HERE`/`*_REPO` in a copied harness, and make the
   probe run the assembled file rather than trusting it.
8. **Mutation hygiene**: rebuild the tree per mutation,
   `PYTHONDONTWRITEBYTECODE=1`, a stale anchor is `BROKEN` not `CAUGHT`, a mutant
   that hangs counts as `[hung  ]` = caught, and a no-op mutation is worthless —
   it surfaces later as `MISSED`. A defect invisible in the *values* (stage 3's
   unconditional `reduce_gradient`) needs a spy, not a comparison.
9. **Register, then commit**: `path.py`, `ROADMAP.md` (the count in the header,
   the ready row, the plan paragraph), the root `README.md` bullet, the course's
   two READMEs, and this file — after deleting `codecraft/{history.jsonl,
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
  stage_*.py .h2-dev/templates/`) and `cmp` them after restoring. `git pull
  --rebase` also refuses with unstaged changes: `--autostash` is the way to push
  around them.

## Ground rules

- **Deterministic, offline, integer-only.** No `time`, `threading`, `asyncio`,
  `random`, `os.environ`, `uuid`, no module-level mutable state, and **no float
  anywhere**: every count is an int, every ratio an exact reduced pair, so a run
  is a function of its inputs and a check can assert a number instead of timing
  something. A8 is the strongest version of this rule — an autograd whose
  gradients are exact rationals, with a cubic that must be off by exactly `h²`.
- **Docs in the repo are English**; the user writes Spanish, so answers are in
  Spanish with paths and identifiers verbatim.
- **The user's twelve-item list in `AGENT-INFRA.md` stays verbatim (Spanish)**;
  the analysis around it is English.
- `./cz` is `python3 codecraft/cli.py`. Before committing: no `history.jsonl`, no
  `profile.json`, no `mentor_cache.json`, no `__pycache__`.
- Ask before destructive commands; a course's own templates are the exercise, so
  never "fix" a stub into a solution outside `solutions/`.
