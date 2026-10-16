"""MQTT Broker From Scratch — stage 2: The two-byte string and the CONNECT.

See `stage_01.py` for the surface and the design decisions; this is the handshake
a session starts with.
"""

import stage_01

CONNECT = stage_01.CONNECT
CONNACK = stage_01.CONNACK
PUBLISH = stage_01.PUBLISH
PUBACK = stage_01.PUBACK
PUBREC = stage_01.PUBREC
PUBREL = stage_01.PUBREL
PUBCOMP = stage_01.PUBCOMP
SUBSCRIBE = stage_01.SUBSCRIBE
SUBACK = stage_01.SUBACK
UNSUBSCRIBE = stage_01.UNSUBSCRIBE
UNSUBACK = stage_01.UNSUBACK
PINGREQ = stage_01.PINGREQ
PINGRESP = stage_01.PINGRESP
DISCONNECT = stage_01.DISCONNECT

PROTOCOL_NAME = "MQTT"
PROTOCOL_LEVEL = 4
MAX_STRING_BYTES = 65_535

CONNECT_KEYS = ("protocol_name", "protocol_level", "clean_start", "keep_alive",
                "client_id", "will", "username", "password")

CLIENT_TYPES = (CONNECT, PUBLISH, PUBACK, PUBREC, PUBREL, PUBCOMP, SUBSCRIBE,
                UNSUBSCRIBE, PINGREQ, DISCONNECT)

CONNACK_ACCEPTED = 0
CONNACK_REFUSED_VERSION = 1
CONNACK_REFUSED_IDENTIFIER = 2
CONNACK_REFUSED_UNAVAILABLE = 3
CONNACK_REFUSED_CREDENTIALS = 4
CONNACK_REFUSED_NOT_AUTHORIZED = 5

CONNACK_CODES = (CONNACK_ACCEPTED, CONNACK_REFUSED_VERSION,
                 CONNACK_REFUSED_IDENTIFIER, CONNACK_REFUSED_UNAVAILABLE,
                 CONNACK_REFUSED_CREDENTIALS, CONNACK_REFUSED_NOT_AUTHORIZED)

WILL_KEYS = ("topic", "payload", "qos", "retain")


def _check_buffer(data, what):
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    raise stage_01.ProtocolError("%s must be bytes, not %s"
                                % (what, type(data).__name__,))


def _check_pos(data, pos):
    if isinstance(pos, bool) or not isinstance(pos, int):
        raise stage_01.ProtocolError("a position must be an int, not %r" % (pos,))
    if not 0 <= pos <= len(data):
        raise stage_01.ProtocolError("a position of %d in %d bytes"
                                     % (pos, len(data)))
    return pos


def _short(data, pos, need):
    """The shortfall of `need` bytes at `pos`, refused as an `Incomplete`."""
    have = len(data) - pos
    if have < need:
        raise stage_01.Incomplete(need - have)


def read_string(data, pos=0):
    """The MQTT string at `pos`, as `(text, pos_after)`.

    Two bytes of length, big-endian, then that many bytes of UTF-8 — so the
    length counts *bytes* and never characters, and a reader that measures the
    text it decoded has already lost the difference. A payload that is not
    UTF-8 is a `ProtocolError` naming the bytes, because no amount of waiting
    turns it into text; a buffer that is short of the length or of the payload
    is an `Incomplete` with the shortfall exactly.
    """
    data = _check_buffer(data, "the buffer a string is read from")
    pos = _check_pos(data, pos)
    _short(data, pos, 2)
    length = (data[pos] << 8) | data[pos + 1]
    start = pos + 2
    _short(data, start, length)
    payload = data[start:start + length]
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise stage_01.ProtocolError("a string payload of %r is not UTF-8"
                                     % (payload,))
    return text, start + length


def read_payload(data, pos=0):
    """Two bytes of length and that many raw bytes, as `(payload, pos_after)`.

    Not a string: a will message and a password are binary data with the same
    two-byte length in front, and decoding them would refuse a legal password or
    a will whose bytes are not text at all.
    """
    data = _check_buffer(data, "the buffer a payload is read from")
    pos = _check_pos(data, pos)
    _short(data, pos, 2)
    length = (data[pos] << 8) | data[pos + 1]
    start = pos + 2
    _short(data, start, length)
    return data[start:start + length], start + length


def write_string(text):
    """`text` as an MQTT string: its UTF-8 bytes, two bytes of length in front."""
    if not isinstance(text, str):
        raise stage_01.ProtocolError("a string must be a str, not %s"
                                     % (type(text).__name__,))
    payload = text.encode("utf-8")
    if len(payload) > MAX_STRING_BYTES:
        raise stage_01.ProtocolError("a string of %d bytes is above the maximum %d"
                                     % (len(payload), MAX_STRING_BYTES))
    return bytes([len(payload) >> 8, len(payload) & 0xFF]) + payload


def read_connect(data, pos=0):
    """The CONNECT at `pos` of its own body, as `(connect, pos_after)`.

    `data` is the packet's body, exactly: the fixed header has already said how
    long it is, so a byte left over at the end is a byte the packet never
    claimed, and one that is missing is a packet that has not arrived. The
    connect flags decide which fields exist — the will's topic and payload, the
    username and the password, in that order — so a reader that reads them
    unconditionally reads the next field's bytes as this one's.

    The protocol name and level are *returned*, not judged: a broker answers a
    name or a level it does not speak with `CONNACK_REFUSED_VERSION` and closes,
    which is a conversation, not a malformed packet. Everything a peer cannot
    mean — the reserved bit set, a will QoS or retain bit with no will, a
    password with no username, a trailing byte — is a `ProtocolError` naming what
    arrived.
    """
    data = _check_buffer(data, "the buffer a CONNECT is read from")
    pos = _check_pos(data, pos)
    name, pos = read_string(data, pos)
    _short(data, pos, 1)
    level = data[pos]
    pos += 1
    _short(data, pos, 1)
    flags = data[pos]
    pos += 1
    _short(data, pos, 2)
    keep_alive = (data[pos] << 8) | data[pos + 1]
    pos += 2
    if flags & 0x01:
        raise stage_01.ProtocolError(
            "the reserved flag bit is set (the flags byte was 0x%02x)" % (flags,))
    will_qos = (flags >> 3) & 0x03
    if will_qos == 3:
        raise stage_01.ProtocolError(
            "a will QoS of 3 is malformed (the flags byte was 0x%02x)" % (flags,))
    has_will = bool(flags & 0x04)
    if not has_will and will_qos:
        raise stage_01.ProtocolError(
            "a will QoS of %d with no will flag (the flags byte was 0x%02x)"
            % (will_qos, flags))
    if not has_will and flags & 0x20:
        raise stage_01.ProtocolError(
            "a will retain bit with no will flag (the flags byte was 0x%02x)"
            % (flags,))
    if flags & 0x40 and not flags & 0x80:
        raise stage_01.ProtocolError(
            "a password with no username (the flags byte was 0x%02x)" % (flags,))
    client_id, pos = read_string(data, pos)
    will = None
    if has_will:
        topic, pos = read_string(data, pos)
        payload, pos = read_payload(data, pos)
        will = {"topic": topic, "payload": payload, "qos": will_qos,
                "retain": bool(flags & 0x20)}
    username = None
    if flags & 0x80:
        username, pos = read_string(data, pos)
    password = None
    if flags & 0x40:
        password, pos = read_payload(data, pos)
    if pos != len(data):
        raise stage_01.ProtocolError(
            "a trailing byte after the CONNECT's fields (%d bytes of body, %d "
            "read)" % (len(data), pos))
    connect = {"protocol_name": name, "protocol_level": level,
               "clean_start": bool(flags & 0x02), "keep_alive": keep_alive,
               "client_id": client_id, "will": will, "username": username,
               "password": password}
    return connect, pos


def connack_code(connect):
    """What a broker answers a parsed CONNECT, as one of the six codes.

    Three questions, in the order a broker may answer them: does it speak this
    protocol name and level (1), may it take this client's identifier (2 — an
    empty name is legal only when the client also asks for a clean start), and
    only then is the session the client asked for a conversation about
    sessions.
    """
    if not isinstance(connect, dict):
        raise stage_01.ProtocolError("a CONNECT must be a dict, not %s"
                                     % (type(connect).__name__,))
    for key in CONNECT_KEYS:
        if key not in connect:
            raise stage_01.ProtocolError("a CONNECT with no %r in it" % (key,))
    if (connect["protocol_name"] != PROTOCOL_NAME
            or connect["protocol_level"] != PROTOCOL_LEVEL):
        return CONNACK_REFUSED_VERSION
    if not connect["client_id"] and not connect["clean_start"]:
        return CONNACK_REFUSED_IDENTIFIER
    return CONNACK_ACCEPTED


def write_connack(session_present, code):
    """The two bytes of a CONNACK: the session-present bit, then the code.

    A refusal may not carry the bit: a client that is told its CONNECT was
    refused and also that a session is waiting for it has two answers to one
    question, and the state the broker would have resumed does not exist.
    """
    if isinstance(session_present, bool):
        present = 1 if session_present else 0
    elif isinstance(session_present, int) and session_present in (0, 1):
        present = session_present
    else:
        raise stage_01.ProtocolError("a session-present flag must be a bool or 0/1, "
                                     "not %r" % (session_present,))
    if isinstance(code, bool) or code not in CONNACK_CODES:
        raise stage_01.ProtocolError("a CONNACK code of %r is not one of the six "
                                     "(%r)" % (code, CONNACK_CODES))
    if code != CONNACK_ACCEPTED and present:
        raise stage_01.ProtocolError(
            "session present set on a refusal (code %d): a refused CONNECT "
            "resumes no session" % (code,))
    return bytes([present, code])
