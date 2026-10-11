"""Queue & Workers From Scratch — stage 10: Two runs, identical bytes: the
scheduler end to end.

SOLUTION. `run` is §3's loop, and it composes the nine stages before it: it
admits each task through stage 7's `admit` under the caller's policy, then, every
tick, resolves the completions stage 4 owes — in `(finishes_at, seq)` order and
*before* stage 5 sweeps the expired leases, so a flight that finished exactly at
its deadline is a success and not a death — turns every failed or died attempt
into stage 6's retry schedule, dispatches while a slot is free and a ticket is
due, and advances the clock to the earliest `finishes_at`, `deadline_at` or retry
`ready_at`. The clock is the caller's, or a fresh one, and it is the only thing
`run` moves.

Three rules make the composition honest. First, a bound stops the run as data,
never as an exception: `max_ticks` is checked against `clock.ticks` right before
the dispatch and `max_steps` against the iterations spent, and either becomes the
record's `stopped` reason. Second, a pool that cannot progress stops rather than
spins: when the queue empties while its dead list grew — every attempt died and
the run gave up on the work rather than finishing it — the run reports
`stopped="no_progress"`. Third, the record is written once, by stage 9's
`run_record`, which is also the single writer of the `stopped` line, so `run`
passes the reason and never appends that line itself. `canonical_run` renders the
log and then the record as JSONL with sorted keys and no whitespace, so two runs
of the same inputs are one text, byte for byte.

The join between stage 4/5 and stage 6 is the one place the composition is not a
plain call. `complete` and `sweep` return a failed or died ticket to `pending`
due immediately; stage 6's `requeue` owns the backoff and the attempt budget, and
is written to take the ticket as it stood *before* the attempt. So the loop hands
it exactly that: the pending entry the resolution just made, with the attempt
this outcome spent backed out again.
"""

import dataclasses
import json

import fleet
import stage_02
import stage_04
import stage_05
import stage_06
import stage_07
import stage_09


def run(pool, tasks, *, worker, clock=None, policy="refuse", lease=None,
        max_ticks=None, max_steps=None):
    """Run `tasks` through `pool` on `worker` until it drains or a bound stops it.

    Every task is offered to the queue through stage 7's `admit` under `policy`,
    so a refusal, a shed or a block is recorded in the log rather than lost — a
    task the queue would not take is a refuse/shed/block line, and the run goes
    on with the tasks it did take. The queue then runs §3's loop for it: resolve
    the completions, sweep the expired leases, schedule the retries, dispatch
    while the pool has a slot, and advance the clock to the next thing that can
    change the state.

    `clock` is the injected clock; a fresh one starts at zero. `lease` is the
    deadline stage 4 stamps on each flight (no lease means no deadline). The two
    bounds are the only way out besides an empty queue: `max_ticks` is checked
    against what the clock has spent before the next dispatch, and `max_steps`
    against the iterations the loop has taken; either is written to the record as
    `stopped`, never raised and never silently dropped. The run is done when the
    queue holds nothing; if it emptied because it gave up on work (the dead list
    grew) the stop is `"no_progress"`, and only a run that finished everything it
    took is a clean drain. The returned queue carries the whole log; the record
    is written here, once, so the `stopped` line is in the log before the caller
    ever asks for it.
    """
    queue = stage_02.Queue(pool, clock=clock)
    for task in tasks:
        try:
            stage_07.admit(queue, task, policy=policy)
        except (stage_02.QueueFull, stage_07.ShedError, stage_07.BlockedError):
            pass
    stopped = _loop(queue, worker, lease, max_ticks, max_steps)
    stage_09.run_record(queue, stopped=stopped)
    return queue


def _loop(queue, worker, lease, max_ticks, max_steps):
    """§3's loop itself: resolve, sweep, retry, dispatch, advance, repeat.

    The bounds are checked after the resolution and before the dispatch, so a
    run at the bound still resolves the work already in the air and only stops
    starting new work. The dead end is `depth() == 0`: a queue holding nothing
    ran to its end, and the dead list says whether it finished or gave up.
    """
    steps = 0
    while True:
        outcomes = tuple(stage_04.complete(queue)) + tuple(stage_05.sweep(queue))
        _retry(queue, outcomes)
        if max_ticks is not None and queue.clock.ticks >= max_ticks:
            return "max_ticks"
        if max_steps is not None and steps >= max_steps:
            return "max_steps"
        steps += 1
        while stage_04.free_slots(queue) > 0:
            if stage_04.start(queue, worker, lease=lease) is None:
                break
        if queue.depth() == 0:
            return "no_progress" if queue.dead else None
        advance_to = _next_time(queue)
        now = queue.clock.now()
        if advance_to is None or advance_to <= now:
            return "no_progress"
        queue.clock.tick(advance_to - now)


def _retry(queue, outcomes):
    """Hand every failed or died attempt to stage 6's schedule.

    Stage 4 and stage 5 already put the ticket back in `pending` with this
    attempt spent and no `ready_at`; stage 6's `requeue` is written for the
    ticket as it stood before the attempt, so the loop backs the attempt out
    again before handing it over. A retry comes back with its backoff and its
    arrival number intact; a ticket out of attempts becomes its dead letter, and
    the dead list is what tells the run it gave up on something.
    """
    for outcome in outcomes:
        if outcome["status"] == "ok":
            continue
        ticket = _pending_ticket(queue, outcome["task"])
        spent = dataclasses.replace(ticket, attempts=outcome["attempt"] - 1)
        stage_06.requeue(queue, spent, reason=outcome["status"])


def _pending_ticket(queue, task_id):
    """The pending ticket the resolution just returned for `task_id`."""
    for ticket in queue.pending:
        if ticket.task.id == task_id:
            return ticket
    raise fleet.QueueError(
        "the queue resolved %r but left no pending ticket for its retry"
        % (task_id,))


def _next_time(queue):
    """The earliest tick that can change the state: finish, lease or retry.

    A completion resolves at its `finishes_at`, a lease at its `deadline_at`,
    and a delayed ticket becomes due at its `ready_at`; the loop moves to the
    first of those, never past one it has not resolved. `None` means nothing can
    change without new work, which is the dead end.
    """
    times = []
    for flight in queue.in_flight.values():
        times.append(flight.finishes_at)
        if flight.deadline_at is not None:
            times.append(flight.deadline_at)
    for ticket in queue.pending:
        if ticket.ready_at is not None:
            times.append(ticket.ready_at)
    return min(times) if times else None


def canonical_run(queue):
    """The run as one text: the events in order, then the record, one per line.

    Each line is a JSON object with its keys sorted and no whitespace, and the
    text is `\\n`-terminated, so the same run renders to the same bytes whenever
    it is rendered. The record line is stage 9's `run_record`, handed the reason
    its own `stopped` line already carries, so rendering is the only thing this
    does — it writes no second log and claims no stop the log cannot corroborate.
    """
    reason = None
    for line in queue.events:
        if line["kind"] == "stopped":
            reason = line.get("reason")
    record = stage_09.run_record(queue, stopped=reason)
    lines = [_canonical(line) for line in queue.events]
    lines.append(_canonical(record))
    return "".join(line + "\n" for line in lines)


def _canonical(value):
    """One line of the run's text: sorted keys, no separators' whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def run_bytes(pool, tasks, *, worker, **kwargs):
    """`canonical_run` of a fresh run, as the bytes of its JSONL text."""
    return canonical_run(run(pool, tasks, worker=worker, **kwargs)).encode("utf-8")
