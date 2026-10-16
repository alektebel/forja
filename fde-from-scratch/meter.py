"""meter.py — the customer's pulse: what the AI cost, and what it did for a team.

Provided, frozen, and never written by the course. This module is the customer's own
meter: one span per request (`SPAN_KEYS`), with the cost computed by the meter from
its own price table (`PRICES`, cents per 1000 tokens, prompt and completion priced
apart) so that a number a stage reports can always be recomputed from `spans()` and
checked against `stats()`.

A span carries the team it was for, the model that answered, the two token counts,
the latency, the support ticket it served and whether that ticket was resolved.
`MINUTES_SAVED` is the customer's own estimate of a human's time saved by one
resolved ticket, per team — the input to every ROI conversation, and the reason the
meter refuses a caller-supplied cost: the price table is the customer's, not the
course's.
"""

from estate import EstateError

SPAN_KEYS = ("tick", "team", "model", "prompt_tokens", "completion_tokens",
             "cost_cents", "latency_ticks", "ticket", "resolved")

PRICES = {
    "north-8b-awq": (12, 34),
    "north-8b-gguf-q4": (10, 28),
    "north-8b-gguf-q8": (16, 44),
    "north-8b-fp16": (30, 60),
    "north-70b-awq": (90, 180),
    "hosted-frontier": (150, 600),
}

MINUTES_SAVED = {"support": 12, "procurement": 40, "finance": 6}

METER_ERROR = "the meter refuses: %s"


class MeterError(EstateError):
    """The meter's refusal: an unknown model, a negative count, someone else's price."""


def _whole(value, what):
    """Check a whole number and answer it, the meter's own way (a `bool` is not one)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise MeterError(METER_ERROR % ("%s is %r, not a whole number" % (what, value)))
    return value


def _string(value, what):
    """Check a string and answer it, the meter's own way."""
    if not isinstance(value, str):
        raise MeterError(METER_ERROR % ("%s is a %s, not a string"
                                        % (what, type(value).__name__)))
    return value


class Meter:
    """One span per request, priced by the customer's own table.

    `Meter()` starts empty. `span` records one request and answers the line it
    recorded, `spans()` answers them all in order, and `stats()` is recomputed from
    them — never kept alongside them.
    """

    def __init__(self):
        self._log = []

    def span(self, tick, team, model, prompt_tokens, completion_tokens, latency_ticks,
             ticket, resolved, cost_cents=None):
        """Record one span, priced by `PRICES`, and answer the recorded line.

        Refused, each naming the offender: an unknown model (both the model and the
        table's keys); a token count, latency or tick that is not a whole number; a
        negative count; a `resolved` that is not a bool; and a caller-supplied
        `cost_cents` — this meter prices its own spans, and a caller-supplied cost is
        refused naming both the supplied and the computed cents.
        """
        _whole(tick, "the tick")
        _string(team, "the team")
        if model not in PRICES:
            raise MeterError(METER_ERROR % ("%r is not one of the priced models %r"
                                            % (model, tuple(PRICES))))
        for name, value in (("prompt_tokens", prompt_tokens),
                            ("completion_tokens", completion_tokens),
                            ("latency_ticks", latency_ticks)):
            _whole(value, name)
            if value < 0:
                raise MeterError(METER_ERROR % ("%s is %d, not a count" % (name, value)))
        if not isinstance(resolved, bool):
            raise MeterError(METER_ERROR % ("resolved is %r, not a bool" % (resolved,)))
        _string(ticket, "the ticket")
        prompt_price, completion_price = PRICES[model]
        computed = (prompt_tokens * prompt_price + completion_tokens * completion_price) // 1000
        if cost_cents is not None and cost_cents != computed:
            raise MeterError(METER_ERROR % ("the caller supplied %r cents where %d was "
                                            "computed for %s" % (cost_cents, computed, model)))
        line = {"tick": tick, "team": team, "model": model,
                "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                "cost_cents": computed, "latency_ticks": latency_ticks,
                "ticket": ticket, "resolved": resolved}
        self._log.append(line)
        return dict(line)

    def spans(self):
        """Every span, in the order it was recorded."""
        return tuple(dict(line) for line in self._log)

    def log(self):
        """Every span as a line of the record — the same lines `spans()` answers."""
        return self.spans()

    def reset(self):
        """Forget every span and answer how many were forgotten."""
        forgotten = len(self._log)
        self._log = []
        return forgotten

    def stats(self):
        """Counters recomputed from the spans: tokens, cents, tickets, minutes, teams."""
        resolved = [line for line in self._log if line["resolved"]]
        by_model = {}
        by_team = {}
        for line in self._log:
            model = by_model.setdefault(line["model"], {"spans": 0, "cost_cents": 0})
            model["spans"] = model["spans"] + 1
            model["cost_cents"] = model["cost_cents"] + line["cost_cents"]
            team = by_team.setdefault(line["team"], {"spans": 0, "cost_cents": 0,
                                                     "resolved": 0})
            team["spans"] = team["spans"] + 1
            team["cost_cents"] = team["cost_cents"] + line["cost_cents"]
            if line["resolved"]:
                team["resolved"] = team["resolved"] + 1
        return {
            "spans": len(self._log),
            "prompt_tokens": sum(line["prompt_tokens"] for line in self._log),
            "completion_tokens": sum(line["completion_tokens"] for line in self._log),
            "cost_cents": sum(line["cost_cents"] for line in self._log),
            "resolved": len(resolved),
            "unresolved": len(self._log) - len(resolved),
            "minutes_saved": sum(MINUTES_SAVED[line["team"]] for line in resolved
                                 if line["team"] in MINUTES_SAVED),
            "by_model": by_model,
            "by_team": by_team,
        }
