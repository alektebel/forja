"""Queue & Workers From Scratch — stage 1: the task and the pool, and the typo
that runs as a default.

The finished implementation. The reasoning — why a typo is refused instead of
defaulted, why a count is an `int` and a `bool` is not one, why the defaults are
materialised before the text is written, and why the canonical text sorts its
keys — lives in the DESIGN DECISION blocks of `stage_01.py`.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from fleet import QueueError

#: What a task spec may say, in the order a reader meets them. `attempts` is the
#: most attempts the task may cost; the queue spends the ticket's own count.
TASK_KEYS = ("id", "ticks", "priority", "tenant", "attempts")

#: What a pool spec may say. `capacity` bounds depth; the water marks are the
#: depths at which a policy starts and stops refusing.
POOL_KEYS = ("id", "max_concurrency", "capacity", "high_water", "low_water")

#: The values a task gets when it does not say: `fleet`'s three defaults plus the
#: attempt budget the queue will spend.
TASK_DEFAULTS = {"ticks": 3, "priority": 5, "tenant": "batch", "attempts": 3}

#: The values a pool gets when it does not say.
POOL_DEFAULTS = {"max_concurrency": 1, "capacity": 4, "high_water": 3,
                 "low_water": 1}


@dataclass(frozen=True)
class Task:
    """One unit of work: what it is called, what it costs, what it is worth, who
    it is billed to, and how many attempts it gets.

    Frozen, so a check can put it in a set and a queue cannot edit it in place;
    an edited ticket is the bug this type exists to make impossible.
    """

    id: str
    ticks: int = TASK_DEFAULTS["ticks"]
    priority: int = TASK_DEFAULTS["priority"]
    tenant: str = TASK_DEFAULTS["tenant"]
    attempts: int = TASK_DEFAULTS["attempts"]


@dataclass(frozen=True)
class Pool:
    """One pool's limits: how many tasks run at once, how deep the queue may
    get, and the water marks a backpressure policy reads."""

    id: str
    max_concurrency: int = POOL_DEFAULTS["max_concurrency"]
    capacity: int = POOL_DEFAULTS["capacity"]
    high_water: int = POOL_DEFAULTS["high_water"]
    low_water: int = POOL_DEFAULTS["low_water"]


def _require_mapping(source, what):
    """A spec is a mapping; a list, a string or a `Task` is not a spec."""
    if not isinstance(source, Mapping):
        raise QueueError("%s must be a mapping, got %r"
                         % (what, type(source).__name__))
    return source


def _reject_unknown_keys(mapping, keys, what):
    """A key the spec does not have is a typo, and a typo is not a default.

    The refusal names both the offending key and the keys that do exist, so the
    reader can see which spelling was meant.
    """
    for key in mapping:
        if key not in keys:
            raise QueueError("%s has no key %r; the keys are %r"
                             % (what, key, keys))
    return mapping


def _require_id(mapping, what):
    """The id: present, a `str`, and not blank."""
    if "id" not in mapping:
        raise QueueError("%s must have an id" % (what,))
    value = mapping["id"]
    if not isinstance(value, str):
        raise QueueError("%s id must be a str, got %r" % (what, value))
    if not value.strip():
        raise QueueError("%s id must not be empty, got %r" % (what, value))
    return value


def _require_int(value, what, *, minimum=0):
    """A count is a real `int` and at least `minimum`.

    `bool` is refused although `isinstance(True, int)` is true: `True` is not a
    count, and letting it through would turn a flag into the number 1.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise QueueError("%s must be an int, got %r" % (what, value))
    if value < minimum:
        raise QueueError("%s must be >= %d, got %r" % (what, minimum, value))
    return value


def _require_str(value, what):
    """A name is a `str`; `None` and `5` are not names."""
    if not isinstance(value, str):
        raise QueueError("%s must be a str, got %r" % (what, value))
    return value


def _value(mapping, key, defaults):
    """The value the spec spells, or the default materialised in its place."""
    return mapping[key] if key in mapping else defaults[key]


def _canonical(values):
    """One text per spec: keys sorted, no separators, no float, no spelling."""
    return json.dumps(values, sort_keys=True, separators=(",", ":"))


def _fields(source, keys, defaults):
    """A spec's public fields, in the frozen key order, defaulted when the bag
    (`fleet.TaskSpec` has no `attempts`) does not carry the key."""
    return {key: getattr(source, key, defaults.get(key)) for key in keys}


def parse_task(mapping):
    """A task mapping into a `Task`, every default materialised.

    A missing field is not an error — it is the default — but an *unknown* field
    is: `{"id": "x", "tickz": 1}` is a typo, and a typo silently defaulted is a
    task that runs with the wrong cost and nobody notices.
    """
    mapping = _reject_unknown_keys(_require_mapping(mapping, "a task"), TASK_KEYS,
                                   "a task")
    task_id = _require_id(mapping, "a task")
    ticks = _require_int(_value(mapping, "ticks", TASK_DEFAULTS), "ticks")
    priority = _require_int(_value(mapping, "priority", TASK_DEFAULTS), "priority")
    attempts = _require_int(_value(mapping, "attempts", TASK_DEFAULTS), "attempts")
    tenant = _require_str(_value(mapping, "tenant", TASK_DEFAULTS), "tenant")
    return Task(id=task_id, ticks=ticks, priority=priority, tenant=tenant,
                attempts=attempts)


def parse_pool(mapping):
    """A pool mapping into a `Pool`, every default materialised.

    The water marks are checked as a chain — `low_water <= high_water <=
    capacity` — because a policy that reads them cannot tell "not yet" from
    "never" if the marks are out of order.
    """
    mapping = _reject_unknown_keys(_require_mapping(mapping, "a pool"), POOL_KEYS,
                                   "a pool")
    pool_id = _require_id(mapping, "a pool")
    max_concurrency = _require_int(
        _value(mapping, "max_concurrency", POOL_DEFAULTS), "max_concurrency",
        minimum=1)
    capacity = _require_int(_value(mapping, "capacity", POOL_DEFAULTS), "capacity")
    high_water = _require_int(_value(mapping, "high_water", POOL_DEFAULTS),
                              "high_water")
    low_water = _require_int(_value(mapping, "low_water", POOL_DEFAULTS),
                             "low_water")
    if not low_water <= high_water <= capacity:
        raise QueueError(
            "a pool's water marks must satisfy low_water <= high_water <= "
            "capacity, got low_water=%r high_water=%r capacity=%r"
            % (low_water, high_water, capacity))
    return Pool(id=pool_id, max_concurrency=max_concurrency, capacity=capacity,
                high_water=high_water, low_water=low_water)


def parse_tasks(sequence):
    """A sequence of task mappings into a tuple of `Task`s, ids distinct.

    A duplicated id makes two different tasks indistinguishable in the queue's
    tables, so it is refused here, naming the id, rather than surfacing later as
    a task that vanished.
    """
    if isinstance(sequence, (str, bytes)) or not isinstance(sequence, Sequence):
        raise QueueError("a task list must be a sequence, got %r"
                         % (type(sequence).__name__,))
    seen = set()
    tasks = []
    for mapping in sequence:
        task = parse_task(mapping)
        if task.id in seen:
            raise QueueError("duplicate task id %r: the ids in a task list must "
                             "be distinct" % (task.id,))
        seen.add(task.id)
        tasks.append(task)
    return tuple(tasks)


def canonical_task(task):
    """The one text of a task spec, defaults materialised.

    Takes a `Task`, a `fleet.TaskSpec`, or a raw mapping (validated the same way
    `parse_task` validates it), so two spellings of one spec — keys in any order,
    fields spelled or left to the default — are one text.
    """
    if isinstance(task, Mapping):
        task = parse_task(task)
    return _canonical(_fields(task, TASK_KEYS, TASK_DEFAULTS))


def canonical_pool(pool):
    """The one text of a pool spec, defaults materialised."""
    if isinstance(pool, Mapping):
        pool = parse_pool(pool)
    return _canonical(_fields(pool, POOL_KEYS, POOL_DEFAULTS))
