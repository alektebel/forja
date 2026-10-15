"""TCP/IP From Scratch — stage 7: The socket API, as a table of calls.

See `stage_07.py` for the surface and the design decisions; this is the table
itself: the eight calls, the descriptors it hands out, the ports it holds, and
the log of every call it answered — the refused ones included.
"""

import stage_05
import stage_06
from wire import BROADCAST_MAC

CALLS = (("socket", 0), ("bind", 2), ("listen", 1), ("accept", 1), ("connect", 2),
         ("send", 2), ("recv", 1), ("close", 1))
ERRNOS = ("EBADF", "EINVAL", "ENOSYS", "EAGAIN", "ECONNREFUSED", "ENOTCONN",
          "EADDRINUSE", "EISCONN")

#: The first descriptor this table hands out, and the only thing it promises
#: about a number: a descriptor that is in use is never handed out again.
FIRST_FD = 3

#: The most a single `send` may put in flight, so a check can count the segments
#: the window allowed out. It is stage 6's own measure of a segment.
_MSS = stage_06.MSS


class SocketError(ValueError):
    """A call the *caller* got wrong — not a call at all, not an int, not a desk."""


# ---- the frozen table -----------------------------------------------------

def arity(name):
    """The number of arguments a call takes, or a refusal naming the call."""
    for key, count in CALLS:
        if key == name:
            return count
    raise SocketError("%r is not a socket call: the calls are %s"
                      % (name, ", ".join(key for key, _ in CALLS)))


def call_name(nr):
    """The name of the call numbered `nr`, from 1, in `CALLS` order."""
    if isinstance(nr, bool) or not isinstance(nr, int) or nr < 1 or nr > len(CALLS):
        raise SocketError("%r is not a call number: the calls are 1..%d"
                          % (nr, len(CALLS)))
    return CALLS[nr - 1][0]


def _fd(value):
    """A descriptor as an int, or a refusal naming what was given."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise SocketError("a descriptor is an int, not %r" % (value,))
    return value


def _port(value):
    """A port number as an int in 1..65535, or `None`."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 1 or value > stage_05.WINDOW_MAX:
        return None
    return value


def _peer(addr):
    """An `(address, port)` pair, or `None` when it is not one."""
    if not isinstance(addr, (tuple, list)) or len(addr) != 2:
        return None
    address, port = addr
    port = _port(port)
    if port is None:
        return None
    if not isinstance(address, str):
        return None
    parts = address.split(".")
    if len(parts) != 4:
        return None
    for part in parts:
        if not part.isdigit() or len(part) > 3 or int(part) > 255:
            return None
    return (address, port)


# ---- the table of sockets -------------------------------------------------

class Sockets:
    """A socket table: eight calls, a set of descriptors, and the log of both.

    Every descriptor is a `stage_05.Connection` (or, before it is bound, nothing
    yet), and `send`/`recv` carry `bytes` through stage 6's `Sender`/`Receiver`,
    so the window rules decided there are the ones in force. Every call is
    answered as data — `{"name", "value", "errno"}` with exactly one of the last
    two `None` — and a call that could not be answered is in no way special: it
    is in the log with its errno, which is the whole point of the layer.
    """

    def __init__(self, host, local_port=40000):
        """A table whose host is where its frames go and from which they come."""
        if host is None or not getattr(host, "ip", None):
            raise SocketError("a socket table needs a host with an address, not %r"
                              % (host,))
        port = _port(local_port)
        if port is None:
            raise SocketError("a default local port is a port 1..%d, not %r"
                              % (stage_05.WINDOW_MAX, local_port))
        self._host = host
        self._ip = host.ip
        self._default_port = port
        self._slots = {}
        self._ports = {}
        self._log = []

    # -- the desk of descriptors -------------------------------------------

    def _blank(self):
        """A free descriptor number, from three, never one that is in use."""
        fd = FIRST_FD
        while fd in self._slots:
            fd += 1
        return fd

    def _slot(self, fd):
        """The slot behind a descriptor, or `None` when there is none."""
        return self._slots.get(fd)

    def _answer(self, name, args, value, errno):
        """Record a call and hand back its answer: exactly one of value/errno."""
        self._log.append({"name": name, "args": tuple(args), "value": value,
                          "errno": errno})
        return {"name": name, "value": value, "errno": errno}

    def call(self, name, *args):
        """One call, answered: `{"name", "value", "errno"}`."""
        if not isinstance(name, str):
            raise SocketError("a call is named by a string, not %r" % (name,))
        for key, count in CALLS:
            if key == name:
                if len(args) != count:
                    return self._answer(name, args, None, "EINVAL")
                value, errno = getattr(self, "_do_" + key)(*args)
                return self._answer(name, args, value, errno)
        return self._answer(name, args, None, "ENOSYS")

    # -- the eight calls ----------------------------------------------------

    def _do_socket(self):
        """A new, unbound descriptor."""
        fd = self._blank()
        self._slots[fd] = {"conn": None, "port": None, "remote": None,
                           "sender": None, "receiver": None, "consumed": 0,
                           "open": False, "ended": False, "pending": []}
        return fd, None

    def _do_bind(self, fd, port):
        """Give a descriptor a local port, on this table's host."""
        fd = _fd(fd)
        slot = self._slot(fd)
        if slot is None:
            return None, "EBADF"
        number = _port(port)
        if number is None or slot["port"] is not None:
            return None, "EINVAL"
        if number in self._ports:
            return None, "EADDRINUSE"
        slot["port"] = number
        slot["conn"] = stage_05.Connection(number, self._ip, seed=number)
        self._ports[number] = fd
        return 0, None

    def _do_listen(self, fd):
        """Turn a bound descriptor into one that waits for a peer."""
        fd = _fd(fd)
        slot = self._slot(fd)
        if slot is None:
            return None, "EBADF"
        if slot["conn"] is None or slot["conn"].state() != "closed":
            return None, "EINVAL"
        slot["conn"].listen()
        return 0, None

    def _do_accept(self, fd):
        """The descriptor of a peer whose handshake completed, or `EAGAIN`."""
        fd = _fd(fd)
        slot = self._slot(fd)
        if slot is None:
            return None, "EBADF"
        if slot["conn"] is None or slot["conn"].state() != "listen":
            return None, "EINVAL"
        self._pump()
        for index, (conn, remote_port) in enumerate(slot["pending"]):
            if conn.state() != "established":
                continue
            del slot["pending"][index]
            new = self._blank()
            self._slots[new] = {"conn": conn, "port": slot["port"],
                                "remote": remote_port, "sender": None,
                                "receiver": stage_06.Receiver(slot["port"]),
                                "consumed": 0, "open": True, "ended": False,
                                "pending": []}
            return new, None
        return None, "EAGAIN"

    def _do_connect(self, fd, addr):
        """Open a descriptor towards a peer, or say the peer refused."""
        fd = _fd(fd)
        slot = self._slot(fd)
        if slot is None:
            return None, "EBADF"
        peer = _peer(addr)
        if peer is None:
            return None, "EINVAL"
        if slot["conn"] is None:
            if self._default_port in self._ports:
                return None, "EINVAL"
            slot["port"] = self._default_port
            slot["conn"] = stage_05.Connection(self._default_port, self._ip)
            self._ports[self._default_port] = fd
        if slot["conn"].state() != "closed":
            return None, "EISCONN"
        slot["remote"] = peer[1]
        opened = slot["conn"].open(peer[0], peer[1])
        self._emit(opened["reply"])
        self._pump()
        if slot["conn"].state() == "closed":
            return None, "ECONNREFUSED"
        return 0, None

    def _do_send(self, fd, data):
        """Queue `data` on a connected descriptor, within the peer's window."""
        fd = _fd(fd)
        slot = self._slot(fd)
        if slot is None:
            return None, "EBADF"
        if not isinstance(data, bytes):
            return None, "EINVAL"
        if (slot["conn"] is None or slot["ended"]
                or slot["conn"].state() != "established"):
            return None, "ENOTCONN"
        self._pump()
        if slot["sender"] is None:
            slot["sender"] = stage_06.Sender(slot["port"], slot["remote"], iss=0,
                                             window=_MSS)
        slot["sender"].queue(data)
        batch = slot["sender"].next_segments(max(1, len(data)))
        moved = 0
        for segment in batch:
            self._emit(segment)
            moved += len(segment["payload"])
        return moved, None

    def _do_recv(self, fd):
        """The bytes this descriptor has been handed, or `EAGAIN`, or `b""`."""
        fd = _fd(fd)
        slot = self._slot(fd)
        if slot is None:
            return None, "EBADF"
        if slot["conn"] is None:
            return None, "ENOTCONN"
        self._pump()
        if slot["receiver"] is not None:
            stream = slot["receiver"].delivered()
            fresh = stream[slot["consumed"]:]
            if fresh:
                slot["consumed"] = len(stream)
                return fresh, None
        if not slot["open"]:
            return None, "ENOTCONN"
        if slot["ended"] or slot["conn"].state() == "closed":
            return b"", None
        return None, "EAGAIN"

    def _do_close(self, fd):
        """Drop a descriptor, and free the port it was the one to bind."""
        fd = _fd(fd)
        slot = self._slot(fd)
        if slot is None:
            return None, "EBADF"
        if slot["port"] is not None and self._ports.get(slot["port"]) == fd:
            del self._ports[slot["port"]]
        del self._slots[fd]
        return 0, None

    # -- the stack behind the table ----------------------------------------

    def _emit(self, segment):
        """One segment out through this table's host, as its packed bytes."""
        if segment is None:
            return
        self._host.send(BROADCAST_MAC, stage_05.pack(segment, self._ip, self._ip))

    def _pump(self):
        """Read the host's mailbox and let every segment find its descriptor."""
        for data in self._host.recv():
            if not isinstance(data, bytes):
                continue
            try:
                segment = stage_05.unpack(data)
            except stage_05.TcpError:
                continue
            self._deliver(segment)

    def _deliver(self, segment):
        """One incoming segment: which descriptor it belongs to, and what to do."""
        for fd in sorted(self._slots):
            slot = self._slots[fd]
            conn = slot["conn"]
            if conn is None or slot["port"] != segment["dst_port"]:
                continue
            if conn.state() == "listen":
                self._arrive_listening(slot, segment)
                continue
            if slot["remote"] is not None and slot["remote"] != segment["src_port"]:
                continue
            if conn.state() == "closed":
                continue
            try:
                decision = conn.step(segment)
            except stage_05.TcpError:
                continue
            if conn.state() == "established":
                slot["open"] = True
            if segment["flags"] & stage_05.RST and conn.state() != "closed":
                slot["ended"] = True
            if slot["sender"] is not None and segment["flags"] & stage_05.ACK:
                try:
                    slot["sender"].acknowledge(segment["ack"])
                except stage_06.WindowError:
                    pass
            self._emit(decision["reply"])
            if segment["payload"]:
                self._arrive_payload(slot, segment)

    def _arrive_listening(self, slot, segment):
        """A segment at a listening descriptor: start a peer, or move one on."""
        if segment["flags"] & stage_05.SYN and not segment["flags"] & stage_05.ACK:
            conn = stage_05.Connection(slot["port"], self._ip,
                                       seed=segment["src_port"])
            conn.listen()
            decision = conn.step(segment)
            self._emit(decision["reply"])
            slot["pending"].append((conn, segment["src_port"]))
            return
        for conn, remote_port in slot["pending"]:
            if remote_port == segment["src_port"]:
                decision = conn.step(segment)
                self._emit(decision["reply"])

    def _arrive_payload(self, slot, segment):
        """A data segment at an established descriptor: buffer it for `recv`.

        The acknowledgement is not sent from here: the connection already
        answered this segment with its own ACK, and stage 6's receiver is here
        for the stream it hands up in order, not for a second copy of that ACK.
        """
        if slot["receiver"] is None:
            slot["receiver"] = stage_06.Receiver(slot["port"])
        slot["receiver"].accept(segment)

    # -- the reads ----------------------------------------------------------

    def state(self, fd):
        """The connection state behind a descriptor, refusing what has none."""
        fd = _fd(fd)
        slot = self._slot(fd)
        if slot is None:
            raise SocketError("no socket has descriptor %d" % (fd,))
        self._pump()
        if slot["conn"] is None:
            return "closed"
        if slot["ended"]:
            return "closed"
        return slot["conn"].state()

    def fds(self):
        """The live descriptors, ascending."""
        return tuple(sorted(self._slots))

    def log(self):
        """Every call this table answered, in order, refused ones included."""
        return tuple(self._log)
