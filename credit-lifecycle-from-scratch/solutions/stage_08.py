"""Credit Lifecycle From Scratch — stage 8: The provision roll-forward, line by line.

The provision between two reporting dates moved, and this stage says why: the loans that
left, the loans that arrived, the stage a loan moved to, the artifact that was replaced,
the weighting of the scenarios, the passage of time, the balances written off and the
money recovered against the stock already written off — and the one line a bank owes its
reader, `other`, for the part all of that failed to explain.

Nothing here re-derives an expected loss. A loan's provision is stage 6's own answer, the
counterfactuals that isolate one cause at a time are stage 6's own answer with a stage
and an artifact handed to it, the passage of time is stage 1's effective rate turned into
a period rate by the policy, and the loans of each population are the book's own account
of who is on it. What this stage owns is the decomposition: which loans are behind each
line, the order of the waterfall, and the discipline that the closing is recomputed and
the lines are held against it.
"""

import dates
import rules
import stage_01
import stage_06
from book import BookError, LAST_REPORTING_DATE, REPORTING_DATES

ROLLFORWARD_KEYS = ("start", "end", "opening_cents", "lines", "pl_cents", "oci_cents",
                    "closing_cents", "difference_cents")

LINES = ("derecognitions", "new-business", "stage-transfers", "parameter", "scenario",
         "unwind", "write-offs", "recoveries", "other")

_AMORTISED_COST = "amortised-cost"

_FVOCI = "fvoci"

_BASE = "base"

_WRITE_OFF = "write-off"

_STAGES = (1, 2, 3)

_OTHER = "other"

_EXPLAINED = LINES[:-1]


def _offender(loan):
    """How a refusal names a loan: its id, or the record's own reading."""
    if isinstance(loan, dict) and "loan" in loan:
        return loan["loan"]
    return loan


def _side(loan):
    """Which half of the bank's income statement the loan's money books to."""
    measured = loan["measured_at"] if isinstance(loan, dict) else None
    if measured == _AMORTISED_COST:
        return _AMORTISED_COST
    if measured == _FVOCI:
        return _FVOCI
    raise BookError("stage 8: %s measures %r, which is neither %r nor %r"
                    % (_offender(loan), measured, _AMORTISED_COST, _FVOCI))


def _covered(date, what):
    """A reporting date the book covers, or a refusal naming the offender.

    The calendar is the contract's own: `REPORTING_DATES` month ends ending at
    `LAST_REPORTING_DATE`. Asking the book for its own list would be an ask, and a
    window that cannot be a window is refused before the book is asked anything, so the
    stage reads the two constants the world publishes rather than the book's answer.
    """
    dates.parse(date)
    first = dates.add_months(LAST_REPORTING_DATE, -(REPORTING_DATES - 1))
    if date < first or date > LAST_REPORTING_DATE or dates.month_end(date) != date:
        raise BookError("stage 8: the %s %s is not a reporting date of the book"
                        % (what, date))
    return date


def _months_between(start, end):
    """Whole months from `start` to `end`: both are month ends of the book."""
    start_year, start_month, _ = dates.parse(start)
    end_year, end_month, _ = dates.parse(end)
    return (end_year - start_year) * 12 + (end_month - start_month)


def _in_force(book, date):
    """The artifact in force at a date: the newest `as_of` not after it."""
    chosen = None
    for model in book.models:
        if model["as_of"] > date:
            continue
        if chosen is None or ((model["as_of"], model["version"])
                              > (chosen["as_of"], chosen["version"])):
            chosen = model
    if chosen is None:
        raise BookError("stage 8: no model artifact is in force at %s" % (date,))
    return chosen


def _artifact(model):
    """How a line's `why` names an artifact: its name and its version."""
    return "%s v%s" % (model["name"], model["version"])


def _stage(book, loan, date):
    """The stage the book records for a loan at a date, or a refusal naming it."""
    record = book.status(loan, date)
    recorded = record.get("stage") if isinstance(record, dict) else None
    if recorded not in _STAGES:
        raise BookError("stage 8: the book records %s at %s with stage %r"
                        % (_offender(loan), date, recorded))
    return recorded


def _period_bp(book, loan):
    """The loan's own period rate: stage 1's effective rate under the day count used."""
    effective = stage_01.effective_rate(book, loan)
    return rules.period_rate(effective["eir_bp"], effective["basis"])


def _provision(book, loan, date):
    """Stage 6's scenario-weighted provision for one loan at one date.

    The stage and the artifact are the book's own for that date — the stage it records
    and, among the artifacts whose `as_of` is not after the date, the newest.
    """
    return stage_06.weighted_ecl(book, loan, date)["weighted_cents"]


def _base_ecl(book, loan, date, stage, model):
    """Stage 6's base-scenario loss for one loan at a counterfactual stage and artifact."""
    return stage_06.ecl(book, loan, date, _BASE, stage=stage, model=model)["ecl_cents"]


def _unwind(book, loan, opening_cents, months):
    """The passage of time on one loan's opening provision, one month at a time.

    The rate is the loan's own period rate and the balance is the provision the loan had
    at the start of the window: a bank unwinds the discount on what was there, not on
    what the other movements brought in afterwards.
    """
    period_bp = _period_bp(book, loan)
    accrued = 0
    for _ in range(months):
        accrued += opening_cents * period_bp // 10000
    return accrued


def _written_off_by(book, loan, date):
    """Whether a write-off event is on the loan at or before a date."""
    for event in book.events(loan):
        if event["kind"] == _WRITE_OFF and event["date"] <= date:
            return True
    return False


def _written_off_between(book, loan, start, end):
    """Whether the loan was written off after `start` and by `end`."""
    for event in book.events(loan):
        if event["kind"] == _WRITE_OFF and start < event["date"] <= end:
            return True
    return False


def _last_live(book, loan, end):
    """The last reporting date at or before `end` at which the book held the loan."""
    for date in reversed(tuple(book.reporting_dates)):
        if date <= end and loan["loan"] in book.on_book(date):
            return date
    return None


def _collected(book, loan, start, end):
    """The flows collected in the window against a loan already written off at `start`.

    A recovery is a flow of a loan whose balance is gone — a balance that was still there
    is a repayment, not a recovery — so the stock this line counts is the one written off
    by the opening date, and a `costs` flow arrives negative and reduces what came back.
    """
    if not _written_off_by(book, loan, start):
        return 0, 0
    total = 0
    flows = 0
    for flow in book.recoveries(loan):
        if start < flow["date"] <= end:
            total += flow["amount_cents"]
            flows += 1
    return total, flows


def _movements(book, loan, start, end, old, new, months, on_start, on_end):
    """One loan's part of the eight lines this stage can compute loan by loan.

    Answers `(opening, closing, amounts, sizes)`: the provision the book held for this
    loan at `start` and at `end` (zero where it held none), one amount per name in the
    eight lines, and the number of loans or flows the loan puts behind each of them so
    the line's own `why` can say what it was counting.

    A loan the book holds at both dates gets the waterfall, in the order the lines are
    printed: the stage it reached against the stage it started at, then the artifact in
    force at `end` against the one in force at `start` (both at the end stage, in the base
    scenario), then the policy's weighting against that base, then the passage of time.
    A loan written off inside the window leaves at the provision it last had on the book;
    a loan gone by the end with no write-off behind it leaves at the provision it had at
    the start; and a loan the book did not hold at the start arrived at its own.
    """
    amounts = dict((name, 0) for name in _EXPLAINED)
    sizes = dict((name, 0) for name in _EXPLAINED)
    here = loan["loan"] in on_start
    there = loan["loan"] in on_end
    opening = _provision(book, loan, start) if here else 0
    closing = _provision(book, loan, end) if there else 0
    if here:
        amounts["unwind"] = _unwind(book, loan, opening, months)
        sizes["unwind"] = 1
    if here and there:
        at_start = _stage(book, loan, start)
        at_end = _stage(book, loan, end)
        held = _base_ecl(book, loan, end, at_start, old)
        reached = _base_ecl(book, loan, end, at_end, old)
        swapped = _base_ecl(book, loan, end, at_end, new)
        amounts["stage-transfers"] = reached - held
        amounts["parameter"] = swapped - reached
        amounts["scenario"] = closing - swapped
        for line in ("stage-transfers", "parameter", "scenario"):
            sizes[line] = 1
    elif _written_off_between(book, loan, start, end):
        gone_at = _last_live(book, loan, end)
        amounts["write-offs"] = -_provision(book, loan, gone_at) if gone_at else 0
        sizes["write-offs"] = 1
    elif here:
        amounts["derecognitions"] = -opening
        sizes["derecognitions"] = 1
    elif there:
        amounts["new-business"] = closing
        sizes["new-business"] = 1
    collected, flows = _collected(book, loan, start, end)
    if flows:
        amounts["recoveries"] = collected
        sizes["recoveries"] = flows
    return opening, closing, amounts, sizes


def _why(line, cents, sizes, facts):
    """One line's own sentence: what it was counting, and the cents it came to."""
    if line == "derecognitions":
        return ("derecognitions: %d loans were gone by %s with no write-off in the window, "
                "taking %d cents of provision with them from %s"
                % (sizes[line], facts["end"], cents, facts["start"]))
    if line == "new-business":
        return ("new-business: %d loans the book held at %s and not at %s, %d cents of "
                "provision they arrived with"
                % (sizes[line], facts["end"], facts["start"], cents))
    if line == "stage-transfers":
        return ("stage-transfers: %d loans were on the book at both dates and %d cents of "
                "their provision moved with the stage the book records at %s"
                % (sizes[line], cents, facts["end"]))
    if line == "parameter":
        return ("parameter: the same %d loans at %s, priced under %s instead of %s, %d cents"
                % (sizes[line], facts["end"], facts["new"], facts["old"], cents))
    if line == "scenario":
        return ("scenario: the same %d loans weighted across the policy's scenarios at %s "
                "instead of the base one, %d cents"
                % (sizes[line], facts["end"], cents))
    if line == "unwind":
        return ("unwind: %d months of the passage of time at each loan's own period rate on "
                "the provision %d loans held at %s, %d cents"
                % (facts["months"], sizes[line], facts["start"], cents))
    if line == "write-offs":
        return ("write-offs: %d loans were written off in the window, each leaving the "
                "provision it last had on the book, %d cents" % (sizes[line], cents))
    if line == "recoveries":
        return ("recoveries: %d flows were collected in the window against the stock "
                "written off by %s, %d cents" % (sizes[line], facts["start"], cents))
    return ("other: what the eight lines above do not explain between %s and %s, %d cents"
            % (facts["start"], facts["end"], cents))


def rollforward(book, start, end):
    """The provision's movement between two reporting dates, line by line.

    `opening_cents` is the total provision at `start` and `closing_cents` the total at
    `end`, each recomputed from the loans the book holds at that date. `lines` is one
    `(line, cents, why)` entry per name in `LINES`, in that order: `derecognitions` (the
    opening provision of the loans no longer on the book at `end` with no write-off in the
    window), `new-business` (the provision of the loans that arrived), `stage-transfers`,
    `parameter` and `scenario` (the waterfall at `end` over the loans in both dates, in
    the base scenario and under the artifact in force at each date), `unwind` (the opening
    provision of every loan the book held at `start` accreted over the months between the
    dates at that loan's own effective rate),
    `write-offs` (the provision the loans written off in the window last had on the book)
    and `recoveries` (the flows collected against the stock written off by `start`), and
    `other` (whatever the eight before it left unexplained). `pl_cents` and `oci_cents`
    are the same cents split by each loan's own `measured_at`, with `other` booked to
    P&L, and `difference_cents` is `closing_cents` less the opening and the nine lines —
    zero when the decomposition is complete.

    A start after the end, a date outside the book's own reporting dates, a loan whose
    stage the book records inconsistently, or a loan whose `measured_at` is neither
    `amortised-cost` nor `fvoci`, raises `BookError` naming the offender.
    """
    _covered(start, "start date")
    _covered(end, "end date")
    if dates.days_between(start, end) < 0:
        raise BookError("stage 8: the start date %s is after the end date %s"
                        % (start, end))
    old = _in_force(book, start)
    new = _in_force(book, end)
    months = _months_between(start, end)
    on_start = set(book.on_book(start))
    on_end = set(book.on_book(end))
    totals = dict((name, 0) for name in LINES)
    sizes = dict((name, 0) for name in LINES)
    opening = 0
    closing = 0
    pl_cents = 0
    oci_cents = 0
    for loan in book.loans:
        side = _side(loan)
        held, reached, amounts, counted = _movements(book, loan, start, end, old, new,
                                                     months, on_start, on_end)
        opening += held
        closing += reached
        explained = 0
        for name in _EXPLAINED:
            totals[name] += amounts[name]
            sizes[name] += counted[name]
            explained += amounts[name]
        if side == _FVOCI:
            oci_cents += explained
        else:
            pl_cents += explained
    totals[_OTHER] = closing - opening - sum(totals[name] for name in _EXPLAINED)
    pl_cents += totals[_OTHER]
    difference = closing - opening - sum(totals[name] for name in LINES)
    facts = {"start": start, "end": end, "months": months,
             "old": _artifact(old), "new": _artifact(new)}
    lines = tuple((name, totals[name], _why(name, totals[name], sizes, facts))
                  for name in LINES)
    return {"start": start, "end": end, "opening_cents": opening, "lines": lines,
            "pl_cents": pl_cents, "oci_cents": oci_cents, "closing_cents": closing,
            "difference_cents": difference}
