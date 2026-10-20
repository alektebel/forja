"""dates.py — the calendar the book's dates live on.

Provided, frozen, and never written by the course. Dates are ISO strings
(`"2031-03-31"`), and nothing here reads a clock: every reporting date in this
course comes from the book, not from the machine.

Two things about this calendar are worth naming before anything else:

* **The clamping rule.** `add_months("2031-01-31", 1)` is `"2031-02-28"`, not an
  error and not `"2031-03-03"`: a day that does not exist in the target month is
  clamped to that month's last day. Every "the month-ends after the first due
  date" in this course is that rule, and a stage that re-implements it locally
  will disagree with the contract's own schedule the first time a 31st meets a
  30-day month.
* **The day count.** `day_count(start, end, basis)` is the two conventions the
  policy knows: `actual-365` counts the real days between two dates, and
  `thirty-360` counts every month as thirty days. They are different numbers for
  the same pair of dates, which is the whole point of asking for a basis.

The Gregorian rule this module follows is the one the contract pinned: a year
divisible by four is a leap year. (Under the full Gregorian rule a century
divisible by 400 is not a leap year, but no date this course touches is near
one, and the contract said four.)

A shape this module cannot accept — a text that is not a date, a month outside
`1..12`, a day outside its month, a basis outside `BASES`, a `months` that is not
a whole number — raises `DateError` **naming the offender**, and never answers a
plausible-looking wrong date.
"""

BASES = ("actual-365", "thirty-360")

DATE_ERROR = "dates: "

_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

#: Cumulative days before the first of each month, in a common year.
_MONTH_START = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)

_THIRTY_360_DAYS = 30

_YEAR_DAYS = 365

_MONTHS = 12


class DateError(ValueError):
    """The calendar's refusal: a text, a month, a day or a basis it cannot accept."""


def _leap(year):
    """Whether `year` is a leap year: divisible by four, as the contract pinned."""
    return year % 4 == 0


def days_in_month(year, month):
    """How many days `month` of `year` has — `28` or `29` for a February."""
    if month == 2 and _leap(year):
        return _MONTH_DAYS[1] + 1
    return _MONTH_DAYS[month - 1]


def _whole(value, what):
    """A whole number, and a `bool` is not one here."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise DateError(DATE_ERROR + ("%s is a %s, not a whole number"
                                      % (what, type(value).__name__)))
    return value


def _text(date, what):
    """A date-shaped text, or the refusal naming what arrived."""
    if not isinstance(date, str):
        raise DateError(DATE_ERROR + ("%s is a %s, not a date text"
                                      % (what, type(date).__name__)))
    return date


def parse(date):
    """The `(year, month, day)` of an ISO date text; a bad text is refused by name.

    The text is exactly `YYYY-MM-DD`: four digits, a hyphen, two digits, a hyphen,
    two digits, and a date that exists — `"2031-02-29"` is refused because 2031 is
    not a leap year, and `"2031-13-01"` because there is no thirteenth month.
    """
    text = _text(date, "the date")
    parts = text.split("-")
    if len(parts) != 3 or [len(part) for part in parts] != [4, 2, 2] \
            or not all(part.isdigit() for part in parts):
        raise DateError(DATE_ERROR + ("%r is not a date of the form YYYY-MM-DD"
                                      % (text,)))
    year, month, day = (int(part) for part in parts)
    if month < 1 or month > _MONTHS:
        raise DateError(DATE_ERROR + ("%r names month %d, which does not exist"
                                      % (text, month)))
    if day < 1 or day > days_in_month(year, month):
        raise DateError(DATE_ERROR + ("%r names day %d of a month of %d days"
                                      % (text, day, days_in_month(year, month))))
    return year, month, day


def iso(year, month, day):
    """The zero-padded ISO text of a date that exists; anything else is refused."""
    _whole(year, "the year")
    _whole(month, "the month")
    _whole(day, "the day")
    if year < 1 or month < 1 or month > _MONTHS:
        raise DateError(DATE_ERROR + ("%04d-%02d-%02d is not a year and a month"
                                      % (year, month, day)))
    if day < 1 or day > days_in_month(year, month):
        raise DateError(DATE_ERROR + ("%04d-%02d-%02d names a day that month does "
                                      "not have" % (year, month, day)))
    return "%04d-%02d-%02d" % (year, month, day)


def month_end(date):
    """The last day of `date`'s own month, as an ISO text."""
    year, month, _day = parse(date)
    return iso(year, month, days_in_month(year, month))


def add_months(date, months):
    """`date` moved by `months` months, its day **clamped to the target month's last**.

    `add_months("2031-01-31", 1)` is `"2031-02-28"`: January's 31st does not exist
    in February, so it becomes February's last day. A negative `months` walks
    backwards by the same rule. `months` is a whole number (zero answers the date
    unchanged), and anything else is refused by name.
    """
    year, month, day = parse(date)
    step = _whole(months, "the months")
    index = (year * _MONTHS + (month - 1)) + step
    year, month = divmod(index, _MONTHS)
    month = month + 1
    if year < 1:
        raise DateError(DATE_ERROR + ("%r moved by %d months leaves the calendar"
                                      % (date, step)))
    return iso(year, month, min(day, days_in_month(year, month)))


def _ordinal(date):
    """The day number of `date` on a proleptic Gregorian calendar — the count of
    days since `0001-01-01`, which is day `1`."""
    year, month, day = parse(date)
    days = _YEAR_DAYS * (year - 1) + (year - 1) // 4 + _MONTH_START[month - 1] + day
    if month > 2 and _leap(year):
        days = days + 1
    return days


def days_between(start, end):
    """The actual days from `start` to `end` — negative when `end` is the earlier.

    A year divisible by four is a leap year here (the contract's own rule), so
    `2032-02-29` exists and February 2032 has twenty-nine days.
    """
    return _ordinal(end) - _ordinal(start)


def day_count(start, end, basis):
    """The days between two dates under one of the two conventions in `BASES`.

    `actual-365` is the real count (`days_between`). `thirty-360` counts every
    month as thirty days:
    `360 * (y2 - y1) + 30 * (m2 - m1) + min(d2, 30) - min(d1, 30)`.
    A basis outside `BASES` is refused by name, never defaulted.
    """
    if basis not in BASES:
        raise DateError(DATE_ERROR + ("%r is not one of the bases %r"
                                      % (basis, BASES)))
    if basis == "actual-365":
        return days_between(start, end)
    year, month, day = parse(start)
    other_year, other_month, other_day = parse(end)
    return (_THIRTY_360_DAYS * _MONTHS * (other_year - year)
            + _THIRTY_360_DAYS * (other_month - month)
            + min(other_day, _THIRTY_360_DAYS) - min(day, _THIRTY_360_DAYS))


def month_ends(start, end):
    """Every month end from `start`'s month to `end`'s month, inclusive, in order.

    Each entry is the last day of its month, so `month_ends("2031-01-15",
    "2031-03-31")` is `("2031-01-31", "2031-02-28", "2031-03-31")`. A range that
    runs backwards answers the empty tuple: there is nothing between the two
    months to walk.
    """
    year, month, _day = parse(start)
    other_year, other_month, _other_day = parse(end)
    if (year, month) > (other_year, other_month):
        return ()
    ends = []
    while (year, month) <= (other_year, other_month):
        ends.append(iso(year, month, days_in_month(year, month)))
        month = month + 1
        if month > _MONTHS:
            year, month = year + 1, 1
    return tuple(ends)
