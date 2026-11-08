"""Advanced Data Structures From Scratch — the graph and point worlds.

The fixtures every stage is judged on: one weighted directed graph with its
pinned single-source distances, the same graph's edges in Kruskal order with
the minimum spanning tree the textbook answer must match, one integer point
set with its brute-force nearest neighbours, the word list the trie answers
from, the LFU script, and the one deterministic byte stream every workload
in the course draws from.

Everything here is ints the whole way — no floats, no `random`, no clock.
The LCG is the only source of "chance" in this course, and it is a constant.
A stage may recompute what it is checked against, but it may never invent a
different answer: when a stage's structure and a brute-force scan disagree,
the scan is law, and `REFERENCE` rows are the scan the course already made.
"""


def _lcg(seed, n):
    """The fixed LCG: the one noise source the world owns."""
    out = []
    state = seed
    for _ in range(n):
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        out.append((state >> 33) & 0xFF)
    return tuple(out)


#: the deterministic byte stream every graded workload draws from: 4096
#: bytes, one fixed LCG, the same 4096 numbers on every machine.
COINS = _lcg(20261108, 4096)

# --- the weighted directed graph --------------------------------------------------
# Nodes are ints 0..9; an edge is (source, target, weight). The graph is small
# on purpose: every distance, every relaxation count, is checkable by hand.
EDGES = (
    (0, 1, 4), (0, 2, 1), (2, 1, 2), (1, 3, 1), (2, 3, 5), (3, 4, 3),
    (2, 4, 8), (4, 5, 2), (3, 5, 6), (1, 5, 12), (0, 6, 7), (6, 7, 1),
    (7, 8, 5), (8, 9, 3), (6, 9, 14), (4, 7, 2), (5, 9, 1), (2, 6, 3),
    (9, 3, 4), (7, 5, 4),
)

NODES = tuple(sorted({s for s, _t, _w in EDGES} | {t for _s, t, _w in EDGES}))


def adjacency(edges=EDGES):
    """Out-edges per node, in (target, weight) order sorted by target."""
    adj = {node: [] for node in NODES}
    for source, target, weight in edges:
        adj[source].append((target, weight))
    for node in adj:
        adj[node].sort()
    return {node: tuple(rows) for node, rows in adj.items()}


# distances from node 0, computed once here by a plain relax-until-stable scan
# (this fixture never uses a heap; the heaps are what the stages build).
def _brute_distances(source=0):
    adj = adjacency()
    dist = {node: None for node in NODES}
    dist[source] = 0
    changed = True
    while changed:
        changed = False
        for u in NODES:
            if dist[u] is None:
                continue
            for v, w in adj[u]:
                if dist[v] is None or dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
                    changed = True
    return {node: d for node, d in dist.items() if d is not None}


#: the law for Dijkstra: distances from node 0 over EDGES.
DIJKSTRA_FROM_0 = _brute_distances(0)

# --- the undirected MST world -----------------------------------------------------
UNDIRECTED_EDGES = (
    (0, 1, 4), (0, 2, 1), (1, 2, 2), (1, 3, 5), (2, 3, 8), (2, 4, 10),
    (3, 4, 2), (0, 5, 7), (3, 5, 3), (4, 5, 6), (1, 6, 9), (5, 6, 4),
)

#: Kruskal's own order: (weight, min-endpoint, max-endpoint), ties by nodes.
KRUSKAL_ORDER = tuple(sorted((w, min(u, v), max(u, v))
                             for u, v, w in UNDIRECTED_EDGES))


def _brute_mst():
    """The MST by the slowest obvious method: grow the tree from cheap edges."""
    parent = {u: u for u in range(7)}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    total = 0
    chosen = []
    for w, u, v in KRUSKAL_ORDER:
        if find(u) != find(v):
            parent[find(u)] = find(v)
            total += w
            chosen.append((u, v, w))
    return total, tuple(chosen)


MST_TOTAL, MST_EDGES = _brute_mst()  # 17, ((0,2,1),(1,2,2),(3,4,2),(3,5,3),(5,6,4),(1,3,5))

# --- the point world for the k-d tree ---------------------------------------------
# integer 2-D points; squared distance is exact in ints, so "nearest" has one
# answer everywhere — and the tree must agree with the linear scan on every
# query, including the ones where two points share a distance.
POINTS = tuple(
    (x, _lcg(1000 + i, 1)[0] % 97)
    for i, x in enumerate(range(0, 48, 2))
) + ((3, 4), (12, 61), (25, 8), (37, 44), (44, 90), (5, 5))


def _brute_nearest(query, k):
    """The linear scan: the law the k-d tree is checked against.

    Order: squared distance, then the point itself, then index. Ties are
    broken by point value, so two implementations can never disagree about
    WHICH tied point answered — only about whether they looked.
    """
    rows = []
    for index, point in enumerate(POINTS):
        d = (point[0] - query[0]) ** 2 + (point[1] - query[1]) ** 2
        rows.append((d, point, index))
    rows.sort()
    return tuple((point, index) for _d, point, index in rows[:k])


QUERIES = ((7, 7), (20, 50), (48, 1), (3, 3), (24, 24))

#: the law: nearest 3 for each query, by the scan above.
NEAREST_3 = tuple(_brute_nearest(q, 3) for q in QUERIES)

# --- the autocomplete world ---------------------------------------------------------
WORDS = ("car", "card", "care", "cargo", "cat", "catch", "caterpillar",
         "cell", "center", "centigrade", "chaos", "chapter", "char",
         "dijkstra", "dial", "digit", "fibonacci", "fiber", "file",
         "graph", "heap", "hash", "queue", "stack", "tree")

# --- the shape bound the consolidation leans on -----------------------------------
# FIB_MIN[d] = the smallest subtree a degree-d node of a consolidated Fibonacci
# heap can own: 1, 2, then N(d) = 2 + sum of the N(i) it collected on the way
# up — the Fibonacci recurrence, and the reason a degree can never exceed
# ~1.44*log2(n). extract-min sizes its bucket table from this, not from the
# root count: a consolidation that miscounted a degree then lands on the
# refusal instead of silently writing past an array.
FIB_MIN = (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597,
           2584, 4181, 6765, 10946)

# --- the work bars ------------------------------------------------------------------
# Filled from the reference runs (the solutions' own __main__ prints), not from
# theory: a bar is a ceiling with slack, and the number it catches is a
# mechanism that does not stop doing work, not a solution 3% slower than
# the author's. `WORK_BARS` was empty until every number below was MEASURED
# by the solutions' own `measure()`; it is not empty now, and a bar whose
# measurement disappears is a loud refusal in stage 10's audit, not a pass.
WORK_BARS = {
    # each ceiling is ~15-30% above the measured reference run, and the
    # number is a bar for a MECHANISM THAT NEVER STOPS DOING WORK (a linear
    # sift, a rescan per pop, a prune that never prunes), never for a
    # solution a few percent slower than the author's.
    "heap_sort_cmp": 100000, "heap_sort_swaps": 60000,
    "dary_sort_cmp": 100000, "dary_sort_swaps": 40000,
    "fib_merge_work": 1200,
    "fib_consolidate_work": 15000,
    "fib_cuts": 400, "fib_cascades": 100, "fib_drain_work": 6000,
    "dijkstra_lazy_pops": 20, "dijkstra_lazy_skipped": 10,
    "dijkstra_dary_cmp": 40, "dijkstra_fib_work": 30,
    "dijkstra_fib_cuts": 10, "dijkstra_fib_pops": 10,
    "uf_kruskal_finds": 30, "uf_kruskal_steps": 60,
    "trie_visits": 50,
    "lfu_probes": 10, "lfu_evictions": 3,
    "kd_seen_total": 100, "kd_probes_total": 100,
    "kd_pruned_total": 100,
}
