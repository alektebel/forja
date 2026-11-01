"""WebSocket From Scratch — stage 3: the payload, and the mask.

A frame header says how long the payload is and whether it is masked. This stage
reads the payload, unmasks it, and writes frames in both directions. Masking is
the part every beginner gets wrong in the same way: it is not encryption and it
is not a key exchange. It is a four-byte XOR that makes a client's bytes look
different from any cached proxy's idea of a request, and the server must remove
it before the message means anything.

The masking rule is directional, and it is a protocol rule rather than a
performance hint: a client MUST mask every frame, and a server MUST NOT. A
server that accepts an unmasked client frame has accepted bytes that a proxy
could have forged; a server that masks its own frames has produced frames a
browser will reject. `require_mask` makes the direction explicit at the one
place that reads a frame.

    apply_mask       XOR a payload with a four-byte key, repeating the key
    read_frame       header + payload -> one frame, or Incomplete/FrameError
    write_frame      one frame's bytes, with an optional client mask

DESIGN DECISION — why does `read_frame` take `require_mask` instead of guessing
from the data? Because the direction is a fact about the *endpoint*, not about
the bytes. A server reading a client frame and a client reading a server frame
are two different rules, and a function that guessed would have to know which
one called it. The caller knows; the function asks.
"""

import stage_02
from stage_02 import FrameError, Incomplete, decode_header, encode_header

MASK_KEY_LEN = 4


def _bytes_of(data, what):
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    raise FrameError("%s must be bytes, not %s"
                     % (what, type(data).__name__))


def apply_mask(payload, key):
    """`payload` XOR `key`, repeating the key every four bytes.

    The operation is its own inverse: applying the same key twice returns the
    original bytes, which is why a server can use one function for masking and
    unmasking and why a check can compare the two directions.
    """
    payload = _bytes_of(payload, "a payload")
    key = _bytes_of(key, "a masking key")
    if len(key) != MASK_KEY_LEN:
        raise FrameError("a masking key is %d bytes, not %d"
                         % (MASK_KEY_LEN, len(key)))
    return bytes(byte ^ key[index % MASK_KEY_LEN]
                 for index, byte in enumerate(payload))


def read_frame(data, pos=0, require_mask=None):
    """Read one complete frame at `pos`, unmasking its payload.

    The result carries the header's facts plus ``payload`` (already unmasked) and
    ``size`` (the number of bytes the whole frame occupied). A buffer that ends
    inside the payload is `Incomplete` with `.needed` equal to the payload's own
    shortfall, not the header's: the header is already known, and the number the
    stream layer needs is how many bytes remain before the frame is whole.
    """
    data = _bytes_of(data, "a frame buffer")
    if require_mask not in (None, True, False):
        raise FrameError("require_mask must be True, False or None, not %r"
                         % (require_mask,))
    header = decode_header(data, pos)
    end = header["payload_offset"] + header["length"]
    if len(data) < end:
        raise Incomplete(end - len(data))
    payload = data[header["payload_offset"]:end]
    if header["masked"]:
        payload = apply_mask(payload, header["mask_key"])
    if require_mask is True and not header["masked"]:
        raise FrameError("a client frame must be masked")
    if require_mask is False and header["masked"]:
        raise FrameError("a server frame must not be masked")
    frame = dict(header)
    frame["payload"] = payload
    frame["size"] = end - pos
    return frame


def write_frame(opcode, payload=b"", fin=True, mask_key=None):
    """One frame's bytes: the header, then the (optionally masked) payload."""
    payload = _bytes_of(payload, "a payload")
    if mask_key is not None:
        mask_key = _bytes_of(mask_key, "a masking key")
        if len(mask_key) != MASK_KEY_LEN:
            raise FrameError("a masking key is %d bytes, not %d"
                             % (MASK_KEY_LEN, len(mask_key)))
    header = encode_header(fin, opcode, len(payload), mask_key)
    if mask_key is not None:
        payload = apply_mask(payload, mask_key)
    return header + payload
