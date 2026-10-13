# Orchestration From Scratch

A big task is a graph of small ones, and the graph is data. Ten graded stages
between a task that is too big for one agent and a run you can replay — on a
provided clock, a scripted fleet, and nine raw plans that include the two that
must be refused.

```
python3 codecraft/cli.py run orchestration-from-scratch
```

Stage 1 is `stage_01.py`. Every stage is a template with `DESIGN DECISION`
docstrings and `NotImplementedError` stubs; the reference implementations are in
`solutions/`, stage for stage. The checks live in the harness that produced the
course (`/home/diego/Desarrollo/.j2-dev/`): `check_NN.py` is the stage's own
caller, `run_all.py NN` runs it against the templates, `mutate_NN.py` plants
mutations in the solution and proves the check catches every one, and
`python3 smoke.py` walks the ten stages composed in one process.

## Provided complete — you do not write these

| File | What it is |
|---|---|
| `fleet.py` | J1's clock and task/pool specs, copied verbatim: an injected `Clock`, immutable `TaskSpec`/`PoolSpec` records, and scripted workers that are honest about what they cost. Nothing here is timed and nothing is threaded. |
| `agents.py` | The model as a callable: a scripted `Agent` answering `Reply(text, tokens)`, with `planner`, `worker`, `reviewer`, `approver`, `flaky_agent`, `refuser` and `bad_shape` scripts. Attempt 1, 2, 3 … are the entries of its plan; a plan that runs out repeats its last entry. |
| `graphs.py` | The raw plans, before anything validates them: `single` (1 node), `chain` (3), `diamond` (4), `review` (2), `gate` (2), `wide` (7), `deep` (5), and the two broken ones — `cycles` (a graph that parses and has no order) and `orphan` (a dependency the graph does not have). `pick(name, **overrides)` returns a fresh mutable copy. |

## The ten stages

| # | Template | What it decides |
|---|---|---|
| 1 | `stage_01.py` | The subtask and the graph: every key a shape spells, every default materialised, a typo refused by name (with the key it was probably meant), and ids, agents and prompts that say something |
| 2 | `stage_02.py` | The order a dependency forces: the edge set, the waves, `would_cycle` for an edit, and a cycle refused by naming its path (`'index' -> 'render' -> 'index'`) |
| 3 | `stage_03.py` | The wave is not the schedule: `runnable` asks whether *every own dependency* is `ok`, and `dispatchable` caps what may start now |
| 4 | `stage_04.py` | The handoff that carries its own context: a child gets its own dependencies' accepted results, each cut to the budget that dependency declared — a token is one character, exactly |
| 5 | `stage_05.py` | The reviewer that can reject: the acceptance, the rework prompt that carries the reason, and the attempt limit `MAX_REWORK` after which a rejection is a failure |
| 6 | `stage_06.py` | One failure, and the rest of the graph: the transitive dependents of a failed node are skipped without running, and a node that already finished is never overwritten |
| 7 | `stage_07.py` | The approval, and the effect it stops: an effect is asked about *before* it runs and never dispatched while the answer is missing |
| 8 | `stage_08.py` | The budget, checked before the call: `spent + node.tokens <= budget`, exact ints, never a float and never a percentage |
| 9 | `stage_09.py` | The record, and the report from it: seven kinds of decision, six fields, no payload text at all, and a report whose every counter is recomputed from the lines and checked against the totals the caller claimed |
| 10 | `stage_10.py` | Two runs, identical bytes: the loop over the injected clock that composes the nine — dispatch, handoff, review, failure, gate, budget, record — and ends with the report, deterministic to the byte |

## What the course refuses to hide

- **A typo is not a default.** A key that is not one of `SUBTASK_KEYS` refuses
  and names the key it was probably meant; a wrong value refuses and names the
  node.
- **A wave is a fact about the plan; `runnable` is a fact about the run.** A fast
  node whose own dependencies are `ok` starts, even while a slow sibling in the
  same wave is still running.
- **A handoff carries its own context, and only that.** An ancestor's result
  never reaches a child, and each dependency's result is cut to the budget that
  dependency declared — a byte count would smuggle in an encoding, so a token is
  a character and the cut is exact.
- **A rejection is data.** It comes back with a reason, the node reworks with it,
  and `MAX_REWORK` is where a rejection becomes a failure instead of a loop.
- **A failure is not contagious to siblings.** Only the transitive dependents are
  skipped, and a node that already finished keeps what it finished with.
- **The gate comes before the effect.** An approval that arrives after the effect
  landed is the classic failure this stage exists to prevent, so the dispatch is
  *held* while the answer is missing.
- **The budget is asked, not discovered.** `spent + cost <= budget` is checked
  before the call, and the refusal lands as a state and not as a crash.
- **The record is not the transcript.** Six fields per line, the seven kinds the
  course allows, no prompt, result or reason text anywhere, and a report the run
  can be audited against — a caller-supplied total the record contradicts is
  refused by name.

## Constraints

Standard library only, offline, deterministic: no `time`, `threading`, `asyncio`,
`random`, `os.environ`, `uuid`, no module-level mutable state, and **no float
literal anywhere** — ticks and tokens are ints. The clock is the injected
`Clock`, so two runs of the same graph with the same agents produce identical
bytes. Every check is a plain `python3` script; nothing here reads a network, a
file or a clock.

## Verified

Ten checks (`check_01.py` … `check_10.py` → `PASS`), 526 planted mutations
(`mutate_all.py 01 … 10` → `TOTAL 526/526`, `MISSED OR BROKEN: 0`), ten stages
audited (`audit_course.py 01 … 10` → `AUDITED: 10, PROBLEMS: 0`), `assemble.py`
→ `assembled 10 checks, 4660 lines, compiles`, `probe_manifest.py` →
`MANIFEST: 10/10 clean`, `smoke.py` → `SMOKE PASS — 11 probes, ten stages
composed, one deterministic run`, and the course itself: `0/10` on the
templates, `10/10` with the solutions overlaid.
