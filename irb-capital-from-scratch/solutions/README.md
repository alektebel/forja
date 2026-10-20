# IRB and Regulatory Capital From Scratch — solutions

Each solution file implements the functions declared in its template.
Run with `python3 solutions/stage_NN.py` to see a small demo output.

| Stage | Demo output |
|---|---|
| `python3 solutions/stage_01.py` | PIT and TTC grades for all twelve loans at two reporting dates |
| `python3 solutions/stage_02.py` | The 23-row quantile grid, known PD lookups, and an off-grid refusal |
| `python3 solutions/stage_03.py` | Correlation and slope per class/PD, maturity factor at three M values |
| `python3 solutions/stage_04.py` | K-series for each live loan, the first year and the last |
| `python3 solutions/stage_05.py` | Best-estimate and downturn LGD: a deal that beats, a deal that misses |
| `python3 solutions/stage_06.py` | BE-EAD for three loans, CCF estimated from the bank's defaults per product |
| `python3 solutions/stage_07.py` | Risk weight and RWA for each loan, total RWA of the book |
| `python3 solutions/stage_08.py` | Floor phase in 2028 (25%), 2030 (60%), 2035 (100%); binding at 2028, not at 2035 |
| `python3 solutions/stage_09.py` | Per-grade provision vs capital, irreconcilable rows with reason codes |
| `python3 solutions/stage_10.py` | Full capital pack: exposures, RWA, floor, reconciliation |