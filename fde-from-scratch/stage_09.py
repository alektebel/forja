"""FDE From Scratch — stage 9: What the AI did for this team, in hours and cents.

Eight stages built the thing; this one has to say what it was worth. A renewal
conversation is not held about prompts and tokens, it is held about hours saved and
cents spent on *their* tickets, per team and per day, and every number in it has to
be recomputable by the person asking. So this stage holds no state of its own: it is
a set of functions over `Meter.spans()`, the customer's own record, and every answer
is recounted from those spans at the moment it is asked for. `Meter.stats()` exists,
is tempting, and is not the input: a dashboard that reads a counter agrees with that
counter's bug forever, which is the argument stage 2's verification and stage 3's
reconciliation are both built on.

The unit of an ROI conversation is a resolution. One span is one request; a ticket
that appears twice in a day — two models answering for it, a retry — is one ticket
for that day, and a span whose ticket is empty is not a ticket at all, it is a
request nobody can bill to anything. Minutes are saved only by resolutions
(`MINUTES_SAVED` is the customer's own estimate of a human's time, per team), so a
meter full of unresolved tickets saves nobody's minutes however many cents it burned.
Cost per resolution is the day's cents over the day's tickets, and it is zero, not an
error, when nothing resolved: a day that spent money and resolved nothing is a
finding, and a report that raises instead of printing it has thrown the finding away.

The return on that spend is a whole percentage, and it is `None` when the spend was
zero. "Infinite ROI" is not a number this stage may print, and neither is a division
by zero: a day whose cost is zero has no ratio, and saying so is the honest answer.
The same instinct governs `anomalies` — a cost compared against a team's own mean
needs more than one day of history to have a mean at all — and the comparison is at
least the threshold, *inclusively*, because the boundary is the number the customer
will argue about, and a boundary nobody pinned is a boundary that moves.

`unattributed` is the last question and the uncomfortable one. A span belongs to a
team; a span whose team is not one the caller owns is a token that was spent for
nobody, and the answer names it in the meter's own order — tick, team, ticket — so
the customer can go and find out who spent it.

    ROLLUP_KEYS                           the six fields of a (team, model) row, in order
    DASHBOARD_KEYS                        the seven fields of one day's dashboard, in order
    RATE_CENTS_PER_MINUTE                 what one saved minute of the customer's time is worth
    ROI_BASIS                             the denominator of a percentage: this many is 100%
    ANOMALY_KEYS                          the five fields of one anomaly, in order
    MetricError(estate.EstateError)       the stage's refusal: a shape it cannot recount
    rollup(meter)                         -> one ROLLUP_KEYS row per (team, model), sorted
    team_day(meter, day)                  -> that day's rows, same shape, same sort
    dashboard(meter, day)                 -> DASHBOARD_KEYS, the day recounted from its spans
    anomalies(meter, day, ratio_percent)  -> ANOMALY_KEYS, one per team at or over the threshold
    unattributed(meter, teams)            -> (tick, team, ticket) for every span of a stranger team

DESIGN DECISION — why is every answer recounted from `spans()` rather than read out
of `stats()`?
Because the meter's counters and the spans they were counted from are one bug apart,
and the counter is the side that cannot be questioned. `stats()` is the meter's belief
about itself: it is recomputed from the same log, by the same hand, and a dashboard
that copies it inherits every mistake in it without ever disagreeing. Reading the
spans makes the dashboard a *measurement* of the record rather than a restatement of
it, and it lets the check hold the two side by side — the spans, summed by the course,
against the stats, summed by the world. Where they differ, the customer's own log is
the tie-breaker, which is exactly the position a dashboard should be in.

DESIGN DECISION — why is a ticket counted once per day, and not once per model, and
not once for all time?
Because the question being answered is "how much did this team get done today, and
what did it cost", and a model is how an answer was produced, not what was resolved.
Two models answering the same ticket in one day, or a retry of the same ticket,
resolved that ticket once; a ticket carried over into tomorrow is a different day's
resolution, and the day is the window the customer reviews — a month-long dedupe would
report fewer resolutions the longer the meter ran. So a resolution is a (day, ticket)
pair, and everything that counts resolutions or minutes counts pairs, never spans.

DESIGN DECISION — why is `roi_percent` `None` when the day cost nothing, and not a
very large number?
Because "infinite" is not a number a report may print. A percentage of an investment is
`return * ROI_BASIS // investment`, and at a zero investment the expression has no
answer that survives being put in a slide: a sentinel like a huge integer is a number
the VP will quote, and quoting it once ends the credibility of every other number on
the page. `None` is not a missing measurement here, it is a verdict — there was no
investment to have a return on — and the shape the contract asks for is a field that
can say so.

DESIGN DECISION — why is a team with one day of history never an anomaly?
Because the baseline would be the day itself, and nothing is ever an anomaly compared
with itself. A team first seen today can only be at 100% of its own mean; calling that
out trains the reader to ignore the report, and the reader who ignores the report is
the one who misses the real anomaly next week. The same reasoning covers a team whose
mean is zero: a baseline of nothing flags nothing, so a team that has spent no cents
over any of its days is passed over instead of divided by.

DESIGN DECISION — why does the anomaly rule compare with `>=` and report the observed
ratio rather than the threshold?
Because the threshold is the caller's and the ratio is the finding. A team at exactly
the threshold is at the number the caller said to look at, so it is in the report;
excluding it is a boundary the check would have to pin on one side only, and a
one-sided boundary is where a defect hides. And a row that echoes the caller's own
constant back tells the reader nothing he did not type — the number worth carrying is
how far past the mean the day actually went, so `ratio_percent` is that observed
percentage, computed the same way the comparison is, in whole numbers.

TODO: implement `MetricError`, `rollup`, `team_day`, `dashboard`, `anomalies` and
`unattributed` in this file: the refusal, the per-(team, model) rollup, the same rows
for one day, the day's dashboard with its two divisions, the anomaly rule with its
baseline, and the spans whose team nobody claimed.
"""

import estate
import meter

ROLLUP_KEYS = ("team", "model", "spans", "cost_cents", "minutes_saved", "resolved")

DASHBOARD_KEYS = ("day", "teams", "cost_cents", "minutes_saved", "resolved",
                  "cost_per_resolution_cents", "roi_percent")

ANOMALY_KEYS = ("team", "day", "cost_cents", "baseline_cents", "ratio_percent")

RATE_CENTS_PER_MINUTE = 45

ROI_BASIS = 100


class MetricError(estate.EstateError):
    """The metric's refusal: something that cannot be counted at all.

    A shape mismatch — a meter that cannot answer `spans()`, a day that is not a
    whole number, a threshold that is not a percentage, teams that are not a tuple
    of team names — raises this, naming the offender, and never returns.
    """


def rollup(meter):
    """One `ROLLUP_KEYS` row per (team, model) pair the meter's spans mention.

    Sorted by (team, model): `spans` is how many spans the pair has, `cost_cents`
    what they cost, and `resolved` the tickets the pair resolved — a (day, ticket)
    pair the meter recorded as resolved, counted once however many spans carry it,
    with the empty ticket not a ticket at all. `minutes_saved` is those resolutions
    times the customer's own `MINUTES_SAVED` for the team.
    """
    raise NotImplementedError("stage 9: implement rollup()")


def team_day(meter, day):
    """The `ROLLUP_KEYS` rows for one day: the rollup of that day's spans only.

    A day is `tick // estate.TICKS_PER_DAY`, the same arithmetic the customer's
    own record uses; a day no span reached is an empty tuple, not a zero row.
    """
    raise NotImplementedError("stage 9: implement team_day()")


def dashboard(meter, day):
    """One day, recounted from its spans, as `DASHBOARD_KEYS`.

    `teams` is sorted; `cost_cents`, `minutes_saved` and `resolved` are the day's
    own totals, with a resolution the same (team, ticket) once; `resolved` is the
    number of tickets resolved that day; `cost_per_resolution_cents` is the day's
    cents over them and `0` when nothing resolved; `roi_percent` is
    `minutes_saved * RATE_CENTS_PER_MINUTE * ROI_BASIS // cost_cents`, and `None`
    when the day cost nothing, because a zero investment has no return to report.
    """
    raise NotImplementedError("stage 9: implement dashboard()")


def anomalies(meter, day, ratio_percent):
    """The teams whose cost on `day` is at least `ratio_percent` of their own mean.

    Sorted by team. A team's mean is over the days it has spans in — the days
    present in the meter for *that team* — and a team with fewer than two such
    days, or a mean of zero, is never an anomaly: there is no baseline to stand
    out from. The comparison is inclusive; `ratio_percent` in each row is the
    ratio observed, in whole percent.
    """
    raise NotImplementedError("stage 9: implement anomalies()")


def unattributed(meter, teams):
    """The spans whose team is not in `teams`, as `(tick, team, ticket)`.

    In the meter's own span order; `teams` is a tuple of team names, and anything
    that is not one raises rather than being iterated as if it were.
    """
    raise NotImplementedError("stage 9: implement unattributed()")
