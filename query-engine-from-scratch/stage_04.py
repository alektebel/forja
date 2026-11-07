"""Query Engine From Scratch — stage 4: The index: a B+tree that splits.

The events index is a sorted list of `(ts, id)` pairs the world pinned; the
B+tree is what turns a sorted list into a structure a scan can walk and a
point query can land in. `build` inserts the entries leaf by leaf — each leaf
a page the pager holds, siblings linked so a range read is a walk, not a
search — and answers the shape: the root page, the height, the leaf count,
the entry count. `lookup` is the walk: from the root, following the
separators, answering the entries whose key matches, or the leaf chain from
`lo` to `hi` for a range. `split` is the half that makes it a tree: a full
leaf divides at its midpoint, the first half stays, the second moves to a
fresh page, the parent gains the separator — and the entries on both sides
are still the entries that went in, in order.

The tree is built on the pager the world provides, so every node is a page
the storage floor can lose, tear, or refuse — and stage 8's commit and stage
9's recovery will hold their promises against exactly these pages.

DESIGN DECISION — Why does `build` answer a shape record instead of a tree
object?
Because the shape is what the planner prices (stage 5's index cost is the
tree's height plus the matched leaves) and what the check can hold against
arithmetic — leaves × capacity bounds the entries, height bounds the walk.
The pager rides alongside the shape, because a tree without its pager is a
map without the territory.

DESIGN DECISION — Why does `split` take a node rather than happen inside
`build`?
Because the split is the course's unit of teaching for this stage: the check
can plant one full leaf and watch it divide, and assert both halves and the
separator against the entries inserted — which needs the operation on its own.

DESIGN DECISION — Why do leaves link their siblings?
Because the range scan is the index's second half: `lookup` for a range
answers the leaf chain from `lo` to `hi`, and a chain that misses an entry
breaks the executor's answer without breaking any single page.

DESIGN DECISION — Why is the byte layout packed bytes rather than the pager's
record format?
Because a tree node's payload is (key, rid) pairs plus a sibling pointer and
a count — a shape the record format does not have. The layout is this stage's
own law and `_read_leaf`/`_read_inner` are its only doors, so a later stage
that must survive a crash re-reads the tree through the same doors.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

TREE_KEYS = ("root", "height", "leaves", "entries")

#: how many (key, rid) entries one leaf holds before it splits — eight, the
#: number the planner's arithmetic needs: 120 entries at fanout 8 are 15
#: leaves, height 2, and an index scan wins exactly when the matches fit
#: four leaves (the boundary the world's facts pin). The check holds it.
LEAF_FANOUT = 8


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, *names):
    raise QueryError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


# --- the node byte layouts ---------------------------------------------------
#
# a leaf page: [kind=0][count][next lo][next hi] then per entry two varints
# (key, rid). `next` is the sibling link, pg.NULL when there is none.
#
# an inner page: [kind=1][count][0][0] then per child one varint child page,
# with one varint separator before every child but the first. separator i is
# the smallest key in child i+1's subtree.

_LEAF = 0
_INNER = 1


def _varint(value):
    """One int as 1..4 big-endian 7-bit groups, the pager's own law."""
    out = bytearray()
    while True:
        out.insert(0, value & 0x7F)
        value >>= 7
        if not value:
            break
    return bytes(out)


def _read_varint(raw, i):
    """The varint at raw[i:], answering (value, next index)."""
    value = 0
    while True:
        value = (value << 7) | (raw[i] & 0x7F)
        i += 1
        if not raw[i - 1] & 0x80:
            return value, i


def _write_leaf(page_bytes, pairs, nxt):
    body = bytearray([_LEAF, len(pairs), (nxt >> 8) & 0xFF, nxt & 0xFF])
    for (key, rid) in pairs:
        body += _varint(key)
        body += _varint(rid)
    page_bytes[:] = bytes(body.ljust(pg.PAGE_SIZE, b"\x00"))


def _read_leaf(pager, page):
    """One leaf page as (pairs, next sibling page)."""
    raw = pager.read(page)
    if raw[0] != _LEAF:
        _refuse("not_a_leaf", page)
    count = raw[1]
    nxt = (raw[2] << 8) | raw[3]
    i = 4
    pairs = []
    for _ in range(count):
        key, i = _read_varint(raw, i)
        rid, i = _read_varint(raw, i)
        pairs.append((key, rid))
    return tuple(pairs), nxt


def _varint(value):
    """One int as big-endian 7-bit groups, the high bit continuing — the
    pager's own law (pages.py's varint): every group but the last has its
    top bit set, so the byte count is decidable."""
    out = bytearray([value & 0x7F])
    value >>= 7
    while value:
        out.insert(0, 0x80 | (value & 0x7F))
        value >>= 7
    return bytes(out)


def _write_inner(page_bytes, children, separators):
    body = bytearray([_INNER, len(children), 0, 0])
    for i, child in enumerate(children):
        if i:
            body += _varint(separators[i - 1])
        body += _varint(child)
    page_bytes[:] = bytes(body.ljust(pg.PAGE_SIZE, b"\x00"))


def _read_inner(pager, page):
    """One inner page as (child0, separators): the leftmost child page and
    one `(separator, child)` pair per remaining child — the door the walk,
    the parent search and the split's check all use."""
    raw = pager.read(page)
    if raw[0] != _INNER:
        _refuse("not_an_inner", page)
    count = raw[1]
    i = 4
    first, i = _read_varint(raw, i)
    separators = []
    for _ in range(count - 1):
        sep, i = _read_varint(raw, i)
        child, i = _read_varint(raw, i)
        separators.append((sep, child))
    return first, tuple(separators)


def build(pager, entries):
    """The tree: leaves in order, siblings linked, the shape answered.

    `entries` is a sorted tuple of (key, rid) pairs — `EVENTS_INDEX`'s shape.
    Answers TREE_KEYS (plus the pager the walk needs): the root page, the
    height (a single leaf is height 1), the leaf count, the entry count.
    Refuses entries that are not sorted, naming the pair that broke the
    order."""
    entries = tuple(entries)
    for j in range(1, len(entries)):
        if entries[j][0] < entries[j - 1][0]:
            _refuse("unsorted", entries[j])
    if not entries:
        _refuse("empty", entries)
    leaves = [entries[start:start + LEAF_FANOUT]
              for start in range(0, len(entries), LEAF_FANOUT)]
    pages = []
    chunk = bytearray(pg.PAGE_SIZE)
    for i, pairs in enumerate(leaves):
        page = pager.allocate()
        pages.append(page)
        # write the previous leaf now that its sibling's page number exists:
        # the forward link is known only when the next page is allocated
        if i:
            _write_leaf(chunk, leaves[i - 1], page)
            pager.write(pages[i - 1], bytes(chunk))
    _write_leaf(chunk, leaves[-1], pg.NULL)
    pager.write(pages[-1], bytes(chunk))

    if len(pages) == 1:
        return {"root": pages[0], "height": 1, "leaves": 1,
                "entries": len(entries), "pager": pager}

    inner = bytearray(pg.PAGE_SIZE)
    _write_inner(inner, tuple(pages),
                 tuple(pairs[0][0] for pairs in leaves[1:]))
    root = pager.allocate()
    pager.write(root, bytes(inner))
    return {"root": root, "height": 2, "leaves": len(pages),
            "entries": len(entries), "pager": pager}


def lookup(tree, key):
    """The entries whose key matches, from the root down.

    `key` is a (lo, hi) range or a bare key. A range answers the entries in
    the leaf chain from lo to hi; a bare key answers the entries whose key
    equals it. The walk is the stage's own; the entries are the world's."""
    if isinstance(key, tuple):
        lo, hi = key
    else:
        lo = hi = key
    pager = tree["pager"]

    # descend to the leaf that may first hold `lo`
    page = tree["root"]
    for _ in range(tree["height"] - 1):
        child0, pairs = _read_inner(pager, page)
        page = child0
        for (sep, child) in pairs:
            if lo >= sep:
                page = child

    out = []
    while page != pg.NULL:
        pairs, nxt = _read_leaf(pager, page)
        for (k, rid) in pairs:
            if k > hi:
                return tuple(out)
            if k >= lo:
                out.append((k, rid))
        page = nxt
    return tuple(out)


def _roots(pager, node):
    """The inner pages that name `node` among their children — a small file,
    so the parent is found by reading the inner pages that exist."""
    found = []
    for page in range(1, pg.PAGES):
        raw = pager.read(page)
        if raw[0] == _INNER:
            child0, pairs = _read_inner(pager, page)
            if node == child0 or node in (child for (_s, child) in pairs):
                found.append(page)
    return found


def split(pager, node):
    """A full leaf divides: first half stays, second moves, parent gains.

    `node` is a page holding a full leaf. Answers TREE_KEYS for the tree
    after the split — the separator the parent gains is the second leaf's
    first key. The entries on both halves are still the entries that went
    in, in order."""
    pairs, nxt = _read_leaf(pager, node)
    if len(pairs) < LEAF_FANOUT:
        _refuse("not_full", node, len(pairs))
    mid = (len(pairs) + 1) // 2
    first, second = pairs[:mid], pairs[mid:]

    fresh = pager.allocate()
    chunk = bytearray(pg.PAGE_SIZE)
    _write_leaf(chunk, first, fresh)
    pager.write(node, bytes(chunk))
    _write_leaf(chunk, second, nxt)
    pager.write(fresh, bytes(chunk))

    # the parent gains the second half's first key as the separator in front
    # of the fresh leaf
    parents = _roots(pager, node)
    if not parents:
        _refuse("no_parent", node)
    root_page = parents[0]
    child0, pairs = _read_inner(pager, root_page)
    # rebuild the child sequence with `fresh` right after `node`
    children = [child0] + [child for (_s, child) in pairs]
    seps = [sep for (sep, _c) in pairs]
    idx = children.index(node)
    children.insert(idx + 1, fresh)
    seps.insert(idx, second[0][0])
    inner = bytearray(pg.PAGE_SIZE)
    _write_inner(inner, tuple(children), tuple(seps))
    pager.write(root_page, bytes(inner))

    return {"root": root_page, "height": 2, "leaves": len(children),
            "entries": len(first) + len(second), "pager": pager}
