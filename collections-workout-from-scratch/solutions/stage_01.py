"""Collections Workout From Scratch — stage 1: Days past due and the delinquency state.

Every later stage of this course acts on a loan's delinquency — the pyramid of
stage 2, the replay of stage 3, the forbearance of stage 4 all read the days
past due first — so this stage has to answer the one question all of them stand
on: how far past due is this loan at this day, under a policy that refuses to
let trivial shortfalls accrue a single day?

The book keeps a payment ledger, not a status row, so the stage re-derives the
delinquency from the raw facts: the instalments the schedule says are due by the
day, the instalment rows the borrower actually paid against those dues by the
day, and the difference — the covered-arrears view, floored at zero. Then comes
the policy's own gate before a day can accrue: the materiality test, two halves
(`rules.MATERIALITY_ABSOLUTE_CENTS` against the arrears, and the same arrears in
basis points of the drawn exposure), BOTH of which must pass. A loan whose
arrears sit under the absolute floor accrues no days however long they have been
sitting there, and neither does one under 1% of its exposure — the bank counts
neither an anecdote nor pocket-change arrears as a delinquency.

The days past due are then the distance from the oldest *materially* short
instalment to the day itself — `rules.BUCKET_DAYS` walk the count through the
buckets, and the record this stage answers names one more thing the bucket needs
to know: that the borrower has already been referred to the workout desk, is
under a forbearance probation, is signalled defaulted or has been written off.
The stage reads that state from the bank's own records — the walk's action log
and the bank's signalling — and echoes the rule it bucketed under, because a
delinquency record nobody can trace back to the rule that made it is a number
nobody can defend.

    DelinquencyError             the refusal this stage raises
    STATE_KEYS                   the nine fields of a delinquency state, in order
    BUCKET_RULE                  the rule text every state record carries
    dpd(book, loan, at)          -> the days past due at `at`, ledger-derived
    state(book, loan, at)        -> STATE_KEYS: the loan's delinquency state

DESIGN DECISION — why is `dpd` re-derived from the ledger rather than read from
the bank's status rows?
Because the statuses are the ANSWER KEY and the stage is the mechanism: the bank
records a `dpd` per reporting date and this stage must be able to say the same
number for a reporting date from the raw facts alone, and something for a day
between reportings that no status row was ever kept on. The re-derivation walks
the same arithmetic the bank's own walk keeps — covered-arrears, drawn
exposure, oldest short instalment — and never reads `book.status`. A stage that
copies the status row agrees with the bank until the bank changes its walk and
never learns why.

DESIGN DECISION — why does a day past due require BOTH halves of the
materiality test?
Because the policy says so, and because each half alone would answer wrong on a
real loan: L-05's arrears are real money to its borrower but sit under the
absolute floor's cousin — they are small enough that the arithmetic materiality
floor refuses them, so they accrue no days ever; and a large loan's single short
instalment can be a large README number while still under 1% of its drawn
exposure, so a stage that takes the absolute half alone would bucket a loan the
bank holds performing. The bank's own statuses are the answer key, and they
agree with this stage exactly on every reporting date.

DESIGN DECISION — why does the state record carry a rule text?
Because a bucket is a claim about a rule, and the claim says which rule: the
buckets are `dpd` walked through `rules.BUCKET_DAYS`, and a signalled default
speaks at zero days rather than borrowing the arithmetic. A record that mixes
the two — bucketed by `dpd` when a default was standing, or defaulted only
because a bucket hit its wall — answers a different question than the bank was
asked, and the bank's own records say which one it was.

DESIGN DECISION — why does the stage read the walk's log for referral and the
book's events for everything else?
Because the two records are the two institutions that produced them: the
referral is the workout desk's own act, on its own log, and every other piece of
state — defaults, cures, forbearances, write-offs — is the credit walk's, on the
book's events. No other source has either, and a stage reading one for the other
would answer "referred" for a loan the desk never touched, or miss a
write-off the bank booked.

DESIGN DECISION — why does the stage answer for any day, not just reporting
dates?
Because the pyramid's steps fire on the day a trigger is reached, not on a
reporting date, and the desk's own arithmetic — the docstring of the provided
world's `workout.py` — walks day by day. A delinquency stage that only said
something on month ends would leave the pyramid's trigger days unanswerable.

TODO: implement `DelinquencyError`, `dpd` and `state` in this file: the ledger
re-derivation of the materiality-tested days past due, and the nine-field state
record that names the bucket rule it used.

    A loan is refused by name when the book does not hold it, and a day is
    refused by name when it is not ISO text.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import workout as col
import dates
import rules

STATE_KEYS = ("loan", "at", "dpd", "bucket", "referred", "forborne",
              "defaulted", "written_off", "rule")

BUCKET_RULE = "dpd through the policy's buckets; a standing default speaks at zero"


class DelinquencyError(ValueError):
    """The refusal this stage raises: something that cannot be a delinquency.

    It names the offender — the loan the book does not hold, the day that is not
    ISO text — because a delinquency the ledger cannot answer must say what it
    was asked for rather than answer a number nobody can defend.
    """


def dpd(book, loan, at):
    """The days past due at `at`, re-derived from the loan's payment ledger.

    The covered-arrears view at `at` is what the schedule is owed by then less
    what the borrower paid against those dues by then, floored at zero; the
    drawn exposure is what the borrower has paid in instalments less what it has
    pre-paid. The policy's materiality test must pass twice over — the arrears
    at or above `rules.MATERIALITY_ABSOLUTE_CENTS`, and the same arrears at or
    above `rules.MATERIALITY_RELATIVE_BP` basis points of the drawn exposure —
    before a single day accrues. The count is then the distance from the oldest
    instalment still materially short at `at`.

    A day that fails either half answers zero; there is no negative `dpd`. A
    loan the book does not hold, or a day that is not ISO text, is refused by
    name.
    """
    record = _resolve(book, loan)
    day = _day(at)
    flows, payments = _loan_history(book, record)
    ref = _reference_due(flows, payments, day)
    if ref is None:
        return 0
    arrears = _arrears_at(flows, payments, day)
    if arrears < rules.MATERIALITY_ABSOLUTE_CENTS:
        return 0
    if arrears * rules.DISCOUNT_SCALE \
            < rules.MATERIALITY_RELATIVE_BP * _drawn_at(payments, day):
        return 0
    return dates.days_between(ref, day)


def state(book, loan, at):
    """The loan's own delinquency state at `at`, every part naming its source.

    The record carries the materiality-tested `dpd`, the bucket `dpd` walks
    through — but a default standing at `at` speaks at zero and takes the
    bucket — and the four standing facts the bank's own records hold: whether
    the desk has referred the loan by then, whether a forbearance probation
    stands, whether the walk holds the loan defaulted, and whether the book has
    written it off. `rule` echoes `BUCKET_RULE`, the rule the bucket claims.

    A loan the book does not hold, or a day that is not ISO text, is refused by
    name.
    """
    record = _resolve(book, loan)
    day = _day(at)
    dpd_answer = dpd(book, loan, day)
    defaults = tuple(row for row in book.defaults() if row["loan"] == _loan_id(record))
    defaulted = _defaulted_at(book, record, defaults, day, dpd_answer)
    if defaulted:
        bucket = "default"
    else:
        bucket = _bucket(dpd_answer)
    return {"loan": _loan_id(record),
            "at": day,
            "dpd": dpd_answer,
            "bucket": bucket,
            "referred": _referred_at(_loan_id(record), day),
            "forborne": _forborne_at(book, record, day),
            "defaulted": defaulted,
            "written_off": _written_off_at(book, record, day),
            "rule": BUCKET_RULE}


# --- the machinery, private to this stage -------------------------------------


def _resolve(book, loan):
    """One loan's record, from an id or a record, or the refusal naming it."""
    if isinstance(loan, dict):
        name = loan.get("loan", loan.get("id"))
    else:
        name = loan
    found = None
    for record in book.loans():
        if _loan_id(record) == name:
            found = record
    if found is None:
        raise DelinquencyError("the book holds no loan %r" % (name,))
    return found


def _loan_id(record):
    """The record's loan id, whatever shape arrived."""
    if isinstance(record, dict):
        return record.get("loan", record.get("id"))
    return record


def _day(value):
    """A check that the day is ISO text, or the refusal naming what arrived."""
    if not isinstance(value, str):
        raise DelinquencyError("the day %r is a %s, not ISO text"
                               % (value, type(value).__name__))
    try:
        dates.parse(value)
    except Exception as error:
        raise DelinquencyError("the day %r is not readable: %s" % (value, error))
    return value


def _loan_history(book, record):
    """The loan's dues and its payment rows, in the shapes the walk reads."""
    schedule = book.schedule(record)
    flows = tuple((flow["date"], flow["amount_cents"])
                  for flow in schedule["flows"])
    payments = tuple(book.payments(record))
    return flows, payments


def _arrears_at(flows, payments, day):
    """The covered-arrears view at `day`: owed less paid against those dues."""
    owed = 0
    covered = 0
    for due, amount in flows:
        if due > day:
            break
        owed = owed + amount
        for row in payments:
            if row["kind"] == "instalment" and row["due"] == due \
                    and row["paid_on"] <= day:
                covered = covered + row["amount_cents"]
    return owed - covered if owed >= covered else 0


def _drawn_at(payments, day):
    """The drawn exposure at `day`: instalments paid less prepayments."""
    instalments = 0
    prepaid = 0
    for row in payments:
        if row["paid_on"] > day:
            break
        if row["kind"] == "instalment":
            instalments = instalments + row["amount_cents"]
        elif row["kind"] == "prepayment":
            prepaid = prepaid + row["amount_cents"]
    return instalments - prepaid if instalments >= prepaid else 0


def _reference_due(flows, payments, day):
    """The oldest instalment still short at `day`, or `None`."""
    for due, amount in flows:
        if due > day:
            return None
        paid = 0
        for row in payments:
            if row["kind"] == "instalment" and row["due"] == due \
                    and row["paid_on"] <= day:
                paid = paid + row["amount_cents"]
        if paid < amount:
            return due
    return None


def _bucket(dpd_answer):
    """`dpd` walked through `rules.BUCKET_DAYS`, the policy's own buckets."""
    for index, bound in enumerate(rules.BUCKET_DAYS):
        if dpd_answer <= bound:
            return rules.BUCKETS[index]
    return rules.BUCKETS[-1]


def _defaulted_at(book, record, defaults, day, dpd_answer):
    """Whether the loan is defaulted at `day`, on the bank's own walk's terms.

    A default is standing when the bank signalled one and it has not validly
    cured, when the `dpd` has reached the backstop, or when an uncured UTP flag
    event stands — the three triggers the bank's own walk reads.
    """
    if dpd_answer >= rules.DEFAULT_DAYS_PAST_DUE:
        return True
    for row in defaults:
        if row["signalled_on"] <= day \
                and (row["cured_on"] is None or row["cured_on"] > day):
            return True
    return _flags_standing(book, record, day)


def _flags_standing(book, record, day):
    """The loan's UTP flag events standing at `day`, uncured."""
    events = tuple(book.events(record))
    cures = tuple(row["cured_on"] for row in book.defaults()
                  if row["loan"] == _loan_id(record) and row["cured_on"] is not None)
    for event in events:
        if event["kind"] in rules.UTP_FLAGS and event["date"] <= day:
            cleared = False
            for cured in cures:
                if event["date"] < cured <= day:
                    cleared = True
            if not cleared:
                return True
    return False


def _referred_at(loan_id, day):
    """Whether the workout desk has referred the loan by `day`."""
    return any(row["action"] == "workout-referral" and row["date"] <= day
               for row in col.log_of(loan_id))


def _forborne_at(book, record, day):
    """Whether a forbearance probation stands at `day`: granted on or before it,
    running for the length the remedies carry."""
    for event in book.events(record):
        if event["kind"] == "forbearance" and event["date"] <= day:
            until = dates.add_months(event["date"], rules.CURE_MONTHS)
            if day < until:
                return True
    return False


def _written_off_at(book, record, day):
    """Whether the bank has written the loan off by `day`."""
    for event in book.events(record):
        if event["kind"] == "write-off" and event["date"] <= day:
            return True
    return False


if __name__ == "__main__":
    import book as book_module
    the_book = book_module.Book.build(7)
    print("stage 1 — the delinquency states")
    for loan_name in ("L-05", "L-06", "L-07", "L-11"):
        for day in ("2031-04-07", "2031-11-30", "2032-03-31"):
            try:
                row = state(the_book, loan_name, day)
            except DelinquencyError as error:
                print("  %-5s %s refused: %s" % (loan_name, day, error))
                continue
            print("  %-5s %s dpd=%-4d %-13s referred=%-5s forborne=%-5s "
                  "defaulted=%-5s written_off=%s"
                  % (loan_name, day, row["dpd"], row["bucket"],
                     row["referred"], row["forborne"], row["defaulted"],
                     row["written_off"]))
