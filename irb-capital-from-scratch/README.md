# IRB and Regulatory Capital From Scratch

The bank's own parameter estimates and the regulator's — ten graded stages over M1's book, dates and rules, with the IRB policy as data. Built over the same provided bank (`book.py`, `dates.py`, `rules.py`) and the new `irb.py` carrying every table the formula needs and nothing else.

Every number is an integer count of basis points, ten-thousandths, or cents. No `float` literal, no `math`, no `statistics`, no `decimal`. Where a division happens the contract pins its rounding (truncation `//`).

## The world is provided, the stages are yours

`book.py`, `dates.py` and `rules.py` are copied verbatim from M1's `credit-lifecycle-from-scratch/`. `irb.py` is the new provided module: the regulator's policy as data (`POLICY_VERSION = "IRB-1.0"`). A stage must reproduce the bank's records from the raw facts; the book's accessors are the answer key.

| File | What it holds |
|---|---|
| `book.py` | M1's twelve-loan book: `Book.build(7)`, 36 reporting dates, three model artifacts, the bank's own records (`grade`, `schedule`, `status`, `defaults`, `migrations`, `rollforward`, `stats()`) |
| `dates.py` | M1's calendar: month ends, day counts, the 360 and 365 bases |
| `rules.py` | M1's policy: the materiality threshold, the 90-day backstop, the cure period, scenarios and their weights in basis points |
| `irb.py` | IRB policy as data: `QUANTILE_GRID` (23-row inverse-normal table), `CORPORATE_CORRELATION_BP`, `RETAIL_CORRELATION_BP`, `SLOPE_ROWS`, `DOWNTURN_MULTIPLIER_BP`, `COLLATERAL_HAIRCUT_BP`, `CCF_BY_PRODUCT_BP`, `FLOOR_PHASE_PERCENT`, `STANDARD_WEIGHT_BP`, `CAPITAL_SCALING_BP` — all integers, zero float |

## How this course is verified

| What | Command | Result |
|---|---|---|
| template mode | `python3 codecraft/cli.py run irb-capital-from-scratch` | 10/10 raise `NotImplementedError` |
| solutions mode | copy solutions over templates, then run checks | 10/10 PASS |
| mutation battery | see below | MISSED: 0 |

## The laws a stage is held to

- Standard library only, no `float`, no `math`, no `statistics`, no `decimal`, no `fractions`, no `random`, no clock, no socket, no thread, no subprocess.
- Every number is an integer count of basis points, ten-thousandths, or cents.
- A stage imports the world and its own stage file only, never a later one.
- No module-level mutable state; the world is never written.
- A shape mismatch raises (``RatingError``, ``QuantileError``, ``WeightError``, etc.), naming the offender; a verdict is returned.
- The first docstring paragraph is the stage's own title line, every public function is a docstring plus exactly one `raise NotImplementedError`, and the file carries its `DESIGN DECISION` blocks and a `TODO:` line.
- Every check ends with a run-twice determinism proof.

## Running it

```bash
python3 codecraft/cli.py run irb-capital-from-scratch
```

## Limits

The world does **not** model: real-world PD migration matrices beyond the bank's twelve loans, stress scenarios beyond what `rules.py` carries, model risk management, capital stress testing, advanced IRB vs Foundation IRB, the Basel III/IV phase-in schedule beyond the output floor, or any regulatory reporting beyond the ten stages. These are the boundaries of this teaching version.