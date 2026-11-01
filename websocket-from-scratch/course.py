"""WebSocket From Scratch — course manifest.

Eight graded stages between an HTTP Upgrade and a session that can be fed any
chunking of the same bytes. The world is deliberately small: there is no socket
and no clock, because a WebSocket is a byte protocol, and the checker is the
client. Every stage is a layer that the next one can stand on:

    handshake -> header -> mask/frame -> control -> fragments -> UTF-8
              -> streaming state machine -> session

The thesis of the whole course is one sentence: A WEBSOCKET IS WHAT YOU READ
AFTER THE HTTP REQUEST ENDS — every byte the server accepts is a frame the
format allows, every message is one the receiver can reconstruct, and every
close is a code the peer is allowed to send.
"""

from codecraft.api import stage

TITLE = "WebSocket From Scratch"
DESCRIPTION = ("The HTTP Upgrade, the frame header, masking, control frames, "
               "fragmentation, UTF-8 across fragments, a streaming reader and "
               "a session — all from bytes, with no sockets.")
LEVEL = "intermediate"
ORDER = 29


# ---------------------------------------------------------------------------
# Helpers shared by the checks
# ---------------------------------------------------------------------------

def _refuses(exc, what, call, names=()):
    try:
        call()
    except NotImplementedError:
        raise
    except exc as got:
        text = str(got)
        for name in names:
            assert name in text, (
                "%s raised %s, but its message does not name %r: %r"
                % (what, exc.__name__, name, text))
        return got
    except Exception as wrong:
        raise AssertionError(
            "%s should raise %s, but raised %s: %s"
            % (what, exc.__name__, type(wrong).__name__, wrong))
    raise AssertionError("%s did not raise %s" % (what, exc.__name__))


def _frame(opcode, payload=b"", fin=True):
    """A decoded-frame dict for the stages that take dicts rather than bytes."""
    return {"fin": fin, "opcode": opcode, "payload": payload}


def _client_frame(opcode, payload=b"", fin=True, key=b"\x11\x22\x33\x44"):
    """A masked frame, the way a browser sends one."""
    import stage_03
    return stage_03.write_frame(opcode, payload, fin=fin, mask_key=key)


def _server_frames(blob):
    """Every unmasked frame in `blob`, in order."""
    import stage_03
    frames = []
    pos = 0
    while pos < len(blob):
        frame = stage_03.read_frame(blob, pos, require_mask=False)
        frames.append(frame)
        pos += frame["size"]
    return frames


def _head(response):
    """Split an HTTP response head from the bytes that follow it."""
    head, sep, rest = response.partition(b"\r\n\r\n")
    assert sep, "an HTTP response ends its headers with CRLF CRLF"
    return head, rest


def _request(method="GET", target="/chat", version="HTTP/1.1", **overrides):
    fields = {
        "host": "server.example.com",
        "upgrade": "websocket",
        "connection": "keep-alive, Upgrade",
        "sec-websocket-key": "dGhlIHNhbXBsZSBub25jZQ==",
        "sec-websocket-version": "13",
    }
    fields.update(overrides)
    lines = ["%s %s %s" % (method, target, version)]
    for name, value in fields.items():
        if value is not None:
            lines.append("%s: %s" % (name, value))
    return ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")


# ---------------------------------------------------------------------------
# Stage 1 — handshake
# ---------------------------------------------------------------------------

def check_1():
    import stage_01 as s

    request = _request()
    parsed = s.parse_request(request)
    assert parsed["method"] == "GET"
    assert parsed["target"] == "/chat"
    assert parsed["version"] == "HTTP/1.1"
    assert parsed["headers"]["host"] == "server.example.com"
    assert parsed["headers"]["upgrade"] == "websocket"
    assert s.header_tokens(parsed["headers"], "Connection") == (
        "keep-alive", "upgrade")

    # A repeated header is joined rather than silently overwritten, so both
    # Connection tokens are still there and a duplicated key cannot win.
    duplicate = (b"GET / HTTP/1.1\r\nHost: x\r\n"
                 b"Connection: keep-alive\r\nConnection: Upgrade\r\n"
                 b"Upgrade: websocket\r\n"
                 b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                 b"Sec-WebSocket-Version: 13\r\n\r\n")
    dup = s.parse_request(duplicate)
    assert s.header_tokens(dup["headers"], "connection") == (
        "keep-alive", "upgrade")
    assert dup["headers"]["connection"] == "keep-alive, Upgrade"

    assert s.accept_key("dGhlIHNhbXBsZSBub25jZQ==") == (
        "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")
    assert s.accept_key("AAAAAAAAAAAAAAAAAAAAAA==") == (
        "ICX+Yqv66kxgM0FcWaLWlFLwTAI=")

    accepted = s.accept(request)
    assert accepted["status"] == 101
    assert accepted["protocol"] is None
    response = accepted["response"]
    assert response.startswith(b"HTTP/1.1 101 Switching Protocols\r\n"), (
        "the handshake response must open with 101 Switching Protocols, got %r"
        % (response[:80],))
    assert response.endswith(b"\r\n\r\n")
    lower = response.lower()
    assert b"upgrade: websocket" in lower
    assert b"connection: upgrade" in lower
    assert b"sec-websocket-accept: s3pplmbitxaq9kygzzhzrbk+xoo=" in lower
    assert b"sec-websocket-protocol" not in lower
    assert accepted["headers"]["sec-websocket-accept"] == (
        "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")

    # The client's order is the preference order, not the server's.
    offered = _request(**{"sec-websocket-protocol": "chat, superchat"})
    chosen = s.accept(offered, ("superchat", "chat"))
    assert chosen["protocol"] == "chat", (
        "the server picks the first protocol the client offered that it also "
        "supports; got %r" % (chosen["protocol"],))
    assert b"sec-websocket-protocol: chat" in chosen["response"].lower()
    no_common = s.accept(offered, ("other",))
    assert no_common["protocol"] is None
    assert b"sec-websocket-protocol" not in no_common["response"].lower()
    case_sensitive = s.accept(
        _request(**{"sec-websocket-protocol": "CHAT"}), ("chat",))
    assert case_sensitive["protocol"] is None, (
        "subprotocol names are case-sensitive; CHAT is not chat")

    # A request body after the header is not part of the handshake.
    assert s.parse_request(request + b"body")["target"] == "/chat"

    # Named refusals, with the status the client can act on.
    err = _refuses(s.HandshakeError, "a POST handshake",
                   lambda: s.accept(_request(method="POST")), names=("GET",))
    assert err.status == 405
    err = _refuses(s.HandshakeError, "an HTTP/1.0 handshake",
                   lambda: s.accept(_request(version="HTTP/1.0")),
                   names=("HTTP/1.1",))
    assert err.status == 400
    err = _refuses(s.HandshakeError, "a target with no slash",
                   lambda: s.accept(_request(target="chat")), names=("/",))
    assert err.status == 400
    err = _refuses(s.HandshakeError, "a missing Host",
                   lambda: s.accept(_request(host=None)), names=("Host",))
    assert err.status == 400
    err = _refuses(s.HandshakeError, "an Upgrade that is not websocket",
                   lambda: s.accept(_request(upgrade="h2c")),
                   names=("websocket",))
    assert err.status == 400
    err = _refuses(s.HandshakeError, "Connection without Upgrade",
                   lambda: s.accept(_request(connection="keep-alive")),
                   names=("Upgrade",))
    assert err.status == 400
    err = _refuses(s.HandshakeError, "version 12",
                   lambda: s.accept(_request(**{"sec-websocket-version": "12"})),
                   names=("13",))
    assert err.status == 426, (
        "a version mismatch is a 426, the response that says which version to "
        "try")
    err = _refuses(s.HandshakeError, "a missing Sec-WebSocket-Key",
                   lambda: s.accept(_request(**{"sec-websocket-key": None})),
                   names=("Sec-WebSocket-Key",))
    assert err.status == 400
    err = _refuses(s.HandshakeError, "a key that is not base64",
                   lambda: s.accept(_request(**{"sec-websocket-key": "not base64"})),
                   names=("base64",))
    assert err.status == 400
    err = _refuses(s.HandshakeError, "a key of the wrong length",
                   lambda: s.accept(_request(
                       **{"sec-websocket-key": "QUFBQUFBQUFBQUFBQUFB"})),
                   names=("16",))
    assert err.status == 400

    _refuses(s.HandshakeError, "a missing header terminator",
             lambda: s.parse_request(b"GET / HTTP/1.1\r\nHost: x\r\n"))
    _refuses(s.HandshakeError, "a header with no colon",
             lambda: s.parse_request(b"GET / HTTP/1.1\r\nBad\r\n\r\n"))
    _refuses(s.HandshakeError, "a request that is not bytes",
             lambda: s.parse_request("GET / HTTP/1.1\r\n\r\n"))
    _refuses(s.HandshakeError, "a non-dict header table",
             lambda: s.header_tokens([], "connection"))
    _refuses(s.HandshakeError, "an accept_key that is not a string",
             lambda: s.accept_key(b"dGhlIHNhbXBsZSBub25jZQ=="))


# ---------------------------------------------------------------------------
# Stage 2 — frame header
# ---------------------------------------------------------------------------

def check_2():
    import stage_02 as s

    assert s.encode_header(True, 0x1, 0) == b"\x81\x00"
    assert s.encode_header(True, 0x1, 125) == b"\x81\x7d"
    assert s.encode_header(True, 0x1, 126) == b"\x81\x7e\x00\x7e"
    assert s.encode_header(True, 0x2, 65535) == b"\x82\x7e\xff\xff"
    assert s.encode_header(True, 0x2, 65536) == (
        b"\x82\x7f\x00\x00\x00\x00\x00\x01\x00\x00")
    assert s.encode_header(False, 0x0, 0) == b"\x00\x00"
    assert s.encode_header(True, 0x1, 5, b"abcd") == b"\x81\x85abcd"

    for fin, opcode, length, key in (
            (True, 1, 0, None),
            (True, 1, 125, None),
            (True, 2, 126, None),
            (False, 0, 65535, None),
            (True, 9, 65536, None),
            (True, 1, 5, b"abcd"),
            (False, 0x0, 130, b"\x00\x01\x02\x03")):
        header = s.encode_header(fin, opcode, length, key)
        decoded = s.decode_header(header)
        assert decoded["fin"] is fin
        assert decoded["opcode"] == opcode
        assert decoded["length"] == length
        assert decoded["masked"] is (key is not None)
        assert decoded["mask_key"] == key
        assert decoded["header_length"] == len(header)
        assert decoded["payload_offset"] == len(header)

    flags = s.decode_header(bytes((0xF2, 0x00)))
    assert flags["fin"] is True
    assert flags["rsv1"] is True
    assert flags["rsv2"] is True
    assert flags["rsv3"] is True
    assert flags["opcode"] == 2

    header = s.encode_header(True, 1, 126)
    offset = s.decode_header(b"xx" + header, 2)
    assert offset["length"] == 126
    assert offset["payload_offset"] == 6

    for data, needed in (
            (b"", 2), (b"\x81", 1),
            (b"\x81\x7e", 2), (b"\x81\x7e\x00", 1),
            (b"\x81\x7f" + b"\x00" * 5, 3),
            (b"\x81\x85abc", 1)):
        err = _refuses(s.Incomplete, "a truncated header %r" % (data,),
                       lambda data=data: s.decode_header(data))
        assert err.needed == needed, (
            "a truncated header needs %d more byte(s), got %d"
            % (needed, err.needed))

    _refuses(s.FrameError, "a 16-bit length used for 125",
             lambda: s.decode_header(b"\x81\x7e\x00\x7d"))
    _refuses(s.FrameError, "a 64-bit length used for 65535",
             lambda: s.decode_header(
                 b"\x81\x7f" + (65535).to_bytes(8, "big")))
    _refuses(s.FrameError, "a 64-bit length with its high bit set",
             lambda: s.decode_header(
                 b"\x81\x7f" + (1 << 63).to_bytes(8, "big")))

    _refuses(s.FrameError, "an opcode above 15",
             lambda: s.encode_header(True, 16, 0))
    _refuses(s.FrameError, "a negative length",
             lambda: s.encode_header(True, 1, -1))
    _refuses(s.FrameError, "a length above 2^63-1",
             lambda: s.encode_header(True, 1, 1 << 63))
    _refuses(s.FrameError, "a fin that is not a bool",
             lambda: s.encode_header(1, 1, 0))
    _refuses(s.FrameError, "a mask key that is not four bytes",
             lambda: s.encode_header(True, 1, 0, b"abc"))
    _refuses(s.FrameError, "a position before zero",
             lambda: s.decode_header(b"\x81\x00", -1))
    _refuses(s.FrameError, "a position past the buffer",
             lambda: s.decode_header(b"\x81\x00", 3))
    _refuses(s.FrameError, "a header that is not bytes",
             lambda: s.decode_header("header"))


# ---------------------------------------------------------------------------
# Stage 3 — masks and complete frames
# ---------------------------------------------------------------------------

def check_3():
    import stage_02 as s2
    import stage_03 as s

    key = b"\x37\xfa\x21\x3d"
    masked = s.apply_mask(b"Hello", key)
    assert masked == b"\x7f\x9f\x4d\x51\x58", (
        "the RFC 6455 masking example is not reproduced: got %r" % (masked,))
    assert s.apply_mask(masked, key) == b"Hello"
    _refuses(s.FrameError, "a masking key of three bytes",
             lambda: s.apply_mask(b"x", b"abc"))
    _refuses(s.FrameError, "a payload that is not bytes",
             lambda: s.apply_mask("x", key))

    plain = s.write_frame(1, b"Hello")
    assert plain == b"\x81\x05Hello"
    client = s.write_frame(1, b"Hello", mask_key=key)
    assert client == b"\x81\x85" + key + masked, (
        "a masked client frame is the header with MASK set, then the key, then "
        "the XORed payload; got %r" % (client,))

    frame = s.read_frame(client, require_mask=True)
    assert frame["payload"] == b"Hello"
    assert frame["masked"] is True
    assert frame["mask_key"] == key
    assert frame["size"] == len(client)
    assert frame["opcode"] == 1
    assert frame["fin"] is True

    prefixed = b"xxx" + client
    at = s.read_frame(prefixed, 3, require_mask=True)
    assert at["payload"] == b"Hello"
    assert at["size"] == len(client)

    _refuses(s2.Incomplete, "a frame whose payload is short",
             lambda: s.read_frame(b"\x81\x05Hel"), names=("2",))
    err = _refuses(s2.Incomplete, "a frame whose payload is short",
                   lambda: s.read_frame(b"\x81\x05Hel"))
    assert err.needed == 2
    err = _refuses(s2.Incomplete, "a 126-byte payload that is short",
                   lambda: s.read_frame(b"\x81\x7e\x00\x7e" + b"x" * 100))
    assert err.needed == 26

    _refuses(s.FrameError, "an unmasked client frame",
             lambda: s.read_frame(plain, require_mask=True))
    _refuses(s.FrameError, "a masked server frame",
             lambda: s.read_frame(client, require_mask=False))
    _refuses(s.FrameError, "a require_mask that is not a bool",
             lambda: s.read_frame(plain, require_mask="yes"))
    _refuses(s2.FrameError, "a frame payload that is not bytes",
             lambda: s.write_frame(1, "Hello"))
    _refuses(s2.FrameError, "a mask key of five bytes",
             lambda: s.write_frame(1, b"Hello", mask_key=b"abcde"))

    big = b"x" * 126
    framed = s.write_frame(2, big)
    assert framed[:4] == b"\x82\x7e\x00\x7e"
    assert s.read_frame(framed)["payload"] == big
    huge = b"y" * 65536
    framed = s.write_frame(2, huge)
    assert framed[:10] == b"\x82\x7f" + (65536).to_bytes(8, "big")
    assert s.read_frame(framed)["payload"] == huge
    assert s.read_frame(s.write_frame(1, b""))["payload"] == b""


# ---------------------------------------------------------------------------
# Stage 4 — control frames and close codes
# ---------------------------------------------------------------------------

def check_4():
    import stage_03 as s3
    import stage_04 as s

    ping = s3.read_frame(s.ping(b"x"))
    assert ping["opcode"] == 0x9
    assert ping["payload"] == b"x"
    assert ping["fin"] is True
    pong = s3.read_frame(s.pong(b"x"))
    assert pong["opcode"] == 0xA
    assert pong["payload"] == b"x"
    close = s3.read_frame(s.close(1000, b"bye"))
    assert close["opcode"] == 0x8
    assert s.parse_close(close["payload"]) == {"code": 1000, "reason": b"bye"}
    assert s.close_payload(1000, b"bye") == b"\x03\xe8bye"
    assert s.close_payload(None) == b""
    assert s.close(None) == b"\x88\x00"
    assert s.parse_close(b"") == {"code": None, "reason": b""}
    assert s.parse_close(b"\x0b\xb8app") == {"code": 3000, "reason": b"app"}

    for code in (1000, 1001, 1002, 1003, 1007, 1008, 1009, 1010, 1011,
                 1012, 1013, 1014, 3000, 4999):
        assert code in s.SENDABLE_CLOSE_CODES, "%d is a sendable close code" % code
        body = s.close_payload(code, b"")
        assert s.parse_close(body)["code"] == code
    for code in (0, 999, 1004, 1005, 1006, 1015, 2999, 5000):
        assert code not in s.SENDABLE_CLOSE_CODES, (
            "%d may not be sent as a close code" % code)
        _refuses(s.ControlError, "close code %d" % (code,),
                 lambda code=code: s.close_payload(code, b""), names=(str(code),))

    _refuses(s.ControlError, "a one-byte close payload",
             lambda: s.parse_close(b"\x03"))
    _refuses(s.ControlError, "a close payload that is not bytes",
             lambda: s.parse_close("\x03\xe8"))
    _refuses(s.ControlError, "a close reason without a code",
             lambda: s.close_payload(None, b"why"))
    _refuses(s.ControlError, "a close reason that overflows a control frame",
             lambda: s.close_payload(1000, b"x" * 124))
    assert s.close_payload(1000, b"x" * 123) == b"\x03\xe8" + b"x" * 123

    # Control frames are FIN, at most 125 bytes, and never fragmented.
    assert s.validate_frame(_frame(0x1, b"data")) is None
    assert s.validate_frame(_frame(0x9, b"ping")) is None
    assert s.validate_frame(_frame(0x8, b"\x03\xe8bye")) is None
    _refuses(s.ControlError, "a fragmented ping",
             lambda: s.validate_frame(_frame(0x9, b"x", fin=False)))
    _refuses(s.ControlError, "a ping over 125 bytes",
             lambda: s.validate_frame(_frame(0x9, b"x" * 126)))
    _refuses(s.ControlError, "a close with an invalid code",
             lambda: s.validate_frame(_frame(0x8, b"\x03\xed")))
    _refuses(s.ControlError, "a reserved opcode",
             lambda: s.validate_frame(_frame(0x3, b"x")))
    _refuses(s.ControlError, "an opcode above 15",
             lambda: s.validate_frame(_frame(0x10, b"x")))
    _refuses(s.ControlError, "a fin that is not a bool",
             lambda: s.validate_frame({"fin": 1, "opcode": 1,
                                       "payload": b"x"}))
    _refuses(s.ControlError, "a frame with no payload",
             lambda: s.validate_frame({"fin": True, "opcode": 9}))
    _refuses(s.ControlError, "a ping over 125 bytes",
             lambda: s.ping(b"x" * 126))
    _refuses(s.ControlError, "a pong over 125 bytes",
             lambda: s.pong(b"x" * 126))
    _refuses(s.ControlError, "a close with an invalid code",
             lambda: s.close(1005, b""))


# ---------------------------------------------------------------------------
# Stage 5 — fragmentation
# ---------------------------------------------------------------------------

def check_5():
    import stage_05 as s

    assembler = s.Assembler()
    events = assembler.feed(_frame(0x1, b"hello"))
    assert events == [{"type": "message", "opcode": 0x1,
                       "payload": b"hello", "fragments": 1}]
    assert assembler.in_message is False

    starting = assembler.feed(_frame(0x1, b"Hel", fin=False))
    assert starting == []
    assert assembler.in_message is True
    assert assembler.feed(_frame(0x0, b"lo", fin=True)) == [
        {"type": "message", "opcode": 0x1, "payload": b"Hello", "fragments": 2}]
    assert assembler.in_message is False

    assert assembler.feed(_frame(0x2, b"a", fin=False)) == []
    assert assembler.feed(_frame(0x0, b"", fin=False)) == []
    assert assembler.feed(_frame(0x0, b"b", fin=True)) == [
        {"type": "message", "opcode": 0x2, "payload": b"ab", "fragments": 3}]

    assert assembler.feed(_frame(0x1, b"a", fin=False)) == []
    ping = assembler.feed(_frame(0x9, b"p"))
    assert ping == [{"type": "ping", "opcode": 0x9, "payload": b"p"}]
    assert assembler.in_message is True
    assert assembler.feed(_frame(0x0, b"b", fin=True))[0]["payload"] == b"ab"

    assert assembler.feed(_frame(0x1, b"")) == [
        {"type": "message", "opcode": 0x1, "payload": b"", "fragments": 1}]

    _refuses(s.MessageError, "a continuation with no start",
             lambda: s.Assembler().feed(_frame(0x0, b"x")))
    _refuses(s.MessageError, "a new text frame during a fragmented message",
             lambda: (lambda a: (a.feed(_frame(0x1, b"a", fin=False)),
                                 a.feed(_frame(0x1, b"b"))))(s.Assembler()),
             names=("fragmented",))
    import stage_02
    _refuses(stage_02.FrameError, "a fragmented ping",
             lambda: s.Assembler().feed(_frame(0x9, b"x", fin=False)))
    _refuses(stage_02.FrameError, "a ping over 125 bytes",
             lambda: s.Assembler().feed(_frame(0x9, b"x" * 126)))
    _refuses(stage_02.FrameError, "a reserved opcode",
             lambda: s.Assembler().feed(_frame(0x3, b"x")))
    _refuses(stage_02.FrameError, "a close with an invalid code",
             lambda: s.Assembler().feed(_frame(0x8, b"\x03\xed")))
    _refuses(s.MessageError, "a frame with no payload",
             lambda: s.Assembler().feed({"fin": True, "opcode": 1}))
    _refuses(s.MessageError, "a frame that is not a dict",
             lambda: s.Assembler().feed("frame"))
    _refuses(s.MessageError, "a maximum message size below zero",
             lambda: s.Assembler(max_message=-1))
    _refuses(s.MessageError, "a maximum message size that is not an int",
             lambda: s.Assembler(max_message="1k"))

    small = s.Assembler(max_message=5)
    _refuses(s.MessageError, "a six-byte message with a five-byte limit",
             lambda: small.feed(_frame(0x1, b"123456")), names=("5",))
    small = s.Assembler(max_message=5)
    assert small.feed(_frame(0x1, b"123", fin=False)) == []
    _refuses(s.MessageError, "a fragmented message over the limit",
             lambda: small.feed(_frame(0x0, b"456", fin=True)), names=("5",))

    unfinished = s.Assembler()
    unfinished.feed(_frame(0x1, b"a", fin=False))
    _refuses(s.MessageError, "an unfinished fragmented message",
             lambda: unfinished.finish(), names=("fragmented",))
    assert s.Assembler().finish() is None

    reset = s.Assembler()
    reset.feed(_frame(0x1, b"a", fin=False))
    assert reset.in_message is True
    reset.reset()
    assert reset.in_message is False
    assert reset.feed(_frame(0x1, b"b"))[0]["payload"] == b"b"


# ---------------------------------------------------------------------------
# Stage 6 — UTF-8
# ---------------------------------------------------------------------------

def check_6():
    import stage_06 as s

    assert s.validate_utf8(b"hello") == "hello"
    assert s.validate_utf8(b"") == ""
    assert s.validate_utf8("é".encode()) == "é"
    assert s.validate_utf8("€".encode()) == "€"
    assert s.validate_utf8("😀".encode()) == "😀"
    assert s.validate_utf8(bytearray("a€😀".encode())) == "a€😀"
    assert s.validate_utf8(b"\xf0\x9f\x98\x80") == "😀"

    for bad, offset, reason in (
            (b"\x80", 0, "start"),
            (b"\xc0\xaf", 0, "start"),
            (b"\xed\xa0\x80", 1, "continuation"),
            (b"\xf4\x90\x80\x80", 1, "continuation"),
            (b"\xe2\x28\xa1", 1, "continuation"),
            (b"\xe0\x80", 1, "continuation"),
            (b"\xf0\x80", 1, "continuation"),
            (b"ab\x80", 2, "start"),
            (b"\xff", 0, "start"),
            (b"\xe2\x82", 0, "truncated"),
            (b"\xf0\x9f\x98", 0, "truncated")):
        err = _refuses(s.UTF8Error, "invalid UTF-8 %r" % (bad,),
                       lambda bad=bad: s.validate_utf8(bad))
        assert err.offset == offset, (
            "%r fails at byte %d, got %d" % (bad, offset, err.offset))
        assert reason in str(err), (
            "%r should be described as %r, got %r" % (bad, reason, str(err)))

    _refuses(s.UTF8Error, "a text payload that is not bytes",
             lambda: s.validate_utf8("hello"))

    stream = s.UTF8Stream()
    for byte in "a€😀".encode():
        stream.feed(bytes((byte,)))
    assert stream.finish() == "a€😀"

    stream = s.UTF8Stream()
    stream.feed(b"a")
    stream.feed(b"\xe2")
    stream.feed(b"\x82")
    stream.feed(b"\xac")
    assert stream.finish() == "a€"

    stream = s.UTF8Stream()
    stream.feed("a€😀".encode()[:3])
    stream.feed("a€😀".encode()[3:])
    assert stream.finish() == "a€😀"

    stream = s.UTF8Stream()
    stream.feed(b"\xed")
    err = _refuses(s.UTF8Error, "a surrogate split across fragments",
                   lambda: stream.feed(b"\xa0\x80"))
    assert err.offset == 1, (
        "the first bad byte of the surrogate is the continuation, got %d"
        % (err.offset,))

    stream = s.UTF8Stream()
    stream.feed(b"\xe2\x82")
    _refuses(s.UTF8Error, "a truncated character at finish",
             lambda: stream.finish(), names=("truncated",))

    stream = s.UTF8Stream()
    assert stream.finish() == ""
    _refuses(s.UTF8Error, "finishing a stream twice",
             lambda: stream.finish())

    stream = s.UTF8Stream()
    stream.feed(b"old")
    stream.reset()
    stream.feed(b"new")
    assert stream.finish() == "new"
    _refuses(s.UTF8Error, "feeding a finished stream",
             lambda: stream.feed(b"x"))
    _refuses(s.UTF8Error, "feeding a fragment that is not bytes",
             lambda: s.UTF8Stream().feed("x"))


# ---------------------------------------------------------------------------
# Stage 7 — the streaming state machine
# ---------------------------------------------------------------------------

def check_7():
    import stage_04 as s4
    import stage_07 as s

    stream = s.FrameStream()
    events = stream.feed(_client_frame(1, b"Hello"))
    assert len(events) == 1
    assert events[0] == {"type": "message", "opcode": 1,
                         "payload": b"Hello", "fragments": 1, "text": "Hello"}
    assert stream.closed is False
    assert stream.feed(b"") == []

    # The same bytes split at every byte must produce the same event.
    data = _client_frame(1, "€".encode())
    split = s.FrameStream()
    collected = []
    for byte in data:
        collected += split.feed(bytes((byte,)))
    assert collected == [{"type": "message", "opcode": 1,
                          "payload": "€".encode(), "fragments": 1,
                          "text": "€"}], (
        "a frame split at every byte must produce one message; got %r"
        % (collected,))

    two = s.FrameStream()
    events = two.feed(_client_frame(1, b"a") + _client_frame(1, b"b"))
    assert [event["text"] for event in events] == ["a", "b"]

    fragmented = s.FrameStream()
    assert fragmented.feed(_client_frame(1, b"Hel", fin=False)) == []
    events = fragmented.feed(_client_frame(9, b"p"))
    assert events == [{"type": "ping", "payload": b"p"}]
    events = fragmented.feed(_client_frame(0, b"lo", fin=True))
    assert events[0]["text"] == "Hello"

    # A fragmented UTF-8 character whose bytes are split across frames.
    euro = "€".encode()
    utf8 = s.FrameStream()
    assert utf8.feed(_client_frame(1, euro[:1], fin=False)) == []
    events = utf8.feed(_client_frame(0, euro[1:], fin=True))
    assert events[0]["text"] == "€"

    close = s.FrameStream()
    events = close.feed(_client_frame(8, s4.close_payload(1000, b"bye")))
    assert events == [{"type": "close", "code": 1000, "reason": "bye"}]
    assert close.closed is True
    assert close.finish() is None
    _refuses(s.ProtocolError, "a frame after a close frame",
             lambda: close.feed(_client_frame(1, b"x")), names=("close",))

    bad_rsv = bytearray(_client_frame(1, b"x"))
    bad_rsv[0] |= 0x40
    _refuses(s.ProtocolError, "a reserved bit",
             lambda: s.FrameStream().feed(bytes(bad_rsv)), names=("reserved",))
    _refuses(s.ProtocolError, "a reserved opcode",
             lambda: s.FrameStream().feed(_client_frame(3, b"x")),
             names=("reserved",))
    _refuses(s.ProtocolError, "a fragmented control frame",
             lambda: s.FrameStream().feed(_client_frame(9, b"x", fin=False)),
             names=("FIN",))
    _refuses(s.ProtocolError, "a control frame over 125 bytes",
             lambda: s.FrameStream().feed(_client_frame(9, b"x" * 126)))
    _refuses(s.ProtocolError, "an unmasked client frame",
             lambda: s.FrameStream().feed(
                 __import__("stage_03").write_frame(1, b"x")),
             names=("masked",))
    _refuses(s.ProtocolError, "invalid UTF-8 in a text frame",
             lambda: s.FrameStream().feed(_client_frame(1, b"\xff")),
             names=("UTF-8",))
    _refuses(s.ProtocolError, "invalid UTF-8 in a close reason",
             lambda: s.FrameStream().feed(
                 _client_frame(8, (1000).to_bytes(2, "big") + b"\xff")),
             names=("UTF-8",))
    _refuses(s.ProtocolError, "a message over the limit",
             lambda: s.FrameStream(max_message=3).feed(
                 _client_frame(1, b"hello")), names=("3",))

    import stage_03
    key = b"\x01\x02\x03\x04"
    body = stage_03.apply_mask(b"hello", key)
    nonminimal = b"\x81\xfe\x00\x05" + key + body
    _refuses(s.ProtocolError, "a non-minimal 16-bit length",
             lambda: s.FrameStream().feed(nonminimal))

    partial = s.FrameStream()
    assert partial.feed(_client_frame(1, b"hello")[:3]) == []
    _refuses(s.ProtocolError, "a stream that ends inside a frame",
             lambda: partial.finish(), names=("frame",))

    unfinished = s.FrameStream()
    unfinished.feed(_client_frame(1, b"a", fin=False))
    _refuses(s.ProtocolError, "a stream that ends inside a message",
             lambda: unfinished.finish(), names=("fragmented",))

    server = s.FrameStream(require_mask=False)
    events = server.feed(stage_03.write_frame(1, b"hi"))
    assert events[0]["text"] == "hi"
    _refuses(s.ProtocolError, "a masked server frame",
             lambda: s.FrameStream(require_mask=False).feed(
                 _client_frame(1, b"x")), names=("masked",))

    assert s.FrameStream().feed(_client_frame(9, b"")) == [
        {"type": "ping", "payload": b""}]
    huge = s.FrameStream()
    events = huge.feed(_client_frame(2, b"x" * 65536))
    assert len(events) == 1 and len(events[0]["payload"]) == 65536

    reset = s.FrameStream()
    reset.feed(_client_frame(8, s4.close_payload(1000, b"")))
    assert reset.closed is True
    reset.reset()
    assert reset.closed is False
    assert reset.feed(_client_frame(1, b"again"))[0]["text"] == "again"

    bad_split = s.FrameStream()
    assert bad_split.feed(_client_frame(1, b"\xed", fin=False)) == []
    _refuses(s.ProtocolError, "invalid UTF-8 split across fragments",
             lambda: bad_split.feed(_client_frame(0, b"\xa0\x80", fin=True)),
             names=("UTF-8",))


# ---------------------------------------------------------------------------
# Stage 8 — the session
# ---------------------------------------------------------------------------

def check_8():
    import stage_03
    import stage_04
    import stage_08 as s

    request = _request(**{"sec-websocket-protocol": "chat, superchat"})
    session = s.Session(protocols=("chat",))
    response = session.feed(request)
    head, rest = _head(response)
    assert head.startswith(b"HTTP/1.1 101 Switching Protocols"), head
    assert b"sec-websocket-protocol: chat" in head.lower()
    assert rest == b""
    assert session.phase == "open"
    report = session.report()
    assert report["handshake"] == "accepted"
    assert report["protocol"] == "chat"
    assert report["bytes_in"] == len(request)
    assert report["bytes_out"] == len(response)

    echoed = session.feed(_client_frame(1, b"hello"))
    frames = _server_frames(echoed)
    assert len(frames) == 1
    assert frames[0]["opcode"] == 1
    assert frames[0]["payload"] == b"hello"
    assert frames[0]["masked"] is False
    report = session.report()
    assert report["messages"] == 1 and report["text_messages"] == 1

    pong = session.feed(_client_frame(9, b"ping-data"))
    frames = _server_frames(pong)
    assert len(frames) == 1
    assert frames[0]["opcode"] == 0xA
    assert frames[0]["payload"] == b"ping-data"
    assert session.report()["pings"] == 1
    assert session.feed(_client_frame(10, b"pong-data")) == b""
    assert session.report()["pongs"] == 1

    fragmented = session.feed(_client_frame(1, b"Hel", fin=False)
                              + _client_frame(9, b"p")
                              + _client_frame(0, b"lo", fin=True))
    frames = _server_frames(fragmented)
    assert [frame["opcode"] for frame in frames] == [0xA, 0x1]
    assert frames[1]["payload"] == b"Hello"

    binary = session.feed(_client_frame(2, b"\x00\x01\x02"))
    frames = _server_frames(binary)
    assert frames[0]["opcode"] == 2
    assert frames[0]["payload"] == b"\x00\x01\x02"
    assert session.report()["binary_messages"] == 1

    out = session.feed(_client_frame(8, stage_04.close_payload(1000, b"bye")))
    frames = _server_frames(out)
    assert len(frames) == 1 and frames[0]["opcode"] == 8
    assert stage_04.parse_close(frames[0]["payload"]) == {
        "code": 1000, "reason": b"bye"}
    assert session.phase == "closed"
    assert session.report()["closes"] == 1
    assert session.feed(_client_frame(1, b"ignored")) == b""

    # Invalid text becomes a 1007 close, not an echo.
    bad = s.Session()
    bad.feed(_request())
    out = bad.feed(_client_frame(1, b"\xff"))
    frames = _server_frames(out)
    assert frames[0]["opcode"] == 8
    assert stage_04.parse_close(frames[0]["payload"])["code"] == 1007
    assert bad.report()["protocol_errors"] == 1
    assert bad.phase == "closed"

    # A bad handshake is an HTTP answer.
    rejected = s.Session()
    out = rejected.feed(_request(method="POST"))
    head, rest = _head(out)
    assert head.startswith(b"HTTP/1.1 405 Method Not Allowed"), head
    assert rest.endswith(b"\n")
    assert rejected.phase == "closed"
    assert rejected.report()["handshake"] == "rejected"

    wrong_version = s.Session()
    out = wrong_version.feed(_request(**{"sec-websocket-version": "12"}))
    head, _ = _head(out)
    assert head.startswith(b"HTTP/1.1 426 Upgrade Required"), head
    assert b"sec-websocket-version: 13" in head.lower()
    assert wrong_version.report()["handshake"] == "rejected"

    # The handshake may arrive one byte at a time.
    split = s.Session()
    pieces = []
    for byte in _request():
        pieces.append(split.feed(bytes((byte,))))
    response = b"".join(pieces)
    assert response.startswith(b"HTTP/1.1 101 Switching Protocols"), (
        "a handshake split at every byte must still produce one 101")
    assert split.phase == "open"

    # The handshake and the first frame may share a chunk.
    together = s.Session()
    out = together.feed(_request() + _client_frame(1, b"same chunk"))
    head, rest = _head(out)
    assert head.startswith(b"HTTP/1.1 101")
    frames = _server_frames(rest)
    assert frames[0]["payload"] == b"same chunk"

    clean = s.Session()
    clean.feed(_request())
    out = clean.feed(_client_frame(8, b""))
    frames = _server_frames(out)
    assert stage_04.parse_close(frames[0]["payload"])["code"] == 1000

    finishing = s.Session()
    finishing.feed(_request())
    out = finishing.feed(_client_frame(1, b"a", fin=False))
    assert out == b""
    out = finishing.finish()
    frames = _server_frames(out)
    assert frames[0]["opcode"] == 8
    assert stage_04.parse_close(frames[0]["payload"])["code"] == 1002
    assert finishing.phase == "closed"
    assert finishing.finish() == b""

    incomplete = s.Session()
    assert incomplete.feed(b"GET / HTTP/1.1\r\n") == b""
    assert incomplete.finish() == b""
    assert incomplete.report()["handshake"] == "incomplete"
    assert incomplete.phase == "closed"

    limited = s.Session(max_message=3)
    limited.feed(_request())
    out = limited.feed(_client_frame(1, b"hello"))
    frames = _server_frames(out)
    assert stage_04.parse_close(frames[0]["payload"])["code"] == 1009

    report = session.report()
    report["messages"] = 999
    assert session.report()["messages"] != 999, (
        "report() must return a copy, not its own mutable state")

    _refuses(TypeError, "a session fed text",
             lambda: s.Session().feed("GET / HTTP/1.1\r\n\r\n"))


STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The handshake, and the nonce a browser checks",
        tags=["http", "handshake", "encoding"],
        action="Write `parse_request`, `header_tokens`, `accept_key` and "
               "`accept` in stage_01.py.",
        predict="Why a version mismatch deserves a different status than a "
                "missing Host header, and what a browser checks in the accept "
                "value before it sends a single frame.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The frame header, its width and its shortest form",
        tags=["framing", "encoding", "boundary"],
        action="Write `encode_header` and `decode_header`, including "
               "`Incomplete.needed`, in stage_02.py.",
        predict="How many bytes the reader needs before it knows where the "
                "payload starts, and why a length that is legal but not the "
                "shortest form is still a protocol error.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The payload, the mask and the direction rule",
        tags=["masking", "framing", "invariants"],
        action="Write `apply_mask`, `read_frame` and `write_frame` in "
               "stage_03.py.",
        predict="Why masking is its own inverse, and why the same function "
                "that reads a client frame must refuse a server frame with the "
                "mask bit set.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="Control frames and the close code that may be sent",
        tags=["control", "lifecycle", "boundary"],
        action="Write `validate_frame`, `close_payload`, `parse_close`, "
               "`ping`, `pong` and `close` in stage_04.py.",
        predict="Why 1005 is useful in a report but illegal on the wire, and "
                "what a close payload of one byte could possibly mean.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="Fragmentation, and the control frame in the middle",
        tags=["fragmentation", "state-machine", "lifecycle"],
        action="Write `Assembler` (`__init__`, `feed`, `finish`, `reset`) in "
               "stage_05.py.",
        predict="What must happen to a ping that arrives between the first and "
                "last fragment of a text message, and why a new text frame "
                "during that message is not a second message.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="UTF-8, even when a character is split across fragments",
        tags=["utf-8", "encoding", "boundary"],
        action="Write `validate_utf8` and `UTF8Stream` (`feed`, `finish`, "
               "`reset`) in stage_06.py.",
        predict="Which byte of a surrogate pair must be rejected, and why a "
                "fragment boundary is allowed to fall in the middle of a "
                "multi-byte character but not in the middle of a bad one.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The streaming reader, and every chunking of the same bytes",
        tags=["streaming", "protocol", "state-machine"],
        action="Write `FrameStream` (`__init__`, `feed`, `finish`, `reset`) in "
               "stage_07.py.",
        predict="Why a protocol error is an exception carrying a close code, "
                "and what a reader must do with the bytes after a close frame.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The session: handshake, echo, pings and a close",
        tags=["session", "lifecycle", "observability"],
        action="Write `Session` (`__init__`, `feed`, `finish`, `report`) in "
               "stage_08.py.",
        predict="Why the report counts bytes rather than beliefs, and what a "
                "server owes a client whose handshake was bad.",
        check=check_8,
    ),
]
