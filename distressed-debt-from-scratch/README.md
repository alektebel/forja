# Distressed Debt Investing From Scratch

A fund's trade over a distressed borrower's capital structure — ten graded stages building the buy-side's underwriting process from first principles: the waterfall of claims and the split of proceeds over them, the entry trade at the market's printed price, the bank's actuals walked into a recovery forecast, the Merton distance and the cumulative probability ladder, the three readings (actuals, identity, comparables) and the middle, the restructuring waterfall against absolute priority and the violations, the distressed exchange and per-holder balloting, the present value, the bisection search, and the internal rate of return, the carry over the months and the hold or pass decision, and the thesis audited against what the world actually settled.

Every number is an integer. No float, no math, no statistics, no decimal, no fractions, no random, no clock, no socket, no thread, no subprocess. Refusals name their offender.

## The world is provided, the stages are yours

`book.py`, `claims.py`, `dates.py`, and `rules.py` are the world, and they are **read-only**: the world is deterministic, and a check can run any world function twice and get the same answer.  The world exposes accessors that serve as the answer key — a stage must reproduce, not read.

| File | What it holds |
|---|---|
| `book.py` | The bank's portfolio of twelve loans across six segments and seven grades, the observed facts (payments, events, recoveries), versioned models, and the bank's own records — `schedule`, `grade`, `status`, `defaults`, `migrations`, `observed_default_rate`, `rollforward` |
| `claims.py` | The fund's side of the trade: one borrower's (`Berthline Industrial Holdings`) whole capital structure — four claims ranked by kind, the quotes the market gave at entry and close, the restructuring ballots and breaks, the Merton inputs, the comparables table, the fund's own facts, and the answer key: what each claim actually received |
| `dates.py` | ISO-date arithmetic — parse, add_months, days_between, month_end. The calendar the whole course runs on. |
| `rules.py` | The bank's policy: GRADES, SEGMENTS, BUCKETS, MATERIALITY thresholds, CURE_MONTHS, UTP_FLAGS, SICR test numbers, scenario weights, COLLATERAL_HAIRCUT_BP, DISCOUNT_SCALE, PERIOD_DAYS, and the period_rate function |

## How this course is verified

| What | Command | Result |
|---|---|---|
| template mode | `python3 course.py` (each `check_N`) | 10/10 raise `NotImplementedError` |
| solutions mode | copy solutions over templates, then run checks | 10/10 PASS |
| mutation battery | see `mutate.py` | MISSED: 0 |

## The laws a stage is held to

- Standard library only, no ``float``, no ``math``, no ``statistics``, no ``decimal``, no ``fractions``, no ``random``, no clock, no socket, no thread, no subprocess.
- A stage imports the world and its own stage file only, never a later one.
- No module-level mutable state; the world is never written.
- A shape mismatch raises (``StructureError``, ``EntryError``, ``ForecastError``, ``MertonError``, ``ValuationError``, ``PriorityError``, ``ExchangeError``, ``ReturnError``, ``HoldError``, ``ThesisError``), naming the offender; a verdict is returned.
- Every division carries the pinned truncation rounding. No two divisions with two different roundings.
- The first docstring paragraph is the stage's own title line, every public function is a docstring plus exactly one ``raise NotImplementedError``, and the file carries its ``DESIGN DECISION`` blocks and a ``TODO: implement`` line.
- Every check ends with a run-twice determinism proof.

## Running it

```bash
python3 codecraft/cli.py run distressed-debt-from-scratch
```

## The stages

| # | Stage | Surface |
|---|---|---|
| 1 | The waterfall of claims and the split of proceeds over them | `waterfall(claims)` → ranked tuple · `pay(proceeds_cents, ranked)` → PAY_KEYS |
| 2 | The entry trade at the market's printed price | `entry(claims, quote)` → ENTRY_KEYS |
| 3 | The bank's actuals walked into a recovery forecast | `expected_recovery(book, claim, at)` → FORECAST_KEYS |
| 4 | The Merton distance and the cumulative probability ladder | `dd(asset_value, debt, band_bp)` → int · `to_pd(dd_units)` → pd_bp |
| 5 | The three readings, the middle, and the spread between them | `three(book, claim, at)` → THREE_KEYS · `spread(reading)` → SPREAD_KEYS |
| 6 | The restructuring waterfall and the absolute-priority violations | `settlement_payment(restructuring, claim_rank)` → S6_PAYMENT_KEYS · `violations(restructuring)` → S6_VIOLATIONS_KEYS |
| 7 | The distressed exchange, the ballot, and per-holder answers | `tender(restructuring, claim)` → EXCHANGE_KEYS · `ballot(restructuring, holder)` → S7_BALLOT_KEYS |
| 8 | The present value, the search, and the internal rate of return | `pv(receipts_cents, rate_bp, months)` → int · `irr(claim, at)` → RETURN_KEYS |
| 9 | The carry over the months and the hold or pass decision | `carry(position, at)` → CARRY_KEYS · `hold(position, at, horizon)` → HOLD_KEYS |
| 10 | The thesis, audited against what actually happened | `thesis(claim, at)` → THESIS_KEYS · `audit(book, claims, at, close)` → AUDIT_KEYS rows |

## Limits

The world does **not** model: real-world regulatory capital requirements, tax effects of restructuring, liquidity premiums, counterparty credit risk on the new paper, stochastic asset paths (only a single tabulated path), correlation between borrowers, or secondary-market trading dynamics beyond the entry and close prints. The recovery forecast reads the bank's actuals but does not model recovery timing uncertainty, and the Merton model uses a single static volatility band rather than a full surface.