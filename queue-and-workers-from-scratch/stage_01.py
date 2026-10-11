"""Queue & Workers From Scratch — stage 1: The task and the pool, and the typo
that runs as a default.

A queue is only as honest as the spec it was handed. This stage turns a job
file's mapping into a `Task` and a pool config's mapping into a `Pool`, and it
turns the two mistakes that are hardest to see — a misspelled field and a
number that is not a number — into a refusal with a name.

DESIGN DECISION — why is an unknown key refused instead of ignored?
    The tempting alternative is `mapping.get(key, default)`: one lookup, no
    guard. Its cost is the bug this stage exists for — `{"id": "train",
    "tickz": 30}` runs with the default 3 ticks, the run is green, and the only
    sign is a duration nobody measured. The refusal names the key and the keys
    that do exist, so the reader sees the spelling they meant.

DESIGN DECISION — why is a `bool` not a count?
    `isinstance(True, int)` is true, so the tempting alternative is to let the
    int guard pass it. Its cost is `priority: True` becoming priority 1 and
    `ticks: False` becoming a free task: a flag smuggled into a count changes
    the schedule and no assertion notices, because both are "ints".

DESIGN DECISION — why are the defaults materialised as the spec is built?
    The tempting alternative is to keep the mapping as written and let every
    consumer consult the defaults. Its cost is that "spelled" and "defaulted"
    become two shapes with one meaning, so the same task submitted from two job
    files takes two paths through the queue — and the run record differs.

DESIGN DECISION — why does the canonical text sort its keys and drop spaces?
    The tempting alternative is `json.dumps(spec)` and whatever order the
    caller wrote. Its cost is that the same spec in two spellings produces two
    texts, so two identical runs stop being byte-identical and a cache keyed on
    the text misses. `sort_keys=True, separators=(",", ":")` makes the text a
    function of the values alone.

DESIGN DECISION — why is `low_water <= high_water <= capacity` checked here?
    The tempting alternative is to check only `low_water < high_water` (or
    nothing, and trust the config). Its cost is a pool whose water marks point
    above its own capacity: the backpressure stage then either never refuses or
    refuses immediately, and the mistake surfaces one stage later as a policy
    that "does not work", far from the config that caused it.

TODO: implement `TASK_KEYS`, `POOL_KEYS`, `TASK_DEFAULTS`, `POOL_DEFAULTS`,
`Task`, `Pool`, `parse_task`, `parse_pool`, `parse_tasks`, `canonical_task`,
`canonical_pool`.
"""

from dataclasses import dataclass

#: What a task spec may say, in the order a reader meets them.
TASK_KEYS = ("id", "ticks", "priority", "tenant", "attempts")

#: What a pool spec may say.
POOL_KEYS = ("id", "max_concurrency", "capacity", "high_water", "low_water")

#: The values a task gets when it does not say.
TASK_DEFAULTS = {"ticks": 3, "priority": 5, "tenant": "batch", "attempts": 3}

#: The values a pool gets when it does not say.
POOL_DEFAULTS = {"max_concurrency": 1, "capacity": 4, "high_water": 3,
                 "low_water": 1}


@dataclass(frozen=True)
class Task:
    """One unit of work: what it is called, what it costs, what it is worth, who
    it is billed to, and how many attempts it gets."""

    id: str
    ticks: int
    priority: int
    tenant: str
    attempts: int


@dataclass(frozen=True)
class Pool:
    """One pool's limits: how many tasks run at once, how deep the queue may
    get, and the water marks a backpressure policy reads."""

    id: str
    max_concurrency: int
    capacity: int
    high_water: int
    low_water: int


def parse_task(mapping):
    """A task mapping into a `Task`, every default materialised."""
    raise NotImplementedError("stage 1: implement parse_task()")


def parse_pool(mapping):
    """A pool mapping into a `Pool`, every default materialised."""
    raise NotImplementedError("stage 1: implement parse_pool()")


def parse_tasks(sequence):
    """A sequence of task mappings into a tuple of `Task`s, ids distinct."""
    raise NotImplementedError("stage 1: implement parse_tasks()")


def canonical_task(task):
    """The one text of a task spec, defaults materialised."""
    raise NotImplementedError("stage 1: implement canonical_task()")


def canonical_pool(pool):
    """The one text of a pool spec, defaults materialised."""
    raise NotImplementedError("stage 1: implement canonical_pool()")
