"""Memcached From Scratch — stage 4: the ASCII protocol, byte-exact.

The finished implementation. The reasoning — why the byte count is verified
before anything is stored, why `add`/`replace` answer NOT_STORED while a CAS
mismatch answers EXISTS, why CAS is a monotonic counter and not a version
string, and how the real daemon's exptime rule (0 / relative / absolute)
maps onto injected integer ticks — lives in the DESIGN DECISION blocks of
`stage_04.py`.
"""

from world import CacheError

#: The protocol's line terminator. A response that joins with "\\n" instead
#: is one invisible character away from a client that hangs.
CRLF = "\r\n"

#: memcached's own boundary: an exptime at or below this value is *seconds
#: from now*; anything larger is an absolute time. On our tick clock the
#: same shape holds: relative unless the number is past the boundary.
RELATIVE_BOUNDARY = 2592000

VERSION = "1.5.32-scratch"


def absolute_exptime(raw, now):
    """The one exptime rule, shared by every storing verb."""
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise CacheError("exptime %r: must be an int of ticks" % (raw,))
    if raw < 0:
        raise CacheError("exptime %d: negative is not a time" % raw)
    if raw == 0:
        return 0                       # 0 means: never expires
    if raw <= RELATIVE_BOUNDARY:
        return now + raw               # relative: seconds/ticks from now
    return raw                         # absolute: a tick on the clock


def parse(line):
    """'verb a b c' -> ('verb', ('a', 'b', 'c')). The refusals are the ones
    the daemon answers ERROR to: an empty line, or one that is not trimmed
    — a leading space makes the verb the empty string."""
    if not isinstance(line, str) or line != line.strip() or not line:
        raise CacheError("bad command line %r" % (line,))
    parts = line.split(" ")
    return parts[0], tuple(parts[1:])


class Ascii:
    """The text interface to a stage-3 store: requests in, responses out,
    both byte-exact.

    Invariants: nothing is stored until the data block's byte count matches;
    a stored key carries a CAS token that every successful mutation bumps;
    `hits`/`misses` count keys, not commands — a two-key `get` that finds
    one is one hit *and* one miss; `stats` derives its report from those
    counters instead of keeping parallel ones.
    """

    def __init__(self, store, clock, version=VERSION):
        self._store = store
        self._clock = clock
        self._version = version
        self._cas = {}           # key -> last issued CAS token
        self._next_cas = 1
        self.hits = 0
        self.misses = 0
        self.commands = 0

    def handle(self, request):
        """One full session text: command line, plus the data block and the
        terminating END line for storing verbs. Returns the exact response,
        terminator included."""
        self.commands += 1
        lines = request.split(CRLF)
        if lines and lines[-1] == "":
            lines.pop()
        if not lines:
            return "ERROR" + CRLF
        try:
            verb, argv = parse(lines[0])
        except CacheError:
            return "ERROR" + CRLF
        if verb == "set":
            return self._store_verb(argv, lines, "set")
        if verb == "add":
            return self._store_verb(argv, lines, "add")
        if verb == "replace":
            return self._store_verb(argv, lines, "replace")
        if verb == "cas":
            return self._cas_verb(argv, lines)
        if verb in ("get", "gets"):
            return self._get(argv, with_cas=(verb == "gets"))
        if verb == "delete":
            return self._delete(argv)
        if verb in ("incr", "decr"):
            return self._arith(argv, 1 if verb == "incr" else -1)
        if verb == "touch":
            return self._touch(argv)
        if verb == "version":
            return "VERSION " + self._version + CRLF
        if verb == "stats":
            return self._stats()
        return "ERROR" + CRLF

    # -- storing verbs ------------------------------------------------------

    def _take(self, argv, lines, expect):
        """Shared shape: 'verb key flags exptime bytes[ cas]' + data + END.
        Returns (spec, None) or (None, error-response). The byte count is
        verified *before* the store sees anything."""
        if len(argv) != expect:
            return None, "ERROR" + CRLF
        key, flags_s, exp_s, bytes_s = argv[:4]
        if not key or " " in key or "\t" in key:
            return None, "CLIENT_ERROR bad command line format" + CRLF
        try:
            flags, nbytes, exp = int(flags_s), int(bytes_s), int(exp_s)
        except ValueError:
            return None, "ERROR" + CRLF
        if len(lines) < 3 or lines[2] != "END":
            return None, "ERROR" + CRLF
        data = lines[1]
        if nbytes < 0 or len(data) != nbytes:
            return None, "CLIENT_ERROR bad data chunk" + CRLF
        spec = (key, flags, absolute_exptime(exp, self._clock.now), data)
        return spec, None

    def _store_verb(self, argv, lines, verb):
        spec, err = self._take(argv, lines, 4)
        if err:
            return err
        key, flags, exp, value = spec
        existing = self._store.get(key, self._clock.now, mark=False)
        if verb == "add" and existing is not None:
            return "NOT_STORED" + CRLF
        if verb == "replace" and existing is None:
            return "NOT_STORED" + CRLF
        self._store.store(key, value, self._clock.now, flags=flags, exptime=exp)
        self._bump_cas(key)
        return "STORED" + CRLF

    def _cas_verb(self, argv, lines):
        spec, err = self._take(argv, lines, 5)
        if err:
            return err
        key, flags, exp, value = spec
        token = argv[4]
        if not token.isdigit():
            return "ERROR" + CRLF
        current = self._store.get(key, self._clock.now, mark=False)
        if current is None:
            return "NOT_FOUND" + CRLF          # the key is gone: a different answer
        if self._cas.get(key) != int(token):
            return "EXISTS" + CRLF             # someone beat us to it
        self._store.store(key, value, self._clock.now, flags=flags, exptime=exp)
        self._bump_cas(key)
        return "STORED" + CRLF

    def _bump_cas(self, key):
        self._cas[key] = self._next_cas
        self._next_cas += 1

    # -- reading and removal --------------------------------------------------

    def _get(self, argv, with_cas):
        if not argv:
            return "ERROR" + CRLF
        out = []
        for key in argv:
            item = self._store.get(key, self._clock.now)   # marks: reads are LRU data
            if item is None:
                self.misses += 1
                continue
            self.hits += 1
            head = "VALUE %s %d %d" % (key, item.flags, len(item.value))
            if with_cas:
                head += " %d" % self._cas.get(key, 0)
            out.append(head)
            out.append(item.value)
        out.append("END")
        return CRLF.join(out) + CRLF

    def _delete(self, argv):
        if len(argv) != 1:
            return "ERROR" + CRLF
        if self._store.delete(argv[0]):
            self._cas.pop(argv[0], None)
            return "DELETED" + CRLF
        return "NOT_FOUND" + CRLF

    def _arith(self, argv, sign):
        if len(argv) != 2 or not argv[1].isdigit():
            return "ERROR" + CRLF
        key, delta_s = argv
        item = self._store.get(key, self._clock.now)
        if item is None:
            return "NOT_FOUND" + CRLF
        if not item.value.isdigit():
            return "ERROR" + CRLF          # incr of a non-number is not arithmetic
        result = int(item.value) + sign * int(delta_s)
        if result < 0:
            result = 0                     # the daemon floors at zero, never wraps
        self._store.store(key, str(result), self._clock.now,
                          flags=item.flags, exptime=item.exptime)
        self._bump_cas(key)
        return str(result) + CRLF

    def _touch(self, argv):
        if len(argv) != 2:
            return "ERROR" + CRLF
        item = self._store.get(argv[0], self._clock.now, mark=False)
        if item is None:
            return "NOT_FOUND" + CRLF
        try:
            exp = absolute_exptime(int(argv[1]), self._clock.now)
        except (CacheError, ValueError):
            return "ERROR" + CRLF
        self._store.store(argv[0], item.value, self._clock.now,
                          flags=item.flags, exptime=exp)
        return "TOUCHED" + CRLF

    # -- the report -----------------------------------------------------------

    def _stats(self):
        s = self._store.stats()
        rows = [
            ("pid", 1),
            ("version", self._version),
            ("curr_items", s["live"]),
            ("evictions", s["evicted_items"]),
            ("expired_unfetched", s["expired_freed"]),
            ("get_hits", self.hits),
            ("get_misses", self.misses),
            ("cmd_total", self.commands),
        ]
        out = ["STAT %s %s" % (k, v) for k, v in rows]
        out.append("END")
        return CRLF.join(out) + CRLF


if __name__ == "__main__":
    from world import Clock
    from stage_03 import LruSlab

    ascii_ = Ascii(LruSlab(2, 2), Clock())
    show = lambda r: print(repr(r))
    show(ascii_.handle("set user:1 0 60 5" + CRLF + "alice" + CRLF + "END"))
    show(ascii_.handle("get user:1"))
    show(ascii_.handle("gets user:1"))
    show(ascii_.handle("set user:1 0 0 6" + CRLF + "END" + CRLF + "END"))   # chunk
    show(ascii_.handle("add user:1 0 0 1" + CRLF + "z" + CRLF + "END"))     # exists
    show(ascii_.handle("cas user:1 0 0 6 1" + CRLF + "alicia" + CRLF + "END"))
    show(ascii_.handle("cas user:1 0 0 6 1" + CRLF + "alicia" + CRLF + "END"))
    show(ascii_.handle("set count 0 0 1" + CRLF + "7" + CRLF + "END"))
    show(ascii_.handle("incr count 2"))
    show(ascii_.handle("decr count 99"))
    show(ascii_.handle("delete user:1"))
    show(ascii_.handle("get user:1"))
    show(ascii_.handle("stats"))
