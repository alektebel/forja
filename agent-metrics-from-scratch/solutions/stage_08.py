"""Agent Metrics From Scratch — stage 8: The window is the decision.

A metric is a fold over a window, and the window is the decision. This stage is
where a *set* of windows is built, and where the difference between a set that
partitions a run and one that merely covers it is decided. `windows` builds the
specs — tumbling when the step is the width, sliding when it is smaller — aligned
to `start`, and cuts the last one at `end` so no window runs past the interval
somebody chose. `fold` is one window's numbers, and it is a function of the
window: the events in `[start, end)` in the order they happened, how many there
are, the ticks of service they spent, and how deep the queue got inside the
window. `partition` folds them all in order; `covers` answers the question the
schema cannot — do those folds hold every event of the interval exactly once?

The window is stage 2's object and the gauge is stage 3's, and this file keeps
its own copy of both rules rather than importing a sibling: an event at
`tick == start` is in and an event at `tick == end` is out, a window with no
width is a point and a point has no fold, and a task is in flight from the tick
it is admitted to the tick it leaves for good. A `retried` event is not a
departure — the task that comes back is still there, which is the whole reason a
retry shows up in a depth at all — and a `dropped` event is a departure only for
a task that was in the queue to be dropped: the one the fleet refused at the door
was never in flight. Getting that wrong is how a run whose tasks were retried
reports a queue of minus one.
"""

from collections.abc import Mapping, Sequence

import telemetry

import stage_01

#: The keys of a fold, in the order `fold()` writes them: the window it folded,
#: the events it found (in the order they happened), how many that is, the ticks
#: of service they spent, and the deepest the queue got while the window was open.
FOLD_KEYS = ("start", "end", "events", "count", "total", "peak_depth")


class PartitionError(stage_01.TelemetryError):
    """A window set, a window spec or an event this stage refuses.

    The refusal names the offender — the width, the step, the tick, the spec's
    key, the index of the event — and, when the offender is within edit distance
    two of a key a spec may have, the key it probably meant.
    """


def windows(start, end, width, *, step=None):
    """The specs of a window set: aligned to `start`, and cut at `end`.

    Window *i* is `[start + i*step, start + i*step + width)`, so the first window
    begins exactly at `start` and the last one is truncated at `end` — no window
    ever runs past the interval. `step=None` (or a step equal to the width) is the
    tumbling set: the windows are a partition of `[start, end)`. A step smaller
    than the width is the sliding set: the windows overlap on purpose, and a fold
    over them may not be summed.

    Refuses `width <= 0`, `step <= 0`, `step > width` ("a step past the width
    leaves a hole, and a hole is an event nobody folds") and `end <= start`, each
    naming what was wrong with it, and a `start`/`end` that is not a
    non-negative int.
    """
    start = _count(start, "start")
    end = _count(end, "end")
    width = _count(width, "width")
    if step is None:
        step = width
    else:
        step = _count(step, "step")
    if end <= start:
        raise PartitionError("a window set with no width is a point, and a point "
                             "has no fold: %d to %d" % (start, end))
    if width <= 0:
        raise PartitionError("a width of %d builds no window: a window with no "
                             "width is a point, and a point has no fold" % (width,))
    if step <= 0:
        raise PartitionError("a step of %d never advances: every window of the "
                             "set would start at the same tick" % (step,))
    if step > width:
        raise PartitionError("a step past the width leaves a hole, and a hole is "
                             "an event nobody folds: step %d, width %d"
                             % (step, width))
    span = end - start
    how_many = (span + step - 1) // step
    built = []
    for index in range(how_many):
        left = start + index * step
        right = left + width
        if right > end:
            right = end
        built.append({"start": left, "end": right,
                      "width": width, "step": step})
    return tuple(built)


def fold(events, spec):
    """One window's numbers, over exactly `FOLD_KEYS` and nothing else.

    `events` is the run (or any sequence of events) and `spec` names the window;
    the fold's `events` are the ones in `[start, end)`, in their original order —
    a fold never sorts. `count` is how many there are, `total` the ticks of
    service they spent (an event whose kind carries no service spends none, and a
    window in which nothing finished spent zero service, which is a measurement
    and not a silence), and `peak_depth` is the deepest the queue got inside the
    window, as stage 3's `{"tick", "depth"}` with the *first* tick that attains
    it. It refuses a spec that is not a window, an `events` that is not a
    sequence, an event that is not a mapping or that has no tick, a service that
    is not a count, and a depth that would go negative — a negative queue is a
    broken fixture, not a metric.
    """
    events = _events(events, "fold")
    start, end = _bounds(spec)
    chosen = _events_in(events, start, end)
    total = 0
    for event in chosen:
        total += _service(event)
    return {"start": start, "end": end, "events": chosen, "count": len(chosen),
            "total": total, "peak_depth": _peak_depth(events, start, end)}


def partition(events, windows_):
    """One fold per window, in the order the windows happen.

    For a tumbling set the folds' events are a *partition* of the events in
    `[start, end)`: every one of them is in exactly one fold, which is what makes
    two overlapping windows agree on their overlap. For a sliding set they are
    not — the events in the overlap are deliberately in two folds — and that is
    what `covers` answers rather than this function summing them.
    """
    events = _events(events, "partition")
    given = _specs(windows_)
    folds = []
    for spec in given:
        folds.append(fold(events, spec))
    return tuple(folds)


def covers(events, windows_):
    """Whether a window set partitions the interval it names: exactly-once.

    Walks the folds and counts, for every event of `[first window's start, the
    last end)`, how many folds hold it: one, and the set covers its interval; two
    (a sliding set) and the events in the overlap would be counted twice if
    anybody summed the folds; none (a set with a hole) and an event nobody folds
    has gone missing. It answers False rather than guessing, and refuses only a
    window set that is not a window set at all.
    """
    events = _events(events, "covers")
    given = _specs(windows_)
    bounds = [_bounds(spec) for spec in given]
    left_edge = min(pair[0] for pair in bounds)
    right_edge = max(pair[1] for pair in bounds)
    counts = [0] * len(events)
    for spec in given:
        for index in _indices(events, spec):
            counts[index] += 1
    for index in _indices(events, {"start": left_edge, "end": right_edge}):
        if counts[index] != 1:
            return False
    return True


def _count(value, what):
    """A count a window's arithmetic needs: a non-negative int, refused by name."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise PartitionError("a window's %s must be an int, got %r (%s)"
                             % (what, value, type(value).__name__))
    if value < 0:
        raise PartitionError("a window's %s is negative: %d" % (what, value))
    return value


def _bounds(spec):
    """The half-open interval a spec names, or a refusal that names the part."""
    if not isinstance(spec, Mapping):
        raise PartitionError("a window spec is a mapping with 'start' and 'end', "
                             "got %r" % (type(spec).__name__,))
    bounds = []
    for key in ("start", "end"):
        if key not in spec:
            raise PartitionError("a window spec has no %r%s"
                                 % (key, telemetry._near(key, tuple(spec))))
        bounds.append(_count(spec[key], key))
    start, end = bounds
    if end <= start:
        raise PartitionError("a window with no width is a point, and a point has "
                             "no fold: %d to %d" % (start, end))
    return start, end


def _specs(windows_):
    """A window set: a non-empty sequence of specs, in the order they happen."""
    if isinstance(windows_, Mapping) or not isinstance(windows_, Sequence) \
            or isinstance(windows_, (str, bytes, bytearray)):
        raise PartitionError("a window set is a sequence of window specs, got %r"
                             % (type(windows_).__name__,))
    given = tuple(windows_)
    if not given:
        raise PartitionError("a window set with no windows in it has no interval "
                             "to partition")
    previous = None
    for index, spec in enumerate(given):
        start, _ = _bounds(spec)
        if previous is not None and start <= previous:
            raise PartitionError("window %d starts at %d, not after the window "
                                 "before it (%d): a window set is in the order "
                                 "its windows happen" % (index, start, previous))
        previous = start
    return given


def _events(events, what):
    """A sequence of events, refused when it is a shape no fold could walk."""
    if isinstance(events, Mapping) or not isinstance(events, Sequence) \
            or isinstance(events, (str, bytes, bytearray)):
        raise PartitionError("%s folds a sequence of events, got %r"
                             % (what, type(events).__name__))
    return events


def _tick_of(event, index):
    """The tick an event happened at, refused by its index when it has none."""
    if not isinstance(event, Mapping):
        raise PartitionError("event %d is not a mapping, got %r"
                             % (index, type(event).__name__))
    tick = event.get("tick", stage_01.ABSENT)
    if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
        raise PartitionError("event %d has no tick to place it in a window: %r"
                             % (index, tick))
    return tick


def _in_window(tick, start, end):
    """The boundary rule, written once: `tick == start` is in, `tick == end` out."""
    return start <= tick < end


def _indices(events, spec):
    """The indices of the events in a spec's window, in the order they happened."""
    start, end = _bounds(spec)
    found = []
    for index, event in enumerate(events):
        if _in_window(_tick_of(event, index), start, end):
            found.append(index)
    return found


def _events_in(events, start, end):
    """The events of `[start, end)`, in their original order: a fold never sorts."""
    return tuple(events[index] for index in _indices(events, {"start": start,
                                                              "end": end}))


def _service(event):
    """The service ticks an event carries, or 0 when its kind carries none."""
    value = event.get("service", stage_01.ABSENT)
    if value == stage_01.ABSENT:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PartitionError("a service must be a non-negative count, got %r"
                             % (value,))
    return value


def _deltas(events):
    """Each tick's net change to the number of tasks in flight.

    Read in two passes, because whether a finish or a drop is a departure is a
    question about the *other* events: a finish a retry follows is a task coming
    back, and a drop of a task nobody ever admitted is a task that was never in
    flight. A tick's events are added up before the tick is looked at, so a task
    admitted and finished at the same tick nets out to zero whatever order the
    two are written in — the kind precedence of the course is a rule about
    reading a tick, and this is the same rule written as a sum.
    """
    back = set()
    queued = set()
    for event in events:
        if event.get("kind") == "retried":
            back.add((event.get("task"), event.get("attempt")))
        elif event.get("kind") == "admitted":
            queued.add(event.get("task"))
    when = [_tick_of(event, index) for index, event in enumerate(events)]
    changes = {}
    for index, event in enumerate(events):
        step = _step(event, back, queued)
        if not step:
            continue
        changes[when[index]] = changes.get(when[index], 0) + step
    return changes


def _step(event, back, queued):
    """What one event does to the number of tasks in flight."""
    kind = event.get("kind")
    if kind == "admitted":
        return 1
    if kind == "finished":
        return 0 if (event.get("task"), event.get("attempt")) in back else -1
    if kind == "dropped":
        return -1 if event.get("task") in queued else 0
    return 0


def _peak_depth(events, start, end):
    """The first tick of `[start, end)` where the queue is deepest, and how deep."""
    changes = _deltas(events)
    depth = 0
    for when, step in changes.items():
        if when < start:
            depth += step
    best_tick, best = start, None
    for tick in range(start, end):
        depth += changes.get(tick, 0)
        if depth < 0:
            raise PartitionError("the queue is %d deep at tick %d: a negative "
                                 "depth is a broken fixture, not a metric"
                                 % (depth, tick))
        if best is None or depth > best:
            best, best_tick = depth, tick
    return {"tick": best_tick, "depth": best}
