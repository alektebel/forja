"""MQTT Broker From Scratch — stage 7: QoS 2, the four-way handshake.

Stage 6 bought "at least once" with two packets: a PUBLISH and an acknowledgement.
The price was duplication, and the licence was that a duplicate is always better
than a loss. QoS 2 buys the other promise — "exactly once" — and pays for it with
four packets and two round trips: PUBLISH, PUBREC, PUBREL, PUBCOMP. The message
itself travels in the first of them; the other three exist only so that both sides
can agree, without any doubt, that it arrived *and* that the handshake about it is
over.

That agreement is a state machine with an id in the middle of it, and every hard
part of this stage is about when that id may move. The sender's id is in flight
from the moment it is taken until the PUBCOMP — not until the PUBREC, not until
the PUBREL was written. The receiver holds both the id **and the message** from
the PUBLISH until the PUBREL, and it delivers the message at exactly one instant:
when the PUBREL arrives. Not at the PUBLISH — a receiver cannot tell a first
transmission from a re-send by looking at it, and a peer that reconnects may
re-send without the DUP bit set at all, so delivering on sight turns QoS 2 into
QoS 1 with two extra packets and a lie in its name. Not at the PUBREC either: the
receipt says "I have it", and the PUBREL says "I am done with this id" — the
message is released by the second of those, and by nothing else.

The two sides are therefore not symmetric, and this stage keeps them apart. A
`Sender` takes ids from stage 6's `PacketIds` (the stage that owns the rule that
an id in flight is not handed out again), records what it sent, and answers an
acknowledgement with the next body to write — `None` when the handshake is over.
A `Receiver` holds what it was told, acknowledges each PUBLISH including the
re-sends, and hands the message over once, when the PUBREL arrives. Both are
driven by the caller (stage 10), never by a poll: the tick is the caller's,
handed in with every packet it moves — `start`, `received` — and read by `due`,
which answers a record whose deadline has passed, one re-send per deadline, `DUP`
on a re-sent PUBLISH and never on a PUBREL.

    PUBREL_FLAGS     0b0010: the low nibble a PUBREL's own type byte must carry
    HANDSHAKE_KEYS   ("packet_id", "message", "state"): one delivery in flight, in order
    Sender(ids)          our side: take an id, PUBLISH, PUBREL, release at PUBCOMP
    Sender.start     (message, now) -> (packet_id, PUBLISH body); the id is taken, in flight
    Sender.received  (kind, packet_id, now) -> the next body to write, or None when done
    Sender.records   () -> HANDSHAKE_KEYS records, in the order they started
    Sender.due       (now, deadline=4) -> ((packet_id, flags, body), ...) to write again
    Receiver()           the other side: the id and the message held across the handshake
    Receiver.took    (publish) -> (PUBREC body, delivered or None): never delivered here
    Receiver.released (packet_id) -> (PUBCOMP body, the message once)
    Receiver.held    () -> how many ids are held, waiting for their PUBREL
    write_pubrec     (packet_id) -> bytes: the PUBREC body
    write_pubrel     (packet_id) -> bytes: the PUBREL body
    write_pubcomp    (packet_id) -> bytes: the PUBCOMP body

Every `write_*` here answers with the packet's **body** — the two bytes of the
packet id and nothing else. The type byte, the low nibble and the length that
frame it are stage 1's numbers and stage 10's job: a body reader never sees a
nibble, which is why `PUBREL_FLAGS` is a constant this stage exports for the
framing rather than a check any of its own functions can make.

A refusal in this stage is a shape that can never be part of a handshake — an
acknowledgement whose kind is not one of the two that belong to a QoS 2 delivery,
an id that is not in flight, an id that cannot be a packet id, a message that is
not QoS 2. A *question* is answered with a value: whether an id is held, and what
to write next, are values, and a PUBREL for an id the receiver does not hold is
answered with a PUBCOMP rather than refused, because the tail of a handshake whose
state was rebuilt is normal on this wire.

DESIGN DECISION — why is the sender's id in flight until the PUBCOMP, and not
until the PUBREC?
Because the handshake is not over at the receipt. Releasing the id at the PUBREC
would let the very next message be handed the same number while the peer is still
waiting for the PUBREL of the previous one — and the peer's PUBREL, then
PUBCOMP, would arrive for an id that now means something else. The four packets
are four precisely so that the id's life has one end, and that end is the last of
them.

DESIGN DECISION — why is the message delivered at the PUBREL, and never at the
PUBLISH or the PUBREC?
Because only the PUBREL resolves the one question the receiver is stuck on: is
this PUBLISH the first transmission or a re-send? The DUP bit is a hint and not an
answer — a client that reconnects may send the message again with DUP clear, and a
receiver that was rebuilt has no memory of the first one either way. Delivering at
the PUBLISH is the whole of QoS 1 plus two packets and a mistaken name; holding
the message until the PUBREL is exactly once, and a duplicate PUBLISH with an id
already held is free to be acknowledged again, because saying "I have it" twice
costs nothing while delivering it twice cannot be undone.

DESIGN DECISION — why is a PUBREL for an unknown id answered with a PUBCOMP rather
than refused?
Because this wire allows the tail of a handshake to arrive after the head was
forgotten. A receiver whose state was rebuilt — a new socket, a restarted process
— can be handed a PUBREL for an id it does not hold, and its peer is behaving
perfectly: it is finishing what it started. A refusal would leave that peer
re-sending the PUBREL for ever, and the one packet that can end the handshake is
the PUBCOMP, which carries no claim about the message at all. The receiver's
answer is a value, not a verdict about the peer.

DESIGN DECISION — why is a duplicate PUBREC answered with the same PUBREL again,
and not with a new handshake?
Because the duplicate almost always means the first PUBREL was lost, and the only
useful answer to "did you get my receipt?" is the same PUBREL over the same id. A
sender that treated the second PUBREC as the start of a fresh handshake would take
a second id, put a second copy of the same message in flight, and leave the
receiver holding an id that will never be released.

DESIGN DECISION — why does `due` hand back `(packet_id, flags, body)` triples
rather than the ids alone?
Because the flags are where the difference between a first transmission and a
re-send actually lives: a re-sent PUBLISH carries DUP (with QoS 2, so `0b1100`),
while a PUBREL is never re-sent with DUP — its low nibble is fixed at
`PUBREL_FLAGS` = `0b0010`, and the DUP bit means nothing in a packet that carries
no message. Returning the ids alone would leave the caller to remember which
packet it is re-sending and what nibble that carries; returning the flags puts the
rule where the packet is chosen, and makes "the re-send that forgot its DUP" and
"the PUBREL that grew one" both visible to a test.

TODO: implement
"""

import stage_01
import stage_05
import stage_06

PUBREL_FLAGS = 0b0010

HANDSHAKE_KEYS = ("packet_id", "message", "state")


class Sender:
    """Our side of an exactly-once delivery: an id in flight until its PUBCOMP.

    Built with the `PacketIds` it takes from — the stage 6 object that owns the
    rule that an id in flight is not handed out again. The clock is the caller's,
    handed in with every packet: the tick a PUBLISH goes out at is where that
    PUBLISH's deadline starts, and the tick a PUBREC arrives at is where the
    PUBREL it triggers starts its own. The per-handshake timestamps are this
    object's private bookkeeping, like a free list is `PacketIds`'.
    """

    def start(self, message, now):
        """Take an id and write the first PUBLISH of the handshake, at `now`.

        `message` is stage 5's publish dict for a QoS 2 delivery. The id comes
        from the `PacketIds` this sender was built with, the delivery goes in
        flight as a "waiting-rec" record whose deadline starts at `now`, and the
        answer is `(packet_id, PUBLISH body)` — the body alone; the type byte and
        the nibble that frame it are stage 10's. A message that is not a QoS 2
        publish dict is refused, naming what arrived, and a `now` that is not a
        tick is refused too — both **before** an id is spent. A message the
        writer itself cannot write — a wildcard topic, a payload that is not
        bytes, a flag that is not a flag — spends no id either: the id taken for
        it is released again before the refusal leaves.
        """
        raise NotImplementedError("stage 7: implement Sender.start()")

    def received(self, kind, packet_id, now):
        """The next body to write for an acknowledgement, or `None` when done.

        A PUBREC moves the record to "waiting-comp", starts its deadline at `now`
        — the tick the PUBREL it answers with goes out at — and answers with the
        PUBREL body; a second PUBREC for the same id answers with the same PUBREL
        again, deadline and all, and changes nothing else. A PUBCOMP releases the
        id and forgets the record. A kind that is not one of the two
        acknowledgements a QoS 2 delivery has, a `PUBCOMP` for a record still
        waiting for its PUBREC, an id that is not in flight and a `now` that is
        not a tick are each refused by name.
        """
        raise NotImplementedError("stage 7: implement Sender.received()")

    def records(self):
        """The deliveries in flight, in the order they started.

        Each is a dict with the three keys of `HANDSHAKE_KEYS`, in that order: the
        packet id, the message as it was handed in, and the state — "waiting-rec"
        until the PUBREC arrives, "waiting-comp" until the PUBCOMP releases it.
        """
        raise NotImplementedError("stage 7: implement Sender.records()")

    def due(self, now, deadline=4):
        """The records whose deadline has passed, as `(packet_id, flags, body)`.

        In the order they started, each with the flags and the body to write
        again: a "waiting-rec" record re-sends its PUBLISH with `DUP` set and QoS
        2 (`0b1100`), a "waiting-comp" record re-sends its PUBREL with exactly
        `PUBREL_FLAGS` and no DUP. The deadline of each record that comes back
        restarts at `now`, so a second `due` on the same tick answers nothing —
        one re-send per deadline, and never one per step. A record one tick short
        of its deadline stays put.
        """
        raise NotImplementedError("stage 7: implement Sender.due()")


class Receiver:
    """The other side: the id and the message held from the PUBLISH to the PUBREL.

    Nothing is delivered here until `released` is told the handshake is over, and
    an id this receiver does not hold is answered with a PUBCOMP rather than
    refused: a handshake may lose its head and keep its tail.
    """

    def took(self, publish):
        """A PUBLISH arrived: `(PUBREC body, delivered or None)`.

        The message is held and acknowledged, and `delivered` is `None` — the
        PUBREL is the only thing that delivers. A publish with an id already held
        is acknowledged again and changes nothing: the id is held once, and the
        message it will deliver is the first one. A publish that is not a QoS 2
        publish dict is refused by name.
        """
        raise NotImplementedError("stage 7: implement Receiver.took()")

    def released(self, packet_id):
        """A PUBREL arrived: `(PUBCOMP body, the message once)`.

        The id is dropped and its message handed over exactly once; a second
        PUBREL for the same id is answered with another PUBCOMP and delivers
        nothing, and so is a PUBREL for an id this receiver never held. A packet
        id that cannot be an id is refused by name.
        """
        raise NotImplementedError("stage 7: implement Receiver.released()")

    def held(self):
        """How many ids are held, waiting for their PUBREL."""
        raise NotImplementedError("stage 7: implement Receiver.held()")


def write_pubrec(packet_id):
    """The PUBREC body: the packet id, two bytes big-endian, and nothing else.

    Nothing but a packet id can be refused by this writer, and the refusal names
    what arrived. The fixed header is stage 10's.
    """
    raise NotImplementedError("stage 7: implement write_pubrec()")


def write_pubrel(packet_id):
    """The PUBREL body: the packet id, two bytes big-endian, and nothing else.

    The nibble that makes this packet a PUBREL rather than a PUBREC is
    `PUBREL_FLAGS` in the *fixed header*, which this writer never writes and a
    reader of bodies never sees.
    """
    raise NotImplementedError("stage 7: implement write_pubrel()")


def write_pubcomp(packet_id):
    """The PUBCOMP body: the packet id, two bytes big-endian, and nothing else."""
    raise NotImplementedError("stage 7: implement write_pubcomp()")
