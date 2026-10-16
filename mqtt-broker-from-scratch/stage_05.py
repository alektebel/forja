"""MQTT Broker From Scratch — stage 5: PUBLISH, routing, and what is retained.

A CONNECT opens a conversation and a SUBSCRIBE says what a client wants to hear;
a PUBLISH is the message itself. It is the only packet in this course whose
*body* has two shapes: the four bits of its header's low nibble — DUP, QoS and
RETAIN — decide whether a two-byte packet id follows the topic, and the reader
cannot know where the payload starts without them. The topic comes first,
always; then, if and only if the QoS is above zero, the id; then the payload, to
the end of the body. A topic is a name, not a pattern: a wildcard in one, or an
empty one, is refused where it arrives instead of being routed as if somebody
could be listening to it.

The rest of the stage is what a broker does with the message once it has it.
Routing is one question — which clients hold a filter that matches this topic —
and it is stage 3's trie that answers it: one entry per client, at the highest
QoS that client holds for the topic, because two matching subscriptions are two
interests and not two messages. Delivery is the same message at each
subscriber's own level: the bytes do not change, the QoS they go out at does.

Retention is the promise that outlives the moment it was made. A message
published with RETAIN is kept for its *topic*, not for a subscriber and not for
a session: the last publish to a topic wins and keeps its QoS, and a client that
subscribes an hour later is handed it then — at subscribe time, and never live
at publish time. A zero-length payload with RETAIN is not a message at all: it
clears the topic, is stored nowhere and is delivered to nobody.

    PUBLISH_KEYS    the six keys of a parsed publish, in the order they are read
    DUP_BIT         bit 3 of the flags nibble: this transmission is a re-send
    QOS_BITS        bits 2-1 of the flags nibble: the level, 0 to 2
    RETAIN_BIT      bit 0 of the flags nibble: keep this message for the topic
    read_publish    (data, pos, flags) -> (publish, pos_after); the flags decide the body
    write_publish   (topic, payload, qos, packet_id, retain, dup) -> the body's bytes
    Retained        the store: one message per topic; store, lookup, topics
    route           (trie, topic) -> [(who, qos)], one entry per client
    deliveries      (publish, subscribers, retained) -> [(who, message)], one per subscriber

A refusal names the offender — the flags nibble, the position, the packet id, the
topic, the subscriber that is not a pair — and it is a refusal only when the
bytes or the shapes cannot mean what they claim. A question about content, such
as which clients a topic reaches, is answered with a value: the empty list is a
legitimate answer to a publish nobody subscribed to.

DESIGN DECISION — why is the flags nibble handed to `read_publish` instead of
being read from the packet's first byte?
Because a reader in this course is handed a body, and the body's *shape* here
depends on a byte that is not in it. PUBLISH is the only packet like that: with
QoS 0 there is no id and with QoS above zero there are two bytes of one, so a
reader that cannot see the nibble cannot tell a payload's first two bytes from
an id. The caller already has them — stage 1's `read_header` returns the flags —
and stage 10's `read_frames` is the only reader that starts from a frame, which
is what hands the nibble down. The alternative, teaching this one reader to
unframe a packet, would put a second copy of the length rule in the course.

DESIGN DECISION — why is a retained message kept for its topic and not for a
subscriber?
Because a subscriber is not who the message is for — the topic is. A message
kept per subscriber answers a question nobody asked (what did this client miss?)
and it multiplies: two hundred subscribers would hold two hundred copies of one
message, and the copy the next subscriber gets would depend on which of them
happened to be listening. Kept per topic, there is exactly one answer to "what
is on a/b?", it is the last message published there, and every later subscriber
is handed the same bytes.

DESIGN DECISION — why does a zero-length payload clear the topic rather than
being stored as an empty message?
Because otherwise a retained topic could never be emptied: the way to stop
handing a stale message to new subscribers has to be a *publish* to that topic,
and a subscriber that receives the empty message cannot tell a cleared topic
from a publisher who meant to send nothing. The clear is therefore an act on the
topic and not a message: it takes the topic away, it is not stored, and it is
delivered to nobody — which is also why `store` answers which of the two it did.

DESIGN DECISION — why does `deliveries` answer `(who, message)` pairs rather
than a list of messages?
Because the caller's next step is to write one frame per subscriber onto that
subscriber's own stream, and a list of messages would have lost which client is
which the moment two subscriptions were deduplicated. The pair carries exactly
what the question asked — who, and the message at their level — and it is the
same shape `route` answers in, so the two halves of this stage read alike.

DESIGN DECISION — why does a delivery carry `packet_id` of `None`?
Because the id on a PUBLISH belongs to the side that sends it, and a delivery is
a new transmission: the id the publisher chose was for the publisher's own
in-flight message, and the broker cannot hand its own id to a message that has
not been put in flight yet. `None` says the message is ready to go and has not
been given an id, which is exactly the state in which stage 6's `PacketIds` is
asked for one — and a delivery that invented an id would have taken one out of a
space it does not own.

DESIGN DECISION — why does `deliveries` take a `retained` flag instead of reading
the publish's own?
Because the same message is delivered twice in a broker's life and the flag is
not the same both times. When it is published it goes out live, and the
subscribers listening at that moment are told `retain=0`: the message is not a
replay of anything, even though the publisher asked for it to be kept. Later, a
client subscribes and the stored copy is handed to it, and *that* delivery says
`retain=1`, which is how the client knows it is history rather than news. The
bytes are identical, so the flag cannot come from them — it is the caller's
knowledge of which of the two acts it is performing, and putting it in the call
keeps the rule in the stage that knows about retention rather than in the
capstone that merely wires the two calls together.

TODO: implement `read_publish`, `write_publish`, `route`, `deliveries` and every
method of `Retained`.
"""

PUBLISH_KEYS = ("topic", "payload", "qos", "packet_id", "retain", "dup")

DUP_BIT = 0b1000
QOS_BITS = 0b0110
RETAIN_BIT = 0b0001


def read_publish(data, pos=0, flags=0):
    """The PUBLISH at `pos` of its own body, as `(publish, pos_after)`.

    `data` is the body — the topic, the optional id and the payload — and
    `flags` is the low nibble of the fixed header, which the caller already has
    from stage 1's `read_header`. PUBLISH is the one packet whose body depends
    on its flags: with QoS 0 no id follows the topic, with QoS above zero the
    next two bytes are it, and a reader that guesses wrong eats the payload's
    first two bytes or reads them as a topic.

    The publish's six keys are `PUBLISH_KEYS`, in that order; `packet_id` is
    `None` at QoS 0, because a QoS 0 publish carries no id and one cannot be
    invented once the bytes are gone. `payload` runs to the end of the body, and
    a body that stops before the id it says it has is an `Incomplete` needing the
    two bytes that have not arrived.
    """
    raise NotImplementedError("stage 5: implement read_publish()")


def write_publish(topic, payload, qos=0, packet_id=None, retain=False, dup=False):
    """The body of a PUBLISH: the topic, the optional id and the payload.

    The body alone: the type byte and the length that frame it are stage 1's,
    and the DUP, QoS and RETAIN bits live in the header's low nibble, which the
    caller writes. `retain` and `dup` are taken anyway, so that one call
    describes the whole packet and a caller cannot frame a QoS 2 message as a
    burst of QoS 0 duplicates without saying so.

    A QoS 0 publish carries no id and a QoS above zero needs one, in 1…65535;
    the topic is judged as a publish topic, so a wildcard or an empty name is
    refused here rather than on the wire.
    """
    raise NotImplementedError("stage 5: implement write_publish()")


class Retained:
    """The retained messages a broker holds, one per topic.

    A retained message belongs to its *topic* and not to a subscriber: the last
    publish to a topic wins and keeps its QoS, and the message is handed to
    whoever subscribes next — at subscribe time, never at publish time, because
    the point of retaining a message is that the subscriber was not there when it
    was published.
    """

    def __init__(self):
        """An empty store: no topic is held until a publish asks to be."""
        self._held = {}

    def store(self, publish):
        """Hold `publish` for its topic, or clear the topic if its payload is empty.

        Answers `True` when the message is now held and `False` when it cleared
        one instead. A zero-length payload is a clear and not a message: it takes
        the topic away, and storing it would leave a subscriber receiving an
        empty message that was never published as one.
        """
        raise NotImplementedError("stage 5: implement Retained.store()")

    def lookup(self, topic):
        """The publish held for exactly this topic, or `None`.

        Exactly: a message retained for `a/b` answers for `a/b` and for nothing
        else, because a topic is a name and not a pattern — a lookup that matched
        by components would hand `a/b`'s message to a subscriber of `a/+`, which
        is the trie's job and not this table's.
        """
        raise NotImplementedError("stage 5: implement Retained.lookup()")

    def topics(self):
        """The topics held, in the order they were first held.

        A topic that is published to again keeps the place it first had: the
        order is the order of first retention, so two runs of one scenario list
        the same topics in the same order.
        """
        raise NotImplementedError("stage 5: implement Retained.topics()")


def route(trie, topic):
    """Every client a publish to `topic` reaches, as `[(who, qos)]`.

    The topic is judged first, by stage 3's `validate_topic`: a wildcard is a
    filter, and a broker that routes one routes a pattern as if it were a name.
    What is left is the trie's own answer — one entry per client, at the highest
    QoS that client holds for the topic — so this is a lookup through the
    matcher, never a second matcher.
    """
    raise NotImplementedError("stage 5: implement route()")


def deliveries(publish, subscribers, retained=False):
    """One delivery per subscriber, as `[(who, message)]`.

    `message` is a copy of `publish` with that subscription's own QoS: the bytes
    on the wire are the same, the level the message goes out at is not. A client
    that holds two filters that both match is handed the message once, at the
    higher of the two QoS — the second subscription is a second interest, not a
    second message.

    A zero-length payload is delivered to nobody: it cleared a retained topic and
    it is not a message. `packet_id` is `None` — the id a message goes out with
    belongs to the sending side and is taken when the message is put in flight —
    and `retain` says which of the two deliveries this is: `True` only when the
    broker is handing a subscriber the stored message it just asked for, and
    `False` for a live one, whatever the publish's own flag says. A message that
    was retained on its way past is still delivered to the subscribers who were
    there as an ordinary message, and the publish's own flag is what the broker
    wrote the store with, not what the subscribers are told.
    """
    raise NotImplementedError("stage 5: implement deliveries()")
