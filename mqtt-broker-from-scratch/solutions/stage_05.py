"""MQTT Broker From Scratch — stage 5: PUBLISH, routing, and what is retained.

See `stage_05.py` for the surface and the design decisions; this is the packet
that carries a message, and the table that keeps one for whoever comes next.
"""

import stage_01
import stage_03

PUBLISH_KEYS = ("topic", "payload", "qos", "packet_id", "retain", "dup")

DUP_BIT = 0b1000
QOS_BITS = 0b0110
RETAIN_BIT = 0b0001


def _buffer(data, what):
    """The buffer as bytes, or a refusal naming what was handed in instead."""
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    raise stage_01.ProtocolError("%s must be bytes, not %s"
                                 % (what, type(data).__name__))


def _position(data, pos):
    """A position inside `data`, or a refusal naming the position and the size."""
    if isinstance(pos, bool) or not isinstance(pos, int):
        raise stage_01.ProtocolError("a position must be an int, not %r" % (pos,))
    if not 0 <= pos <= len(data):
        raise stage_01.ProtocolError("a position of %d in %d bytes"
                                     % (pos, len(data)))
    return pos


def _short(data, pos, need):
    """Refuse `need` bytes that have not arrived, as an `Incomplete`."""
    have = len(data) - pos
    if have < need:
        raise stage_01.Incomplete(need - have)


def _nibble(flags):
    """The flags nibble of a PUBLISH, or a refusal naming what arrived."""
    if isinstance(flags, bool) or not isinstance(flags, int):
        raise stage_01.ProtocolError("a PUBLISH flags nibble must be an int, not %r"
                                     % (flags,))
    if not 0 <= flags <= 0b1111:
        raise stage_01.ProtocolError("a flags nibble of %d is not four bits"
                                     % (flags,))
    return flags


def _qos(value):
    """A QoS level, 0 to 2, or a refusal naming what arrived."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise stage_01.ProtocolError("a QoS must be an int, not %s"
                                     % (type(value).__name__,))
    if not 0 <= value <= 2:
        raise stage_01.ProtocolError("a QoS of %d is not 0, 1 or 2" % (value,))
    return value


def _bit(value, what):
    """A flag that is on or off, as a bool, or a refusal naming what arrived."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    raise stage_01.ProtocolError("%s must be a bool or 0/1, not %r"
                                 % (what, value))


def _packet_id(packet_id):
    """A packet id in 1…65535, or a refusal naming what arrived."""
    if isinstance(packet_id, bool) or not isinstance(packet_id, int):
        raise stage_01.ProtocolError("a packet id must be an int, not %r"
                                     % (packet_id,))
    if not 1 <= packet_id <= 65_535:
        raise stage_01.ProtocolError("a packet id of %d is not between 1 and 65535"
                                     % (packet_id,))
    return packet_id


def _message(publish):
    """A copy of a publish with its six keys in `PUBLISH_KEYS` order."""
    if not isinstance(publish, dict):
        raise stage_01.ProtocolError("a publish must be a dict, not %s"
                                     % (type(publish).__name__,))
    for key in PUBLISH_KEYS:
        if key not in publish:
            raise stage_01.ProtocolError("a publish with no %r in it" % (key,))
    return {key: publish[key] for key in PUBLISH_KEYS}


def _topic_from(data, pos):
    """The topic at `pos`, as `(name, pos_after)`: two bytes of length, then UTF-8.

    The length counts *bytes* and never characters, and the name is judged by
    stage 3's `validate_topic` the moment it is text: a PUBLISH may not carry a
    wildcard, and an empty topic names nothing to publish to. A payload that is
    not UTF-8 is a refusal naming the bytes, because no amount of waiting turns
    it into a topic.
    """
    _short(data, pos, 2)
    length = (data[pos] << 8) | data[pos + 1]
    start = pos + 2
    _short(data, start, length)
    raw = data[start:start + length]
    try:
        name = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise stage_01.ProtocolError("a publish topic of %r is not UTF-8"
                                     % (raw,))
    return stage_03.validate_topic(name), start + length


def _topic_bytes(name):
    """The topic's wire bytes: two bytes of length, then its UTF-8."""
    raw = stage_03.validate_topic(name).encode("utf-8")
    return bytes([len(raw) >> 8, len(raw) & 0xFF]) + raw


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
    data = _buffer(data, "the buffer a PUBLISH is read from")
    pos = _position(data, pos)
    flags = _nibble(flags)
    topic, pos = _topic_from(data, pos)
    qos = (flags & QOS_BITS) >> 1
    if qos == 3:
        raise stage_01.ProtocolError(
            "a PUBLISH with a QoS of 3 (the flags nibble was 0x%02x)" % (flags,))
    packet_id = None
    if qos > 0:
        _short(data, pos, 2)
        packet_id = (data[pos] << 8) | data[pos + 1]
        pos += 2
    publish = {"topic": topic, "payload": data[pos:], "qos": qos,
               "packet_id": packet_id, "retain": bool(flags & RETAIN_BIT),
               "dup": bool(flags & DUP_BIT)}
    return publish, len(data)


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
    body = _topic_bytes(topic)
    if not isinstance(payload, (bytes, bytearray)):
        raise stage_01.ProtocolError("a publish payload must be bytes, not %s"
                                     % (type(payload).__name__,))
    qos = _qos(qos)
    _bit(retain, "the retain flag")
    _bit(dup, "the DUP flag")
    if qos == 0:
        if packet_id is not None:
            raise stage_01.ProtocolError(
                "a QoS 0 publish carries no packet id, and %r was given"
                % (packet_id,))
    else:
        if packet_id is None:
            raise stage_01.ProtocolError("a QoS %d publish needs a packet id"
                                         % (qos,))
        _packet_id(packet_id)
        body += bytes([packet_id >> 8, packet_id & 0xFF])
    return body + bytes(payload)


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
        held = _message(publish)
        if not held["payload"]:
            self._held.pop(held["topic"], None)
            return False
        self._held[held["topic"]] = held
        return True

    def lookup(self, topic):
        """The publish held for exactly this topic, or `None`.

        Exactly: a message retained for `a/b` answers for `a/b` and for nothing
        else, because a topic is a name and not a pattern — a lookup that matched
        by components would hand `a/b`'s message to a subscriber of `a/+`, which
        is the trie's job and not this table's.
        """
        return self._held.get(topic)

    def topics(self):
        """The topics held, in the order they were first held.

        A topic that is published to again keeps the place it first had: the
        order is the order of first retention, so two runs of one scenario list
        the same topics in the same order.
        """
        return tuple(self._held)


def route(trie, topic):
    """Every client a publish to `topic` reaches, as `[(who, qos)]`.

    The topic is judged first, by stage 3's `validate_topic`: a wildcard is a
    filter, and a broker that routes one routes a pattern as if it were a name.
    What is left is the trie's own answer — one entry per client, at the highest
    QoS that client holds for the topic — so this is a lookup through the
    matcher, never a second matcher.
    """
    name = stage_03.validate_topic(topic)
    return [(who, qos) for who, qos in trie.match(name)]


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
    held = _message(publish)
    retained = _bit(retained, "the retained delivery flag")
    wanted = {}
    for entry in subscribers:
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            raise stage_01.ProtocolError("a subscriber must be a (who, qos) pair, "
                                         "not %r" % (entry,))
        who, qos = entry
        if not isinstance(who, str):
            raise stage_01.ProtocolError("a subscriber's name must be a str, not %s"
                                         % (type(who).__name__,))
        qos = _qos(qos)
        if who not in wanted or qos > wanted[who]:
            wanted[who] = qos
    if not held["payload"]:
        return []
    return [(who, {"topic": held["topic"], "payload": held["payload"], "qos": qos,
                   "packet_id": None, "retain": bool(retained), "dup": False})
            for who, qos in wanted.items()]
