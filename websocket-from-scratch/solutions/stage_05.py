"""WebSocket From Scratch — stage 5: fragmentation.

A message is not a frame. A text or binary message may be split across one
starting frame and any number of continuation frames, and the last one sets FIN.
Control frames may arrive in the middle of that sequence, because a ping is
allowed to interrupt a message that is still being assembled. The receiver's job
is to put the data frames back together in order, pass control frames straight
through, and refuse the sequences the protocol does not allow:

* a continuation with no message to continue;
* a new text or binary frame while a fragmented message is still open;
* a fragmented message that grows past the receiver's limit;
* a control frame that is fragmented or too long (stage 4's rules).

    Assembler(max_message=...)  the state machine, one feed per decoded frame
    feed(frame)                 -> zero or more events
    finish()                    -> refuse an unfinished fragmented message
    in_message                  whether a start frame is waiting for its FIN

An event is either ``{"type": "message", "opcode": 1|2, "payload": bytes,
"fragments": n}`` or a control event ``{"type": "ping"|"pong"|"close",
"opcode": n, "payload": bytes}``.

DESIGN DECISION — why does the assembler take decoded frames rather than bytes?
Because framing and message assembly are different failures. Stage 3 can say
"this frame is complete"; only the assembler knows whether a complete frame is
the continuation of something, the start of something, or a protocol error.
Keeping the two layers separate is what makes both testable on their own.
"""

import stage_02
import stage_03
import stage_04
from stage_02 import FrameError

DEFAULT_MAX_MESSAGE = 1_048_576


class MessageError(FrameError):
    """A sequence of frames that cannot be a message, named as what is wrong."""


def _frame_facts(frame):
    if not isinstance(frame, dict):
        raise MessageError("a frame must be a dict, not %s"
                           % (type(frame).__name__,))
    for key in ("fin", "opcode", "payload"):
        if key not in frame:
            raise MessageError("a frame with no %r in it" % (key,))
    if not isinstance(frame["fin"], bool):
        raise MessageError("a frame's fin is a bool, not %r" % (frame["fin"],))
    opcode = frame["opcode"]
    if isinstance(opcode, bool) or not isinstance(opcode, int):
        raise MessageError("an opcode is an int, not %r" % (opcode,))
    payload = frame["payload"]
    if not isinstance(payload, (bytes, bytearray)):
        raise MessageError("a frame payload is bytes, not %s"
                           % (type(payload).__name__,))
    return frame["fin"], opcode, bytes(payload)


class Assembler:
    """Put data frames back into messages, and let control frames through."""

    def __init__(self, max_message=DEFAULT_MAX_MESSAGE):
        if isinstance(max_message, bool) or not isinstance(max_message, int):
            raise MessageError("max_message must be an int, not %r"
                               % (max_message,))
        if max_message < 0:
            raise MessageError("max_message must be at least 0, not %d"
                               % (max_message,))
        self.max_message = max_message
        self.in_message = False
        self._opcode = None
        self._parts = []
        self._size = 0
        self._fragments = 0

    def _start(self, opcode, payload):
        self.in_message = True
        self._opcode = opcode
        self._parts = [payload]
        self._size = len(payload)
        self._fragments = 1
        if self._size > self.max_message:
            self.reset()
            raise MessageError("a message is at most %d bytes, not %d"
                               % (self.max_message, self._size))

    def _finish(self):
        message = {"type": "message", "opcode": self._opcode,
                   "payload": b"".join(self._parts),
                   "fragments": self._fragments}
        self.reset()
        return message

    def reset(self):
        """Forget any message being assembled, without judging it."""
        self.in_message = False
        self._opcode = None
        self._parts = []
        self._size = 0
        self._fragments = 0

    def feed(self, frame):
        """One decoded frame in, zero or more events out."""
        fin, opcode, payload = _frame_facts(frame)
        stage_04.validate_frame(frame)

        if opcode in stage_02.CONTROL_OPCODES:
            name = stage_02.OPCODES[opcode]
            return [{"type": name, "opcode": opcode, "payload": payload}]

        if opcode in (0x1, 0x2):
            if self.in_message:
                raise MessageError("a data frame arrived while a fragmented "
                                   "message was still open")
            if fin:
                if len(payload) > self.max_message:
                    raise MessageError("a message is at most %d bytes, not %d"
                                       % (self.max_message, len(payload)))
                return [{"type": "message", "opcode": opcode,
                         "payload": payload, "fragments": 1}]
            self._start(opcode, payload)
            return []

        if opcode == 0x0:
            if not self.in_message:
                raise MessageError("a continuation frame arrived with no "
                                   "fragmented message to continue")
            if self._size + len(payload) > self.max_message:
                raise MessageError("a message is at most %d bytes, not %d"
                                   % (self.max_message, self._size + len(payload)))
            self._parts.append(payload)
            self._size += len(payload)
            self._fragments += 1
            if fin:
                return [self._finish()]
            return []

        raise MessageError("opcode 0x%X is not a data or control opcode" % (opcode,))

    def finish(self):
        """Refuse a fragmented message that never received its FIN."""
        if self.in_message:
            raise MessageError("a fragmented message was not finished")
        return None
