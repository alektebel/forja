"""TCP/IP From Scratch — stage 1: The frame, and the type field that says what is inside.

See `stage_01.py` for the surface and the design decisions; this is the frame.
"""

from hosts import MACS
from wire import BROADCAST_MAC, WireError, mac_text

ETHERNET_HEADER = 14
MIN_FRAME = 60
TYPES = {0x0800: "ipv4", 0x0806: "arp"}

#: The most a payload may be. 1500 is the ethernet MTU; it is *not* the 46 bytes
#: a short frame pads to, and reading `MIN_FRAME - ETHERNET_HEADER` as this
#: number refuses the commonest payload there is.
_MAX_PAYLOAD = 1500


class FrameError(WireError):
    """A frame this stack cannot build or read, named as what is wrong with it.

    It is the link's `WireError` as well, because `wire.mac_text` is the one
    authority on what an address is: a caller that catches the link's refusals
    catches this stage's too, and a bad address names the same offender either
    way.
    """


def _types():
    """The table as a sentence, so a refusal about a type can name the others."""
    return ", ".join("%d %s" % (number, TYPES[number]) for number in sorted(TYPES))


def _peer(mac):
    """The world's name for a MAC, or the MAC's own text form when it has none."""
    for name in sorted(MACS):
        if MACS[name] == mac:
            return name
    return mac


def _address(mac):
    """`mac_text`'s spelling of an address, with its refusal in this family."""
    try:
        return mac_text(mac)
    except WireError as refused:
        raise FrameError(str(refused))


def mac_bytes(mac):
    """The six bytes of an address, from six bytes or from its text form."""
    return bytes(int(part, 16) for part in _address(mac).split(":"))


def build(dst, src, type_, payload, pad=True):
    """The frame: `dst(6) | src(6) | type(2) | payload`, padded to `MIN_FRAME`."""
    if not isinstance(payload, bytes):
        raise FrameError("a payload is bytes, not %r" % (type(payload).__name__,))
    if len(payload) > _MAX_PAYLOAD:
        raise FrameError("a payload is at most %d bytes, not %d"
                         % (_MAX_PAYLOAD, len(payload)))
    number = type_number(type_) if isinstance(type_, str) else type_
    type_name(number)                    # an unknown number is refused, named
    frame = (mac_bytes(dst) + mac_bytes(src) + number.to_bytes(2, "big") + payload)
    if pad and len(frame) < MIN_FRAME:
        frame = frame + b"\x00" * (MIN_FRAME - len(frame))
    return frame


def parse(frame):
    """The frame's four facts: `{"dst", "src", "type", "payload"}`."""
    if not isinstance(frame, bytes):
        raise FrameError("a frame is bytes, not %r" % (type(frame).__name__,))
    if len(frame) < ETHERNET_HEADER:
        raise FrameError("a frame is at least %d bytes, not %d"
                         % (ETHERNET_HEADER, len(frame)))
    number = int.from_bytes(frame[12:14], "big")
    return {"dst": mac_text(frame[:6]), "src": mac_text(frame[6:12]),
            "type": type_name(number), "payload": frame[ETHERNET_HEADER:]}


def type_name(number):
    """The name of a type number, or a refusal naming the number nobody knows."""
    if isinstance(number, bool) or not isinstance(number, int) or number not in TYPES:
        raise FrameError("no type is numbered %r: the types are %s"
                         % (number, _types()))
    return TYPES[number]


def type_number(name):
    """The number of a type name, or a refusal naming the unknown name."""
    if not isinstance(name, str) or not name:
        raise FrameError("a type name is a non-empty string, not %r" % (name,))
    for number in sorted(TYPES):
        if TYPES[number] == name:
            return number
    raise FrameError("no type is called %r: the types are %s" % (name, _types()))


def is_broadcast(mac):
    """Whether an address is `BROADCAST_MAC`, in either form `mac_text` takes."""
    return _address(mac) == BROADCAST_MAC


def describe(frame):
    """The frame as one readable line: `"src -> dst type length bytes"`."""
    envelope = parse(frame)
    return "%s -> %s %s %d bytes" % (_peer(envelope["src"]),
                                     _peer(envelope["dst"]),
                                     envelope["type"],
                                     len(envelope["payload"]))
