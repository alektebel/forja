"""The LFU cache with an LRU tie-break: eviction is a total order.

Least-Frequently-Used evicts the coldest key; when two keys share the
minimum frequency, the one that was touched EARLIER loses. That single
rule — compare (frequency, age) as a pair — is the whole stage, and the
check pins it by replaying a fixed access script and reading the exact
eviction order back off the cache's own ledger.

DESIGN DECISION — eviction scans the live keys and takes the min of the
pair: O(capacity) per eviction, and that is the honesty the stage pays
for. The bucketed O(1) variant (a doubly-linked list per frequency) moves
the same total order into pointer surgery, and a pointer bug there shows
up as "evicted the wrong key" with the SAME counters — impossible to
distinguish from a policy mistake in a graded run. The scan makes the
policy, and only the policy, judged; `probes` counts every pair the scan
compared, so the bar catches a scan that does not stop. The buckets are
the reader's next exercise, not this stage's contract.

DESIGN DECISION — a `put` over an existing key refreshes value,
frequency, and age — the same three facts a `get` refreshes. A cache
where put and get disagree on age lets a write-heavy caller freeze its
own hot keys while a reader's keys evaporate; the pair order must be the
ONE order both roads maintain.

DESIGN DECISION — counters `hits`, `misses`, `evictions` and the exact
`evicted` tuple are the graded reading: a policy that happens to evict
right on one script but counts wrong is a policy not understood.
"""


class CacheError(Exception):
    """Refusal: a cache this policy cannot run."""


class LFUCache:
    """capacity -> live map; (frequency, age) -> the coldest key."""

    def __init__(self, capacity):
        if isinstance(capacity, bool) or not isinstance(capacity, int) \
                or capacity < 1:
            raise CacheError("capacity must be an int >= 1, not %r"
                             % (capacity,))
        self.capacity = capacity
        self._value = {}
        self._freq = {}
        self._age = {}
        self._clock = 0
        self.hits = 0
        self.misses = 0
        self.probes = 0            # pair comparisons in every coldest scan
        self.evictions = 0
        self.evicted = ()          # keys, in the order they were evicted

    def get(self, key):
        """None on a miss — the lookup that misses must not age a key."""
        if key not in self._value:
            self.misses += 1
            return None
        self.hits += 1
        self._touch(key)
        return self._value[key]

    def _touch(self, key):
        self._clock += 1
        self._freq[key] += 1
    def _coldest(self):
        """The scan, counted: the first key is a free champion, every later
        key is one comparison — so `probes` is exactly capacity-1 per
        eviction and a double scan cannot hide in the arithmetic."""
        best = None
        best_rank = None
        for k in self._value:
            rank = (self._freq[k], self._age[k])
            if best is None:
                best, best_rank = k, rank
                continue
            self.probes += 1
            if rank < best_rank:
                best, best_rank = k, rank
        return best

    def put(self, key, value):
        """Insert or refresh; evict exactly one coldest key when full."""
        if key in self._value:
            self._value[key] = value
            self._touch(key)
            return
        if len(self._value) == self.capacity:
            victim = self._coldest()
            del self._value[victim]
            del self._freq[victim]
            del self._age[victim]
            self.evictions += 1
            self.evicted = self.evicted + (victim,)
        self._clock += 1
        self._value[key] = value
        self._freq[key] = 1        # a newborn's one sighting IS its freq
        self._age[key] = self._clock

    def __contains__(self, key):
        return key in self._value

    def __len__(self):
        return len(self._value)

    def snapshot(self):
        """The live state the check compares against expectation: which
        keys, with which frequencies."""
        return tuple(sorted((k, self._freq[k]) for k in self._value))


#: the script the module and the check both replay: 5 keys, capacity 3.
#: Eviction order is forced by the (freq, age) law, step by step.
SCRIPT = (
    ("put", "a", 1), ("put", "b", 2), ("put", "c", 3),
    ("get", "a", None), ("get", "a", None), ("get", "b", None),
    ("put", "d", 4),            # coldest: c (freq1, oldest of the 1s)
    ("get", "d", None),
    ("put", "e", 5),            # coldest: b (freq1) — a has 2, d has 2, e new
    ("get", "e", None), ("get", "a", None),
    ("put", "f", 6),            # live: a(3) d(2) e(2) +f: coldest d (age 2<3)
)


def replay(script=SCRIPT, capacity=3):
    """Run a fixed (op, key, value) script; return the cache. Scripts are
    data so the check and the learner's demo execute the same history."""
    cache = LFUCache(capacity)
    for op, key, value in script:
        if op == "get":
            cache.get(key)
        elif op == "put":
            cache.put(key, value)
        else:
            raise CacheError("op must be 'get' or 'put', not %r" % (op,))
    return cache


def measure():
    """The measured bars for the LFU stage: the replay's probe count."""
    cache = replay()
    # the eviction law, once by hand: (c, b, d) in that exact order
    assert cache.evicted == ("c", "b", "d"), \
        "eviction order changed: %r — the (freq, age) law is what moved" \
        % (cache.evicted,)
    assert cache.snapshot() == (("a", 4), ("e", 2), ("f", 1)), \
        cache.snapshot()
    return {"lfu_probes": cache.probes, "lfu_evictions": cache.evictions}


if __name__ == "__main__":
    c = replay()
    print("stage 9 — LFU cache:", measure(), "evicted:", c.evicted)
