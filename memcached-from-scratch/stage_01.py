"""Memcached From Scratch — stage 1: the ring, and the hash that must not move.

A memcached client routes a key to a server with no coordination, no mapping
on the server, and no version of the cluster stored anywhere. This stage
builds that router: keys land on nodes through positions on a circle, and
the circle survives the addition and removal of nodes without asking anyone.

DESIGN DECISION — why md5 of the key's bytes, and never `hash()`?
    The tempting alternative is Python's builtin `hash(s)`: free, fast, one
    call. Its cost is that CPython salts `hash()` per process, so two
    clients — or a client and this course's checks — route the same key to
    different nodes. Every cache hit in the system presumes the router is
    the same function of the key everywhere, forever. md5 of the UTF-8
    bytes is that function.

DESIGN DECISION — why 150 virtual nodes per real node instead of one point?
    The tempting alternative is one hash point per node. Its cost is
    lumpiness: with 9 points spread over 12,000 keys one node takes 147%
    over its fair share — the circle gives it a huge arc by luck. Each real
    node owns 150 interleaved arcs instead, and the law of large numbers
    does the balancing for free. The memory is trivial; the skew is not.

DESIGN DECISION — why does the FIRST point clockwise of the key own it?
    The tempting alternative is "nearest point", measuring distance both
    ways. Its cost is a boundary that moves when a node is inserted on the
    other side of it: two equidistant points tie differently than a strict
    clockwise rule, and the tie-breaking depends on the whole ring, not on
    the key. "First point past the key's own position, wrapping once" is
    decided by the key alone.

DESIGN DECISION — why does `successors` skip nodes it already named?
    The tempting alternative is to walk clockwise and take the next `count`
    points. Its cost is that with 150 points per node the next three points
    are almost always three vnodes of the SAME server — three replicas,
    one machine. Distinct real nodes is what survives a crash; the walk
    keeps going until `count` different names are named.

TODO: implement `HashRing.__init__`, `add_node`, `remove_node`, `nodes`,
`positions`, `route` and `successors`.
"""

from world import CacheError, stable_hash

#: One point per real node per entry. 150 is the number `system-design`'s
#: consistent-hash ring uses for the same reason: fewer lumps, one memory
#: cost; the demo prints what each choice actually does to the spread.
VNODES = 150


class HashRing:
    """Keys to nodes, with no server ever seeing the mapping."""

    def __init__(self, vnodes=VNODES):
        raise NotImplementedError("stage 1: implement HashRing.__init__()")

    def add_node(self, name):
        """Place this node's `vnodes` points on the circle, keeping the
        (position, node) list sorted; refuse an empty or duplicate name."""
        raise NotImplementedError("stage 1: implement HashRing.add_node()")

    def remove_node(self, name):
        """Take every point of this node off the circle; refuse a name the
        ring does not have."""
        raise NotImplementedError("stage 1: implement HashRing.remove_node()")

    def nodes(self):
        """The real node names, in a stable order."""
        raise NotImplementedError("stage 1: implement HashRing.nodes()")

    def positions(self):
        """The ring's points as sorted (position, node) tuples."""
        raise NotImplementedError("stage 1: implement HashRing.positions()")

    def route(self, key):
        """The node owning this key: first point strictly past the key's
        own md5, wrapping to the head of the list past the last point."""
        raise NotImplementedError("stage 1: implement HashRing.route()")

    def successors(self, key, count):
        """Up to `count` DISTINCT nodes clockwise from the route, starting
        at the route itself; asking for more than exist names them all."""
        raise NotImplementedError("stage 1: implement HashRing.successors()")
