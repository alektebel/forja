"""MQTT Broker From Scratch — stage 1: The fixed header and the variable-length integer.

See `stage_01.py` for the surface and the design decisions; this is the reader
every other stage's bytes go through first.
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


def _as_bytes(data, what):
    """The buffer as bytes, or a refusal naming what was handed in instead."""
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    raise ProtocolError("%s must be bytes, not %s" % (what, type(data).__name__,))


def _as_pos(data, pos):
    """A position inside `data`, or a refusal naming the position and the size."""
    if isinstance(pos, bool) or not isinstance(pos, int):
        raise ProtocolError("a position must be an int, not %r" % (pos,))
    if not 0 <= pos <= len(data):
        raise ProtocolError("a position of %d in %d bytes" % (pos, len(data)))
    return pos


def read_varint(data, pos=0):
    """The variable-length integer at `pos`, as `(value, pos_after)`.

    One to four groups of seven bits, low group first, the high bit set on every
    group but the last — so the last group is what says the integer has ended. A
    group that continues past the fourth byte can never be a remaining length,
    and neither can a buffer that ends while a group is continued: the first is
    a `ProtocolError` naming the four bytes that arrived, the second is an
    `Incomplete` that needs one more byte — the one that could end it.
    """
    data = _as_bytes(data, "the buffer a remaining length is read from")
    pos = _as_pos(data, pos)
    value = 0
    shift = 0
    start = pos
    while True:
        if pos >= len(data):
            raise Incomplete(1)
        group = data[pos]
        pos += 1
        value |= (group & 0x7F) << shift
        if not group & 0x80:
            return value, pos
        if shift == 21:
            raise ProtocolError(
                "a remaining length of more than four bytes (they were %r)"
                % (data[start:pos],))
        shift += 7


def write_varint(value):
    """`value` as the shortest variable-length integer, seven bits per byte.

    Zero is one byte (`b"\\x00"`), not none: a length of nothing is still a
    length, and a reader that treats an empty encoding as an answer advances no
    position and reads the same bytes forever.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolError("a remaining length must be an int, not %s"
                            % (type(value).__name__,))
    if not 0 <= value <= MAX_REMAINING_LENGTH:
        raise ProtocolError("a remaining length of %d is not between 0 and %d"
                            % (value, MAX_REMAINING_LENGTH))
    out = bytearray()
    while True:
        group = value & 0x7F
        value >>= 7
        if not value:
            out.append(group)
            return bytes(out)
        out.append(group | 0x80)


def read_header(data, pos=0):
    """The fixed header at `pos`, as `(header, payload_pos)`.

    `header` carries four keys in order — `type`, `flags`, `length` (the
    remaining length, the body's own byte count) and `size` (the header's) — and
    `payload_pos` is where the body starts. The buffer is judged as a whole
    packet: with the header whole but the body short the refusal's `.needed` is
    the body's shortfall exactly, so a reader that waits for that many bytes
    never reads half a packet twice.
    """
    data = _as_bytes(data, "the buffer a fixed header is read from")
    pos = _as_pos(data, pos)
    if pos >= len(data):
        raise Incomplete(2)
    first = data[pos]
    kind = first >> 4
    flags = first & 0x0F
    if kind in RESERVED_TYPES:
        raise ProtocolError("packet type %d is reserved (the byte was 0x%02x)"
                            % (kind, first))
    required = REQUIRED_FLAGS[kind]
    if required is not None and flags != required:
        raise ProtocolError("packet type %d carries flags 0x%x, not 0x%x (the byte "
                            "was 0x%02x)" % (kind, flags, required, first))
    length, body = read_varint(data, pos + 1)
    end = body + length
    if end > len(data):
        raise Incomplete(end - len(data))
    return {"type": kind, "flags": flags, "length": length, "size": body - pos}, body
