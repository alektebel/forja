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

`budget` measures, `burn` shares, `alert` decides, and `run` is the pipeline
end to end over `telemetry.record()`: record the fleet, fold the fixture's
windows, build the report against the fleet's own count, price the budget and
decide the alert. Two runs of the same fleet are equal field for field, and the
run's report equals the summary that fleet counted for itself on every key they
share — the course's claim in one line: the numbers on this dashboard are folds
of events that happened, over a window this SLO chose.

DESIGN DECISION — why is the burn the sum of the overshoots, and not the number
of windows that breached?
    Because the budget is denominated in the metric's own unit — ticks for a
    quantile of latency, micros for a spend, basis points for a rate — and a
    count of bad windows is denominated in nothing. A window that came in one
    tick over a p95 target and a window that came in forty ticks over it are one
    breach each and utterly different news; the operator whose page says "3
    windows breached" cannot tell which of the two days it was. The overshoot is
    the *size* of the promise that was broken, which is the only thing a budget
    in the promise's unit can measure: one badly missed window spends more of it
    than three narrowly missed ones, and the alert that fires on the sum is the
    alert worth waking up for.

DESIGN DECISION — why does the alert fire on the budget rather than on the first
window that misses its target?
    Because the budget is what makes a target a promise rather than a wish, and
    a promise that cannot survive a single bad window is not one an operator can
    keep. A target alone is unlivable: every window of every day has a tail, and
    a fleet that pages on the first one has its alert muted by lunchtime. The
    budget is the amount of missing the promise has already bought the run, so a
    window inside the target spends nothing however close it came, a window above
    it spends exactly its overshoot, and the page arrives only when the sum of
    those overshoots passes the allowance. The reason it carries names the window
    that spent the last of it, because that is the window the duty engineer
    should look at first.

DESIGN DECISION — why is a window's metric folded over the *run* rather than
over the window's own events?
    Because a window is a state somebody was already in, and an attempt belongs
    to the window its finish fell in — both rules were frozen by stage 9, and
    this stage walks the same windows the run's own row is folded over. An
    attempt whose `started` event lies before the window's first tick is still
    that window's measurement, and folding only the window's own events would
    lose it: `attempt_latency` matches a finish to its start by `(task,
    attempt)`, so a window holding a finish whose start it cut off has no
    measurement at all. `metrics(events, start, end)` is the reading that keeps
    both halves: the counters from the window's own events, the latencies and the
    state from the run.

DESIGN DECISION — why is a breach a window *strictly* above the target?
    Because the target is the promise and "at most the target" is what was
    promised: a window that came in exactly at it kept the promise and spent
    nothing, so the comparison is `>` and never `>=`. The same rule shows up in
    the alert on the other side of the budget — the page arrives when the spend
    is *greater* than the allowance, so a budget that is exactly used up is a
    budget that was not exceeded, and the noise floor moves from "one window
    missed" to "the promise has actually been broken". Pinning both sides is what
    lets the check assert the digit rather than the mood.

DESIGN DECISION — why is a zero budget refused by `burn` but accepted by
`alert`?
    Because they are different questions about the same number. A share of a
    zero budget is a fraction with a zero denominator, and this course refuses a
    ratio nobody asked for rather than inventing one: "a budget nobody set is not
    a budget" is a verdict on the SLO, and `burn` names it. `alert` asks only
    whether the spend is above the allowance, and the answer is defined for every
    allowance including zero: a target of zero is the strictest promise there is,
    the first window above it spends the last of a budget that never existed, and
    the page fires. A stage that refused both would leave the strictest
    objective in the book undecidable.

DESIGN DECISION — why does `run` read its fixtures by name, and what makes it a
pure function of them?
    Because a typo in a fixture name must be the world's refusal and never a
    silent default: `run` hands `slo` and `windows_` to `telemetry.slo` and
    `telemetry.window`, which name the offender and suggest the fixture that was
    meant, so `run(slo="latency_p95x")` stops at the world rather than pricing
    the wrong promise. Purity is the other half of the same discipline: neither
    bound has a mutable default, every fixture is read through an accessor that
    hands back a fresh copy, no window spec or objective is written in place, and
    every mapping the run returns is built fresh — so two runs of the same fleet
    are equal field for field, and a caller can hand the result around.

TODO: implement `budget`, `burn`, `alert` and `run`.
"""

from collections.abc import Mapping, Sequence

import telemetry as world

import stage_01
import stage_08
import stage_09

#: An objective's four keys, in the order this stage reads them: the metric the
#: promise is about, the target the metric has to stay inside, the window fixture
#: it is measured over, and the budget the overshoots are spent from. A target
#: and a budget are both in the metric's own unit, which is why the metric's
#: spelling and the number beside it are one promise and not two.
SLO_KEYS = ("metric", "target", "window", "budget")

#: The metrics a target and a budget may be denominated in, because a target in a
#: unit other than its metric's is a promise nobody can spend: a quantile of
#: latency is ticks, a spend is micros, and a rate is basis points.
_METRICS = ("p50", "p95", "p99", "micros", "failure_bp", "retry_bp")


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
      spec the window set handed over: the windows themselves, not a count of
      them.

    `windows_` is the window set the budget is walked over: a fixture's name
    (read through the world, so a typo is the world's refusal) or the specs
    themselves, as `stage_08.windows` hands them back. Every window is folded and
    measured whatever its metric came out at, so a caller can see the whole
    series and not only the bad news, and a window that measured nothing answers
    zero rather than refusing — the refusals live in the folds below this stage,
    where a caller who asks them directly still finds them.

    Refuses an objective that is not a mapping over `SLO_KEYS`, a metric a target
    cannot be denominated in, a target or budget that is not a non-negative int,
    a window fixture with no name, a `windows_` that is neither a name nor a
    sequence of specs, and a spec that is not a window — each naming the
    offender.
    """
    objective = _objective(slo)
    given = _windows(windows_)
    metric = objective["metric"]
    target = objective["target"]
    folds = []
    breaches = []
    spent = 0
    for spec in given:
        fold = dict(stage_08.fold(events, spec))
        value = _value(events, spec, metric)
        fold[metric] = value
        folds.append(fold)
        if value > target:
            breaches.append(spec)
            spent += value - target
    return {"allowed": objective["budget"], "spent": spent,
            "folds": tuple(folds), "breaches": tuple(breaches)}


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
    objective = _objective(slo)
    walked = budget(events, objective, windows_=windows_)
    allowed = walked["allowed"]
    if allowed == 0:
        raise SloError("the objective on %s over %r has a budget of zero: a burn "
                       "is a share of the budget and a budget nobody set is not "
                       "a budget" % (objective["metric"], objective["window"]))
    spent = walked["spent"]
    divisor = _gcd(spent, allowed)
    return {"burn": spent, "allowed": allowed,
            "fraction": (spent // divisor, allowed // divisor)}


def alert(events, slo, *, windows_):
    """Whether the budget is gone, and which window spent the last of it.

    A mapping over exactly `("fires", "reason", "metric", "window")`. `fires` is
    the one boolean this course reports rather than refuses: it is `True` exactly
    when the spend is *strictly* above the allowance, so a budget that is exactly
    used up is not an exceeded one and every window inside the target fires
    nothing, however many of them there are. A window above the target spends its
    overshoot, and `reason` — a `str`, always — names the window that spent the
    last of the budget: the one whose overshoot carried the running total past
    the allowance. `metric` is the metric the promise is about and `window` the
    name of the window fixture it was measured over.

    `windows_` is read exactly as `budget` reads it. Refuses everything `budget`
    refuses about its arguments, and never divides, so a budget of zero is a
    perfectly decidable objective here: the first window above the target spends
    the last of it.
    """
    objective = _objective(slo)
    given = _windows(windows_)
    metric = objective["metric"]
    target = objective["target"]
    allowed = objective["budget"]
    spent = 0
    last = None
    for spec in given:
        value = _value(events, spec, metric)
        if value <= target:
            continue
        spent += value - target
        if last is None and spent > allowed:
            last = spec["start"]
    if spent > allowed:
        reason = ("spent %d of %d on %s: the window that spent the last of it "
                  "opened at tick %d" % (spent, allowed, metric, last))
    else:
        reason = ("spent %d of %d on %s: every window stayed inside %d"
                  % (spent, allowed, metric, target))
    return {"fires": spent > allowed, "reason": reason, "metric": metric,
            "window": objective["window"]}


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
    recorded = world.record(pool, tasks, worker=worker, max_ticks=max_ticks)
    events = stage_01.read_events(recorded["text"])
    summary = recorded["summary"]
    objective = world.slo(slo)
    if windows_ is None:
        windows_ = objective["window"]
    fixture = world.window(windows_)
    specs = stage_08.windows(fixture["start"], fixture["end"], fixture["width"],
                             step=fixture["step"])
    spent = budget(events, objective, windows_=specs)
    share = burn(events, objective, windows_=specs)
    page = alert(events, objective, windows_=specs)
    return {"events": events, "summary": summary, "windows": specs,
            "folds": stage_08.partition(events, specs),
            "report": stage_09.report(events, summary),
            "budget": spent, "burn": share, "alert": page,
            "clock": recorded["clock"]}


def _objective(slo):
    """The objective a budget spends: the four keys, each one of them checked.

    The metric decides the unit the target and the budget are read in, so it has
    to be a metric a target can be denominated in — the point of the whole stage
    is that a budget in a different unit from its metric cannot be spent.
    """
    if not isinstance(slo, Mapping):
        raise SloError("an objective is a mapping over %s, got %s"
                       % (", ".join(SLO_KEYS), type(slo).__name__))
    for key in SLO_KEYS:
        if key not in slo:
            raise SloError("an objective has no %r%s"
                           % (key, world._near(key, tuple(slo))))
    for key in slo:
        if key not in SLO_KEYS:
            raise SloError("an objective carries %r, which is not one of %s%s"
                           % (key, ", ".join(SLO_KEYS),
                              world._near(key, SLO_KEYS)))
    metric = slo["metric"]
    if metric not in _METRICS:
        raise SloError("a target is in the metric's own unit, and %r is not a "
                       "metric this course can denominate: %s%s"
                       % (metric, ", ".join(_METRICS),
                          world._near(metric, _METRICS)))
    _amount(slo["target"], "target")
    _amount(slo["budget"], "budget")
    _fixture(slo["window"], "window")
    return slo


def _amount(value, what):
    """A target or a budget: a non-negative int count, refused by its name."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise SloError("the %s of an objective is a count in the metric's own "
                       "unit and must be an int, got %r (%s)"
                       % (what, value, type(value).__name__))
    if value < 0:
        raise SloError("the %s of an objective is negative: %d" % (what, value))
    return value


def _fixture(value, what):
    """A fixture's name: a non-empty string with no space in it."""
    if not isinstance(value, str) or len(value.split()) != 1:
        raise SloError("the %s of an objective names a window fixture, got %r"
                       % (what, value))
    return value


def _windows(windows_):
    """The window set a budget walks: a fixture's name, or the specs themselves.

    A name is read through the world's accessor and built by stage 8, so a typo
    is refused by the world and a fixture that names a sliding set stays sliding.
    A sequence of specs is handed over as it stands, each one checked to be a
    spec a fold could read.
    """
    if isinstance(windows_, str):
        fixture = world.window(windows_)
        return stage_08.windows(fixture["start"], fixture["end"],
                                fixture["width"], step=fixture["step"])
    written = isinstance(windows_, (bytes, bytearray))
    if written or not isinstance(windows_, Sequence):
        raise SloError("a budget walks a sequence of window specs, or the name of "
                       "a window fixture, got %s"
                       % (type(windows_).__name__,))
    given = tuple(windows_)
    for index, spec in enumerate(given):
        if not isinstance(spec, Mapping):
            raise SloError("window %d is not a spec: %r" % (index, spec))
    return given


def _value(events, spec, metric):
    """One window's metric: stage 9's row for that window, read at one cell.

    The window is folded *over the run* rather than over the window's own events,
    because an attempt belongs to the window its finish fell in and a window is a
    state somebody was already in: a window that begins in the middle of an
    attempt still holds that attempt's cost, and a window whose queue was there
    before it opened still folds that queue. Handing the window's own events to
    stage 5 would turn both into holes.
    """
    return stage_09.metrics(events, start=spec["start"], end=spec["end"])[metric]


def _gcd(first, second):
    """The greatest common divisor of two counts, Euclid's way — no `math` here."""
    while second:
        first, second = second, first % second
    return first
