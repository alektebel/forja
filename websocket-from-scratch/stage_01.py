"""WebSocket From Scratch — stage 1: the HTTP Upgrade handshake.

A WebSocket connection starts life as an ordinary HTTP/1.1 request. The client
asks the server to *upgrade* the connection, proves it knows the protocol with a
random 16-byte nonce, and the server answers ``101 Switching Protocols`` with a
digest of that nonce. After that blank line the same TCP connection carries
WebSocket frames, not HTTP.

This stage builds the handshake and nothing else. The two failures it exists to
prevent are the ones that look like success: accepting a request that never
asked to upgrade, and computing an ``Accept`` value that is *almost* right. The
first opens a WebSocket to an HTTP client; the second makes a browser close the
connection before the first frame.

    GUID          the RFC 6455 constant appended to the client's key
    VERSION       the only protocol version this server speaks: 13
    parse_request bytes -> method, target, version, lower-cased headers
    header_tokens comma-separated tokens, lower-cased (Connection, Upgrade)
    accept_key    SHA-1(key + GUID), base64-encoded
    accept        the whole handshake: 101 response or a named refusal

DESIGN DECISION — why parse the HTTP request by hand instead of using
``http.server``? Because the interesting part is the *upgrade*: a server that
lets a general HTTP parser decide what a WebSocket request is has hidden the
token rules, the version rule and the nonce rule behind a framework. The rules
are the lesson, so they are visible here.

DESIGN DECISION — why is a version mismatch a 426 rather than a 400? Because
the client can fix a version mismatch by trying again with version 13, and RFC
6455 gives the response a header that says which version to try. A 400 says the
request is malformed; a 426 says the request is understood and the protocol
version is the thing that must change.

TODO: implement `parse_request`, `header_tokens`, `accept_key` and `accept`.
"""

import base64
import binascii
import hashlib

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
VERSION = "13"

REASONS = {
    101: "Switching Protocols",
    400: "Bad Request",
    405: "Method Not Allowed",
    426: "Upgrade Required",
}


class HandshakeError(ValueError):
    """A request this server will not upgrade, with the status it deserves."""

    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


def parse_request(request):
    """Parse an HTTP/1.1 request head into four facts.

    The result is ``{"method", "target", "version", "headers"}``. Header names
    are lower-cased; a header that appears twice is joined with ``", "``, which
    is exactly what the token parser needs for ``Connection`` and what makes a
    duplicated ``Sec-WebSocket-Key`` fail the nonce check instead of silently
    winning. The bytes after the first blank line are ignored: a handshake has
    no body, and a client that sent one has already made a different mistake.
    """
    raise NotImplementedError("stage 1: implement parse_request()")


def header_tokens(headers, name):
    """The lower-cased tokens of a comma-separated header, in order."""
    raise NotImplementedError("stage 1: implement header_tokens()")


def accept_key(key):
    """The ``Sec-WebSocket-Accept`` value for a client's base64 nonce.

    The key is a base64-encoded 16-byte value. Decoding it before hashing is the
    point: a server that hashes any old string will happily answer a client that
    sent an invalid nonce, and the client will not notice until its browser
    closes the connection.
    """
    raise NotImplementedError("stage 1: implement accept_key()")


def accept(request, protocols=()):
    """The handshake's answer: a 101 response, or a refusal with a status.

    ``protocols`` is the server's supported subprotocol list. The server picks
    the first protocol the *client* offered that the server also supports, which
    is the order a browser uses when it offers a preference. No common protocol
    is not an error: the handshake succeeds without one, which is the behaviour
    the RFC requires.
    """
    raise NotImplementedError("stage 1: implement accept()")
