"""Collections Workout From Scratch — stage 4: Forbearance as the bank's decision.

The bank's collections operation is a pyramid and a waterfall, but between them
sits the bank's own decision to grant forbearance: a temporary relief from the
normal terms. Three remedies are available — restructure the schedule, extend the
term, or capitalise the arrears — each with its own eligibility flags. The desk
grants the first remedy whose flags all pass, and the loan carries the grant
on record until the probation ends.

This stage asks three questions the bank's records answer: whether a remedy is
eligible on a given day, what the remedy's terms are, and whether the probation
starts, what its length is, and whether the cure requirement from the policy
holds.

    ForbearanceError         the refusal this stage raises
    REMEDY_KEYS              the four fields of a forbearance grant, in order
    eligible(book, loan, at, remedy) -> True/False + which flags passed/failed
    terms(remedy)            -> the remedy's terms: probation_months and description
    probation(certifies)     -> the probation start, length and cure requirement

DESIGN DECISION — why does the stage check flags on a specific date rather than
over the whole history?
Because forbearance eligibility is a snapshot: the desk asks "can I grant
[remedy] *today*?" and the answer depends on what the loan's history shows
*today*. A flag that passed three months ago and failed yesterday does not
make the remedy eligible today.

DESIGN DECISION — why does the stage read the loan's events directly instead of
reading workout.py's GRANTS?
Because the GRANTS table is the answer key (the desk's own book) and the stage
must be able to compute eligibility from the raw facts: the loan's events, the
materiality test, and the default status. A stage that reads the GRANTS table
would not learn how the desk reaches its decision.

DESIGN DECISION — why is the probation length the policy's `CURE_MONTHS` and not
different per remedy?
Because the policy's own rule is that every remedy runs a probation long enough
to cure under the policy's own definition (three months from the grant), and
this is a uniform rule across all remedies.

TODO: implement `ForbearanceError`, `eligible`, `terms` and `probation` in
this file: the flag checks, the remedy terms, and the probation record.

    A loan is refused by name when the book does not hold it.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import book as book_module
import workout as col
import dates
import rules

REMEDY_KEYS = ("loan", "granted_on", "remedy", "probation_until")


class ForbearanceError(ValueError):
    """The refusal this stage raises: a remedy the rules do not allow.

    It names the offender — the loan the book does not hold, the remedy outside
    `col.REMEDIES`, the date that is not ISO text — because a forbearance the
    rules cannot book must say what it was asked for rather than answer a row
    nobody can defend.
    """


def eligible(book, loan, at, remedy):
    raise NotImplementedError("stage 69: implement eligible()")























def terms(remedy):
    raise NotImplementedError("stage 94: implement terms()")


















def probation(certifies):
    """The probation record for a forbearance grant.

    Given the grant date and the remedy, returns the probation record with the
    start date, the end date (start + `CURE_MONTHS`), the length, and the
    cure requirement (`CURE_MONTHS` months from the signalled default).

    A grant date that is not ISO text is refused by name.
    """
    _day(certifies["granted_on"])
    granted_on = certifies["granted_on"]
    probation_months = certifies.get("probation_months", rules.CURE_MONTHS)
    probation_until = dates.add_months(granted_on, probation_months)
    return {
        "start": granted_on,
        "end": probation_until,
        "length_months": probation_months,
        "cure_requirement": rules.CURE_MONTHS,
    }


# --- private helpers --------------------------------------------------------

def _resolve(book, loan, remedy):
    """Validate loan and remedy exist, refusing by name."""
    if isinstance(loan, dict):
        name = loan.get("loan", loan.get("id"))
    else:
        name = loan
    if not name:
        raise ForbearanceError("the loan argument carries no name")
    for record in book.loans():
        if record.get("loan") == name or record.get("id") == name:
            return record
    raise ForbearanceError("the book holds no loan %r" % (name,))


def _day(value):
    """Check the day is ISO text, refusing by name."""
    if not isinstance(value, str):
        raise ForbearanceError("the day %r is a %s, not ISO text" % (value, type(value).__name__))
    try:
        dates.parse(value)
    except Exception as error:
        raise ForbearanceError("the day %r is not readable: %s" % (value, error))
    return value


def _remedy_record(remedy_name):
    """One remedy from the world's REMEDIES, or the refusal naming it."""
    for r in col.REMEDIES:
        if r["remedy"] == remedy_name:
            return r
    raise ForbearanceError(
        "the remedy %r is not one of the world's remedies %r"
        % (remedy_name, tuple(r["remedy"] for r in col.REMEDIES)))


def _flag_states(book, record, day):
    """The flags one remedy's eligibility answers at `day`, per the pinned rules."""
    loan_id = record["loan"]
    lens = col._LoanLens(book, record)

    # arrears-material
    arrears = lens.arrears(day)
    drawn = lens.drawn(day)
    flags = {
        "arrears-material": (
            arrears >= rules.MATERIALITY_ABSOLUTE_CENTS
            and arrears * rules.DISCOUNT_SCALE
            >= rules.MATERIALITY_RELATIVE_BP * drawn),
    }

    # no-forbearance-standing
    standing = []
    for event in lens.events:
        if event["kind"] == "forbearance" and event["date"] < day:
            standing.append(event)
    flags["no-forbearance-standing"] = not standing

    # not-defaulted
    defaulted_earlier = any(row["signalled_on"] < day
                            for row in lens.defaults)
    flags["not-defaulted"] = (not defaulted_earlier
                              and lens.dpd(day) < rules.DEFAULT_DAYS_PAST_DUE
                              and not lens.flags_at(day))

    # not-written-off
    flags["not-written-off"] = lens.write_off is None or lens.write_off > day

    # instalments-remaining
    flags["instalments-remaining"] = any(due > day for due, _amount in lens.dues)

    return flags


if __name__ == "__main__":
    book = book_module.Book.build(7)
    print("stage 4 — forbearance eligibility")
    for loan_name in ("L-01", "L-02", "L-07", "L-08"):
        for remedy_name in ("restructure", "term-extension", "capitalisation"):
            try:
                elig, flags = eligible(book, loan_name, "2032-01-01", remedy_name)
                status = "eligible" if elig else "not eligible"
                print("  %-5s %-15s %s" % (loan_name, remedy_name, status))
                if not elig:
                    failed = [k for k, v in flags.items() if not v]
                    print("        failed flags: %s" % ", ".join(failed))
            except ForbearanceError as error:
                print("  %-5s %-15s refused: %s" % (loan_name, remedy_name, error))
    print()
    print("  terms:")
    for r in col.REMEDIES:
        t = terms(r["remedy"])
        print("        %-15s probation=%d months %s"
              % (t["remedy"], t["probation_months"], t["description"]))
