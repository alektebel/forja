"""Memcached From Scratch — stage 5: tail tolerance, paying latency in queries.

The finished implementation. The reasoning — why the backup goes to the
ring's *successor* and not a random node, why the late reply is discarded
instead of merged, why an injected clock makes a race provable without
threads, and what the extra origin queries cost — lives in the DESIGN
DECISION blocks of `stage_05.py`.
"""

from world import CacheError, stable_hash


class Server:
    """One memcached node answering gets by reading the origin.

    Its service delay is a *fact about the node and key*, not a coin:
    hashing into a band makes a fixed slice of requests slow — the same
    slice in every run. That is what the real tail looked like at Facebook:
    the same few machines were slow over and over, which is exactly why
    waiting longer does not help and asking a neighbour does.
    """

    FAST = 3
    SLOW = 25

    def __init__(self, name, origin, clock, slow_mod=10, slow_at=(0,)):
        self.name = name
        self.origin = origin
        self.clock = clock
        self._slow_mod = slow_mod
        self._slow_at = tuple(slow_at)
        self.served = 0

    def delay(self, key):
        bucket = stable_hash(self.name + "|" + key) % self._slow_mod
        return self.SLOW if bucket in self._slow_at else self.FAST

    def total(self, key):
        """Ticks from request to reply on this node: service plus the
        origin's own rebuild cost."""
        return self.delay(key) + self.origin.cost(key)

    def fetch(self, key):
        """Answer a get: pay the service delay, then read the origin."""
        self.served += 1
        self.clock.advance(self.delay(key))
        return self.origin.fetch(key, self.clock)


class PlainClient:
    """The control: one request, one node, the full tail in the reply."""

    def __init__(self, ring, servers):
        self._ring = ring
        self._servers = servers

    def get(self, key):
        server = self._servers[self._ring.route(key)]
        start = server.clock.now
        value = server.fetch(key)
        return value, server.clock.now - start, server.name


class TailClient:
    """Get-with-backup: a reply that would land after `backup_after` ticks
    also asks the successor, fired `backup_after` ticks in, and whichever
    lands first wins. The clock is the scheduler — there are no threads
    because every moment is arithmetic on one monotonic integer, and the
    same arithmetic replays identically in every run.

    The abandoned request is NOT cancellable: the other node reads the
    origin anyway, so every backup costs one extra origin query. Queries go
    up while client-visible latency goes down. That trade is the stage; a
    client that hides it did not cut the tail, it fudged the ledger.
    """

    def __init__(self, ring, servers, clock, backup_after=8):
        self._ring = ring
        self._servers = servers
        self._clock = clock
        self._backup_after = backup_after
        self.backups_sent = 0
        self.backups_won = 0

    def get(self, key):
        start = self._clock.now
        primary = self._servers[self._ring.route(key)]
        primary_done = start + primary.total(key)
        names = self._ring.successors(key, 2)
        if len(names) < 2 or primary_done <= start + self._backup_after:
            value = primary.fetch(key)       # fast path, or nowhere to back up
            return value, self._clock.now - start, primary.name
        backup = self._servers[names[1]]
        backup_done = start + self._backup_after + backup.total(key)
        self.backups_sent += 1
        if backup_done < primary_done:
            winner, loser, loser_done = backup, primary, primary_done
            self.backups_won += 1
        else:
            winner, loser, loser_done = primary, backup, backup_done
        # Fire the winner at its moment on the one shared clock.
        if winner is backup:
            self._clock.advance(self._backup_after)
        value = winner.fetch(key)
        waited = self._clock.now - start
        # The abandoned request still completes on its node and still reads
        # the origin: move to that moment, pay that query, drop the reply.
        loser_read = loser_done - loser.origin.cost(key)
        if loser_read > self._clock.now:
            self._clock.advance(loser_read - self._clock.now)
        loser.origin.fetch(key, self._clock)
        if loser_done > self._clock.now:
            self._clock.advance(loser_done - self._clock.now)
        return value, waited, winner.name


def _sweep(ring, rows, keys, client_factory):
    from world import Clock, Origin
    origin = Origin(rows)
    clock = Clock()
    servers = {n: Server(n, origin, clock) for n in sorted(ring.nodes())}
    client = client_factory(ring, servers, clock)
    worst = waited_total = 0
    for k in keys:
        _, waited, _ = client.get(k)
        worst = max(worst, waited)
        waited_total += waited
    return {"worst": worst,
            "mean": waited_total / len(keys),
            "clock": clock.now,
            "queries": origin.queries,
            "client": client}


def run_plain(ring, rows, keys):
    """The same sweep with no backup — the tail the backup exists to cut."""
    return _sweep(ring, rows, keys,
                  lambda r, s, c: PlainClient(r, s))


def run_with_backup(ring, rows, keys, backup_after=8):
    """One sweep through a TailClient on a fresh clock and origin."""
    return _sweep(ring, rows, keys,
                  lambda r, s, c: TailClient(r, s, c, backup_after))


if __name__ == "__main__":
    from stage_01 import HashRing

    rows = {"k%d" % i: ("v%d" % i, 4) for i in range(600)}
    keys = sorted(rows)

    ring = HashRing()
    for n in ("a", "b", "c"):
        ring.add_node(n)
    p = run_plain(ring, rows, keys)
    b = run_with_backup(ring, rows, keys, backup_after=8)
    print("plain:    worst %dms, mean %.1fms, origin queries %d"
          % (p["worst"], p["mean"], p["queries"]))
    print("tailcut:  worst %dms, mean %.1fms, origin queries %d "
          "(%d backups sent, %d won)"
          % (b["worst"], b["mean"], b["queries"],
             b["client"].backups_sent, b["client"].backups_won))
