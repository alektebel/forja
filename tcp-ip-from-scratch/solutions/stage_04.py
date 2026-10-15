"""TCP/IP From Scratch — stage 4: ICMP, and the checksum over the whole message.

See `stage_04.py` for the surface and the design decisions; this is the message,
the checksum that covers all of it, and the peer that answers.
"""

import stage_01
import stage_03

ICMP_HEADER = 8
ERROR_QUOTE = 28
ICMP_ECHO_REPLY, ICMP_UNREACHABLE, ICMP_ECHO_REQUEST, ICMP_TIME_EXCEEDED = 0, 3, 8, 11
ICMP_TYPES = {0: "echo_reply", 3: "unreachable", 8: "echo_request", 11: "time_exceeded"}

#: The words stage 3 refuses with, and the type each one turns into. A refusal
#: this stack cannot name is not a message it can build.
_ERRORS = {"ttl_expired": ICMP_TIME_EXCEEDED, "no_route": ICMP_UNREACHABLE}

#: The two types whose `rest` is four zero bytes and whose payload is the
#: datagram that caused the error.
_QUOTING = (ICMP_UNREACHABLE, ICMP_TIME_EXCEEDED)


class IcmpError(ValueError):
    """An ICMP message this stack cannot build or read, named as it is wrong."""


def _types():
    """The table as a sentence, so a refusal about a type can name the rest."""
    return ", ".join("%d %s" % (number, ICMP_TYPES[number])
                     for number in sorted(ICMP_TYPES))


def _type_number(type_):
    """The type number, or a refusal naming the type nobody knows."""
    if isinstance(type_, bool) or not isinstance(type_, int) or type_ not in ICMP_TYPES:
        raise IcmpError("no icmp type is numbered %r: the types are %s"
                        % (type_, _types()))
    return type_


def _short(value, what):
    """A sixteen-bit field, or a refusal naming what was given."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 65535:
        raise IcmpError("%s is 0..65535, not %r" % (what, value))
    return value


def _count(value, what):
    """A tick count that cannot run backwards, or a refusal naming it."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IcmpError("%s is a tick count, not %r" % (what, value))
    return value


def build(type_, ident=0, seq=0, payload=b""):
    """The eight bytes of §2.3 and the payload, in one message."""
    number = _type_number(type_)
    if not isinstance(payload, bytes):
        raise IcmpError("a payload is bytes, not %r" % (type(payload).__name__,))
    tag = _short(ident, "an identifier")
    order = _short(seq, "a sequence number")
    body = (bytes((number, 0)) + b"\x00\x00" + tag.to_bytes(2, "big")
            + order.to_bytes(2, "big") + payload)
    field = stage_03.checksum(body)
    return body[:2] + field.to_bytes(2, "big") + body[4:]


def parse(message):
    """The message's facts, its checksum's verdict and the bytes it quotes."""
    if not isinstance(message, bytes):
        raise IcmpError("an icmp message is bytes, not %r"
                        % (type(message).__name__,))
    if len(message) < ICMP_HEADER:
        raise IcmpError("an icmp message is at least %d bytes, not %d"
                        % (ICMP_HEADER, len(message)))
    number = message[0]
    if number not in ICMP_TYPES:
        raise IcmpError("icmp type %d is not one this stack speaks: %s"
                        % (number, _types()))
    body = message[ICMP_HEADER:]
    return {"type": number, "name": ICMP_TYPES[number], "code": message[1],
            "ident": int.from_bytes(message[4:6], "big"),
            "seq": int.from_bytes(message[6:8], "big"),
            "payload": body, "checksum_ok": stage_03.checksum_ok(message),
            "quote": body if number in _QUOTING else None}


def echo_reply(request):
    """The reply to an echo request: type 0, the request's ident, seq and payload."""
    message = parse(request)
    if message["type"] != ICMP_ECHO_REQUEST:
        raise IcmpError("type %d is not an echo request: only a request is answered"
                        % (message["type"],))
    return build(ICMP_ECHO_REPLY, message["ident"], message["seq"],
                 message["payload"])


def error_message(datagram, reason):
    """The message a refused datagram earns, quoting `ERROR_QUOTE` bytes of it."""
    if not isinstance(datagram, bytes):
        raise IcmpError("a quoted datagram is bytes, not %r"
                        % (type(datagram).__name__,))
    if len(datagram) < stage_03.IPV4_HEADER:
        raise IcmpError("a quoted datagram is at least %d bytes, not %d"
                        % (stage_03.IPV4_HEADER, len(datagram)))
    if reason not in _ERRORS:
        raise IcmpError("no icmp error is called %r: a refusal is one of %s"
                        % (reason, ", ".join(sorted(_ERRORS))))
    return build(_ERRORS[reason], payload=datagram[:ERROR_QUOTE])


def answer(host, datagram, reason=None):
    """The peer's whole behaviour: answer a request, or quote a refusal."""
    envelope = stage_03.unpack_header(datagram)
    if not envelope["checksum_ok"]:
        return None
    if reason is not None:
        if reason in _ERRORS:
            return error_message(datagram, reason)
        return None
    if envelope["protocol"] != "icmp":
        return None
    if envelope["dst"] != host.ip:
        return None
    try:
        message = parse(envelope["payload"])
    except IcmpError:
        return None
    if not message["checksum_ok"]:
        return None
    if message["type"] != ICMP_ECHO_REQUEST:
        return None
    return echo_reply(envelope["payload"])


def _reply_in(host, source, ident, seq):
    """The first echo reply in this host's box that answers this echo, or `None`.

    The box belongs to the link: anybody on it may put anything in there, so a
    frame that is not a frame, a frame that is not ipv4, a datagram that is not a
    datagram, one from another address, one whose checksum disagrees, a message
    that is not a reply and one for another echo are all *not* this exchange's
    answer.
    """
    for frame in host.recv():
        try:
            envelope = stage_01.parse(frame)
            if envelope["type"] != "ipv4":
                continue
            datagram = stage_03.unpack_header(envelope["payload"])
            if datagram["protocol"] != "icmp" or datagram["src"] != source:
                continue
            if datagram["dst"] != host.ip or not datagram["checksum_ok"]:
                continue
            message = parse(datagram["payload"])
        except (stage_01.FrameError, stage_03.IpError, IcmpError):
            continue
        if not message["checksum_ok"] or message["type"] != ICMP_ECHO_REPLY:
            continue
        if message["ident"] != ident or message["seq"] != seq:
            continue
        return datagram["payload"]
    return None


def ping(wire, host, dst_mac, dst_ip, ident=0, seq=1, payload=b"", ticks=2):
    """The whole exchange: an echo request put on the link, and what came back."""
    wait = _count(ticks, "ticks")
    request = build(ICMP_ECHO_REQUEST, ident, seq, payload)
    datagram = stage_03.build(host.ip, dst_ip, "icmp", request)
    frame = stage_01.build(dst_mac, host.mac, "ipv4", datagram)
    ordinal = host.send(dst_mac, frame)
    entered = wire.tick()
    wire.advance(wait)
    reply = _reply_in(host, dst_ip, ident, seq)
    return {"sent": ordinal, "request": request, "reply": reply,
            "ticks": wire.tick() - entered}
