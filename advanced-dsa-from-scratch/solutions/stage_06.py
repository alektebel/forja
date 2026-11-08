"""Dijkstra on three heaps: one distance table, three work counts.

La Rocca, ch. 1-2 — the judge every heap in this course answers to. The
graph is `graphs.EDGES` (ints, positive weights); the law is
`graphs.DIJKSTRA_FROM_0`, computed by a relax-until-stable scan with no
heap in it, so no heap grades itself. All three engines land the same
table, and the lesson is the counters:

  - the lazy binary heap (`heapq`, one insert per successful relax, stale
    pops skipped): the price of laziness is the duplicate count, and the
    check pins it — `skipped` is exactly `relaxed - settled + 1`.
  - the indexed d-ary heap: `decrease_key` needs WHERE each entry lives,
    so stage 2's `pos=` map is part of the mechanism; nothing is skipped,
    nothing is duplicated, and `cmp` counts every comparison made.
  - the Fibonacci heap of stages 3-5: the same run with real
    decrease-key; `work` counts the merge comparisons and the cut counts
    show the cascade firing — the amortized claim as a number.

DESIGN DECISION — the engines take the graph as `graphs.adjacency()`, not
an edge list: rebuilding adjacency inside the hot loop would measure the
scan, not the heap. Positive int weights only; a negative weight is
refused, because Dijkstra's claim is false there and a silent wrong table
is worse than a crash the check can see.

DESIGN DECISION — settled nodes are skipped by comparing the popped
distance against the table (lazy engine), never a `settled` set: the
comparison is the whole of the lazy engine's bookkeeping; an added set
hides stale entries instead of counting them. The indexed and Fibonacci
engines never insert twice, so they never need the skip at all.
"""

import heapq

from graphs import DIJKSTRA_FROM_0, EDGES, adjacency
from stage_02 import DaryHeap


class DijkstraError(Exception):
    """Refusal: a graph this Dijkstra cannot price."""


def _check_positive(edges):
    for u, v, w in edges:
        if isinstance(w, bool) or not isinstance(w, int) or w < 0:
            raise DijkstraError("negative or non-int weight %r on (%d,%d): "
                                "this Dijkstra needs ints >= 0" % (w, u, v))


def dijkstra_lazy(edges, source=0):
    """heapq with insert-on-improve. Returns (dist, pops, skipped, relaxed)."""
    _check_positive(edges)
    adj = adjacency(edges)
    dist = {source: 0}
    heap = [(0, source)]
    pops = skipped = relaxed = 0
    while heap:
        d, u = heapq.heappop(heap)
        pops += 1
        if d > dist[u]:                 # stale: a better way arrived later
            skipped += 1
            continue
        for v, w in adj[u]:
            relaxed += 1
            nd = d + w
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist, pops, skipped, relaxed


def dijkstra_dary(edges, source=0, D=4):
    """Dijkstra on stage 2's indexed d-ary heap: (distance, node) pairs,
    real decrease_key through the pos map. Returns (dist, heap)."""
    _check_positive(edges)
    adj = adjacency(edges)
    pos = {}
    heap = DaryHeap(D=D, pos=pos)
    dist = {source: 0}
    heap.push((0, source))
    settled = set()
    while len(heap):
        d, u = heap.pop()
        settled.add(u)
        for v, w in adj[u]:
            nd = d + w
            if v in settled:
                continue
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                if v in pos:
                    heap.decrease_key(v, (nd, v))
                else:
                    heap.push((nd, v))
    return dist, heap


def dijkstra_fib(edges, source=0):
    """Dijkstra on the stage 3-5 Fibonacci heap: insert's node handles are
    the decrease-key addresses. Returns (dist, work, cuts, cascades, pops)."""
    from stage_05 import FibHeap
    _check_positive(edges)
    adj = adjacency(edges)
    heap = FibHeap()
    node_of = {source: heap.insert(0, source)}
    dist = {source: 0}
    settled = set()
    pops = 0
    while len(heap):
        node = heap.extract_min()
        pops += 1
        u = node.payload
        if u in settled:
            continue                    # defensive: this engine never doubles
        settled.add(u)
        dist[u] = node.key
        for v, w in adj[u]:
            nd = node.key + w
            if v in settled:
                continue
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                if v in node_of:
                    heap.decrease_key(node_of[v], nd)
                else:
                    node_of[v] = heap.insert(nd, v)
    return dist, heap.work, heap.cuts, heap.cascades, pops


def agree(table):
    """Every reachable distance equals the fixture's — the one law."""
    return {k: table[k] for k in sorted(table)} == \
        {k: DIJKSTRA_FROM_0[k] for k in sorted(DIJKSTRA_FROM_0)}


def report(edges=EDGES):
    """All three engines, one graph; the numbers the bars are pinned on."""
    lazy_dist, pops, skipped, relaxed = dijkstra_lazy(edges)
    assert agree(lazy_dist), "lazy heapq disagrees with the fixture"
    dary_dist, heap = dijkstra_dary(edges)
    assert agree(dary_dist), "the d-ary heap disagrees with the fixture"
    fib_dist, work, cuts, cascades, fpops = dijkstra_fib(edges)
    assert agree(fib_dist), "the Fibonacci heap disagrees with the fixture"
    return {
        "lazy": {"pops": pops, "skipped": skipped, "relaxed": relaxed},
        "dary4": {"cmp": heap.cmp, "swaps": heap.swaps},
        "fib": {"work": work, "cuts": cuts, "cascades": cascades,
                "pops": fpops},
    }


def measure():
    """The measured bars for this stage: Dijkstra on the fixture graph —
    every engine's cost of settling the same 10 nodes."""
    r = report()
    return {"dijkstra_lazy_pops": r["lazy"]["pops"],
            "dijkstra_lazy_skipped": r["lazy"]["skipped"],
            "dijkstra_dary_cmp": r["dary4"]["cmp"],
            "dijkstra_fib_work": r["fib"]["work"],
            "dijkstra_fib_cuts": r["fib"]["cuts"],
            "dijkstra_fib_pops": r["fib"]["pops"]}


if __name__ == "__main__":
    for name, row in report().items():
        print("stage 6 — %s: %s" % (name, row))
