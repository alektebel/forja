"""The stage 4 solution: leaves on pages, siblings linked, a full leaf splits."""

import disk as dk
import pages as pg
import tables as tb
import ops

TREE_KEYS = ("root", "height", "leaves", "entries")

#: how many (key, rid) entries one leaf holds before it splits — small on
#: purpose: a 256-byte page is a handful of pairs, and the check needs a
#: leaf it can fill.
LEAF_FANOUT = 4

#: the page the tree's meta lives on: root, height, leaf head. The pager's
#: own meta page is 0; the tree takes the next one.
_TREE_META = 1


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, what):
    """The one refusal: a reason word and the offender that earned it."""
    raise QueryError("%s: %r" % (reason, what))


# --- node encoding: one page per node ---------------------------------------
# a leaf page: the tag byte _LEAF, the next-leaf page (one byte, 0 ends the
# chain), then (key, rid) pairs as two varints each.
# an inner page: the tag byte _INNER, the entry count, then per entry the
# separator key as a varint and the child page as a varint.
_LEAF = b"\x01"
_INNER = b"\x02"


def _varint(value):
    """A 7-bit varint, big-endian, non-negative — the pager's own law."""
    if value < 0:
        _refuse("negative", value)
    out = bytearray([value & 0x7F])
    value >>= 7
    while value:
        out.insert(0, 0x80 | (value & 0x7F))
        value >>= 7
    return bytes(out)


def _read_varint(data, at):
    """One varint and where it ended."""
    value = 0
    while True:
        byte = data[at]
        value = (value << 7) | (byte & 0x7F)
        at += 1
        if not byte & 0x80:
            return value, at


def _write_leaf(pager, page, pairs, nxt):
    """One leaf page: tag, next pointer, the pairs."""
    body = _LEAF + _varint(nxt) + b"".join(_varint(k) + _varint(r)
                                          for (k, r) in pairs)
    pager.write(page, body.ljust(pg.PAGE_SIZE, b"\x00"))


def _read_leaf(pager, page):
    """The pairs and the next pointer back from a leaf page."""
    data = pager.read(page)
    if data[0:1] != _LEAF:
        _refuse("not_leaf", page)
    nxt, at = _read_varint(data, 1)
    pairs = []
    while at < len(data) and data[at] != 0:
        key, at = _read_varint(data, at)
        rid, at = _read_varint(data, at)
        pairs.append((key, rid))
    return pairs, nxt


def _write_inner(pager, page, child0, separators):
    """One inner page: tag, count, the first child, then (sep, child) pairs."""
    body = _INNER + _varint(len(separators)) + _varint(child0) + b"".join(
        _varint(k) + _varint(c) for (k, c) in separators)
    pager.write(page, body.ljust(pg.PAGE_SIZE, b"\x00"))


def _read_inner(pager, page):
    """The first child and the (separator, child) pairs from an inner page."""
    data = pager.read(page)
    if data[0:1] != _INNER:
        _refuse("not_inner", page)
    count, at = _read_varint(data, 1)
    child0, at = _read_varint(data, at)
    separators = []
    for _ in range(count):
        key, at = _read_varint(data, at)
        child, at = _read_varint(data, at)
        separators.append((key, child))
    return child0, separators


def build(pager, entries):
    """Leaves in order, siblings linked, the shape answered."""
    entries = tuple(entries)
    for before, after in zip(entries, entries[1:]):
        if after[0] < before[0]:
            _refuse("unsorted", after)
    if not entries:
        _refuse("empty", entries)

    pager.allocate()          # the tree's meta page: root, height, leaf head
    leaf_pages = []
    for start in range(0, len(entries), LEAF_FANOUT):
        chunk = entries[start:start + LEAF_FANOUT]
        page = pager.allocate()
        leaf_pages.append((page, chunk))
    for (page, chunk), (next_page, _next_chunk) in zip(leaf_pages,
                                                       leaf_pages[1:]):
        _write_leaf(pager, page, chunk, next_page)
    last_page, last_chunk = leaf_pages[-1]
    _write_leaf(pager, last_page, last_chunk, 0)

    if len(leaf_pages) == 1:
        root, height = leaf_pages[0][0], 1
    else:
        separators = [(chunk[0][0], leaf_page)
                      for (leaf_page, chunk) in leaf_pages[1:]]
        root = pager.allocate()
        _write_inner(pager, root, leaf_pages[0][0], separators)
        height = 2
    pager.write(_TREE_META, (_varint(root) + _varint(height))
                .ljust(pg.PAGE_SIZE, b"\x00"))
    return {"root": root, "height": height, "leaves": len(leaf_pages),
            "entries": len(entries), "_pager": pager}


def lookup(tree, key):
    """The walk: from the root, following separators, the matching entries."""
    if isinstance(key, tuple):
        lo, hi = key
    else:
        lo = hi = key
    pager = tree["_pager"]
    page = tree["root"]
    for _level in range(tree["height"] - 1):
        child0, separators = _read_inner(pager, page)
        child = child0
        for separator, next_child in separators:
            if lo >= separator:
                child = next_child
        page = child
    out = []
    while page:
        pairs, nxt = _read_leaf(pager, page)
        for (k, rid) in pairs:
            if lo <= k <= hi:
                out.append((k, rid))
            elif k > hi:
                return tuple(out)
        page = nxt
    return tuple(out)


def split(pager, node):
    """A full leaf divides at its midpoint; the parent gains the separator."""
    pairs, nxt = _read_leaf(pager, node)
    if len(pairs) < LEAF_FANOUT:
        _refuse("not_full", node)
    mid = (len(pairs) + 1) // 2
    first, second = pairs[:mid], pairs[mid:]
    fresh = pager.allocate()
    _write_leaf(pager, node, first, fresh)
    _write_leaf(pager, fresh, second, nxt)
    separator = second[0][0]
    # the parent (the tree's root while the tree is two levels) gains it
    meta = pager.read(_TREE_META)
    root, _height = _read_varint(meta, 0)
    child0, separators = _read_inner(pager, root)
    if node == child0:
        _write_inner(pager, root, node,
                     [(separator, fresh)] + separators)
    else:
        out = []
        for (k, c) in separators:
            out.append((k, fresh) if c == node else (k, c))
            if c == node:
                break
        _write_inner(pager, root, child0, out)
    return {"root": root, "height": 2, "leaves": len(separators) + 2,
            "entries": len(first) + len(second), "_pager": pager}
