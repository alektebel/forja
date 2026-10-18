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
are still the entries that went in, in order, because a tree that reordered
the world's index would be a lie with pages.

The tree is built on the pager the world provides, so every node is a page
the storage floor can lose, tear, or refuse — and stage 8's commit and stage
9's recovery will hold their promises against exactly these pages.

DESIGN DECISION — Why does `build` answer a shape record instead of a tree
object?
Because the shape is what the planner prices (stage 5's index cost is the
tree's height plus the matched leaves) and what the check can hold against
arithmetic — leaves × capacity bounds the entries, height bounds the walk.
A tree object would invite later stages to walk its internals; the shape
record keeps the node layout this stage's property.

DESIGN DECISION — Why does `split` take a node rather than happen inside
`build`?
Because the split is the course's unit of teaching for this stage: build with
a capacity small enough and every insert is a split, and the check can plant
one full leaf and watch it divide. Folding it into build would make the tree
appear finished but never show the seam the stage exists to teach — and the
check asserts both halves and the separator against the entries inserted,
which needs the operation on its own.

DESIGN DECISION — Why do leaves link their siblings?
Because the range scan is the index's second half: `lookup` for a range
answers the leaf chain from `lo` to `hi`, and a chain that misses an entry
breaks the executor's answer without breaking any single page. The links are
the invariant the check walks leaf by leaf.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

TREE_KEYS = ("root", "height", "leaves", "entries")

#: how many (key, rid) entries one leaf holds before it splits — small on
#: purpose: a 256-byte page is a handful of pairs, and the check needs a
#: leaf it can fill.
LEAF_FANOUT = 4


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def build(pager, entries):
    """The tree: leaves in order, siblings linked, the shape answered.

    `entries` is a sorted tuple of (key, rid) pairs — `EVENTS_INDEX`'s shape.
    Answers TREE_KEYS: the root page, the height (a single leaf is height 1),
    the leaf count, the entry count. Refuses entries that are not sorted,
    naming the pair that broke the order."""

    raise NotImplementedError("stage 4: implement build()")


def lookup(tree, key):
    """The entries whose key matches, from the root down.

    `key` is a (lo, hi) range or a bare key. A range answers the entries in
    the leaf chain from lo to hi; a bare key answers the entries whose key
    equals it. The walk is the stage's own; the entries are the world's."""

    raise NotImplementedError("stage 4: implement lookup()")


def split(pager, node):
    """A full leaf divides: first half stays, second moves, parent gains.

    `node` is a page holding a full leaf. Answers TREE_KEYS for the tree
    after the split — the separator the parent gains is the second leaf's
    first key. The entries on both halves are still the entries that went
    in, in order."""

    raise NotImplementedError("stage 4: implement split()")
