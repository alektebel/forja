"""kv.py — the version grammar (provided world).

A version is `("v", value, clock)`; a clock is a tuple of `(node,
counter)` pairs sorted by node, distinct, counters >= 0; the value is an
opaque string. That is the whole storage shape A6 described, with the
floats and the objects removed: clocks are DATA, and a stage can hold
one wrong at most.

The world ships `dominates` only — the four-way comparison and the
sibling coalescing are the student's stage 1, because the fabric itself
never orders versions. Constructors refuse every malformed shape with
`KvError`, naming the offender: a clock that is unsorted, has a
duplicate node, a negative counter, or a value that is not a string
never reaches a scenario.
"""

from topology import NODES

KIND_VERSION = "v"
KIND_HINT = "hint"

VALID_NODES = tuple(sorted(n for n, _ in NODES))


class KvError(ValueError):
    """The world's refusal: a version, clock, or hint that is not shaped right."""


def _check_clock(clock):
    if not isinstance(clock, tuple):
        raise KvError("kv: a clock must be a tuple, got %r" % (type(clock).__name__,))
    prev = None
    for entry in clock:
        if (not isinstance(entry, tuple) or len(entry) != 2
                or not isinstance(entry[0], str) or not isinstance(entry[1], int)):
            raise KvError("kv: a clock entry must be a (node, int) pair, got %r"
                          % (entry,))
        node, counter = entry
        if node not in VALID_NODES:
            raise KvError("kv: clock names %r, which is not in the fleet %s"
                          % (node, ", ".join(VALID_NODES)))
        if counter < 0:
            raise KvError("kv: clock counter for %s is %d, below 0" % (node, counter))
        if prev is not None and node <= prev:
            raise KvError("kv: clock entries must be sorted by node and distinct, "
                          "got %r after %r" % (node, prev))
        prev = node
    return clock


def version(value, clock):
    """`("v", value, clock)`; value an opaque string, clock checked."""
    if not isinstance(value, str):
        raise KvError("kv: a version's value must be a string, got %r"
                      % (type(value).__name__,))
    return (KIND_VERSION, value, _check_clock(clock))


def clock_of(v):
    """The version's clock."""
    _check_version(v)
    return v[2]


def value_of(v):
    """The version's opaque value."""
    _check_version(v)
    return v[1]


def _check_version(v):
    if (not isinstance(v, tuple) or len(v) != 3 or v[0] != KIND_VERSION
            or not isinstance(v[1], str)):
        raise KvError("kv: a version must be ('v', value:str, clock), got %r" % (v,))
    _check_clock(v[2])
    return v


def bump(clock, node):
    """The clock with `node`'s counter +1 (absent node becomes (node, 1)).
    The write side of A6's increment; stays immutable and sorted."""
    _check_clock(clock)
    if node not in VALID_NODES:
        raise KvError("kv: bump names %r, which is not in the fleet %s"
                      % (node, ", ".join(VALID_NODES)))
    entries = dict(clock)
    entries[node] = entries.get(node, 0) + 1
    return tuple(sorted(entries.items()))


def dominates(a, b):
    """True iff every counter in `b` is present in `a` and >=. Equal clocks
    dominate each other; the four-way law (before/after/equal/concurrent)
    is stage 1's to derive from this primitive."""
    _check_clock(a)
    _check_clock(b)
    da = dict(a)
    return all(da.get(node, 0) >= counter for node, counter in b)


def hint(key, ver, intended_for):
    """`("hint", key, version, intended_for)` — a write parked on a node
    that a peer could not reach. Held, never owned: serving it as yours
    is stage 3's refusal."""
    if not isinstance(key, str) or not key:
        raise KvError("kv: a hint's key must be a non-empty string, got %r" % (key,))
    _check_version(ver)
    if intended_for not in VALID_NODES:
        raise KvError("kv: a hint intended_for %r, which is not in the fleet %s"
                      % (intended_for, ", ".join(VALID_NODES)))
    return (KIND_HINT, key, ver, intended_for)
