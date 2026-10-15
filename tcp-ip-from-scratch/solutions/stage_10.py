"""TCP/IP From Scratch — stage 10: The session, and the wire's own log as the tie-breaker.

The nine stages before this one each proved a layer on its own. This one runs
the whole stack over one wire and then refuses to believe its own paperwork: the
session reports what it thinks happened, `cross_check` asks the wire, and a
disagreement is the failure the stage exists to catch.

One session is one payload from one client to one server, and the four movements
are the four stages of a handshake, a transfer and a close:

* **resolve** the peer's address with ARP (stage 2), because a frame needs a MAC
  and nothing above the link can invent one;
* **shake hands** with two `stage_05.Connection`s, each stepped with the other's
  segment, wrapped in stage 3's datagram inside stage 1's frame;
* **move the payload** through stage 8's `Reliable`, so a wire that eats a
  segment is retransmitted over by the one timer that doubles, with stage 6's
  `Receiver` on the far side handing the bytes up in order;
* **close** with stage 9, both directions, until the states say `time_wait` and
  `closed`.

The session is both sides: the world's peers are passive by design, so a session
that wants an answer has to be the thing that gives it. Every frame it emits is
counted with the ordinal the wire handed back, and every frame it takes out of a
box is counted as a delivery. `report` recomputes the ledger from those counts,
and `cross_check` holds it against `Wire.sent()`, `Wire.dropped()`,
`Wire.delivered()` and the sends' ordinals. Where the two disagree, the wire is
right — which is the whole reason a ledger is worth keeping.
"""

import stage_01
import stage_02
import stage_03
import stage_05
import stage_06
import stage_08
import stage_09
from hosts import MACS, NAMES, ip_of, mac_of
from wire import BROADCAST_MAC, Wire, WireError

#: The scenario's own keys: what `plan()` hands back and `open_session` demands.
SESSION_KEYS = ("peers", "payload", "rules", "ticks", "ports")

#: The ledger's keys, in the order `report` hands them over.
LEDGER_KEYS = ("sent", "received", "bytes", "handshake", "closed", "resent",
               "ticks", "delivered", "dropped", "expired", "events")

#: What the session spends before the payload starts: the ARP request, its reply,
#: the SYN, the SYN,ACK and the client's ACK. The sixth frame on the wire is the
#: first payload segment, which is how a scenario can name the segment a loss
#: should eat.
PROLOGUE_FRAMES = 5

#: The one protocol number this stage carries, and the name stage 3 reads back.
TCP = 6
_TCP_NAME = "tcp"

def _scenarios():
    """The course's own sessions, built fresh every time `plan()` is asked."""
    return (
        # a clean wire: one tick of latency and nothing else
        {"peers": ("client", "web"), "payload": b"GET / HTTP/1.0",
         "rules": None, "ticks": 48, "ports": (40000, 80)},
        # one segment eaten on the way out, so the payload arrives only because
        # the timer sent it again
        {"peers": ("client", "db"), "payload": b"select id from t",
         "rules": {"loss": [PROLOGUE_FRAMES + 1]}, "ticks": 64,
         "ports": (40001, 80)},
        # a wire that carries nothing at all: the session says so, not an exception
        {"peers": ("dns", "web"), "payload": b"who is there",
         "rules": {"loss": list(range(1, 33))}, "ticks": 24, "ports": (40002, 80)},
    )


class SessionError(ValueError):
    """A scenario, a peer or a port this stage cannot honour, named as what is wrong."""


# ---- the scenario ---------------------------------------------------------

def _int(value, what, low, high):
    """An int in `low..high`, or a refusal naming the offender."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise SessionError("%s is an int, not %r" % (what, value))
    if value < low or value > high:
        raise SessionError("%s is between %d and %d, not %r"
                           % (what, low, high, value))
    return value


def _peer(name, what):
    """One of the world's names, or a refusal naming what arrived instead."""
    if not isinstance(name, str) or name not in NAMES:
        raise SessionError("%s is one of the world's names, and %r is not: %s"
                           % (what, name, ", ".join(sorted(NAMES))))
    return name


def _scenario(spec):
    """One scenario, validated and copied, so two runs cannot share a dict."""
    if not isinstance(spec, dict):
        raise SessionError("a scenario is a dict with the keys %s, not %r"
                           % (", ".join(SESSION_KEYS), type(spec).__name__))
    for key in SESSION_KEYS:
        if key not in spec:
            raise SessionError("a scenario has a %r key: %r is missing it"
                               % (key, sorted(spec)))
    peers = spec["peers"]
    if (not isinstance(peers, (tuple, list)) or len(peers) != 2):
        raise SessionError("a scenario's peers are two names, not %r" % (peers,))
    client = _peer(peers[0], "the first peer")
    server = _peer(peers[1], "the second peer")
    if client == server:
        raise SessionError("a session's two peers are two hosts, and both are %r"
                           % (client,))
    payload = spec["payload"]
    if not isinstance(payload, bytes):
        raise SessionError("a scenario's payload is bytes, not %r" % (payload,))
    payload = bytes(payload)
    rules = spec["rules"]
    if rules is not None:
        if not isinstance(rules, dict):
            raise SessionError("a scenario's rules are a dict or None, not %r"
                               % (rules,))
        try:
            Wire(rules=rules).rules()
        except (WireError, TypeError, ValueError) as refused:
            raise SessionError("the wire refuses these rules: %s" % (refused,))
        rules = dict(rules)
    ports = spec["ports"]
    if (not isinstance(ports, (tuple, list)) or len(ports) != 2):
        raise SessionError("a scenario's ports are two ports, not %r" % (ports,))
    client_port = _int(ports[0], "the client's port", 1, 65535)
    server_port = _int(ports[1], "the server's port", 1, 65535)
    if client_port == server_port:
        raise SessionError("a session's two ports are two ports, and both are %d"
                           % (client_port,))
    return {"peers": (client, server), "payload": payload, "rules": rules,
            "ticks": _int(spec["ticks"], "a scenario's tick budget", 1, 4096),
            "ports": (client_port, server_port)}


def plan(sessions=None):
    """The course's scenarios, as fresh copies, or the ones a caller hands over."""
    specs = _scenarios() if sessions is None else sessions
    if isinstance(specs, dict):
        specs = (specs,)
    if not isinstance(specs, (tuple, list)) or not specs:
        raise SessionError("a plan is one scenario or a sequence of them, not %r"
                           % (specs,))
    return tuple(_scenario(spec) for spec in specs)


# ---- the objects one session runs on --------------------------------------

def open_session(link, client, server, payload, rules=None, ports=None):
    """Two hosts, two ends and the payload between them, on `link`.

    Both ends are `stage_05.Connection`s: the client's is opened towards the
    server, the server's is listened on the same port it will answer from. The
    session is the peer for both of them, so a segment one of them emits is a
    segment the other is handed.
    """
    if not isinstance(link, Wire):
        raise SessionError("a session runs on a Wire, not %r" % (type(link).__name__,))
    spec = _scenario({"peers": (client, server), "payload": payload, "rules": rules,
                      "ticks": 64, "ports": (40000, 80) if ports is None else ports})
    client_port, server_port = spec["ports"]
    return {
        "wire": link,
        "peers": spec["peers"],
        "payload": spec["payload"],
        "rules": dict(rules) if isinstance(rules, dict) else None,
        "ticks": spec["ticks"],
        "ports": spec["ports"],
        "client": spec["peers"][0],
        "server": spec["peers"][1],
        "client_host": _host(spec["peers"][0], link),
        "server_host": _host(spec["peers"][1], link),
        "client_ip": ip_of(spec["peers"][0]),
        "server_ip": ip_of(spec["peers"][1]),
        "client_mac": mac_of(spec["peers"][0]),
        "server_mac": mac_of(spec["peers"][1]),
        "conn": stage_05.Connection(client_port, ip_of(spec["peers"][0]),
                                    seed=client_port),
        "server_conn": _listening(spec["peers"][1], server_port,
                                  (ip_of(spec["peers"][0]), client_port)),
        "sender": stage_06.Sender(client_port, server_port, iss=0),
        "receiver": stage_06.Receiver(server_port),
        "reliable": None,
        "peer_mac": None,
        "ran": False,
        "ledger": {"sent": 0, "received": False, "bytes": 0, "handshake": None,
                   "closed": None, "resent": 0, "ticks": 0, "delivered": 0,
                   "dropped": 0, "expired": False, "events": [],
                   "ordinals": []},
    }


def _listening(name, port, remote):
    """The server's end: a connection in `listen`, waiting for the client's SYN.

    Its peer is the client's pair, because a listener that has not been handed a
    segment yet cannot learn who it is talking to and the close (stage 9) needs
    to know where a `FIN` goes.
    """
    conn = stage_05.Connection(port, ip_of(name), remote=remote, seed=port)
    conn.listen()
    return conn


def _host(name, link):
    """One of the world's hosts, on this session's wire."""
    from hosts import Host
    return Host(name, ip_of(name), mac_of(name), link)


# ---- one frame out, one frame in ------------------------------------------

class Frames:
    """The thing a segment goes out through: a datagram, a frame, an ordinal.

    Stage 8's `Reliable` only asks its peer for `send(segment)`, so this is what
    makes the session's own sends countable: every one records the ordinal the
    wire handed back, and those ordinals are what `cross_check` holds against the
    wire's log.
    """

    def __init__(self, session, host, dst_mac, src_ip, dst_ip, note):
        self.session = session
        self.ledger = session["ledger"]
        self.host = host
        self.dst_mac = dst_mac
        self.src_mac = host.mac
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.note = note

    def send(self, segment):
        """Put one segment on the wire, and count the frame it became."""
        segment = stage_05.pack(segment, self.src_ip, self.dst_ip)
        datagram = stage_03.build(self.src_ip, self.dst_ip, TCP, segment)
        frame = stage_01.build(self.dst_mac, self.src_mac, "ipv4", datagram)
        ordinal = self.host.send(self.dst_mac, frame)
        self.ledger["sent"] += 1
        self.ledger["ordinals"].append(ordinal)
        return ordinal


def _segments(frames, host, src_ip, dst_ip, port):
    """This pair's segments among `frames`, and how many frames were taken.

    A frame from the host's own address is not counted: a broadcast frame comes
    back to the host that sent it, the box keeps it, and a stack does not hand it
    up — counting it would make every session with an ARP request in it claim a
    delivery the wire never made.
    """
    taken = 0
    out = []
    for frame in frames:
        if not isinstance(frame, bytes) or len(frame) < stage_01.ETHERNET_HEADER:
            continue
        try:
            parsed = stage_01.parse(frame)
        except stage_01.FrameError:
            continue
        if parsed["src"] == host.mac:
            continue
        taken += 1
        if parsed["type"] != "ipv4":
            continue
        body = parsed["payload"]
        if len(body) < stage_03.IPV4_HEADER:
            continue
        try:
            header = stage_03.unpack_header(body)
        except stage_03.IpError:
            continue
        if header["protocol"] != _TCP_NAME:
            continue
        try:
            segment = stage_05.unpack(header["payload"], src_ip, dst_ip)
        except stage_05.TcpError:
            continue
        if segment["dst_port"] != port:
            continue
        out.append(segment)
    return out, taken


def _read(session, host, src_ip, dst_ip, port):
    """Every segment in a host's box for this pair, and the frames it took."""
    return _segments(host.recv(), host, src_ip, dst_ip, port)


def _client_frames(session, note):
    return Frames(session, session["client_host"], session["peer_mac"],
                  session["client_ip"], session["server_ip"], note)


def _server_frames(session, note):
    return Frames(session, session["server_host"], session["client_mac"],
                  session["server_ip"], session["client_ip"], note)


# ---- the four movements ---------------------------------------------------

def _resolve(session):
    """The client asks the server for its MAC, and the session answers as the server."""
    from hosts import Host  # noqa: F401  (the world's host table is the only source of MACs)
    link, ledger = session["wire"], session["ledger"]
    ask = stage_02.build_message(stage_02.ARP_REQUEST, session["client_mac"],
                                 session["client_ip"], BROADCAST_MAC,
                                 session["server_ip"])
    session["client_host"].send(
        BROADCAST_MAC,
        stage_01.build(BROADCAST_MAC, session["client_mac"], "arp", ask))
    ledger["sent"] += 1
    ledger["ordinals"].append(link.sent())
    link.advance(1)
    for frame in session["server_host"].recv():
        ledger["delivered"] += 1
        parsed = stage_01.parse(frame)
        if parsed["type"] != "arp":
            continue
        message = parsed["payload"][:stage_02.ARP_LENGTH]
        heard = stage_02.parse_message(message)
        if heard["target_ip"] != session["server_ip"]:
            continue
        answer = stage_02.reply_to(message, session["server_mac"], session["server_ip"])
        session["server_host"].send(
            session["client_mac"],
            stage_01.build(session["client_mac"], session["server_mac"], "arp",
                           answer))
        ledger["sent"] += 1
        ledger["ordinals"].append(link.sent())
    link.advance(1)
    for frame in session["client_host"].recv():
        parsed = stage_01.parse(frame)
        if parsed["src"] == session["client_mac"]:
            continue
        ledger["delivered"] += 1
        if parsed["type"] != "arp":
            continue
        reply = stage_02.parse_message(parsed["payload"][:stage_02.ARP_LENGTH])
        if (reply["op"] == stage_02.ARP_REPLY
                and reply["sender_ip"] == session["server_ip"]):
            session["peer_mac"] = reply["sender"]
            ledger["events"].append({"event": "resolved", "mac": reply["sender"]})
    return session["peer_mac"]


def _handshake(session):
    """The three segments, each end stepped with the other's."""
    link, ledger = session["wire"], session["ledger"]
    out = _client_frames(session, "handshake")
    opened = session["conn"].open(session["server_ip"], session["ports"][1])
    out.send(opened["reply"])
    link.advance(1)
    seen, frames = _read(session, session["server_host"], session["client_ip"],
                         session["server_ip"], session["ports"][1])
    ledger["delivered"] += frames
    for segment in seen:
        second = session["server_conn"].step(segment)
        if second["reply"] is not None:
            _server_frames(session, "handshake").send(second["reply"])
    link.advance(1)
    seen, frames = _read(session, session["client_host"], session["server_ip"],
                         session["client_ip"], session["ports"][0])
    ledger["delivered"] += frames
    for segment in seen:
        third = session["conn"].step(segment)
        if third["reply"] is not None:
            out.send(third["reply"])
    link.advance(1)
    seen, frames = _read(session, session["server_host"], session["client_ip"],
                         session["server_ip"], session["ports"][1])
    ledger["delivered"] += frames
    for segment in seen:
        session["server_conn"].step(segment)
    ledger["handshake"] = link.tick()
    ledger["events"].append({"event": "handshake",
                             "client": session["conn"].state(),
                             "server": session["server_conn"].state()})
    return ledger["handshake"]


def _transfer(session, budget):
    """Queue the payload and move it: window, wire, acknowledgement, timer."""
    link, ledger = session["wire"], session["ledger"]
    if session["conn"].state() != "established":
        return False
    session["reliable"] = stage_08.Reliable(session["sender"], stage_08.Timer(),
                                            _client_frames(session, "payload"))
    session["reliable"].send(session["payload"], link.tick())
    while link.tick() < budget:
        link.advance(1)
        now = link.tick()
        seen, frames = _read(session, session["server_host"], session["client_ip"],
                             session["server_ip"], session["ports"][1])
        ledger["delivered"] += frames
        for segment in seen:
            answer = session["server_conn"].step(segment)
            if answer["reply"] is not None:
                _server_frames(session, "ack").send(answer["reply"])
            if segment["payload"]:
                session["receiver"].accept(segment)
        seen, frames = _read(session, session["client_host"], session["server_ip"],
                             session["client_ip"], session["ports"][0])
        ledger["delivered"] += frames
        for segment in seen:
            session["reliable"].received(segment, now)
        late = session["reliable"].tick(now)
        if late.get("resent"):
            ledger["resent"] += late["resent"]
        ledger["bytes"] = len(session["receiver"].delivered())
        if ledger["bytes"] >= len(session["payload"]):
            ledger["received"] = True
            return True
        if late.get("expired"):
            return False
    return False


def _shutdown(session, now):
    """The four-way close: FIN, ACK, FIN, ACK, with both ends stepped."""
    link, ledger = session["wire"], session["ledger"]
    out = _client_frames(session, "close")
    back = _server_frames(session, "close")
    if session["conn"].state() != "established":
        ledger["closed"] = session["conn"].state()
        return ledger["closed"]
    started = stage_09.close(session["conn"], now)
    out.send(started["segment"])
    link.advance(1)
    seen, frames = _read(session, session["server_host"], session["client_ip"],
                         session["server_ip"], session["ports"][1])
    ledger["delivered"] += frames
    for segment in seen:
        told = stage_09.step_close(session["server_conn"], segment, link.tick())
        if told["segment"] is not None:
            back.send(told["segment"])
    link.advance(1)
    seen, frames = _read(session, session["client_host"], session["server_ip"],
                         session["client_ip"], session["ports"][0])
    ledger["delivered"] += frames
    for segment in seen:
        moved = stage_09.step_close(session["conn"], segment, link.tick())
        if moved["segment"] is not None:
            out.send(moved["segment"])
    if session["server_conn"].state() != "close_wait":
        ledger["closed"] = session["conn"].state()
        ledger["events"].append({"event": "closed", "client": session["conn"].state(),
                                 "server": session["server_conn"].state()})
        return ledger["closed"]
    last = stage_09.close(session["server_conn"], link.tick())
    back.send(last["segment"])
    link.advance(1)
    seen, frames = _read(session, session["client_host"], session["server_ip"],
                         session["client_ip"], session["ports"][0])
    ledger["delivered"] += frames
    for segment in seen:
        moved = stage_09.step_close(session["conn"], segment, link.tick())
        if moved["segment"] is not None:
            out.send(moved["segment"])
    link.advance(1)
    seen, frames = _read(session, session["server_host"], session["client_ip"],
                         session["server_ip"], session["ports"][1])
    ledger["delivered"] += frames
    for segment in seen:
        stage_09.step_close(session["server_conn"], segment, link.tick())
    ledger["closed"] = session["conn"].state()
    ledger["events"].append({"event": "closed", "client": session["conn"].state(),
                             "server": session["server_conn"].state()})
    return ledger["closed"]


def run(session, max_ticks=64):
    """One session, end to end, and the ledger it believes."""
    if session.get("ran"):
        raise SessionError("this session has already run: open another one")
    session["ran"] = True
    link, ledger = session["wire"], session["ledger"]
    budget = min(session["ticks"], max_ticks)
    if _resolve(session) is None:
        ledger["expired"] = True
    elif _handshake(session) is None:
        ledger["expired"] = True
    elif not _transfer(session, budget):
        ledger["expired"] = not ledger["received"]
    _shutdown(session, link.tick())
    link.advance(1)
    ledger["ticks"] = link.tick()
    ledger["dropped"] = ledger["sent"] - ledger["delivered"]
    return ledger


# ---- the two accounts -----------------------------------------------------

def _wire_counts(session):
    """What the wire itself says happened, in the ledger's own vocabulary.

    `payload_seen` is the world's evidence that the payload arrived: a frame in
    the server's box carrying a segment with a body. It is read from the box, not
    from the session's ledger, which is what makes it worth comparing.
    """
    link = session["wire"]
    seen, _ = _segments(session["server_host"].inbox(), session["server_host"],
                        session["client_ip"], session["server_ip"],
                        session["ports"][1])
    return {
        "sent": link.sent(),
        "delivered": link.delivered(),
        "dropped": link.dropped(),
        "ticks": link.tick(),
        "ordinals": tuple(entry["ordinal"] for entry in link.log()
                          if entry.get("event") == "send"),
        "payload_seen": any(segment["payload"] for segment in seen),
        "server_box": len(session["server_host"].inbox()),
        "client_box": len(session["client_host"].inbox()),
    }


def report(session):
    """The session's own account, recomputed from its ledger."""
    ledger = session["ledger"]
    return {key: (tuple(ledger[key]) if key == "events" else ledger[key])
            for key in LEDGER_KEYS}


def cross_check(session):
    """The session's ledger against the wire's record: the wire is right."""
    ours = report(session)
    theirs = _wire_counts(session)
    disagreements = []
    for key in ("sent", "delivered", "dropped", "ticks"):
        if ours[key] != theirs[key]:
            disagreements.append((key, ours[key], theirs[key]))
    if ours["received"] is not theirs["payload_seen"]:
        disagreements.append(("received", ours["received"], theirs["payload_seen"]))
    if tuple(session["ledger"]["ordinals"]) != theirs["ordinals"]:
        disagreements.append(("ordinals", tuple(session["ledger"]["ordinals"]),
                              theirs["ordinals"]))
    return {"agree": not disagreements, "disagreements": tuple(disagreements)}
