# Next session — where everything is

Written at the end of the session that shipped phase J's registration, G3
(`cpu-from-scratch`) and the J1 checkpoint. Everything in *Done* is committed and
pushed; everything in *In progress* is what to pick up next.

## Done, pushed, on `origin/main`

| Commit | Unit |
|---|---|
| `86724f2` | F1 `benchmark-from-scratch` |
| `4e6c7f2` | F2 `eval-framework-from-scratch` — 272 mutations, `MISSED OR BROKEN: 0` |
| `9332df2` | **Agent Infra**: `AGENT-INFRA.md` (the twelve-item list kept verbatim, mapped to courses by mechanism) and **phase J** registered in `codecraft/path.py` + `ROADMAP.md` |
| `68c98bb` | **G3 `cpu-from-scratch`** — 10 stages, provided `isa.py`, 360 mutations, `MISSED OR BROKEN: 0` |
| `b8c4a3b` | **J1 checkpoint**: the `queue-and-workers-from-scratch` scaffold and the provided `fleet.py` (proof: 29 checks, `ALL CHECKS PASS`) |

G3's numbers, for reference when a later course is measured against it:
`run_all.py` → `FAILED: 0`; `mutate_all.py` → `TOTAL 360/360` with per stage
36, 38, 32, 35, 33, 38, 37, 37, 40, 34; `verify_isa.py` → 56 checks;
`vcheck.py cpu-from-scratch` → `FAILED: 0`; `cz run cpu-from-scratch` → `0/10`;
`g3-smoke.py` → `SMOKE PASS` (fib 202 → 137 cycles across the three machines).
`codecraft/ROADMAP.md` now says **Sixteen courses, 191 graded checks**, and the
"next course to author" note names phase J.

## In progress — J1 `queue-and-workers-from-scratch` (phase J)

**What exists**

- `queue-and-workers-from-scratch/` — the scaffold from `cli.py new`, and
  `fleet.py`, the provided module, complete and proven.
- `/tmp/j1-checks/verify_fleet.py` — the provided module's own proof (29 checks).
  **`/tmp` is not durable**: if it is gone, rewrite it from the description at the
  end of this file; the design below is the authority, not the file.
- The recon that grounds this design: C2/D1/F2/A7 ownership, the manifest
  contract, and the three risks — summarised under *Ground rules* below.

**What is missing** — in this order (the G3 workflow, unchanged):

1. `/tmp/j1-checks/CONTRACT.md` — not written yet; **this document is the
   frozen design instead.** Copy the *Design* section below into it, add the
   per-stage mistake catalogue, and hand it to the ten delegates.
2. The ten stage templates + `solutions/stage_NN.py` + `/tmp/j1-checks/check_NN.py`
   + `mutate_NN.py` — one delegate per stage, each writing only its own four
   files (the rule that worked for F1, F2 and G3).
3. The harness: copy `/tmp/g3-checks/{run_all.py, mutate_all.py, assemble.py}`
   and adapt (`COURSE`, `HERE`, `G3_REPO` → `J1_REPO`); rewrite
   `course_head.py`/`course_tail.py` for this course (`ORDER = 17`, ten `STAGES`
   entries with real titles/tags/action/predict). Two things already fixed in the
   G3 versions and worth keeping: `mutate_all.py` counts a 60-second hang as
   *caught* (`[hung  ]`), and `assemble.py` refuses to emit a body that calls a
   dropped harness helper (`_env_dir`/`_course_dir`/`_main`) — put the `sys.path`
   insert in `_main()`, never inside `check()`.
4. The parent sweep: `python3 /tmp/j1-checks/run_all.py` (`FAILED: 0`) and
   `python3 /tmp/j1-checks/mutate_all.py` (`MISSED OR BROKEN: 0`, every planted
   mutation caught). A delegate's own verdict is not evidence.
5. `/tmp/j1-smoke.py` — all ten stages composed, with `time.time`,
   `time.sleep`, `time.monotonic` and `time.perf_counter` landmined, plus a
   module-dict check that no stage imports `time`, `threading` or `random`.
6. `python3 /tmp/j1-checks/assemble.py` → `queue-and-workers-from-scratch/course.py`,
   then the checks the repo itself gives: the assembled module's ten checks pass,
   `cz run queue-and-workers-from-scratch` → `0/10` with `not implemented yet`
   lines, and the READMEs (`README.md`, `solutions/README.md`) written from the
   real numbers.
7. Registration: `codecraft/path.py` J1 → `"course": "queue-and-workers-from-scratch"`,
   `"kind": "ready"` and a real `why`; `ROADMAP.md`
   (Sixteen → **Seventeen** courses, 191 → **201** checks, the ready row, the
   "next course to author" note moves to J2); the root README bullet.
8. Clean (`codecraft/{history.jsonl,profile.json,mentor_cache.json}` and every
   `__pycache__`), commit with the long body, `git pull --rebase origin main &&
   git push origin main`.

## Ground rules (unchanged, and they are what the grading rests on)

- **Stdlib only, deterministic.** No `time`, no `threading`, no `asyncio`, no
  `random`, no `os`, no network, no module-level mutable state, no wall clock
  anywhere. In this course the clock is `fleet.Clock` and **only the scheduler
  moves it**.
- **A course is its tests.** Each check catches mistakes that are easy to make
  and hard to notice, and its message names the mistake, not the symptom. The
  bar is every planted mutation caught (`MISSED OR BROKEN: 0`).
- **Docs are English.** The user writes Spanish; `AGENT-INFRA.md` keeps the
  user's twelve-item list verbatim in Spanish with English analysis.
- **Template shape**: `Queue & Workers From Scratch — stage N: <noun phrase>`,
  three to six `DESIGN DECISION — <question>?` blocks (each naming the rejected
  alternative *and its cost*), then `TODO: implement <names>.`; stubs raise
  `NotImplementedError("stage N: implement fn()")`. Solutions live in
  `solutions/stage_NN.py` and defer the reasoning to the template.
- **A stage imports earlier stages, never a later one.** The ladder for this
  course is given per stage below.
- **What J1 must not re-teach** (each already has a graded home): the tool loop,
  approvals and the audit line (C2 `agents-from-scratch` → `mcp-from-scratch`
  D1); budgets checked before the call and the `Ticker` idiom (C2 stage 9, F2
  stage 4); the retry taxonomy and idempotency keys (C2 stage 5, D1 stage 8);
  percentiles and metrics (A7 `deploy-and-debug`, C1 `evals-from-scratch`); and
  leases/heartbeats/WAL/crash recovery (J3), queue-depth metrics (J5). J1 ends at
  **scheduling, ordering, refusal, records and byte-identical runs**.
- **Word the failures for the coach**: `codecraft/patterns.py` classifies an
  unsolved stage's error text, and its needles for this course's topics are
  `timeout`/`ttl`/`redeliver`/`visibility` (lifecycle), `deadlock`/`race`/
  `atomic` (concurrency) and `order`/`tie`/`deterministic` (ordering). An
  assertion message that says "two runs diverge: the tie at priority 5 was
  broken by id" lands in the right bucket; "assertion failed" does not.

## Design — the provided module (written, committed, proven)

`fleet.py`, complete: `Clock` (`now`/`tick`/`.ticks`, bool-and-string hostile),
`QueueError(ValueError)`, `OUTCOMES = ("ok", "failed", "died")`, the read-only
catalogues `TASKS` (eight tasks: `id`, `ticks`, `priority`, `tenant`) and `POOLS`
(three pools: `id`, `max_concurrency`, `capacity`, `high_water`, `low_water`),
the fixture bags `TaskSpec`/`PoolSpec` + `make_task`/`make_pool`/`catalogue`, and
the workers `reliable`, `instant`, `sluggish`, `flaky`, `crasher`, `dying`,
`always`, `scripted`, `bad_shape`.

Two properties are load-bearing and must not be weakened:

- **A worker is a pure function of `(task, attempt)`.** It answers
  `{"status", "ticks", "detail"}` and there is no clock in its signature. The
  *scheduler* charges the ticks. That is what makes "the scheduler is a data
  structure and not a thread pool" literally true, and it is what makes two runs
  byte-identical.
- **`died` is not `failed`.** `failed` is a finished attempt that did not
  succeed; `died` is an attempt that never finished — the worker is gone and the
  queue has to get the task back. That distinction is stage 5's whole reason to
  exist.

## Design — the execution model (frozen; every stage's semantics hang off it)

The run is a discrete-event loop over ticks; there is never a real thread:

1. **Completions first.** Resolve everything due at the current tick, in
   `(finishes_at, sequence)` order — never in dictionary order.
   `ok` → the task is done; `failed` → the attempt failed; `died` (or a flight
   past its lease) → the task comes back.
2. **Then dispatch.** While there is a free slot and a pending ticket, start the
   highest-order ticket *at the current tick*.
3. **Then advance.** The clock moves to the earliest of the pending
   `finishes_at`, `deadline_at` and retry `ready_at`. Only the scheduler ever
   calls `tick()`, and it never advances past a completion it has not resolved.

The queue's state, **fixed here so that ten independently written stages agree**
(each is a frozen dataclass declared in `stage_02.py`):

```python
Ticket(seq, task, submitted_at, attempts, ready_at=None)   # one queued task
Flight(ticket, attempt, started_at, finishes_at, deadline_at)  # one running task
DeadLetter(task, attempts, reason, at)                     # one task the queue gave up on
Queue(pool, clock, pending: list, in_flight: dict, dead: list, events: list,
      sequence: int, decisions: dict)
```

`pending` holds `Ticket`s, `in_flight` is keyed by task id, `events` is the run's
record (each stage appends its own), `sequence` is the arrival counter (the tail
of every total order), and `decisions` counts the admission decisions
(`admitted`/`refused`/`shed`/`blocked`).

## Design — the ten stages

Each stage names the exact surface, the semantics the check must pin, and the
mistakes that must be planted as mutations. Titles are the ones for
`course_tail.py`.

### 1. `stage_01.py` — the task and the pool, and the typo that runs as a default

`TASK_KEYS`, `POOL_KEYS`, `TASK_DEFAULTS`, `POOL_DEFAULTS`, `Task`, `Pool`,
`parse_task`, `parse_pool`, `canonical_task`, `canonical_pool`.

- `parse_task(mapping)`: refuses an unknown key (naming it and the known ones), a
  missing `id`, an `id` that is not a non-empty str, `ticks`/`priority`/`attempts`
  that are bools, strings or negative, a `tenant` that is not a str. Applies the
  defaults. `attempts` is the task's maximum attempts (default 3) — stage 6 reads
  it, nothing before that cares.
- `parse_pool`: the same discipline, plus `low_water <= high_water <= capacity`
  and `max_concurrency >= 1`; a pool that fails either is refused with the two
  numbers in the message.
- `canonical_task`/`canonical_pool`: the sorted-key JSON text with the defaults
  materialised, so two spellings of the same spec are the same text — this is
  what makes a run reproducible from a config.
- Mistakes to plant: a typo accepted as a default; `"3"` accepted for `ticks`; a
  bool accepted as `priority`; defaults never materialised (so two spellings
  differ); the key order of the input surviving into the canonical text; a
  duplicated `id` in a list of tasks accepted; a pool whose water marks are
  nonsense accepted.

### 2. `stage_02.py` — admission, and the full queue that refuses instead of growing

`Queue` (with `submit`, `depth`, `queued`, `is_full`) and `QueueFull(QueueError)`,
plus the frozen state shapes above.

- `submit(task)`: validates through stage 1 when handed a raw mapping, then
  appends a `Ticket` with the next `sequence`. When `depth() == capacity` it
  **refuses with `QueueFull`**, naming the pool, the capacity and the task —
  a full queue never grows and never drops in silence.
- `depth()` is `len(pending) + len(in_flight)`; `queued()` is `len(pending)`.
- Appends the `submitted` event (and the `refused` event on refusal).
- Mistakes: silent drop when full; capacity counting only pending (so in-flight
  work is free); `submit` accepting a raw dict without validation; the sequence
  counter reset or shared between two queues; the refusal raising the base
  `QueueError` (so a caller cannot tell "full" from "malformed").

### 3. `stage_03.py` — priority as a total order, and the tie that makes two runs differ

`order_key(ticket)`, `reorder(queue)`, `pick_next(queue)`, `take_next(queue)`.

- `order_key(ticket)` is `(-ticket.task.priority, ticket.seq)`: **higher priority
  first, and the tie is broken by arrival, never by id**. `reorder` returns the
  pending tickets in service order; `pick_next` returns the first or `None`;
  `take_next` removes and returns it.
- Mistakes: sorting by priority alone and leaning on Python's stable sort (which
  is only the arrival order for the *first* sort, and silently wrong after a
  requeue); sorting by `id` (two runs with different submission orders diverge);
  reversing the priority sign so low numbers win; an unstable key that compares
  tasks (not tuples) and raises on a tie of equal priority *and* equal seq.

### 4. `stage_04.py` — the concurrency limit, checked before the worker starts

`free_slots(queue)`, `start(queue, ticket=None, worker=None)`, `complete(queue)`,
`OutcomeError(QueueError)`, `validate_outcome(answer)`.

- `free_slots` is `pool.max_concurrency - len(queue.in_flight)`.
- `start` returns `None` when no slot is free (the limit is *data*, not an
  exception) and increments `queue.decisions["limit_hits"]`; otherwise it takes
  the next ticket by stage 3's order, calls `worker(ticket.task, attempt=…)`,
  validates the outcome, and records a `Flight` with
  `started_at = clock.now()`, `finishes_at = started_at + outcome["ticks"]`,
  `deadline_at = None` (stage 5 fills that). It appends the `started` event.
- `complete(queue)` resolves every flight whose `finishes_at <= clock.now()`, in
  `(finishes_at, seq)` order: `ok` → drop the flight, count it, append
  `succeeded`; `failed`/`died` → drop the flight, return the ticket to pending
  with `attempts + 1` (stage 6 adds `ready_at` and the dead-letter policy).
- `validate_outcome` refuses anything that is not exactly
  `{"status", "ticks", "detail"}` with `status in OUTCOMES` and a non-negative
  int `ticks` — a worker's bad shape is a `QueueError` naming what was wrong, not
  a success and not a `KeyError`.
- Mistakes: the limit checked *after* the worker runs (so one too many always
  happens); a flight that never completes; completions resolved in dict order
  (two runs diverge); `finishes_at` not using the clock (so nothing ever
  finishes); a bad outcome filed as `ok`; `ticks` trusted without validation
  (a negative tick runs the clock backwards).

### 5. `stage_05.py` — the lease, and the worker that dies holding the slot

`DEFAULT_LEASE`, `sweep(queue)`, `ack(queue, task_id)`, `release(queue, task_id)`.

- `start` (stage 4) is called with a lease that stage 5 supplies by default;
  `deadline_at = started_at + lease`.
- `sweep(queue)`: any flight past its `deadline_at` **without a completion** is a
  `died` — it is removed, the ticket goes back with `attempts + 1`, the `died`
  event is appended, and the slot is free again. This is the whole point: a
  worker that goes away must not take the task with it.
- `ack` removes a flight and returns its task (the normal path); `release` puts
  the task back *without* counting a new attempt (a caller that knows better).
- Mistakes: a lease that never expires (the slot leaks forever); the swept task
  dropped instead of requeued; the sweep counting an attempt twice; a flight
  completing after its lease still counted as a success; `deadline_at` set from
  `finishes_at` (which is exactly the value that must not be trusted).

### 6. `stage_06.py` — retries, backoff on the injected clock, and the poison task

`BACKOFF_BASE`, `backoff(attempt)`, `due(queue)`, `dead_letter(queue, ticket, reason)`.

- On `failed`/`died`, the ticket re-enters with `ready_at = now + backoff(attempt)`
  on the *injected* clock, and the `retried` event is appended. Nothing sleeps.
- When `attempts >= task.attempts`, the task is dead-lettered instead: a
  `DeadLetter` with the reason, the `dead_lettered` event, and `queue.decisions`
  left alone. A dead-lettered task is *not* a failed run; it is a recorded
  outcome, and `queue.dead` is where it lives.
- `due(queue)` returns the tickets whose `ready_at` is at or before `now`
  (a delayed task is not eligible, and the scheduler must not pick it).
- Mistakes: backoff in wall time; a task retried forever because `attempts` is
  never compared; the attempt counter incremented on the *flight* instead of the
  ticket (so a requeue loses the count); a delayed ticket eligible early; the
  DLQ entry carrying no reason; a DLQ task also left in `pending`.

### 7. `stage_07.py` — backpressure: refuse, shed or block, and never lose a task

`POLICIES = ("refuse", "shed", "block")`, `admit(queue, task, *, policy="refuse")`,
`ShedError(QueueError)`, `BlockedError(QueueError)`.

- Below `high_water` every policy admits. At or above it: `refuse` raises
  `QueueFull`; `shed` dead-letters the *lowest-order pending* ticket (not the
  newest, and never an in-flight one) and then admits; `block` raises
  `BlockedError` and admits nothing, so the producer is *told* rather than
  silently queued.
- `queue.decisions` counts `admitted`, `refused`, `shed`, `blocked` — from the
  decisions actually taken, never from an intention.
- Mistakes: `shed` dropping the newest instead of the lowest-order task; `shed`
  dropping an in-flight task (which is how a running task disappears); a shed
  task vanishing without a DLQ entry; `block` queuing anyway; the counters
  incremented before the decision (so a refusal that raised still counted as
  admitted).

### 8. `stage_08.py` — ageing, and the tenant that never gets served

`AGE_STEP`, `AGE_LIMIT`, `waited(ticket, *, now)`, `effective_priority(ticket, *, now)`,
`reorder_aged(queue, *, now=None)`, `starved(queue, *, now=None, limit=AGE_LIMIT)`.

- `effective_priority = min(9, task.priority + waited // AGE_STEP)` — waiting
  buys priority in steps, capped, so a low-priority task cannot be postponed
  forever but also cannot leapfrog everything at once. Keep stage 3's
  `order_key(ticket)` untouched: ageing is a *second* order, and the check
  compares the two on a fixture where they differ.
- `starved` returns the tickets whose `waited` exceeds `limit` — the check
  asserts a fixture where the unaged order starves a tenant and the aged order
  does not.
- Mistakes: ageing added to the priority without the cap (so a very old task
  outranks everything, including the interactive tenant); `waited` measured from
  submission for an in-flight task and from `now` for a pending one (two clocks
  in one function); the aged order still breaking ties by id; `starved` counting
  in-flight tasks.

### 9. `stage_09.py` — the record: counters from the tickets, not from intentions

`EVENT_KINDS`, `RUN_KEYS`, `event(queue, kind, **fields)`, `run_record(queue, *, stopped=None)`.

- `RUN_KEYS = ("pool", "tasks", "submitted", "admitted", "refused", "shed",
  "blocked", "started", "succeeded", "failed", "died", "retried",
  "dead_lettered", "max_in_flight", "final_depth", "ticks", "stopped")`,
  **all present and zero-filled** except `stopped`.
- Every counter is derived from `queue.events` (and the queue's own tables),
  never from a separate tally kept alongside it: two sources of truth is how a
  record ends up disagreeing with the log it summarises.
- `max_in_flight` is the high-water mark of `len(in_flight)` over the run;
  `ticks` is `clock.ticks`; `stopped` is `None` for a drained run and a named
  reason otherwise (`"max_ticks"`, `"max_steps"`).
- Mistakes: a count taken from `decisions` where events are the truth (or the
  reverse); `max_in_flight` from a guess; a missing key instead of a zero; the
  record holding the live `events` list; `ticks` from `now()` instead of what
  was spent; `stopped` set on a run that finished.

### 10. `stage_10.py` — the scheduler run: two runs, identical bytes

`run(pool, tasks, *, worker, clock=None, policy="refuse", lease=DEFAULT_LEASE,
max_ticks=None, max_steps=None)`, `canonical_run(queue)`, `run_bytes(...)`.

- `run` is the loop from the model above: resolve completions, sweep leases,
  dispatch while slots allow, advance the clock to the earliest due time, repeat
  until the queue is drained or a bound stops it. `max_ticks` is checked against
  `clock.ticks` **before** the next dispatch, and the stop is `stopped="max_ticks"`
  in the record — not an exception and not a silent truncation.
- `canonical_run` is the JSONL of the events followed by the record line, sorted
  keys, ints only, `\n`-terminated: two runs of the same pool, tasks and worker
  produce the same bytes, and so do a run and a run rebuilt from
  `canonical_task`/`canonical_pool` text.
- Mistakes: the loop advancing the clock past an unresolved completion;
  `max_ticks` checked after a dispatch; the loop spinning when nothing can
  progress (a `died`-forever pool must stop, not hang); events in insertion
  order but the record regenerated from `decisions` (so the summary and the log
  disagree); `-0`/float leakage into the canonical text; an unordered dict
  surviving into the bytes.

## What `verify_fleet.py` checks (rewrite it if `/tmp` is gone)

29 checks, `checks: n, failed: 0` then `ALL CHECKS PASS`:

- the module's namespace holds none of `time`, `random`, `os`, `threading`,
  `asyncio`, `subprocess`, `multiprocessing`, `socket`, `queue`, `select`,
  `signal`, `uuid`, and its source does not mention `time.sleep`/`time.time`/`time
  .monotonic`/`threading.Thread`;
- `DEFAULT_TICKS`/`DEFAULT_PRIORITY`/`DEFAULT_TENANT`/`OUTCOMES` exactly, and
  `OUTCOMES` is a tuple; `QueueError` is a `ValueError`;
- `Clock`: reads 0, `tick()` is 1, `tick(4)` is 4 more, `.ticks` counts, `start=`
  sets the reading, `repr` is `Clock(now=0, ticks=0)`, monotone, and refusals for
  a bool/str/float/None start, a bool/str/float/None/negative tick, with the
  reading unchanged after a refusal;
- `TASKS`/`POOLS` are `MappingProxyType` and `operator.setitem` raises
  `TypeError`; every task spec has exactly `id/ticks/priority/tenant` with
  `id == key` and sane types; every pool spec has exactly
  `id/max_concurrency/capacity/high_water/low_water` with
  `low_water <= high_water <= capacity` and `max_concurrency >= 1`;
- `TaskSpec`/`PoolSpec` are frozen; `make_task`/`make_pool` read the catalogue,
  take overrides, give defaults for an unknown id, and refuse an unknown field
  with `TypeError`; `catalogue()` returns a list in order;
- `outcome()` has exactly three keys; `Worker` counts `calls` and `attempts`,
  refuses a non-callable and a bad attempt (`0`, `-1`, `True`, `"1"`);
  **no worker's signature contains `clock`**; every scripted worker answers the
  documented shape with the documented status and cost, and no two workers share
  state; `flaky(failures=2)` fails twice then works; `crasher(on_attempt=3)`
  fails exactly the third; `dying(on_attempt=2)` dies once; `scripted` repeats
  its last entry and refuses an empty or invalid plan; `bad_shape`'s four shapes
  answer what they claim and an unknown shape is refused.

## The two things that will bite

1. **A queue course is where wall time sneaks back in.** Every stage and every
   check must be greppable for `time`/`threading`/`random`, and the smoke run
   must landmine `time.time`, `time.sleep`, `time.monotonic` and
   `time.perf_counter`. The landmine is the proof; the convention is not.
2. **A check that only proves the solution passes proves nothing here.** The
   characteristic bugs of this course are the unstated ones: off-by-one at
   exactly `max_concurrency`, an unordered tie that makes two runs diverge, a
   refused-then-dropped task, a requeued task re-entering at the head and
   starving everyone, a lease that never expires, counters that disagree with the
   log. Plant them all.
