"""Disjoint sets: the forest that counts its finds.

La Rocca, ch. 3 / CLRS ch. 21 — union-find is two ideas and the counters
tell which one you actually built: union BY RANK keeps trees shallow
(O(log n) without any path compression at all), and COMPRESSION on find
flattens the path you just walked. The amortized bound (inverse Ackermann)
is not checkable on 600 operations; what IS checkable is the shape and
the counters, which is exactly why every method counts its own work.

DESIGN DECISION — `find` is iterative and compresses every node on the
climb, not just the argument: the recursive one-liner compresses on the
way out of a call stack, which is the same set of nodes but costs O(path)
stack frames — and a 100k-deep chain (the mutation this stage exists to
catch: union-by-rank dropped) recurses into a crash the check cannot
distinguish from a slow test. The loop keeps the same nodes in the same
counters, visibly.

DESIGN DECISION — rank is an upper bound on height, maintained only when
the roots tie: a rank that "updates" on every union is recomputing height
the bound exists to avoid. The check pins `rank[root]` after a lopsided
merge: the winner's rank moved by at most one.
"""

from graphs import MST_EDGES, MST_TOTAL, UNDIRECTED_EDGES


class UnionFindError(Exception):
    """Refusal: a call about an element the forest does not know."""


class DisjointSet:
    """parent/rank dicts, with finds and unions on the ledger."""

    def __init__(self):
        self.parent = {}
        self.rank = {}
        self.finds = 0             # find() calls, each with the path walked
        self.path_steps = 0        # parent-pointer hops inside all finds
        self.unions = 0
        self.roots = 0

    def add(self, x):
        if x in self.parent:
            raise UnionFindError("add of a known element %r" % (x,))
        self.parent[x] = x
        self.rank[x] = 0
        self.roots += 1

    def find(self, x):
        if x not in self.parent:
            raise UnionFindError("find of an unknown element %r" % (x,))
        self.finds += 1
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        # compress on the way back: every node touched points at the root
        while self.parent[x] != x:
            nxt = self.parent[x]
            self.path_steps += 1
            self.parent[x] = root
            x = nxt
        self.path_steps += 1       # the hop that landed on the root
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.unions += 1
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        self.roots -= 1
        return True

    def connected(self, a, b):
        return self.find(a) == self.find(b)

    def sizes(self):
        """component -> member count, the shape report the check reads."""
        table = {}
        for x in self.parent:
            r = self.find(x)
            table[r] = table.get(r, 0) + 1
        return table


def mst_kruskal(nodes, edges, ds_factory=DisjointSet):
    """Kruskal on the fixture's UNDIRECTED_EDGES: sort by weight, union the
    endpoints, keep an edge iff it joins two components. Returns
    (total, chosen, ds) — the structure's counters ride along because this
    is the stage where finds are the lesson."""
    ds = ds_factory()
    for n in nodes:
        ds.add(n)
    order = sorted(((w, u, v) for u, v, w in edges))
    chosen = []
    total = 0
    for w, u, v in order:
        if ds.union(u, v):
            chosen.append((u, v, w))
            total += w
    return total, tuple(chosen), ds



def measure():
    """The measured bars for this stage: Kruskal on the fixture's
    undirected graph — finds is the number that says whether compression
    fired, and the answer must be the pinned tree."""
    nodes = sorted({u for u, _v, _w in UNDIRECTED_EDGES} |
                   {v for _u, v, _w in UNDIRECTED_EDGES})
    total, chosen, ds = mst_kruskal(nodes, UNDIRECTED_EDGES)
    assert total == MST_TOTAL and chosen == MST_EDGES, \
        "Kruskal disagrees with the fixture's MST: %r/%r" % (total, chosen)
    return {"uf_kruskal_finds": ds.finds, "uf_kruskal_steps": ds.path_steps}


if __name__ == "__main__":
    print("stage 7 — union-find:", measure())
