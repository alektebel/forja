"""meter.py — the customer's meter: what one decision cost, in cents and ticks.

Provided, frozen, and never written by the course. This module is the customer's own
meter: one `charge` is one line of the record (`COST_KEYS`), priced by the customer's
table (`PRICE_CENTS`, cents per unit of work) so that a number a stage reports can
always be recomputed from `charges()` and checked against `stats()`.

The five kinds are the five decisions a retrieval pipeline makes — an embedding, a
retrieval, a rerank, a critique and a generation — and the tick is the caller's: the
meter never reads a clock, never sleeps and never retries. `total_ticks()` is the
highest tick it has been charged at, which is the only sense in which a meter knows
what time it is; a budget the course holds is an `int` the caller supplied and
compared, never one this module advanced.
"""

PRICE_CENTS = {"embed": 1, "retrieve": 2, "rerank": 3, "critique": 4, "generate": 12}
COST_KEYS = ("kind", "units", "cents", "tick")

METER_ERROR = "meter: "


class MeterError(ValueError):
    """The meter's refusal: a kind it does not price, a count that is not a count."""


def _whole(value, what):
    """Check a whole number and answer it, the meter's way (a `bool` is not one)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise MeterError(METER_ERROR + ("%s is %r, not a whole number" % (what, value)))
    return value


def _kind(kind):
    """Check that `kind` is one the meter prices and answer it."""
    if kind not in PRICE_CENTS:
        raise MeterError(METER_ERROR + ("%r is not one of the priced kinds %r"
                                        % (kind, tuple(PRICE_CENTS))))
    return kind


class Meter:
    """One charge per decision, priced by the customer's own table.

    `Meter()` starts empty. `charge(kind, units, tick)` records one `COST_KEYS` line,
    `charges()` answers them all in order, and `stats()` is recomputed from them —
    never kept alongside them, because a meter's own counters are a claim until the
    log agrees with them.
    """

    def __init__(self):
        self._log = []

    def charge(self, kind, units, tick):
        """Record one charge and answer the recorded line.

        Refused, each naming the offender: a kind that is not in `PRICE_CENTS` (both
        the kind and the table's keys), a unit count or tick that is not a whole
        number, and a negative count (`-1` is not a count of anything).
        """
        _kind(kind)
        _whole(units, "units")
        if units < 0:
            raise MeterError(METER_ERROR + ("units is %d for %s, not a count"
                                            % (units, kind)))
        _whole(tick, "the tick")
        line = {"kind": kind, "units": units, "cents": PRICE_CENTS[kind] * units,
                "tick": tick}
        self._log.append(line)
        return dict(line)

    def charges(self):
        """Every charge, in the order it was recorded."""
        return tuple(dict(line) for line in self._log)

    def total_cents(self):
        """What every charge cost, in cents."""
        return sum(line["cents"] for line in self._log)

    def total_ticks(self):
        """The highest tick this meter was charged at — 0 when it was never called."""
        return max([line["tick"] for line in self._log] or [0])

    def by_kind(self):
        """What each kind cost, and how much of it was asked for."""
        totals = {}
        for line in self._log:
            seen = totals.setdefault(line["kind"], {"charges": 0, "units": 0,
                                                    "cents": 0})
            seen["charges"] = seen["charges"] + 1
            seen["units"] = seen["units"] + line["units"]
            seen["cents"] = seen["cents"] + line["cents"]
        return totals

    def log(self):
        """Every charge as a line of the record — the same lines `charges()` answers."""
        return self.charges()

    def reset(self):
        """Forget every charge and answer how many were forgotten."""
        forgotten = len(self._log)
        self._log = []
        return forgotten

    def stats(self):
        """Counters recomputed from the charges: calls, units, cents, ticks, kinds."""
        kinds = self.by_kind()
        return {
            "charges": len(self._log),
            "units": sum(line["units"] for line in self._log),
            "cents": self.total_cents(),
            "ticks": self.total_ticks(),
            "kinds": len(kinds),
            "by_kind": kinds,
        }
