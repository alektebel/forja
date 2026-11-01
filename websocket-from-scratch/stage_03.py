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

TODO: implement `apply_mask`, `read_frame` and `write_frame`.
"""

import stage_02
from stage_02 import FrameError, Incomplete, decode_header, encode_header

MASK_KEY_LEN = 4


def apply_mask(payload, key):
    """`payload` XOR `key`, repeating the key every four bytes.

    The operation is its own inverse: applying the same key twice returns the
    original bytes, which is why a server can use one function for masking and
    unmasking and why a check can compare the two directions.
    """
    raise NotImplementedError("stage 3: implement apply_mask()")


def read_frame(data, pos=0, require_mask=None):
    """Read one complete frame at `pos`, unmasking its payload.

    The result carries the header's facts plus ``payload`` (already unmasked) and
    ``size`` (the number of bytes the whole frame occupied). A buffer that ends
    inside the payload is `Incomplete` with `.needed` equal to the payload's own
    shortfall, not the header's: the header is already known, and the number the
    stream layer needs is how many bytes remain before the frame is whole.
    """
    raise NotImplementedError("stage 3: implement read_frame()")


def write_frame(opcode, payload=b"", fin=True, mask_key=None):
    """One frame's bytes: the header, then the (optionally masked) payload."""
    raise NotImplementedError("stage 3: implement write_frame()")
