"""MQTT Broker From Scratch — course manifest.

Ten graded stages between a byte stream and a broker whose every frame the
course's own reader accepts. The world is provided and complete: `streams.py` is
the transport — named streams a broker accepts one `CHUNK` at a time, a `send`
that returns how many bytes it took so the tail stays the caller's to keep, an
agreed `close` that refuses while a byte is still in flight, a `cut` that never
refuses and counts what it lost, a clock that moves only through `step()`, and a
log that `stats()` recomputes every number from; `grants.py` is the policy — a
table of topics per client, a ceiling no grant can widen, a closed vocabulary of
six reasons, and a decision line written before the act it allows.

The thesis of the whole course is one sentence, and every stage's check asserts
it: A BROKER IS A READER THAT NEVER GUESSES AND A WRITER THAT NEVER IMPROVISES —
EVERY BYTE IT ACCEPTS IS A FRAME THE FORMAT ALLOWS, AND EVERY BYTE IT SENDS IS ONE
ITS OWN READER TAKES BACK. Each stage exists because the one before it left a
hole: a packet's own length is written in a variable-width field, so nothing can
be read before that field is; a flags byte decides which of the following fields
exist, and two of them are not text; `+` and `#` are matched by components and
`#` includes its own parent, which no prefix comparison ever does; a granted QoS
is a different number from the one that was asked for, and one packet carries
many of both; a retained message belongs to a topic and not to a subscriber, and
is delivered to a subscription that did not exist when it was published; a packet
id is in flight until its acknowledgement arrives, and the clock — never a poll —
decides when a message is sent again; exactly-once is a state machine that holds
an id across four packets and delivers at the third; subscriptions, the queued
tail, the will and the keep-alive are promises that outlive the socket they were
made on; a grant narrows the broker's ceiling and a denial is a line written
before the act; and the only proof of any of it is one scripted run whose every
written frame the course's own reader accepts, twice, with its report held
against the transport's own log.

The failures worth preventing are the ones that look like success: a reader that
treats the bytes it has as the packet it wants; a variable-length integer read
until the buffer ends, so a truncation becomes a value; a string measured in
characters after being decoded in bytes; a will payload decoded as text; a filter
matched with `startswith`, so `a/b` matches `a/bc` and `a/#` forgets its parent; a
granted QoS higher than the cap; a retained message redelivered as if it were
live; a packet id released before the acknowledgement that releases it; a
redelivery loop that re-sends every tick because the deadline was reset without
sending or never compared at all; a QoS 2 message delivered twice at the two
different places it could be; a session that resumes with yesterday's
subscriptions gone; a will that fires on a clean DISCONNECT; a denial that is
logged after the publish it refused; and a capstone that reports what the broker
believed instead of what the trace and the transport's log both show.

Standard library only, offline, deterministic, **ints only** (every length, tick,
byte count, packet id, deadline and ratio — there is no float literal anywhere in
this course): no `time`, no `threading`, no `asyncio`, no `random`, no `os`, no
`socket`, no subprocesses, no wall clock, no module-level mutable state, and no
`statistics`, `math`, `decimal` or `fractions` either. `socket` is banned because
*it is the subject*: the transport is handed in, a step is the only thing that
moves a byte or a tick, and the broker's whole value is that its frames can be
read back by the same rules it read them with. The last stage is the run that
holds both accounts against each other: the broker's report and the transport's
log.

This is the third of `NETWORKING.md`'s three series and the last course of phase
L. L1 is the framing half of a wire — a frame and its type field, addresses,
checksums, the sliding window, retransmission on an injected clock. J4 is the
policy: a capability decides what a program may do and the decision is recorded
before it acts. L3 is both halves at once on a protocol small enough to read end
to end: every field the format has, every promise a session makes, and every
refusal written down.

    python3 codecraft/cli.py run mqtt-broker-from-scratch
"""

from codecraft.api import stage

TITLE = "MQTT Broker From Scratch"
DESCRIPTION = ("A broker at the end of a byte pipe: the fixed header and its "
               "variable-length integer, CONNECT and the flags that say which "
               "fields exist, a topic trie where `+` and `#` are components and "
               "never prefixes, SUBSCRIBE's granted QoS and PUBLISH's retained "
               "message, QoS 1 as a packet id held in flight until its PUBACK, "
               "QoS 2 as the four-way handshake that delivers exactly once at "
               "PUBREL, a session that keeps subscriptions, a queued tail, a will "
               "and a keep-alive across a reconnect, the grants that decide who "
               "may publish where, and a capstone whose trace is re-read by the "
               "course's own reader and cross-checked against the transport's "
               "log.")

LEVEL = "advanced"
ORDER = 28


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "mqtt-broker-from-scratch"

    TYPE_NUMBERS = {
        "CONNECT": 1, "CONNACK": 2, "PUBLISH": 3, "PUBACK": 4, "PUBREC": 5,
        "PUBREL": 6, "PUBCOMP": 7, "SUBSCRIBE": 8, "SUBACK": 9, "UNSUBSCRIBE": 10,
        "UNSUBACK": 11, "PINGREQ": 12, "PINGRESP": 13, "DISCONNECT": 14,
    }

    VARINTS = (0, 1, 5, 127, 128, 129, 255, 16_383, 16_384, 300, 2_097_151,
               2_097_152, 300, 268_435_454, 268_435_455)

    GROUPS = lambda value: (1 if value < 128 else 2 if value < 16_384
                            else 3 if value < 2_097_152 else 4)

    def _repo(start=None):
        for candidate_start in (os.environ.get("L3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _constants(s):
        for name, number in sorted(TYPE_NUMBERS.items()):
            got = getattr(s, name)
            assert got == number, (
                "%s is packet type %d on the wire, not %r" % (name, number, got))
            assert s.TYPE_NAMES.get(number) == name, (
                "TYPE_NAMES says %r is called %r, so a refusal prints the wrong name"
                % (number, s.TYPE_NAMES.get(number)))
        assert len(s.TYPE_NAMES) == 14, (
            "there are fourteen packet types, not %d: %r"
            % (len(s.TYPE_NAMES), sorted(s.TYPE_NAMES)))
        for reserved in (6, 8, 10):
            assert s.REQUIRED_FLAGS[reserved] == 0b0010, (
                "PUBREL, SUBSCRIBE and UNSUBSCRIBE are the packets whose low nibble "
                "is required to be 0b0010, and the table says %r for type %d"
                % (s.REQUIRED_FLAGS.get(reserved), reserved))
        assert s.REQUIRED_FLAGS[3] is None, (
            "PUBLISH's nibble is DUP, QoS and RETAIN — there is no one value to "
            "require, and the table says %r" % (s.REQUIRED_FLAGS.get(3),))
        for bare in (1, 2, 4, 5, 7, 9, 11, 12, 13, 14):
            assert s.REQUIRED_FLAGS[bare] == 0, (
                "type %d carries no flags at all, and the table says %r"
                % (bare, s.REQUIRED_FLAGS.get(bare)))
        assert tuple(s.RESERVED_TYPES) == (0, 15), (
            "types 0 and 15 are reserved: %r" % (s.RESERVED_TYPES,))
        assert s.MAX_REMAINING_LENGTH == 268_435_455, (
            "four groups of seven bits carry 268_435_455, not %r"
            % (s.MAX_REMAINING_LENGTH,))
        assert issubclass(s.ProtocolError, ValueError), (
            "ProtocolError must be a ValueError, so a caller's `except ValueError` "
            "still catches a broken course: %r" % (s.ProtocolError.__mro__,))
        assert issubclass(s.Incomplete, ValueError), (
            "Incomplete must be a ValueError: %r" % (s.Incomplete.__mro__,))
        assert not issubclass(s.Incomplete, s.ProtocolError), (
            "Incomplete must not be a kind of ProtocolError — a short buffer is the "
            "normal state of a reader between two ticks, and the two answers lead to "
            "opposite decisions: %r" % (s.Incomplete.__mro__,))

    def _reading(s):
        for value in VARINTS:
            encoded = s.write_varint(value)
            got, after = s.read_varint(encoded, 0)
            assert got == value, (
                "%d encoded as %r and read back as %r" % (value, encoded, got))
            assert after == len(encoded), (
                "%d's %r is %d bytes and the read stopped at %d"
                % (value, encoded, len(encoded), after))
        assert s.read_varint(b"\x00") == (0, 1), (
            "a single clear group is a zero of one byte: %r" % (s.read_varint(b"\x00"),))
        assert s.read_varint(b"\x7f") == (127, 1), (
            "seven bits all set is 127, and the next byte is a new group: %r"
            % (s.read_varint(b"\x7f"),))
        assert s.read_varint(b"\x80\x01") == (128, 2), (
            "128 is a zero group continued, then a one: %r"
            % (s.read_varint(b"\x80\x01"),))
        assert s.read_varint(b"\xff\xff\xff\x7f") == (268_435_455, 4), (
            "the largest four-group integer is 268_435_455: %r"
            % (s.read_varint(b"\xff\xff\xff\x7f"),))
        assert s.read_varint(b"\x80\x00") == (0, 2), (
            "a continued zero is still a zero — nothing forbids the long form, and a "
            "reader that refuses it rejects a legal peer: %r"
            % (s.read_varint(b"\x80\x00"),))
        assert s.read_varint(b"\x05\x6b\x01", 1) == (107, 2), (
            "the bytes before the position are not part of the integer: %r"
            % (s.read_varint(b"\x05\x6b\x01", 1),))
        assert s.read_varint(b"\x05\x6b\x01", 2) == (1, 3), (
            "and a read at the last byte is a one-byte integer: %r"
            % (s.read_varint(b"\x05\x6b\x01", 2),))
        assert s.read_varint(bytearray(b"\x2a")) == (42, 1), (
            "a bytearray is a buffer like any other: %r"
            % (s.read_varint(bytearray(b"\x2a")),))

    def _incomplete(s):
        for buffer in (b"", b"\x80", b"\x80\x80", b"\x80\x80\x80"):
            refused = _refuses(s.Incomplete, "the integer in %r" % (buffer,),
                               lambda buffer=buffer: s.read_varint(buffer))
            assert refused.needed == 1, (
                "%r ends with a continued group, so one more byte could end the "
                "integer, and the refusal asked for %d"
                % (buffer, refused.needed))
            assert "1" in str(refused), (
                "the refusal says %r, which does not tell a reader how many bytes to "
                "wait for" % (str(refused),))
        assert s.read_varint(b"\x81\x01") == (129, 2), (
            "the byte that arrives is what ends the integer, and 0x81 then 0x01 is "
            "129: %r" % (s.read_varint(b"\x81\x01"),))
        empty = _refuses(s.Incomplete, "an empty buffer's header",
                         lambda: s.read_header(b""))
        assert empty.needed == 2, (
            "an empty buffer needs the type byte and at least one length byte — two "
            "— and the refusal asked for %d" % (empty.needed,))
        one = _refuses(s.Incomplete, "a one-byte buffer's header",
                       lambda: s.read_header(b"\x30"))
        assert one.needed == 1, (
            "with the type byte arrived, one more byte could end the length, and the "
            "refusal asked for %d" % (one.needed,))
        short = _refuses(s.Incomplete, "a body of five with two arrived",
                         lambda: s.read_header(b"\x30\x05ab"))
        assert short.needed == 3, (
            "the header is whole and three of the body's five bytes are still to "
            "come, and the refusal asked for %d" % (short.needed,))
        huge = _refuses(s.Incomplete, "a body of 268_435_455 with none arrived",
                        lambda: s.read_header(b"\x30\xff\xff\xff\x7f"))
        assert huge.needed == 268_435_455, (
            "the whole packet's length is the shortfall when none of the body is "
            "here, and the refusal asked for %d" % (huge.needed,))

    def _writing(s):
        assert s.write_varint(0) == b"\x00", (
            "zero is one clear group, not an empty encoding: %r" % (s.write_varint(0),))
        assert s.write_varint(127) == b"\x7f", (
            "seven bits fit one group: %r" % (s.write_varint(127),))
        assert s.write_varint(128) == b"\x80\x01", (
            "128 carries into a second group, low group first: %r"
            % (s.write_varint(128),))
        assert s.write_varint(16_383) == b"\xff\x7f", (
            "two groups carry 16_383: %r" % (s.write_varint(16_383),))
        assert s.write_varint(16_384) == b"\x80\x80\x01", (
            "16_384 is the first three-group value: %r" % (s.write_varint(16_384),))
        assert s.write_varint(268_435_455) == b"\xff\xff\xff\x7f", (
            "the maximum is four groups: %r" % (s.write_varint(268_435_455),))
        for value in VARINTS:
            encoded = s.write_varint(value)
            assert len(encoded) == GROUPS(value), (
                "%d is carried by the shortest encoding of %d groups, not %d: %r"
                % (value, GROUPS(value), len(encoded), encoded))
        _refuses(s.ProtocolError, "a negative length", lambda: s.write_varint(-1),
                 names=("-1",))
        _refuses(s.ProtocolError, "a length above the maximum",
                 lambda: s.write_varint(268_435_456),
                 names=("268435456", "268435455"))
        _refuses(s.ProtocolError, "a bool for a length", lambda: s.write_varint(True),
                 names=("bool",))
        _refuses(s.ProtocolError, "a string for a length",
                 lambda: s.write_varint("5"), names=("str",))

    def _headers(s):
        header, body = s.read_header(b"\xc0\x00")
        assert header == {"type": 12, "flags": 0, "length": 0, "size": 2}, (
            "PINGREQ is one type byte and a zero length, and the header reads as %r"
            % (header,))
        assert body == 2, (
            "PINGREQ has no body, so the payload starts where the header ends, at 2: "
            "%r" % (body,))
        assert list(header) == ["type", "flags", "length", "size"], (
            "the header's four keys are read in the order the stage declares them: %r"
            % (list(header),))
        header, body = s.read_header(b"\x3b\x04abcd")
        assert (header["type"], header["flags"]) == (3, 0b1011), (
            "the type is the high nibble and the flags the low one — PUBLISH with "
            "DUP, QoS 2 and RETAIN is 0x3b: %r" % (header,))
        assert (header["length"], header["size"], body) == (4, 2, 2), (
            "a four-byte body behind a two-byte header: %r" % (header,))
        packet = b"\x62\x84\x01" + b"x" * 132
        header, body = s.read_header(packet)
        assert (header["type"], header["flags"]) == (6, 0b0010), (
            "PUBREL's low nibble is the one the format fixes at 0b0010, and the "
            "header that carries it is a header: %r" % (header,))
        assert (header["length"], header["size"], body) == (132, 3, 3), (
            "a length of 132 is two bytes, so the header is three and the body starts "
            "at 3: %r" % (header,))
        assert header["size"] + header["length"] == len(packet), (
            "the header's size plus its length is where the packet ends, and the "
            "reader's two numbers must add up: %r" % (header,))
        late = b"\x2a\x20\x32" + b"x" * 50
        header, body = s.read_header(late, 1)
        assert (header["type"], header["flags"], header["length"], body) == (2, 0, 50, 3), (
            "at position 1 the header is the CONNACK behind the leading byte, and its "
            "body starts at 3: %r" % (header,))
        assert s.read_header(b"\x30\x80\x00")[0]["length"] == 0, (
            "a header whose length is written the long way still says zero: %r"
            % (s.read_header(b"\x30\x80\x00")[0],))
        paid = b"\xc0\x00" + b"payload"
        header, body = s.read_header(paid)
        assert paid[body:] == b"payload", (
            "the payload position is what the reader leaves alone: %r"
            % (paid[body:],))
        for kind, nibble in ((s.SUBSCRIBE, 0b0011), (s.UNSUBSCRIBE, 0b0000),
                             (s.PUBREL, 0b1010), (s.PUBACK, 0b0001), (s.PINGREQ, 0b1000)):
            _refuses(s.ProtocolError, "the flags a type %d header must carry" % (kind,),
                     lambda kind=kind, nibble=nibble: s.read_header(bytes([kind << 4 | nibble, 0])),
                     names=(str(kind),))
        assert s.read_header(b"\x82\x00")[0]["flags"] == 0b0010, (
            "the nibble a SUBSCRIBE owes is the one a header may carry: %r"
            % (s.read_header(b"\x82\x00")[0],))
        assert s.read_header(b"\x3f\x00")[0]["flags"] == 0b1111, (
            "PUBLISH's low nibble is its own payload's shape, every bit of it, so any "
            "value is a legal header: %r" % (s.read_header(b"\x3f\x00")[0],))
        for kind in (0, 15):
            _refuses(s.ProtocolError, "a reserved type",
                     lambda kind=kind: s.read_header(bytes([kind << 4, 0])),
                     names=(str(kind),))
        _refuses(s.ProtocolError, "a string buffer",
                 lambda: s.read_header("c0"), names=("str",))
        _refuses(s.ProtocolError, "a position past the buffer",
                 lambda: s.read_header(b"\xc0\x00", 9), names=("9", "2"))
        _refuses(s.ProtocolError, "a bool position",
                 lambda: s.read_header(b"\xc0\x00", True), names=("True",))
        _refuses(s.ProtocolError, "a fifth length group in a header",
                 lambda: s.read_header(b"\x30\x80\x80\x80\x80\x01"),
                 names=("four",))
        refused = _refuses(s.ProtocolError, "a fifth group",
                           lambda: s.read_varint(b"\xff\xff\xff\xff\x01"),
                           names=("four",))
        assert "xff" in str(refused), (
            "the refusal names the four bytes that arrived, and it says %r"
            % (str(refused),))

    def _read_once(s, buffer):
        try:
            header, body = s.read_header(buffer)
        except s.Incomplete as short:
            return ("incomplete", short.needed)
        return ("header", header, body)

    def _twice(s):
        for value in VARINTS:
            assert s.write_varint(value) == s.write_varint(value), (
                "%d encodes to two different byte strings: %r vs %r"
                % (value, s.write_varint(value), s.write_varint(value)))
        for buffer in (b"\xc0\x00", b"\x3b\x04abcd", b"\x30\x05ab", b""):
            one = _read_once(s, buffer)
            two = _read_once(s, buffer)
            assert one == two, (
                "%r read twice gives two answers — a reader that consumes more the "
                "second time reads the stream wrong from then on: %r vs %r"
                % (buffer, one, two))

    import stage_01 as s
    _constants(s)
    _reading(s)
    _incomplete(s)
    _writing(s)
    _headers(s)
    _twice(s)

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "mqtt-broker-from-scratch"

    TYPE_NUMBERS = {
        "CONNECT": 1, "CONNACK": 2, "PUBLISH": 3, "PUBACK": 4, "PUBREC": 5,
        "PUBREL": 6, "PUBCOMP": 7, "SUBSCRIBE": 8, "SUBACK": 9, "UNSUBSCRIBE": 10,
        "UNSUBACK": 11, "PINGREQ": 12, "PINGRESP": 13, "DISCONNECT": 14,
    }

    CODES = {
        "CONNACK_ACCEPTED": 0, "CONNACK_REFUSED_VERSION": 1,
        "CONNACK_REFUSED_IDENTIFIER": 2, "CONNACK_REFUSED_UNAVAILABLE": 3,
        "CONNACK_REFUSED_CREDENTIALS": 4, "CONNACK_REFUSED_NOT_AUTHORIZED": 5,
    }

    GOOD_CONNECT = {
        "protocol_name": "MQTT", "protocol_level": 4, "clean_start": True,
        "keep_alive": 10, "client_id": "c", "will": None, "username": None,
        "password": None,
    }

    def _enc(text):
        """A hand-built MQTT string: two bytes of length, then UTF-8."""
        payload = text.encode("utf-8")
        return bytes([len(payload) >> 8, len(payload) & 0xFF]) + payload

    def _pay(raw):
        """A hand-built MQTT payload: two bytes of length, then raw bytes."""
        return bytes([len(raw) >> 8, len(raw) & 0xFF]) + raw

    def _body(flags, keep_alive=0, client_id="c", name="MQTT", level=4,
              will=None, username=None, password=None):
        """A CONNECT body built the way its flags say it should be."""
        out = (_enc(name) + bytes([level, flags, keep_alive >> 8, keep_alive & 0xFF])
               + _enc(client_id))
        if will is not None:
            topic, payload = will
            out += _enc(topic) + _pay(payload)
        if username is not None:
            out += _enc(username)
        if password is not None:
            out += _pay(password)
        return out

    def _repo(start=None):
        for candidate_start in (os.environ.get("L3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _constants(s):
        assert s.PROTOCOL_NAME == "MQTT", (
            "a CONNECT opens with the four bytes of the protocol name, and the "
            "stage says %r" % (s.PROTOCOL_NAME,))
        assert s.PROTOCOL_LEVEL == 4, (
            "level 4 is the one this broker speaks, and the stage says %r"
            % (s.PROTOCOL_LEVEL,))
        assert s.MAX_STRING_BYTES == 65_535, (
            "a string's length field is two bytes, so 65_535 is the most it can "
            "carry, not %r" % (s.MAX_STRING_BYTES,))
        assert tuple(s.CONNECT_KEYS) == (
            "protocol_name", "protocol_level", "clean_start", "keep_alive",
            "client_id", "will", "username", "password"), (
            "the eight keys of a parsed CONNECT, in wire order: %r"
            % (s.CONNECT_KEYS,))
        assert tuple(s.WILL_KEYS) == ("topic", "payload", "qos", "retain"), (
            "a will is four keys, in this order: %r" % (s.WILL_KEYS,))
        assert tuple(s.CLIENT_TYPES) == (1, 3, 4, 5, 6, 7, 8, 10, 12, 14), (
            "the ten packet types a client may send a broker: %r"
            % (s.CLIENT_TYPES,))
        for name, number in sorted(CODES.items()):
            assert getattr(s, name) == number, (
                "%s is return code %d on the wire, not %r"
                % (name, number, getattr(s, name)))
        assert tuple(s.CONNACK_CODES) == (0, 1, 2, 3, 4, 5), (
            "the six CONNACK codes are 0 through 5, and the stage lists %r"
            % (s.CONNACK_CODES,))
        for name, number in sorted(TYPE_NUMBERS.items()):
            got = getattr(s, name)
            assert got == number, (
                "%s is packet type %d on the wire, and the stage re-exports %r"
                % (name, number, got))

    def _strings(s, w):
        assert s.read_string(b"\x00\x00") == ("", 2), (
            "a zero length is no payload and a position of two: %r"
            % (s.read_string(b"\x00\x00"),))
        assert s.read_string(b"\x00\x01a") == ("a", 3), (
            "a length of 0x0001 is one byte, big-endian first, and the read gives %r"
            % (s.read_string(b"\x00\x01a"),))
        assert s.read_string(b"\x01\x00" + b"x" * 256) == ("x" * 256, 258), (
            "0x0100 is 256 bytes, not one: a reader that takes the length "
            "little-endian slices the next field 255 bytes short: %r"
            % (s.read_string(b"\x01\x00" + b"x" * 256),))
        big = "a" * s.MAX_STRING_BYTES
        encoded = s.write_string(big)
        assert s.read_string(encoded) == (big, 2 + s.MAX_STRING_BYTES), (
            "the largest string a two-byte length carries must read back whole, and "
            "a reader at the boundary returned %d bytes"
            % (len(s.read_string(encoded)[0]),))
        refused = _refuses(w.Incomplete, "a string one byte short of its payload",
                           lambda: s.read_string(encoded[:-1]))
        assert refused.needed == 1, (
            "one byte of the payload is still to come, and the refusal asked for %d"
            % (refused.needed,))
        refused = _refuses(w.Incomplete, "a five-byte string with three arrived",
                           lambda: s.read_string(b"\x00\x05abc"))
        assert refused.needed == 2, (
            "three of the payload's five bytes have arrived, so two are still to "
            "come, and the refusal asked for %d" % (refused.needed,))
        refused = _refuses(w.Incomplete, "a string with no length byte at all",
                           lambda: s.read_string(b""))
        assert refused.needed == 2, (
            "a string needs two bytes of length, and the refusal asked for %d"
            % (refused.needed,))
        refused = _refuses(w.Incomplete, "a string with one length byte",
                           lambda: s.read_string(b"\x00"))
        assert refused.needed == 1, (
            "one more length byte could size the string, and the refusal asked for %d"
            % (refused.needed,))
        assert s.read_string(b"\xff\x00\x01a", 1) == ("a", 4), (
            "the bytes before the position are not part of the string: %r"
            % (s.read_string(b"\xff\x00\x01a", 1),))
        assert s.read_string(b"\xff\xff\x00\x02hi", 2) == ("hi", 6), (
            "a string read at a non-zero position ends after its own payload: %r"
            % (s.read_string(b"\xff\xff\x00\x02hi", 2),))
        assert s.read_string(b"\x00\x05caf\xc3\xa9") == ("café", 7), (
            "the length counts bytes: \"café\" is five bytes and four characters, "
            "and the read gives %r" % (s.read_string(b"\x00\x05caf\xc3\xa9"),))
        _refuses(w.ProtocolError, "a payload that is not UTF-8",
                 lambda: s.read_string(b"\x00\x02\xff\xfe"), names=("xff",))
        _refuses(w.ProtocolError, "a string buffer",
                 lambda: s.read_string("MQTT"), names=("str",))
        _refuses(w.ProtocolError, "a bool for a string position",
                 lambda: s.read_string(b"\x00\x00", True), names=("True",))
        _refuses(w.ProtocolError, "a string position past the buffer",
                 lambda: s.read_string(b"\x00\x00", 9), names=("9", "2"))

    def _payloads(s, w):
        assert s.read_payload(b"\x00\x00") == (b"", 2), (
            "a zero-length payload is no bytes and a position of two: %r"
            % (s.read_payload(b"\x00\x00"),))
        assert s.read_payload(b"\x00\x01a") == (b"a", 3), (
            "a payload's length is big-endian too: %r"
            % (s.read_payload(b"\x00\x01a"),))
        raw = b"\xff" * s.MAX_STRING_BYTES
        encoded = _pay(raw)
        assert s.read_payload(encoded) == (raw, 2 + s.MAX_STRING_BYTES), (
            "a payload may be the full 65_535 bytes and read back untouched: %r"
            % (s.read_payload(encoded),))
        refused = _refuses(w.Incomplete, "a payload one byte short of its length",
                           lambda: s.read_payload(encoded[:-1]))
        assert refused.needed == 1, (
            "one byte of the payload is still to come, and the refusal asked for %d"
            % (refused.needed,))
        refused = _refuses(w.Incomplete, "a five-byte payload with three arrived",
                           lambda: s.read_payload(b"\x00\x05abc"))
        assert refused.needed == 2, (
            "two of the payload's bytes are still to come, and the refusal asked "
            "for %d" % (refused.needed,))
        refused = _refuses(w.Incomplete, "a payload with no length byte at all",
                           lambda: s.read_payload(b""))
        assert refused.needed == 2, (
            "a payload needs two bytes of length, and the refusal asked for %d"
            % (refused.needed,))
        refused = _refuses(w.Incomplete, "a payload with one length byte",
                           lambda: s.read_payload(b"\x00"))
        assert refused.needed == 1, (
            "one more length byte could size the payload, and the refusal asked "
            "for %d" % (refused.needed,))
        assert s.read_payload(b"\xff\xff\x00\x02hi", 2) == (b"hi", 6), (
            "a payload read at a non-zero position leaves the bytes before it "
            "alone: %r" % (s.read_payload(b"\xff\xff\x00\x02hi", 2),))
        assert s.read_payload(b"\x00\x03\xff\xfe\xfd") == (b"\xff\xfe\xfd", 5), (
            "a payload is bytes and never decoded — these bytes are not UTF-8 and "
            "are perfectly legal: %r" % (s.read_payload(b"\x00\x03\xff\xfe\xfd"),))
        _refuses(w.ProtocolError, "a payload buffer",
                 lambda: s.read_payload("MQTT"), names=("str",))
        _refuses(w.ProtocolError, "a bool for a payload position",
                 lambda: s.read_payload(b"\x00\x00", True), names=("True",))

    def _writing(s, w):
        assert s.write_string("") == b"\x00\x00", (
            "an empty string is a zero length and nothing after it: %r"
            % (s.write_string(""),))
        assert s.write_string("MQTT") == b"\x00\x04MQTT", (
            "the four bytes of MQTT behind a length of four: %r"
            % (s.write_string("MQTT"),))
        assert s.write_string("café") == b"\x00\x05caf\xc3\xa9", (
            "the length is the UTF-8 byte count, five, not the character count, "
            "four: %r" % (s.write_string("café"),))
        assert s.write_string("a" * s.MAX_STRING_BYTES) == _enc(
            "a" * s.MAX_STRING_BYTES), (
            "a string exactly at the maximum is legal and writes its length first: "
            "%r" % (s.write_string("a" * s.MAX_STRING_BYTES)[:4],))
        for text in ("", "a", "MQTT", "café", "a" * 1000, "a" * s.MAX_STRING_BYTES):
            written = s.write_string(text)
            assert s.read_string(written) == (text, len(written)), (
                "%r written and read back gives %r — the length does not describe "
                "its own payload" % (text[:8], s.read_string(written)))
        _refuses(w.ProtocolError, "a string that is not a str",
                 lambda: s.write_string(5), names=("int",))
        _refuses(w.ProtocolError, "a bytes value written as a string",
                 lambda: s.write_string(b"MQTT"), names=("bytes",))
        _refuses(w.ProtocolError, "one byte above the maximum string",
                 lambda: s.write_string("a" * (s.MAX_STRING_BYTES + 1)),
                 names=("65536", "65535"))

    def _connects(s, w):
        body = _body(0x00, keep_alive=0x1234, client_id="cli")
        connect, after = s.read_connect(body)
        assert after == len(body), (
            "a whole body is read to its end, and the read stopped at %d of %d"
            % (after, len(body)))
        assert list(connect) == list(s.CONNECT_KEYS), (
            "a parsed CONNECT carries the eight keys in wire order: %r"
            % (list(connect),))
        assert (connect["protocol_name"], connect["protocol_level"]) == ("MQTT", 4), (
            "the protocol name and level are returned, not judged: %r"
            % (connect["protocol_name"],))
        assert connect["keep_alive"] == 0x1234, (
            "keep_alive is two bytes big-endian, and 0x12 0x34 is 4660, not %r"
            % (connect["keep_alive"],))
        assert connect["clean_start"] is False, (
            "flags 0 ask for no clean start, and the reader says %r"
            % (connect["clean_start"],))
        assert connect["client_id"] == "cli", (
            "the client identifier is the string after the flags: %r"
            % (connect["client_id"],))
        assert connect["will"] is None, (
            "flags 0 promise no will, and the reader invented %r"
            % (connect["will"],))
        assert connect["username"] is None and connect["password"] is None, (
            "flags 0 promise no username and no password: %r / %r"
            % (connect["username"], connect["password"]))
        connect, _ = s.read_connect(_body(0x02, client_id="cli"))
        assert connect["clean_start"] is True, (
            "bit 1 is the clean start, and flags 0x02 says %r"
            % (connect["clean_start"],))
        will_body = _body(0x2C, client_id="cli", will=("will/t", b"\xff\x00go"))
        connect, _ = s.read_connect(will_body)
        will = connect["will"]
        assert list(will) == list(s.WILL_KEYS), (
            "a will carries the four keys of WILL_KEYS in order: %r" % (list(will),))
        assert will == {"topic": "will/t", "payload": b"\xff\x00go", "qos": 1,
                        "retain": True}, (
            "bits 2, 4-3 and 5 are the will flag, its QoS and its retain, and the "
            "will reads as %r" % (will,))
        connect, _ = s.read_connect(
            _body(0x24, client_id="cli", will=("t", b"m")))
        assert connect["will"] == {"topic": "t", "payload": b"m", "qos": 0,
                                   "retain": True}, (
            "a will QoS of 0 with retain set: %r" % (connect["will"],))
        connect, _ = s.read_connect(
            _body(0x14, client_id="cli", will=("t", b"m")))
        assert connect["will"]["qos"] == 2 and connect["will"]["retain"] is False, (
            "bits 4-3 carry a will QoS of 2: %r" % (connect["will"],))
        connect, _ = s.read_connect(_body(0x80, client_id="cli", username="user"))
        assert connect["username"] == "user" and connect["password"] is None, (
            "bit 7 is the username and bit 6 the password: %r / %r"
            % (connect["username"], connect["password"]))
        connect, _ = s.read_connect(
            _body(0xC0, client_id="cli", username="user", password=b"\x00\xff"))
        assert connect["username"] == "user", (
            "the username is a string: %r" % (connect["username"],))
        assert connect["password"] == b"\x00\xff", (
            "the password is a length and that many raw bytes — a password that is "
            "not UTF-8 is legal, and the reader gave %r" % (connect["password"],))
        whole = _body(0x02, keep_alive=10, client_id="cli")
        stops = {0: 2, 1: 1, 5: 1, 6: 1, 7: 1, 8: 2, 9: 1, 10: 2, 11: 1,
                 12: 3, 13: 2, 14: 1}
        for cut, need in sorted(stops.items()):
            refused = _refuses(
                w.Incomplete, "a body that stops %d bytes in" % (cut,),
                lambda cut=cut: s.read_connect(whole[:cut]))
            assert refused.needed == need, (
                "the body stops %d bytes in, so the next field needs exactly %d "
                "bytes, and the refusal asked for %d"
                % (cut, need, refused.needed))
        whole = _body(0xCC, keep_alive=10, client_id="cli", will=("w", b"p"),
                      username="u", password=b"s")
        stops = {15: 2, 16: 1, 17: 1, 18: 2, 19: 1, 20: 1, 21: 2, 22: 1, 23: 1,
                 24: 2, 25: 1, 26: 1}
        for cut, need in sorted(stops.items()):
            refused = _refuses(
                w.Incomplete, "a will body that stops %d bytes in" % (cut,),
                lambda cut=cut: s.read_connect(whole[:cut]))
            assert refused.needed == need, (
                "the will body stops %d bytes in, so the next field needs exactly "
                "%d bytes, and the refusal asked for %d"
                % (cut, need, refused.needed))
        _refuses(w.ProtocolError, "a reserved flag bit",
                 lambda: s.read_connect(_body(0x01, client_id="cli")),
                 names=("0x01",))
        _refuses(w.ProtocolError, "a will QoS of 3",
                 lambda: s.read_connect(_body(0x1C, client_id="cli")),
                 names=("0x1c",))
        _refuses(w.ProtocolError, "a will QoS with no will flag",
                 lambda: s.read_connect(_body(0x08, client_id="cli")),
                 names=("0x08",))
        _refuses(w.ProtocolError, "a will retain with no will flag",
                 lambda: s.read_connect(_body(0x20, client_id="cli")),
                 names=("0x20",))
        _refuses(w.ProtocolError, "a password with no username",
                 lambda: s.read_connect(_body(0x40, client_id="cli")),
                 names=("0x40",))
        _refuses(w.ProtocolError, "a trailing byte after the fields",
                 lambda: s.read_connect(_body(0x00, client_id="cli") + b"\x00"),
                 names=("trailing",))
        _refuses(w.ProtocolError, "a CONNECT buffer",
                 lambda: s.read_connect("MQTT"), names=("str",))

    def _connack_code(s, w):
        assert s.connack_code(dict(GOOD_CONNECT)) == s.CONNACK_ACCEPTED, (
            "a name and level the broker speaks is accepted, and it answered %r"
            % (s.connack_code(dict(GOOD_CONNECT)),))
        bad = dict(GOOD_CONNECT, protocol_name="MQISDP")
        assert s.connack_code(bad) == s.CONNACK_REFUSED_VERSION, (
            "a protocol name the broker does not speak is code 1, not %r"
            % (s.connack_code(bad),))
        bad = dict(GOOD_CONNECT, protocol_level=5)
        assert s.connack_code(bad) == s.CONNACK_REFUSED_VERSION, (
            "a level the broker does not speak is code 1, and it answered %r"
            % (s.connack_code(bad),))
        empty = dict(GOOD_CONNECT, client_id="", clean_start=True)
        assert s.connack_code(empty) == s.CONNACK_ACCEPTED, (
            "an empty identifier is legal when the client also asks for a clean "
            "start, and it answered %r" % (s.connack_code(empty),))
        empty = dict(GOOD_CONNECT, client_id="", clean_start=False)
        assert s.connack_code(empty) == s.CONNACK_REFUSED_IDENTIFIER, (
            "an empty identifier without a clean start is code 2, not %r"
            % (s.connack_code(empty),))
        assert s.connack_code(dict(GOOD_CONNECT)) in s.CONNACK_CODES, (
            "a verdict is one of the six codes and never an exception: %r"
            % (s.connack_code(dict(GOOD_CONNECT)),))
        _refuses(w.ProtocolError, "a CONNECT that is not a dict",
                 lambda: s.connack_code(["MQTT"]), names=("list",))
        missing = dict(GOOD_CONNECT)
        del missing["keep_alive"]
        _refuses(w.ProtocolError, "a CONNECT with a key missing",
                 lambda: s.connack_code(missing), names=("keep_alive",))

    def _connack_write(s, w):
        assert s.write_connack(False, 0) == b"\x00\x00", (
            "no session and an accept is two clear bytes: %r"
            % (s.write_connack(False, 0),))
        assert s.write_connack(True, 0) == b"\x01\x00", (
            "a resumed session sets bit 0 of the first byte, so an accept with a "
            "session is b\"\\x01\\x00\", not %r" % (s.write_connack(True, 0),))
        assert s.write_connack(0, 0) == b"\x00\x00", (
            "0 is a session flag like false: %r" % (s.write_connack(0, 0),))
        assert s.write_connack(1, 0) == b"\x01\x00", (
            "1 is a session flag like true: %r" % (s.write_connack(1, 0),))
        for code in s.CONNACK_CODES[1:]:
            assert s.write_connack(False, code) == bytes([0, code]), (
                "a refusal carries no session-present bit, so code %d writes "
                "b\"\\x00%02x\", not %r" % (code, code, s.write_connack(False, code)))
            assert s.write_connack(0, code) == bytes([0, code]), (
                "a refusal written from a 0 flag still writes no bit for code %d: %r"
                % (code, s.write_connack(0, code)))
        assert isinstance(s.write_connack(False, 0), (bytes, bytearray)), (
            "a CONNACK is two bytes on the wire, not %r"
            % (type(s.write_connack(False, 0)).__name__,))
        assert len(s.write_connack(True, 0)) == 2, (
            "a CONNACK is exactly two bytes: %r" % (s.write_connack(True, 0),))
        _refuses(w.ProtocolError, "a code outside the six",
                 lambda: s.write_connack(False, 6), names=("6",))
        _refuses(w.ProtocolError, "a bool for a CONNACK code",
                 lambda: s.write_connack(False, True), names=("True",))
        _refuses(w.ProtocolError, "a session flag on a refusal",
                 lambda: s.write_connack(True, 1), names=("1",))
        _refuses(w.ProtocolError, "a session flag of 1 on a refusal",
                 lambda: s.write_connack(1, s.CONNACK_REFUSED_IDENTIFIER),
                 names=("2",))
        _refuses(w.ProtocolError, "a session flag that is not a bool or 0/1",
                 lambda: s.write_connack(2, 0), names=("2",))
        _refuses(w.ProtocolError, "a string for a session flag",
                 lambda: s.write_connack("yes", 0), names=("yes",))

    def _fixture(s, w):
        """Every reader on one buffer each; compare two runs of this."""
        reads = [
            (s.read_string, b"", 0),
            (s.read_string, b"\x00", 0),
            (s.read_string, b"\x00\x00", 0),
            (s.read_string, b"\x00\x05abc", 0),
            (s.read_string, b"\x00\x02\xff\xfe", 0),
            (s.read_string, b"\x00\x04MQTT\x04\x02", 0),
            (s.read_string, b"\x00\x05caf\xc3\xa9", 0),
            (s.read_string, b"\xff\x00\x01a", 1),
            (s.read_payload, b"", 0),
            (s.read_payload, b"\x00\x00", 0),
            (s.read_payload, b"\x00\x05abc", 0),
            (s.read_payload, b"\x00\x03\xff\xfe\xfd", 0),
            (s.read_payload, b"\xff\xff\x00\x02hi", 2),
            (s.read_connect, _body(0x00, keep_alive=7, client_id="cli"), 0),
            (s.read_connect, _body(0x2C, client_id="cli", will=("w/t", b"\xff")), 0),
            (s.read_connect, _body(0xC0, client_id="cli", username="u",
                                   password=b"\x00"), 0),
            (s.read_connect, _body(0x02, client_id="cli")[:9], 0),
        ]
        out = []
        for reader, data, pos in reads:
            try:
                got = reader(data, pos)
            except w.Incomplete as short:
                got = ("incomplete", short.needed)
            except w.ProtocolError as refused:
                got = ("refused", str(refused))
            out.append(got)
        out.append(s.read_string(s.write_string("café")))
        out.append(s.write_string(""))
        out.append(s.write_string("café"))
        out.append(s.read_payload(_pay(b"\xff\xfe")))
        out.append(s.write_connack(True, 0))
        out.append(s.write_connack(False, 3))
        out.append(s.connack_code(dict(GOOD_CONNECT)))
        return tuple(out)

    def _twice(s, w):
        one = _fixture(s, w)
        two = _fixture(s, w)
        assert one == two, (
            "one fixture read twice gave two answers — a reader that consumes more "
            "the second time reads the stream wrong from then on: %r vs %r"
            % (one, two))

    import stage_01 as w
    import stage_02 as s
    _constants(s)
    _strings(s, w)
    _payloads(s, w)
    _writing(s, w)
    _connects(s, w)
    _connack_code(s, w)
    _connack_write(s, w)
    _twice(s, w)

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "mqtt-broker-from-scratch"

    TOO_LONG = "a" * 65_536

    AT_LIMIT = "a" * 65_535

    def _repo(start=None):
        for candidate_start in (os.environ.get("L3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _constants(s):
        assert s.MAX_TOPIC_BYTES == 65_535, (
            "a two-byte length carries 65_535 bytes, and the topic name's ceiling is "
            "the same number, not %r" % (s.MAX_TOPIC_BYTES,))
        assert tuple(s.WILDCARDS) == ("+", "#"), (
            "the two wildcards, in the order the stage declares them, are ('+', '#'): "
            "%r" % (s.WILDCARDS,))
        assert issubclass(s.TopicError, ValueError), (
            "TopicError must be a ValueError, so a caller's `except ValueError` still "
            "catches a broken course: %r" % (s.TopicError.__mro__,))
        for level, want in (("+", True), ("#", True), ("+b", False), ("b+", False),
                            ("##", False), ("#+", False), ("a", False), ("", False),
                            ("/", False)):
            got = s.is_wildcard(level)
            assert got is want, (
                "is_wildcard(%r) is %r — only a whole level can be a wildcard, and "
                "that level is '+' or '#'" % (level, got))

    def _levels(s):
        for name, want in (("a", ("a",)), ("a/b", ("a", "b")), ("a/b/c", ("a", "b", "c")),
                           ("a//b", ("a", "", "b")), ("a/", ("a", "")), ("/a", ("", "a")),
                           ("/", ("", "")), ("", ("",)), ("a//b//", ("a", "", "b", "", ""))):
            got = s.levels(name)
            assert got == want, (
                "%r splits into %r, and the split says %r — an empty level is a level"
                % (name, want, got))
            assert isinstance(got, tuple), (
                "the levels of %r come back as a tuple, not a %s"
                % (name, type(got).__name__))

    def _topics(s):
        for name in ("a", "a/b", "a//b", "a/", "/", "a/+b", "a/b+", "#x", AT_LIMIT):
            assert s.validate_topic(name) == name, (
                "validate_topic(%r) answers the name itself, and it answered %r"
                % (name, s.validate_topic(name)))
        for name, want in (("+", ("'+'",)), ("#", ("'#'",)), ("a/#", ("'#'",)),
                           ("a/+/b", ("'+'",))):
            _refuses(s.TopicError, "the topic %r" % (name,),
                     lambda name=name: s.validate_topic(name), names=want)
        _refuses(s.TopicError, "an empty topic", lambda: s.validate_topic(""),
                 names=("empty",))
        _refuses(s.TopicError, "a topic one byte over the ceiling",
                 lambda: s.validate_topic(TOO_LONG), names=("65536", "65535"))
        _refuses(s.TopicError, "a topic that is not a str",
                 lambda: s.validate_topic(5), names=("int",))
        _refuses(s.TopicError, "a topic of bytes rather than text",
                 lambda: s.validate_topic(b"a/b"), names=("bytes",))
        two_byte = "\u00e9"
        assert s.validate_topic(two_byte * 32_767) == two_byte * 32_767, (
            "the ceiling counts bytes: 32_767 two-byte characters are 65_534 bytes, "
            "one below it, and the name must come back unchanged")
        _refuses(s.TopicError, "a topic of 32_768 two-byte characters",
                 lambda: s.validate_topic(two_byte * 32_768), names=("65536", "65535"))

    def _filters(s):
        for name in ("a", "a/b", "#", "+", "a/#", "a/+", "+/+", "a/+/b", "a/", "/",
                     "a//b", "a/b/", AT_LIMIT):
            assert s.validate_filter(name) == name, (
                "validate_filter(%r) answers the filter itself, and it answered %r"
                % (name, s.validate_filter(name)))
        for name, want in (("a/+b", ("'+b'",)), ("a/b+", ("'b+'",)),
                           ("a/#b", ("'#b'",)), ("+b/c", ("'+b'",)),
                           ("#b", ("'#b'",)), ("##/a", ("'##'",))):
            _refuses(s.TopicError, "the filter %r" % (name,),
                     lambda name=name: s.validate_filter(name), names=want)
        for name in ("#/a", "a/#/b", "a/+/#/+", "#/+/a"):
            _refuses(s.TopicError, "the filter %r" % (name,),
                     lambda name=name: s.validate_filter(name),
                     names=("last", "#"))
        _refuses(s.TopicError, "an empty filter", lambda: s.validate_filter(""),
                 names=("empty",))
        _refuses(s.TopicError, "a filter one byte over the ceiling",
                 lambda: s.validate_filter(TOO_LONG), names=("65536", "65535"))
        _refuses(s.TopicError, "a filter that is not a str",
                 lambda: s.validate_filter(None), names=("NoneType",))

    def _holding(s):
        trie = s.Trie()
        assert trie.filters() == (), (
            "a fresh trie holds no filter, and it holds %r" % (trie.filters(),))
        assert trie.subscribers("a") == (), (
            "nobody is on a filter a trie does not hold, and it says %r"
            % (trie.subscribers("a"),))
        assert trie.match("a") == [], (
            "a topic nobody asked for reaches nobody, and it reached %r"
            % (trie.match("a"),))
        assert isinstance(trie.filters(), tuple), (
            "the filters held come back as a tuple: %r" % (trie.filters(),))
        assert isinstance(trie.subscribers("a"), tuple), (
            "the clients on a filter come back as a tuple: %r" % (trie.subscribers("a"),))
        assert trie.subscribe("a/b", "bob", 1) == "a/b", (
            "subscribe answers the filter it was given: %r" % (trie.subscribe("a/b", "bob", 1),))
        assert trie.filters() == ("a/b",), (
            "the one filter held is ('a/b',), and the trie says %r" % (trie.filters(),))
        assert trie.subscribers("a/b") == (("bob", 1),), (
            "bob is on a/b at QoS 1, and the trie says %r" % (trie.subscribers("a/b"),))
        trie.subscribe("a/b", "ann", 0)
        assert trie.filters() == ("a/b",), (
            "a second client on one filter is still one filter: %r" % (trie.filters(),))
        assert trie.subscribers("a/b") == (("bob", 1), ("ann", 0)), (
            "the clients come back in the order they joined: %r"
            % (trie.subscribers("a/b"),))
        trie.subscribe("a/b", "bob", 2)
        assert trie.subscribers("a/b") == (("bob", 2), ("ann", 0)), (
            "a client re-subscribed moves to its new QoS and keeps its place: %r"
            % (trie.subscribers("a/b"),))
        assert trie.match("a/b") == [("bob", 2), ("ann", 0)], (
            "match answers in the order the clients joined, at their QoS: %r"
            % (trie.match("a/b"),))
        _refuses(s.TopicError, "a filter the trie may not hold",
                 lambda: trie.subscribe("a/#/b", "zed", 0), names=("#", "last"))
        assert trie.filters() == ("a/b",), (
            "a refused subscribe holds nothing at all: %r" % (trie.filters(),))
        _refuses(s.TopicError, "an empty filter",
                 lambda: trie.subscribe("", "zed", 0), names=("empty",))
        assert trie.filters() == ("a/b",), (
            "and a second refusal holds nothing either: %r" % (trie.filters(),))

    def _leaving(s):
        trie = s.Trie()
        trie.subscribe("a/b", "bob", 0)
        trie.subscribe("c", "bob", 1)
        assert trie.unsubscribe("a/b", "bob") is True, (
            "bob was on a/b, so unsubscribe answers True: %r"
            % (trie.unsubscribe("a/b", "bob"),))
        assert trie.unsubscribe("a/b", "bob") is False, (
            "bob has already left a/b, so the second unsubscribe answers False: %r"
            % (trie.unsubscribe("a/b", "bob"),))
        assert trie.unsubscribe("nope", "bob") is False, (
            "a filter nobody was ever on answers False, not an error: %r"
            % (trie.unsubscribe("nope", "bob"),))
        assert trie.unsubscribe("c", "ann") is False, (
            "a client who was never on a held filter answers False: %r"
            % (trie.unsubscribe("c", "ann"),))
        assert trie.filters() == ("c",), (
            "a filter nobody is left on is not held any more: %r" % (trie.filters(),))
        assert trie.subscribers("a/b") == (), (
            "and nobody is on it: %r" % (trie.subscribers("a/b"),))
        assert trie.match("a/b") == [], (
            "so a topic it would have matched reaches nobody: %r" % (trie.match("a/b"),))
        assert trie.match("c") == [("bob", 1)], (
            "while the filter bob stayed on still reaches him: %r" % (trie.match("c"),))
        trie.subscribe("a/b", "zed", 1)
        assert trie.filters() == ("c", "a/b"), (
            "a filter that was dropped and subscribed again is inserted at the end: %r"
            % (trie.filters(),))
        assert trie.match("a/b") == [("zed", 1)], (
            "and it reaches the client who just joined it: %r" % (trie.match("a/b"),))

    def _matching(s):
        trie = s.Trie()
        trie.subscribe("a/b", "bob", 1)
        assert trie.match("a/b") == [("bob", 1)], (
            "the plain case: %r" % (trie.match("a/b"),))
        assert trie.match("a/bc") == [], (
            "a/b must not match a/bc — the filter is two levels and the topic is two "
            "different ones: %r" % (trie.match("a/bc"),))
        assert trie.match("a") == [], (
            "nor may it match the parent level: %r" % (trie.match("a"),))
        assert trie.match("a/b/c") == [], (
            "nor a topic below it: %r" % (trie.match("a/b/c"),))
        trie.subscribe("a/bc", "eve", 0)
        assert trie.match("a/b") == [("bob", 1)], (
            "a/bc is a different filter and does not reach bob's topic: %r"
            % (trie.match("a/b"),))
        assert trie.match("a/bc") == [("eve", 0)], (
            "and a/b does not reach eve's: %r" % (trie.match("a/bc"),))

        hashed = s.Trie()
        hashed.subscribe("a/#", "ann", 0)
        for topic in ("a", "a/", "a/b", "a/b/c", "a//b"):
            assert hashed.match(topic) == [("ann", 0)], (
                "a/# matches %r — '#' covers its own level and everything under it: %r"
                % (topic, hashed.match(topic)))
        for topic in ("ab", "b", "", "/a"):
            assert hashed.match(topic) == [], (
                "a/# does not match %r: %r" % (topic, hashed.match(topic)))

        plus = s.Trie()
        plus.subscribe("sport/+", "sid", 2)
        assert plus.match("sport/") == [("sid", 2)], (
            "a/+ matches the empty level of 'a/': %r" % (plus.match("sport/"),))
        assert plus.match("sport/tennis") == [("sid", 2)], (
            "and one level with text in it: %r" % (plus.match("sport/tennis"),))
        assert plus.match("sport") == [], (
            "but + is exactly one level, and 'sport' has no level to spare: %r"
            % (plus.match("sport"),))
        assert plus.match("sport/tennis/1") == [], (
            "and it is exactly one, not any number: %r" % (plus.match("sport/tennis/1"),))
        solo = s.Trie()
        solo.subscribe("+", "one", 0)
        assert solo.match("a") == [("one", 0)] and solo.match("") == [("one", 0)], (
            "'+' matches one level, empty or not: %r / %r"
            % (solo.match("a"), solo.match("")))
        assert solo.match("a/b") == [], (
            "and never two levels: %r" % (solo.match("a/b"),))
        empty = s.Trie()
        empty.subscribe("a/+", "eve", 1)
        assert empty.match("a/") == [("eve", 1)], (
            "the empty trailing level is a level, so a/+ matches a/: %r"
            % (empty.match("a/"),))
        assert empty.match("a") == [], (
            "while a has no second level at all: %r" % (empty.match("a"),))

    def _dollar(s):
        trie = s.Trie()
        trie.subscribe("+/+", "any", 0)
        trie.subscribe("#", "all", 0)
        trie.subscribe("$SYS/#", "sys", 2)
        trie.subscribe("a/+", "one", 1)
        assert trie.match("$SYS/x") == [("sys", 2)], (
            "a filter whose first level is a wildcard does not reach a topic whose "
            "first level begins with $, and the literal $SYS/# does: %r"
            % (trie.match("$SYS/x"),))
        assert trie.match("$SYS") == [("sys", 2)], (
            "and $SYS itself is the level $SYS/# belongs to: %r" % (trie.match("$SYS"),))
        assert trie.match("$") == [], (
            "a bare $ is a first level beginning with $, and no wildcard filter "
            "reaches it: %r" % (trie.match("$"),))
        assert trie.match("a/b") == [("any", 0), ("all", 0), ("one", 1)], (
            "an ordinary topic still reaches every wildcard filter, in insertion "
            "order: %r" % (trie.match("a/b"),))
        assert trie.match("a/$x") == [("any", 0), ("all", 0), ("one", 1)], (
            "the $ rule is about the first level alone, so a/$x is matched: %r"
            % (trie.match("a/$x"),))
        lonely = s.Trie()
        lonely.subscribe("a/b", "bob", 0)
        assert lonely.match("$a/b") == [], (
            "a literal first level does not match the $ topic either: %r"
            % (lonely.match("$a/b"),))
        assert lonely.match("a/b") == [("bob", 0)], (
            "while the same filter matches its own topic: %r" % (lonely.match("a/b"),))

    def _once_and_highest(s):
        trie = s.Trie()
        trie.subscribe("z/b", "bob", 1)
        trie.subscribe("#", "ann", 0)
        trie.subscribe("#", "bob", 2)
        assert trie.filters() == ("z/b", "#"), (
            "the filters are held in the order they were inserted: %r" % (trie.filters(),))
        assert isinstance(trie.match("z/b"), list), (
            "match answers a list: %r" % (trie.match("z/b"),))
        assert trie.match("z/b") == [("bob", 2), ("ann", 0)], (
            "bob reached this topic through two filters and is answered once, at his "
            "highest QoS, in the order the filters were inserted — not sorted by "
            "filter text: %r" % (trie.match("z/b"),))
        assert trie.match("z/c") == [("ann", 0), ("bob", 2)], (
            "with only the '#' filters matching, the order is ann then bob, as each "
            "of them joined: %r" % (trie.match("z/c"),))
        low = s.Trie()
        low.subscribe("#", "bob", 2)
        low.subscribe("a/b", "bob", 0)
        assert low.match("a/b") == [("bob", 2)], (
            "the highest QoS wins whichever filter it came from: %r"
            % (low.match("a/b"),))
        assert low.filters() == ("#", "a/b"), (
            "and the case where the filter text would sort the other way is held the "
            "way it was inserted: %r" % (low.filters(),))

    def _twice(s):
        def record():
            trie = s.Trie()
            for name, who, qos in (("a/#", "ann", 0), ("a/b", "bob", 1),
                                   ("#", "cid", 2), ("+/x", "dee", 0),
                                   ("a/b", "ann", 2)):
                trie.subscribe(name, who, qos)
            left = trie.unsubscribe("a/b", "bob")
            return (trie.filters(), trie.subscribers("a/#"), trie.subscribers("a/b"),
                    trie.match("a/b"), trie.match("a"), trie.match("$SYS/x"),
                    trie.match("q/x"), left,
                    s.levels("a//b"), s.levels("/"), s.validate_topic("a/+b"),
                    s.validate_filter("a/+/#"), s.is_wildcard("#"))

        one, two = record(), record()
        assert one == two, (
            "the same fixture built twice gives two answers — a matcher whose state "
            "leaks between runs answers differently the second time: %r vs %r"
            % (one, two))

    import stage_03 as s
    _constants(s)
    _levels(s)
    _topics(s)
    _filters(s)
    _holding(s)
    _leaving(s)
    _matching(s)
    _dollar(s)
    _once_and_highest(s)
    _twice(s)

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "mqtt-broker-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _string(text):
        """One MQTT string on the wire: two bytes of length, then the UTF-8 bytes."""
        payload = text.encode("utf-8")
        return bytes([len(payload) >> 8, len(payload) & 0xFF]) + payload

    def _subscribe_body(packet_id, topics, trailing=b""):
        """A SUBSCRIBE body: the id, then each filter and its requested QoS byte."""
        body = bytearray([packet_id >> 8, packet_id & 0xFF])
        for filter_, qos in topics:
            body += _string(filter_)
            body.append(qos)
        body += trailing
        return bytes(body)

    def _unsubscribe_body(packet_id, filters, trailing=b""):
        """An UNSUBSCRIBE body: the id, then each filter with no QoS byte."""
        body = bytearray([packet_id >> 8, packet_id & 0xFF])
        for filter_ in filters:
            body += _string(filter_)
        body += trailing
        return bytes(body)

    def _constants(s):
        assert s.SUBSCRIBE_FLAGS == 0b0010, (
            "a SUBSCRIBE's low nibble is 0b0010 on the wire, not %r"
            % (s.SUBSCRIBE_FLAGS,))
        assert s.MAX_QOS == 2, (
            "this broker speaks QoS up to 2, not %r" % (s.MAX_QOS,))
        assert s.SUBACK_FAILURE == 0x80, (
            "the SUBACK failure code is 0x80, not %r" % (s.SUBACK_FAILURE,))
        assert s.SUBSCRIBE_KEYS == ("packet_id", "topics"), (
            "a parsed SUBSCRIBE carries packet_id then topics, and the keys are %r"
            % (s.SUBSCRIBE_KEYS,))

    def _subscribe(s, s1):
        body = _subscribe_body(0x1234, (("sport/tennis", 1), ("a/#", 2)))
        subscribe, after = s.read_subscribe(body)
        assert after == len(body), (
            "the read stopped at %d of the body's %d bytes" % (after, len(body)))
        assert list(subscribe) == ["packet_id", "topics"], (
            "a parsed SUBSCRIBE carries the two keys of SUBSCRIBE_KEYS in order, and "
            "it read as %r" % (list(subscribe),))
        assert subscribe["packet_id"] == 0x1234, (
            "the packet id 0x1234 read back as %r" % (subscribe["packet_id"],))
        assert subscribe["topics"] == (("sport/tennis", 1), ("a/#", 2)), (
            "the two filters in the order they were asked for read back as %r"
            % (subscribe["topics"],))
        assert isinstance(subscribe["topics"], tuple), (
            "the topics are a tuple of pairs, not %r" % (type(subscribe["topics"]),))

        late = b"\xff" + body
        subscribe, after = s.read_subscribe(late, 1)
        assert subscribe["packet_id"] == 0x1234 and after == 1 + len(body), (
            "a read at position 1 leaves the leading byte alone and stops at the "
            "body's end: %r, %r" % (subscribe, after))

        _refuses(s1.ProtocolError, "a SUBSCRIBE packet id of 0",
                 lambda: s.read_subscribe(_subscribe_body(0, (("a", 0),))),
                 names=("packet id",))
        refused = _refuses(s1.ProtocolError, "a requested QoS of 3",
                           lambda: s.read_subscribe(_subscribe_body(7, (("a", 3),))),
                           names=("3",))
        assert "3" in str(refused), (
            "the refusal says %r, which does not name the QoS that arrived"
            % (str(refused),))
        _refuses(s1.ProtocolError, "a SUBSCRIBE with no filters",
                 lambda: s.read_subscribe(_subscribe_body(7, ())),
                 names=("filter",))
        _refuses(s1.ProtocolError, "a trailing byte",
                 lambda: s.read_subscribe(_subscribe_body(7, (("a", 0),),
                                                          trailing=b"\xff")),
                 names=("trailing", "1"))
        _refuses(s1.ProtocolError, "two trailing bytes",
                 lambda: s.read_subscribe(_subscribe_body(7, (("a", 0),),
                                                          trailing=b"\x00\x00")),
                 names=("trailing",))
        short = _refuses(s1.Incomplete, "a body that stops without its QoS byte",
                         lambda: s.read_subscribe(_subscribe_body(7, (("a", 0),))[:-1]))
        assert short.needed == 1, (
            "the body ends at the filter and the QoS byte is still to come, and the "
            "refusal asked for %d" % (short.needed,))
        _refuses(s1.ProtocolError, "a non-UTF-8 filter",
                 lambda: s.read_subscribe(b"\x00\x07\x00\x02\xff\xfe\x00"),
                 names=("UTF-8",))
        _refuses(s1.ProtocolError, "a string handed in for a body",
                 lambda: s.read_subscribe("x"), names=("str",))
        _refuses(s1.ProtocolError, "a bool for a position",
                 lambda: s.read_subscribe(body, True), names=("True",))
        _refuses(s1.ProtocolError, "a position past the buffer",
                 lambda: s.read_subscribe(body, len(body) + 1), names=("24", "23"))

        short = _refuses(s1.Incomplete, "a body short of its packet id",
                         lambda: s.read_subscribe(b"\x00"))
        assert short.needed == 1, (
            "one byte of a packet id has arrived and one is still to come, and the "
            "refusal asked for %d" % (short.needed,))
        short = _refuses(s1.Incomplete, "a filter whose length overruns the buffer",
                         lambda: s.read_subscribe(b"\x00\x07\x00\x05ab"))
        assert short.needed == 3, (
            "a filter of five bytes with two arrived is three bytes away, and the "
            "refusal asked for %d" % (short.needed,))
        short = _refuses(s1.Incomplete, "a body that stops inside the first filter",
                         lambda: s.read_subscribe(b"\x00\x07\x00"))
        assert short.needed == 2, (
            "one byte of the first filter's length has arrived and one is still to "
            "come, and the refusal asked for %d" % (short.needed,))
        short = _refuses(s1.Incomplete, "a body that stops before the first QoS byte",
                         lambda: s.read_subscribe(b"\x00\x07\x00\x01"))
        assert short.needed == 1, (
            "the first filter's length is all here and its QoS byte is still to come, "
            "and the refusal asked for %d" % (short.needed,))

    def _unsubscribe(s, s1):
        body = _unsubscribe_body(9, ("a/b", "c"))
        got, after = s.read_unsubscribe(body)
        assert isinstance(got, list) and len(got) == 2, (
            "an UNSUBSCRIBE reads as [packet_id, filters], and it read as %r" % (got,))
        assert got[0] == 9, (
            "the packet id 9 read back as %r" % (got[0],))
        assert got[1] == ("a/b", "c"), (
            "the two filters — with no QoS byte between them — read back as %r"
            % (got[1],))
        assert isinstance(got[1], tuple), (
            "the filters are a tuple, not %r" % (type(got[1]),))
        assert after == len(body), (
            "the read stopped at %d of the body's %d bytes" % (after, len(body)))

        _refuses(s1.ProtocolError, "an UNSUBSCRIBE packet id of 0",
                 lambda: s.read_unsubscribe(_unsubscribe_body(0, ("a",))),
                 names=("packet id",))
        _refuses(s1.ProtocolError, "an UNSUBSCRIBE with no filters",
                 lambda: s.read_unsubscribe(_unsubscribe_body(7, ())),
                 names=("filter",))
        _refuses(s1.ProtocolError, "a trailing byte after an UNSUBSCRIBE",
                 lambda: s.read_unsubscribe(_unsubscribe_body(7, ("a",),
                                                              trailing=b"\xff")),
                 names=("trailing", "1"))
        _refuses(s1.ProtocolError, "a string handed in for an UNSUBSCRIBE body",
                 lambda: s.read_unsubscribe("x"), names=("str",))

        short = _refuses(s1.Incomplete, "an UNSUBSCRIBE body short of its packet id",
                         lambda: s.read_unsubscribe(b"\x00"))
        assert short.needed == 1, (
            "one byte of the id has arrived and one is still to come, and the "
            "refusal asked for %d" % (short.needed,))
        short = _refuses(s1.Incomplete, "an UNSUBSCRIBE filter overrunning the buffer",
                         lambda: s.read_unsubscribe(b"\x00\x07\x00\x05ab"))
        assert short.needed == 3, (
            "a filter of five bytes with two arrived is three bytes away, and the "
            "refusal asked for %d" % (short.needed,))
        short = _refuses(s1.Incomplete,
                         "an UNSUBSCRIBE that stops inside its first filter",
                         lambda: s.read_unsubscribe(b"\x00\x07\x00"))
        assert short.needed == 1, (
            "one byte of the first filter's length has arrived and one is still to "
            "come, and the refusal asked for %d" % (short.needed,))

    def _granted(s, s1):
        for requested in (0, 1, 2):
            for cap in (0, 1, 2):
                got = s.granted_qos(requested, cap)
                assert got == min(requested, cap), (
                    "a request of %d under a cap of %d grants %d, not %r"
                    % (requested, cap, min(requested, cap), got))
        assert s.granted_qos(2) == 2, (
            "the default cap is MAX_QOS, so a request of 2 grants 2, not %r"
            % (s.granted_qos(2),))
        _refuses(s1.ProtocolError, "a requested QoS of 3",
                 lambda: s.granted_qos(3), names=("3",))
        _refuses(s1.ProtocolError, "a negative requested QoS",
                 lambda: s.granted_qos(-1), names=("-1",))
        _refuses(s1.ProtocolError, "a cap of 3", lambda: s.granted_qos(1, 3),
                 names=("3",))
        _refuses(s1.ProtocolError, "a bool for a requested QoS",
                 lambda: s.granted_qos(True), names=("bool",))
        _refuses(s1.ProtocolError, "a string for a requested QoS",
                 lambda: s.granted_qos("1"), names=("str",))

    def _codes(s, s1):
        subscribe = {"packet_id": 7, "topics": (("a/#", 2), ("b", 1), ("c", 0))}
        assert s.grant_codes(subscribe) == (2, 1, 0), (
            "three filters with three grants get three codes in order, and they came "
            "back %r" % (s.grant_codes(subscribe),))
        assert isinstance(s.grant_codes(subscribe), tuple), (
            "the codes are a tuple, not %r" % (type(s.grant_codes(subscribe)),))
        assert s.grant_codes(subscribe, cap=1) == (1, 1, 0), (
            "a cap of 1 narrows the request of 2 but not the lower ones: %r"
            % (s.grant_codes(subscribe, cap=1),))
        assert s.grant_codes(subscribe, refused=("b",)) == (2, s.SUBACK_FAILURE, 0), (
            "the refused filter gets SUBACK_FAILURE and only it: %r"
            % (s.grant_codes(subscribe, refused=("b",)),))
        assert s.grant_codes(subscribe, cap=1, refused=("a/#", "c")) == (
            s.SUBACK_FAILURE, 1, s.SUBACK_FAILURE), (
            "refusals and the cap compose per filter: %r"
            % (s.grant_codes(subscribe, cap=1, refused=("a/#", "c")),))

        _refuses(s1.ProtocolError, "a subscription that is not a dict",
                 lambda: s.grant_codes(5), names=("dict",))
        _refuses(s1.ProtocolError, "a subscription missing a key",
                 lambda: s.grant_codes({"packet_id": 7}), names=("topics",))
        _refuses(s1.ProtocolError, "a topic that is not a pair",
                 lambda: s.grant_codes({"packet_id": 7, "topics": (("a",),)}),
                 names=("pair",))

    def _writes(s, s1):
        assert s.write_suback(7, (1,)) == b"\x00\x07\x01", (
            "write_suback(7, (1,)) is the body id then code, and it is %r"
            % (s.write_suback(7, (1,)),))
        assert isinstance(s.write_suback(7, (1,)), bytes), (
            "a writer returns bytes, not %r" % (type(s.write_suback(7, (1,))),))
        assert s.write_suback(0x1234, (0, s.SUBACK_FAILURE, 1)) == (
            b"\x12\x34\x00\x80\x01"), (
            "the client's id is echoed in front of one code per filter: %r"
            % (s.write_suback(0x1234, (0, s.SUBACK_FAILURE, 1)),))
        assert s.write_suback(7, ()) == b"\x00\x07", (
            "a SUBACK body with no codes is the echoed id alone: %r"
            % (s.write_suback(7, ()),))
        assert s.write_suback(65535, (0,)) == b"\xff\xff\x00", (
            "the largest packet id is a legal id: %r" % (s.write_suback(65535, (0,)),))
        assert s.write_unsuback(7) == b"\x00\x07", (
            "write_unsuback(7) is the bare id, and it is %r" % (s.write_unsuback(7),))
        assert s.write_unsuback(0x1234) == b"\x12\x34", (
            "the UNSUBACK echoes the id and nothing else: %r"
            % (s.write_unsuback(0x1234),))

        for bad in (0, -1, 65536):
            _refuses(s1.ProtocolError, "a packet id of %d" % (bad,),
                     lambda bad=bad: s.write_suback(bad, (0,)),
                     names=(str(bad),))
            _refuses(s1.ProtocolError, "an UNSUBACK packet id of %d" % (bad,),
                     lambda bad=bad: s.write_unsuback(bad), names=(str(bad),))
        _refuses(s1.ProtocolError, "a bool for a packet id",
                 lambda: s.write_suback(True, (0,)), names=("bool",))
        for bad in (3, 0x81):
            _refuses(s1.ProtocolError, "a SUBACK code of %r" % (bad,),
                     lambda bad=bad: s.write_suback(7, (bad,)), names=(str(bad),))
        _refuses(s1.ProtocolError, "a bool for a SUBACK code",
                 lambda: s.write_suback(7, (True,)), names=("True",))

    def _nibble(s, s1):
        """The reserved nibble is stage 1's rule, pinned here as the interaction."""
        body = _subscribe_body(7, (("a", 0),))
        legal = bytes([(s1.SUBSCRIBE << 4) | s.SUBSCRIBE_FLAGS]) + s1.write_varint(len(body)) + body
        dirty = bytes([(s1.SUBSCRIBE << 4) | 0b0011]) + s1.write_varint(len(body)) + body
        header, _ = s1.read_header(legal)
        assert header["flags"] == s.SUBSCRIBE_FLAGS, (
            "the framing layer reports the legal SUBSCRIBE nibble as %r, not %r"
            % (header["flags"], s.SUBSCRIBE_FLAGS))
        try:
            header, _ = s1.read_header(dirty)
        except s1.ProtocolError:
            pass
        else:
            assert header["flags"] != s.SUBSCRIBE_FLAGS, (
                "a dirty-nibble SUBSCRIBE frame reached the reader as flags %r, which "
                "the framing layer must not report as the legal nibble"
                % (header["flags"],))

    def _once(s):
        subscribe, sub_after = s.read_subscribe(_subscribe_body(7, (("a", 1), ("b", 2))))
        unsubscribe, unsub_after = s.read_unsubscribe(_unsubscribe_body(9, ("x", "y")))
        return (subscribe, sub_after, unsubscribe, unsub_after,
                s.granted_qos(2, 1), s.granted_qos(0, 2),
                s.grant_codes(subscribe), s.grant_codes(subscribe, cap=1,
                                                        refused=("b",)),
                s.write_suback(7, (1, s.SUBACK_FAILURE)), s.write_unsuback(9))

    def _twice(s):
        one = _once(s)
        two = _once(s)
        assert one == two, (
            "one fixture read twice gives two answers — a reader that consumes more "
            "the second time reads the stream wrong from then on: %r vs %r"
            % (one, two))

    import stage_01
    import stage_04 as s
    _constants(s)
    _subscribe(s, stage_01)
    _unsubscribe(s, stage_01)
    _granted(s, stage_01)
    _codes(s, stage_01)
    _writes(s, stage_01)
    _nibble(s, stage_01)
    _twice(s)

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "mqtt-broker-from-scratch"

    MAX_TOPIC_BYTES = 65_535

    def _repo(start=None):
        for candidate_start in (os.environ.get("L3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _string(text):
        """An MQTT string as it is written: two bytes of length, then its UTF-8."""
        raw = text.encode("utf-8")
        return bytes([len(raw) >> 8, len(raw) & 0xFF]) + raw

    def _body(topic, payload=b"", packet_id=None):
        """A PUBLISH body: the topic, the optional big-endian id, then the payload."""
        out = _string(topic)
        if packet_id is not None:
            out += bytes([packet_id >> 8, packet_id & 0xFF])
        return out + payload

    def _flags(qos=0, retain=False, dup=False):
        """The low nibble that describes a PUBLISH: DUP, QoS and RETAIN."""
        return (0b1000 if dup else 0) | (qos << 1) | (1 if retain else 0)

    def _expected(topic, payload, qos=0, packet_id=None, retain=False, dup=False):
        """The six keys of a parsed publish, in order."""
        return {"topic": topic, "payload": payload, "qos": qos, "packet_id": packet_id,
                "retain": retain, "dup": dup}

    def _publish(topic, payload=b"hi", qos=0, packet_id=None, retain=False, dup=False):
        """A publish as a value, for the store and the deliverer to be handed."""
        return {"topic": topic, "payload": payload, "qos": qos, "packet_id": packet_id,
                "retain": retain, "dup": dup}

    def _delivered(topic, payload, qos, retain=False):
        """The message a subscriber is handed: a publish that has no id yet."""
        return {"topic": topic, "payload": payload, "qos": qos, "packet_id": None,
                "retain": retain, "dup": False}

    def _constants(s):
        assert tuple(s.PUBLISH_KEYS) == ("topic", "payload", "qos", "packet_id",
                                         "retain", "dup"), (
            "a publish is six values in the order a reader meets them: %r"
            % (s.PUBLISH_KEYS,))
        assert s.DUP_BIT == 0b1000, (
            "DUP is bit 3 of the flags nibble, and the stage says %r" % (s.DUP_BIT,))
        assert s.QOS_BITS == 0b0110, (
            "the QoS is bits 2-1 of the flags nibble, and the stage says %r"
            % (s.QOS_BITS,))
        assert s.RETAIN_BIT == 0b0001, (
            "RETAIN is bit 0 of the flags nibble, and the stage says %r"
            % (s.RETAIN_BIT,))
        assert (s.DUP_BIT | s.QOS_BITS | s.RETAIN_BIT) == 0b1111, (
            "the three groups are the whole nibble, and %r, %r and %r leave %r out"
            % (s.DUP_BIT, s.QOS_BITS, s.RETAIN_BIT, 0b1111
               & ~(s.DUP_BIT | s.QOS_BITS | s.RETAIN_BIT)))
        assert not (s.DUP_BIT & s.QOS_BITS) and not (s.DUP_BIT & s.RETAIN_BIT) \
            and not (s.QOS_BITS & s.RETAIN_BIT), (
            "a nibble is three disjoint groups — DUP, QoS and RETAIN — and %r, %r "
            "and %r overlap" % (s.DUP_BIT, s.QOS_BITS, s.RETAIN_BIT))

    def _reading(s, world):
        body = _body("a/b", b"hi")
        got, after = s.read_publish(body, 0, 0)
        assert got == _expected("a/b", b"hi"), (
            "a QoS 0 publish is a topic and a payload, and it read as %r" % (got,))
        assert list(got) == list(s.PUBLISH_KEYS), (
            "the six keys come back in the order the stage declares them: %r"
            % (list(got),))
        assert got["packet_id"] is None, (
            "a QoS 0 publish carries no packet id, and the reader invented %r"
            % (got["packet_id"],))
        assert after == len(body), (
            "the payload runs to the end of the body, so the read stops at %d and "
            "the body is %d bytes" % (after, len(body)))

        same = _body("a/b", b"\x00\x07hi")
        quiet, _ = s.read_publish(same, 0, 0)
        loud, _ = s.read_publish(same, 0, _flags(1, retain=True))
        assert quiet == _expected("a/b", b"\x00\x07hi"), (
            "with QoS 0 no id follows the topic, so those two bytes are payload: %r"
            % (quiet,))
        assert loud == _expected("a/b", b"hi", 1, 7, retain=True), (
            "with QoS 1 the two bytes after the topic are the id, and the body read "
            "as %r" % (loud,))
        assert quiet != loud, (
            "the flags decide the body's shape, so the same bytes with a different "
            "nibble cannot answer the same: %r" % (quiet,))

        got, _ = s.read_publish(_body("a/b", b"hi", 7), 0, _flags(1, retain=True, dup=True))
        assert got == _expected("a/b", b"hi", 1, 7, retain=True, dup=True), (
            "DUP is bit 3 and RETAIN bit 0, and a re-sent retained QoS 1 publish "
            "read as %r" % (got,))
        got, _ = s.read_publish(_body("a/b", b"hi", 258), 0, _flags(2))
        assert got == _expected("a/b", b"hi", 2, 258), (
            "a QoS 2 publish's id is 258 when its two bytes are 0x01 0x02 — the id "
            "is big-endian — and the body read as %r" % (got,))
        got, _ = s.read_publish(_body("a/b", b"hi", 1), 0, _flags(1))
        assert got["packet_id"] == 1 and got["payload"] == b"hi", (
            "an id of one is not eaten from the payload: %r" % (got,))
        got, _ = s.read_publish(_body("caf\xe9/x", b""), 0, 0)
        assert got["topic"] == "caf\xe9/x" and got["payload"] == b"", (
            "a topic's length counts bytes and not characters, so a two-byte "
            "character is two of them: %r" % (got,))
        late = b"\x30\x00" + body
        got, after = s.read_publish(late, 2, 0)
        assert got == _expected("a/b", b"hi") and after == len(late), (
            "a read at position 2 leaves the bytes before it alone and stops at the "
            "end: %r at %r" % (got, after))
        got, _ = s.read_publish(bytearray(body), 0, 0)
        assert got == _expected("a/b", b"hi"), (
            "a bytearray is a buffer like any other: %r" % (got,))

        for buffer, needed in ((b"", 2), (b"\x00", 1), (b"\x00\x03a", 2)):
            refused = _refuses(world.Incomplete, "the topic in %r" % (buffer,),
                               lambda buffer=buffer: s.read_publish(buffer, 0, 0),
                               names=(str(needed),))
            assert refused.needed == needed, (
                "%r is %d bytes short of a topic, and the refusal asked for %d"
                % (buffer, needed, refused.needed))
        for buffer, needed in ((_string("a"), 2), (_string("a") + b"\x00", 1)):
            refused = _refuses(world.Incomplete,
                               "the id a QoS 1 publish says it has",
                               lambda buffer=buffer: s.read_publish(buffer, 0, _flags(1)),
                               names=(str(needed),))
            assert refused.needed == needed, (
                "a QoS 1 publish whose id has not arrived is %d bytes short, and the "
                "refusal asked for %d" % (needed, refused.needed))
        got, _ = s.read_publish(_string("a") + b"\x00\x01", 0, _flags(1))
        assert got == _expected("a", b"", 1, 1), (
            "the byte that arrives is what ends the wait, and a QoS 1 publish with "
            "an id of one and no payload read as %r" % (got,))
        got, _ = s.read_publish(_string("a") + b"\x00\x02", 0, _flags(2))
        assert got["qos"] == 2 and got["packet_id"] == 2, (
            "the QoS comes from the nibble and not from the body: %r" % (got,))

        _refuses(world.ProtocolError, "a topic that is not UTF-8",
                 lambda: s.read_publish(b"\x00\x02\xff\xfe", 0, 0), names=("xff",))
        _refuses(world.ProtocolError, "a wildcard publish topic",
                 lambda: s.read_publish(_body("a/+", b"hi"), 0, 0),
                 names=("wildcard", "'+'"))
        _refuses(world.ProtocolError, "an empty publish topic",
                 lambda: s.read_publish(_body("", b"hi"), 0, 0), names=("empty",))
        _refuses(world.ProtocolError, "a QoS of 3 in the flags nibble",
                 lambda: s.read_publish(body, 0, 0b0110), names=("3",))
        _refuses(world.ProtocolError, "a string handed in for a buffer",
                 lambda: s.read_publish("003a", 0, 0), names=("str",))
        _refuses(world.ProtocolError, "a position past the buffer",
                 lambda: s.read_publish(body, 99, 0), names=("99", "7"))
        _refuses(world.ProtocolError, "a bool position",
                 lambda: s.read_publish(body, True, 0), names=("True",))
        _refuses(world.ProtocolError, "a bool flags nibble",
                 lambda: s.read_publish(body, 0, True), names=("True",))
        _refuses(world.ProtocolError, "a flags nibble that is not four bits",
                 lambda: s.read_publish(body, 0, 0b10000), names=("16",))

    def _writing(s, world):
        assert s.write_publish("a/b", b"hi") == _string("a/b") + b"hi", (
            "the body is the topic and the payload: no type byte, no remaining "
            "length and no flags byte, and the writer wrote %r"
            % (s.write_publish("a/b", b"hi"),))
        assert s.write_publish("a/b", b"hi", 1, 7) == _string("a/b") + b"\x00\x07hi", (
            "the id sits between the topic and the payload, and it is big-endian: %r"
            % (s.write_publish("a/b", b"hi", 1, 7),))
        assert s.write_publish("a/b", b"", 2, 258) == _string("a/b") + b"\x01\x02", (
            "258 is 0x01 then 0x02: %r" % (s.write_publish("a/b", b"", 2, 258),))
        assert s.write_publish("a/b", b"hi", retain=True, dup=True) \
            == s.write_publish("a/b", b"hi"), (
            "DUP, QoS and RETAIN live in the header's nibble, so they change nothing "
            "on the wire: %r" % (s.write_publish("a/b", b"hi", retain=True, dup=True),))
        assert s.write_publish("a/b", b"", retain=1, dup=0) == _string("a/b"), (
            "a flag may be a bool or 0/1, and 1 is on: %r"
            % (s.write_publish("a/b", b"", retain=1, dup=0),))
        assert s.write_publish("\xe9", b"") == b"\x00\x02\xc3\xa9", (
            "a topic's length counts bytes and not characters: %r"
            % (s.write_publish("\xe9", b""),))
        longest = "x" * MAX_TOPIC_BYTES
        assert s.write_publish(longest, b"") == b"\xff\xff" + longest.encode("utf-8"), (
            "a topic of exactly %d bytes is a topic: %r"
            % (MAX_TOPIC_BYTES, s.write_publish(longest, b"")[:4]))
        _refuses(world.ProtocolError, "a topic one byte above the maximum",
                 lambda: s.write_publish("x" * (MAX_TOPIC_BYTES + 1), b""),
                 names=("65535", "65536"))

        for qos, packet_id in ((0, None), (1, 7), (2, 258), (1, 65_535)):
            for retain, dup in ((False, False), (True, True), (True, False)):
                written = s.write_publish("a/b", b"hi", qos, packet_id,
                                          retain=retain, dup=dup)
                flags = _flags(qos, retain=retain, dup=dup)
                assert (flags & 0b0110) == (qos << 1), (
                    "the fixture's nibble %r does not describe QoS %d" % (flags, qos))
                read, after = s.read_publish(written, 0, flags)
                assert read == _expected("a/b", b"hi", qos, packet_id, retain, dup), (
                    "a QoS %d publish with id %r, retain %r and dup %r was written as "
                    "%r and read back as %r"
                    % (qos, packet_id, retain, dup, written, read))
                assert after == len(written), (
                    "what was written is exactly the body that was read: %r"
                    % (written,))
                assert (read["packet_id"] is not None) == (qos > 0), (
                    "the id is on the wire exactly when the QoS is above zero: %r"
                    % (read,))
        _refuses(world.ProtocolError, "a QoS of zero with an id",
                 lambda: s.write_publish("a/b", b"", 0, 7), names=("7",))
        _refuses(world.ProtocolError, "a QoS above zero with no id",
                 lambda: s.write_publish("a/b", b"", 1), names=("packet id",))
        _refuses(world.ProtocolError, "a QoS of 3",
                 lambda: s.write_publish("a/b", b"", 3), names=("3",))
        _refuses(world.ProtocolError, "a negative QoS",
                 lambda: s.write_publish("a/b", b"", -1, 5), names=("-1",))
        _refuses(world.ProtocolError, "a bool for a QoS",
                 lambda: s.write_publish("a/b", b"", True), names=("bool",))
        _refuses(world.ProtocolError, "a packet id of 0",
                 lambda: s.write_publish("a/b", b"", 1, 0), names=("0",))
        _refuses(world.ProtocolError, "a packet id above the maximum",
                 lambda: s.write_publish("a/b", b"", 1, 65_536), names=("65536",))
        _refuses(world.ProtocolError, "a bool for a packet id",
                 lambda: s.write_publish("a/b", b"", 1, True), names=("True",))
        _refuses(world.ProtocolError, "a str handed in for a payload",
                 lambda: s.write_publish("a/b", "hi"), names=("str",))
        _refuses(world.ProtocolError, "a wildcard publish topic",
                 lambda: s.write_publish("a/+", b""), names=("wildcard", "'+'"))
        _refuses(world.ProtocolError, "an empty publish topic",
                 lambda: s.write_publish("", b""), names=("empty",))
        _refuses(world.ProtocolError, "a non-str topic",
                 lambda: s.write_publish(b"a/b", b""), names=("bytes",))
        _refuses(world.ProtocolError, "a retain flag that is not a flag",
                 lambda: s.write_publish("a/b", b"", retain="yes"), names=("retain",))
        _refuses(world.ProtocolError, "a DUP flag that is not a flag",
                 lambda: s.write_publish("a/b", b"", dup=2), names=("DUP",))

    def _retained(s, world):
        store = s.Retained()
        assert tuple(store.topics()) == (), (
            "a store that has held nothing lists nothing: %r" % (store.topics(),))
        assert store.lookup("a/b") is None, (
            "a topic nobody retained is not held: %r" % (store.lookup("a/b"),))
        assert store.store(_publish("a/b", b"hi", 1, 7)) is True, (
            "storing a message that is not empty holds it, and `store` reported "
            "something else")
        held = store.lookup("a/b")
        assert held == _publish("a/b", b"hi", 1, 7), (
            "what is looked up is what was stored: %r" % (held,))
        assert list(held) == list(s.PUBLISH_KEYS), (
            "a held publish keeps the six keys in order: %r" % (list(held),))
        assert tuple(store.topics()) == ("a/b",), (
            "one topic was retained: %r" % (store.topics(),))

        assert store.store(_publish("a/b", b"second", 2, 9)) is True, (
            "the last publish to a topic wins")
        held = store.lookup("a/b")
        assert held == _publish("a/b", b"second", 2, 9), (
            "the last publish to a topic replaces the one before it, and the store "
            "still answers %r" % (held,))
        assert held["qos"] == 2, (
            "a retained message keeps the QoS it was published at: %r" % (held,))
        assert tuple(store.topics()) == ("a/b",), (
            "re-publishing to a topic does not list it twice: %r" % (store.topics(),))

        ordered = s.Retained()
        ordered.store(_publish("zulu", b"1"))
        ordered.store(_publish("alpha", b"2"))
        ordered.store(_publish("zulu", b"3"))
        assert tuple(ordered.topics()) == ("zulu", "alpha"), (
            "the topics are listed in the order they were first held, and a "
            "re-publish keeps its place: %r" % (ordered.topics(),))
        assert ordered.lookup("zulu")["payload"] == b"3", (
            "the re-published message is the one held: %r"
            % (ordered.lookup("zulu"),))

        cleared = s.Retained()
        cleared.store(_publish("a/b", b"kept"))
        assert cleared.lookup("a/b") is not None, (
            "the message is held before the clear")
        assert cleared.store(_publish("a/b", b"")) is False, (
            "a zero-length payload clears the topic, and `store` reported it as a "
            "store instead")
        assert cleared.lookup("a/b") is None, (
            "a cleared topic holds nothing: %r" % (cleared.lookup("a/b"),))
        assert tuple(cleared.topics()) == (), (
            "a cleared topic is not listed: %r" % (cleared.topics(),))
        assert cleared.store(_publish("never", b"")) is False, (
            "clearing a topic that was never held takes nothing away and is still "
            "not a store")
        assert tuple(cleared.topics()) == (), (
            "clearing a topic that was never held lists nothing: %r"
            % (cleared.topics(),))

        exact = s.Retained()
        exact.store(_publish("a/b", b"hi"))
        for other in ("a", "a/b/c", "a/+", "b"):
            assert exact.lookup(other) is None, (
                "a retained message belongs to its own topic and not to %r: %r"
                % (other, exact.lookup(other)))
        assert exact.lookup("a/b") is not None, (
            "and the topic it does belong to still answers")

        one, two = s.Retained(), s.Retained()
        one.store(_publish("a/b", b"hi"))
        assert tuple(two.topics()) == () and two.lookup("a/b") is None, (
            "two stores are two tables, and %r leaked between them" % (two.topics(),))

        _refuses(world.ProtocolError, "a publish that is not a dict",
                 lambda: store.store("a/b"), names=("str",))
        _refuses(world.ProtocolError, "a publish missing the payload",
                 lambda: store.store({"topic": "a/b"}), names=("payload",))
        _refuses(world.ProtocolError, "a publish missing the retain flag",
                 lambda: store.store({"topic": "a/b", "payload": b"hi", "qos": 0,
                                      "packet_id": None, "dup": False}),
                 names=("retain",))

    def _routing(s, world, topics):
        trie = topics.Trie()
        trie.subscribe("a/b", "one", 1)
        trie.subscribe("a/+", "one", 2)
        trie.subscribe("a/b", "two", 0)
        trie.subscribe("b", "three", 2)
        trie.subscribe("b/+", "three", 1)
        assert s.route(trie, "a/b") == [("one", 2), ("two", 0)], (
            "one entry per client at its highest QoS, in the order the filters were "
            "inserted, and the route answered %r" % (s.route(trie, "a/b"),))
        assert s.route(trie, "b") == [("three", 2)], (
            "a topic reaches the clients whose filters match it and nobody else: %r"
            % (s.route(trie, "b"),))
        assert s.route(trie, "c") == [], (
            "a topic nobody subscribed to reaches nobody, and the route answered %r"
            % (s.route(trie, "c"),))
        assert s.route(trie, "a/b/c") == [], (
            "a/b does not match a/b/c: %r" % (s.route(trie, "a/b/c"),))
        assert s.route(trie, "a/c") == [("one", 2)], (
            "a/+ matches a/c and a/b only: %r" % (s.route(trie, "a/c"),))

        before = trie.filters()
        s.route(trie, "a/b")
        assert trie.filters() == before, (
            "routing reads the trie and does not change it: %r" % (trie.filters(),))

        wild = topics.Trie()
        wild.subscribe("#", "all", 0)
        wild.subscribe("+/x", "plus", 1)
        assert s.route(wild, "$SYS/x") == [], (
            "a filter whose first level is a wildcard does not reach a topic that "
            "begins with $, and the route answered %r" % (s.route(wild, "$SYS/x"),))
        assert s.route(wild, "SYS/x") == [("all", 0), ("plus", 1)], (
            "the same topic without the $ is reached: %r" % (s.route(wild, "SYS/x"),))

        _refuses(world.ProtocolError, "a wildcard handed to the router as a topic",
                 lambda: s.route(trie, "a/+"), names=("wildcard", "'+'"))
        _refuses(world.ProtocolError, "an empty topic handed to the router",
                 lambda: s.route(trie, ""), names=("empty",))
        _refuses(world.ProtocolError, "a non-str topic handed to the router",
                 lambda: s.route(trie, b"a/b"), names=("bytes",))

    def _deliveries(s, world):
        got = s.deliveries(_publish("a/b", b"hi"), [("one", 2), ("two", 0)])
        assert got == [("one", _delivered("a/b", b"hi", 2)),
                       ("two", _delivered("a/b", b"hi", 0))], (
            "one delivery per subscriber, each at that subscription's own QoS, and "
            "the deliverer answered %r" % (got,))
        assert [list(message) for who, message in got] \
            == [list(s.PUBLISH_KEYS)] * 2, (
            "a delivered message is a publish with the six keys in order: %r"
            % ([list(message) for who, message in got],))
        assert got[0][1]["packet_id"] is None, (
            "a delivery has no id yet — the sending side takes one when the message "
            "is put in flight: %r" % (got[0][1],))
        assert got[0][1]["retain"] is False and got[1][1]["retain"] is False, (
            "a live delivery does not carry the retain flag: %r" % (got,))
        assert got[0][1]["dup"] is False, (
            "a first transmission is not a duplicate: %r" % (got[0][1],))

        stored = s.deliveries(_publish("a/b", b"hi", retain=True), [("one", 1)])
        assert stored == [("one", _delivered("a/b", b"hi", 1))], (
            "a publish that was retained on its way past reaches the subscribers who "
            "were there as an ordinary message, and the deliverer answered %r"
            % (stored,))
        assert stored[0][1]["retain"] is False, (
            "the retain flag on the wire is not the publisher's wish to keep the "
            "message: %r" % (stored[0][1],))

        replay = s.deliveries(_publish("a/b", b"hi", retain=True), [("one", 1)],
                              retained=True)
        assert replay == [("one", _delivered("a/b", b"hi", 1, retain=True))], (
            "the stored message handed to a subscriber that just asked for it is a "
            "retained delivery, and the deliverer answered %r" % (replay,))
        assert replay[0][1]["retain"] is True, (
            "a retained delivery carries the flag as a bool and not as the bit "
            "itself: %r" % (replay[0][1],))
        assert s.deliveries(_publish("a/b", b"hi"), [("one", 1)], retained=1) \
            == [("one", _delivered("a/b", b"hi", 1, retain=True))], (
            "a retained flag may be a bool or 0/1, and 1 is on")

        twice = s.deliveries(_publish("a/b", b"hi"), [("one", 0), ("two", 1),
                                                      ("one", 2)])
        assert twice == [("one", _delivered("a/b", b"hi", 2)),
                         ("two", _delivered("a/b", b"hi", 1))], (
            "a client on two matching filters is handed the message once, at the "
            "higher QoS, and the deliverer answered %r" % (twice,))
        once = s.deliveries(_publish("a/b", b"hi"), [("one", 1), ("one", 1)])
        assert once == [("one", _delivered("a/b", b"hi", 1))], (
            "the same subscription twice is still one delivery: %r" % (once,))

        assert s.deliveries(_publish("a/b", b"hi", 2, 5), [("one", 0)]) \
            == [("one", _delivered("a/b", b"hi", 0))], (
            "the level a delivery goes out at is the subscription's and not the "
            "publisher's: %r" % (s.deliveries(_publish("a/b", b"hi", 2, 5),
                                             [("one", 0)]),))
        assert s.deliveries(_publish("a/b", b"hi"), []) == [], (
            "a publish nobody is subscribed to is delivered to nobody: %r"
            % (s.deliveries(_publish("a/b", b"hi"), []),))
        assert s.deliveries(_publish("a/b", b"", retain=True), [("one", 2)]) == [], (
            "a zero-length payload cleared a topic and is delivered to nobody: %r"
            % (s.deliveries(_publish("a/b", b"", retain=True), [("one", 2)]),))

        _refuses(world.ProtocolError, "a subscriber that is not a pair",
                 lambda: s.deliveries(_publish("a/b"), ["one"]), names=("'one'",))
        _refuses(world.ProtocolError, "a subscriber with three fields",
                 lambda: s.deliveries(_publish("a/b"), [("one", 1, 2)]),
                 names=("pair",))
        _refuses(world.ProtocolError, "a subscriber at a QoS of 3",
                 lambda: s.deliveries(_publish("a/b"), [("one", 3)]), names=("3",))
        _refuses(world.ProtocolError, "a subscriber whose name is not a str",
                 lambda: s.deliveries(_publish("a/b"), [(7, 0)]), names=("int",))
        _refuses(world.ProtocolError, "a retained flag that is not a flag",
                 lambda: s.deliveries(_publish("a/b"), [("one", 0)], retained="yes"),
                 names=("retained",))
        _refuses(world.ProtocolError, "a publish that is not a dict",
                 lambda: s.deliveries("a/b", [("one", 0)]), names=("str",))
        _refuses(world.ProtocolError, "a publish missing the QoS",
                 lambda: s.deliveries({"topic": "a/b", "payload": b"hi"},
                                      [("one", 0)]), names=("qos",))

    def _workload(s, world):
        """One run of the stage: write, read back, store, route, deliver, clear."""
        trie = world.Trie()
        trie.subscribe("a/b", "one", 2)
        trie.subscribe("a/+", "two", 1)
        store = s.Retained()
        out = []
        for qos, packet_id in ((0, None), (1, 7), (2, 258)):
            for retain in (False, True):
                body = s.write_publish("a/b", b"hi", qos, packet_id, retain=retain)
                publish, after = s.read_publish(body, 0, _flags(qos, retain=retain))
                out.append((body, publish, after))
                out.append(store.store(publish))
                out.append(s.route(trie, "a/b"))
                out.append(s.deliveries(publish, s.route(trie, "a/b")))
                out.append(s.deliveries(publish, s.route(trie, "a/b"), retained=True))
        out.append(store.topics())
        out.append(store.lookup("a/b"))
        out.append(store.store(_publish("a/b", b"", 0, None, retain=True)))
        out.append(store.topics())
        out.append(store.lookup("a/b"))
        out.append(s.route(trie, "a/b/c"))
        return out

    def _twice(s, world):
        one = _workload(s, world)
        two = _workload(s, world)
        assert one == two, (
            "the same workload twice answers differently — a stage whose answer "
            "depends on a set, or on what ran before it, cannot be replayed: %r vs "
            "%r" % (one, two))

    import stage_01 as world
    import stage_03 as topics
    import stage_05 as s
    _constants(s)
    _reading(s, world)
    _writing(s, world)
    _retained(s, world)
    _routing(s, world, topics)
    _deliveries(s, world)
    _twice(s, topics)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "mqtt-broker-from-scratch"

    KEYS = ("packet_id", "topic", "payload", "qos", "sent_at", "attempts")

    DEADLINES = 4

    WORKLOAD_BYTES = 34

    def _repo(start=None):
        for candidate_start in (os.environ.get("L3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _message(topic, payload, qos=1, retain=False):
        """One message to send: the keys the table needs, and one it must ignore."""
        return {"topic": topic, "payload": payload, "qos": qos, "retain": retain}

    def _framed(w, kind, body, flags=0):
        """`body` as a whole packet: the type and flags, the length, then the body."""
        return bytes([(kind << 4) | flags]) + w.write_varint(len(body)) + body

    def _publish_body(two, topic, payload, packet_id):
        """A QoS 1 PUBLISH body: the topic, the id's two bytes, then the payload.

        Stage 5 writes these bodies for real; this one is built here so that the two
        bytes this stage's PUBACK is made of can be pinned against a body's own,
        without this check having to trust another stage's writer to say it.
        """
        return (two.write_string(topic) + bytes([packet_id >> 8, packet_id & 0xFF])
                + payload)

    def _constants(s):
        assert s.MIN_PACKET_ID == 1, (
            "the first packet id is 1: a zero would make every QoS 0 publish an "
            "acknowledgement, and the stage says %r" % (s.MIN_PACKET_ID,))
        assert s.MAX_PACKET_ID == 65_535, (
            "two bytes carry 65_535 as the largest packet id, and the stage says %r"
            % (s.MAX_PACKET_ID,))
        assert s.DEFAULT_DEADLINE == 4, (
            "a message waits four ticks for its acknowledgement before it is sent "
            "again, and the stage says %r" % (s.DEFAULT_DEADLINE,))
        assert s.ACK_FLAGS == 0, (
            "a bare acknowledgement carries no flags of its own, and the stage says "
            "%r" % (s.ACK_FLAGS,))
        assert tuple(s.INFLIGHT_KEYS) == KEYS, (
            "a record's six keys are %r and the stage declares %r"
            % (list(KEYS), list(s.INFLIGHT_KEYS)))

    def _spending(s, w):
        """The id space: what it hands out, what it takes back, and what it refuses."""
        space = s.PacketIds()
        assert space.free() == 65_535, (
            "a fresh space is free in every one of its 65_535 ids, and it says %r"
            % (space.free(),))
        assert space.in_flight() == (), (
            "and nothing is in flight in it: %r" % (space.in_flight(),))
        assert isinstance(space.in_flight(), tuple), (
            "`in_flight()` is a tuple a caller may keep, not the space's own "
            "bookkeeping: %r" % (space.in_flight(),))
        first = space.take()
        assert first == 1, (
            "ids are handed out from the bottom of the space upwards, so the first "
            "take is 1 and this one was %r" % (first,))
        second = space.take()
        assert second == 2, (
            "with 1 in flight, the id at the bottom of the space is 2, and the take "
            "that followed answered %r" % (second,))
        assert space.in_flight() == (1, 2), (
            "`in_flight()` is the order of the takes: %r" % (space.in_flight(),))
        assert space.free() == 65_533, (
            "two ids in flight leave 65_533 free, and the space says %r"
            % (space.free(),))
        freed = space.release(first)
        assert freed == 1, (
            "releasing an id answers the id it freed: %r" % (freed,))
        assert space.in_flight() == (2,), (
            "and the id leaves the space: %r" % (space.in_flight(),))
        assert space.free() == 65_534, (
            "one released id is free again: %r" % (space.free(),))
        reused = space.take()
        assert reused == 1, (
            "a released id is handed out again before any id above it, because it is "
            "the bottom of the space: %r" % (reused,))
        assert space.in_flight() == (2, 1), (
            "and it is in flight again, in the order of the takes: %r"
            % (space.in_flight(),))
        after = space.take()
        assert after == 3, (
            "the take walks past the ids that are in flight — 1 and 2 are held, so "
            "the id at the bottom of the space that is nobody's is 3 — and this take "
            "answered %r" % (after,))
        assert space.in_flight() == (2, 1, 3), (
            "three ids in flight, in the order they were taken: %r"
            % (space.in_flight(),))

        full = s.PacketIds()
        taken = [full.take() for _ in range(65_535)]
        assert len(set(taken)) == 65_535, (
            "the space has 65_535 ids and handed out %d different ones: an id taken "
            "twice names two messages at once, and one PUBACK then frees both and "
            "leaves the second waiting forever" % (len(set(taken)),))
        assert taken == list(range(1, 65_536)), (
            "and they are handed out from the bottom upwards, 1 then 2 then 3 … "
            "65_535: this run began %r and ended %r"
            % (taken[:3], taken[-3:]))
        assert full.free() == 0, (
            "with every id in flight there is nothing left to hand out: %r"
            % (full.free(),))
        _refuses(w.ProtocolError, "a take with every id in flight",
                 lambda: full.take(), names=("65535",))
        returned = full.release(1)
        assert returned == 1, (
            "an id in a full space is an id like any other: %r" % (returned,))
        assert full.free() == 1, (
            "and one release makes room for one take: %r free" % (full.free(),))
        bottom = full.take()
        assert bottom == 1, (
            "the id handed back is the one at the bottom of the space, so it is the "
            "one a take finds first: %r" % (bottom,))
        top = full.release(65_535)
        assert top == 65_535, (
            "and the top of the space releases too: %r" % (top,))
        assert 65_535 not in full.in_flight(), (
            "the release answered 65_535, so 65_535 is the id that left the space — "
            "not somebody else's — and the space still holds %d ids"
            % (len(full.in_flight()),))
        assert full.free() == 1, (
            "one id in flight after all that: %r free" % (full.free(),))

        strangers = s.PacketIds()
        strangers.take()
        strangers.take()
        _refuses(w.ProtocolError, "releasing an id nobody took",
                 lambda: strangers.release(7), names=("7",))
        assert strangers.in_flight() == (1, 2), (
            "a refused release frees nothing — an id freed on a stranger's word is "
            "handed to a new message while the first is still in flight — and the "
            "space holds %r" % (strangers.in_flight(),))
        strangers.release(1)
        _refuses(w.ProtocolError, "releasing the same id twice",
                 lambda: strangers.release(1), names=("1",))
        assert strangers.in_flight() == (2,), (
            "and the second release frees nothing either: %r"
            % (strangers.in_flight(),))
        for bad, name in ((0, "0"), (65_536, "65536"), ("1", "str"), (True, "bool")):
            _refuses(w.ProtocolError, "releasing %r as a packet id" % (bad,),
                     lambda bad=bad: strangers.release(bad), names=(name,))

    def _writing(s, w, two):
        """The two bytes of an acknowledgement, and the body they belong to."""
        for packet_id, body in ((1, b"\x00\x01"), (7, b"\x00\x07"),
                                (255, b"\x00\xff"), (256, b"\x01\x00"),
                                (65_535, b"\xff\xff")):
            assert s.write_puback(packet_id) == body, (
                "the body of a PUBACK for %d is %r and this one is %r"
                % (packet_id, body, s.write_puback(packet_id)))
        for packet_id in (1, 2, 255, 256, 65_535):
            body = s.write_puback(packet_id)
            assert len(body) == 2, (
                "a bare acknowledgement's body is the id and nothing else — two "
                "bytes — so a caller's frame carries as much as its length says, and "
                "id %d wrote %d bytes: %r" % (packet_id, len(body), body))
            assert body == bytes([packet_id >> 8, packet_id & 0xFF]), (
                "the id is two bytes big-endian, high byte first, and %d wrote %r"
                % (packet_id, body))
        published = _publish_body(two, "a/b", b"hello", 7)
        topic, after = two.read_string(published)
        assert (topic, after) == ("a/b", 5), (
            "stage 2's string writer puts the topic in front of the id's two bytes: "
            "%r read as %r and %r" % (published, topic, after))
        assert published[5:7] == s.write_puback(7) == b"\x00\x07", (
            "a QoS 1 publish carries its packet id in the same two bytes a PUBACK "
            "does, right after its topic: %r against %r"
            % (published, s.write_puback(7)))
        body = s.write_puback(7)
        frame = _framed(w, w.PUBACK, body)
        assert frame == b"\x40\x02\x00\x07", (
            "a PUBACK on the wire is the type byte, a length of two and the id: %r"
            % (frame,))
        header, payload = w.read_header(frame)
        assert header == {"type": 4, "flags": 0, "length": 2, "size": 2}, (
            "stage 1 reads that frame as a bare PUBACK: %r" % (header,))
        assert frame[payload:] == body, (
            "and what is left at the payload is the body this stage wrote: %r"
            % (frame[payload:],))
        assert s.read_ack(frame[payload:]) == (7, 2), (
            "which reads back as the id and the position after it: %r"
            % (s.read_ack(frame[payload:]),))
        for kind in (w.PUBACK, w.PUBREC, w.PUBREL, w.PUBCOMP):
            assert s.write_ack(kind, 7) == b"\x00\x07", (
                "every bare acknowledgement carries the id and nothing else — type "
                "%d included — and this one wrote %r" % (kind, s.write_ack(kind, 7)))
        assert s.write_ack(w.PUBCOMP, 65_535) == b"\xff\xff", (
            "the four ways of saying the same thing are the same two bytes: %r"
            % (s.write_ack(w.PUBCOMP, 65_535),))
        for kind in (w.PUBLISH, w.SUBSCRIBE, w.PINGREQ, 0, 9):
            _refuses(w.ProtocolError, "the body of a type %d packet" % (kind,),
                     lambda kind=kind: s.write_ack(kind, 7), names=(repr(kind),))
        for packet_id, name in ((0, "0"), (65_536, "65536"), ("7", "str"),
                                (True, "bool")):
            _refuses(w.ProtocolError, "the id %r" % (packet_id,),
                     lambda packet_id=packet_id: s.write_puback(packet_id),
                     names=(name,))
        _refuses(w.ProtocolError, "the id of a bare acknowledgement of type 4",
                 lambda: s.write_ack(w.PUBACK, 0), names=("0",))

    def _reading(s, w):
        """The id behind a body, from both sides of every boundary."""
        for packet_id in (1, 2, 255, 256, 65_535):
            body = s.write_puback(packet_id)
            assert s.read_ack(body) == (packet_id, 2), (
                "the two bytes of %d read back as %r" % (packet_id, s.read_ack(body)))
        assert s.read_ack(b"\x00\x07") == (7, 2), (
            "a body read from the front: %r" % (s.read_ack(b"\x00\x07"),))
        behind = b"\x2a" + s.write_puback(9)
        assert s.read_ack(behind, 1) == (9, 3), (
            "at position 1 the body is the id behind the leading byte, and the "
            "position after it is 3: %r" % (s.read_ack(behind, 1),))
        assert s.read_ack(bytearray(b"\x00\x07")) == (7, 2), (
            "a bytearray is a buffer like any other: %r"
            % (s.read_ack(bytearray(b"\x00\x07")),))
        for body, needed in ((b"", 2), (b"\x00", 1)):
            refused = _refuses(w.Incomplete, "the id in %r" % (body,),
                               lambda body=body: s.read_ack(body))
            assert refused.needed == needed, (
                "%r is %d of the id's two bytes, so %d more could end it, and the "
                "refusal asked for %d"
                % (body, len(body), needed, refused.needed))
            assert str(needed) in str(refused), (
                "the refusal says %r, which does not tell a reader how many bytes to "
                "wait for" % (str(refused),))
        refused = _refuses(w.ProtocolError, "a packet id of zero",
                           lambda: s.read_ack(b"\x00\x00"), names=("0",))
        assert "x00" in str(refused), (
            "the refusal names the two bytes that carried it, and it says %r"
            % (str(refused),))
        _refuses(w.ProtocolError, "a zero id with a byte behind it",
                 lambda: s.read_ack(b"\x00\x00\x00"), names=("0",))
        for body in (b"\x00\x07\x00", b"\x00\x07hello"):
            _refuses(w.ProtocolError, "a byte after the id in %r" % (body,),
                     lambda body=body: s.read_ack(body),
                     names=("trailing", str(len(body))))
        _refuses(w.ProtocolError, "a string for a buffer",
                 lambda: s.read_ack("00"), names=("str",))
        _refuses(w.ProtocolError, "a bool for a position",
                 lambda: s.read_ack(b"\x00\x07", True), names=("True",))
        _refuses(w.ProtocolError, "a position past the buffer",
                 lambda: s.read_ack(b"\x00\x07", 9), names=("9", "2"))

    def _world(s, w, streams):
        """The world carries the frame this stage writes, and counts it."""
        transport = streams.Transport()
        transport.listen("broker")
        client = transport.connect("client", "broker")
        frame = _framed(w, w.PUBACK, s.write_puback(9))
        assert transport.answer(client, frame) == len(frame), (
            "the transport takes a %d-byte answer whole when its chunk is %d: a "
            "broker that believes more went than was taken has lost the tail"
            % (len(frame), transport.stats()["chunk"]))
        transport.step()
        assert transport.to_client(client) == frame, (
            "the bytes at the client are not the PUBACK the broker answered with: %r"
            % (transport.to_client(client),))
        assert transport.stats()["bytes_carried"] == len(frame), (
            "the transport's own account of the bytes it carried is %r and the frame "
            "was %d bytes" % (transport.stats()["bytes_carried"], len(frame)))

    def _bare(s, w):
        """A table built over nothing: the records, and the ids left to the caller."""
        table = s.InFlight()
        assert table.records() == (), (
            "a table built with no id space holds nothing: %r" % (table.records(),))
        record = table.add(_message("a/b", b"one"), 7, 0)
        assert (record["packet_id"], record["attempts"]) == (7, 1), (
            "and the id is the caller's to hand in at `add`: %r" % (record,))
        assert table.due(3) == (), (
            "a message sent at tick 0 is not late at 3: %r" % (table.due(3),))
        assert [held["packet_id"] for held in table.due(4)] == [7], (
            "and it is late at 4: %r"
            % ([held["packet_id"] for held in table.due(4)],))
        resent = table.again(7, 5)
        assert resent["attempts"] == 2, (
            "a re-send under an id nobody took for it is the same message re-sent: %r"
            % (resent,))
        done = table.settle(7)
        assert done["packet_id"] == 7 and table.records() == (), (
            "the acknowledgement answers the record and takes it out of the table, "
            "even with no space to give the id back to: %r" % (done,))
        _refuses(w.ProtocolError, "the second acknowledgement of id 7",
                 lambda: table.settle(7), names=("7",))
        assert table.records() == (), (
            "and the second one frees nothing and forgets nothing: %r"
            % (table.records(),))

    def _records(s, w):
        """A record's shape, and the id it does not spend by being put in flight."""
        space = s.PacketIds()
        table = s.InFlight(space)
        assert table.records() == (), (
            "a table with nothing sent holds nothing: %r" % (table.records(),))
        assert isinstance(table.records(), tuple), (
            "`records()` is a tuple a caller may keep: %r" % (table.records(),))
        first = space.take()
        record = table.add(_message("a/b", b"one"), first, 0)
        assert list(record) == list(s.INFLIGHT_KEYS), (
            "a record is a dict of exactly `INFLIGHT_KEYS`, in order: %r"
            % (list(record),))
        assert (record["packet_id"], record["topic"], record["payload"],
                record["qos"], record["sent_at"]) == (1, "a/b", b"one", 1, 0), (
            "the record of a message sent at tick 0 is %r" % (record,))
        assert record["attempts"] == 1, (
            "the first transmission carries no DUP — nothing has been sent twice — "
            "so the count starts at one, and this record says %r"
            % (record["attempts"],))
        assert table.records() == (record,), (
            "the table holds the record it answered with: %r" % (table.records(),))
        assert space.free() == 65_534 and space.in_flight() == (1,), (
            "the caller took the id before the send and putting the message in "
            "flight spends nothing: the space is %r with %d free"
            % (space.in_flight(), space.free()))

        second = space.take()
        other = table.add(_message("c/d", b"two"), second, 1)
        assert [held["packet_id"] for held in table.records()] == [1, 2], (
            "records come back in the order the sends were added: %r"
            % ([held["packet_id"] for held in table.records()],))
        assert (other["packet_id"], other["sent_at"]) == (2, 1), (
            "the second record is its own message at its own tick: %r" % (other,))
        assert space.free() == 65_533, (
            "two ids in flight: %r free" % (space.free(),))

        assert table.due(3) == (), (
            "a message sent at tick 0 with a deadline of four ticks is not late at 3: "
            "%r" % (table.due(3),))
        assert [held["packet_id"] for held in table.due(4)] == [1], (
            "at tick 4 the deadline has been reached — the tick itself counts — and "
            "only the first message is that old: %r"
            % ([held["packet_id"] for held in table.due(4)],))
        assert [held["packet_id"] for held in table.due(5)] == [1, 2], (
            "at tick 5 both are late: %r"
            % ([held["packet_id"] for held in table.due(5)],))
        held = table.records()
        assert table.due(5) == table.due(5), (
            "asking what is due twice answers the same thing: %r vs %r"
            % (table.due(5), table.due(5)))
        assert table.records() == held and held[0]["sent_at"] == 0, (
            "asking is a question: it does not re-send, so `sent_at` stays where the "
            "send put it, and the table went from %r to %r"
            % (held, table.records()))
        assert table.due(8, 9) == (), (
            "a deadline the caller chose is measured from the same `sent_at`: %r"
            % (table.due(8, 9),))
        assert [held["packet_id"] for held in table.due(9, 9)] == [1], (
            "and it is reached at 9 for a message sent at 0: %r"
            % ([held["packet_id"] for held in table.due(9, 9)],))
        for now, name in ((-1, "-1"), ("3", "str"), (True, "bool")):
            _refuses(w.ProtocolError, "asking at a tick of %r" % (now,),
                     lambda now=now: table.due(now), names=(name,))
        for deadline, name in ((0, "0"), (-1, "-1"), ("4", "str"), (True, "bool")):
            _refuses(w.ProtocolError, "a deadline of %r" % (deadline,),
                     lambda deadline=deadline: table.due(5, deadline), names=(name,))

        done = table.settle(second)
        assert done["packet_id"] == 2, (
            "`settle` answers the record it took: %r" % (done,))
        assert [held["packet_id"] for held in table.records()] == [1], (
            "and the acknowledged message is gone from the table: %r"
            % ([held["packet_id"] for held in table.records()],))
        assert space.in_flight() == (1,) and space.free() == 65_534, (
            "as is its id, back in the space: %r with %d free"
            % (space.in_flight(), space.free()))

        again = table.again(first, 6)
        assert (again["packet_id"], again["sent_at"], again["attempts"]) == (1, 6, 2), (
            "a re-send is the same message under the same id, at the tick it went "
            "out, and it is a duplicate now: %r" % (again,))
        assert space.in_flight() == (1,) and space.free() == 65_534, (
            "a re-send takes no id and frees none — a fresh one would leave the first "
            "in flight for an acknowledgement already on its way: %r"
            % (space.in_flight(),))
        assert table.due(9) == (), (
            "the deadline moved with the re-send: at 9 a message last sent at 6 is "
            "not late: %r" % (table.due(9),))
        assert [held["packet_id"] for held in table.due(10)] == [1], (
            "and it is late at 10: %r"
            % ([held["packet_id"] for held in table.due(10)],))
        twice = table.again(first, 12)
        assert twice["attempts"] == 3, (
            "a second re-send is the third attempt: %r" % (twice,))
        assert (twice["packet_id"], twice["sent_at"]) == (1, 12), (
            "under the same id and from the tick it went out at: %r" % (twice,))
        assert table.due(15) == () and [held["packet_id"]
                                        for held in table.due(16)] == [1], (
            "and the deadline follows the last send, not the first: %r then %r"
            % (table.due(15), [held["packet_id"] for held in table.due(16)]))

    def _refusals(s, w):
        """The ids nobody is waiting on, and the second acknowledgement."""
        space = s.PacketIds()
        table = s.InFlight(space)
        one, two = space.take(), space.take()
        table.add(_message("a/b", b"x"), one, 0)
        table.add(_message("c/d", b"y"), two, 0)
        table.settle(one)
        assert space.in_flight() == (2,) and space.free() == 65_534, (
            "one acknowledgement freed one id: %r with %d free"
            % (space.in_flight(), space.free()))
        _refuses(w.ProtocolError, "the second acknowledgement of id 1",
                 lambda: table.settle(one), names=("1",))
        assert space.in_flight() == (2,) and space.free() == 65_534, (
            "a refused acknowledgement frees nothing, and the space still holds %r "
            "with %d free" % (space.in_flight(), space.free()))
        assert [held["packet_id"] for held in table.records()] == [2], (
            "and the message whose PUBACK has not come is still in flight: %r"
            % ([held["packet_id"] for held in table.records()],))
        _refuses(w.ProtocolError, "an acknowledgement for id 99",
                 lambda: table.settle(99), names=("99",))
        _refuses(w.ProtocolError, "a re-send of id 99",
                 lambda: table.again(99, 5), names=("99",))
        assert space.in_flight() == (2,), (
            "and neither of those touched the space: %r" % (space.in_flight(),))
        for bad, name in ((0, "0"), (65_536, "65536"), ("1", "str"), (True, "bool")):
            _refuses(w.ProtocolError, "settling %r as a packet id" % (bad,),
                     lambda bad=bad: table.settle(bad), names=(name,))
            _refuses(w.ProtocolError, "re-sending %r as a packet id" % (bad,),
                     lambda bad=bad: table.again(bad, 1), names=(name,))
        for now, name in ((-1, "-1"), ("5", "str"), (True, "bool")):
            _refuses(w.ProtocolError, "re-sending id 2 at a tick of %r" % (now,),
                     lambda now=now: table.again(two, now), names=(name,))
        resent = table.again(two, 5)
        assert (resent["sent_at"], resent["attempts"]) == (5, 2), (
            "and a re-send at a tick of the clock's own moves the record to that tick "
            "and counts one more attempt — none of those refusals moved it: %r"
            % (resent,))

        empty = s.InFlight(s.PacketIds())
        for label, call, name in (
                ("a message that is not a dict",
                 lambda: empty.add(("a/b", b"x"), 1, 0), "tuple"),
                ("a message with no payload",
                 lambda: empty.add({"topic": "a/b", "qos": 1}, 1, 0), "payload"),
                ("a message with no topic",
                 lambda: empty.add({"payload": b"x", "qos": 1}, 1, 0), "topic"),
                ("a message with no qos",
                 lambda: empty.add({"topic": "a/b", "payload": b"x"}, 1, 0), "qos"),
                ("a packet id of zero",
                 lambda: empty.add(_message("a/b", b"x"), 0, 0), "0"),
                ("a packet id above the space",
                 lambda: empty.add(_message("a/b", b"x"), 65_536, 0), "65536"),
                ("a string for a packet id",
                 lambda: empty.add(_message("a/b", b"x"), "1", 0), "str"),
                ("a bool for a packet id",
                 lambda: empty.add(_message("a/b", b"x"), True, 0), "bool"),
                ("a tick before the clock started",
                 lambda: empty.add(_message("a/b", b"x"), 1, -1), "-1"),
                ("a string for a tick",
                 lambda: empty.add(_message("a/b", b"x"), 1, "0"), "str"),
                ("a bool for a tick",
                 lambda: empty.add(_message("a/b", b"x"), 1, True), "bool")):
            _refuses(w.ProtocolError, label, call, names=(name,))
        assert empty.records() == (), (
            "every one of those refusals left the table as it was: %r"
            % (empty.records(),))

        held = s.PacketIds()
        busy = s.InFlight(held)
        taken = held.take()
        busy.add(_message("a/b", b"x"), taken, 0)
        _refuses(w.ProtocolError, "a second message under an id already in flight",
                 lambda: busy.add(_message("c/d", b"y"), taken, 1),
                 names=(str(taken),))
        assert held.in_flight() == (taken,) and [r["packet_id"]
                                                 for r in busy.records()] == [taken], (
            "one packet id waits on one message, and the refusal changed nothing: %r"
            % (busy.records(),))
        _refuses(w.ProtocolError, "a table over something that is not an id space",
                 lambda: s.InFlight("space"), names=("str",))
        _refuses(w.ProtocolError, "a table over a number that is not an id space",
                 lambda: s.InFlight(7), names=("int",))

    def _workload(s, w, two, streams):
        """One scripted QoS 1 run, as a tuple of plain values about itself.

        Two deliveries go out from a space of one broker's own, the first is late
        after four ticks and goes out again under the same id with DUP set, and each
        is acknowledged with a PUBACK this stage wrote. Every step appends what it
        did, so two runs of the script can be compared entry by entry.
        """
        transport = streams.Transport()
        transport.listen("broker")
        client = transport.connect("client", "broker")
        space = s.PacketIds()
        table = s.InFlight(space)
        trace = []

        def send_delivery(topic, payload, packet_id, dup=False):
            """A PUBLISH body in a frame, with the nibble the flags call for."""
            body = _publish_body(two, topic, payload, packet_id)
            flags = 0b1010 if dup else 0b0010
            packet = _framed(w, w.PUBLISH, body, flags)
            taken = transport.answer(client, packet)
            assert taken == len(packet), (
                "the transport took %d of a %d-byte PUBLISH" % (taken, len(packet)))
            return packet

        assert transport.tick() == 0, (
            "a fresh transport starts at tick 0: %r" % (transport.tick(),))
        first = space.take()
        first_frame = send_delivery("a", b"one", first)
        table.add(_message("a", b"one"), first, transport.tick())
        trace.append(("sent", first, transport.tick(), space.free()))

        transport.step()
        assert transport.to_client(client) == first_frame, (
            "the first delivery did not arrive whole: %r"
            % (transport.to_client(client),))
        second = space.take()
        second_frame = send_delivery("b", b"two", second)
        table.add(_message("b", b"two"), second, transport.tick())
        trace.append(("sent", second, transport.tick(), space.free()))

        transport.step(2)
        assert transport.to_client(client) == second_frame, (
            "the second delivery was carried on the tick after it went out: %r"
            % (transport.to_client(client),))
        trace.append(("due", transport.tick(),
                      tuple(held["packet_id"] for held in table.due(transport.tick()))))
        assert trace[-1] == ("due", 3, ()), (
            "at tick 3 nothing is late yet: %r" % (trace[-1],))

        transport.step()
        due = table.due(transport.tick())
        assert [held["packet_id"] for held in due] == [first], (
            "at tick 4 the first delivery is late and the second is not: %r"
            % ([held["packet_id"] for held in due],))
        assert due[0]["attempts"] == 1, (
            "the first transmission carries no DUP: %r" % (due[0],))
        resent = table.again(first, transport.tick())
        assert resent["attempts"] == 2, (
            "the re-send is the second attempt: %r" % (resent,))
        resent_frame = send_delivery("a", b"one", first, dup=True)
        trace.append(("resent", first, transport.tick(), space.free()))
        assert resent_frame[0] != first_frame[0], (
            "a re-send carries DUP and the first transmission did not: %r and %r"
            % (resent_frame, first_frame))
        assert resent_frame[1:] == first_frame[1:], (
            "and it is otherwise the same packet: %r against %r"
            % (resent_frame, first_frame))

        transport.step()
        assert transport.to_client(client) == resent_frame, (
            "the re-send did not arrive whole: %r" % (transport.to_client(client),))
        trace.append(("due", transport.tick(),
                      tuple(held["packet_id"] for held in table.due(transport.tick()))))
        assert trace[-1] == ("due", 5, (second,)), (
            "the re-sent delivery is not late again and the other one now is: %r"
            % (trace[-1],))
        ack = _framed(w, w.PUBACK, s.write_puback(first))
        assert transport.send(client, ack) == len(ack), (
            "the client's PUBACK went out whole: %r" % (ack,))
        transport.step()
        assert transport.to_server(client) == ack, (
            "the PUBACK did not arrive at the broker: %r"
            % (transport.to_server(client),))
        header, payload = w.read_header(ack)
        assert header["type"] == w.PUBACK and header["length"] == 2, (
            "and it is a bare PUBACK of two bytes: %r" % (header,))
        assert s.read_ack(ack[payload:]) == (first, 2), (
            "whose body is the id it answers: %r" % (s.read_ack(ack[payload:]),))
        done = table.settle(first)
        trace.append(("settled", done["packet_id"], len(table.records()),
                      space.free()))
        assert space.in_flight() == (second,), (
            "one acknowledgement freed one id: %r" % (space.in_flight(),))
        reused = space.take()
        assert reused == first, (
            "and the freed id is the id at the bottom of the space, so it is the next "
            "one handed out: %r" % (reused,))
        trace.append(("reused", reused, transport.tick()))

        table.settle(second)
        space.release(reused)
        trace.append(("settled", second, len(table.records()), space.free()))
        assert table.records() == (), (
            "both deliveries are acknowledged: %r" % (table.records(),))
        assert space.in_flight() == () and space.free() == 65_535, (
            "and every id is back in the space: %r with %d free"
            % (space.in_flight(), space.free()))
        trace.append(("stats", transport.stats()["bytes_carried"],
                      transport.steps()))
        assert transport.stats()["bytes_carried"] == WORKLOAD_BYTES, (
            "this script puts three PUBLISHes and one PUBACK on the wire, %d bytes, "
            "and the transport counted %r"
            % (WORKLOAD_BYTES, transport.stats()["bytes_carried"]))
        return tuple(trace)

    def _twice(s, w, two, streams):
        """One scripted workload, run twice, and the two runs must agree."""
        one = _workload(s, w, two, streams)
        other = _workload(s, w, two, streams)
        assert one == other, (
            "two runs of the same scripted workload answered differently — a table or "
            "a space with a clock of its own, or a reader that ate a byte the second "
            "time round, cannot say the same thing twice:\n%r\n%r" % (one, other))
        assert [entry[1] for entry in one if entry[0] == "sent"] == [1, 2], (
            "the two deliveries went out under the two ids the space handed out: %r"
            % (one,))
        assert [entry[3] for entry in one if entry[0] == "sent"] == [65_534, 65_533], (
            "and each take left the space one id smaller: %r" % (one,))
        assert [entry[1:3] for entry in one if entry[0] == "resent"] == [(1, 4)], (
            "the first delivery was re-sent at tick 4, its deadline, under its own "
            "id: %r" % (one,))
        assert [entry[1:3] for entry in one if entry[0] == "settled"] == [
            (1, 1), (2, 0)], (
            "each acknowledgement took one message out of the table: %r" % (one,))
        assert one[-1][1] == WORKLOAD_BYTES, (
            "the last entry is the transport's own count of the bytes it carried, and "
            "this script carries %d: %r" % (WORKLOAD_BYTES, one[-1]))

    import stage_01 as w
    import stage_02 as two
    import stage_06 as s
    import streams
    _constants(s)
    _spending(s, w)
    _writing(s, w, two)
    _reading(s, w)
    _world(s, w, streams)
    _bare(s, w)
    _records(s, w)
    _refusals(s, w)
    _twice(s, w, two, streams)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "mqtt-broker-from-scratch"

    LOW_ID = 1

    HIGH_ID = 65_535

    QOS2 = 2 << 1                       # the QoS bits of the fixed header's low nibble

    RETAIN = 0b0001                     # the retain bit of the same nibble

    PUBLISH_AGAIN = 0b1100              # DUP set, QoS 2: what a re-sent PUBLISH carries

    PUBREL_AGAIN = 0b0010               # PUBREL_FLAGS: what a re-sent PUBREL carries

    def _repo(start=None):
        for candidate_start in (os.environ.get("L3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _message(topic="a/b", payload=b"hi", qos=2, packet_id=None, retain=False,
                 dup=False):
        """A stage 5 publish dict, in `PUBLISH_KEYS` order, for a fixture."""
        return {"topic": topic, "payload": payload, "qos": qos,
                "packet_id": packet_id, "retain": retain, "dup": dup}

    def _id_bytes(packet_id):
        """The two bytes every bare acknowledgement in this stage writes."""
        return bytes([packet_id >> 8, packet_id & 0xFF])

    def _constants(s, stage_01):
        assert s.PUBREL_FLAGS == 0b0010, (
            "a PUBREL's low nibble is 0b0010, and this stage says %r"
            % (s.PUBREL_FLAGS,))
        assert stage_01.REQUIRED_FLAGS.get(6) == s.PUBREL_FLAGS, (
            "the nibble stage 1 requires for a PUBREL is %r and this stage calls it "
            "%r — one rule, two halves" % (stage_01.REQUIRED_FLAGS.get(6),
                                           s.PUBREL_FLAGS))
        assert tuple(s.HANDSHAKE_KEYS) == ("packet_id", "message", "state"), (
            "a record in flight is the id, the message and the state, in that order: %r"
            % (s.HANDSHAKE_KEYS,))

    def _writers(s, stage_01):
        for packet_id in (LOW_ID, 7, 255, 256, 4_096, HIGH_ID):
            want = _id_bytes(packet_id)
            for name in ("write_pubrec", "write_pubrel", "write_pubcomp"):
                got = getattr(s, name)(packet_id)
                assert got == want, (
                    "%s(%d) is the body %r, and this writer answers %r"
                    % (name, packet_id, want, got))
        for name in ("write_pubrec", "write_pubrel", "write_pubcomp"):
            writer = getattr(s, name)
            label = name.split("_")[-1].upper()
            for bad, said in ((0, "0"), (HIGH_ID + 1, "65536"), (-1, "-1")):
                _refuses(stage_01.ProtocolError, "%s(%d)" % (name, bad),
                         lambda writer=writer, bad=bad: writer(bad),
                         names=(said, label))
            _refuses(stage_01.ProtocolError, "%s(True)" % (name,),
                     lambda writer=writer: writer(True), names=("bool", label))
            _refuses(stage_01.ProtocolError, "%s('7')" % (name,),
                     lambda writer=writer: writer("7"), names=("str", label))

    def _sender(s, stage_01, stage_05, stage_06):
        ids = stage_06.PacketIds()
        free = ids.free()
        send = s.Sender(ids)
        topic, payload = "sport/tennis", b"ace"
        message = _message(topic, payload)
        packet_id, body = send.start(message, 10)
        assert LOW_ID <= packet_id <= HIGH_ID, (
            "the sender takes an id of its own from the PacketIds it was built with, "
            "and it took %r" % (packet_id,))
        assert tuple(ids.in_flight()) == (packet_id,), (
            "a delivered message's id is in flight the moment it is taken: %r"
            % (ids.in_flight(),))
        assert ids.free() == free - 1, (
            "one id is in flight, so %d are free and not %d" % (free - 1, ids.free()))
        assert body == stage_05.write_publish(topic, payload, 2, packet_id), (
            "the first PUBLISH body is stage 5's own, under this id: %r" % (body,))
        publish, end = stage_05.read_publish(body, flags=QOS2)
        assert publish == {"topic": topic, "payload": payload, "qos": 2,
                           "packet_id": packet_id, "retain": False, "dup": False}, (
            "the body the sender writes reads back as the message it was given, and "
            "it reads back as %r" % (publish,))
        assert end == len(body), (
            "the PUBLISH body ends where the reader says it does: %r of %d"
            % (end, len(body)))

        kept = _message("a/b", b"kept", retain=True)
        kept_id, kept_body = send.start(kept, 11)
        assert kept_id != packet_id, (
            "two messages in flight are two ids, not one twice: %r" % (kept_id,))
        kept_back, _ = stage_05.read_publish(kept_body, flags=QOS2 | RETAIN)
        assert kept_back["retain"] is True and kept_back["packet_id"] == kept_id, (
            "a retained message keeps its retain flag through the handshake: %r"
            % (kept_back,))

        assert send.records() == (
            {"packet_id": packet_id, "message": message, "state": "waiting-rec"},
            {"packet_id": kept_id, "message": kept, "state": "waiting-rec"}), (
            "the records are the deliveries in the order they started, and they are "
            "%r" % (send.records(),))
        assert [list(record) for record in send.records()] == [list(s.HANDSHAKE_KEYS)] * 2, (
            "a record's keys are HANDSHAKE_KEYS' keys in that order: %r"
            % ([list(record) for record in send.records()],))

        pubrel = send.received(stage_01.PUBREC, packet_id, 12)
        assert pubrel == s.write_pubrel(packet_id) == _id_bytes(packet_id), (
            "the answer to a PUBREC is the PUBREL body for that id, and it is %r"
            % (pubrel,))
        assert [record["state"] for record in send.records()] == ["waiting-comp",
                                                                 "waiting-rec"], (
            "the PUBREC moves that record to waiting-comp and leaves the rest: %r"
            % (send.records(),))
        assert tuple(ids.in_flight()) == (packet_id, kept_id), (
            "a PUBREC does not release the id — only the PUBCOMP does: %r"
            % (ids.in_flight(),))

        again = send.received(stage_01.PUBREC, packet_id, 13)
        assert again == pubrel, (
            "a duplicate PUBREC is answered with the same PUBREL again, not with %r"
            % (again,))
        assert send.records() == (
            {"packet_id": packet_id, "message": message, "state": "waiting-comp"},
            {"packet_id": kept_id, "message": kept, "state": "waiting-rec"}), (
            "and a duplicate PUBREC changes nothing else — no second record, no second "
            "id, no second state: %r" % (send.records(),))
        assert tuple(ids.in_flight()) == (packet_id, kept_id), (
            "the duplicate PUBREC did not take or release an id: %r" % (ids.in_flight(),))
        late = send.due(16)
        assert [item[0] for item in late] == [kept_id], (
            "the PUBREL's own deadline restarted at 13, so at 16 only the PUBLISH "
            "from 11 is late and %r are" % ([item[0] for item in late],))
        assert late[0][1] == PUBLISH_AGAIN, (
            "and that one is re-sent as a PUBLISH with DUP and QoS 2: %r" % (late[0],))

        assert send.received(stage_01.PUBCOMP, packet_id, 17) is None, (
            "the PUBCOMP ends the handshake — there is nothing left to write")
        assert tuple(ids.in_flight()) == (kept_id,), (
            "the PUBCOMP is what releases the id, and afterwards %r are in flight"
            % (ids.in_flight(),))
        assert ids.free() == free - 1, (
            "one message is still in flight, so %d ids are free and not %d"
            % (free - 1, ids.free()))
        assert send.records() == (
            {"packet_id": kept_id, "message": kept, "state": "waiting-rec"},), (
            "a released delivery is no longer a record in flight: %r"
            % (send.records(),))

        _refuses(stage_01.ProtocolError, "a PUBREC for an id nobody sent",
                 lambda: send.received(stage_01.PUBREC, 9, 20), names=("9",))
        _refuses(stage_01.ProtocolError, "a PUBCOMP for an id nobody sent",
                 lambda: send.received(stage_01.PUBCOMP, 9, 20), names=("9",))
        _refuses(stage_01.ProtocolError, "a PUBACK, which acknowledges a QoS 1 delivery",
                 lambda: send.received(stage_01.PUBACK, kept_id, 20), names=("4",))
        _refuses(stage_01.ProtocolError, "a PUBREL, which a sender writes and never reads",
                 lambda: send.received(stage_01.PUBREL, kept_id, 20), names=("6",))
        _refuses(stage_01.ProtocolError,
                 "a PUBCOMP for a record that is still waiting for its PUBREC",
                 lambda: send.received(stage_01.PUBCOMP, kept_id, 20),
                 names=("waiting-rec", str(kept_id)))
        _refuses(stage_01.ProtocolError, "an acknowledgement whose kind is not a packet type",
                 lambda: send.received("PUBREC", kept_id, 20), names=("str",))
        _refuses(stage_01.ProtocolError, "an acknowledgement for an id that is not an id",
                 lambda: send.received(stage_01.PUBREC, 0, 20), names=("0",))
        _refuses(stage_01.ProtocolError,
                 "an acknowledgement arriving at a tick that is not a count",
                 lambda: send.received(stage_01.PUBREC, kept_id, "20"), names=("str",))
        _refuses(stage_01.ProtocolError, "a message that is not a QoS 2 publish",
                 lambda: send.start(_message("a/b", b"x", qos=1), 20), names=("1",))
        _refuses(stage_01.ProtocolError, "a message with no retain flag in it",
                 lambda: send.start({"topic": "a/b", "payload": b"x", "qos": 2,
                                     "packet_id": None, "dup": False}, 20),
                 names=("retain",))
        _refuses(stage_01.ProtocolError, "a message whose retain flag is not a flag",
                 lambda: send.start(dict(_message("a/b", b"x"), retain="yes"), 20),
                 names=("retain",))
        _refuses(stage_01.ProtocolError, "a PUBLISH sent at a tick that is not a count",
                 lambda: send.start(_message("a/b", b"x"), "20"), names=("str",))
        _refuses(stage_01.ProtocolError, "a PUBLISH sent at a tick below zero",
                 lambda: send.start(_message("a/b", b"x"), -1), names=("-1",))
        assert tuple(ids.in_flight()) == (kept_id,), (
            "a refused start spends no id: %r" % (ids.in_flight(),))
        assert ids.free() == free - 1, (
            "a refused start leaves the id space alone: %d free, not %d"
            % (free - 1, ids.free()))
        _refuses(stage_01.ProtocolError, "a sender built on something that is not a PacketIds",
                 lambda: s.Sender((1, 2, 3)), names=("tuple",))

    def _due(s, stage_01, stage_05, stage_06):
        ids = stage_06.PacketIds()
        send = s.Sender(ids)
        first, first_body = send.start(_message("a/b", b"one"), 0)
        second, second_body = send.start(_message("c/d", b"two"), 0)
        assert send.due(3) == (), (
            "three ticks into a deadline of four, nothing is late, and the answer was "
            "%r" % (send.due(3),))
        assert send.due(3, 4) == (), (
            "and the same is true when the deadline is said out loud: %r"
            % (send.due(3, 4),))
        late = send.due(4)
        assert [item[0] for item in late] == [first, second], (
            "at the deadline both records come back, in the order they started: %r"
            % (late,))
        assert [item[1] for item in late] == [PUBLISH_AGAIN, PUBLISH_AGAIN], (
            "a re-sent PUBLISH carries DUP with QoS 2 (0b1100), and these carry %r"
            % ([item[1] for item in late],))
        assert [item[2] for item in late] == [first_body, second_body], (
            "each re-sent body is the body of its own message under its own id: %r"
            % ([item[2] for item in late],))
        wanted = ({"topic": "a/b", "payload": b"one", "qos": 2, "packet_id": first,
                   "retain": False, "dup": True},
                  {"topic": "c/d", "payload": b"two", "qos": 2, "packet_id": second,
                   "retain": False, "dup": True})
        for item, want in zip(late, wanted):
            back, end = stage_05.read_publish(item[2], flags=item[1])
            assert back == want, (
                "read with the flags it comes with, the re-sent PUBLISH is the same "
                "message marked as a re-send, and it reads back as %r" % (back,))
            assert end == len(item[2]), (
                "the re-sent body ends where the reader says it does: %r of %d"
                % (end, len(item[2])))

        assert send.received(stage_01.PUBREC, second, 4) == s.write_pubrel(second), (
            "the second record is moved along before its own deadline")
        assert send.due(4) == (), (
            "the deadline restarted at the re-send, so the same tick answers nothing "
            "twice: %r" % (send.due(4),))
        assert send.due(7) == (), (
            "and one tick short of the next deadline it is still quiet: %r"
            % (send.due(7),))
        late = send.due(8)
        assert [item[0] for item in late] == [first, second], (
            "a record in waiting-comp is re-sent too, in the same order: %r" % (late,))
        assert late[0][1] == PUBLISH_AGAIN, (
            "the PUBLISH re-send still carries DUP and QoS 2: %r" % (late[0][1],))
        assert late[1] == (second, PUBREL_AGAIN, s.write_pubrel(second)), (
            "and the PUBREL re-send carries exactly PUBREL_FLAGS, no DUP: %r"
            % (late[1],))
        assert late[1][1] == 0b0010, (
            "a re-sent PUBREL keeps the reserved nibble 0b0010, and this one has %r"
            % (late[1][1],))
        assert tuple(ids.in_flight()) == (first, second), (
            "a re-send neither releases an id nor takes another: %r" % (ids.in_flight(),))
        assert [(record["packet_id"], record["state"]) for record in send.records()] == [
            (first, "waiting-rec"), (second, "waiting-comp")], (
            "and it does not change what is in flight: %r" % (send.records(),))

        fresh = s.Sender(stage_06.PacketIds())
        only, only_body = fresh.start(_message("e/f", b"three"), 10)
        assert fresh.due(10, 1) == (), (
            "a deadline of one tick has not passed on the tick the message was sent: "
            "%r" % (fresh.due(10, 1),))
        assert fresh.due(11, 1) == ((only, PUBLISH_AGAIN, only_body),), (
            "one tick later it has, and the answer is the whole triple: %r"
            % (fresh.due(11, 1),))
        _refuses(stage_01.ProtocolError, "a deadline of zero ticks",
                 lambda: fresh.due(11, 0), names=("0",))
        _refuses(stage_01.ProtocolError, "a tick that is not a count",
                 lambda: fresh.due("11", 1), names=("str",))
        _refuses(stage_01.ProtocolError, "a tick below zero",
                 lambda: fresh.due(-1, 1), names=("-1",))

    def _receiver(s, stage_01):
        recv = s.Receiver()
        assert recv.held() == 0, (
            "a new receiver holds nothing, and this one holds %r" % (recv.held(),))
        first = _message("a/b", b"once", packet_id=7)
        body, delivered = recv.took(first)
        assert body == s.write_pubrec(7) == b"\x00\x07", (
            "the answer to a PUBLISH is the PUBREC body for its id, and it is %r"
            % (body,))
        assert delivered is None, (
            "a PUBLISH delivers nothing at all — the PUBREL is what delivers, and this "
            "one delivered %r" % (delivered,))
        assert recv.held() == 1, "the id is held after the PUBLISH: %r" % (recv.held(),)

        body, delivered = recv.took(_message("a/b", b"twice", packet_id=7))
        assert body == b"\x00\x07", (
            "a re-sent PUBLISH for an id already held is acknowledged again, and the "
            "answer was %r" % (body,))
        assert delivered is None, (
            "and it delivers nothing either: %r" % (delivered,))
        assert recv.held() == 1, (
            "the id is held once, however many times the PUBLISH arrives: %r"
            % (recv.held(),))
        comp, message = recv.released(7)
        assert comp == s.write_pubcomp(7) == b"\x00\x07", (
            "the answer to a PUBREL is the PUBCOMP body for that id, and it is %r"
            % (comp,))
        assert message == first, (
            "the message delivered is the first one held, not the re-send's: %r"
            % (message,))
        assert recv.held() == 0, (
            "the released id is no longer held: %r" % (recv.held(),))
        comp, message = recv.released(7)
        assert (comp, message) == (b"\x00\x07", None), (
            "a second PUBREL for the same id is answered with another PUBCOMP and "
            "delivers nothing: %r" % ((comp, message),))
        assert recv.released(9) == (_id_bytes(9), None), (
            "and a PUBREL for an id this receiver never held is answered the same way, "
            "not refused: %r" % (recv.released(9),))

        recv.took(_message("c/d", b"two", packet_id=3))
        recv.took(_message("e/f", b"three", packet_id=5))
        assert recv.held() == 2, (
            "two ids are held and the count says %r" % (recv.held(),))
        assert recv.released(3)[1] == _message("c/d", b"two", packet_id=3), (
            "each id delivers its own message")
        assert recv.held() == 1, (
            "and the count follows: %r" % (recv.held(),))

        _refuses(stage_01.ProtocolError, "a PUBREL for an id of 0",
                 lambda: recv.released(0), names=("0",))
        _refuses(stage_01.ProtocolError, "a PUBREL for an id below the range",
                 lambda: recv.released(-1), names=("-1",))
        _refuses(stage_01.ProtocolError, "a PUBREL for an id above 65_535",
                 lambda: recv.released(HIGH_ID + 1), names=("65536",))
        _refuses(stage_01.ProtocolError, "a PUBREL for a bool id",
                 lambda: recv.released(True), names=("bool",))
        _refuses(stage_01.ProtocolError, "a QoS 1 publish, which has no handshake",
                 lambda: recv.took(_message("a/b", b"x", qos=1, packet_id=4)),
                 names=("1",))
        _refuses(stage_01.ProtocolError, "a QoS 0 publish, which carries no id",
                 lambda: recv.took(_message("a/b", b"x", qos=0)), names=("0",))
        _refuses(stage_01.ProtocolError, "a QoS 2 publish whose id is not an id",
                 lambda: recv.took(_message("a/b", b"x", packet_id=0)),
                 names=("0", "PUBLISH id"))
        _refuses(stage_01.ProtocolError, "a dish handed over as a message",
                 lambda: recv.took("a publish"), names=("str",))

    def _handshake(s, stage_01, stage_06):
        """One whole four-way handshake, as the list of every value it produced."""
        ids = stage_06.PacketIds()
        send = s.Sender(ids)
        recv = s.Receiver()
        seen = []
        tick = 0
        for topic, payload in (("a/b", b"one"), ("c/d", b"two")):
            tick += 1
            packet_id, body = send.start(_message(topic, payload), tick)
            seen.append(("start", packet_id, body))
            seen.append(("took", recv.took(_message(topic, payload, packet_id=packet_id))))
            tick += 1
            seen.append(("received", send.received(stage_01.PUBREC, packet_id, tick)))
            tick += 5
            seen.append(("due", send.due(tick)))
            tick += 1
            seen.append(("released", recv.released(packet_id)))
            seen.append(("received", send.received(stage_01.PUBCOMP, packet_id, tick)))
            seen.append(("records", send.records()))
        seen.append(("held", recv.held()))
        seen.append(("in-flight", tuple(ids.in_flight())))
        seen.append(("free", ids.free()))
        return tuple(seen)

    def _twice(s, stage_01, stage_06):
        one = _handshake(s, stage_01, stage_06)
        two = _handshake(s, stage_01, stage_06)
        assert one == two, (
            "the same handshake run twice gives two different answers — the ids, the "
            "bytes and the records all have to follow from the fixture: %r vs %r"
            % (one, two))

    import stage_01
    import stage_05
    import stage_06
    import stage_07 as s
    _constants(s, stage_01)
    _writers(s, stage_01)
    _sender(s, stage_01, stage_05, stage_06)
    _due(s, stage_01, stage_05, stage_06)
    _receiver(s, stage_01)
    _twice(s, stage_01, stage_06)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "mqtt-broker-from-scratch"

    DEADLINES = ((0, 0), (1, 1), (2, 3), (3, 4), (4, 6), (5, 7), (6, 9), (7, 10),
                 (9, 13), (10, 15), (100, 150), (65_535, 98_302))

    WILL = {"topic": "clients/gone", "payload": b"bye", "qos": 1, "retain": False}

    OTHER_WILL = {"topic": "clients/gone-too", "payload": b"so long",
                  "qos": 2, "retain": True}

    def _repo(start=None):
        for candidate_start in (os.environ.get("L3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _string(text):
        payload = text.encode("utf-8")
        return bytes([len(payload) >> 8, len(payload) & 0xFF]) + payload

    def _payload(data):
        return bytes([len(data) >> 8, len(data) & 0xFF]) + data

    def _body(client_id, clean_start=0, keep_alive=0, will=None, username=None,
              password=None):
        """A CONNECT's body, as the wire writes it: stage 2 is the reader."""
        flags = 0
        if will is not None:
            flags |= 0b0000_0100 | ((will["qos"] & 0b11) << 3)
            if will["retain"]:
                flags |= 0b0010_0000
        if clean_start:
            flags |= 0b0000_0010
        if username is not None:
            flags |= 0b1000_0000
        if password is not None:
            flags |= 0b0100_0000
        body = b"\x00\x04MQTT\x04" + bytes([flags])
        body += bytes([keep_alive >> 8, keep_alive & 0xFF])
        body += _string(client_id)
        if will is not None:
            body += _string(will["topic"]) + _payload(will["payload"])
        if username is not None:
            body += _string(username)
        if password is not None:
            body += _payload(password)
        return body

    def _connect(stage_02, client_id, clean_start=0, keep_alive=0, will=None,
                 username=None, password=None):
        """The CONNECT a broker really gets: stage 2's reader over real bytes."""
        body = _body(client_id, clean_start, keep_alive, will, username, password)
        connect, pos = stage_02.read_connect(body)
        assert pos == len(body), (
            "the fixture's CONNECT of %d bytes was read to %d"
            % (len(body), pos))
        return connect

    def _broker(streams, clients):
        """A real transport, a listener, and one open stream per name asked for."""
        transport = streams.Transport({"backlog": 16})
        transport.listen("broker")
        return transport, [transport.connect(name, "broker") for name in clients]

    def _publish(topic, payload, qos, packet_id=None):
        return {"topic": topic, "payload": payload, "qos": qos,
                "packet_id": packet_id, "retain": False, "dup": False}

    def _constants(s):
        assert tuple(s.SESSION_KEYS) == ("client_id", "clean_start", "keep_alive",
                                         "will", "stream", "subscriptions",
                                         "pending", "queue", "started_at",
                                         "last_seen"), (
            "a session record carries ten fields in the order the stage declares "
            "them, and SESSION_KEYS is %r" % (s.SESSION_KEYS,))
        assert s.QUEUE_MAX == 8, (
            "a queue holds QUEUE_MAX = 8 messages, and the constant is %r"
            % (s.QUEUE_MAX,))
        assert s.KEEP_ALIVE_NUMERATOR == 3, (
            "the margin is three halves of the keep-alive, and the numerator is %r"
            % (s.KEEP_ALIVE_NUMERATOR,))
        assert s.KEEP_ALIVE_DENOMINATOR == 2, (
            "the margin is three halves of the keep-alive, and the denominator is %r"
            % (s.KEEP_ALIVE_DENOMINATOR,))

    def _deadline(s, stage_01):
        for keep_alive, want in DEADLINES:
            got = s.deadline_from(keep_alive)
            assert got == want, (
                "a keep-alive of %d lets a client be silent for %d ticks, and the "
                "stage says %r" % (keep_alive, want, got))
        assert s.deadline_from(2) == 3, (
            "the half first bites at 2 — 2 + 1 —, so a reader that ignores it is "
            "wrong from here on: %r" % (s.deadline_from(2),))
        assert s.deadline_from(0) == 0, (
            "a client that asked for no keep-alive has a deadline of 0: %r"
            % (s.deadline_from(0),))
        _refuses(stage_01.ProtocolError, "a negative keep-alive",
                 lambda: s.deadline_from(-1), names=("-1",))
        _refuses(stage_01.ProtocolError, "a bool for a keep-alive",
                 lambda: s.deadline_from(True), names=("bool",))
        _refuses(stage_01.ProtocolError, "a str for a keep-alive",
                 lambda: s.deadline_from("4"), names=("str",))

    def _record(s, streams, stage_02, stage_01):
        transport, (one,) = _broker(streams, ["c1"])
        tick = transport.step()
        held = s.Sessions()
        connect = _connect(stage_02, "c1", clean_start=1, keep_alive=4, will=WILL)
        session, present = held.attach(connect, one.id, tick)
        assert present == 0, (
            "a clean start resumes nothing, so the present flag is 0, and it was %r"
            % (present,))
        assert list(session) == list(s.SESSION_KEYS), (
            "a session's keys are SESSION_KEYS in that order: %r" % (list(session),))
        assert session["client_id"] == "c1", (
            "the record belongs to the client that connected: %r" % (session,))
        assert session["clean_start"] is True, (
            "this connection began clean, and the record says %r"
            % (session["clean_start"],))
        assert session["keep_alive"] == 4, (
            "the record's keep-alive is the one this CONNECT asked for: %r"
            % (session["keep_alive"],))
        assert session["will"] == WILL, (
            "the CONNECT carried a will and the session records it: %r"
            % (session["will"],))
        assert session["stream"] == one.id, (
            "the record is on the stream the transport handed out (%r) and it says "
            "%r" % (one.id, session["stream"]))
        assert session["subscriptions"] == {} and isinstance(
            session["subscriptions"], dict), (
            "a session that begins now has no subscriptions: %r"
            % (session["subscriptions"],))
        assert session["pending"] == 0, (
            "nothing has been dropped for a session that has held nothing: %r"
            % (session["pending"],))
        assert session["queue"] == [] and isinstance(session["queue"], list), (
            "a session that begins now has queued nothing: %r" % (session["queue"],))
        assert session["started_at"] == tick == transport.tick(), (
            "the session began at the tick the transport is on (%r): %r"
            % (transport.tick(), session))
        assert session["last_seen"] == tick, (
            "and its client last spoke at the CONNECT: %r" % (session,))
        assert held.sessions() == (session,), (
            "the one client attached is the one session held: %r"
            % (held.sessions(),))
        assert held.sessions()[0] is session, (
            "the table hands the record it holds and not a copy of it, because the "
            "broker writes its subscriptions into that very dict: %r"
            % (held.sessions()[0],))
        assert [record["stream"] for record in held.sessions()] == [
            stream.id for stream in transport.streams()], (
            "the sessions are on the streams the transport itself opened: %r vs %r"
            % ([record["stream"] for record in held.sessions()],
               [stream.id for stream in transport.streams()]))

    def _resume(s, streams, stage_02, stage_01):
        transport, (one, two) = _broker(streams, ["c1", "c2"])
        first_tick = transport.step()
        held = s.Sessions()
        session, present = held.attach(
            _connect(stage_02, "c1", clean_start=1, keep_alive=4, username="diego",
                     password=b"hunter2"), one.id, first_tick)
        assert present == 0, "c1 begins clean: %r" % (present,)
        later, other = held.attach(
            _connect(stage_02, "c2", clean_start=0, keep_alive=2), two.id, first_tick)
        assert other == 0, (
            "a clean start of 0 with nothing held begins a session and says 0: %r"
            % (other,))
        assert later["clean_start"] is False, (
            "c2 asked for no clean start and the new record says %r, so the field is "
            "this connection's and not a constant" % (later["clean_start"],))
        session["subscriptions"]["sport/#"] = 1
        session["subscriptions"]["news/+"] = 2
        queued = [_publish("sport/%d" % (index,), bytes([index]), 1, index + 1)
                  for index in range(2)]
        for message in queued:
            assert held.queue_for("c1", message) is True, (
                "a QoS 1 message for a client that is away is kept: %r" % (message,))
        away = transport.step()
        assert held.detach("c1", streams.CUT, away) is None, (
            "c1's CONNECT carried no will, so the end owes nothing")
        assert held.sessions()[0]["stream"] is None, (
            "a detached session is on no stream, and the record says %r"
            % (held.sessions()[0]["stream"],))
        assert tuple(record["client_id"] for record in held.sessions()) == ("c1", "c2"), (
            "the table is in the order its clients attached: %r"
            % ([record["client_id"] for record in held.sessions()],))
        back = transport.step(3)
        again = transport.connect("c1", "broker")
        resumed, present = held.attach(
            _connect(stage_02, "c1", clean_start=0, keep_alive=10), again.id, back)
        assert present == 1, (
            "a clean start of 0 over a session the broker holds resumes it, so the "
            "present flag is 1, and it was %r" % (present,))
        assert resumed["subscriptions"] == {"sport/#": 1, "news/+": 2}, (
            "a resumed session's subscriptions are in force before the next "
            "SUBSCRIBE, and the record holds %r" % (resumed["subscriptions"],))
        assert resumed is held.sessions()[0], (
            "the resumed session is the record the table holds and not a copy of "
            "it: %r" % (resumed,))
        assert resumed["queue"] == queued, (
            "the messages queued for the away client are handed back oldest first: "
            "%r vs %r" % (resumed["queue"], queued))
        assert resumed["pending"] == 0, (
            "nothing was dropped for wanting room, and the count says %r"
            % (resumed["pending"],))
        assert resumed["started_at"] == first_tick, (
            "the session began at the tick it was first attached (%r) and it says %r"
            % (first_tick, resumed["started_at"]))
        assert resumed["last_seen"] == back, (
            "this connection spoke at %r, so that is the session's last_seen: %r"
            % (back, resumed["last_seen"]))
        assert resumed["keep_alive"] == 10 and resumed["clean_start"] is False, (
            "the keep-alive and the clean start are this connection's promises, and "
            "the record says %r and %r"
            % (resumed["keep_alive"], resumed["clean_start"]))
        assert resumed["stream"] == again.id, (
            "the resumed session is on the new stream the transport opened (%r): %r"
            % (again.id, resumed["stream"]))
        assert resumed["will"] is None, (
            "this CONNECT carried no will, so this connection owes none: %r"
            % (resumed["will"],))
        assert tuple(record["client_id"] for record in held.sessions()) == ("c1", "c2"), (
            "a resume is the same session and keeps its place: %r"
            % ([record["client_id"] for record in held.sessions()],))
        taken = held.take_queued("c1")
        assert taken == queued, (
            "take_queued hands back what was waiting, oldest first: %r vs %r"
            % (taken, queued))
        assert held.sessions()[0]["queue"] == [], (
            "and hands it back once — the queue is left empty: %r"
            % (held.sessions()[0]["queue"],))
        resumed["subscriptions"]["pool/+"] = 0
        assert held.detach("c1", streams.CLOSED, back) is None, (
            "a clean end owes nothing")
        late = transport.step(2)
        last = transport.connect("c1", "broker")
        third, present = held.attach(
            _connect(stage_02, "c1", clean_start=0, keep_alive=4), last.id, late)
        assert present == 1, "the session is still held: %r" % (present,)
        assert third["subscriptions"] == {"sport/#": 1, "news/+": 2, "pool/+": 0}, (
            "the subscriptions written into the handed-back record are the table's "
            "own, so a second resume still has them: %r" % (third["subscriptions"],))
        assert third["queue"] == [], (
            "what was taken is not handed out twice: %r" % (third["queue"],))
        assert third["started_at"] == first_tick, (
            "the session still began at %r and it says %r"
            % (first_tick, third["started_at"]))
        fresh = transport.step()
        newest = transport.connect("c1", "broker")
        replaced, present = held.attach(
            _connect(stage_02, "c1", clean_start=1, keep_alive=4, will=OTHER_WILL),
            newest.id, fresh)
        assert present == 0, (
            "a clean start says 0 even when the broker holds the client's session: "
            "%r" % (present,))
        assert list(replaced) == list(s.SESSION_KEYS), (
            "the new session is a record like any other: %r" % (list(replaced),))
        assert replaced["subscriptions"] == {}, (
            "a clean start throws the old subscriptions away: %r"
            % (replaced["subscriptions"],))
        assert replaced["queue"] == [] and replaced["pending"] == 0, (
            "and everything else the old session held: %r, %r"
            % (replaced["queue"], replaced["pending"]))
        assert replaced["will"] == OTHER_WILL and replaced["stream"] == newest.id, (
            "the new session records this connection's will and stream: %r"
            % (replaced,))
        assert replaced["started_at"] == fresh == replaced["last_seen"], (
            "a session that begins now began now: %r" % (replaced,))
        assert tuple(record["client_id"] for record in held.sessions()) == ("c2", "c1"), (
            "a clean start is a new session and appears where it was attached: %r"
            % ([record["client_id"] for record in held.sessions()],))
        assert held.sessions()[1] == replaced and len(held.sessions()) == 2, (
            "the old record is gone rather than kept beside the new one: %r"
            % (held.sessions(),))

    def _touch(s, streams, stage_02, stage_01):
        transport, (one,) = _broker(streams, ["c1"])
        began = transport.step()
        held = s.Sessions()
        session, present = held.attach(
            _connect(stage_02, "c1", clean_start=1, keep_alive=4, will=WILL),
            one.id, began)
        before = dict(session)
        spoke = transport.step(3)
        touched = held.touch("c1", spoke)
        assert touched == session, (
            "touch answers the session it moved, and it answered %r" % (touched,))
        assert touched["last_seen"] == spoke, (
            "the client spoke at %r and the session says %r"
            % (spoke, touched["last_seen"]))
        assert {key: value for key, value in touched.items() if key != "last_seen"} == {
            key: value for key, value in before.items() if key != "last_seen"}, (
            "touch moves `last_seen` and one field only; the record went from %r to "
            "%r" % (before, touched))
        assert held.sessions()[0]["last_seen"] == spoke, (
            "the session the table holds is the one that moved, not a copy: %r"
            % (held.sessions()[0]["last_seen"],))
        stranger = held.touch("nobody", spoke)
        assert stranger is None, (
            "a client this table has never met has no session to touch: %r"
            % (stranger,))
        _refuses(stage_01.ProtocolError, "a client named by an int",
                 lambda: held.touch(7, spoke), names=("str",))
        _refuses(stage_01.ProtocolError, "a bool tick",
                 lambda: held.touch("c1", True), names=("bool",))
        _refuses(stage_01.ProtocolError, "a tick before the clock started",
                 lambda: held.touch("c1", -1), names=("-1",))
        _refuses(stage_01.ProtocolError, "a str tick",
                 lambda: held.touch("c1", "3"), names=("str",))

    def _expired(s, streams, stage_02, stage_01):
        transport, (one, two, three) = _broker(streams, ["b1", "a1", "c3"])
        began = transport.step()
        held = s.Sessions()
        held.attach(_connect(stage_02, "b1", clean_start=1, keep_alive=2, will=WILL),
                    one.id, began)
        held.attach(_connect(stage_02, "a1", clean_start=1, keep_alive=2), two.id,
                    began)
        held.attach(_connect(stage_02, "c3", clean_start=1, keep_alive=0), three.id,
                    began)
        assert held.expired(began) == (), (
            "a client that has just connected has been silent for no ticks at all: %r"
            % (held.expired(began),))
        assert held.expired(began + 2) == (), (
            "a keep-alive of 2 is a deadline of 3, and two ticks is not three: %r"
            % (held.expired(began + 2),))
        assert held.expired(began + 3) == ("b1", "a1"), (
            "silence for exactly the deadline ends the session, both are due at %r, "
            "and the answers come in attach order and not in any sorted one: %r"
            % (began + 3, held.expired(began + 3)))
        held.touch("a1", began + 4)
        assert held.expired(began + 6) == ("b1",), (
            "a client that has spoken is not named: a1 spoke at %r and its deadline "
            "is three, and the stage names %r"
            % (began + 4, held.expired(began + 6)))
        assert held.expired(began + 7) == ("b1", "a1"), (
            "three ticks after a1 spoke it is due again, and at %r the stage names %r"
            % (began + 7, held.expired(began + 7)))
        assert held.expired(began + 200) == ("b1", "a1"), (
            "a keep-alive of 0 is no keep-alive at all, so c3 is never named however "
            "long it is quiet: %r" % (held.expired(began + 200),))
        _refuses(stage_01.ProtocolError, "an expiry for a client that has spoken",
                 lambda: held.detach("a1", "expired", began + 6),
                 names=("a1", str(began + 4), "3", str(began + 6)))
        assert held.sessions()[1]["stream"] == two.id, (
            "a refused end does not end anything, and the session is still on %r"
            % (held.sessions()[1]["stream"],))
        _refuses(stage_01.ProtocolError, "an expiry for a client with no keep-alive",
                 lambda: held.detach("c3", "expired", began + 200), names=("c3",))
        fell = held.detach("b1", "expired", began + 3)
        assert fell == WILL, (
            "a keep-alive that really ran out is an abnormal end, so b1's will is "
            "owed, and the end handed back %r" % (fell,))
        again_fell = held.detach("b1", "expired", began + 3)
        assert again_fell is None, (
            "and it is owed once: a second end cannot hand it back again: %r"
            % (again_fell,))
        assert held.expired(began + 200) == ("a1",), (
            "the session that ended is not waiting for anything and is not named "
            "again: %r" % (held.expired(began + 200),))
        _refuses(stage_01.ProtocolError, "a bool expiry tick",
                 lambda: held.expired(True), names=("bool",))
        _refuses(stage_01.ProtocolError, "an expiry tick before the clock started",
                 lambda: held.expired(-1), names=("-1",))

    def _will(s, streams, stage_02, stage_01):
        transport, (one,) = _broker(streams, ["c1"])
        began = transport.step()
        held = s.Sessions()
        session, present = held.attach(
            _connect(stage_02, "c1", clean_start=1, keep_alive=4, will=WILL),
            one.id, began)
        assert session["will"] == WILL, (
            "the session holds the will this CONNECT asked for: %r" % (session,))
        transport.cut(one, "the client vanished")
        ended = transport.step()
        owed = held.detach("c1", streams.CUT, ended)
        assert owed == WILL, (
            "a cut is an end nobody agreed to, and the will is owed: %r" % (owed,))
        assert held.sessions()[0]["will"] is None, (
            "the will leaves the session as it is handed over, so nothing stale can "
            "fire later: %r" % (held.sessions()[0],))
        assert held.sessions()[0]["stream"] is None, (
            "and the session has outlived its socket: %r" % (held.sessions()[0],))
        again_owed = held.detach("c1", streams.CUT, ended)
        assert again_owed is None, (
            "a second abnormal end owes nothing: %r" % (again_owed,))
        stranger = held.detach("nobody", streams.CUT, ended)
        assert stranger is None, (
            "a client this table has never met has no will at all: %r" % (stranger,))
        stranger_closed = held.detach("nobody", streams.CLOSED, ended)
        assert stranger_closed is None, (
            "and no end of any kind owes one: %r" % (stranger_closed,))
        back = transport.step(2)
        again = transport.connect("c1", "broker")
        resumed, present = held.attach(
            _connect(stage_02, "c1", clean_start=0, keep_alive=4, will=WILL),
            again.id, back)
        assert present == 1 and resumed["will"] == WILL, (
            "a new connection brings its own will, and the table holds %r"
            % (resumed["will"],))
        goodbye = held.detach("c1", streams.CLOSED, back)
        assert goodbye is None, (
            "a client that says goodbye properly is owed no will: %r" % (goodbye,))
        assert held.sessions()[0]["will"] is None, (
            "and a clean end clears it just as firmly, so nothing is left to fire: "
            "%r" % (held.sessions()[0],))
        stale = held.detach("c1", streams.CUT, back)
        assert stale is None, (
            "a later abnormal end cannot fire a promise that is already paid: %r"
            % (stale,))
        _refuses(stage_01.ProtocolError, "an end this stage cannot mean",
                 lambda: held.detach("c1", "lost", back), names=("lost",))
        _refuses(stage_01.ProtocolError, "an end with no reason at all",
                 lambda: held.detach("c1", None, back), names=("None",))
        _refuses(stage_01.ProtocolError, "a client named by a list",
                 lambda: held.detach([], streams.CUT, back), names=("str",))

    def _queue(s, streams, stage_02, stage_01):
        transport, (one,) = _broker(streams, ["c1"])
        began = transport.step()
        held = s.Sessions()
        session, present = held.attach(
            _connect(stage_02, "c1", clean_start=1, keep_alive=4), one.id, began)
        held.detach("c1", streams.CUT, began)
        live = _publish("sport/live", b"now", 0)
        live_queued = held.queue_for("c1", live)
        assert live_queued is False, (
            "a QoS 0 message is never queued — it was never promised — and the stage "
            "answered %r" % (live_queued,))
        assert held.sessions()[0]["queue"] == [], (
            "so nothing is in the queue: %r" % (held.sessions()[0]["queue"],))
        assert held.sessions()[0]["pending"] == 0, (
            "and a message that was never queueable is not a message that was "
            "dropped: %r" % (held.sessions()[0]["pending"],))
        kept = [_publish("sport/%d" % (index,), bytes([index]), 1, index + 1)
                for index in range(s.QUEUE_MAX)]
        for message in kept:
            assert held.queue_for("c1", message) is True, (
                "a session holds its first %d messages and refused %r"
                % (s.QUEUE_MAX, message))
        assert held.sessions()[0]["queue"] == kept, (
            "the queue holds what was queued, oldest first: %r vs %r"
            % (held.sessions()[0]["queue"], kept))
        assert held.sessions()[0]["pending"] == 0, (
            "nothing has been dropped yet: %r" % (held.sessions()[0]["pending"],))
        over = [_publish("sport/over%d" % (index,), b"late", 2, 100 + index)
                for index in range(3)]
        for message in over:
            assert held.queue_for("c1", message) is False, (
                "a full queue refuses the message that has just arrived: %r"
                % (message,))
        assert held.sessions()[0]["pending"] == 3, (
            "the newest is dropped *and counted*: three were dropped and the count "
            "says %r" % (held.sessions()[0]["pending"],))
        assert held.sessions()[0]["queue"] == kept, (
            "and nothing that was already waiting is lost: %r vs %r"
            % (held.sessions()[0]["queue"], kept))
        assert held.queue_for("c1", live) is False, (
            "QoS 0 is refused for what it is, not for want of room")
        assert held.sessions()[0]["pending"] == 3, (
            "so it does not move the count: %r" % (held.sessions()[0]["pending"],))
        taken = held.take_queued("c1")
        assert taken == kept, (
            "take_queued hands the messages over oldest first: %r vs %r"
            % (taken, kept))
        assert held.sessions()[0]["queue"] == [], (
            "and clears the queue: %r" % (held.sessions()[0]["queue"],))
        assert held.sessions()[0]["pending"] == 3, (
            "`pending` counts what was dropped, not what was taken: %r"
            % (held.sessions()[0]["pending"],))
        nothing = held.take_queued("c1")
        assert nothing == [], (
            "a second take has nothing to hand over: %r" % (nothing,))
        nowhere = held.queue_for("nobody", kept[0])
        assert nowhere is False, (
            "there is nowhere to queue a message for a client with no session: %r"
            % (nowhere,))
        empty = held.take_queued("nobody")
        assert empty == [], (
            "and a client with no session has queued nothing: %r" % (empty,))
        _refuses(stage_01.ProtocolError, "a publish with no QoS in it",
                 lambda: held.queue_for("c1", {"topic": "sport/1"}),
                 names=("qos",))
        _refuses(stage_01.ProtocolError, "a QoS this course cannot mean",
                 lambda: held.queue_for("c1", _publish("sport/1", b"x", 3)),
                 names=("3",))
        _refuses(stage_01.ProtocolError, "a publish that is not a dict",
                 lambda: held.queue_for("c1", b"sport/1"), names=("bytes",))
        _refuses(stage_01.ProtocolError, "a client named by an int",
                 lambda: held.queue_for(7, kept[0]), names=("str",))
        _refuses(stage_01.ProtocolError, "a client named by an int",
                 lambda: held.take_queued(7), names=("str",))

    def _stream(s, streams, stage_02, stage_01):
        transport, (one,) = _broker(streams, ["c1"])
        held = s.Sessions()
        connect = _connect(stage_02, "c1", clean_start=1, keep_alive=4)
        attached, present = held.attach(connect, one.id, transport.step())
        assert attached["stream"] == one.id, (
            "the attach is handed the id the transport opened: %r" % (one.id,))
        _refuses(stage_01.ProtocolError, "a stream named by a str",
                 lambda: held.attach(connect, "1", 1), names=("'1'",))
        _refuses(stage_01.ProtocolError, "a bool for a stream",
                 lambda: held.attach(connect, True, 1), names=("True",))
        _refuses(stage_01.ProtocolError, "a stream id of 0",
                 lambda: held.attach(connect, 0, 1), names=("0",))
        _refuses(stage_01.ProtocolError, "a CONNECT that is not a dict",
                 lambda: held.attach("connect", one.id, 1), names=("str",))
        short = dict(connect)
        del short["client_id"]
        _refuses(stage_01.ProtocolError, "a CONNECT with a field missing",
                 lambda: held.attach(short, one.id, 1), names=("client_id",))
        assert len(held.sessions()) == 1, (
            "a refused attach attaches nothing: %r" % (held.sessions(),))

    def _twice(s, streams, stage_02):
        def scenario():
            transport, (one, two) = _broker(streams, ["c1", "c2"])
            held = s.Sessions()
            began = transport.step()
            first, present = held.attach(
                _connect(stage_02, "c1", clean_start=1, keep_alive=4, will=WILL),
                one.id, began)
            other, other_present = held.attach(
                _connect(stage_02, "c2", clean_start=0, keep_alive=2, will=OTHER_WILL),
                two.id, began)
            first["subscriptions"]["sport/#"] = 1
            kept = [_publish("sport/%d" % (index,), bytes([index]), 1, index + 1)
                    for index in range(s.QUEUE_MAX + 2)]
            queued = [held.queue_for("c1", message) for message in kept]
            end = held.detach("c1", streams.CUT, began)
            spoke = transport.step(2)
            held.touch("c2", spoke)
            due = held.expired(spoke)
            closed = held.detach("c2", streams.CLOSED, spoke)
            return {"present": (present, other_present),
                    "sessions": [dict(record) for record in held.sessions()],
                    "queued": queued,
                    "will": end,
                    "other": other["client_id"],
                    "closed": closed,
                    "due": due,
                    "taken": held.take_queued("c1"),
                    "stats": transport.stats()}

        one = scenario()
        two = scenario()
        assert one == two, (
            "two runs of one fixture are the same bytes and the same records, and "
            "they differ: %r vs %r" % (one, two))

    import stage_01
    import stage_02
    import streams
    import stage_08 as s
    _constants(s)
    _deadline(s, stage_01)
    _record(s, streams, stage_02, stage_01)
    _resume(s, streams, stage_02, stage_01)
    _touch(s, streams, stage_02, stage_01)
    _expired(s, streams, stage_02, stage_01)
    _will(s, streams, stage_02, stage_01)
    _queue(s, streams, stage_02, stage_01)
    _stream(s, streams, stage_02, stage_01)
    _twice(s, streams, stage_02)

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "mqtt-broker-from-scratch"

    TOO_LONG = "a" * 65_536

    WALK = (("publish", "a/1", 1), ("publish", "b/1", 2), ("publish", "a/+", 3),
            ("publish", "a", 4), ("subscribe", "a/b", 5), ("subscribe", "a/#", 6),
            ("subscribe", "", 7))

    def _repo(start=None):
        for candidate_start in (os.environ.get("L3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _policy(grants, publish=(), subscribe=(), ceiling_publish=("#",),
                ceiling_subscribe=("#",), who="alice"):
        """One client's grants and the broker's ceiling, as a real `Grants` table."""
        return grants.Grants(
            table={who: {"publish": publish, "subscribe": subscribe}},
            ceiling={"publish": ceiling_publish, "subscribe": ceiling_subscribe})

    def _two(grants):
        """A table where one client's patterns cannot be read and another's can."""
        return grants.Grants(
            table={"carol": {"publish": ("x/#/y",), "subscribe": ("#/x",)},
                   "alice": {"publish": ("a/#",), "subscribe": ("a/#",)}},
            ceiling={"publish": ("#",), "subscribe": ("#",)})

    def _verdict(got, allowed, reason, what):
        """The pair `got` must be, or the mistake named."""
        assert isinstance(got, tuple) and len(got) == 2, (
            "%s answers %r, and a verdict is the pair (allowed, reason)" % (what, got))
        assert isinstance(got[0], bool), (
            "%s answers %r as its allowed, and an allowed is True or False and never a "
            "truthy stand-in" % (what, got[0]))
        assert got == (allowed, reason), (
            "%s answers %r, and this request must be answered (%r, %r)"
            % (what, got, allowed, reason))

    def _constants(s, grants):
        assert tuple(s.DECISION_KEYS) == tuple(grants.DECISION_KEYS), (
            "a decision's six fields are the world's: %r, and the stage says %r"
            % (tuple(grants.DECISION_KEYS), tuple(s.DECISION_KEYS)))
        assert tuple(s.DECISION_KEYS) == ("tick", "client", "action", "topic",
                                          "allowed", "reason"), (
            "the fields are written in this order: %r" % (tuple(s.DECISION_KEYS),))
        assert len(s.DECISION_KEYS) == 6, (
            "a decision has six fields, not %d: %r"
            % (len(s.DECISION_KEYS), tuple(s.DECISION_KEYS)))

    def _reasons(s, grants, stage_03):
        """Every reason code the world names, out of a real table."""
        plain = _policy(grants, publish=("a/#",), subscribe=("a/+",))

        # allowed: the one reason that says yes
        _verdict(s.allowed_publish(plain, "alice", "a/1"), True, "allowed",
                 "a publish the client's grant and the ceiling both reach")
        _verdict(s.allowed_subscribe(plain, "alice", "a/b"), True, "allowed",
                 "a subscribe the client's grant and the ceiling both reach")

        # no-grant: the client's own grant does not reach, however wide the ceiling is
        _verdict(s.allowed_publish(plain, "alice", "b/1"), False, "no-grant",
                 "a publish the ceiling reaches and this client's grant does not")
        _verdict(s.allowed_subscribe(plain, "alice", "a/b/c"), False, "no-grant",
                 "a subscribe the ceiling reaches and this client's grant does not")
        _verdict(s.allowed_publish(plain, "nobody", "a/1"), False, "no-grant",
                 "a client the table never names, whose grants are all empty")

        # ceiling: the client's grant reaches and the broker's own reach ends sooner
        narrow = _policy(grants, publish=("a/#",), subscribe=("a/#",),
                         ceiling_publish=("a/b",), ceiling_subscribe=("a/+",))
        _verdict(s.allowed_publish(narrow, "alice", "a/1"), False, "ceiling",
                 "a publish this client's grant reaches and the ceiling does not")
        _verdict(s.allowed_publish(narrow, "alice", "a/b"), True, "allowed",
                 "the one topic this grant and this ceiling both reach")
        _verdict(s.allowed_publish(narrow, "alice", "a/bc"), False, "ceiling",
                 "a topic a/# reaches and a/b does not, which startswith would pass")
        _verdict(s.allowed_subscribe(narrow, "alice", "a/x"), True, "allowed",
                 "a subscribe this grant and this ceiling both reach")
        _verdict(s.allowed_subscribe(narrow, "alice", "a/x/y"), False, "ceiling",
                 "a subscribe the grant reaches and the ceiling's a/+ does not")
        _verdict(s.allowed_subscribe(narrow, "alice", "a/#"), False, "ceiling",
                 "a subscribe a + can never cover, whatever the grant says")
        _verdict(s.allowed_subscribe(narrow, "alice", "a/b/c"), False, "ceiling",
                 "a subscribe the publish ceiling would reach and the subscribe "
                 "ceiling does not: the ceiling is read for the action asked about")

        # the client's own grant is judged first: a topic neither reaches is no-grant
        _verdict(s.allowed_publish(narrow, "alice", "z/1"), False, "no-grant",
                 "a publish neither this client's grant nor the ceiling reaches")
        _verdict(s.allowed_publish(_policy(grants, publish=("a/c",),
                                           ceiling_publish=("a/b",)),
                                   "alice", "a/b"), False, "no-grant",
                 "a publish the ceiling reaches and this client's grant does not")

        # a grant narrows and never widens: the ceiling # does not lend it reach
        tight = _policy(grants, publish=("a/b",), ceiling_publish=("#",))
        _verdict(s.allowed_publish(tight, "alice", "a/b"), True, "allowed",
                 "the one topic a grant of a/b under a ceiling of # reaches")
        _verdict(s.allowed_publish(tight, "alice", "a/c"), False, "no-grant",
                 "a topic the ceiling's # reaches and the grant of a/b does not")

        # wildcard, empty, and a name that cannot be one: the request's own shape
        _verdict(s.allowed_publish(plain, "alice", "a/+"), False, "wildcard",
                 "a publish topic holding the wildcard +")
        _verdict(s.allowed_publish(plain, "alice", "#"), False, "wildcard",
                 "a publish topic that is the wildcard #")
        _verdict(s.allowed_publish(plain, "alice", ""), False, "empty",
                 "an empty publish topic")
        _verdict(s.allowed_subscribe(plain, "alice", ""), False, "empty",
                 "an empty subscribe filter")
        _verdict(s.allowed_subscribe(plain, "alice", "a/#/b"), False, "malformed",
                 "a subscribe filter whose # is not its last level")
        _verdict(s.allowed_subscribe(plain, "alice", "a/+b"), False, "malformed",
                 "a filter with a wildcard glued to text")
        _verdict(s.allowed_publish(plain, "alice", TOO_LONG), False, "malformed",
                 "a publish topic above the maximum a name may be")
        _verdict(s.allowed_subscribe(plain, "alice", TOO_LONG), False, "malformed",
                 "a subscribe filter above the maximum a name may be")

        # malformed: a pattern in the table that is not a filter at all
        _refuses(stage_03.TopicError, "the misplaced # this fixture is built on",
                 lambda: stage_03.validate_filter("x/#/y"))
        broken = _policy(grants, publish=("x/#/y",), subscribe=("#/x",))
        _verdict(s.allowed_publish(broken, "alice", "a/1"), False, "malformed",
                 "a table whose publish pattern is not a filter")
        _verdict(s.allowed_subscribe(broken, "alice", "a/1"), False, "malformed",
                 "a table whose subscribe pattern is not a filter")
        bad_ceiling = _policy(grants, publish=("a/#",), subscribe=("a/#",),
                              ceiling_publish=("a/#", "b/+x"))
        _verdict(s.allowed_publish(bad_ceiling, "alice", "a/1"), False, "malformed",
                 "a ceiling whose own publish pattern is not a filter")
        _verdict(s.allowed_subscribe(bad_ceiling, "alice", "a/1"), True, "allowed",
                 "the same ceiling, which says nothing unreadable about subscribing")
        _verdict(s.allowed_publish(_two(grants), "alice", "a/1"), True, "allowed",
                 "another client's unreadable pattern, which is not this client's")

    def _matching(s, grants):
        """The matcher's components, and never the strings' first characters."""
        for topic in ("a", "a/b", "a/b/c", "a//b", "a/"):
            _verdict(s.allowed_publish(_policy(grants, publish=("a/#",)),
                                       "alice", topic), True, "allowed",
                     "a grant of a/# reaching %r, its own level or below it" % (topic,))
        for topic in ("ab", "a1/b", "b/a", "/a"):
            _verdict(s.allowed_publish(_policy(grants, publish=("a/#",)),
                                       "alice", topic), False, "no-grant",
                     "a grant of a/# and the topic %r, which it does not reach"
                     % (topic,))

        one = _policy(grants, publish=("a/+",))
        for topic in ("a/", "a/x", "a/b"):
            _verdict(s.allowed_publish(one, "alice", topic), True, "allowed",
                     "a grant of a/+ reaching the one level of %r" % (topic,))
        for topic in ("a/x/y", "a", "ab/x"):
            _verdict(s.allowed_publish(one, "alice", topic), False, "no-grant",
                     "a grant of a/+ and the topic %r: + is one level, never zero "
                     "and never two" % (topic,))

        _verdict(s.allowed_publish(_policy(grants, publish=("a/b",)),
                                   "alice", "a/b"), True, "allowed",
                 "a grant of a/b reaching a/b")
        _verdict(s.allowed_publish(_policy(grants, publish=("a/b",)),
                                   "alice", "a/bc"), False, "no-grant",
                 "a grant of a/b and the topic a/bc: components, never startswith")
        _verdict(s.allowed_publish(_policy(grants, publish=("a/bc",)),
                                   "alice", "a/b"), False, "no-grant",
                 "a grant of a/bc and the topic a/b: components, in both directions")

        for request in ("a", "a/b", "a/#", "a/+"):
            _verdict(s.allowed_subscribe(_policy(grants, subscribe=("a/#",)),
                                         "alice", request), True, "allowed",
                     "a subscribe to the filter %r under a grant of a/#" % (request,))
        for request in ("a", "a/#", "a/b/c"):
            _verdict(s.allowed_subscribe(_policy(grants, subscribe=("a/+",)),
                                         "alice", request), False, "no-grant",
                     "a subscribe to the filter %r under a grant of a/+: + is one "
                     "level" % (request,))
        _verdict(s.allowed_subscribe(_policy(grants, subscribe=("+/b",)),
                                     "alice", "a/b"), True, "allowed",
                 "a subscribe to a/b under a grant of +/b")
        _verdict(s.allowed_subscribe(_policy(grants, subscribe=("+/b",)),
                                     "alice", "a/b/c"), False, "no-grant",
                 "a subscribe to a/b/c under a grant of +/b")

        # the $ rule: a grant whose first level is a wildcard does not reach $SYS
        _verdict(s.allowed_publish(_policy(grants, publish=("#",)), "alice",
                                   "$SYS/x"), False, "no-grant",
                 "a grant of # and a topic in the broker's own $SYS tree")
        _verdict(s.allowed_subscribe(_policy(grants, subscribe=("#",)), "alice",
                                     "$SYS/x"), False, "no-grant",
                 "a subscribe to $SYS/x under a grant of #")
        _verdict(s.allowed_publish(_policy(grants, publish=("$SYS/#",),
                                           ceiling_publish=("$SYS/#",)),
                                   "alice", "$SYS/x"), True, "allowed",
                 "a grant of $SYS/#, whose first level is not a wildcard")
        _verdict(s.allowed_publish(_policy(grants, publish=("$SYS/#",)),
                                   "alice", "$SYS/x"), False, "ceiling",
                 "a grant of $SYS/# under a ceiling whose # does not reach $SYS")
        _verdict(s.allowed_subscribe(_policy(grants, subscribe=("$SYS/#",)),
                                     "alice", "$SYS/#"), False, "ceiling",
                 "a subscribe a grant of $SYS/# reaches and a ceiling of # does not")

    def _decisions(s, grants):
        """`decide`'s six fields, in order, from every reason code to the line."""
        policy = _policy(grants, publish=("a/#",), subscribe=("a/+",))
        for action, request, tick, allowed, reason in (
                ("publish", "a/1", 7, True, "allowed"),
                ("publish", "b/1", 8, False, "no-grant"),
                ("publish", "", 9, False, "empty"),
                ("publish", "a/+", 10, False, "wildcard"),
                ("subscribe", "a/b", 11, True, "allowed"),
                ("subscribe", "a/#", 12, False, "no-grant")):
            decision = s.decide(policy, "alice", action, request, tick)
            assert isinstance(decision, dict), (
                "a decision is a dict, and this one is %r" % (decision,))
            assert list(decision) == ["tick", "client", "action", "topic", "allowed",
                                      "reason"], (
                "a decision's keys are DECISION_KEYS in that order, and they are %r"
                % (list(decision),))
            assert decision == {"tick": tick, "client": "alice", "action": action,
                                "topic": request, "allowed": allowed,
                                "reason": reason}, (
                "the %s of %r at tick %d is %r, and decide answered %r"
                % (action, request, tick, (allowed, reason), decision))
            assert decision["tick"] == tick, (
                "a decision carries the tick it was made at, and %r does not" % (decision,))
            written = grants.line(decision)
            assert isinstance(written, str) and written.count(" ") == 5, (
                "every decision decide returns is a line the world can write, and %r "
                "wrote %r" % (decision, written))
        assert s.decide(policy, "alice", "publish", "a/1", 0)["tick"] == 0, (
            "zero is a tick like any other: %r"
            % (s.decide(policy, "alice", "publish", "a/1", 0),))
        refused_request = s.decide(policy, "alice", "publish", "", 0)
        assert (refused_request["allowed"], refused_request["reason"]) == (False, "empty"), (
            "a request that is merely not allowed is a decision and not an exception: %r"
            % (refused_request,))

        _refuses(grants.GrantsError, "an action outside the world's two",
                 lambda: s.decide(policy, "alice", "purge", "a/1", 0),
                 names=("purge", "publish", "subscribe"))
        _refuses(grants.GrantsError, "an action that is not a string",
                 lambda: s.decide(policy, "alice", 3, "a/1", 0), names=("3",))
        _refuses(grants.GrantsError, "a tick that is a bool",
                 lambda: s.decide(policy, "alice", "publish", "a/1", True),
                 names=("True",))
        _refuses(grants.GrantsError, "a tick below zero",
                 lambda: s.decide(policy, "alice", "publish", "a/1", -1),
                 names=("-1",))
        _refuses(grants.GrantsError, "a tick that is not a number at all",
                 lambda: s.decide(policy, "alice", "publish", "a/1", "3"),
                 names=("str",))
        _refuses(grants.GrantsError, "a topic that is not a string",
                 lambda: s.decide(policy, "alice", "publish", 5, 0), names=("int",))
        _refuses(grants.GrantsError, "a request that is not a name at all",
                 lambda: s.allowed_publish(policy, "alice", None),
                 names=("NoneType",))
        _refuses(grants.GrantsError, "a table that is not a Grants",
                 lambda: s.decide({"publish": ()}, "alice", "publish", "a/1", 0),
                 names=("dict",))
        _refuses(grants.GrantsError, "a client that is not a name",
                 lambda: s.decide(policy, 5, "publish", "a/1", 0), names=("int",))

    def _ledger(s, grants):
        """The line written before the act, and the counts that come from it."""
        policy = _policy(grants, publish=("a/#",), subscribe=("a/#",))
        ledger = s.Ledger()
        empty = ledger.report()
        assert list(empty) == ["lines", "allowed", "denied", "by-reason"], (
            "a report's four keys are lines, allowed, denied and by-reason, in that "
            "order, and this one is %r" % (list(empty),))
        assert empty == {"lines": 0, "allowed": 0, "denied": 0,
                         "by-reason": {reason: 0 for reason in grants.REASONS}}, (
            "an empty ledger reports every reason the world names at zero: %r"
            % (empty,))
        assert (ledger.lines(), ledger.denials(), ledger.allowed()) == ((), (), ()), (
            "an empty ledger has no lines and no decisions: %r"
            % ((ledger.lines(), ledger.denials(), ledger.allowed()),))

        first = s.decide(policy, "alice", "publish", "a/1", 7)
        written = ledger.before(first)
        assert written == ("tick=7 client=alice action=publish topic=a/1 "
                           "allowed=True reason=allowed"), (
            "a line is the six fields in DECISION_KEYS order as key=value pairs, and "
            "it was %r" % (written,))
        assert ledger.lines() == (written,), (
            "the line is written before the act it allows, so it is on the ledger the "
            "moment before() answers, and lines() says %r" % (ledger.lines(),))
        one = ledger.report()
        assert one["lines"] == 1 and one["allowed"] == 1 and one["denied"] == 0, (
            "one allowed line reports one line: %r" % (one,))
        assert one["by-reason"]["allowed"] == 1 and one["by-reason"]["no-grant"] == 0, (
            "the report counts the line by its reason: %r" % (one["by-reason"],))

        # a line nobody's decide() produced: it is written in DECISION_KEYS order
        # however its own keys are ordered, and it moves the counts
        by_hand = {"reason": "ceiling", "allowed": False, "topic": "a/1",
                   "action": "publish", "client": "alice", "tick": 8}
        second = ledger.before(by_hand)
        assert second == ("tick=8 client=alice action=publish topic=a/1 "
                          "allowed=False reason=ceiling"), (
            "the line's six fields are written in DECISION_KEYS order, and it was %r"
            % (second,))
        two = ledger.report()
        assert two["lines"] == 2, (
            "a report counts the lines that are on the ledger, not a tally kept "
            "beside them: after a line was added by hand it says %r" % (two,))
        assert two["allowed"] == 1 and two["denied"] == 1, (
            "a report counts each line by its own outcome: %r" % (two,))
        assert two["by-reason"] == {"allowed": 1, "no-grant": 0, "ceiling": 1,
                                    "wildcard": 0, "empty": 0, "malformed": 0}, (
            "the report counts by reason from the lines, and it says %r"
            % (two["by-reason"],))

        third = ledger.before(s.decide(policy, "bob", "publish", "a/1", 9))
        fourth = ledger.before(s.decide(policy, "carol", "publish", "a/1", 10))
        assert ledger.lines() == (written, second, third, fourth), (
            "the lines come back in the order they were written: %r"
            % (ledger.lines(),))
        assert ledger.allowed() == (first,), (
            "allowed answers the decisions that allowed: %r" % (ledger.allowed(),))
        assert len(ledger.denials()) == 3 and by_hand in ledger.denials(), (
            "denials answers the decisions that refused: %r" % (ledger.denials(),))
        counted = ledger.report()
        assert (counted["lines"], counted["allowed"], counted["denied"]) == (4, 1, 3), (
            "the report counts what the lines say: %r" % (counted,))
        assert counted["by-reason"]["no-grant"] == 2, (
            "two lines with the same reason count twice: %r" % (counted["by-reason"],))
        assert counted["allowed"] + counted["denied"] == counted["lines"], (
            "every line is either allowed or denied: %r" % (counted,))
        assert sum(counted["by-reason"].values()) == counted["lines"], (
            "every line has exactly one reason: %r" % (counted,))

        held = ledger.lines()
        _refuses(grants.GrantsError, "a decision with no reason in it",
                 lambda: ledger.before({"tick": 3, "client": "alice",
                                        "action": "publish", "topic": "a/1",
                                        "allowed": False}), names=("reason",))
        _refuses(grants.GrantsError, "a reason outside the world's vocabulary",
                 lambda: ledger.before({"tick": 3, "client": "alice",
                                        "action": "publish", "topic": "a/1",
                                        "allowed": False, "reason": "denied"}),
                 names=("denied",))
        _refuses(grants.GrantsError, "an allow whose reason is not allowed",
                 lambda: ledger.before({"tick": 3, "client": "alice",
                                        "action": "publish", "topic": "a/1",
                                        "allowed": True, "reason": "no-grant"}),
                 names=("allowed",))
        _refuses(grants.GrantsError, "a denial whose reason is allowed",
                 lambda: ledger.before({"tick": 3, "client": "alice",
                                        "action": "publish", "topic": "a/1",
                                        "allowed": False, "reason": "allowed"}),
                 names=("allowed",))
        _refuses(grants.GrantsError, "an allowed that is not a bool",
                 lambda: ledger.before({"tick": 3, "client": "alice",
                                        "action": "publish", "topic": "a/1",
                                        "allowed": 1, "reason": "allowed"}),
                 names=("1",))
        _refuses(grants.GrantsError, "a decision that is not a dict",
                 lambda: ledger.before("tick=3 client=alice"), names=("str",))
        assert ledger.lines() == held, (
            "a decision the line refuses is neither written nor held, and lines() "
            "says %r" % (ledger.lines(),))
        assert ledger.report()["lines"] == 4, (
            "and it moves no count either: %r" % (ledger.report(),))

        mutable = s.decide(policy, "dave", "publish", "a/1", 11)
        fifth = ledger.before(mutable)
        mutable["topic"] = "elsewhere"
        mutable["allowed"] = True
        mutable["reason"] = "allowed"
        assert ledger.lines()[-1] == fifth, (
            "the decision a line was written from is held as it was, so editing it "
            "afterwards cannot rewrite the line, and it now reads %r"
            % (ledger.lines()[-1],))
        assert ledger.allowed() == (first,), (
            "nor can it change which side the ledger counts it on: %r"
            % (ledger.allowed(),))

    def _walk(s, grants):
        """One walk through the policy: the decisions, the lines and the report."""
        policy = _policy(grants, publish=("a/#",), subscribe=("a/+",))
        ledger = s.Ledger()
        verdicts = [s.decide(policy, "alice", action, request, tick)
                    for action, request, tick in WALK]
        for decision in verdicts:
            ledger.before(decision)
        return (verdicts, ledger.lines(), ledger.report(), ledger.denials(),
                ledger.allowed())

    def _twice(s, grants):
        one = _walk(s, grants)
        two = _walk(s, grants)
        assert one == two, (
            "two runs of one fixture are the same run: %r vs %r" % (one, two))
        verdicts, lines, report, denials, allowed = one
        assert [decision["reason"] for decision in verdicts] == [
            "allowed", "no-grant", "wildcard", "allowed", "allowed", "no-grant",
            "empty"], (
            "the walk's seven requests answer these reasons in order: %r"
            % ([decision["reason"] for decision in verdicts],))
        assert len(lines) == len(WALK) and len(denials) == 4 and len(allowed) == 3, (
            "the walk wrote %d lines, %d of them denials and %d of them allows: %r"
            % (len(lines), len(denials), len(allowed), (lines, denials, allowed)))
        assert report["by-reason"] == {"allowed": 3, "no-grant": 2, "ceiling": 0,
                                       "wildcard": 1, "empty": 1, "malformed": 0}, (
            "the walk's report counts its lines by reason: %r"
            % (report["by-reason"],))

    import grants
    import stage_03
    import stage_09 as s
    _constants(s, grants)
    _reasons(s, grants, stage_03)
    _matching(s, grants)
    _decisions(s, grants)
    _ledger(s, grants)
    _twice(s, grants)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "mqtt-broker-from-scratch"

    BROKER_KEYS = ("client", "stream", "buffers", "sessions", "trie", "retained",
                   "inflight", "queued", "decisions", "trace", "tick")

    REPORT_KEYS = ("streams", "sessions", "subscriptions", "deliveries", "qos0",
                   "qos1", "qos2", "redeliveries", "queued", "dropped", "refusals",
                   "frames", "bytes")

    TABLE = {"one": {"publish": ("a/#",), "subscribe": ("a/#",)},
             "two": {"publish": ("a/#",), "subscribe": ("a/+",)},
             "three": {"publish": ("a/+",), "subscribe": ("a/#",)}}

    CEILING = {"publish": ("a/+",), "subscribe": ("a/#",)}

    def _repo(start=None):
        for candidate_start in (os.environ.get("L3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _varint(value):
        """A variable-length integer, written here so a fixture does not lean on it."""
        out = bytearray()
        while True:
            group = value & 0x7F
            value >>= 7
            if not value:
                out.append(group)
                return bytes(out)
            out.append(group | 0x80)

    def _frame(kind, flags, body):
        """One whole packet: the type and its nibble, the length, then the body."""
        return bytes([(kind << 4) | flags]) + _varint(len(body)) + body

    def _string(text):
        """An MQTT string: two bytes of length, then its UTF-8."""
        payload = text.encode("utf-8")
        return bytes([len(payload) >> 8, len(payload) & 0xFF]) + payload

    def _payload(data):
        """A length-prefixed blob, for the will's message."""
        return bytes([len(data) >> 8, len(data) & 0xFF]) + data

    def _connect_body(client_id, clean_start=0, keep_alive=0, will=None):
        """A CONNECT's body, as a client writes one: stage 2 is its reader."""
        flags = 0
        if will is not None:
            flags |= 0b0000_0100 | ((will["qos"] & 0b11) << 3)
            if will["retain"]:
                flags |= 0b0010_0000
        if clean_start:
            flags |= 0b0000_0010
        body = b"\x00\x04MQTT\x04" + bytes([flags])
        body += bytes([keep_alive >> 8, keep_alive & 0xFF]) + _string(client_id)
        if will is not None:
            body += _string(will["topic"]) + _payload(will["payload"])
        return body

    def _subscribe_body(packet_id, topics):
        """A SUBSCRIBE's body: the id, then one (filter, asked-for QoS) per filter."""
        body = bytes([packet_id >> 8, packet_id & 0xFF])
        for filter, qos in topics:
            body += _string(filter) + bytes([qos])
        return body

    def _publish_body(topic, payload, qos=0, packet_id=None):
        """A PUBLISH's body: the topic, the id when the QoS carries one, the payload."""
        body = _string(topic)
        if qos:
            body += bytes([packet_id >> 8, packet_id & 0xFF])
        return body + payload

    def _will(topic, payload, qos=0, retain=False):
        """A will, in the four fields `WILL_KEYS` names."""
        return {"topic": topic, "payload": payload, "qos": qos, "retain": retain}

    def _walk(data):
        """Every whole frame in a buffer, read the long way round, by this check's own rules.

        A client's end of a run has to be looked at without asking the stage under
        test to read it: the type and the nibble are the first byte's two halves and
        the length is the one-to-four-group integer after it, which is the format the
        course is about and not stage 10's opinion of it.

        A frame the buffer does not hold the whole of stops the walk: a client read
        in the middle of a turn may have the first bytes of a packet the transport
        has split or the broker has not finished handing over, and that is a fact
        about the run and not a reading of it. The check's pins then read the same
        buffer with stage 10's reader and require `pos` to be its length, which is
        where a tail that never completes is caught.
        """
        frames = []
        pos = 0
        while pos < len(data):
            first = data[pos]
            length = 0
            shift = 0
            at = pos + 1
            while True:
                group = data[at]
                at += 1
                length |= (group & 0x7F) << shift
                if not group & 0x80:
                    break
                shift += 7
            if at + length > len(data):
                break
            frames.append((first >> 4, first & 0x0F, data[at:at + length]))
            pos = at + length
        return frames

    def _nibbles(heard):
        """The `(type, flags)` of every frame a client heard, in order."""
        return [(kind, flags) for kind, flags, _ in _walk(heard)]

    def _bodies(heard, kind):
        """The bodies of every frame of one type a client heard, in order."""
        return [body for kind_of, _, body in _walk(heard) if kind_of == kind]

    def _id_bytes(packet_id):
        """A packet id as the two bytes every bare acknowledgement carries."""
        return bytes([packet_id >> 8, packet_id & 0xFF])

    def _publishes(heard, stage_05):
        """Every PUBLISH a client heard, as `(flags, publish)` by stage 5's reader."""
        return [(flags, stage_05.read_publish(body, 0, flags)[0])
                for kind, flags, body in _walk(heard) if kind == 3]

    def _qos_ids(heard, qos, stage_05, dup=None):
        """The packet ids of the PUBLISH frames of one QoS a client heard.

        `dup` picks the first transmissions (`False`), the re-sends (`True`), or
        every one of them (`None`), because a frame written again carries the same id
        as the frame it repeats — which is the whole of what DUP promises.
        """
        out = []
        for flags, publish in _publishes(heard, stage_05):
            if (flags & 0b0110) >> 1 != qos:
                continue
            if dup is not None and bool(flags & 0b1000) != dup:
                continue
            out.append(publish["packet_id"])
        return out

    class _Wire:
        """One client's end of a stream on the real transport: what it says, what it heard.

        A wire connects a stream, hands the broker what arrived at the server's end
        one arrival at a time — so a packet split by the transport is offered in
        pieces and the broker reassembles it — and carries the frames the broker
        answered back to the client, taking them so the transport is left with
        nothing in flight.
        """

        def __init__(self, transport, broker, client, tag=None):
            self.transport = transport
            self.broker = broker
            self.client = client
            self.tag = tag or client
            self.stream = transport.connect(client, "broker")
            self.heard = b""

        def say(self, data):
            """Say one whole frame, and carry whatever the broker wrote back."""
            rest = data
            while rest:
                taken = self.transport.send(self.stream, rest)
                rest = rest[taken:]
                if rest:
                    self.transport.step()
            written = []
            while True:
                arrived = self.transport.to_server(self.stream)
                if arrived:
                    written.extend(self.broker.receive(self.stream, arrived))
                if not self.transport.waiting_at(self.stream, "server"):
                    break
                self.transport.step()
            rest = b"".join(written)
            while rest:
                taken = self.transport.answer(self.stream, rest)
                rest = rest[taken:]
                if rest:
                    self.transport.step()
            self.take()
            return written

        def take(self):
            """Everything that has arrived at this client, appended to what it has heard.

            The server's bytes are read through the transport's own view — what is
            queued for this client and what has been carried and not taken — so a
            frame that the transport had to split across steps is read whole, and a
            client's history never holds half of one.
            """
            heard = b""
            for _ in range(64):
                heard += self.transport.to_client(self.stream)
                if not self.transport.waiting(self.stream)[1]:
                    break
                self.transport.step()
            self.heard += heard
            return heard

        def idle(self, ticks=1):
            """Give the broker one turn of `ticks` ticks, and take what reaches the client.

            One call is one `broker.step(ticks)` — one turn — so the re-sends a
            deadline causes happen once each and not once per tick, which is what
            makes a run's frame count something a check can state.
            """
            self.broker.step(ticks)
            return self.take()

        def turn(self):
            """One tick of the broker's own turn, for what does not fit one outbox."""
            self.broker.step()
            return self.take()

        def frames(self, read_frames):
            """This client's whole history, read by the course's own reader."""
            frames, pos = read_frames(self.heard)
            assert pos == len(self.heard), (
                "%s heard %d bytes and the course's reader stopped at %d"
                % (self.client, len(self.heard), pos))
            return frames

    def _table(grants):
        """The policy this scenario runs under: a grant, and a ceiling above it."""
        return grants.Grants(TABLE, CEILING)

    def _owing(broker):
        """The bytes the broker still owes the streams it believes are open.

        The broker's own state is readable — `BROKER_KEYS` is the shape of a run —
        and this is the fixture asking whether a client can be read yet: a frame
        larger than the transport's chunk leaves a tail in the broker's hand, and a
        client that has not been given the whole of its frame has heard half of one.
        """
        return sum(len(held["out"])
                   for held in broker.state["buffers"].values()
                   if held["open"] and held["out"])

    def _script(streams, stage_01, stage_05, stage_10, grants, seen):
        """The capstone's scenario: one scripted client side, runnable twice.

        Every step is a packet a client says and what it must be answered with:
        a clean CONNECT and a subscription granted below what was asked, a retained
        message that reaches a subscription made later, three publishes at the three
        QoS with a QoS 2 handshake that delivers at its PUBREL, a publish refused by
        the ceiling and one refused for want of a grant and one subscription refused
        the same way, two deadlines that pass with a message in flight, a client cut
        mid-handshake whose will is owed, a retained message replaced and then
        cleared, the queue a resumed session takes back, a keep-alive that runs out
        with a will of its own, and a clean goodbye the transport can agree to.
        """
        s1 = stage_01

        def run():
            transport = streams.Transport({"chunk": 64, "backlog": 4})
            transport.listen("broker")
            broker = stage_10.Broker(transport, "broker", _table(grants))
            one = _Wire(transport, broker, "one")
            two = _Wire(transport, broker, "two")
            three = _Wire(transport, broker, "three")
            wires = [one, two, three]
            settled = {}

            def take():
                """Every client reads the bytes that have arrived for it."""
                for wire in wires:
                    wire.take()

            def quiet(ticks=1):
                """A turn of the broker's own: the clock moves, and what it owes is carried.

                The broker offers one chunk of each stream it owes per step, so a
                frame larger than that takes one more turn to hand over: the loop
                turns while it still owes a stream it believes is open, and stops
                after three either way — a turn of the clock is also what makes a
                deadline pass, and a fixture that kept turning while anything was
                owed would be sending the same frame again and again.
                """
                broker.step(ticks)
                for _ in range(3):
                    take()
                    if not _owing(broker):
                        break
                    broker.step()
                take()

            def fresh(wire, qos):
                """The first transmissions of one QoS this client has not answered yet.

                A packet id is handed out again the moment it is released, so an id
                is not a name for one delivery across a whole run: what is counted
                here is the *occurrence* — the n-th first transmission of that QoS a
                client heard — and its id is read off the frame that carried it.
                """
                ids = _qos_ids(wire.heard, qos, stage_05, dup=False)
                return ids[settled.get(wire.tag, 0):]

            def answered(wire, count):
                """Record `count` first transmissions of one client as answered."""
                settled[wire.tag] = settled.get(wire.tag, 0) + count

            def settle(wire, qos, hold=0):
                """Finish this client's handshakes of one QoS, all but the last `hold`."""
                waiting = fresh(wire, qos)
                done = waiting[:len(waiting) - hold if hold else len(waiting)]
                for packet_id in done:
                    answered(wire, 1)
                    if qos == 1:
                        wire.say(_frame(s1.PUBACK, 0, _id_bytes(packet_id)))
                    else:
                        wire.say(_frame(s1.PUBREC, 0, _id_bytes(packet_id)))
                        wire.say(_frame(s1.PUBCOMP, 0, _id_bytes(packet_id)))
                return done

            def reach(wire, qos, upto):
                """Bring the first unfinished handshake of `wire` to 1 its PUBREC, 2 both."""
                for packet_id in fresh(wire, qos):
                    answered(wire, 1)
                    wire.say(_frame(s1.PUBREC, 0, _id_bytes(packet_id)))
                    if upto == 2:
                        wire.say(_frame(s1.PUBCOMP, 0, _id_bytes(packet_id)))
                    return packet_id
                return None

            # a broker with a policy, and a client that subscribes at the top QoS
            one.say(_frame(s1.CONNECT, 0, _connect_body("one", clean_start=1)))
            one.say(_frame(s1.SUBSCRIBE, 0b0010, _subscribe_body(1, [("a/#", 2)])))

            # a third client on the same filter, at the QoS a stored message goes at
            three.say(_frame(s1.CONNECT, 0, _connect_body("three", clean_start=1,
                                                          will=_will("a/late",
                                                                     b"first"))))
            three.say(_frame(s1.SUBSCRIBE, 0b0010, _subscribe_body(1, [("a/#", 0)])))

            # a client with a will of its own, whose second filter is refused
            two.say(_frame(s1.CONNECT, 0, _connect_body(
                "two", clean_start=1, will=_will("a/will", b"gone", qos=1))))
            two.say(_frame(s1.SUBSCRIBE, 0b0010,
                           _subscribe_body(2, [("a/+", 1), ("b/#", 0)])))

            # one topic, one publish at each QoS: three subscribers, three QoS
            one.say(_frame(s1.PUBLISH, 0, _publish_body("a/b", b"q0")))
            one.say(_frame(s1.PUBLISH, 0b0010, _publish_body("a/b", b"q1", 1, 9)))
            one.say(_frame(s1.PUBLISH, 0b0100, _publish_body("a/b", b"q2", 2, 10)))
            one.say(_frame(s1.PUBREL, 0b0010, _id_bytes(10)))
            quiet()
            settle(one, 2)
            settle(two, 1)

            # a kept message, retained above what anybody asked to be sent
            one.say(_frame(s1.PUBLISH, 0b0011, _publish_body("a/keep", b"v1", 1, 11)))
            quiet()
            settle(one, 2)
            settle(two, 1)

            # what the grants refuse: a topic above the ceiling, a publish with no
            # grant, and a filter refused the same way
            one.say(_frame(s1.PUBLISH, 0, _publish_body("a/b/c", b"no")))
            two.say(_frame(s1.PUBLISH, 0b0010, _publish_body("b/x", b"no", 1, 5)))
            two.say(_frame(s1.SUBSCRIBE, 0b0010, _subscribe_body(3, [("b/x", 0)])))

            # a publish left unacknowledged and a QoS 2 handshake stopped at its
            # PUBREL: one turn of the broker past the deadline writes each again
            one.say(_frame(s1.PUBLISH, 0b0100, _publish_body("a/strand", b"s", 2, 12)))
            one.say(_frame(s1.PUBREL, 0b0010, _id_bytes(12)))
            quiet()
            stranded = reach(one, 2, 1)
            settle(two, 1, hold=1)
            quiet(6)
            one.say(_frame(s1.PUBCOMP, 0, _id_bytes(stranded)))
            settle(two, 1)

            # the client is cut mid-handshake: half a frame arrived, and nobody
            # agreed to the end, so the will it left is owed
            half = _frame(s1.PUBLISH, 0b0010,
                          _publish_body("a/half", b"y" * 40, 1, 8))[:8]
            transport.send(two.stream, half)
            transport.step()
            broker.receive(two.stream, transport.to_server(two.stream))
            transport.cut(two.stream, "the peer is gone")
            quiet()
            settle(one, 2)

            # while it is away its session keeps what it was promised
            one.say(_frame(s1.PUBLISH, 0b0010, _publish_body("a/queued", b"q", 1, 13)))
            quiet()
            settle(one, 2)

            # and what it missed is handed over when it comes back
            two2 = _Wire(transport, broker, "two", tag="two-2")
            wires.append(two2)
            two2.say(_frame(s1.CONNECT, 0, _connect_body("two", clean_start=0)))
            quiet(2)
            settle(two2, 1)

            # the kept message is replaced, and a big one is kept beside it: one
            # frame each way is larger than the transport carries at once
            one.say(_frame(s1.PUBLISH, 0b0011, _publish_body("a/keep", b"v2", 1, 14)))
            one.say(_frame(s1.PUBLISH, 0b0011,
                           _publish_body("a/big", b"z" * 80, 1, 15)))
            quiet()
            settle(one, 2)
            settle(two2, 1)

            # a filter made after the fact is handed the kept message
            two2.say(_frame(s1.SUBSCRIBE, 0b0010, _subscribe_body(3, [("a/big", 1)])))
            quiet()
            settle(two2, 1)

            # and the empty payload clears it, so a filter made later is handed nothing
            one.say(_frame(s1.PUBLISH, 0b0011, _publish_body("a/big", b"", 1, 16)))
            quiet()
            settle(one, 2)
            settle(two2, 1)
            three.say(_frame(s1.SUBSCRIBE, 0b0010, _subscribe_body(2, [("a/big", 1)])))

            # a ping is answered, and a client that stops talking is cut when its
            # keep-alive runs out, with a will of its own owed
            three.say(_frame(s1.PINGREQ, 0, b""))
            four = _Wire(transport, broker, "four")
            wires.append(four)
            four.say(_frame(s1.CONNECT, 0, _connect_body(
                "four", clean_start=1, keep_alive=4,
                will=_will("a/late", b"late", qos=1))))
            quiet(8)
            settle(one, 2)
            settle(two2, 1)

            # a clean goodbye, and a stream both ends read everything on
            quiet()
            one.say(_frame(s1.DISCONNECT, 0, b""))
            transport.close(one.stream)

            seen.append({"transport": transport, "broker": broker, "one": one,
                         "two": two, "two2": two2, "three": three, "four": four})
            return broker

        return run

    def _keys(s):
        assert s.BROKER_KEYS == ("client", "stream", "buffers", "sessions", "trie",
                                 "retained", "inflight", "queued", "decisions",
                                 "trace", "tick"), (
            "a run's state is the eleven parts of a broker's own bookkeeping, in the "
            "order they were first needed, and the stage names %r" % (s.BROKER_KEYS,))
        assert s.REPORT_KEYS == ("streams", "sessions", "subscriptions",
                                 "deliveries", "qos0", "qos1", "qos2",
                                 "redeliveries", "queued", "dropped", "refusals",
                                 "frames", "bytes"), (
            "a report is the thirteen counts the capstone asks for, in order, and "
            "the stage names %r" % (s.REPORT_KEYS,))

    def _trace(s, stage_01):
        trace = s.Trace()
        assert trace.frames() == [], (
            "an empty trace has no frames, and it answered %r" % (trace.frames(),))
        assert trace.bytes() == b"", (
            "an empty trace wrote no bytes, and it answered %r" % (trace.bytes(),))
        assert trace.wrote(3, b"\x20\x02") == b"\x20\x02", (
            "wrote() answers the same bytes it was handed, so a caller can write and "
            "record in one step")
        trace.wrote(4, b"\x40\x02\x00\x01")
        assert trace.frames() == [(3, b"\x20\x02"), (4, b"\x40\x02\x00\x01")], (
            "the tick recorded is the tick of the write, not of the read that follows "
            "it — a trace stamped when it is read dates every frame the same way — and "
            "the frames came back as %r" % (trace.frames(),))
        assert trace.bytes() == b"\x20\x02\x40\x02\x00\x01", (
            "the bytes of a run are its writes in order, and they came back as %r"
            % (trace.bytes(),))
        taken = trace.frames()
        taken.append((9, b"\x00"))
        assert len(trace.frames()) == 2, (
            "frames() hands back a copy: a caller that appended to what it was given "
            "changed the trace's own record")
        assert trace.wrote(5, b"") == b"", (
            "an empty write is still a write the trace records")
        _refuses(stage_01.ProtocolError, "a tick that is not a tick",
                 lambda: trace.wrote("3", b"\x00"), names=("int", "str"))
        _refuses(stage_01.ProtocolError, "a tick below zero",
                 lambda: trace.wrote(-1, b"\x00"), names=("-1",))
        _refuses(stage_01.ProtocolError, "a bool handed in for a tick",
                 lambda: trace.wrote(True, b"\x00"), names=("bool",))
        _refuses(stage_01.ProtocolError, "a string handed in for bytes",
                 lambda: trace.wrote(0, "\x20\x02"), names=("bytes", "str"))

    def _reader(s, stage_01):
        run = b"\x20\x02\x00\x00\x40\x02\x00\x01\xd0\x00"
        frames, pos = s.read_frames(run)
        assert [(kind, flags) for kind, flags, _ in frames] == [
            (stage_01.CONNACK, 0), (stage_01.PUBACK, 0), (stage_01.PINGRESP, 0)], (
            "the course's own reader takes a run of frames back as themselves, in "
            "order, and it answered %r" % ([(k, f) for k, f, _ in frames],))
        assert pos == len(run), (
            "the position is where the last frame ended, which is the end of a whole "
            "run: %d of %d bytes" % (pos, len(run)))
        assert [body for _, _, body in frames] == [b"\x00\x00", b"\x00\x01", b""], (
            "each body is the body its writer wrote, and they came back as %r"
            % ([body for _, _, body in frames],))
        split = _refuses(stage_01.Incomplete, "a buffer that stops inside a frame",
                         lambda: s.read_frames(run[:6]))
        assert split.needed == 2, (
            "a PUBACK's header arrived with none of its two body bytes, so the reader "
            "needs two more and it asked for %r" % (split.needed,))
        once = _refuses(stage_01.Incomplete, "a frame whose last body byte is short",
                        lambda: s.read_frames(run[:3]))
        assert once.needed == 1, (
            "a CONNACK's header and one of its two body bytes arrived, so one more is "
            "needed and it asked for %r" % (once.needed,))
        whole, at = s.read_frames(run)
        assert ([(kind, flags) for kind, flags, _ in whole], at) == (
            [(stage_01.CONNACK, 0), (stage_01.PUBACK, 0), (stage_01.PINGRESP, 0)],
            len(run)), (
            "the frame a short buffer stopped in is read once when the rest arrives, "
            "and the whole run read after it came back as %r"
            % ([(k, f) for k, f, _ in whole],))
        after = s.read_frames(run, 4)
        assert [(kind, flags) for kind, flags, _ in after[0]] == [
            (stage_01.PUBACK, 0), (stage_01.PINGRESP, 0)], (
            "a read at a non-zero position leaves the frames before it alone")
        assert after[1] == len(run), (
            "and lands at the end all the same: %d" % (after[1],))
        _refuses(stage_01.ProtocolError, "a PUBREL whose nibble is plain zero",
                 lambda: s.read_frames(b"\x60\x02\x00\x01"), names=("6", "0x60"))
        _refuses(stage_01.ProtocolError, "a reserved type in a run",
                 lambda: s.read_frames(b"\x00\x02\x00\x00"), names=("0", "reserved"))
        _refuses(stage_01.ProtocolError, "a string handed in for a buffer",
                 lambda: s.read_frames("\x20\x02\x00\x00"), names=("bytes", "str"))
        _refuses(stage_01.ProtocolError, "a position outside the buffer",
                 lambda: s.read_frames(run, 99), names=("99",))
        _refuses(stage_01.ProtocolError, "a position that is not an int",
                 lambda: s.read_frames(run, "4"), names=("int",))
        _refuses(stage_01.ProtocolError, "a bool handed in for a position",
                 lambda: s.read_frames(run, True), names=("True",))

    def _publishes_of(wire, stage_05):
        """One client's PUBLISH frames, as `(topic, qos, packet_id, dup)`."""
        return [(message["topic"], message["qos"], message["packet_id"],
                 bool(flags & 0b1000))
                for flags, message in _publishes(wire.heard, stage_05)]

    def _wires(s, records, stage_01, stage_05):
        one, two, two2, three, four = (records[name] for name in
                                       ("one", "two", "two2", "three", "four"))
        for wire in (one, two, two2, three, four):
            frames, pos = s.read_frames(wire.heard)
            assert pos == len(wire.heard) and frames, (
                "%s heard %d bytes and the course's own reader stopped at %d with %d "
                "frames: a client's end of a run is whole frames and nothing else"
                % (wire.client, len(wire.heard), pos, len(frames)))

        assert _nibbles(one.heard) == [
            (2, 0), (9, 0), (3, 0b0100), (3, 0b0100), (4, 0), (5, 0),
            (3, 0b0100), (7, 0), (3, 0b1100), (3, 0b1100), (6, 0b0010),
            (6, 0b0010), (6, 0b0010), (3, 0b0100), (4, 0), (6, 0b0010), (5, 0),
            (3, 0b0100), (7, 0), (6, 0b0010), (6, 0b0010), (3, 0b0100),
            (6, 0b0010), (3, 0b0100), (4, 0), (6, 0b0010), (3, 0b0100), (4, 0),
            (3, 0b0100), (4, 0), (3, 0b1100), (3, 0b1100), (3, 0b1100),
            (3, 0b1100), (6, 0b0010), (6, 0b0010), (4, 0), (3, 0b0100),
            (6, 0b0010),], (
            "a client at QoS 2 is handed every delivery at QoS 2, answers each with "
            "the PUBREC the broker meets with a PUBREL, and its PUBCOMPs are the only "
            "acks it writes: %r" % (_nibbles(one.heard),))
        assert _publishes_of(one, stage_05) == [
            ('a/b', 2, 1, False), ('a/b', 2, 2, False), ('a/b', 2, 3, False),
            ('a/b', 2, 1, True), ('a/b', 2, 2, True), ('a/keep', 2, 1, False),
            ('a/strand', 2, 1, False), ('a/will', 2, 1, False),
            ('a/queued', 2, 1, False), ('a/keep', 2, 1, False),
            ('a/big', 2, 2, False), ('a/keep', 2, 1, True),
            ('a/big', 2, 2, True), ('a/keep', 2, 1, True), ('a/big', 2, 2, True),
            ('a/late', 2, 1, False),], (
            "every delivery to the QoS 2 subscription, in order, with the id it went "
            "out under and the DUP of a repeat — a repeat carries the same id as the "
            "frame it repeats: %r" % (_publishes_of(one, stage_05),))

        assert _nibbles(two.heard) == [
            (2, 0), (9, 0), (3, 0b0010), (3, 0b0010), (3, 0b0010), (3, 0b1010),
            (3, 0b1010), (3, 0b0010), (9, 0), (3, 0b0010), (3, 0b1010),], (
            "a client granted QoS 1 on a/+ is handed the two publishes under it at "
            "QoS 1, and the two whose deadline passed come back with DUP and their "
            "own ids: %r" % (_nibbles(two.heard),))
        assert _bodies(two.heard, stage_01.SUBACK) == [b"\x00\x02\x01\x80",
                                                       b"\x00\x03\x80"], (
            "one SUBSCRIBE is granted a/+ at QoS 1 and refused b/# with the failure "
            "code 0x80, and a second refused filter answers 0x80 alone: %r"
            % (_bodies(two.heard, stage_01.SUBACK),))
        assert _publishes_of(two, stage_05) == [
            ('a/b', 1, 1, False), ('a/b', 1, 2, False), ('a/b', 1, 3, False),
            ('a/b', 1, 1, True), ('a/b', 1, 2, True), ('a/keep', 1, 1, False),
            ('a/strand', 1, 1, False), ('a/strand', 1, 1, True),], (
            "a QoS 1 subscription takes what the trie reaches it, in order: %r"
            % (_publishes_of(two, stage_05),))

        assert _nibbles(two2.heard) == [
            (2, 0), (3, 0b0010), (3, 0b0010), (3, 0b0010), (3, 0b0010),
            (3, 0b1010), (3, 0b1010), (3, 0b1010), (3, 0b1010), (9, 0),
            (3, 0b0011), (3, 0b1010), (3, 0b0010),], (
            "the client that comes back into its session is handed what its streams "
            "missed, then the kept message a fresh filter asks for with RETAIN set, "
            "and its repeats: %r" % (_nibbles(two2.heard),))
        assert _bodies(two2.heard, stage_01.CONNACK) == [b"\x01\x00"], (
            "a CONNECT with clean_start false answers the session-present byte 1, and "
            "a broker that asks for a clean start anyway has nothing to hand over: %r"
            % (_bodies(two2.heard, stage_01.CONNACK),))
        assert _publishes_of(two2, stage_05) == [
            ('a/will', 1, 1, False), ('a/queued', 1, 2, False),
            ('a/keep', 1, 1, False), ('a/big', 1, 2, False),
            ('a/keep', 1, 1, True), ('a/big', 1, 2, True),
            ('a/keep', 1, 1, True), ('a/big', 1, 2, True),
            ('a/big', 1, 1, False), ('a/big', 1, 1, True),
            ('a/late', 1, 1, False),], (
            "the will fired while this client was away is the first thing its queue "
            "had for it, and the retained a/big is handed at its own id: %r"
            % (_publishes_of(two2, stage_05),))

        assert _nibbles(three.heard) == [
            (2, 0), (9, 0), (3, 0), (3, 0), (3, 0), (3, 0), (3, 0), (3, 0),
            (3, 0), (3, 0), (3, 0), (9, 0), (13, 0), (3, 0),], (
            "a QoS 0 subscription is handed every delivery with no id and no ack, its "
            "pings are answered with a PINGRESP, and the message a later filter would "
            "have been handed was cleared: %r" % (_nibbles(three.heard),))
        assert _bodies(three.heard, stage_01.SUBACK) == [b"\x00\x01\x00",
                                                         b"\x00\x02\x01"], (
            "a/# is granted at QoS 0 and a/big at QoS 1: %r"
            % (_bodies(three.heard, stage_01.SUBACK),))
        assert [topic for topic, _, _, _ in _publishes_of(three, stage_05)] == [
            'a/b', 'a/b', 'a/b', 'a/keep', 'a/strand', 'a/will', 'a/queued',
            'a/keep', 'a/big', 'a/late',], (
            "every message the trie reached this client with, in order — and the "
            "empty payload that cleared a/big is not one of them: %r"
            % ([topic for topic, _, _, _ in _publishes_of(three, stage_05)],))

        assert _nibbles(four.heard) == [
            (2, 0),], (
            "a client that connects with a keep-alive, subscribes to nothing and then "
            "goes silent is handed its CONNACK and nothing else: %r"
            % (_nibbles(four.heard),))

    def _account(s, streams, broker, transport):
        assert broker.accepted() == (1, 3, 2, 4, 5), (
            "the streams that completed a CONNECT, in the order they did: the third "
            "client's CONNECT is read before the second's because that is the order "
            "the script says them in, and the answer was %r"
            % (broker.accepted(),))
        sessions = broker.state["sessions"].sessions()
        assert [session["client_id"] for session in sessions] == ["one", "three",
                                                                 "two", "four"], (
            "three clients connected and one of them came back into its session, so "
            "there are four sessions and not five: %r"
            % ([session["client_id"] for session in sessions],))
        assert [session["subscriptions"] for session in sessions] == [
            {"a/#": 2}, {"a/#": 0, "a/big": 1}, {"a/+": 1, "a/big": 1}, {}], (
            "a session's own filters and their granted QoS: the refused ones are not "
            "in them, and the resumed session holds the filter it was granted before "
            "the cut beside the one it asked for after: %r"
            % ([session["subscriptions"] for session in sessions],))
        assert sessions[1]["will"] == {"topic": "a/late", "payload": b"first",
                                       "qos": 0, "retain": False}, (
            "the will of a client that is still connected is still owed: %r"
            % (sessions[1]["will"],))
        assert sessions[3]["will"] is None, (
            "the will of the client whose keep-alive ran out has been spent, and a "
            "will that fires once is not a will that fires every step: %r"
            % (sessions[3]["will"],))
        assert [session["pending"] for session in sessions] == [0, 0, 0, 0], (
            "every delivery the script acknowledged is settled: %r"
            % ([session["pending"] for session in sessions],))
        assert [session["queue"] for session in sessions] == [[], [], [], []], (
            "nothing is left waiting for a client that is not coming back: %r"
            % ([session["queue"] for session in sessions],))

        trie = broker.state["trie"]
        assert tuple(trie.filters()) == ("a/#", "a/+", "a/big"), (
            "the filters the trie holds, in the order they were first held: %r"
            % (tuple(trie.filters()),))
        assert [trie.subscribers(name) for name in trie.filters()] == [
            (("one", 2), ("three", 0)), (("two", 1),), (("two", 1), ("three", 1))], (
            "the clients on each filter, in the order they joined, at the QoS each "
            "was granted: %r" % ([trie.subscribers(name) for name in trie.filters()],))
        assert tuple(broker.state["retained"].topics()) == ("a/keep",), (
            "the retained store holds the message the last publish to a/keep left, and "
            "the empty payload that followed a/big took that topic away: %r"
            % (tuple(broker.state["retained"].topics()),))

        denials = broker.state["decisions"].denials()
        assert [(line["action"], line["topic"], line["allowed"], line["reason"])
                for line in denials] == [
            ("subscribe", "b/#", False, "no-grant"),
            ("publish", "a/b/c", False, "ceiling"),
            ("publish", "b/x", False, "no-grant"),
            ("subscribe", "b/x", False, "no-grant")], (
            "every refusal stage 9 made, with the reason it gave: a filter outside the "
            "grant, a topic inside the grant but above the ceiling, a publish with no "
            "grant at all, and one more refused filter: %r"
            % ([(line["action"], line["topic"], line["reason"]) for line in denials],))

        report = broker.report()
        assert report == {"streams": 5, "sessions": 4, "subscriptions": 5,
                          "deliveries": 45, "qos0": 10, "qos1": 19, "qos2": 16,
                          "redeliveries": 14, "queued": 0, "dropped": 8,
                          "refusals": 4, "frames": 78, "bytes": 1420}, (
            "the report of this run, counted from the trace and the sessions: five "
            "streams and four sessions, five subscriptions on three filters, the "
            "forty-five PUBLISH frames written as ten at QoS 0, nineteen at QoS 1 and "
            "sixteen at QoS 2, fourteen of them repeats, nothing queued, the eight "
            "bytes of the half-frame the cut left behind counted as dropped, four "
            "refusals, and the seventy-eight frames and 1420 bytes of the trace — the "
            "report said %r" % (report,))
        assert _owing(broker) == 0, (
            "the run ends with nothing owed to a stream the broker still believes is "
            "open, which is what makes the bytes it wrote and the bytes the transport "
            "took the same number: %r" % (_owing(broker),))

        trace = broker.trace()
        assert len(trace.frames()) == report["frames"] == 78, (
            "the report counts the writes and not a counter beside them: %d writes "
            "and a report of %r" % (len(trace.frames()), report["frames"]))
        assert len(trace.bytes()) == report["bytes"] == 1420, (
            "and the bytes: %d written and a report of %r"
            % (len(trace.bytes()), report["bytes"]))
        whole, at = s.read_frames(trace.bytes())
        assert at == len(trace.bytes()) and len(whole) == len(trace.frames()), (
            "the course's own reader takes the whole trace back with no byte left "
            "over: %d of %d bytes and %d of %d frames"
            % (at, len(trace.bytes()), len(whole), len(trace.frames())))
        assert [(kind, flags) for kind, flags, _ in whole] == \
            _nibbles(trace.bytes()), (
            "and each frame is the frame the broker wrote, in the order it wrote it")

        assert transport.tick() == 137, (
            "the run is 137 ticks long, and the tick is the caller's: a stage that "
            "read a clock of its own would move this number and make two runs differ")
        stats = transport.stats()
        assert (stats["streams"], stats["connects"], stats["accepts"],
                stats["closes"], stats["cuts"]) == (5, 5, 5, 1, 2), (
            "the transport opened five streams, accepted all five, saw one agreed end "
            "and two that nobody agreed to: %r" % (stats,))
        assert stats["bytes_dropped"] == 0, (
            "no byte was lost in the transport itself: the eight the report counts as "
            "dropped never left the broker's hand, because the half-frame stopped at "
            "the broker and was never offered back: %r" % (stats["bytes_dropped"],))
        assert [(record["stream"], record["reason"])
                for record in transport.log() if record["event"] == "cut"] == \
            [(2, "the peer is gone"), (5, "keep-alive expired")], (
            "the two cuts name their own reasons, and the client that said goodbye is "
            "not one of them: %r"
            % ([(r["stream"], r["reason"]) for r in transport.log()
                if r["event"] == "cut"],))
        assert transport.stream(1).state == streams.CLOSED, (
            "the stream the client said goodbye on was closed by both ends, which the "
            "transport only allows while it holds no byte in flight: %r"
            % (transport.stream(1).state,))
        return report

    def _crossed(s, stage_01, transport, report):
        across = s.cross_check(report, transport)
        assert across == {"agree": True, "disagreements": []}, (
            "the report and the transport's own log say the same numbers for this "
            "run, and cross_check answered %r" % (across,))
        for key, wrong in (("bytes", report["bytes"] + 1),
                           ("streams", report["streams"] + 1)):
            doctored = dict(report)
            doctored[key] = wrong
            across = s.cross_check(doctored, transport)
            assert across["agree"] is False and len(across["disagreements"]) == 1, (
                "a %r of %r where the transport's log says otherwise is a "
                "disagreement and not a resolution: %r" % (key, wrong, across))
            assert key in across["disagreements"][0] and "%d" % (wrong,) in \
                across["disagreements"][0], (
                "the disagreement names the key and both numbers, and it says %r"
                % (across["disagreements"][0],))
        assert s.cross_check(report, transport)["agree"] is True, (
            "the same report checked twice disagrees the second time: the check keeps "
            "no state of its own")
        _refuses(stage_01.ProtocolError, "a report missing one of its keys",
                 lambda: s.cross_check({key: report[key] for key in report
                                        if key != "queued"}, transport),
                 names=("queued",))
        _refuses(stage_01.ProtocolError, "a report that is not a dict",
                 lambda: s.cross_check([], transport), names=("list",))
        _refuses(stage_01.ProtocolError, "something that is not a transport",
                 lambda: s.cross_check(report, object()), names=("object",))

    def _replayed(s, stage_01, streams, stage_05, stage_10, grants, broker):
        def scenario():
            """The scripted client side, rebuilt from nothing and run again."""
            return _script(streams, stage_01, stage_05, stage_10, grants, [])()
        first = s.replay(scenario)
        assert first == s.replay(scenario), (
            "two replays of one scenario are the same bytes, and they were not: a set "
            "or an unordered dict reached the wire")
        assert first == broker.trace().bytes(), (
            "the replay of this scenario is this run's trace: %d bytes against %d"
            % (len(first), len(broker.trace().bytes())))
        _refuses(stage_01.ProtocolError, "a scenario that is not callable",
                 lambda: s.replay(7), names=("int",))
        _refuses(stage_01.ProtocolError, "a scenario that answers no Broker",
                 lambda: s.replay(lambda: b"nope"), names=("bytes",))

    def _twice(seen):
        first, second = seen
        assert first["broker"].trace().bytes() == second["broker"].trace().bytes(), (
            "two runs of one scripted scenario write the same bytes, and these two "
            "wrote %d and %d" % (len(first["broker"].trace().bytes()),
                                 len(second["broker"].trace().bytes())))
        assert first["broker"].report() == second["broker"].report(), (
            "and count the same report: %r against %r"
            % (first["broker"].report(), second["broker"].report()))
        for name in ("one", "two", "two2", "three", "four"):
            assert first[name].heard == second[name].heard, (
                "%s heard two different runs of one script: %r against %r"
                % (name, first[name].heard, second[name].heard))
        assert first["transport"].log() == second["transport"].log(), (
            "the transport's own log of the two runs is the same transcript")

    import grants
    import stage_01
    import stage_05
    import stage_10
    import streams

    _keys(stage_10)
    _trace(stage_10, stage_01)
    _reader(stage_10, stage_01)
    seen = []
    run = _script(streams, stage_01, stage_05, stage_10, grants, seen)
    run()
    run()
    records = seen[0]
    _wires(stage_10, records, stage_01, stage_05)
    report = _account(stage_10, streams, records["broker"], records["transport"])
    _crossed(stage_10, stage_01, records["transport"], report)
    _replayed(stage_10, stage_01, streams, stage_05, stage_10, grants,
              records["broker"])
    _twice(seen)

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The fixed header and the variable-length integer",
        tags=["framing", "varint"],
        action="Write `ProtocolError`, `Incomplete`, `read_varint`, `write_varint` "
               "and `read_header` in stage_01.py.",
        predict="Why a length that says how long the rest is cannot be a fixed "
                "width, and what a reader does with a buffer that stops in the "
                "middle of one.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The two-byte string and the CONNECT",
        tags=["strings", "connect"],
        action="Write `read_string`, `read_payload`, `write_string`, `read_connect`, "
               "`connack_code` and `write_connack` in stage_02.py.",
        predict="Which of a CONNECT's fields are present is decided by one flags "
                "byte, and what a broker owes a client whose protocol name is right "
                "and whose level is not.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The topic filter, and the trie that matches it",
        tags=["topics", "trie", "wildcards"],
        action="Write `Trie`, `validate_topic`, `validate_filter` and `TopicError` "
               "in stage_03.py.",
        predict="What `a/#` matches beyond `a/b`, and why a filter that starts with "
                "a wildcard is not allowed to see a topic that starts with `$`.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="SUBSCRIBE, SUBACK and the granted QoS",
        tags=["subscribe", "qos"],
        action="Write `read_subscribe`, `read_unsubscribe`, `write_suback`, "
               "`write_unsuback`, `granted_qos` and `grant_codes` in stage_04.py.",
        predict="What a broker owes a client that asks for QoS 2 when the broker "
                "offers QoS 1, and what it answers for a filter it will not route.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="PUBLISH, routing, and what is retained",
        tags=["publish", "retain"],
        action="Write `read_publish`, `write_publish`, `Retained`, `route` and "
               "`deliveries` in stage_05.py.",
        predict="Which subscribers a retained message reaches when it is published, "
                "and which of them it reaches when they subscribe an hour later.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="QoS 1, the packet id, and the PUBACK",
        tags=["qos1", "packet-ids", "redelivery"],
        action="Write `PacketIds`, `InFlight`, `read_ack`, `write_puback` and "
               "`write_ack` in stage_06.py.",
        predict="What DUP means on the second transmission and never on the first, "
                "and who decides when a message is sent again when there is no wall "
                "clock to decide with.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="QoS 2, the four-way handshake",
        tags=["qos2", "handshake", "exactly-once"],
        action="Write `Sender`, `Receiver`, `write_pubrec`, `write_pubrel` and "
               "`write_pubcomp` in stage_07.py.",
        predict="Where an exactly-once promise is actually kept, and why an id may "
                "not be handed to another message before PUBCOMP arrives.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The session that outlives the socket",
        tags=["sessions", "will", "keep-alive"],
        action="Write `Sessions`, `deadline_from` and the queue and will rules in "
               "stage_08.py.",
        predict="Which of a broker's promises survive the connection that made "
                "them, and what a will is owed when the client says goodbye "
                "properly.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="Grants, denials, and the line written before the act",
        tags=["acl", "policy", "audit"],
        action="Write `allowed_publish`, `allowed_subscribe`, `decide` and "
               "`Ledger` in stage_09.py.",
        predict="What a client may do once its grants and the broker's own ceiling "
                "are compared, and what an MQTT broker can even say to a client "
                "about a publish it refuses.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="One scenario, twice, and the reader's verdict",
        tags=["capstone", "cross-check", "determinism"],
        action="Write `Broker`, `Trace`, `read_frames`, `cross_check` and `replay` "
               "in stage_10.py.",
        predict="Which number in the broker's own report the transport's log will "
                "disagree with first, and why a trace that is not byte-identical "
                "twice proves nothing at all.",
        check=check_10,
    ),
]
