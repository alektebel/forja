"""WebSocket From Scratch — stage 8: a session, over a stream of bytes.

The seven stages before this one each prove a layer. This one is the thing a
browser actually talks to: a session that starts with an HTTP Upgrade, turns
into a frame stream, answers pings, echoes text and binary messages, and ends
with a close handshake. It is still fed bytes, not sockets, so the check chooses
where every chunk stops — including in the middle of the handshake, in the
middle of a frame, and in the middle of a UTF-8 character.

    Session(protocols=(), max_message=...)
    feed(chunk)   -> the bytes the server should send now
    finish()      -> the close frame owed when the peer simply stops
    report()      -> what happened, with every count named

The report is deliberately not a count of beliefs: `bytes_in` and `bytes_out`
are the bytes that crossed the boundary, `messages` is messages delivered, and
`protocol_errors` is the number of times the stream refused the peer. A session
that claims to have sent a message the caller never received is the bug this
stage's capstone check is looking for.

DESIGN DECISION — why does `feed` return bytes instead of writing to a socket?
Because the protocol is the subject, not the operating system. A returned byte
string is the whole output of one move, so a check can split the input anywhere
and compare the concatenated output with one uninterrupted run. The same
`Session` can be dropped behind a real socket in twenty lines; it does not need
to own the socket to be correct.

DESIGN DECISION — why does a bad handshake become a response instead of an
exception? Because an HTTP client is entitled to an HTTP answer. The session
turns `HandshakeError` into the status and the reason, and also records that the
handshake was rejected. An exception here would leave a browser staring at a
closed port with no explanation.

TODO: implement `Session` (`__init__`, `feed`, `finish`, `report`).
"""

import stage_01
import stage_03
import stage_04
import stage_07

MAX_HANDSHAKE = 16_384
PROTOCOL_ERROR_REASON = b"protocol error"


class Session:
    """One WebSocket connection, from the first HTTP byte to the close frame."""

    def __init__(self, protocols=(), max_message=1_048_576):
        raise NotImplementedError("stage 8: implement Session.__init__()")

    @property
    def phase(self):
        return self._phase

    def report(self):
        """A copy of the session's counters, safe for a caller to edit."""
        raise NotImplementedError("stage 8: implement Session.report()")

    def feed(self, data):
        """Accept bytes from the peer and return the bytes to send back."""
        raise NotImplementedError("stage 8: implement Session.feed()")

    def finish(self):
        """End the session and return a close frame if one is still owed."""
        raise NotImplementedError("stage 8: implement Session.finish()")
