"""Agent Metrics From Scratch — the provided world: the fleet and its events.

`fleet.py` is the fleet (J1's, byte-identical); this file is what the fleet
leaves behind and what it was promised. Nothing here folds, averages, prices or
windows anything for the student — every one of those is a stage — but
`record()` *does* run the fleet, deterministically, on `fleet.Clock`, and it
counts what it did as it goes. That count is `summary`, and it is the tie-breaker
every report in this course is decided against: the events are the world's
record of what happened, and the summary is the world's own count of the same
run, kept separately on purpose. A fold that silently loses an event disagrees
with it.

Everything is plain dicts in read-only mappings plus accessors that hand back
fresh mutable copies, so a check can bend a fixture without a type standing in
the way.
"""

import types
from collections.abc import Mapping, Sequence

import fleet

#: The keys of one telemetry event, in the order `line()` writes them. Every
#: field is always present: a field the event's kind does not carry is `ABSENT`.
EVENT_KEYS = ("tick", "task", "pool", "tenant", "kind", "attempt", "outcome",
              "wait", "service", "tokens_in", "tokens_out", "error")

#: The five kinds of fact the fleet records, in the order they may happen at a
#: single tick (a finish at tick t is a departure at tick t, so a task admitted
#: and finished at the same tick nets out to zero).
KINDS = ("admitted", "started", "finished", "retried", "dropped")

#: The keys whose value is a number rather than a name, so the writer's inverse
#: knows what to convert back and what to leave alone.
NUMERIC_KEYS = ("tick", "attempt", "wait", "service", "tokens_in", "tokens_out")

#: What an absent field is spelled. Never a number, never an empty string: a
#: field nobody measured is a position in the line and not a silence.
ABSENT = "-"

#: Every reason an event may carry, and the whole of it. A free-text reason would
#: put a space inside a field of a line that has no quoting, so the fleet writes
#: a token and the reader may assume one — the same rule every audit in this
#: repository follows, and the reason a line can be split on a single space.
ERRORS = ("failed", "died", "queue_full", "out_of_time")

#: The six keys of a trace — E1's `agent-harness-from-scratch` stage 8, the same
#: names, because the trace is the input this course folds and the two courses
#: must not disagree about what a trace is. A trace is per call; an event is a
#: fact about the fleet; keeping them apart is the first lesson.
TRACE_KEYS = ("turn", "kind", "tokens", "duration_ms", "tool", "ok")

#: The keys of the fleet's own count of a run — what it did, never derived from
#: the lines it wrote. `first_tick` and `last_tick` bound the run.
SUMMARY_KEYS = ("tasks", "attempts", "admissions", "failures", "died", "retries",
                "dropped", "tokens_in", "tokens_out", "micros", "first_tick",
                "last_tick")

#: What one call to a task costs, in tokens. A property of the task.
TOKENS = types.MappingProxyType({
    "render": {"in": 120, "out": 40},
    "index": {"in": 300, "out": 90},
    "notify": {"in": 20, "out": 8},
    "train": {"in": 900, "out": 260},
    "audit": {"in": 200, "out": 60},
    "purge": {"in": 40, "out": 12},
    "digest": {"in": 160, "out": 55},
    "publish": {"in": 80, "out": 30},
})

#: What a token costs, in micros, per pool — a property of the pool, because the
#: pool is what ran the task on a model.
PRICES = types.MappingProxyType({
    "small": {"in": 2, "out": 12},
    "narrow": {"in": 5, "out": 30},
    "wide": {"in": 10, "out": 60},
})

#: The aggregation fixtures: a half-open interval, a width and a step.
WINDOWS = types.MappingProxyType({
    "minute": {"start": 0, "end": 120, "width": 20, "step": 20},
    "rolling": {"start": 0, "end": 120, "width": 40, "step": 20},
})

#: The promises. A target and a budget are both in the metric's own unit — ticks
#: for a quantile of latency, micros for a cost, basis points for a rate — because
#: a budget in a different unit from the target is a budget nobody can spend.
SLOS = types.MappingProxyType({
    "latency_p95": {"metric": "p95", "target": 6, "window": "minute",
                    "budget": 12},
    "failure_rate": {"metric": "failure_bp", "target": 250, "window": "minute",
                     "budget": 200},
})

#: The worker plans a caller may name. Each entry is a factory: the run builds a
#: fresh `fleet.Worker` every time, so nothing at all is shared between two runs.
#: `mixed` fails its first attempt and succeeds on the second — one retry per
#: task, which is what makes the default run worth looking at — and `sickly` does
#: the same while *dying*, which is a different event: a death releases the slot
#: and the task that comes back is the same task.
WORKERS = types.MappingProxyType({
    "reliable": fleet.reliable,
    "sluggish": fleet.sluggish,
    "flaky": lambda: fleet.flaky(failures=1),
    "crasher": fleet.crasher,
    "dying": fleet.dying,
    "mixed": lambda: fleet.scripted(("failed", "ok")),
    "sickly": lambda: fleet.scripted(("died", "ok")),
})

#: The default workload: which tasks arrive, one per tick, in this order. Seven
#: of `fleet.TASKS`, more than the default pool's capacity, so a run has a queue
#: in it, a wait worth measuring, and a refusal worth counting.
DEFAULT_WORKLOAD = ("render", "notify", "index", "audit", "purge", "publish",
                    "digest")

#: How many attempts one task is allowed before its last outcome stands. The
#: fleet's own policy, not the student's.
MAX_ATTEMPTS = 3

#: How long a failed task waits, in ticks, before it may be queued again. A
#: retry is not free and it is not instant: the ticks between a failure and the
#: next attempt are time the task spent in the system and in neither attempt, and
#: an event stream that re-queued at the failing tick would make that interval
#: zero for every run the world can produce — a word in this course's vocabulary
#: (stage 5's gap, stage 9's `in_flight`) that no fixture could ever reach.
RETRY_BACKOFF = 1

#: The distance within which one name earns a suggestion for another.
_NEAR = 2


class EventError(ValueError):
    """An event, a fixture or an override this world refuses."""


def _levenshtein(one, other):
    """The edit distance between two names, the plain two-row way."""
    if one == other:
        return 0
    if not one:
        return len(other)
    if not other:
        return len(one)
    previous = list(range(len(other) + 1))
    for i, left in enumerate(one, start=1):
        current = [i]
        for j, right in enumerate(other, start=1):
            current.append(min(previous[j] + 1,
                               current[j - 1] + 1,
                               previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def _near(name, names):
    """The nearest name within `_NEAR`, or an empty string.

    A refusal that names the offender and the name it probably meant is worth
    two refusals that only do the first — this is every course's rule, and the
    world keeps its own copy so a stage need not write a second one.
    """
    if not isinstance(name, str):
        return ""
    best, distance = "", _NEAR + 1
    for candidate in names:
        gap = _levenshtein(name, candidate)
        if gap < distance:
            best, distance = candidate, gap
    if distance > _NEAR:
        return ""
    return " (did you mean %r?)" % (best,)


def _pick(table, name, what):
    """A fixture out of a read-only table, refused by name when it is not one."""
    if not isinstance(name, str):
        raise EventError("a %s must be a str, got %r" % (what, type(name).__name__))
    if name not in table:
        raise EventError("%r is not a %s this world has%s"
                         % (name, what, _near(name, tuple(table))))
    return dict(table[name])


def event(**fields):
    """A fresh, mutable event record: every key, in `EVENT_KEYS` order.

    Fields the caller does not give are `ABSENT`, which is what an event the
    fleet has not finished writing looks like. Nothing here validates — that is
    stage 1's job, and a world that validated for the student would be a world
    that did the stage.
    """
    unknown = [key for key in fields if key not in EVENT_KEYS]
    if unknown:
        raise EventError("an event has no field %r%s"
                         % (unknown[0], _near(unknown[0], EVENT_KEYS)))
    record = dict.fromkeys(EVENT_KEYS, ABSENT)
    record.update(fields)
    return record


def line(record):
    """The world's own writer: one event, one line, fields in `EVENT_KEYS` order.

    The inverse of stage 1's reader, and written here so a student's reader can
    be tested against the bytes the world actually produced.
    """
    if not isinstance(record, Mapping):
        raise EventError("an event must be a mapping, got %r"
                         % (type(record).__name__,))
    missing = [key for key in EVENT_KEYS if key not in record]
    if missing:
        raise EventError("an event is missing %r" % (missing[0],))
    extra = [key for key in record if key not in EVENT_KEYS]
    if extra:
        raise EventError("an event has no field %r%s"
                         % (extra[0], _near(extra[0], EVENT_KEYS)))
    return " ".join("%s=%s" % (key, record[key]) for key in EVENT_KEYS)


def trace(**fields):
    """A fresh trace of the six keys E1's harness writes. Absent means `""`."""
    unknown = [key for key in fields if key not in TRACE_KEYS]
    if unknown:
        raise EventError("a trace has no key %r%s"
                         % (unknown[0], _near(unknown[0], TRACE_KEYS)))
    record = dict.fromkeys(TRACE_KEYS, "")
    record.update(fields)
    return record


def summary(**fields):
    """A fresh copy of the fleet's own count. Every key, in `SUMMARY_KEYS` order."""
    unknown = [key for key in fields if key not in SUMMARY_KEYS]
    if unknown:
        raise EventError("a summary has no key %r%s"
                         % (unknown[0], _near(unknown[0], SUMMARY_KEYS)))
    record = dict.fromkeys(SUMMARY_KEYS, 0)
    record.update(fields)
    return record


def price(pool):
    """The pool's price per token, in micros."""
    return _pick(PRICES, pool, "pool")


def tokens(task):
    """What one call to the task costs, in tokens."""
    return _pick(TOKENS, task, "task")


def window(name):
    """A window fixture: `{"start", "end", "width", "step"}`."""
    return _pick(WINDOWS, name, "window")


def slo(name):
    """An SLO fixture: `{"metric", "target", "window", "budget"}`."""
    return _pick(SLOS, name, "objective")


def worker_plan(name):
    """A fresh worker built from one of `WORKERS`."""
    if not isinstance(name, str) or name not in WORKERS:
        raise EventError("%r is not a worker this world has%s"
                         % (name, _near(name, tuple(WORKERS))))
    return WORKERS[name]()


def read(text):
    """The world's own lines, read back as records.

    Returns `{"events", "text"}` — and deliberately **not** a summary: the
    fleet's own count is not in the lines, which is the whole reason it can be
    used to check a fold that was.
    """
    if isinstance(text, str):
        lines = (text,)
    elif isinstance(text, Sequence) and not isinstance(text, (bytes, bytearray)):
        lines = tuple(text)
    else:
        raise EventError("read takes a line or a sequence of lines, got %r"
                         % (type(text).__name__,))
    events = []
    for index, raw in enumerate(lines):
        if not isinstance(raw, str):
            raise EventError("line %d is not a str, got %r"
                             % (index, type(raw).__name__))
        fields = {}
        for position, chunk in enumerate(raw.split(" ")):
            if "=" not in chunk:
                raise EventError("line %d field %d is not key=value: %r"
                                 % (index, position, chunk))
            key, _, value = chunk.partition("=")
            if key not in EVENT_KEYS:
                raise EventError("line %d has no field %r%s"
                                 % (index, key, _near(key, EVENT_KEYS)))
            fields[position] = (key, value)
        order = tuple(key for _, (key, _) in sorted(fields.items()))
        if order != EVENT_KEYS:
            raise EventError("line %d is not in %s order: %r"
                             % (index, ", ".join(EVENT_KEYS), raw))
        record = {key: value for _, (key, value) in sorted(fields.items())}
        for key in NUMERIC_KEYS:
            record[key] = _as_int(record[key], index, key)
        events.append(record)
    return {"events": tuple(events), "text": tuple(lines)}


def _as_int(text, index, key):
    """The int a written field holds, refused by line and kind."""
    if text == ABSENT:
        return ABSENT
    body = text[1:] if text.startswith("-") else text
    if not body.isdigit():
        raise EventError("line %d: %s=%r is not a number" % (index, key, text))
    return int(text)


def record(pool="small", tasks=None, *, worker="mixed", max_ticks=60):
    """Run the fleet and write down what happened.

    Deterministic: one task arrives per tick (in `DEFAULT_WORKLOAD` order), the
    pool's concurrency decides what may run, the named worker plan decides each
    attempt's outcome, and a task that fails is retried up to `MAX_ATTEMPTS`.
    Returns the lines, the same events as records, the fleet's **own** count of
    the run, the traces of the tasks that finished, and the tick it stopped at.
    """
    if not isinstance(max_ticks, int) or isinstance(max_ticks, bool) or max_ticks < 1:
        raise EventError("max_ticks must be a positive int, got %r" % (max_ticks,))
    _pick(PRICES, pool, "pool")           # a pool with no price named is refused
    spec = fleet.make_pool(pool)
    cast = worker_plan(worker)
    workload = tuple(DEFAULT_WORKLOAD if tasks is None else tasks)
    for task_id in workload:
        if task_id not in fleet.TASKS:
            raise EventError("%r is not a task this fleet has%s"
                             % (task_id, _near(task_id, tuple(fleet.TASKS))))
    clock = fleet.Clock()
    out = []
    counts = dict.fromkeys(SUMMARY_KEYS, 0)
    traces = {}
    waiting = []          # [[task, attempt, queued_at], ...] FIFO
    running = []          # [[task, attempt, started_at, ends_at], ...]
    arrivals = list(workload)

    def emit(**fields):
        fresh = event(**fields)
        out.append(fresh)
        counts["last_tick"] = fresh["tick"]
        return fresh

    while clock.now() < max_ticks:
        now = clock.now()
        # 1. arrivals, one per tick, while the run has tasks to admit.
        if arrivals:
            task_id = arrivals.pop(0)
            if len(waiting) >= spec.capacity:
                emit(tick=now, task=task_id, pool=spec.id,
                     tenant=fleet.make_task(task_id).tenant, kind="dropped",
                     attempt=1, error="queue_full")
                counts["dropped"] += 1
            else:
                emit(tick=now, task=task_id, pool=spec.id,
                     tenant=fleet.make_task(task_id).tenant, kind="admitted",
                     attempt=1)
                counts["tasks"] += 1
                counts["admissions"] += 1
                if counts["admissions"] == 1:
                    counts["first_tick"] = now
                waiting.append([task_id, 1, now])
        # 2. starts, up to the pool's concurrency: the first *ready* entry in
        #    arrival order, so a task in its retry backoff is not yet queueable
        #    (and the wait it is charged is the time since it became queueable).
        while len(running) < spec.max_concurrency:
            position = next((index for index, entry in enumerate(waiting)
                             if entry[2] <= now), None)
            if position is None:
                break
            task_id, attempt, queued_at = waiting.pop(position)
            task = fleet.make_task(task_id)
            answer = cast(task, attempt=attempt)
            ticks = answer.get("ticks", task.ticks)
            emit(tick=now, task=task_id, pool=spec.id, tenant=task.tenant,
                 kind="started", attempt=attempt, wait=now - queued_at)
            running.append([task_id, attempt, now, now + ticks, answer])
        # 3. finishes at this tick, in start order.
        finished_now = [entry for entry in running if entry[3] <= now]
        for task_id, attempt, started_at, ends_at, answer in finished_now:
            running.remove([task_id, attempt, started_at, ends_at, answer])
            task = fleet.make_task(task_id)
            status = answer.get("status", "ok")
            tokens_of = TOKENS[task_id]
            emit(tick=now, task=task_id, pool=spec.id, tenant=task.tenant,
                 kind="finished", attempt=attempt, outcome=status,
                 service=ends_at - started_at, tokens_in=tokens_of["in"],
                 tokens_out=tokens_of["out"],
                 error=ABSENT if status == "ok" else status)
            counts["attempts"] += 1
            counts["tokens_in"] += tokens_of["in"]
            counts["tokens_out"] += tokens_of["out"]
            rate = PRICES[spec.id]
            counts["micros"] += (tokens_of["in"] * rate["in"]
                                 + tokens_of["out"] * rate["out"])
            if status != "ok":
                counts["failures"] += 1
                if status == "died":
                    counts["died"] += 1
                if attempt < MAX_ATTEMPTS:
                    emit(tick=now, task=task_id, pool=spec.id, tenant=task.tenant,
                         kind="retried", attempt=attempt, error=status)
                    counts["retries"] += 1
                    waiting.append([task_id, attempt + 1, now + RETRY_BACKOFF])
                # the last attempt's outcome stands: no further event.
            else:
                traces[task_id] = trace(
                    turn=attempt, kind=task_id,
                    tokens=tokens_of["in"] + tokens_of["out"],
                    duration_ms=(ends_at - started_at) * 10, tool=spec.id, ok=True)
        if not (arrivals or waiting or running):
            break
        clock.tick(1)
    # anything the run never got to do: the fleet's own drop, not a loss.
    for task_id, attempt, _ in waiting:
        emit(tick=clock.now(), task=task_id, pool=spec.id,
             tenant=fleet.make_task(task_id).tenant, kind="dropped",
             attempt=attempt, error="out_of_time")
        counts["dropped"] += 1
    return {"text": tuple(line(record_) for record_ in out),
            "events": tuple(out),
            "summary": summary(**counts),
            "traces": dict(traces),
            "clock": clock.now()}
