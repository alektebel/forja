"""MQTT Broker From Scratch — stage 2: The two-byte string and the CONNECT.

Before a broker has a session, a subscription or a single byte of payload, it has
to read one packet whose fields are not all the same kind of thing. A CONNECT is
two strings that must be text (the protocol name and the client's identifier),
two fields that must *not* be (the will's message and the password — MQTT calls
them binary data on purpose, and a broker that decodes them refuses a legal
password), and a flags byte that decides which of the rest exist at all.

The flags byte is the stage. Bit 7 says a username follows, bit 6 a password, bit
5 a will retain, bits 4–3 a will QoS, bit 2 the will itself, bit 1 the clean
start, and bit 0 is reserved and must be zero. Every one of those decisions
changes the shape of everything after it, so a reader that reads the will
unconditionally reads the client's username as the will's topic — and the error
does not surface here, it surfaces three stages later as a subscription nobody
asked for.

The other half of the stage is what a broker may *say*. A protocol name it does
not speak and a level it does not implement are not malformed packets: they are
a conversation, and the answer is a CONNACK with code 1 and then a close. An
empty client identifier is legal — if and only if the client also asks for a
clean start — and the answer when it is not is code 2. A CONNACK is two bytes,
and the first of them may not lie: a refused CONNECT resumes no session, so the
session-present bit is zero on every refusal.

    PROTOCOL_NAME            "MQTT", the four bytes a CONNECT must start with
    PROTOCOL_LEVEL           4, the one level this broker speaks
    MAX_STRING_BYTES         65_535, because a string's length field is two bytes
    CONNECT_KEYS             the eight keys a parsed CONNECT carries, in wire order
    WILL_KEYS                the four keys of a will: topic, payload, qos, retain
    CLIENT_TYPES             the ten packet types a client may send a broker
    CONNACK_ACCEPTED … _NOT_AUTHORIZED   the six codes, 0 through 5
    CONNACK_CODES            the six, in order
    read_string              (data, pos) -> (text, pos): two bytes of length, then UTF-8
    read_payload             (data, pos) -> (bytes, pos): two bytes of length, then raw bytes
    write_string             (text) -> bytes: the UTF-8 bytes, length in front
    read_connect             (data, pos) -> (connect, pos): the body of a CONNECT, exactly
    connack_code             (connect) -> int: what a broker answers, and why
    write_connack            (session_present, code) -> bytes: the two bytes, and their rule

`read_connect` is handed the packet's body and not the whole packet: the fixed
header from stage 1 has already said how long the body is, so a byte left over at
the end is a byte the packet never claimed. Every refusal names what arrived — the
flags byte, the payload that was not UTF-8, the trailing byte — and every refusal
belongs to stage 1's `ProtocolError`, so a caller's `except` is the same one.

DESIGN DECISION — why does a string's length count bytes rather than characters?
Because the wire counts bytes and nothing else. A length of 5 in front of "café"
describes a five-byte payload that decodes to four characters; a reader that
compares its decoded text against the length it read will slice the next field
one byte short, and the first symptom will be a will topic with a letter missing.
So the read is: take the length as *bytes*, slice that many, and only then decode
— and the decode is where a payload that is not UTF-8 becomes a refusal.

DESIGN DECISION — why are the protocol name and level returned instead of
refused?
Because they are a question a broker is allowed to have an opinion about, and
MQTT gives it an answer to say: CONNACK with return code 1, then close. A
`ProtocolError` means the bytes can never be a packet — the reserved bit, a
password with no username, a trailing byte — while a level of 5 is a perfectly
well-formed CONNECT from a client this broker does not speak to. Mixing the two
would leave the broker with no way to answer, and a client with no way to know
which of the two happened.

DESIGN DECISION — why are the will's message and the password raw bytes, when the
will's topic and the client's identifier are strings?
Because MQTT says so, and for a reason a reader can feel: a password is a secret
whose bytes need not be text at all (a digest, a certificate, anything), and a
will's message is somebody's payload — the same bytes that would have been
published. Only the fields that MQTT requires to be *well-formed UTF-8* are read
as strings, and everything else is read as a length and that many bytes. A reader
that decodes every length-prefixed field the same way refuses legal packets and,
worse, reports them as malformed rather than as unreadable.

DESIGN DECISION — why must `data` be the CONNECT's body, exactly?
Because the count is the check. The fixed header said the body is N bytes; the
fields the flags promised must use exactly N. A reader that ignores the leftover
is a reader that will happily take two packets worth of bytes as one, and the
next packet starts somewhere it does not, which is the failure mode every later
stage inherits. So the last thing `read_connect` does is compare its own position
against the body's length and refuse the difference by name.

DESIGN DECISION — why may a refusal not carry the session-present bit?
Because the bit is a promise about state, and a refusal is the absence of any. A
client told "refused, but a session is waiting" has two incompatible answers to
one CONNECT: it may believe a subscription it once made is still in force and
never re-subscribe, and then lose every message published to it. The wire rule is
one byte wide — the bit is set only when the code is zero — and it costs one line
to keep.

TODO: implement
"""

CONNECT = 1
CONNACK = 2
PUBLISH = 3
PUBACK = 4
PUBREC = 5
PUBREL = 6
PUBCOMP = 7
SUBSCRIBE = 8
SUBACK = 9
UNSUBSCRIBE = 10
UNSUBACK = 11
PINGREQ = 12
PINGRESP = 13
DISCONNECT = 14

PROTOCOL_NAME = "MQTT"
PROTOCOL_LEVEL = 4
MAX_STRING_BYTES = 65_535

CONNECT_KEYS = ("protocol_name", "protocol_level", "clean_start", "keep_alive",
                "client_id", "will", "username", "password")

CLIENT_TYPES = (CONNECT, PUBLISH, PUBACK, PUBREC, PUBREL, PUBCOMP, SUBSCRIBE,
                UNSUBSCRIBE, PINGREQ, DISCONNECT)

CONNACK_ACCEPTED = 0
CONNACK_REFUSED_VERSION = 1
CONNACK_REFUSED_IDENTIFIER = 2
CONNACK_REFUSED_UNAVAILABLE = 3
CONNACK_REFUSED_CREDENTIALS = 4
CONNACK_REFUSED_NOT_AUTHORIZED = 5

CONNACK_CODES = (CONNACK_ACCEPTED, CONNACK_REFUSED_VERSION,
                 CONNACK_REFUSED_IDENTIFIER, CONNACK_REFUSED_UNAVAILABLE,
                 CONNACK_REFUSED_CREDENTIALS, CONNACK_REFUSED_NOT_AUTHORIZED)

WILL_KEYS = ("topic", "payload", "qos", "retain")


def read_string(data, pos=0):
    """The MQTT string at `pos`, as `(text, pos_after)`.

    Two bytes of length, big-endian, then that many bytes of UTF-8 — so the
    length counts *bytes* and never characters. A payload that is not UTF-8 is a
    `ProtocolError` naming the bytes; a buffer that is short of the length or of
    the payload is an `Incomplete` with the shortfall exactly.
    """
    raise NotImplementedError("stage 2: implement read_string()")


def read_payload(data, pos=0):
    """Two bytes of length and that many raw bytes, as `(payload, pos_after)`.

    Not a string: the will's message and the client's password are binary data
    with the same two-byte length in front.
    """
    raise NotImplementedError("stage 2: implement read_payload()")


def write_string(text):
    """`text` as an MQTT string: its UTF-8 bytes, two bytes of length in front."""
    raise NotImplementedError("stage 2: implement write_string()")


def read_connect(data, pos=0):
    """The CONNECT at `pos` of its own body, as `(connect, pos_after)`.

    The eight keys of `CONNECT_KEYS`, in that order, with `will` either `None` or
    a dict of `WILL_KEYS`. The protocol name and level are returned rather than
    judged; a reserved bit, a will QoS or retain with no will, a password with no
    username and a trailing byte are `ProtocolError`s naming what arrived.
    """
    raise NotImplementedError("stage 2: implement read_connect()")


def connack_code(connect):
    """What a broker answers a parsed CONNECT, as one of `CONNACK_CODES`."""
    raise NotImplementedError("stage 2: implement connack_code()")


def write_connack(session_present, code):
    """The two bytes of a CONNACK: the session-present bit, then the code."""
    raise NotImplementedError("stage 2: implement write_connack()")
