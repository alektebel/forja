"""link.py — the in-memory link, PROVIDED COMPLETE.

This is the whole world of this course, and it is deliberately small: a
`Client` scripted with the requests it sends, a `Connection` the server accepts
and answers, and a `Link` that carries bytes between them, one tick at a time,
and **keeps its own log of every move**.

Why the world is provided and the server is not: a server is a policy about who
gets the processor next, and that policy is the subject of all ten stages. The
link is the thing the policy is measured against — its bytes, its ticks, its
drops — so it has to be the same for every model, and it cannot be written by the
model it is grading. Nothing in here calls the server: the server calls the link.

The laws this module keeps, which every stage inherits:

* **Deterministic.** There is no clock but the one handed in, no randomness, no
  threads, no I/O. The only thing that moves a byte is `step()`.
* **No time, no floats.** A duration is a number of ticks; there is not one float
  literal in this file.
* **A shape mismatch raises; a verdict about content is returned.** A client, a
  chunk or a connection the link cannot honour raises `LinkError` naming the
  offender; a short `write` is *data* — that is backpressure, and deferring the
  rest of it is stage 8.
* **The record is the world's.** `log()` hands back copies and `stats()`
  recomputes every number from the log, so a model can be held against the link
  rather than against its own beliefs. That comparison is the capstone.

The four moves a server makes, and the two a client makes:

    listen(conn)        the server is ready for this connection again
    accept()            the oldest client waiting, or None
    read(conn, n)       up to n bytes of the client's current request
    write(conn, data)   bytes the outbox took (a short write is normal)
    close(conn)         the server is done with this connection
    drain(conn)         the client takes its inbox (the link does it on schedule)
"""

#: The most bytes one move carries, in either direction.
MAX_CHUNK = 64

#: How many clients a listener holds before it refuses another.
BACKLOG = 4

#: Bytes a connection's outbox holds before `write` starts refusing.
DEFAULT_OUTBOX = 8

#: Every event the log can carry, and nothing else.
EVENTS = ("accept", "listen", "read", "write", "drop", "drain", "close")

#: The three ways a connection ends: the server closed it, the client dropped it
#: (patience spent), or its client was done and the server closed it last.
CLOSE_CAUSES = ("server", "patience", "client")


class LinkError(ValueError):
    """A client, a connection, a chunk or a move the link refuses."""


def _require_int(value, what, *, minimum=0, maximum=None):
    """The house guard: a bool is not an int, and neither is a string."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise LinkError("%s is an int, not %r" % (what, value))
    if value < minimum:
        raise LinkError("%s is at least %d, not %r" % (what, minimum, value))
    if maximum is not None and value > maximum:
        raise LinkError("%s is at most %d, not %r" % (what, maximum, value))
    return value


def _require_bytes(value, what):
    if not isinstance(value, bytes):
        raise LinkError("%s is bytes, not %r" % (what, value))
    return value


class Client:
    """A scripted client: the requests it sends, how often it reads, how much.

    `requests` are sent one at a time: the next one becomes available when this
    client has drained the reply to the one before it. That is a request/reply
    protocol, which is what a server course needs — pipelining is a different
    subject and a later one.

    `read_every` is the whole of "a slow client": a client that drains its inbox
    every fourth tick is the one that stops a blocking server, and `chunk` is how
    much it takes per drain. `patience` is how many ticks it waits for a reply
    after its request has been fully handed over before it drops the link;
    `patience=0` means it waits as long as it takes.
    """

    def __init__(self, name, requests, *, read_every=1, chunk=MAX_CHUNK,
                 patience=0):
        if not isinstance(name, str) or not name:
            raise LinkError("a client's name is a non-empty string, not %r"
                            % (name,))
        if not isinstance(requests, (tuple, list)) or not requests:
            raise LinkError("%s's requests are a non-empty sequence, not %r"
                            % (name, requests))
        for request in requests:
            _require_bytes(request, "%s's request" % (name,))
            if not request:
                raise LinkError("%s sends an empty request" % (name,))
        self.name = name
        self.requests = tuple(requests)
        self.read_every = _require_int(read_every, "%s's read_every" % (name,),
                                       minimum=1)
        self.chunk = _require_int(chunk, "%s's chunk" % (name,), minimum=1,
                                  maximum=MAX_CHUNK)
        self.patience = _require_int(patience, "%s's patience" % (name,))

    def __repr__(self):
        return "Client(%s, %d request(s), read_every=%d, chunk=%d)" % (
            self.name, len(self.requests), self.read_every, self.chunk)


class Connection:
    """One client, one id, and the bytes in flight in both directions.

    The world tracks five things a server must not confuse: `inbox` (the reply
    bytes that have reached the client and not been drained), `outbox` (the
    reply bytes the server queued that the link has not carried yet), `sent`
    (how much of the client's current request has been handed over), `owed`
    (whether a request is waiting for its first reply byte), and `closed`.
    Reading them is fine; a stage that writes them is a stage that has stopped
    using the link and started guessing at it.
    """

    def __init__(self, cid, client, arrival):
        self.id = cid
        self.client = client
        self.arrival = arrival
        self.link = None            # bound by `Link`, so a move can refuse a stranger
        self.inbox = b""
        self.outbox = b""
        self.pending = b""          # the current request, handed over so far
        self.sent = 0               # bytes of the current request handed over
        self.request = 0            # which request of the client is in flight
        self.owed = False           # the request is in, the reply has not started
        self.used = 0               # bytes of the current request handed over (total)
        self.requests_done = 0      # requests the server has answered
        self.closed = False
        self.cause = None           # one of CLOSE_CAUSES once closed
        self.waited = 0             # ticks since the request was fully sent
        self.listened = False       # the server is ready for this connection

    def current(self):
        """The client's current request, or `b""` when there is none."""
        if self.request >= len(self.client.requests):
            return b""
        return self.client.requests[self.request]

    def __repr__(self):
        return "Connection(%d, %s, closed=%s)" % (self.id, self.client.name,
                                                 self.closed)


class Link:
    """The world: clients, connections, readiness, bytes, and its own log.

    `seed` staggers the arrivals by that many ticks (client *i* becomes readable
    at tick `i * seed`), which is how a check builds a busy listener without a
    clock to make it busy. `seed=0` — the default — has everyone arrive at once.
    """

    def __init__(self, clients, *, outbox=DEFAULT_OUTBOX, clock=None, seed=0):
        if not isinstance(clients, (tuple, list)) or not clients:
            raise LinkError("clients is a non-empty sequence, not %r" % (clients,))
        for client in clients:
            if not isinstance(client, Client):
                raise LinkError("a client is a Client, not %r" % (client,))
        names = [client.name for client in clients]
        if len(set(names)) != len(names):
            raise LinkError("two clients share a name: %r" % (names,))
        self.outbox_limit = _require_int(outbox, "outbox", minimum=1)
        self.seed = _require_int(seed, "seed")
        self.clock = clock if clock is not None else _Clock()
        self._log = []
        self._clients = tuple(clients)
        self._conns = {}
        self._backlog = []
        self._next_id = 1
        for index, client in enumerate(self._clients):
            cid = self._next_id
            self._next_id += 1
            conn = Connection(cid, client, index * self.seed)
            conn.link = self
            self._conns[cid] = conn
            self._backlog.append(cid)

    # ---- the record ------------------------------------------------------

    def now(self):
        """The clock's reading."""
        return self.clock.now()

    def _event(self, kind, conn, n=0, cause=None):
        entry = {"tick": self.clock.now(), "event": kind, "id": conn.id,
                 "byte_count": n, "event_count": len(self._log) + 1}
        self._log.append(entry)

    def log(self):
        """Every event so far, oldest first, as copies the caller cannot edit."""
        return tuple(dict(entry) for entry in self._log)

    def events(self, kind=None):
        """The log filtered by event name — `events("write")` — as copies."""
        if kind is not None and kind not in EVENTS:
            raise LinkError("no such event %r; the log carries %r"
                            % (kind, list(EVENTS)))
        return tuple(dict(entry) for entry in self._log
                     if kind is None or entry["event"] == kind)

    def stats(self):
        """The tie-breaker numbers, every one of them recomputed from the log."""
        counts = {kind: 0 for kind in EVENTS}
        moved = {kind: 0 for kind in EVENTS}
        for entry in self._log:
            counts[entry["event"]] += 1
            moved[entry["event"]] += entry["byte_count"]
        return {"ticks": self.clock.now(),
                "events": len(self._log),
                "accepted": counts["accept"],
                "listened": counts["listen"],
                "read_calls": counts["read"],
                "write_calls": counts["write"],
                "drops": counts["drop"],
                "drains": counts["drain"],
                "closes": counts["close"],
                "bytes_read": moved["read"],
                "bytes_written": moved["write"],
                "bytes_dropped": moved["drop"],
                "bytes_drained": moved["drain"]}

    def __repr__(self):
        return "Link(%d client(s), now=%d, events=%d)" % (
            len(self._clients), self.clock.now(), len(self._log))

    # ---- the backlog -----------------------------------------------------

    def connection(self, cid):
        """The connection with that id, or None when the link never made it."""
        return self._conns.get(cid)

    def conns(self):
        """Every connection, in accept order, as a fresh tuple."""
        return tuple(self._conns[cid] for cid in sorted(self._conns))

    def waiting(self):
        """The clients the listener holds, oldest first, as a fresh tuple."""
        return tuple(self._backlog)

    def accept(self):
        """The oldest client waiting, or None when nobody is waiting.

        A client is waiting when it has arrived (its `arrival` tick has come) and
        the server has not accepted it yet. Accepting it is a move the log keeps.
        """
        for cid in list(self._backlog):
            conn = self._conns[cid]
            if conn.arrival <= self.clock.now():
                self._backlog.remove(cid)
                conn.listened = False
                self._event("accept", conn)
                return conn
        return None

    def listen(self, conn):
        """The server is ready for this connection again; the client may send on."""
        self._check(conn)
        if len(self._backlog) >= BACKLOG and conn.id not in self._backlog:
            raise LinkError("the backlog holds %d; %r cannot be listened to yet"
                            % (BACKLOG, conn.id))
        if conn.id not in self._backlog:
            self._backlog.append(conn.id)
        conn.listened = True
        self._event("listen", conn)

    # ---- readiness -------------------------------------------------------

    def _check(self, conn):
        if not isinstance(conn, Connection):
            raise LinkError("a connection is a Connection, not %r" % (conn,))
        if conn.link is not self or conn.id not in self._conns:
            raise LinkError("connection %r is not this link's" % (conn.id,))
        return conn

    def readable(self, conn):
        """The connection has request bytes the server has not taken yet."""
        self._check(conn)
        if conn.closed or conn.arrival > self.clock.now():
            return False
        return conn.sent < len(conn.current())

    def writable(self, conn):
        """The outbox has room for at least one byte."""
        self._check(conn)
        if conn.closed:
            return False
        return len(conn.outbox) < self.outbox_limit

    def idle(self, conn):
        """Nothing to read, nothing owed, nothing on the way: the server's move."""
        self._check(conn)
        return not self.readable(conn) and not conn.owed and not conn.outbox

    def owed(self, conn):
        """The request is in and the reply has not started: the server owes one."""
        self._check(conn)
        return conn.owed

    def drainable(self, conn):
        """The client has reply bytes to take, on its own schedule."""
        self._check(conn)
        return bool(conn.inbox) and not conn.closed

    # ---- the server's moves ----------------------------------------------

    def read(self, conn, n=MAX_CHUNK):
        """Up to `n` bytes of the client's current request; `b""` when none.

        Reading a closed connection raises: a server that reads a closed socket
        is a server that lost track of its own state, which is stage 1's subject.
        """
        self._check(conn)
        _require_int(n, "read(n): n", minimum=1, maximum=MAX_CHUNK)
        if conn.closed:
            raise LinkError("connection %d is closed: nothing to read" % conn.id)
        request = conn.current()
        if conn.sent >= len(request):
            return b""
        take = request[conn.sent:conn.sent + n]
        conn.sent += len(take)
        conn.used += len(take)
        if conn.sent >= len(request):
            conn.owed = True
            conn.waited = 0
        self._event("read", conn, len(take))
        return take

    def write(self, conn, data):
        """The bytes the outbox took; the rest is the caller's to keep.

        A return value smaller than `len(data)` is not an error: the outbox is
        bounded, and a short write is what backpressure *is*. A zero return is
        recorded as a `drop`, so the log says when the server queued bytes that
        did not fit.
        """
        self._check(conn)
        _require_bytes(data, "write(data): data")
        if conn.closed:
            raise LinkError("connection %d is closed: nothing to write" % conn.id)
        room = self.outbox_limit - len(conn.outbox)
        take = data[:room]
        if take:
            conn.outbox += take
            conn.owed = False
            self._event("write", conn, len(take))
        else:
            self._event("drop", conn, len(data))
        return len(take)

    def close(self, conn, *, cause="server"):
        """The server is done with this connection. Closing twice changes nothing."""
        self._check(conn)
        if cause not in CLOSE_CAUSES:
            raise LinkError("a close cause is one of %r, not %r"
                            % (list(CLOSE_CAUSES), cause))
        if conn.closed:
            return False
        conn.closed = True
        conn.cause = cause
        if conn.id in self._backlog:
            self._backlog.remove(conn.id)
        self._event("close", conn)
        return True

    def drain(self, conn):
        """The client takes its inbox, up to its chunk. Returns how many bytes."""
        self._check(conn)
        if conn.closed or not conn.inbox:
            return 0
        client = conn.client
        take = conn.inbox[:client.chunk]
        conn.inbox = conn.inbox[len(take):]
        self._event("drain", conn, len(take))
        self._advance(conn)
        return len(take)

    # ---- the tick --------------------------------------------------------

    def step(self, n=1):
        """Advance `n` ticks: the only thing in this world that moves a byte.

        Each tick, in this order: every connection carries up to `MAX_CHUNK`
        bytes of its outbox into its client's inbox; every client whose
        `read_every` divides the tick drains what it can; and a client whose
        `patience` is spent drops the link. Nothing else happens, and nothing
        happens between ticks.
        """
        _require_int(n, "step(n): n", minimum=1)
        for _ in range(n):
            tick = self.clock.tick()
            for cid in sorted(self._conns):
                conn = self._conns[cid]
                if conn.closed:
                    continue
                if conn.outbox:
                    take = conn.outbox[:MAX_CHUNK]
                    conn.outbox = conn.outbox[len(take):]
                    conn.inbox += take
                if conn.arrival > tick:
                    continue
                if tick % conn.client.read_every == 0:
                    self.drain(conn)
                self._patience(conn)
        return self.clock.now()

    def _patience(self, conn):
        """A client that waited too long for its reply drops the link."""
        if conn.closed or not conn.owed:
            if not conn.closed:
                conn.waited = 0
            return
        client = conn.client
        if not client.patience:
            return
        conn.waited += 1
        if conn.waited > client.patience:
            self.close(conn, cause="patience")

    def _advance(self, conn):
        """A drained request moves the client to its next one, once the reply is in."""
        if conn.closed or conn.owed or conn.outbox or conn.inbox:
            return
        if conn.request >= len(conn.client.requests) - 1:
            return
        if conn.sent >= len(conn.current()) and conn.sent:
            conn.request += 1
            conn.sent = 0
            conn.used = 0
            conn.requests_done += 1
            conn.listened = False
            self._event("read", conn, 0)

    def done(self):
        """Every client answered and drained, or dropped: the run is over.

        A client is finished when nothing is in flight either way and it has no
        request bytes left to hand over. A client that is merely *between* its
        requests is not finished: its next request is readable the moment the
        server listens for it again.
        """
        for cid in sorted(self._conns):
            conn = self._conns[cid]
            if conn.closed:
                continue
            if conn.inbox or conn.outbox or conn.owed:
                return False
            if conn.sent < len(conn.current()):
                return False
        return True

    def __len__(self):
        return len(self._clients)


class _Clock:
    """A counter, not a wall clock: J1's `fleet.Clock`, without the import.

    The course's own clock is `fleet.Clock`, and `verify_provided.py` checks this
    one behaves the same way. It exists so `link.py` can be read on its own.
    """

    def __init__(self, start=0):
        self.value = _require_int(start, "clock start")
        self.ticks = 0

    def now(self):
        return self.value

    def tick(self, n=1):
        _require_int(n, "tick(n): n")
        self.value += n
        self.ticks += n
        return self.value

    def __repr__(self):
        return "Clock(now=%d, ticks=%d)" % (self.value, self.ticks)
