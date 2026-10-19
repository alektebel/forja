"""scenarios.py — the fixed schedules the cluster driver interprets.

Seven runs of the fabric, each one built to force a protocol to show its
true colors: elections, a partition that heals, a partition that
INTERSECTS (the asymmetric one — where the naive foil commits the same
slot twice), a majority-less minority that must never commit, a node left
behind and healed, a crash that tears the last disk record, and a
membership change under a partition. Every event is one of:

    ("cut", tick, node_x, node_y)   the link between x and y is severed
    ("heal", tick)                  every severed link is restored
    ("crash", tick, node)           the node dies with its disk torn
    ("restart", tick, node)         the node recovers from the disk
    ("submit", tick, node, command) a client call lands on `node`

`ticks` is the horizon the driver runs to. The result facts each
scenario pins are written in the same order the driver records them, so
a check can compare a run against the table without re-deriving it.
"""

ELECT_ONE = (
    ("submit", 11, "a4", "x=1"),
)

HEAL = (
    ("submit", 11, "a4", "x=1"),
    ("cut", 14, "a4", "a1"), ("cut", 14, "a4", "a2"),
    ("cut", 14, "a4", "a3"),
    ("submit", 16, "a4", "y=2"),
    ("heal", 40),
    ("submit", 44, "a4", "z=3"),
)

ASYMMETRIC = (
    ("cut", 12, "a4", "a1"), ("cut", 12, "a4", "a2"),
    ("cut", 12, "a5", "a1"), ("cut", 12, "a5", "a2"),
    ("submit", 13, "a4", "x=1"),
    ("cut", 24, "a3", "a4"),
    ("submit", 25, "a2", "y=2"),
    ("heal", 40),
    ("submit", 45, "a2", "get x"),
)

MINORITY = (
    ("submit", 11, "a4", "x=1"),
    ("cut", 15, "a4", "a1"), ("cut", 15, "a4", "a2"),
    ("cut", 15, "a4", "a3"), ("cut", 15, "a5", "a1"),
    ("cut", 15, "a5", "a2"), ("cut", 15, "a5", "a3"),
    ("submit", 16, "a4", "y=2"),
    ("heal", 40),
    ("submit", 42, "a4", "get y"),
)

LAGGARD = (
    ("submit", 11, "a4", "x=1"),
    ("cut", 13, "a5", "a1"), ("cut", 13, "a5", "a2"),
    ("cut", 13, "a5", "a3"), ("cut", 13, "a5", "a4"),
    ("submit", 16, "a4", "y=2"),
    ("submit", 22, "a4", "z=3"),
    ("heal", 45),
    ("submit", 60, "a4", "get z"),
)

TORN = (
    ("submit", 11, "a4", "x=1"),
    ("submit", 14, "a4", "y=2"),
    ("crash", 20, "a2"),
    ("restart", 22, "a2"),
    ("submit", 26, "a4", "z=3"),
    ("submit", 31, "a2", "get x"),
)

JOINT = (
    ("submit", 11, "a4", "x=1"),
    ("cut", 20, "a4", "a5"),
    ("submit", 22, "a4", "members:a1,a2,a3"),
    ("heal", 45),
    ("submit", 52, "a4", "y=2"),
)

SCENARIOS = (
    ("ELECT_ONE", "election", ELECT_ONE, 30),
    ("HEAL", "partition", HEAL, 55),
    ("ASYMMETRIC", "partition", ASYMMETRIC, 60),
    ("MINORITY", "partition", MINORITY, 55),
    ("LAGGARD", "catch-up", LAGGARD, 70),
    ("TORN", "crash", TORN, 40),
    ("JOINT", "membership", JOINT, 75),
)


PINS = {
    'ELECT_ONE': {
        'probe': {'leaders': ((5, 1, 'a4'),), 'committed': ((11, 0, 1, 'x=1'),), 'conflicts': (), 'linear': True},
        'naive': {'leaders': ((5, 1, 'a4'),), 'committed': ((11, 0, 1, 'x=1'),), 'conflicts': (), 'linear': True},
    },
    'HEAL': {
        'probe': {'leaders': ((5, 1, 'a4'), (17, 2, 'a2'), (34, 4, 'a2'), (40, 6, 'a4')), 'committed': ((11, 0, 1, 'x=1'), (44, 1, 1, 'y=2'), (44, 2, 6, 'z=3')), 'conflicts': (), 'linear': True},
        'naive': {'leaders': ((5, 1, 'a4'), (17, 2, 'a2'), (34, 4, 'a2'), (40, 6, 'a4')), 'committed': ((11, 0, 1, 'x=1'), (44, 1, 1, 'y=2'), (44, 2, 6, 'z=3')), 'conflicts': (), 'linear': True},
    },
    'ASYMMETRIC': {
        'probe': {'leaders': ((5, 1, 'a4'), (40, 6, 'a4')), 'committed': ((13, 0, 1, 'x=1'),), 'conflicts': (), 'linear': True},
        'naive': {'leaders': ((5, 1, 'a4'), (17, 2, 'a2'), (40, 6, 'a4')), 'committed': ((13, 0, 1, 'x=1'), (25, 0, 2, 'y=2')), 'conflicts': ((25, 0, 'x=1', 'y=2'),), 'linear': True},
    },
    'MINORITY': {
        'probe': {'leaders': ((5, 1, 'a4'), (17, 2, 'a2'), (47, 3, 'a4')), 'committed': ((11, 0, 1, 'x=1'),), 'conflicts': (), 'linear': True},
        'naive': {'leaders': ((5, 1, 'a4'), (17, 2, 'a2'), (47, 3, 'a4')), 'committed': ((11, 0, 1, 'x=1'),), 'conflicts': (), 'linear': True},
    },
    'LAGGARD': {
        'probe': {'leaders': ((5, 1, 'a4'), (54, 5, 'a4')), 'committed': ((11, 0, 1, 'x=1'), (16, 1, 1, 'y=2'), (22, 2, 1, 'z=3')), 'conflicts': (), 'linear': True},
        'naive': {'leaders': ((5, 1, 'a4'), (49, 4, 'a5'), (54, 5, 'a4')), 'committed': ((11, 0, 1, 'x=1'), (16, 1, 1, 'y=2'), (22, 2, 1, 'z=3')), 'conflicts': (), 'linear': False},
    },
    'TORN': {
        'probe': {'leaders': ((5, 1, 'a4'),), 'committed': ((11, 0, 1, 'x=1'), (14, 1, 1, 'y=2'), (26, 2, 1, 'z=3')), 'conflicts': (), 'linear': True},
        'naive': {'leaders': ((5, 1, 'a4'),), 'committed': ((11, 0, 1, 'x=1'), (14, 1, 1, 'y=2'), (26, 2, 1, 'z=3')), 'conflicts': (), 'linear': True},
    },
    'JOINT': {
        'probe': {'leaders': ((5, 1, 'a4'), (35, 3, 'a2'), (40, 4, 'a4')), 'committed': ((11, 0, 1, 'x=1'), (22, 1, 1, 'members:a1,a2,a3'), (52, 2, 4, 'y=2')), 'conflicts': (), 'linear': True},
        'naive': {'leaders': ((5, 1, 'a4'), (28, 2, 'a5'), (35, 3, 'a4')), 'committed': ((11, 0, 1, 'x=1'), (22, 1, 1, 'members:a1,a2,a3'), (52, 2, 3, 'y=2')), 'conflicts': (), 'linear': True},
    },
}


_NAMES = dict((name, (kind, spec, ticks))
              for name, kind, spec, ticks in SCENARIOS)


def scenario(name):
    """(kind, events, ticks, pins) for a scenario name — or a refusal
    naming the table. `pins` is the PINS row: the facts a run of this
    schedule MUST show, keyed by protocol class ("probe" = a correct
    implementation, "naive" = the foil)."""
    if name not in _NAMES:
        raise KeyError("scenarios: %r is not in the table; the names are "
                       "%s" % (name, ", ".join(sorted(_NAMES))))
    return _NAMES[name] + (PINS[name],)
