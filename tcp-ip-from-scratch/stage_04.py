"""TCP/IP From Scratch — stage 4: ICMP, and the checksum over the whole message.

A datagram that arrives has a sender, and the sender is the one peer who has to
be told when the datagram does not arrive. That is the whole of this stage: a
message small enough to fit in anything, whose only job is to say something back.
An echo request says *are you there*; an echo reply says *yes*; a time-exceeded
says *your hop count ran out at me*; an unreachable says *I have no route to what
you named*. Stage 3 refused with a word — `"ttl_expired"`, `"no_route"` — and
this stage is what turns the word into a message somebody can read.

The checksum is the title's subject, and it is deliberately *not* the one stage 3
wrote. Stage 3's sum covers the twenty bytes of a header a router rewrites and
nothing else; this message's sum covers the whole message, because an ICMP
message is never rewritten in flight and because the bytes that matter are
exactly the ones the sender composed. Both are the same function — the
one's-complement sum, complemented — and both are the same reading at the
receiver's end: sum the whole thing with the field in place, and a valid message
sums to `0xffff`. Reusing stage 3's `checksum` rather than writing a second one
is the point: a format decided twice is a format that disagrees once.

The other half of the stage is the error message, and it exists to answer one
question: *which of my datagrams was refused?* A sender with five datagrams in
flight cannot act on "somewhere, something expired". So an error message carries
the offending datagram's own header — which names the source, the destination and
the identifier — and the first eight bytes of its payload, which is where a
transport header begins. Twenty-eight bytes, `ERROR_QUOTE`, and not more: real
ICMP quotes as much as fits, and this course quotes exactly what a sender needs
to recognise its own datagram.

DESIGN DECISION — why does this checksum cover the whole message while the
datagram's covers only its header?
Because the two messages are rewritten by different parties. A router changes the
TTL of every datagram it forwards, so a sum over the payload would force every
router to read bytes it has no business reading and to recompute a sum over
everything it carries. An ICMP message is written once by the peer that sends it
and read once by the peer it arrives at, so its sum can cover all of it — and
covering all of it is what makes a truncated or padded message detectable, which
a header-only sum of an eight-byte header cannot do. The rule is not "one
protocol checksums more"; it is "a checksum covers what may change".

DESIGN DECISION — why does `parse` report a bad checksum, while a message that is
not eight bytes long raises?
Because eight bytes that are not a message are not a message: there is no type to
report, no identifier to match a reply against, and a caller that reads them as
one is the one that is wrong. A message of the right shape whose sum disagrees is
a real message from a real peer that was damaged in the crossing — the receiving
peer's whole job is to decide what to do about that, and the decision this course
makes is to report it and stay silent. That is the same boundary stage 3 draws for
`unpack_header`, and it is the boundary every stage in this course draws: shape
raises, a verdict about a peer's bytes is returned.

DESIGN DECISION — why do `answer`, `echo_reply` and `error_message` never touch
the wire, while `ping` owns the whole exchange?
Because a peer's behaviour is a function and an exchange is a wait. `answer` is
the peer: hand it a datagram and it hands back the message it would have sent, or
`None` for silence — and the world's hosts are passive, so the caller is the one
who wraps the message in a datagram and a frame and puts it on the link. `ping`
is the caller: it composes the request, sends it, advances the wire by exactly
the ticks it was told to wait, and looks in its own box for the answer. Writing
the two as one would mean a stage that drives the link from inside a decision,
and this course has exactly one driver: the caller.

DESIGN DECISION — why is a bad checksum, a datagram for another address, a
message that is not a request and an unknown reason all `None` instead of a
refusal?
Because all four are *somebody else's* datagram, and a peer that raises on one is
a peer that stops answering the ones that were fine. Silence is the answer a
receiver gives to a packet it cannot use: the wire already had to carry it, and an
exception here would travel no further than the caller, who is not the sender and
cannot tell it anything. The one case that does raise is a datagram that cannot be
unpacked at all — a shape that is not a datagram — because there the caller has
handed this stage something it promised would be one.

    ICMP_HEADER        the eight bytes: `type | code | checksum | rest(4)`
    ERROR_QUOTE        28 bytes of the datagram an error message quotes
    ICMP_ECHO_REPLY    type 0: yes
    ICMP_UNREACHABLE   type 3: no route to that address
    ICMP_ECHO_REQUEST  type 8: are you there
    ICMP_TIME_EXCEEDED type 11: the hop count ran out at me
    ICMP_TYPES         the four types, as numbers and as names
    build              the bytes, with the checksum over all of them
    parse              the message's facts, its checksum's verdict and its quote
    echo_reply         type 0, with the request's ident, seq and payload
    error_message      the type the reason names, quoting the datagram
    answer             the peer: a request is answered, a refusal is quoted,
                       anything else is silence
    ping               the exchange: a request on the link, and the reply

`IcmpError` is the family, and every refusal names the offender: the type nobody
knows, the identifier or sequence number that is not sixteen bits, the payload
that is not bytes, the message shorter than its header, the reason that is not one
a router says.

TODO: implement `build`, `parse`, `echo_reply`, `error_message`, `answer` and
`ping`.
"""

ICMP_HEADER = 8
ERROR_QUOTE = 28
ICMP_ECHO_REPLY, ICMP_UNREACHABLE, ICMP_ECHO_REQUEST, ICMP_TIME_EXCEEDED = 0, 3, 8, 11
ICMP_TYPES = {0: "echo_reply", 3: "unreachable", 8: "echo_request", 11: "time_exceeded"}


class IcmpError(ValueError):
    """An ICMP message this stack cannot build or read, named as it is wrong.

    It is a `ValueError` like every refusal in this course, and the message names
    the offender: the type number, the identifier, the length, the reason word.
    """


def build(type_, ident=0, seq=0, payload=b""):
    """The eight bytes of §2.3 and the payload, in one message.

    `type_` is one of the four numbers, `ident` and `seq` are the sixteen-bit
    fields an echo's `rest` carries, and `payload` is the echo's data or — for an
    error — the datagram being quoted. The checksum covers everything, the field
    is zero while it is computed, and it lands where §2.3 puts it.
    """
    raise NotImplementedError("stage 4: implement build()")


def parse(message):
    """The message's facts: `{"type", "name", "code", "ident", "seq",
    "payload", "checksum_ok", "quote"}`.

    `quote` is the quoted datagram for an error type and `None` for an echo.
    Fewer than `ICMP_HEADER` bytes or a type nobody knows raises, naming the
    offender; a checksum that does not check out comes back as
    `"checksum_ok": False`.
    """
    raise NotImplementedError("stage 4: implement parse()")


def echo_reply(request):
    """The reply to an echo request: type 0, the request's ident, seq and
    payload."""
    raise NotImplementedError("stage 4: implement echo_reply()")


def error_message(datagram, reason):
    """The message a refused datagram earns, quoting `ERROR_QUOTE` bytes of it.

    `reason` is the word stage 3 refused with: `"ttl_expired"` is a time-exceeded
    and `"no_route"` is an unreachable. Anything else is a refusal naming the
    word; a datagram shorter than a header is a refusal naming its length.
    """
    raise NotImplementedError("stage 4: implement error_message()")


def answer(host, datagram, reason=None):
    """The peer's whole behaviour, and it returns `bytes` or `None`.

    A datagram whose checksum does not check out, one that is not addressed to
    this host, one that is not `icmp`, one whose message is not an echo request
    and a `reason` nobody knows are all `None` — silence, not a refusal. An echo
    request is answered with `echo_reply`'s bytes, and a `"ttl_expired"` or
    `"no_route"` reason is answered with `error_message`'s.
    """
    raise NotImplementedError("stage 4: implement answer()")


def ping(wire, host, dst_mac, dst_ip, ident=0, seq=1, payload=b"", ticks=2):
    """The whole exchange: `{"sent", "request", "reply", "ticks"}`.

    An echo request goes into a datagram into a frame addressed to `dst_mac`, the
    wire is advanced by `ticks` ticks, and this host's box is searched for a
    reply from `dst_ip` whose own checksums check out and whose ident and seq are
    this echo's. `reply` is the reply message and `None` when nothing came back —
    the wire having lost the frame is not an error.
    """
    raise NotImplementedError("stage 4: implement ping()")
