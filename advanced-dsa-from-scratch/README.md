# Advanced Data Structures From Scratch

Ten graded stages that build the structures a senior interview still reaches
for — in the order the amortized analysis reaches for them — and judge every
one of them by its own work counter, not by its return value.

The thesis, asserted by every check: **the counter is the lesson.** A structure
that returns the right answer can still be the wrong structure: a prune that
never prunes, a sift that rescans, a merge that restructures. Every stage counts
its work, `graphs.WORK_BARS` holds ceilings measured from the reference run, and
stage 10 fails any bar with no measurement behind it.

Everything is ints the whole way. No `random`, no clock, no threads, no float
literal in a template or a solution. The only noise in the course is one fixed
LCG in [`graphs.py`](graphs.py).

## Run it

```bash
python3 codecraft/cli.py run advanced-dsa-from-scratch      # or: ./cz run advanced-dsa-from-scratch
python3 codecraft/cli.py run advanced-dsa-from-scratch --stage 3
```

Each stage file `stage_01.py` … `stage_10.py` names what to write; the check
imports **your** module, calls it, and compares against the fixture in
[`graphs.py`](graphs.py) (provided, complete, never edited).

## The stages

| # | File | The one mechanism | Measured bar(s) |
|---|---|---|---|
| 1 | `stage_01.py` | Binary heap: the array layout, the two hole-and-place sifts, a counted sort | `heap_sort_cmp=85636 swaps=45473` |
| 2 | `stage_02.py` | D-way heap: children `D*i+1..D*i+D`, parent `(i-1)//D`, optional shared position map for decrease-key | `dary_sort_cmp=88691 swaps=25684` |
| 3 | `stage_03.py` | Fibonacci heap I: one circular root ring, child rings, the O(1) lazy union, an integrity walk that terminates on corruption | `fib_merge_work=1023` |
| 4 | `stage_04.py` | Fibonacci heap II: consolidate — bucket roots by degree from the watermark, pay the bill at extract-min | `fib_consolidate_work=11863` |
| 5 | `stage_05.py` | Fibonacci heap III: decrease-key, the mark, the cascading cut, delete as decrease+extract | `fib_cuts=200 cascades=52 drain=5321` |
| 6 | `stage_06.py` | Dijkstra on three engines — lazy `heapq`, the indexed d-ary heap, the Fibonacci heap — each with its own ledger | `pops=17 skipped=7 · dary_cmp=25 · fib_work=20 cuts=5 pops=10` |
| 7 | `stage_07.py` | Union-find: union by rank, iterative path compression, `finds`/`path_steps` counters judging Kruskal's MST | `finds=24 path_steps=40`, MST total 17 |
| 8 | `stage_08.py` | Trie: terminal flags, lexical autocomplete from sorted children, the deepest prefix, a visit counter | `trie_visits=35` |
| 9 | `stage_09.py` | LFU cache: eviction as one `(frequency, age)` total order, a counted coldest scan, a fixed script | `probes=6 evictions=3`, order `('c','b','d')` |
| 10 | `stage_10.py` | Capstone: k-d tree with median splits and the tie-law prune, verified against the linear scan by visit count — plus the audit of every bar | `seen=62 probes=62 pruned=22` of 150 linear |

The Fibonacci heap is deliberately spread over **three stages**, one mechanism
each: merge, consolidate, cut. Bundling them would make stage 3 pass while
stages 4–5 were still wrong.

## Verification

Graded checks — every stage passes on the reference solutions and on nothing
less:

```bash
# templates as shipped: every stage reports TODO, none FAIL/ERROR
python3 codecraft/cli.py run advanced-dsa-from-scratch     # 0/10, next: 1

# solutions over the templates, 10/10
python3 - <<'PY'
import sys; sys.path.insert(0, '.')
from codecraft.contract import run_course_module
print(run_course_module('advanced-dsa-from-scratch'))      # after the overlay
PY
```

Mutation battery — 29 planted bugs, 3 per stage at minimum, every one CAUGHT
(`MISSED OR BROKEN: 0`):

```bash
python3 _build/run_mutations.py
```

The catalogue lives in [`_build/mutations.py`](_build/mutations.py); the
checker it drives is `_build/grade.py`, a dev-only runner that lets each
`check_N` run against mutated solution copies (`_build/` is excluded from
student exports).

Templates are **generated**, never hand-edited:

```bash
python3 .claude/skills/graded-module/scripts/make_templates.py \
    advanced-dsa-from-scratch advanced-dsa-from-scratch/_build/hints.py
```

`_build/hints.py` lists every mechanism, underscored helpers included: in this
course the "private" sift *is* the exercise.

## Design decisions worth knowing

- **Bars are measured ceilings, not theory.** `WORK_BARS` was filled from the
  reference run with ~15–30% slack; each bar catches a mechanism that *never
  stops doing work* (a rescanned sift, a stale pop that is not skipped, an
  audit that dropped a bar), not a solution a few percent slower.
- **The watermark, not the live count.** Consolidation sizes its bucket table
  from the most nodes the heap ever held (`FibHeap.high`). Guarding on the live
  count refuses legal heaps after cuts and extractions.
- **Roots are never marked.** The cascade climbs only marked non-roots; the
  first loss of a non-root marks it and stops. The check pins a hand-built
  cascade: `(cuts, cascades) == (3, 1)`, potential `8 → 6`.
- **The ring must be a ring in both directions.** Every union and every
  extract re-checks `x.right.left is x and x.left.right is x`; a one-way splice
  passes forward traversal and fails this.
- **The prune descends on a tie.** `gap*gap <= worst` — the k-d tie law breaks
  by `(distance, point, index)`, so an equidistant far point can still win.
  A deterministically built five-point case makes the `<=` observable.

## Limits

- The course covers the book's heap/probing/string/cache/geometric chapters it
  grades; treaps, Bloom filters, SS-trees, DBSCAN/OPTICS, embeddings and the
  search algorithms are **not** in it — the row's wider ambition is not
  silently claimed.
- The k-d tree is 2-D over ints; squared distance is exact, so "nearest" has one
  answer everywhere.
- Bars are pinned to the fixtures in `graphs.py`. Change a fixture and the bars
  must be re-measured (`stage_10.py` will refuse a bar with no measurement).
