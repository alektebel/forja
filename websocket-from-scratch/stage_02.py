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

TODO: implement `encode_header` and `decode_header`.
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


def encode_header(fin, opcode, length, mask_key=None):
    """The frame header: FIN, opcode, MASK, the shortest length, and the key.

    The length is encoded in the shortest legal form: 0..125 in the seven-bit
    field, 126..65535 as 126 followed by two bytes, and 65536..2^63-1 as 127
    followed by eight bytes. The high bit of the eight-byte form is not part of
    the length, so a value that would set it is refused rather than silently
    truncated.
    """
    raise NotImplementedError("stage 2: implement encode_header()")


def decode_header(data, pos=0):
    """The header's facts, or `Incomplete`/`FrameError`.

    The result is a dict with ``fin``, ``rsv1``..``rsv3``, ``opcode``, ``masked``,
    ``mask_key``, ``length``, ``header_length``, ``payload_offset``. The reserved
    bits are reported rather than judged: an extension may use them, and no
    extension has asked this course for permission yet (stage 7 refuses them).
    """
    raise NotImplementedError("stage 2: implement decode_header()")
