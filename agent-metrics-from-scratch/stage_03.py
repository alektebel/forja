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

DESIGN DECISION — why is the depth *derived* from two counters instead of being
written down by the fleet as one more event?
    Because a gauge and a counter are different kinds of number and a dashboard
    that confuses them is wrong in a way no reader can see. An admitted event is
    a fact that happened once and a finished event is another; the depth is a
    fact about what those two add up to *at an instant*, and if the fleet wrote it
    down as its own event then two folds of the same run could disagree about
    every tick between them and there would be no way to say which was right.
    Deriving it keeps the two counters as the only things counted, which is also
    what makes a gauge foldable over a window at all — a window's depth is the
    counters at its edges, not a sum of the depths inside it.

DESIGN DECISION — why is a `retried` event an arrival when a failed attempt's
`finished` event was a departure at the same tick?
    Because the retry is what makes the depth mean "in flight" rather than "in the
    worker". An attempt that fails leaves the worker — that is a departure, and
    the `finished` event says so — and the task goes straight back to the back of
    the queue, which is the `retried` event. Read the two together and the task
    never left the queue; read only the finish and every retried task sinks the
    depth by one, which is exactly the fixture the negative-depth refusal is
    about. A `started` event is the third possibility and moves nothing: a task
    that is running has been admitted and has not finished.

DESIGN DECISION — why is a `dropped` event of a task that was never admitted not
a departure either?
    Because there was nothing for it to leave. The fleet writes a `dropped` event
    in two situations that look alike and are not: a task that arrived at a queue
    that was full never entered it — no `admitted` event precedes it — and a task
    that was admitted and then abandoned never ran; only the second is a task
    leaving the queue. Counting the first as a departure would make the fleet's
    own default run's depth go negative on a fixture nobody could repair, whereas
    the refusal is reserved for the departure that has no arrival behind it at
    all.

DESIGN DECISION — why refuse a depth that would go negative instead of reporting
a `-1` and letting the caller decide?
    Because a negative queue is not a measurement with a bad sign, it is evidence
    that the fixture is broken: a task finished twice against one admission means
    the `retried` event between its attempts was lost, and every number a fold
    built on that series is a number about nothing. A metric layer that prints
    `-1` teaches its reader to expect it, and the refusal — which names the task
    that left twice and the tick it did so at — is repairable in a way a series
    with a `-1` in it never is.

DESIGN DECISION — why does `peak_depth` name the *first* tick that attains the
maximum, and why may a gauge be averaged over an interval but never summed?
    Because both answers are the same answer, seen twice. A peak is a fact about
    when the queue was that deep, not how long it stayed: the first tick that
    attains the maximum is the earliest instant the number is true, and taking the
    last one would report a peak tick that only exists because of a plateau. The
    mean over an interval, on the other hand, is the gauge's one legitimate scalar
    — the sum over the number of ticks, as an exact reduced pair — and the sum
    itself is not: its unit is task-ticks, and a dashboard that offers one is
    offering a number nobody can act on.

TODO: implement `depth_at`, `depth_series`, `peak_depth` and `average_depth`.
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
    raise NotImplementedError("stage 3: implement depth_at()")


def depth_series(events, start, end):
    """One number per tick of `[start, end)`: the gauge at each tick, in order.

    The interval is half-open and carries the depth the ticks before it left
    behind, because a gauge at 10 means nothing without the nine ticks before
    it. A series with no width is refused — a point has no fold — and so is a
    fixture whose depth would go negative: the refusal names the task that left
    twice rather than reporting a queue of minus one.
    """
    raise NotImplementedError("stage 3: implement depth_series()")


def peak_depth(events, start, end):
    """The first tick that attains the maximum depth of `[start, end)`.

    A mapping over exactly `("tick", "depth")`, in that order. The tie rule is
    frozen: the *first* tick that attains the maximum wins, because a peak is
    when the queue was that deep and not the last time it happened to be.
    """
    raise NotImplementedError("stage 3: implement peak_depth()")


def average_depth(events, start, end):
    """The gauge over `[start, end)` as a mean: an exact reduced pair.

    This is the one place a gauge may be averaged — the sum of the series over
    the number of ticks it has, reduced by their gcd. It is a pair and not a
    scalar because `(5, 2)` is the answer and `2` is not: a depth summed over
    time is a number in task-ticks, and this stage will not hand one back.
    """
    raise NotImplementedError("stage 3: implement average_depth()")
