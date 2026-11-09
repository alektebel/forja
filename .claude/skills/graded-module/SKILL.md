---
name: graded-module
description: Build or modify a graded learning module in this repository (templates + check.py or course.py + solutions/ + _build/ + lessons.json). Use when creating a new from-scratch module, adding steps or checks to an existing one, regenerating templates or guides, publishing stage metadata to the deployed site, or mutation-testing a checker.
---

# Graded module

The format every from-scratch module in this repo follows, and the rules that
make a stage *graded* rather than merely described. Canonical examples to copy
from: `database-from-scratch/` (stdlib only), `ml-systems/framework/` (numpy),
`aws-from-scratch/` (63 single-behaviour stages behind `check.py` +
`lessons.json`) and `advanced-dsa-from-scratch/` (an authored `course.py`
course with counters and an audit). Read `PHILOSOPHY.md` at the repo root first:
design decisions named, MVP then limit cases, verification you can run.

A course is not a syllabus with exercises attached. **A course is its tests**
(`codecraft/README.md`), and a stage is one observable behaviour added to working
code. Everything below follows from those two sentences.

## Two shapes, one result

`codecraft/manifests.py` discovers a course directory and picks the mode:

| Mode | Trigger | Grader | Stage metadata |
|---|---|---|---|
| `check` | `check.py` exists | `check.py` run as a subprocess; its `✓ · ✗` block is parsed by `codecraft/contract.py` | `lessons.json` (one row per stage), else `curriculum.py` |
| `course` | `course.py` exists | imported in-process; `course.py` defines `STAGES` from `codecraft.api.stage(...)` and a `check_N` per stage | `stage(...)` fields in `course.py` |

Both return the same result dict, so the coach, the site and `stats.py` never
care which mode a course uses. Do not build a third mode.

### Layout — `check` mode (single-behaviour ladder)

```
<module>/
  README.md            what the course is, how to run, design decisions, limits
  START.md             stage-0 onboarding page (generated)
  stages/NN-*.md       one guide per stage (generated from lessons.json; never hand-edit)
  COMPLIANCE.md        house-law and AWS-fidelity record where the course has one
  REDESIGN.md          the teaching contract and the ladder, when a course was reorganised
  AUDIT.md             dated audit history; keep old numbering as history, not as syllabus
  check.py             runs one stage or a range; imports your module, never solutions/
  stage_checks.py      the checks themselves (`s01()` … `sNN()`), one function per stage
  lessons.json         stage metadata: context, task, predict, target, hints, learning, requirements
  <file>.py …          templates (generated, never hand-edited)
  solutions/           complete implementations + README.md with expected demo output
  _build/
    hints.py           HINTS = {"file.py": {"func_or_Class.method": "graded hint"}}
    mutations.py       MUTATIONS = [(description, file, old_text, new_text, step)]
```

### Layout — `course` mode (authored course)

```
<module>/
  README.md
  course.py            TITLE/DESCRIPTION/LEVEL/ORDER + `check_N` + STAGES
  <fixture>.py         the provided world and its naive laws; never edited by the learner
  stage_NN.py …        templates (generated)
  solutions/           complete stage modules, each with a `__main__` demo
  _build/
    hints.py
    mutations.py
    grade.py           dev-only: run check_N against mutated copies in the CWD
    run_mutations.py   drives grade.py over MUTATIONS, prints CAUGHT/MISSED
```

## What a graded course is supposed to look like

### The stage, as a unit

1. **One mechanism per stage.** Not one topic, one mechanism. If a stage needs
   two words joined by "and", it is two stages (the Fibonacci heap ships as
   merge / consolidate / cut, three stages). Bundling lets a stage pass while
   the mechanism it names is still wrong.
2. **One observable behaviour added, on top of everything earlier.** Setup may
   rely on earlier stages; the new assertions and the failure text may concern
   only the new behaviour. That is why a stage check reads as one sentence.
3. **One screen of prose**, in this order: context (the situation where the
   behaviour matters), task (the function/method and one input/output example),
   prediction (the exact question to answer before running), acceptance (one
   positive case and its closest edge case), debrief (what real AWS/HTTP/the paper
   does, *after* the check). Requirements and non-goals are explicit lists, not
   prose the learner has to infer.
4. **A prediction that is checkable.** "What bytes come back after putting
   `b/hello` under key `a/b.txt`?" Not "what do you think will happen".
5. **Hints are a ladder, not a walkthrough.** Each hint names the next fact to
   notice (where the map lives, which record is appended, which helper finds the
   bucket); none is a code snippet, and the last one still leaves the edit to the
   learner. The site shows them one at a time.
6. **A `learning` block for the tutor**: `check_case` (exactly what the checker
   does), `failure_focus` (where to look when red), one concept question and one
   transfer question, each with options, a correct index and per-option feedback.
7. **No scope creep.** Do not ask for an entire API, a refactor, production
   infrastructure, an AWS account, telemetry "while you're at it", or a symptom
   fix. Put real-world caveats after the check, where they refine understanding
   without enlarging the coding task.

### The check, as a contract

- **It names the cause.** `assert ..., "A bucket already exists: the guard must
  run before the insert"`, not `assert False` or "unexpected". The message is the
  tutor; the whole repo is built on that.
- **It exercises the limit case deterministically.** Construct overlapping
  fixtures, ties, boundary thresholds, alias/adjacency cases by hand. Random data
  does not hit them (see the mistakes list).
- **It refuses invalid input**, not only accepts valid input: a `_refuses(Exc,
  what, call)` helper that pins *which* rule said no, and messages that name the
  rule ("kernels are odd-sided", "thresholds are ints >= 0").
- **It does not test wiring, copies, mocks, forwarders, source text, or
  tautologies.** "Non-empty", "length grew", "does not throw", "the field exists"
  are not behaviours.
- **It pins the observable invariant, not just the output.** Where two
  implementations can agree on output while one is structurally wrong (labels,
  roots, counters), assert the structure: one union-find root per component, a
  ledger equal to `pixels × taps`, a bar met but not exceeded.
- **It is deterministic and isolated**: no clock, no network, no sockets, no
  `random`; where a "random-looking" input is needed use a fixed LCG fixture in
  the provided world. House law for the numeric courses: ints the whole way, no
  float literal, no `random`, no clock in templates or solutions.
- **It must be shown catching bugs**, not only shown passing on the reference
  solution. Step 5 below is not optional.

### Work counters and bars

When the lesson is "this is the right algorithm, not merely a working one",
count the work at the one place it can go missing and assert a measured ceiling
(`WORK_BARS`). Bars are *measured ceilings* from a reference run — never theory,
never a guess — and the capstone's `audit()` refuses a bar with no measurement
behind it as loudly as a run over its ceiling. Change a fixture and re-measure;
stale bars are worse than none.

### Metadata, the site and the deployed surface

`lessons.json` (check mode) or `stage(...)` (course mode) is the single source of
truth. Everything else renders from it:

```
lessons.json ──► manifests.load ──► serve.build_state ──► /api/state
                                                   ├── codecraft/web/app.js  (stage card)
                                                   ├── codecraft/guide.py    (stages/NN-*.md)
                                                   └── scripts/forja_site.py (bake → state.json + data.json)
```

Stage fields a card may render: `file`, `target` (dotted, e.g.
`S3.put_object / S3.get_object`), `title`, `context`, `task`, `example`,
`requirements` (MUST do, one per bullet), `out_of_scope` ("Not in this stage"),
`predict`, `hints`, `learning`, `optional`. **Anything a learner must read must
live in a metadata field that `manifests.py` passes through** — prose that exists
only in a README or only in a local guide does not reach the deployed site.

Checks that follow from this:

- a new field is added in **three** places: the metadata file, `manifests.py`'s
  stage dict, and the renderers (`app.js` for the site, `_render_micro_stage` in
  `guide.py` for the generated guides);
- generated guides are regenerated, never hand-edited
  (`python3 codecraft/cli.py guides --write --force`); a diff should show only
  the stages whose metadata changed;
- the bake is exercised locally before trusting CI:
  `python3 scripts/forja_site.py /tmp/forja-site` and grep the baked
  `state.json`/`data.json` for the new field;
- the workflow that deploys (`forja.yml`) only bakes on push to `main`; a branch
  build proves the payload, not the deployment.
- **Use the repo-local CLI for verification**: `python3 codecraft/cli.py …` and
  `python3 <course>/check.py <step>`. An installed `cz`/`forja` can be a stale
  dump of an older curriculum (measured here: installed binaries reported "9 of
  36" for a course whose repo-local CLI reports "9 of 63"). Never publish stage
  numbers, titles or metadata from an installed binary.

## Procedure

1. **Decide the course-wide contract before stage 1.** What is provided, what is
   graded, what the counters are, which house laws apply (stdlib only, ints
   only, no clock/random, one LCG fixture). Write it down in the course README
   (and `REDESIGN.md` when the ladder is being reworked). Freeze the stage list:
   one mechanism per stage, in dependency order; a later stage may use earlier
   behaviour as setup.
2. **Solutions first.** Write `solutions/*.py` completely. Each file opens with a
   docstring: what it implements (cite the source: paper section, book chapter,
   RFC), and every `DESIGN DECISION — <question>` with the alternatives and the
   cost of the choice made. Give each file a `__main__` demo that prints a
   measurement. Run every demo; a demo that disagrees with the provided world is
   a bug in the solution, not in the world.
3. **The checks.** In `check` mode, add `sNN()` to `stage_checks.py` and a
   `lessons.json` row in the same commit: context, task, predict, target, hints,
   `learning`, `requirements`, `out_of_scope`. In `course` mode, write `check_N`
   functions plus `STAGES`; `_repo()` honours an env override (`<SLUG>_REPO`) and
   `_env()` puts the course dir first on `sys.path`. Assertions name the cause;
   refusals pin the rule.
4. **Run the checks against the solutions** in a temporary copy (copy
   `solutions/*.py` over the templates, or set the env var the harness expects).
   Every stage must pass, and the copy must be outside the course directory so
   the pristine templates stay pristine.
5. **Templates.** Write `_build/hints.py`, then
   `python3 .claude/skills/graded-module/scripts/make_templates.py <module> <module>/_build/hints.py`.
   List every mechanism-bearing function, underscored helpers included; do not
   list trivial ledger plumbing. Verify: the shipped templates report every stage
   as TODO and none as FAIL/ERROR, and with only the first solution file copied
   in, the first steps pass and the checker points at the next one.
6. **Mutation test.** Write `_build/mutations.py`: at least one planted bug per
   file, each a classic mistake for that mechanism, each a minimal text edit.
   Run `python3 .claude/skills/graded-module/scripts/mutate.py <module> <module>/_build/mutations.py`
   (check mode) or `python3 <module>/_build/run_mutations.py` (course mode, which
   drives `_build/grade.py`). Every mutation must print CAUGHT. If one is MISSED,
   strengthen the check; never weaken or drop the mutation. If a mutation is
   *equivalent* — the code changed but the fixture cannot tell — find the fixture
   where the difference is observable (a merge point, a tie, a measured counter),
   or delete the mutation as not a bug worth claiming.
7. **Docs.** `<module>/README.md` (stages table with the measured bar, the
   mutation count, how to run, design decisions, limits), `solutions/README.md`
   with the expected demo output, regenerated guides, and one line in the root
   `README.md` under the right section (plus `codecraft/path.py`, `stats.py` and
   `ROADMAP.md` when the course is a registered row).
8. **Record the tester size.** Add the `(tests, mutants)` row to
   `codecraft/stats.py`: `tests` is recomputable from the grader (count `assert`,
   `raise` and `_refuses` calls inside each `check_N`); `mutants` is the number
   the battery proved caught. A changed check invalidates its row.
9. **Delete every `__pycache__`**, commit the explicit paths (never a whole-tree
   commit while someone else's merge is in progress), push, and let the site
   bake.

### Commands that verify without polluting progress

```bash
python3 <module>/check.py 9              # check mode, one stage, no history write
python3 <module>/check.py --all          # every stage: TODO/FAIL/ERROR/PASS
python3 codecraft/cli.py stage <module> 9   # metadata + hints + size
python3 codecraft/cli.py guide <module> 9   # the generated guide page
python3 codecraft/cli.py run <module> --stage 9   # runs AND records an attempt
python3 codecraft/cli.py smoke <module>  # is the course runnable at all
python3 _build/run_mutations.py          # course mode battery
python3 .claude/skills/graded-module/scripts/mutate.py <module> <module>/_build/mutations.py
```

`codecraft run` writes `codecraft/history.jsonl`; `serve.py` explicitly does not.
When a check must be run repeatedly while authoring, run it directly, not through
the command that records learner progress.

## Mistakes already made in this repo (do not repeat them)

- **Random data does not hit limit cases.** A randomised B-tree test never
  clustered large entries in one half, so a count-based split passed. Construct
  the limit case deterministically.
- **One defence masking another.** A corrupted byte broke the JSON before the
  missing CRC check mattered. Corrupt in a way that only the defence under test
  can catch.
- **Module names shadowing the stdlib.** `profile.py` shadows `profile`, which
  `cProfile` imports. Check new file names against the standard library.
- **Constants inside a graph.** Autograd ran `_backward` on constant nodes that
  never received a gradient. Every check suite needs a case mixing constants with
  tracked values.
- **A schedule hiding the phenomenon.** A dirty read let the second transaction
  see the first one's write, which hid a write skew. When demonstrating an
  anomaly, do all reads before any write.
- **A checker that only proves the solution passes proves nothing.** The mutation
  step is not optional.
- **Fixtures that hide the case they exist for.** Two rectangles that overlap
  cannot demonstrate "a threshold removes exactly one"; an "isolated" island
  eight-adjacent to a strong edge is not isolated; a diagonal pair proves 8-vs-4
  connectivity only if nothing else merges. Compute the expected difference and
  assert that the fixture *has* it before asserting what the code does.
- **Equivalent mutants hide weak checks.** Removing a union still produced the
  right labels because min-label propagation already carried the component; the
  observable invariant (one forest root per component) was the assertion that
  made the bug real. An invariant is stronger than an output when the output can
  be right for the wrong reason.
- **Stale bars after a fixture edit.** Bars are measured; changing a fixture
  invalidates every exact count. Re-measure and regenerate the bar table in the
  same change, and let the capstone audit fail until you do.
- **Metadata that never leaves the repo.** A stage's detail written only into a
  README, or only into a hand-edited `stages/NN-*.md`, does not exist on the
  deployed site. The chain is metadata → `manifests.py` → renderer → bake;
  verify all four links.
- **Two numbering systems at once.** `AUDIT.md` records a 36-stage checker that
  was replaced by a 63-stage ladder; old stage numbers are history, not
  syllabus. After a reorganisation, regenerate guides, invalidate recorded
  progress (or map it explicitly), and delete text that still describes the old
  ladder.
- **Recipes and docs drift.** The c-compiler solutions README compiled every unit
  except the one whose flags it forgot (`-I$R`); the delivered code was fine, the
  documented build was not. Run the documented recipe verbatim before claiming
  it.
