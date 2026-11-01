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


def _bytes_of(data, what):
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    raise HandshakeError("%s must be bytes, not %s"
                         % (what, type(data).__name__))


def _header_list(headers, name):
    """The header's comma-separated values, preserving case and order."""
    raw = headers.get(name.lower(), "")
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def parse_request(request):
    """Parse an HTTP/1.1 request head into four facts.

    The result is ``{"method", "target", "version", "headers"}``. Header names
    are lower-cased; a header that appears twice is joined with ``", "``, which
    is exactly what the token parser needs for ``Connection`` and what makes a
    duplicated ``Sec-WebSocket-Key`` fail the nonce check instead of silently
    winning. The bytes after the first blank line are ignored: a handshake has
    no body, and a client that sent one has already made a different mistake.
    """
    data = _bytes_of(request, "a request")
    if b"\x00" in data:
        raise HandshakeError("a request may not contain a NUL byte")
    if b"\r\n\r\n" not in data:
        raise HandshakeError("a request ends its headers with CRLF CRLF")
    head = data.split(b"\r\n\r\n", 1)[0]
    lines = head.split(b"\r\n")
    if not lines or not lines[0]:
        raise HandshakeError("a request starts with a request line")
    try:
        request_line = lines[0].decode("latin-1")
    except UnicodeDecodeError:
        raise HandshakeError("the request line is not latin-1")
    parts = request_line.split(" ")
    if len(parts) != 3:
        raise HandshakeError("a request line is METHOD TARGET VERSION, not %r"
                             % (request_line,))
    method, target, version = parts
    if not method or not target or not version:
        raise HandshakeError("a request line has three non-empty parts")
    headers = {}
    for line in lines[1:]:
        if not line:
            raise HandshakeError("an empty header line before the end of headers")
        if b":" not in line:
            raise HandshakeError("a header line has no colon: %r" % (line,))
        name, value = line.split(b":", 1)
        try:
            name = name.decode("latin-1").strip().lower()
            value = value.decode("latin-1").strip()
        except UnicodeDecodeError:
            raise HandshakeError("a header is not latin-1")
        if not name:
            raise HandshakeError("a header has an empty name")
        if name in headers:
            headers[name] += ", " + value
        else:
            headers[name] = value
    return {"method": method, "target": target, "version": version,
            "headers": headers}


def header_tokens(headers, name):
    """The lower-cased tokens of a comma-separated header, in order."""
    if not isinstance(headers, dict):
        raise HandshakeError("headers must be a dict, not %s"
                             % (type(headers).__name__,))
    if not isinstance(name, str) or not name:
        raise HandshakeError("a header name must be a non-empty string")
    return tuple(token.lower() for token in _header_list(headers, name))


def accept_key(key):
    """The ``Sec-WebSocket-Accept`` value for a client's base64 nonce.

    The key is a base64-encoded 16-byte value. Decoding it before hashing is the
    point: a server that hashes any old string will happily answer a client that
    sent an invalid nonce, and the client will not notice until its browser
    closes the connection.
    """
    if not isinstance(key, str) or not key:
        raise HandshakeError("Sec-WebSocket-Key must be a non-empty string")
    try:
        raw = base64.b64decode(key, validate=True)
    except (binascii.Error, ValueError):
        raise HandshakeError("Sec-WebSocket-Key is not base64: %r" % (key,))
    if len(raw) != 16:
        raise HandshakeError("Sec-WebSocket-Key decodes to 16 bytes, not %d"
                             % (len(raw),))
    digest = hashlib.sha1((key + GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def _offer_list(headers):
    """The client's subprotocol offers, preserving their case and order."""
    return _header_list(headers, "sec-websocket-protocol")


def _choose_protocol(headers, supported):
    offers = _offer_list(headers)
    if not offers:
        return None
    for offer in offers:
        if offer in supported:
            return offer
    return None


def _response(status, headers, body=b""):
    reason = REASONS.get(status, "Error")
    lines = ["HTTP/1.1 %d %s" % (status, reason)]
    for name, value in headers:
        lines.append("%s: %s" % (name, value))
    if body:
        lines.append("Content-Length: %d" % (len(body),))
    lines.extend(["", ""])
    return ("\r\n".join(lines)).encode("latin-1") + body


def accept(request, protocols=()):
    """The handshake's answer: a 101 response, or a refusal with a status.

    ``protocols`` is the server's supported subprotocol list. The server picks
    the first protocol the *client* offered that the server also supports, which
    is the order a browser uses when it offers a preference. No common protocol
    is not an error: the handshake succeeds without one, which is the behaviour
    the RFC requires.
    """
    parsed = parse_request(request)
    if parsed["method"] != "GET":
        raise HandshakeError("a WebSocket handshake is a GET, not %s"
                             % (parsed["method"],), 405)
    if parsed["version"] != "HTTP/1.1":
        raise HandshakeError("a WebSocket handshake is HTTP/1.1, not %s"
                             % (parsed["version"],))
    if not parsed["target"].startswith("/"):
        raise HandshakeError("a request target starts with '/', not %r"
                             % (parsed["target"],))
    headers = parsed["headers"]
    if "host" not in headers or not headers["host"]:
        raise HandshakeError("a WebSocket handshake has a Host header")
    if "websocket" not in header_tokens(headers, "upgrade"):
        raise HandshakeError("Upgrade must contain the token 'websocket', not %r"
                             % (headers.get("upgrade", ""),))
    if "upgrade" not in header_tokens(headers, "connection"):
        raise HandshakeError("Connection must contain the token 'Upgrade', not %r"
                             % (headers.get("connection", ""),))
    version = headers.get("sec-websocket-version", "")
    if version != VERSION:
        raise HandshakeError("this server speaks WebSocket version %s, not %r"
                             % (VERSION, version), 426)
    if "sec-websocket-key" not in headers:
        raise HandshakeError("a WebSocket handshake has a Sec-WebSocket-Key header")
    accept_value = accept_key(headers["sec-websocket-key"])

    if isinstance(protocols, str):
        protocols = (protocols,)
    supported = tuple(protocols)
    for protocol in supported:
        if not isinstance(protocol, str) or not protocol:
            raise HandshakeError("a subprotocol is a non-empty string, not %r"
                                 % (protocol,))
    selected = _choose_protocol(headers, supported)

    response_headers = [("Upgrade", "websocket"),
                        ("Connection", "Upgrade"),
                        ("Sec-WebSocket-Accept", accept_value)]
    if selected is not None:
        response_headers.append(("Sec-WebSocket-Protocol", selected))
    body = b""
    response = _response(101, response_headers, body)
    return {"status": 101, "protocol": selected,
            "headers": {name.lower(): value for name, value in response_headers},
            "response": response}
