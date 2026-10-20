# LBO Model From Scratch

A leveraged buyout model from first principles. Ten graded stages building the
deal: sources and uses balanced to the cent, the operating build from revenue to
free cash flow, the debt schedule tranche by tranche, the waterfall that moves
cash, the covenants that measure leverage, the exit on the multiple the market
realised, the money multiple and the IRR, the return decomposed into its engines,
the sensitivity grid with the breach kept visible, and the sponsor's memo, audited
line by line.

## The stages

| # | Stage | Tags |
|---|-------|------|
| 1 | The sources and the uses, balanced to the cent | sources-uses, close, balance |
| 2 | The operating build, revenue to free cash flow | build, tax, free-cash |
| 3 | The debt schedule, tranche by tranche | debt, schedule, tranches |
| 4 | The mandatory prepayment and the cash that sweeps | waterfall, sweep, state-machine |
| 5 | The covenants the model cannot quietly violate | covenants, breach, cure |
| 6 | The exit on the multiple the market realised | exit, multiple, terminal |
| 7 | The money multiple and the rate that discounts the deal | moic, irr, bisection |
| 8 | Where the return came from, engine by engine | decomposition, carry, growth, leverage |
| 9 | The sensitivity grid, with the breach kept visible | sensitivity, grid, breach |
| 10 | The sponsor's memo, audited line by line | memo, audit, capstone |

## The world is provided, the stages are yours

The world holds the deal — the facts at entry, the five-year path the company
took, the financing terms, the covenant treaty, and the answer key the checks
use to verify that each stage recomputes rather than reads.

| Module | What it holds |
|--------|---------------|
| `estate.py` | The deal: Coyote Industrial Group, five years, entry/exit multiples, four tranches (revolver, term-loan-a, term-loan-b, mezzanine), the fee schedule, the tax bands, the leverage limits, the cure, and the sponsor's memo with three wrong lines. |
| `dates.py` | The calendar: ISO date parsing, day count (`actual-365` and `thirty-360`), month-end clamping. Imported by stages that need interest day counts. |
| `rules.py` | The rulebook: provision grades, bucket bounds, materiality test, scenario weights. Not directly used by these stages but present as the model's policy context. |

## How to run

```bash
# From the repo root:
python3 codecraft/cli.py run lbo-model-from-scratch

# Or from within the course directory:
python3 stage_01.py   # each stage's __main__ demo
python3 course.py     # run all checks
```

## Verification

| Result | Count |
|--------|-------|
| Solution checks pass | 10 / 10 |
| Template checks raise | 10 / 10 |
| Mutations caught | 20 / 20 |
| Mutations missed | 0 |

## House laws

1. **Standard library only.** No numpy, pandas, requests.
2. **No float, ever.** Every number is an integer count of cents or basis
   points. Every division is `//` with the truncation the estate's own
   arithmetic uses.
3. **No math, no statistics, no decimal, no fractions, no random.**
4. **No clock, no socket, no thread.** Everything is deterministic.
5. **The world is data and holds the ground truth.** A stage reads the
   world and recomputes; the world's accessors are the answer key.
6. **Everything is deterministic.** Same inputs, same answer, run twice.
7. **Refusals name their offender.** Every error class raises messages
   containing the name of the offending value.

## Design decisions

- **Integer cents over float dollars.** The whole model lives in cents to
  avoid rounding ambiguity. A float dollar amount loses pennies on a five-
  year cascade of divisions.
- **Basis points over decimals.** Rates and multiples are stored as integer
  basis points (10000 bp = 100%). This avoids float representation error
  and makes every comparison exact.
- **Breach as data, not exception.** A covenant breach is a row in the test
  result, not an error that stops the model. The caller decides what to do.
- **Stepped NPV over powered.** The IRR search uses `factor = factor * 10000
  // (10000 + rate)` per year, not `pow`. This matches the estate's pinned
  truncation and makes the residue honest data.
- **No stage borrows a stage.** Each stage recomputes its own view of the
  waterfall, the build, and the IRR. This is the "recompute-first" principle
  that makes the checks prove the stages never read the answer key.

## Limits

- Five-year horizon. The model does not handle extensions, refinancing after
  year five, or any date outside the estate's recorded calendar.
- One deal. The estate models Coyote Industrial Group at one set of multiples.
  The sensitivity grid explores adjacent multiples but does not model
  restructuring or refinancing.
- Mezzanine is never swept, never cured, never repaid early. The mezzanine
  tranche carries its interest for five years and exits at the sale.
- No tax-loss carryforward. The tax bands apply to each year's taxable base
  independently.
"""