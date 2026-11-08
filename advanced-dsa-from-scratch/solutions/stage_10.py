"""The k-d tree: split space, prune by the plane, prove it by counting.

La Rocca, ch. 8 — the last structure of the course and the one the whole
syllabus pays for: a binary tree whose levels alternate axes, built by
medians so it is balanced by construction, answering nearest-neighbour
queries by walking down, then deciding with ONE integer comparison whether
the far subtree could possibly hold a closer point. The pruning is the
mechanism; without it the tree is a slow linear scan that stores more.

THE TIE LAW (from `graphs._brute_nearest`): order by squared distance,
then by the point, then by index. Squared distances are ints, so there is
no epsilon anywhere. The law has teeth the sloppy implementations miss:
when the split plane's squared gap EQUALS the worst distance in hand, a
point in the far subtree can tie on distance and still WIN on point value
— so the far subtree is pruned only when `gap*gap > worst`, never on `>=`.
The fixture's queries hit this (query (3,3) returns (3,4)@24 then (4,5)@2
then (5,5)@29: all three within a narrow band, ordered by point value on
no tie at all but (7,7)'s 29-vs-29 band is pinned by the scan), so a `>=`
implementation disagrees on a pinned row instead of silently later.

DESIGN DECISION — the result set is a sorted list of at most k rows kept
in the tie order by a bisect insert and a truncation: a max-heap of
negated distances gives the same worst bound but loses the ORDERED answer,
and the ORDER is the graded output. k is small (3), so list surgery is the
cheap and the legible thing.

DESIGN DECISION — the three counters (`seen`, `probes`, `pruned`) count
node visits, plane tests, and subtrees skipped. `seen` is what the bar
hangs on: it is the only one that can run away. A prune inverted to
always-descend returns the right rows and pays full linear cost — the
classic "correct but not the structure" bug, invisible to any check that
only reads distances.

THE CAPSTONE PART: `audit()` reads `graphs.WORK_BARS` and every stage's
`measure()` and reports each measured number against its ceiling, refusing
when a bar has no measurement behind it. A course that pins work without
measuring it pins nothing.
"""

from bisect import insort

from graphs import NEAREST_3, POINTS, QUERIES, WORK_BARS


class KdError(Exception):
    """Refusal: a tree or query this k-d tree cannot answer."""


class KDNode:
    """point, its index in POINTS, the split axis, two children."""

    __slots__ = ("point", "index", "axis", "left", "right")

    def __init__(self, point, index, axis):
        self.point = point
        self.index = index
        self.axis = axis
        self.left = None
        self.right = None


def build(points=POINTS):
    """Median split, axis = depth % 2. The sort key is the tie law's key
    (axis value, other value, index) so the tree shape is ONE shape — not
    whichever median a stable sort happened to leave at the pivot."""
    for p in points:
        if (not isinstance(p, tuple) or len(p) != 2
                or any(isinstance(c, bool) or not isinstance(c, int)
                       for c in p)):
            raise KdError("points are int pairs, not %r" % (p,))
    return _build([(p, i) for i, p in enumerate(points)], 0)


def _build(rows, depth):
    if not rows:
        return None
    axis = depth % 2
    rows.sort(key=lambda r: (r[0][axis], r[0][1 - axis], r[1]))
    mid = len(rows) // 2
    node = KDNode(rows[mid][0], rows[mid][1], axis)
    node.left = _build(rows[:mid], depth + 1)
    node.right = _build(rows[mid + 1:], depth + 1)
    return node


def _dist2(point, query):
    return (point[0] - query[0]) ** 2 + (point[1] - query[1]) ** 2


def nearest(tree, query, k=3):
    """The k answers in the tie law's order, plus the three counters.
    Returns (rows, seen, probes, pruned) with rows = ((point, index), ...)."""
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise KdError("k must be an int >= 1, not %r" % (k,))
    best = []
    seen = [0]
    probes = [0]
    pruned = [0]

    def search(node):
        if node is None:
            return
        seen[0] += 1
        d = _dist2(node.point, query)
        row = (d, node.point, node.index)
        if len(best) < k or row < best[-1]:
            insort(best, row)
            del best[k:]
        gap = query[node.axis] - node.point[node.axis]
        # `gap >= 0` walks the right subtree first: right holds the points
        # whose axis value came after the pivot's in the tie-law sort.
        near, far = ((node.right, node.left) if gap >= 0
                     else (node.left, node.right))
        search(near)
        probes[0] += 1
        if len(best) < k or gap * gap <= best[-1][0]:
            search(far)                 # ties win on point value: never `>=`
        else:
            pruned[0] += 1

    search(tree)
    return (tuple((r[1], r[2]) for r in best),
            seen[0], probes[0], pruned[0])


def measure():
    """The kd-tree's own bars: total node visits across the five queries.
    The assertion rows == NEAREST_3 is the fixture grading every visit."""
    tree = build()
    seen = probes = pruned = 0
    for i, query in enumerate(QUERIES):
        rows, s, p, r = nearest(tree, query, 3)
        assert rows == NEAREST_3[i], \
            "k-d nearest disagrees with the scan on query %r: %r != %r" \
            % (query, rows, NEAREST_3[i])
        seen += s
        probes += p
        pruned += r
    linear = len(POINTS) * len(QUERIES)
    assert seen < linear, \
        "the tree visits every point on every query: the prune is not " \
        "pruning (%d of %d)" % (seen, linear)
    return {"kd_seen_total": seen, "kd_probes_total": probes,
            "kd_pruned_total": pruned}


def audit():
    """Every stage's measured work against its bar; a bar with no number
    behind it is a refusal, not a pass."""
    import stage_01
    import stage_02
    import stage_03
    import stage_04
    import stage_05
    import stage_06
    import stage_07
    import stage_08
    import stage_09
    import stage_10
    measured = {}
    for mod in (stage_01, stage_02, stage_03, stage_04, stage_05, stage_06,
                stage_07, stage_08, stage_09, stage_10):
        measured.update(mod.measure())
    missing = sorted(set(WORK_BARS) - set(measured))
    if missing:
        raise KdError("bars with no measurement behind them: %s" % (missing,))
    over = sorted(k for k in WORK_BARS if measured[k] > WORK_BARS[k])
    if over:
        raise KdError("measured work exceeded its bar: %s"
                      % ", ".join("%s=%d>%d" % (k, measured[k], WORK_BARS[k])
                                  for k in over))
    return {k: (measured[k], WORK_BARS[k]) for k in sorted(WORK_BARS)}


if __name__ == "__main__":
    print("stage 10 — k-d tree:", measure())
    for key, (got, cap) in audit().items():
        print("  bar %-22s measured=%d ceiling=%d" % (key, got, cap))
