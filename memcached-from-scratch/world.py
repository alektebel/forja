"""Memcached From Scratch — the provided world.

Three things the ten stages share, complete and proven: a clock you move by
hand, an origin (the system of record) whose reads cost ticks, and a stable
hash that makes "random" decisions reproducible between runs.

`Clock` follows the rule every from-scratch systems course in this repo uses:
ticks are counted, never timed. No stage may import `time`; a check walks the
landmine by running the same plan twice and comparing bytes.

DESIGN DECISION — why is the jitter hash of `(key, round)` instead of RNG?
    The tempting alternative is `random.random()` for statistical herding.
    Its cost is that two runs of the same inputs stop producing the same
    report, and the capstone's byte-identity check — the one that proves the
    whole machine is a data structure — can never pass. A hash of
    `f"{key}#{round}"` is *uniform like a coin* and *fixed like a fact*: the
    distribution the paper describes survives, and the run replays.

DESIGN DECISION — why does a value count as one character?
    `orchestration-from-scratch` stage 4 made a token a character so a cut
    would be exact; this course inherits it for byte counts too: the value
    length is `len(text)`, no encoding is consulted, and a check on `wasted
    bytes` cannot be fudged by a charset.
"""

import hashlib


class CacheError(Exception):
    """Every refusal in this course raises it, and every message names the
    thing the reader can go fix: the key, the class, the node, the number."""


class Clock:
    """Integer ticks, injected. `advance` refuses negatives and bools for the
    reasons every fleet in this repo refuses them: time running backwards and
    `True` arriving as `1` are both bugs the caller should hear about."""

    def __init__(self):
        self._now = 0

    @property
    def now(self):
        return self._now

    def advance(self, ticks):
        if isinstance(ticks, bool) or not isinstance(ticks, int):
            raise CacheError("advance(%r): ticks must be an int, not %s"
                             % (ticks, type(ticks).__name__))
        if ticks < 0:
            raise CacheError("advance(%d): time does not run backwards" % ticks)
        self._now += ticks
        return self._now


def stable_hash(text):
    """md5 to an int: stable across processes and runs, which `hash()` is not."""
    if not isinstance(text, str):
        raise CacheError("stable_hash(%r): the hash is of text" % (text,))
    return int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)


class Origin:
    """The system of record behind the cache. Each row has a rebuild cost in
    ticks — the number a herding or single-flight stage is trying to avoid
    paying N times for the same key. `queries` is the counter every
    protection stage is finally measured against."""

    def __init__(self, rows):
        if not isinstance(rows, dict):
            raise CacheError("Origin(rows): rows must be a mapping of "
                             "key -> (value, rebuild_ticks)")
        self._rows = {}
        for key, spec in rows.items():
            if not isinstance(spec, tuple) or len(spec) != 2:
                raise CacheError("origin row '%s' is %r, expected "
                                 "(value, rebuild_ticks)" % (key, spec))
            value, cost = spec
            if not isinstance(value, str):
                raise CacheError("origin row '%s' holds %r, and a value is text"
                                 % (key, value))
            if isinstance(cost, bool) or not isinstance(cost, int) or cost < 0:
                raise CacheError("origin row '%s' costs %r: rebuild ticks are "
                                 "a non-negative int" % (key, cost))
            self._rows[key] = (value, cost)
        self.queries = 0

    def cost(self, key):
        if key not in self._rows:
            raise CacheError("origin has no row for '%s'" % key)
        return self._rows[key][1]

    def fetch(self, key, clock):
        """One read of the origin: counted, then it costs its rebuild ticks."""
        self.queries += 1
        if key not in self._rows:
            raise CacheError("no origin row for '%s'" % key)
        value, cost = self._rows[key]
        clock.advance(cost)
        return value
