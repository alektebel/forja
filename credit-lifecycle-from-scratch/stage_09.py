"""Credit Lifecycle From Scratch — stage 9: The reporting pack and the reconciliation that holds it.

Eight stages have answered one question each — what the contract owes, which
bucket a loan sits in, what the PD and the LGD and the exposure are, what the
provision costs, which stage books it and how it moved between two dates — and
none of them is a report. This stage is the bank's report: one pack at one date,
every loan in it, every dimension of it (stage, grade, bucket, segment), the
cohort matrix a vintage table is, the stage migration of the last year, and the
forbearance subset disclosed beside the rest rather than instead of it.

The pack's whole design is that it prints its own detail. A pack is not a page of
aggregates: it is `lines` — one record per loan it counted — and the totals and
the cells that are nothing but those lines aggregated. A number a reader cannot
take apart is a number a reader cannot check, and the reconciliation the stage's
second half runs is exactly that reader.

`reconcile` therefore walks a pack against the book and answers the problems it
finds as `(problem, offender)` pairs in `PACK_PROBLEMS` order: a loan the pack
lost, a loan it counted twice, a cell whose coverage is not its own loss over its
own exposure, a line that disagrees with the bank's own status record, and a
pack whose parts do not add up to its totals. A refusal is a record with the
reason in it; a mismatch in *shape* — a pack that is not a pack — is a
`BookError` naming the offender.

    PACK_KEYS                                    the twelve keys of a pack, in order
    PACK_PROBLEMS                                the five problems a scan answers, in order
    pack(book, date)                             -> the bank's reporting pack at a date
    reconcile(pack, book)                        -> the pack's problems, as (problem, offender)
    vintage(book, date)                          -> the cohort matrix: origination months against stages

DESIGN DECISION — why does the pack print its lines instead of only its cells?
Because an aggregate cannot be checked and a reconciliation that cannot name a
loan is not a reconciliation. `lines` is one record per loan the pack counted —
the loan, its stage, its grade, its bucket, its segment, its exposure and its
provision — in the book's loan order, and every other number in the pack is those
lines added up. That is what makes `missing-loan` and `double-counted` decidable
at all: a loan with no line and a loan with two are facts about the detail, and a
page of totals would hide both behind a number that happens to look plausible.

DESIGN DECISION — why is the coverage ratio's denominator the exposure?
Because a ratio is a claim about the number beneath it. The provision is measured
against the exposure at default — the drawn balance plus the cash-flow-equivalent
undrawn limit — so that is what the coverage is divided by; the drawn balance
would be a smaller denominator for the same loss, and a coverage computed on it
would be a larger ratio with nothing to say about the lending the bank has
actually committed. The division is truncated (`ecl_cents * 10000 //
exposure_cents`) so the printed ratio always sits at or below the true one, and
an exposure of zero answers `0`, because a ratio with no denominator is not a
ratio and the pack does not invent one.

DESIGN DECISION — why is the forbearance subset a memo rather than a dimension?
Because a subset reported *instead* of the portfolio changes the pack's totals.
The flagged loans are on the book and they belong in the stage, grade, bucket and
segment rows; the forbearance block is the same loans reported again, with their
own coverage, as the disclosure a supervisor asks for beside the tables and not
in place of them. Reported as a fifth dimension it would either double count the
pack or silently shrink it, and this stage's whole subject is which of the two a
number is.

DESIGN DECISION — why is the vintage ordered by cohort and the migration's
remainder put in one column?
Because both are the same discipline stage 3 already fixed. A vintage table with
its rows in the order the loans happened to be read is a table no month can be
compared with the month before, so the rows are in date order (the origination
month) and the columns in the stages' own order. The stage migration is stage 3's
matrix one dimension coarser: the rates are per row, each row sums to exactly
10000, and the whole remainder of the truncation goes to the last column — the
credit-impaired stage, the coarse analogue of the absorbing default — so a reader
who checks one row by hand gets 10000 rather than a 9999 that has to be explained.

DESIGN DECISION — why does `reconcile` answer every problem rather than the
first one?
Because the first problem in a pack is rarely the only one, and a scanner that
stops at it hides the rest behind it: a supervisor reading a reconciliation wants
the whole list, in a fixed order, each entry naming the loan or the cell it is
about. So the scan runs all five kinds in `PACK_PROBLEMS` order and returns their
pairs as a tuple; a pack this stage built scans to `()` and a hand-broken one is
named rather than trusted.

DESIGN DECISION — why does the pack ask the earlier stages instead of reading the
bank's own records?
Because a report is not a place to re-derive a policy. The stage, the bucket, the
exposure and the provision come from stages 7, 2, 5 and 6 — the same rules the
bank booked under — which is what lets `reconcile` catch a line that disagrees
with the bank's own status record instead of quietly reproducing it. Two things
do come from the book itself: the grade, because a grade is the bank's own
recorded rating at the date and not an arithmetic fact, and the population, which
is `book.on_book(date)` — the loans live then. A written-off loan is derecognised
and does not belong in the pack, and the bank's status record, which answers for
every date including one before an origination, is not the place to ask.

TODO: implement `PACK_KEYS`, `PACK_PROBLEMS`, `pack`, `reconcile` and `vintage`
in this file: the pack at a date with its lines, its totals and its four
dimensions; the cohort matrix; and the scanner that walks a pack against the book
and answers its problems in `PACK_PROBLEMS` order.
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


def pack(book, date):
    """The bank's reporting pack at `date`, and every number in it is a line's.

    The pack answers `PACK_KEYS` in order: the date, one line per loan the book
    holds at that date (its stage, grade, bucket, segment, exposure and
    provision), the exposure and provision totals, the total's coverage ratio,
    the four dimensions — each a dict of key to `("loans", "exposure_cents",
    "ecl_cents", "coverage_bp")` — the forbearance subset reported beside them,
    the cohort matrix `vintage` answers and the stage migration of the last year.
    A date the book does not report at raises `BookError` naming it; a date with
    no loans on it is answered as an empty pack rather than refused.
    """
    raise NotImplementedError("stage 9: implement pack()")


def reconcile(pack, book):
    """The problems a pack has against the book, in `PACK_PROBLEMS` order.

    The scan is over the pack's own lines and cells: a loan live on the book at
    the pack's date with no line, a loan with two lines, a cell whose coverage is
    not its own loss over its own exposure, a line that disagrees with the bank's
    own record for that loan at that date, and a total or a dimension that does
    not add up to the pack's own detail. Each problem is answered as `(problem,
    offender)` — the offender naming the loan or the cell — and the pack `pack`
    builds scans to `()`. A pack whose shape is not a pack raises `BookError`
    naming the offender.
    """
    raise NotImplementedError("stage 9: implement reconcile()")


def vintage(book, date):
    """The cohort matrix at `date`: origination months against stages.

    One row per origination month, one column per stage the date's loans sit in,
    each cell `("loans", "exposure_cents", "coverage_bp")`, the rows in date order
    and the columns in the stages' own order.
    """
    raise NotImplementedError("stage 9: implement vintage()")
