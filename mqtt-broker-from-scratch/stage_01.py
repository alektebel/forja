"""MQTT Broker From Scratch — stage 1: The fixed header and the variable-length integer.

Every packet in MQTT starts with the same two things: one byte that says what
kind of packet it is and which flags it carries, and a number that says how many
bytes follow. The number is not a fixed-width field. It is written seven bits at
a time, low group first, with the high bit set on every group but the last — so
a length of 5 is one byte and a length of 300 is two, and neither the reader nor
the writer may ever assume it knows how long the length itself is.

That is the whole stage, and it is the stage everything else stands on. A reader
that guesses at a length reads the rest of the session wrong: it eats the first
bytes of a payload as if they were a packet header, and it reports a frame that
was never sent. The two failures this stage exists to prevent are therefore
symmetrical — a short buffer called malformed (the stream simply has not got
there yet, which is the normal state of a reader between two ticks), and a peer's
impossible bytes accepted as a packet (a fifth group, a reserved type, a length
that never ends).

    CONNECT … DISCONNECT    the fourteen packet types, by their real numbers
    TYPE_NAMES              the same numbers as the names a refusal prints
    REQUIRED_FLAGS          per type: the low nibble it must carry, or None
    RESERVED_TYPES          the numbers no packet may have: 0 and 15
    MAX_REMAINING_LENGTH    268_435_455 — the largest four groups of seven bits carry
    ProtocolError           the family: bytes that can never be a frame
    Incomplete              the frame is not here yet; `.needed` says how many bytes more
    read_varint             (data, pos) -> (value, pos): one to four groups, low group first
    write_varint            (value) -> bytes: the shortest encoding, or a refusal naming the value
    read_header             (data, pos) -> (header, payload_pos): type, flags, length, size

`read_header` judges the packet as a whole: with the header whole but the body
short, the refusal's `.needed` is the body's own shortfall, which is the number a
reader waits for. A refusal names the offender — the byte that arrived, the four
bytes that could not be a length, the position outside the buffer — because a
message that says only "invalid packet" cannot be told apart from the bug it is
hiding.

DESIGN DECISION — why is `Incomplete` not a kind of `ProtocolError`?
Because the two answers have opposite consequences. A `ProtocolError` means these
bytes can never be a packet, and the only thing left to do with the stream is
close it; an `Incomplete` means the packet is on its way and the reader must wait,
consuming nothing. If they were one family, every caller would have to remember
which half it caught — and the first caller that forgets closes a healthy
connection or, worse, waits forever on a peer that is already wrong.

DESIGN DECISION — why does `read_header` report the body's shortfall rather than
just "not enough"?
Because the number it reports is the number the stream layer needs: with
`.needed` in hand, a reader that has to wait for bytes knows exactly how many,
and a check can assert that the answer changes as bytes arrive instead of
asserting that something failed. It is also the difference between a buffer that
is short and a length that is a lie: a body of 300 bytes announced and 297
arrived is three bytes away from a packet, and no amount of waiting turns a
malformed length into one.

DESIGN DECISION — why is the last group the one that says the integer has ended,
and not a separate length byte?
Because a separate length byte would have to be a fixed width, which is the whole
problem the encoding exists to avoid. The continuation bit makes the integer
self-ending: the reader stops when the high bit is clear, and the writer never
emits more groups than the value needs. A side effect is worth knowing: with at
most four groups, no legal encoding can reach a value above `MAX_REMAINING_LENGTH`
— the four-byte rule *is* the maximum, which is why the solution checks the rule
and not the sum.

DESIGN DECISION — why does `write_varint(0)` return one byte instead of none?
Because an empty encoding is a reader that never advances. A zero-length packet
is legal (`PINGREQ` is exactly two bytes, both of them the header), and the
shortest encoding of nothing is a single group with the high bit clear — the
smallest answer that still says "the length ended here".

TODO: implement
"""

CONNECT = 1
CONNACK = 2
PUBLISH = 3
PUBACK = 4
PUBREC = 5
PUBREL = 6
PUBCOMP = 7
SUBSCRIBE = 8
SUBACK = 9
UNSUBSCRIBE = 10
UNSUBACK = 11
PINGREQ = 12
PINGRESP = 13
DISCONNECT = 14

TYPE_NAMES = {
    1: "CONNECT",
    2: "CONNACK",
    3: "PUBLISH",
    4: "PUBACK",
    5: "PUBREC",
    6: "PUBREL",
    7: "PUBCOMP",
    8: "SUBSCRIBE",
    9: "SUBACK",
    10: "UNSUBSCRIBE",
    11: "UNSUBACK",
    12: "PINGREQ",
    13: "PINGRESP",
    14: "DISCONNECT",
}

REQUIRED_FLAGS = {
    1: 0,
    2: 0,
    3: None,
    4: 0,
    5: 0,
    6: 0b0010,
    7: 0,
    8: 0b0010,
    9: 0,
    10: 0b0010,
    11: 0,
    12: 0,
    13: 0,
    14: 0,
}

RESERVED_TYPES = (0, 15)

MAX_REMAINING_LENGTH = 268_435_455


class ProtocolError(ValueError):
    """A peer's bytes that can never be a frame, named by what arrived instead."""


class Incomplete(ValueError):
    """A frame that has not arrived yet, with `.needed` bytes still to come.

    Not a kind of `ProtocolError`: a stream may split anywhere, so a buffer that
    stops in the middle of a length is the normal state of a reader between two
    ticks, not a peer's mistake.
    """

    def __init__(self, needed):
        self.needed = needed
        super().__init__("needs at least %d more byte%s"
                         % (needed, "" if needed == 1 else "s"))


def read_varint(data, pos=0):
    """The variable-length integer at `pos`, as `(value, pos_after)`.

    One to four groups of seven bits, low group first, the high bit set on every
    group but the last — so the last group is what says the integer has ended. A
    group that continues past the fourth byte can never be a remaining length,
    and neither can a buffer that ends while a group is continued: the first is
    a `ProtocolError` naming the four bytes that arrived, the second is an
    `Incomplete` that needs one more byte — the one that could end it.
    """
    raise NotImplementedError("stage 1: implement read_varint()")


def write_varint(value):
    """`value` as the shortest variable-length integer, seven bits per byte.

    Zero is one byte (`b"\\x00"`), not none: a length of nothing is still a
    length, and a reader that treats an empty encoding as an answer advances no
    position and reads the same bytes forever.
    """
    raise NotImplementedError("stage 1: implement write_varint()")


def read_header(data, pos=0):
    """The fixed header at `pos`, as `(header, payload_pos)`.

    `header` carries four keys in order — `type`, `flags`, `length` (the
    remaining length, the body's own byte count) and `size` (the header's) — and
    `payload_pos` is where the body starts. The type's low nibble is judged here
    too: `REQUIRED_FLAGS` says what each type must carry (`0b0010` for PUBREL,
    SUBSCRIBE and UNSUBSCRIBE, zero for the types that carry none, and `None` for
    PUBLISH, whose nibble is its payload's own shape), and a byte that disagrees
    is a `ProtocolError` naming the type, the flags it carried and the flags it
    owed. The buffer is judged as a whole packet: with the header whole but the
    body short the refusal's `.needed` is the body's shortfall exactly, so a
    reader that waits for that many bytes never reads half a packet twice.
    """
    raise NotImplementedError("stage 1: implement read_header()")
