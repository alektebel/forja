"""Queue & Workers From Scratch — stage 10: Two runs, identical bytes: the
scheduler end to end.

You are writing the loop that composes the nine stages before it — the
completions, the sweeps, the dispatch and the advance of §3 — plus the one text
a run renders to, so that two runs of the same inputs are the same bytes.

DESIGN DECISION — In what order do the completions and the sweeps run?
    Rejected: sweep first, then complete. It is cheaper to write because the
    sweeper is the only thing that removes a flight past its deadline, so doing
    it first seems to clear the table. Its cost is a lie in the record: a
    worker that answered at exactly its deadline finished, and sweeping it first
    files a success as a death and requeues a task that had already run.
    Completions run first, so the flight that finished is gone before the
    sweeps look for expired ones.

DESIGN DECISION — How does a failed or died attempt reach the retry schedule?
    Rejected: let stage 4's `complete` and stage 5's `sweep` requeue the ticket,
    and dispatch it again as soon as it is due. Its cost is a pool with no
    backoff and no budget: a poison task is dispatched in a tight loop forever,
    because nothing ever compares the attempts spent against the task's own
    allowance. The loop applies stage 6's `requeue` to every non-ok outcome, so
    the retry waits `backoff` ticks on the injected clock and a task out of
    attempts becomes a dead letter.

DESIGN DECISION — How does a bound stop the run?
    Rejected: raise when `max_ticks` or `max_steps` is spent. Its cost is a
    caller that cannot tell a stopped run from a broken one, and a queue whose
    log ends mid-sentence with no line saying why. The bound is data: the loop
    returns the reason and the record carries it as `stopped`, with the matching
    `stopped` line in the log — the same shape a normal completion has.

DESIGN DECISION — What ends a run that cannot make progress?
    Rejected: stop only when the queue is empty, and let a pool whose every
    attempt dies keep being retried. Its cost is a deterministic loop that never
    terminates — a scheduler that hangs is worse than one that reports. The loop
    notices when the queue emptied with a grown dead list: it gave up on work
    rather than finishing it, and `stopped` is `"no_progress"`, not a clean
    drain.

TODO: implement `run`, `canonical_run`, `run_bytes`.
"""


def run(pool, tasks, *, worker, clock=None, policy="refuse", lease=None,
        max_ticks=None, max_steps=None):
    """Admit `tasks`, then drive §3's loop until the queue drains or a bound
    stops it, and return the queue with its log and its record."""
    raise NotImplementedError("stage 10: implement run()")


def canonical_run(queue):
    """The run's events, in order, each a JSON object on its own line, then the
    record line, `\\n`-terminated and identical whenever it is rendered."""
    raise NotImplementedError("stage 10: implement canonical_run()")


def run_bytes(pool, tasks, *, worker, **kwargs):
    """`canonical_run` of a fresh run of the same inputs, as bytes."""
    raise NotImplementedError("stage 10: implement run_bytes()")
