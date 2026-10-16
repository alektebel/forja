"""MQTT Broker From Scratch — stage 4: SUBSCRIBE, SUBACK and the granted QoS.

A client that has connected and has a session now says what it wants to hear. A
SUBSCRIBE carries a packet id and then one or more topic filters, each with the
QoS the client is *asking* for. The broker answers with a SUBACK that echoes the
client's packet id and carries one return code per filter — and the number the
client asked for is not the number it is granted.

That gap is the whole stage. A broker that echoes the request back promises a
delivery level it may not be able to keep: the client stops keeping its own copy
of a message, the broker drops one under load, and the message is gone with both
sides believing the other still has it. So the grant is `min(requested, cap)` —
deliberately a different number from the ask — and a filter the broker will not
route is answered with `SUBACK_FAILURE` rather than quietly granted at zero. The
client is told what happened to each subscription, one code per filter, in the
order it asked.

    SUBSCRIBE_FLAGS         0b0010 — the low nibble a SUBSCRIBE must carry
    MAX_QOS                 2 — the highest QoS this broker speaks
    SUBACK_FAILURE          0x80 — the code for a filter that will not be routed
    SUBSCRIBE_KEYS          the two keys of a parsed SUBSCRIBE, in order
    read_subscribe          (data, pos) -> (subscribe, pos): id and (filter, qos) tuples
    read_unsubscribe        (data, pos) -> ([packet_id, filters], pos): no QoS byte
    granted_qos             (requested, cap) -> the granted qos: min, but a refusal if malformed
    grant_codes             (subscribe, cap, refused) -> one code per filter, in order
    write_suback            (packet_id, codes) -> bytes: the body, id echoed in front
    write_unsuback          (packet_id) -> bytes: the body, a bare id

A SUBSCRIBE rides in a packet whose fixed header — its type, its reserved low
nibble and its length — is read once by stage 1 before any of these readers run,
so a reader here is handed a body and never sees the nibble. What the body can
still get wrong is its own shape: a packet id of 0, a requested QoS above
`MAX_QOS`, a body with no filter at all, and a trailing byte are the refusals —
bytes a peer can never mean, answered with stage 1's `ProtocolError` naming the
id, the QoS or the count that arrived. A buffer that stops mid-field is stage 1's
`Incomplete`, `.needed` exact, because the packet is on its way and no amount of
waiting turns a malformed request into a well-formed one.

DESIGN DECISION — why is the granted QoS a different number from the requested
one, and not simply the request echoed back?
Because they are answers to two different questions. The client asks "what would
you like?"; the broker answers "here is what I will actually do", and a broker
that can only speak QoS 1 must say so *before* the client relies on QoS 2. The
echo is the lie that loses messages: the client hands over its only copy, the
broker delivers at best effort, and neither side learns the difference. A single
`min(requested, cap)` — returned as a value, never thrown — keeps both sides
honest about which of them owns the message.

DESIGN DECISION — why is a refused filter answered with `SUBACK_FAILURE` instead
of just a granted QoS of 0?
Because "I will deliver this unreliably" and "I will not deliver this at all"
are different promises, and a client that hears 0 will keep waiting for messages
that will never come. `SUBACK_FAILURE` is the one code that means the
subscription does not exist, so a client can stop, log it, or tell its user. It
is per filter and not per packet for the same reason: a SUBSCRIBE is often a set
of filters, and the broker may accept some and refuse others.

DESIGN DECISION — why does the SUBACK echo the client's packet id rather than one
of the broker's own?
Because the id is the client's handle on a question *it* asked. A broker that
invents a fresh id leaves the client waiting for an answer to a packet it never
sent, and the client's own bookkeeping — which id is in flight, what it is
waiting for — never matches the broker's again. The id names the request, so the
answer must carry the requester's name for it, whatever the broker's own next id
happens to be.

DESIGN DECISION — why does UNSUBSCRIBE carry no QoS byte after each filter, when
SUBSCRIBE carries one?
Because there is nothing to ask for. A SUBSCRIBE's QoS is the client saying how
it wants future deliveries; an UNSUBSCRIBE only removes a subscription that
already has one. A reader that consumes a byte after the filter eats the next
filter's first length byte — and the client is unsubscribed from a filter it
never named, while the one it did name stays. So the two readers share an id and
a filter list and differ in exactly that one byte.

DESIGN DECISION — why is a malformed request an exception while a grant lower
than the ask is a returned value?
Because only one of them is an answer a client can act on. "You asked for QoS 2
and I grant QoS 1" is a broker negotiating, and the client can downgrade its
expectations; but a requested QoS of 3, a packet id of 0 or a body that is not a
body describe bytes no peer can mean, and a value returned for them would be read
as a grant. The course draws the line at the shape: a question with an opinion is
answered with a *value*, and a shape that is not a shape is a `ProtocolError` —
the same distinction a client and a broker make about what was asked for.

TODO: implement
"""

SUBSCRIBE_FLAGS = 0b0010
MAX_QOS = 2
SUBACK_FAILURE = 0x80

SUBSCRIBE_KEYS = ("packet_id", "topics")


def read_subscribe(data, pos=0):
    """The SUBSCRIBE body at `pos`, as `(subscribe, pos_after)`.

    A non-zero packet id, then one or more filters — each a two-byte-length string
    followed by the QoS the client is asking for. The QoS bytes are requests,
    never grants: a requested QoS above `MAX_QOS`, a packet id of 0, no filter at
    all and a trailing byte are `ProtocolError`s naming what arrived; a body that
    stops inside a field is stage 1's `Incomplete`, `.needed` exact.
    """
    raise NotImplementedError("stage 4: implement read_subscribe()")


def read_unsubscribe(data, pos=0):
    """The UNSUBSCRIBE body at `pos`, as `([packet_id, filters], pos_after)`.

    The same non-zero id and the same one-or-more filters as a SUBSCRIBE — but
    each filter is a bare string with no QoS byte after it.
    """
    raise NotImplementedError("stage 4: implement read_unsubscribe()")


def granted_qos(requested, cap=MAX_QOS):
    """What the broker actually grants: `min(requested, cap)`.

    Deliberately a different number from the ask. A requested QoS or a cap that
    is not 0, 1 or 2 is a `ProtocolError` naming it, never a lower grant.
    """
    raise NotImplementedError("stage 4: implement granted_qos()")


def grant_codes(subscribe, cap=MAX_QOS, refused=()):
    """One return code per filter, in the order the filters were asked for.

    `SUBACK_FAILURE` for a filter named in `refused`, the granted QoS otherwise.
    """
    raise NotImplementedError("stage 4: implement grant_codes()")


def write_suback(packet_id, codes):
    """The SUBACK body: the echoed packet id, then exactly one code per filter."""
    raise NotImplementedError("stage 4: implement write_suback()")


def write_unsuback(packet_id):
    """The UNSUBACK body: the echoed packet id and nothing else."""
    raise NotImplementedError("stage 4: implement write_unsuback()")
