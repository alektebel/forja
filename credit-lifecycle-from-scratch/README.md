# Credit Lifecycle From Scratch

A loan's whole life as numbers, in ten graded stages, over a bank's own book.

The course is the arithmetic a bank runs between a loan being granted and the day it
leaves the balance sheet: the contractual schedule and the rate that discounts it, the
days past due and the new definition of default, the rating migration matrix and the
lifetime probability of default built from it, the recovery cash flows behind a loss
given default, the drawn and undrawn balance behind an exposure, the expected credit
loss with its horizon and its scenarios, IFRS 9's three stages and the test that moves a
loan between them, the provision roll-forward decomposed line by line, the reporting
pack with its coverage ratios and its reconciliation, and the backtest, validation and
attribution of a model the course did **not** fit.

Every number is an integer count of cents or basis points. There is no `float` literal
in the course, no `math`, no `statistics`, no `decimal`, no `fractions`, and no `/`
between two ints; where a division happens the contract pins its rounding, because the
arithmetic a reviewer recomputes by hand is exactly the arithmetic a float would hide.

## The world is provided, the stages are yours

`dates.py`, `rules.py` and `book.py` are the world, and they are **read-only**: the
book is a deterministic portfolio (`Book.build(7)`), the policy is data
(`rules.py`, `POLICY_VERSION`), and the bank's own records — its schedules, its
statuses, its migration counts, its roll-forward — are the answer key a stage has to
reproduce from the raw facts. A stage is one file; a check and a mutation battery are
what happen to it.

| # | Stage |
|---|---|
| 1 | The schedule, the day count and the rate that discounts it |
| 2 | The bucket, the materiality threshold and the new definition of default |
| 3 | The migration matrix, the term structure and the lifetime PD |
| 4 | The recovery cash flows and the loss given default |
| 5 | The drawn balance, the undrawn limit and the exposure at default |
| 6 | The expected credit loss, its horizon and its scenarios |
| 7 | The three stages and the significant increase in credit risk |
| 8 | The provision roll-forward, line by line |
| 9 | The reporting pack and the reconciliation that holds it |
| 10 | The backtest, the model artifact and the journal of the delta |

## How this course is verified

Nothing here is asserted in prose. The world is pinned by its own verifier, every stage
is graded in both directions (it must fail as a template and pass as a solution), and
every check has a mutation battery anchored to the solution's own text.

| What | Command | Result |
|---|---|---|
| the world | `python3 .m1-dev/verify_provided.py` | `PROVIDED: 9417, PROBLEMS: 0` |
| the stages | `python3 .m1-dev/check_NN.py` (1..10) | ten `PASS`, and ten exits 2 against the templates |
| the mutations | `python3 .m1-dev/mutate_all.py` | `TOTAL 643/643`, `MISSED OR BROKEN: 0` |
| the ladder and the laws | `python3 .m1-dev/audit_course.py` | `AUDITED: 10, PROBLEMS: 0` |
| the whole course as one module | `python3 .m1-dev/smoke.py`, `run_assembled.py` | `SMOKE: PASS`, `ASSEMBLED: 10/10` |
| a second, independent reading | `python3 .m1-dev/probe_stages.py` | `PROBED: 13849, PROBLEMS: 0` |
| the tests the course ships | `python3 .m1-dev/count_tests.py credit-lifecycle-from-scratch` | 727, per stage `[104, 101, 87, 49, 44, 63, 81, 38, 87, 73]` |

The provided world is pinned by digest:

| File | sha256 |
|---|---|
| `dates.py` | `cb3afa72bae7e11d73d2328de57ca78131649b1a15dea690109e8d55275d6e69` |
| `rules.py` | `df87096d1236e281b56a94614d3184b5e752b3c535142115ac90605f485d8bb2` |
| `book.py` | `d1124d002bcfcdba9e83340cb34109b4f53c072ff341424b6293b7a4f0354040` |

## The laws a stage is held to

- Standard library only, no `float` literal, no division of two ints; a division's
  rounding is pinned by the contract.
- A stage imports the world and earlier stages only, never a later one.
- No module-level mutable state; the book is never written.
- A shape mismatch raises (`BookError`, `DateError`, `ScheduleError`), naming the
  offender; a verdict is returned.
- The first docstring paragraph is the stage's own title line, every public function is
  a docstring plus exactly one `raise NotImplementedError`, and the file carries its
  `DESIGN DECISION` blocks and a `TODO: implement` line.

## Running it

    python3 codecraft/cli.py run credit-lifecycle-from-scratch

The ten stages are graded in order; the later ones depend on the earlier ones, and stage
8 is the course's integration point — it provisions the whole book at both ends of a
window and has to land on the bank's own numbers.
