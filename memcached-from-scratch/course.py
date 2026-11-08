"""Memcached From Scratch — course manifest.

Ten graded stages that build the internals of the largest cache fleet ever
run — not the client library, not "put Redis in front", but the things the
ops teams at Danga, LiveJournal and Facebook had to write into the daemon
and its clients to survive petabyte-scale reads: a ring that routes
without maintaining a mapping, a slab allocator that never splits a value,
an LRU that evicts a whole page and buries a hot key with it, a protocol
whose byte counts are verified before anything is stored, and then the
client-side defences the NSDI'13 paper measured — tail tolerance,
statistical herding, single-flight, warm restart — ending in a capstone
whose two runs produce one identical byte string.

The thesis of the whole course, asserted by every check: THE CACHE IS A
DATA STRUCTURE, NOT A THREAD POOL. No stage imports `time`, `random`,
`threading` or `asyncio`; the clock is injected and moves only by integer
costs; every coin is `stable_hash` of names and ticks. A race is therefore
provable with arithmetic, a tail is reproducible, and determinism is not a
property you hope for — it is a property the capstone check reads off two
digests.

`world.py` is provided and complete: `CacheError`, the integer `Clock`,
`stable_hash`, and the `Origin` of record whose `queries` counter is what
every protection stage is finally measured against. The exercise is the
daemon and its clients.

    python3 codecraft/cli.py run memcached-from-scratch
"""

from codecraft.api import stage

TITLE = "Memcached From Scratch"
DESCRIPTION = ("The ops-at-scale internals of memcached on an injected "
               "integer clock: route keys on a hash ring with virtual nodes "
               "instead of a mod-N mapping, place items on a slab ladder "
               "without splitting a value, evict whole pages and let a hot "
               "key die with its neighbours, answer the ASCII protocol "
               "byte-exactly with CAS tokens and chunk checks, cut the tail "
               "with hedged gets while the origin's query ledger rises, herd "
               "a synchronized expiry over ticks with a ramp-priced coin, "
               "fold a cold stampede with a per-key flight and show that "
               "neither flight nor herding protects the other's shape, "
               "survive a node crash with zero origin queries and refill a "
               "warm restart through reads, report from counters that must "
               "add up, and replay the whole machine twice into one "
               "identical byte string.")
LEVEL = "intermediate"
ORDER = 41

# --- the checks. Each one is self-contained: its fixtures are nested
# inside it because `course.py` is one namespace for ten stages.

import hashlib
import json
import os
import sys


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(HERE))

    def _repo(start=None):
        for candidate_start in (os.environ.get("M1_REPO"), start,
                                os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "memcached-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("cannot find the repo: set M1_REPO=/path/to/repo/root")

    def _refuses(exc, what, call):
        try:
            accepted = call()
        except exc as err:
            return str(err)
        raise AssertionError("%s was accepted: %r" % (what, accepted))

    _repo()
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if DEFAULT_REPO not in sys.path:
        sys.path.append(DEFAULT_REPO)

    import world
    import stage_01 as s

    reject = world.CacheError

    # --- the frozen default: 150 points per node, not one ------------------
    assert s.VNODES == 150, (
        "the ring's default vnode count is %r, not the course's 150 — the "
        "lumpiness test below leans on this exact default" % (s.VNODES,))
    _refuses(reject, "a vnode count of zero", lambda: s.HashRing(vnodes=0))
    _refuses(reject, "a vnode count that is a bool",
             lambda: s.HashRing(vnodes=True))
    _refuses(reject, "a vnode count that is a float",
             lambda: s.HashRing(vnodes=1.5))

    ring = s.HashRing()
    for i in range(6):
        ring.add_node("node-%d" % i)

    _refuses(reject, "an empty node name", lambda: ring.add_node(""))
    _refuses(reject, "a duplicated node", lambda: ring.add_node("node-0"))
    _refuses(reject, "a node name that is not text", lambda: ring.add_node(7))

    # --- positions sorted; route is the first point strictly clockwise ----
    points = ring.positions()
    assert points == tuple(sorted(points)), (
        "positions() is not in clockwise order, so 'the next node' means "
        "whatever order the list happened to keep")
    assert len(points) == 6 * s.VNODES, (
        "the ring holds %r points, expected 6 nodes x %r vnodes"
        % (len(points), s.VNODES))

    keys = ["k%d" % i for i in range(12000)]

    def _pos(key):
        return int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16)

    def _want(key):
        pos = _pos(key)
        for p, n in points:
            if p > pos:
                return n
        return points[0][1]

    for k in keys[:2000]:
        got = ring.route(k)
        assert got in ring.nodes(), (
            "route('%s') answered %r, a node that is not on the ring"
            % (k, got))
        assert got == _want(k), (
            "route('%s') is not the first point strictly clockwise of the "
            "key's own md5: got %r, expected %r — the ring must order, "
            "not guess" % (k, got, _want(k)))

    wrapped = [k for k in keys if _pos(k) > points[-1][0]]
    assert wrapped and all(ring.route(k) == points[0][1] for k in wrapped), (
        "a key past the last point must wrap to the first — the ring is a "
        "circle, not a range; %d such keys were found" % len(wrapped))

    _refuses(reject, "routing on an empty ring",
             lambda: s.HashRing().route("k0"))
    _refuses(reject, "an empty key", lambda: ring.route(""))
    _refuses(reject, "a key that is not text", lambda: ring.route(42))

    # --- the load test 150 vnodes exists for --------------------------------
    counts = {}
    for k in keys:
        n = ring.route(k)
        counts[n] = counts.get(n, 0) + 1
    ideal = len(keys) // 6
    worst = max(abs(c - ideal) for c in counts.values())
    assert worst * 100 < 15 * ideal, (
        "the worst node carries %d of the %d it should — worse than random: "
        "the virtual nodes are not interleaving the ranges"
        % (ideal - worst, ideal))

    lumped = s.HashRing(vnodes=1)
    for i in range(9):
        lumped.add_node("node-%d" % i)
    counts = {}
    for k in keys:
        n = lumped.route(k)
        counts[n] = counts.get(n, 0) + 1
    ideal = len(keys) // 9
    worst = max(abs(c - ideal) for c in counts.values())
    assert worst * 2 > ideal, (
        "one point per node spread %d keys across 9 nodes with worst "
        "deviation %d%% — if that passes, the test ring is not the one the "
        "lesson needs" % (len(keys), 100 * worst // ideal))

    # --- the reason a mapping is refused, not maintained --------------------
    ring5 = s.HashRing()
    for i in range(5):
        ring5.add_node("node-%d" % i)
    keys5 = ["k%d" % i for i in range(10000)]
    before = [ring5.route(k) for k in keys5]
    ring5.remove_node("node-2")
    after = [ring5.route(k) for k in keys5]
    moved = sum(1 for a, b in zip(before, after) if a != b)
    assert moved * 4 <= len(keys5), (
        "dropping 1 of 5 nodes moved %d%% of the keys — a mod-5 mapping "
        "moves ~80%%; the ring is re-lotterying, not routing"
        % (100 * moved // len(keys5)))
    assert all(a == b for a, b in zip(before, after) if a != "node-2"), (
        "a key whose node survived changed hands — the only keys allowed "
        "to move are the dead node's own range")
    assert "node-2" not in set(after) and set(after) <= set(ring5.nodes()), (
        "the removed node is still answering routes")
    _refuses(reject, "removing a node that is not there",
             lambda: ring5.remove_node("node-2"))

    # --- re-adding puts every point back, and order of adding is nothing ---
    never_broke = s.HashRing()
    for i in range(5):
        never_broke.add_node("node-%d" % i)
    rebuilt = s.HashRing()
    for i in range(5):
        rebuilt.add_node("node-%d" % i)
    rebuilt.remove_node("node-2")
    rebuilt.add_node("node-2")
    assert rebuilt.positions() == never_broke.positions(), (
        "a remove+add cycle did not restore the ring exactly — vnode "
        "positions are hashed from the name, so they must be identical "
        "forever")
    other = s.HashRing()
    for i in reversed(range(6)):
        other.add_node("node-%d" % i)
    assert all(other.route(k) == ring.route(k) for k in keys[:1000]), (
        "routing depends on the order nodes were added — the ring is a "
        "list with a sort missing")

    # --- successors: clockwise, distinct, starting at the route ------------
    def _clockwise(key, count):
        pos = _pos(key)
        n = len(points)
        start = 0
        for i, (p, _) in enumerate(points):
            if p > pos:
                start = i
                break
        out, seen = [], set()
        for step in range(n):
            node = points[(start + step) % n][1]
            if node in seen:
                continue
            seen.add(node)
            out.append(node)
            if len(out) == count:
                break
        return out

    for k in keys[:500]:
        succ = ring.successors(k, 3)
        assert succ == _clockwise(k, 3), (
            "successors('%s', 3) is %r, expected the clockwise walk %r "
            "starting at the route" % (k, succ, _clockwise(k, 3)))
    big = ring.successors("k1", 99)
    assert sorted(big) == sorted(ring.nodes()) and len(big) == 6, (
        "asking for 99 replicas on a 6-node ring must name all 6 nodes "
        "once, not repeat: %r" % (big,))
    _refuses(reject, "successors with a count below 1",
             lambda: ring.successors("k1", 0))

    return "ring: strict clockwise routing, <15% spread at 12k, 1-vnode " \
           "lumpy, drop moves <=25% of keys"


# --- stage 2 -----------------------------------------------------------------------
def check_2():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(HERE))

    def _repo(start=None):
        for candidate_start in (os.environ.get("M2_REPO"), start,
                                os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "memcached-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("cannot find the repo: set M2_REPO=/path/to/repo/root")

    def _refuses(exc, what, call):
        try:
            accepted = call()
        except exc as err:
            return str(err)
        raise AssertionError("%s was accepted: %r" % (what, accepted))

    _repo()
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if DEFAULT_REPO not in sys.path:
        sys.path.append(DEFAULT_REPO)

    import world
    import stage_02 as s

    reject = world.CacheError

    # --- the ladder itself ---------------------------------------------------
    slab = s.Slab(start=8, growth=2.0, max_item=64, page_bytes=64)
    assert slab.classes() == (8, 16, 32, 64), (
        "the ladder from 8 doubling under 64 is %r, not (8, 16, 32, 64)"
        % (slab.classes(),))
    assert slab.class_for(0) == 8 and slab.class_for(5) == 8 \
        and slab.class_for(8) == 8, (
        "a size at or under the first class does not round up to it")
    assert slab.class_for(9) == 16 and slab.class_for(17) == 32 \
        and slab.class_for(33) == 64, (
        "class_for is not the SMALLEST class that fits — rounding to the "
        "nearest or the largest is a different allocator")

    text = _refuses(reject, "an item past the max class",
                    lambda: slab.class_for(65))
    assert "65" in text and "64" in text and "split" in text, (
        "the refusal did not name the size, the ceiling and the rule: %r"
        % text)
    _refuses(reject, "a bool size", lambda: slab.class_for(True))
    _refuses(reject, "a float size", lambda: slab.class_for(9.5))
    _refuses(reject, "a negative size", lambda: slab.class_for(-1))
    _refuses(reject, "a growth of 1.0", lambda: s.Slab(growth=1.0))
    _refuses(reject, "a start above the max item",
             lambda: s.Slab(start=48, max_item=47))

    # --- placement: a slot names its class, page and hole --------------------
    a = slab.place("user:1", 10)
    assert (a.cls, a.page, a.index) == (16, 0, 0), (
        "the first 10-byte item got %r, not the 16-class page 0 slot 0"
        % (a,))
    b = slab.place("user:2", 5)
    assert (b.cls, b.page, b.index) == (8, 0, 0), (
        "a 5-byte item does not get the 8-class page's first slot: %r" % (b,))
    assert a != b and slab.slot_of("user:1") == a == s.Slot(16, 0, 0), (
        "slots of different classes collide, or Slot does not compare by "
        "(cls, page, index)")
    assert repr(a) == "Slot(cls=16, page=0, index=0)", (
        "the slot does not print its three facts: %r" % (repr(a),))
    assert len({a, b, s.Slot(16, 0, 0)}) == 2, (
        "Slot is not hashable by its triple — stage 3's free lists will "
        "double-book a hole")

    dup = _refuses(reject, "a double-place of one key",
                   lambda: slab.place("user:1", 10))
    assert "user:1" in dup, (
        "the double-place refusal did not name the key whose slot it "
        "would have orphaned: %r" % dup)
    _refuses(reject, "an empty key", lambda: slab.place("", 4))
    _refuses(reject, "a non-text key", lambda: slab.place(5, 4))

    # --- holes come before pages ---------------------------------------------
    before = slab.stats()
    assert before["pages"][16] == 1 and before["free"][16] == 0, (
        "the first class-16 place should sit on page 0 with no holes: %r"
        % before)
    slab.remove("user:1")
    _refuses(reject, "a double remove", lambda: slab.remove("user:1"))
    _refuses(reject, "a slot_of for a key that holds nothing",
             lambda: slab.slot_of("user:1"))
    after = slab.stats()
    assert after["free"][16] == 1, (
        "the remove did not put the flat index back on the free list: %r"
        % after)
    c = slab.place("user:3", 12)                     # class 16 again
    assert (c.cls, c.page, c.index) == (16, 0, 0), (
        "the 12-byte item did not land in the freed 16/0/0 hole: %r" % (c,))
    assert slab.stats()["pages"][16] == before["pages"][16], (
        "a hole was free in class 16 and a new item still triggered a "
        "page — fragmentation IS this")
    assert c == a, (
        "the reused hole is not the one that was freed: %r vs %r" % (c, a))

    # --- growth only when the holes are gone -----------------------------------
    d = slab.place("user:4", 9)                      # class 16 page 0 index 1
    assert (d.cls, d.page, d.index) == (16, 0, 1), (
        "the next class-16 item skipped the page's own next hole: %r" % (d,))
    e = slab.place("user:5", 9)                      # class 16 page 0 index 2
    f = slab.place("user:6", 14)                     # index 3 — page has 4
    for slot in (e, f):
        assert slot.page == 0, (
            "a class with room on its page opened page 1 anyway: %r" % slot)
    g = slab.place("user:7", 15)                     # index 4: new page
    assert (g.cls, g.page, g.index) == (16, 1, 0), (
        "the class of 4 slots per page filled and the 5th landed at %r — "
        "flat index 4 must decode to page 1 slot 0" % (g,))
    st = slab.stats()
    assert st["pages"][16] == 2 and st["granted"][16] == 5, (
        "after four class-16 items, one hole reused, and one page grown: %r"
        % st)
    assert st["granted"][16] <= st["pages"][16] * (64 // 16), (
        "class 16 granted more flat indices than its pages hold")
    assert slab.live() == 6, (
        "live() is %r after 7 places and 1 remove — it counts writes to a "
        "log, not keys held" % slab.live())
    _refuses(reject, "a place past the max", lambda: slab.place("big", 65))

    # --- the default ladder is the daemon's own ---------------------------------
    big = s.Slab()
    assert big.classes()[0] == s.SLAB_START == 48, (
        "the default ladder starts at %r, not the daemon's 48"
        % (s.SLAB_START,))
    last = big.classes()[-1]
    assert last <= s.SLAB_MAX_ITEM < 2 * last, (
        "the default ladder tops out at %r, not just under the daemon's "
        "1 MB ceiling: growth 1.25 should overshoot ONCE at most" % (last,))
    _refuses(reject, "a value one byte past the last class",
             lambda: big.class_for(s.SLAB_MAX_ITEM))

    return "slab: smallest-fit ladder, holes before pages, flat indices " \
           "decode to (page, index), granted <= pages x spp"


# --- stage 3 -----------------------------------------------------------------------
def check_3():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(HERE))

    def _repo(start=None):
        for candidate_start in (os.environ.get("M3_REPO"), start,
                                os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "memcached-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("cannot find the repo: set M3_REPO=/path/to/repo/root")

    def _refuses(exc, what, call):
        try:
            accepted = call()
        except exc as err:
            return str(err)
        raise AssertionError("%s was accepted: %r" % (what, accepted))

    _repo()
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if DEFAULT_REPO not in sys.path:
        sys.path.append(DEFAULT_REPO)

    import world
    import stage_03 as s

    reject = world.CacheError

    # --- page mechanics: the verbs the eviction is made of ---------------------
    page = s.Page(8, 0, 2)
    assert page.full() is False and page.free_slot() == 0, (
        "a new page is not empty or does not name its first hole")
    slot_a = page.put("a", "x", 0, 0, 1)
    slot_b = page.put("b", "x", 0, 0, 2)
    assert (slot_a, slot_b) == (0, 1) and page.full() is True, (
        "the page's holes are not handed out in order, or full() lies")
    _refuses(reject, "a free slot on a full page", page.free_slot)
    page.touch(slot_a, 50)
    assert page.order == [slot_b, slot_a], (
        "touch did not move the slot to the young end: %r" % (page.order,))
    assert page.items[slot_a].touched == 50, "touch did not stamp the item"
    assert page.lru_stamp() == 2, (
        "lru_stamp must be the OLDEST front's stamp, not the newest: %r"
        % page.lru_stamp())
    doomed = page.clear()
    assert [it.key for it in doomed] == ["b", "a"], (
        "clear must return the dying items in the page's own order: %r"
        % ([it.key for it in doomed],))
    assert page.items == {} and page.order == [] \
        and page.lru_stamp() is None, (
        "the recycled page came back dirty — its next tenant inherits "
        "someone else's age")
    drop_page = s.Page(8, 0, 2)
    drop_page.put("x", "v", 0, 0, 1)
    assert drop_page.drop(0).key == "x" and drop_page.free_slot() == 0, (
        "drop did not free the slot for reuse")

    # --- item facts the protocol answers with -----------------------------------
    slab = s.LruSlab(capacity_per_page=2, max_pages_per_class=1)
    slab.store("k", "value", now=7, flags=3, exptime=40)
    item = slab.get("k", 10)
    assert (item.key, item.value, item.flags, item.exptime) == (
        "k", "value", 3, 40), (
        "the item does not carry the facts stage 4's VALUE line needs: %r"
        % (item,))
    assert item.touched == 10, "a marked read did not stamp the item"
    slab.store("peek", "v", now=10)
    slab.get("peek", 55, mark=False)
    assert slab.get("peek", 56, mark=False).touched == 10, (
        "mark=False still stamped — a peek is how stats and the LRU "
        "order lie about recency")
    assert slab.get("k", 39) is not None and slab.get("k", 40) is None, (
        "the expiry boundary is now >= exptime, not >")
    assert slab.stats()["expired_freed"] == 1, (
        "the expired read answered a miss but kept the bytes")

    _refuses(reject, "an empty key", lambda: slab.store("", "v", now=1))
    _refuses(reject, "a value that is not text",
             lambda: slab.store("k2", 5, now=1))
    _refuses(reject, "an exptime at or before now",
             lambda: slab.store("k3", "v", now=70, exptime=70))
    _refuses(reject, "a capacity that is a bool", lambda: s.LruSlab(True, 2))
    _refuses(reject, "a page limit that is zero", lambda: s.LruSlab(2, 0))
    assert slab.get("absent", 1) is None and slab.delete("absent") is False, (
        "a miss is not None or deleting it is not False")

    # --- re-store replaces and refreshes, never doubles --------------------------
    slab = s.LruSlab(capacity_per_page=2, max_pages_per_class=2)
    slab.store("a", "x", now=1)
    slab.store("b", "x", now=100)               # page 1, front = 'a' at 1
    slab.store("c", "x", now=50)
    slab.store("d", "x", now=60)                # page 2, front = 'c' at 50
    slab.store("a", "yy", now=70)               # replaces, touches 'a'
    assert slab.live() == 4, (
        "re-storing a key grew the store to %r — a value and its old copy "
        "now share a class" % slab.live())
    assert slab.get("a", 71, mark=False).value == "yy", (
        "re-store kept the old value")
    slab.store("e", "x", now=80)                # full class: recycle a page
    assert slab.get("c", 81) is None and slab.get("d", 81) is None, (
        "the touching replace must have moved page 1's front to 'b' at 100, "
        "making page 2 (front 'c' at 50) the oldest — the victim is chosen "
        "by the page's own front, and 'a' + 'b' survive together: c=%r d=%r"
        % (slab.get("c", 81), slab.get("d", 81)))
    assert slab.get("a", 81) is not None and slab.get("b", 81) is not None, (
        "a read that refreshed 'a' did not save the page it lives on — the "
        "refresh must reorder the page's own LRU")
    st = slab.stats()
    assert st["evicted_pages"] == 1 and st["evicted_items"] == 2 \
        and slab.live() == 3, (
        "one page of two died and the ledger read %r — items are counted "
        "for the `evictions` stat, and the recycler's first tenant is 'e'"
        % (st,))

    # --- the hot key dies with its page -----------------------------------------
    slab = s.LruSlab(capacity_per_page=2, max_pages_per_class=2)
    slab.store("p1:a", "x", now=1)
    slab.store("p1:b", "x", now=2)
    slab.store("hot", "x", now=3)
    slab.store("p2:c", "x", now=100)
    for t in range(200, 300):
        assert slab.get("hot", t) is not None
    slab.store("newcomer", "x", now=400)
    assert slab.get("p1:a", 401) is None and slab.get("p1:b", 401) is None, (
        "the whole-page recycle missed a neighbour — either eviction is "
        "per slot after all, or the page's map and order diverged")
    assert slab.get("hot", 401) is not None, (
        "the beloved key died at its own page's front: a read must move it")
    st = slab.stats()
    assert st["evicted_pages"] == 1 and st["evicted_items"] == 2, (
        "one page of two died and the counters read %r — items must be "
        "counted for the `evictions` stat" % st)
    slab.store("p1:d", "x", now=500)
    slab.store("newcomer2", "x", now=600)
    assert slab.get("hot", 601) is None, (
        "the hot key survived its own page being recycled — the victim is "
        "the page whose FRONT is oldest, and the recycler's first tenant "
        "must be re-aged or the page is chosen again on an item it no "
        "longer holds")
    st = slab.stats()
    assert st["evicted_pages"] == 2 and st["evicted_items"] == 4, (
        "after two wholesale recycles the ledger reads %r" % st)

    # --- the freed slot is reused before any page is recycled --------------------
    slab.delete("p1:d")
    alive_before = slab.stats()["evicted_pages"]
    slab.store("rebound", "x", now=610)
    assert slab.stats()["evicted_pages"] == alive_before, (
        "a hole existed and the class still recycled a page")

    # --- expiry frees before it answers -------------------------------------------
    slab = s.LruSlab(capacity_per_page=4, max_pages_per_class=1)
    slab.store("dies@700", "y", now=650, exptime=700)
    assert slab.get("dies@700", 699) is not None, (
        "an item at 699 of its 700 is not expired")
    assert slab.get("dies@700", 700) is None, "expiry at its own tick"
    assert slab.stats()["expired_freed"] == 1, (
        "the expired read answered a miss but kept the bytes")
    before = slab.stats()["evicted_pages"]
    slab.store("fill1", "a", now=701)
    slab.store("fill2", "b", now=702)
    slab.store("fill3", "c", now=703)
    assert slab.stats()["evicted_pages"] == before, (
        "the expired item's slot was not reused — expiry that does not "
        "free grows pages instead of holes")

    return "lru: page verbs, replace-refreshes, wholesale recycle buries " \
           "the hot key, expiry frees its slot"


# --- stage 4 -----------------------------------------------------------------------
def check_4():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(HERE))

    def _repo(start=None):
        for candidate_start in (os.environ.get("M4_REPO"), start,
                                os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "memcached-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("cannot find the repo: set M4_REPO=/path/to/repo/root")

    _repo()
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if DEFAULT_REPO not in sys.path:
        sys.path.append(DEFAULT_REPO)

    import world
    import stage_03 as store_mod
    import stage_04 as s

    E = s.CRLF
    assert s.CRLF == "\r\n", (
        "the terminator is %r — a response joined on \\n is one invisible "
        "character away from a client that hangs" % s.CRLF)
    assert s.RELATIVE_BOUNDARY == 2592000, (
        "the relative/absolute boundary is the daemon's 30 days: %r"
        % s.RELATIVE_BOUNDARY)
    reject = world.CacheError

    # --- the exptime rule, exact at the boundary -----------------------------
    assert s.absolute_exptime(0, 500) == 0, "0 must mean never, not tick 500"
    assert s.absolute_exptime(60, 500) == 560, "relative must be now + raw"
    assert s.absolute_exptime(2592000, 5) == 2592005, (
        "exactly at the boundary is still relative — the daemon's rule is "
        "at-or-below")
    assert s.absolute_exptime(2592001, 5) == 2592001, (
        "past the boundary is an absolute tick, not a huge offset")
    for bad in (True, -1, "60", 1.5):
        try:
            got = s.absolute_exptime(bad, 0)
        except reject:
            pass
        else:
            raise AssertionError("exptime %r was accepted as %r" % (bad, got))

    # --- parse refuses the lines the daemon answers ERROR to -------------------
    assert s.parse("get a b") == ("get", ("a", "b"))
    assert s.parse("version") == ("version", ())
    for bad in ("", " set a 0 0 1", "trailing "):
        try:
            s.parse(bad)
        except reject:
            pass
        else:
            raise AssertionError("parse accepted the malformed line %r" % bad)

    ascii_ = s.Ascii(store_mod.LruSlab(2, 2), world.Clock())

    # --- set/get/gets, byte for byte -------------------------------------------
    got = ascii_.handle("set user:1 0 60 5" + E + "alice" + E + "END" + E)
    assert got == "STORED" + E, "the storing reply is %r, not the 8 bytes" % got
    assert ascii_.handle("get user:1" + E) == (
        "VALUE user:1 0 5" + E + "alice" + E + "END" + E), (
        "the get answer is not VALUE/size, data, END byte-exact")
    head = ascii_.handle("gets user:1" + E).split(E)[0]
    assert head == "VALUE user:1 0 5 1", (
        "gets must carry the CAS token the set minted, as a 4th field: %r"
        % head)

    # --- the chunk is verified BEFORE anything is stored -----------------------
    wrong = ascii_.handle("set user:1 0 0 6" + E + "END" + E + "END" + E)
    assert wrong == "CLIENT_ERROR bad data chunk" + E, (
        "a mismatched byte count is answered %r — CLIENT_ERROR or nothing "
        "else: the client framed wrong and must not leave a half-write"
        % wrong)
    assert "alice" in ascii_.handle("get user:1" + E), (
        "the bad-chunk set still stored: the count was verified after the "
        "store, which is the bug this stage exists for")

    # --- add / replace are different refusals -----------------------------------
    assert ascii_.handle("add user:1 0 0 1" + E + "z" + E + "END" + E) \
        == "NOT_STORED" + E, "add of an existing key stored anyway"
    assert ascii_.handle("add fresh:1 0 0 1" + E + "z" + E + "END" + E) \
        == "STORED" + E, "add of a new key refused"
    assert ascii_.handle("replace nothere 0 0 1" + E + "z" + E + "END" + E) \
        == "NOT_STORED" + E, "replace of a missing key stored anyway"
    assert ascii_.handle("replace user:1 0 0 2" + E + "ab" + E + "END" + E) \
        == "STORED" + E, "replace of an existing key refused"

    # --- CAS: EXISTS when beaten, NOT_FOUND when gone ----------------------------
    assert ascii_.handle("cas user:1 0 0 6 1" + E + "alicia" + E + "END" + E) \
        == "EXISTS" + E, (
        "a stale CAS token answered something else — 'someone beat you' "
        "and 'the key is gone' are different repairs")
    token = int(ascii_.handle("gets user:1" + E).split(E)[0].split()[4])
    assert ascii_.handle("cas user:1 0 0 6 %d" % token + E + "alicia" + E
                        + "END" + E) == "STORED" + E, (
        "the current token did not store")
    new_token = int(ascii_.handle("gets user:1" + E).split(E)[0].split()[4])
    assert new_token > token, (
        "a successful mutation did not bump the CAS token")
    assert ascii_.handle("cas gone:1 0 0 1 1" + E + "z" + E + "END" + E) \
        == "NOT_FOUND" + E, (
        "cas of a missing key answered EXISTS — the client would retry a "
        "key that will never come back")
    assert ascii_.handle("cas user:1 0 0 1 notanumber" + E + "z" + E
                        + "END" + E) == "ERROR" + E, (
        "a CAS token that is not digits must be ERROR — framing first, "
        "token second: the byte count here matches so the refusal can "
        "only come from the token")
    assert ascii_.handle("set k 0 0 1 x" + E + "z" + E + "END" + E) \
        == "ERROR" + E, "a key with a space in it is not a framing success"
    assert ascii_.handle("set k2 0 0 3" + E + "ab" + E + "END" + E) \
        == "CLIENT_ERROR bad data chunk" + E
    assert ascii_.handle("get k2" + E) == "END" + E, (
        "a short data chunk stored a prefix — the byte count is the "
        "whole rule")

    # --- arithmetic: floored, never wrapping ---------------------------------------
    ascii_ = s.Ascii(store_mod.LruSlab(2, 2), world.Clock())
    ascii_.handle("set count 0 0 1" + E + "7" + E + "END" + E)
    assert ascii_.handle("incr count 2" + E) == "9" + E
    assert ascii_.handle("decr count 99" + E) == "0" + E, (
        "decr past zero wrapped negative or round-tripped a huge int — "
        "the daemon floors at 0")
    assert ascii_.handle("incr nothere 1" + E) == "NOT_FOUND" + E
    ascii_.handle("set txt 0 0 3" + E + "abc" + E + "END" + E)
    assert ascii_.handle("incr txt 1" + E) == "ERROR" + E, (
        "incr of a non-number computed something")

    # --- delete, touch, version, ERROR ---------------------------------------------
    assert ascii_.handle("delete count" + E) == "DELETED" + E
    assert ascii_.handle("delete count" + E) == "NOT_FOUND" + E
    assert ascii_.handle("get count" + E) == "END" + E
    assert ascii_.handle("set t1 0 0 1" + E + "x" + E + "END" + E) \
        == "STORED" + E
    assert ascii_.handle("touch t1 50" + E) == "TOUCHED" + E
    assert ascii_.handle("touch gone 50" + E) == "NOT_FOUND" + E
    assert ascii_.handle("version" + E) == "VERSION " + s.VERSION + E
    assert ascii_.handle("frobnicate x" + E) == "ERROR" + E
    assert ascii_.handle("" + E) == "ERROR" + E

    # --- multi-key get counts KEYS, and stats derive from the counters -------------
    ascii_ = s.Ascii(store_mod.LruSlab(2, 2), world.Clock())
    ascii_.handle("set a 0 0 1" + E + "x" + E + "END" + E)
    reply = ascii_.handle("get a b" + E)
    assert reply == "VALUE a 0 1" + E + "x" + E + "END" + E, (
        "a multi-get with one present key: %r — missing keys are silent "
        "inside the END block, not a separate line" % reply)
    assert ascii_.hits == 1 and ascii_.misses == 1, (
        "hits %r misses %r — a get of two keys counts two keys, not one "
        "command" % (ascii_.hits, ascii_.misses))
    stats = ascii_.handle("stats" + E)
    rows = {}
    for line in stats.split(E):
        if line.startswith("STAT "):
            name, _, value = line[5:].partition(" ")
            rows[name] = value
    assert rows["get_hits"] == "1" and rows["get_misses"] == "1", (
        "stats contradicts the counters the protocol kept: %r" % rows)
    assert rows["curr_items"] == "1" and rows["evictions"] == "0", (
        "stats must ask the STORE for items and evictions, never keep a "
        "second copy: %r" % rows)
    assert stats.endswith("END" + E) and rows["version"] == s.VERSION, (
        "the stats block is not STAT rows terminated by END: %r" % stats)

    return "ascii: byte-exact verbs, chunk-before-store, EXISTS != " \
           "NOT_FOUND, keys-not-commands, derived stats"


# --- stage 5 -----------------------------------------------------------------------
def check_5():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(HERE))

    def _repo(start=None):
        for candidate_start in (os.environ.get("M5_REPO"), start,
                                os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "memcached-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("cannot find the repo: set M5_REPO=/path/to/repo/root")

    _repo()
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if DEFAULT_REPO not in sys.path:
        sys.path.append(DEFAULT_REPO)

    import world
    import stage_01 as ring_mod
    import stage_05 as s

    rows = {"k%d" % i: ("v%d" % i, 4) for i in range(600)}
    clock = world.Clock()
    origin = world.Origin(rows)
    ring = ring_mod.HashRing()
    for n in ("a", "b", "c"):
        ring.add_node(n)
    servers = {n: s.Server(n, origin, clock) for n in ("a", "b", "c")}

    # --- the delay is a fact about (node, key), never a coin ------------------
    assert s.Server.FAST < s.Server.SLOW, (
        "a node's slow delay must exceed its fast delay or there is no "
        "tail to cut")
    for k in ("k0", "k7", "k123"):
        d = servers["a"].delay(k)
        assert d in (s.Server.FAST, s.Server.SLOW) and d == servers["a"].delay(k), (
            "delay('%s') is %r or moved between calls — the tail must be "
            "a fixed slice of (node, key), not a coin" % (k, d))
        assert servers["a"].total(k) == d + 4, (
            "total() must add the origin's rebuild cost to the service "
            "delay or the backup fires on the wrong arithmetic")

    # --- one slow primary, one fast successor: the backup wins, and pays ------
    slow_fast = [k for k in sorted(rows)
                 if servers[ring.route(k)].delay(k) == s.Server.SLOW
                 and servers[ring.successors(k, 2)[1]].delay(k)
                 == s.Server.FAST]
    assert slow_fast, (
        "no key in 600 has a slow primary and a fast successor — with a "
        "fixed 1-in-10 slow slice across 3 nodes at least one must")
    k = slow_fast[0]
    primary = servers[ring.route(k)]
    backup = servers[ring.successors(k, 2)[1]]
    assert primary.total(k) == 29 and backup.total(k) == 7, (
        "the fixture's arithmetic moved: primary %r backup %r"
        % (primary.total(k), backup.total(k)))

    clock = world.Clock()
    origin = world.Origin(rows)
    servers = {n: s.Server(n, origin, clock) for n in ("a", "b", "c")}
    client = s.TailClient(ring, servers, clock, backup_after=8)
    value, waited, winner = client.get(k)
    assert value == rows[k][0], "the backup answered the wrong value"
    assert winner == ring.successors(k, 2)[1], (
        "the winner of a slow-primary get was %r, not the fast successor"
        % winner)
    assert client.backups_sent == 1 and client.backups_won == 1, (
        "a slow primary behind an 8-tick fuse must send and win exactly "
        "one backup: sent=%r won=%r"
        % (client.backups_sent, client.backups_won))
    assert waited == 15, (
        "waited %r is not fire(8) + successor delay(3) + rebuild(4)"
        % waited)
    assert origin.queries == 2, (
        "one hedged get cost %r origin queries — the abandoned request is "
        "not cancellable: it still reads the origin. A client that "
        "reports 1 is not cutting the tail, it is hiding the ledger"
        % origin.queries)
    assert clock.now == 29, (
        "the clock stopped at the winner's 15 and dropped the loser's "
        "completion: %r" % clock.now)

    # --- a fast key: no backup, one query, the plain wait -----------------------
    fast_key = next(k for k in sorted(rows)
                    if servers[ring.route(k)].delay(k) == s.Server.FAST)
    clock = world.Clock()
    origin = world.Origin(rows)
    servers = {n: s.Server(n, origin, clock) for n in ("a", "b", "c")}
    client = s.TailClient(ring, servers, clock, backup_after=8)
    value, waited, winner = client.get(fast_key)
    assert waited == 7 and origin.queries == 1 and client.backups_sent == 0, (
        "a within-fuse get hedged anyway: waited=%r queries=%r sent=%r"
        % (waited, origin.queries, client.backups_sent))

    # --- one node: nowhere to back up, and the client knows --------------------
    solo = ring_mod.HashRing()
    solo.add_node("a")
    clock = world.Clock()
    origin = world.Origin(rows)
    servers = {"a": s.Server("a", origin, clock)}
    client = s.TailClient(solo, servers, clock, backup_after=8)
    for key in sorted(rows):
        client.get(key)
    assert client.backups_sent == 0 and origin.queries == 600, (
        "a single-node ring sent %r backups and cost %r queries — with no "
        "successor there is nothing to hedge against, and every request "
        "still costs exactly one read"
        % (client.backups_sent, origin.queries))

    # --- the sweep: latency bought with queries, identically twice --------------
    keys = sorted(rows)
    p1 = s.run_plain(ring, rows, keys)
    p2 = s.run_plain(ring, rows, keys)
    b1 = s.run_with_backup(ring, rows, keys, backup_after=8)
    b2 = s.run_with_backup(ring, rows, keys, backup_after=8)
    assert (p1["worst"], p1["clock"], p1["queries"]) == \
        (p2["worst"], p2["clock"], p2["queries"]), (
        "two identical plain sweeps disagreed — the slow slice is hashing, "
        "not a coin")
    assert (b1["worst"], b1["clock"], b1["queries"]) == \
        (b2["worst"], b2["clock"], b2["queries"]), (
        "two identical hedged sweeps disagreed")
    assert p1["worst"] == 29, (
        "the plain sweep's worst is %r, not the slow node's 25+4 — the "
        "slice was not fixed or the cost not counted" % p1["worst"])
    assert b1["mean"] < p1["mean"], (
        "mean %.1f ms hedged against %.1f ms plain — hedging did not buy "
        "latency" % (b1["mean"], p1["mean"]))
    assert b1["worst"] <= p1["worst"], (
        "worst latency grew with hedging — a backup may join a reply but "
        "never delay one past the primary it replaced")
    assert b1["queries"] > p1["queries"], (
        "hedged queries %r <= plain %r: backups that cost the origin "
        "nothing are not real backups" % (b1["queries"], p1["queries"]))
    assert b1["queries"] == 600 + b1["client"].backups_sent, (
        "the query ledger must be exactly one read per request plus one "
        "per backup sent: %r vs 600+%r"
        % (b1["queries"], b1["client"].backups_sent))
    b = b1["client"]
    assert b.backups_sent >= 1 and 0 <= b.backups_won <= b.backups_sent, (
        "the sent/won ledger is inverted or empty: sent=%r won=%r"
        % (b.backups_sent, b.backups_won))

    return "tail: fixed slow slice, one win buys one extra origin read, " \
           "mean down on a paid ledger"


# --- stage 6 -----------------------------------------------------------------------
def check_6():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(HERE))

    def _repo(start=None):
        for candidate_start in (os.environ.get("M6_REPO"), start,
                                os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "memcached-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("cannot find the repo: set M6_REPO=/path/to/repo/root")

    def _refuses(exc, what, call):
        try:
            accepted = call()
        except exc as err:
            return str(err)
        raise AssertionError("%s was accepted: %r" % (what, accepted))

    _repo()
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if DEFAULT_REPO not in sys.path:
        sys.path.append(DEFAULT_REPO)

    import world
    import stage_06 as s

    reject = world.CacheError
    assert s.FETCH_COST == 4, (
        "the fetch cost the coin is priced against is the course's fixed "
        "4 ticks: %r" % s.FETCH_COST)

    keys = ["k%d" % i for i in range(25)]
    caches = ["fe-%02d" % i for i in range(40)]
    cheap = {k: 2 for k in keys}
    dear = {k: 100 for k in keys}

    no_w = s.wave(keys, caches, ttl=50, window=0)
    w_cheap = s.wave(keys, caches, ttl=50, window=20, recompute=cheap)
    w_dear = s.wave(keys, caches, ttl=50, window=20, recompute=dear)

    # --- the synchronized death: one column of caches x keys ----------------
    assert no_w["total"] == 2000, (
        "40 caches x 25 keys warm at tick 0 and dead at tick 50 is 2000 "
        "rebuilds, and herding may change nothing here: %r" % no_w)
    assert no_w["spike"] == 1000 and no_w["at_death"] == 1000 \
        and no_w["early"] == 0, (
        "without a window every death-time copy lands in the tick-50 "
        "column: %r" % no_w)
    assert no_w["profile"].get(50) == 1000, (
        "the death column is not on the tick the ttl says: %r"
        % no_w["profile"])

    # --- the coin thins the column and moves nothing else --------------------
    assert w_cheap["total"] == no_w["total"], (
        "herded total %r vs no-window %r — statistical herding RELOCATES "
        "rebuilds; a total that shrank means the coin skipped work, and a "
        "cache that skips rebuilds is stale"
        % (w_cheap["total"], no_w["total"]))
    assert w_cheap["spike"] * 2 < no_w["spike"], (
        "the cheap-rebuild spike is %r against no-window %r — a ramp that "
        "grows with age must thin the death column by more than half; a "
        "fixed offset chosen at store time only MOVES it"
        % (w_cheap["spike"], no_w["spike"]))
    assert w_cheap["early"] + w_cheap["at_death"] == 1000, (
        "early %r + at_death %r must account for all 1000 death-window "
        "decisions" % (w_cheap["early"], w_cheap["at_death"]))

    # --- an expensive rebuild herds LESS; that is the pricing -----------------
    assert w_dear["spike"] > w_cheap["spike"], (
        "expensive rebuilds spiked %r <= cheap %r — the coin prices "
        "itself at FETCH_COST/recompute, so work the backend can least "
        "afford to re-do expires early least"
        % (w_dear["spike"], w_cheap["spike"]))
    assert w_dear["early"] < w_cheap["early"] and \
        w_dear["spike"] < no_w["spike"], (
        "the priced coin is either absent (spike %r) or unpriced (early %r "
        "is not below the cheap coin's)" % (w_dear["spike"], w_dear["early"]))

    # --- determinism: the same wave twice, tick for tick -----------------------
    again = s.wave(keys, caches, ttl=50, window=20, recompute=cheap)
    assert again["profile"] == w_cheap["profile"], (
        "two identical waves produced different per-tick profiles — the "
        "coin moved between runs. stable_hash of (cache, key, tick) is the "
        "only coin this course allows")
    assert again["early"] == w_cheap["early"], "the early counter moved too"

    # --- each frontend decides for itself: the salt IS the spread ---------------
    clock = world.Clock()
    origin = world.Origin({k: (k + "-v", 0) for k in keys})
    shared = s.Herder(["fe-00", "fe-01"], clock, origin, window=20,
                      recompute=cheap)
    for k in keys:
        shared.request("fe-00", k, 50)
        shared.request("fe-01", k, 50)
    clock.advance(45)
    q_before = origin.queries
    early0 = set()
    early1 = set()
    for k in keys:
        before_k = shared.early
        shared.request("fe-00", k, 50)
        if shared.early > before_k:
            early0.add(k)
        before_k = shared.early
        shared.request("fe-01", k, 50)
        if shared.early > before_k:
            early1.add(k)
    assert origin.queries - q_before == len(early0) + len(early1), (
        "every early decision must have rebuilt, and every rebuild came "
        "from a decision: %r queries for %r+%r early"
        % (origin.queries - q_before, len(early0), len(early1)))
    assert 0 < len(early0) + len(early1) < 2 * len(keys), (
        "at tick 45 of a 20-wide window either nothing expired early or "
        "everything did: %r — the ramp is flat"
        % (len(early0) + len(early1),))
    assert early0 != early1, (
        "both frontends expired EXACTLY the same %d keys early — the coin "
        "is not salted with the cache name, so 40 frontends share one "
        "decision and the herd re-forms one tick sooner" % len(early0))

    # --- the guards the ramp needs ------------------------------------------------
    _refuses(reject, "a negative window",
             lambda: s.Herder(["c"], world.Clock(), origin, window=-1))
    _refuses(reject, "a window that is a bool",
             lambda: s.Herder(["c"], world.Clock(), origin, window=True))
    clock = world.Clock()
    o = world.Origin({"k": ("v", 0)})
    bad = s.Herder(["c"], clock, o, window=10, recompute={"k": True})
    bad.request("c", "k", 20)                    # warm at 0, dies at 20
    clock.advance(10)                             # tick 10 = edge of window
    text = _refuses(reject, "a bool recompute cost inside the window",
                    lambda: bad.request("c", "k", 20))
    assert "recompute" in text and "k" in text, (
        "the refusal did not name the cost or the key: %r" % text)
    bad = s.Herder(["c"], clock, o, window=10, recompute={"k": 0})
    bad.request("c", "k", 20)                     # warm at 10, dies at 30
    clock.advance(10)                             # tick 20 = edge again
    _refuses(reject, "a zero recompute cost inside the window",
             lambda: bad.request("c", "k", 20))

    # --- spike() ignores the warm ------------------------------------------------
    clock = world.Clock()
    h = s.Herder(["c"], clock, world.Origin({"k": ("v", 0)}), window=0)
    h.request("c", "k", 20)
    assert h.peak() == 1 and h.spike() == 0, (
        "spike() counted the warm-up column as a herd (peak=%r spike=%r) — "
        "the death neighbourhood starts at tick 1 or every window looks "
        "like a win" % (h.peak(), h.spike()))

    return "herding: 1000-deep death column, ramp-priced coin thins it to " \
           "<half with an identical total"


# --- stage 7 -----------------------------------------------------------------------
def check_7():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(HERE))

    def _repo(start=None):
        for candidate_start in (os.environ.get("M7_REPO"), start,
                                os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "memcached-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("cannot find the repo: set M7_REPO=/path/to/repo/root")

    _repo()
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if DEFAULT_REPO not in sys.path:
        sys.path.append(DEFAULT_REPO)

    import world
    import stage_07 as s

    keys = ["k%d" % i for i in range(20)]
    deep = {k: (k + "v", 30) for k in keys}
    cheap_re = {k: 2 for k in keys}
    zero = {k: (k + "v", 0) for k in keys}

    # --- the depth wave: 10 clients x 20 cold keys, one tick --------------------
    clock = world.Clock()
    origin = world.Origin(deep)
    plain = s.SingleFlight(clock, origin)
    s.cold_wave(plain, keys, 10)
    assert origin.queries == 200 and clock.now == 6000, (
        "an unprotected cold wave paid %r origin queries and %r ticks of "
        "busy — each of 10 clients re-fetched every key: that is the "
        "stampede" % (origin.queries, clock.now))

    clock = world.Clock()
    origin = world.Origin(deep)
    guarded = s.SingleFlight(clock, origin, mutex=True)
    s.cold_wave(guarded, keys, 10)
    assert origin.queries == 20 and clock.now == 600, (
        "a per-key flight must collapse 200 cold fetches to 20 (one per "
        "key): queries=%r busy=%r" % (origin.queries, clock.now))
    assert guarded.waits == 180, (
        "waits %r != 180 — the 19 arrivals after each leader's must join "
        "the flight without querying" % guarded.waits)
    assert guarded.peak(0, 0) == 20, (
        "the tick-0 column is %r, not 20 — the depth win is measured on "
        "the origin's per-tick column, not its total" % guarded.peak(0, 0))

    # --- herding cannot fix depth: the cold wave is the same with a window -----
    clock = world.Clock()
    origin = world.Origin(deep)
    herded = s.SingleFlight(clock, origin, window=10, recompute=cheap_re)
    s.cold_wave(herded, keys, 10)
    assert origin.queries == 200 and clock.now == 6000 and herded.early == 0, (
        "a coin on a COLD wave: queries=%r early=%r — statistical herding "
        "expires ENTRIES early, and a cold key has none. The mutex cannot "
        "thin width, and the coin cannot fold depth"
        % (origin.queries, herded.early))

    # --- a waiter is served the leader's value, and costs nothing --------------
    clock = world.Clock()
    origin = world.Origin({"k": ("value", 10)})
    cache = s.SingleFlight(clock, origin, mutex=True)
    assert cache.request("k", 0, 50) == "value", "the leader's read broke"
    assert cache.request("k", 5, 50) == "value", (
        "tick 5 is inside the leader's in-flight window — a waiter must be "
        "served the leader's value")
    assert origin.queries == 1 and cache.waits == 1 and clock.now == 10, (
        "the waiter queried (%r) or waited wrong (%r) or moved the clock "
        "(%r) — joining a flight is free"
        % (origin.queries, cache.waits, clock.now))

    # --- a late arrival reads the reply; an early one re-fetches without the mutex
    clock = world.Clock()
    origin = world.Origin({"k": ("value", 3)})
    cache = s.SingleFlight(clock, origin, mutex=True)
    cache.request("k", 0, 50)
    assert cache.request("k", 5, 50) == "value" and origin.queries == 1, (
        "tick 5 is past the reply landing at 3 — a late arrival reads the "
        "entry, it is not a wait")
    assert cache.waits == 0, (
        "a served-from-cache hit counted as a wait: %r" % cache.waits)
    clock = world.Clock()
    origin = world.Origin({"k": ("value", 10)})
    cache = s.SingleFlight(clock, origin, mutex=False)
    cache.request("k", 0, 50)
    assert cache.request("k", 5, 50) == "value" and origin.queries == 2, (
        "without the mutex an in-flight arrival must re-fetch — that is "
        "the stampede the mutex exists for: queries=%r" % origin.queries)

    # --- a synchronous write lands on arrival, not on the reply -----------------
    clock = world.Clock()
    origin = world.Origin({"k": ("value", 10)})
    cache = s.SingleFlight(clock, origin, mutex=True)
    cache.store_value("k", "written", 5, 50)
    assert cache.request("k", 6, 50) == "written" and origin.queries == 0, (
        "a write-through is not in flight: an arrival one tick later must "
        "hit it without touching the origin (queries=%r)" % origin.queries)

    # --- the width wave: 10 frontends x 20 keys, copies die together at 50 ------
    origin, cols = s.frontend_wave(False, 0, keys, 10, zero, cheap_re)
    assert origin.queries == 400, (
        "width wave total %r — 200 warm + 200 deaths: herding must move "
        "the column, never thin the total" % origin.queries)
    assert cols.get(50, 0) == 200, (
        "the unprotected death column is %r — 10 frontends x 20 keys all "
        "rebuild on tick 50" % cols)
    origin, cols = s.frontend_wave(True, 0, keys, 10, zero, cheap_re)
    assert cols.get(50, 0) == 200 and origin.queries == 400, (
        "mutex=True left the death column at %r — the flight is per key "
        "per cache, and with one flight per key per cache there is NO "
        "waiter to absorb: width is untouched. The mutex alone loses to "
        "the wide wave" % cols)

    # --- only the coin thins the column, and never changes the total ------------
    origin, hcols = s.frontend_wave(False, 10, keys, 10, zero, cheap_re)
    assert origin.queries == 400, (
        "herding changed the total to %r — production does not need less "
        "work, it needs the work spread over ticks" % origin.queries)
    assert hcols.get(50, 0) == 0, (
        "the death column survived herding: %r" % hcols.get(50, 0))
    assert max(v for t, v in hcols.items() if t > 0 and t != 50) == 45, (
        "the spread peak is %r, not the pinned 45 — the ramp is flat or "
        "the coin is shared between frontends"
        % (max(v for t, v in hcols.items() if t and t != 50),))
    assert sum(hcols.values()) == 400, (
        "the columns do not add up to the total: %r" % hcols)
    origin, mcols = s.frontend_wave(True, 10, keys, 10, zero, cheap_re)
    assert mcols == hcols and origin.queries == 400, (
        "adding the mutex to herding changed the profile — with zero "
        "waiters it must be the byte-for-byte same shape")
    _, again = s.frontend_wave(False, 10, keys, 10, zero, cheap_re)
    assert again == hcols, (
        "two identical width waves disagreed — the coin moved between "
        "runs; stable_hash of (frontend, key, tick) is the only coin")

    return "flight: 200->20 on depth, 180 waits, width column 200 with or " \
           "without the mutex, coin thins it to 0 on an identical total"


# --- stage 8 -----------------------------------------------------------------------
def check_8():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(HERE))

    def _repo(start=None):
        for candidate_start in (os.environ.get("M8_REPO"), start,
                                os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "memcached-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("cannot find the repo: set M8_REPO=/path/to/repo/root")

    def _refuses(exc, what, call):
        try:
            accepted = call()
        except exc as err:
            return str(err)
        raise AssertionError("%s was accepted: %r" % (what, accepted))

    _repo()
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if DEFAULT_REPO not in sys.path:
        sys.path.append(DEFAULT_REPO)

    import world
    import stage_01 as ring_mod
    import stage_03 as store_mod
    import stage_08 as s

    reject = world.CacheError

    def rig(rows):
        clock = world.Clock()
        origin = world.Origin(rows)
        ring = ring_mod.HashRing()
        names = ("n1", "n2", "n3")
        for n in names:
            ring.add_node(n)
        stores = {n: store_mod.LruSlab(s.NODE_SLOTS, 1) for n in names}
        return clock, origin, ring, stores, \
            s.ReplicatedCache(ring, stores, origin, clock, factor=2)

    # --- a set lands on the primary and its successor, and on nobody else ------
    clock, origin, ring, stores, c = rig({"x": ("from-origin", 7)})
    c.set("x", "v", ttl=20)
    assert origin.queries == 0, (
        "a set read the origin %r times — the caller already holds the "
        "value" % origin.queries)
    holders = c._holders("x")
    assert holders == ring.successors("x", 2), (
        "the replicas are not the ring's first %r successors: %r"
        % (2, holders))
    third = [n for n in ("n1", "n2", "n3") if n not in holders][0]
    assert all(stores[n].get("x", 0, mark=False) is not None
               for n in holders), "a holder lost the write: %r" % (holders,)
    assert stores[third].get("x", 0, mark=False) is None, (
        "factor 2 wrote to all three nodes — the third copy is not what "
        "the stage asked for, and it is the reason a crash would be free "
        "for the wrong reason")
    assert [stores[n].get("x", 0, mark=False).exptime for n in holders] \
        == [20, 20], (
        "the copies did not inherit the ttl as an absolute tick: %r"
        % ([stores[n].get("x", 0, mark=False).exptime for n in holders],))

    # --- an expired copy costs one origin read and re-lands on both holders ----
    clock.advance(20)
    assert c.get("x") == "from-origin" and origin.queries == 1 \
        and clock.now == 27, (
        "the expired read answered %r / queries %r / clock %r — a miss "
        "must rebuild once, pay the row's cost, and restock"
        % (c.get("x"), origin.queries, clock.now))
    assert all(stores[n].get("x", 27, mark=False) is not None
               for n in c._holders("x")), (
        "a rebuilt value stayed on one node")

    # --- the crash a plain cache cannot absorb ---------------------------------
    rows = {"k%d" % i: ("v%d" % i, 5) for i in range(90)}
    warm, after, fallbacks = s.failure_report(rows, False)
    assert (warm, after, fallbacks) == (90, 28, 0), (
        "one of three nodes dies and a plain cache costs the origin %r "
        "reads on the recovery sweep (warm %r, fallbacks %r) — that is "
        "the dead node's whole range handed to the backend at once"
        % (after, warm, fallbacks))
    warm, after, fallbacks = s.failure_report(rows, True)
    assert (warm, after) == (90, 0), (
        "replicated, the crash cost %r origin queries — with factor 2 on "
        "3 nodes every key has a live holder, so the answer is ZERO"
        % (after,))
    assert fallbacks == 0, (
        "the replicated recovery counted %r fallback hits — when a node "
        "dies its successor IS re-routed to become the primary, so the "
        "copy is served from holder 0: 'the backup is not insurance; it "
        "is the new primary, already warm'. A nonzero fallback count "
        "means the replica sits on a random peer the ring does not "
        "consult" % fallbacks)

    # --- the warm restart: traffic re-warms the returning node ------------------
    r = s.restart_report(rows)
    assert r["queries_during_crash"] == 0, (
        "the crash itself leaked %r queries" % r["queries_during_crash"])
    assert r["queries_after_restart"] == 0, (
        "the returning node cost the origin %r reads — a warm restart "
        "means the origin never sees the difference"
        % r["queries_after_restart"])
    assert r["backfills"] == 112 and r["fallback_hits"] == 28 \
        and r["items_on_restarted"] == 56, (
        "the restart's shape is wrong: %r — 28 reads rescued by a backup "
        "each refill the empty node, and the other 84 route back to it "
        "where their copies already live" % (r,))
    assert r["items_on_restarted"] == r["backfills"] // 2, (
        "the refilled copies and what the node holds disagree: %r vs %r"
        % (r["items_on_restarted"], r["backfills"]))

    # --- a backfill carries the ORIGINAL exptime, never a fresh permanent one ---
    clock, origin, ring, stores, c = rig({"x": ("from-origin", 0)})
    c.set("x", "v", ttl=100)
    holders = c._holders("x")
    c.crash(holders[0])
    c.restart(holders[0])                  # back in the ring, empty
    assert c.get("x") == "v" and origin.queries == 0, (
        "the read that refilled a restarted holder went to the origin")
    refilled = stores[holders[0]].get("x", 0, mark=False)
    assert refilled is not None and refilled.exptime == 100, (
        "the refill lost the ttl (exptime %r) — a backfill that resets "
        "the expiry silently makes the restarted node the one place data "
        "lives forever" % (refilled and refilled.exptime,))
    clock.advance(100)                     # now >= 100: every copy is dead
    assert c.get("x") == "from-origin" and origin.queries == 1, (
        "a backfilled copy that outlived its ttl: the sweep past tick 100 "
        "answered %r / queries %r" % (c.get("x"), origin.queries))

    # --- the guards the ledger needs ------------------------------------------------
    _refuses(reject, "a replication factor of zero",
             lambda: s.ReplicatedCache(ring, stores, origin, clock, factor=0))
    _refuses(reject, "a replication factor that is a bool",
             lambda: s.ReplicatedCache(ring, stores, origin, clock,
                                       factor=True))
    _refuses(reject, "crashing a node the ring does not know",
             lambda: c.crash("n9"))
    _refuses(reject, "restarting a node that is already up",
             lambda: c.restart("n1"))

    return "replication: factor 2 on 3 nodes makes one death a zero-query " \
           "event, the restart re-warms through reads, refills keep the ttl"


# --- stage 9 -----------------------------------------------------------------------
def check_9():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(HERE))

    def _repo(start=None):
        for candidate_start in (os.environ.get("M9_REPO"), start,
                                os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "memcached-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("cannot find the repo: set M9_REPO=/path/to/repo/root")

    def _refuses(exc, what, call):
        try:
            accepted = call()
        except exc as err:
            return str(err)
        raise AssertionError("%s was accepted: %r" % (what, accepted))

    _repo()
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if DEFAULT_REPO not in sys.path:
        sys.path.append(DEFAULT_REPO)

    import world
    import stage_03 as store_mod
    import stage_09 as s

    reject = world.CacheError

    # --- the demo, reported exactly -------------------------------------------
    slab = s.StatsSlab(store_mod.LruSlab(capacity_per_page=4,
                                         max_pages_per_class=2))
    counters = {"get_hits": 0, "get_misses": 0, "cmd_set": 0, "cmd_get": 0}
    for i in range(6):
        slab.store("k%d" % i, "value-%d" % i, now=0)
        counters["cmd_set"] += 1
    for i in range(10):
        counters["cmd_get"] += 1
        if slab.get("k%d" % (i % 7), 0) is None:
            counters["get_misses"] += 1
        else:
            counters["get_hits"] += 1
    st = s.report(slab, counters, 100)
    assert st == {"uptime": 100, "curr_items": 6, "evictions": 0,
                  "expired_freed": 0, "get_hits": 9, "get_misses": 1,
                  "hit_rate": 0.9, "sets": 6, "pages": 2}, (
        "the report is %r — 6 sets, 10 gets of k0..k6 (k6 is the "
        "deliberate miss: 9 hits, 1 miss, rate 0.9, two pages)" % (st,))
    assert "wasted_bytes" not in st, (
        "a StatsSlab with NO ladder reported wasted_bytes %r — the waste "
        "is only computable when the class ladder is known, and the toy "
        "ladder's answer (0) is a finding, not a default"
        % st.get("wasted_bytes"))

    # --- the ladder changes what can be reported, not what is true --------------
    laddered = s.StatsSlab(store_mod.LruSlab(4, 2), ladder=(8, 16, 32))
    laddered.store("k", "abc", now=0)
    st = s.report(laddered, {"get_hits": 0, "get_misses": 0, "cmd_set": 1,
                             "cmd_get": 0}, 0)
    assert st.get("wasted_bytes") == laddered.wasted(), (
        "with a ladder the report must carry exactly slab.wasted(): %r vs "
        "%r" % (st.get("wasted_bytes"), laddered.wasted()))
    assert st["curr_items"] == 1 and st["sets"] == 1, (
        "the ladder changed the counts it should not: %r" % st)

    # --- a rate is derived, never stored ----------------------------------------
    counters2 = dict(counters)
    counters2["get_hits"] = 18
    counters2["get_misses"] = 2
    counters2["cmd_get"] = 20
    st = s.report(slab, counters2, 100)
    assert st["hit_rate"] == 0.9 and st["get_hits"] == 18, (
        "the rate followed the counters or did not: hits=%r rate=%r — "
        "hit_rate is hits/(hits+misses) RECOMPUTED at report time; the "
        "report that stores a rate copy is the second chance to be wrong"
        % (st["get_hits"], st["hit_rate"]))

    # --- the identity the counters must satisfy ---------------------------------
    for name in ("get_hits", "get_misses", "cmd_get", "cmd_set"):
        broken = dict(counters)
        broken[name] = True
        text = _refuses(reject, "counter %s as a bool" % name,
                        lambda: s.report(slab, broken, 100))
        assert name in text, (
            "the refusal did not name the counter: %r" % text)
        broken = dict(counters)
        broken[name] = -1
        _refuses(reject, "counter %s negative" % name,
                 lambda: s.report(slab, broken, 100))
        broken = dict(counters)
        broken[name] = 1.5
        _refuses(reject, "counter %s a float" % name,
                 lambda: s.report(slab, broken, 100))
    skewed = dict(counters)
    skewed["get_hits"] = 8
    text = _refuses(reject, "hits+misses != cmd_get",
                    lambda: s.report(slab, skewed, 100))
    assert "counts twice" in text or "disagree" in text, (
        "the disagreement message lost its cause: %r — a two-key get "
        "counts TWO keys and that is exactly why the identity holds" % text)
    missing = {"get_hits": 9, "get_misses": 1}
    _refuses(reject, "counters with no cmd_get",
             lambda: s.report(slab, missing, 100))
    for bad_uptime in (True, -1, 1.5, "100"):
        _refuses(reject, "uptime %r" % (bad_uptime,),
                 lambda: s.report(slab, counters, bad_uptime))

    # --- the numbers come from the STORE, not from a counter the store ignores --
    evicting = s.StatsSlab(store_mod.LruSlab(2, 1))
    evicting.store("a", "x", now=1)
    evicting.store("b", "x", now=2)
    evicting.store("c", "x", now=3)            # recycles page 1 wholesale
    st = s.report(evicting, {"get_hits": 0, "get_misses": 0, "cmd_set": 3,
                             "cmd_get": 0}, 0)
    assert st["evictions"] == 2 and st["curr_items"] == 1, (
        "the report read evictions from a counter the store never "
        "consulted: %r — the whole-page recycle killed TWO items and left "
        "only 'c' standing, and the daemon's `evictions` is the store's "
        "number" % st)

    # --- the wrapper refuses the attributes it does not have ---------------------
    text = _refuses(reject, "StatsSlab.uptime()",
                    lambda: slab.uptime)
    assert "uptime" in text, "the refusal did not name the attribute: %r" % text
    assert slab.stats()["live"] == 6, "the wrapper lost the store it wraps"

    return "stats: derived rates, store-sourced evictions, the counts must " \
           "add up, waste only when the ladder is known"


# --- stage 10 ----------------------------------------------------------------------
def check_10():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(HERE))

    def _repo(start=None):
        for candidate_start in (os.environ.get("M10_REPO"), start,
                                os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "memcached-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("cannot find the repo: set M10_REPO=/path/to/repo/root")

    def _refuses(exc, what, call):
        try:
            accepted = call()
        except exc as err:
            return str(err)
        raise AssertionError("%s was accepted: %r" % (what, accepted))

    _repo()
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if DEFAULT_REPO not in sys.path:
        sys.path.append(DEFAULT_REPO)

    import world
    import stage_01 as ring_mod
    import stage_03 as store_mod
    import stage_07 as flight_mod
    import stage_10 as s

    reject = world.CacheError

    # --- the script is validated before anything runs ------------------------
    _refuses(reject, "an empty script", lambda: s.request_script([]))
    _refuses(reject, "a script that is not a list",
             lambda: s.request_script("0|c|get|k"))
    text = _refuses(reject, "a backwards script",
                    lambda: s.request_script([(1, "c", "get", "k"),
                                              (0, "c", "get", "k")]))
    assert "row 1" in text and "backwards" in text, (
        "the refusal did not name the row: %r — a badly-sorted script must "
        "fail with its row number, not mid-run" % text)
    text = _refuses(reject, "a bool tick",
                    lambda: s.request_script([(True, "c", "get", "k")]))
    assert "row 0" in text, "the refusal did not name the row: %r" % text
    _refuses(reject, "a negative tick",
             lambda: s.request_script([(-1, "c", "get", "k")]))
    _refuses(reject, "an unknown op",
             lambda: s.request_script([(0, "c", "flush", "k")]))
    _refuses(reject, "a row of the wrong shape",
             lambda: s.request_script([(0, "c", "get")]))
    _refuses(reject, "a key that is not text",
             lambda: s.request_script([(0, "c", "get", 7)]))
    assert s.request_script([(0, "c", "get", "k"),
                             (0, "c", "set", "k")]) is not None, (
        "a valid script was refused")

    # --- the tier quacks like the origin, even when it holds -----------------
    ring = ring_mod.HashRing()
    for n in ("n1", "n2", "n3"):
        ring.add_node(n)
    clock = world.Clock()
    origin = world.Origin({"k": ("v", 3)})
    stores = {n: store_mod.LruSlab(4096, 1) for n in ("n1", "n2", "n3")}
    tier = s.NodeTier(ring, stores, origin)
    assert tier.cost("k") == 3, "the tier does not price the row"
    assert tier.fetch("k", clock) == "v" and origin.queries == 1, (
        "a cold fetch missed the origin")
    assert stores[ring.route("k")].get("k", 3, mark=False) is not None, (
        "the rebuilt copy was not stored on the routed node — stage 3's "
        "slab is load-bearing here")
    assert tier.cost("k") == 3, (
        "cost() dropped once the node held the copy — the coin prices the "
        "WORST case, the backend the frontend cannot see into")
    assert tier.fetch("k", clock) == "v" and origin.queries == 1, (
        "a warm node still went to the origin: queries=%r" % origin.queries)
    assert tier.node_hits == {ring.route("k"): 1}, (
        "the node-hit ledger is %r — one served copy, one count"
        % (tier.node_hits,))

    # --- the demo script, replayed twice: one byte string ---------------------
    rows = {"k%d" % i: ("v%d" % i, 3) for i in range(20)}
    keys = sorted(rows)
    caches = ["fe-%02d" % i for i in range(4)]
    script = []
    for c in caches:
        for k in keys:
            script.append((0, c, "get", k))
    for t in range(1, 7):
        for c in caches:
            script.append((t, c, "get", "k0"))
    for t in (7, 8):
        for c in caches:
            for k in keys:
                script.append((t, c, "get", k))
    for t in range(10, 16):
        for c in caches:
            for k in keys:
                script.append((t, c, "get", k))
    assert len(script) == 744, (
        "the capstone's script is %d rows, not 744 — every number pinned "
        "below is a function of this exact script" % len(script))
    a = s.run(rows, script, caches, ttl=6, window=2)
    b = s.run(rows, script, caches, ttl=6, window=2)
    assert a == b, (
        "two runs of one script disagreed — the digest check is the whole "
        "point of the course: `hash()`, float time, or a shared coin "
        "between frontends each turns this file into a story")
    assert s.digest(a.encode("utf-8")) == \
        "1a8e93c17be92c60e573add8bbd8cc0a3be0b288d35670860a6905b250abcf06", (
        "the report's sha256 moved: %r — the machine is not the same "
        "machine" % s.digest(a.encode("utf-8"))[:16])
    assert s.run_bytes(rows, script, caches, ttl=6, window=2) == \
        a.encode("utf-8"), "run_bytes is not the encoded run"

    report = json.loads(a)
    assert sorted(report) == ["busy", "caches", "node_hits",
                              "origin_queries"], (
        "the report grew a field the other nine stages do not feed: %r"
        % sorted(report))
    assert report["origin_queries"] == 20 and report["busy"] == 60, (
        "20 keys x 3 ticks of rebuild is 60 ticks of origin busy time, and "
        "the ring's tier means the origin is queried ONCE per key: %r/%r"
        % (report["origin_queries"], report["busy"]))
    assert report["node_hits"] == [["n1", 49], ["n2", 56], ["n3", 35]], (
        "the server tier's ledger moved: %r" % report["node_hits"])
    assert [r[0] for r in report["caches"]] == sorted(caches), (
        "the per-cache rows are not sorted by name: %r" % report["caches"])
    front_queries = [r[3] for r in report["caches"]]
    assert front_queries == [40, 40, 40, 40], (
        "each frontend rebuilds 40 times (20 warm + 20 in the death "
        "sweep): %r" % front_queries)
    assert sum(front_queries) == report["origin_queries"] + \
        sum(v for _, v in report["node_hits"]), (
        "conservation broke: the frontends' %r rebuilds must equal the "
        "origin's %r reads plus the tier's %r served copies — every "
        "rebuild was answered exactly once, somewhere"
        % (sum(front_queries), report["origin_queries"],
           sum(v for _, v in report["node_hits"])))
    assert report["caches"] == [["fe-00", 31, 11, 40],
                                ["fe-01", 35, 7, 40],
                                ["fe-02", 35, 7, 40],
                                ["fe-03", 29, 13, 40]], (
        "the waits/early columns moved: %r — each frontend decides apart, "
        "so the early counts DIFFER while every frontend rebuilds the same "
        "40 times" % report["caches"])

    # --- the encoding is the contract ----------------------------------------
    assert a == json.dumps(json.loads(a), sort_keys=True,
                           separators=(",", ":")), (
        "the canonical form is not sorted-keys-no-spaces: %r" % a[:40])
    text = _refuses(reject, "a float in the report",
                    lambda: s.canonical({"hit_rate": 0.9}))
    assert "hit_rate" in text, "the refusal did not name the field: %r" % text
    assert s.canonical({"a": 1}) == '{"a":1}', "ints and strings pass"

    # --- the write-through lands on arrival ---------------------------------
    sc = [(0, "fe-00", "set", "k0"), (1, "fe-00", "get", "k0")]
    rep = json.loads(s.run(rows, sc, ["fe-00"], ttl=6, window=2))
    assert rep["origin_queries"] == 1 and rep["node_hits"] == \
        [["n1", 0], ["n2", 0], ["n3", 0]], (
        "a set then a get one tick later: %r — the write-through is not "
        "in flight, so the get must be served from the entry and touch "
        "neither the tier nor the origin" % rep)
    _refuses(reject, "a script naming an unknown cache",
             lambda: s.run(rows, [(0, "fe-99", "get", "k0")], caches))
    _refuses(reject, "a script naming an unknown key",
             lambda: s.run(rows, [(0, "fe-00", "get", "nothere")], caches))

    return "capstone: 744 rows replay byte-identical, digest 1a8e93c1, " \
           "160 rebuilds = 20 origin reads + 140 node hits"


STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The ring, and the hash that must not move",
        tags=["hashing", "routing", "data-structures"],
        action="Write `VNODES`, `HashRing.add_node`, `HashRing.remove_node`, "
               "`HashRing.nodes`, `HashRing.positions`, `HashRing.route` and "
               "`HashRing.successors` in stage_01.py: 150 vnode points per "
               "node, sorted clockwise, routing to the first point strictly "
               "past the key's own md5, wrapping to the head.",
        predict="What a 12,000-key sweep costs when each node has one point "
                "instead of 150, and what fraction of the keys change hands "
                "when 1 of 5 nodes is dropped.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="Slab classes, and the size that does not fit",
        tags=["memory", "allocation", "data-structures"],
        action="Write `SLAB_START`, `SLAB_GROWTH`, `SLAB_MAX_ITEM`, "
               "`PAGE_BYTES`, `Slot` and `Slab.class_for`, `Slab.place`, "
               "`Slab.remove`, `Slab.slot_of`, `Slab.live` and `Slab.stats` "
               "in stage_02.py: the smallest class that fits, a hole before "
               "a new page, flat chunk indices that decode back to "
               "(page, index).",
        predict="Where a 100-byte value lands, how many bytes the rounding "
                "wastes, and what `class_for(1048576)` answers on the "
                "default ladder.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="Per-page LRU, and the hot key that dies",
        tags=["lru", "eviction", "data-structures"],
        action="Write `Item`, `Page.full`, `Page.free_slot`, `Page.put`, "
               "`Page.touch`, `Page.drop`, `Page.clear`, `Page.lru_stamp` "
               "and `LruSlab.store`, `LruSlab.get`, `LruSlab.delete`, "
               "`LruSlab.live`, `LruSlab.stats` in stage_03.py: reads move "
               "an item to its page's young end, a full class recycles the "
               "page whose own front is oldest, and an expired read frees "
               "its slot before answering a miss.",
        predict="Whether a key read 100 times survives its page being "
                "recycled, and what one eviction event counts as — pages, "
                "items, or both.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The ASCII protocol, byte-exact",
        tags=["protocol", "parsing", "networking"],
        action="Write `CRLF`, `RELATIVE_BOUNDARY`, `VERSION`, "
               "`absolute_exptime`, `parse` and `Ascii.handle` in "
               "stage_04.py: set/add/replace/cas/get/gets/delete/incr/decr/"
               "touch/version/stats, the data chunk verified before anything "
               "is stored, CAS tokens bumped by every successful mutation, "
               "hits and misses counted per key.",
        predict="What `cas` answers when the token is stale versus when the "
                "key is gone, and what a `get a b` with one present key "
                "does to the hit and miss counters.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="Tail tolerance, paying latency in queries",
        tags=["latency", "hedging", "distributed-systems"],
        action="Write `Server.delay`, `Server.total`, `Server.fetch`, "
               "`PlainClient.get`, `TailClient.get`, `run_plain` and "
               "`run_with_backup` in stage_05.py: a fixed 1-in-10 slow "
               "slice hashed from (node, key), a backup fired at the ring's "
               "successor once the fuse burns, the late reply discarded.",
        predict="What happens to the origin's query count when the client's "
                "mean latency drops — and whether an abandoned backup "
                "request can be cancelled.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="Statistical herding, spread over ticks",
        tags=["expiry", "thundering-herd", "distributed-systems"],
        action="Write `FETCH_COST`, `Herder.request`, `Herder.peak`, "
               "`Herder.spike`, `Herder.stats` and `wave` in stage_06.py: "
               "inside the final `window` ticks each cache rolls "
               "stable_hash of its own name, the key and the tick, "
               "expiring early with probability ramp * (FETCH_COST / "
               "recompute).",
        predict="Whether the death spike gets shorter or merely moves when "
                "every copy of a key is jittered, and which herds LESS: "
                "the cheap-to-rebuild key or the expensive one.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="Single-flight, and why the mutex alone loses to the wide "
              "wave",
        tags=["stampede", "mutex", "distributed-systems"],
        action="Write `SingleFlight.request`, `SingleFlight.store_value`, "
               "`SingleFlight.peak`, `cold_wave`, `frontend_wave` and "
               "`line` in stage_07.py: a leader stores at the reply tick, "
               "so an arrival while the rebuild is in flight either joins "
               "(mutex) or re-fetches; the coin spreads a synchronized "
               "death.",
        predict="What 10 clients x 20 cold keys cost with and without the "
                "mutex — and why the same mutex leaves a synchronized "
                "expiry across 10 frontends completely untouched.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="Backup replication and the warm restart",
        tags=["replication", "failure", "distributed-systems"],
        action="Write `NODE_SLOTS`, `ReplicatedCache.set`, "
               "`ReplicatedCache.get`, `ReplicatedCache.crash`, "
               "`ReplicatedCache.restart`, `failure_report` and "
               "`restart_report` in stage_08.py: every write lands on the "
               "primary and its clockwise successors, a read served "
               "off-holder refills every holder missing it, keeping the "
               "original exptime.",
        predict="How many origin queries the death of 1 of 3 nodes costs a "
                "plain cache versus a replicated one, and what the "
                "restarting node holds by the end of the next full sweep.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The report, and the rates that must be derived",
        tags=["observability", "stats", "reporting"],
        action="Write `report` and `StatsSlab` (`wasted`, `ladder`, "
               "`__getattr__`) in stage_09.py: every number computed from "
               "the counters or the store's own stats(), the identity "
               "hits + misses == cmd_get enforced, wasted_bytes reported "
               "only when the class ladder is known.",
        predict="Why storing `hit_rate` next to its two ints is a bug even "
                "while both are true, and which stat must come from the "
                "store rather than any counter.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The capstone, two runs, one byte string",
        tags=["capstone", "determinism", "replay"],
        action="Write `NODE_SLOTS`, `request_script`, `NodeTier.cost`, "
               "`NodeTier.fetch`, `run`, `canonical`, `run_bytes` and "
               "`digest` in stage_10.py: frontends with a flight and a "
               "coin over a ring of slab stores over one origin, reported "
               "as sorted-keys, no-space, integer-only JSON.",
        predict="Whether two runs of one 744-row script produce the same "
                "bytes, and whether the frontends' rebuilds conserve as "
                "origin reads plus node hits.",
        check=check_10,
    ),
]
