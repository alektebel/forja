# codecraft

Your own CodeCrafters, on this repo.

CodeCrafters works because you build a real thing stage by stage and a grader
tells you when each stage is done. This directory is that, local and yours: a
course is a directory of templates plus the tests that define them, and
`codecraft` runs them, remembers how you did, and tunes what it shows you to
how you are actually learning.

It has two jobs, and they are the same job from two sides:

1. **Run any course and coach you through it.** The seven existing projects
   (`llm-from-scratch`, `dynamo-paper`, `context-caching`, `contextcite`,
   `aws-from-scratch`, `deploy-and-debug`, `compiler-and-vgpu`) work
   immediately — it wraps their existing `check.py`.
2. **Let you author new ones.** `codecraft new` scaffolds a course you can fill
   in, so the set of things you can learn grows with your curiosity.

No dependencies. `python3 codecraft/cli.py`, nothing else. There is also a
one-line shim, `cz`, that forwards to the same CLI (`cz run llm-from-scratch`);
see [The `cz` shim](#the-cz-shim) for putting it on your PATH.

---

## Quickstart

```bash
python3 codecraft/cli.py                      # your learning board
python3 codecraft/cli.py path                 # the ordered plan, with live progress
python3 codecraft/cli.py dag [<course>]       # the DAG: what must come first
python3 codecraft/cli.py tracks [<course>]    # the same graph as tracks: what each row ends
python3 codecraft/cli.py brief [<course>]     # how to author a row: rules, reading, bar
python3 codecraft/cli.py run llm-from-scratch # run it; read the nudge
python3 codecraft/cli.py run llm-from-scratch --stage 3   # one stage, not all of them
python3 codecraft/cli.py stage llm-from-scratch 5  # one stage, before you write it
python3 codecraft/cli.py next                 # just the next action
python3 codecraft/cli.py hint llm-from-scratch# when the nudge is not enough
python3 codecraft/cli.py explain              # ask the NAN mentor what you're getting wrong
python3 codecraft/cli.py ask "why the mask before softmax?"   # or any question
python3 codecraft/cli.py status llm-from-scratch
python3 codecraft/cli.py review               # concepts still unretired
```

A `run` shows the course's own checker output, then three or four coach lines:

```
  codecraft · LLM From Scratch · stage 5  attention.py  — attention weights and the causal mask
  cause   row 1 must differ from the full-attention row — the future leaked
  now     Apply the causal mask as -inf BEFORE the softmax, so each row still
          sums to 1 and position 0 attends only to itself.
  pace    One function at a time; re-run after each.
  predict the output row for position 0 equals V[0].
  stuck? run: python3 codecraft/cli.py hint llm-from-scratch
```

The `cause` is condensed from the checker; `now` is the single micro-action;
`predict` is the number to commit to *before* you run, which is where the
learning actually consolidates.

A `stage` is the page *before* the run — the file you edit, what goes in it, how
big the tester is, and where you are on the ladder:

```
  codecraft · OS From Scratch · stage 5 of 10

  stage_05.py  — The syscall boundary, and the pointer you did not check
  status  TODO  nothing has run this stage yet
  size    93 asserts · 69 planted mutations the check must catch
  tags    syscalls, user pointers

  what    Write `SyscallError`, `SYSCALLS`, `ERRNOS`, `number`, `user_range`,
          `copy_in`, `copy_out`, `dispatch` and `audit_line` in stage_05.py.
  predict What a kernel has to know about a pointer before it may read through
          it, and why the line about a call is written before it.

  run     python3 codecraft/cli.py run os-from-scratch
  ladder  ··········  0 of 10 passed
```

`asserts` counts the `assert` and `raise` sites in the stage's check — that number
can be recomputed from `course.py` at any time. `mutants` counts the planted
mistakes that check was *proven* to catch, and it is recorded in
`codecraft/stats.py` on purpose: the harness that plants them is built and deleted
while a course is authored, outside this repository, so for nine of the twenty-four
courses the number is gone and the page says so rather than printing a zero.
`stage <row>` also answers for a course that is registered but not written yet: it
prints the row, its prerequisites and its thesis, which is what `cz stage G7`
shows today.

A `dag` is the same registry read the other way: what must come first, and what
merely should.

```
  codecraft · the dependency DAG · 62 projects · 91 hard edges · 9 waves

  wave 0 · nothing must come first
  ○ A1  AWS From Scratch                    ready   unlocks A6 A7
  ○ A2  LLM From Scratch                    ready   unlocks A3 A4 A8 B1 H1 I2

  wave 3 · after 3 waves
  ○ J3  Durable Execution From Scratch      ready   unlocks H6 L2

  good first · nothing forces these, a thesis asks for them
  · A1  after A5
        A5's thesis: 'Makes sqs/dynamodb in A1 click' — and A5 is 'optional but cheap'
```

Two layers, and the difference is the point. **`prereq` is the honest
dependency**: it is what the row's own thesis says the course is built on, it is
the only thing that becomes an edge, and every row lands in the wave its longest
path reaches — wave 0 has nothing in front of it, and anything sharing a wave can
be worked in parallel. **`advice` is advice**: nine places where a row's thesis
says something would be *good* to have done first even though nothing forces it,
each stored with the sentence that asks for it, so the advisory layer can be
audited in `codecraft/path.py` instead of trusted from `codecraft/dag.py`.

`dag <course>` zooms on one row: its wave, its direct prereqs, everything that
must come first in wave order, everything it opens, and the advice. A row is named
by slug, id (`cz dag J3`) or title. The graph is also a self-test: `cz self-test`
fails if a prereq names no row, if two rows share an id, or if the registry ever
stops being acyclic.

`tracks` is the same graph read a third way: not what comes first, but what each
row *ends*. A track is not written down anywhere — it is the ancestor set of a
terminal row (one nothing depends on), in wave order — so a prereq added to a row
moves it into every track that row feeds, and the split cannot drift from the
registry.

```
  codecraft · the tracks · 62 projects · 91 hard edges · 26 tracks · 9 waves

  roots   A1, A2, A5, G1, G6, H4, H7, M1 — nothing must come first for these
  furthest I13 Serving Cluster From Scratch · 17 rows behind it
  leverage A2 in 20 tracks · A4 in 15 tracks · C1 in 15 tracks · G1 in 15 tracks · B1
          in 13 tracks

  → L2  Concurrent Servers                  9 rows · wave 0→6
      A1 A2 A4 A7 B1 C1 C2 J1 J3
```

Tracks overlap on purpose, which is what makes them useful: a row in two or more
of them (in yellow) is where two tracks merge, and moving it moves all of them at
once. A2 sits in twenty of the twenty-six, so six of them end without it; the
seven roots are the rows nothing must come first for. `cz tracks <row>` zooms on
one row: every track it is part of, the lane leading to it, and — when nothing
depends on it yet — the track it ends.

---

## One stage at a time

A `run` takes the whole course unless you say otherwise:

```bash
python3 codecraft/cli.py run os-from-scratch            # every stage, in order
python3 codecraft/cli.py run os-from-scratch --stage 3  # stage 3 and nothing else
python3 codecraft/cli.py run os-from-scratch 3          # the same request, the older spelling
```

The stage is chosen where the manifest is actually filtered, not in the argument
parser: an authored course narrows its own `STAGES`, and a `check.py` course is
handed the number as the argument it already honours. One stage is one row of
your record — the checker prints that stage's line, the coach still talks about
the course's next step, and every other stage keeps the status it had, so a
scoped run never rewrites the ladder. A number the course does not have is
refused by name before anything runs (`os-from-scratch has stages 1..10 — no
stage 99`), and `--stage x` answers that a stage is a number.

## The authoring brief

`path` says what to build and in what order, `dag` says what must come first, and
`brief` says how a course here is written and what a finished one clears.

```bash
python3 codecraft/cli.py brief                        # every row still to author, one line each
python3 codecraft/cli.py brief tcp-ip-from-scratch    # one row's brief, in full
```

A row is named by slug, id (`cz brief L1`) or title, the same as everywhere else,
and the brief comes in three parts. **guidelines** state the house rules once:
stdlib only, no float anywhere, the clock injected, no module-level mutable
state, the banned imports, what a template and its solution owe each other, the
check that must let `NotImplementedError` escape, the ≥34 mutations a stage's
check is proven against, and the audit that enforces all of it. **resources** are
where to read first: the row's own words in `path.py`, the ROADMAP section the
row is a slot in, the workflow `NEXT-SESSION.md` records, the document the row
itself names, and the courses to imitate. **requirements** are the acceptance
checklist — the manifest and its ten stages, the stubs and their solutions, the
per-stage counts in `stats.py`, `./cz self-test` green, the run green from an
unrelated cwd, the row flipped to `ready` — together with the row's own frozen
contract when it has one (`cz brief L1` points at `.l1-dev/CONTRACT.md`, the
model for how specific a brief has to be), or the plain statement that it has
none, in which case the row's own words are the spec.

---

## The `cz` shim

`cz` is a one-line forwarder to `codecraft/cli.py`, for when the full path is
noise:

```bash
cz run aws-from-scratch     # same as python3 codecraft/cli.py run aws-from-scratch
cz run os-from-scratch --stage 3   # one stage, not all of them
cz path
cz dag                       # the dependency DAG: waves, unlocks and advice
cz dag J3                    # one row: what must come first, what it opens
cz tracks                    # the same graph as tracks: what each row ends
cz tracks L2                 # one row: the track it ends, and where it merges
cz brief                     # every row still to author, one line each
cz brief L1                  # one row's brief: the rules, the reading, the bar
cz stage aws-from-scratch 3 # one stage: what to write, what the tester costs
cz hint aws-from-scratch
```

It lives at the repository root (`./cz`) and is symlinked into `~/.local/bin`,
which your shell already adds to `PATH` via `~/.local/bin/env`. If `cz` is not
found, either use `./cz` from the repository, or add the symlink yourself:

```bash
ln -sf "$PWD/cz" ~/.local/bin/cz
```

Every subcommand of the CLI is available through it; it does nothing else.

---

## The look: milestones and the mentor

Two layers of output, never one. The course's own `check.py` is left untouched —
it is the raw, diagnostic truth. On top of it codecraft adds ceremony and
diagnosis.

**A stage landing gets a banner**, because that is the moment the learning
consolidates:

```
╭────────────────────────────────────╮
│ ✓  Stage 1 passed  —  stage_01.py  │
│    add and contains                │
│    first try — no hints            │
│    █████████████░░░░░░░░░░░░░  1/2 │
╰────────────────────────────────────╯
  ✧ ✦ ✶ ✹ ✷
```

Finishing a course gets a bigger one. A regression (a stage that passed and no
longer does) is called out in yellow rather than hidden.

**A failure gets the mentor — immediately.** The rule-based coach can see the
*shape* of your failure but not your code. The mentor can. The moment a stage
fails (or any time you type `explain`) codecraft sends the failing stage's
source, the exact error, and your history to a model on the NAN subscription and
asks for the misconception behind it — before the advice, right after the error:

```
  ✦ mentor  (deepseek-v4-flash)

  misconception  You're treating contains() as a lookup that recalls what you
                 inserted, instead of a test that only ever reads bits.
  the model      contains() is an AND over the positions the item hashes to:
                 all set → maybe present; any unset → definitely absent.
  try this       Before any add, print the bit array and ask which positions
                 _pos returns — can any read 1?
```

It is explicitly **not** a solution generator: the prompt forbids printing the
fix, and if you have failed five times it may describe the algorithm in words
but still not write it. Answers are cached by stage content + error, so a repeat
run is free.

`ask "..."` uses the same context for a free-form question about the current
stage. Both need `NAN_API_KEY` in your environment; codecraft falls back to the
rule-based coach silently when it is absent.

```bash
python3 codecraft/cli.py config --mentor auto     # explain every failure (default)
python3 codecraft/cli.py config --mentor stuck    # only when the history says you're circling
python3 codecraft/cli.py config --mentor manual   # only when you type explain/ask
python3 codecraft/cli.py config --mentor off      # never
python3 codecraft/cli.py config --model glm5.3    # any NAN model id
```

**Privacy:** `explain`/`ask` send the stage source file and the error to
`api.nan.builders` under your own key. Nothing else leaves your machine.
`--mentor off` (or `--no-mentor` on a single run) disables it entirely.

---

## How it adapts

Every run is appended to `history.jsonl`. From that record `codecraft` derives
a model in `profile.json` and classifies the moment you are in:

| Moment | What it saw | What it does |
|---|---|---|
| **focused** | first or second attempt, or a fresh `TODO` | minimal nudge: cause, action, prediction |
| **accelerate** | two stages passed on the first try | tells you to move on with hints closed; if it keeps happening, it says the material is below your level and to author something harder |
| **stuck** | three runs, same failure signature | stops you re-running unchanged, gives the smallest experiment, raises the hint level |
| **flailing** | three runs, three *different* failures | tells you to change too much at once and shrink to the smallest case |
| **done** | every stage passes | recommends the next course and queues concepts for review |

Two things make this more than a run counter:

- **Failure signatures.** Each failure text is normalised (numbers, paths and
  quoted values dropped) so the *same* misconception on repeat runs collapses to
  one key, while a genuinely new failure does not. Same failure three times is
  "stuck"; three different failures is "flailing" — very different advice.
- **Concept tags.** Every stage is tagged with the concepts it exercises
  (`boundary`, `numerical-stability`, `masking`, `aliasing`, `quorum-consistency`,
  …). When a tagged stage fails, the tag's mastery box drops. The same tag
  failing in three courses is surfaced as a **habit**, not bad luck:

  ```
  pattern boundary/off-by-one: 4 misses across 3 courses. That is a habit, not a one-off.
  ```

### The hint ladder

Hints escalate only as far as you ask. `hint` raises you one rung and remembers
it for that stage:

```
hint 0  the micro-action for the stage
hint 1  the smallest experiment to run, plus what to predict
hint 2  where the reference solution lives (read it after attempting)
```

Author-specified hints, when a course has them, come first.

### Pacing and style

`python3 codecraft/cli.py config --style deep|balanced|fast`

- **deep** — never auto-reveal; always make you predict; surface review.
- **balanced** — the default above.
- **fast** — accelerate sooner and keep the coach terse.

---

## Authoring a course

```bash
python3 codecraft/cli.py new bloom-filter --title "Build a Bloom Filter" --stages 3
```

That writes a runnable course. Edit `course.py` — a course *is* its tests:

```python
from codecraft.api import stage

TITLE = "Build a Bloom Filter"
DESCRIPTION = "A probabilistic set, from hashing to false-positive math."

def check_1():
    from stage_01 import BloomFilter
    bf = BloomFilter(bits=64, hashes=2)
    bf.add("x")
    assert "x" in bf
    assert "y" not in bf, "a fresh filter must not report false members"

STAGES = [
    stage(1, file="stage_01.py", title="add and contains",
          tags=["hashing", "data-structure"],
          action="Implement add(): set the k bit positions for the item.",
          predict="Can contains() ever be certain an item is absent?",
          check=check_1),
]
```

Then `python3 codecraft/cli.py run bloom-filter`. Stage files under
`stage_NN.py` raise `NotImplementedError` until you fill them; finished
versions go in `solutions/`.

Write the checks that catch **the mistakes that are easy to make and hard to
notice** — a wrong bit index, a false negative on a fresh filter — not line
coverage. A check whose message names the likely cause is a tutor; the whole
repo is built on that idea, and your courses inherit it.

---

## Files

```
codecraft/
├── cli.py         # the command surface
├── contract.py    # run a check.py (subprocess) or course.py (import) → one result shape
├── manifests.py   # discover courses; merge built-in curriculum or authored course.py
├── curriculum.py  # built-in metadata for the seven existing projects
├── api.py         # the `stage(...)` helper an authored course imports
├── adapt.py       # the adaptive decision: kind, hint level, pacing, review
├── patterns.py    # failure text → category + stable signature
├── store.py       # history.jsonl + profile.json
├── render.py      # the coach block
├── style.py       # banners, progress bars, the mentor box
├── mentor.py      # NAN client + prompt + cache
├── scaffold.py    # `codecraft new`
├── path.py        # the ordered plan (see ROADMAP.md)
├── briefs.py      # a row's authoring brief: the rules, the reading, the bar
└── history.jsonl / profile.json / mentor_cache.json   # your record (git-ignored)
```

## Design decisions

- **Wrap, do not patch.** The seven checkers already teach well; editing them to
  emit JSON would risk that and touch seven projects. `contract.py` parses their
  existing output, and authored courses import through `api.py`. One result
  shape either way.
- **A course is its tests.** Authoring a course *is* writing the grader, so the
  scaffold puts metadata and checks in one file, `course.py`, next to the
  templates. There is no separate lesson format to learn.
- **Legible rules over an opaque model.** `adapt.py` is a handful of named
  thresholds you can read and disagree with. An "AI tutor" whose reasoning you
  cannot inspect is hard to trust with your learning.
- **Standard library only.** Same rule as the rest of the repo: if it cannot run
  with `python3`, the lesson gets buried under an install.

## Where this stops

- **It does not grade correctness beyond the checks you (or the project) wrote.**
  A weak check makes a weak course. The quality of the course is the quality of
  its assertions.
- **Review is concept-level, not a full spaced-repetition scheduler.** It
  resurfaces concepts you failed; it does not schedule cards by half-life.
- **No timing analytics yet.** Attempt timestamps are stored, so pace-over-time
  is possible, but nothing reads them yet.
- **It will not write the course for you.** Generating exercises is a different
  tool; this one makes the ones you write adapt to you.
- **The mentor can be wrong.** It sees the failing file and the error, not the
  whole repo or your intent. Treat its diagnosis as a strong hypothesis to test,
  not a verdict — which is why it is asked for an experiment rather than a fix.
  It also needs network access to `api.nan.builders`; the rule-based coach works
  offline.
