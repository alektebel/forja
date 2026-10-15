"""TCP/IP From Scratch — stage 2: ARP, and the address that ages out.

See `stage_02.py` for the surface and the design decisions; this is the protocol
and the table it fills.
"""

import stage_01
from wire import BROADCAST_MAC, WireError, mac_text

ARP_LENGTH = 28
ARP_REQUEST, ARP_REPLY = 1, 2
CACHE_TICKS = 8

#: The one hardware type and the one protocol this stack honours, and the widths
#: they imply: six bytes of hardware address, four of protocol address.
_HTYPE = 1
_PTYPE = 0x0800
_HLEN = 6
_PLEN = 4


class ArpError(WireError):
    """An ARP message this stack cannot build or read, named as what is wrong.

    It is the link's `WireError` as well: `wire.mac_text` is the one authority on
    what an address is, and a caller that catches the link's refusals catches
    this stage's too.
    """


# ---- the small conversions every entry point shares -----------------------

def _count(value, what, low=0):
    """A tick that cannot run backwards, or a refusal naming what was given."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArpError("%s is a tick count, not %r" % (what, value))
    if value < low:
        raise ArpError("%s is %d, and the least it can be is %d"
                       % (what, value, low))
    return value


def _octets(ip, what):
    """An address as four ints, from dotted-quad text or from four octets."""
    if isinstance(ip, bytes):
        if len(ip) != 4:
            raise ArpError("%s is four octets, not %d bytes" % (what, len(ip)))
        return tuple(ip)
    if not isinstance(ip, str):
        raise ArpError("%s is dotted-quad text or four bytes, not %r"
                       % (what, ip))
    parts = ip.split(".")
    if len(parts) != 4:
        raise ArpError("%s has four octets, not %d: %r" % (what, len(parts), ip))
    out = []
    for part in parts:
        if not part.isdigit() or (len(part) > 1 and part[0] == "0") or int(part) > 255:
            raise ArpError("%s has four octets in plain digits, each 0..255: %r"
                           % (what, ip))
        out.append(int(part))
    return tuple(out)


def _ip_text(ip, what):
    """An address in its text form, whatever form it arrived in."""
    return ".".join(str(part) for part in _octets(ip, what))


def _ip_bytes(ip, what):
    """An address as the four octets the message carries."""
    return bytes(_octets(ip, what))


def _mac_text(mac, what):
    """An address in the wire's text form, or a refusal naming the offender."""
    try:
        return mac_text(mac)
    except WireError as refused:
        raise ArpError("%s is not an address: %s" % (what, refused))


def _op(op):
    """The operation number, or a refusal naming the number nobody knows."""
    if isinstance(op, bool) or not isinstance(op, int) or op not in (ARP_REQUEST,
                                                                    ARP_REPLY):
        raise ArpError("no arp operation is numbered %r: %d is a request and %d "
                       "is a reply" % (op, ARP_REQUEST, ARP_REPLY))
    return op


# ---- the message ----------------------------------------------------------

def build_message(op, sender, sender_ip, target_mac, target_ip):
    """The 28 bytes: `htype | ptype | hlen | plen | op | sha | spa | tha | tpa`."""
    sender = _mac_text(sender, "the sender's address")
    target_mac = _mac_text(target_mac, "the target's address")
    return (int.to_bytes(_HTYPE, 2, "big") + int.to_bytes(_PTYPE, 2, "big")
            + bytes((_HLEN, _PLEN)) + int.to_bytes(_op(op), 2, "big")
            + stage_01.mac_bytes(sender) + _ip_bytes(sender_ip, "the sender's ip")
            + stage_01.mac_bytes(target_mac) + _ip_bytes(target_ip, "the target's ip"))


def parse_message(message):
    """The message's five facts: `{"op", "sender", "sender_ip", "target",
    "target_ip"}`."""
    if not isinstance(message, bytes):
        raise ArpError("an arp message is bytes, not %r"
                       % (type(message).__name__,))
    if len(message) != ARP_LENGTH:
        raise ArpError("an arp message is %d bytes, not %d"
                       % (ARP_LENGTH, len(message)))
    htype = int.from_bytes(message[0:2], "big")
    if htype != _HTYPE:
        raise ArpError("hardware type %d is not the one this stack speaks: %d"
                       % (htype, _HTYPE))
    ptype = int.from_bytes(message[2:4], "big")
    if ptype != _PTYPE:
        raise ArpError("protocol type %d is not the one this stack speaks: %d"
                       % (ptype, _PTYPE))
    if message[4] != _HLEN:
        raise ArpError("hardware address length %d is not %d bytes"
                       % (message[4], _HLEN))
    if message[5] != _PLEN:
        raise ArpError("protocol address length %d is not %d octets"
                       % (message[5], _PLEN))
    return {"op": _op(int.from_bytes(message[6:8], "big")),
            "sender": mac_text(message[8:14]),
            "sender_ip": _ip_text(message[14:18], "the sender's ip"),
            "target": mac_text(message[18:24]),
            "target_ip": _ip_text(message[24:28], "the target's ip")}


# ---- the exchange ---------------------------------------------------------

def _answer_for(host, ip):
    """The first reply in this host's box that is about `ip`, or `None`.

    The frame's padding is cut off by the only layer that knows how long an ARP
    message is: `ARP_LENGTH` is the length field this message does not carry.

    A frame that is not a frame, a message that is not this message, a frame
    that is not ARP, a reply about a different address and a reply addressed to
    somebody else are all *not* this exchange's answer — the box belongs to the
    link, and anybody on it may put anything in there.
    """
    for frame in host.recv():
        try:
            envelope = stage_01.parse(frame)
            if envelope["type"] != "arp":
                continue
            message = parse_message(envelope["payload"][:ARP_LENGTH])
        except (stage_01.FrameError, ArpError):
            continue
        if message["op"] != ARP_REPLY:
            continue
        if message["sender_ip"] != ip:
            continue
        if message["target"] != host.mac or message["target_ip"] != host.ip:
            continue
        return message
    return None


def request(wire, host, ip, now=None):
    """The whole exchange: `{"ip", "mac", "sent", "received", "ticks"}`."""
    wanted = _ip_text(ip, "the address being resolved")
    start = wire.tick() if now is None else _count(now, "now")
    message = build_message(ARP_REQUEST, host.mac, host.ip, BROADCAST_MAC, wanted)
    frame = stage_01.build(BROADCAST_MAC, host.mac, "arp", message)
    ordinal = host.send(BROADCAST_MAC, frame)
    entered = wire.tick()
    wait = start + CACHE_TICKS - entered
    wire.advance(wait if wait > 0 else 0)
    answer = _answer_for(host, wanted)
    return {"ip": wanted, "mac": None if answer is None else answer["sender"],
            "sent": ordinal, "received": answer is not None,
            "ticks": wire.tick() - entered}


def reply_to(message, my_mac, my_ip):
    """The reply to a request aimed at this pair, as a 28-byte message."""
    mine = _mac_text(my_mac, "my address")
    my_address = _ip_text(my_ip, "my address")
    ask = parse_message(message)
    if ask["op"] != ARP_REQUEST:
        raise ArpError("op %d is not a request: only a request is answered"
                       % (ask["op"],))
    if ask["target_ip"] != my_address:
        raise ArpError("this request asks about %s, and my address is %s"
                       % (ask["target_ip"], my_address))
    if ask["target"] != mine and ask["target"] != BROADCAST_MAC:
        raise ArpError("this request is addressed to %s, and my address is %s"
                       % (ask["target"], mine))
    return build_message(ARP_REPLY, mine, my_address, ask["sender"],
                         ask["sender_ip"])


# ---- the table ------------------------------------------------------------

def _order_key(ip):
    """The order addresses sort in: four octets, not the text they are written as."""
    return tuple(int(part) for part in ip.split("."))


class Cache:
    """Learned addresses, each with the tick it was learned and the one it dies."""

    def __init__(self, ticks=CACHE_TICKS):
        """A cache whose entries live `ticks` ticks, and an empty log."""
        self._ticks = _count(ticks, "an entry's lifetime", 1)
        self._table = {}
        self._learned = []
        self._events = []

    def _record(self, now, event, ip, mac, expires):
        """One decision, as it happened, in the order it happened."""
        self._events.append({"now": now, "event": event, "ip": ip, "mac": mac,
                             "expires": expires})
        return None

    def _forget(self, ip, now):
        """Take an entry out of the table and say so."""
        gone = self._table.pop(ip)
        self._learned.remove(ip)
        self._record(now, "expired", ip, gone["mac"], gone["expires"])
        return gone

    def learn(self, ip, mac, now):
        """Believe `mac` for `ip` from `now`: `{"ip", "mac", "fresh",
        "expires"}`."""
        address = _ip_text(ip, "the address being learned")
        hardware = _mac_text(mac, "the address being learned")
        when = _count(now, "now")
        known = address in self._table
        replaced = known and self._table[address]["mac"] != hardware
        expires = when + self._ticks
        if not known:
            self._learned.append(address)
        self._table[address] = {"mac": hardware, "expires": expires}
        self._record(when, "replace" if replaced else
                     ("refresh" if known else "learn"), address, hardware, expires)
        return {"ip": address, "mac": hardware, "fresh": known,
                "expires": expires}

    def lookup(self, ip, now):
        """The MAC believed for `ip`, or `None` — an expired entry is gone."""
        address = _ip_text(ip, "the address being looked up")
        when = _count(now, "now")
        entry = self._table.get(address)
        if entry is None:
            return None
        if entry["expires"] <= when:
            self._forget(address, when)
            return None
        return entry["mac"]

    def expire(self, now):
        """The entries that ran out, in the order they were learned."""
        when = _count(now, "now")
        gone = []
        for address in list(self._learned):
            entry = self._table[address]
            if entry["expires"] <= when:
                gone.append((address, entry["mac"], entry["expires"]))
                self._forget(address, when)
        return tuple(gone)

    def entries(self, now):
        """The live entries, as `(ip, mac, expires)`, sorted by address."""
        when = _count(now, "now")
        live = [(address, self._table[address]["mac"],
                 self._table[address]["expires"])
                for address in self._table
                if self._table[address]["expires"] > when]
        return tuple(sorted(live, key=lambda row: _order_key(row[0])))

    def log(self):
        """Every decision this cache made, in order, as dicts."""
        return tuple(self._events)
