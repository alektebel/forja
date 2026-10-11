"""Queue & Workers From Scratch — stage 2: admission, and the full queue that
refuses instead of growing.

SOLUTION. This file also declares the execution model's frozen state for the
whole course: `Ticket`, `Flight`, `DeadLetter`, `Queue` and `EVENT_KINDS` are
read by eight later stages, so their field names, defaults and counter keys are
exactly §3's. The behaviour is four small methods, and the point of them is the
boundary: a queue holds `capacity` tasks — waiting plus running — and a submit
that would exceed it is a *refusal* (a `QueueFull` and a `refused` line), never a
silent drop and never a longer list. Nothing here moves the clock: the
timestamps and the event's `at` read `clock.now()`, and only the scheduler ticks.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

import fleet
import stage_01

#: Every kind of line a run's record can carry, in the order §3 fixes them.
EVENT_KINDS = ("submitted", "refused", "admitted", "shed", "blocked", "started",
               "succeeded", "failed", "died", "retried", "dead_lettered",
               "stopped")

#: The admission decisions a queue counts, zero-filled, in this order.
DECISION_KEYS = ("admitted", "refused", "shed", "blocked", "limit_hits")

#: What a task bag may carry: the fields `submit` reads off a foreign shape.
TASK_FIELDS = ("id", "ticks", "priority", "tenant", "attempts")


class QueueFull(fleet.QueueError):
    """The queue is at `capacity` and will not take one more task.

    It is a `QueueError`, so "the queue said no" is still one `except`. It is
    also its own type, because "full, come back later" is a different answer
    from "that is not a task", and a caller that retries has to tell them apart.
    """


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
    clock: fleet.Clock = field(default_factory=fleet.Clock)
    pending: list = field(default_factory=list)
    in_flight: dict = field(default_factory=dict)
    dead: list = field(default_factory=list)
    events: list = field(default_factory=list)
    sequence: int = 0
    decisions: dict = field(default_factory=_zero_decisions)

    def __post_init__(self):
        if self.clock is None:
            object.__setattr__(self, "clock", fleet.Clock())
        if isinstance(self.pool, Mapping):
            object.__setattr__(self, "pool", stage_01.parse_pool(self.pool))

    def depth(self):
        """Everything the queue is holding: the waiting *and* the running."""
        return len(self.pending) + len(self.in_flight)

    def queued(self):
        """What is still waiting for a slot."""
        return len(self.pending)

    def is_full(self):
        """True when the queue may not take one more task."""
        return self.depth() >= self.pool.capacity

    def submit(self, source):
        """Take one task in, or refuse it if the queue is already at capacity.

        The arrival counter is the queue's own: a ticket takes `sequence`, and
        only an admission spends it.
        """
        task = _as_task(source)
        if self.is_full():
            self.events.append({"at": self.clock.now(), "kind": "refused",
                                "task": task.id, "reason": "full"})
            raise QueueFull("pool %r is full: capacity %d, depth %d, refusing %r"
                            % (self.pool.id, self.pool.capacity, self.depth(),
                               task.id))
        ticket = Ticket(seq=self.sequence, task=task,
                        submitted_at=self.clock.now(), attempts=0)
        self.pending.append(ticket)
        object.__setattr__(self, "sequence", self.sequence + 1)
        self.events.append({"at": self.clock.now(), "kind": "submitted",
                            "task": task.id})
        return ticket


def _as_task(source):
    """One validated `stage_01.Task`, from any shape a caller may hand in.

    A `Task` is already validated, and a `Ticket` names one; everything else is
    a spec and goes through stage 1, so a typo'd key or a string tick is refused
    here rather than read as a default three stages later.
    """
    if isinstance(source, stage_01.Task):
        return source
    if isinstance(source, Ticket):
        return source.task
    if isinstance(source, Mapping):
        return stage_01.parse_task(source)
    fields = {name: getattr(source, name) for name in TASK_FIELDS
              if hasattr(source, name)}
    if fields:
        return stage_01.parse_task(fields)
    raise fleet.QueueError(
        "submit() takes a Task, a Ticket or a task mapping, not %r"
        % (type(source).__name__,))
