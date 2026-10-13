"""fleet.py — the clock, the tasks and the workers, PROVIDED COMPLETE.

This is J1's `lab.py`/`isa.py`: the thing under test and the things that fail. A
task queue is a machine that decides *when* other people's work runs, and then
has to say something true about what it did, so the domain here is deliberately
hostile: tasks that cost one tick and tasks that cost twelve, workers that are
slower than the estimate, workers that fail on the third attempt, workers that
die holding the slot and never come back, and a worker that reports a shape
nobody asked for.

Everything in this file is deterministic. There is no `threading`, no `time`, no
`random`, no `os`, no network, and no module-level mutable state: the "clock" is
a counter (`Clock`) that **the queue** advances, so a wait, a lease and a backoff
are properties of the code under test and not of the machine it ran on.

A worker here is a *pure function* of a task and an attempt: it answers with a
status and the number of ticks the task costs, and it never touches the clock.
That is the whole point of the model — the scheduler is a data structure, so two
runs of the same pool over the same tasks are the same run, byte for byte.

Nothing here knows about admission, ordering, concurrency limits, leases,
retries, dead letters, backpressure, ageing or records — that is the course.
"""

from dataclasses import dataclass
import types

#: What one task costs when it does not say.
DEFAULT_TICKS = 3

#: What one task is worth when it does not say (higher is served first).
DEFAULT_PRIORITY = 5

#: The default tenant: what a task is billed to, and what ages.
DEFAULT_TENANT = "batch"

#: The three things a worker can report about a task it was given.
#: `ok` and `failed` are finished (one succeeded, one did not); `died` is a task
#: that never finished — the worker is gone and the queue has to get it back.
OUTCOMES = ("ok", "failed", "died")

#: The raw task catalogue: the shape a job file carries, before anything
#: validates it. `ticks` is what the task costs a worker that runs it.
TASKS = types.MappingProxyType({
    "render": {"id": "render", "ticks": 3, "priority": 5, "tenant": "batch"},
    "index": {"id": "index", "ticks": 7, "priority": 1, "tenant": "batch"},
    "notify": {"id": "notify", "ticks": 1, "priority": 9, "tenant": "interactive"},
    "train": {"id": "train", "ticks": 12, "priority": 3, "tenant": "batch"},
    "audit": {"id": "audit", "ticks": 5, "priority": 5, "tenant": "compliance"},
    "purge": {"id": "purge", "ticks": 2, "priority": 7, "tenant": "compliance"},
    "digest": {"id": "digest", "ticks": 4, "priority": 6, "tenant": "interactive"},
    "publish": {"id": "publish", "ticks": 3, "priority": 9, "tenant": "interactive"},
})

#: The raw pool catalogue: the shape a pool config carries, before anything
#: validates it. `capacity` is how many tasks the queue will hold; the water
#: marks are the depths at which a policy starts and stops refusing.
POOLS = types.MappingProxyType({
    "small": {"id": "small", "max_concurrency": 1, "capacity": 4,
              "high_water": 3, "low_water": 1},
    "narrow": {"id": "narrow", "max_concurrency": 2, "capacity": 6,
               "high_water": 5, "low_water": 2},
    "wide": {"id": "wide", "max_concurrency": 4, "capacity": 16,
             "high_water": 12, "low_water": 4},
})


class QueueError(ValueError):
    """A spec, a pool, a task or a policy the queue refuses.

    The queue's own refusal (a typo in a spec, a task that is not a task, a
    limit that is already gone) travels as this type, so a check can tell "your
    configuration is wrong" from "the work failed".
    """


def _require_int(value, what, *, minimum=0):
    """The house guard: a bool is not an int, and neither is a string."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise QueueError("%s must be an int, got %r" % (what, value))
    if value < minimum:
        raise QueueError("%s must be >= %d, got %r" % (what, minimum, value))
    return value


class Clock:
    """The injected clock: a counter, not a wall clock.

    A tick is one unit of work. The only thing that moves the value is `tick()`,
    and in this course the only caller is the queue: workers report what a task
    costs and the scheduler charges it.
    """

    def __init__(self, start=0):
        self._value = _require_int(start, "Clock start")
        self.ticks = 0

    def now(self):
        """The current reading."""
        return self._value

    def tick(self, n=1):
        """Advance by `n` ticks and return the new reading."""
        _require_int(n, "tick(n): n")
        self._value += n
        self.ticks += n
        return self._value

    def __repr__(self):
        return "Clock(now=%d, ticks=%d)" % (self._value, self.ticks)


@dataclass(frozen=True)
class TaskSpec:
    """A task the way `parse_task` will build one: an attribute bag, not a
    student type, so a check can fill a queue without importing stage 1."""

    id: str
    ticks: int = DEFAULT_TICKS
    priority: int = DEFAULT_PRIORITY
    tenant: str = DEFAULT_TENANT


@dataclass(frozen=True)
class PoolSpec:
    """A pool the way `parse_pool` will build one."""

    id: str
    max_concurrency: int = 1
    capacity: int = 4
    high_water: int = 3
    low_water: int = 1


def make_task(id, *, ticks=None, priority=None, tenant=None):
    """A task spec by id, out of `TASKS` unless overridden. A field the shape
    does not have is refused here, not ignored: the fixtures teach the same
    lesson as the course."""
    base = dict(TASKS.get(id, {"id": id}))
    base.update({"id": id})
    for key, value in (("ticks", ticks), ("priority", priority), ("tenant", tenant)):
        if value is not None:
            base[key] = value
    return TaskSpec(**base)


def make_pool(id="small", *, max_concurrency=None, capacity=None,
              high_water=None, low_water=None):
    """A pool spec by id, out of `POOLS` unless overridden."""
    base = dict(POOLS.get(id, {"id": id}))
    base["id"] = id
    for key, value in (("max_concurrency", max_concurrency), ("capacity", capacity),
                       ("high_water", high_water), ("low_water", low_water)):
        if value is not None:
            base[key] = value
    return PoolSpec(**base)


def outcome(status, ticks=0, detail=""):
    """The dict a worker answers with. Build one rather than spelling the keys."""
    return {"status": status, "ticks": ticks, "detail": detail}


class Worker:
    """A scripted worker: `worker(task, *, attempt=1) -> outcome`.

    `calls` counts invocations, which is what a retry check asserts ("the task
    was attempted twice, not once and not three times"). The worker never moves
    the clock: it answers with the ticks the task costs and the scheduler
    charges them.
    """

    def __init__(self, fn, *, label=None):
        if not callable(fn):
            raise QueueError("Worker needs a callable, got %r" % (type(fn).__name__,))
        self._fn = fn
        self.label = label or getattr(fn, "__name__", "worker")
        self.calls = 0
        self.attempts = {}

    def __call__(self, task, *, attempt=1):
        _require_int(attempt, "attempt", minimum=1)
        task_id = getattr(task, "id", task)
        self.calls += 1
        self.attempts[task_id] = self.attempts.get(task_id, 0) + 1
        answer = self._fn(task, attempt)
        if isinstance(answer, dict) and "status" in answer:
            return answer
        return answer

    def __repr__(self):
        return "<Worker %s calls=%d>" % (self.label, self.calls)


def _ticks_of(task, factor=1):
    ticks = getattr(task, "ticks", DEFAULT_TICKS)
    return ticks * factor


def reliable(*, factor=1, detail=""):
    """Does the work and reports it: `ok`, at the task's cost (times `factor`)."""
    def fn(task, attempt):
        return outcome("ok", _ticks_of(task, factor), detail or "done")
    return Worker(fn, label="reliable")


def instant():
    """Reports `ok` while costing *no* ticks — a task that is not really work."""
    def fn(task, attempt):
        return outcome("ok", 0, "nothing to do")
    return Worker(fn, label="instant")


def sluggish(*, factor=3):
    """Always slower than the estimate, and honest about it."""
    def fn(task, attempt):
        return outcome("ok", _ticks_of(task, factor), "slow but correct")
    return Worker(fn, label="sluggish")


def flaky(*, failures=2, cost=None):
    """Fails the first `failures` attempts, then does the work."""
    def fn(task, attempt):
        if attempt <= failures:
            return outcome("failed", _ticks_of(task, cost or 1),
                           "attempt %d failed" % attempt)
        return outcome("ok", _ticks_of(task), "succeeded on attempt %d" % attempt)
    return Worker(fn, label="flaky")


def crasher(*, on_attempt=3):
    """Succeeds until `on_attempt`, which it fails — the classic poison task."""
    def fn(task, attempt):
        if attempt == on_attempt:
            return outcome("failed", _ticks_of(task), "crashed on attempt %d" % attempt)
        return outcome("ok", _ticks_of(task), "fine")
    return Worker(fn, label="crasher")


def dying(*, on_attempt=2, ticks=None):
    """Dies on `on_attempt`: it never finishes, and the slot it held must come
    back to the queue — that is the lease the course has to honour."""
    def fn(task, attempt):
        if attempt == on_attempt:
            return outcome("died", _ticks_of(task) if ticks is None else ticks,
                           "the worker went away")
        return outcome("ok", _ticks_of(task), "fine")
    return Worker(fn, label="dying")


def always(status, *, ticks=None):
    """Answers the same thing every time. `always("died")` is a pool that
    cannot make progress, and a queue that must notice rather than spin."""
    def fn(task, attempt):
        cost = _ticks_of(task) if ticks is None else ticks
        return outcome(status, cost, "always %s" % status)
    return Worker(fn, label="always_%s" % status)


def scripted(plan, *, ticks=None):
    """A worker whose attempt 1, 2, ... are `plan` — `scripted(["died", "ok"])`
    dies once and then succeeds; a plan that runs out repeats its last entry."""
    steps = tuple(plan)
    if not steps:
        raise QueueError("scripted() needs at least one status")
    for status in steps:
        if status not in OUTCOMES:
            raise QueueError("scripted(%r): %r is not one of %r"
                             % (plan, status, OUTCOMES))

    def fn(task, attempt):
        status = steps[min(attempt, len(steps)) - 1]
        cost = _ticks_of(task) if ticks is None else ticks
        return outcome(status, cost, "attempt %d: %s" % (attempt, status))
    return Worker(fn, label="scripted")


def bad_shape(shape="string"):
    """A worker that reports something that is not an outcome at all, so the
    queue has to refuse it instead of filing it as a success."""
    shapes = {
        "string": lambda task, attempt: "ok",
        "no_ticks": lambda task, attempt: {"status": "ok"},
        "bad_status": lambda task, attempt: {"status": "fine", "ticks": 1},
        "negative": lambda task, attempt: {"status": "ok", "ticks": -1},
    }
    if shape not in shapes:
        raise QueueError("bad_shape(%r): want one of %r" % (shape, tuple(shapes)))
    return Worker(shapes[shape], label="bad_shape_%s" % shape)


def catalogue(*ids, **overrides):
    """The raw catalogue entries for `ids` as task specs — `catalogue("render",
    "index")` is the usual fixture for a whole run."""
    return [make_task(task_id, **overrides) for task_id in ids]
