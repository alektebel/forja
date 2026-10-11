"""Queue & Workers From Scratch — stage 2: Admission, and the full queue that
refuses instead of growing

This stage declares the execution model's frozen state for the whole course.
`Ticket`, `Flight`, `DeadLetter`, `Queue` and `EVENT_KINDS` are read by eight
later stages, so their field names, defaults and counter keys are fixed here,
once; nothing in this file may change them. What is *yours* is the boundary of
the queue: what a submit does when the queue is already holding `capacity`
tasks.

DESIGN DECISION — a full queue refuses; it does not grow and it does not drop.
    The alternative is to append anyway (the queue becomes an unbounded buffer,
    so a producer that outruns its workers turns a bounded machine into an
    out-of-memory crash instead of a signal) or to drop the task in silence (the
    task is lost and the run's own record says it was never offered, which is the
    one thing a record must never say). A refusal costs one exception and one
    `refused` line, and it is the only outcome a caller can act on.

DESIGN DECISION — `depth()` counts the running tasks too, not just the waiting.
    `depth() == len(pending)` is the tempting reading, and its cost is doubled
    capacity: `max_concurrency` tasks running plus `capacity` tasks waiting means
    the configured bound no longer bounds anything. Depth is what the queue is
    responsible for: waiting plus running.

DESIGN DECISION — the arrival counter and the clock belong to the queue.
    The alternative is a module-level sequence counter or a module-level clock.
    Its cost is not a crash, it is silent cross-talk: two queues built in one
    process then share an arrival order and a time, so the second run is not the
    first run, and "two runs of the same input are the same run" stops being true
    before any scheduler exists. A fresh `Queue(pool)` gets a fresh `Clock()`, and
    `submit` reads that clock — it never moves it.

DESIGN DECISION — a refusal is recorded first and raised second.
    The alternative is `raise` and then log, or raising the base `QueueError`.
    The first cost is a run whose log claims the task was never offered, when it
    was offered and turned away; the second is a caller that cannot tell "full,
    come back later" from "that is not a task, never". So: append the `refused`
    line, then raise `QueueFull`, and neither the pending list nor the arrival
    counter moves.

DESIGN DECISION — the records are frozen; the queue's tables are plain lists.
    The alternative is a mutable record. Its cost is an alias: a caller that
    edits the ticket it was handed back changes what the log already said, and
    the next stage's check reads the edit as history. The tables are mutable
    because the queue is the machine that moves tickets between them, but the
    fields that name them are frozen, so a queue cannot be rewired mid-run.

TODO: implement `Queue.__post_init__`, `Queue.submit`, `Queue.depth`,
`Queue.queued` and `Queue.is_full`.

    Queue(pool, *, clock=None)   a queue over one pool; `clock=None` makes its
                                 own `fleet.Clock`; a raw pool mapping is
                                 validated through stage 1
    queue.submit(source) -> Ticket
                                 one task in: a `stage_01.Task`, a `Ticket` (its
                                 task is admitted as a new arrival), a task
                                 mapping or a fleet-style task bag — everything
                                 but a Task/Ticket goes through stage 1's
                                 `parse_task`, so a typo is refused, not read as
                                 a default. The ticket takes `seq = sequence`,
                                 `attempts = 0` and `submitted_at = clock.now()`.
                                 At `capacity` it raises `QueueFull` (naming the
                                 pool, the capacity and the task) after appending
                                 a `refused` line, and nothing else moves.
    queue.depth()  -> int        waiting + running
    queue.queued() -> int        waiting only
    queue.is_full() -> bool      depth() >= pool.capacity
"""

from dataclasses import dataclass, field

import fleet
import stage_01

#: Every kind of line a run's record can carry, in the order §3 fixes them.
EVENT_KINDS = ("submitted", "refused", "admitted", "shed", "blocked", "started",
               "succeeded", "failed", "died", "retried", "dead_lettered",
               "stopped")

#: The admission decisions a queue counts, zero-filled, in this order.
DECISION_KEYS = ("admitted", "refused", "shed", "blocked", "limit_hits")


class QueueFull(fleet.QueueError):
    """The queue is at `capacity` and will not take one more task."""


def _zero_decisions():
    """A fresh counter bag: one dict per queue, never a shared default."""
    return {key: 0 for key in DECISION_KEYS}


@dataclass(frozen=True)
class Ticket:
    """One queued task: the arrival, its place in line, and its attempt count."""

    seq: int
    task: stage_01.Task
    submitted_at: int
    attempts: int
    ready_at: int | None = None


@dataclass(frozen=True)
class Flight:
    """One running task: its ticket, the attempt, and the three tick marks."""

    ticket: Ticket
    attempt: int
    started_at: int
    finishes_at: int
    deadline_at: int | None


@dataclass(frozen=True)
class DeadLetter:
    """One task the queue gave up on: which, how many attempts, why, and when."""

    task: stage_01.Task
    attempts: int
    reason: str
    at: int


@dataclass(frozen=True)
class Queue:
    """The queue: the pool it serves, the clock it reads, and its tables.

    Frozen, because a caller must not be able to swap a queue's clock or its
    tables out from under the records that name them; the tables it names are
    themselves mutable, because they are the state. Every field but `pool`
    defaults, so `Queue(pool)` is a fresh empty queue with its own clock.
    """

    pool: stage_01.Pool
    clock: fleet.Clock = None
    pending: list = field(default_factory=list)
    in_flight: dict = field(default_factory=dict)
    dead: list = field(default_factory=list)
    events: list = field(default_factory=list)
    sequence: int = 0
    decisions: dict = field(default_factory=_zero_decisions)

    def __post_init__(self):
        raise NotImplementedError("stage 2: implement Queue.__post_init__()")

    def depth(self):
        raise NotImplementedError("stage 2: implement Queue.depth()")

    def queued(self):
        raise NotImplementedError("stage 2: implement Queue.queued()")

    def is_full(self):
        raise NotImplementedError("stage 2: implement Queue.is_full()")

    def submit(self, source):
        raise NotImplementedError("stage 2: implement Queue.submit()")
