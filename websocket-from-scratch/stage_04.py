"""WebSocket From Scratch — stage 4: control frames and the close code.

Control frames are the protocol's out-of-band channel: ping, pong and close.
They share the frame format with data, but the rules around them are stricter in
ways a naive implementation always misses. A control frame must be FIN, must be
at most 125 bytes, and must never be fragmented. A close frame's payload is not
free text: the first two bytes are a status code, the rest is a UTF-8 reason, and
a one-byte payload is neither.

The close code is the part that carries meaning. 1000 says "normal", 1002 says
"you broke the protocol", 1007 says "the payload was not UTF-8", 1009 says "too
big", and 3000..4999 are reserved for applications. Codes 1004, 1005, 1006 and
1015 may not be sent on the wire at all; they describe states that a close frame
would be lying about.

    SENDABLE_CLOSE_CODES  the codes this course will put on the wire
    validate_frame        the control-frame rules on a decoded frame
    close_payload         a close body: code + reason, or a named refusal
    parse_close           a close body -> code and reason
    ping / pong / close   the three control frames, ready to send

DESIGN DECISION — why is `1005` refused as a close code when it is so useful in
reports? Because 1005 means "no status code was present"; it is a local
observation, not something a peer may send. A close frame carrying 1005 would be
a frame that claims to be the absence of a frame. The same reasoning applies to
1006 (the connection closed abnormally) and 1015 (the TLS handshake failed).

TODO: implement `validate_frame`, `close_payload`, `parse_close`, `ping`,
`pong` and `close`.
"""

import stage_02
import stage_03
from stage_02 import FrameError

SENDABLE_CLOSE_CODES = frozenset(
    (1000, 1001, 1002, 1003) + tuple(range(1007, 1015)) + tuple(range(3000, 5000))
)

CLOSE_CODES = {
    1000: "normal closure",
    1001: "going away",
    1002: "protocol error",
    1003: "unsupported data",
    1007: "invalid payload data",
    1008: "policy violation",
    1009: "message too big",
    1010: "mandatory extension",
    1011: "internal error",
    1012: "service restart",
    1013: "try again later",
    1014: "bad gateway",
}


class ControlError(FrameError):
    """A control frame that the protocol does not allow, named as what is wrong."""


def validate_frame(frame):
    """Apply the control-frame rules to one decoded frame.

    Data frames pass through: fragmentation, message size and text validity are
    stage 5's and stage 6's business. The reserved opcodes are refused here
    because no extension has been negotiated, so a frame using one can never be
    understood by this connection.
    """
    raise NotImplementedError("stage 4: implement validate_frame()")


def close_payload(code=1000, reason=b""):
    """A close body, or a refusal naming the code or the reason length.

    ``code=None`` is the "no status code" close: it is legal, but only when the
    reason is empty, because a reason without a code has nowhere to start.
    """
    raise NotImplementedError("stage 4: implement close_payload()")


def parse_close(payload):
    """A close body -> ``{"code": int|None, "reason": bytes}``.

    A body of zero bytes is the legal close with no code. A body of one byte is
    impossible: there is no such thing as half a status code.
    """
    raise NotImplementedError("stage 4: implement parse_close()")


def ping(payload=b""):
    """A ping frame with at most 125 bytes of application data."""
    raise NotImplementedError("stage 4: implement ping()")


def pong(payload=b""):
    """A pong frame, usually echoing the ping's application data."""
    raise NotImplementedError("stage 4: implement pong()")


def close(code=1000, reason=b""):
    """A close frame carrying `code` and `reason`."""
    raise NotImplementedError("stage 4: implement close()")
