"""scenarios.py — the seven schedules and the pinned truth (provided world).

The drill book for the whole course: `SCENARIOS` names every schedule,
`scenario(name)` hands back its kind, event list, horizon and pins, and
`PINS` records what a CORRECT node (probe column) and the foil (naive
column) actually do on each one — replayed from real runs of
`probe_failover.py` and `naive.py`, never asserted. A stage READS PINS
and never recomputes it.

Events are kind-first tuples: ("kill", t, id), ("revive", t, id),
("cut", t), ("heal", t), ("client", t, home, command) — the shape the
fabric schedules. Verdicts: ("ok", values), ("applied",),
("redirect", region), ("refused", reason).

rto is the first served answer at or after the first refused one, minus
that refused tick — `None` when nothing was ever refused or nothing was
ever served after the first refusal. rpo is the count of `lost`.
"""

ONE_NODE = (
    ('client', 2, 'east', 'set a=1 c=alpha r=1'),
    ('kill', 4, 'e2'),
    ('client', 6, 'east', 'get a c=alpha r=2'),
)

REGION_DIE = (
    ('client', 1, 'east', 'get a c=alpha r=1'),
    ('client', 3, 'east', 'set a=2 c=alpha r=2'),
    ('kill', 5, 'e1'),
    ('kill', 5, 'e2'),
    ('kill', 5, 'e3'),
    ('client', 7, 'east', 'set a=2 c=alpha r=2'),
    ('client', 9, 'east', 'set b=2 c=beta r=3'),
    ('client', 11, 'east', 'set b=2 c=beta r=3'),
)

DUAL = (
    ('client', 1, 'east', 'set a=1 c=e1 r=1'),
    ('client', 2, 'east', 'set a=2 c=e2 r=3'),
    ('cut', 3),
    ('client', 4, 'east', 'set a=3 c=e3 r=5'),
    ('client', 5, 'west', 'set a=4 c=w1 r=6'),
    ('client', 7, 'west', 'set a=5 c=w2 r=8'),
    ('heal', 12),
    ('client', 14, 'east', 'get a c=e1 r=9'),
    ('client', 15, 'west', 'get a c=w1 r=10'),
)

FLAP = (
    ('cut', 2),
    ('kill', 6, 'e1'),
    ('kill', 6, 'e2'),
    ('kill', 6, 'e3'),
    ('client', 7, 'east', 'set a=1 c=alpha r=3'),
    ('client', 9, 'east', 'set a=1 c=alpha r=3'),
    ('heal', 10),
    ('cut', 12),
    ('client', 13, 'east', 'set a=1 c=alpha r=3'),
    ('revive', 14, 'e2'),
    ('client', 14, 'east', 'get a c=beta r=4'),
    ('heal', 16),
)

LAG = (
    ('cut', 1),
    ('client', 2, 'east', 'set p=1 c=alpha r=1'),
    ('client', 4, 'east', 'set p=2 c=alpha r=2'),
    ('kill', 6, 'e1'),
    ('kill', 6, 'e2'),
    ('kill', 6, 'e3'),
    ('heal', 8),
)

FAKE_DEATH = (
    ('cut', 3),
    ('client', 5, 'west', 'set a=1 c=w1 r=1'),
    ('client', 7, 'east', 'get a c=e1 r=2'),
    ('heal', 10),
)

ALL_DIE = (
    ('client', 2, 'east', 'set a=0 c=alpha r=1'),
    ('kill', 3, 'e1'),
    ('kill', 3, 'e2'),
    ('kill', 3, 'e3'),
    ('kill', 3, 'w1'),
    ('kill', 3, 'w2'),
    ('cut', 4),
    ('client', 6, 'east', 'set a=1 c=alpha r=2'),
    ('client', 8, 'west', 'get a c=beta r=3'),
)

SCENARIOS = (
    ('ONE_NODE', 'single-node', ONE_NODE, 24),
    ('REGION_DIE', 'region-death', REGION_DIE, 24),
    ('DUAL', 'dual-write', DUAL, 24),
    ('FLAP', 'flapping', FLAP, 24),
    ('LAG', 'lag', LAG, 24),
    ('FAKE_DEATH', 'false-death', FAKE_DEATH, 24),
    ('ALL_DIE', 'total-loss', ALL_DIE, 24),
)

PINS = {
    'ONE_NODE': {
        'probe': {
            'promotes': (),
            'answers': ((2, 'alpha', 1, ('applied',)), (6, 'alpha', 2, ('ok', ('1',)))),
            'dups': (),
            'lost': (),
            'rto': None,
            'rpo': 0,
        },
        'naive': {
            'promotes': ((3, 'east', 2), (6, 'west', 2)),
            'answers': ((2, 'alpha', 1, ('applied',)), (6, 'alpha', 2, ('ok', ('1',)))),
            'dups': (),
            'lost': (),
            'rto': None,
            'rpo': 0,
        },
    },
    'REGION_DIE': {
        'probe': {
            'promotes': ((6, 'west', 2),),
            'answers': ((1, 'alpha', 1, ('ok', ())), (3, 'alpha', 2, ('applied',)), (7, 'alpha', 2, ('applied',)), (9, 'beta', 3, ('applied',)), (11, 'beta', 3, ('applied',))),
            'dups': (),
            'lost': (),
            'rto': None,
            'rpo': 0,
        },
        'naive': {
            'promotes': ((3, 'east', 2), (6, 'west', 2)),
            'answers': ((1, 'alpha', 1, ('ok', ())), (3, 'alpha', 2, ('applied',)), (7, 'alpha', 2, ('applied',)), (9, 'beta', 3, ('applied',)), (11, 'beta', 3, ('applied',))),
            'dups': (('beta', 3, 'w1'),),
            'lost': (),
            'rto': None,
            'rpo': 0,
        },
    },
    'DUAL': {
        'probe': {
            'promotes': (),
            'answers': ((1, 'e1', 1, ('applied',)), (2, 'e2', 3, ('applied',)), (4, 'e3', 5, ('applied',)), (5, 'w1', 6, ('applied',)), (7, 'w2', 8, ('applied',)), (14, 'e1', 9, ('ok', ('3', '5'))), (15, 'w1', 10, ('ok', ('3', '5')))),
            'dups': (),
            'lost': (),
            'rto': None,
            'rpo': 0,
        },
        'naive': {
            'promotes': ((3, 'east', 2), (6, 'west', 2)),
            'answers': ((1, 'e1', 1, ('applied',)), (2, 'e2', 3, ('applied',)), (4, 'e3', 5, ('applied',)), (5, 'w1', 6, ('applied',)), (7, 'w2', 8, ('applied',)), (14, 'e1', 9, ('ok', ('3',))), (15, 'w1', 10, ('ok', ('5',)))),
            'dups': (),
            'lost': (),
            'rto': None,
            'rpo': 0,
        },
    },
    'FLAP': {
        'probe': {
            'promotes': ((12, 'west', 2),),
            'answers': ((7, 'alpha', 3, ('refused', 'unpromoted')), (9, 'alpha', 3, ('refused', 'unpromoted')), (13, 'alpha', 3, ('applied',)), (14, 'beta', 4, ('redirect', 'west')), (15, 'beta', 4, ('ok', ('1',)))),
            'dups': (),
            'lost': (),
            'rto': 6,
            'rpo': 0,
        },
        'naive': {
            'promotes': ((3, 'east', 2), (6, 'west', 2)),
            'answers': ((7, 'alpha', 3, ('applied',)), (9, 'alpha', 3, ('applied',)), (13, 'alpha', 3, ('applied',)), (14, 'beta', 4, ('ok', ()))),
            'dups': (('alpha', 3, 'w1'), ('alpha', 3, 'w1')),
            'lost': (),
            'rto': None,
            'rpo': 0,
        },
    },
    'LAG': {
        'probe': {
            'promotes': ((10, 'west', 2),),
            'answers': ((2, 'alpha', 1, ('applied',)), (4, 'alpha', 2, ('applied',))),
            'dups': (),
            'lost': (('alpha', 1, 'p'), ('alpha', 2, 'p')),
            'rto': None,
            'rpo': 2,
        },
        'naive': {
            'promotes': ((3, 'east', 2), (6, 'west', 2)),
            'answers': ((2, 'alpha', 1, ('applied',)), (4, 'alpha', 2, ('applied',))),
            'dups': (),
            'lost': (('alpha', 1, 'p'), ('alpha', 2, 'p')),
            'rto': None,
            'rpo': 2,
        },
    },
    'FAKE_DEATH': {
        'probe': {
            'promotes': (),
            'answers': ((5, 'w1', 1, ('applied',)), (7, 'e1', 2, ('ok', ()))),
            'dups': (),
            'lost': (),
            'rto': None,
            'rpo': 0,
        },
        'naive': {
            'promotes': ((3, 'east', 2), (6, 'west', 2)),
            'answers': ((5, 'w1', 1, ('applied',)), (7, 'e1', 2, ('ok', ()))),
            'dups': (),
            'lost': (),
            'rto': None,
            'rpo': 0,
        },
    },
    'ALL_DIE': {
        'probe': {
            'promotes': (),
            'answers': ((2, 'alpha', 1, ('applied',)), (6, 'alpha', 2, ('refused', 'unpromoted')), (8, 'beta', 3, ('redirect', 'east')), (9, 'beta', 3, ('refused', 'unpromoted'))),
            'dups': (),
            'lost': (('alpha', 1, 'a'),),
            'rto': None,
            'rpo': 1,
        },
        'naive': {
            'promotes': ((6, 'west', 2),),
            'answers': ((2, 'alpha', 1, ('applied',)), (6, 'alpha', 2, ('applied',)), (8, 'beta', 3, ('ok', ('1',)))),
            'dups': (),
            'lost': (('alpha', 1, 'a'),),
            'rto': None,
            'rpo': 1,
        },
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
