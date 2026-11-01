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
        if isinstance(protocols, str):
            protocols = (protocols,)
        self._protocols = tuple(protocols)
        self._max_message = max_message
        self._phase = "handshake"
        self._handshake = b""
        self._stream = None
        self._report = {
            "phase": "handshake",
            "handshake": "pending",
            "protocol": None,
            "messages": 0,
            "text_messages": 0,
            "binary_messages": 0,
            "pings": 0,
            "pongs": 0,
            "closes": 0,
            "protocol_errors": 0,
            "bytes_in": 0,
            "bytes_out": 0,
        }

    @property
    def phase(self):
        return self._phase

    def report(self):
        """A copy of the session's counters, safe for a caller to edit."""
        return dict(self._report)

    def _send(self, data):
        self._report["bytes_out"] += len(data)
        return data

    def _reject(self, status, reason):
        phrase = stage_01.REASONS.get(status, "Error")
        body = (reason + "\n").encode("utf-8")
        headers = ["HTTP/1.1 %d %s" % (status, phrase),
                   "Content-Type: text/plain; charset=utf-8",
                   "Content-Length: %d" % (len(body),),
                   "Connection: close"]
        if status == 426:
            headers.append("Sec-WebSocket-Version: 13")
        return ("\r\n".join(headers) + "\r\n\r\n").encode("latin-1") + body

    def _close_for_error(self, exc):
        reason = str(exc).encode("utf-8")
        if len(reason) > 123:
            reason = PROTOCOL_ERROR_REASON
        return stage_04.close(exc.code, reason)

    def feed(self, data):
        """Accept bytes from the peer and return the bytes to send back."""
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("a session is fed bytes, not %s"
                            % (type(data).__name__,))
        data = bytes(data)
        if not data:
            return b""
        self._report["bytes_in"] += len(data)
        if self._phase == "closed":
            return b""

        out = b""
        if self._phase == "handshake":
            self._handshake += data
            if (b"\r\n\r\n" not in self._handshake
                    and len(self._handshake) > MAX_HANDSHAKE):
                self._phase = "closed"
                self._report["phase"] = "closed"
                self._report["handshake"] = "rejected"
                return self._send(self._reject(
                    400, "the handshake headers are larger than %d bytes"
                    % (MAX_HANDSHAKE,)))
            if b"\r\n\r\n" not in self._handshake:
                return b""
            head, rest = self._handshake.split(b"\r\n\r\n", 1)
            request = head + b"\r\n\r\n"
            try:
                accepted = stage_01.accept(request, self._protocols)
            except stage_01.HandshakeError as exc:
                self._phase = "closed"
                self._report["phase"] = "closed"
                self._report["handshake"] = "rejected"
                return self._send(self._reject(exc.status, str(exc)))
            self._phase = "open"
            self._report["phase"] = "open"
            self._report["handshake"] = "accepted"
            self._report["protocol"] = accepted["protocol"]
            out += accepted["response"]
            self._stream = stage_07.FrameStream(
                require_mask=True, max_message=self._max_message)
            pending = rest
            if not pending:
                return self._send(out)
        else:
            pending = data

        try:
            events = self._stream.feed(pending)
        except stage_07.ProtocolError as exc:
            self._report["protocol_errors"] += 1
            out += self._close_for_error(exc)
            self._phase = "closed"
            self._report["phase"] = "closed"
            return self._send(out)

        for event in events:
            kind = event["type"]
            if kind == "ping":
                self._report["pings"] += 1
                out += stage_04.pong(event["payload"])
            elif kind == "pong":
                self._report["pongs"] += 1
            elif kind == "close":
                self._report["closes"] += 1
                code = event["code"] if event["code"] is not None else 1000
                reason = event["reason"].encode("utf-8")
                if len(reason) > 123:
                    reason = b""
                out += stage_04.close(code, reason)
                self._phase = "closed"
                self._report["phase"] = "closed"
            elif kind == "message":
                self._report["messages"] += 1
                if event["opcode"] == 0x1:
                    self._report["text_messages"] += 1
                else:
                    self._report["binary_messages"] += 1
                out += stage_03.write_frame(event["opcode"], event["payload"])
        return self._send(out)

    def finish(self):
        """End the session and return a close frame if one is still owed."""
        if self._phase == "closed":
            return b""
        if self._phase == "handshake":
            self._phase = "closed"
            self._report["phase"] = "closed"
            self._report["handshake"] = "incomplete"
            return b""
        try:
            self._stream.finish()
        except stage_07.ProtocolError as exc:
            self._report["protocol_errors"] += 1
            out = self._close_for_error(exc)
            self._phase = "closed"
            self._report["phase"] = "closed"
            return self._send(out)
        out = stage_04.close(1000, b"")
        self._phase = "closed"
        self._report["phase"] = "closed"
        return self._send(out)
