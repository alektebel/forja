# Solutions

Finished, runnable versions of each stage. Read them *after* attempting — a
solution read cold is just more prose.

| File | Stage |
|---|---|
| `stage_01.py` | The link and the fabric: hops, bytes, a step's max, a plan's sum, `validate` |
| `stage_02.py` | Broadcast: the ring one turn per step, the tree one level per step |
| `stage_03.py` | Reduce, and where the accumulator lives: the travelling chain, the tree deepest first |
| `stage_04.py` | The ring all-reduce: reduce-scatter then all-gather, `2(N−1)` steps |
| `stage_05.py` | The tree all-reduce, recursive doubling, and `all_reduce_best` |
| `stage_06.py` | All-gather and reduce-scatter as first-class collectives |
| `stage_07.py` | All-to-all: one step, one transfer per pair, offsets cumulative by destination |
| `stage_08.py` | Send, recv and groups: one launch, priced by its slowest transfer |
| `stage_09.py` | Choosing an algorithm, and the lower bound: every candidate priced, SHARP as a plan |
| `stage_10.py` | One step, end to end: four axes on one topology, comms behind compute |

What imports what, for the stages that build on earlier ones:

```
stage_01  ──────────────► the cost model every other stage prices with
stage_02  standalone     broadcast
stage_03  standalone     reduce
stage_04  standalone     the ring all-reduce (its own chunking and hops)
stage_05  stage_01, stage_04   tree, doubling, and best-of-three
stage_06  standalone     all-gather and reduce-scatter
stage_07  standalone     the all-to-all and its transpose
stage_08  stage_01       a group's price is its step's slowest transfer
stage_09  stage_01, stage_04, stage_05   choose over the candidates, plus SHARP
stage_10  stage_01, stage_07, stage_08, stage_09   one step over four axes
```

So copying one over its template needs the earlier ones in place too — the same
ladder the checks import. To compare a stage, copy it over the template, re-run
the checker, then restore the template if you want to try again:

```bash
cp solutions/stage_05.py stage_05.py
python3 codecraft/cli.py run interconnects-from-scratch
```

All ten pass their checks with the standard library alone: no threads, no
clock, no network, no float anywhere — every tick is an int computed from the
fabric's bandwidths and latencies, which is what lets a check assert the price a
plan should have instead of timing a run.

To see the whole course work at once, copy every solution over its template and
run the course's own checker:

```bash
for n in 01 02 03 04 05 06 07 08 09 10; do cp solutions/stage_$n.py stage_$n.py; done
python3 codecraft/cli.py run interconnects-from-scratch
```
