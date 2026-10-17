"""Credit Lifecycle From Scratch — stage 2: The bucket, the materiality threshold and the new definition of default.

The bank holds a contractual schedule per loan and a ledger of what was actually paid
against it. This stage turns the two into the delinquency answer a supervisor asks for:
the days past due counted from the oldest due the instalments have not covered and only
when the arrears clear both halves of the policy's materiality test, the bucket those
days fall in, the ordered triggers that make the loan a default, and the defaults the
book signalled with the probation that decides whether a cure counted. The days are the
world's own calendar, the arrears are the book's own reading of its ledger, and a
default the bank signalled still stands at zero days.
"""

import dates
import rules

BUCKET_KEYS = ("loan", "date", "dpd", "bucket", "arrears_cents", "material", "triggers")

DEFAULT_KEYS = ("loan", "signalled_on", "triggers", "cured_on", "probation_until")

BUCKETS = ("performing", "1-30", "31-60", "61-90", "default")

UTP_FLAGS = ("forbearance", "distressed-restructuring", "cross-default", "bankruptcy")

#: The backstop's own name in a trigger tuple: it is not a `UTP_FLAGS` event, it is
#: the days count crossing `rules.DEFAULT_DAYS_PAST_DUE`.
_DAYS_PAST_DUE = "days-past-due"


def _identify(book_, loan):
    """The book's own record for `loan`, or the refusal naming what arrived.

    The book's lookup door resolves a record or an id and refuses an unknown loan by
    name **before** it writes a line of its ledger, so a refused call still leaves the
    book's `stats()` untouched.
    """
    return book_.loan(loan)


def _cures(book_, loan):
    """Every `cure` event date the loan carries, oldest first."""
    return tuple(sorted(event["date"] for event in book_.events(loan)
                        if event["kind"] == "cure"))


def _cured_on(book_, loan, probation_until):
    """The first cure at or after `probation_until`, or `None` when none survives it."""
    for cured in _cures(book_, loan):
        if cured >= probation_until:
            return cured
    return None


def _windows(book_, loan):
    """The loan's signalled defaults as `(signalled_on, probation_until, cured_on)`.

    The book records which defaults were signalled and when; the probation and the valid
    cure are this stage's arithmetic on top of that record. Sorted by `signalled_on`, so
    a loan that defaulted twice answers its windows in the order they happened.
    """
    windows = []
    for recorded in book_.defaults():
        if recorded["loan"] != loan["loan"]:
            continue
        signalled_on = recorded["signalled_on"]
        probation_until = dates.add_months(signalled_on, rules.CURE_MONTHS)
        windows.append((signalled_on, probation_until,
                        _cured_on(book_, loan, probation_until)))
    windows.sort()
    return tuple(windows)


def _cleared(book_, loan, date):
    """The latest valid cure at or before `date`, or `None` when none has landed.

    A cure clears every flag raised before it, so the only cure that matters at a date is
    the latest one that has landed by then.
    """
    latest = None
    for _signalled_on, _probation_until, cured in _windows(book_, loan):
        if cured is not None and cured <= date and (latest is None or cured > latest):
            latest = cured
    return latest


def _flags(book_, loan, date):
    """The policy flags standing at `date`: raised by an event, not cleared by a cure."""
    cleared = _cleared(book_, loan, date)
    standing = set()
    for event in book_.events(loan):
        if event["date"] > date or event["kind"] not in UTP_FLAGS:
            continue
        if cleared is None or event["date"] > cleared:
            standing.add(event["kind"])
    return standing


def _named(days, flags):
    """A trigger tuple: the backstop first when it is crossed, then the flags in order."""
    named = []
    if days >= rules.DEFAULT_DAYS_PAST_DUE:
        named.append(_DAYS_PAST_DUE)
    for flag in UTP_FLAGS:
        if flag in flags:
            named.append(flag)
    return tuple(named)


def _picture(book_, loan, date):
    """The exposure, the oldest uncovered due and the arrears at `date`.

    The instalment payments are matched to the dues they name: a due is uncovered while
    the payments booked against it on or before the date do not cover it, and the oldest
    such due is the one the days run from. The exposure is every instalment paid by the
    date less what was prepaid, floored at zero, because a prepayment returns money
    rather than covering an instalment. `None` is the oldest due when nothing is
    uncovered.
    """
    covered = {}
    paid = 0
    prepaid = 0
    for payment in book_.payments(loan):
        if payment["paid_on"] > date:
            continue
        if payment["kind"] == "instalment":
            paid = paid + payment["amount_cents"]
            covered[payment["due"]] = covered.get(payment["due"], 0) \
                + payment["amount_cents"]
        elif payment["kind"] == "prepayment":
            prepaid = prepaid + payment["amount_cents"]
    exposure = paid - prepaid
    if exposure < 0:
        exposure = 0
    owed = 0
    matched = 0
    oldest = None
    for flow in book_.schedule(loan)["flows"]:
        if flow["date"] > date:
            break
        owed = owed + flow["amount_cents"]
        matched = matched + covered.get(flow["date"], 0)
        if oldest is None and covered.get(flow["date"], 0) < flow["amount_cents"]:
            oldest = flow["date"]
    arrears = owed - matched
    if arrears < 0:
        arrears = 0
    return exposure, oldest, arrears


def _material(arrears, exposure):
    """The policy's own two-part test: both halves have to hold, or the days do not count."""
    if arrears < rules.MATERIALITY_ABSOLUTE_CENTS:
        return False
    return arrears * rules.DISCOUNT_SCALE >= exposure * rules.MATERIALITY_RELATIVE_BP


def _days(book_, loan, date):
    """The materially unpaid days at `date`: zero unless arrears clear both halves."""
    exposure, oldest, arrears = _picture(book_, loan, date)
    if oldest is None or not _material(arrears, exposure):
        return 0
    return dates.days_between(oldest, date)


def _standing(book_, loan, date):
    """True while a signalled default of the loan has no valid cure yet.

    A default the bank signalled speaks even at zero days past due: it is in the default
    bucket until a cure at or after its probation lands, whatever the arrears and the
    flags say in between.
    """
    for signalled_on, _probation_until, cured_on in _windows(book_, loan):
        if cured_on is None and signalled_on <= date:
            return True
    return False


def _bucket_name(days, defaulted):
    """`BUCKET_DAYS` walked in order, with the default bucket speaking for a default."""
    if defaulted:
        return BUCKETS[-1]
    for upper, name in zip(rules.BUCKET_DAYS, BUCKETS):
        if days <= upper:
            return name
    return BUCKETS[-1]


def dpd(book_, loan, date):
    """The days from the oldest materially unpaid instalment to `date`.

    An instalment is uncovered while the instalment payments received by `date` do not
    cover the schedule up to it, and the arrears those payments leave behind are material
    when they are at least `MATERIALITY_ABSOLUTE_CENTS` **and** at least
    `MATERIALITY_RELATIVE_BP` of the drawn balance. Arrears below either half leave the
    days at zero. A loan the book does not hold raises `BookError` naming it.
    """
    return _days(book_, _identify(book_, loan), date)


def bucket(book_, loan, date):
    """The delinquency bucket of `loan` at `date`, with the arrears that put it there.

    `BUCKET_KEYS` in order: the loan, the date, the days, the bucket `BUCKET_DAYS` maps
    those days to, the arrears the days were measured against, whether those arrears
    cleared the policy's two-part test, and the triggers that make the loan a default.
    The bucket is `"default"` whenever the loan is a default — a trigger holds, or a
    default the bank signalled has not validly cured — so a signalled default speaks at
    zero days.
    """
    held = _identify(book_, loan)
    exposure, oldest, arrears = _picture(book_, held, date)
    material = _material(arrears, exposure)
    days = dates.days_between(oldest, date) if oldest is not None and material else 0
    named = _named(days, _flags(book_, held, date))
    defaulted = bool(named) or _standing(book_, held, date)
    return {"loan": held["loan"], "date": date, "dpd": days,
            "bucket": _bucket_name(days, defaulted), "arrears_cents": arrears,
            "material": material, "triggers": named}


def triggers(book_, loan, date):
    """What makes `loan` a default at `date`, in `UTP_FLAGS` order under the backstop.

    `days-past-due` first when the days reach `DEFAULT_DAYS_PAST_DUE`, then every policy
    flag an event raised by the date and no valid cure has cleared. An empty tuple is the
    verdict that the loan is not a default.
    """
    held = _identify(book_, loan)
    return _named(_days(book_, held, date), _flags(book_, held, date))


def defaults(book_):
    """Every default the book records, with the probation that decides its cure.

    `DEFAULT_KEYS` in order: the loan, the date it was signalled,
    `probation_until = add_months(signalled_on, CURE_MONTHS)`, and `cured_on` — the first
    cure event at or after the probation, or `None` while the default still stands.
    """
    answers = []
    for recorded in book_.defaults():
        held = _identify(book_, recorded)
        signalled_on = recorded["signalled_on"]
        probation_until = dates.add_months(signalled_on, rules.CURE_MONTHS)
        answers.append({"loan": held["loan"], "signalled_on": signalled_on,
                        "triggers": triggers(book_, held, signalled_on),
                        "cured_on": _cured_on(book_, held, probation_until),
                        "probation_until": probation_until})
    return tuple(answers)
