"""topology.py — the fleet as pure data (provided world).

Two regions, three nodes each, independent clocks. `TICK_RATE = 2` means
west is ticked once per two global ticks: a number one region stamps can
never be compared with a number the other stamps, which is why ordering
anything that can cross the link takes the vector clock (stage 1) or the
epoch (stage 7) and never a stamp. `LAG_BOUND` is the applied-count a
healthy node may trail the region's best by and still count toward a
quorum — the health signal is servability, not presence.

Everything here is tuples, strings and ints: the shape of the failure is
data, so every scenario is reproducible.
"""


REGIONS = ("east", "west")

NODES = (("e1", "east"), ("e2", "east"), ("e3", "east"),
         ("w1", "west"), ("w2", "west"), ("w3", "west"))

# The primary region at tick 0 and its epoch: the world's starting truth.
# Promotion (stage 7) is the only way this changes, and the fabric fences
# old epochs forever after.
PRIMARY = "east"
INITIAL_EPOCH = 1

# West ticks once per two global ticks: independent clocks, in operation.
TICK_RATE = 2

# A healthy node's applied_count may trail the region's best observed by
# at most this many writes. PINS-bound: stage 5's rule, not a tunable.
LAG_BOUND = 2

_BY_ID = dict(NODES)


def region_of(node_id):
    """The region a node id lives in; unknown ids refuse with a name."""
    if node_id not in _BY_ID:
        raise ValueError("topology: unknown node id %r (fleet is %s)"
                         % (node_id, ", ".join(sorted(_BY_ID))))
    return _BY_ID[node_id]


def nodes_of(region):
    """The region's node ids, sorted — the entry node is the first live one."""
    if region not in REGIONS:
        raise ValueError("topology: unknown region %r (fleet is %s)"
                         % (region, ", ".join(REGIONS)))
    return tuple(sorted(n for n, r in NODES if r == region))


def peers_of(node_id):
    """The same region's OTHER nodes, sorted. A node never hears from the
    other region except across the link, and that is the fabric's business."""
    region = region_of(node_id)
    return tuple(n for n in nodes_of(region) if n != node_id)


def majority(n):
    """H6's law, restated: a decision needs n // 2 + 1, an int, never a
    fraction. majority(3) == 2 and majority(2) == 2."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("topology: majority needs an int >= 0, got %r"
                         % (n,))
    return n // 2 + 1
