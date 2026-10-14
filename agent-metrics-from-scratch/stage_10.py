"""Agent Metrics From Scratch — stage 10: The capstone: two windows, one answer.

Nine stages have each answered one question about a fold; this one spends the
answers. An objective names a metric, a target, a window fixture and a budget,
and the budget is walked over that fixture's windows: each window is folded, the
metric is read off the fold, and every window whose metric came out *above* the
target has spent its overshoot — `metric - target`, in the metric's own unit —
out of the budget. The burn is the sum of those overshoots and the alert fires
when that sum exceeds the allowance, which is the whole point of denominating a
target and a budget in the same unit: one very bad window is worse news than
three slightly bad ones, and a budget is what turns a single bad window into a
page.

`budget` measures, `burn` shares, `alert` decides, and `run` is the pipeline end
to end over `telemetry.record()`: record the fleet, fold the fixture's windows,
build the report against the fleet's own count, price the budget and decide the
alert. Two runs of the same fleet are equal field for field, and the run's report
equals the summary that fleet counted for itself on every key they share — the
course's claim in one line: the numbers on this dashboard are folds of events
that happened, over a window this SLO chose.

DESIGN DECISION — why is the burn the sum of the overshoots, and not the number
of windows that breached?
    Because the budget is denominated in the metric's own unit — ticks for a
    quantile of latency, micros for a spend, basis points for a rate — and a
    count of bad windows is denominated in nothing. A window that came in one
    tick over a p95 target and a window that came in forty ticks over it are one
    breach each and utterly different news; an operator whose page says "3
    windows breached" cannot tell which of the two days it was. The overshoot is
    the *size* of the promise that was broken, which is the only thing a budget
    in the promise's unit can measure.

DESIGN DECISION — why does the alert fire on the budget rather than on the first
window that misses its target?
    Because the budget is what makes a target a promise rather than a wish, and
    a promise that cannot survive a single bad window is not one an operator can
    keep. A target alone is unlivable: every window of every day has a tail, and
    a fleet that pages on the first one has its alert muted by lunchtime. The
    budget is the amount of missing the promise the run has already bought, so a
    window inside the target spends nothing however close it came, a window above
    it spends exactly its overshoot, and the page arrives only when the sum of
    those overshoots passes the allowance.

DESIGN DECISION — why is a window's metric folded over the *run* rather than over
the window's own events?
    Because a window is a state somebody was already in, and an attempt belongs
    to the window its finish fell in — both rules were frozen by stage 9. An
    attempt whose `started` event lies before the window's first tick is still
    that window's measurement: stage 5 matches a finish to its start by `(task,
    attempt)`, so a window that cut a start off has no measurement at all if it
    is folded alone. The report's own reading keeps both halves — the counters
    from the window's own events, the latencies and the state from the run.

DESIGN DECISION — why is a breach a window *strictly* above the target, and why
does a budget of zero still fire a page?
    Because the target is the promise and "at most the target" is what was
    promised, so the comparison is `>` and never `>=`; likewise the page arrives
    when the spend is *greater* than the allowance, so a budget that is exactly
    used up is not an exceeded one. A zero budget is the other side of the same
    discipline: `burn` refuses it, because a share of nothing is a fraction with
    a zero denominator, while `alert` answers it, because a target of zero is the
    strictest promise there is and its first breach spends the last of it.

DESIGN DECISION — why does `run` read its fixtures by name, and what makes it a
pure function of them?
    Because a typo in a fixture name must be the world's refusal and never a
    silent default: `run` hands its two names to the world's accessors, which
    name the offender and suggest the fixture that was meant. Purity is the other
    half of the same discipline: neither bound has a mutable default, every
    fixture is read through an accessor that hands back a fresh copy, no window
    spec or objective is written in place, and every mapping the run returns is
    built fresh — so two runs of the same fleet are equal field for field.

TODO: implement `budget`, `burn`, `alert` and `run`.
"""

import stage_01

#: An objective's four keys, in the order this stage reads them: the metric the
#: promise is about, the target the metric has to stay inside, the window fixture
#: it is measured over, and the budget the overshoots are spent from. A target
#: and a budget are both in the metric's own unit, which is why the metric's
#: spelling and the number beside it are one promise and not two.
SLO_KEYS = ("metric", "target", "window", "budget")


class SloError(stage_01.TelemetryError):
    """An objective, a window set or a window this stage refuses.

    The refusal names the offender — the key of the objective that is missing or
    extra, the metric no target can be denominated in, the target or budget that
    is not a count, the window fixture with no name, the index of the spec that
    is not a window — and, when the offender is within edit distance two of a
    name that would have worked, the world's own suggestion.
    """


def budget(events, slo, *, windows_):
    """One objective's budget, walked over a window set.

    A mapping over exactly `("allowed", "spent", "folds", "breaches")`:

    * `allowed` — the objective's budget, in the metric's own unit;
    * `spent` — the sum of the overshoots of the windows that breached, each one
      `metric - target` for a window whose metric came out strictly above the
      target, so one badly missed window spends more of it than three narrowly
      missed ones;
    * `folds` — one fold per window, in the order the windows happen, each over
      stage 8's `FOLD_KEYS` *plus* the objective's metric;
    * `breaches` — the specs of the windows that breached, in order, each one the
      spec the window set handed over: the windows themselves, not a count.

    `windows_` is the window set the budget is walked over: a fixture's name
    (read through the world, so a typo is the world's refusal) or the specs
    themselves, as `stage_08.windows` hands them back. Every window is folded and
    measured whatever its metric came out at, so a caller can see the whole
    series and not only the bad news, and a window that measured nothing answers
    zero rather than refusing — the refusals live in the folds below this stage.

    Refuses an objective that is not a mapping over `SLO_KEYS`, a metric a target
    cannot be denominated in, a target or budget that is not a non-negative int,
    a window fixture with no name, a `windows_` that is neither a name nor a
    sequence of specs, and a spec that is not a window — each naming the
    offender.
    """
    raise NotImplementedError("stage 10: implement budget()")


def burn(events, slo, *, windows_):
    """The same budget, as the share of it that is gone.

    A mapping over exactly `("burn", "allowed", "fraction")`: the spend `budget`
    measured, the objective's budget, and the share of it that is gone as an
    exact reduced pair — `(burn, allowed)` by their greatest common divisor, the
    way every ratio in this course is spelled, so a burn of 4 out of a budget of
    8 is `(1, 2)` and a run that spent nothing is `(0, 1)`. A burn may exceed its
    allowance: that is the news the alert exists to carry.

    Refuses a budget of zero — a share of nothing is a fraction with a zero
    denominator, which is a question with no answer rather than a number — naming
    the objective it belongs to, and everything `budget` refuses.
    """
    raise NotImplementedError("stage 10: implement burn()")


def alert(events, slo, *, windows_):
    """Whether the budget is gone, and which window spent the last of it.

    A mapping over exactly `("fires", "reason", "metric", "window")`. `fires` is
    the one boolean this course reports rather than refuses: it is `True` exactly
    when the spend is *strictly* above the allowance, so a budget that is exactly
    used up is not an exceeded one and every window inside the target fires
    nothing, however many of them there are. A window above the target spends its
    overshoot, and `reason` — a `str`, always — names the window that spent the
    last of the budget: the one whose overshoot carried the running total past the
    allowance. `metric` is the metric the promise is about and `window` the name
    of the window fixture it was measured over.

    `windows_` is read exactly as `budget` reads it. Refuses everything `budget`
    refuses about its arguments, and never divides, so a budget of zero is a
    perfectly decidable objective here: the first window above the target spends
    the last of it.
    """
    raise NotImplementedError("stage 10: implement alert()")


def run(pool="small", tasks=None, *, worker="flaky", slo="latency_p95",
        windows_=None, max_ticks=60):
    """The whole pipeline over one run of the fleet, as one mapping of nine keys.

    `telemetry.record()` runs the fleet and writes down what happened; the lines
    are read back as events, the fleet's own count is kept beside them, and then
    the pipeline stands on those events and nothing else:

    * `events` — the run's events, as `stage_01.read_events` reads them;
    * `summary` — the fleet's own count of the run, which is what makes the next
      key a proof rather than a printout;
    * `windows` — the fixture's window specs, `stage_08.windows`' tumbling or
      sliding set, cut at the fixture's end;
    * `folds` — one fold per window of the fixture, in stage 8's own six keys;
      `budget`'s own folds are these plus the objective's metric;
    * `report` — the whole run's row, tied against the fleet's own count by
      `stage_09.report`, so a fold that lost an event refuses here rather than
      printing;
    * `budget`, `burn`, `alert` — this stage's three answers over those windows;
    * `clock` — the tick the run stopped at, the fleet's own, not the last
      event's.

    `slo` and `windows_` are fixture *names*, read through `telemetry.slo` and
    `telemetry.window`, so a typo is the world's refusal and never a silent
    default; `windows_=None` means the objective's own window fixture. Nothing is
    written in place, no bound has a mutable default, and every mapping returned
    is built fresh, so two runs of the same fleet are equal field for field.
    """
    raise NotImplementedError("stage 10: implement run()")
