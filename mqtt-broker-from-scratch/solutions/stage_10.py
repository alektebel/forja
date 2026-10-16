"""MQTT Broker From Scratch — stage 10: One scenario, twice, and the reader's verdict.

The capstone: the whole broker, running on the provided transport. Every frame
it writes goes through one trace, the trace is read back by the course's own
reader with no byte left over, and the report the broker counts from that trace
is held against the transport's own log.
"""

import grants
import stage_01
import stage_02
import stage_03
import stage_04
import stage_05
import stage_06
import stage_07
import stage_08
import stage_09
import streams

BROKER_KEYS = ("client", "stream", "buffers", "sessions", "trie", "retained",
               "inflight", "queued", "decisions", "trace", "tick")

REPORT_KEYS = ("streams", "sessions", "subscriptions", "deliveries", "qos0",
               "qos1", "qos2", "redeliveries", "queued", "dropped", "refusals",
               "frames", "bytes")

_QOS0_FLAGS = 0
_QOS1_FLAGS = 1 << 1
_QOS2_FLAGS = 2 << 1


def _buffer(data, what):
    """The bytes themselves, or a refusal naming the type that arrived instead."""
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    raise stage_01.ProtocolError("%s must be bytes, not %s"
                                 % (what, type(data).__name__))


def _tick(tick, what):
    """A tick at or after zero, or a refusal naming what arrived instead."""
    if isinstance(tick, bool) or not isinstance(tick, int):
        raise stage_01.ProtocolError("%s must be an int, not %s"
                                     % (what, type(tick).__name__))
    if tick < 0:
        raise stage_01.ProtocolError("%s is zero or more, not %d" % (what, tick))
    return tick


def _position(data, pos):
    """A position inside `data`, or a refusal naming the position and the size."""
    if isinstance(pos, bool) or not isinstance(pos, int):
        raise stage_01.ProtocolError("a position must be an int, not %r" % (pos,))
    if not 0 <= pos <= len(data):
        raise stage_01.ProtocolError("a position of %d in %d bytes"
                                     % (pos, len(data)))
    return pos


def _name(name):
    """A non-empty name, or a refusal naming what arrived instead."""
    if not isinstance(name, str) or not name:
        raise stage_01.ProtocolError("a name must be a non-empty str, not %r"
                                     % (name,))
    return name


def _transport(transport):
    """The transport itself, or a refusal naming what was handed in instead."""
    if not isinstance(transport, streams.Transport):
        raise stage_01.ProtocolError("a broker runs on a Transport, not %s"
                                     % (type(transport).__name__,))
    return transport


def _policy(grants_table):
    """A `grants.Grants` table, or `None` for a broker with no policy at all."""
    if grants_table is None:
        return None
    if not isinstance(grants_table, grants.Grants):
        raise stage_01.ProtocolError("a broker's policy is a grants.Grants table, "
                                     "not %s" % (type(grants_table).__name__,))
    return grants_table


def _frame(kind, flags, body):
    """One whole packet: the type and its flags, the length, then the body."""
    body = _buffer(body, "a packet body")
    return bytes([(kind << 4) | flags]) + stage_01.write_varint(len(body)) + body


def _matches(filter, topic):
    """Whether `filter` reaches `topic`: the course's matcher, one filter at a time.

    A retained message is stored under a *topic* and a subscriber asks with a
    *filter*, so the question is the trie's own — asked here by putting the one
    filter in a trie of its own and matching the topic through it, rather than by
    comparing strings, which is the mistake stage 3 exists to prevent.
    """
    scratch = stage_03.Trie()
    scratch.subscribe(filter, "m", 0)
    return bool(scratch.match(topic))


class Trace:
    """Every byte the broker wrote, in the order it wrote them, with its tick."""

    def __init__(self):
        """Nothing written yet: no frames, no bytes, no ticks."""
        self._writes = []

    def wrote(self, tick, data):
        """Record `data` as written at `tick`, and answer the same bytes.

        The tick is the caller's — the trace never reads a clock of its own, and
        the tick it records is the tick of the *write*, not of the read that
        follows it.
        """
        tick = _tick(tick, "the tick a frame is written at")
        data = _buffer(data, "the bytes a trace records")
        self._writes.append((tick, data))
        return data

    def frames(self):
        """Every write, as `[(tick, bytes)]`, in the order it happened."""
        return [(tick, data) for tick, data in self._writes]

    def bytes(self):
        """Every byte written, in order: one run, as one buffer."""
        return b"".join(data for _, data in self._writes)


def read_frames(data, pos=0):
    """Every frame in `data` from `pos`, as `([(type, flags, body)], pos_after)`.

    The course's own reader: stage 1's `read_header` judges each fixed header and
    says where its body starts, and the body is the `length` bytes after it. The
    buffer is walked to its end — the position that comes back is where the last
    frame ended — and a buffer that stops inside a frame is stage 1's
    `Incomplete`, needing exactly the bytes that have not arrived, so a caller
    that keeps the buffer and offers it again after the next step reads the frame
    once.
    """
    data = _buffer(data, "the buffer a trace is read from")
    pos = _position(data, pos)
    frames = []
    while pos < len(data):
        header, body_at = stage_01.read_header(data, pos)
        end = body_at + header["length"]
        frames.append((header["type"], header["flags"], data[body_at:end]))
        pos = end
    return frames, pos


def _report(report):
    """A report carrying every key of `REPORT_KEYS`, or a refusal naming the one lost."""
    if not isinstance(report, dict):
        raise stage_01.ProtocolError("a report is a dict of counts, not %s"
                                     % (type(report).__name__,))
    for key in REPORT_KEYS:
        if key not in report:
            raise stage_01.ProtocolError("a report with no %r in it (the keys are "
                                         "%r)" % (key, REPORT_KEYS))
    return report


def cross_check(report, transport):
    """The report and the transport's own account, held together key by key.

    Only the keys both accounts can state are compared, because they are the only
    ones a disagreement can be about: the streams the transport opened (which the
    broker counts as the streams that completed a CONNECT) and the bytes it took
    towards its clients (which the broker counts as every byte it wrote). The
    transport knows nothing of sessions and the broker is not a transcript of the
    transport's log, so everything else is left alone.

    A disagreement is named rather than resolved: the answer carries `agree` and
    a `disagreements` list, empty when the two accounts say the same numbers.
    """
    report = _report(report)
    transport = _transport(transport)
    log = transport.log()
    watched = (("streams", transport.stats()["streams"]),
               ("bytes", sum(record["count"] for record in log
                             if record["event"] == "send"
                             and record.get("side") == "client")))
    disagreements = ["%r is %r in the report and %r in the transport's log"
                     % (key, report[key], observed)
                     for key, observed in watched if report[key] != observed]
    return {"agree": not disagreements, "disagreements": disagreements}


def replay(scenario):
    """Run a scenario once and answer the bytes that run wrote.

    A scenario is a callable that builds its own transport, listens, connects its
    clients and answers the broker it drove — so two calls are two whole runs,
    and the only thing worth comparing about them is the trace: two runs of one
    scripted scenario are the same bytes, or one of them is not deterministic.
    """
    if not callable(scenario):
        raise stage_01.ProtocolError("a scenario must be callable, not %s"
                                     % (type(scenario).__name__,))
    broker = scenario()
    if not isinstance(broker, Broker):
        raise stage_01.ProtocolError("a scenario answers the Broker it drove, not "
                                     "%s" % (type(broker).__name__,))
    return broker.trace().bytes()


class Broker:
    """The whole broker: a transport, a state dict, and one scripted run.

    `state` carries the keys of `BROKER_KEYS`, in that order, and it is the whole
    of what a run is: the stream each client is on and the client each stream
    speaks for, the buffers the broker holds for a stream, stage 8's sessions,
    stage 3's trie of subscriptions in force, stage 5's retained store, the id
    spaces and the in-flight tables of stage 6 and 7 per client, the messages a
    resume took back, stage 9's ledger of lines, stage 10's own trace, and the
    tick the broker last saw.

    Who carries the bytes of a turn is the one rule the two halves of the surface
    divide between them. `receive` answers a peer's packet *to its caller's hand*:
    the frames written for the stream that packet arrived on come back as a list,
    and the caller — the harness that owns the wire in a test, a socket loop in a
    server — hands them to the transport. Anything the same turn writes for
    *another* stream, and everything `step` writes, is the broker's own to carry,
    so it waits in the stream's outbound buffer and the broker offers it to the
    transport on its own next turn, holding the tail the outbox could not take.
    """

    def __init__(self, transport, name="broker", grants=None):
        """A broker answering to `name` on `transport`, under `grants` or none.

        A broker with no table has no policy: it says yes to every publish and
        every subscribe and writes no line, because a line is the record of a
        decision and a broker that was handed no grants has nothing to decide.
        """
        self.transport = _transport(transport)
        self.name = _name(name)
        self.grants = _policy(grants)
        self._owner = None
        self.state = {
            "client": {},
            "stream": {},
            "buffers": {},
            "sessions": stage_08.Sessions(),
            "trie": stage_03.Trie(),
            "retained": stage_05.Retained(),
            "inflight": {},
            "queued": {},
            "decisions": stage_09.Ledger(),
            "trace": Trace(),
            "tick": 0,
        }

    # ---- the surface -------------------------------------------------------

    def accepted(self):
        """The streams that have completed a CONNECT, in the order they did."""
        return tuple(self.state["client"])

    def receive(self, stream, data):
        """The frames this broker wrote in answer to `data`, as a list.

        `data` is what one arrival at the server's end of `stream` carried: the
        broker keeps it beside whatever arrived before and reads frames out of
        the whole buffer, so a packet split across two arrivals is read once it
        is whole and nothing before it is read twice. A buffer that stops inside
        a frame answers nothing and keeps the bytes — the caller offers them
        again after the next step — and a frame the course's own reader refuses
        is refused here, naming the bytes that arrived.
        """
        ident = self._stream(stream)
        data = _buffer(data, "the bytes one arrival carried")
        self.state["tick"] = self.transport.tick()
        held = self._held(ident)
        held["in"] += data
        try:
            frames, pos = read_frames(held["in"])
        except stage_01.Incomplete:
            return []
        held["in"] = held["in"][pos:]
        written = []
        self._owner = (ident, written)
        try:
            for kind, flags, body in frames:
                self._dispatch(ident, kind, flags, body)
        finally:
            self._owner = None
        return written

    def step(self, ticks=1):
        """Move the clock `ticks`, do the broker's own work, and answer the tick.

        One step is one turn of the whole broker: the connections the caller
        ended without telling it, the deliveries whose deadline has passed, the
        keep-alives that have run out — a will is owed to each of those — the
        messages a resumed session took back, and the last chunk of whatever the
        broker still owes the wire.
        """
        tick = self.transport.step(ticks)
        self.state["tick"] = tick
        self._endings(tick)
        self._resends(tick)
        self._expiries(tick)
        self._backlog(tick)
        self._flush()
        return tick

    def report(self):
        """The counts of this run, in `REPORT_KEYS` order.

        Every number is counted from the trace, from the sessions or from the
        trie, never from a counter kept beside them: the frames are the trace's
        own writes, re-read by the course's own reader so a QoS is the nibble the
        wire carried, the subscriptions are the ones in force, the queued and the
        dropped are what the sessions hold, and the refusals are the lines stage
        9 wrote. `dropped` is the bytes the broker still holds for a stream that
        is no longer open: bytes it wrote and the wire can never carry.
        """
        written = self.state["trace"].bytes()
        frames = read_frames(written)[0]
        deliveries = [flags for kind, flags, _ in frames
                      if kind == stage_01.PUBLISH]
        qos = [(flags & stage_05.QOS_BITS) >> 1 for flags in deliveries]
        sessions = self.state["sessions"].sessions()
        trie = self.state["trie"]
        return {
            "streams": len(self.state["client"]),
            "sessions": len(sessions),
            "subscriptions": sum(len(trie.subscribers(filter))
                                 for filter in trie.filters()),
            "deliveries": len(deliveries),
            "qos0": qos.count(0),
            "qos1": qos.count(1),
            "qos2": qos.count(2),
            "redeliveries": sum(1 for flags in deliveries
                                if flags & stage_05.DUP_BIT),
            "queued": sum(len(session["queue"]) for session in sessions)
                      + sum(len(waiting) for waiting in self.state["queued"].values()),
            "dropped": sum(len(held["in"]) + len(held["out"])
                           for held in self.state["buffers"].values()
                           if not held["open"]),
            "refusals": len(self.state["decisions"].denials()),
            "frames": len(frames),
            "bytes": len(written),
        }

    def trace(self):
        """The trace this run wrote: the same trace, from its first byte on."""
        return self.state["trace"]

    # ---- one frame in, the frames it earns out -----------------------------

    def _dispatch(self, ident, kind, flags, body):
        """The work one frame of `kind` asks for, in the order it is owed.

        The type is the fixed header's business — stage 1 read it and the body
        arrives here alone — so this is where a broker's own dispatcher lives:
        CONNECT before anything else, because a stream has no client to speak for
        until one has, and the four bare acknowledgements after the two packets
        that carry messages.
        """
        tick = self.state["tick"]
        if kind == stage_01.CONNECT:
            self._connect(ident, body, tick)
            return
        client_id = self.state["client"].get(ident)
        if client_id is None:
            raise stage_01.ProtocolError(
                "stream %d has not completed a CONNECT, so it has no client to "
                "speak for" % (ident,))
        self.state["sessions"].touch(client_id, tick)
        if kind == stage_01.SUBSCRIBE:
            self._subscribe(client_id, body, tick)
        elif kind == stage_01.UNSUBSCRIBE:
            self._unsubscribe(client_id, body, tick)
        elif kind == stage_01.PUBLISH:
            self._publish(client_id, flags, body, tick)
        elif kind in (stage_01.PUBACK, stage_01.PUBREC, stage_01.PUBREL,
                      stage_01.PUBCOMP):
            self._acknowledge(client_id, kind, body, tick)
        elif kind == stage_01.PINGREQ:
            self._write(ident, _frame(stage_01.PINGRESP, 0, b""))
        elif kind == stage_01.DISCONNECT:
            self._detach(client_id, streams.CLOSED, tick)
        else:
            raise stage_01.ProtocolError(
                "packet type %d is not one a client sends a broker" % (kind,))

    def _connect(self, ident, body, tick):
        """A CONNECT: the session it opens or resumes, and the CONNACK it earns.

        A name or a level the broker does not speak, or a client identifier it
        may not take, is answered with the code that says so and no session at
        all: a refused connection is a conversation, not a broken packet. An
        accepted one puts the stream on the client, clears what a clean start
        promised to throw away, brings the session's filters back into force —
        the trie is the broker's and holds nobody's subscriptions until its
        client is here — and takes back the queue a resume was owed.
        """
        connect = stage_02.read_connect(body)[0]
        code = stage_02.connack_code(connect)
        if code != stage_02.CONNACK_ACCEPTED:
            self._write(ident, _frame(stage_01.CONNACK, 0,
                                      stage_02.write_connack(0, code)))
            return
        session, present = self.state["sessions"].attach(connect, ident, tick)
        client_id = session["client_id"]
        self.state["client"][ident] = client_id
        self.state["stream"][client_id] = ident
        self._held(ident)["open"] = True
        if not present:
            self.state["queued"].pop(client_id, None)
            self.state["inflight"].pop(client_id, None)
        self._resubscribe(client_id, session)
        waiting = self.state["sessions"].take_queued(client_id)
        if waiting:
            self.state["queued"].setdefault(client_id, []).extend(waiting)
        self._write(ident, _frame(stage_01.CONNACK, 0,
                                  stage_02.write_connack(present, 0)))

    def _resubscribe(self, client_id, session):
        """The subscriptions in force: this session's own, and nobody else's.

        A resumed session's filters go back into the trie, because the trie is
        the broker's and is in nobody's session; a clean start's filters were
        thrown away with the session, so the trie is emptied of them, filter by
        filter, before the new ones — there are none — go in.
        """
        held = session["subscriptions"]
        for filter in self.state["trie"].filters():
            if filter not in held:
                self.state["trie"].unsubscribe(filter, client_id)
        for filter, qos in held.items():
            self.state["trie"].subscribe(filter, client_id, qos)

    def _subscribe(self, client_id, body, tick):
        """A SUBSCRIBE: the line before each grant, the SUBACK, the retained store.

        Every filter is decided on its own — one code per filter is what a SUBACK
        carries — and a filter the grants refuse is answered with the failure code
        and is not put in force. A granted filter is subscribed at the QoS the
        broker grants, which is a different number from the one the client asked
        for, and then the retained messages it now reaches are delivered, at the
        subscription's own QoS and with the retain flag the wire wants on a
        message that was published before the subscription existed.
        """
        subscribe = stage_04.read_subscribe(body)[0]
        session = self.state["sessions"].touch(client_id, tick)
        refused = []
        granted_filters = []
        for filter, qos in subscribe["topics"]:
            if not self._allowed(client_id, "subscribe", filter, tick):
                refused.append(filter)
                continue
            granted = stage_04.granted_qos(qos)
            self.state["trie"].subscribe(filter, client_id, granted)
            session["subscriptions"][filter] = granted
            granted_filters.append((filter, granted))
        codes = stage_04.grant_codes(subscribe, stage_04.MAX_QOS, tuple(refused))
        ident = self.state["stream"][client_id]
        self._write(ident, _frame(stage_01.SUBACK, 0,
                                  stage_04.write_suback(subscribe["packet_id"],
                                                        codes)))
        for filter, granted in granted_filters:
            self._stored(client_id, filter, granted, tick)

    def _unsubscribe(self, client_id, body, tick):
        """An UNSUBSCRIBE: the filters go out of the trie, and a UNSUBACK is owed.

        A filter the client was not on is not an error — the trie answers `False`
        and the UNSUBACK is written all the same, because the client asked and a
        client is answered.
        """
        packet_id, filters = stage_04.read_unsubscribe(body)[0]
        session = self.state["sessions"].touch(client_id, tick)
        for filter in filters:
            self.state["trie"].unsubscribe(filter, client_id)
            session["subscriptions"].pop(filter, None)
        ident = self.state["stream"][client_id]
        self._write(ident, _frame(stage_01.UNSUBACK, 0,
                                  stage_04.write_unsuback(packet_id)))

    def _publish(self, client_id, flags, body, tick):
        """A PUBLISH: the line before the act, the routing, and the answer owed.

        The topic, the payload and the three bits that shaped the body all come
        from stage 5's reader, which is the one reader whose body depends on the
        fixed header's nibble. A publish the grants refuse is *acted on* by not
        being acted on — MQTT has no answer for one — but the line is written
        first and nothing is routed or retained for it. QoS 0 is routing and
        nothing else; QoS 1 is routing and a PUBACK, the message is the client's
        to re-send and the broker's to deliver at once; QoS 2 is a PUBREC and the
        message *held*, because the packet that delivers an exactly-once message
        is the PUBREL and not the PUBLISH.
        """
        publish = stage_05.read_publish(body, 0, flags)[0]
        if not self._allowed(client_id, "publish", publish["topic"], tick):
            return
        if publish["retain"]:
            self.state["retained"].store(publish)
        ident = self.state["stream"][client_id]
        if publish["qos"] == 0:
            self._route(publish, tick)
            return
        if publish["qos"] == 1:
            self._route(publish, tick)
            self._write(ident, _frame(stage_01.PUBACK, 0,
                                      stage_06.write_ack(stage_01.PUBACK,
                                                         publish["packet_id"])))
            return
        record = self._inflight(client_id)
        pubrec, _ = record["received"].took(publish)
        self._write(ident, _frame(stage_01.PUBREC, 0, pubrec))

    def _acknowledge(self, client_id, kind, body, tick):
        """One bare acknowledgement, and what it settles.

        The id is all four of these packets carry, so stage 6 reads it once. A
        PUBACK settles a QoS 1 delivery and gives its id back; a PUBREC moves the
        handshake and is answered with the PUBREL that carries the *same* id under
        its own nibble; a PUBREL delivers the message the PUBLISH before it put
        aside, and is answered with the PUBCOMP that ends the id's life; and a
        PUBCOMP settles the broker's own handshake — and is refused for an id the
        broker is not waiting on, because an acknowledgement that frees somebody
        else's id is the mistake the whole handshake exists to prevent.
        """
        packet_id = stage_06.read_ack(body)[0]
        record = self._inflight(client_id)
        ident = self.state["stream"][client_id]
        if kind == stage_01.PUBACK:
            record["flight"].settle(packet_id)
        elif kind == stage_01.PUBREC:
            pubrel = record["sender"].received(stage_01.PUBREC, packet_id, tick)
            self._write(ident, _frame(stage_01.PUBREL, stage_07.PUBREL_FLAGS,
                                      pubrel))
        elif kind == stage_01.PUBREL:
            pubcomp, message = record["received"].released(packet_id)
            if message is not None:
                self._route(message, tick)
            self._write(ident, _frame(stage_01.PUBCOMP, 0, pubcomp))
        else:
            record["sender"].received(stage_01.PUBCOMP, packet_id, tick)

    # ---- the broker's own turn --------------------------------------------

    def _endings(self, tick):
        """The connections the caller ended without telling the broker.

        The transport's own state is the tie-breaker: a stream this broker
        believes is live and the transport says is closed was ended by the
        client, and one it says was cut was not ended by anybody — which is the
        difference a will hangs on. A client, a clean start and a resumed session
        are all the session table's business, so nothing else is decided here.
        """
        for client_id in tuple(self.state["stream"]):
            ident = self.state["stream"][client_id]
            if ident is None:
                continue
            state = self.transport.stream(ident).state
            if state != streams.OPEN:
                self._detach(client_id, state, tick)

    def _detach(self, client_id, reason, tick):
        """End one connection as `reason`, and route the will it owes, if any.

        Stage 8 writes the three reasons and the rule about which of them owes a
        will; the session itself survives all three, because a session is a
        promise about the *client* and not about the socket. The stream's buffers
        are marked not open — the bytes the broker still held for it are dropped
        where they stand, and the report counts them.
        """
        ident = self.state["stream"].get(client_id)
        self.state["stream"][client_id] = None
        if ident is not None:
            self._held(ident)["open"] = False
        will = self.state["sessions"].detach(client_id, reason, tick)
        if will is not None:
            self._route(self._message_from(will), tick)

    def _message_from(self, will):
        """A will as a publish, in `PUBLISH_KEYS` order, ready to be routed.

        A will is the connection's own promise, made when the broker accepted the
        CONNECT with it, so it is routed as the publish it describes and is not
        put to the grants a second time: what the broker agreed to at CONNECT is
        not re-opened by the client's dying.
        """
        return {"topic": will["topic"], "payload": will["payload"],
                "qos": will["qos"], "packet_id": None,
                "retain": will["retain"], "dup": False}

    def _resends(self, tick):
        """The deliveries whose deadline has passed, written again as duplicates.

        Two tables, because the two levels fail differently: stage 6's in-flight
        table for the QoS 1 deliveries, which come back as a PUBLISH carrying DUP
        and the *same* id, and stage 7's sender for the QoS 2 handshakes, which
        says in its own answer which of the two packets it is waiting on — a
        PUBLISH carrying DUP and QoS 2, or a PUBREL carrying its own nibble and
        never DUP, because this format has no DUP on a PUBREL.
        """
        for client_id in tuple(self.state["inflight"]):
            ident = self.state["stream"].get(client_id)
            if ident is None:
                continue
            record = self.state["inflight"][client_id]
            for flight in record["flight"].due(tick):
                flight = record["flight"].again(flight["packet_id"], tick)
                body = stage_05.write_publish(flight["topic"], flight["payload"],
                                              flight["qos"],
                                              flight["packet_id"])
                self._write(ident, _frame(stage_01.PUBLISH,
                                          stage_05.DUP_BIT
                                          | (flight["qos"] << 1), body))
            for packet_id, flags, body in record["sender"].due(tick):
                kind = (stage_01.PUBREL if flags == stage_07.PUBREL_FLAGS
                        else stage_01.PUBLISH)
                self._write(ident, _frame(kind, flags, body))

    def _expiries(self, tick):
        """The keep-alives that have run out: the connection is cut, the will owed.

        The session table answers which clients have gone quiet — no client that
        has spoken is named — and the broker then ends what stage 8 has already
        decided: the stream is cut, because a connection whose promise ran out is
        not ended by agreement, and the will of *that* connection is routed.
        """
        for client_id in self.state["sessions"].expired(tick):
            ident = self.state["stream"].get(client_id)
            if ident is not None:
                self.transport.cut(self.transport.stream(ident),
                                   "keep-alive expired")
            self._detach(client_id, "expired", tick)

    def _backlog(self, tick):
        """The messages a resumed session was owed, delivered now it is here.

        A resume hands the queue over once — stage 8 takes it out of the session
        so the next resume cannot deliver it again — and the broker holds what it
        took until it can write it: the client may be cut again before the next
        step, and a message taken and lost would be a promise broken twice.
        """
        for client_id in tuple(self.state["queued"]):
            ident = self.state["stream"].get(client_id)
            if ident is None:
                continue
            waiting = self.state["queued"].pop(client_id)
            for message in waiting:
                self._deliver(ident, message, tick)

    def _flush(self):
        """Hand the transport what fits of what the broker still owes each stream.

        One offer per step, in the order the buffers were first used: a frame
        larger than the outbox is carried a chunk at a time, and the tail stays
        the broker's until the next step takes it. A stream that is no longer
        open takes nothing, and what was held for it stays held — the report
        counts those bytes as dropped, because no wire will ever carry them.
        """
        for ident in tuple(self.state["buffers"]):
            held = self.state["buffers"][ident]
            if not held["open"] or not held["out"]:
                continue
            stream = self.transport.stream(ident)
            if stream.state != streams.OPEN:
                held["open"] = False
                continue
            taken = self.transport.answer(stream, held["out"])
            held["out"] = held["out"][taken:]

    # ---- the pieces the turns are made of ---------------------------------

    def _deliver(self, ident, message, tick):
        """Write one message to one stream, at the QoS it was promised.

        A delivery is written where it is asked for and nowhere else: QoS 0 is a
        frame; QoS 1 takes an id from the client's own space and puts the message
        in flight, where it stays until a PUBACK names that id; QoS 2 takes an id
        too, but through stage 7's sender, and the id stays in flight across the
        four packets. The retain bit is the message's own — `True` only for the
        stored message a fresh subscription was owed — and DUP is never set on a
        first transmission, which is the whole of what DUP means.
        """
        client_id = self.state["client"][ident]
        qos = message["qos"]
        flags = (qos << 1) | (stage_05.RETAIN_BIT if message["retain"] else 0)
        if qos == 0:
            body = stage_05.write_publish(message["topic"], message["payload"], 0)
            self._write(ident, _frame(stage_01.PUBLISH, flags, body))
            return
        record = self._inflight(client_id)
        if qos == 1:
            packet_id = record["ids"].take()
            record["flight"].add(message, packet_id, tick)
            body = stage_05.write_publish(message["topic"], message["payload"], 1,
                                          packet_id)
        else:
            packet_id, body = record["sender"].start(message, tick)
        self._write(ident, _frame(stage_01.PUBLISH, flags, body))

    def _route(self, publish, tick):
        """Every subscriber a publish reaches: delivered here, queued there.

        The trie decides who is reached and at what QoS — stage 3's matcher, one
        entry per client at its highest holding — and stage 5 turns that into one
        message per subscriber. A subscriber whose session is not on a stream is
        queued for rather than delivered to, and the queue's own rule keeps a QoS
        0 message out of it: a message nobody promised is not a message anybody
        is owed later.
        """
        subscribers = stage_05.route(self.state["trie"], publish["topic"])
        for client_id, message in stage_05.deliveries(publish, subscribers):
            ident = self.state["stream"].get(client_id)
            if ident is None:
                self.state["sessions"].queue_for(client_id, message)
                continue
            self._deliver(ident, message, tick)

    def _stored(self, client_id, filter, granted, tick):
        """The retained messages a fresh subscription is handed, oldest first."""
        for topic in self.state["retained"].topics():
            if not _matches(filter, topic):
                continue
            stored = self.state["retained"].lookup(topic)
            for _, message in stage_05.deliveries(stored, [(client_id, granted)],
                                                  retained=True):
                ident = self.state["stream"].get(client_id)
                if ident is not None:
                    self._deliver(ident, message, tick)

    def _allowed(self, client_id, action, topic, tick):
        """Whether an act is granted, writing the line before it happens.

        A broker with no table has no policy and writes no line. A broker that
        has one asks stage 9, which answers `(allowed, reason)` from the client's
        own grant and the broker's ceiling both, and the line for that decision
        is written into the ledger *before* the act is done or not done.
        """
        if self.grants is None:
            return True
        decision = stage_09.decide(self.grants, client_id, action, topic, tick)
        self.state["decisions"].before(decision)
        return decision["allowed"]

    def _inflight(self, client_id):
        """This client's id space and the three tables that share it.

        One `PacketIds` per client and not per level: an id in flight is an id
        somebody is waiting on, and a QoS 1 delivery and a QoS 2 handshake that
        drew `7` from two spaces would be two different messages under one id.
        The receiver is the other direction — the publishes this client sent that
        the broker is holding until their PUBRELs.
        """
        record = self.state["inflight"].get(client_id)
        if record is None:
            ids = stage_06.PacketIds()
            record = {"ids": ids, "flight": stage_06.InFlight(ids),
                      "sender": stage_07.Sender(ids),
                      "received": stage_07.Receiver()}
            self.state["inflight"][client_id] = record
        return record

    def _write(self, ident, frame):
        """Record a frame in the trace and hand it to whoever owns this turn.

        The trace is the broker's, whatever the turn: every byte the broker
        writes is recorded with the tick it was written at, so the report and the
        reader and the transport can be held against one another. Where the frame
        goes next depends on whom it is *for*: the frame answering the arrival
        being read goes back to that caller's hand, and a frame for any other
        stream — a delivery routed to a second subscriber, a will, a re-send —
        is the broker's own to carry, so it waits in the stream's outbound buffer
        for the next `_flush`.

        A stream that already owes the wire something is not answered in the
        caller's hand even when this turn is its own: the frame joins the queue
        behind the bytes that are ahead of it. A frame handed straight to the
        caller goes to the transport at once, so answering one while the broker
        still held the tail of an earlier frame for that same stream would put the
        second frame's bytes in front of the first frame's last bytes — one
        stream carrying two frames in the wrong order, which no reader can
        untangle.
        """
        frame = self.state["trace"].wrote(self.state["tick"], frame)
        if (self._owner is not None and self._owner[0] == ident
                and not self._held(ident)["out"]):
            self._owner[1].append(frame)
        else:
            self._held(ident)["out"] += frame
        return frame

    def _stream(self, stream):
        """The id of one of this transport's streams, or a refusal naming it."""
        return self.transport.stream(stream).id

    def _held(self, ident):
        """This stream's two buffers and whether it is still expected to carry.

        The inbound buffer is the reassembly the course keeps out of the readers:
        a frame that arrives in pieces waits here until it is whole. The outbound
        one is what the broker still owes the wire, and `open` is the broker's
        own record of an ending it has seen — the bytes of a stream nobody will
        read again stay where they are, and the report counts them as dropped.
        """
        return self.state["buffers"].setdefault(
            ident, {"in": b"", "out": b"", "open": True})
