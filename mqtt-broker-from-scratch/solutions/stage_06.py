"""MQTT Broker From Scratch — stage 6: QoS 1, the packet id, and the PUBACK.

See `stage_06.py` for the surface and the design decisions; this is the id space,
the two bytes of an acknowledgement, and the table that decides when a message
goes out again.
"""

import stage_01

MIN_PACKET_ID = 1
MAX_PACKET_ID = 65_535
DEFAULT_DEADLINE = 4

ACK_FLAGS = 0

INFLIGHT_KEYS = ("packet_id", "topic", "payload", "qos", "sent_at", "attempts")

_BARE_ACKS = (stage_01.PUBACK, stage_01.PUBREC, stage_01.PUBREL, stage_01.PUBCOMP)

_ID_SPACE = MAX_PACKET_ID - MIN_PACKET_ID + 1


def _buffer(data, what):
    """The buffer as bytes, or a refusal naming what was handed in instead."""
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    raise stage_01.ProtocolError("%s must be bytes, not %s"
                                 % (what, type(data).__name__))


def _position(data, pos):
    """A position inside `data`, or a refusal naming the position and the size."""
    if isinstance(pos, bool) or not isinstance(pos, int):
        raise stage_01.ProtocolError("a position must be an int, not %r" % (pos,))
    if not 0 <= pos <= len(data):
        raise stage_01.ProtocolError("a position of %d in %d bytes"
                                     % (pos, len(data)))
    return pos


def _packet_id(packet_id, what="a packet id"):
    """A packet id in 1…65_535, or a refusal naming what arrived instead."""
    if isinstance(packet_id, bool) or not isinstance(packet_id, int):
        raise stage_01.ProtocolError("%s must be an int, not %s"
                                     % (what, type(packet_id).__name__))
    if not MIN_PACKET_ID <= packet_id <= MAX_PACKET_ID:
        raise stage_01.ProtocolError("%s of %d is not between %d and %d"
                                     % (what, packet_id, MIN_PACKET_ID,
                                        MAX_PACKET_ID))
    return packet_id


def _tick(now, what):
    """A tick at or after zero, or a refusal naming what arrived instead."""
    if isinstance(now, bool) or not isinstance(now, int):
        raise stage_01.ProtocolError("%s must be an int, not %s"
                                     % (what, type(now).__name__))
    if now < 0:
        raise stage_01.ProtocolError("%s of %d is before the clock started"
                                     % (what, now))
    return now


def _deadline(deadline):
    """A deadline of at least one tick, or a refusal naming what arrived."""
    if isinstance(deadline, bool) or not isinstance(deadline, int):
        raise stage_01.ProtocolError("a deadline must be an int, not %s"
                                     % (type(deadline).__name__,))
    if deadline < 1:
        raise stage_01.ProtocolError("a deadline of %d ticks is no deadline at all"
                                     % (deadline,))
    return deadline


def _message(message):
    """The three things a message in flight needs, or a refusal naming the one lost."""
    if not isinstance(message, dict):
        raise stage_01.ProtocolError("a message must be a dict, not %s"
                                     % (type(message).__name__,))
    for key in ("topic", "payload", "qos"):
        if key not in message:
            raise stage_01.ProtocolError("a message in flight with no %r in it"
                                         % (key,))
    return message


class PacketIds:
    """The sender's own packet id space: 1…65_535, handed out from the bottom up.

    An id is in flight from the moment it is taken until the acknowledgement that
    names it releases it, and a space that has handed out everything it has is a
    sender that must wait before it can send again — the refusal is backpressure,
    not a broken peer.
    """

    def __init__(self):
        """Every id free, at the bottom of the space, with none handed out yet."""
        self._held = {}
        self._next = MIN_PACKET_ID

    def take(self):
        """An id no message is using, or a refusal when every id is in flight.

        Ids are handed out from the bottom of the space upwards, skipping the
        ones in flight, so the answer is an int in 1…65_535 that nothing else is
        already waiting on. A space that has handed out all of them has no answer
        left, and the refusal names the space it exhausted — which is also what
        keeps the cursor inside the space: it can only walk up over ids that are
        in flight, and a cursor at the last id with nothing free below it is a
        full space, refused above.
        """
        if len(self._held) >= _ID_SPACE:
            raise stage_01.ProtocolError("no packet id is free: all %d ids are in "
                                         "flight" % (_ID_SPACE,))
        while self._next in self._held:
            self._next += 1
        packet_id = self._next
        self._held[packet_id] = packet_id
        return packet_id

    def release(self, packet_id):
        """Hand `packet_id` back, and answer it.

        A released id goes back to the bottom edge of the space, where the next
        take looks first, so the cursor never sits above an id that is free. A
        stranger's id, a second release of the same id, and an id that is not a
        two-byte int are each refused by name: the second release of an id would
        free somebody else's.
        """
        packet_id = _packet_id(packet_id)
        if packet_id not in self._held:
            raise stage_01.ProtocolError("packet id %d is not in flight"
                                         % (packet_id,))
        del self._held[packet_id]
        if packet_id < self._next:
            self._next = packet_id
        return packet_id

    def in_flight(self):
        """The ids in flight, in the order they were taken.

        A tuple, not the space's own bookkeeping: a caller may keep it, and two
        runs of one workload answer the same sequence because the order is the
        order of the takes.
        """
        return tuple(self._held)

    def free(self):
        """How many ids the space can still hand out.

        The whole space minus the ones in flight, so it reaches zero exactly when
        `take` starts refusing.
        """
        return _ID_SPACE - len(self._held)


def read_ack(data, pos=0):
    """The packet id a bare acknowledgement carries, as `(packet_id, pos_after)`.

    `data` is the packet's body, exactly: PUBACK, PUBREC, PUBREL and PUBCOMP
    carry nothing but the id, so the body is two bytes and the type byte is the
    dispatcher's business — it read the type out of the fixed header, and this
    reader never sees it. The id is big-endian and non-zero, because zero is the
    id a QoS 0 publish would have if it had one; a body that stops inside the id
    is an `Incomplete` needing the bytes that have not arrived, and a byte left
    over after the id is refused naming the count, since the body's length and
    its contents have to agree.
    """
    data = _buffer(data, "the buffer an acknowledgement is read from")
    pos = _position(data, pos)
    have = len(data) - pos
    if have < 2:
        raise stage_01.Incomplete(2 - have)
    packet_id = (data[pos] << 8) | data[pos + 1]
    pos += 2
    if not MIN_PACKET_ID <= packet_id <= MAX_PACKET_ID:
        raise stage_01.ProtocolError(
            "a packet id of %d is not between %d and %d (the two bytes were %r)"
            % (packet_id, MIN_PACKET_ID, MAX_PACKET_ID, data[pos - 2:pos]))
    if pos != len(data):
        raise stage_01.ProtocolError(
            "a trailing byte after the packet id (%d bytes of body, %d read)"
            % (len(data), pos))
    return packet_id, pos


def write_puback(packet_id):
    """The *body* of a PUBACK: the packet id, two bytes big-endian.

    The body alone — `b"\\x00\\x07"` for 7 is the whole answer. The type byte
    (`0x40`) and the remaining length (stage 1's `write_varint`) are what frame
    it, and they are written where a whole packet is written. An id outside
    1…65_535, or one that is not an int at all, is refused naming what arrived: a
    `bool` is not an id, however much it looks like one.
    """
    packet_id = _packet_id(packet_id)
    return bytes([packet_id >> 8, packet_id & 0xFF])


def write_ack(kind, packet_id):
    """The *body* of a bare acknowledgement of type `kind`.

    All four bare acknowledgements carry the same body, so this answers exactly
    what `write_puback` answers — and refuses any other kind, naming it: a
    packet whose body is more than an id (a PUBLISH with its topic, a SUBACK
    with its codes) is a call that has confused a body with a packet. The nibble
    that frames the answer belongs to the framer: PUBACK, PUBREC and PUBCOMP
    travel under `ACK_FLAGS`, and PUBREL under the `0b0010` stage 1 requires.
    """
    if kind not in _BARE_ACKS:
        raise stage_01.ProtocolError("packet type %r is not one of the bare "
                                     "acknowledgements %r" % (kind, _BARE_ACKS))
    return write_puback(packet_id)


class InFlight:
    """The messages that have been sent and whose acknowledgement has not come.

    A record is a plain dict of the six keys of `INFLIGHT_KEYS`, in that order:
    the id the message is waited on, the topic, payload and QoS it is, the tick
    it last went out at, and how many times it has gone out. `attempts` is the
    whole of DUP's state — one is the first transmission and carries no duplicate
    flag, anything above one is a re-send and carries it — so a record cannot be
    re-sent without the count moving, nor the count move without a re-send.

    The table is built over the `PacketIds` its ids come from when its caller has
    one, and `settle` is what gives an id back: a message in flight is an id in
    flight, so the two objects are two halves of one rule and the table closes
    the loop it can see. Built over nothing — `InFlight()`, the ids handed in at
    `add` — it records the flight and leaves the releasing to its caller, because
    a space it cannot see is a space it must not guess at.
    """

    def __init__(self, ids=None):
        """A table over the id space its ids come from, or over the records alone."""
        if ids is not None and not isinstance(ids, PacketIds):
            raise stage_01.ProtocolError("an id space must be a PacketIds, not %s"
                                         % (type(ids).__name__,))
        self._ids = ids
        self._records = {}

    def add(self, message, packet_id, now):
        """Put `message` in flight under `packet_id`, and answer its record.

        `message` is what is being sent — a dict with at least `topic`, `payload`
        and `qos` in it; anything else it carries (a retain flag, a DUP bit from
        some other order of events) is not this table's business. The record
        starts with `sent_at` at `now`, the tick the caller says this first
        transmission went out at, because the clock is the caller's and the table
        has none. `attempts` starts at one: nothing has been re-sent yet, so the
        record carries no duplicate flag. A message that is not a dict, one
        missing any of the three keys, a packet id outside 1…65_535 and a tick
        that is not a tick are each refused by name — and an id already in flight
        is refused too, because one id waits on one message.
        """
        packet_id = _packet_id(packet_id)
        now = _tick(now, "the tick a message goes out at")
        message = _message(message)
        if packet_id in self._records:
            raise stage_01.ProtocolError("packet id %d is already in flight"
                                         % (packet_id,))
        record = {"packet_id": packet_id, "topic": message["topic"],
                  "payload": message["payload"], "qos": message["qos"],
                  "sent_at": now, "attempts": 1}
        self._records[packet_id] = record
        return record

    def settle(self, packet_id):
        """The acknowledgement for `packet_id`: take the record, free the id.

        The record leaves the table and, when the table was built over a space,
        the id goes back to it in the same breath: the two say the same thing —
        this message is done. An id the table is not holding is refused by name,
        and so is a *second* settle of an id already acknowledged: the record is
        gone and nothing is released, since an acknowledgement that frees
        somebody else's id is the failure this refusal exists to prevent.
        """
        record = self._record_for(packet_id)
        if self._ids is not None:
            self._ids.release(record["packet_id"])
        del self._records[record["packet_id"]]
        return record

    def due(self, now, deadline=DEFAULT_DEADLINE):
        """The records whose deadline has been reached at `now`, in added order.

        A record is due when `now` has reached its `sent_at` plus `deadline`; the
        tick itself counts, because a deadline of four ticks means four ticks of
        silence are allowed and the fifth tick is late. The question changes
        nothing — a re-send is `again` — so a caller that asks twice before doing
        anything gets the same answer twice. A deadline below one tick is refused
        naming it: a deadline of nothing is every message due on every tick,
        which is the busy-wait this stage is written against.
        """
        now = _tick(now, "the tick a re-send is decided at")
        deadline = _deadline(deadline)
        return tuple(record for record in self._records.values()
                     if now >= record["sent_at"] + deadline)

    def again(self, packet_id, now):
        """The record for `packet_id` after a re-send: same id, fresh deadline.

        `sent_at` moves to `now` and `attempts` goes up by one, so from here on
        the record is a duplicate — DUP set on the wire — and its next deadline
        is measured from *this* send, which is what makes a re-send one per
        deadline rather than one per tick. The id is not touched: a re-send is
        the same message, and taking a fresh id would leave the first one in
        flight, waiting for an acknowledgement that is already on its way. An id
        the table is not holding is refused by name, and nothing else about the
        record changes.
        """
        now = _tick(now, "the tick a re-send goes out at")
        record = self._record_for(packet_id)
        record["sent_at"] = now
        record["attempts"] += 1
        return record

    def records(self):
        """The records in flight, in the order they were added.

        A tuple of the records the table holds: a caller may read them, and the
        order is the order of the sends, so two runs of one workload compare
        equal.
        """
        return tuple(self._records.values())

    def _record_for(self, packet_id):
        """The record waiting on `packet_id`, or a refusal naming the id."""
        packet_id = _packet_id(packet_id)
        if packet_id not in self._records:
            raise stage_01.ProtocolError("packet id %d is not in flight"
                                         % (packet_id,))
        return self._records[packet_id]
