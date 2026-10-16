"""FDE From Scratch — stage 9: What the AI did for this team, in hours and cents.

The ninth stage as the customer will read it: the per-(team, model) rollup of the
meter's own spans, one day's dashboard recounted from those spans with its ROI, the
teams standing out against their own mean, and the spans no team claimed.
"""

import estate
import meter

ROLLUP_KEYS = ("team", "model", "spans", "cost_cents", "minutes_saved", "resolved")

DASHBOARD_KEYS = ("day", "teams", "cost_cents", "minutes_saved", "resolved",
                  "cost_per_resolution_cents", "roi_percent")

ANOMALY_KEYS = ("team", "day", "cost_cents", "baseline_cents", "ratio_percent")

RATE_CENTS_PER_MINUTE = 45

ROI_BASIS = 100

_REFUSAL = "the metric refuses: %s"


class MetricError(estate.EstateError):
    """The metric's refusal: something that cannot be counted at all.

    A shape mismatch — a meter that cannot answer `spans()`, a day that is not a
    whole number, a threshold that is not a percentage, teams that are not a tuple
    of team names — raises this, naming the offender, and never returns.
    """


def _whole(value, what):
    """A whole number, or the refusal naming what arrived instead (a bool is not one)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise MetricError(_REFUSAL % ("%s is %r, not a whole number"
                                      % (what, value)))
    return value


def _spans(meter):
    """The spans the meter can recount, or the refusal naming what arrived."""
    if not callable(getattr(meter, "spans", None)):
        raise MetricError(_REFUSAL % ("%r cannot answer spans()" % (meter,)))
    return meter.spans()


def _day_of(span):
    """The day a span belongs to: its tick over the estate's own ticks per day."""
    return span["tick"] // estate.TICKS_PER_DAY


def _rate(team):
    """What the customer's own table says one resolution of this team's ticket saves."""
    return meter.MINUTES_SAVED.get(team, 0)


def _rows(spans):
    """The `ROLLUP_KEYS` rows for these spans, one per (team, model), sorted.

    A resolution is a (day, ticket) pair: the same ticket twice in one day — two
    models, one retry — is one resolution, and a span with the empty ticket is not
    a ticket at all.
    """
    seen = {}
    for span in spans:
        state = seen.get((span["team"], span["model"]))
        if state is None:
            state = seen[(span["team"], span["model"])] = {"spans": 0,
                                                           "cost_cents": 0,
                                                           "tickets": set()}
        state["spans"] += 1
        state["cost_cents"] += span["cost_cents"]
        if span["resolved"] and span["ticket"] != "":
            state["tickets"].add((_day_of(span), span["ticket"]))
    rows = []
    for team, model in sorted(seen):
        state = seen[(team, model)]
        rows.append({"team": team, "model": model, "spans": state["spans"],
                     "cost_cents": state["cost_cents"],
                     "minutes_saved": len(state["tickets"]) * _rate(team),
                     "resolved": len(state["tickets"])})
    return tuple(rows)


def rollup(meter):
    """One `ROLLUP_KEYS` row per (team, model) pair the meter's spans mention."""
    return _rows(_spans(meter))


def team_day(meter, day):
    """The `ROLLUP_KEYS` rows for one day: the rollup of that day's spans only."""
    spans = _spans(meter)
    _whole(day, "the day")
    return _rows(tuple(span for span in spans if _day_of(span) == day))


def dashboard(meter, day):
    """One day, recounted from its spans, as `DASHBOARD_KEYS`."""
    spans = _spans(meter)
    _whole(day, "the day")
    today = tuple(span for span in spans if _day_of(span) == day)
    teams = sorted({span["team"] for span in today})
    cost_cents = sum(span["cost_cents"] for span in today)
    tickets = {(span["team"], span["ticket"]) for span in today
               if span["resolved"] and span["ticket"] != ""}
    resolved = len(tickets)
    minutes_saved = 0
    for team, ticket in sorted(tickets):
        minutes_saved = minutes_saved + _rate(team)
    cost_per_resolution = cost_cents // resolved if resolved else 0
    roi = (minutes_saved * RATE_CENTS_PER_MINUTE * ROI_BASIS // cost_cents
           if cost_cents else None)
    return {"day": day, "teams": tuple(teams), "cost_cents": cost_cents,
            "minutes_saved": minutes_saved, "resolved": resolved,
            "cost_per_resolution_cents": cost_per_resolution,
            "roi_percent": roi}


def anomalies(meter, day, ratio_percent):
    """The teams whose cost on `day` is at least `ratio_percent` of their own mean."""
    spans = _spans(meter)
    _whole(day, "the day")
    _whole(ratio_percent, "the ratio")
    if ratio_percent < 0:
        raise MetricError(_REFUSAL % ("the ratio is %r percent, and a threshold is "
                                      "not negative" % (ratio_percent,)))
    by_team = {}
    for span in spans:
        days = by_team.setdefault(span["team"], {})
        days[_day_of(span)] = days.get(_day_of(span), 0) + span["cost_cents"]
    found = []
    for team in sorted(by_team):
        days = by_team[team]
        if len(days) < 2:
            continue
        baseline = sum(days.values()) // len(days)
        if baseline <= 0:
            continue
        cost = days.get(day, 0)
        if cost * 100 >= ratio_percent * baseline:
            found.append({"team": team, "day": day, "cost_cents": cost,
                          "baseline_cents": baseline,
                          "ratio_percent": cost * 100 // baseline})
    return tuple(found)


def unattributed(meter, teams):
    """The spans whose team is not in `teams`, as `(tick, team, ticket)`, in order."""
    spans = _spans(meter)
    if not isinstance(teams, tuple):
        raise MetricError(_REFUSAL % ("teams is %r, and a tuple of team names was "
                                      "wanted" % (teams,)))
    for team in teams:
        if not isinstance(team, str):
            raise MetricError(_REFUSAL % ("%r is not a team name" % (team,)))
    return tuple((span["tick"], span["team"], span["ticket"]) for span in spans
                 if span["team"] not in teams)
