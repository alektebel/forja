"""WebSocket From Scratch — stage 7: the streaming state machine.

A TCP connection does not deliver frames. It delivers bytes, in whatever sizes
the network chose, so a reader has to keep a buffer, parse as many whole frames
as it can, and wait when the next frame is not complete. This stage is that
reader. It combines the previous six stages into one object that accepts any
chunking of the same byte stream and produces the same events.

The events are small and explicit: a text or binary message (with text already
decoded for opcode 1), a ping, a pong, or a close. A protocol error becomes a
`ProtocolError` carrying the close code the session should send: 1002 for a
broken frame or sequence, 1007 for invalid UTF-8, 1009 for a message over the
limit.

    FrameStream(require_mask=True, max_message=...)
    feed(chunk)   -> events, or ProtocolError
    finish()      -> refuse a buffer that ends in the middle of a frame
    closed        -> true after a close frame

DESIGN DECISION — why is a protocol error an exception rather than an event?
Because the caller's next action is not "handle this frame"; it is "stop reading
this connection and send one close frame". An event would be another thing to
remember to handle, and a reader that forgets would keep parsing bytes after the
protocol has already ended.

DESIGN DECISION — why does `feed` return a list rather than a single event?
One TCP chunk can contain two frames, and one frame can finish a fragmented
message while a ping arrives before it. The caller needs all of them in order,
and the check can compare that order to the bytes that produced it.

TODO: implement `FrameStream` (`__init__`, `feed`, `finish`, `reset`).
"""

import stage_02
import stage_03
import stage_04
import stage_05
import stage_06
from stage_02 import FrameError, Incomplete

RESERVED_OPCODES = (0x3, 0x4, 0x5, 0x6, 0x7, 0xB, 0xC, 0xD, 0xE, 0xF)


class ProtocolError(FrameError):
    """A stream that has broken the protocol, with the close code to send."""

    def __init__(self, message, code=1002):
        self.code = code
        super().__init__(message)


class FrameStream:
    """Incremental bytes -> frames -> messages, controls and close."""

    def __init__(self, require_mask=True, max_message=stage_05.DEFAULT_MAX_MESSAGE):
        raise NotImplementedError("stage 7: implement FrameStream.__init__()")

    @property
    def closed(self):
        return self._closed

    def reset(self):
        """Forget the buffer and every piece of message state."""
        raise NotImplementedError("stage 7: implement FrameStream.reset()")

    def feed(self, data):
        """Accept a chunk of bytes and return every event it completed."""
        raise NotImplementedError("stage 7: implement FrameStream.feed()")

    def finish(self):
        """The stream has ended: refuse anything left that is not a whole frame."""
        raise NotImplementedError("stage 7: implement FrameStream.finish()")
