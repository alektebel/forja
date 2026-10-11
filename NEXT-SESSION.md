# Next session — where everything is

Written at the end of the session that shipped **H1
(`distributed-training-from-scratch`)** — ten stages, 554 planted mutations, and
the whole course running as one process — and that started **A8
(`autograd-from-scratch`)** on the user's call. Everything in *Done* is committed
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

## Done, in the commit that follows this file

**H1 `distributed-training-from-scratch`** — the second half of the I9/H1 pair,
`codecraft/path.py` H1 → `kind: "ready"`. Ten stages, stdlib only, offline,
deterministic, **every number an int**, on **three provided modules**:
`fabric.py` (copied verbatim from I9), `plans.py` (I9's collectives lifted into
one file) and `model.py` (the shape calculus, the reference arithmetic and the
`tiny`/`1b`/`7b` fixtures).

The thesis, one sentence, and every stage's check asserts it: **one model, many
devices, the same math.** A plan is frozen data with three independent checks —
its bytes (per rank and over the network), its memory ledger, and its semantics
recomputed against the reference single-device result.

- `python3 /home/diego/Desarrollo/.h1-dev/check_NN.py` → PASS for all ten;
  `run_all.py 1 … 10` → **`FAILED: 0`**.
- `mutate_all.py 1 … 10` → **`TOTAL 554/554`, `MISSED OR BROKEN: 0`**. Per stage:
  49, 57, 60, 54, 54, 46, 46, 59, 45, 84.
- `audit_course.py 1 … 10` → `AUDITED: 10, PROBLEMS: 0`.
- `assemble.py` → `assembled 10 checks, 4575 lines, compiles`;
  `probe_manifest.py` runs the assembled manifest's `check_1()`…`check_10()`, each
  in a **fresh subprocess** over a solutions-overlaid tree with the repo root on
  `PYTHONPATH` and `H1_REPO` set → `MANIFEST: 10/10 clean`, and the same check on
  the *templates* raises `NotImplementedError: stage 1: implement plan_bytes()`
  (so the ten rc=0 runs are real passes and not silence).
- `smoke.py` (in `.h1-dev/`) → **`SMOKE PASS — 30 probes, ten stages, one
  deterministic step`**: the ledger and the tick model, DP's overlap, ZeRO's
  ladder, FSDP's two collectives per unit and its peak, the tensor-parallel
  reassembly, both pipeline bubbles and the interleaving, the hot routing, ring
  attention against the reference for every split, and the configuration whose
  report is recomputed from its own plan.
- `./cz run distributed-training-from-scratch` → **0 crosses** on the templates
  (the `NotImplementedError` escape rule), `Course complete` with the solutions
  overlaid, and the ten templates restored byte-for-byte afterwards.
- Registered: `path.py` H1 → `course: "distributed-training-from-scratch"`,
  `kind: "ready"`, a real `why`; `ROADMAP.md` → **Nineteen courses, 221 graded
  checks**, a ready row, the I9/H1 table marking H1 built, the legacy note for
  `distributed-training/` saying it is superseded; a bullet in the root
  `README.md`; `distributed-training-from-scratch/README.md` and
  `solutions/README.md`.
- Harness: `/home/diego/Desarrollo/.h1-dev/` (24 files: `CONTRACT.md`, every
  `check_NN.py` / `mutate_NN.py`, the runners, `smoke.py`, `probe_manifest.py`,
  `assemble.py`). **Never in `/tmp`** — it was wiped three times this session and
  killed four delegates.

Numbers worth keeping: 16 bytes per parameter for the full training state;
ZeRO-1's ledger `4 + 12/N` against ZeRO-2's `2 + 2/N + 12/N`; FSDP's per-rank
per-step figure `4P(N−1)/N`, the same as DDP's and stage 3's ZeRO-2 — not the
`3P` folklore; an all-to-all's step count as a property of the topology
(7 `full(8)`, 14 `ring(8)`, 16 `switch(8, width=4)`, 19 `tree(8)`); GPipe
`(4, 8)` = makespan 22, 24 idle pairs, `3/11` against 1F1B's 15, 12 and `1/5`;
interleaving `(p−1)/(m·v+p−1)` = `3/19` at `(4, 8, 2)` where `v = 1` reproduces
GPipe chunk for chunk.

## In flight — A8 `autograd-from-scratch`

The user asked for their own autograd, mid-session, and chose **tensors over exact
rationals**: a reverse-mode engine where the *forward* algebra is provided and
every gradient is yours. The frozen contract is `.h2-dev/CONTRACT.md` (ten stages,
the two provided modules `exact.py` + `fixtures.py`, the mistake catalogue, and
the rule that nothing in the course is a float). Registered already:
`path.py` **A8** → `kind: "author"`, the ROADMAP's next-course paragraph names it.

- A delegate is writing `exact.py` (the rational and the tensor, with
  `reduce_gradient` as the provided half of the hard part), `fixtures.py` (the
  datasets, the models, the learning rate, and the reference gradients the last
  stage must reproduce) and `.h2-dev/verify_exact.py`. **A delegate's verdict is
  not evidence**: re-run the verifier.
- Then the ten stages, one delegate each, four files: `stage_NN.py`,
  `solutions/stage_NN.py`, `check_NN.py`, `mutate_NN.py` — node and topological
  order, the local derivatives, broadcasting and the reduction, the matmul chain,
  accumulation, the seed of a non-scalar output, detach, the kink at a tie, the
  finite-difference oracle, and one training step.
- Then the same gates H1 passed: `run_all`, `mutate_all`, `audit_course`,
  `assemble`, a `smoke.py` that composes the ten stages in one process, READMEs,
  registration, commit.

After A8, in the order the roadmap already has: J2 `orchestration-from-scratch`,
J3 `durable-execution-from-scratch`, J4 `sandbox-capabilities-from-scratch`,
J5 `agent-metrics-from-scratch`, then G4 (an OS course) and G5/G6.

## The workflow that produced G3, F2, J1, I9 and H1 — keep it

1. **Recon**, then **freeze a contract** in a dev directory beside the repo
   (`/home/diego/Desarrollo/.h1-dev/CONTRACT.md`, now `.h2-dev/`): thesis,
   conventions, the provided modules, and per stage the surface, the frozen shapes
   and the *mistake catalogue*. Freeze it before writing any stage, and amend it
   the moment a stage's real signature differs from the plan — the path references
   inside it too.
2. **Never `/tmp`.** It was wiped three times and killed four delegates. The
   harness lives beside the repo and is re-synced after every change.
3. **One delegate per stage**, four files each. **A delegate's verdict is not
   evidence**: the parent re-runs `check_NN.py`, `mutate_NN.py`, `run_all.py NN`,
   `mutate_all.py NN`, `audit_course.py NN` — every time.
4. **Keep delegate briefs short** and point at the contract. Two stage-6
   delegations died with length-stops producing no files; the parent wrote that
   stage itself in the end. A delegate that reports a surface the smoke disagrees
   with is a *contract* discrepancy, not a delegate failure — fix the surface and
   re-check.
5. **The smoke is where your own expectations get caught, not the course.** Five
   of H1's first smoke runs failed on the *probe*, not the stage: `plan_memory`
   divides the state by the plan's group while ZeRO's ladder lives in the plan's
   own `memory`; a `(3,4)` added to a `(4,)` sums its gradient back, so the
   column-parallel reassembly is a *concatenation* and not a sum; stage 8 wants
   one expert per rank and a hot routing only shows up in the balance loss when
   `top_k < experts`; stage 9's attention blocks are *sequence* chunks with equal
   sides, not a full query against a partial KV; and stage 7's bubble is replayed
   from its own slots because stage 6's `bubble` refuses a five-field `Slot`.
   Write the smoke early, run it against stubs for the missing stages, and expect
   it to teach you the surfaces.
6. **The `NotImplementedError` rule.** Every check must let it escape (a broad
   handler re-raises it first), or an untouched template reports as `✗` instead of
   `· not implemented yet` in `./cz run`. Verified both ways: 0 crosses on the
   templates, `Course complete` with the solutions overlaid.
7. **Mutation hygiene**: rebuild the tree per mutation, `PYTHONDONTWRITEBYTECODE=1`,
   a stale anchor is `BROKEN` not `CAUGHT`, a mutant that hangs counts as
   `[hung  ]` = caught, and a no-op mutation is worthless — it surfaces later as
   `MISSED`.
8. **A summary that declares a value instead of deriving it** is the defect class
   this whole line of courses keeps finding: H1's stage 10 exists for it, and the
   smoke asserts `report["step_ticks"] == step_ticks(world, plan)` recomputed.
9. **Register, then commit**: `path.py`, `ROADMAP.md` (the count in the header,
   the ready row, the plan table), the root `README.md` bullet, the course's two
   READMEs, and this file — after deleting `codecraft/{history.jsonl,profile.json,
   mentor_cache.json}` and every `__pycache__`. Then `git pull --rebase
   --autostash origin main && git push origin main`.

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
  it — but back the ten templates up to the dev directory first, and `cmp` them
  after restoring. `git pull --rebase` also refuses with unstaged changes:
  `--autostash` is the way to push around them.

## Ground rules

- **Deterministic, offline, integer-only.** No `time`, `threading`, `asyncio`,
  `random`, `os.environ`, `uuid`, no module-level mutable state, and **no float
  anywhere**: every count is an int, every ratio an exact reduced pair, so a run
  is a function of its inputs and a check can assert a number instead of timing
  something. A8 is the strongest version of this rule — an autograd whose
  gradients are exact rationals.
- **Docs in the repo are English**; the user writes Spanish, so answers are in
  Spanish with paths and identifiers verbatim.
- **The user's twelve-item list in `AGENT-INFRA.md` stays verbatim (Spanish)**;
  the analysis around it is English.
- `./cz` is `python3 codecraft/cli.py`. Before committing: no `history.jsonl`, no
  `profile.json`, no `mentor_cache.json`, no `__pycache__`.
- Ask before destructive commands; a course's own templates are the exercise, so
  never "fix" a stub into a solution outside `solutions/`.
