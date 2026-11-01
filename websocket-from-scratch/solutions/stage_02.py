"""WebSocket From Scratch — stage 2: the frame header.

Every WebSocket frame begins with two bytes and then, depending on what they
say, up to ten more header bytes. The first byte carries FIN and the opcode. The
second carries MASK and a seven-bit length. A length of 126 means "read the next
two bytes as a 16-bit length"; a length of 127 means "read the next eight bytes
as a 64-bit length"; a set MASK bit means "read the next four bytes as the
masking key".

The header is where a stream reader learns how many bytes the rest of the frame
will take. That makes it the natural home of the two failures this stage
prevents: a length that is read from the wrong width, and a length that is not
encoded in the shortest form. The first reads the payload from the wrong offset;
the second accepts bytes that a strict peer will reject.

    OPCODES          the legal opcode numbers and their names
    Incomplete       "not enough bytes yet", with `.needed` saying how many
    FrameError       bytes that can never be a frame header
    encode_header    fin, opcode, length, optional mask key -> header bytes
    decode_header    bytes -> the header's facts, or Incomplete/FrameError

DESIGN DECISION — why is `Incomplete` separate from `FrameError`? Because the
two answers have opposite consequences. A stream may stop anywhere, so a
half-arrived header is the normal state of a reader between two reads; the
reader must wait and consume nothing. A malformed header will never become a
frame no matter how long the reader waits. If they were one family, every caller
would have to remember which half it caught.
"""

OPCODES = {
    0x0: "continuation",
    0x1: "text",
    0x2: "binary",
    0x8: "close",
    0x9: "ping",
    0xA: "pong",
}

CONTROL_OPCODES = (0x8, 0x9, 0xA)
MAX_PAYLOAD = (1 << 63) - 1


class FrameError(ValueError):
    """Bytes that can never be a WebSocket frame, named as what is wrong."""


class Incomplete(ValueError):
    """A frame that has not arrived yet, with `.needed` bytes still to come."""

    def __init__(self, needed):
        self.needed = needed
        super().__init__("needs at least %d more byte%s"
                         % (needed, "" if needed == 1 else "s"))


def _bytes_of(data, what):
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    raise FrameError("%s must be bytes, not %s"
                     % (what, type(data).__name__))


def _int(value, what, low, high):
    if isinstance(value, bool) or not isinstance(value, int):
        raise FrameError("%s must be an int, not %s"
                         % (what, type(value).__name__))
    if not low <= value <= high:
        raise FrameError("%s must be %d..%d, not %d" % (what, low, high, value))
    return value


def encode_header(fin, opcode, length, mask_key=None):
    """The frame header: FIN, opcode, MASK, the shortest length, and the key.

    The length is encoded in the shortest legal form: 0..125 in the seven-bit
    field, 126..65535 as 126 followed by two bytes, and 65536..2^63-1 as 127
    followed by eight bytes. The high bit of the eight-byte form is not part of
    the length, so a value that would set it is refused rather than silently
    truncated.
    """
    if not isinstance(fin, bool):
        raise FrameError("fin must be a bool, not %s" % (type(fin).__name__,))
    _int(opcode, "an opcode", 0, 0x0F)
    _int(length, "a payload length", 0, MAX_PAYLOAD)
    if mask_key is not None:
        mask_key = _bytes_of(mask_key, "a masking key")
        if len(mask_key) != 4:
            raise FrameError("a masking key is 4 bytes, not %d" % (len(mask_key),))
    first = (0x80 if fin else 0x00) | opcode
    masked = 0x00 if mask_key is None else 0x80
    if length <= 125:
        header = bytes((first, masked | length))
    elif length <= 0xFFFF:
        header = bytes((first, masked | 126)) + length.to_bytes(2, "big")
    else:
        header = bytes((first, masked | 127)) + length.to_bytes(8, "big")
    if mask_key is not None:
        header += mask_key
    return header


def decode_header(data, pos=0):
    """The header's facts, or `Incomplete`/`FrameError`.

    The result is a dict with ``fin``, ``rsv1``..``rsv3``, ``opcode``, ``masked``,
    ``mask_key``, ``length``, ``header_length``, ``payload_offset``. The reserved
    bits are reported rather than judged: an extension may use them, and no
    extension has asked this course for permission yet (stage 7 refuses them).
    """
    data = _bytes_of(data, "a frame buffer")
    if isinstance(pos, bool) or not isinstance(pos, int):
        raise FrameError("a position must be an int, not %r" % (pos,))
    if not 0 <= pos <= len(data):
        raise FrameError("a position of %d in %d bytes" % (pos, len(data)))
    start = pos
    available = len(data) - pos
    if available < 2:
        raise Incomplete(2 - available)
    first, second = data[pos], data[pos + 1]
    pos += 2
    fin = bool(first & 0x80)
    rsv1 = bool(first & 0x40)
    rsv2 = bool(first & 0x20)
    rsv3 = bool(first & 0x10)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F

    if length == 126:
        if len(data) - pos < 2:
            raise Incomplete(2 - (len(data) - pos))
        length = int.from_bytes(data[pos:pos + 2], "big")
        pos += 2
        if length < 126:
            raise FrameError("a 126 length is not used for %d bytes" % (length,))
    elif length == 127:
        if len(data) - pos < 8:
            raise Incomplete(8 - (len(data) - pos))
        length = int.from_bytes(data[pos:pos + 8], "big")
        pos += 8
        if length & (1 << 63):
            raise FrameError("the high bit of a 64-bit length is not a length bit")
        if length < 65536:
            raise FrameError("a 127 length is not used for %d bytes" % (length,))

    mask_key = None
    if masked:
        if len(data) - pos < 4:
            raise Incomplete(4 - (len(data) - pos))
        mask_key = bytes(data[pos:pos + 4])
        pos += 4

    return {"fin": fin, "rsv1": rsv1, "rsv2": rsv2, "rsv3": rsv3,
            "opcode": opcode, "masked": masked, "mask_key": mask_key,
            "length": length, "header_length": pos - start,
            "payload_offset": pos}
