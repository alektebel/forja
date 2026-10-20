"""IRB and Regulatory Capital — stage 8: The output floor, phased in.

An IRB bank's capital is bounded below by what a *standardized* bank would
report for the same exposures — the output floor — and the floor phases in:
a quarter of the proxy in the first regulated year, growing one seeded step a
year until it holds the whole thing. `irb.FLOOR_PHASE_PERCENT` is that
schedule as data — an integer percent per calendar year — and `phase(year)`
answers the row or refuses a year outside the schedule by name.

The floor binds per exposure, not in aggregate: each loan's own IRB risk
weight is set against the same loan's share of the standardized proxy —
the proxy is `ead * STANDARD_WEIGHT_BP[class] // 10000` at the class row the
policy provides (a fixed table, never computed from anything the course
produced), and the share is `proxy * percent // 100`, truncated. The
exposure files the greater of the two, and the totals fall out of the rows:
the floor's own total is the sum of the shares, the bank's own total is the
sum of the weights, and the applied answer is the sum of what each exposure
files.

What the schedule is precise about, the fixtures are precise about: in 2028 the
floor is a quarter of the proxy, and the estate has its own exposure-level
answers in both directions — a loan the floor already holds up at 25%, and a
year in which nothing binds and the bank files its own weights. The year 2031
is the one the pack files `floor` over: 60% of the proxy and the two loans it
holds up name themselves in the totals.
TODO: implement `phase` and `applied` in this file: the year the floor's
schedule has reached, and the greater of own capital and the floor's share,
exposure by exposure."""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

import dates
import irb
import rules
from book import BookError
from irb import PolicyError

#: The schedule itself, as the policy carries it — a percent per calendar year.
FLOOR_PHASE_PERCENT = irb.FLOOR_PHASE_PERCENT

#: The standardized proxy's own weights per asset class, in basis points.
STANDARD_WEIGHT_BP = irb.STANDARD_WEIGHT_BP

#: The asset classes the proxy weights are keyed on, in their own order.
CLASSES = irb.CLASSES

#: The years the schedule runs over, pinned for the refusal's message.
YEARS = tuple(sorted(FLOOR_PHASE_PERCENT))

#: The two ways a bank files: the floor's answer, or its own weights.
FILES = ("floor", "own")

#: The fields of the applied record, in order.
APPLIED_KEYS = ("at", "year", "percent", "exposures", "own_rwa_cents",
                "floor_rwa_cents", "applied_rwa_cents", "bound_exposures", "files")

#: The scale every rate and basis-point measure is held at.
BP_SCALE = 10000


class FloorError(PolicyError):
    """The refusal this stage raises: something that cannot be a floor answer.

    It names the offender — the year outside the schedule, the date the book
    does not cover, the artifact of stage 7 the estate cannot produce — because
    a filing the schedule does not hold must say what it was asked for rather
    than answer one phase-in early or late.
    """


def phase(year):
    """The percent of the proxy the floor holds in `year`, from the schedule.

    The schedule is the policy's own table: `2028` answers one quarter, `2035`
    the whole of it, each integer percent as the year's row. A year outside the
    schedule — before `min(YEARS)` or after `max(YEARS)` — is refused by name,
    naming the years the schedule does hold, because a floor applied one year
    early is precisely the filing a supervisor reads for.
    """
    raise NotImplementedError("stage 8: implement phase()")


def applied(book, at, year):
    """The floor's answer for `at` at `year`, exposure by exposure.

    The record carries the year's percent, the loans the floor prices — the
    ones on the book at `at` with a remaining term — and the three totals the
    rows produce: the bank's own risk-weighted amount, the floor's total (the
    sum of the shares the schedule asks of each exposure), and the applied
    answer, which is the sum of what each exposure *files* — its own weight or
    the floor's share, whichever is greater. `bound_exposures` names how many
    loans floor holds above their own weight, and `files` answers
    `"floor"` when at least one does and `"own"` when none does, because the
    proposal a bank submits names which of the two answers it filed — an
    aggregate-only floor would hide the loans the profits were taken from.

    A year outside the schedule and a date the book does not cover are refused
    by name.
    """
    raise NotImplementedError("stage 8: implement applied()")
