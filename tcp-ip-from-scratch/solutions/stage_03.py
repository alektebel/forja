"""TCP/IP From Scratch — stage 3: IPv4, and the hop that was one too many.

See `stage_03.py` for the surface and the design decisions; this is the header,
the checksum over it, and the router's one decision.
"""

IPV4_HEADER = 20
IPV4_VERSION = 4
DEFAULT_TTL = 64
MAX_TTL = 255
IDENT_MAX = 65535
PROTOCOLS = {1: "icmp", 6: "tcp"}

#: The two fields of §2.3 this course never varies: the type of service a
#: datagram asks for, and the flag/fragment pair of one that is never fragmented.
_TOS = 0
_FLAGS_FRAGMENT = 0

#: The most `total_length` can say: a sixteen-bit field is the whole limit there
#: is, and it is why a datagram's length is a *field* and not a wire's count.
_MAX_LENGTH = 65535


class IpError(ValueError):
    """A datagram this stack cannot build or read, named as what is wrong."""


def _protocols():
    """The table as a sentence, so a refusal about a protocol can name the rest."""
    return ", ".join("%d %s" % (number, PROTOCOLS[number])
                     for number in sorted(PROTOCOLS))


def _four(octets, what):
    """Four octets 0..255, from four bytes or from a sequence of four ints."""
    if isinstance(octets, bytes):
        if len(octets) != 4:
            raise IpError("%s is four octets, not %d bytes" % (what, len(octets)))
        return tuple(octets)
    if isinstance(octets, str):
        raise IpError("%s is four octets, not the text %r" % (what, octets))
    try:
        parts = tuple(octets)
    except TypeError:
        raise IpError("%s is four octets, not %r" % (what, octets))
    if len(parts) != 4:
        raise IpError("%s is four octets, not %d" % (what, len(parts)))
    for part in parts:
        if isinstance(part, bool) or not isinstance(part, int) or not 0 <= part <= 255:
            raise IpError("%s has four octets 0..255, not %r" % (what, part))
    return parts


def _octets(address, what):
    """An address as four octets, from its text form or from four ints."""
    if isinstance(address, str):
        return parse_ip(address)
    return _four(address, what)


def _number(address, what):
    """An address as the thirty-two-bit int the routing table compares."""
    return int.from_bytes(bytes(_octets(address, what)), "big")


def parse_ip(text):
    """The four octets of `"10.0.0.2"`, or a refusal naming the text it got."""
    if not isinstance(text, str):
        raise IpError("an address is dotted-quad text, not %r" % (text,))
    parts = text.split(".")
    if len(parts) != 4:
        raise IpError("an address has four octets, not %d: %r"
                      % (len(parts), text))
    out = []
    for part in parts:
        if not part.isdigit() or (len(part) > 1 and part[0] == "0") or int(part) > 255:
            raise IpError("an address has four octets in plain digits, each "
                          "0..255: %r" % (text,))
        out.append(int(part))
    return tuple(out)


def ip_text(octets):
    """The dotted-quad text of four octets, or a refusal naming what it got."""
    return ".".join(str(part) for part in _four(octets, "an address"))


def mask_of(prefix):
    """The network mask of a prefix length, as the int `24 -> 0xffffff00`."""
    if isinstance(prefix, bool) or not isinstance(prefix, int) or not 0 <= prefix <= 32:
        raise IpError("a prefix is a bit count 0..32, not %r" % (prefix,))
    return (0xffffffff << (32 - prefix)) & 0xffffffff


def network_of(ip, prefix):
    """The address with its host bits clear, as the int a table compares."""
    return _number(ip, "the address") & mask_of(prefix)


def _words(data):
    """`data` as sixteen-bit words, an odd last byte padded with a zero byte."""
    if not isinstance(data, bytes):
        raise IpError("the checksum covers bytes, not %r" % (type(data).__name__,))
    if len(data) % 2:
        data = data + b"\x00"
    return [int.from_bytes(data[at:at + 2], "big")
            for at in range(0, len(data), 2)]


def _sum16(data):
    """The one's-complement sum of the words, carries folded back in as they come."""
    total = 0
    for word in _words(data):
        total += word
        total = (total & 0xffff) + (total >> 16)
    return total


def checksum(data):
    """The value that goes *into* a checksum field for `data`."""
    return (~_sum16(data)) & 0xffff


def checksum_ok(data):
    """Whether `data` already carries a valid checksum field."""
    return _sum16(data) == 0xffff


def _protocol(protocol):
    """The protocol number, from its name or its number, or a refusal naming it."""
    if isinstance(protocol, str):
        for number in sorted(PROTOCOLS):
            if PROTOCOLS[number] == protocol:
                return number
        raise IpError("no protocol is called %r: the protocols are %s"
                      % (protocol, _protocols()))
    if isinstance(protocol, bool) or not isinstance(protocol, int) or protocol not in PROTOCOLS:
        raise IpError("no protocol is numbered %r: the protocols are %s"
                      % (protocol, _protocols()))
    return protocol


def _short(value, what, low, high):
    """An int field of `low..high`, or a refusal naming what was given."""
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise IpError("%s is %d..%d, not %r" % (what, low, high, value))
    return value


def pack_header(src, dst, protocol, payload_length, ttl, ident):
    """The twenty bytes of §2.3, with the checksum over the header alone."""
    source = _number(src, "the source address")
    destination = _number(dst, "the destination address")
    number = _protocol(protocol)
    length = _short(payload_length, "a payload's length", 0,
                    _MAX_LENGTH - IPV4_HEADER)
    hop = _short(ttl, "a ttl", 1, MAX_TTL)
    tag = _short(ident, "an identifier", 0, IDENT_MAX)
    total = IPV4_HEADER + length
    bare = (bytes((IPV4_VERSION << 4 | 5, _TOS))
            + total.to_bytes(2, "big")
            + tag.to_bytes(2, "big")
            + _FLAGS_FRAGMENT.to_bytes(2, "big")
            + bytes((hop, number))
            + b"\x00\x00"
            + source.to_bytes(4, "big")
            + destination.to_bytes(4, "big"))
    return bare[:10] + checksum(bare).to_bytes(2, "big") + bare[12:]


def unpack_header(data):
    """The header's facts, with the payload cut to `total_length - 20` bytes."""
    if not isinstance(data, bytes):
        raise IpError("a datagram is bytes, not %r" % (type(data).__name__,))
    if len(data) < IPV4_HEADER:
        raise IpError("a datagram is at least %d bytes, not %d"
                      % (IPV4_HEADER, len(data)))
    if data[0] >> 4 != IPV4_VERSION:
        raise IpError("version %d is not the version this stack reads: %d"
                      % (data[0] >> 4, IPV4_VERSION))
    if data[0] & 0x0f != 5:
        raise IpError("an IHL of %d is not the %d of no options"
                      % (data[0] & 0x0f, 5))
    total = int.from_bytes(data[2:4], "big")
    if total < IPV4_HEADER:
        raise IpError("total length %d is shorter than the %d-byte header"
                      % (total, IPV4_HEADER))
    if total > len(data):
        raise IpError("total length %d is longer than the %d bytes it was given"
                      % (total, len(data)))
    number = data[9]
    if number not in PROTOCOLS:
        raise IpError("protocol %d is not one this stack speaks: %s"
                      % (number, _protocols()))
    header = data[:IPV4_HEADER]
    return {"src": ip_text(header[12:16]), "dst": ip_text(header[16:20]),
            "protocol": PROTOCOLS[number], "payload_length": total - IPV4_HEADER,
            "ttl": data[8], "ident": int.from_bytes(data[4:6], "big"),
            "checksum_ok": checksum_ok(header),
            "payload": data[IPV4_HEADER:total]}


def build(src, dst, protocol, payload, ttl=DEFAULT_TTL, ident=0):
    """The header and its payload, with `total_length` counting both."""
    if not isinstance(payload, bytes):
        raise IpError("a payload is bytes, not %r" % (type(payload).__name__,))
    return (pack_header(src, dst, protocol, len(payload), ttl, ident) + payload)


def route(table, dst):
    """The longest prefix in the table that matches `dst`, or `no_route`."""
    address = _number(dst, "the destination address")
    best = None
    for entry in table:
        if not isinstance(entry, (tuple, list)) or len(entry) != 4:
            raise IpError("a route is (network, prefix, port, next_hop), not %r"
                          % (entry,))
        network, prefix, port, next_hop = entry
        mask = mask_of(prefix)
        if (address & mask) == (_number(network, "a route's network") & mask):
            if best is None or prefix > best["prefix"]:
                best = {"port": port, "next_hop": next_hop, "prefix": prefix}
    if best is None:
        return {"refused": "no_route"}
    return best


def forward(table, datagram):
    """The router's whole job: check, spend a hop, route, rebuild, hand back."""
    envelope = unpack_header(datagram)
    if not envelope["checksum_ok"]:
        return {"refused": "bad_checksum"}
    ttl = envelope["ttl"]
    if ttl <= 1:
        return {"refused": "ttl_expired"}
    decision = route(table, envelope["dst"])
    if "refused" in decision:
        return {"refused": "no_route"}
    ttl = ttl - 1
    sent = build(envelope["src"], envelope["dst"], envelope["protocol"],
                 envelope["payload"], ttl, envelope["ident"])
    return {"sent": sent, "ttl": ttl, "port": decision["port"],
            "next_hop": decision["next_hop"], "ident": envelope["ident"]}
