"""The registry's dependency DAG — what must come first, and what merely should.

`path.PHASES` owns the rows and their `prereq` lists; this module reads them and
nothing else, so the graph cannot drift from the plan. It answers four things:

    graph()       the nodes, the hard edges, each row's dependents, the roots,
                  the waves (longest-path levels), and the two defects a registry
                  can have: a prereq that names no row, and a cycle
    before(row)   everything that must come first, transitively, in wave order
    unlocks(row)  the same closure the other way: everything the row opens up
    advice(row)   the advisory layer below: what a row's own thesis says would be
                  good to have done first, where nothing forces it

`prereq` is the honest dependency. `ADVICE` is advice, never an edge, and every
entry names the row whose thesis asks for it, so it can be audited by reading
the registry rather than by trusting this file.

    python3 codecraft/cli.py dag             # the whole DAG, in waves
    python3 codecraft/cli.py dag <course>    # one row: what comes before it
"""

from . import path as pathmod

# Advice, not edges: row to do first, whose thesis asks for it, and in what words.
ADVICE = {
    "A1": [("A5", "A5's thesis: 'Makes sqs/dynamodb in A1 click' \u2014 and A5 is "
                  "'optional but cheap'")],
    "C2": [("A5", "A5's thesis: 'underpins the agent half' \u2014 the caching, "
                  "idempotency and rate-limit vocabulary C2's loops and budgets "
                  "reuse")],
    "F2": [("C1", "F2's thesis: 'phase C1 owns what to measure' \u2014 F2 is the "
                  "runner, not the metrics")],
    "H1": [("A8", "A8's thesis: 'the engine every training course in this "
                  "repository assumes', and H1 is a training course")],
    "H5": [("A6", "H5's thesis: 'A6 is the distributed half this repo already "
                  "has' \u2014 the same quorums and anti-entropy, at one node")],
    "I11": [("A3", "I11's thesis: 'A3's routing and A7's percentiles are the two "
                   "halves it joins'; A7 is already a prereq")],
    "I12": [("F2", "I12's thesis: 'F1/F2 own the measurement machinery'; F1 is "
                   "already a prereq")],
    "J5": [("E1", "J5's thesis: 'E1's six-key trace is the input' to its metrics")],
    "K5": [("J4", "K5's thesis: 'J4 is the sandbox half and this is the "
                  "data-in-transit half'")],
}


def rows():
    """The registry's rows in plan order, each with its letter, phase and glyph."""
    out = []
    for letter, phase, items in pathmod.PHASES:
        for item in items:
            row = dict(item)
            row["letter"] = letter
            row["phase"] = phase
            row["symbol"] = pathmod.SYMBOL.get(item["kind"], "\u00b7")
            out.append(row)
    return out


def _level(rid, edges, levels):
    """Longest path from a root: 0 when nothing has to come first."""
    if rid in levels:
        return levels[rid]
    level = 0
    for pre in edges.get(rid, ()):
        level = max(level, _level(pre, edges, levels) + 1)
    levels[rid] = level
    return level


def _cycles(edges):
    """Every cycle as the path that closes it. Empty when the registry is a DAG."""
    state, found = {}, []

    def walk(rid, stack):
        if state.get(rid) == 1:
            cut = stack.index(rid) if rid in stack else 0
            found.append(stack[cut:] + [rid])
            return
        if state.get(rid) == 2:
            return
        state[rid] = 1
        for pre in edges.get(rid, ()):
            walk(pre, stack + [rid])
        state[rid] = 2

    for rid in edges:
        walk(rid, [])
    return found


def graph():
    """The DAG, computed from `path.PHASES` and nothing else.

    A prereq that names no row is not hidden: it is reported in `dangles` and
    still counts as one level. A cycle is reported in `cycles`, and then there
    are no waves to report, because there is no order.
    """
    nodes = rows()
    ids = [n["id"] for n in nodes]
    edges = {n["id"]: list(n.get("prereq") or ()) for n in nodes}
    dependents = {rid: [] for rid in ids}
    for rid in ids:
        for pre in edges[rid]:
            dependents.setdefault(pre, []).append(rid)
    cycles = _cycles(edges)
    levels = {}
    if not cycles:
        for rid in ids:
            _level(rid, edges, levels)
    waves = [[] for _ in range(max(levels.values()) + 1)] if levels else []
    for rid in ids:
        if rid in levels:
            waves[levels[rid]].append(rid)
    return {"nodes": nodes, "ids": ids, "edges": edges, "dependents": dependents,
            "roots": [rid for rid in ids if not edges[rid]],
            "dangles": sorted({p for pre in edges.values() for p in pre
                               if p not in edges}),
            "cycles": cycles, "levels": levels, "waves": waves,
            "order": {rid: i for i, rid in enumerate(ids)},
            "advice": {rid: ADVICE.get(rid, ()) for rid in ids}}


def _closure(start, links, g):
    """Everything reachable from `start`, in wave order, `start` excluded."""
    seen, stack, out = {start}, [start], []
    while stack:
        for nxt in links.get(stack.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                out.append(nxt)
                stack.append(nxt)
    return sorted(out, key=lambda rid: (g["levels"].get(rid, 0),
                                        g["order"].get(rid, 0)))


def before(rid, g=None):
    """Everything that must come first, transitively, in wave order."""
    g = g or graph()
    return _closure(rid, g["edges"], g)


def unlocks(rid, g=None):
    """Everything the row opens up, transitively, in wave order."""
    g = g or graph()
    return _closure(rid, g["dependents"], g)


def advice(rid):
    """(row, whose thesis, the words) — worth doing first, forced by nothing."""
    return list(ADVICE.get(rid, ()))


def tracks(g=None):
    """The tracks: what each row nothing waits on ends, and where they merge.

    A track is not written down anywhere. It is the ancestor set of a *terminal*
    row — one nothing depends on — in wave order, so the tracks cannot drift from
    the registry: a prereq added to a row moves it into every track that row
    feeds.

    Because a row can feed more than one terminal, a track is not a partition:
    `shared` names the rows in two or more, which is where the tracks merge and
    where a unit's leverage is. `furthest` is the terminal with the most behind
    it, and `leverage` is the row the most tracks run through.
    """
    g = g or graph()
    by_id = {n["id"]: n for n in g["nodes"]}
    terminals = [rid for rid in g["ids"] if not g["dependents"].get(rid)]
    spines = []
    for rid in terminals:
        coming = before(rid, g)
        if not coming:
            continue
        spines.append({"id": rid, "terminal": by_id[rid], "rows": coming,
                       "size": len(coming),
                       "wave": g["levels"].get(rid, 0)})
    spines.sort(key=lambda s: (-s["size"], g["order"][s["id"]]))
    counts = {}
    for spine in spines:
        for rid in spine["rows"]:
            counts[rid] = counts.get(rid, 0) + 1
    shared = sorted((rid for rid, n in counts.items() if n > 1),
                    key=lambda rid: (-counts[rid], g["order"][rid]))
    return {"spines": spines, "shared": shared, "counts": counts,
            "roots": list(g["roots"]), "terminals": terminals,
            "wave_span": max((s["wave"] for s in spines), default=0),
            "furthest": spines[0] if spines else None,
            "leverage": shared[0] if shared else None}


def track_of(rid, t=None):
    """The tracks a row sits in: (which terminal, its size, its wave)."""
    t = t or tracks()
    return [(s["id"], s["size"], s["wave"]) for s in t["spines"]
            if rid in s["rows"] or rid == s["id"]]


def focus(rid, g=None):
    """One row with both closures, ready to render. None when there is no row."""
    g = g or graph()
    node = next((n for n in g["nodes"] if n["id"] == rid), None)
    if node is None:
        return None
    return {"node": node, "wave": g["levels"].get(rid, 0),
            "waves": len(g["waves"]), "needs": g["edges"].get(rid, []),
            "dependents": g["dependents"].get(rid, []),
            "before": before(rid, g), "after": unlocks(rid, g),
            "advice": advice(rid)}
