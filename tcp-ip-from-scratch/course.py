"""TCP/IP From Scratch — course manifest.

Ten graded stages between a link that carries frames and a stack whose every
decision can be held against the wire's own log. The world is provided and
complete: `wire.py` is the link — `Wire(rules)` carries `bytes` from a MAC to a
MAC, one tick of latency, exactly one delivery per frame except when a rule says
otherwise (`loss` names the ordinals that never arrive, `duplicate` the ones that
arrive twice, `delay` the ones that arrive late, and `order` whether the frames
handed over at a tick keep the order they were sent), a full event log (`send`,
`drop`, `hold`, `duplicate`, `deliver`) that the course's own ledger is checked
against, and `mac_text`, the one address parser; `hosts.py` is the peers — a
`Host` with a box of frames addressed to it or to everybody, a `Router` whose
ports each answer to their own MAC, a `Clock`, the five-peer name table
(`router`, `web`, `dns`, `db`, `client`) and `HostsError`.

The thesis of the whole course is one sentence, and every stage's check asserts
it: A NETWORK STACK IS WHAT YOU WRITE AFTER THE LINK LOSES THE FRAME YOU ASSUMED
ARRIVED. Each stage exists because the one before it left a hole: a frame is a
type field and nothing more, so a peer has to be asked for an address before it
can be addressed; an address that never ages is an address that lies; a datagram
with no hop limit circulates forever; an error with no message is an error nobody
learns about; a connection whose state machine is not a state machine answers
segments it never agreed to; a window with no cumulative acknowledgement loses
data the sender believed was sent; an API whose calls are not a table cannot
answer a call it does not have; a timer that does not double floods the link it
is trying to help; a connection that never closes holds what the other side has
already released; and only a session proves any of it, because only a session is
run against the record the wire kept.

The failures worth preventing are the ones that look like success: padding
counted as payload, an ARP entry that ages out but is still returned, a checksum
verdict raised as an exception, a duplicate SYN resetting a connection, an
acknowledgement that covers one segment, a descriptor reused while it is still in
use, a timeout that never doubles, a TIME_WAIT deadline measured from the wrong
tick, and a ledger counted from the stack's beliefs instead of the wire's log.

Standard library only, offline, deterministic, **ints only** (every port,
sequence number, acknowledgement, tick, window, length, checksum and address —
there is no float literal anywhere in this course): no `time`, no `threading`, no
`asyncio`, no `random`, no `os`, no sockets, no subprocesses, no wall clock, no
module-level mutable state, and no `statistics`, `math`, `decimal` or `fractions`
either — the last four would decide by themselves the two things this course
decides by hand (the one's-complement sum, and how a window that moved by three
segments is spelled). The wire is the clock: time passes only through
`Wire.advance` and the `now` argument a stage is handed, and every count the
course needs is an exact integer.

The salvaged curriculum in `linux-from-scratch/` is the other half of this unit:
176 exercises on real hardware across fifteen phases, and its own README says it
cannot ship a checker. This is that checker, on a link small enough to grade.

    python3 codecraft/cli.py run tcp-ip-from-scratch
"""

from codecraft.api import stage

TITLE = "TCP/IP From Scratch"
DESCRIPTION = ("The frame as the input and the wire's own log as the output: a "
               "frame whose type field is the only thing it says about its "
               "payload, an ARP cache whose entries age out instead of lying, an "
               "IPv4 header whose hop count is spent before the datagram can "
               "circulate forever, an ICMP error that quotes the datagram it "
               "refuses, a handshake that is a state machine answering only the "
               "segments it agreed to, a sliding window whose acknowledgement "
               "covers everything behind it, a socket API answered as a table of "
               "calls, a retransmission timer that doubles for the oldest "
               "segment still unacknowledged, a close with TIME_WAIT as a state "
               "with a deadline rather than a sleep, and a session whose ledger "
               "the wire's own event log is the tie-breaker for.")
LEVEL = "advanced"
ORDER = 26


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "tcp-ip-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

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
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import stage_01 as s
    from wire import BROADCAST_MAC, Wire
    from hosts import Host, MACS, NAMES, ip_of, mac_of

    web_mac, web_ip = mac_of("web"), ip_of("web")
    client_mac, client_ip = mac_of("client"), ip_of("client")

    # ---- the constants ----------------------------------------------------

    assert s.ETHERNET_HEADER == 14, (
        "a frame's header is dst(6) | src(6) | type(2): %r" % (s.ETHERNET_HEADER,))
    assert s.MIN_FRAME == 60, (
        "the least a frame may be on the wire is 60 bytes: %r" % (s.MIN_FRAME,))
    assert s.TYPES == {0x0800: "ipv4", 0x0806: "arp"}, (
        "the two types this course speaks: %r" % (s.TYPES,))
    assert set(NAMES) == set(MACS), (
        "the world's two tables name the same peers: %r vs %r"
        % (sorted(NAMES), sorted(MACS)))

    # ---- the address conversion -------------------------------------------

    assert s.mac_bytes(web_mac) == bytes((0x10, 0, 0, 0, 0, 0x02)), (
        "mac_bytes(%r) is the six bytes of that address: %r"
        % (web_mac, s.mac_bytes(web_mac)))
    assert s.mac_bytes(b"\x10\x00\x00\x00\x00\x05") == b"\x10\x00\x00\x00\x00\x05", (
        "mac_bytes takes six bytes as they are")
    assert s.mac_bytes(BROADCAST_MAC) == b"\xff" * 6, (
        "the broadcast address is six 0xff bytes: %r" % (s.mac_bytes(BROADCAST_MAC),))
    for bad in ("10:00:00:00:00", "AA:BB:CC:DD:EE:FF", "10-00-00-00-00-02", 2,
                None, b"\x10\x00", ""):
        _refuses(s.FrameError, "mac_bytes(%r)" % (bad,),
                 lambda bad=bad: s.mac_bytes(bad), names=(repr(bad),))

    # ---- the type table, both ways ----------------------------------------

    assert s.type_name(0x0800) == "ipv4", (
        "0x0800 is ipv4: %r" % (s.type_name(0x0800),))
    assert s.type_name(0x0806) == "arp", (
        "0x0806 is arp: %r" % (s.type_name(0x0806),))
    assert s.type_number("ipv4") == 0x0800, (
        "ipv4 is numbered 0x0800: %r" % (s.type_number("ipv4"),))
    assert s.type_number("arp") == 0x0806, (
        "arp is numbered 0x0806: %r" % (s.type_number("arp"),))
    for name in sorted(s.TYPES.values()):
        assert s.type_name(s.type_number(name)) == name, (
            "the type round trip: %r" % (name,))
    _refuses(s.FrameError, "type_name of a number nobody knows",
             lambda: s.type_name(0x0805), names=("2053",))
    _refuses(s.FrameError, "type_name of something that is not a number at all",
             lambda: s.type_name("ipv4"), names=("'ipv4'",))
    _refuses(s.FrameError, "type_name of True",
             lambda: s.type_name(True), names=("True",))
    _refuses(s.FrameError, "type_number of a name nobody knows",
             lambda: s.type_number("ipv5"), names=("'ipv5'",))
    _refuses(s.FrameError, "type_number of the empty name",
             lambda: s.type_number(""), names=("''", "empty"))
    _refuses(s.FrameError, "type_number of a number",
             lambda: s.type_number(0x0800), names=("2048", "string"))

    # ---- the broadcast question -------------------------------------------

    assert s.is_broadcast(BROADCAST_MAC) is True, (
        "the broadcast address is the broadcast address")
    assert s.is_broadcast(b"\xff" * 6) is True, (
        "and it is the same six bytes when the wire spells them as bytes")
    assert s.is_broadcast(web_mac) is False, (
        "web's address is not the broadcast address: %r" % (web_mac,))
    assert s.is_broadcast(mac_of("router")) is False, (
        "and neither is the router's")
    _refuses(s.FrameError, "is_broadcast of an int",
             lambda: s.is_broadcast(0), names=("not 0",))
    _refuses(s.FrameError, "is_broadcast of None",
             lambda: s.is_broadcast(None), names=("None",))

    # ---- the message this stage is a frame for ----------------------------

    # A real ARP request body: an address, and the address being asked about.
    # Stage 2 owns this message; stage 1 must not care what is in it.
    message = (b"\x00\x01" + b"\x08\x00" + b"\x06" + b"\x04" + b"\x00\x01"
               + s.mac_bytes(web_mac) + bytes((10, 0, 0, 2))
               + b"\xff" * 6 + bytes((10, 0, 0, 1)))
    assert len(message) == 28, "the message is 28 bytes: %r" % (len(message),)

    # ---- build ------------------------------------------------------------

    frame = s.build(BROADCAST_MAC, web_mac, "arp", message)
    assert frame[:6] == b"\xff" * 6, (
        "the first six bytes are the destination: %r" % (frame[:6],))
    assert frame[6:12] == s.mac_bytes(web_mac), (
        "the next six are the source: %r" % (frame[6:12],))
    assert frame[12:14] == b"\x08\x06", (
        "then the type, most significant byte first: %r" % (frame[12:14],))
    assert frame[14:42] == message, (
        "and then the payload as it was handed over: %r" % (frame[14:42],))
    assert len(frame) == s.MIN_FRAME == 60, (
        "build pads a short frame out to MIN_FRAME: %d" % (len(frame),))
    assert frame[42:] == b"\x00" * 18, (
        "the padding is trailing zero bytes: %r" % (frame[42:],))
    assert s.build(BROADCAST_MAC, web_mac, 0x0806, message) == frame, (
        "a type may be given as its number as well as by its name")

    exact = s.build(BROADCAST_MAC, web_mac, 0x0806, message, pad=False)
    assert len(exact) == s.ETHERNET_HEADER + 28 == 42, (
        "pad=False is a frame that stays short: %d" % (len(exact),))
    assert exact == frame[:42], (
        "and it is the same bytes as the padded frame's first 42: %r" % (exact,))

    # A payload of exactly 46 bytes fills a frame; it is not a limit.
    full = s.build(BROADCAST_MAC, web_mac, "arp", b"\xaa" * 46)
    assert len(full) == s.MIN_FRAME == 60, (
        "46 bytes of payload already make a frame of MIN_FRAME: %d" % (len(full),))
    assert full[14:] == b"\xaa" * 46, (
        "and no padding was added: %r" % (full[14:],))
    assert s.build(BROADCAST_MAC, web_mac, "arp", b"\xaa" * 47) == full + b"\xaa", (
        "47 bytes of payload make a frame one byte longer than MIN_FRAME")

    long_payload = b"\x00" * 1500
    assert len(s.build(BROADCAST_MAC, web_mac, "arp", long_payload, pad=False)) == 1514, (
        "a payload of 1500 bytes is legal, and pad=False is the frame that shows it")
    assert len(s.build(BROADCAST_MAC, web_mac, "ipv4", b"", pad=False)) == 14, (
        "an empty payload is a frame of nothing but its header")

    _refuses(s.FrameError, "a payload of 1501 bytes",
             lambda: s.build(BROADCAST_MAC, web_mac, "arp", b"\x00" * 1501),
             names=("1501",))
    _refuses(s.FrameError, "build with a type number nobody knows",
             lambda: s.build(BROADCAST_MAC, web_mac, 0x0805, b""),
             names=("2053",))
    _refuses(s.FrameError, "build with a type name nobody knows",
             lambda: s.build(BROADCAST_MAC, web_mac, "ipv5", b""),
             names=("'ipv5'",))
    _refuses(s.FrameError, "build with the empty type name",
             lambda: s.build(BROADCAST_MAC, web_mac, "", b""), names=("''",))
    _refuses(s.FrameError, "build with a payload that is not bytes",
             lambda: s.build(BROADCAST_MAC, web_mac, "arp", "arp"),
             names=("str",))
    _refuses(s.FrameError, "build with a destination the wire refuses",
             lambda: s.build("nope", web_mac, "arp", b""), names=("'nope'",))
    _refuses(s.FrameError, "build with a source the wire refuses",
             lambda: s.build(BROADCAST_MAC, b"\x01\x02", "arp", b""),
             names=("2",))

    # ---- parse ------------------------------------------------------------

    parsed = s.parse(frame)
    assert parsed["dst"] == BROADCAST_MAC, (
        "parse reports the destination in the wire's text form: %r"
        % (parsed["dst"],))
    assert parsed["src"] == web_mac, (
        "and the source: %r" % (parsed["src"],))
    assert parsed["type"] == "arp", (
        "the type is a name, not the number the wire carries: %r" % (parsed["type"],))
    assert parsed["type"] == s.type_name(int.from_bytes(frame[12:14], "big")), (
        "and it is the name of the number that is in the frame")
    assert parsed["payload"] == message + b"\x00" * 18, (
        "the payload is what is after the header, exactly as it arrived — the "
        "message and the padding the frame was built with: %r" % (parsed["payload"],))
    assert parsed["payload"][:len(message)] == message, (
        "the message is the first 28 bytes of it, whatever the padding is")
    assert set(parsed) == {"dst", "src", "type", "payload"}, (
        "a frame has exactly four facts: %r" % (sorted(parsed),))

    short = s.parse(exact)
    assert short["payload"] == message, (
        "an unpadded frame's payload is the message and nothing else: %r"
        % (short["payload"],))
    assert short["dst"] == BROADCAST_MAC and short["src"] == web_mac, (
        "and the addresses do not depend on the length: %r" % (short,))
    assert s.parse(s.build(BROADCAST_MAC, web_mac, "ipv4", b""))["payload"] == b"\x00" * 46, (
        "an empty payload is still padded out to MIN_FRAME, so parse sees the "
        "padding as payload: 46 bytes")
    assert s.parse(frame[:14])["payload"] == b"", (
        "a frame of exactly the header has an empty payload: %r"
        % (s.parse(frame[:14]),))

    for bad, why in ((frame[:13], "13 bytes"), (b"", "nothing"), (b"\x00" * 6, "six")):
        _refuses(s.FrameError, "parse of a frame of %s" % (why,),
                 lambda bad=bad: s.parse(bad), names=("at least", str(len(bad))))
    _refuses(s.FrameError, "parse of a frame that is not bytes",
             lambda: s.parse("a frame"), names=("str",))
    _refuses(s.FrameError, "parse of a frame whose type nobody knows",
             lambda: s.parse(b"\x00" * 12 + b"\x08\x05" + b"\x00" * 46),
             names=("2053",))

    # ---- describe ---------------------------------------------------------

    line = s.describe(exact)
    assert line == "web -> ff:ff:ff:ff:ff:ff arp 28 bytes", (
        "describe spells the frame out: %r" % (line,))
    assert s.describe(frame) == "web -> ff:ff:ff:ff:ff:ff arp 46 bytes", (
        "the length describe reports is the payload's, padding included — the "
        "frame is 60 bytes and it says 46, which is what parse handed back: %r"
        % (s.describe(frame),))
    assert s.describe(s.build(mac_of("db"), mac_of("dns"), "ipv4", b"\x45" * 52)) == (
        "dns -> db ipv4 52 bytes"), (
        "the source comes before the destination, and a payload longer than the "
        "padding leaves the frame longer than MIN_FRAME: %r"
        % (s.describe(s.build(mac_of("db"), mac_of("dns"), "ipv4", b"\x45" * 52)),))
    assert len(s.build(mac_of("dns"), mac_of("db"), "ipv4", b"\x45" * 52)) == 66, (
        "52 bytes of payload make a frame of 66, which is above MIN_FRAME and is "
        "not padded: %d"
        % (len(s.build(mac_of("dns"), mac_of("db"), "ipv4", b"\x45" * 52)),))
    assert s.describe(s.build("10:00:00:00:00:99", web_mac, "arp", message)) == (
        "web -> 10:00:00:00:00:99 arp 46 bytes"), (
        "an address the world does not know is printed in its own text form: %r"
        % (s.describe(s.build("10:00:00:00:00:99", web_mac, "arp", message)),))
    assert "ipv4" in s.describe(s.build(web_mac, client_mac, "ipv4", message)), (
        "describe prints the type's name where it promised the name: %r"
        % (s.describe(s.build(web_mac, client_mac, "ipv4", message)),))

    # ---- the frame on a real wire, between real hosts ---------------------

    wire = Wire()
    web = Host("web", web_ip, web_mac, wire)
    client = Host("client", client_ip, client_mac, wire)
    router = Host("router", ip_of("router"), mac_of("router"), wire)

    ordinal = web.send(BROADCAST_MAC, frame)
    assert ordinal == 1, "the first send on a fresh wire is ordinal 1: %r" % (ordinal,)
    assert web.sent() == 1, "the host counts its own sends: %r" % (web.sent(),)
    assert wire.sent() == 1 and wire.delivered() == 0, (
        "the frame is on the link and has not arrived: %r sent, %r delivered"
        % (wire.sent(), wire.delivered()))
    assert wire.pending() == [{"ordinal": 1, "due": 1, "src": web_mac,
                               "dst": BROADCAST_MAC}], (
        "every frame takes one tick to cross: %r" % (wire.pending(),))
    assert wire.tick() == 0, "and no time has passed yet: %r" % (wire.tick(),)

    wire.advance(1)
    assert wire.tick() == 1 and wire.delivered() == 1, (
        "one tick later the frame has been handed over: %r delivered at tick %r"
        % (wire.delivered(), wire.tick()))
    arrivals = wire.deliver()
    assert [record["data"] for record in arrivals] == [frame], (
        "the link handed over exactly the bytes it was given: %r" % (arrivals,))
    assert [record["ordinal"] for record in arrivals] == [ordinal], (
        "and it knows which send they came from: %r" % (arrivals,))
    assert client.inbox() == [frame], (
        "a frame addressed to the broadcast address is in every host's box: %r"
        % (client.inbox(),))
    assert router.inbox() == [frame], (
        "every host on the link, not just the ones a check remembered: %r"
        % (router.inbox(),))

    taken = client.recv()
    assert taken == [frame], "a host hands up what arrived: %r" % (taken,)
    assert client.recv() == [], (
        "and `recv` takes them, so the second read says nothing arrived")
    assert client.inbox() == [frame], (
        "the box still holds what was taken, which is how a check sees it later")
    out = s.parse(taken[0])
    assert out["payload"][:len(message)] == message, (
        "the payload that came out the other end is the payload that went in: %r"
        % (out["payload"],))
    assert out["src"] == web_mac and out["dst"] == BROADCAST_MAC, (
        "and so are the addresses: %r" % (out,))

    # A unicast frame reaches the one host it names and nobody else.
    wire = Wire()
    web = Host("web", web_ip, web_mac, wire)
    client = Host("client", client_ip, client_mac, wire)
    router = Host("router", ip_of("router"), mac_of("router"), wire)
    unicast = s.build(client_mac, web_mac, "arp", message)
    web.send(client_mac, unicast)
    wire.advance(1)
    assert client.inbox() == [unicast], (
        "the addressed host has it: %r" % (client.inbox(),))
    assert web.inbox() == [] and router.inbox() == [], (
        "and the other two do not: %r and %r" % (web.inbox(), router.inbox()))
    assert client.recv() == [unicast] and client.recv() == [], (
        "a host reads its box and takes what it read")

    # ---- the number the stage cannot know, and the world can --------------

    # Every number the stage returns about this frame is right: the addresses,
    # the type, the payload it says it got. What it cannot say — what nobody but
    # the layer above can say — is how long the *message* is, because a payload
    # of 46 bytes and a payload of 28 bytes followed by 18 zero bytes are the
    # same bytes on the wire. The world's record is the frame; the message's own
    # length is stage 2's `ARP_LENGTH`, and the difference is the first real
    # decision of the course.
    wire = Wire()
    web = Host("web", web_ip, web_mac, wire)
    client = Host("client", client_ip, client_mac, wire)
    web.send(client_mac, frame)
    wire.advance(1)
    record = [event for event in wire.log() if event["event"] == "send"][0]
    assert len(record["data"]) == s.MIN_FRAME == 60, (
        "the wire carried the padded frame: %d bytes" % (len(record["data"]),))
    assert s.parse(record["data"])["payload"] == message + b"\x00" * 18, (
        "the stage reports the frame's payload, padding and all: %r"
        % (s.parse(record["data"])["payload"],))
    assert len(s.parse(record["data"])["payload"]) == 46 and len(message) == 28, (
        "which is 46 bytes of frame and 28 bytes of message: %r and %r"
        % (len(s.parse(record["data"])["payload"]), len(message)))
    assert s.describe(record["data"]).endswith("46 bytes"), (
        "and describe reports the frame's number, not the message's: %r"
        % (s.describe(record["data"]),))
    assert client.recv()[0] == record["data"], (
        "what came out of the box is what the wire's log says was handed over")

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "tcp-ip-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so an exception of the
        right family raised for the wrong reason is not the refusal the contract
        asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import stage_01 as s1
    import stage_02 as s
    from wire import BROADCAST_MAC, Wire
    from hosts import Host, MACS, NAMES, ip_of, mac_of

    client_mac, client_ip = mac_of("client"), ip_of("client")
    web_mac, web_ip = mac_of("web"), ip_of("web")
    dns_mac, dns_ip = mac_of("dns"), ip_of("dns")
    db_mac, db_ip = mac_of("db"), ip_of("db")

    # ---- the constants ----------------------------------------------------

    assert s.ARP_LENGTH == 28, (
        "an arp message is 28 bytes: %r" % (s.ARP_LENGTH,))
    assert s.ARP_REQUEST == 1 and s.ARP_REPLY == 2, (
        "a request is 1 and a reply is 2: %r and %r"
        % (s.ARP_REQUEST, s.ARP_REPLY))
    assert s.CACHE_TICKS == 8, (
        "a learned address is believed for 8 ticks: %r" % (s.CACHE_TICKS,))

    question = s.build_message(s.ARP_REQUEST, client_mac, client_ip,
                               BROADCAST_MAC, web_ip)
    answer = s.build_message(s.ARP_REPLY, web_mac, web_ip, client_mac, client_ip)

    # ---- build_message ----------------------------------------------------

    assert len(question) == s.ARP_LENGTH == 28, (
        "the message is ARP_LENGTH bytes, not %d" % (len(question),))
    assert question == (b"\x00\x01" + b"\x08\x00" + bytes((6, 4)) + b"\x00\x01"
                        + s1.mac_bytes(client_mac) + bytes((10, 0, 0, 5))
                        + b"\xff" * 6 + bytes((10, 0, 0, 2))), (
        "the 28 bytes, in the layout the contract freezes: %r" % (question,))
    assert answer == (b"\x00\x01" + b"\x08\x00" + bytes((6, 4)) + b"\x00\x02"
                      + s1.mac_bytes(web_mac) + bytes((10, 0, 0, 2))
                      + s1.mac_bytes(client_mac) + bytes((10, 0, 0, 5))), (
        "and a reply puts the answer in sha/spa and the asker in tha/tpa: %r"
        % (answer,))
    assert s.build_message(s.ARP_REPLY, s1.mac_bytes(web_mac), bytes((10, 0, 0, 2)),
                           s1.mac_bytes(client_mac), bytes((10, 0, 0, 5))) == answer, (
        "a MAC may be given as six bytes and an address as four octets")
    assert s.build_message(s.ARP_REQUEST, client_mac, client_ip, BROADCAST_MAC,
                           web_ip) == question, (
        "and the same message twice is the same 28 bytes")

    _refuses(s.ArpError, "an operation nobody knows",
             lambda: s.build_message(3, client_mac, client_ip, BROADCAST_MAC, web_ip),
             names=("3",))
    _refuses(s.ArpError, "the operation zero",
             lambda: s.build_message(0, client_mac, client_ip, BROADCAST_MAC, web_ip),
             names=("0",))
    _refuses(s.ArpError, "an operation that is a name rather than a number",
             lambda: s.build_message("request", client_mac, client_ip,
                                     BROADCAST_MAC, web_ip),
             names=("'request'",))
    _refuses(s.ArpError, "a sender that is five bytes of MAC",
             lambda: s.build_message(s.ARP_REQUEST, b"\x01\x02\x03\x04\x05",
                                     client_ip, BROADCAST_MAC, web_ip),
             names=("5",))
    _refuses(s.ArpError, "a sender whose MAC the wire refuses",
             lambda: s.build_message(s.ARP_REQUEST, "nope", client_ip,
                                     BROADCAST_MAC, web_ip), names=("'nope'",))
    _refuses(s.ArpError, "a target MAC that is not text and not six bytes",
             lambda: s.build_message(s.ARP_REQUEST, client_mac, client_ip, 7, web_ip),
             names=("7",))
    _refuses(s.ArpError, "a sender ip of three octets",
             lambda: s.build_message(s.ARP_REQUEST, client_mac, b"\x0a\x00\x00",
                                     BROADCAST_MAC, web_ip), names=("3",))
    _refuses(s.ArpError, "a target ip with three parts",
             lambda: s.build_message(s.ARP_REQUEST, client_mac, client_ip,
                                     BROADCAST_MAC, "10.0.0"), names=("10.0.0",))
    _refuses(s.ArpError, "a target ip with an octet above 255",
             lambda: s.build_message(s.ARP_REQUEST, client_mac, client_ip,
                                     BROADCAST_MAC, "10.0.0.256"),
             names=("10.0.0.256",))
    _refuses(s.ArpError, "a target ip that is not text at all",
             lambda: s.build_message(s.ARP_REQUEST, client_mac, client_ip,
                                     BROADCAST_MAC, None), names=("None",))

    # ---- parse_message ----------------------------------------------------

    parsed = s.parse_message(question)
    assert parsed == {"op": s.ARP_REQUEST, "sender": client_mac,
                      "sender_ip": client_ip, "target": BROADCAST_MAC,
                      "target_ip": web_ip}, (
        "the message's five facts, in their text forms: %r" % (parsed,))
    assert set(parsed) == {"op", "sender", "sender_ip", "target", "target_ip"}, (
        "an arp message has exactly five facts: %r" % (sorted(parsed),))
    assert s.parse_message(answer) == {"op": s.ARP_REPLY, "sender": web_mac,
                                       "sender_ip": web_ip, "target": client_mac,
                                       "target_ip": client_ip}, (
        "and the reply's: %r" % (s.parse_message(answer),))
    assert s.parse_message(question) == s.parse_message(question), (
        "parsing is a read, not an act: the same bytes give the same facts")

    _refuses(s.ArpError, "a message one byte short",
             lambda: s.parse_message(question[:27]), names=("27",))
    _refuses(s.ArpError, "a message one byte long",
             lambda: s.parse_message(question + b"\x00"), names=("29",))
    _refuses(s.ArpError, "the empty message",
             lambda: s.parse_message(b""), names=("0",))
    _refuses(s.ArpError, "a message that is not bytes",
             lambda: s.parse_message("an arp message"), names=("str",))
    _refuses(s.ArpError, "a hardware type this stack does not speak",
             lambda: s.parse_message(b"\x00\x02" + question[2:]), names=("2",))
    _refuses(s.ArpError, "a protocol type this stack does not speak",
             lambda: s.parse_message(question[:2] + b"\x08\x06" + question[4:]),
             names=("2054",))
    _refuses(s.ArpError, "an hlen that is not six",
             lambda: s.parse_message(question[:4] + bytes((5,)) + question[5:]),
             names=("5",))
    _refuses(s.ArpError, "a plen that is not four",
             lambda: s.parse_message(question[:5] + bytes((6,)) + question[6:]),
             names=("6",))
    _refuses(s.ArpError, "an operation nobody knows",
             lambda: s.parse_message(question[:6] + b"\x00\x09" + question[8:]),
             names=("9",))

    # ---- reply_to ---------------------------------------------------------

    assert s.reply_to(question, web_mac, web_ip) == answer, (
        "the reply to the client's question is the answer's 28 bytes")
    assert s.parse_message(s.reply_to(question, web_mac, web_ip)) == {
        "op": s.ARP_REPLY, "sender": web_mac, "sender_ip": web_ip,
        "target": client_mac, "target_ip": client_ip}, (
        "which is what lets the asker learn the pair it asked about")
    for name in ("dns", "db", "router"):
        _refuses(s.ArpError, "reply_to for a request aimed at web, answered by %s"
                 % (name,),
                 lambda name=name: s.reply_to(question, mac_of(name), ip_of(name)),
                 names=(web_ip,))
    not_a_request = s.build_message(s.ARP_REPLY, client_mac, client_ip,
                                    web_mac, web_ip)
    _refuses(s.ArpError, "reply_to for a message that is a reply, aimed at this "
             "very pair",
             lambda: s.reply_to(not_a_request, web_mac, web_ip),
             names=("2", "request"))
    _refuses(s.ArpError, "reply_to for a message that is not a message",
             lambda: s.reply_to(question[:10], web_mac, web_ip), names=("10",))
    aimed_elsewhere = s.build_message(s.ARP_REQUEST, client_mac, client_ip,
                                      dns_mac, web_ip)
    _refuses(s.ArpError, "reply_to for a request unicast to another host's MAC",
             lambda: s.reply_to(aimed_elsewhere, web_mac, web_ip),
             names=(dns_mac,))
    aimed_at_me = s.build_message(s.ARP_REQUEST, client_mac, client_ip, web_mac,
                                  web_ip)
    assert s.reply_to(aimed_at_me, web_mac, web_ip) == answer, (
        "and a request unicast to this MAC for this address is answered, because "
        "a broadcast naming no single host is not the only request there is")
    assert s.reply_to(question, s1.mac_bytes(web_mac), bytes((10, 0, 0, 2))) == answer, (
        "reply_to takes this pair in either form, like everything else")

    # ---- the broadcast reaches every host, and only one answers -----------

    wire = Wire()
    peers = {name: Host(name, ip_of(name), mac_of(name), wire)
             for name in sorted(NAMES)}
    client, web = peers["client"], peers["web"]
    asked = s1.build(BROADCAST_MAC, client_mac, "arp", question)
    ordinal = client.send(BROADCAST_MAC, asked)
    assert ordinal == 1 and wire.sent() == 1, (
        "the question is on the link: ordinal %r" % (ordinal,))
    wire.advance(1)
    for name in sorted(NAMES):
        assert peers[name].inbox() == [asked], (
            "a broadcast frame is in every host's box, and %s's holds %r"
            % (name, peers[name].inbox()))
    assert [record["dst"] for record in wire.deliver()] == [BROADCAST_MAC], (
        "the link hands it over addressed to the broadcast address: %r"
        % (wire.deliver(),))
    only_one = s.reply_to(question, web_mac, web_ip)
    assert s.parse_message(only_one)["sender"] == web_mac, (
        "only the host that was asked has an answer: %r"
        % (s.parse_message(only_one),))

    client.recv()
    answered = s1.build(client_mac, web_mac, "arp", only_one)
    web.send(client_mac, answered)
    wire.advance(1)
    assert client.inbox() == [asked, answered], (
        "the answer is addressed to the asker and nobody else: %r"
        % (client.inbox(),))
    assert peers["dns"].inbox() == [asked] and peers["db"].inbox() == [asked], (
        "and the other hosts' boxes still hold the question and nothing more: %r"
        % (peers["dns"].inbox(),))
    heard = client.recv()
    assert heard == [answered], (
        "the asker reads the answer out of its box: %r" % (heard,))
    learned = s.parse_message(s1.parse(answered)["payload"][:s.ARP_LENGTH])
    assert (learned["sender"], learned["sender_ip"]) == (web_mac, web_ip), (
        "and the pair it learned is the pair it asked about: %r" % (learned,))

    # ---- request: the whole exchange over a real wire ---------------------

    # The link is one tick wide and `request` owns the whole wait, so the peer's
    # answer is put on the link first and held: ordinal 1 is held two ticks, so
    # it arrives at tick 3, after the question crossed at tick 1.
    wire = Wire({"delay": {1: 2}})
    client = Host("client", client_ip, client_mac, wire)
    web = Host("web", web_ip, web_mac, wire)
    held = s.reply_to(question, web_mac, web_ip)
    web.send(client_mac, s1.build(client_mac, web_mac, "arp", held))
    assert wire.pending() == [{"ordinal": 1, "due": 3, "src": web_mac,
                               "dst": client_mac}], (
        "the answer is held, so it is due three ticks from now — after the "
        "question the asker is about to send, which takes one: %r"
        % (wire.pending(),))
    found = s.request(wire, client, web_ip)
    assert found == {"ip": web_ip, "mac": web_mac, "sent": 2, "received": True,
                     "ticks": s.CACHE_TICKS}, (
        "the exchange: %r — `sent` is the send ordinal the wire gave the "
        "question, which is 2 because the held answer was ordinal 1" % (found,))
    assert wire.tick() == s.CACHE_TICKS == 8, (
        "the wire was advanced by the ticks request promised to wait: %r"
        % (wire.tick(),))
    assert wire.sent() == 2 and client.sent() == 1 and web.sent() == 1, (
        "one question and one answer crossed the link: %r"
        % (wire.sent(),))
    sends = [event for event in wire.log() if event["event"] == "send"]
    assert sends[0]["dst"] == client_mac and sends[1]["dst"] == BROADCAST_MAC, (
        "the question is the frame addressed to the broadcast address: %r"
        % ([event["dst"] for event in sends],))
    arrivals = [event for event in wire.log() if event["event"] == "deliver"]
    assert [event["ordinal"] for event in arrivals] == [1, 2], (
        "the link hands over its due frames in send order, the held answer "
        "first: %r" % ([event["ordinal"] for event in arrivals],))
    assert [event["tick"] for event in arrivals] == [s.CACHE_TICKS, s.CACHE_TICKS], (
        "and one advance lands on one tick, which is where its deliveries are "
        "logged: %r" % ([event["tick"] for event in arrivals],))
    assert [event["dst"] for event in arrivals] == [client_mac, BROADCAST_MAC], (
        "the answer is the frame addressed to the asker and the question is the "
        "one addressed to everybody: %r" % ([event["dst"] for event in arrivals],))
    assert sends[1]["data"] == s1.build(BROADCAST_MAC, client_mac, "arp", question), (
        "and the bytes the wire carries are the frame `build` would have made: %r"
        % (sends[1]["data"],))

    # ---- nobody answers, and a reply about another address ----------------

    wire = Wire()
    client = Host("client", client_ip, client_mac, wire)
    nobody = s.request(wire, client, web_ip)
    assert nobody == {"ip": web_ip, "mac": None, "sent": 1, "received": False,
                      "ticks": s.CACHE_TICKS}, (
        "an unanswered question is a result and not a stack that spins: %r"
        % (nobody,))
    assert wire.tick() == 8 and wire.sent() == 1 and wire.dropped() == 0, (
        "the wait is eight ticks and one frame: %r at tick %r"
        % (wire.sent(), wire.tick()))
    assert client.recv() == [], (
        "and nothing came back to the asker: %r" % (client.recv(),))

    wire = Wire()
    client = Host("client", client_ip, client_mac, wire)
    db = Host("db", db_ip, db_mac, wire)
    someone_else = s.build_message(s.ARP_REQUEST, client_mac, client_ip,
                                   BROADCAST_MAC, db_ip)
    db.send(client_mac, s1.build(client_mac, db_mac, "arp",
                                 s.reply_to(someone_else, db_mac, db_ip)))
    wrong = s.request(wire, client, web_ip)
    assert wrong["mac"] is None and wrong["received"] is False, (
        "a reply about another address is not this exchange's answer: %r"
        % (wrong,))
    assert wrong["ticks"] == s.CACHE_TICKS, (
        "and the asker waited the whole time for an answer about %s: %r"
        % (web_ip, wrong["ticks"]))

    # A reply whose pair is the answer's, but which is addressed to another
    # host (or to the broadcast address), is a cache poison and not an answer.
    wire = Wire()
    client = Host("client", client_ip, client_mac, wire)
    db = Host("db", db_ip, db_mac, wire)
    db.send(client_mac, s1.build(client_mac, db_mac, "arp",
             s.build_message(s.ARP_REPLY, web_mac, web_ip, dns_mac, dns_ip)))
    db.send(client_mac, s1.build(client_mac, db_mac, "arp",
             s.build_message(s.ARP_REPLY, web_mac, web_ip, BROADCAST_MAC, client_ip)))
    poisoned = s.request(wire, client, web_ip)
    assert poisoned["mac"] is None and poisoned["received"] is False, (
        "a reply addressed to another host, or to everybody, is not this "
        "asker's answer: %r" % (poisoned,))

    # `now` moves the deadline, and the report is read off the wire's clock.
    wire = Wire()
    client = Host("client", client_ip, client_mac, wire)
    late = s.request(wire, client, web_ip, now=20)
    assert late["ticks"] == 28 and wire.tick() == 28, (
        "a wait counted from `now` lands at now + CACHE_TICKS: %r at tick %r"
        % (late["ticks"], wire.tick()))
    wire = Wire()
    client = Host("client", client_ip, client_mac, wire)
    wire.advance(5)
    behind = s.request(wire, client, web_ip, now=0)
    assert behind["ticks"] == 3 and wire.tick() == 8, (
        "and a deadline already five ticks behind is three ticks of waiting: %r "
        "at tick %r" % (behind["ticks"], wire.tick()))
    _refuses(s.ArpError, "a negative now",
             lambda: s.request(Wire(), Host("client", client_ip, client_mac, None),
                               web_ip, now=-1), names=("-1",))
    _refuses(s.ArpError, "an address that is not an address",
             lambda: s.request(Wire(), Host("client", client_ip, client_mac, None),
                               "10.0.0.256"), names=("10.0.0.256",))

    # ---- the frame's length and the message's are two different numbers ---

    wire = Wire()
    client = Host("client", client_ip, client_mac, wire)
    s.request(wire, client, web_ip)
    carried = [event for event in wire.log() if event["event"] == "send"][0]["data"]
    envelope = s1.parse(carried)
    assert len(carried) == s1.MIN_FRAME == 60, (
        "the wire carried a padded frame: %d bytes" % (len(carried),))
    assert envelope["type"] == "arp" and len(envelope["payload"]) == 46, (
        "and parse hands up the frame's payload, padding and all: %r"
        % (len(envelope["payload"]),))
    assert envelope["payload"][:s.ARP_LENGTH] == question, (
        "the message is the first ARP_LENGTH bytes of it: %r"
        % (envelope["payload"][:s.ARP_LENGTH],))
    _refuses(s.ArpError, "a frame's whole payload as a message",
             lambda: s.parse_message(envelope["payload"]), names=("46",))
    assert s.parse_message(envelope["payload"][:s.ARP_LENGTH])["target_ip"] == web_ip, (
        "which is why the layer that knows ARP_LENGTH is the one that cuts: %r"
        % (s.parse_message(envelope["payload"][:s.ARP_LENGTH]),))

    # ---- the cache --------------------------------------------------------

    cache = s.Cache()
    assert cache.entries(0) == () and cache.log() == (), (
        "a fresh cache believes nothing: %r" % (cache.entries(0),))
    first = cache.learn(web_ip, web_mac, 0)
    assert first == {"ip": web_ip, "mac": web_mac, "fresh": False, "expires": 8}, (
        "a new address is not fresh and dies eight ticks later: %r" % (first,))
    again = cache.learn(web_ip, web_mac, 3)
    assert again == {"ip": web_ip, "mac": web_mac, "fresh": True, "expires": 11}, (
        "an address that is already known is refreshed, and reports fresh: %r"
        % (again,))
    assert cache.lookup(web_ip, 10) == web_mac, (
        "the refreshed entry is still believed at 10: %r" % (cache.lookup(web_ip, 10),))
    assert cache.entries(11) == (), (
        "an entry whose deadline is the tick being asked about is not live, even "
        "though nothing has swept it: %r" % (cache.entries(11),))
    assert [line["event"] for line in cache.log()] == ["learn", "refresh"], (
        "a refresh is the decision it is, and the log says so: %r"
        % ([line["event"] for line in cache.log()],))
    assert cache.lookup(web_ip, 11) is None, (
        "and is gone at the tick it dies: %r" % (cache.lookup(web_ip, 11),))
    assert cache.lookup(web_ip, 10) is None, (
        "an expired entry is taken out on read, so it cannot be asked twice: %r"
        % (cache.lookup(web_ip, 10),))
    assert cache.entries(10) == () and cache.entries(11) == (), (
        "and the table is empty of it: %r" % (cache.entries(10),))

    cache = s.Cache()
    cache.learn(web_ip, web_mac, 0)
    replaced = cache.learn(web_ip, dns_mac, 1)
    assert replaced["fresh"] is True and replaced["mac"] == dns_mac, (
        "a different MAC for a known address replaces it and is reported: %r"
        % (replaced,))
    assert cache.entries(2) == ((web_ip, dns_mac, 9),), (
        "and the table has the new MAC and the new deadline: %r"
        % (cache.entries(2),))
    assert cache.lookup(web_ip, 2) == dns_mac, (
        "which is what lookup answers with: %r" % (cache.lookup(web_ip, 2),))
    events = [line["event"] for line in cache.log()]
    assert events == ["learn", "replace"], (
        "the log records the decision a replacement is: %r" % (events,))
    assert set(cache.log()[0]) == {"now", "event", "ip", "mac", "expires"}, (
        "a log line is the decision and its numbers: %r" % (sorted(cache.log()[0]),))
    assert cache.log()[1]["now"] == 1 and cache.log()[1]["mac"] == dns_mac, (
        "a line is stamped with the tick it happened at: %r" % (cache.log()[1],))
    assert isinstance(cache.log(), tuple) and isinstance(cache.entries(2), tuple), (
        "the log and the table are read, so they are handed back as tuples")

    # `entries` sorts by address, and `expire` reports in the order learned.
    cache = s.Cache()
    cache.learn("10.0.0.9", mac_of("web"), 0)
    cache.learn("10.0.0.5", mac_of("dns"), 0)
    cache.learn("10.0.0.10", mac_of("db"), 4)
    listed = cache.entries(4)
    assert [row[0] for row in listed] == ["10.0.0.5", "10.0.0.9", "10.0.0.10"], (
        "an address is four octets and sorts like four octets, not like text: %r"
        % ([row[0] for row in listed],))
    assert all(row[2] == 8 for row in listed[:2]) and listed[2][2] == 12, (
        "each entry carries its own deadline, not the cache's last one: %r"
        % (listed,))
    gone = cache.expire(8)
    assert gone == (("10.0.0.9", mac_of("web"), 8), ("10.0.0.5", mac_of("dns"), 8)), (
        "expire reports the ones that ran out in the order they were learned: %r"
        % (gone,))
    assert cache.expire(8) == () and cache.entries(8) == (("10.0.0.10", mac_of("db"), 12),), (
        "and it removed what it reported: %r" % (cache.entries(8),))
    assert cache.lookup("10.0.0.9", 8) is None and cache.entries(9) == (
        ("10.0.0.10", mac_of("db"), 12),), (
        "an address that ran out is not answered with: %r" % (cache.entries(9),))
    assert [line["event"] for line in cache.log()] == [
        "learn", "learn", "learn", "expired", "expired"], (
        "the log has every decision, the purges included: %r"
        % ([line["event"] for line in cache.log()],))

    # A cache with a lifetime of its own, and a re-learned entry that moves.
    short = s.Cache(3)
    short.learn(web_ip, web_mac, 0)
    assert short.entries(2) == ((web_ip, web_mac, 3),), (
        "a cache with a lifetime of three dies at three: %r" % (short.entries(2),))
    assert short.lookup(web_ip, 3) is None and short.entries(3) == (), (
        "and is gone at three: %r" % (short.entries(3),))
    short.learn(web_ip, web_mac, 0)
    short.learn(web_ip, web_mac, 2)
    assert short.lookup(web_ip, 4) == web_mac and short.lookup(web_ip, 5) is None, (
        "a refresh moves the deadline, so the entry outlives its first one")
    _refuses(s.ArpError, "a cache whose entries live no ticks at all",
             lambda: s.Cache(0), names=("0",))
    _refuses(s.ArpError, "a cache whose lifetime is not a number of ticks",
             lambda: s.Cache(None), names=("None",))
    _refuses(s.ArpError, "learning an address that is not four octets",
             lambda: s.Cache().learn("10.0.0", web_mac, 0), names=("10.0.0",))
    _refuses(s.ArpError, "learning an address that is not a MAC",
             lambda: s.Cache().learn(web_ip, "nope", 0), names=("'nope'",))
    _refuses(s.ArpError, "learning at a tick that does not exist",
             lambda: s.Cache().learn(web_ip, web_mac, -1), names=("-1",))
    _refuses(s.ArpError, "looking up an address that is not four octets",
             lambda: s.Cache().lookup("10.0.0", 0), names=("10.0.0",))
    assert s.Cache().lookup(web_ip, 0) is None, (
        "an address nobody learned is `None`, not a refusal: %r"
        % (s.Cache().lookup(web_ip, 0),))
    assert s.Cache().expire(0) == () and s.Cache().entries(0) == (), (
        "and expiring an empty table reports nothing at all")

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "tcp-ip-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

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
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import stage_01 as s1
    import stage_03 as s
    from wire import Wire
    from hosts import Host, MACS, NAMES, ip_of, mac_of

    web_mac, web_ip = mac_of("web"), ip_of("web")
    db_mac, db_ip = mac_of("db"), ip_of("db")
    dns_mac, dns_ip = mac_of("dns"), ip_of("dns")
    client_mac, client_ip = mac_of("client"), ip_of("client")
    router_mac = mac_of("router")

    # ---- the constants ----------------------------------------------------

    assert s.IPV4_HEADER == 20, (
        "an ipv4 header is twenty bytes: %r" % (s.IPV4_HEADER,))
    assert s.IPV4_VERSION == 4, (
        "the version this stack reads is 4: %r" % (s.IPV4_VERSION,))
    assert s.DEFAULT_TTL == 64, (
        "a datagram is built with a hop count of 64: %r" % (s.DEFAULT_TTL,))
    assert s.MAX_TTL == 255, (
        "the most a hop count can be is 255: %r" % (s.MAX_TTL,))
    assert s.IDENT_MAX == 65535, (
        "the most an identifier can be is 65535: %r" % (s.IDENT_MAX,))
    assert s.PROTOCOLS == {1: "icmp", 6: "tcp"}, (
        "the two protocols this course speaks: %r" % (s.PROTOCOLS,))
    assert issubclass(s.IpError, ValueError), (
        "IpError is a ValueError, like every refusal in this course: %r"
        % (s.IpError.__mro__,))

    # ---- the address, both ways -------------------------------------------

    assert s.parse_ip("10.0.0.2") == (10, 0, 0, 2), (
        "parse_ip(%r) is four octets: %r" % ("10.0.0.2", s.parse_ip("10.0.0.2")))
    assert isinstance(s.parse_ip("10.0.0.2"), tuple), (
        "and it hands them back as a tuple: %r" % (s.parse_ip("10.0.0.2"),))
    assert s.parse_ip("0.0.0.0") == (0, 0, 0, 0), (
        "the address of nothing is four zero octets: %r" % (s.parse_ip("0.0.0.0"),))
    assert s.parse_ip("255.255.255.255") == (255, 255, 255, 255), (
        "and every octet may be 255: %r" % (s.parse_ip("255.255.255.255"),))
    assert s.parse_ip("10.9.8.7") == (10, 9, 8, 7), (
        "the octets are the octets, in order: %r" % (s.parse_ip("10.9.8.7"),))

    for bad in ("10.0.0", "10.0.0.2.3", "10.0.0.256", "010.0.0.1", "10.0.0.-1",
                "10.0.0.a", "", "10.0.0. 1", "10.0.0.2."):
        _refuses(s.IpError, "parse_ip(%r)" % (bad,),
                 lambda bad=bad: s.parse_ip(bad), names=(repr(bad),))
    _refuses(s.IpError, "parse_ip of three octets", lambda: s.parse_ip("10.0.0"),
             names=("3",))
    _refuses(s.IpError, "parse_ip of a number", lambda: s.parse_ip(2),
             names=("2",))
    _refuses(s.IpError, "parse_ip of None", lambda: s.parse_ip(None),
             names=("None",))
    _refuses(s.IpError, "parse_ip of four octets already",
             lambda: s.parse_ip(b"\x0a\x00\x00\x02"), names=("dotted-quad",))

    assert s.ip_text((10, 0, 0, 2)) == "10.0.0.2", (
        "ip_text is the other direction: %r" % (s.ip_text((10, 0, 0, 2)),))
    assert s.ip_text(b"\x0a\x00\x00\x02") == "10.0.0.2", (
        "four bytes are four octets too: %r" % (s.ip_text(b"\x0a\x00\x00\x02"),))
    assert s.ip_text([255, 255, 255, 255]) == "255.255.255.255", (
        "and a list of four is read like a tuple: %r"
        % (s.ip_text([255, 255, 255, 255]),))
    for name in ("web", "db", "client"):
        assert s.ip_text(s.parse_ip(ip_of(name))) == ip_of(name), (
            "the two directions meet: %r" % (ip_of(name),))
    _refuses(s.IpError, "ip_text of three octets", lambda: s.ip_text((1, 2, 3)),
             names=("3",))
    _refuses(s.IpError, "ip_text of an octet above 255",
             lambda: s.ip_text((256, 0, 0, 1)), names=("256",))
    _refuses(s.IpError, "ip_text of two bytes", lambda: s.ip_text(b"\x0a\x00"),
             names=("2",))
    _refuses(s.IpError, "ip_text of the text it should produce",
             lambda: s.ip_text("10.0.0.2"), names=("10.0.0.2",))
    _refuses(s.IpError, "ip_text of None", lambda: s.ip_text(None),
             names=("None",))

    # ---- the mask and the network -----------------------------------------

    assert s.mask_of(0) == 0, (
        "a prefix of nothing masks nothing: %r" % (s.mask_of(0),))
    assert s.mask_of(8) == 0xff000000, (
        "eight bits are the first octet: %r" % (hex(s.mask_of(8)),))
    assert s.mask_of(16) == 0xffff0000, (
        "sixteen bits are the first two: %r" % (hex(s.mask_of(16)),))
    assert s.mask_of(24) == 0xffffff00, (
        "the contract's own example: %r" % (hex(s.mask_of(24)),))
    assert s.mask_of(30) == 0xfffffffc, (
        "and thirty is the two host bits clear: %r" % (hex(s.mask_of(30)),))
    assert s.mask_of(32) == 0xffffffff, (
        "all of it is every bit: %r" % (hex(s.mask_of(32)),))
    for prefix in (0, 1, 7, 15, 23, 31, 32):
        assert s.mask_of(prefix) & ((1 << (32 - prefix)) - 1) == 0, (
            "a prefix of %d leaves every host bit clear: %r"
            % (prefix, hex(s.mask_of(prefix))))
    for bad in (33, -1, 64, "24", None, True):
        _refuses(s.IpError, "mask_of(%r)" % (bad,),
                 lambda bad=bad: s.mask_of(bad), names=(repr(bad),))

    assert s.network_of("10.0.0.2", 24) == 0x0a000000, (
        "the host bits are clear: %r" % (hex(s.network_of("10.0.0.2", 24)),))
    assert s.network_of("10.0.1.2", 16) == 0x0a000000, (
        "at a shorter prefix more of the address is masked: %r"
        % (hex(s.network_of("10.0.1.2", 16)),))
    assert s.network_of("10.0.0.2", 32) == 0x0a000002, (
        "and at thirty-two nothing is: %r" % (hex(s.network_of("10.0.0.2", 32)),))
    assert s.network_of("10.0.0.2", 0) == 0, (
        "at zero, every address is the same network: %r"
        % (hex(s.network_of("10.0.0.2", 0)),))
    assert s.network_of((10, 0, 0, 2), 24) == 0x0a000000, (
        "an address in either form is the same address: %r"
        % (hex(s.network_of((10, 0, 0, 2), 24)),))
    assert s.network_of(b"\x0a\x00\x01\x02", 8) == 0x0a000000, (
        "even as four bytes: %r" % (hex(s.network_of(b"\x0a\x00\x01\x02", 8)),))
    _refuses(s.IpError, "network_of with a prefix outside 0..32",
             lambda: s.network_of("10.0.0.2", 33), names=("33",))
    _refuses(s.IpError, "network_of of an address that is not one",
             lambda: s.network_of("10.0.0.256", 24), names=("10.0.0.256",))

    # ---- the checksum, and the reading that is its other half --------------

    bare_header = bytes.fromhex("4500001400000000400100000a0000020a000004")
    assert s.checksum(bare_header) == 0x66e4, (
        "the checksum of this header, field zero: %r" % (hex(s.checksum(bare_header)),))
    envelope = bytes.fromhex("450000730000400040110000c0a80001c0a800c7")
    assert s.checksum(envelope) == 0xb861, (
        "the standard's own example header checksums to 0xb861: %r"
        % (hex(s.checksum(envelope)),))
    assert s.checksum(b"") == 0xffff, (
        "the complement of a sum of nothing is every bit: %r"
        % (hex(s.checksum(b"")),))
    assert s.checksum(b"\x00\x00") == 0xffff, (
        "and a zero word adds nothing to it: %r" % (hex(s.checksum(b"\x00\x00")),))
    assert s.checksum(b"\x00\x01\x00\x02") == 0xfffc, (
        "a sum of three is complemented to 0xfffc: %r"
        % (hex(s.checksum(b"\x00\x01\x00\x02")),))
    assert s.checksum(b"\x01\x02\x03") == s.checksum(b"\x01\x02\x03\x00"), (
        "an odd-length message is padded with one zero byte: %r and %r"
        % (hex(s.checksum(b"\x01\x02\x03")), hex(s.checksum(b"\x01\x02\x03\x00"))))
    assert s.checksum(bytes.fromhex("ffff0002")) == 0xfffd, (
        "a carry is folded back into the sum: %r"
        % (hex(s.checksum(bytes.fromhex("ffff0002"))),))
    assert s.checksum(bytes.fromhex("ffffffff")) == 0x0000, (
        "two words that each carry fold to 0xffff, whose complement is zero: %r"
        % (hex(s.checksum(bytes.fromhex("ffffffff"))),))

    assert s.checksum_ok(bare_header) is False, (
        "a header whose checksum field is still zero does not check out")
    filled = bare_header[:10] + s.checksum(bare_header).to_bytes(2, "big") + bare_header[12:]
    assert filled[10:12] == b"\x66\xe4", (
        "the field goes where §2.3 puts it, most significant byte first: %r"
        % (filled[10:12],))
    assert s.checksum_ok(filled) is True, (
        "and a message that carries its own checksum checks out: %r"
        % (s.checksum_ok(filled),))
    assert s.checksum(filled) == 0, (
        "the reading is the complement taken twice's opposite: a valid message "
        "sums to 0xffff, so its complement is zero, not 0xffff: %r"
        % (hex(s.checksum(filled)),))
    assert s.checksum_ok(filled[:10] + b"\x00\x00" + filled[12:]) is False, (
        "a field that does not agree with its bytes is a verdict, not a raise")
    assert s.checksum_ok(filled[:9] + bytes((filled[9] ^ 0x01,)) + filled[10:]) is False, (
        "and it does not agree when a byte of the body moved either")
    assert s.checksum_ok(b"") is False, (
        "the empty message carries no valid field: %r" % (s.checksum_ok(b""),))
    assert s.checksum_ok(bytes.fromhex("ffff")) is True, (
        "the one message whose sum is already 0xffff: %r"
        % (s.checksum_ok(bytes.fromhex("ffff")),))
    _refuses(s.IpError, "a checksum over something that is not bytes",
             lambda: s.checksum("a header"), names=("str",))
    _refuses(s.IpError, "checksum_ok of something that is not bytes",
             lambda: s.checksum_ok(None), names=("None",))

    # ---- pack_header ------------------------------------------------------

    header = s.pack_header("10.0.0.2", "10.0.0.4", "icmp", 0, 64, 0)
    assert header == bytes.fromhex("4500001400000000400166e40a0000020a000004"), (
        "the twenty bytes, in the layout §2.3 freezes: %r" % (header.hex(),))
    assert len(header) == s.IPV4_HEADER == 20, (
        "which is IPV4_HEADER bytes: %d" % (len(header),))
    assert header[0] == 0x45, (
        "version and IHL share the first byte, and both are 4 and 5: %r"
        % (header[0],))
    assert header[1] == 0, (
        "the type of service this course asks for is zero: %r" % (header[1],))
    assert int.from_bytes(header[2:4], "big") == 20, (
        "total_length counts the header and its payload, and the payload is "
        "empty: %r" % (int.from_bytes(header[2:4], "big"),))
    assert int.from_bytes(header[4:6], "big") == 0, (
        "the identifier is what the caller gave: %r"
        % (int.from_bytes(header[4:6], "big"),))
    assert header[6:8] == b"\x00\x00", (
        "nothing is fragmented: %r" % (header[6:8],))
    assert header[8] == 64 and header[9] == 1, (
        "then the hop count and the protocol: %r and %r" % (header[8], header[9]))
    assert header[10:12] == b"\x66\xe4", (
        "then the checksum, over the header alone: %r" % (header[10:12],))
    assert header[12:16] == bytes((10, 0, 0, 2)), (
        "and the two addresses, source first: %r" % (header[12:16],))
    assert header[16:20] == bytes((10, 0, 0, 4)), (
        "and then the destination: %r" % (header[16:20],))
    assert s.checksum_ok(header) is True, (
        "what pack_header wrote is what checksum_ok reads")

    long_header = s.pack_header("10.0.0.2", "10.0.0.4", "icmp", 8, 3, 7)
    assert long_header == bytes.fromhex("4500001c000700000301a3d50a0000020a000004"), (
        "a payload of eight makes total_length 28, and the checksum follows it: %r"
        % (long_header.hex(),))
    assert s.pack_header("10.0.0.2", "10.0.0.4", 1, 0, 64, 0) == header, (
        "a protocol may be given as its number as well as by its name")
    assert s.pack_header(b"\x0a\x00\x00\x02", (10, 0, 0, 4), "tcp", 0, 64, 0)[9] == 6, (
        "and both addresses may be given as octets")
    assert s.pack_header("10.0.0.2", "10.0.0.4", "icmp", 0, 255, 0)[8] == 255, (
        "a ttl of MAX_TTL is a ttl")
    assert s.pack_header("10.0.0.2", "10.0.0.4", "icmp", 0, 64, 65535)[4:6] == b"\xff\xff", (
        "and an identifier of IDENT_MAX is an identifier")
    assert int.from_bytes(
        s.pack_header("10.0.0.2", "10.0.0.4", "icmp", 65515, 64, 0)[2:4], "big") == 65535, (
        "the longest datagram there is: 65515 of payload and a 20-byte header")

    _refuses(s.IpError, "a protocol number this stack does not speak",
             lambda: s.pack_header("10.0.0.2", "10.0.0.4", 17, 0, 64, 0), names=("17",))
    _refuses(s.IpError, "the protocol number zero",
             lambda: s.pack_header("10.0.0.2", "10.0.0.4", 0, 0, 64, 0), names=("0",))
    _refuses(s.IpError, "a protocol name nobody knows",
             lambda: s.pack_header("10.0.0.2", "10.0.0.4", "udp", 0, 64, 0),
             names=("'udp'",))
    _refuses(s.IpError, "a protocol that is a Boolean",
             lambda: s.pack_header("10.0.0.2", "10.0.0.4", True, 0, 64, 0),
             names=("True",))
    _refuses(s.IpError, "a payload length that cannot be one",
             lambda: s.pack_header("10.0.0.2", "10.0.0.4", "icmp", 65516, 64, 0),
             names=("65516",))
    _refuses(s.IpError, "a negative payload length",
             lambda: s.pack_header("10.0.0.2", "10.0.0.4", "icmp", -1, 64, 0),
             names=("-1",))
    _refuses(s.IpError, "a ttl of zero, which is no hop at all",
             lambda: s.pack_header("10.0.0.2", "10.0.0.4", "icmp", 0, 0, 0),
             names=("0",))
    _refuses(s.IpError, "a ttl above MAX_TTL",
             lambda: s.pack_header("10.0.0.2", "10.0.0.4", "icmp", 0, 256, 0),
             names=("256",))
    _refuses(s.IpError, "an identifier above IDENT_MAX",
             lambda: s.pack_header("10.0.0.2", "10.0.0.4", "icmp", 0, 64, 65536),
             names=("65536",))
    _refuses(s.IpError, "a source that is not an address",
             lambda: s.pack_header("10.0.0.256", "10.0.0.4", "icmp", 0, 64, 0),
             names=("10.0.0.256",))
    _refuses(s.IpError, "a destination that is not an address",
             lambda: s.pack_header("10.0.0.2", None, "icmp", 0, 64, 0),
             names=("None",))

    # ---- build and unpack_header ------------------------------------------

    datagram = s.build("10.0.0.2", "10.0.0.4", "icmp", b"12345678", ttl=3, ident=7)
    assert datagram == (bytes.fromhex("4500001c000700000301a3d50a0000020a000004")
                        + b"12345678"), (
        "build is the header and its payload: %r" % (datagram.hex(),))
    assert datagram == (s.pack_header("10.0.0.2", "10.0.0.4", "icmp", 8, 3, 7)
                        + b"12345678"), (
        "and its header is exactly the header pack_header makes")
    assert int.from_bytes(datagram[2:4], "big") == s.IPV4_HEADER + 8, (
        "total_length counts both halves: %r" % (int.from_bytes(datagram[2:4], "big"),))
    assert len(s.build(web_ip, db_ip, "icmp", b"")) == 20, (
        "a datagram of no payload is the header alone")
    _refuses(s.IpError, "a payload that is not bytes",
             lambda: s.build(web_ip, db_ip, "icmp", "12345678"), names=("str",))
    _refuses(s.IpError, "a payload longer than a datagram can carry",
             lambda: s.build(web_ip, db_ip, "icmp", b"\x00" * 65516),
             names=("65516",))

    envelope_ = s.unpack_header(datagram)
    assert envelope_ == {"src": "10.0.0.2", "dst": "10.0.0.4", "protocol": "icmp",
                         "payload_length": 8, "ttl": 3, "ident": 7,
                         "checksum_ok": True, "payload": b"12345678"}, (
        "the header's eight facts, in their text forms: %r" % (envelope_,))
    assert list(envelope_) == ["src", "dst", "protocol", "payload_length", "ttl",
                               "ident", "checksum_ok", "payload"], (
        "the facts come back in the order the contract lists them: %r"
        % (list(envelope_),))
    assert s.unpack_header(datagram) == envelope_, (
        "parsing is a read, not an act: the same bytes give the same facts")
    assert s.unpack_header(s.build(web_ip, db_ip, "tcp", b"", ttl=1, ident=99)) == {
        "src": web_ip, "dst": db_ip, "protocol": "tcp", "payload_length": 0,
        "ttl": 1, "ident": 99, "checksum_ok": True, "payload": b""}, (
        "and the protocol comes back as its name, like a frame's type")

    # ---- total_length is where the padding stops being anybody's problem ---

    frame = s1.build(db_mac, web_mac, "ipv4", datagram)
    region = s1.parse(frame)["payload"]
    assert len(frame) == s1.MIN_FRAME == 60, (
        "the wire carries a padded frame: %d bytes" % (len(frame),))
    assert len(region) == 46 and region[:28] == datagram, (
        "whose payload region is 46 bytes with the 28-byte datagram first: %r"
        % (region,))
    assert s.unpack_header(region) == envelope_, (
        "and unpack_header cuts the padding off, because total_length says 28")
    assert s.unpack_header(region)["payload"] == b"12345678", (
        "the payload is exactly total_length - IPV4_HEADER bytes, not the frame's "
        "46: %r" % (s.unpack_header(region)["payload"],))
    assert s.unpack_header(s1.parse(s1.build(db_mac, web_mac, "ipv4", datagram,
                                             pad=False))["payload"]) == envelope_, (
        "an unpadded frame carries the same datagram and parses the same")
    assert s.unpack_header(datagram + b"\x00" * 46) == envelope_, (
        "and trailing bytes the header did not count are not the payload")

    # ---- unpack_header's boundaries ---------------------------------------

    _refuses(s.IpError, "a datagram of nineteen bytes",
             lambda: s.unpack_header(datagram[:19]), names=("19", "20"))
    empty = s.build(web_ip, db_ip, "icmp", b"", ttl=3, ident=7)
    assert s.unpack_header(empty)["payload"] == b"", (
        "a datagram of exactly the header has no payload: %r"
        % (s.unpack_header(empty),))
    _refuses(s.IpError, "a version this stack does not read",
             lambda: s.unpack_header(bytes((0x65,)) + datagram[1:]), names=("6", "4"))
    _refuses(s.IpError, "an IHL that is not five",
             lambda: s.unpack_header(bytes((0x46,)) + datagram[1:]), names=("6",))
    _refuses(s.IpError, "a total_length shorter than the header",
             lambda: s.unpack_header(datagram[:2] + b"\x00\x13" + datagram[4:]),
             names=("19", "20"))
    assert s.unpack_header(datagram[:2] + b"\x00\x14" + datagram[4:])["payload"] == b"", (
        "a total_length of exactly the header is a datagram of no payload")
    _refuses(s.IpError, "a total_length longer than the bytes handed in",
             lambda: s.unpack_header(datagram[:27]), names=("28", "27"))
    _refuses(s.IpError, "a protocol this stack does not speak",
             lambda: s.unpack_header(datagram[:9] + bytes((17,)) + datagram[10:]),
             names=("17",))
    _refuses(s.IpError, "a datagram that is not bytes",
             lambda: s.unpack_header("a datagram"), names=("str",))

    # A wrong checksum is a *verdict about a peer's bytes*, never an exception.
    hurt = datagram[:15] + bytes((datagram[15] ^ 0xff,)) + datagram[16:]
    hurt_envelope = s.unpack_header(hurt)
    assert hurt_envelope["checksum_ok"] is False, (
        "a header whose checksum disagrees is reported, not raised: %r"
        % (hurt_envelope,))
    assert hurt_envelope["src"] == "10.0.0.253" and hurt_envelope["dst"] == "10.0.0.4", (
        "and its facts are still read out of it: %r" % (hurt_envelope,))
    assert hurt_envelope["payload"] == b"12345678", (
        "its payload too, because total_length still says where it ends: %r"
        % (hurt_envelope["payload"],))
    assert s.unpack_header(b"\x45" + datagram[1:15] + bytes((254,)) + datagram[16:])[
        "checksum_ok"] is False, (
        "any byte of the header, not just the source")

    # ---- route ------------------------------------------------------------

    table = [("0.0.0.0", 0, "eth1", router_mac), ("10.0.0.0", 24, "eth0", db_mac)]
    assert s.route(table, db_ip) == {"port": "eth0", "next_hop": db_mac, "prefix": 24}, (
        "the longest prefix that matches, not the first line: %r" % (s.route(table, db_ip),))
    assert s.route(table, "10.0.1.4") == {
        "port": "eth1", "next_hop": router_mac, "prefix": 0}, (
        "an address outside the specific network falls to the default: %r"
        % (s.route(table, "10.0.1.4"),))
    assert s.route([("10.0.0.0", 24, "eth0", db_mac),
                    ("0.0.0.0", 0, "eth1", router_mac)], db_ip)["port"] == "eth0", (
        "and the order the table was written in does not decide it")
    assert s.route([("10.0.0.0", 16, "eth2", web_mac),
                    ("10.0.0.0", 24, "eth0", db_mac)], db_ip)["prefix"] == 24, (
        "nor which of two matching lines came first: %r"
        % (s.route([("10.0.0.0", 16, "eth2", web_mac),
                    ("10.0.0.0", 24, "eth0", db_mac)], db_ip),))
    assert s.route([("10.0.0.99", 24, "eth0", db_mac)], db_ip) == {
        "port": "eth0", "next_hop": db_mac, "prefix": 24}, (
        "a table entry with host bits in it names the same network: %r"
        % (s.route([("10.0.0.99", 24, "eth0", db_mac)], db_ip),))
    assert s.route([("10.0.0.99", 24, "eth0", db_mac)], "10.0.1.4") == {
        "refused": "no_route"}, (
        "and still only its own network: %r"
        % (s.route([("10.0.0.99", 24, "eth0", db_mac)], "10.0.1.4"),))
    assert s.route([("10.0.0.0", 24, "eth0", db_mac)], "10.0.0.255")["port"] == "eth0", (
        "the whole network matches, broadcast address and all")
    assert s.route([], db_ip) == {"refused": "no_route"}, (
        "an empty table has no route: %r" % (s.route([], db_ip),))
    assert s.route([("10.0.1.0", 24, "eth0", db_mac)], db_ip) == {
        "refused": "no_route"}, (
        "and neither has a table whose networks are all somewhere else: %r"
        % (s.route([("10.0.1.0", 24, "eth0", db_mac)], db_ip),))
    assert s.route([("10.0.0.0", 24, "eth0", db_mac)], (10, 0, 0, 4))["prefix"] == 24, (
        "a destination in either form is the same destination")
    assert set(s.route(table, db_ip)) == {"port", "next_hop", "prefix"}, (
        "a route is three facts: %r" % (sorted(s.route(table, db_ip)),))
    assert list(s.route([], db_ip)) == ["refused"], (
        "and a refusal is one: %r" % (s.route([], db_ip),))

    _refuses(s.IpError, "a table entry that is not four items",
             lambda: s.route([("10.0.0.0", 24, "eth0")], db_ip),
             names=("10.0.0.0",))
    _refuses(s.IpError, "a prefix outside the bits an address has",
             lambda: s.route([("10.0.0.0", 33, "eth0", db_mac)], db_ip), names=("33",))
    _refuses(s.IpError, "a negative prefix",
             lambda: s.route([("10.0.0.0", -1, "eth0", db_mac)], db_ip), names=("-1",))
    _refuses(s.IpError, "a destination that is not an address",
             lambda: s.route(table, "10.0.0.256"), names=("10.0.0.256",))
    _refuses(s.IpError, "a route's own network that is not an address",
             lambda: s.route([("10.0.0.999", 24, "eth0", db_mac)], db_ip),
             names=("10.0.0.999",))

    # ---- forward: the decision, and the words it refuses with -------------

    onetable = [("10.0.0.0", 24, "eth0", db_mac)]
    moving = s.build(client_ip, db_ip, "icmp", b"12345678", ttl=3, ident=7)
    out = s.forward(onetable, moving)
    assert set(out) == {"sent", "ttl", "port", "next_hop", "ident"}, (
        "a forwarded datagram comes back with the route it took: %r"
        % (sorted(out),))
    assert out["ttl"] == 2 and out["ident"] == 7, (
        "one hop is spent and the identifier is untouched: %r" % (out,))
    assert out["port"] == "eth0" and out["next_hop"] == db_mac, (
        "and the route is the one the table gave: %r" % (out,))
    assert out["sent"] == s.build(client_ip, db_ip, "icmp", b"12345678", ttl=2, ident=7), (
        "the datagram sent is the one with the new ttl and the new checksum: %r"
        % (out["sent"].hex(),))
    assert out["sent"][:20] == bytes.fromhex(
        "4500001c000700000201a4d20a0000050a000004"), (
        "byte for byte: %r" % (out["sent"][:20].hex(),))
    assert s.unpack_header(out["sent"]) == {
        "src": client_ip, "dst": db_ip, "protocol": "icmp", "payload_length": 8,
        "ttl": 2, "ident": 7, "checksum_ok": True, "payload": b"12345678"}, (
        "and reading it back says the ttl moved and nothing else did: %r"
        % (s.unpack_header(out["sent"]),))

    assert s.forward(onetable, s.build(client_ip, db_ip, "icmp", b"", ttl=2, ident=0))[
        "ttl"] == 1, (
        "a datagram with two hops left may take one: %r"
        % (s.forward(onetable, s.build(client_ip, db_ip, "icmp", b"", ttl=2, ident=0)),))
    assert s.forward(onetable, s.build(client_ip, db_ip, "icmp", b"", ttl=1, ident=0)) == {
        "refused": "ttl_expired"}, (
        "and with one hop left it is refused, not forwarded with none: %r"
        % (s.forward(onetable, s.build(client_ip, db_ip, "icmp", b"", ttl=1, ident=0)),))
    hurt = moving[:15] + bytes((moving[15] ^ 0xff,)) + moving[16:]
    assert s.forward(onetable, hurt) == {"refused": "bad_checksum"}, (
        "a datagram whose checksum disagrees is refused with the word: %r"
        % (s.forward(onetable, hurt),))
    assert s.forward([], moving) == {"refused": "no_route"}, (
        "and one this table cannot route: %r" % (s.forward([], moving),))
    assert s.forward([("10.0.1.0", 24, "eth0", db_mac)], moving) == {
        "refused": "no_route"}, (
        "even when the table is not empty, it is still nowhere: %r"
        % (s.forward([("10.0.1.0", 24, "eth0", db_mac)], moving),))
    assert s.forward([], s.build(client_ip, db_ip, "icmp", b"", ttl=1, ident=0)) == {
        "refused": "ttl_expired"}, (
        "a spent hop count is decided before the table is even consulted: %r"
        % (s.forward([], s.build(client_ip, db_ip, "icmp", b"", ttl=1, ident=0)),))
    assert s.forward([], hurt) == {"refused": "bad_checksum"}, (
        "and a bad checksum before both: %r" % (s.forward([], hurt),))
    _refuses(s.IpError, "forward of bytes that are not a datagram",
             lambda: s.forward(onetable, b"\x00" * 10), names=("10",))

    # ---- forward on a real wire, between real hosts -----------------------

    wire = Wire()
    router = Host("router", ip_of("router"), router_mac, wire)
    db = Host("db", db_ip, db_mac, wire)
    crossing = s.build(client_ip, db_ip, "tcp", b"\x01\x02\x03\x04", ttl=5, ident=42)
    decision = s.forward(onetable, crossing)
    assert wire.sent() == 0, (
        "forward decides and sends nothing: the caller owns the link: %r"
        % (wire.sent(),))
    frame = s1.build(decision["next_hop"], router.mac, "ipv4", decision["sent"])
    ordinal = router.send(decision["next_hop"], frame)
    assert ordinal == 1 and wire.sent() == 1 and router.sent() == 1, (
        "the router puts the forwarded datagram on the link: %r" % (ordinal,))
    assert wire.pending() == [{"ordinal": 1, "due": 1, "src": router_mac,
                               "dst": db_mac}], (
        "addressed to the next hop the table named: %r" % (wire.pending(),))
    wire.advance(1)
    assert db.recv() == [frame], (
        "the next hop's box has the frame: %r" % (db.inbox(),))
    arrived = s.unpack_header(s1.parse(db.inbox()[0])["payload"])
    assert arrived["ttl"] == 4 and arrived["checksum_ok"] is True, (
        "carrying the datagram with its hop spent and its checksum right: %r"
        % (arrived,))
    assert arrived["src"] == client_ip and arrived["dst"] == db_ip, (
        "and its addresses untouched: %r" % (arrived,))
    assert arrived["payload"] == b"\x01\x02\x03\x04", (
        "and its payload untouched, padding and all cut away: %r"
        % (arrived["payload"],))
    assert [event["data"] for event in wire.events("send")] == [frame], (
        "the wire's log agrees with the bytes that went in: %r"
        % ([event["data"] for event in wire.events("send")],))
    assert [event["ordinal"] for event in wire.events("deliver")] == [ordinal], (
        "and the ordinal the router was handed is the one the log knows")

    # A refusal puts nothing on the wire: the words are the whole answer.
    wire = Wire()
    router = Host("router", ip_of("router"), router_mac, wire)
    for refused, datagram_ in (("bad_checksum", hurt),
                               ("ttl_expired", s.build(client_ip, db_ip, "icmp", b"",
                                                       ttl=1, ident=0)),
                               ("no_route", s.build(client_ip, "10.0.1.4", "icmp",
                                                    b"", ttl=9, ident=1))):
        table_ = [] if refused == "no_route" else onetable
        answer = s.forward(table_, datagram_)
        assert answer == {"refused": refused}, (
            "the refusal is a word and nothing else: %r" % (answer,))
        assert "sent" not in answer and router.sent() == 0 and wire.sent() == 0, (
            "and nothing went on the link: %r sent" % (wire.sent(),))

    # The wire that drops the forwarded frame is a fact only its log has.
    wire = Wire({"loss": [1]})
    router = Host("router", ip_of("router"), router_mac, wire)
    db = Host("db", db_ip, db_mac, wire)
    decision = s.forward(onetable, crossing)
    router.send(decision["next_hop"],
                s1.build(decision["next_hop"], router.mac, "ipv4", decision["sent"]))
    assert wire.dropped() == 1 and wire.sent() == 1, (
        "the link ate the frame the router believed it sent: %r of %r"
        % (wire.dropped(), wire.sent()))
    wire.advance(3)
    assert db.recv() == [], (
        "and the next hop's box is empty, which is the whole point: %r"
        % (db.inbox(),))
    assert decision["ttl"] == 4 and decision["port"] == "eth0", (
        "the stack's own report is unchanged and wrong: %r" % (decision,))
    assert [event["event"] for event in wire.log()] == ["send", "drop"], (
        "the log is where the difference lives: %r"
        % ([event["event"] for event in wire.log()],))

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "tcp-ip-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

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
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import stage_01 as s1
    import stage_03 as s3
    import stage_04 as s
    from wire import Wire
    from hosts import Host, MACS, NAMES, ip_of, mac_of

    web_mac, web_ip = mac_of("web"), ip_of("web")
    db_mac, db_ip = mac_of("db"), ip_of("db")
    dns_mac, dns_ip = mac_of("dns"), ip_of("dns")
    client_mac, client_ip = mac_of("client"), ip_of("client")

    # ---- the constants ----------------------------------------------------

    assert s.ICMP_HEADER == 8, (
        "an icmp message's header is eight bytes: %r" % (s.ICMP_HEADER,))
    assert s.ERROR_QUOTE == 28, (
        "an error quotes the datagram's header and eight bytes of its payload: %r"
        % (s.ERROR_QUOTE,))
    assert (s.ICMP_ECHO_REPLY, s.ICMP_UNREACHABLE, s.ICMP_ECHO_REQUEST,
            s.ICMP_TIME_EXCEEDED) == (0, 3, 8, 11), (
        "the four types, as §2.3 numbers them: %r"
        % ((s.ICMP_ECHO_REPLY, s.ICMP_UNREACHABLE, s.ICMP_ECHO_REQUEST,
            s.ICMP_TIME_EXCEEDED),))
    assert s.ICMP_TYPES == {0: "echo_reply", 3: "unreachable", 8: "echo_request",
                            11: "time_exceeded"}, (
        "and their names: %r" % (s.ICMP_TYPES,))
    assert issubclass(s.IcmpError, ValueError), (
        "IcmpError is a ValueError, like every refusal in this course: %r"
        % (s.IcmpError.__mro__,))

    # ---- build ------------------------------------------------------------

    request = s.build(s.ICMP_ECHO_REQUEST, 0x1234, 1)
    assert request == bytes.fromhex("0800e5ca12340001"), (
        "the eight bytes of an echo request, checksum and all: %r" % (request.hex(),))
    assert s.build(s.ICMP_ECHO_REPLY, 0x1234, 1) == bytes.fromhex("0000edca12340001"), (
        "and of its reply: %r" % (s.build(s.ICMP_ECHO_REPLY, 0x1234, 1).hex(),))
    assert s.build(s.ICMP_ECHO_REQUEST) == bytes.fromhex("0800f7ff00000000"), (
        "the default ident and seq are zero: %r"
        % (s.build(s.ICMP_ECHO_REQUEST).hex(),))
    assert s.build(s.ICMP_TIME_EXCEEDED) == bytes.fromhex("0b00f4ff00000000"), (
        "and an error's four zero bytes: %r"
        % (s.build(s.ICMP_TIME_EXCEEDED).hex(),))
    assert s.build(s.ICMP_UNREACHABLE) == bytes.fromhex("0300fcff00000000"), (
        "an unreachable is a message like any other: %r"
        % (s.build(s.ICMP_UNREACHABLE).hex(),))
    assert len(s.build(s.ICMP_ECHO_REQUEST)) == s.ICMP_HEADER == 8, (
        "which is ICMP_HEADER bytes: %d" % (len(s.build(s.ICMP_ECHO_REQUEST)),))
    assert s.build(s.ICMP_ECHO_REQUEST)[:2] == b"\x08\x00", (
        "type first, then the code, which this course always writes zero: %r"
        % (s.build(s.ICMP_ECHO_REQUEST)[:2],))
    assert s.build(s.ICMP_ECHO_REQUEST, 1, 2, b"")[4:8] == b"\x00\x01\x00\x02", (
        "then the rest: the identifier before the sequence number, both big-endian")

    with_data = s.build(s.ICMP_ECHO_REQUEST, 7, 2, b"abcd")
    assert with_data == bytes.fromhex("080033300007000261626364"), (
        "a message with a payload, checksummed over all of it: %r" % (with_data.hex(),))
    assert s3.checksum_ok(with_data) is True, (
        "because what build wrote is what a receiver reads")
    assert s3.checksum(with_data) == 0, (
        "and a message that carries its own checksum complements to zero: %r"
        % (hex(s3.checksum(with_data)),))
    odd = s.build(s.ICMP_ECHO_REQUEST, 7, 2, b"abc")
    assert odd == bytes.fromhex("0800339400070002616263"), (
        "an odd-length message pads with one zero byte in the sum and not in the "
        "bytes: %r" % (odd.hex(),))
    assert len(odd) == 11, (
        "the message is as long as what was handed to it: %d" % (len(odd),))
    assert s.build(s.ICMP_ECHO_REQUEST, 65535, 65535)[4:8] == b"\xff\xff\xff\xff", (
        "both fields may be the most a sixteen-bit field can be")
    for type_ in sorted(s.ICMP_TYPES):
        assert s.parse(s.build(type_, 1, 2, b"xy"))["type"] == type_, (
            "every type this stack speaks can be built and read back: %r" % (type_,))

    for bad in (4, 7, 99, -1, 256, "echo_request", None, True):
        _refuses(s.IcmpError, "build of type %r" % (bad,),
                 lambda bad=bad: s.build(bad), names=(repr(bad),))
    _refuses(s.IcmpError, "an identifier that is not sixteen bits",
             lambda: s.build(s.ICMP_ECHO_REQUEST, 65536), names=("65536",))
    _refuses(s.IcmpError, "a negative identifier",
             lambda: s.build(s.ICMP_ECHO_REQUEST, -1), names=("-1",))
    _refuses(s.IcmpError, "a sequence number that is not sixteen bits",
             lambda: s.build(s.ICMP_ECHO_REQUEST, 0, 65536), names=("65536",))
    _refuses(s.IcmpError, "a payload that is not bytes",
             lambda: s.build(s.ICMP_ECHO_REQUEST, 0, 0, "abcd"), names=("str",))

    # ---- parse ------------------------------------------------------------

    parsed = s.parse(request)
    assert parsed == {"type": s.ICMP_ECHO_REQUEST, "name": "echo_request",
                      "code": 0, "ident": 0x1234, "seq": 1, "payload": b"",
                      "checksum_ok": True, "quote": None}, (
        "the message's eight facts: %r" % (parsed,))
    assert list(parsed) == ["type", "name", "code", "ident", "seq", "payload",
                            "checksum_ok", "quote"], (
        "in the order the contract lists them: %r" % (list(parsed),))
    assert s.parse(s.build(s.ICMP_ECHO_REPLY, 0x1234, 1))["name"] == "echo_reply", (
        "a type comes back as the name it is called: %r"
        % (s.parse(s.build(s.ICMP_ECHO_REPLY, 0x1234, 1)),))
    assert s.parse(with_data)["payload"] == b"abcd", (
        "the payload is everything after the eight-byte header: %r"
        % (s.parse(with_data)["payload"],))
    assert s.parse(with_data)["quote"] is None, (
        "and an echo quotes nothing: %r" % (s.parse(with_data)["quote"],))

    # The checksum covers the *whole* message: move the payload and the field
    # that was right for the old one is wrong for the new one.
    spent = with_data[:8] + b"abce"
    assert s.parse(spent)["checksum_ok"] is False, (
        "a message whose payload moved does not check out: %r"
        % (s.parse(spent)["checksum_ok"],))
    assert s.parse(spent)["payload"] == b"abce", (
        "and its facts are still read out of it: %r" % (s.parse(spent),))
    hurt = request[:2] + bytes((request[2] ^ 0xff,)) + request[3:]
    assert s.parse(hurt)["checksum_ok"] is False, (
        "a damaged checksum field is a verdict about a peer's bytes, never an "
        "exception: %r" % (s.parse(hurt),))
    assert s.parse(hurt)["type"] == s.ICMP_ECHO_REQUEST and s.parse(hurt)["seq"] == 1, (
        "and the rest of the message reads out normally: %r" % (s.parse(hurt),))

    _refuses(s.IcmpError, "a message shorter than its header",
             lambda: s.parse(b"\x08\x00\x00\x00\x00\x00\x00"), names=("7", "8"))
    other_code = s.parse(b"\x0b\x01\x00\x00\x00\x00\x00\x00")
    assert other_code["code"] == 1 and other_code["name"] == "time_exceeded", (
        "a code this stack never writes is still a field to read: %r" % (other_code,))
    assert other_code["checksum_ok"] is False, (
        "and its checksum is a verdict about somebody else's bytes: %r"
        % (other_code,))
    assert s.parse(s.build(s.ICMP_ECHO_REQUEST, 0, 0))["payload"] == b"", (
        "a message of exactly the header has no payload: %r"
        % (s.parse(s.build(s.ICMP_ECHO_REQUEST, 0, 0)),))
    _refuses(s.IcmpError, "a message of no bytes at all",
             lambda: s.parse(b""), names=("0",))
    _refuses(s.IcmpError, "a message that is not bytes",
             lambda: s.parse("an icmp message"), names=("str",))
    _refuses(s.IcmpError, "a type nobody knows",
             lambda: s.parse(b"\x63\x00\x00\x00\x00\x00\x00\x00"), names=("99",))
    _refuses(s.IcmpError, "a type nobody knows, in a message of the right length",
             lambda: s.parse(b"\x07\x00\x00\x00\x00\x00\x00\x00"), names=("7",))

    # ---- echo_reply -------------------------------------------------------

    reply = s.echo_reply(request)
    assert reply == s.build(s.ICMP_ECHO_REPLY, 0x1234, 1), (
        "the reply is a type-0 message: %r" % (reply.hex(),))
    assert reply == bytes.fromhex("0000edca12340001"), (
        "with the same ident and seq, byte for byte: %r" % (reply.hex(),))
    assert s.echo_reply(with_data) == s.build(s.ICMP_ECHO_REPLY, 7, 2, b"abcd"), (
        "and the same payload, not an empty one: %r"
        % (s.echo_reply(with_data).hex(),))
    assert s.parse(s.echo_reply(with_data)) == {
        "type": s.ICMP_ECHO_REPLY, "name": "echo_reply", "code": 0, "ident": 7,
        "seq": 2, "payload": b"abcd", "checksum_ok": True, "quote": None}, (
        "which reads back as the reply to that echo: %r"
        % (s.parse(s.echo_reply(with_data)),))
    _refuses(s.IcmpError, "a reply built for a message that is already a reply",
             lambda: s.echo_reply(reply), names=("0",))
    _refuses(s.IcmpError, "a reply built for a time-exceeded",
             lambda: s.echo_reply(s.build(s.ICMP_TIME_EXCEEDED)), names=("11",))
    _refuses(s.IcmpError, "a reply built for something that is not a message",
             lambda: s.echo_reply(b""), names=("0",))

    # ---- error_message ----------------------------------------------------

    quoted = s3.build(client_ip, db_ip, "icmp", with_data)
    assert len(quoted) == 20 + len(with_data) == 32, (
        "the datagram that will be refused: %r" % (len(quoted),))
    timed_out = s.error_message(quoted, "ttl_expired")
    assert timed_out == bytes.fromhex(
        "0b00b9c6000000004500002000000000400166d50a0000050a000004"
        "0800333000070002"), (
        "a time-exceeded quotes the datagram's first 28 bytes: %r"
        % (timed_out.hex(),))
    assert len(timed_out) == s.ICMP_HEADER + s.ERROR_QUOTE == 36, (
        "which makes a 36-byte message: %d" % (len(timed_out),))
    assert timed_out[:2] == b"\x0b\x00" and timed_out[4:8] == b"\x00\x00\x00\x00", (
        "an error's type, its code and its four zero rest bytes: %r"
        % (timed_out[:8],))
    assert timed_out[8:28] == quoted[:20], (
        "and then the offending datagram's own header: %r" % (timed_out[8:28],))
    assert timed_out[28:36] == quoted[20:28], (
        "and the first eight bytes of its payload — the header is not the payload "
        "and the payload is not the header: %r" % (timed_out[28:36],))
    assert timed_out[8:] == quoted[:s.ERROR_QUOTE], (
        "the quote is one run of bytes, the datagram's own: %r" % (timed_out[8:],))
    assert s.parse(timed_out)["quote"] == quoted[:s.ERROR_QUOTE], (
        "and parse hands the quote back for an error: %r"
        % (s.parse(timed_out)["quote"],))
    assert s.parse(timed_out)["name"] == "time_exceeded", (
        "a TTL expiry is the type a TTL expiry is: %r" % (s.parse(timed_out),))
    assert s.error_message(quoted, "no_route") == bytes.fromhex(
        "0300c1c6000000004500002000000000400166d50a0000050a000004"
        "0800333000070002"), (
        "and no route is an unreachable: %r"
        % (s.error_message(quoted, "no_route").hex(),))
    assert s.parse(s.error_message(quoted, "no_route"))["type"] == s.ICMP_UNREACHABLE, (
        "type 3, not type 11: %r" % (s.parse(s.error_message(quoted, "no_route")),))
    assert s.parse(s.error_message(quoted, "ttl_expired"))["type"] == (
        s.ICMP_TIME_EXCEEDED), (
        "and a TTL expiry is type 11, not type 3")
    short = s3.build(client_ip, db_ip, "icmp", b"", ttl=64, ident=0)
    assert s.error_message(short, "ttl_expired")[8:] == short[:s.ERROR_QUOTE], (
        "a datagram with no payload is quoted as far as it goes")
    _refuses(s.IcmpError, "a reason a router does not say",
             lambda: s.error_message(quoted, "too_slow"), names=("'too_slow'",))
    _refuses(s.IcmpError, "no reason at all",
             lambda: s.error_message(quoted, None), names=("None",))
    _refuses(s.IcmpError, "a datagram that is not bytes",
             lambda: s.error_message("a datagram", "ttl_expired"), names=("str",))
    _refuses(s.IcmpError, "a datagram too short to quote",
             lambda: s.error_message(quoted[:10], "ttl_expired"), names=("10",))
    assert s.error_message(quoted[:20], "no_route")[8:] == quoted[:20], (
        "a datagram of exactly a header is quoted, header and nothing else")

    # ---- answer: the peer's whole behaviour -------------------------------

    datagram = s3.build(client_ip, db_ip, "icmp", request)
    nowhere = s3.build(client_ip, dns_ip, "icmp", request)
    wire = Wire()
    peer = Host("db", db_ip, db_mac, wire)

    assert s.answer(peer, datagram) == reply, (
        "an echo request for this host is answered: %r" % (s.answer(peer, datagram),))
    assert s.answer(peer, datagram) == s.echo_reply(request), (
        "and answered with echo_reply's own bytes")
    assert s.answer(peer, s3.build(client_ip, db_ip, "icmp", with_data)) == (
        s.build(s.ICMP_ECHO_REPLY, 7, 2, b"abcd")), (
        "the ident, the seq and the payload all come back: %r"
        % (s.answer(peer, s3.build(client_ip, db_ip, "icmp", with_data)).hex(),))

    # The answer is a *message*: the caller wraps it.
    assert s.parse(s.answer(peer, datagram))["type"] == s.ICMP_ECHO_REPLY, (
        "and what comes back is the message, not the datagram: %r"
        % (s.parse(s.answer(peer, datagram)),))
    assert s.answer(peer, datagram) != s3.build(db_ip, client_ip, "icmp", reply), (
        "which is why the caller is the one that wraps it")
    assert s.answer(peer, quoted, reason="ttl_expired") == s.error_message(
        quoted, "ttl_expired"), (
        "a ttl_expired reason is quoted back: %r"
        % (s.answer(peer, quoted, reason="ttl_expired"),))
    assert s.answer(peer, quoted, reason="no_route") == s.error_message(
        quoted, "no_route"), (
        "and so is a no_route one: %r"
        % (s.answer(peer, quoted, reason="no_route"),))
    assert s.answer(peer, nowhere, reason="ttl_expired") == s.error_message(
        nowhere, "ttl_expired"), (
        "the offending datagram is not addressed to the router that refuses it")

    silence = [
        ("a datagram whose checksum disagrees",
         datagram[:15] + bytes((datagram[15] ^ 0xff,)) + datagram[16:]),
        ("a message whose checksum disagrees",
         s3.build(client_ip, db_ip, "icmp",
                  request[:2] + bytes((request[2] ^ 0xff,)) + request[3:])),
        ("a datagram for another address", nowhere),
        ("a datagram that is not icmp",
         s3.build(client_ip, db_ip, "tcp", request)),
        ("a datagram that is already a reply",
         s3.build(client_ip, db_ip, "icmp", reply)),
        ("a message that is not a request",
         s3.build(client_ip, db_ip, "icmp", s.build(s.ICMP_TIME_EXCEEDED))),
    ]
    for why, datagram_ in silence:
        silent = s.answer(peer, datagram_)
        assert silent is None, (
            "silence is the answer to %s: %r" % (why, silent))
    assert s.answer(peer, datagram, reason="too_slow") is None, (
        "and a reason this stack does not know is silence too: %r"
        % (s.answer(peer, datagram, reason="too_slow"),))
    assert s.answer(peer, s3.build(client_ip, db_ip, "icmp", b"\x63\x00\x00\x00"
                                   b"\x00\x00\x00\x00")) is None, (
        "and so is a message this stack cannot read at all")
    _refuses(s3.IpError, "answer of something that is not a datagram",
             lambda: s.answer(peer, b"\x00" * 10), names=("10",))

    # ---- answer on a real wire, between real hosts ------------------------

    wire = Wire()
    caller = Host("client", client_ip, client_mac, wire)
    peer = Host("db", db_ip, db_mac, wire)
    frame = s1.build(db_mac, client_mac, "ipv4", datagram)
    ordinal = caller.send(db_mac, frame)
    assert ordinal == 1 and wire.sent() == 1, (
        "the request goes on the link: %r" % (ordinal,))
    wire.advance(1)
    assert peer.recv() == [frame], (
        "and arrives in the peer's box: %r" % (peer.inbox(),))
    region = s1.parse(frame)["payload"]
    assert len(region) == 46, (
        "as a 46-byte payload region, the padding included: %d" % (len(region),))
    assert s3.unpack_header(region)["payload"] == request, (
        "whose datagram is 28 bytes of it, because total_length says so: %r"
        % (s3.unpack_header(region)["payload"],))
    assert s.answer(peer, region) == reply, (
        "the peer answers what really arrived, padding and all: %r"
        % (s.answer(peer, region),))
    answered = s3.build(db_ip, client_ip, "icmp", s.answer(peer, region))
    peer.send(client_mac, s1.build(client_mac, db_mac, "ipv4", answered))
    wire.advance(1)
    assert len(caller.recv()) == 1, (
        "and the answer comes back to the asker: %r" % (caller.inbox(),))
    inner = s1.parse(caller.inbox()[0])["payload"]
    assert inner[:s3.IPV4_HEADER + 8] == answered, (
        "a forty-six byte region again, with the answer first: %r" % (inner,))
    assert s.parse(s3.unpack_header(inner)["payload"]) == s.parse(reply), (
        "the layer above cuts it with total_length, and reads the reply")
    assert len(inner) == 46 and inner[s3.IPV4_HEADER:s3.IPV4_HEADER + 8] == reply, (
        "the message is the eight bytes at the twentieth of the region: %r"
        % (inner,))
    assert len(reply) == s.ICMP_HEADER == 8 and len(inner) == 46, (
        "so the region is forty-six bytes and the message is eight: a sum over "
        "one is not a sum over the other")
    assert [event["ordinal"] for event in wire.events("deliver")] == [1, 2], (
        "the wire's log ties the two frames to their sends")
    assert [event["data"] for event in wire.events("send")] == [
        frame, s1.build(client_mac, db_mac, "ipv4", answered)], (
        "and the bytes that crossed are the bytes the stages built")

    # ---- ping: the exchange the wire and the caller's box decide ----------

    echo = s.build(s.ICMP_ECHO_REQUEST, 0, 1)
    probe = Wire()
    probe_peer = Host("db", db_ip, db_mac, probe)
    probe_caller = Host("client", client_ip, client_mac, probe)
    requested = s3.build(client_ip, db_ip, "icmp", echo)
    reply_message = s.answer(probe_peer, requested)
    assert reply_message is not None, (
        "the peer answers the request ping is about to send: %r" % (reply_message,))
    reply_datagram = s3.build(db_ip, client_ip, "icmp", reply_message)
    reply_frame = s1.build(client_mac, db_mac, "ipv4", reply_datagram)

    # The reply is on the link, held, so it arrives on the last tick the
    # exchange waits: a ping that advanced once would miss it.
    wire = Wire({"delay": {1: 1}})
    caller = Host("client", client_ip, client_mac, wire)
    peer = Host("db", db_ip, db_mac, wire)
    held = peer.send(client_mac, reply_frame)
    assert held == 1 and wire.pending() == [{"ordinal": 1, "due": 2, "src": db_mac,
                                             "dst": client_mac}], (
        "the answer is the link's first frame and is due at tick two: %r"
        % (wire.pending(),))
    found = s.ping(wire, caller, db_mac, db_ip)
    assert found == {"sent": 2, "request": echo, "reply": reply_message, "ticks": 2}, (
        "the exchange, up to the bytes that came back: %r" % (found,))
    assert found["reply"] == s.build(s.ICMP_ECHO_REPLY, 0, 1), (
        "the reply is the message, ident and seq and all: %r" % (found["reply"],))
    assert wire.tick() == 2 and found["ticks"] == 2, (
        "the wire was advanced by the ticks ping promised to wait: %r at tick %r"
        % (found["ticks"], wire.tick()))
    assert wire.sent() == 2 and caller.sent() == 1 and peer.sent() == 1, (
        "one question and one answer crossed: %r" % (wire.sent(),))
    sends = wire.events("send")
    assert sends[1]["dst"] == db_mac and sends[1]["data"] == s1.build(
        db_mac, client_mac, "ipv4", requested), (
        "and the question is the frame the stages build, addressed to the peer: %r"
        % (sends[1],))
    assert sends[0]["data"] == reply_frame, (
        "the answer the caller read is the frame the peer put on the link")
    assert caller.inbox() == [reply_frame], (
        "and it is in the caller's box, which is where ping looked")

    # ---- nobody answers, and the wire that eats the answer ----------------

    wire = Wire()
    caller = Host("client", client_ip, client_mac, wire)
    nobody = s.ping(wire, caller, db_mac, db_ip)
    assert nobody == {"sent": 1, "request": echo, "reply": None, "ticks": 2}, (
        "an unanswered echo is a result and not an error: %r" % (nobody,))
    assert wire.sent() == 1 and wire.dropped() == 0 and caller.recv() == [], (
        "one frame went out and nothing came back: %r sent" % (wire.sent(),))
    _refuses(s.IcmpError, "a tick count that runs backwards",
             lambda: s.ping(Wire(), Host("client", client_ip, client_mac, None),
                            db_mac, db_ip, ticks=-1), names=("-1",))
    _refuses(s.IcmpError, "ping with an identifier that is not sixteen bits",
             lambda: s.ping(Wire(), Host("client", client_ip, client_mac, None),
                            db_mac, db_ip, ident=65536), names=("65536",))
    _refuses(s3.IpError, "ping to an address that is not an address",
             lambda: s.ping(Wire(), Host("client", client_ip, client_mac, None),
                            db_mac, "10.0.0.256"), names=("10.0.0.256",))
    _refuses(s1.FrameError, "ping to a MAC the wire refuses",
             lambda: s.ping(Wire(), Host("client", client_ip, client_mac, None),
                            "nope", db_ip), names=("'nope'",))

    wire = Wire({"loss": [1]})
    caller = Host("client", client_ip, client_mac, wire)
    peer = Host("db", db_ip, db_mac, wire)
    peer.send(client_mac, reply_frame)
    lost = s.ping(wire, caller, db_mac, db_ip)
    assert lost["reply"] is None and lost["sent"] == 2 and lost["ticks"] == 2, (
        "the link ate the answer, so the exchange is the same as an unanswered "
        "one: %r" % (lost,))
    assert wire.dropped() == 1 and [event["ordinal"] for event in
                                    wire.events("drop")] == [1], (
        "and the wire's own record says which frame it was: %r"
        % (wire.events("drop"),))
    assert [event["event"] for event in wire.log()] == [
        "send", "drop", "send", "deliver"], (
        "the log has the send that was eaten, the one that was not, and the one "
        "delivery there was: %r" % ([event["event"] for event in wire.log()],))

    wire = Wire({"loss": [2]})
    caller = Host("client", client_ip, client_mac, wire)
    peer = Host("db", db_ip, db_mac, wire)
    peer.send(client_mac, reply_frame)
    gone = s.ping(wire, caller, db_mac, db_ip)
    assert gone["reply"] == reply_message, (
        "a request the wire lost still meets the answer that was prearranged: %r"
        % (gone,))
    assert wire.dropped() == 1 and [event["ordinal"] for event in
                                    wire.events("drop")] == [2], (
        "and the wire's record is the one that says the request died: %r"
        % (wire.events("drop"),))

    # ---- the frames that are in the box but are not the answer ------------

    not_the_answer = (
        ("another echo's answer", s3.build(db_ip, client_ip, "icmp",
                                           s.build(s.ICMP_ECHO_REPLY, 99, 1))),
        ("a request where a reply belongs", s3.build(db_ip, client_ip, "icmp",
                                                     echo)),
        ("a datagram from another address", s3.build(dns_ip, client_ip, "icmp",
                                                     reply_message)),
        ("a datagram for another address", s3.build(db_ip, dns_ip, "icmp",
                                                    reply_message)),
    )
    for why, datagram_ in not_the_answer:
        wire = Wire()
        caller = Host("client", client_ip, client_mac, wire)
        peer = Host("db", db_ip, db_mac, wire)
        peer.send(client_mac, s1.build(client_mac, db_mac, "ipv4", datagram_))
        missed = s.ping(wire, caller, db_mac, db_ip)
        assert missed["reply"] is None, (
            "%s is not this exchange's answer: %r" % (why, missed))

    wire = Wire()
    caller = Host("client", client_ip, client_mac, wire)
    peer = Host("db", db_ip, db_mac, wire)
    peer.send(client_mac, s1.build(client_mac, db_mac, "ipv4",
             reply_datagram[:15] + bytes((reply_datagram[15] ^ 0xff,))
             + reply_datagram[16:]))
    assert s.ping(wire, caller, db_mac, db_ip)["reply"] is None, (
        "a reply whose datagram checksum disagrees is not an answer")

    wire = Wire()
    caller = Host("client", client_ip, client_mac, wire)
    peer = Host("db", db_ip, db_mac, wire)
    lever = reply_message[:2] + bytes((reply_message[2] ^ 0xff,)) + reply_message[3:]
    peer.send(client_mac, s1.build(client_mac, db_mac, "ipv4",
                                   s3.build(db_ip, client_ip, "icmp", lever)))
    assert s.ping(wire, caller, db_mac, db_ip)["reply"] is None, (
        "and one whose icmp checksum disagrees is not one either")

    wire = Wire()
    caller = Host("client", client_ip, client_mac, wire)
    peer = Host("db", db_ip, db_mac, wire)
    peer.send(client_mac, s1.build(client_mac, db_mac, "arp",
                                   s3.build(db_ip, client_ip, "icmp",
                                            reply_message)))
    assert s.ping(wire, caller, db_mac, db_ip)["reply"] is None, (
        "a frame that announces another type is not an ipv4 frame, whatever is "
        "inside it")

    wire = Wire()
    caller = Host("client", client_ip, client_mac, wire)
    peer = Host("db", db_ip, db_mac, wire)
    peer.send(dns_mac, reply_frame)
    elsewheres = s.ping(wire, caller, db_mac, db_ip)
    assert elsewheres["reply"] is None, (
        "a frame the link handed to somebody else is not in this host's box: %r"
        % (elsewheres,))
    assert [event["dst"] for event in wire.events("deliver")] == [dns_mac, db_mac], (
        "the link handed the answer to dns and the request to the peer, and "
        "nothing to the caller: %r" % ([event["dst"] for event in
                                        wire.events("deliver")],))
    assert caller.recv() == [], (
        "so the caller's box is empty, and a ping that read the wire's log "
        "instead of the box would count a frame that was never its own")

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "tcp-ip-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

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
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    CLIENT_IP = "10.0.0.5"

    SERVER_IP = "10.0.0.2"

    SYN_SEGMENT = {"src_port": 40000, "dst_port": 80, "seq": 1000, "ack": 0,
                   "flags": 2, "window": 65535, "payload": b""}

    def _syn():
        """A fresh SYN segment: the checks mutate their fixtures, never the fixture."""
        return dict(SYN_SEGMENT)

    def _ack(ack_number, seq=1001, payload=b"", flags=None):
        """A segment from the peer on port 40000, acknowledging `ack_number`."""
        return {"src_port": 40000, "dst_port": 80, "seq": seq, "ack": ack_number,
                "flags": 24 if flags is None else flags, "window": 65535,
                "payload": payload}

    def _connection_cases(s):
        """The state machine on its own: the table, the refusals and the log."""
        server = s.Connection(80, SERVER_IP, state="listen", seed=7)
        iss = s.initial_seq(7)

        first = server.step(_syn(), now=0)
        assert tuple(first) == ("state", "reply", "event"), (
            "a transition is three facts in the contract's order: %r" % (tuple(first),))
        assert first["state"] == "syn_received", (
            "a SYN in listen moves to syn_received: %r" % (first["state"],))
        assert first["event"] == "syn_received", (
            "and the event says so: %r" % (first["event"],))
        assert server.state() == "syn_received", (
            "the connection is where the transition put it: %r" % (server.state(),))
        assert s.flags_text(first["reply"]["flags"]) == "SYN,ACK", (
            "the answer to a SYN is SYN,ACK: %r" % (first["reply"],))
        assert first["reply"]["src_port"] == 80, (
            "the answer comes from this connection's port: %r" % (first["reply"],))
        assert first["reply"]["dst_port"] == 40000, (
            "and goes to the port the SYN came from: %r" % (first["reply"],))
        assert first["reply"]["seq"] == iss, (
            "the SYN,ACK's own sequence number is the ISN this side chose: %r"
            % (first["reply"]["seq"],))
        assert first["reply"]["ack"] == 1001 == s.seq_add(1000, 1), (
            "and its acknowledgement counts the peer's SYN as one sequence number: "
            "%r" % (first["reply"]["ack"],))
        assert first["reply"]["window"] == s.WINDOW_MAX, (
            "the window is the window, not the payload's length: %r"
            % (first["reply"]["window"],))
        assert first["reply"]["payload"] == b"", (
            "a SYN,ACK carries no payload: %r" % (first["reply"]["payload"],))

        completed = server.step(_ack(s.seq_add(iss, 1)), now=1)
        assert completed == {"state": "established", "reply": None, "event": "established"}, (
            "the peer's acknowledgement of our ISN is what establishes the "
            "connection, and nothing goes back: %r" % (completed,))
        assert server.state() == "established", (
            "and the state moved: %r" % (server.state(),))

        data = server.step(_ack(s.seq_add(iss, 1), seq=1001, payload=b"hello"), now=2)
        assert data["state"] == "established" and data["event"] == "data", (
            "a payload in established is data and leaves the state alone: %r" % (data,))
        assert data["reply"]["ack"] == 1006 == s.seq_add(1001, 5), (
            "its acknowledgement covers the payload it just took: %r"
            % (data["reply"]["ack"],))
        assert data["reply"]["seq"] == s.seq_add(iss, 1), (
            "and it is sent from this side's next sequence number: %r"
            % (data["reply"]["seq"],))
        assert s.flags_text(data["reply"]["flags"]) == "ACK", (
            "with the ack bit and nothing else: %r" % (data["reply"],))
        assert data["reply"]["payload"] == b"", (
            "an acknowledgement is a segment with no payload: %r"
            % (data["reply"]["payload"],))

        again = server.step(_syn(), now=3)
        assert again["state"] == "established" and again["event"] == "duplicate", (
            "a duplicate SYN does not reset a connection: %r" % (again,))
        assert server.state() == "established", (
            "the state it was in is the state it stays in: %r" % (server.state(),))
        assert s.flags_text(again["reply"]["flags"]) == "ACK", (
            "and it is answered with an acknowledgement, not with a handshake: %r"
            % (again["reply"],))
        assert again["reply"]["ack"] == 1001, (
            "which counts the SYN it is answering: %r" % (again["reply"]["ack"],))

        assert server.log() == (
            ("syn_received", "syn_received", "SYN,ACK", 0),
            ("established", "established", "", 1),
            ("established", "data", "ACK", 2),
            ("established", "duplicate", "ACK", 3)), (
            "the log is the transitions themselves — the state moved to, the event, "
            "the reply's flags and the tick — and a transition with no reply has no "
            "flags: %r" % (server.log(),))

        stranger = server.step(_ack(1001), now=4)
        assert stranger["state"] == "established" and stranger["event"] == "rejected", (
            "a segment that fits no row of this state is rejected, and the state it "
            "was in is the state it stays in: %r" % (stranger,))
        assert s.flags_text(stranger["reply"]["flags"]) == "RST", (
            "and the answer to it is a reset: %r" % (stranger["reply"],))
        assert stranger["reply"]["seq"] == s.seq_add(iss, 1), (
            "a reset is sent from this side's next sequence number: %r"
            % (stranger["reply"]["seq"],))
        assert stranger["reply"]["ack"] == 1001, (
            "and acknowledges what the segment it refuses acknowledged: %r"
            % (stranger["reply"]["ack"],))
        assert stranger["reply"]["payload"] == b"", (
            "a reset carries nothing: %r" % (stranger["reply"]["payload"],))
        assert server.state() == "established", (
            "a rejected segment never moves the connection: %r" % (server.state(),))
        assert server.log()[-1] == ("established", "rejected", "RST", 4), (
            "the rejection is a transition with the tick it happened at: %r"
            % (server.log()[-1],))

        reset = dict(_syn(), flags=s.RST, seq=1001)
        silenced = server.step(reset, now=5)
        assert silenced == {"state": "established", "reply": None,
                            "event": "rejected"}, (
            "an RST is never answered with an RST: %r" % (silenced,))
        assert server.state() == "established", (
            "and it does not move this state either: %r" % (server.state(),))
        assert server.log()[-1] == ("established", "rejected", "", 5), (
            "a transition that sends nothing has no flags to name: %r"
            % (server.log()[-1],))

        # ---- the active open --------------------------------------------------

        client = s.Connection(40000, CLIENT_IP, seed=3)
        assert client.state() == "closed", (
            "a connection starts closed: %r" % (client.state(),))
        assert client.log() == (), (
            "and has made no transition: %r" % (client.log(),))
        opened = client.open(SERVER_IP, "web")
        assert tuple(opened) == ("state", "reply", "event"), (
            "an open answers the same three facts: %r" % (tuple(opened),))
        assert opened["state"] == "syn_sent" and opened["event"] == "syn_sent", (
            "an active open moves to syn_sent and says so: %r" % (opened,))
        assert s.flags_text(opened["reply"]["flags"]) == "SYN", (
            "and hands back a bare SYN: %r" % (opened["reply"],))
        assert opened["reply"]["seq"] == s.initial_seq(3), (
            "carrying the ISN this side chose: %r" % (opened["reply"]["seq"],))
        assert opened["reply"]["ack"] == 0, (
            "a SYN acknowledges nothing, and says nothing: %r"
            % (opened["reply"]["ack"],))
        assert opened["reply"]["dst_port"] == 80 == s.WELL_KNOWN["web"], (
            "a well-known name in the port position is the port it stands for: %r"
            % (opened["reply"]["dst_port"],))
        assert opened["reply"]["src_port"] == 40000, (
            "and the source port is this connection's: %r" % (opened["reply"],))
        assert client.state() == "syn_sent", (
            "the connection is where the open put it: %r" % (client.state(),))

        answered = client.step({"src_port": 80, "dst_port": 40000, "seq": 5000,
                                "ack": s.seq_add(s.initial_seq(3), 1),
                                "flags": s.SYN | s.ACK, "window": 65535,
                                "payload": b""}, now=10)
        assert answered["state"] == "established", (
            "the SYN,ACK that acknowledges our ISN establishes the connection: %r"
            % (answered["state"],))
        assert s.flags_text(answered["reply"]["flags"]) == "ACK", (
            "and the last handshake segment is an acknowledgement: %r"
            % (answered["reply"],))
        assert answered["reply"]["ack"] == 5001, (
            "counting the peer's SYN: %r" % (answered["reply"]["ack"],))
        assert answered["reply"]["seq"] == s.seq_add(s.initial_seq(3), 1), (
            "and sent from this side's next sequence number: %r"
            % (answered["reply"]["seq"],))
        assert client.state() == "established", "and the state moved"

        # an acknowledgement one short does not complete the handshake
        early = s.Connection(40000, CLIENT_IP, seed=3)
        early.open(SERVER_IP, 80)
        too_early = early.step({"src_port": 80, "dst_port": 40000, "seq": 5000,
                                "ack": s.initial_seq(3), "flags": s.SYN | s.ACK,
                                "window": 65535, "payload": b""}, now=1)
        assert too_early["event"] == "rejected", (
            "a SYN,ACK that acknowledges the sequence number before our ISN is not "
            "the segment this state waits for: %r" % (too_early,))
        assert early.state() == "syn_sent", (
            "and the handshake is not half-open, it is open: %r" % (early.state(),))
        assert s.flags_text(too_early["reply"]["flags"]) == "RST", (
            "so it is refused: %r" % (too_early["reply"],))

        refused = s.Connection(40000, CLIENT_IP, seed=3)
        refused.open(SERVER_IP, 80)
        reset_by_peer = refused.step({"src_port": 80, "dst_port": 40000, "seq": 1,
                                      "ack": 0, "flags": s.RST, "window": 0,
                                      "payload": b""}, now=1)
        assert reset_by_peer == {"state": "closed", "reply": None,
                                 "event": "refused"}, (
            "an RST in syn_sent refuses the connection and closes it, silently: %r"
            % (reset_by_peer,))
        assert refused.state() == "closed", (
            "and the state is closed, not syn_sent: %r" % (refused.state(),))

        # ---- the passive open -------------------------------------------------

        listener = s.Connection(80, SERVER_IP)
        listening = listener.listen()
        assert tuple(listening) == ("state", "reply", "event"), (
            "a listen answers the same three facts: %r" % (tuple(listening),))
        assert listening == {"state": "listen", "reply": None, "event": "listen"}, (
            "a passive open sends nothing and says so: %r" % (listening,))
        assert listener.state() == "listen", "and the state moved"
        assert listener.log() == (("listen", "listen", "", 0),), (
            "which is a transition of its own: %r" % (listener.log(),))

        with_payload = listener.step({"src_port": 40000, "dst_port": 80, "seq": 1000,
                                      "ack": 0, "flags": s.SYN, "window": 65535,
                                      "payload": b"x"}, now=0)
        assert with_payload["event"] == "rejected", (
            "a SYN carrying a payload is not the segment a listener answers: %r"
            % (with_payload,))
        assert listener.state() == "listen", (
            "and the listener is still listening: %r" % (listener.state(),))

        ack_only = listener.step(_ack(1001, flags=s.ACK), now=0)
        assert ack_only["event"] == "rejected", (
            "and neither is a bare acknowledgement: %r" % (ack_only,))
        assert s.flags_text(ack_only["reply"]["flags"]) == "RST", (
            "a listener refuses with a reset, exactly like any other state: %r"
            % (ack_only["reply"],))

        half_open = listener.step({"src_port": 40000, "dst_port": 80, "seq": 1000,
                                   "ack": 1, "flags": s.SYN | s.ACK, "window": 65535,
                                   "payload": b""}, now=0)
        assert half_open["event"] == "rejected", (
            "a SYN,ACK is the other end's answer to *our* SYN, and a listener never "
            "sent one: %r" % (half_open,))
        assert listener.state() == "listen", (
            "so a listener stays listening, which is the half-open handshake this "
            "stage exists to not believe in: %r" % (listener.state(),))

        # ---- the steps this connection counts when no tick is handed over -----

        counted = s.Connection(80, SERVER_IP, state="listen")
        counted.step(_syn(), now=None)
        counted.step(_ack(1001, flags=s.ACK), now=None)
        assert [entry[3] for entry in counted.log()] == [0, 1], (
            "a connection with no clock counts its own steps, so two transitions "
            "are two different ticks: %r" % (counted.log(),))

        # ---- the refusals -----------------------------------------------------

        _refuses(s.TcpError, "Connection(0)", lambda: s.Connection(0),
                 names=("0", "port"))
        _refuses(s.TcpError, "Connection with a port above 65535",
                 lambda: s.Connection(70000), names=("70000",))
        _refuses(s.TcpError, "Connection with a port nobody knows",
                 lambda: s.Connection("ssh"), names=("'ssh'",))
        _refuses(s.TcpError, "Connection in a state that does not exist",
                 lambda: s.Connection(80, state="open"), names=("'open'",))
        _refuses(s.TcpError, "Connection with a seed that is not an int",
                 lambda: s.Connection(80, seed="1"), names=("'1'",))
        _refuses(s.TcpError, "Connection with a negative window",
                 lambda: s.Connection(80, window=-1), names=("-1",))
        _refuses(s.TcpError, "Connection with a window the field cannot hold",
                 lambda: s.Connection(80, window=70000), names=("70000",))
        _refuses(s.TcpError, "Connection with a local address that is not one",
                 lambda: s.Connection(80, local_ip="10.0.0"), names=("'10.0.0'",))
        _refuses(s.TcpError, "Connection with an octet above 255",
                 lambda: s.Connection(80, local_ip="10.0.0.256"), names=("'10.0.0.256'",))
        _refuses(s.TcpError, "Connection with a padded octet",
                 lambda: s.Connection(80, local_ip="10.0.0.05"), names=("'10.0.0.05'",))
        _refuses(s.TcpError, "Connection with a peer that is not a pair",
                 lambda: s.Connection(80, remote="10.0.0.2"), names=("'10.0.0.2'",))
        _refuses(s.TcpError, "Connection with a peer port nobody knows",
                 lambda: s.Connection(80, remote=(SERVER_IP, 0)), names=("0",))

        assert s.Connection("dns").state() == "closed", (
            "a connection may be built around a well-known name rather than a number")

        listening_again = s.Connection(80, SERVER_IP)
        listening_again.listen()
        _refuses(s.TcpError, "a second listen on the same connection",
                 lambda: listening_again.listen(), names=("'listen'",))
        _refuses(s.TcpError, "an open of a connection that is listening",
                 lambda: listening_again.open(SERVER_IP, 80), names=("'listen'",))

        _refuses(s.TcpError, "step of something that is not a dict",
                 lambda: s.Connection(80, state="listen").step(["not", "a", "segment"]),
                 names=("list",))
        _refuses(s.TcpError, "step of a segment missing a field",
                 lambda: s.Connection(80, state="listen").step(
                     {"src_port": 1, "dst_port": 80, "seq": 0, "ack": 0, "flags": 0,
                      "window": 0}),
                 names=("payload",))
        _refuses(s.TcpError, "step of an ack bit with a zero acknowledgement",
                 lambda: s.Connection(80, state="listen").step(
                     {"src_port": 1, "dst_port": 80, "seq": 0, "ack": 0,
                      "flags": s.ACK, "window": 0, "payload": b""}),
                 names=("ack",))
        _refuses(s.TcpError, "step of a segment for a port this connection is not on",
                 lambda: s.Connection(80, state="listen").step(
                     {"src_port": 1, "dst_port": 9, "seq": 0, "ack": 0, "flags": s.SYN,
                      "window": 0, "payload": b""}),
                 names=("9", "80"))
        _refuses(s.TcpError, "step of a segment from a peer that is not this one",
                 lambda: s.Connection(40000, CLIENT_IP, remote=(SERVER_IP, 80)).step(
                     {"src_port": 7, "dst_port": 40000, "seq": 0, "ack": 0,
                      "flags": s.SYN, "window": 0, "payload": b""}),
                 names=("7", "80"))
        _refuses(s.TcpError, "step at a tick that never happened",
                 lambda: s.Connection(80, state="listen").step(_syn(), now=-1),
                 names=("-1",))

    def _wire_cases(s, stage_01, Wire, Host, mac_of):
        """The handshake for real: three segments across a wire, decided from what
        arrived."""
        client_mac, server_mac = mac_of("client"), mac_of("web")
        wire = Wire()
        client_host = Host("client", CLIENT_IP, client_mac, wire)
        server_host = Host("web", SERVER_IP, server_mac, wire)

        client_end = s.Connection(40000, CLIENT_IP, seed=3)
        server_end = s.Connection(80, SERVER_IP, state="listen", seed=7)

        def carry(from_host, to_host, to_mac, segment, from_ip, to_ip):
            # The frame is built unpadded on purpose: a segment has no length field
            # of its own, so the padding a NIC adds is cut by the datagram's
            # total_length (stage 3) and never by this layer. The caller hands a
            # segment over exactly as it is.
            frame = stage_01.build(to_mac, from_host.mac, "ipv4",
                                   s.pack(segment, from_ip, to_ip), pad=False)
            from_host.send(to_mac, frame)
            wire.advance(1)
            arrived = to_host.recv()
            assert len(arrived) == 1, (
                "one frame sent is one frame in the other host's box: %r" % (arrived,))
            envelope = stage_01.parse(arrived[0])
            segment_back = s.unpack(envelope["payload"], from_ip, to_ip)
            assert segment_back["checksum_ok"] is True, (
                "the segment that crossed the wire is the segment the checksum was "
                "computed for: %r" % (segment_back,))
            return segment_back

        syn = carry(client_host, server_host, server_mac,
                    client_end.open(SERVER_IP, 80)["reply"], CLIENT_IP, SERVER_IP)
        assert syn["flags"] == s.SYN, (
            "what arrived is the SYN that was sent: %r" % (syn["flags"],))
        assert syn["seq"] == s.initial_seq(3), (
            "with the sequence number the stage chose: %r" % (syn["seq"],))

        answer = server_end.step(syn, now=wire.tick())
        assert answer["state"] == "syn_received", (
            "and the listener decides from what arrived: %r" % (answer,))
        syn_ack = carry(server_host, client_host, client_mac, answer["reply"],
                        SERVER_IP, CLIENT_IP)
        assert syn_ack["flags"] == s.SYN | s.ACK, (
            "a SYN,ACK is a SYN,ACK on the wire: %r" % (syn_ack["flags"],))

        done = client_end.step(syn_ack, now=wire.tick())
        assert done["state"] == "established", (
            "the peer's acknowledgement completes the active open: %r" % (done,))
        final = carry(client_host, server_host, server_mac, done["reply"],
                      CLIENT_IP, SERVER_IP)
        assert final["flags"] == s.ACK, (
            "and the last segment of the handshake is an acknowledgement: %r"
            % (final["flags"],))
        assert server_end.step(final, now=wire.tick()) == {
            "state": "established", "reply": None, "event": "established"}, (
            "which establishes the other end too")

        assert client_end.state() == server_end.state() == "established", (
            "both ends of one handshake, or neither: %r and %r"
            % (client_end.state(), server_end.state()))
        assert wire.sent() == 3 and wire.delivered() == 3, (
            "and the wire carried exactly the three segments the handshake is: %r "
            "sent, %r delivered" % (wire.sent(), wire.delivered()))
        assert [entry["ordinal"] for entry in wire.deliver()] == [3], (
            "the last frame is the third send: %r" % (wire.deliver(),))
        assert len(server_host.inbox()) == 2 and len(client_host.inbox()) == 1, (
            "two segments arrived at the listener and one at the client: %r and %r"
            % (server_host.inbox(), client_host.inbox()))

    import stage_01
    import stage_05 as s
    from hosts import Host, mac_of
    from wire import Wire

    # ---- the constants ----------------------------------------------------

    assert s.TCP_HEADER == 20, (
        "a tcp header with no options is 20 bytes: %r" % (s.TCP_HEADER,))
    assert s.TCP_OFFSET == 5, (
        "the data offset that says 'no options' is 5: %r" % (s.TCP_OFFSET,))
    assert s.SEQ_MAX == 2 ** 32, (
        "the sequence space is 2**32: %r" % (s.SEQ_MAX,))
    assert s.SEQ_HALF == 2 ** 31 == s.SEQ_MAX // 2, (
        "half the sequence space is 2**31: %r" % (s.SEQ_HALF,))
    assert s.WINDOW_MAX == 65535, (
        "the most a 16-bit window field can say is 65535: %r" % (s.WINDOW_MAX,))
    assert (s.FIN, s.SYN, s.RST, s.PSH, s.ACK) == (1, 2, 4, 8, 16), (
        "the six flags are bits 0 to 4, FIN first: %r"
        % ((s.FIN, s.SYN, s.RST, s.PSH, s.ACK),))
    assert s.FLAGS == (s.FIN, s.SYN, s.RST, s.PSH, s.ACK), (
        "FLAGS is the same five in the header's own order: %r" % (s.FLAGS,))
    assert s.STATES == ("closed", "listen", "syn_sent", "syn_received",
                        "established"), (
        "five states, in the order the ladder walks them: %r" % (s.STATES,))
    assert s.WELL_KNOWN == {"dns": 53, "web": 80, "db": 5432}, (
        "the three ports a name stands for: %r" % (s.WELL_KNOWN,))
    assert issubclass(s.TcpError, ValueError), (
        "a refusal here is a ValueError: %r" % (s.TcpError,))

    # ---- the flag vocabulary ----------------------------------------------

    assert s.flags_text(s.SYN | s.ACK) == "SYN,ACK", (
        "the two flags of a handshake's answer, in that order: %r"
        % (s.flags_text(s.SYN | s.ACK),))
    assert s.flags_text(s.FIN | s.SYN | s.RST | s.PSH | s.ACK) == (
        "FIN,SYN,RST,PSH,ACK"), (
        "every flag, in the header's own order: %r"
        % (s.flags_text(s.FIN | s.SYN | s.RST | s.PSH | s.ACK),))
    assert s.flags_text(s.ACK) == "ACK", (
        "one flag is one word: %r" % (s.flags_text(s.ACK),))
    assert s.flags_text(s.SYN) == "SYN", (
        "and the SYN is spelled the way the contract spells it: %r"
        % (s.flags_text(s.SYN),))
    assert s.flags_text(0) == "", (
        "a segment with no flags set is a name of no words: %r"
        % (s.flags_text(0),))
    _refuses(s.TcpError, "flags_text(32)", lambda: s.flags_text(32),
             names=("32",))
    _refuses(s.TcpError, "flags_text of the reserved bit 64",
             lambda: s.flags_text(64), names=("64",))
    _refuses(s.TcpError, "flags_text of a string",
             lambda: s.flags_text("SYN"), names=("'SYN'",))

    # ---- the segment's bytes ----------------------------------------------

    segment = {"src_port": 40000, "dst_port": 80, "seq": 1, "ack": 0,
               "flags": s.SYN, "window": s.WINDOW_MAX, "payload": b""}
    data = s.pack(segment, CLIENT_IP, SERVER_IP)
    assert data == bytes.fromhex("9c40005000000001000000005002ffffff4a0000"), (
        "a SYN from 40000 to 80, seq 1, window 65535, packs to exactly these "
        "bytes: %r" % (data.hex(),))
    assert s.pack(segment, CLIENT_IP, SERVER_IP) == data, (
        "and packing the same segment twice is the same bytes")
    assert len(data) == s.TCP_HEADER == 20, (
        "a header with no options is exactly TCP_HEADER bytes: %d" % (len(data),))

    parsed = s.unpack(data, CLIENT_IP, SERVER_IP)
    assert tuple(parsed) == ("src_port", "dst_port", "seq", "ack", "flags",
                            "window", "payload", "checksum_ok"), (
        "a segment's eight facts, in the contract's order: %r" % (tuple(parsed),))
    assert parsed["src_port"] == 40000 and parsed["dst_port"] == 80, (
        "the two ports are the first four bytes: %r" % (parsed,))
    assert parsed["seq"] == 1 and parsed["ack"] == 0, (
        "then the sequence number and the acknowledgement: %r" % (parsed,))
    assert parsed["flags"] == s.SYN == 2, (
        "the flags are the low six bits of the offset/flags word: %r"
        % (parsed["flags"],))
    assert parsed["window"] == s.WINDOW_MAX == 65535, (
        "then the window: %r" % (parsed["window"],))
    assert parsed["payload"] == b"", (
        "a header with nothing after it has an empty payload: %r"
        % (parsed["payload"],))
    assert parsed["checksum_ok"] is True, (
        "the segment was packed with the pseudo-header checksum, so it checks "
        "out: %r" % (parsed["checksum_ok"],))
    assert s.unpack(data)["checksum_ok"] is None, (
        "without the two addresses there is nothing to check the checksum "
        "against, and a segment nobody checked is not a segment that checked "
        "out: %r" % (s.unpack(data)["checksum_ok"],))
    assert s.unpack(data, CLIENT_IP, "10.0.0.9")["checksum_ok"] is False, (
        "a checksum is a fact about two addresses, and the wrong address says "
        "so: %r" % (s.unpack(data, CLIENT_IP, "10.0.0.9")["checksum_ok"],))

    payload_segment = {"src_port": 80, "dst_port": 40000, "seq": 1, "ack": 100,
                       "flags": s.ACK | s.PSH, "window": 8, "payload": b"hello"}
    with_payload = s.pack(payload_segment, SERVER_IP, CLIENT_IP)
    assert with_payload == bytes.fromhex(
        "00509c40000000010000006450180008baf1000068656c6c6f"), (
        "a data segment with a five-byte payload packs to exactly these bytes, "
        "odd byte and all: %r" % (with_payload.hex(),))
    assert len(with_payload) == s.TCP_HEADER + 5 == 25, (
        "the payload follows the header: %d bytes" % (len(with_payload),))
    read_back = s.unpack(with_payload, SERVER_IP, CLIENT_IP)
    assert read_back["payload"] == b"hello", (
        "and it comes back exactly as it went in: %r" % (read_back["payload"],))
    assert read_back["flags"] == s.ACK | s.PSH == 24, (
        "with both of its flags: %r" % (read_back["flags"],))
    assert read_back["checksum_ok"] is True, (
        "a payload is covered by the checksum too: %r" % (read_back["checksum_ok"],))
    corrupt = with_payload[:24] + b"\x00"
    assert s.unpack(corrupt, SERVER_IP, CLIENT_IP)["checksum_ok"] is False, (
        "one byte changed and the checksum does not check out: %r"
        % (s.unpack(corrupt, SERVER_IP, CLIENT_IP)["checksum_ok"],))

    for bad, why in ((data[:19], "19"), (b"", "0")):
        _refuses(s.TcpError, "unpack of %s bytes" % (why,),
                 lambda bad=bad: s.unpack(bad), names=("20", why))
    _refuses(s.TcpError, "unpack of something that is not bytes",
             lambda: s.unpack("a segment"), names=("str",))
    offset_six = bytearray(data)
    offset_six[12] = 0x60
    _refuses(s.TcpError, "unpack of a data offset of 6",
             lambda: s.unpack(bytes(offset_six)), names=("6", "5"))
    _refuses(s.TcpError, "unpack of a zero source port",
             lambda: s.unpack(b"\x00\x00" + data[2:]), names=("0",))
    _refuses(s.TcpError, "unpack of a zero destination port",
             lambda: s.unpack(data[:2] + b"\x00\x00" + data[4:]), names=("0",))

    _refuses(s.TcpError, "pack without the two addresses",
             lambda: s.pack(segment), names=("src", "dst"))
    _refuses(s.TcpError, "pack of a dict that is not a segment",
             lambda: s.pack(["not", "a", "segment"]), names=("list",))
    _refuses(s.TcpError, "pack of a segment missing its payload",
             lambda: s.pack({"src_port": 1, "dst_port": 2, "seq": 0, "ack": 0,
                             "flags": 0, "window": 0}),
             names=("payload",))
    _refuses(s.TcpError, "pack of a payload that is not bytes",
             lambda: s.pack(dict(segment, payload="hello"), CLIENT_IP, SERVER_IP),
             names=("str",))
    _refuses(s.TcpError, "pack of an ack bit with a zero acknowledgement",
             lambda: s.pack(dict(segment, flags=s.ACK), CLIENT_IP, SERVER_IP),
             names=("ack",))
    _refuses(s.TcpError, "pack of an address that is not an address",
             lambda: s.pack(segment, CLIENT_IP, "nope"), names=("'nope'",))

    # ---- the sequence space ----------------------------------------------

    assert s.seq_add(0, 1) == 1, "one past zero is one: %r" % (s.seq_add(0, 1),)
    assert s.seq_add(s.SEQ_MAX - 1, 1) == 0, (
        "one past the last sequence number is zero: %r"
        % (s.seq_add(s.SEQ_MAX - 1, 1),))
    assert s.seq_add(s.SEQ_MAX - 1, 2) == 1, (
        "and two past it is one: %r" % (s.seq_add(s.SEQ_MAX - 1, 2),))
    assert s.seq_add(0, -1) == s.SEQ_MAX - 1, (
        "backwards wraps the same way: %r" % (s.seq_add(0, -1),))
    assert s.seq_add(5, 0) == 5, "nothing moved is the same number"

    assert s.seq_before(0, 1) is True, "zero is behind one"
    assert s.seq_before(1, 0) is False, "one is not behind zero"
    assert s.seq_before(s.SEQ_MAX - 1, 1) is True, (
        "the last sequence number is behind the first one, which is the case "
        "`<` gets wrong: %r" % (s.seq_before(s.SEQ_MAX - 1, 1),))
    assert s.seq_before(1, s.SEQ_MAX - 1) is False, (
        "and the first one is not behind the last: %r"
        % (s.seq_before(1, s.SEQ_MAX - 1),))
    assert s.seq_before(0, s.SEQ_HALF - 1) is True, (
        "half the space away is still behind: %r"
        % (s.seq_before(0, s.SEQ_HALF - 1),))
    assert s.seq_before(0, s.SEQ_HALF) is False, (
        "exactly half the space away has no answer, and the formula's is 'not "
        "behind': %r" % (s.seq_before(0, s.SEQ_HALF),))
    assert s.seq_before(5, 5) is True, (
        "two equal sequence numbers are zero apart, so nothing is ahead: %r"
        % (s.seq_before(5, 5),))
    _refuses(s.TcpError, "seq_add of a string", lambda: s.seq_add("1", 1),
             names=("'1'",))
    _refuses(s.TcpError, "seq_add of a bool", lambda: s.seq_add(True, 1),
             names=("True",))
    _refuses(s.TcpError, "seq_before of a string", lambda: s.seq_before(1, "2"),
             names=("'2'",))

    # ---- the number a connection starts at --------------------------------

    assert s.initial_seq(0) == 3257408855, (
        "seed 0 is this sequence number: %r" % (s.initial_seq(0),))
    assert s.initial_seq(1) == 1400643606, (
        "seed 1 is this one: %r" % (s.initial_seq(1),))
    assert s.initial_seq(7) == 1121102384, (
        "seed 7 is this one: %r" % (s.initial_seq(7),))
    assert s.initial_seq(7) == s.initial_seq(7) != 7, (
        "the same seed is the same number, and it is never the seed itself: %r"
        % (s.initial_seq(7),))
    assert 0 <= s.initial_seq(2 ** 40 + 3) < s.SEQ_MAX, (
        "a huge seed is still a sequence number: %r"
        % (s.initial_seq(2 ** 40 + 3),))
    assert s.initial_seq(3) != s.initial_seq(4), (
        "two seeds a step apart are not two nearby sequence numbers: %r and %r"
        % (s.initial_seq(3), s.initial_seq(4)))
    assert abs(s.initial_seq(1) - s.initial_seq(0)) > 1000000, (
        "the sequence numbers a seed apart are spread over the whole space, not "
        "the seed: %r and %r" % (s.initial_seq(0), s.initial_seq(1)))
    _refuses(s.TcpError, "initial_seq of a string",
             lambda: s.initial_seq("seven"), names=("'seven'",))
    _refuses(s.TcpError, "initial_seq of a bool",
             lambda: s.initial_seq(True), names=("True",))

    _connection_cases(s)
    _wire_cases(s, stage_01, Wire, Host, mac_of)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "tcp-ip-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

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
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _seg(seq, payload, dst_port=80, src_port=40000):
        """A segment on its way to whoever is listening on `dst_port`."""
        return {"src_port": src_port, "dst_port": dst_port, "seq": seq, "ack": 0,
                "flags": 24, "window": 8, "payload": payload}

    def _receiver_cases(s):
        """The receiver: what arrived, what waits, and the one number that covers it."""
        stream = s.Receiver(80)
        assert stream.window() == 8, (
            "a fresh receiver of the default capacity offers eight bytes: %r"
            % (stream.window(),))
        assert stream.buffered() == (), (
            "and holds nothing: %r" % (stream.buffered(),))
        assert stream.delivered() == b"", (
            "and has handed up nothing: %r" % (stream.delivered(),))
        assert stream.log() == (), (
            "and has decided nothing: %r" % (stream.log(),))

        first = stream.accept(_seg(0, b"abcdefgh"))
        assert tuple(first) == ("acked", "buffered", "delivered", "window"), (
            "a decision is four facts in the contract's order: %r" % (tuple(first),))
        assert first == {"acked": 8, "buffered": 0, "delivered": 8, "window": 8}, (
            "the first segment defines where the stream begins, goes straight up, "
            "and is acknowledged by the number after its last byte: %r" % (first,))
        assert stream.delivered() == b"abcdefgh", (
            "and the stream is the bytes it carried: %r" % (stream.delivered(),))
        assert stream.buffered() == (), (
            "nothing is left waiting: %r" % (stream.buffered(),))
        assert stream.window() == 8, (
            "and nothing is held, so the whole window is free again: %r"
            % (stream.window(),))
        assert stream.log() == ({"seq": 0, "length": 8, "event": "delivered",
                                 "acked": 8},), (
            "the decision is logged as the segment, what it moved and what it is "
            "acknowledged with: %r" % (stream.log(),))

        ahead = stream.accept(_seg(24, b"QRSTUVWX"))
        assert ahead == {"acked": 8, "buffered": 1, "delivered": 0, "window": 0}, (
            "a segment ahead of the front is held, not discarded, and the window "
            "shrinks by exactly what is held: %r" % (ahead,))
        assert stream.buffered() == ((24, b"QRSTUVWX"),), (
            "the buffer is the segments themselves, in sequence order: %r"
            % (stream.buffered(),))
        assert stream.window() == 0, (
            "one segment in a window of one segment leaves no window at all: %r"
            % (stream.window(),))
        assert stream.log()[-1] == {"seq": 24, "length": 8, "event": "buffered",
                                    "acked": 8}, (
            "and the log says the segment was a wait, not the stream: %r"
            % (stream.log()[-1],))

        # The same segment again: every number can be right and the stream still be
        # wrong, which is why this is the case that reads the bytes.
        repeat = stream.accept(_seg(24, b"QRSTUVWX"))
        assert repeat["acked"] == 8, (
            "an acknowledgement of a segment already held moves nothing: %r"
            % (repeat["acked"],))
        assert repeat == {"acked": 8, "buffered": 1, "delivered": 0, "window": 0}, (
            "and the receiver is exactly where it was: %r" % (repeat,))
        assert stream.buffered() == ((24, b"QRSTUVWX"),), (
            "the segment is stored once, whatever it arrived twice: %r"
            % (stream.buffered(),))
        assert stream.delivered() == b"abcdefgh", (
            "and the stream does not have its bytes twice: %r"
            % (stream.delivered(),))
        assert stream.log()[-1] == {"seq": 24, "length": 8, "event": "repeat",
                                    "acked": 8}, (
            "the log calls it what it is: a repeat, acknowledged again: %r"
            % (stream.log()[-1],))

        crowded = stream.accept(_seg(32, b"abcdefgh"))
        assert crowded == {"acked": 8, "buffered": 1, "delivered": 0, "window": 0}, (
            "a segment that does not fit the window is acknowledged with the "
            "current number and dropped: %r" % (crowded,))
        assert stream.buffered() == ((24, b"QRSTUVWX"),), (
            "and it is not held: %r" % (stream.buffered(),))
        assert stream.log()[-1]["event"] == "refused", (
            "which is a decision of its own: %r" % (stream.log()[-1],))

        bare = stream.accept(_seg(64, b""))
        assert bare == {"acked": 8, "buffered": 1, "delivered": 0, "window": 0}, (
            "a bare acknowledgement ahead of the front moves nothing and fills "
            "nothing: %r" % (bare,))
        assert stream.buffered() == ((24, b"QRSTUVWX"),), (
            "an empty segment is never worth a place in the buffer: %r"
            % (stream.buffered(),))

        assert stream.accept(_seg(8, b"IJKLMNOP"))["acked"] == 16, (
            "the front moves to the end of what is contiguous, and no further")
        filled = stream.accept(_seg(16, b"qrstuvwx"))
        assert filled == {"acked": 32, "buffered": 0, "delivered": 16, "window": 8}, (
            "the segment that fills the gap covers everything behind it in one "
            "number: %r" % (filled,))
        assert stream.delivered() == b"abcdefghIJKLMNOPqrstuvwxQRSTUVWX", (
            "and the stream is in order, however it arrived: %r"
            % (stream.delivered(),))
        assert stream.buffered() == (), (
            "the buffer is empty once its contents are contiguous: %r"
            % (stream.buffered(),))
        assert stream.window() == 8, (
            "and the window is free again: %r" % (stream.window(),))

        old = stream.accept(_seg(0, b"abcdefgh"))
        assert old == {"acked": 32, "buffered": 0, "delivered": 0, "window": 8}, (
            "a segment already handed up is a repeat of a segment already handed "
            "up: %r" % (old,))
        assert stream.delivered() == b"abcdefghIJKLMNOPqrstuvwxQRSTUVWX", (
            "and the stream is not handed the same bytes twice: %r"
            % (stream.delivered(),))
        assert stream.log()[-1] == {"seq": 0, "length": 8, "event": "repeat",
                                    "acked": 32}, (
            "the acknowledgement is the one it already gave: %r"
            % (stream.log()[-1],))
        assert stream.log() == (
            {"seq": 0, "length": 8, "event": "delivered", "acked": 8},
            {"seq": 24, "length": 8, "event": "buffered", "acked": 8},
            {"seq": 24, "length": 8, "event": "repeat", "acked": 8},
            {"seq": 32, "length": 8, "event": "refused", "acked": 8},
            {"seq": 64, "length": 0, "event": "repeat", "acked": 8},
            {"seq": 8, "length": 8, "event": "delivered", "acked": 16},
            {"seq": 16, "length": 8, "event": "delivered", "acked": 32},
            {"seq": 0, "length": 8, "event": "repeat", "acked": 32}), (
            "every decision this receiver made, in order: %r" % (stream.log(),))

        # ---- a window of three segments --------------------------------------

        wide = s.Receiver(80, capacity=24)
        assert wide.window() == 24, (
            "a capacity of three segments is a window of three segments: %r"
            % (wide.window(),))
        assert wide.accept(_seg(100, b"01234567")) == {
            "acked": 108, "buffered": 0, "delivered": 8, "window": 24}, (
            "and its first segment defines where this stream begins")
        assert wide.accept(_seg(124, b"abcdefgh")) == {
            "acked": 108, "buffered": 1, "delivered": 0, "window": 16}, (
            "the window is in bytes, and eight held out of order leave sixteen: %r"
            % (wide.window(),))
        assert wide.accept(_seg(116, b"IJKLMNOP")) == {
            "acked": 108, "buffered": 2, "delivered": 0, "window": 8}, (
            "and sixteen held leave eight, not one segment: %r" % (wide.window(),))
        assert wide.buffered() == ((116, b"IJKLMNOP"), (124, b"abcdefgh")), (
            "the buffer is in sequence order, not arrival order: %r"
            % (wide.buffered(),))
        assert wide.accept(_seg(108, b"QRSTUVWX")) == {
            "acked": 132, "buffered": 0, "delivered": 24, "window": 24}, (
            "the acknowledgement is the next expected number, never the last one "
            "received: %r" % (wide.log()[-1],))
        assert wide.delivered() == b"01234567QRSTUVWXIJKLMNOPabcdefgh", (
            "and the whole stream goes up in one call, in order: %r"
            % (wide.delivered(),))

        # ---- the refusals -----------------------------------------------------

        _refuses(s.WindowError, "a capacity below one mss",
                 lambda: s.Receiver(80, capacity=4), names=("4", "8"))
        _refuses(s.WindowError, "a capacity of zero",
                 lambda: s.Receiver(80, capacity=0), names=("0",))
        _refuses(s.WindowError, "a receiver on a port that is not a port",
                 lambda: s.Receiver(0), names=("0",))
        _refuses(s.WindowError, "an accept of something that is not a dict",
                 lambda: stream.accept(["not", "a", "segment"]), names=("list",))
        _refuses(s.WindowError, "an accept of a segment missing a field",
                 lambda: stream.accept({"seq": 0, "payload": b""}),
                 names=("src_port",))
        _refuses(s.WindowError, "an accept of a payload that is not bytes",
                 lambda: stream.accept(_seg(0, "abcdefgh")), names=("str",))
        _refuses(s.WindowError, "an accept of a payload longer than the window",
                 lambda: s.Receiver(80).accept(_seg(0, b"123456789")),
                 names=("9", "8"))

    def _sender_cases(s, stage_05):
        """The sender: what the queue implies and what the window allows."""
        sender = s.Sender(40000, 80, iss=1000)
        assert sender.in_flight() == 0, (
            "a fresh sender has nothing in flight: %r" % (sender.in_flight(),))
        assert sender.sent() == (), (
            "and no in-flight table: %r" % (sender.sent(),))
        assert sender.log() == (), (
            "and has decided nothing: %r" % (sender.log(),))

        queued = sender.queue(b"abcdefghijklmnopq")
        assert len(queued) == 3, (
            "seventeen bytes are three segments: %r" % (len(queued),))
        assert [segment["seq"] for segment in queued] == [1000, 1008, 1016], (
            "at the sequence numbers the queue implies: %r"
            % ([segment["seq"] for segment in queued],))
        assert [len(segment["payload"]) for segment in queued] == [8, 8, 1], (
            "the last segment is short and is not rounded up: %r"
            % ([len(segment["payload"]) for segment in queued],))
        assert queued[2]["payload"] == b"q", (
            "and it is the bytes that were left: %r" % (queued[2]["payload"],))
        assert queued[2]["window"] == 8, (
            "a short segment still carries the window, not its own length: %r"
            % (queued[2]["window"],))
        assert b"".join(segment["payload"] for segment in queued) == (
            b"abcdefghijklmnopq"), (
            "the segments are the payload, in order, with nothing added or lost")
        assert tuple(queued[0]) == ("src_port", "dst_port", "seq", "ack", "flags",
                                    "window", "payload"), (
            "a queued segment is a segment, with stage 5's seven fields: %r"
            % (tuple(queued[0]),))
        assert queued[0]["src_port"] == 40000 and queued[0]["dst_port"] == 80, (
            "on this sender's ports: %r" % (queued[0],))
        assert queued[0]["flags"] == stage_05.PSH, (
            "a data segment carries data and pushes it: %r" % (queued[0]["flags"],))
        assert queued[0]["ack"] == 0, (
            "and acknowledges nothing, because it is not this end's number: %r"
            % (queued[0]["ack"],))
        assert queued[0]["window"] == 8, (
            "and carries the window the sender is honouring: %r"
            % (queued[0]["window"],))
        assert sender.in_flight() == 0, (
            "queueing is not sending: %r" % (sender.in_flight(),))
        assert sender.sent() == (), (
            "so the in-flight table is still empty: %r" % (sender.sent(),))
        assert sender.log() == ({"event": "queue", "segments": 3, "bytes": 17},), (
            "and the queue is a decision: %r" % (sender.log(),))

        first_batch = sender.next_segments(2)
        assert len(first_batch) == 1, (
            "asked for two segments and allowed one, it hands over one: %r"
            % (len(first_batch),))
        assert first_batch[0] is queued[0], (
            "and it is the first of the queue, in order: %r" % (first_batch,))
        assert sender.in_flight() == 8, (
            "which is eight bytes in flight: %r" % (sender.in_flight(),))
        assert sender.sent() == ((1000, 8),), (
            "the in-flight table says which sequence number and how long: %r"
            % (sender.sent(),))
        assert sender.next_segments(5) == (), (
            "and nothing more fits the window, however many are asked for")
        assert sender.in_flight() == 8, (
            "so the window is still full: %r" % (sender.in_flight(),))
        assert sender.log()[1] == {"event": "next", "segments": 1, "bytes": 8}, (
            "the call is logged with what it handed over: %r" % (sender.log()[1],))

        ack = sender.acknowledge(1008)
        assert tuple(ack) == ("acked", "again", "in_flight"), (
            "an acknowledgement is three facts in the contract's order: %r"
            % (tuple(ack),))
        assert ack == {"acked": 8, "again": False, "in_flight": 0}, (
            "the segment that ends at the acknowledged number leaves the table: %r"
            % (ack,))
        assert sender.sent() == (), (
            "and the table is empty: %r" % (sender.sent(),))
        again = sender.acknowledge(1008)
        assert again == {"acked": 0, "again": True, "in_flight": 0}, (
            "an acknowledgement that moves nothing is a signal, not progress: %r"
            % (again,))
        following = sender.next_segments(1)
        assert [segment["seq"] for segment in following] == [1008], (
            "and the queue goes on where it left off: %r" % (following,))
        assert sender.in_flight() == 8, (
            "the second segment is now in flight: %r" % (sender.in_flight(),))

        # ---- a window of three segments --------------------------------------

        wider = s.Sender(40000, 80, iss=0, window=24)
        assert wider.queue(b"0123456789abcdefghij")[2]["payload"] == b"ghij", (
            "twenty bytes are eight, eight and four")
        batch = wider.next_segments(3)
        assert len(batch) == 3, (
            "and a window of twenty-four lets all three out: %r" % (len(batch),))
        assert wider.in_flight() == 20, (
            "which is twenty bytes in flight: %r" % (wider.in_flight(),))
        assert wider.sent() == ((0, 8), (8, 8), (16, 4)), (
            "the table is `(seq, length)` pairs, in order: %r" % (wider.sent(),))
        assert wider.next_segments(2) == (), (
            "and there is nothing left to hand over")
        part = wider.acknowledge(8)
        assert part == {"acked": 8, "again": False, "in_flight": 12}, (
            "a cumulative acknowledgement of 8 covers the first segment and only "
            "the first: %r" % (part,))
        assert wider.sent() == ((8, 8), (16, 4)), (
            "and leaves the ones behind it in the table: %r" % (wider.sent(),))
        assert wider.acknowledge(8) == {"acked": 0, "again": True, "in_flight": 12}, (
            "a duplicate acknowledgement is not progress: %r"
            % (wider.acknowledge(8),))
        last = wider.acknowledge(20)
        assert last == {"acked": 12, "again": False, "in_flight": 0}, (
            "and the acknowledgement that covers everything clears the table: %r"
            % (last,))
        assert wider.sent() == () and wider.in_flight() == 0, (
            "nothing is in flight once everything is acknowledged")
        assert wider.log() == (
            {"event": "queue", "segments": 3, "bytes": 20},
            {"event": "next", "segments": 3, "bytes": 20},
            {"event": "next", "segments": 0, "bytes": 0},
            {"event": "ack", "segments": 1, "bytes": 8},
            {"event": "ack", "segments": 0, "bytes": 0},
            {"event": "ack", "segments": 2, "bytes": 12}), (
            "every decision the sender made, in order: %r" % (wider.log(),))

        # ---- the boundaries ---------------------------------------------------

        zero = s.Sender(40000, 80, iss=0, window=0)
        zero.queue(b"abcdefgh")
        assert zero.next_segments(1) == (), (
            "a peer that offered no window gets no segment: %r"
            % (zero.next_segments(1),))
        assert zero.in_flight() == 0, "and nothing is in flight"

        counting = s.Sender(40000, 80, iss=0, window=24)
        counting.queue(b"0123456789abcdefghij")
        assert counting.next_segments(0) == (), (
            "asking for no segments hands over none, however open the window is")
        assert counting.in_flight() == 0, (
            "and puts nothing in flight: %r" % (counting.in_flight(),))
        one_of_three = counting.next_segments(1)
        assert len(one_of_three) == 1, (
            "asking for one segment when the window allows three hands over one: "
            "%r" % (len(one_of_three),))
        assert counting.in_flight() == 8, (
            "which is one segment's worth of bytes: %r" % (counting.in_flight(),))

        fresh = s.Sender(40000, 80, iss=0)
        assert fresh.acknowledge(0) == {"acked": 0, "again": True, "in_flight": 0}, (
            "an acknowledgement of everything sent when nothing was sent is the "
            "boundary: %r" % (fresh.acknowledge(0),))
        _refuses(s.WindowError, "an acknowledgement of a sequence number never sent",
                 lambda: fresh.acknowledge(8), names=("8",))

        one = s.Sender(40000, 80, iss=0)
        one.queue(b"abcdefgh")
        one.next_segments(1)
        _refuses(s.WindowError, "an acknowledgement one past the last byte sent",
                 lambda: one.acknowledge(9), names=("9",))
        assert one.acknowledge(8) == {"acked": 8, "again": False, "in_flight": 0}, (
            "and the acknowledgement of the last byte sent is the last it accepts")

        _refuses(s.WindowError, "a negative window",
                 lambda: s.Sender(1, 2, window=-1), names=("-1",))
        _refuses(s.WindowError, "a window the 16-bit field cannot hold",
                 lambda: s.Sender(1, 2, window=70000), names=("70000",))
        _refuses(s.WindowError, "an iss that is not an int",
                 lambda: s.Sender(1, 2, iss="0"), names=("'0'",))
        _refuses(s.WindowError, "an iss that is a bool",
                 lambda: s.Sender(1, 2, iss=True), names=("True",))
        _refuses(s.WindowError, "a sender on a port that is not a port",
                 lambda: s.Sender(0, 80), names=("0",))
        _refuses(s.WindowError, "a payload that is not bytes",
                 lambda: s.Sender(1, 2).queue("payload"), names=("str",))
        _refuses(s.WindowError, "a negative count",
                 lambda: s.Sender(1, 2).next_segments(-1), names=("-1",))

    import stage_05
    import stage_06 as s

    assert s.MSS == 8, (
        "one segment carries eight bytes, on purpose: %r" % (s.MSS,))
    assert issubclass(s.WindowError, ValueError), (
        "a refusal here is a ValueError: %r" % (s.WindowError,))

    _receiver_cases(s)
    _sender_cases(s, stage_05)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "tcp-ip-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

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
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _only_one(answer, name):
        """`answer` is a call's answer, with exactly one of value and errno set."""
        assert answer["name"] == name, (
            "the answer names the call it answers: %r" % (answer,))
        assert (answer["value"] is None) != (answer["errno"] is None), (
            "exactly one of value and errno is None: %r" % (answer,))
        return answer

    def _verbose(wire):
        """Let one tick pass, so a frame a call sent is now in a mailbox."""
        wire.advance(1)

    def _fresh(s, Host, NAMES, mac_of, Wire):
        """A socket table on a host of its own, ready to be poked at."""
        wire = Wire()
        host = Host("client", NAMES["client"], mac_of("client"), wire)
        return wire, host, s.Sockets(host)

    def _desk_cases(s, Host, MACS, NAMES, mac_of, Wire, stage_05):
        """The descriptors, the log, and the calls that can never be answered."""
        wire, host, table = _fresh(s, Host, NAMES, mac_of, Wire)
        assert table.fds() == (), (
            "a fresh table has no descriptors: %r" % (table.fds(),))
        assert table.log() == (), (
            "and has answered nothing: %r" % (table.log(),))

        first = _only_one(table.call("socket"), "socket")
        assert first == {"name": "socket", "value": 3, "errno": None}, (
            "the first descriptor is three: %r" % (first,))
        second = table.call("socket")
        assert second["value"] == 4, (
            "and the next is four: %r" % (second,))
        assert table.fds() == (3, 4), (
            "the live descriptors, ascending: %r" % (table.fds(),))
        assert "live" not in table.state(3), (
            "a socket with no connection has no handshake to report: %r"
            % (table.state(3),))

        _only_one(table.call("close", 4), "close")
        assert table.fds() == (3,), (
            "a closed descriptor is gone: %r" % (table.fds(),))
        assert table.call("socket")["value"] == 4, (
            "and the number is free to be handed out again: %r"
            % (table.call("socket"),))

        # ---- the calls that cannot be answered -------------------------------

        assert table.call("listen", 99)["errno"] == "EBADF", (
            "a descriptor that is not open is EBADF: %r"
            % (table.call("listen", 99),))
        assert table.call("close", 99)["errno"] == "EBADF", (
            "and closing one that is not open is EBADF too: %r"
            % (table.call("close", 99),))
        assert table.call("listen", 3, 3)["errno"] == "EINVAL", (
            "the wrong arity is EINVAL, and the call is one that exists: %r"
            % (table.call("listen", 3, 3),))
        assert table.call("syscall", 1)["errno"] == "ENOSYS", (
            "a name that is not a call is ENOSYS: %r"
            % (table.call("syscall", 1),))
        assert table.call("send")["errno"] == "EINVAL", (
            "and a known call with the wrong arity is still EINVAL, not ENOSYS: %r"
            % (table.call("send"),))

        refused = table.call("syscall", 1)
        assert table.log()[-1] == {"name": "syscall", "args": (1,), "value": None,
                                   "errno": "ENOSYS"}, (
            "a refused call is in the log: %r" % (table.log()[-1],))
        assert table.log()[-2]["errno"] == "EINVAL", (
            "and so is every other one: %r" % (table.log()[-2],))
        assert any(row["errno"] == "EBADF" for row in table.log()), (
            "the EBADF is in the log too: %r" % (table.log(),))

        # ---- bind, listen and the port it holds -------------------------------

        assert table.call("listen", 3)["errno"] == "EINVAL", (
            "a socket that is not bound cannot listen: %r"
            % (table.call("listen", 3),))
        _only_one(table.call("bind", 3, 80), "bind")
        _only_one(table.call("listen", 3), "listen")
        assert table.state(3) == "listen", (
            "a listening socket reports it: %r" % (table.state(3),))
        assert table.call("accept", 3)["errno"] == "EAGAIN", (
            "accept with nobody waiting is EAGAIN: %r" % (table.call("accept", 3),))
        assert table.call("connect", 3, (NAMES["web"], 80))["errno"] == "EISCONN", (
            "connect on a listening socket is EISCONN, not a handshake: %r"
            % (table.call("connect", 3, (NAMES["web"], 80)),))
        assert table.state(3) == "listen", (
            "and the listening socket is still listening: %r" % (table.state(3),))

        other = table.call("socket")["value"]
        assert table.call("bind", other, 80)["errno"] == "EADDRINUSE", (
            "a port that is taken is EADDRINUSE: %r"
            % (table.call("bind", other, 80),))
        _only_one(table.call("close", 3), "close")
        rebound = _only_one(table.call("bind", other, 80), "bind")
        assert rebound["errno"] is None, (
            "closing the listener freed its port for the next bind: %r" % (rebound,))
        assert table.state(other) == "closed", (
            "closing the listener freed its port for the next bind: %r"
            % (table.state(other),))

        assert table.call("send", other, b"x")["errno"] == "ENOTCONN", (
            "send on a socket that is not established is ENOTCONN: %r"
            % (table.call("send", other, b"x"),))
        assert table.call("accept", other)["errno"] == "EINVAL", (
            "accept on a socket that is not listening is EINVAL: %r"
            % (table.call("accept", other),))
        assert table.call("recv", other)["errno"] == "ENOTCONN", (
            "and so is recv: %r" % (table.call("recv", other),))

        # ---- the caller's own mistakes raise ---------------------------------

        _refuses(s.SocketError, "a call name that is not a string",
                 lambda: table.call(7), names=("7",))
        _refuses(s.SocketError, "a descriptor that is not an int",
                 lambda: table.call("close", "3"), names=("'3'",))
        _refuses(s.SocketError, "a state asked of a descriptor that is not an int",
                 lambda: table.state(None), names=("None",))
        _refuses(s.SocketError, "a state asked of a descriptor that does not exist",
                 lambda: table.state(99), names=("99",))

    def _table_cases(s, Host, NAMES, mac_of, Wire):
        """Two socket tables and a wire: the handshake and the stream over it."""
        wire = Wire()
        web = Host("web", NAMES["web"], mac_of("web"), wire)
        client = Host("client", NAMES["client"], mac_of("client"), wire)
        server = s.Sockets(web)
        peer = s.Sockets(client)

        _only_one(server.call("socket"), "socket")
        _only_one(peer.call("socket"), "socket")
        _only_one(server.call("bind", 3, 80), "bind")
        _only_one(server.call("listen", 3), "listen")

        assert peer.call("connect", 3, (NAMES["web"], 80))["value"] == 0, (
            "a connect answers zero and puts a SYN on the wire: %r"
            % (peer.call("connect", 3, (NAMES["web"], 80)),))
        _verbose(wire)
        assert server.call("accept", 3)["errno"] == "EAGAIN", (
            "a handshake half done is not a connection to accept: %r"
            % (server.call("accept", 3),))
        _verbose(wire)
        assert peer.call("recv", 3)["errno"] == "EAGAIN", (
            "the peer's own recv drives its half to established, with nothing yet: %r"
            % (peer.call("recv", 3),))
        assert peer.state(3) == "established", (
            "the client is established: %r" % (peer.state(3),))
        _verbose(wire)
        taken = _only_one(server.call("accept", 3), "accept")
        assert taken["value"] == 4, (
            "a completed handshake is accepted as a new descriptor: %r" % (taken,))
        assert server.state(4) == "established", (
            "and it is established: %r" % (server.state(4),))
        assert server.state(3) == "listen", (
            "while the listener is still listening: %r" % (server.state(3),))
        assert server.fds() == (3, 4), (
            "both descriptors are live, ascending: %r" % (server.fds(),))

        moved = _only_one(server.call("send", 4, b"hello"), "send")
        assert moved["value"] == 5, (
            "a send of five bytes puts five bytes in flight: %r" % (moved,))
        assert peer.call("recv", 3)["errno"] == "EAGAIN", (
            "before the wire carries them, there is nothing to read: %r"
            % (peer.call("recv", 3),))
        _verbose(wire)
        got = _only_one(peer.call("recv", 3), "recv")
        assert got["value"] == b"hello", (
            "and once it does, the bytes arrive in order: %r" % (got,))
        assert peer.call("recv", 3)["errno"] == "EAGAIN", (
            "a second recv with nothing new is EAGAIN, not an empty read: %r"
            % (peer.call("recv", 3),))

        # ---- the window is the one decided in stage 6 -------------------------

        _verbose(wire)
        wide = _only_one(server.call("send", 4, b"0123456789ab"), "send")
        assert wide["value"] == 8, (
            "a send of twelve bytes asks the window, and the window of one segment "
            "lets eight out: %r" % (wide,))
        _verbose(wire)
        read = _only_one(peer.call("recv", 3), "recv")
        assert read["value"] == b"01234567", (
            "and exactly those eight arrive: %r" % (read,))

        # ---- a peer that resets ends the stream -------------------------------

        reset = {"src_port": 80, "dst_port": 40000, "seq": 0, "ack": 0,
                 "flags": 4, "window": 0, "payload": b""}
        web.send(client.mac, _pack(reset, web.ip, client.ip))
        _verbose(wire)
        ended = _only_one(peer.call("recv", 3), "recv")
        assert ended["value"] == b"", (
            "a stream that ended reads as empty bytes, not EAGAIN: %r" % (ended,))
        assert peer.state(3) == "closed", (
            "and the socket behind it reports closed: %r" % (peer.state(3),))

        # ---- a peer that refuses ---------------------------------------------

        angry = Wire()
        angry_web = Host("web", NAMES["web"], mac_of("web"), angry)
        angry_client = Host("client", NAMES["client"], mac_of("client"), angry)
        table = s.Sockets(angry_client)
        _only_one(table.call("socket"), "socket")
        rst = {"src_port": 80, "dst_port": 40000, "seq": 0, "ack": 0,
               "flags": 4, "window": 0, "payload": b""}
        angry_web.send(angry_client.mac, _pack(rst, angry_web.ip, angry_client.ip))
        _verbose(angry)
        refused = _only_one(table.call("connect", 3, (NAMES["web"], 80)), "connect")
        assert refused["errno"] == "ECONNREFUSED", (
            "a peer that resets the handshake refuses the connection: %r" % (refused,))
        assert table.state(3) == "closed", (
            "and the socket is closed: %r" % (table.state(3),))

        # a connect twice is EISCONN
        doubled = Wire()
        host = Host("client", NAMES["client"], mac_of("client"), doubled)
        once = s.Sockets(host)
        _only_one(once.call("socket"), "socket")
        _only_one(once.call("connect", 3, (NAMES["web"], 80)), "connect")
        assert once.call("connect", 3, (NAMES["web"], 80))["errno"] == "EISCONN", (
            "a second connect on a socket that already is is EISCONN: %r"
            % (once.call("connect", 3, (NAMES["web"], 80)),))

    def _pack(segment, src, dst):
        import stage_05
        return stage_05.pack(segment, src, dst)

    import stage_05
    import stage_07 as s
    from hosts import Host, MACS, NAMES, mac_of
    from wire import Wire

    assert s.CALLS == (("socket", 0), ("bind", 2), ("listen", 1), ("accept", 1),
                       ("connect", 2), ("send", 2), ("recv", 1), ("close", 1)), (
        "the frozen table, in the frozen order: %r" % (s.CALLS,))
    assert s.ERRNOS == ("EBADF", "EINVAL", "ENOSYS", "EAGAIN", "ECONNREFUSED",
                        "ENOTCONN", "EADDRINUSE", "EISCONN"), (
        "the closed errno vocabulary: %r" % (s.ERRNOS,))
    assert issubclass(s.SocketError, ValueError), (
        "a refusal here is a ValueError: %r" % (s.SocketError,))

    for index, (name, count) in enumerate(s.CALLS, start=1):
        assert s.arity(name) == count, (
            "the table's arity for %r is %d: %r" % (name, count, s.arity(name)))
        assert s.call_name(index) == name, (
            "call %d is %r: %r" % (index, name, s.call_name(index)))
    _refuses(s.SocketError, "the arity of a name that is not a call",
             lambda: s.arity("syscall"), names=("syscall",))
    _refuses(s.SocketError, "the name of a number that is not a call",
             lambda: s.call_name(0), names=("0",))
    _refuses(s.SocketError, "a number above the last call",
             lambda: s.call_name(9), names=("9",))

    _desk_cases(s, Host, MACS, NAMES, mac_of, Wire, stage_05)
    _table_cases(s, Host, NAMES, mac_of, Wire)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "tcp-ip-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

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
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    class _Peer:
        """The thing a `Reliable` transmits through: it keeps what it was given."""

        def __init__(self):
            self.sent = []

        def send(self, segment):
            self.sent.append(segment)

    def _ack(ack, seq=0, src_port=80, dst_port=40000):
        """A bare acknowledgement from the peer to a sender on 40000."""
        return {"src_port": src_port, "dst_port": dst_port, "seq": seq, "ack": ack,
                "flags": 16, "window": 8, "payload": b""}

    def _timer_cases(s, stage_05):
        """The one timer: the doubling, the cap, the tries and the acknowledgement."""
        timer = s.Timer()
        assert timer.due(0) is None, (
            "a fresh timer is not armed, so it fires at no tick: %r" % (timer.due(0),))
        assert timer.log() == (), (
            "and has seen nothing: %r" % (timer.log(),))

        armed = timer.start(100, 0)
        assert tuple(armed) == ("seq", "due", "timeout"), (
            "arming the timer is three facts in the contract's order: %r"
            % (tuple(armed),))
        assert armed == {"seq": 100, "due": 2, "timeout": 2}, (
            "the first deadline is the initial timeout after now: %r" % (armed,))
        assert timer.due(0) == 2, (
            "and the timer fires at that tick: %r" % (timer.due(0),))

        first = timer.fired(2)
        assert first == {"seq": 100, "tries": 1, "timeout": 4}, (
            "the first retransmission doubles the wait: %r" % (first,))
        assert timer.due(2) == 6, (
            "and the next deadline is now plus the new wait, not plus the old one: %r"
            % (timer.due(2),))
        second = timer.fired(6)
        assert second == {"seq": 100, "tries": 2, "timeout": 8}, (
            "the second doubles again: %r" % (second,))
        third = timer.fired(14)
        assert third == {"seq": 100, "tries": 3, "timeout": 16}, (
            "the third doubles to the cap: %r" % (third,))
        fourth = timer.fired(30)
        assert fourth == {"seq": 100, "tries": 4, "timeout": 16}, (
            "and the fourth is capped, not doubled past the cap: %r" % (fourth,))
        assert timer.due(30) == 46, (
            "so the fourth deadline is thirty plus sixteen: %r" % (timer.due(30),))
        assert timer.fired(46) == {"expired": True}, (
            "the fifth firing is one try too many, and it expires rather than "
            "raising: %r" % (timer.fired(46),))
        assert timer.due(46) is None, (
            "an expired timer is no longer armed: %r" % (timer.due(46),))
        assert timer.log() == (
            {"event": "start", "seq": 100, "due": 2, "timeout": 2},
            {"event": "fire", "seq": 100, "tries": 1, "timeout": 4, "due": 6},
            {"event": "fire", "seq": 100, "tries": 2, "timeout": 8, "due": 14},
            {"event": "fire", "seq": 100, "tries": 3, "timeout": 16, "due": 30},
            {"event": "fire", "seq": 100, "tries": 4, "timeout": 16, "due": 46},
            {"event": "expire", "seq": 100, "tries": 4}), (
            "every event this timer saw, in order: %r" % (timer.log(),))
        _refuses(s.RetransmitError, "a start after the timer gave up",
                 lambda: timer.start(200, 46), names=("given up",))

        # ---- the acknowledgement that stops it -------------------------------

        covered = s.Timer()
        covered.start(50, 0)
        stopped = covered.acknowledged(51, 1)
        assert tuple(stopped) == ("stopped", "again"), (
            "an acknowledgement is two facts in the contract's order: %r"
            % (tuple(stopped),))
        assert stopped == {"stopped": True, "again": False}, (
            "an acknowledgement past the armed segment stops the timer: %r"
            % (stopped,))
        assert covered.due(1) is None, (
            "and the timer is no longer armed: %r" % (covered.due(1),))
        assert covered.acknowledged(51, 2) == {"stopped": False, "again": True}, (
            "a further acknowledgement stops nothing that is already stopped: %r"
            % (covered.acknowledged(51, 2),))

        behind = s.Timer()
        behind.start(50, 0)
        assert behind.acknowledged(49, 1) == {"stopped": False, "again": True}, (
            "an acknowledgement behind the armed segment moves nothing: %r"
            % (behind.acknowledged(49, 1),))
        assert behind.acknowledged(50, 1) == {"stopped": False, "again": True}, (
            "and an acknowledgement of the segment's own first number covers none "
            "of it: %r" % (behind.acknowledged(50, 1),))
        assert behind.due(1) == 2, (
            "so the timer stays armed for the very same tick: %r"
            % (behind.due(1),))
        assert behind.acknowledged(51, 1) == {"stopped": True, "again": False}, (
            "the acknowledgement past its first byte is what covers it: %r"
            % (behind.acknowledged(51, 1),))
        assert behind.log() == (
            {"event": "start", "seq": 50, "due": 2, "timeout": 2},
            {"event": "ack", "ack": 49, "stopped": False},
            {"event": "ack", "ack": 50, "stopped": False},
            {"event": "ack", "ack": 51, "stopped": True}), (
            "every acknowledgement the timer judged, in order, with its verdict: %r"
            % (behind.log(),))

        wrapped = s.Timer()
        wrapped.start(stage_05.SEQ_MAX - 1, 0)
        assert wrapped.acknowledged(2, 1) == {"stopped": True, "again": False}, (
            "an acknowledgement ahead of the armed segment across the wrap stops "
            "it: %r" % (wrapped.acknowledged(2, 1),))

        idle = s.Timer()
        assert idle.fired(0) == {"expired": True}, (
            "a timer that was never armed has nothing to send again: %r"
            % (idle.fired(0),))
        assert idle.acknowledged(0, 0) == {"stopped": False, "again": True}, (
            "and an acknowledgement against nothing is no progress: %r"
            % (idle.acknowledged(0, 0),))

        # ---- the refusals -----------------------------------------------------

        _refuses(s.RetransmitError, "a timeout below one",
                 lambda: s.Timer(timeout=0), names=("0",))
        _refuses(s.RetransmitError, "a backoff below one",
                 lambda: s.Timer(backoff=0), names=("0",))
        _refuses(s.RetransmitError, "a tries below one",
                 lambda: s.Timer(tries=0), names=("0",))
        _refuses(s.RetransmitError, "a timeout that is not an int",
                 lambda: s.Timer(timeout="2"), names=("'2'",))
        armed2 = s.Timer()
        armed2.start(1, 0)
        _refuses(s.RetransmitError, "a second start while armed",
                 lambda: armed2.start(2, 0), names=("armed",))
        _refuses(s.RetransmitError, "a negative now",
                 lambda: s.Timer().start(1, -1), names=("-1",))

    def _reliable_cases(s, stage_06):
        """The sender and its one timer, moved by acknowledgements and ticks."""
        sender = stage_06.Sender(40000, 80, iss=0, window=stage_06.MSS)
        peer = _Peer()
        timer = s.Timer()
        reliable = s.Reliable(sender, timer, peer)
        assert reliable.give_up(0) is False, (
            "a fresh connection has not given up: %r" % (reliable.give_up(0),))

        opened = reliable.send(b"abcdefghijkl", 0)
        assert tuple(opened) == ("segments", "sent", "due"), (
            "a send is three facts in the contract's order: %r" % (tuple(opened),))
        assert opened == {"segments": 2, "sent": 1, "due": 2}, (
            "twelve bytes are two segments, a window of one lets one out, and the "
            "timer is armed for it: %r" % (opened,))
        assert len(peer.sent) == 1 and peer.sent[0]["payload"] == b"abcdefgh", (
            "and the segment that went out is the first one: %r" % (peer.sent,))

        idle = reliable.tick(1)
        assert tuple(idle) == ("resent", "expired", "due"), (
            "a tick is three facts in the contract's order: %r" % (tuple(idle),))
        assert idle == {"resent": 0, "expired": False, "due": 2}, (
            "a tick before the deadline resent nothing and the timer is still set: %r"
            % (idle,))

        got = reliable.received(_ack(8), 2)
        assert got == {"acked": 8, "event": "ack"}, (
            "an acknowledgement of the first segment moves eight bytes: %r" % (got,))
        assert timer.due(2) is None, (
            "and stops the timer, because it covered the segment it was armed "
            "for: %r" % (timer.due(2),))

        after = reliable.tick(2)
        assert len(peer.sent) == 2, (
            "the tick that finds the window open puts the next segment out: %r"
            % (peer.sent,))
        assert peer.sent[1]["payload"] == b"ijkl", (
            "and it is the segment behind the acknowledged one: %r" % (peer.sent[1],))
        assert after["due"] == 4, (
            "the timer is armed for the new oldest segment: %r" % (after["due"],))

        fired = reliable.tick(4)
        assert fired == {"resent": 1, "expired": False, "due": 8}, (
            "at its deadline a tick retransmits that segment and backs off: %r"
            % (fired,))
        assert len(peer.sent) == 3 and peer.sent[2]["payload"] == b"ijkl", (
            "and the segment sent again is the oldest unacknowledged one, not the "
            "newest: %r" % (peer.sent,))
        assert reliable.give_up(4) is False, (
            "one retransmission is not giving up: %r" % (reliable.give_up(4),))

        duplicate = reliable.received(_ack(8), 5)
        assert duplicate == {"acked": 0, "event": "again"}, (
            "a duplicate acknowledgement moves nothing: %r" % (duplicate,))
        assert timer.due(5) == 8, (
            "and does not reset the timer, which stays armed for the same tick: %r"
            % (timer.due(5),))

        last = reliable.received(_ack(12), 5)
        assert last == {"acked": 4, "event": "ack"}, (
            "the acknowledgement that covers the last bytes moves the rest: %r"
            % (last,))
        assert reliable.log() == (
            {"event": "send", "segments": 1, "due": 2},
            {"event": "tick", "resent": 0, "expired": False},
            {"event": "ack", "acked": 8},
            {"event": "tick", "resent": 0, "expired": False},
            {"event": "tick", "resent": 1, "expired": False},
            {"event": "again", "acked": 0},
            {"event": "ack", "acked": 4}), (
            "every decision this connection made, in order: %r" % (reliable.log(),))
        assert s.Reliable(sender, s.Timer(), _Peer()).log() == (), (
            "a fresh reliable connection has decided nothing: %r"
            % (s.Reliable(sender, s.Timer(), _Peer()).log(),))

        crowded = s.Reliable(stage_06.Sender(40000, 80, iss=0, window=24),
                             s.Timer(), _Peer())
        bulk = crowded.send(b"0123456789abcdefghij", 0)
        assert bulk["segments"] == 3 and bulk["sent"] == 3, (
            "a window of three segments lets three out: %r" % (bulk,))

        peer2 = _Peer()
        wide = s.Reliable(stage_06.Sender(40000, 80, iss=0, window=24),
                          s.Timer(), peer2)
        wide.send(b"a" * 20, 0)
        assert [segment["seq"] for segment in peer2.sent] == [0, 8, 16], (
            "three segments out of a window of three, oldest first: %r"
            % ([segment["seq"] for segment in peer2.sent],))
        fired_again = wide.tick(2)
        assert fired_again["resent"] == 1, (
            "and the deadline retransmits one of them: %r" % (fired_again,))
        assert [segment["seq"] for segment in peer2.sent] == [0, 8, 16, 0], (
            "the one it sends again is the oldest unacknowledged segment, not the "
            "newest: %r" % ([segment["seq"] for segment in peer2.sent],))

        _refuses(s.RetransmitError, "a received for another connection's segment",
                 lambda: s.Reliable(stage_06.Sender(40000, 80), s.Timer(),
                                    _Peer()).received(_ack(1, dst_port=9999), 0),
                 names=("9999",))

    def _run_cases(s, Host, NAMES, mac_of, Wire):
        """`run` on a clean wire, on a wire that drops one, and on one that drops all."""
        clean = Wire()
        client = Host("client", NAMES["client"], mac_of("client"), clean)
        report = s.run(clean, client, mac_of("web"), NAMES["web"], b"abcdefghijkl")
        assert tuple(report) == ("sent", "resent", "acked", "ticks", "delivered",
                                 "dropped", "expired"), (
            "a run reports seven facts in the contract's order: %r"
            % (tuple(report),))
        assert report["acked"] == 12, (
            "on a clean wire the whole payload is acknowledged: %r" % (report,))
        assert report["resent"] == 0, (
            "and nothing is ever retransmitted: %r" % (report,))
        assert report["dropped"] == 0, (
            "because the wire dropped nothing: %r" % (report,))
        assert report["delivered"] > 0, (
            "and it delivered the frames it carried: %r" % (report,))
        assert report["expired"] is False, (
            "so the connection never gave up: %r" % (report,))

        lossy = Wire({"loss": [3]})
        client = Host("client", NAMES["client"], mac_of("client"), lossy)
        hurt = s.run(lossy, client, mac_of("web"), NAMES["web"], b"abcdefghijkl")
        assert hurt["dropped"] == 1, (
            "the extra wire dropped exactly the one frame it was told to: %r"
            % (hurt,))
        assert hurt["resent"] == 1, (
            "and the retransmission is the only reason the payload arrives: %r"
            % (hurt,))
        assert hurt["acked"] == 12, (
            "because the whole payload is acknowledged in the end: %r" % (hurt,))
        assert hurt["expired"] is False, (
            "one loss is not a give-up: %r" % (hurt,))

        dead = Wire({"loss": list(range(1, 40))})
        client = Host("client", NAMES["client"], mac_of("client"), dead)
        doomed = s.run(dead, client, mac_of("web"), NAMES["web"], b"abcdefghijkl")
        assert doomed["dropped"] == doomed["sent"] + doomed["resent"], (
            "when every frame is dropped, the wire's drop count is every send: %r"
            % (doomed,))
        assert doomed["delivered"] == 0, (
            "and nothing arrives at all: %r" % (doomed,))
        assert doomed["resent"] == s.MAX_TRIES, (
            "the retransmissions equal the tries before the connection gives up: %r"
            % (doomed,))
        assert doomed["expired"] is True, (
            "and the give-up is reported, not raised: %r" % (doomed,))
        assert doomed["acked"] == 0, (
            "with nothing acknowledged: %r" % (doomed,))

    import stage_05
    import stage_06
    import stage_08 as s
    from hosts import Host, NAMES, mac_of
    from wire import Wire

    assert s.INITIAL_TIMEOUT == 2, (
        "the first wait is two ticks: %r" % (s.INITIAL_TIMEOUT,))
    assert s.MAX_TIMEOUT == 16, (
        "the wait stops doubling at sixteen ticks: %r" % (s.MAX_TIMEOUT,))
    assert s.MAX_TRIES == 4, (
        "a connection retransmits four times before giving up: %r"
        % (s.MAX_TRIES,))
    assert s.BACKOFF == 2, (
        "each wait is twice the one before it: %r" % (s.BACKOFF,))
    assert issubclass(s.RetransmitError, ValueError), (
        "a refusal here is a ValueError: %r" % (s.RetransmitError,))

    _timer_cases(s, stage_05)
    _reliable_cases(s, stage_06)
    _run_cases(s, Host, NAMES, mac_of, Wire)

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "tcp-ip-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

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
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    CLIENT_IP = "10.0.0.5"

    SERVER_IP = "10.0.0.2"

    def _to_client(flags, seq, ack, payload=b"", src_port=80, dst_port=40000):
        """A segment arriving at the client's connection, sent from the server's port."""
        return {"src_port": src_port, "dst_port": dst_port, "seq": seq, "ack": ack,
                "flags": flags, "window": 65535, "payload": payload}

    def _to_server(flags, seq, ack, payload=b"", src_port=40000, dst_port=80):
        """A segment arriving at the server's connection, sent from the client's port."""
        return {"src_port": src_port, "dst_port": dst_port, "seq": seq, "ack": ack,
                "flags": flags, "window": 65535, "payload": payload}

    def _wire_cases(s, stage_01, stage_05, Wire, Host, mac_of):
        """A whole close across a real link: five frames, one of them lost."""
        client_mac, server_mac = mac_of("client"), mac_of("web")
        wire = Wire(rules={"loss": (1,)})
        client_host = Host("client", CLIENT_IP, client_mac, wire)
        server_host = Host("web", SERVER_IP, server_mac, wire)
        client_end = stage_05.Connection(40000, CLIENT_IP, remote=(SERVER_IP, 80),
                                         state="established", seed=3)
        server_end = stage_05.Connection(80, SERVER_IP, remote=(CLIENT_IP, 40000),
                                         state="established", seed=7)
        client_iss = stage_05.initial_seq(3)

        def frame_of(from_mac, to_mac, segment, from_ip, to_ip):
            return stage_01.build(to_mac, from_mac, "ipv4",
                                  stage_05.pack(segment, from_ip, to_ip), pad=False)

        def cross(from_host, to_host, to_mac, segment, from_ip, to_ip):
            frame = frame_of(from_host.mac, to_mac, segment, from_ip, to_ip)
            from_host.send(to_mac, frame)
            wire.advance(1)
            arrived = to_host.recv()
            assert len(arrived) == 1, (
                "one frame sent is one frame in the other host's box: %r" % (arrived,))
            envelope = stage_01.parse(arrived[0])
            back = stage_05.unpack(envelope["payload"], from_ip, to_ip)
            assert back["checksum_ok"] is True, (
                "the segment that crossed the wire is the segment the checksum was "
                "computed for: %r" % (back,))
            return back

        # the first FIN is lost, so the same frame goes out twice
        fin = s.close(client_end, 0)["segment"]
        lost = frame_of(client_host.mac, server_mac, fin, CLIENT_IP, SERVER_IP)
        client_host.send(server_mac, lost)
        wire.advance(1)
        assert server_host.recv() == [], (
            "the link dropped the first FIN and the listener's box is empty: %r"
            % (server_host.inbox(),))
        assert wire.dropped() == 1 and wire.sent() == 1, (
            "and the wire's own log is where that is visible: %r dropped of %r sent"
            % (wire.dropped(), wire.sent()))
        assert [event["ordinal"] for event in wire.events("drop")] == [1], (
            "the first frame is the one that never arrived: %r"
            % (wire.events("drop"),))
        client_host.send(server_mac, lost)
        wire.advance(1)
        arrived = server_host.recv()
        assert len(arrived) == 1, (
            "the second send is the one that arrives: %r" % (arrived,))
        heard = stage_05.unpack(stage_01.parse(arrived[0])["payload"],
                                CLIENT_IP, SERVER_IP)
        assert heard["flags"] == stage_05.FIN, (
            "what arrives the second time is the FIN that was sent: %r"
            % (heard["flags"],))
        assert heard["seq"] == stage_05.seq_add(client_iss, 1), (
            "with the sequence number the close chose: %r" % (heard["seq"],))

        told = s.step_close(server_end, heard, wire.tick())
        assert told["state"] == "close_wait", (
            "and the told side decides from what arrived: %r" % (told,))
        back = cross(server_host, client_host, client_mac, told["segment"],
                     SERVER_IP, CLIENT_IP)
        assert back["flags"] == stage_05.ACK, (
            "a close_wait answers with an acknowledgement: %r" % (back,))
        assert back["ack"] == stage_05.seq_add(heard["seq"], 1), (
            "counting the FIN as one number: %r" % (back["ack"],))
        settled = s.step_close(client_end, back, wire.tick())
        assert settled == {"state": "fin_wait_2", "segment": None,
                           "event": "fin_wait_2"}, (
            "and the far end is half-open: %r" % (settled,))
        assert s.half_open(client_end) and s.half_open(server_end), (
            "both ends are half-open, one in each direction: %r and %r"
            % (s.half_open(client_end), s.half_open(server_end)))

        last = s.close(server_end, wire.tick())
        assert last["state"] == "last_ack", (
            "the told side's own FIN puts it in last_ack: %r" % (last,))
        crossed = s.step_close(client_end, cross(server_host, client_host, client_mac,
                                                 last["segment"], SERVER_IP, CLIENT_IP),
                               wire.tick())
        assert crossed["state"] == "time_wait", (
            "the FIN moves the far end to time_wait: %r" % (crossed,))
        assert s.time_wait_over(client_end, wire.tick()) is False, (
            "where the wait has only just begun: %r"
            % (s.time_wait_over(client_end, wire.tick()),))
        ended = s.step_close(server_end, cross(client_host, server_host, server_mac,
                                               crossed["segment"], CLIENT_IP,
                                               SERVER_IP), wire.tick())
        assert ended == {"state": "closed", "segment": None, "event": "closed"}, (
            "and the last acknowledgement ends the told side: %r" % (ended,))
        assert client_end.state() == "time_wait" and server_end.state() == "closed", (
            "one side waits and the other is done: %r and %r"
            % (client_end.state(), server_end.state()))

        # ---- the wire's own record of the close -------------------------------

        assert wire.sent() == 5 and wire.delivered() == 4 and wire.dropped() == 1, (
            "five frames sent, one dropped, four delivered: %r, %r and %r"
            % (wire.sent(), wire.delivered(), wire.dropped()))
        sends = wire.events("send")
        assert sends[0]["data"] == sends[1]["data"] == lost, (
            "the FIN that was lost and the one that arrived are the same bytes: %r"
            % (sends,))
        assert sends[0]["src"] == client_mac and sends[0]["dst"] == server_mac, (
            "and it was addressed from the client to the server: %r" % (sends[0],))
        assert [event["ordinal"] for event in wire.deliver()] == [5], (
            "the last frame the link handed over is the fifth send: %r"
            % (wire.deliver(),))
        assert len(server_host.inbox()) == 2 and len(client_host.inbox()) == 2, (
            "two frames reached each box, the lost one reaching neither: %r and %r"
            % (server_host.inbox(), client_host.inbox()))

    import stage_01
    import stage_05
    import stage_09 as s
    from hosts import Host, mac_of
    from wire import Wire

    # ---- the constants ----------------------------------------------------

    assert s.TIME_WAIT_TICKS == 8, (
        "a connection waits eight ticks in time_wait: %r" % (s.TIME_WAIT_TICKS,))
    assert s.CLOSE_STATES == ("fin_wait_1", "fin_wait_2", "closing", "time_wait",
                             "close_wait", "last_ack", "closed"), (
        "the seven states of a close, in the ladder's own order: %r"
        % (s.CLOSE_STATES,))
    assert issubclass(s.CloseError, ValueError), (
        "a refusal here is a ValueError: %r" % (s.CloseError,))

    # ---- the active close, from the FIN to time_wait ----------------------

    client = stage_05.Connection(40000, CLIENT_IP, remote=(SERVER_IP, 80),
                                 state="established", seed=3)
    client_iss = stage_05.initial_seq(3)
    opened = s.close(client, 0)
    assert tuple(opened) == ("state", "segment", "event"), (
        "a close answers the same three facts a step answers: %r"
        % (tuple(opened),))
    assert opened["state"] == "fin_wait_1" and opened["event"] == "fin_wait_1", (
        "close sends the FIN and moves to fin_wait_1: %r" % (opened,))
    assert client.state() == "fin_wait_1", (
        "the connection is where the close put it: %r" % (client.state(),))
    fin = opened["segment"]
    assert stage_05.flags_text(fin["flags"]) == "FIN", (
        "the segment close hands back is the FIN: %r" % (fin,))
    assert fin["src_port"] == 40000 and fin["dst_port"] == 80, (
        "and it is addressed from this connection's port to its peer's: %r"
        % (fin,))
    assert fin["seq"] == stage_05.seq_add(client_iss, 1), (
        "its own sequence number is this side's next, the SYN's plus one: %r"
        % (fin["seq"],))
    assert fin["ack"] == 0, (
        "a FIN carries no acknowledgement of its own: %r" % (fin["ack"],))
    assert fin["window"] == stage_05.WINDOW_MAX, (
        "the window is the window, not the payload's length: %r"
        % (fin["window"],))
    assert fin["payload"] == b"", (
        "a FIN carries nothing: %r" % (fin["payload"],))
    fin_seq = fin["seq"]

    settled = s.step_close(client, _to_client(stage_05.ACK, 5001,
                                              stage_05.seq_add(fin_seq, 1)), 1)
    assert tuple(settled) == ("state", "segment", "event"), (
        "and so does a step: %r" % (tuple(settled),))
    assert settled == {"state": "fin_wait_2", "segment": None,
                       "event": "fin_wait_2"}, (
        "the peer's acknowledgement of our FIN moves to fin_wait_2, silently: %r"
        % (settled,))
    assert client.state() == "fin_wait_2", (
        "and the connection moved: %r" % (client.state(),))
    assert s.half_open(client) is True, (
        "one direction is closed and the other is not, so the connection is "
        "half-open: %r" % (s.half_open(client),))

    # in fin_wait_2 the peer's data is still the peer's stream
    stream = s.step_close(client, _to_client(stage_05.ACK, 5001,
                                             stage_05.seq_add(fin_seq, 1),
                                             b"half"), 2)
    assert stream["state"] == "fin_wait_2" and stream["event"] == "data", (
        "a payload in fin_wait_2 is still taken, and leaves the state alone: %r"
        % (stream,))
    assert client.state() == "fin_wait_2", (
        "half-open is a state, not a transition: %r" % (client.state(),))
    assert stage_05.flags_text(stream["segment"]["flags"]) == "ACK", (
        "the data is acknowledged: %r" % (stream["segment"],))
    assert stream["segment"]["ack"] == stage_05.seq_add(5001, 4) == 5005, (
        "with a number covering exactly the four bytes that arrived: %r"
        % (stream["segment"]["ack"],))
    assert stream["segment"]["payload"] == b"", (
        "an acknowledgement carries nothing back: %r"
        % (stream["segment"]["payload"],))

    over = s.step_close(client, _to_client(stage_05.FIN | stage_05.ACK, 5005,
                                           stage_05.seq_add(fin_seq, 1)), 3)
    assert over["state"] == "time_wait" and over["event"] == "time_wait", (
        "the peer's FIN moves fin_wait_2 to time_wait: %r" % (over,))
    assert client.state() == "time_wait", (
        "and the connection is waiting: %r" % (client.state(),))
    assert stage_05.flags_text(over["segment"]["flags"]) == "ACK", (
        "the FIN is acknowledged: %r" % (over["segment"],))
    assert over["segment"]["ack"] == 5006 == stage_05.seq_add(5005, 1), (
        "counting the FIN it answers as one sequence number: %r"
        % (over["segment"]["ack"],))
    assert s.half_open(client) is False, (
        "both directions are closed now, so nothing is half-open: %r"
        % (s.half_open(client),))

    # after the close is complete the connection takes nothing
    late = s.step_close(client, _to_client(stage_05.ACK, 5006,
                                           stage_05.seq_add(fin_seq, 1),
                                           b"late"), 4)
    assert late["event"] == "rejected", (
        "a payload arriving in time_wait is not taken: %r" % (late,))
    assert late["segment"] is None, (
        "and it is not acknowledged: %r" % (late["segment"],))
    assert late["state"] == "time_wait" and client.state() == "time_wait", (
        "a rejected segment never moves the connection: %r" % (client.state(),))

    # ---- the wait is a question about a tick ------------------------------

    assert s.time_wait_over(client, 3) is False, (
        "the wait begins when the state was entered, so its own tick is not "
        "over: %r" % (s.time_wait_over(client, 3),))
    assert s.time_wait_over(client, 10) is False, (
        "ten is three plus seven, and seven is less than TIME_WAIT_TICKS: %r"
        % (s.time_wait_over(client, 10),))
    assert s.time_wait_over(client, 11) is True, (
        "three plus eight is eight ticks after the state was entered: %r"
        % (s.time_wait_over(client, 11),))
    assert s.time_wait_over(client, 99) is True, (
        "and a tick long after it is over too: %r"
        % (s.time_wait_over(client, 99),))

    # a fresh SYN for the same pair, while the wait is on
    early = s.step_close(client, _to_client(stage_05.SYN, 9000, 0), 10)
    assert early["state"] == "time_wait" and early["event"] == "rejected", (
        "a fresh SYN while the state is still waiting is refused: %r" % (early,))
    assert stage_05.flags_text(early["segment"]["flags"]) == "RST", (
        "with a reset, because the peer has not learned about the close: %r"
        % (early["segment"],))
    assert early["segment"]["seq"] == stage_05.seq_add(client_iss, 1), (
        "a reset comes from this side's next sequence number: %r"
        % (early["segment"]["seq"],))
    assert client.state() == "time_wait", (
        "and the connection is still waiting: %r" % (client.state(),))

    # ... and the same SYN once the wait is over
    again = s.step_close(client, _to_client(stage_05.SYN, 9000, 0), 11)
    assert again["state"] == "syn_received" and again["event"] == "syn_received", (
        "a fresh SYN after the wait is accepted, and the pair goes back to the "
        "handshake: %r" % (again,))
    assert stage_05.flags_text(again["segment"]["flags"]) == "SYN,ACK", (
        "answered with this side's own SYN,ACK: %r" % (again["segment"],))
    assert again["segment"]["ack"] == 9001 == stage_05.seq_add(9000, 1), (
        "whose acknowledgement counts the SYN it answers: %r"
        % (again["segment"]["ack"],))
    assert again["segment"]["dst_port"] == 80, (
        "and goes back to the port the SYN came from: %r" % (again["segment"],))
    assert client.state() == "syn_received", (
        "the connection is out of the close and back in the handshake: %r"
        % (client.state(),))

    # ---- the log is the transitions themselves ----------------------------

    assert client.log() == (
        ("fin_wait_1", "fin_wait_1", "FIN", 0),
        ("fin_wait_2", "fin_wait_2", "", 1),
        ("fin_wait_2", "data", "ACK", 2),
        ("time_wait", "time_wait", "ACK", 3),
        ("time_wait", "rejected", "", 4),
        ("time_wait", "rejected", "RST", 10),
        ("syn_received", "syn_received", "SYN,ACK", 11)), (
        "the close's log is the transitions the way the handshake's is — the "
        "state moved to, the event, the reply's flags and the tick: %r"
        % (client.log(),))

    # ---- a payload after close is not taken -------------------------------

    fresh = stage_05.Connection(40000, CLIENT_IP, remote=(SERVER_IP, 80),
                                state="established", seed=3)
    s.close(fresh, 0)
    refused = s.step_close(fresh, _to_client(stage_05.ACK, 7000,
                                             stage_05.seq_add(client_iss, 1),
                                             b"more"), 1)
    assert refused["event"] == "rejected", (
        "close returns in fin_wait_1, and a payload arriving there is not "
        "taken: %r" % (refused,))
    assert refused["segment"] is None, (
        "nothing acknowledges it either: %r" % (refused["segment"],))
    assert refused["state"] == "fin_wait_1" and fresh.state() == "fin_wait_1", (
        "the state the close put the connection in is the state it stays in: %r"
        % (fresh.state(),))
    assert s.half_open(fresh) is False, (
        "and a connection whose FIN nobody has acknowledged is not half-open: %r"
        % (s.half_open(fresh),))

    # ---- the passive close ------------------------------------------------

    server = stage_05.Connection(80, SERVER_IP, remote=(CLIENT_IP, 40000),
                                 state="established", seed=7)
    server_iss = stage_05.initial_seq(7)
    told = s.step_close(server, _to_server(stage_05.FIN | stage_05.ACK, 1001,
                                           stage_05.seq_add(server_iss, 1)), 0)
    assert told["state"] == "close_wait" and told["event"] == "close_wait", (
        "the peer's FIN in established moves the told side to close_wait: %r"
        % (told,))
    assert stage_05.flags_text(told["segment"]["flags"]) == "ACK", (
        "and it is acknowledged: %r" % (told["segment"],))
    assert told["segment"]["window"] == stage_05.WINDOW_MAX, (
        "an acknowledgement reports the window, not the payload's length: %r"
        % (told["segment"]["window"],))
    assert told["segment"]["ack"] == 1002 == stage_05.seq_add(1001, 1), (
        "counting the FIN as one sequence number: %r"
        % (told["segment"]["ack"],))
    assert told["segment"]["src_port"] == 80 and told["segment"]["dst_port"] == 40000, (
        "addressed from this side's port to the peer's: %r" % (told["segment"],))
    assert s.half_open(server) is True, (
        "the peer has closed and this side has not, which is half-open: %r"
        % (s.half_open(server),))

    bye = s.step_close(server, _to_server(stage_05.ACK, 1002,
                                          stage_05.seq_add(server_iss, 1),
                                          b"bye"), 1)
    assert bye["state"] == "close_wait" and bye["event"] == "data", (
        "and the connection still takes the peer's data in close_wait: %r"
        % (bye,))
    assert bye["segment"]["ack"] == 1005 == stage_05.seq_add(1002, 3), (
        "covering the three bytes that arrived: %r" % (bye["segment"]["ack"],))

    last = s.close(server, 2)
    assert last["state"] == "last_ack" and last["event"] == "last_ack", (
        "closing from close_wait sends this side's FIN and waits in last_ack: %r"
        % (last,))
    assert stage_05.flags_text(last["segment"]["flags"]) == "FIN", (
        "the segment is a FIN: %r" % (last["segment"],))
    assert last["segment"]["seq"] == stage_05.seq_add(server_iss, 1), (
        "from this side's next sequence number: %r" % (last["segment"]["seq"],))
    assert last["segment"]["dst_port"] == 40000, (
        "and addressed to the peer's port: %r" % (last["segment"],))

    done = s.step_close(server, _to_server(
        stage_05.ACK, 1005, stage_05.seq_add(last["segment"]["seq"], 1)), 3)
    assert done == {"state": "closed", "segment": None, "event": "closed"}, (
        "the acknowledgement of our FIN ends last_ack in closed: %r" % (done,))
    assert server.state() == "closed", (
        "and the connection is closed: %r" % (server.state(),))
    assert s.half_open(server) is False, (
        "a closed connection is not half-open: %r" % (s.half_open(server),))
    assert server.log() == (
        ("close_wait", "close_wait", "ACK", 0),
        ("close_wait", "data", "ACK", 1),
        ("last_ack", "last_ack", "FIN", 2),
        ("closed", "closed", "", 3)), (
        "and the told side's own ladder is in its log: %r" % (server.log(),))

    lingering = stage_05.Connection(80, SERVER_IP, remote=(CLIENT_IP, 40000),
                                    state="established", seed=7)
    s.step_close(lingering, _to_server(stage_05.FIN | stage_05.ACK, 1001,
                                       stage_05.seq_add(server_iss, 1)), 0)
    lingering_fin = s.close(lingering, 1)["segment"]
    assert lingering.state() == "last_ack", (
        "the told side waits in last_ack for the acknowledgement of its FIN: %r"
        % (lingering.state(),))
    still = s.step_close(lingering, _to_server(stage_05.ACK, 1000, 999), 2)
    assert still["event"] == "rejected" and still["segment"] is None, (
        "an acknowledgement that does not cover our own FIN leaves last_ack "
        "where it is: %r" % (still,))
    assert lingering.state() == "last_ack", (
        "so the peer keeps waiting, as it should: %r" % (lingering.state(),))
    finished = s.step_close(lingering, _to_server(
        stage_05.ACK, 1000, stage_05.seq_add(lingering_fin["seq"], 1)), 3)
    assert finished == {"state": "closed", "segment": None, "event": "closed"}, (
        "and the right one ends it: %r" % (finished,))

    # ---- both sides sent a FIN before the acknowledgement -----------------

    both = stage_05.Connection(40000, CLIENT_IP, remote=(SERVER_IP, 80),
                               state="established", seed=3)
    both_fin = s.close(both, 0)["segment"]
    crossed = s.step_close(both, _to_client(stage_05.FIN, 2000, 0), 5)
    assert crossed["state"] == "closing" and crossed["event"] == "closing", (
        "a FIN arriving in fin_wait_1 before the peer acknowledged ours moves "
        "the connection to closing: %r" % (crossed,))
    assert stage_05.flags_text(crossed["segment"]["flags"]) == "ACK", (
        "and that FIN is acknowledged: %r" % (crossed["segment"],))
    assert crossed["segment"]["ack"] == 2001 == stage_05.seq_add(2000, 1), (
        "counting the FIN as one sequence number: %r"
        % (crossed["segment"]["ack"],))
    assert s.half_open(both) is False, (
        "both sides have sent a FIN, so nothing here is half-open: %r"
        % (s.half_open(both),))

    stray_ack = s.step_close(both, _to_client(stage_05.ACK, 2001, 2000), 6)
    assert stray_ack["event"] == "rejected" and stray_ack["segment"] is None, (
        "an acknowledgement that does not cover our own FIN does not end "
        "closing: %r" % (stray_ack,))
    assert both.state() == "closing", (
        "and the connection waits for the right one: %r" % (both.state(),))

    waited = s.step_close(both, _to_client(stage_05.ACK, 2001,
                                           stage_05.seq_add(both_fin["seq"], 1)),
                          6)
    assert waited["state"] == "time_wait" and waited["event"] == "time_wait", (
        "and only the acknowledgement of our own FIN ends closing in "
        "time_wait: %r" % (waited,))
    assert waited["segment"] is None, (
        "which is answered with nothing: %r" % (waited["segment"],))
    assert s.time_wait_over(both, 13) is False, (
        "the wait is measured from this entry, tick six: %r"
        % (s.time_wait_over(both, 13),))
    assert s.time_wait_over(both, 14) is True, (
        "six plus eight: %r" % (s.time_wait_over(both, 14),))

    # ---- a FIN that already acknowledges ours -----------------------------

    direct = stage_05.Connection(40000, CLIENT_IP, remote=(SERVER_IP, 80),
                                 state="established", seed=3)
    direct_fin = s.close(direct, 4)["segment"]
    straight = s.step_close(direct, _to_client(
        stage_05.FIN | stage_05.ACK, 3000, stage_05.seq_add(direct_fin["seq"], 1)),
        9)
    assert straight["state"] == "time_wait" and straight["event"] == "time_wait", (
        "a FIN that acknowledges our own moves fin_wait_1 straight to "
        "time_wait, without a stop in closed: %r" % (straight,))
    assert straight["segment"]["ack"] == 3001, (
        "and it is acknowledged in turn: %r" % (straight["segment"],))
    assert s.time_wait_over(direct, 16) is False, (
        "the deadline is the tick time_wait was entered plus the wait — nine "
        "and eight, not four and eight: %r" % (s.time_wait_over(direct, 16),))
    assert s.time_wait_over(direct, 17) is True, (
        "seventeen is nine plus eight: %r" % (s.time_wait_over(direct, 17),))

    # ---- half_open answers the question about the state -------------------

    assert s.half_open(stage_05.Connection(80, SERVER_IP, state="listen")) is False, (
        "a listener has not closed a direction at all: %r"
        % (s.half_open(stage_05.Connection(80, SERVER_IP, state="listen")),))

    # ---- the refusals -----------------------------------------------------

    closing_end = stage_05.Connection(40000, CLIENT_IP, remote=(SERVER_IP, 80),
                                      state="established", seed=3)
    s.close(closing_end, 0)
    _refuses(s.CloseError, "close of a connection that is already closing",
             lambda: s.close(closing_end, 1),
             names=("'fin_wait_1'", "already closing"))
    _refuses(s.CloseError, "close of a connection that is already closed",
             lambda: s.close(server, 4), names=("'closed'", "already closed"))
    _refuses(s.CloseError, "close of a connection that is listening",
             lambda: s.close(stage_05.Connection(80, SERVER_IP, state="listen"), 0),
             names=("'listen'",))
    _refuses(s.CloseError, "close of a connection with no peer",
             lambda: s.close(stage_05.Connection(80, SERVER_IP,
                                                 state="established"), 0),
             names=("peer",))
    _refuses(s.CloseError, "close at a tick that never happened",
             lambda: s.close(closing_end, -1), names=("-1",))

    waiting = stage_05.Connection(40000, CLIENT_IP, remote=(SERVER_IP, 80),
                                  state="established", seed=3)
    waiting_fin = s.close(waiting, 0)["segment"]
    s.step_close(waiting, _to_client(stage_05.ACK, 4000,
                                     stage_05.seq_add(waiting_fin["seq"], 1)), 0)
    s.step_close(waiting, _to_client(stage_05.FIN | stage_05.ACK, 4001,
                                     stage_05.seq_add(waiting_fin["seq"], 1)), 0)
    _refuses(s.CloseError, "time_wait_over at a tick that never happened",
             lambda: s.time_wait_over(waiting, -1), names=("-1",))
    _refuses(s.CloseError, "time_wait_over of a connection that is not waiting",
             lambda: s.time_wait_over(stage_05.Connection(
                 80, SERVER_IP, remote=(CLIENT_IP, 40000), state="established",
                 seed=7), 0),
             names=("'established'",))
    _refuses(s.CloseError, "time_wait_over of a connection in fin_wait_1",
             lambda: s.time_wait_over(closing_end, 0), names=("'fin_wait_1'",))

    established = stage_05.Connection(80, SERVER_IP, remote=(CLIENT_IP, 40000),
                                      state="established", seed=7)
    _refuses(s.CloseError, "step_close of a connection in closed",
             lambda: s.step_close(server, _to_server(stage_05.ACK, 1005, 1), 5),
             names=("closed",))
    _refuses(s.CloseError, "step_close at a tick that never happened",
             lambda: s.step_close(established, _to_server(stage_05.FIN, 1, 1), -1),
             names=("-1",))
    _refuses(s.CloseError, "step_close of a connection that is not closing",
             lambda: s.step_close(stage_05.Connection(80, SERVER_IP,
                                                      state="listen"),
                                  _to_server(stage_05.SYN, 1, 0), 0),
             names=("'listen'", "not one this machine closes"))
    _refuses(s.CloseError, "step_close of something that is not a dict",
             lambda: s.step_close(established, ["not", "a", "segment"], 0),
             names=("list",))
    _refuses(s.CloseError, "step_close of a segment missing a field",
             lambda: s.step_close(established,
                                  {"src_port": 40000, "dst_port": 80, "seq": 0,
                                   "ack": 0, "flags": 0, "window": 0}, 0),
             names=("payload",))
    _refuses(s.CloseError, "step_close of an ack bit with a zero acknowledgement",
             lambda: s.step_close(established, _to_server(stage_05.ACK, 1, 0), 0),
             names=("ack",))
    _refuses(s.CloseError, "step_close of a payload that is not bytes",
             lambda: s.step_close(established,
                                  _to_server(stage_05.FIN, 1, 1, payload="x"), 0),
             names=("str",))
    _refuses(s.CloseError, "step_close of a segment for a port this connection "
                           "is not on",
             lambda: s.step_close(established,
                                  _to_server(stage_05.FIN, 1, 1, dst_port=9), 0),
             names=("9", "80"))
    _refuses(s.CloseError, "step_close of a segment from a peer that is not "
                           "this one",
             lambda: s.step_close(established,
                                  _to_server(stage_05.FIN, 1, 1, src_port=7), 0),
             names=("7", "40000"))

    # a segment that is not a FIN does not move an established connection
    stray = s.step_close(established, _to_server(stage_05.ACK, 1000,
                                                 stage_05.seq_add(server_iss, 1)),
                         1)
    assert stray["event"] == "rejected" and stray["segment"] is None, (
        "in established the only thing this machine takes is the peer's FIN: %r"
        % (stray,))
    assert established.state() == "established", (
        "and the state it was in is the state it stays in: %r"
        % (established.state(),))

    # ---- the whole close on a real wire -----------------------------------

    _wire_cases(s, stage_01, stage_05, Wire, Host, mac_of)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "tcp-ip-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

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
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _session(s, link, scenario, **over):
        """One scenario opened on one wire, with anything the check wants to change."""
        spec = dict(scenario)
        spec.update(over)
        return s.open_session(link, spec["peers"][0], spec["peers"][1],
                              spec["payload"], spec["rules"], spec["ports"])

    import stage_10 as s
    import stage_04 as icmp
    from hosts import NAMES, ip_of, mac_of
    from wire import Wire

    # ---- the constants ----------------------------------------------------

    assert s.SESSION_KEYS == ("peers", "payload", "rules", "ticks", "ports"), (
        "a scenario's five keys, in this order: %r" % (s.SESSION_KEYS,))
    assert s.LEDGER_KEYS == ("sent", "received", "bytes", "handshake", "closed",
                             "resent", "ticks", "delivered", "dropped", "expired",
                             "events"), (
        "the ledger's keys, in this order: %r" % (s.LEDGER_KEYS,))
    assert s.PROLOGUE_FRAMES == 5, (
        "the resolve and the handshake are five frames: the ARP request, its "
        "reply, the SYN, the SYN,ACK and the client's ACK: %r"
        % (s.PROLOGUE_FRAMES,))
    assert issubclass(s.SessionError, ValueError), (
        "a refusal here is a ValueError: %r" % (s.SessionError,))

    # ---- the plan ---------------------------------------------------------

    first = s.plan()
    assert isinstance(first, tuple) and len(first) == 3, (
        "three scenarios, as a tuple: %r" % (first,))
    for scenario in first:
        assert set(scenario) == set(s.SESSION_KEYS), (
            "every scenario has exactly the frozen keys: %r" % (sorted(scenario),))
        assert isinstance(scenario["payload"], bytes), (
            "a payload is bytes: %r" % (scenario["payload"],))
        assert isinstance(scenario["ports"], tuple) and len(scenario["ports"]) == 2, (
            "the ports are a pair: %r" % (scenario["ports"],))
        assert all(1 <= port <= 65535 for port in scenario["ports"]), (
            "both ports are ports: %r" % (scenario["ports"],))
        assert isinstance(scenario["ticks"], int) and scenario["ticks"] > 0, (
            "the tick budget is a positive int: %r" % (scenario["ticks"],))
        assert scenario["peers"][0] != scenario["peers"][1], (
            "two peers are two hosts: %r" % (scenario["peers"],))
        assert all(peer in NAMES for peer in scenario["peers"]), (
            "both peers are the world's: %r" % (scenario["peers"],))
    assert any(scenario["rules"] for scenario in first), (
        "one scenario is the lossy one: %r" % ([x["rules"] for x in first],))
    lossy = [scenario for scenario in first if scenario["rules"]][0]
    assert lossy["rules"].get("loss") == [s.PROLOGUE_FRAMES + 1], (
        "the lossy scenario eats the sixth frame, the first payload segment: %r"
        % (lossy["rules"],))

    second = s.plan()
    assert first == second, ("a plan is the same scenarios every time",)
    assert first[0] is not second[0], "each plan is a fresh copy"
    assert first[0]["ports"] is not second[0]["ports"], (
        "…down to the tuples inside it")
    second[0]["ports"] = (1, 2)
    assert s.plan()[0]["ports"] != (1, 2), (
        "a caller mutating one plan does not change the next one")
    defaulted = s.plan()
    assert defaulted == first, "the scenarios themselves are unchanged"

    for bad, what in [
        ({"peers": ("client", "web")}, "a scenario with one key"),
        ("client", "a scenario that is a string"),
        ([], "a plan that is a list of nothing"),
        (("client", {"peers": ("client", "web")}),
         "a plan with something that is not a scenario in it"),
    ]:
        _refuses(s.SessionError, "plan(%r)" % (bad,), lambda bad=bad: s.plan(bad))
    _refuses(s.SessionError, "a scenario that is not a scenario",
             lambda: s.plan(("client", first[0])), names=("str",))
    _refuses(s.SessionError, "a plan with an unknown peer",
             lambda: s.plan(dict(first[0], peers=("client", "nowhere"))),
             names=("nowhere",))
    _refuses(s.SessionError, "a plan whose two peers are one host",
             lambda: s.plan(dict(first[0], peers=("client", "client"))),
             names=("client",))
    _refuses(s.SessionError, "a plan whose payload is not bytes",
             lambda: s.plan(dict(first[0], payload="GET /")), names=("GET /",))
    _refuses(s.SessionError, "a plan whose tick budget is zero",
             lambda: s.plan(dict(first[0], ticks=0)), names=("tick budget", "0"))
    _refuses(s.SessionError, "a plan whose port is out of range",
             lambda: s.plan(dict(first[0], ports=(0, 80))), names=("0",))
    _refuses(s.SessionError, "a plan whose two ports are one port",
             lambda: s.plan(dict(first[0], ports=(80, 80))), names=("80",))
    _refuses(s.SessionError, "a plan whose rules the wire refuses",
             lambda: s.plan(dict(first[0], rules={"order": "shuffled"})),
             names=("shuffled",))
    _refuses(s.SessionError, "a scenario whose loss is not a list",
             lambda: s.plan(dict(first[0], rules={"loss": 6})), names=("rules",))

    # ---- open_session's own refusals --------------------------------------

    _refuses(s.SessionError, "a session on something that is not a wire",
             lambda: _session(s, None, first[0]), names=("NoneType",))
    _refuses(s.SessionError, "a session with an unknown peer",
             lambda: s.open_session(Wire(), "client", "nowhere", b"x", None,
                                    (40000, 80)), names=("nowhere",))

    # ---- the clean session ------------------------------------------------

    clean = _session(s, Wire(), first[0])
    ledger = s.run(clean)
    assert set(ledger) >= set(s.LEDGER_KEYS), (
        "a run hands back the ledger, with the frozen keys: %r" % (sorted(ledger),))
    got = s.report(clean)
    assert set(got) == set(s.LEDGER_KEYS), (
        "a report has exactly the ledger's keys: %r" % (sorted(got),))
    assert got["received"] is True, (
        "the clean session's payload arrives: %r" % (got,))
    assert got["bytes"] == len(first[0]["payload"]), (
        "all %d bytes of it, in order: %r"
        % (len(first[0]["payload"]), got["bytes"]))
    assert isinstance(got["handshake"], int) and got["handshake"] > 0, (
        "the handshake completed at a tick: %r" % (got["handshake"],))
    assert got["closed"] == "time_wait", (
        "the side that closed first waits: %r" % (got["closed"],))
    assert got["resent"] == 0, (
        "a clean wire needs no retransmission: %r" % (got["resent"],))
    assert got["expired"] is False, (
        "and nothing ran out of time: %r" % (got["expired"],))
    assert got["sent"] == clean["wire"].sent(), (
        "every frame the session sent is a frame the wire carried: %r vs %r"
        % (got["sent"], clean["wire"].sent()))
    states = {event["event"]: event for event in got["events"]}
    assert states["handshake"]["server"] == "established", (
        "the server's end shook hands too: %r" % (states["handshake"],))
    assert states["closed"]["server"] == "closed", (
        "the told side ends closed: %r" % (states["closed"],))
    agreed = s.cross_check(clean)
    assert agreed["agree"] is True, (
        "the session and the wire tell the same story: %r" % (agreed,))
    assert agreed["disagreements"] == (), (
        "with nothing to disagree about: %r" % (agreed["disagreements"],))

    # ---- the lossy session ------------------------------------------------

    lossy_run = _session(s, Wire(rules=first[1]["rules"]), first[1])
    s.run(lossy_run)
    got = s.report(lossy_run)
    assert got["received"] is True, (
        "the payload arrives despite the loss: %r" % (got,))
    assert got["resent"] >= 1, (
        "because the timer sent a segment again: %r" % (got["resent"],))
    assert got["dropped"] == 1, (
        "one frame was lost, and the session knows it: %r" % (got["dropped"],))
    assert lossy_run["wire"].dropped() == 1, (
        "the wire lost exactly one: %r" % (lossy_run["wire"].dropped(),))
    assert got["sent"] > s.PROLOGUE_FRAMES + 1, (
        "a retransmission is another frame on the wire: %r" % (got["sent"],))
    agreed = s.cross_check(lossy_run)
    assert agreed["agree"] is True, (
        "and it still agrees with the wire: %r" % (agreed,))

    # ---- the session whose wire carries nothing ---------------------------

    hopeless = _session(s, Wire(rules=first[2]["rules"]), first[2])
    ledger = s.run(hopeless)
    got = s.report(hopeless)
    assert got["received"] is False, (
        "a wire that carries nothing delivers nothing: %r" % (got,))
    assert got["bytes"] == 0, "and hands up no bytes: %r" % (got["bytes"],)
    assert got["expired"] is True, (
        "the budget is what ran out, and the session says so: %r" % (got,))
    assert got["handshake"] is None, (
        "no handshake ever completed: %r" % (got["handshake"],))
    assert got["closed"] == "closed", (
        "the client's end is where the reset left it: %r" % (got["closed"],))
    assert got["dropped"] == got["sent"], (
        "every frame it sent was lost: %r of %r" % (got["dropped"], got["sent"]))
    agreed = s.cross_check(hopeless)
    assert agreed["agree"] is True, (
        "the wire agrees about that too: %r" % (agreed,))

    # ---- the same scenario twice ------------------------------------------

    again = _session(s, Wire(), s.plan()[0])
    s.run(again)
    assert s.report(again) == s.report(clean), (
        "two runs of one scenario are the same report, byte for byte")

    # ---- what the cross-check is for --------------------------------------

    tampered = _session(s, Wire(), first[0])
    s.run(tampered)
    tampered["ledger"]["sent"] += 1
    caught = s.cross_check(tampered)
    assert caught["agree"] is False, (
        "a ledger that counts a frame the wire never carried is a disagreement")
    assert ("sent", s.report(tampered)["sent"], tampered["wire"].sent()) in caught["disagreements"], (
        "and the disagreement names the key, ours and theirs: %r"
        % (caught["disagreements"],))

    tampered = _session(s, Wire(), first[0])
    s.run(tampered)
    tampered["ledger"]["ordinals"].append(999)
    caught = s.cross_check(tampered)
    assert caught["agree"] is False, (
        "an ordinal the wire never handed out is a disagreement")
    assert any(entry[0] == "ordinals" for entry in caught["disagreements"]), (
        "named as the ordinals: %r" % (caught["disagreements"],))

    lying = _session(s, Wire(rules=first[2]["rules"]), first[2])
    s.run(lying)
    lying["ledger"]["received"] = True
    caught = s.cross_check(lying)
    assert caught["agree"] is False, (
        "a session claiming a payload the server's box never saw is a disagreement")
    assert any(entry[0] == "received" for entry in caught["disagreements"]), (
        "named as received: %r" % (caught["disagreements"],))

    # ---- and the same wire is still a wire --------------------------------

    link = Wire()
    reused = _session(s, link, first[0])
    s.run(reused)
    assert link.sent() == reused["ledger"]["sent"], (
        "the wire counted every frame this session put on it: %r vs %r"
        % (link.sent(), reused["ledger"]["sent"]))
    assert link.delivered() + link.dropped() == link.sent(), (
        "and every frame it carried was either delivered or dropped: %r + %r vs %r"
        % (link.delivered(), link.dropped(), link.sent()))

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The frame, and the type field that says what is inside",
        tags=["ethernet", "framing"],
        action="Write `FrameError`, `ETHERNET_HEADER`, `MIN_FRAME`, `TYPES`, "
               "`mac_bytes`, `build`, `parse`, `type_name`, `type_number`, "
               "`is_broadcast` and `describe` in stage_01.py.",
        predict="Why a frame's type field is the only thing a frame says about "
                "its payload, and where the padding a real NIC adds stops being "
                "anybody's problem.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="ARP, and the address that ages out",
        tags=["arp", "cache"],
        action="Write `ArpError`, `ARP_LENGTH`, `ARP_REQUEST`, `ARP_REPLY`, "
               "`CACHE_TICKS`, `build_message`, `parse_message`, `request`, "
               "`reply_to` and `Cache` (`learn`, `lookup`, `expire`, `entries`, "
               "`log`) in stage_02.py.",
        predict="Why an address that never ages out is an address that lies, and "
                "what a reply must carry for the peer that asked to be able to "
                "learn it.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="IPv4, and the hop that was one too many",
        tags=["ipv4", "routing"],
        action="Write `IpError`, `IPV4_HEADER`, `IPV4_VERSION`, `DEFAULT_TTL`, "
               "`MAX_TTL`, `IDENT_MAX`, `PROTOCOLS`, `parse_ip`, `ip_text`, "
               "`mask_of`, `network_of`, `checksum`, `checksum_ok`, "
               "`pack_header`, `unpack_header`, `build`, `route` and `forward` "
               "in stage_03.py.",
        predict="What the hop count is for, and what a router must do with a "
                "datagram whose hop count is already spent.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="ICMP, and the checksum over the whole message",
        tags=["icmp", "checksum"],
        action="Write `IcmpError`, `ICMP_HEADER`, `ERROR_QUOTE`, "
               "`ICMP_ECHO_REPLY`, `ICMP_UNREACHABLE`, `ICMP_ECHO_REQUEST`, "
               "`ICMP_TIME_EXCEEDED`, `ICMP_TYPES`, `build`, `parse`, "
               "`echo_reply`, `error_message`, `answer` and `ping` in "
               "stage_04.py.",
        predict="Why this message's checksum covers the whole message while the "
                "datagram's covers only its header, and what an error message "
                "has to carry to be useful.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The handshake, and the state machine that has to know where it is",
        tags=["tcp", "handshake"],
        action="Write `TcpError`, `TCP_HEADER`, `TCP_OFFSET`, `SEQ_MAX`, "
               "`SEQ_HALF`, `WINDOW_MAX`, `FIN`, `SYN`, `RST`, `PSH`, `ACK`, "
               "`FLAGS`, `STATES`, `WELL_KNOWN`, `flags_text`, `pack`, `unpack`, "
               "`seq_add`, `seq_before`, `initial_seq` and `Connection` (`open`, "
               "`listen`, `step`, `state`, `log`) in stage_05.py.",
        predict="Why a connection has to be a state machine, and which segment a "
                "state that does not fit its own state must answer with.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="The window, and the acknowledgement that covers everything behind it",
        tags=["tcp", "window"],
        action="Write `WindowError`, `MSS`, `Receiver` (`accept`, `window`, "
               "`buffered`, `delivered`, `log`) and `Sender` (`queue`, "
               "`next_segments`, `acknowledge`, `in_flight`, `sent`, `log`) in "
               "stage_06.py.",
        predict="What a cumulative acknowledgement promises, and what a receiver "
                "does with a segment that arrives before the one it expected.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The socket API, as a table of calls",
        tags=["sockets", "api"],
        action="Write `SocketError`, `CALLS`, `ERRNOS`, `arity`, `call_name` and "
               "`Sockets` (`call`, `state`, `fds`, `log`) in stage_07.py.",
        predict="What a call that cannot be answered must return rather than "
                "raise, and why a closed descriptor's port is not free yet.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The retransmission, and the timer that doubles",
        tags=["tcp", "retransmission"],
        action="Write `RetransmitError`, `INITIAL_TIMEOUT`, `MAX_TIMEOUT`, "
               "`MAX_TRIES`, `BACKOFF`, `Timer` (`start`, `due`, `fired`, "
               "`acknowledged`, `log`), `Reliable` (`send`, `received`, `tick`, "
               "`give_up`, `log`) and `run` in stage_08.py.",
        predict="Why the timeout doubles, and why a stack keeps one timer for "
                "the oldest segment rather than one per segment.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The close, and the state you wait in",
        tags=["tcp", "close"],
        action="Write `CloseError`, `TIME_WAIT_TICKS`, `CLOSE_STATES`, `close`, "
               "`step_close`, `half_open` and `time_wait_over` in stage_09.py.",
        predict="What half-open means, and what a connection in TIME_WAIT must "
                "do with a fresh SYN for the same pair.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The session, and the wire's own log as the tie-breaker",
        tags=["session", "capstone"],
        action="Write `SessionError`, `SESSION_KEYS`, `plan`, `open_session`, "
               "`run`, `report` and `cross_check` in stage_10.py.",
        predict="Which of the session's own numbers the wire disagrees with, and "
                "what that says about a ledger counted from beliefs instead of "
                "from the log.",
        check=check_10,
    ),
]
