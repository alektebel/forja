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


def _payload_of(frame):
    if not isinstance(frame, dict):
        raise ControlError("a frame must be a dict, not %s" % (type(frame).__name__,))
    for key in ("fin", "opcode", "payload"):
        if key not in frame:
            raise ControlError("a frame with no %r in it" % (key,))
    payload = frame["payload"]
    if not isinstance(payload, (bytes, bytearray)):
        raise ControlError("a frame payload is bytes, not %s"
                           % (type(payload).__name__,))
    return bytes(payload)


def validate_frame(frame):
    """Apply the control-frame rules to one decoded frame.

    Data frames pass through: fragmentation, message size and text validity are
    stage 5's and stage 6's business. The reserved opcodes are refused here
    because no extension has been negotiated, so a frame using one can never be
    understood by this connection.
    """
    payload = _payload_of(frame)
    opcode = frame["opcode"]
    if isinstance(opcode, bool) or not isinstance(opcode, int):
        raise ControlError("an opcode must be an int, not %r" % (opcode,))
    if not 0 <= opcode <= 0x0F:
        raise ControlError("an opcode is a four-bit number, not %r" % (opcode,))
    if not isinstance(frame["fin"], bool):
        raise ControlError("a frame's fin is a bool, not %r" % (frame["fin"],))
    if opcode in (0x3, 0x4, 0x5, 0x6, 0x7, 0xB, 0xC, 0xD, 0xE, 0xF):
        raise ControlError("opcode 0x%X is reserved and no extension is active"
                           % (opcode,))
    if opcode not in stage_02.CONTROL_OPCODES:
        return None
    if not frame["fin"]:
        raise ControlError("a control frame must be FIN, not a fragment")
    if len(payload) > 125:
        raise ControlError("a control frame is at most 125 bytes, not %d"
                           % (len(payload),))
    if opcode == 0x8:
        parse_close(payload)
    return None


def close_payload(code=1000, reason=b""):
    """A close body, or a refusal naming the code or the reason length.

    ``code=None`` is the "no status code" close: it is legal, but only when the
    reason is empty, because a reason without a code has nowhere to start.
    """
    if not isinstance(reason, (bytes, bytearray)):
        raise ControlError("a close reason is bytes, not %s"
                           % (type(reason).__name__,))
    reason = bytes(reason)
    if code is None:
        if reason:
            raise ControlError("a close with no code has no reason either")
        return b""
    if isinstance(code, bool) or not isinstance(code, int):
        raise ControlError("a close code must be an int, not %r" % (code,))
    if code not in SENDABLE_CLOSE_CODES:
        raise ControlError("close code %d may not be sent on the wire" % (code,))
    if len(reason) + 2 > 125:
        raise ControlError("a close body is at most 125 bytes, not %d"
                           % (len(reason) + 2,))
    return code.to_bytes(2, "big") + reason


def parse_close(payload):
    """A close body -> ``{"code": int|None, "reason": bytes}``.

    A body of zero bytes is the legal close with no code. A body of one byte is
    impossible: there is no such thing as half a status code.
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise ControlError("a close payload is bytes, not %s"
                           % (type(payload).__name__,))
    payload = bytes(payload)
    if not payload:
        return {"code": None, "reason": b""}
    if len(payload) == 1:
        raise ControlError("a close payload of one byte has no whole status code")
    code = int.from_bytes(payload[:2], "big")
    if code not in SENDABLE_CLOSE_CODES:
        raise ControlError("close code %d may not be sent on the wire" % (code,))
    return {"code": code, "reason": payload[2:]}


def ping(payload=b""):
    """A ping frame with at most 125 bytes of application data."""
    if not isinstance(payload, (bytes, bytearray)):
        raise ControlError("a ping payload is bytes, not %s"
                           % (type(payload).__name__,))
    if len(payload) > 125:
        raise ControlError("a control frame is at most 125 bytes, not %d"
                           % (len(payload),))
    return stage_03.write_frame(0x9, bytes(payload))


def pong(payload=b""):
    """A pong frame, usually echoing the ping's application data."""
    if not isinstance(payload, (bytes, bytearray)):
        raise ControlError("a pong payload is bytes, not %s"
                           % (type(payload).__name__,))
    if len(payload) > 125:
        raise ControlError("a control frame is at most 125 bytes, not %d"
                           % (len(payload),))
    return stage_03.write_frame(0xA, bytes(payload))


def close(code=1000, reason=b""):
    """A close frame carrying `code` and `reason`."""
    return stage_03.write_frame(0x8, close_payload(code, reason))
