# Distressed Debt Investing From Scratch — solutions

Each solution file implements the functions declared in its template.
Run with `python3 solutions/stage_NN.py` to see a small demo output.

| Stage | Demo output |
|---|---|
| `python3 solutions/stage_01.py` | The close's own pool (48M) split over the waterfall: secured gets full, unsecured gets the remainder, equity gets nothing |
| `python3 solutions/stage_02.py` | The sheet priced as trades: every debt claim at entry and close — the unsecured at 18% of par costs 8.1M, the loan at 92% costs 36.8M |
| `python3 solutions/stage_03.py` | Expected recovery from the bank's defaulted book: corporate segment recovers ~X bp, giving Y cents on the unsecured's face |
| `python3 solutions/stage_04.py` | The distance at three bands — calm, normal, stressed — each mapping through the PD ladder to a cumulative probability |
| `python3 solutions/stage_05.py` | The three readings side by side (forecast, Merton, comparables), the middle, and the signed gaps between each pair |
| `python3 solutions/stage_06.py` | The close recomputed from the decree and waterfall, per rank — and the absolute-priority violation: 3.6M given to the insurer, taken from unsecured |
| `python3 solutions/stage_07.py` | The club's terms: 37.5M tendered becomes paper worth 33.75M at 90%, maturity extended 54 months; per-holder answers for tender, hold, and cash |
| `python3 solutions/stage_08.py` | The fund's gate over every debt claim: IRR searched under the wall, residue reported — the unsecured return is ~25988 bp with residue 914 |
| `python3 solutions/stage_09.py` | The fund's live carry at entry and close dates, and the 12-month horizon decision: hold on an upside of 7.2M |
| `python3 solutions/stage_10.py` | The fund's thesis for the unsecured position — triplet, receipts, return, carry, upside, decision — and the audit grading each claim against the world's outcome |