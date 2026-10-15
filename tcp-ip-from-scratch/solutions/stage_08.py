"""TCP/IP From Scratch — stage 8: The retransmission, and the timer that doubles.

See `stage_08.py` for the surface and the design decisions; this is the timer
that doubles, the connection that keeps one of them, and the little session
`run` drives to prove both.
"""

import stage_03
import stage_05
import stage_06
from hosts import Host
from wire import Wire

INITIAL_TIMEOUT = 2
MAX_TIMEOUT = 16
MAX_TRIES = 4
BACKOFF = 2

#: The two ports `run`'s little session uses: a client on an ephemeral one and a
#: peer on the web port. They are frozen here so a check can say which segment
#: was dropped without inventing a number.
_CLIENT_PORT = 40000
_PEER_PORT = 80


class RetransmitError(ValueError):
    """A timer or a connection this stage cannot honour, named as what is wrong."""


# ---- the small conversions every entry point shares -----------------------

def _int(value, what):
    """An int, or a refusal naming what was given instead."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise RetransmitError("%s is an int, not %r" % (what, value))
    return value


def _count(value, what, low=0):
    """An int at or above `low`, or a refusal naming the offender."""
    number = _int(value, what)
    if number < low:
        raise RetransmitError("%s is %d, and the least it can be is %d"
                              % (what, number, low))
    return number


def _segment(segment):
    """The seven fields stage 5 froze, or a refusal naming the one that is wrong."""
    keys = ("src_port", "dst_port", "seq", "ack", "flags", "window", "payload")
    if not isinstance(segment, dict):
        raise RetransmitError("a segment is a dict of its fields, not %r"
                              % (type(segment).__name__,))
    for key in keys:
        if key not in segment:
            raise RetransmitError("a segment has a %r field, and this one does not: %r"
                                  % (key, sorted(segment)))
    return segment


# ---- the timer ------------------------------------------------------------

class Timer:
    """One retransmission timer, for the oldest segment still unacknowledged.

    A connection keeps exactly one of these, and that is the whole point: a timer
    that restarted for every segment in flight would give each segment its own
    timeout, and the retransmissions would have no shape a check could count.
    """

    def __init__(self, timeout=INITIAL_TIMEOUT, backoff=BACKOFF, tries=MAX_TRIES):
        """A timer that waits `timeout` ticks, doubles by `backoff`, gives up after `tries`."""
        self._timeout = _count(timeout, "a timeout", 1)
        self._backoff = _count(backoff, "a backoff", 1)
        self._tries = _count(tries, "a tries", 1)
        self._armed = None
        self.gave_up = False
        self._events = []

    def start(self, seq, now):
        """Arm the timer for the segment that begins at `seq`, from `now`."""
        number = _int(seq, "a sequence number")
        when = _count(now, "now")
        if self._armed is not None:
            raise RetransmitError("this timer is already armed for %d: one timer, "
                                  "one segment" % (self._armed["seq"],))
        if self.gave_up:
            raise RetransmitError("this timer has already given up")
        self._armed = {"seq": number, "tries": 0, "timeout": self._timeout,
                       "due": when + self._timeout}
        due = when + self._timeout
        self._events.append({"event": "start", "seq": number, "due": due,
                             "timeout": self._timeout})
        return {"seq": number, "due": due, "timeout": self._timeout}

    def due(self, now):
        """The tick this timer fires at, or `None` when it is not armed."""
        if self._armed is None:
            return None
        return self._armed["due"]

    def fired(self, now):
        """The timer went off: the segment to send again, or `{"expired": True}`."""
        when = _count(now, "now")
        if self._armed is None:
            return {"expired": True}
        if self._armed["tries"] >= self._tries:
            self._events.append({"event": "expire", "seq": self._armed["seq"],
                                 "tries": self._armed["tries"]})
            self._armed = None
            self.gave_up = True
            return {"expired": True}
        self._armed["tries"] += 1
        self._armed["timeout"] = min(self._armed["timeout"] * self._backoff,
                                     MAX_TIMEOUT)
        self._armed["due"] = when + self._armed["timeout"]
        self._events.append({"event": "fire", "seq": self._armed["seq"],
                             "tries": self._armed["tries"],
                             "timeout": self._armed["timeout"],
                             "due": self._armed["due"]})
        return {"seq": self._armed["seq"], "tries": self._armed["tries"],
                "timeout": self._armed["timeout"]}

    def acknowledged(self, ack, now):
        """An acknowledgement arrived: `{"stopped", "again"}`.

        The timer stops only when the acknowledgement covers the segment it is
        armed for, in the modular sense of `stage_05.seq_before` — an
        acknowledgement that moves nothing leaves it running, because a duplicate
        acknowledgement is a signal, not progress.
        """
        number = _int(ack, "an acknowledgement")
        _count(now, "now")
        if self._armed is None:
            return {"stopped": False, "again": True}
        if (number != self._armed["seq"]
                and stage_05.seq_before(self._armed["seq"], number)):
            self._events.append({"event": "ack", "ack": number, "stopped": True})
            self._armed = None
            return {"stopped": True, "again": False}
        self._events.append({"event": "ack", "ack": number, "stopped": False})
        return {"stopped": False, "again": True}

    def log(self):
        """Every event this timer saw, in order, as dicts."""
        return tuple(self._events)


# ---- the reliable connection ----------------------------------------------

class Reliable:
    """A sender plus the one timer that decides when its oldest segment is late.

    It owns no wire either, exactly as stage 6's `Sender` does not: `peer` is the
    thing it transmits through, and the caller is the one that brings the peer's
    acknowledgements back in through `received`.
    """

    def __init__(self, sender, timer, peer):
        """A sender, its timer, and the thing a segment goes out through."""
        if not isinstance(timer, Timer):
            raise RetransmitError("a reliable connection needs a Timer, not %r"
                                  % (type(timer).__name__,))
        self._sender = sender
        self._timer = timer
        self._peer = peer
        self._inflight = []
        self._events = []

    def _transmit(self, segment):
        """Put one segment on the way out through the peer."""
        self._peer.send(segment)

    def _push(self, now):
        """Send every queued segment the window now allows, oldest first."""
        count = 0
        while True:
            batch = self._sender.next_segments(1)
            if not batch:
                break
            segment = batch[0]
            self._transmit(segment)
            self._inflight.append(segment)
            count += 1
        return count

    def _arm(self, now):
        """Arm the one timer for the oldest segment in flight, if it is idle."""
        if self._timer.due(now) is None and self._inflight:
            self._timer.start(self._inflight[0]["seq"], now)

    def _drop_acknowledged(self, ack):
        """Remove every segment whose last byte is covered by `ack`."""
        kept = []
        for segment in self._inflight:
            end = stage_05.seq_add(segment["seq"], len(segment["payload"]))
            if not stage_05.seq_before(end, ack):
                kept.append(segment)
        self._inflight = kept

    def send(self, data, now):
        """Queue `data`, put what the window allows in flight, arm the timer."""
        queued = self._sender.queue(data)
        sent = self._push(now)
        self._arm(now)
        self._events.append({"event": "send", "segments": sent,
                             "due": self._timer.due(now)})
        return {"segments": len(queued), "sent": sent, "due": self._timer.due(now)}

    def received(self, segment, now):
        """An acknowledgement arrived: move the window, stop or keep the timer."""
        seg = _segment(segment)
        if (seg["dst_port"] != self._sender._local_port
                or seg["src_port"] != self._sender._remote_port):
            raise RetransmitError("this connection is %d<-%d, not %d<-%d"
                                  % (self._sender._local_port,
                                     self._sender._remote_port,
                                     seg["dst_port"], seg["src_port"]))
        ack = seg["ack"]
        result = self._sender.acknowledge(ack)
        self._drop_acknowledged(ack)
        self._timer.acknowledged(ack, now)
        self._arm(now)
        event = "ack" if result["acked"] else "again"
        self._events.append({"event": event, "acked": result["acked"]})
        return {"acked": result["acked"], "event": event}

    def tick(self, now):
        """One tick of the clock: fire the timer, then push what now fits."""
        resent = 0
        expired = False
        due = self._timer.due(now)
        if due is not None and now >= due:
            fired = self._timer.fired(now)
            if "expired" in fired:
                expired = True
            else:
                segment = None
                for held in self._inflight:
                    if held["seq"] == fired["seq"]:
                        segment = held
                        break
                if segment is not None:
                    self._transmit(segment)
                    resent = 1
        if not expired:
            self._push(now)
            self._arm(now)
        self._events.append({"event": "tick", "resent": resent, "expired": expired})
        return {"resent": resent, "expired": expired, "due": self._timer.due(now)}

    def give_up(self, now):
        """Whether the tries are spent and this connection has stopped trying."""
        _count(now, "now")
        return self._timer.gave_up

    def log(self):
        """Every decision this connection made, in order, as dicts."""
        return tuple(self._events)


# ---- the little session that proves it ------------------------------------

class _Link:
    """The one thing `run` needs and the world does not have: a datagram out."""

    def __init__(self, host, src_ip, dst_ip, dst_mac):
        self._host = host
        self._src_ip = src_ip
        self._dst_ip = dst_ip
        self._dst_mac = dst_mac
        self._count = 0

    def send(self, segment):
        """Pack one segment into a datagram and put it on the link."""
        body = stage_05.pack(segment, self._src_ip, self._dst_ip)
        datagram = stage_03.build(self._src_ip, self._dst_ip, "tcp", body)
        self._host.send(self._dst_mac, datagram)
        self._count += 1

    def count(self):
        """How many datagrams went out through this link."""
        return self._count


def _read_datagram(data, src_ip, dst_ip):
    """The segment inside a datagram, or `None` when it cannot be one."""
    try:
        header = stage_03.unpack_header(data)
    except stage_03.IpError:
        return None
    if header["protocol"] != "tcp" or not header["checksum_ok"]:
        return None
    try:
        return stage_05.unpack(header["payload"], src_ip, dst_ip)
    except stage_05.TcpError:
        return None


def run(wire, host, peer_mac, peer_ip, data, *, rules=None, max_ticks=64,
        wire_rules=None):
    """Drive one payload across one wire and report what the wire did.

    A client on `host` sends `data` to the peer at `peer_ip`/`peer_mac` through a
    `Reliable`; the peer is scripted here (the world's peers are passive) and
    acknowledges what arrives; the wire is advanced tick by tick, and `dropped`
    and `delivered` are read back out of its log rather than believed.
    """
    if wire is None:
        wire = Wire(wire_rules)
    client_ip = host.ip
    client_port = _CLIENT_PORT
    peer_port = _PEER_PORT
    if not isinstance(data, bytes):
        raise RetransmitError("a payload is bytes, not %r" % (type(data).__name__,))

    peer_host = Host("peer", peer_ip, peer_mac, wire)
    sender = stage_06.Sender(client_port, peer_port, iss=0,
                             window=stage_06.MSS)
    timer = Timer()
    out = _Link(host, client_ip, peer_ip, peer_mac)
    reliable = Reliable(sender, timer, out)
    receiver = stage_06.Receiver(peer_port)
    peer_seq = 0

    opened = reliable.send(data, wire.tick())
    acked = 0
    ticks = 0
    while ticks < max_ticks:
        if reliable.give_up(wire.tick()) or sender.in_flight() == 0:
            break
        wire.advance(1)
        ticks += 1
        now = wire.tick()
        for frame in host.recv():
            segment = _read_datagram(frame, peer_ip, client_ip)
            if segment is None:
                continue
            decision = reliable.received(segment, now)
            acked += decision["acked"]
        for frame in peer_host.recv():
            segment = _read_datagram(frame, client_ip, peer_ip)
            if segment is None or not segment["payload"]:
                continue
            answer = receiver.accept(segment)
            ack = {"src_port": peer_port, "dst_port": client_port, "seq": peer_seq,
                   "ack": answer["acked"], "flags": stage_05.ACK,
                   "window": receiver.window(), "payload": b""}
            peer_host.send(host.mac, stage_03.build(peer_ip, client_ip, "tcp",
                                                    stage_05.pack(ack, peer_ip,
                                                                  client_ip)))
        reliable.tick(now)

    log = wire.log()
    resent = len([e for e in timer.log() if e["event"] == "fire"])
    return {"sent": opened["sent"], "resent": resent,
            "acked": acked, "ticks": ticks,
            "delivered": len([e for e in log if e["event"] == "deliver"]),
            "dropped": len([e for e in log if e["event"] == "drop"]),
            "expired": reliable.give_up(wire.tick())}
