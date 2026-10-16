"""MQTT Broker From Scratch — stage 8: The session that outlives the socket.

See `stage_01.py` for the surface and the design decisions; this is what the
broker keeps for a client between two connections — the subscriptions, the
queued messages, and the will — and the arithmetic that decides when a client
that has gone quiet is gone.
"""

import stage_01
import stage_02
import streams

SESSION_KEYS = ("client_id", "clean_start", "keep_alive", "will", "stream",
                "subscriptions", "pending", "queue", "started_at", "last_seen")

QUEUE_MAX = 8

KEEP_ALIVE_NUMERATOR = 3
KEEP_ALIVE_DENOMINATOR = 2

# the three words a connection can end with: the transport's own states for an
# ended stream, and the broker's word for a clock that ended it.
_CLEAN = streams.CLOSED
_CUT = streams.CUT
_EXPIRED = "expired"
_REASONS = (_CLEAN, _CUT, _EXPIRED)


def deadline_from(keep_alive):
    """The ticks a client may be silent for: `keep_alive + keep_alive // 2`.

    The half is the point. A client that sends a packet every `k` ticks and a
    broker that watches for `k` ticks are two clocks that drift apart, and the
    first one to be a tick ahead loses a healthy connection; half again is the
    margin MQTT asks a server to allow. The ratio is written as its own two
    constants because it is a decision, not a lucky expression.

    Zero is a client that asked for no keep-alive at all, and `0 + 0 // 2` is 0:
    a deadline of zero, which this table reads as "there is no deadline" rather
    than as "already gone". A `bool` is not a keep-alive and a negative one
    cannot come off a two-byte field: both are refused by name.
    """
    if isinstance(keep_alive, bool) or not isinstance(keep_alive, int):
        raise stage_01.ProtocolError("a keep-alive must be an int, not %s"
                                     % (type(keep_alive).__name__,))
    if keep_alive < 0:
        raise stage_01.ProtocolError("a keep-alive of %d cannot be negative"
                                     % (keep_alive,))
    return keep_alive * KEEP_ALIVE_NUMERATOR // KEEP_ALIVE_DENOMINATOR


def _client(client_id):
    if not isinstance(client_id, str):
        raise stage_01.ProtocolError("a client is named by a str, not %s"
                                     % (type(client_id).__name__,))
    return client_id


def _tick(tick, what):
    if isinstance(tick, bool) or not isinstance(tick, int):
        raise stage_01.ProtocolError("%s must be an int tick, not %s"
                                     % (what, type(tick).__name__,))
    if tick < 0:
        raise stage_01.ProtocolError("%s of %d is before the clock started"
                                     % (what, tick))
    return tick


def _stream_id(stream):
    if isinstance(stream, bool) or not isinstance(stream, int) or stream < 1:
        raise stage_01.ProtocolError(
            "a stream is the id the transport handed out, a positive int, not %r"
            % (stream,))
    return stream


def _connect(connect):
    if not isinstance(connect, dict):
        raise stage_01.ProtocolError("a CONNECT must be a dict, not %s"
                                     % (type(connect).__name__,))
    for key in stage_02.CONNECT_KEYS:
        if key not in connect:
            raise stage_01.ProtocolError("a CONNECT with no %r in it" % (key,))
    return connect


def _qos(publish):
    if not isinstance(publish, dict):
        raise stage_01.ProtocolError("a publish must be a dict, not %s"
                                     % (type(publish).__name__,))
    if "qos" not in publish:
        raise stage_01.ProtocolError("a publish with no 'qos' in it (%r)"
                                     % (sorted(publish),))
    qos = publish["qos"]
    if isinstance(qos, bool) or not isinstance(qos, int) or not 0 <= qos <= 2:
        raise stage_01.ProtocolError("a publish's QoS of %r is not 0, 1 or 2"
                                     % (qos,))
    return qos


def _fresh(connect, stream, tick):
    """A session that begins here: nothing carried over, in `SESSION_KEYS` order."""
    return {"client_id": connect["client_id"],
            "clean_start": bool(connect["clean_start"]),
            "keep_alive": connect["keep_alive"],
            "will": connect["will"],
            "stream": stream,
            "subscriptions": {},
            "pending": 0,
            "queue": [],
            "started_at": tick,
            "last_seen": tick}


def _due(session, tick):
    """Whether `session`'s keep-alive has run out by `tick`.

    `last_seen` is the last **packet**, and every packet moves it, because the
    keep-alive is a promise about the connection and not about the payload: a
    client that pings and publishes nothing is alive, and a client that
    subscribed once and publishes every tick is alive for a reason the client
    never asked about. A deadline of 0 is no deadline at all.
    """
    deadline = deadline_from(session["keep_alive"])
    return deadline > 0 and tick - session["last_seen"] >= deadline


class Sessions:
    """What a broker keeps for a client that is not connected any more.

    The table is keyed by client id and holds one record per client, in
    `SESSION_KEYS` order, and it is the broker's own table: `attach` hands back
    the record itself rather than a copy, so the subscriptions a caller writes
    into it after a resumed CONNECT are in force on the next resume without a
    second store.
    """

    def __init__(self):
        """No client held yet: the broker has met nobody."""
        self._held = {}

    def attach(self, connect, stream, tick):
        """Take `connect` on the stream `stream` at `tick`, as `(session, present)`.

        A clean start is a promise the broker makes to the client: everything
        held for this client id is thrown away, the session is new, and the
        present flag is 0, because there is nothing to present. A clean start of
        0 has two answers, and the bit is which one this is: the record the
        broker holds, present 1, or a session that begins now, present 0.

        The record that resumes keeps what the connection did **not** create: its
        subscriptions and its queue, and the tick the session began at. What the
        connection did create is written again — the keep-alive and the will are
        the new connection's promises, the stream is the new socket, and
        `last_seen` is now.
        """
        connect = _connect(connect)
        stream = _stream_id(stream)
        tick = _tick(tick, "an attach tick")
        client_id = connect["client_id"]
        session = self._held.get(client_id)
        if bool(connect["clean_start"]) or session is None:
            self._held.pop(client_id, None)
            session = _fresh(connect, stream, tick)
            self._held[client_id] = session
            return session, 0
        session["clean_start"] = bool(connect["clean_start"])
        session["keep_alive"] = connect["keep_alive"]
        session["will"] = connect["will"]
        session["stream"] = stream
        session["last_seen"] = tick
        return session, 1

    def detach(self, client_id, reason, tick):
        """End `client_id`'s connection as `reason` at `tick`, as the will owed.

        Three reasons, because a connection ends in three ways: `closed` (both
        ends said so — the client sent a DISCONNECT), `cut` (nobody agreed), and
        `expired` (the keep-alive ran out). Only the first is an end the client
        chose, and only the others are ends a will is owed for.

        The will leaves the session as it is handed back, so the same will cannot
        be published twice, and a client that reconnects with a will of its own
        replaces it — the will belongs to the connection, not to the client. An
        end that is a `closed` end clears the will too: a client that said
        goodbye owes nothing, and there is nothing left to owe. A client the
        table has never met has no will to answer with, and answers `None`.

        An `expired` end is refused unless the keep-alive really has run out —
        the clock, not the caller, decides that — so the answer `expired` gives
        and the act it leads to cannot disagree.
        """
        client_id = _client(client_id)
        tick = _tick(tick, "a detach tick")
        if reason not in _REASONS:
            raise stage_01.ProtocolError("a connection ends as one of %r, not %r"
                                         % (_REASONS, reason))
        session = self._held.get(client_id)
        if session is None:
            return None
        if reason == _EXPIRED and not _due(session, tick):
            raise stage_01.ProtocolError(
                "%s's keep-alive has not run out: last seen at %d, %d ticks due, "
                "and the end asked for is at %d"
                % (client_id, session["last_seen"],
                   deadline_from(session["keep_alive"]), tick))
        session["stream"] = None
        will = session["will"]
        session["will"] = None
        return None if reason == _CLEAN else will

    def touch(self, client_id, tick):
        """`client_id`'s session with `last_seen` moved to `tick`.

        One field, and only one: a session is touched by every packet its client
        sends, and a ping is a packet even though it carries nothing. A client
        the table has never met answers `None`, the same as `detach`.
        """
        client_id = _client(client_id)
        tick = _tick(tick, "a touch tick")
        session = self._held.get(client_id)
        if session is None:
            return None
        session["last_seen"] = tick
        return session

    def expired(self, tick):
        """The clients whose keep-alive has run out by `tick`, in attach order.

        The question, not the act: nothing is ended here, and the caller that
        wants the will published follows with `detach(client, "expired", tick)`.
        Only a connection can go quiet: a session that is already detached holds
        no stream, is not waiting for anything, and is not named twice. A client
        that has spoken — any packet, and `touch` is what says so — is not named
        however long it has been since the last one it published.
        """
        tick = _tick(tick, "an expiry tick")
        return tuple(session["client_id"] for session in self._held.values()
                     if session["stream"] is not None and _due(session, tick))

    def queue_for(self, client_id, publish):
        """Queue `publish` for `client_id`, as `True`, or answer `False`.

        `False` has three reasons and none of them is an error: a QoS 0 message
        is not queued (it was never promised, so keeping it would deliver
        something the client's own choice did not ask to survive), the queue is
        full, or there is no session to queue for. A full queue drops the
        message that has just arrived and keeps the ones already waiting, in the
        order they were queued — the oldest are the ones a client is owed first,
        and a queue that dropped them would break the order promise to keep a
        message nobody is waiting for. A dropped message is *counted*:
        `session["pending"]` goes up by one, because "the newest is dropped" and
        "the newest is dropped silently" are different promises and only the
        first one is honest. `pending` is that count and not a second copy of
        the queue. A QoS 0 message is refused for what it is, not for want of
        room, and never moves the count.
        """
        client_id = _client(client_id)
        qos = _qos(publish)
        session = self._held.get(client_id)
        if session is None or qos == 0:
            return False
        if len(session["queue"]) >= QUEUE_MAX:
            session["pending"] += 1
            return False
        session["queue"].append(publish)
        return True

    def take_queued(self, client_id):
        """The messages queued for `client_id`, oldest first, and the queue emptied.

        Handed over once: what is returned is what was waiting, and the session
        is left with an empty queue rather than a copy that would deliver the
        same message again on the next resume.
        """
        client_id = _client(client_id)
        session = self._held.get(client_id)
        if session is None:
            return []
        queued = session["queue"]
        session["queue"] = []
        return queued

    def sessions(self):
        """The sessions held, in the order their clients were attached.

        The records themselves, not copies: a session is live state the broker
        writes to — a SUBSCRIBE adds a filter to it — while the transport's log
        is an account of what happened and is copied on the way out.
        """
        return tuple(self._held.values())
