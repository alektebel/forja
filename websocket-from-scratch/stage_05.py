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

TODO: implement `Assembler` (`__init__`, `feed`, `finish`, `reset`).
"""

import stage_02
import stage_03
import stage_04
from stage_02 import FrameError

DEFAULT_MAX_MESSAGE = 1_048_576


class MessageError(FrameError):
    """A sequence of frames that cannot be a message, named as what is wrong."""


class Assembler:
    """Put data frames back into messages, and let control frames through."""

    def __init__(self, max_message=DEFAULT_MAX_MESSAGE):
        raise NotImplementedError("stage 5: implement Assembler.__init__()")

    def reset(self):
        """Forget any message being assembled, without judging it."""
        raise NotImplementedError("stage 5: implement Assembler.reset()")

    def feed(self, frame):
        """One decoded frame in, zero or more events out."""
        raise NotImplementedError("stage 5: implement Assembler.feed()")

    def finish(self):
        """Refuse a fragmented message that never received its FIN."""
        raise NotImplementedError("stage 5: implement Assembler.finish()")
