"""Memcached From Scratch — stage 5: tail tolerance, paying latency in queries.

The NSDI'13 paper's first measured client trick: get-with-backup. A client
that expects a reply after its fuse burns asks a SECOND server the same
question and takes whichever answer lands first. The stage builds the
scheduler for it — an integer clock, no threads — and makes the client pay
for the win on the origin's ledger.

DESIGN DECISION — why is the slow slice hashed from (node, key), not a
coin flip?
    The tempting alternative is `random.random() < 0.1` per request. Its
    cost is twice over: first, the course's determinism — a tail you cannot
    replay is a tail you cannot debug; second, the real finding: the paper
    measured the SAME few machines slow over and over, which is exactly why
    waiting longer does not help and asking a neighbour does. A fixed
    1-in-10 slice of (node, key) pairs is the honest model.

DESIGN DECISION — why does the abandoned backup still read the origin?
    The tempting alternative is to count only the winner's query and report
    one read per get. Its cost is the whole point of the stage disappearing:
    a TCP request already on the wire CANNOT be cancelled — the other node
    wakes up, misses, and rebuilds from the backend regardless. The hedge
    buys client-visible latency with origin queries, one extra per backup
    sent, and a client that hides that did not cut the tail, it fudged the
    ledger.

DESIGN DECISION — why does the clock jump to the LOSER's completion?
    The tempting alternative is to stop the timeline at the winner's reply.
    Its cost is that the next request would start "earlier" than the world
    actually is — the loser's query would then land in the past. One shared
    monotonic integer means the sweep's end tick is the origin's true busy
    time; the check pins clock.now == 29 even though the client saw the
    answer at 15.

DESIGN DECISION — why ask the ring's SUCCESSOR instead of any random node?
    The tempting alternative is a random peer. Its cost is that the backup
    does not hold the key — a cold miss every time. The successor is where
    the key lives if the primary is down or rebalanced (stage 1's ring), so
    a hedged get and a failover read the same place.

TODO: implement `Server.__init__`, `delay`, `total`, `fetch`,
`PlainClient.get`, `TailClient.__init__`, `get`, `run_plain`,
`run_with_backup`.
"""

from world import CacheError, stable_hash


class Server:
    """One memcached node answering gets by reading the origin.

    Its service delay is a *fact about the node and key*, not a coin:
    hashing into a band makes a fixed slice of requests slow — the same
    slice in every run.
    """

    FAST = 3
    SLOW = 25

    def __init__(self, name, origin, clock, slow_mod=10, slow_at=(0,)):
        raise NotImplementedError("stage 5: implement Server.__init__()")

    def delay(self, key):
        """SLOW when stable_hash(name + '|' + key) % slow_mod names this
        node-key pair as one of the slow slice; FAST otherwise. Same answer
        on every call — the tail is a property, not a dice roll."""
        raise NotImplementedError("stage 5: implement Server.delay()")

    def total(self, key):
        """Ticks from request to reply on this node: service delay plus the
        origin's rebuild cost."""
        raise NotImplementedError("stage 5: implement Server.total()")

    def fetch(self, key):
        """Answer a get: advance the clock by the delay, then read the
        origin."""
        raise NotImplementedError("stage 5: implement Server.fetch()")


class PlainClient:
    """The control: one request, one node, the full tail in the reply.
    `get(key)` returns (value, waited_ticks, node_name)."""

    def __init__(self, ring, servers):
        raise NotImplementedError("stage 5: implement PlainClient.__init__()")

    def get(self, key):
        raise NotImplementedError("stage 5: implement PlainClient.get()")


class TailClient:
    """Get-with-backup: a reply that would land after `backup_after` ticks
    also asks the successor, fired `backup_after` ticks in, and whichever
    lands first wins. `get(key)` returns (value, waited_ticks, winner_name)
    and the client keeps the `backups_sent` / `backups_won` ledger.

    The clock is the scheduler — there are no threads because every moment
    is arithmetic on one monotonic integer, and the same arithmetic replays
    identically in every run. The abandoned request is NOT cancellable: the
    other node reads the origin anyway, so every backup costs one extra
    origin query."""

    def __init__(self, ring, servers, clock, backup_after=8):
        raise NotImplementedError("stage 5: implement TailClient.__init__()")

    def get(self, key):
        raise NotImplementedError("stage 5: implement TailClient.get()")


def run_plain(ring, rows, keys):
    """One sweep of `keys` through a PlainClient on a fresh clock and
    origin: {"worst", "mean", "clock", "queries", "client"}."""
    raise NotImplementedError("stage 5: implement run_plain()")


def run_with_backup(ring, rows, keys, backup_after=8):
    """The same sweep through a TailClient. `queries` must equal len(keys)
    + backups_sent — every request one read, every hedge one more."""
    raise NotImplementedError("stage 5: implement run_with_backup()")
