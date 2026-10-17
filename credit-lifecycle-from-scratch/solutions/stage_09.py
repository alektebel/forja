"""Credit Lifecycle From Scratch — stage 9: The reporting pack and the reconciliation that holds it.

The pack is the bank's own disclosure, and the only thing that makes it worth
anything is that it is *recomputable*: every loan the book records at the date
becomes one line — its stage, its grade, its bucket, its segment, its exposure
and its provision — and every cell of every dimension is those lines aggregated.
Nothing in the pack is a number of its own, which is exactly why a reconciliation
can hold it: the detail is printed beside the totals, so a cell that does not add
up to its own lines is a finding rather than an opinion.

`vintage` is the cohort view (origination month against stage), the pack's
`migration` is the stage movement over the last year on the same counts-and-rates
shape stage 3 uses, the `forbearance` block is the flagged subset reported beside
the dimensions rather than instead of them, and every coverage ratio is the
provision over the exposure in basis points — truncated, and zero where there is
no exposure, because a ratio whose denominator is nothing is not a ratio.

`reconcile` is the scanner. It walks the pack's lines against the book's own
records, names the loan (or the cell) each problem belongs to, and answers its
problems in `PACK_PROBLEMS` order rather than stopping at the first one: a pack
this stage built scans to `()`, and a hand-broken one is named, not trusted.
"""

import dates
import rules
import stage_02
import stage_05
import stage_06
import stage_07
from book import BookError

PACK_KEYS = ("date", "lines", "exposures", "ecl", "coverage_bp", "by_stage",
             "by_grade", "by_bucket", "by_segment", "forbearance", "vintage",
             "migration")

PACK_PROBLEMS = ("missing-loan", "double-counted", "coverage-mismatch",
                 "stage-mismatch", "total-mismatch")

#: The seven fields of one line of the pack, in the order a line is printed in.
_LINE_KEYS = ("loan", "stage", "grade", "bucket", "segment", "exposure_cents",
              "ecl_cents")

#: The four dimensions: each one's name, the record slot it keys on, and the
#: rulebook's own order for its keys (the stages have no rulebook tuple; they are
#: ordered by their own value).
_DIMENSIONS = (("by_stage", 1, None),
               ("by_grade", 2, rules.GRADES),
               ("by_bucket", 3, rules.BUCKETS),
               ("by_segment", 4, rules.SEGMENTS))

#: The cell-bearing parts of a pack that carry a coverage ratio of their own.
_COVERED = ("by_stage", "by_grade", "by_bucket", "by_segment")


def _coverage(ecl_cents, exposure_cents):
    """The coverage ratio in basis points: the loss over the exposure, truncated.

    A cell with no exposure answers `0` rather than dividing by nothing: an empty
    cohort's coverage is not zero per cent, it is a ratio that does not exist, and
    the pack's own convention is to book it as `0`.
    """
    if exposure_cents == 0:
        return 0
    return ecl_cents * 10000 // exposure_cents


def _month(date):
    """The origination month a cohort is keyed by, read off the world's calendar."""
    year, month, _day = dates.parse(date)
    return "%04d-%02d" % (year, month)


def _stage_rank(stage):
    """The order the stages are printed in: by their own value, whatever it is."""
    if isinstance(stage, int):
        return (0, stage, "")
    return (1, 0, str(stage))


def _rank(key, order):
    """Where a dimension's key sits: the rulebook's order, unknown keys last."""
    if order is None:
        return _stage_rank(key)
    for place, known in enumerate(order):
        if known == key:
            return (0, place, "")
    return (1, 0, str(key))


def _ordered(keys, order):
    """A dimension's keys, in the dimension's own order and never the book's."""
    return tuple(sorted(keys, key=lambda key: _rank(key, order)))


def _population(book, date):
    """The loans on the bank's book at `date`: the world's own liveness rule.

    A loan is on the book once it has originated and until it is written off, and
    `on_book` is where the world says which. The pack asks that and never
    `status`: the bank's own status row answers for every date (before an
    origination and after a write-off too), so it is not a liveness test, and a
    pack that counted a written-off loan would report an exposure the bank no
    longer has. The ids come back in the book's own loan order, so every
    dimension prints in the same sequence.
    """
    try:
        return tuple(book.on_book(date))
    except BookError:
        return ()


def _require_date(book, date):
    """The date must be one the book reports at, or the offender is named."""
    if date not in book.reporting_dates:
        raise BookError("stage 9: the book does not report at %r" % (date,))
    return date


def _records(book, date):
    """One record per loan the book records at `date`, in the book's loan order.

    The record is everything the pack says about a loan — the loan's id, its
    stage, its grade, its bucket, its segment, its exposure and its provision —
    plus the origination the cohort matrix needs, so that the whole pack is built
    from one pass over the book. The stage is stage 7's answer, the bucket stage
    2's, the exposure stage 5's and the provision stage 6's, because a reporting
    pack that re-derived any of them would be a second implementation of the same
    policy rather than a report of it. The grade is the bank's own recorded grade
    at the date, which is the grade a migration and a disclosure both count.
    """
    _require_date(book, date)
    live = set(_population(book, date))
    rows = []
    for loan in book.loans:
        holder = loan["loan"]
        if holder not in live:
            continue
        rows.append((holder,
                     stage_07.stage(book, loan, date)["stage"],
                     book.grade(holder, date),
                     stage_02.bucket(book, loan, date)["bucket"],
                     loan["segment"],
                     stage_05.ead(book, loan, date)["ead_cents"],
                     stage_06.weighted_ecl(book, loan, date)["weighted_cents"],
                     loan["origination"],
                     loan))
    return tuple(rows)


def _aggregate(rows):
    """The cell a set of lines makes: how many, how much exposure, how much loss.

    The coverage is the cell's own loss over the cell's own exposure — never
    another cell's — because that is the arithmetic a reader checking the pack by
    hand performs, and the whole point of printing a ratio is that it can be
    reproduced from the two numbers beside it.
    """
    exposure = sum(row[5] for row in rows)
    ecl = sum(row[6] for row in rows)
    return (len(rows), exposure, ecl, _coverage(ecl, exposure))


def _dimension(rows, slot, order):
    """One dimension of the pack: its cells, keyed and ordered by the dimension.

    `slot` is the record's field this dimension keys on (1 stage, 2 grade, 3
    bucket, 4 segment) and `order` the rulebook's own order for the keys, so the
    same portfolio always prints its rows in the same sequence.
    """
    buckets = {}
    for row in rows:
        key = row[slot]
        if key in buckets:
            buckets[key].append(row)
        else:
            buckets[key] = [row]
    cells = {}
    for key in _ordered(buckets.keys(), order):
        cells[key] = _aggregate(tuple(buckets[key]))
    return cells


def _flagged(book, date, rows):
    """The lines of the loans whose own flags at `date` include a forbearance.

    The subset is stage 2's answer, not a second reading of the events: a flag
    that a `cure` cleared is not a flag, and the pack reports the subset the
    bank's own rulebook would call forborne.
    """
    return tuple(row for row in rows
                 if "forbearance" in stage_02.triggers(book, row[8], date))


def _vintage(rows):
    """The cohort matrix: one row per origination month, one column per stage.

    A row is ordered by the month it originated in and a column by the stage the
    loan sits in at the date, and a cell carries how many loans the cohort holds,
    their exposure, and the cohort's own coverage. Rows are in date order because
    a vintage table read out of order is a table nobody can compare with the
    month before.
    """
    months = {}
    for row in rows:
        month = _month(row[7])
        stage = row[1]
        if month not in months:
            months[month] = {}
        if stage not in months[month]:
            months[month][stage] = []
        months[month][stage].append(row)
    cohorts = {}
    for month in sorted(months):
        cells = {}
        for stage in _ordered(months[month].keys(), None):
            held = tuple(months[month][stage])
            exposure = sum(row[5] for row in held)
            ecl = sum(row[6] for row in held)
            cells[stage] = (len(held), exposure, _coverage(ecl, exposure))
        cohorts[month] = cells
    return cohorts


def _stage_at(book, date):
    """The stage every loan the book holds at a date sits in, by loan id.

    A date the book does not report at is no observation and therefore no
    movement: the migration's window reaches a year back, and a pack at the first
    reporting date of the history would otherwise be asking the book for a date
    it does not have.
    """
    if date not in book.reporting_dates:
        return {}
    live = set(_population(book, date))
    sitting = {}
    for loan in book.loans:
        if loan["loan"] in live:
            sitting[loan["loan"]] = stage_07.stage(book, loan, date)["stage"]
    return sitting


def _migration(book, date):
    """The stage migration of the last year: the counts and their rates in bp.

    The window is the date a year before to the date, and only the loans the book
    records at *both* ends are movements — a loan that arrived or left in between
    is new business or a derecognition, not a transfer. The shape is stage 3's,
    one dimension coarser: the rates are per row and the whole remainder goes to
    the last column (the credit-impaired stage, the coarse analogue of the
    absorbing default), so every row sums to exactly 10000 and a row with no
    loans is the absorb-the-rest row.
    """
    start = dates.add_months(date, -12)
    before = _stage_at(book, start)
    after = _stage_at(book, date)
    counts = {}
    seen = []
    for loan in book.loans:
        holder = loan["loan"]
        if holder in before and holder in after:
            pair = (before[holder], after[holder])
            if pair not in counts:
                counts[pair] = 0
                seen.append(pair)
            counts[pair] = counts[pair] + 1
    stages = _ordered(set(before.values()) | set(after.values()), None)
    row_totals = {}
    rates = {}
    for stage in stages:
        total = sum(counts.get((stage, column), 0) for column in stages)
        row_totals[stage] = total
        row = {}
        running = 0
        for column in stages[:-1]:
            rate = counts.get((stage, column), 0) * 10000 // total if total else 0
            row[column] = rate
            running = running + rate
        row[stages[-1]] = 10000 - running if total else 10000
        rates[stage] = row
    return {"from_date": start, "to_date": date, "stages": stages,
            "counts": counts, "rates_bp": rates, "row_totals": row_totals}


def pack(book, date):
    """The bank's reporting pack at `date`, and every number in it is a line's.

    The pack answers the pack's own keys in order: the date, one line per loan
    the book records at that date (in the book's loan order), the exposure and
    the provision totals, the total's coverage, the four dimensions (stage,
    grade, bucket, segment — each one a dict of key to `("loans",
    "exposure_cents", "ecl_cents", "coverage_bp")`), the forbearance subset
    reported beside the dimensions, the cohort matrix `vintage` answers and the
    stage migration of the last year. The forbearance block is a memo and not a
    fifth dimension: those loans stay in the stage, grade, bucket and segment
    rows, because a subset reported *instead* of the portfolio would make the
    pack's totals a different number from the bank's book.

    A date the book does not report at raises `BookError` naming it; a date with
    no loans on it is answered as an empty pack rather than refused, because an
    empty book is a fact about the period and not a mistake by the caller.
    """
    rows = _records(book, date)
    lines = tuple(row[:len(_LINE_KEYS)] for row in rows)
    exposure = sum(row[5] for row in rows)
    ecl = sum(row[6] for row in rows)
    record = {"date": date, "lines": lines, "exposures": exposure, "ecl": ecl,
              "coverage_bp": _coverage(ecl, exposure)}
    for name, slot, order in _DIMENSIONS:
        record[name] = _dimension(rows, slot, order)
    record["forbearance"] = _aggregate(_flagged(book, date, rows))
    record["vintage"] = _vintage(rows)
    record["migration"] = _migration(book, date)
    return record


def vintage(book, date):
    """The cohort matrix at `date`: origination months against stages.

    One row per origination month, one column per stage the date's loans sit in,
    and each cell `("loans", "exposure_cents", "coverage_bp")`. Rows are in date
    order and columns in the stages' own order, so two months can be compared
    line by line — which is the only reason a bank reports a vintage at all.
    """
    return _vintage(_records(book, date))


def _as_pack(pack):
    """The pack as a record, or `BookError` naming what is not a pack."""
    if not isinstance(pack, dict):
        raise BookError("stage 9: a pack is a record, and %r is not one" % (pack,))
    for key in PACK_KEYS:
        if key not in pack:
            raise BookError("stage 9: the pack has no %r" % (key,))
    return pack


def _as_lines(lines):
    """The pack's lines as seven-field records, or `BookError` naming the offender."""
    if not isinstance(lines, (list, tuple)):
        raise BookError("stage 9: a pack's lines are a sequence, and %r is not"
                        % (lines,))
    out = []
    for place, line in enumerate(lines):
        if not isinstance(line, (list, tuple)) or len(line) != len(_LINE_KEYS):
            raise BookError("stage 9: line %d is not a line: %r" % (place, line))
        out.append(tuple(line))
    return tuple(out)


def _as_cell(cell, what):
    """A four-field cell of a dimension, or `BookError` naming the offender."""
    if not isinstance(cell, (list, tuple)) or len(cell) != 4:
        raise BookError("stage 9: %s is not a cell: %r" % (what, cell))
    for field in cell:
        if not isinstance(field, int) or isinstance(field, bool):
            raise BookError("stage 9: %s holds %r where a count belongs: %r"
                            % (what, field, cell))
    return tuple(cell)


def _as_cohort(cell, what):
    """A three-field cohort cell, or `BookError` naming the offender."""
    if not isinstance(cell, (list, tuple)) or len(cell) != 3:
        raise BookError("stage 9: %s is not a cohort cell: %r" % (what, cell))
    for field in cell:
        if not isinstance(field, int) or isinstance(field, bool):
            raise BookError("stage 9: %s holds %r where a count belongs: %r"
                            % (what, field, cell))
    return tuple(cell)


def _as_number(value, what):
    """A total of the pack as an int, or `BookError` naming the offender."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise BookError("stage 9: %s is not a number of cents: %r" % (what, value))
    return value


def _as_dimension(cells, name):
    """A dimension as a dict of key to cell, or `BookError` naming the offender."""
    if not isinstance(cells, dict):
        raise BookError("stage 9: %s is not a dimension: %r" % (name, cells))
    return cells


def _seen(lines):
    """The loans a pack counts, once each, in the order the lines print them."""
    found = []
    for line in lines:
        if line[0] not in found:
            found.append(line[0])
    return tuple(found)


def _disagrees(state, loan, line):
    """Whether a line says something other than what the bank records for it.

    The line is the pack's own answer and the record is the bank's: the stage,
    the grade, the bucket, the segment, the exposure and the provision all have
    to be the same fact, and a pack whose line disagrees with the bank's own
    status row is a pack reporting a portfolio that is not the one on the book.
    """
    return (line[1] != state["stage"] or line[2] != state["grade"]
            or line[3] != state["bucket"] or line[4] != loan["segment"]
            or line[5] != state["ead_cents"] or line[6] != state["ecl_cents"])


def _validate(record):
    """The pack's own shape: every total, every cell, or `BookError` naming it.

    The shape is checked before the book is asked anything, so a pack that is not
    a pack costs the book nothing — a refused call is not a lookup, and the book's
    own `stats()` is where a check sees that.
    """
    _as_number(record["exposures"], "exposures")
    _as_number(record["ecl"], "ecl")
    _as_number(record["coverage_bp"], "coverage_bp")
    for name in _COVERED:
        cells = _as_dimension(record[name], name)
        for key in cells:
            _as_cell(cells[key], "%s[%r]" % (name, key))
    _as_cell(record["forbearance"], "forbearance")
    cohorts = _as_dimension(record["vintage"], "vintage")
    for month in cohorts:
        cells = _as_dimension(cohorts[month], "vintage[%r]" % (month,))
        for stage in cells:
            _as_cohort(cells[stage], "vintage[%r][%r]" % (month, stage))
    return record


def _coverage_problems(record):
    """Every printed coverage ratio that is not its own loss over its own exposure.

    The scan covers the totals row, the four dimensions and the forbearance
    block, and it recomputes the ratio rather than comparing it with another
    one: a cell's coverage is a claim about the two numbers printed beside it.
    The cohort cells carry no loss of their own, so their coverage cannot be
    recomputed from the pack alone and is not scanned here.
    """
    problems = []
    if record["coverage_bp"] != _coverage(record["ecl"], record["exposures"]):
        problems.append(("coverage-mismatch", "coverage_bp"))
    for name in _COVERED:
        for key in record[name]:
            cell = record[name][key]
            if cell[3] != _coverage(cell[2], cell[1]):
                problems.append(("coverage-mismatch", "%s:%s" % (name, key)))
    memo = record["forbearance"]
    if memo[3] != _coverage(memo[2], memo[1]):
        problems.append(("coverage-mismatch", "forbearance"))
    return problems


def _total_problems(record, lines):
    """What does not add up: the totals against the lines, the cells against both.

    The lines are the pack's own detail, so they are what the totals are held
    against — and the cells of every dimension are the same detail aggregated, so
    a pack whose cells count a loan twice, or not at all, is caught here even
    when its own totals are internally consistent.
    """
    exposure = sum(line[5] for line in lines)
    ecl = sum(line[6] for line in lines)
    problems = []
    if record["exposures"] != exposure:
        problems.append(("total-mismatch", "exposures"))
    if record["ecl"] != ecl:
        problems.append(("total-mismatch", "ecl"))
    for name in _COVERED:
        cells = record[name]
        if (sum(cell[0] for cell in cells.values()) != len(lines)
                or sum(cell[1] for cell in cells.values()) != exposure
                or sum(cell[2] for cell in cells.values()) != ecl):
            problems.append(("total-mismatch", name))
    held = 0
    for month in record["vintage"]:
        for stage in record["vintage"][month]:
            held = held + record["vintage"][month][stage][1]
    if held != exposure:
        problems.append(("total-mismatch", "vintage"))
    return problems


def reconcile(pack, book):
    """Every problem a pack has against the book, in `PACK_PROBLEMS` order.

    The scan is over the pack's own detail and it never stops at the first
    finding: a supervisor reads the whole list. Five things are asked, in this
    order, of every pack:

    * `missing-loan` — a loan live on the book at the pack's date with no line;
    * `double-counted` — a loan with more than one line;
    * `coverage-mismatch` — a cell whose printed ratio is not its own loss over
      its own exposure (the offender is the cell, `"by_grade:B"`);
    * `stage-mismatch` — a line whose stage, grade, bucket, segment, exposure or
      provision is not what the bank's own record for that loan at that date
      says;
    * `total-mismatch` — the totals against the lines, and the cells of each
      dimension against the same detail, the offender naming the total or the
      dimension that does not add up.

    A pack this stage built scans to `()`. A pack whose shape is not a pack
    raises `BookError` naming the offender rather than answering, and a date the
    book does not report at is refused before anything is counted.
    """
    record = _as_pack(pack)
    date = record["date"]
    lines = _as_lines(record["lines"])
    _validate(record)
    _require_date(book, date)
    counted = {}
    for line in lines:
        counted[line[0]] = counted.get(line[0], 0) + 1
    live = _population(book, date)
    problems = []
    for holder in live:
        if counted.get(holder, 0) == 0:
            problems.append(("missing-loan", holder))
    for holder in _seen(lines):
        if holder not in live:
            problems.append(("missing-loan", holder))
    for holder in live:
        if counted.get(holder, 0) > 1:
            problems.append(("double-counted", holder))
    for holder in _seen(lines):
        if holder not in live and counted.get(holder, 0) > 1:
            problems.append(("double-counted", holder))
    for problem in _coverage_problems(record):
        problems.append(problem)
    held = {}
    for line in lines:
        held.setdefault(line[0], []).append(line)
    for holder in live:
        state = book.status(holder, date)
        loan = book.loan(holder)
        for line in held.get(holder, ()):
            if _disagrees(state, loan, line):
                problems.append(("stage-mismatch", holder))
                break
    for problem in _total_problems(record, lines):
        problems.append(problem)
    return tuple(problems)
