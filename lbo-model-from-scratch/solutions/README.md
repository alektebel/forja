# Solutions — LBO Model From Scratch

Each solution file ends with a `__main__` demo that prints a small,
readable measurement from the world's own deal.

## stage_01.py — Sources and uses

```
the close at 60000 bp of entry EBITDA, balanced
source: sponsor                       2232500000
source: revolver                               0
source: term-loan-a                 2100000000
source: term-loan-b                 2700000000
source: mezzanine                    600000000
use: equity purchase                7200000000
use: advisor                         72000000
use: arrangement-term-loan-a        525000000
use: arrangement-term-loan-b        810000000
use: arrangement-mezzanine           27000000
use: opening cash                    200000000
total sources                      7632500000
total uses                         7632500000
```

## stage_02.py — The operating build

```
year 1: revenue 6300000000, ebitda 1292000000, free 164000000
year 2: revenue 6615000000, ebitda 1425000000, free 553000000
year 3: revenue 6945000000, ebitda 1562000000, free 785000000
year 4: revenue 6250000000, ebitda 1180000000, free 172000000
year 5: revenue 6884000000, ebitda 1543000000, free 695000000
```

## stage_03.py — The debt schedule

```
year 1: 4 tranches
  revolver        int=82687500 amort=0
  term-loan-a     int=112312500 amort=105000000
  term-loan-b     int=183750000 amort=0
  mezzanine       int=72643835 amort=0
year 2: 4 tranches
...
year 5: 4 tranches
```

## stage_04.py — The waterfall

```
year 1 waterfall:
  interest:  457939835
  amort:     105000000
  draw:      200000000
  repay:     0
  sweep:     0
  cure:      0
  dist:      0
```

## stage_05.py — The covenants

```
year 1: breach=False cure=0
year 2: breach=False cure=0
year 3: breach=True cure=15000000000
year 4: breach=False cure=0
year 5: breach=True cure=...
```

## stage_06.py — The exit

```
exit at 62500 bp: gross=9643750000, debt=4137569772, equity=5756180228
```

## stage_07.py — The money multiple and the IRR

```
sponsor flows: 11 dated events
  2026-06-30: -2232500000
  2027-06-30: 57770000
  2028-06-30: 109593033
  ...
moic: 26856 bp (2.69x)
irr: 2433 bp
```

## stage_08.py — The decomposition

```
decomposition:
  IRR:      2433 bp
  carry:    1795 bp
  growth:   225 bp
  multiple: 46 bp
  leverage: 367 bp
  sum:      2433 bp (should equal IRR)
  residual: 0 bp (should be zero)
```

## stage_09.py — The sensitivity grid

```
grid (3 entries × 3 exits = 9 cells):
  57500/50000 -> irr=1456 breach=0 by=0
  57500/55000 -> irr=1823 breach=0 by=0
  57500/60000 -> irr=2134 breach=0 by=0
  ...
  62500/60000 -> irr=2901 breach=3 by=1200
```

## stage_10.py — The memo, audited

```
the sponsor's memo, audited line by line
line                   verdict        what changed
irr_bp                 off            claimed X, model Y
moic_bp                off            claimed X, model Y
carry_bp               off            claimed X, model Y
growth_bp              match          225
multiple_bp            off            claimed X, model Y
leverage_bp            off            claimed X, model Y
debt-path year 1       match
debt-path year 2       match
debt-path year 3       match
debt-path year 4       match
debt-path year 5       match
limit 2027-06-30       match
...
exit                   match
worst_irr_bp           off            claimed X, model Y
wrong lines: 5 of 21
```