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
        if not isinstance(require_mask, bool):
            raise ProtocolError("require_mask must be a bool, not %r"
                                % (require_mask,))
        self.require_mask = require_mask
        self.max_message = max_message
        self._buffer = b""
        self._assembler = stage_05.Assembler(max_message=max_message)
        self._utf8 = None
        self._closed = False

    @property
    def closed(self):
        return self._closed

    def _utf8_feed(self, data):
        try:
            self._utf8.feed(data)
        except stage_06.UTF8Error as exc:
            raise ProtocolError("invalid UTF-8 text: %s" % (exc,), 1007)

    def _utf8_finish(self):
        try:
            return self._utf8.finish()
        except stage_06.UTF8Error as exc:
            raise ProtocolError("invalid UTF-8 text: %s" % (exc,), 1007)

    def reset(self):
        """Forget the buffer and every piece of message state."""
        self._buffer = b""
        self._assembler.reset()
        self._utf8 = None
        self._closed = False

    def feed(self, data):
        """Accept a chunk of bytes and return every event it completed."""
        if not isinstance(data, (bytes, bytearray)):
            raise ProtocolError("a stream carries bytes, not %s"
                                % (type(data).__name__,))
        data = bytes(data)
        if not data:
            return []
        if self._closed:
            raise ProtocolError("a frame arrived after close")
        self._buffer += data
        events = []

        while self._buffer:
            try:
                frame = stage_03.read_frame(self._buffer,
                                            require_mask=self.require_mask)
            except Incomplete:
                break
            except FrameError as exc:
                raise ProtocolError(str(exc), 1002)
            self._buffer = self._buffer[frame["size"]:]

            if frame["rsv1"] or frame["rsv2"] or frame["rsv3"]:
                raise ProtocolError("a reserved bit is set and no extension is "
                                    "active", 1002)
            opcode = frame["opcode"]
            if opcode in RESERVED_OPCODES:
                raise ProtocolError("opcode 0x%X is reserved and no extension "
                                    "is active" % (opcode,), 1002)

            if opcode in stage_02.CONTROL_OPCODES:
                try:
                    stage_04.validate_frame(frame)
                except FrameError as exc:
                    raise ProtocolError(str(exc), 1002)
                if opcode == 0x8:
                    parsed = stage_04.parse_close(frame["payload"])
                    reason = ""
                    if parsed["reason"]:
                        try:
                            reason = stage_06.validate_utf8(parsed["reason"])
                        except stage_06.UTF8Error as exc:
                            raise ProtocolError("invalid close reason: %s" % (exc,),
                                                1007)
                    self._closed = True
                    events.append({"type": "close", "code": parsed["code"],
                                   "reason": reason})
                    if self._buffer:
                        raise ProtocolError("a frame arrived after close")
                    break
                if opcode == 0x9:
                    events.append({"type": "ping", "payload": frame["payload"]})
                elif opcode == 0xA:
                    events.append({"type": "pong", "payload": frame["payload"]})
                continue

            # A data frame. The UTF-8 stream follows a fragmented text message
            # from its first frame to its final continuation.
            if opcode == 0x0 and self._utf8 is not None:
                self._utf8_feed(frame["payload"])
            elif opcode == 0x1 and not frame["fin"]:
                self._utf8 = stage_06.UTF8Stream()
                self._utf8_feed(frame["payload"])

            try:
                produced = self._assembler.feed(frame)
            except stage_05.MessageError as exc:
                code = 1009 if "at most" in str(exc) else 1002
                raise ProtocolError(str(exc), code)

            for event in produced:
                if event["type"] == "message" and event["opcode"] == 0x1:
                    if self._utf8 is not None:
                        event["text"] = self._utf8_finish()
                        self._utf8 = None
                    else:
                        try:
                            event["text"] = stage_06.validate_utf8(event["payload"])
                        except stage_06.UTF8Error as exc:
                            raise ProtocolError("invalid UTF-8 text: %s" % (exc,),
                                                1007)
                events.append(event)
        return events

    def finish(self):
        """The stream has ended: refuse anything left that is not a whole frame."""
        if self._closed:
            return None
        if self._buffer:
            raise ProtocolError("the stream ended in the middle of a frame", 1002)
        if self._assembler.in_message:
            raise ProtocolError("the stream ended in the middle of a fragmented "
                                "message", 1002)
        if self._utf8 is not None:
            self._utf8_finish()
            self._utf8 = None
        return None
