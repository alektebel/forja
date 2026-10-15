"""TCP/IP From Scratch — stage 3: IPv4, and the hop that was one too many.

An address is not an identity; it is a *place*, and a place only means something
relative to the table that holds it. So this stage has two halves that only look
separate. The first is the header: twenty bytes that say where a datagram came
from, where it is going, how long it is, what is inside it, and how many more
hops it may take. The second is the router's one decision, and it is the whole
reason the header exists: given a place, which of my links is the one that gets
closer to it, and if I cannot say, what do I say instead.

The hop count is the title's subject. Without it a datagram whose destination is
unreachable — a table with a wrong entry, a link that loops, an address nobody
owns — circulates until something else stops it, and nothing else does. With it,
every router that touches the datagram takes one off the number, and the router
that finds none left does not forward: it refuses, with the word `"ttl_expired"`,
and stage 4 is the stage that turns that word into a message somebody can read.
The number is spent *before* the datagram is sent, not after it arrives, because
the hop the router is about to take is exactly the hop it is counting.

The header's checksum is the header's own, and that is the second decision. A
router may change the TTL and nothing else, so a sum that covered the payload
would have to be recomputed over bytes the router has no business reading — and a
sum that covered the payload would make every router of a large datagram touch
all of it. The checksum here covers the twenty bytes, the field is treated as
zero while it is computed, and the *receiver* is the one who decides: a wrong
checksum is reported, not raised, because the datagram belongs to a peer and a
stack that dies on a hostile packet is a stack that stops forwarding the packets
that were fine.

DESIGN DECISION — why is a wrong checksum *reported* by `unpack_header` and by
`forward`, while a header too short to be a header *raises*?
Because those are two different questions. A header of nineteen bytes is not a
header at all — there is no reading of it, no version to check, no length to
trust — so the caller has made a mistake and a mistake is loud. A header whose
checksum disagrees with its bytes is a complete, well-formed header that was
damaged somewhere between here and there: the router's whole job is to decide
what to do about that, and the decision this course makes is `"bad_checksum"`,
a word the caller can act on. An exception is not a report; a word is.

DESIGN DECISION — why does the TTL refuse at one, and why is it spent before the
route is chosen?
Because the number counts the hops still available to the datagram, and a
datagram that still has one hop may take it: it is forwarded with zero left, and
the *next* router refuses. A datagram that arrives with one hop left is one whose
next hop is its last, and a datagram that arrives with zero is one that has
already spent what it had — the refusal is `ttl_expired`, and it happens before
the table is consulted, because a datagram this router must not forward is not a
datagram whose route anybody needs to know. Refusing after decrementing gives the
same answer as refusing at one and a worse answer at zero.

DESIGN DECISION — why is a route the *longest* prefix that matches rather than
the first one that does?
Because a table is written coarse-to-fine. `0.0.0.0/0` is "everywhere else" and
it is the last thing a router wants to use; `10.0.0.0/24` is the one link that
actually gets there. A table searched in the order it was written answers with
whichever line came first, which makes the meaning of a table depend on the order
somebody happened to write it in — and the fix is one number: the prefix, which
is exactly how specific a line is. The same number decides the match, too: both
the destination and the table's own network are masked, because a table entry may
have host bits in it and `10.0.0.99/24` names the same network as `10.0.0.0/24`.

DESIGN DECISION — why is `total_length` a field the header carries, when the
wire already counted the bytes?
Because the wire's count is the *frame's*, and a frame is padded. A datagram of
twenty-eight bytes inside a short ethernet frame arrives as forty-six bytes of
payload region, and only the layer that owns the header can say where the
datagram ends: `total_length` is where the padding finally stops being anybody's
problem, and `unpack_header` cuts the payload to exactly `total_length` minus the
header. A parser that hands back everything after the header hands back garbage
that the next layer will try to read.

    IPV4_HEADER    the twenty bytes of `version/ihl | tos | length | ident |
                   flags | ttl | protocol | checksum | src | dst`
    IPV4_VERSION   the version this stack reads; the other half of the byte is 5
    DEFAULT_TTL    what a datagram is built with: 64
    MAX_TTL        the most a hop count can be: 255
    IDENT_MAX      the most an identifier can be: 65535
    PROTOCOLS      the two protocols this course speaks: 1 icmp, 6 tcp
    parse_ip       `"10.0.0.2"` -> `(10, 0, 0, 2)`
    ip_text        the four octets -> the dotted quad
    mask_of        `24` -> `0xffffff00`, because a route is a bit test
    network_of     the address with its host bits clear
    checksum       the one's-complement sum of a message, complemented
    checksum_ok    whether a message already carries a valid checksum field
    pack_header    the twenty bytes, checksum over the header alone
    unpack_header  the header's facts, or a refusal naming what is wrong
    build          the header and its payload, with `total_length` counting both
    route          the longest prefix in the table that matches, or no_route
    forward        the router's whole job: check, spend a hop, route, rebuild

`IpError` is the family, and every refusal names the offender: the address with
an octet above 255, the octet written `010`, the wrong number of octets, the
prefix that is not a bit count, the header too short or of another version, the
length that overruns the bytes it was given, the protocol nobody speaks.

TODO: implement `parse_ip`, `ip_text`, `mask_of`, `network_of`, `checksum`,
`checksum_ok`, `pack_header`, `unpack_header`, `build`, `route` and `forward`.
"""

IPV4_HEADER = 20
IPV4_VERSION = 4
DEFAULT_TTL = 64
MAX_TTL = 255
IDENT_MAX = 65535
PROTOCOLS = {1: "icmp", 6: "tcp"}


class IpError(ValueError):
    """A datagram this stack cannot build or read, named as what is wrong.

    It is a `ValueError` like every refusal in this course, and the message names
    the offender: the address, the prefix, the length, the protocol number.
    """


def parse_ip(text):
    """The four octets of `"10.0.0.2"`, or a refusal naming the text it got."""
    raise NotImplementedError("stage 3: implement parse_ip()")


def ip_text(octets):
    """The dotted-quad text of four octets, or a refusal naming what it got."""
    raise NotImplementedError("stage 3: implement ip_text()")


def mask_of(prefix):
    """The network mask of a prefix length, as the int `24 -> 0xffffff00`."""
    raise NotImplementedError("stage 3: implement mask_of()")


def network_of(ip, prefix):
    """The address with its host bits clear, as the int a table compares."""
    raise NotImplementedError("stage 3: implement network_of()")


def checksum(data):
    """The value that goes *into* a checksum field for `data`.

    The sixteen-bit one's-complement sum of the message's words, complemented. An
    odd-length message is padded with one zero byte, which is the standard's own
    rule and not this course's convenience.
    """
    raise NotImplementedError("stage 3: implement checksum()")


def checksum_ok(data):
    """Whether `data` already carries a valid checksum field.

    The receiver's reading: sum the message with the field in place, and the sum
    of a message that is already correct is `0xffff`, so nothing is complemented
    a second time.
    """
    raise NotImplementedError("stage 3: implement checksum_ok()")


def pack_header(src, dst, protocol, payload_length, ttl, ident):
    """The twenty bytes of §2.3, with the checksum over the header alone."""
    raise NotImplementedError("stage 3: implement pack_header()")


def unpack_header(data):
    """The header's facts, with the payload cut to `total_length - 20` bytes.

    `{"src", "dst", "protocol", "payload_length", "ttl", "ident",
    "checksum_ok", "payload"}`. A data too short, of another version, with an IHL
    that is not 5, a `total_length` shorter than the header or longer than the
    bytes it was given raises, naming the offender. A checksum that does not
    check out comes back as `"checksum_ok": False`.
    """
    raise NotImplementedError("stage 3: implement unpack_header()")


def build(src, dst, protocol, payload, ttl=DEFAULT_TTL, ident=0):
    """The header and its payload, with `total_length` counting both."""
    raise NotImplementedError("stage 3: implement build()")


def route(table, dst):
    """The longest prefix in the table that matches `dst`, or `no_route`.

    A table is a sequence of `(network, prefix, port, next_hop)`; the answer is
    `{"port", "next_hop", "prefix"}` when something matches and
    `{"refused": "no_route"}` when nothing does.
    """
    raise NotImplementedError("stage 3: implement route()")


def forward(table, datagram):
    """The router's whole job: check, spend a hop, route, rebuild, hand back.

    `{"sent", "ttl", "port", "next_hop", "ident"}` when the datagram is
    forwarded, and `{"refused": word}` — `"bad_checksum"`, `"ttl_expired"` or
    `"no_route"` — when it is not.
    """
    raise NotImplementedError("stage 3: implement forward()")
