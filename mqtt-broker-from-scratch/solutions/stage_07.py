"""MQTT Broker From Scratch — stage 7: QoS 2, the four-way handshake.

See `stage_01.py` for the surface and the design decisions; this is the promise
that a message arrives exactly once, paid for with two round trips — an id that is
in flight until its PUBCOMP, and a message delivered only when the PUBREL says the
handshake about it is over.
"""

import stage_01
import stage_05
import stage_06

PUBREL_FLAGS = 0b0010

HANDSHAKE_KEYS = ("packet_id", "message", "state")

_WAITING_REC = "waiting-rec"
_WAITING_COMP = "waiting-comp"

_RESEND_FLAGS = stage_05.DUP_BIT | (2 << 1)

_MIN_PACKET_ID = 1
_MAX_PACKET_ID = 65_535


def _tick(now, what):
    """`now` as a tick: a count of ticks, zero or more."""
    if isinstance(now, bool) or not isinstance(now, int):
        raise stage_01.ProtocolError(
            "%s of type %s is not a tick (a count, zero or more)"
            % (what, type(now).__name__))
    if now < 0:
        raise stage_01.ProtocolError(
            "%s of %d is not a tick (a count, zero or more)" % (what, now))
    return now


def _packet_id(packet_id, what):
    """`packet_id` as an id this course can write, or a refusal naming what came."""
    if isinstance(packet_id, bool) or not isinstance(packet_id, int):
        raise stage_01.ProtocolError(
            "%s of type %s is not a packet id (an int, %d to %d)"
            % (what, type(packet_id).__name__, _MIN_PACKET_ID, _MAX_PACKET_ID))
    if not _MIN_PACKET_ID <= packet_id <= _MAX_PACKET_ID:
        raise stage_01.ProtocolError(
            "%s of %d is outside %d..%d"
            % (what, packet_id, _MIN_PACKET_ID, _MAX_PACKET_ID))
    return packet_id


def _kind(kind):
    """`kind` as a packet type that may acknowledge a QoS 2 delivery."""
    if isinstance(kind, bool) or not isinstance(kind, int):
        raise stage_01.ProtocolError(
            "the kind of an acknowledgement is a packet type, not %s"
            % (type(kind).__name__,))
    if kind not in (stage_01.PUBREC, stage_01.PUBCOMP):
        raise stage_01.ProtocolError(
            "packet type %d is not an acknowledgement of a QoS 2 delivery"
            % (kind,))
    return kind


def _message(message):
    """`message` as a QoS 2 publish dict, or a refusal naming what is wrong."""
    if not isinstance(message, dict):
        raise stage_01.ProtocolError(
            "a message must be a publish dict, not %s" % (type(message).__name__,))
    for key in stage_05.PUBLISH_KEYS:
        if key not in message:
            raise stage_01.ProtocolError("a message with no %r in it" % (key,))
    if message["qos"] != 2:
        raise stage_01.ProtocolError(
            "a QoS %r message is not what a four-way handshake carries"
            % (message["qos"],))
    return message


def _body(message, packet_id, dup=False):
    """Stage 5's PUBLISH body for `message` under this handshake's id."""
    return stage_05.write_publish(message["topic"], message["payload"], 2,
                                  packet_id, message["retain"], dup)


class Sender:
    """Our side of an exactly-once delivery: an id in flight until its PUBCOMP."""

    def __init__(self, ids):
        """The `PacketIds` this sender takes its ids from."""
        if not isinstance(ids, stage_06.PacketIds):
            raise stage_01.ProtocolError(
                "a sender takes its ids from a PacketIds, not from %s"
                % (type(ids).__name__,))
        self._ids = ids
        self._order = []
        self._records = {}

    def start(self, message, now):
        """Take an id and write the first PUBLISH of the handshake, at `now`.

        An id taken for a message that cannot be written — a wildcard topic, a
        payload that is not bytes, a flag that is not a flag — is released again
        before the refusal leaves this method: a refusal spends no id.
        """
        message = _message(message)
        when = _tick(now, "the tick a PUBLISH goes out at")
        packet_id = self._ids.take()
        try:
            body = _body(message, packet_id)
        except stage_01.ProtocolError:
            self._ids.release(packet_id)
            raise
        self._order.append(packet_id)
        self._records[packet_id] = {"message": message, "state": _WAITING_REC,
                                    "sent_at": when}
        return packet_id, body

    def received(self, kind, packet_id, now):
        """The next body to write for an acknowledgement, or `None` when done.

        A PUBREC answers with the PUBREL body, moves the record to "waiting-comp"
        and starts that record's deadline at `now` — the tick the PUBREL goes out
        at, which is where the next re-send is measured from. A second PUBREC
        answers with the same PUBREL again and changes nothing else, the deadline
        restarting with it. A PUBCOMP releases the id and forgets the record — but
        only once the PUBREC has been seen, because that is where the id's life
        ends.
        """
        kind = _kind(kind)
        packet_id = _packet_id(packet_id, "an acknowledgement id")
        when = _tick(now, "the tick an acknowledgement arrives at")
        if packet_id not in self._records:
            raise stage_01.ProtocolError(
                "packet id %d is not in flight" % (packet_id,))
        record = self._records[packet_id]
        if kind == stage_01.PUBREC:
            record["state"] = _WAITING_COMP
            record["sent_at"] = when
            return write_pubrel(packet_id)
        if record["state"] != _WAITING_COMP:
            raise stage_01.ProtocolError(
                "packet id %d is %s, so a PUBCOMP does not acknowledge it"
                % (packet_id, record["state"]))
        self._release(packet_id)
        return None

    def records(self):
        """The deliveries in flight, in the order they started."""
        return tuple({"packet_id": packet_id,
                      "message": self._records[packet_id]["message"],
                      "state": self._records[packet_id]["state"]}
                     for packet_id in self._order)

    def due(self, now, deadline=4):
        """The records whose deadline has passed: `(packet_id, flags, body)` each.

        The deadline is the clock's, never a poll: a record whose `sent_at` is
        `deadline` ticks behind `now` comes back with the flags and the body to
        write again, and its `sent_at` restarts at `now`, so the same tick answers
        nothing twice. A PUBLISH re-send carries `DUP` with QoS 2 (`0b1100`); a
        PUBREL re-send carries exactly `PUBREL_FLAGS`, because DUP does not exist
        for a PUBREL in this format.
        """
        when = _tick(now, "now")
        if isinstance(deadline, bool) or not isinstance(deadline, int) or deadline < 1:
            raise stage_01.ProtocolError(
                "a deadline of %r is not a count of ticks (one or more)"
                % (deadline,))
        late = []
        for packet_id in self._order:
            record = self._records[packet_id]
            if when - record["sent_at"] < deadline:
                continue
            record["sent_at"] = when
            if record["state"] == _WAITING_REC:
                late.append((packet_id, _RESEND_FLAGS,
                             _body(record["message"], packet_id, dup=True)))
            else:
                late.append((packet_id, PUBREL_FLAGS, write_pubrel(packet_id)))
        return tuple(late)

    def _release(self, packet_id):
        """Let the id go and stop holding the record: the PUBCOMP's own work."""
        self._records.pop(packet_id)
        self._order.remove(packet_id)
        self._ids.release(packet_id)


class Receiver:
    """The other side: the id and the message held from the PUBLISH to the PUBREL."""

    def __init__(self):
        """A receiver holding nothing."""
        self._order = []
        self._held = {}

    def took(self, publish):
        """A PUBLISH arrived: `(PUBREC body, delivered or None)`.

        The message is held and acknowledged, and nothing is delivered here — the
        PUBREL is the only packet that delivers. An id already held is
        acknowledged again and keeps the message it already holds.
        """
        publish = _message(publish)
        packet_id = _packet_id(publish["packet_id"], "a PUBLISH id")
        if packet_id not in self._held:
            self._order.append(packet_id)
            self._held[packet_id] = publish
        return write_pubrec(packet_id), None

    def released(self, packet_id):
        """A PUBREL arrived: `(PUBCOMP body, the message once)`.

        An id this receiver does not hold — never seen, or already released — is
        answered with a PUBCOMP and delivers nothing.
        """
        packet_id = _packet_id(packet_id, "a PUBREL id")
        if packet_id not in self._held:
            return write_pubcomp(packet_id), None
        message = self._held.pop(packet_id)
        self._order.remove(packet_id)
        return write_pubcomp(packet_id), message

    def held(self):
        """How many ids are held, waiting for their PUBREL."""
        return len(self._held)


def write_pubrec(packet_id):
    """The PUBREC body: the packet id, two bytes big-endian, and nothing else.

    A bare acknowledgement has one body, and stage 6 owns it: this is stage 6's
    `write_ack` under PUBREC's number, with the id judged here first so a refusal
    says which of the three packets was being written. The fixed header is stage
    10's.
    """
    return stage_06.write_ack(stage_01.PUBREC,
                              _packet_id(packet_id, "a PUBREC id"))


def write_pubrel(packet_id):
    """The PUBREL body: the packet id, two bytes big-endian, and nothing else.

    The nibble that makes this packet a PUBREL rather than a PUBREC is
    `PUBREL_FLAGS` in the *fixed header*, which this writer never writes and a
    reader of bodies never sees.
    """
    return stage_06.write_ack(stage_01.PUBREL,
                              _packet_id(packet_id, "a PUBREL id"))


def write_pubcomp(packet_id):
    """The PUBCOMP body: the packet id, two bytes big-endian, and nothing else."""
    return stage_06.write_ack(stage_01.PUBCOMP,
                              _packet_id(packet_id, "a PUBCOMP id"))
