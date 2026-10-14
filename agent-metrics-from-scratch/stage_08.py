"""Agent Metrics From Scratch — stage 8: The window is the decision.

A metric is not a measurement; it is a *fold over a window*, and the window is the
decision. Stage 2 gave the one window and stage 3 gave the gauge inside it; this
stage is about the *set* of windows, because a dashboard is a row of numbers and
each number is a fold over a window somebody chose. Two sets of windows are worth
distinguishing and the difference is not decoration. A **tumbling** set (`step` is
`None`, or the width) cuts the interval into windows that do not overlap: window
*i* is `[start + i*step, start + i*step + width)`, the first begins exactly at
`start`, and the last is truncated at `end`, so the windows are a **partition** of
`[start, end)` — every event in the interval is in exactly one window, and that is
what makes two folds comparable, summable, and honest about the run they cover. A
**sliding** set (`step < width`) overlaps its windows on purpose: a rolling
percentile needs the overlap, and the overlap is exactly why the folds may not be
summed — the events in it are counted twice.

`fold` is one window's numbers, and it is a function of the window rather than of
the run: the events in `[start, end)` in the order they happened, how many there
are, the ticks of service they spent, and how deep the queue got while the window
was open. `partition` folds every window in the order they happen. `covers`
answers the one question the shape of a fold cannot: does this set of windows hold
every event of its interval exactly once? It answers `False` rather than guessing,
because a set with a hole and a set with an overlap are both *covering* a run in
the loose sense and neither is partitioning it.

The window is stage 2's object and the gauge is stage 3's, and this file keeps its
own copy of both rules rather than importing a sibling: an event at
`tick == start` is in and an event at `tick == end` is out, a window with no width
is a point and a point has no fold, and a task is in flight from the tick it is
admitted to the tick it leaves for good. A `retried` event is not a departure —
the task that comes back is still there, which is the whole reason a retry shows
up in a depth at all — and a `dropped` event is a departure only for a task that
was in the queue to be dropped: the one the fleet refused at the door was never in
flight. Getting that wrong is how a run whose tasks were retried reports a queue
of minus one.

DESIGN DECISION — why is the *set* of windows this stage's subject, when stage 2
already has one window and stage 3 already has the gauge inside it?
    Because one window has no properties worth checking and a set has several that
    are the difference between a dashboard and a pile of numbers. A tumbling set
    partitions its interval, so the folds' events are the interval's events once
    each, their counts add up, and their totals add up: a number computed window by
    window is the same number computed over the interval, which is the whole reason
    anybody believes a time series. A sliding set has none of those properties, and
    a reader who sums a rolling series anyway gets a number that is roughly the run
    multiplied by how much the windows overlap — a wrong answer that looks like a
    right one. So the set is where the course decides, and `covers` is where the
    decision is written down as a question with a yes or a no.

DESIGN DECISION — why is the last window truncated at `end` instead of refused or
padded?
    Because the interval is the promise and the width is not. A caller who asks for
    `[0, 50)` in windows of `20` has asked a complete question, and the answer is
    three windows — the third of them ten ticks wide — and refusing it would make
    every caller round their own intervals to the width, which is how a dashboard
    ends up quietly dropping the tail of every run. Padding the last window past
    `end` is worse: the window would then hold events the caller excluded, and a
    fold over it would answer a question about an interval nobody chose. So the
    width is what the set was built with, the interval is what the window is, and a
    spec carries both: `width` and `step` say how the set was cut, `start` and `end`
    say what the window holds.

DESIGN DECISION — why does a fold carry the window's *events*, and why is `total`
zero in a window where nothing finished?
    Because a fold that carried only a count could not be checked for the property
    that makes it a fold. `partition`'s folds have to be walked to see that an event
    is in exactly one of them — that is `covers`, and it is why the events ride
    along in the fold rather than being counted and thrown away. `total` is the one
    counter a window of these events holds: the ticks of service its events
    measured, and zero when none of them measured any. That zero is not stage 2's
    refusal of a total nobody measured: the question "what did service cost in this
    window" has an answer here — nothing finished in it — and a window is asked
    about whatever it contains, including an empty one. Stage 2 refuses a field the
    *run* never wrote; a window that finished nothing has still spent no service.

DESIGN DECISION — why is the depth computed from every event and not from the
window's own events?
    Because a queue is not inside its window. The depth at a tick is what the run
    had in flight at that instant, and a window that begins at tick 20 is looking at
    a queue that tick 0 filled: an admission from before the window is still sitting
    in it. So `fold` takes the run and the spec, filters the run for the window's
    *events*, and walks the whole run for the window's *depth* — which is why the
    signature takes the events first. A fold built from the window's events alone
    would report a queue that drains to nothing the moment the window ends, and a
    peak that is a property of the window rather than of the fleet.

DESIGN DECISION — why is a step past the width a refusal, while an overlapping set
is answered `False` instead of refused?
    Because the two are different kinds of mistake. A step wider than the width is a
    caller who has asked `windows` for a set that cannot cover its own interval: it
    leaves a hole, and the hole is events nobody folds, so the *builder* refuses
    before the set exists and names the step and the width. A sliding set that a
    caller built on purpose is a legitimate question — a rolling window is a real
    metric — so nothing refuses, and `covers` answers `False`: the set does not
    partition its interval, the events in the overlap are in two folds, and summing
    the folds would count them twice. A refusal is for a caller who made a mistake;
    `False` is for a question whose answer is no.

TODO: implement `windows`, `fold`, `partition` and `covers`.
"""

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

    Returns a tuple of specs, each a fresh mapping over `start`, `end`, `width`
    and `step` in that order — the interval the window names and the two numbers
    the set was built with, so a spec is a `telemetry.WINDOWS` fixture and a world
    fixture builds its own set.

    Refuses `width <= 0`, `step <= 0`, `step > width` ("a step past the width
    leaves a hole, and a hole is an event nobody folds") and `end <= start` ("a
    window with no width is a point, and a point has no fold"), each naming what
    was wrong with it, and a `start`/`end` that is not a non-negative int.
    """
    raise NotImplementedError("stage 8: implement windows()")


def fold(events, spec):
    """One window's numbers, over exactly `FOLD_KEYS` and nothing else.

    `events` is the run (or any sequence of events) and `spec` names the window
    by its interval; anything else the spec carries is what the set remembers
    about itself. The fold's `events` are the ones in `[start, end)`, in their
    original order — *a fold never sorts*, so folding a window is a read of the
    run and not a rewrite of it. `count` is how many of them there are, `total`
    the ticks of service they spent, and `peak_depth` the deepest the queue got
    inside the window, as stage 3's `{"tick", "depth"}` with the *first* tick that
    attains it — the depth is counted over the whole run, because a queue that
    tick 0 filled is still there when the window opens at 20.

    Refuses a spec that is not a mapping over `start` and `end`, a spec with no
    width, an `events` that is not a sequence, an event that is not a mapping or
    that has no tick to place in a window, a service that is not a count, and a
    depth that would go negative — a negative queue is a broken fixture, not a
    metric, and this stage refuses it rather than reporting it.
    """
    raise NotImplementedError("stage 8: implement fold()")


def partition(events, windows_):
    """One fold per window, in the order the windows happen.

    `windows_` is a non-empty sequence of specs in the order their windows start,
    which is the order a tumbling set comes back from `windows` in. For a tumbling
    set the folds' events are a partition of the events in the interval the set
    names — every one of them in exactly one fold — and that is the property that
    makes a fold over a window a contribution rather than a whole.

    Refuses a window set that is not a sequence, one with no windows in it, and
    one whose windows do not ascend, each naming the offender.
    """
    raise NotImplementedError("stage 8: implement partition()")


def covers(events, windows_):
    """Whether a window set partitions the interval it names: exactly once.

    Walks the folds and counts, for every event of `[the first window's start, the
    last window's end)`, how many folds hold it. `True` means the set is a
    partition and the folds may be summed; `False` means it is not — the events in
    a sliding set's overlap are in two folds, and a set with a step past its width
    leaves events in none. It answers `False` rather than guessing, and refuses
    only a window set that is not a window set at all.
    """
    raise NotImplementedError("stage 8: implement covers()")
