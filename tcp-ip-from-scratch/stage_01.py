"""TCP/IP From Scratch — stage 1: The frame, and the type field that says what is inside.

A frame here is fourteen bytes of header and then the payload, exactly as the
layer above handed it over: `dst(6) | src(6) | type(2) | payload`. Nothing else
is in it, and the type field is the *only* thing it says about what it carries.
It is not a length, it is not a checksum, it is not a hint: it is a name for a
conversation, and a frame that announces a name this stack does not know is a
frame this stack cannot read at all. That is why `TYPES` has exactly two entries
in this course — `ipv4` and `arp` — and why `parse` refuses an unknown number
rather than handing the bytes up to something that will guess.

The second half of the stage is the padding, and it is the course's first real
decision. A real NIC pads a short frame out to `MIN_FRAME` because the wire used
to need the bytes; a real receiver cannot strip that padding, because a payload
of 46 bytes and a payload of 28 bytes followed by 18 zero bytes are the same
bytes on the wire. So `build` pads (unless it is told not to) and `parse` hands
the payload back *with the padding still on it*. Whose problem is the padding,
then? The next layer's — and every next layer in this course has a length field,
which is exactly what makes the number the frame reports and the number the
message reports two different numbers.

DESIGN DECISION — why does `parse` report the type as a name and not as the
number the wire carries?
Because the number is a wire fact and the name is what the stack talks about. A
check that reads `{"type": 2054}` has to know the table to say what arrived; a
check that reads `{"type": "arp"}` can be read by somebody who does not. The
number is not lost — `type_number` is the way back, and it is one call — and the
round trip is asserted in both directions, so nothing depends on which spelling
is stored where.

DESIGN DECISION — why does `build` pad, and why does `parse` not unpick the
padding it knows was added?
Because a receiver may not assume it knows where a payload ends: trailing zero
bytes are payload as often as they are padding, and a parser that strips them
silently shortens a legitimate message. `build` pads because the frame it emits
should look like a frame; `parse` returns what is there because a parser that
guesses is a parser that lies. The length that matters lives one layer up.

DESIGN DECISION — why is a payload limit 1500 rather than `MIN_FRAME -
ETHERNET_HEADER`?
Because those are two unrelated numbers that happen to be written near each
other: 60 is the *least* a frame may be on the wire, 1500 is the *most* a payload
may be inside one, and 46 is what a short frame happens to pad to. A stage that
reads the second as the first refuses a payload of exactly 46 bytes — a payload
that is not merely legal but is the commonest one on a link that pads.

DESIGN DECISION — why does `describe` print a peer's name where the world has
one?
Because `describe` exists to be read in a failing assertion, and `web ->
ff:ff:ff:ff:ff:ff arp 28 bytes` says which frame failed in a way that two MAC
addresses do not. The name is decoration and never an answer: `describe` still
takes the addresses out of the frame, and a MAC the world does not know is
printed in its own text form rather than refused.

    ETHERNET_HEADER  the fourteen bytes of `dst | src | type`
    MIN_FRAME        the least a frame may be on the wire; `build` pads to it
    TYPES            the two types this course speaks: 0x0800 ipv4, 0x0806 arp
    mac_bytes        six bytes from six-byte bytes or from `mac_text`'s spelling
    build            the frame, padded unless told otherwise
    parse            the frame's four facts, with the payload as it arrived
    type_name        the name of a type number
    type_number      the number of a type name
    is_broadcast     whether an address is the one everybody answers
    describe         `"src -> dst type length bytes"`, for people

`FrameError` is the family, and every refusal names the offender: the payload
that is too long, the type nobody knows, the frame too short to be a frame, the
address the wire's own parser would not take, the payload that is not bytes.

TODO: implement `mac_bytes`, `build`, `parse`, `type_name`, `type_number`,
`is_broadcast` and `describe`.
"""

from hosts import MACS
from wire import BROADCAST_MAC, WireError, mac_text

ETHERNET_HEADER = 14
MIN_FRAME = 60
TYPES = {0x0800: "ipv4", 0x0806: "arp"}


class FrameError(WireError):
    """A frame this stack cannot build or read, named as what is wrong with it.

    It is the link's `WireError` as well, because `wire.mac_text` is the one
    authority on what an address is: a caller that catches the link's refusals
    catches this stage's too, and a bad address names the same offender either
    way. `WireError` is a `ValueError`, so the family stays what the contract
    says it is.
    """


def mac_bytes(mac):
    """The six bytes of an address, from six bytes or from its text form.

    `wire.mac_text` is the one address parser in this course, so this function
    is a conversion and never a second spelling: an upper-case group, a dash for
    a colon, the wrong number of bytes and an int are all refused, naming what
    was given, before a byte is built.
    """
    raise NotImplementedError("stage 1: implement mac_bytes()")


def build(dst, src, type_, payload, pad=True):
    """The frame: `dst(6) | src(6) | type(2) | payload`, padded to `MIN_FRAME`.

    `dst` and `src` are addresses in either of the two forms `mac_bytes` takes,
    `type_` is a number or a name, and `payload` is `bytes` of at most 1500.
    `pad` is the padding decision and it is the caller's: a frame that is
    already `MIN_FRAME` long is never padded again, and `pad=False` is a frame
    that stays short because the layer above knows it needs no help.
    """
    raise NotImplementedError("stage 1: implement build()")


def parse(frame):
    """The frame's four facts: `{"dst", "src", "type", "payload"}`.

    `dst` and `src` come back in the wire's text form and `type` as the *name*
    of the type number the frame carries. The payload is what is after the
    fourteenth byte, exactly as it arrived — padding included, because only the
    layer above knows how long its own message is.
    """
    raise NotImplementedError("stage 1: implement parse()")


def type_name(number):
    """The name of a type number, or a refusal naming the number nobody knows."""
    raise NotImplementedError("stage 1: implement type_name()")


def type_number(name):
    """The number of a type name, or a refusal naming the unknown name."""
    raise NotImplementedError("stage 1: implement type_number()")


def is_broadcast(mac):
    """Whether an address is `BROADCAST_MAC`, in either form `mac_text` takes."""
    raise NotImplementedError("stage 1: implement is_broadcast()")


def describe(frame):
    """The frame as one readable line: `"src -> dst type length bytes"`.

    The addresses are printed as the world's name for them when the world has
    one and as text otherwise, the type is its name, and the length is the
    payload's — never the frame's.
    """
    raise NotImplementedError("stage 1: implement describe()")
