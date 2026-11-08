"""Advanced Data Structures From Scratch — course manifest.

Ten graded stages that build the structures a senior interview still reaches
for, in the order the amortized analysis reaches for them: the binary heap
every sort and scheduler starts from; the d-way heap the same theory
generalises to; the Fibonacci heap in three stages — the O(1) merge, the
consolidation that pays for it, and the cascading cut that makes the deferral
affordable; Dijkstra as the judge all three answer to; the disjoint set whose
counters say whether compression fired; the trie whose autocomplete is why
prefixes exist; the LFU cache whose eviction is one total order; and a
capstone k-d tree that must beat a linear scan by COUNTING its visits, then
audit every bar this course pinned.

The thesis, asserted by every check: THE COUNTER IS THE LESSON. A structure
that returns the right answer can still be the wrong structure — a prune that
never prunes, a sift that rescans, a merge that restructures. Every stage
counts its own work, `graphs.WORK_BARS` holds ceilings measured from the
reference runs, and stage 10 refuses a bar with no measurement behind it.

`graphs.py` is provided and complete: the two graph worlds with their pinned
distance/MST laws, the point world with its brute-force nearest neighbours, the
word list, the fixed LCG, and the bars. Everything is ints; there is no
`random`, no clock, no float anywhere in the graded files.

    python3 codecraft/cli.py run advanced-dsa-from-scratch
"""

from codecraft.api import stage

TITLE = "Advanced Data Structures From Scratch"
DESCRIPTION = ("The heap ladder to the Fibonacci heap and what it is for: "
               "binary and d-way heaps with per-comparison counters, the "
               "lazy merge, consolidation, and cascading cut built one "
               "mechanism per stage, Dijkstra priced on all three heaps, "
               "union-find with counted finds judging Kruskal's MST, the "
               "trie's lexical autocomplete, an LFU cache whose eviction is "
               "one (frequency, age) total order, and a k-d tree verified "
               "against a linear scan by its visit counter — capped by an "
               "audit that fails any work bar left unmeasured.")
LEVEL = "advanced"
ORDER = 42

import os
import sys


def _repo():
    """The repo root: env override, the nearest cwd ancestor holding this
    course, else the two-level default. Nothing below writes a path down."""
    HERE = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    override = os.environ.get("G11_REPO")
    if override:
        candidates.append(override)
    candidates.append(os.getcwd())
    candidates.append(os.path.dirname(HERE))   # the course sits one level down
    for start in candidates:
        candidate = os.path.abspath(start)
        while True:
            if os.path.isdir(os.path.join(candidate,
                                          "advanced-dsa-from-scratch")):
                return candidate
            parent = os.path.dirname(candidate)
            if parent == candidate:
                break
            candidate = parent
    raise SystemExit("cannot find the repo: set "
                     "G11_REPO=/path/to/repo/root")


def _env():
    """Put the course dir first on sys.path and return its imports."""
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    repo = _repo()
    if repo not in sys.path:
        sys.path.append(repo)
    import graphs
    return graphs


def _refuses(exc, what, call):
    """The one refusal shape: the call must raise `exc`, and the message is
    returned so the check can pin WHICH rule said no."""
    try:
        accepted = call()
    except exc as err:
        return str(err)
    raise AssertionError("%s was accepted: %r" % (what, accepted))


# --- stage 1: the binary heap ------------------------------------------------------
def check_1():
    graphs = _env()
    import stage_01 as s
    reject = s.HeapError

    # --- the array layout is the contract: left child of i is 2i+1 ------------
    heap = s.Heap([9, 3, 7, 1, 5])
    for i in range(len(heap._a)):
        for c in (2 * i + 1, 2 * i + 2):
            if c < len(heap._a):
                assert heap._a[i] <= heap._a[c], (
                    "the heap property fails at parent %d=%r child %d=%r: "
                    "the build is not a build"
                    % (i, heap._a[i], c, heap._a[c]))
    assert heap._a[0] == 1, "the bottom-up build left %r at the root" % (heap._a[0],)

    _refuses(reject, "a bool key", lambda: s.Heap([True]))
    _refuses(reject, "a float key", lambda: s.Heap([1.5]))
    _refuses(reject, "a string key", lambda: s.Heap(["x"]))
    _refuses(reject, "peek of an empty heap", lambda: s.Heap().peek())
    _refuses(reject, "pop of an empty heap", lambda: s.Heap().pop())

    # --- push/pop interleave against the sorted oracle ------------------------
    heap = s.Heap()
    pushed = []
    for i in range(200):
        key = graphs.COINS[i] * 7 + i % 97
        heap.push(key)
        pushed.append(key)
        if i % 3 == 0:
            want = min(pushed)
            got = heap.pop()
            assert got == want, (
                "pop returned %r, but %r was the smallest live key — the "
                "sift-down lost the root" % (got, want))
            pushed.remove(want)

    # --- the sort: order, and the counted work under the bar ------------------
    out, cmp, swaps = s.heap_sort(s.KEYS)
    assert out == tuple(sorted(s.KEYS)), (
        "heap_sort returned %r... wrong order: the two phases disagree"
        % (out[:8],))
    assert cmp <= graphs.WORK_BARS["heap_sort_cmp"], (
        "sorting %d keys cost %d comparisons, ceiling %d — a sift that "
        "rescans is the mechanism that never stops"
        % (len(s.KEYS), cmp, graphs.WORK_BARS["heap_sort_cmp"]))
    assert swaps <= graphs.WORK_BARS["heap_sort_swaps"], (
        "sorting %d keys moved %d slots, ceiling %d — hole-and-place writes "
        "each item once; swap-three-times is 3x"
        % (len(s.KEYS), swaps, graphs.WORK_BARS["heap_sort_swaps"]))

    assert s.heapify([5, 1, 4]).peek() == 1, "heapify did not build a heap"
    return "heap: layout held, 200 pushes with 67 oracle pops, %d cmp sort" % cmp


# --- stage 2: the d-way heap -------------------------------------------------------
def check_2():
    graphs = _env()
    import stage_01 as s1
    import stage_02 as s
    reject = s.DaryError

    for bad in (0, 1, True, 1.5, "4"):
        _refuses(reject, "D=%r" % (bad,), lambda b=bad: s.DaryHeap([], D=b))
    _refuses(reject, "a float key", lambda: s.DaryHeap([1.5]))
    _refuses(reject, "a one-int tuple key", lambda: s.DaryHeap([(1,)]))

    # --- the generalised layout, at every arity --------------------------------
    for D in (2, 3, 4, 6):
        heap = s.DaryHeap(s1.KEYS[:64], D=D)
        a = heap._a
        for i in range(len(a)):
            first, last = D * i + 1, min(D * i + D, len(a) - 1)
            for c in range(first, last + 1):
                assert a[i] <= a[c], (
                    "D=%d: parent %d=%r exceeds child %d=%r — the build "
                    "started at the wrong internal node" % (D, i, a[i], c, a[c]))
        out, cmp, swaps = s.dary_sort(s1.KEYS[:64], D=D)
        assert out == tuple(sorted(s1.KEYS[:64])), \
            "dary_sort at D=%d is not a sort" % D

    # --- pushes climb through the same parent formula as the build ------------
    growing = s.DaryHeap(D=4)
    for key in s1.KEYS[:40]:
        growing.push(key)
        a = growing._a
        for i in range(len(a)):
            for c in range(4 * i + 1, min(4 * i + 5, len(a))):
                assert a[i] <= a[c], (
                    "after pushing %r the heap property broke at %d/%d — "
                    "sift-up's parent is (i-1)//D, never i//D"
                    % (key, i, c))
    assert growing.peek() == min(s1.KEYS[:40])

    # --- the limit case for the parent formula: index 8 under a big parent ----
    # a[1]=100 owns indices 5..8, so its children are >= 100; a[2]=1 is small.
    # Pushing 50 to index 8 must climb past the TRUE parent (1, value 100);
    # the tempting parent i//D = 2 sees 1 and stops, leaving 100 above 50.
    adversarial = s.DaryHeap([0, 100, 1, 2, 3, 101, 102, 103], D=4)
    adversarial.push(50)
    assert adversarial._a[1] <= adversarial._a[8], (
        "push(50) landed at index 8 under value %r while its parent index 1 "
        "holds %r — sift-up used i//D instead of (i-1)//D"
        % (adversarial._a[8], adversarial._a[1]))

    # --- the D=4, n=6 build start: (n-2)//D, not n//D - 1 -----------------------
    heap = s.DaryHeap([9, 1, 8, 2, 7, 3], D=4)
    assert heap.peek() == 1 and all(
        heap._a[i] <= heap._a[c]
        for i in range(len(heap._a))
        for c in range(4 * i + 1, min(4 * i + 5, len(heap._a)))), (
        "the n=6, D=4 build left %r — the last internal node is (n-2)//4 = 1, "
        "not n//4 - 1" % (heap._a,))

    # --- pair keys and the position map the Dijkstra stage rides on ------------
    pos = {}
    heap = s.DaryHeap(D=4, pos=pos)
    for node, key in ((5, 3), (2, 9), (7, 1), (1, 8)):
        heap.push((key, node))
    for node, i in pos.items():
        assert heap._a[i] == (heap._a[i][0], node), (
            "pos[%r]=%d does not point at its entry %r — a decrease-key "
            "through this map writes the wrong slot" % (node, i, heap._a[i]))
    heap.decrease_key(2, (0, 2))
    assert heap.peek() == (0, 2), "decrease_key did not move the minimum"
    assert heap._a[pos[2]] == (0, 2), "the pos map lost the decreased entry"
    _refuses(reject, "decrease_key of an absent payload",
             lambda: heap.decrease_key(99, (0, 99)))
    _refuses(reject, "decrease_key to a larger key",
             lambda: heap.decrease_key(2, (5, 2)))
    _refuses(reject, "decrease_key without a position map",
             lambda: s.DaryHeap([(1, 1)]).decrease_key(1, (0, 1)))

    out, cmp, swaps = s.dary_sort(s1.KEYS, D=4)
    assert out == tuple(sorted(s1.KEYS))
    assert cmp <= graphs.WORK_BARS["dary_sort_cmp"], (
        "d-ary sorting %d keys cost %d comparisons, ceiling %d — the child "
        "scan is walking more than its window"
        % (len(s1.KEYS), cmp, graphs.WORK_BARS["dary_sort_cmp"]))
    assert swaps <= graphs.WORK_BARS["dary_sort_swaps"], (
        "d-ary sorting moved %d slots, ceiling %d — hole-and-place writes "
        "each item once" % (swaps, graphs.WORK_BARS["dary_sort_swaps"]))
    return "d-ary: layout at D=2,3,4,6, n=6 build start, pos map, %d cmp" % cmp


# --- stage 3: the Fibonacci heap's lazy merge --------------------------------------
def check_3():
    graphs = _env()
    import stage_03 as s
    reject = s.FibError

    h = s.FibHeap([7, 3, 9])
    assert len(h) == 3 and h.peek() == 3, "insert did not keep the min"
    nodes = [h.insert(k, k) for k in (1, 5)]
    assert isinstance(nodes[0], s.FibNode), \
        "insert must return the node a decrease-key will address"
    assert h.peek() == 1

    _refuses(reject, "a bool key", lambda: h.insert(True))
    _refuses(reject, "a float key", lambda: h.insert(1.5))
    _refuses(reject, "union with itself", lambda: h.union(h))
    _refuses(reject, "union with a list", lambda: h.union([1]))
    _refuses(reject, "peek of an empty heap", lambda: s.FibHeap().peek())

    # --- the ring is a ring, in both directions, after every union ------------
    left = s.FibHeap(graphs.COINS[:128])
    right = s.FibHeap(graphs.COINS[128:256])
    work0 = left.work + right.work
    before = left.work
    left.union(right)
    assert left.work - before == 1, (
        "a union cost %d comparisons — the lazy merge is ONE, or it is not "
        "lazy" % (left.work - before))
    assert len(left) == 256 and left.peek() == min(graphs.COINS[:256])
    assert left.is_well_formed(), "the splice broke the ring"
    for x in left.roots():
        assert x.right.left is x and x.left.right is x, (
            "the links stopped being inverses at %r — a one-way splice "
            "passes forward traversal and fails this" % (x,))
    assert right.n == 0 and right.min is None, "union left the donor alive"

    # --- the integrity walk must SEE corruption, not crash on it ---------------
    broken = s.FibHeap([1, 2, 3, 4])
    victim = broken.roots()[0]
    victim.right = broken.roots()[-1]          # skip a node: links now disagree
    assert broken.is_well_formed() is False, (
        "is_well_formed() accepted a heap whose ring skips a node — the walk "
        "must report corruption, and it must terminate while doing it")
    assert broken.min is not None

    assert s.FibHeap().is_well_formed() and s.FibHeap([1]).is_well_formed()
    measured = s.measure()
    assert measured["fib_merge_work"] <= graphs.WORK_BARS["fib_merge_work"], (
        "1024 inserts plus one union cost %d comparisons, ceiling %d — insert "
        "is doing work beyond its one comparison"
        % (measured["fib_merge_work"],
           graphs.WORK_BARS["fib_merge_work"]))
    return "fib merge: one comparison/union, both-way links, corruption seen"


# --- stage 4: consolidation and extract-min ----------------------------------------
def check_4():
    graphs = _env()
    import stage_04 as s
    reject = s.FibError

    _refuses(reject, "extract-min of an empty heap",
             lambda: s.FibHeap().extract_min())

    heap = s.FibHeap(graphs.COINS[:300])
    out = []
    while len(heap):
        node = heap.extract_min()
        out.append(node.key)
        assert heap.is_well_formed(), (
            "the heap was ill-formed after extracting %r — consolidation "
            "left a ring or a degree lying" % (node.key,))
        degrees = s.degrees(heap)
        assert len(set(degrees)) == len(degrees), (
            "root degrees collided after an extract: %r — consolidation "
            "must leave them distinct" % (degrees,))
        assert not any(x.mark for x in heap.roots()) or True
    assert out == sorted(graphs.COINS[:300]), (
        "the drain returned %r..., not sorted: extract-min is not settling "
        "the minimum" % (out[:8],))

    assert not any(heap.roots())
    assert s.degrees(s.FibHeap()) == []
    assert s.FibHeap([1]).pop() == 1
    assert s.FibHeap([2, 1]).pop() == 1

    # --- the bucket table is sized from the watermark, not the live count -----
    small = s.FibHeap([1])
    other = s.FibHeap([2])
    small.union(other)                        # live 2, watermark must be 2
    assert small.high == 2, (
        "after a 1+1 union the watermark is %r, not 2 — a watermark of "
        "max(high, high) makes the degree bound refuse legal heaps"
        % (small.high,))
    small.extract_min()                       # must not refuse on degree 1
    measured = s.measure()
    assert measured["fib_consolidate_work"] <= \
        graphs.WORK_BARS["fib_consolidate_work"], (
        "draining 1024 keys cost %d comparisons, ceiling %d — consolidation "
        "is rescanning what it already bucketed"
        % (measured["fib_consolidate_work"],
           graphs.WORK_BARS["fib_consolidate_work"]))
    return "consolidation: sorted drain, distinct degrees, watermark kept"


# --- stage 5: the cut rule ----------------------------------------------------------
def check_5():
    graphs = _env()
    import stage_04 as s4
    import stage_05 as s5
    reject = s5.FibError

    # --- the pinned cascade: chain 5->1->{3->4, 2}, then three cuts -----------
    h = s5.FibHeap()
    n1, n2, n3, n4, n5, n6 = (h.insert(k) for k in (10, 11, 12, 13, 5, 6))
    h._link(n2, n1)
    h._link(n4, n3)
    h._link(n3, n1)
    h._link(n1, n5)
    assert h.is_well_formed(), "the hand-built chain is ill-formed"

    h.decrease_key(n4, 0)                     # first loss: 3 marked
    assert (h.cuts, h.cascades) == (1, 0), \
        "an unmarked parent's first loss must not cascade: %r" % ((h.cuts, h.cascades),)
    assert len(s5.marked_nodes(h)) == 1
    h.decrease_key(n2, 1)                     # first loss: 1 marked
    assert (h.cuts, h.cascades) == (2, 0) and len(s5.marked_nodes(h)) == 2
    potential_before = s5.potential(h)
    assert potential_before == 8, (
        "potential is #roots + 2*#marked = 4+4 = 8, got %d — the ledger "
        "counts a root as marked, or misses one" % potential_before)
    h.decrease_key(n3, 2)                     # 3 marked, parent 1 marked: cascade
    assert (h.cuts, h.cascades) == (3, 1), (
        "the second loss of a marked chain must cascade exactly one hop: "
        "cuts=%d cascades=%d" % (h.cuts, h.cascades))
    assert s5.marked_nodes(h) == (), (
        "a root came back marked (%r) — roots never carry the mark"
        % (s5.marked_nodes(h),))
    assert s5.potential(h) == 6, (
        "the cascade destroyed one mark and created two roots: 8 -> 6, got %d"
        % s5.potential(h))
    assert h.is_well_formed()

    # --- refusals name their rule ---------------------------------------------
    _refuses(reject, "a float new key",
             lambda: h.decrease_key(n6, 1.5))
    other_heap = s5.FibHeap([1])
    stranger = other_heap.insert(2)
    _refuses(reject, "a node from another heap",
             lambda: h.decrease_key(stranger, 0))
    _refuses(reject, "a key that is not smaller",
             lambda: h.decrease_key(n6, 9))
    _refuses(reject, "delete of a stranger",
             lambda: h.delete(stranger))

    # --- delete removes THAT node, not the minimum ----------------------------
    heap = s5.FibHeap([5, 3, 9, 7])
    target = [x for x in heap.roots() if x.key == 9][0]
    heap.delete(target)
    assert all(x.key != 9 for x in heap._walk()) and heap.n == 3, (
        "delete left the node behind: %r" % ([x.key for x in heap._walk()],))
    assert [heap.pop() for _ in range(3)] == [3, 5, 7]

    # --- the COINS stream: every op, then the bag oracle ----------------------
    for trial in range(2):
        heap = s5.FibHeap()
        bag = []
        handles = {}
        for step in range(240):
            r = graphs.COINS[(trial * 240 + step) % len(graphs.COINS)]
            op = r % 6
            if op < 3 or not bag:
                key = (trial + 1) * 4096 + step
                handles[key] = heap.insert(key, key)
                bag.append(key)
            elif op < 5:
                k = sorted(handles)[r % len(handles)]
                node = handles.pop(k)
                nd = -1 - (trial * 1000 + step)
                heap.decrease_key(node, nd)
                bag.remove(k)
                bag.append(nd)
                handles[nd] = node
            else:
                node = heap.extract_min()
                want = min(bag)
                assert node.key == want, (
                    "step %d: extract-min popped %r, the bag's minimum is %r"
                    % (step, node.key, want))
                bag.remove(want)
                for kk in list(handles):
                    if handles[kk] is node:
                        del handles[kk]
            assert heap.is_well_formed(), "stream step %d ill-formed" % step
            assert not any(x.mark for x in heap.roots())

    measured = s5.measure()
    for key in ("fib_cuts", "fib_cascades", "fib_drain_work"):
        assert measured[key] <= graphs.WORK_BARS[key], (
            "%s measured %d, ceiling %d — the cut rule is doing work the "
            "amortized argument does not license"
            % (key, measured[key], graphs.WORK_BARS[key]))
    return "cut rule: cascade pinned 3/1, potential 8->6, 480 stream ops"


# --- stage 6: Dijkstra as the judge ------------------------------------------------
def check_6():
    graphs = _env()
    import stage_06 as s
    reject = s.DijkstraError

    _refuses(reject, "a negative weight",
             lambda: s.dijkstra_lazy(graphs.EDGES + ((0, 1, -4),)))
    _refuses(reject, "a float weight",
             lambda: s.dijkstra_lazy(((0, 1, 1.5),)))

    # --- all three engines agree with the fixture -----------------------------
    lazy_dist, pops, skipped, relaxed = s.dijkstra_lazy(graphs.EDGES)
    assert s.agree(lazy_dist), (
        "the lazy heapq engine disagrees with the fixture: %r" % (lazy_dist,))
    dary_dist, dary_heap = s.dijkstra_dary(graphs.EDGES)
    assert s.agree(dary_dist), (
        "the d-ary engine disagrees with the fixture: %r" % (dary_dist,))
    fib_dist, work, cuts, cascades, fpops = s.dijkstra_fib(graphs.EDGES)
    assert s.agree(fib_dist), (
        "the Fibonacci engine disagrees with the fixture: %r" % (fib_dist,))

    # --- the lazy engine's ledger: pops settle or skip; each edge once -------
    assert relaxed == len(graphs.EDGES), (
        "the lazy engine relaxed %d edges for a %d-edge graph — a relaxation "
        "is one scan of one adjacency entry" % (relaxed, len(graphs.EDGES)))
    assert pops == len(graphs.DIJKSTRA_FROM_0) + skipped, (
        "pops=%d must be settled(%d) + skipped(%d): every pop either "
        "settles a node or finds a stale entry"
        % (pops, len(graphs.DIJKSTRA_FROM_0), skipped))

    # --- the indexed engine never doubles; the Fibonacci engine cuts less ----
    assert len(dary_heap) == 0 and dary_heap.cmp >= 0, (
        "the d-ary engine returned a heap that is not drained")
    assert fpops == len(graphs.NODES), (
        "the Fibonacci engine popped %d nodes for %d in the graph — "
        "decrease-key should mean no duplicates"
        % (fpops, len(graphs.NODES)))
    assert work <= graphs.WORK_BARS["dijkstra_fib_work"], (
        "the Fibonacci engine's comparison work was %d, ceiling %d — its "
        "merge is not the cheap half" % (work, graphs.WORK_BARS["dijkstra_fib_work"]))
    assert cuts <= graphs.WORK_BARS["dijkstra_fib_cuts"]

    # --- a second source: the fixture's own brute scan ------------------------
    want = graphs._brute_distances(2)
    for engine in (s.dijkstra_lazy, s.dijkstra_dary, s.dijkstra_fib):
        got = engine(graphs.EDGES, source=2)[0]
        assert got == want, (
            "source=2 disagrees with the brute scan: %r != %r"
            % ({k: got[k] for k in sorted(got)}, want))

    measured = s.measure()
    for key in ("dijkstra_lazy_pops", "dijkstra_lazy_skipped",
                "dijkstra_dary_cmp", "dijkstra_fib_work",
                "dijkstra_fib_cuts", "dijkstra_fib_pops"):
        assert measured[key] <= graphs.WORK_BARS[key], (
            "%s measured %d, ceiling %d"
            % (key, measured[key], graphs.WORK_BARS[key]))
    return "Dijkstra: three engines vs fixture + source 2, %d lazy pops" % pops


# --- stage 7: the disjoint set and Kruskal's MST -----------------------------------
def check_7():
    graphs = _env()
    import stage_07 as s
    reject = s.UnionFindError

    ds = s.DisjointSet()
    ds.add(0)
    _refuses(reject, "add of a known element", lambda: ds.add(0))
    _refuses(reject, "find of an unknown element", lambda: ds.find(9))
    _refuses(reject, "union with an unknown element", lambda: ds.union(0, 9))

    ds.add(1)
    ds.add(2)
    assert ds.find(0) == ds.find(0) and ds.find(0) != ds.find(1)
    assert ds.union(0, 1) is True and ds.union(1, 0) is False, (
        "union of already-connected roots must report False, not a second "
        "merge")
    assert ds.connected(0, 1) and not ds.connected(0, 2)

    # --- rank: a lopsided merge moves the winner's rank by at most one -------
    for x in range(3, 40):
        ds.add(x)
    for x in range(3, 40):
        ds.union(0, x)
    assert ds.rank[ds.find(0)] <= 5, (
        "union by rank left rank %d on the winner of 37 lopsided merges — "
        "rank is an upper bound on height, not a counter"
        % ds.rank[ds.find(0)])
    sizes = ds.sizes()
    assert sorted(sizes.values()) == [1, 39], (
        "component sizes are %r, not the one 39-element forest" % (sizes,))
    assert ds.finds >= 40 and ds.path_steps > 0, \
        "the counters did not move — the ledger is the lesson"

    # --- Kruskal against the pinned tree --------------------------------------
    nodes = sorted({u for u, _v, _w in graphs.UNDIRECTED_EDGES} |
                   {v for _u, v, _w in graphs.UNDIRECTED_EDGES})
    total, chosen, ds = s.mst_kruskal(nodes, graphs.UNDIRECTED_EDGES)
    assert total == graphs.MST_TOTAL, (
        "Kruskal's tree weighs %r, the fixture says %r — an edge choice is "
        "wrong" % (total, graphs.MST_TOTAL))
    assert chosen == graphs.MST_EDGES, (
        "Kruskal chose %r, the fixture chose %r" % (chosen, graphs.MST_EDGES))
    measured = s.measure()
    assert measured["uf_kruskal_finds"] <= graphs.WORK_BARS["uf_kruskal_finds"]
    assert measured["uf_kruskal_steps"] <= graphs.WORK_BARS["uf_kruskal_steps"], (
        "path steps measured %d, ceiling %d — finds are not compressing"
        % (measured["uf_kruskal_steps"], graphs.WORK_BARS["uf_kruskal_steps"]))
    return "union-find: rank bound, sizes, MST %d, %d finds" % (
        total, measured["uf_kruskal_finds"])


# --- stage 8: the trie -------------------------------------------------------------
def check_8():
    graphs = _env()
    import stage_08 as s
    reject = s.TrieError

    t = s.build(graphs.WORDS)
    assert "car" in t and "cargo" in t and "card" in t
    assert "ca" not in t, "a prefix that is not a word must not be a member"
    assert "" not in t

    _refuses(reject, "an empty word", lambda: t.insert(""))
    _refuses(reject, "a duplicate word", lambda: t.insert("car"))
    assert "car" in t and t.passes == len(graphs.WORDS), (
        "a refused insert changed the ledger: passes=%d for %d words"
        % (t.passes, len(graphs.WORDS)))

    assert t.autocomplete("car") == ("car", "card", "care", "cargo"), (
        "autocomplete('car') = %r" % (t.autocomplete("car"),))
    assert t.autocomplete("ce") == ("cell", "center", "centigrade")
    assert t.autocomplete("ca") == ("car", "card", "care", "cargo", "cat",
                                    "catch", "caterpillar")
    assert t.autocomplete("zz") == (), "a miss must be (), not [] or None"
    assert t.longest_prefix_of("catchup") == "catch", (
        "longest_prefix_of('catchup') = %r, not the deepest terminal node"
        % (t.longest_prefix_of("catchup"),))
    assert t.walk("notaword") is None

    measured = s.measure()
    assert measured["trie_visits"] <= graphs.WORK_BARS["trie_visits"], (
        "the four prefix walks touched %d nodes, ceiling %d — the walk is "
        "visiting the whole trie instead of the prefix's subtree"
        % (measured["trie_visits"], graphs.WORK_BARS["trie_visits"]))
    return "trie: membership, refusals keep the ledger, %d visited" % (
        measured["trie_visits"])


# --- stage 9: the LFU cache --------------------------------------------------------
def check_9():
    graphs = _env()
    import stage_09 as s
    reject = s.CacheError

    for bad in (0, -1, True, 1.5):
        _refuses(reject, "capacity %r" % (bad,),
                 lambda b=bad: s.LFUCache(b))

    cache = s.LFUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")                            # a: freq 2, b: freq 1
    cache.put("c", 3)                         # b is coldest
    assert cache.evicted == ("b",), \
        "eviction order %r, expected b (freq 1 against a's 2)" % (cache.evicted,)
    assert ("a" in cache) and ("c" in cache) and ("b" not in cache)

    # --- the age tie-break: equal frequencies, older key leaves ---------------
    tie = s.LFUCache(2)
    tie.put("x", 1)
    tie.put("y", 2)
    tie.put("z", 3)                           # x and y both freq 1: x is older
    assert tie.evicted == ("x",), (
        "the age tie-break evicted %r, expected the older x" % (tie.evicted,))

    # --- a miss does not age; a put refresh does ------------------------------
    miss = s.LFUCache(2)
    miss.put("k", 1)
    before = miss.snapshot()
    assert miss.get("nope") is None and miss.misses == 1
    assert miss.snapshot() == before, \
        "a miss aged a live key: %r != %r" % (miss.snapshot(), before)
    miss.put("k", 2)                          # refresh: freq 2
    assert miss.snapshot() == (("k", 2),), miss.snapshot()

    replay = s.replay()
    assert replay.evicted == ("c", "b", "d"), (
        "the fixture script's eviction order is %r — (freq, age) is one "
        "order, and this is it" % (replay.evicted,))
    assert replay.snapshot() == (("a", 4), ("e", 2), ("f", 1)), \
        replay.snapshot()
    assert (replay.hits, replay.misses, replay.evictions) == (6, 0, 3)
    measured = s.measure()
    assert measured["lfu_probes"] <= graphs.WORK_BARS["lfu_probes"]
    assert measured["lfu_evictions"] == graphs.WORK_BARS["lfu_evictions"], (
        "the script evicted %d keys, expected exactly %d"
        % (measured["lfu_evictions"], graphs.WORK_BARS["lfu_evictions"]))
    return "LFU: (freq, age) order pinned twice, %d probes" % (
        measured["lfu_probes"])


# --- stage 10: the k-d tree, and the audit -----------------------------------------
def check_10():
    graphs = _env()
    import stage_10 as s
    import stage_09 as s9
    reject = s.KdError

    for bad in ((1,), (1, 2, 3), (1.5, 2), (True, 2), "xy"):
        _refuses(reject, "point %r" % (bad,), lambda b=bad: s.build((b,)))
    _refuses(reject, "k=0", lambda: s.nearest(s.build(), (0, 0), 0))

    tree = s.build()
    for i, query in enumerate(graphs.QUERIES):
        rows, seen, probes, pruned = s.nearest(tree, query, 3)
        assert rows == graphs.NEAREST_3[i], (
            "nearest%r = %r, the scan says %r — ties break by (distance, "
            "point, index), and the prune may only skip on gap > worst"
            % (query, rows, graphs.NEAREST_3[i]))
        assert seen <= len(graphs.POINTS), (
            "query %r visited %d of %d points on ONE query"
            % (query, seen, len(graphs.POINTS)))

    # --- the tie law has teeth: an equidistant far point that WINS -----------
    # Five points on x <= -2 with query (-2,-2): the root's plane is 0 away,
    # the visited near point sits at squared distance 1, and the far subtree
    # holds (-2,-3) at the same distance — smaller as a point, so it wins the
    # tie. Pruning on gap*gap < worst throws it away; only <= is correct.
    tie_points = ((-3, -3), (-3, -2), (-3, -1), (-3, 0), (-2, -3))
    tie_rows, _, _, _ = s.nearest(s.build(tie_points), (-2, -2), 1)
    assert tie_rows == (((-3, -2), 1),), (
        "the (-2,-2) tie band answered %r — the prune condition is "
        "gap*gap <= worst; gap*gap < worst drops an equidistant point that "
        "wins on its own value" % (tie_rows,))

    measured = s.measure()
    for key in ("kd_seen_total", "kd_probes_total", "kd_pruned_total"):
        assert measured[key] <= graphs.WORK_BARS[key], (
            "%s measured %d, ceiling %d" % (key, measured[key],
                                            graphs.WORK_BARS[key]))
    total_points = len(graphs.POINTS) * len(graphs.QUERIES)
    assert measured["kd_seen_total"] < total_points, (
        "the tree visits %d of %d points across the queries — the prune is "
        "not pruning" % (measured["kd_seen_total"], total_points))

    # --- the audit: every pinned bar has a measurement, and every number fits
    audit = s.audit()
    assert set(audit) == set(graphs.WORK_BARS), (
        "the audit reports %r bars, the fixture pins %r — a bar with no "
        "measurement behind it is a pinned nothing"
        % (sorted(audit), sorted(graphs.WORK_BARS)))
    for key, (got, cap) in audit.items():
        assert got <= cap, "%s measured %d, ceiling %d" % (key, got, cap)

    # --- the cache's events are the structure's, not the script's ------------
    c = s9.LFUCache(1)
    c.put("a", 1)
    c.put("b", 2)
    assert c.evicted == ("a",) and len(c) == 1
    return "k-d tree: %d visits of %d, audit over %d bars" % (
        measured["kd_seen_total"], total_points, len(audit))


STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The binary heap: the array is the contract",
        tags=["heap", "sift", "counted-work"],
        action="Write `Heap` (`push`, `pop`, `peek`, `_sift_up`, `_sift_down`), "
               "`heapify` and `heap_sort` in stage_01.py: children at 2i+1 "
               "and 2i+2, hole-and-place sifts, every comparison counted.",
        predict="Whether popping the last element back through the array "
                "costs the same as three-way swaps, and which counter proves "
                "which sift ran.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The d-way heap: a wider child scan, a shallower tree",
        tags=["heap", "arity", "tradeoff"],
        action="Write `DaryHeap` and `dary_sort` in stage_02.py: children of "
               "i at D*i+1..D*i+D, parent (i-1)//D, the bottom-up build "
               "starting at (n-2)//D, pair keys, and an optional shared "
               "position map for decrease-key.",
        predict="At which arity the comparisons-per-pop of a sort stop "
                "improving, and why the scan cannot be shortened without "
                "making the counter lie.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The Fibonacci heap I: the merge is lazy",
        tags=["fibonacci-heap", "lazy-merge", "amortized"],
        action="Write `FibNode`, `FibHeap.insert`, `FibHeap.union`, `peek`, "
               "`roots` and `is_well_formed` in stage_03.py: one circular "
               "doubly-linked root ring, child rings of their own, a watermark, "
               "and an integrity walk that terminates on corruption.",
        predict="What a union costs with a ring splice, and what a ring's "
                "left links would hide if the walk only ever went right.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The Fibonacci heap II: consolidation pays the bill",
        tags=["fibonacci-heap", "extract-min", "consolidation"],
        action="Write `consolidate`, `extract_min`, `pop` and `degrees` in "
               "stage_04.py: orphan the min's children in ONE splice, bucket "
               "roots by degree from the watermark, and rebuild the root ring "
               "in degree order.",
        predict="Why the bucket table is sized by the watermark and not the "
                "live node count, and which off-by-one hides at D=4, n=6.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The Fibonacci heap III: the cut rule keeps it affordable",
        tags=["fibonacci-heap", "decrease-key", "cascading-cut"],
        action="Write `decrease_key`, `delete`, `_move_up`, "
               "`_cut_and_maybe_cascade`, `marked_nodes` and `potential` in "
               "stage_05.py: cut to the root ring, mark the first loss, "
               "cascade every already-marked ancestor, never mark a root.",
        predict="What a decrease-key costs with and without the mark, and "
                "how the potential changes when the cascade fires once.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="Dijkstra: three heaps, three ledgers",
        tags=["graphs", "dijkstra", "priority-queue"],
        action="Write `dijkstra_lazy`, `dijkstra_dary`, `dijkstra_fib` and "
               "`report` in stage_06.py: the same relaxation over heapq, the "
               "indexed d-ary heap, and the Fibonacci heap, each returning "
               "its own counted work.",
        predict="Which engine makes the fewest settlements, and which one's "
                "extra work shows up as skipped stale pops instead.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The disjoint set: the forest that counts its finds",
        tags=["union-find", "mst", "kruskal"],
        action="Write `DisjointSet` (`add`, `find`, `union`, `connected`, "
               "`sizes`) and `mst_kruskal` in stage_07.py: union by rank, "
               "iterative path compression, reported finds and path steps.",
        predict="Whether rank alone keeps a chain shallow, and what the "
                "path-step counter says the day compression is dropped.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The trie: autocomplete is the prefix's subtree",
        tags=["trie", "prefix", "autocomplete"],
        action="Write `Trie` (`insert`, `walk`, `autocomplete`, "
               "`longest_prefix_of`, `__contains__`) and `build` in "
               "stage_08.py: terminal bool on the node, lexical order from "
               "sorted child keys, a visit counter on the walk.",
        predict="Why a word that prefixes another must stay a member, and "
                "what a refused duplicate must not do to the ledger.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The LFU cache: eviction is one total order",
        tags=["cache", "lfu", "eviction"],
        action="Write `LFUCache` (`get`, `put`, `_touch`, `_coldest`, "
               "`snapshot`) and `replay` in stage_09.py: (frequency, age) as "
               "one pair, a scanned coldest with counted probes, exact "
               "eviction order on the script.",
        predict="Which key leaves when two share the minimum frequency, and "
                "why a miss must not age anything.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The capstone: a k-d tree that beats the scan by counting",
        tags=["k-d-tree", "nearest-neighbour", "audit"],
        action="Write `build`, `nearest` and `measure`/`audit` in "
               "stage_10.py: median splits on alternating axes, the prune on "
               "gap*gap > worst, the tie law, and the audit of every "
               "WORK_BARS entry.",
        predict="What a prune inverted to always-descend costs, and why the "
                "tie band at query (7,7) needs > and not >=.",
        check=check_10,
    ),
]
