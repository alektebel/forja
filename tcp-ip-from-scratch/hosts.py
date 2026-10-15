"""TCP/IP From Scratch — the peers.

The wire (`wire.py`) is the link; this module is *who is on it*. A `Host` is a
name, an address, a MAC and an inbox. A `Router` is a box with named ports and
the same two verbs. `NAMES` is the name table the checks resolve against, and
`Clock` is time, which passes only when a caller advances it.

    clock = Clock()
    wire = Wire({"loss": [2]})
    web = Host("web", "10.0.0.2", "10:00:00:00:00:02", wire)
    web.send(BROADCAST_MAC, b"...")          # -> the send ordinal
    wire.advance(1)
    web.recv()                               # the frames addressed to it so far

DESIGN DECISION — why is a host's MAC a string and not six bytes?
Because a check has to be able to say *which* address the stack put in the
header, and `"10:00:00:00:00:02"` is readable in a failing assertion in a way that
`b"\\x10\\x00\\x00\\x00\\x00\\x02"` is not. `wire._mac` accepts six bytes too and
converts, so a stage that builds addresses the byte way is not punished for it —
but everything the log records is the readable spelling.

DESIGN DECISION — why does a host not know how to talk?
Because every conversation in this course is written by the student. `Host` owns
an address and an inbox and nothing else: it does not know what a frame is, what
an ARP reply means, or that a handshake exists. A peer that could answer on its
own would be a peer that grades the student's work for them.

DESIGN DECISION — why is the name table a module constant?
`NAMES` is a fixture, not a service: `"web" -> "10.0.0.2"` is what the checks
hand a stack that is asked to resolve a name, and DNS itself is deliberately not
in this course (the `dns-server` legacy slot owns that subject). It exists so
that a stage can be asked to turn a name into an address without a resolver, and
so that two peers in a scenario are the same two peers in every scenario.
"""

# The link's own spelling of the broadcast address and of a MAC, re-exported so a
# stage can reach them from either module and get the same answer.
from wire import BROADCAST_MAC, WireError, mac_text

#: The name table every check resolves against. Four peers and a router.
NAMES = {
    "web": "10.0.0.2",
    "dns": "10.0.0.3",
    "db": "10.0.0.4",
    "client": "10.0.0.5",
    "router": "10.0.0.1",
}

#: The MACs those names answer to, in the same order.
MACS = {
    "router": "10:00:00:00:00:01",
    "web": "10:00:00:00:00:02",
    "dns": "10:00:00:00:00:03",
    "db": "10:00:00:00:00:04",
    "client": "10:00:00:00:00:05",
}


class HostsError(ValueError):
    """A peer the module refuses to build, named as what is wrong with it."""


def mac_of(name):
    """The MAC a name in `NAMES` answers to; a refusal names the unknown name."""
    if name not in MACS:
        raise HostsError("no peer named %r: the names are %s"
                         % (name, ", ".join(sorted(MACS))))
    return MACS[name]


def ip_of(name):
    """The address a name in `NAMES` answers to; a refusal names the unknown name."""
    if name not in NAMES:
        raise HostsError("no peer named %r: the names are %s"
                         % (name, ", ".join(sorted(NAMES))))
    return NAMES[name]


class Clock:
    """Time, as a counter: `now()` reads it, `advance(n)` is the only thing that
    moves it, and nothing in this course sleeps."""

    def __init__(self, start=0):
        start = int(start)
        if start < 0:
            raise HostsError("a clock starts at ticks, not %d" % (start,))
        self._now = start
        self._advanced = 0

    def now(self):
        """The current tick."""
        return self._now

    def advance(self, ticks=1):
        """Move forward and return where you landed. Backwards is a refusal."""
        ticks = int(ticks)
        if ticks < 0:
            raise HostsError("time does not run backwards: %d" % (ticks,))
        self._now += ticks
        self._advanced += ticks
        return self._now

    def advanced(self):
        """How many ticks this clock has been moved, in total."""
        return self._advanced


class Host:
    """A peer: an address, a MAC, and the frames the link handed it.

    `send` puts a frame on the wire and returns its send ordinal — the number the
    log knows it by. `recv` gives you the frames addressed to this host (or to
    the broadcast address) that you have not taken yet, in arrival order, and
    takes them out of the inbox. `inbox` is the whole box without emptying it,
    which is how a check asks what a host *was* sent after a stage that did not
    read it.
    """

    def __init__(self, name, ip, mac, wire, clock=None):
        if not name:
            raise HostsError("a host has a name")
        if not isinstance(ip, str) or ip.count(".") != 3:
            raise HostsError("a host's address is dotted-quad text: %r" % (ip,))
        for part in ip.split("."):
            if not part.isdigit() or int(part) > 255 or (len(part) > 1
                                                         and part[0] == "0"):
                raise HostsError("a host's address has four octets 0..255: %r"
                                 % (ip,))
        self.name = name
        self.ip = ip
        try:
            self.mac = mac_text(mac)
        except WireError as wrong:
            raise HostsError(str(wrong))
        self.wire = wire
        self.clock = clock
        self._taken = 0
        self._sent = 0

    def send(self, dst_mac, frame):
        """Put a frame on the link; return its send ordinal."""
        if self.wire is None:
            raise HostsError("host %r has no link to send on" % (self.name,))
        ordinal = self.wire.send(self.mac, dst_mac, frame)
        self._sent += 1
        return ordinal

    def sent(self):
        """How many frames this host has put on the link."""
        return self._sent

    def _addressed_to_me(self, record):
        return record["dst"] in (self.mac, BROADCAST_MAC)

    def inbox(self):
        """Every frame addressed to this host, in arrival order, without taking."""
        return [r["data"] for r in self.wire.events("deliver")
                if self._addressed_to_me(r)]

    def recv(self):
        """The frames addressed to this host that it has not taken yet."""
        arrived = [r["data"] for r in self.wire.events("deliver")
                   if self._addressed_to_me(r)]
        taken = arrived[self._taken:]
        self._taken = len(arrived)
        return taken

    def tick(self):
        """The tick this host reads, from its clock when it has one."""
        if self.clock is not None:
            return self.clock.now()
        return self.wire.tick() if self.wire is not None else 0


class Router:
    """A box with named ports on the same link.

    It can send out of a port and read what arrived on one, and that is all: the
    forwarding table, the TTL and the decision to drop are stage 3's subject, so
    the router here is the *hardware* the student's code drives, never the
    intelligence behind it.
    """

    def __init__(self, name, wire, ports, clock=None):
        ports = dict(ports or {})
        if not ports:
            raise HostsError("a router has at least one port")
        self.name = name
        self.wire = wire
        self.clock = clock
        self._ports = {}
        for port, mac in sorted(ports.items()):
            try:
                self._ports[port] = mac_text(mac)
            except WireError as wrong:
                raise HostsError(str(wrong))
        self._taken = {}
        self._sent = {}

    def ports(self):
        """The port names, in the order they were declared."""
        return list(self._ports)

    def mac(self, port):
        """The MAC a port answers to; a refusal names the unknown port."""
        if port not in self._ports:
            raise HostsError("no port %r on %r: the ports are %s"
                             % (port, self.name, ", ".join(self._ports)))
        return self._ports[port]

    def send(self, port, dst_mac, frame):
        """Put a frame on the link out of `port`, addressed to `dst_mac`.

        The next hop is the student's decision — that is what a forwarding table
        is for — so the router refuses to invent one.
        """
        mac = self.mac(port)
        ordinal = self.wire.send(mac, dst_mac, frame)
        self._sent[port] = self._sent.get(port, 0) + 1
        return ordinal

    def recv(self, port):
        """The frames addressed to this port that it has not taken yet."""
        mac = self.mac(port)
        arrived = [r["data"] for r in self.wire.events("deliver")
                   if r["dst"] in (mac, BROADCAST_MAC)]
        taken = self._taken.get(port, 0)
        self._taken[port] = len(arrived)
        return arrived[taken:]

    def sent(self, port=None):
        """How many frames went out, of one port or of all of them."""
        if port is None:
            return sum(self._sent.values())
        return self._sent.get(port, 0)
