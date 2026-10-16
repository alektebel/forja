"""MQTT Broker From Scratch — stage 6: QoS 1, the packet id, and the PUBACK.

Quality of service 1 is one promise: this message arrives at least once. The
whole cost of that promise is a packet id kept busy. The sender takes an id from
its own space, puts the message on the wire under that id, and may not hand the
id to anything else until the PUBACK carrying it comes back — because the
acknowledgement is the only thing that says the other end has the message, and
an id reused too early makes two messages look like one: the PUBACK that should
have freed the first frees the second instead, and the first is lost with nobody
counting it.

The other half of the stage is what a sender does when the PUBACK is late.
Nothing here waits. The clock is the caller's — a tick at a time, handed to the
table with every question and every act — and the sender's whole memory of when
a message went out is one number per record. A record whose `sent_at` plus its
deadline has been reached is sent again with DUP set, and its deadline starts
over from the tick of that re-send, so a late re-send never becomes an early one:
one re-send per deadline, not one per tick. The first transmission never carries
DUP and a re-send always does — that is what DUP is for, and it is the reason a
record counts `attempts` instead of storing a flag: a flag has to be set and
cleared by somebody who remembers, and a count cannot be wrong about whether this
is the first time.

Every `write_*` here answers the packet's *body* and never a whole packet.
`write_puback(7)` is `b"\\x00\\x07"` and nothing else; the type byte and the
variable-length integer that frame it are stage 1's `write_varint`, and stage 10
is the only place a body is framed. The readers mirror it: `read_ack` is handed a
body, so it never sees the type byte — all four bare acknowledgements carry
nothing but the id, and which of the four arrived is a fact the dispatcher read
out of the fixed header.

    MIN_PACKET_ID, MAX_PACKET_ID   1 and 65_535: the whole of a sender's id space
    DEFAULT_DEADLINE               four ticks between a send and its re-send
    ACK_FLAGS                      0: the low nibble of a bare acknowledgement
    INFLIGHT_KEYS                  the six keys of one in-flight record, in order
    PacketIds                      the sender's id space: take, release, size
    read_ack                       (data, pos) -> (packet_id, pos): the id an ack carries
    write_puback                   (packet_id) -> bytes: the body of a PUBACK
    write_ack                      (kind, packet_id) -> bytes: the same body, checked
    InFlight                       the messages sent and not yet acknowledged

DESIGN DECISION — why is an id in flight until the acknowledgement rather than
until the send?
Because the acknowledgment is the only evidence that the message arrived. An id
freed at the send can name two different messages inside one deadline: the first
is still on the wire, its PUBACK has not come, and the second is handed the same
two bytes — so the PUBACK that does arrive frees the wrong message and the first
one disappears. "At least once" means at least one attempt has to be *answered*
before the id is anybody else's.

DESIGN DECISION — why does the first transmission carry no DUP and every re-send
carry it?
Because DUP does not mean "this message is a duplicate"; it means "this packet id
has been sent to you before". A receiver that sees it knows the message may
already have been delivered and that its own earlier acknowledgement was lost; a
receiver that never sees it on a second transmission cannot tell a re-send from a
new message, and delivers the payload twice while believing it is being careful.
The bit only means anything in that direction, so the record counts `attempts`:
every count above one is a re-send, and a record that has not been re-sent cannot
carry the bit by accident.

DESIGN DECISION — why does the table not own a clock?
Because the only clock in a deterministic run is the caller's, and a table that
remembered the last tick it was shown would answer differently in two runs that
showed it the same ticks in a different order — and no test could say which run
was right. So `due(now)` is a question: it hands back the records whose deadline
has been reached at `now` and changes nothing, which is why it may be asked
twice. `again(packet_id, now)` is the act of re-sending, and it is the only thing
that moves a deadline.

DESIGN DECISION — why is a released id handed out again before an id that was
never used?
Because a space with a bottom edge is a space whose use is predictable. Ids are
handed out from the bottom upwards, and releasing one puts it back at the bottom
of the space, so a sender that keeps a handful of messages alive reuses the same
handful of ids for the whole run instead of handing out id after id as it goes.
Two runs that do the same work take the same ids in the same order — which is
what makes a trace of one run worth comparing against another.

DESIGN DECISION — why does `settle` refuse an id it is not holding?
Because an acknowledgement for an id nobody waits on means exactly one of two
things: a peer acknowledging a message it never received (or one whose PUBACK we
have already acted on), or our own table having lost the record. Neither is worth
guessing about, and freeing an id on a stranger's word would hand a packet id to
a new message while the old one is still in flight, which is the one thing this
stage exists to prevent. The same refusal covers the second acknowledgement of a
message already settled: the promise is kept once, and an id is not freed twice.

TODO: implement
"""

import stage_01

MIN_PACKET_ID = 1
MAX_PACKET_ID = 65_535
DEFAULT_DEADLINE = 4

ACK_FLAGS = 0

INFLIGHT_KEYS = ("packet_id", "topic", "payload", "qos", "sent_at", "attempts")


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
        raise NotImplementedError("stage 6: implement PacketIds.take()")

    def release(self, packet_id):
        """Hand `packet_id` back, and answer it.

        A released id goes back to the bottom edge of the space, where the next
        take looks first, so the cursor never sits above an id that is free. A
        stranger's id, a second release of the same id, and an id that is not a
        two-byte int are each refused by name: the second release of an id would
        free somebody else's.
        """
        raise NotImplementedError("stage 6: implement PacketIds.release()")

    def in_flight(self):
        """The ids in flight, in the order they were taken.

        A tuple, not the space's own bookkeeping: a caller may keep it, and two
        runs of one workload answer the same sequence because the order is the
        order of the takes.
        """
        raise NotImplementedError("stage 6: implement PacketIds.in_flight()")

    def free(self):
        """How many ids the space can still hand out.

        The whole space minus the ones in flight, so it reaches zero exactly when
        `take` starts refusing.
        """
        raise NotImplementedError("stage 6: implement PacketIds.free()")


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
    raise NotImplementedError("stage 6: implement read_ack()")


def write_puback(packet_id):
    """The *body* of a PUBACK: the packet id, two bytes big-endian.

    The body alone — `b"\\x00\\x07"` for 7 is the whole answer. The type byte
    (`0x40`) and the remaining length (stage 1's `write_varint`) are what frame
    it, and they are written where a whole packet is written. An id outside
    1…65_535, or one that is not an int at all, is refused naming what arrived: a
    `bool` is not an id, however much it looks like one.
    """
    raise NotImplementedError("stage 6: implement write_puback()")


def write_ack(kind, packet_id):
    """The *body* of a bare acknowledgement of type `kind`.

    All four bare acknowledgements carry the same body, so this answers exactly
    what `write_puback` answers — and refuses any other kind, naming it: a
    packet whose body is more than an id (a PUBLISH with its topic, a SUBACK
    with its codes) is a call that has confused a body with a packet. The nibble
    that frames the answer belongs to the framer: PUBACK, PUBREC and PUBCOMP
    travel under `ACK_FLAGS`, and PUBREL under the `0b0010` stage 1 requires.
    """
    raise NotImplementedError("stage 6: implement write_ack()")


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
        raise NotImplementedError("stage 6: implement InFlight.add()")

    def settle(self, packet_id):
        """The acknowledgement for `packet_id`: take the record, free the id.

        The record leaves the table and, when the table was built over a space,
        the id goes back to it in the same breath: the two say the same thing —
        this message is done. An id the table is not holding is refused by name,
        and so is a *second* settle of an id already acknowledged: the record is
        gone and nothing is released, since an acknowledgement that frees
        somebody else's id is the failure this refusal exists to prevent.
        """
        raise NotImplementedError("stage 6: implement InFlight.settle()")

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
        raise NotImplementedError("stage 6: implement InFlight.due()")

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
        raise NotImplementedError("stage 6: implement InFlight.again()")

    def records(self):
        """The records in flight, in the order they were added.

        A tuple of the records the table holds: a caller may read them, and the
        order is the order of the sends, so two runs of one workload compare
        equal.
        """
        raise NotImplementedError("stage 6: implement InFlight.records()")
