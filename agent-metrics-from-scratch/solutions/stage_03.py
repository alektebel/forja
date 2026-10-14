"""Agent Metrics From Scratch — stage 3: Queue depth is a gauge, not a counter.

Stages 1 and 2 folded events into counters, and a counter is a thing you add up:
admissions over a window, tokens over a window, finishes over a window. A queue's
depth is the other kind of number. It has a value at an instant and no value at
all as a sum, because the sum of a depth over forty-eight ticks is a quantity in
task-ticks that nobody has ever put on a dashboard.

So the depth here is *derived*, not recorded. A task enters the queue at its
`admitted` event and leaves it at its `finished` or its `dropped` one, and the
gauge at an instant is the first count minus the second — two counters, and the
difference between them is a number neither of them is. The subtlety is which
event is which. A failed attempt's `finished` event *is* a departure: the attempt
left the worker and the task went back to the back of the queue, which the fleet
writes down as a `retried` event — and that retry is the arrival that puts it
back, which is the whole reason a retried task stays in the depth. A `started`
event moves nothing: a task that is running has not left the queue. And a
`dropped` task that was never admitted — a queue that was full when the task
arrived — never entered, so there was nothing for it to leave.

Two rules are frozen here. The events at one tick are read in stage 1's kind
order — admitted, started, finished, retried, dropped — so a task admitted and
finished at the same tick nets out to zero whichever order the caller wrote the
two events in. And the gauge is refused the moment it would go below zero: a
queue that is minus one deep is not a queue, it is a fixture whose retry event
was lost, and a refusal that names the task which left twice beats a series with
a `-1` in it.

    GaugeError      what a fixture whose depth would go negative raises
    depth_at        the gauge at one instant: the tasks in flight at `tick`
    depth_series    one number per tick of `[start, end)`, refusing a negative
    peak_depth      the *first* tick that attains the maximum, and the maximum
    average_depth   the interval's mean, as an exact reduced pair
"""

from stage_01 import TelemetryError

#: The order two events at a single tick happened in — stage 1's `KINDS`, here
#: because this is the stage that has to read them in that order: a task
#: admitted and finished at tick t nets out to zero, and it only does if the
#: admit is read before the finish.
_ORDER = ("admitted", "started", "finished", "retried", "dropped")


class GaugeError(TelemetryError):
    """A fixture whose depth this stage cannot read.

    The refusal names the task whose departure had nothing to depart from — a
    task the fleet finished twice, which is a fixture that lost a retry — and it
    is a `TelemetryError` like every other refusal in this course.
    """


def depth_at(events, tick):
    """The gauge at one instant: the tasks in flight at `tick`.

    The events at or before `tick` are walked in `_ORDER`'s order and the tasks
    in flight are counted, so the answer is `#(entered ≤ t) − #(left ≤ t)` — the
    two counters, and nothing else. A `tick` that is not a non-negative `int` is
    refused by name, and a fixture whose depth would go negative is refused with
    the task that left twice.
    """
    return _last(_walk(events, tick), tick)


def depth_series(events, start, end):
    """One number per tick of `[start, end)`: the gauge at each tick, in order.

    The interval is half-open and carries the depth the ticks before it left
    behind, because a gauge at 10 means nothing without the nine ticks before
    it. A series with no width is refused — a point has no fold — and so is a
    fixture whose depth would go negative: the refusal names the task that left
    twice rather than reporting a queue of minus one.
    """
    start, end = _interval(start, end)
    marks = _walk(events, end - 1)
    return tuple(_last(marks, tick) for tick in range(start, end))


def peak_depth(events, start, end):
    """The first tick that attains the maximum depth of `[start, end)`.

    A mapping over exactly `("tick", "depth")`, in that order. The tie rule is
    frozen: the *first* tick that attains the maximum wins, because a peak is
    when the queue was that deep and not the last time it happened to be.
    """
    depth = 0
    tick = start
    for offset, value in enumerate(depth_series(events, start, end)):
        if value > depth:
            depth = value
            tick = start + offset
    return {"tick": tick, "depth": depth}


def average_depth(events, start, end):
    """The gauge over `[start, end)` as a mean: an exact reduced pair.

    This is the one place a gauge may be averaged — the sum of the series over
    the number of ticks it has, reduced by their gcd. It is a pair and not a
    scalar because `(5, 2)` is the answer and `2` is not: a depth summed over
    time is a number in task-ticks, and this stage will not hand one back.
    """
    series = depth_series(events, start, end)
    total = sum(series)
    ticks = len(series)
    divisor = _gcd(total, ticks)
    return (total // divisor, ticks // divisor)


def _gcd(one, other):
    """The greatest common divisor of two non-negative ints, by Euclid.

    `math` is banned in this course for the reason the course exists: a check
    has to assert an exact pair, and a library that reduces it is a library that
    has decided the thing the exercise is about.
    """
    while other:
        one, other = other, one % other
    return one or 1


def _point(tick):
    """A tick, or a refusal that names the offender."""
    if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
        raise GaugeError("a tick must be a non-negative int, got %r" % (tick,))
    return tick


def _interval(start, end):
    """A half-open interval of ticks, or a refusal that names what is wrong."""
    _point(start)
    _point(end)
    if end <= start:
        raise GaugeError("a series needs at least one tick: [%r, %r) has no "
                         "width" % (start, end))
    return start, end


def _rank(event):
    """A sort key: the event's tick, then its kind's place in `_ORDER`.

    Reading a tick's events in this order is what makes a task admitted and
    finished at the same tick net out to zero — the admit is read before the
    finish, whatever order the caller wrote them in.
    """
    return (event["tick"], _ORDER.index(event["kind"]))


def _step(in_flight, event):
    """The tasks in flight after one event, or the refusal the event earns.

    `admitted` and `retried` put the task in flight; `started` moves nothing,
    because a task that is running has not left the queue; `finished` takes the
    task out and refuses when it was not there — a task finished twice is a
    fixture that lost its `retried` event; `dropped` takes it out when it is
    there and says nothing when it is not, because a task the queue refused
    never entered.
    """
    kind = event["kind"]
    task = event["task"]
    if kind == "admitted":
        in_flight.add(task)
    elif kind == "started":
        pass
    elif kind == "finished":
        if task not in in_flight:
            raise GaugeError("the fleet finished task %s twice at tick %d: a "
                             "depth below zero is a broken fixture, not a queue"
                             % (task, event["tick"]))
        in_flight.discard(task)
    elif kind == "retried":
        in_flight.add(task)
    elif kind == "dropped":
        in_flight.discard(task)
    return in_flight


def _walk(events, stop):
    """The depth at the end of every tick up to `stop`, in tick order.

    The events are ordered by `_rank` and folded one at a time, so a tick's
    events are all applied before its depth is written down. A tick with no
    event carries no entry: it is the tick before the next one that changed,
    and `_last` fills it in.
    """
    _point(stop)
    in_flight = set()
    marks = {}
    for event in sorted(events, key=_rank):
        if event["tick"] > stop:
            break
        _step(in_flight, event)
        marks[event["tick"]] = len(in_flight)
    return marks


def _last(marks, tick):
    """The depth a walk left behind at `tick`: the last tick with an event.

    `marks` is in tick order, so the answer is the value of the last entry whose
    tick is at or before `tick`, and zero when there is none — a queue that has
    not seen an event yet is empty, not unmeasured.
    """
    depth = 0
    for at, value in marks.items():
        if at > tick:
            break
        depth = value
    return depth
