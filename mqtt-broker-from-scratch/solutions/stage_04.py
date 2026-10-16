"""MQTT Broker From Scratch — stage 4: SUBSCRIBE, SUBACK and the granted QoS.

See `stage_01.py` for the surface and the design decisions; this is the ask a
client makes and the grant a broker answers with — two numbers that need not
agree, and a packet id that must come back unchanged.
"""

import stage_01

SUBSCRIBE_FLAGS = 0b0010
MAX_QOS = 2
SUBACK_FAILURE = 0x80

SUBSCRIBE_KEYS = ("packet_id", "topics")


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


def _check_id(packet_id):
    """A packet id as the wire can carry it: an int between 1 and 65535."""
    if isinstance(packet_id, bool) or not isinstance(packet_id, int):
        raise stage_01.ProtocolError("a packet id must be an int, not %s"
                                     % (type(packet_id).__name__,))
    if not 1 <= packet_id <= 65535:
        raise stage_01.ProtocolError(
            "a packet id of %d is not between 1 and 65535" % (packet_id,))
    return packet_id


def _read_filter(data, pos, what):
    """The two-byte-length string at `pos`; the caller has two bytes for the length."""
    length = (data[pos] << 8) | data[pos + 1]
    start = pos + 2
    if len(data) - start < length:
        raise stage_01.Incomplete(length - (len(data) - start))
    payload = data[start:start + length]
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise stage_01.ProtocolError("a %s filter of %r is not UTF-8"
                                     % (what, payload))
    return text, start + length


def read_subscribe(data, pos=0):
    """The SUBSCRIBE body at `pos`, as `(subscribe, pos_after)`.

    `data` is the body, exactly: the fixed header — its type, its reserved nibble
    and its length — was read once by stage 1 and does not arrive here. The body
    carries a non-zero packet id and one or more filters, each a two-byte-length
    string followed by the QoS the client is asking for, never the one it is
    granted. A requested QoS above `MAX_QOS`, a packet id of 0, no filter at all
    and a trailing byte are all `ProtocolError`s naming what arrived; a field that
    claims more bytes than have arrived is stage 1's `Incomplete`, `.needed` exact.
    """
    data = _check_buffer(data, "the buffer a SUBSCRIBE is read from")
    pos = _check_pos(data, pos)
    if len(data) - pos < 2:
        raise stage_01.Incomplete(2 - (len(data) - pos))
    packet_id = (data[pos] << 8) | data[pos + 1]
    if packet_id == 0:
        raise stage_01.ProtocolError(
            "a SUBSCRIBE's packet id of 0 is not an id (every id is 1..65535)")
    pos += 2
    topics = []
    while pos < len(data):
        if len(data) - pos < 3:
            if not topics:
                raise stage_01.Incomplete(3 - (len(data) - pos))
            raise stage_01.ProtocolError(
                "a trailing byte after the SUBSCRIBE's filters (%d byte(s) left)"
                % (len(data) - pos,))
        text, pos = _read_filter(data, pos, "SUBSCRIBE")
        if pos >= len(data):
            raise stage_01.Incomplete(1)
        qos = data[pos]
        pos += 1
        if qos > MAX_QOS:
            raise stage_01.ProtocolError(
                "a requested QoS of %d is malformed (only 0, 1 and 2 are spoken)"
                % (qos,))
        topics.append((text, qos))
    if not topics:
        raise stage_01.ProtocolError(
            "a SUBSCRIBE with no filters has nothing to answer")
    subscribe = {"packet_id": packet_id, "topics": tuple(topics)}
    return subscribe, pos


def read_unsubscribe(data, pos=0):
    """The UNSUBSCRIBE body at `pos`, as `([packet_id, filters], pos_after)`.

    The same non-zero packet id and the same one-or-more filters as a SUBSCRIBE —
    but each filter is a bare string with **no** QoS byte after it. Reading one
    anyway eats the next filter's length and unsubscribes a client from a filter
    it never asked about.
    """
    data = _check_buffer(data, "the buffer an UNSUBSCRIBE is read from")
    pos = _check_pos(data, pos)
    if len(data) - pos < 2:
        raise stage_01.Incomplete(2 - (len(data) - pos))
    packet_id = (data[pos] << 8) | data[pos + 1]
    if packet_id == 0:
        raise stage_01.ProtocolError(
            "an UNSUBSCRIBE's packet id of 0 is not an id (every id is 1..65535)")
    pos += 2
    filters = []
    while pos < len(data):
        if len(data) - pos < 2:
            if not filters:
                raise stage_01.Incomplete(2 - (len(data) - pos))
            raise stage_01.ProtocolError(
                "a trailing byte after the UNSUBSCRIBE's filters (%d byte(s) left)"
                % (len(data) - pos,))
        text, pos = _read_filter(data, pos, "UNSUBSCRIBE")
        filters.append(text)
    if not filters:
        raise stage_01.ProtocolError(
            "an UNSUBSCRIBE with no filters has nothing to answer")
    return [packet_id, tuple(filters)], pos


def granted_qos(requested, cap=MAX_QOS):
    """What a broker actually grants for a request: `min(requested, cap)`.

    A *different* number from the ask, which is the point: a grant may narrow
    what the client asked for and never widen it. A requested QoS (or a cap) that
    is not 0, 1 or 2 is malformed, and so is anything that is not an int.
    """
    if isinstance(requested, bool) or not isinstance(requested, int):
        raise stage_01.ProtocolError("a requested QoS must be an int, not %s"
                                     % (type(requested).__name__,))
    if not 0 <= requested <= MAX_QOS:
        raise stage_01.ProtocolError(
            "a requested QoS of %d is malformed (only 0, 1 and 2 are spoken)"
            % (requested,))
    if isinstance(cap, bool) or not isinstance(cap, int):
        raise stage_01.ProtocolError("a QoS cap must be an int, not %s"
                                     % (type(cap).__name__,))
    if not 0 <= cap <= MAX_QOS:
        raise stage_01.ProtocolError(
            "a QoS cap of %d is not a QoS (only 0, 1 and 2 are spoken)" % (cap,))
    return min(requested, cap)


def grant_codes(subscribe, cap=MAX_QOS, refused=()):
    """One return code per filter, in the order the filters were asked for.

    A filter already decided against — named in `refused` — is answered with
    `SUBACK_FAILURE`; everything else with the granted QoS under `cap`. It is
    one code per filter and never one code for all of them, because the client
    is told what happened to *each* subscription, not to the packet.
    """
    if not isinstance(subscribe, dict):
        raise stage_01.ProtocolError("a subscription must be a dict, not %s"
                                     % (type(subscribe).__name__,))
    for key in SUBSCRIBE_KEYS:
        if key not in subscribe:
            raise stage_01.ProtocolError("a subscription with no %r in it" % (key,))
    decided = tuple(refused)
    codes = []
    for topic in subscribe["topics"]:
        if not isinstance(topic, (tuple, list)) or len(topic) != 2:
            raise stage_01.ProtocolError(
                "a subscription topic of %r is not a (filter, qos) pair" % (topic,))
        filter_, qos = topic
        if filter_ in decided:
            codes.append(SUBACK_FAILURE)
        else:
            codes.append(granted_qos(qos, cap))
    return tuple(codes)


def write_suback(packet_id, codes):
    """The SUBACK body: the echoed packet id, then one code per filter.

    The id is the client's own, written back unchanged — a fresh id leaves a
    client waiting for an answer to a packet it never sent. Each code is a
    granted QoS or `SUBACK_FAILURE`; anything else cannot be a return code. The
    fixed header that frames this body is stage 1's `write_varint` and stage
    10's job, never a writer's.
    """
    _check_id(packet_id)
    body = bytearray()
    body.append(packet_id >> 8)
    body.append(packet_id & 0xFF)
    for code in codes:
        if isinstance(code, bool) or not isinstance(code, int) or code not in (0, 1, 2, SUBACK_FAILURE):
            raise stage_01.ProtocolError(
                "a SUBACK code of %r is not a granted QoS or a failure" % (code,))
        body.append(code)
    return bytes(body)


def write_unsuback(packet_id):
    """The UNSUBACK body: the echoed packet id and nothing else.

    No codes, no filters: an UNSUBSCRIBE is answered by saying the id was heard.
    The fixed header is not this writer's to write.
    """
    _check_id(packet_id)
    return bytes([packet_id >> 8, packet_id & 0xFF])
