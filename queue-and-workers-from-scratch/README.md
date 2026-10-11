# Queue & Workers From Scratch

Build a scheduler as a data structure: ten stages, one queue, and two runs that
produce identical bytes. In pure standard-library Python — no threads, no
asyncio, no wall clock, no sleeps.

Every "worker pool" that gets written starts life as `concurrent.futures` with a
loop around it, and the loop is where the hard parts hide: who counts as
running, what happens when the limit is reached, what a task that never
finishes gives back, and how many times a poison task is tried before somebody
gives up on it. None of those are answered by a thread pool — they are answered
by the queue, and this course builds that queue from the empty file up. The
threads are deliberately absent: a worker here is a pure function of `(task,
attempt)`, so the whole system is deterministic, and every claim about it can be
an assertion with a number in it.

## The stages

Ten graded stages. Each one targets a mistake that is easy to make and hard to
notice.

| # | File | The mechanism | The thing people get wrong |
|---|---|---|---|
| 1 | `stage_01.py` | Typed specs, one canonical text per spec | A misspelled field accepted and defaulted (`{"prioriti": 9}` runs at priority 5) |
| 2 | `stage_02.py` | Admission, `QueueFull`, depth, the sequence | Capacity measured against the pending list, so running tasks get queue space |
| 3 | `stage_03.py` | Priority as a total order: `(-priority, seq)` | Sorting by priority alone, which is stable only until the first requeue |
| 4 | `stage_04.py` | The concurrency limit checked before the worker runs | A limit checked after the worker, so a full pool starts one task too many |
| 5 | `stage_05.py` | The lease: `deadline_at`, `sweep`, `ack`, `release` | A lease that never expires, so the slot leaks forever |
| 6 | `stage_06.py` | A growing backoff on the injected clock, and dead letters | A flat or off-by-one schedule, so a poison task hammers the pool or waits forever |
| 7 | `stage_07.py` | The water mark and the three answers: refuse, shed, block | A mark compared against `capacity` instead of `depth()`; `shed` dropping the wrong ticket |
| 8 | `stage_08.py` | Ageing as a second order, not a second clock | An uncapped boost, so an old task outranks the interactive tenant forever |
| 9 | `stage_09.py` | `run_record`: every number rebuilt from the log | A counter taken from a tally beside the log, and a stop the record declares instead of reads |
| 10 | `stage_10.py` | The loop, the bounds, and canonical JSONL bytes | Sweeps running before completions, so a flight finishing at its deadline is filed as a death |

Stages 4–10 compose the earlier ones (stage 7 admits through stage 6's requeue,
stage 9 reads the log stage 2 declares, stage 10 runs all nine in order), so
they are meant to be done in order — each check imports the solutions of the
stages it builds on.

## The provided fleet

`fleet.py` is given and is not part of the exercise: it is the world the
scheduler schedules. It holds `Clock` (the only clock, moved only by whoever
schedules), the frozen `TaskSpec`/`PoolSpec` specs with `make_task`/`make_pool`
and the named `TASKS`/`POOLS` above, `outcome`, and a catalogue of workers built
to fail in the interesting ways: `instant`, `reliable`, `sluggish`, `flaky`
(fails a fixed number of attempts), `crasher` (raises), `dying` (never finishes,
so a lease is what reclaims it), `always`, `scripted`, `bad_shape`, `catalogue`.

Two rules make the rest of the course checkable:

- **A worker is a pure function of `(task, attempt)`** answering
  `{"status", "ticks", "detail"}`. It reads no clock and holds no state; the
  scheduler charges the ticks it reports.
- **The clock is the queue's own.** Nothing else moves it, `sleep` appears
  nowhere, and no number in this course is a float: every count is an int, so a
  run is a function of its inputs and nothing else.

## How to use this directory

```bash
python3 codecraft/cli.py run queue-and-workers-from-scratch   # what to build next, and why
python3 codecraft/cli.py hint queue-and-workers-from-scratch  # when a nudge is not enough
```

Or without codecraft:

```bash
python3 -c "import course; [print(i, s.title) for i, s in enumerate(course.STAGES, 1)]"
```

Implement the templates at the top level; finished versions are in `solutions/`.
Copy a solution over its template to compare (`cp solutions/stage_05.py
stage_05.py`), and put the template back to try again.

## Prerequisites

`J1` is where the J line starts: nothing here needs a course before it. Basic
Python (classes, dataclasses, closures) is enough; the parts that usually trip
people up — a frozen dataclass, a mapping proxy, a key function that returns a
tuple — are introduced where they are used. No dependencies outside the
standard library, no network.

## Design decisions

- **The clock is injected and only the scheduler moves it.** `Clock` has
  `tick(n)` and a `ticks` count and nothing else; a worker that wanted to wait
  would have nowhere to wait. That is what makes a lease, a backoff and a
  max-ticks bound checkable numbers instead of timing-dependent behaviour.
- **`died` is not `failed`.** A `failed` task finished and did not succeed; a
  task that `died` never finished at all, so the queue owes it back to
  somebody. Collapsing the two is how a slot leaks in production.
- **Completions resolve before sweeps, at every tick.** A flight that finishes
  exactly at its deadline is a completion, not a death. The order is frozen in
  the contract and checked by stage 10, because the opposite order loses one
  task per deadline and looks fine.
- **The lease is a parameter, not a field.** `start(queue, worker, *,
  lease=None)` takes the deadline policy from the caller and stores it on the
  flight, so stage 4 can schedule work with no lease at all and stage 10 can
  pass its own.
- **State lives where the contract says it lives.** `Ticket`, `Flight`,
  `DeadLetter`, `Queue` and the twelve event kinds are frozen in stage 2 and
  read by eight later stages. A per-queue private table (stage 4 keeps the
  worker's answer in one) is not part of that shape, and the checks pin the
  shape.
- **The record is the log, and nothing else.** Every counter in `run_record`
  is rebuilt from the lines the run wrote; `stopped` is read off the log's last
  stop. A reason handed to the function is written once through `event()` if
  the log carries no stop at all, and the log wins whenever the two disagree.
  A summary that declares a value instead of deriving it is the defect this
  stage exists to make impossible.
- **Shedding picks the lowest-order pending ticket — by the same order
  everything else uses.** No policy in this course chooses a task by id, by
  list position or by age except where ageing says so, and stage 7 counts what
  each decision cost so "nothing was lost" is a number.

## Verification

The solutions pass all ten checks, and every check is mutation-tested: 386
plausible wrong implementations — the typo'd field that runs as a default, the
limit checked after the worker, a lease that never expires, a flat backoff, the
mark compared against `capacity`, an uncapped boost, a counter read off the
decisions tally, sweeps before completions — are each planted into a solution
and the stage's check must fail. Per stage: 38, 40, 33, 40, 40, 40, 40, 39, 40,
36. `git log` and the checks are the record; the mutations were applied
privately, by anchor, to a rebuilt tree, and the assertions that catch them name
the mistake in their message.

A single end-to-end smoke then runs the assembled course against the reference
solutions, in one process and one clock:

```
SMOKE PASS — 10 stages, one deterministic queue
  run: 8 tasks, pool 'wide' (concurrency 4, capacity 16): 15 ticks, 32 events, 1415 bytes canonical
  record: started 8, succeeded 8, failed 0, died 0, retried 0, dead-lettered 0, max_in_flight 4, final_depth 0, stopped None
  lease: a flight past 8 ticks returns its task and frees its slot
  backoff: [1, 2, 4] ticks for attempts (1, 2, 3)
  policies: refuse, shed, block — each a decision, and the queue never past capacity
  ageing: after 24 ticks the starved tenant is named, and the cap holds
  stuck: a pool whose every attempt dies stops with 'no_progress', not a hang
```

That smoke earned its keep once: `run_record(queue)` with no reason reported
`stopped=None` while the queue's log carried `{'kind': 'stopped', 'reason':
'no_progress'}` — a record declaring a value instead of reading one. Stage 9 now
derives the stop from the log, and the case is a fixture with two mutations
behind it.

## Where this stops

Deliberately left out, so you know the boundary:

- **No threads, no processes, no I/O.** The scheduler is a data structure that
  moves tasks between three tables as the clock advances. Running it for real
  means a runner that pops a task and calls a subprocess; the concurrency, the
  rate limiting and the cancellation policy are the parts worth getting right
  first, and they are all here.
- **No persistence and no multiple schedulers.** One queue, one clock, one
  process: the events are a log you can read, not a log you can replay after a
  crash, and nothing here coordinates two schedulers over the same workers.
- **Fairness is one mechanism deep.** Ageing with a cap is implemented and
  checked; weighted fair queueing, quotas per tenant and the difference between
  fairness and rate limiting are the subjects of the system-design material,
  not of these ten stages.
- **The bounds are the caller's problem.** `max_ticks` and `max_steps` stop a
  run with a reason; deciding how long a real deployment should wait, and
  what to do with the tasks still queued, is a policy this course deliberately
  leaves as data.
