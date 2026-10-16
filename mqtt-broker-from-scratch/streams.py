"""MQTT Broker From Scratch — the streams.

The world this course is handed: a transport of named, byte-oriented streams, a
clock that moves only when a caller moves it, and one ordered log that every
claim about a run can be held against. Nothing here knows what an MQTT packet is
and nothing here parses anything: the frame format is the course's own, and a
transport that framed for it would be providing the interesting half.

DESIGN DECISION — why is a stream a byte pipe rather than a message link?
Because MQTT is a byte protocol. A packet's remaining length is written into the
stream after its first byte, so a reader cannot know where a packet ends until it
has parsed that length, and the two failures worth teaching — a length split
across two arrivals, and two packets that arrive in one — cannot even be
expressed on a link that delivers whole messages. The world of
`tcp-ip-from-scratch` carries whole frames of unparsed bytes and says so; this
file is the layer above that course, where the bytes have become a stream that
may stop anywhere.

DESIGN DECISION — why does `send` return a count instead of raising?
Because a full outbox is not an error, it is backpressure. A broker that hands
the transport a 300-byte packet and gets 16 back has learned exactly what this
tick can carry, and it is the broker's own business to keep the remaining 284
bytes somewhere and try again — which is the state a real server keeps per
connection, and whose bug (forgetting the tail, or believing all 300 went) lives
until a client compares two payloads. A transport that took everything and
dropped the excess would be lying about its own name.

DESIGN DECISION — why is time a `step`, and why do the counters live here?
Because the course's claim is that a broker's honesty can be measured, and a wall
clock measures nothing: two runs of one scenario have to be the same bytes. So
time is an integer this module owns — `step(ticks)` moves it and carries one
`chunk` in each direction of every open stream — and the record of what actually
moved is kept here, in `log()` and `stats()`, recomputed from the same events
that carried the bytes. A broker that reports a delivery the transport never made
is caught by comparing the two, and that comparison means something only because
the two accounts are not the same code.

DESIGN DECISION — why can a stream be *cut* as well as closed, and why may a
stream with bytes in it not be closed at all?
Because a will is owed to a client that did not say goodbye. `close()` is an end
both sides agreed to and it refuses to happen while bytes are still in flight —
queued, carried or waiting to be taken — since an agreed end means both ends read
everything the other sent, and a client that never drained its side is the
failure this refusal names. `cut()` is the other end: nobody agreed, the peer is
gone, whatever was in flight is lost, and the loss is counted in the log rather
than quietly forgotten. A broker that only knew `close()` could not tell a client
that left politely from one that vanished, and its will would fire for both or
for neither.

The rules this module keeps, written down because they are load-bearing: every
refusal is a `StreamsError` naming the offender (the stream, the name, the count,
the byte string); `log()` and `events()` hand back copies; `to_server()`,
`to_client()` and `waiting()` are the only ways to see what arrived, and the two
`to_*` calls consume what they hand back.
"""

CHUNK = 16
BACKLOG = 4

OPEN = "open"
CLOSED = "closed"
CUT = "cut"

STATES = (OPEN, CLOSED, CUT)

EVENTS = ("listen", "connect", "accept", "send", "deliver", "close", "cut", "drop")


class StreamsError(ValueError):
    """A rule this transport cannot honour, named as the rule that is wrong."""


def _count(value, what, low=0, high=None):
    """A non-negative int in range, or a refusal naming what arrived instead."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise StreamsError("%s must be an int, not %s"
                           % (what, type(value).__name__))
    if value < low or (high is not None and value > high):
        raise StreamsError("%s must be %s, not %d"
                           % (what, "at least %d" % (low,) if high is None
                              else "%d to %d" % (low, high), value))
    return value


def _bytes_of(data, what):
    """The bytes themselves, or a refusal naming the type that arrived."""
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    raise StreamsError("%s must be bytes, not %s" % (what, type(data).__name__))


def _name(value, what):
    """A non-empty name, or a refusal naming what arrived instead."""
    if not isinstance(value, str) or not value:
        raise StreamsError("%s must be a non-empty name, not %r" % (what, value))
    return value


class Stream:
    """One connection between two names, as four buffers and a state.

    Public attributes: `id` (a small int, unique on its transport), `client` and
    `server` (the two names) and `state`, one of `STATES` — `open` only until
    somebody ends it. The buffers are the transport's business: a stage reads
    them with `to_server()` and `to_client()` and never pokes at them, which is
    what keeps `stats()` an independent account rather than a mirror.
    """

    def __init__(self, ident, client, server):
        self.id = ident
        self.client = client
        self.server = server
        self.state = OPEN
        self._queued_client = bytearray()
        self._queued_server = bytearray()
        self._arrived_server = bytearray()
        self._arrived_client = bytearray()
        self._taken_server = 0
        self._taken_client = 0

    def __repr__(self):
        return "<Stream %d %s->%s %s>" % (self.id, self.client, self.server,
                                          self.state)


class Transport:
    """The world: listeners, streams, a clock, and one log of all of it."""

    def __init__(self, rules=None):
        rules = dict(rules or {})
        for key in rules:
            if key not in ("chunk", "backlog"):
                raise StreamsError("no such rule as %r (the rules are chunk and "
                                   "backlog)" % (key,))
        self._chunk = _count(rules.get("chunk", CHUNK), "the rule 'chunk'", 1)
        self._backlog = _count(rules.get("backlog", BACKLOG), "the rule 'backlog'", 1)
        self._rules = {"chunk": self._chunk, "backlog": self._backlog}
        self._now = 0
        self._steps = 0
        self._listeners = {}
        self._streams = {}
        self._next = 1
        self._log = []

    # ---- the clock ---------------------------------------------------------

    def tick(self):
        """The current tick. Time passes only when a caller advances it."""
        return self._now

    def step(self, ticks=1):
        """Move the clock `ticks` forward, carry what fits, and return the tick.

        Each single step carries at most one `chunk` in each direction of every
        open stream, client to server first. `step(0)` is legal and carries
        nothing; a negative count is refused.
        """
        _count(ticks, "a number of ticks")
        for _ in range(ticks):
            self._now += 1
            self._steps += 1
            for stream in list(self._streams.values()):
                if stream.state == OPEN:
                    self._carry(stream)
        return self._now

    def steps(self):
        """How many single steps this transport has been moved by."""
        return self._steps

    # ---- listeners and streams ---------------------------------------------

    def listen(self, name, backlog=None):
        """Register `name` as somewhere a client may connect, and answer the name."""
        name = _name(name, "a listener's name")
        if name in self._listeners:
            raise StreamsError("a listener already answers to %r" % (name,))
        self._listeners[name] = _count(
            backlog if backlog is not None else self._backlog, "a backlog", 1)
        self._event("listen", None, name=name, backlog=self._listeners[name])
        return name

    def listeners(self):
        """The names that answer, in the order they started answering."""
        return tuple(self._listeners)

    def connect(self, client, to):
        """Open a stream from `client` to the listener `to`, and answer the stream."""
        client = _name(client, "a client's name")
        to = _name(to, "a listener's name")
        if to not in self._listeners:
            raise StreamsError("nothing listens as %r (the listeners are %r)"
                               % (to, sorted(self._listeners)))
        waiting = sum(1 for stream in self._streams.values()
                      if stream.server == to and stream.state == OPEN)
        if waiting >= self._listeners[to]:
            raise StreamsError("the backlog of %r holds %d and %d are waiting"
                               % (to, self._listeners[to], waiting))
        stream = Stream(self._next, client, to)
        self._next += 1
        self._streams[stream.id] = stream
        self._event("connect", stream)
        self._event("accept", stream)
        return stream

    def streams(self):
        """Every stream this transport has opened, in the order it made them."""
        return tuple(self._streams[key] for key in sorted(self._streams))

    def open_streams(self):
        """The streams nobody has ended yet, in the order they were connected."""
        return tuple(stream for stream in self.streams() if stream.state == OPEN)

    def stream(self, ident):
        """The stream with this id (or this `Stream`), or a refusal naming the id."""
        if isinstance(ident, Stream):
            return self.stream(ident.id)
        if isinstance(ident, bool) or not isinstance(ident, int):
            raise StreamsError("a stream id must be an int, not %s"
                               % (type(ident).__name__,))
        if ident not in self._streams:
            raise StreamsError("no stream %d (the streams are %r)"
                               % (ident, sorted(self._streams)))
        return self._streams[ident]

    # ---- bytes: the client's direction -------------------------------------

    def send(self, stream, data):
        """The client's bytes towards the server, and how many of them were taken.

        What does not fit stays in the caller's hands: nothing is ever queued
        beyond the outbox's own room, so a short answer is the truth about this
        tick. The transport never drops what it took; it only takes what it can
        carry next step.
        """
        stream = self.stream(stream)
        if stream.state != OPEN:
            raise StreamsError("stream %d is %s and carries nothing"
                               % (stream.id, stream.state))
        data = _bytes_of(data, "the bytes a stream carries")
        room = self._chunk - len(stream._queued_client)
        taken = min(room, len(data))
        if taken:
            stream._queued_client += data[:taken]
            self._event("send", stream, side="server", count=taken)
        return taken

    def to_server(self, stream):
        """Everything the client's bytes have become at the server, and take it."""
        stream = self.stream(stream)
        arrived = bytes(stream._arrived_server)
        stream._arrived_server.clear()
        if arrived:
            stream._taken_server += len(arrived)
        return arrived

    # ---- bytes: the server's direction -------------------------------------

    def answer(self, stream, data):
        """The server's bytes towards the client, and how many of them were taken.

        The same contract as `send`, in the other direction: a short answer is
        backpressure, and the tail is the broker's to hold or lose.
        """
        stream = self.stream(stream)
        if stream.state != OPEN:
            raise StreamsError("stream %d is %s and carries nothing"
                               % (stream.id, stream.state))
        data = _bytes_of(data, "the bytes a stream carries")
        room = self._chunk - len(stream._queued_server)
        taken = min(room, len(data))
        if taken:
            stream._queued_server += data[:taken]
            self._event("send", stream, side="client", count=taken)
        return taken

    def to_client(self, stream):
        """Everything the server's bytes have become at the client, and take it."""
        stream = self.stream(stream)
        arrived = bytes(stream._arrived_client)
        stream._arrived_client.clear()
        if arrived:
            stream._taken_client += len(arrived)
        return arrived

    def waiting(self, stream):
        """The bytes in flight for each end, as `(to_server, to_client)`.

        A read: what has been queued or carried and not yet taken, in both
        directions, without taking any of it.
        """
        stream = self.stream(stream)
        return (len(stream._queued_client) + len(stream._arrived_server),
                len(stream._queued_server) + len(stream._arrived_client))

    def waiting_at(self, stream, end):
        """The bytes in flight for one end: `"server"` or `"client"`."""
        if end not in ("server", "client"):
            raise StreamsError("an end is 'server' or 'client', not %r" % (end,))
        queued, arrived = self.waiting(stream)
        return queued if end == "server" else arrived

    # ---- endings -----------------------------------------------------------

    def close(self, stream):
        """End a stream both sides agreed to; refuses while bytes are in flight.

        An agreed end means both ends read everything the other sent. A stream
        with bytes queued, carried or waiting to be taken is refused by name,
        because closing it would leave somebody's bytes in a buffer nobody will
        ever read.
        """
        stream = self.stream(stream)
        if stream.state != OPEN:
            raise StreamsError("stream %d is already %s" % (stream.id, stream.state))
        queued = len(stream._queued_client) + len(stream._queued_server)
        arrived = len(stream._arrived_server) + len(stream._arrived_client)
        if queued or arrived:
            raise StreamsError("stream %d still holds %d bytes in flight (%d "
                               "queued, %d arrived and untaken)"
                               % (stream.id, queued + arrived, queued, arrived))
        stream.state = CLOSED
        self._event("close", stream)
        return stream

    def cut(self, stream, reason="the peer is gone"):
        """End a stream nobody agreed to: what was in flight is lost and counted."""
        stream = self.stream(stream)
        if stream.state != OPEN:
            raise StreamsError("stream %d is already %s" % (stream.id, stream.state))
        _name(reason, "the reason a stream was cut")
        lost = (len(stream._queued_client) + len(stream._queued_server)
                + len(stream._arrived_server) + len(stream._arrived_client))
        stream.state = CUT
        self._event("cut", stream, reason=reason, lost=lost)
        if lost:
            self._event("drop", stream, count=lost)
        return stream

    # ---- the record --------------------------------------------------------

    def log(self):
        """Every event this transport saw, in order: copies, not a live view."""
        return [dict(record) for record in self._log]

    def events(self, event):
        """One kind of event, in order."""
        if event not in EVENTS:
            raise StreamsError("no such event as %r (the events are %r)"
                               % (event, EVENTS))
        return [dict(record) for record in self._log if record["event"] == event]

    def stats(self):
        """The counts, recomputed from the log rather than accumulated beside it."""
        counts = {event: 0 for event in EVENTS}
        for record in self._log:
            counts[record["event"]] += 1
        return {
            "ticks": self._now,
            "steps": self._steps,
            "listeners": len(self._listeners),
            "streams": len(self._streams),
            "connects": counts["connect"],
            "accepts": counts["accept"],
            "closes": counts["close"],
            "cuts": counts["cut"],
            "sends": counts["send"],
            "delivers": counts["deliver"],
            "takes": sum(stream._taken_server + stream._taken_client
                         for stream in self._streams.values()),
            "bytes_sent": sum(record["count"] for record in self._log
                              if record["event"] == "send"),
            "bytes_carried": sum(record["count"] for record in self._log
                                 if record["event"] == "deliver"),
            "bytes_dropped": sum(record["count"] for record in self._log
                                 if record["event"] == "drop"),
            "chunk": self._chunk,
            "backlog": self._backlog,
        }

    def rules(self):
        """The rules this transport was built with, as they were given."""
        return dict(self._rules)

    def reset(self):
        """Forget the streams, the listeners, the log and the counts; keep the clock."""
        self._streams = {}
        self._listeners = {}
        self._log = []
        self._next = 1

    # ---- the private half --------------------------------------------------

    def _carry(self, stream):
        """Move one `chunk` of each queue across, and log the two arrivals."""
        for queued, arrived, side in (
                (stream._queued_client, stream._arrived_server, "server"),
                (stream._queued_server, stream._arrived_client, "client")):
            moved = min(self._chunk, len(queued))
            if not moved:
                continue
            arrived += queued[:moved]
            del queued[:moved]
            self._event("deliver", stream, side=side, count=moved)

    def _event(self, event, stream, **fields):
        record = {"tick": self._now, "event": event,
                  "stream": None if stream is None else stream.id}
        record.update(fields)
        self._log.append(record)
        return record
