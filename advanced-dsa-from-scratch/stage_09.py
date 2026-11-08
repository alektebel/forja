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
        # TODO: validate capacity; value/freq/age maps and the counters.
        raise NotImplementedError("LFUCache.__init__")

    def get(self, key):
        """None on a miss — the lookup that misses must not age a key."""
        # TODO: miss -> None and misses++; hit -> value and a touch.
        raise NotImplementedError("LFUCache.get")

    def _touch(self, key):
        # TODO: new sighting: bump the clock and the frequency.
        raise NotImplementedError("LFUCache._touch")
    def _coldest(self):
        """The scan, counted: the first key is a free champion, every later
        key is one comparison — so `probes` is exactly capacity-1 per
        eviction and a double scan cannot hide in the arithmetic."""
        # TODO: scan every live key, one counted probe after the champion.
        raise NotImplementedError("LFUCache._coldest")

    def put(self, key, value):
        """Insert or refresh; evict exactly one coldest key when full."""
        # TODO: refresh an existing key; otherwise evict the coldest when full.
        raise NotImplementedError("LFUCache.put")

    def __contains__(self, key):
        # TODO: is the key live?
        raise NotImplementedError("LFUCache.__contains__")

    def __len__(self):
        # TODO: the live count.
        raise NotImplementedError("LFUCache.__len__")

    def snapshot(self):
        """The live state the check compares against expectation: which
        keys, with which frequencies."""
        # TODO: sorted (key, frequency) pairs.
        raise NotImplementedError("LFUCache.snapshot")


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
    # TODO: run the (op, key, value) script through one cache.
    raise NotImplementedError("replay")


def measure():
    """The measured bars for the LFU stage: the replay's probe count."""
    # TODO: the replay's probe and eviction counters as the bars.
    raise NotImplementedError("measure")


if __name__ == "__main__":
    c = replay()
    print("stage 9 — LFU cache:", measure(), "evicted:", c.evicted)
