# Agent Metrics From Scratch

A trace is not a metric. A trace is what one call did; a metric is a *fold over a
window of events*, and the window is the decision — which events are in it, what
its ends mean, whether two of them together cover a run exactly once, and which
counter is the denominator of the number on the dashboard. Ten graded stages
between a fleet that writes down what happened and a report whose every number is
recomputed from those lines and cross-checked against the fleet's own count of
the same run.

```
python3 codecraft/cli.py run agent-metrics-from-scratch
```

Stage 1 is `stage_01.py`. Every stage is a template with `DESIGN DECISION`
docstrings and `NotImplementedError` stubs; the reference implementations are in
`solutions/`, stage for stage. The checks live in the harness that produced the
course (`/home/diego/Desarrollo/.j5-dev/`): `check_NN.py` is the stage's own
caller, `run_all.py NN` runs it against the templates, `mutate_NN.py` plants
mutations in the solution and proves the check catches every one, `verify_provided.py`
checks the provided world before any stage stands on it, `assemble.py` builds the
manifest `course.py`, `probe_manifest.py` runs its ten checks in ten fresh
processes, and `python3 smoke.py` walks the ten stages composed in one process
against one real run of the fleet.

## Provided complete — you do not write these

| File | What it is |
|---|---|
| `fleet.py` | J1's file, byte for byte: the injected `Clock`, the immutable `TaskSpec`/`PoolSpec` fixtures (`small`, `narrow`, `wide`), `TASKS`, `OUTCOMES`, and the scripted workers (`reliable`, `sluggish`, `flaky`, `crasher`, `dying`, `always`, `scripted`). This course uses one thing from it — **the tick is counted, never timed** — so two runs of the same plan agree about the tick an event happened at. |
| `telemetry.py` | The fleet's events and the fleet's own promises. `EVENT_KEYS` (twelve fields), `KINDS` (five), `ABSENT`, `ERRORS` (a closed, space-free vocabulary — a line has no quoting, so no value may contain a space), `TRACE_KEYS` (E1's six, byte for byte), `SUMMARY_KEYS` (the fleet's own count), `NUMERIC_KEYS`, `TOKENS` (what a call to a task costs), `PRICES` (what a token costs, **per pool**), `WINDOWS`, `SLOS` (a target and a budget in the metric's own unit), `WORKERS`, `MAX_ATTEMPTS`, `RETRY_BACKOFF`; the *writer* `line` and the *reader* `read`; the accessors `event`, `trace`, `summary`, `price`, `tokens`, `window`, `slo`, `worker_plan`, each handing back a fresh copy and refusing an unknown name with a suggestion; `_near` (the one suggestion rule in the course); and `record()`, which runs the fleet deterministically and **counts what it did as it goes** — a count that is deliberately *not* in the lines it writes. That count is the tie-breaker every report in this course is decided against. |

## The ten stages

| # | Template | What it decides |
|---|---|---|
| 1 | `stage_01.py` | The event, and the fact it records: the twelve fields in their written order, the five kinds, an absent field spelled `-` and never omitted, `CARRIES`/`REQUIRED` so the *kind* decides which fields exist — a `started` event that carries an outcome is refused, a `finished` event that does not is too, and `error` is the one field a kind carries that may still be empty |
| 2 | `stage_02.py` | The window, and the fold: `[start, end)` with `tick == start` in and `tick == end` out, a fold that never sorts or drops anything, and an unmeasured field refused rather than read as zero — `count` answers `0`, `total` and `mean` refuse, because a total of nothing is not a total of zero |
| 3 | `stage_03.py` | Queue depth is a gauge, not a counter: depth derived from a state machine over the kinds in tick order (`admitted`/`retried` in, `finished`/`dropped` out), a queue-full drop of a task that never entered as no departure at all, a depth that would go negative refused with the task that left twice, and an average that is a series' one legitimate sum |
| 4 | `stage_04.py` | The percentile is an index: `ceil(n·p) − 1` by integer arithmetic, clamped, always a sample somebody recorded — `p95` of eight samples is the maximum — with the caller's tuple sorted as a copy and a float sample refused by name |
| 5 | `stage_05.py` | Latency, and where the time went: finishes matched to starts by `(task, attempt)`, a task's latency spanning admission to its *last* finish, the three components summed so that `wait + service + gap == total` exactly, and the gap being the backoff nobody counted as either |
| 6 | `stage_06.py` | Tokens, and the cost that was summed first: the price read from the pool that ran the task and refused by name when it has none, micros summed over the events and divided **once** by the tasks that finished, and a cost per task that is an exact reduced pair plus floored basis points |
| 7 | `stage_07.py` | Failures and retries are rates: a failure is an *attempt* and not a task (a task that failed once and then succeeded is one failure and one success), `rate` is the one door a ratio is built behind, and every denominator is named in its own refusal |
| 8 | `stage_08.py` | The window is the decision: aligned windows whose last one is cut at the end and whose step may not exceed the width, a fold that is the window's own six numbers, and `covers` answering `False` for a sliding set because the events in the overlap are deliberately in two folds and summing them would count them twice |
| 9 | `stage_09.py` | The report, and the fleet's own count: eighteen cells recomputed from the events in the window, a default window that is the whole run, and a report that refuses to be printed when any key disagrees with the fleet's own count — naming the key and **both** numbers — with `audit` reporting the same disagreement instead of raising |
| 10 | `stage_10.py` | The capstone: two windows, one answer: an SLO whose target and budget are in the metric's own unit, a burn that is the size of the overshoot rather than a count of bad windows, an alert that fires on the budget and names the window that spent the last of it, and a `run` that is a pure function of its arguments and whose report equals the fleet's own count |

## What the course refuses to hide

- **A fold takes the events and nothing else.** No function in this course takes
  a count, a total or a fleet object alongside the events it is supposed to be
  folding: a number that arrives from outside is a number the fold cannot be
  wrong about, and the whole point of the last three stages is that a fold can be
  wrong.
- **An unmeasured field is not a zero.** `count([])` is `0` — nothing was in the
  window, which is a fact — while `total(events, "tokens_out")` over events that
  never carried the field *refuses*, because "nobody measured this" and "the
  measurement was zero" are different statements and only one of them is true.
- **A percentile is an index, not an interpolation.** With floats banned there is
  nothing to interpolate with, so `p95` of a window of eight samples is its
  maximum and `p99` of a window of a hundred is its 95th sample by rank — always a
  number somebody actually recorded.
- **A gauge is derived, never summed.** Depth has a value at an instant and no
  value as a sum; the two counters it is derived from are admissions and
  departures, and the departure that follows a failure is the retry coming back,
  not a task leaving.
- **Sum, then divide.** A cost per task is the total spent divided once by the
  tasks that finished — never the mean of a column of per-event ratios, which is
  a number that depends on how the events were grouped rather than on what was
  spent.
- **The window's ends are the decision.** A tumbling set partitions a run and a
  sliding set does not; a step past the width leaves a hole nobody folds; and an
  event at exactly `end` belongs to the next window, which is the difference
  between a dashboard that adds up and one that counts its busiest minute twice.
- **The report is the events, or it is wrong.** Every cell is recomputed from the
  events in the window and then compared against the fleet's own count of the same
  run — a count that is not in the lines, so a fold that quietly lost an event has
  nowhere to hide.

## Constraints

Standard library only, offline, deterministic: no `time`, `threading`, `asyncio`,
`random`, `os`, `uuid`, `socket`, `subprocess`, `secrets`, `shutil`, `tempfile`,
`pathlib`, `math`, `statistics`, `decimal` or `fractions`, no module-level mutable
state, and **no float literal anywhere** — ticks, tokens, micros and basis points
are ints, every ratio is an exact reduced pair and every scalar is floored basis
points. `statistics.mean`, `math.ceil` and `fractions.Fraction` are banned for the
same reason the course exists: each of them would decide by itself the two things
this course decides by hand — which rank a percentile is, and what a ratio means.
Nothing here is timed, sampled or measured from a wall: the clock is J1's counter,
the fleet is scripted, the events are the only input, and the fleet's own count is
the only witness. `deploy-and-debug` (A7) is the same work over floats and a live
histogram; this one is checked to the digit.

## Verified

Ten checks (`check_01.py` … `check_10.py` → `PASS`), **510 planted mutations**
(`mutate_all.py 01 … 10` → `TOTAL 510/510`, `MISSED OR BROKEN: 0`, every stage at
or above the bar: 43, 40, 45, 47, 49, 47, 39, 67, 61, 72), ten stages audited
(`audit_course.py 01 … 10` → `AUDITED: 10, PROBLEMS: 0`), the provided world
checked before any stage stood on it (`verify_provided.py` → `provided: ALL PASS
(82 checks)`), `assemble.py` → `assembled 10 checks, 4062 lines, compiles`,
`probe_manifest.py` → `MANIFEST: 10/10 clean`, `smoke.py` → `smoke: 51 probes
PASS` over one real run of the fleet, and the course itself: `0/10` on the
templates, `10/10` with the solutions overlaid, templates restored byte for byte
afterwards.
