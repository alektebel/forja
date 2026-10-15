"""TCP/IP From Scratch — stage 5: The handshake, and the state machine that has to know where it is.

See `stage_05.py` for the surface and the design decisions; this is the segment,
the sequence arithmetic and the state machine.
"""

TCP_HEADER = 20
TCP_OFFSET = 5
SEQ_MAX = 2 ** 32
SEQ_HALF = 2 ** 31
WINDOW_MAX = 65535
FIN, SYN, RST, PSH, ACK = 1, 2, 4, 8, 16
FLAGS = (FIN, SYN, RST, PSH, ACK)
STATES = ("closed", "listen", "syn_sent", "syn_received", "established")
WELL_KNOWN = {"dns": 53, "web": 80, "db": 5432}

#: The sequence space as a mask: every sequence number is an int in 0..SEQ_MAX-1,
#: and the arithmetic that wraps is the arithmetic this stage does by hand.
_MASK = SEQ_MAX - 1

#: The six flag bits; the six reserved bits of the offset/flags word are zero on
#: the wire and are not a flag.
_FLAG_BITS = 0x3F

#: The flag bits this course names. The field is six bits wide and this course
#: speaks five of them, so the sixth is a bit `flags_text` refuses rather than
#: prints.
_NAMED = FIN | SYN | RST | PSH | ACK

#: The segment's own fields, in the order the header carries them. A segment is
#: these seven facts and nothing else: the two addresses its checksum is about
#: are a fact about a *datagram*, and a segment does not carry them.
_SEGMENT_KEYS = ("src_port", "dst_port", "seq", "ack", "flags", "window", "payload")

#: The order the flags are named in, which is the header's own order.
_NAMES = ("FIN", "SYN", "RST", "PSH", "ACK")


class TcpError(ValueError):
    """A segment this stack cannot build or read, named as what is wrong with it."""


# ---- the small conversions every entry point shares -----------------------

def _int(value, what):
    """An int, or a refusal naming what was given instead."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TcpError("%s is an int, not %r" % (what, value))
    return value


def _count(value, what, low=0, high=None):
    """An int inside its range, or a refusal naming the offender."""
    number = _int(value, what)
    if number < low:
        raise TcpError("%s is %d, and the least it can be is %d"
                       % (what, number, low))
    if high is not None and number > high:
        raise TcpError("%s is %d, and the most it can be is %d"
                       % (what, number, high))
    return number


def _octets(ip, what):
    """An address as the four octets the pseudo-header carries."""
    if isinstance(ip, bytes):
        if len(ip) != 4:
            raise TcpError("%s is four octets, not %d bytes" % (what, len(ip)))
        return bytes(ip)
    if not isinstance(ip, str):
        raise TcpError("%s is dotted-quad text or four bytes, not %r" % (what, ip))
    parts = ip.split(".")
    if len(parts) != 4:
        raise TcpError("%s has four octets, not %d: %r" % (what, len(parts), ip))
    out = []
    for part in parts:
        if not part.isdigit() or (len(part) > 1 and part[0] == "0") or int(part) > 255:
            raise TcpError("%s has four octets in plain digits, each 0..255: %r"
                           % (what, ip))
        out.append(int(part))
    return bytes(out)


def _ip_text(ip, what):
    """An address in its text form, whatever form it arrived in."""
    return ".".join(str(octet) for octet in _octets(ip, what))


def _port(value, what):
    """A port number, or the port a well-known name answers to."""
    if isinstance(value, str):
        if value in WELL_KNOWN:
            return WELL_KNOWN[value]
        raise TcpError("no well-known port is called %r: the names are %s"
                       % (value, ", ".join(sorted(WELL_KNOWN))))
    number = _int(value, what)
    if number < 1 or number > WINDOW_MAX:
        raise TcpError("%s is a port 1..%d, not %d" % (what, WINDOW_MAX, number))
    return number


def _state(name):
    """A state this machine has, or a refusal naming the one it was handed."""
    if name not in STATES:
        raise TcpError("no connection state is called %r: the states are %s"
                       % (name, ", ".join(STATES)))
    return name


def _pair(remote):
    """An `(address, port)` pair, or a refusal naming what was given."""
    if not isinstance(remote, (tuple, list)) or len(remote) != 2:
        raise TcpError("a peer is an (address, port) pair, not %r" % (remote,))
    address, port = remote
    return (_ip_text(address, "the remote address"), _port(port, "the remote port"))


def _segment(segment):
    """The segment's seven fields, or a refusal naming the one that is wrong."""
    if not isinstance(segment, dict):
        raise TcpError("a segment is a dict of its fields, not %r"
                       % (type(segment).__name__,))
    for key in _SEGMENT_KEYS:
        if key not in segment:
            raise TcpError("a segment has a %r field, and this one does not: %r"
                           % (key, sorted(segment)))
    for key in ("src_port", "dst_port", "seq", "ack", "flags", "window"):
        _int(segment[key], "a segment's %s" % (key,))
    if not isinstance(segment["payload"], bytes):
        raise TcpError("a segment's payload is bytes, not %r"
                       % (type(segment["payload"]).__name__,))
    if segment["flags"] & ACK and segment["ack"] == 0:
        raise TcpError("a segment with the ack bit set acknowledges something, "
                       "not %d" % (segment["ack"],))
    return segment


# ---- the pseudo-header checksum -------------------------------------------

def _sum16(data):
    """The 16-bit one's-complement sum of `data`, odd length padded with a zero."""
    if len(data) % 2:
        data = data + b"\x00"
    total = 0
    for index in range(0, len(data), 2):
        total += int.from_bytes(data[index:index + 2], "big")
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return total & 0xFFFF


def _pseudo(src, dst, length):
    """The twelve bytes a tcp checksum is about and a segment does not carry."""
    return (_octets(src, "the source address") + _octets(dst, "the destination address")
            + bytes((0, 6)) + int.to_bytes(length, 2, "big"))


def _checksum(segment_bytes, src, dst):
    """The value that goes into the checksum field of these bytes."""
    return (~_sum16(_pseudo(src, dst, len(segment_bytes)) + segment_bytes)) & 0xFFFF


# ---- the segment ----------------------------------------------------------

def flags_text(flags):
    """`"SYN,ACK"` — the closed vocabulary, in the header's own order."""
    number = _int(flags, "a flag word")
    if number & ~_NAMED:
        raise TcpError("no tcp flag is numbered %d: the flags are %s"
                       % (number, ", ".join("%d %s" % (value, name)
                                            for value, name in zip(FLAGS, _NAMES))))
    return ",".join(name for value, name in zip(FLAGS, _NAMES) if number & value)


def pack(segment, src=None, dst=None):
    """The 20-byte header and its payload, with the pseudo-header checksum."""
    seg = _segment(segment)
    if src is None or dst is None:
        raise TcpError("a segment's checksum covers two addresses it does not "
                       "carry: pack needs src and dst, not %r" % ((src, dst),))
    head = (int.to_bytes(seg["src_port"], 2, "big")
            + int.to_bytes(seg["dst_port"], 2, "big")
            + int.to_bytes(seg["seq"] & _MASK, 4, "big")
            + int.to_bytes(seg["ack"] & _MASK, 4, "big")
            + int.to_bytes((TCP_OFFSET << 12) | (seg["flags"] & _FLAG_BITS), 2, "big")
            + int.to_bytes(seg["window"], 2, "big")
            + b"\x00\x00" + b"\x00\x00")
    body = head + seg["payload"]
    check = _checksum(body, src, dst)
    return body[:16] + int.to_bytes(check, 2, "big") + body[18:]


def unpack(data, src=None, dst=None):
    """The segment's eight facts, refusing what cannot be a segment."""
    if not isinstance(data, bytes):
        raise TcpError("a segment is bytes, not %r" % (type(data).__name__,))
    if len(data) < TCP_HEADER:
        raise TcpError("a segment is at least %d bytes, not %d"
                       % (TCP_HEADER, len(data)))
    offset = data[12] >> 4
    if offset != TCP_OFFSET:
        raise TcpError("a data offset of %d is not this stack's %d"
                       % (offset, TCP_OFFSET))
    src_port = int.from_bytes(data[0:2], "big")
    if src_port == 0:
        raise TcpError("a segment's source port is 1..%d, not 0" % (WINDOW_MAX,))
    dst_port = int.from_bytes(data[2:4], "big")
    if dst_port == 0:
        raise TcpError("a segment's destination port is 1..%d, not 0" % (WINDOW_MAX,))
    checked = None
    if src is not None and dst is not None:
        checked = _sum16(_pseudo(src, dst, len(data)) + data) == 0xFFFF
    return {"src_port": src_port, "dst_port": dst_port,
            "seq": int.from_bytes(data[4:8], "big"),
            "ack": int.from_bytes(data[8:12], "big"),
            "flags": int.from_bytes(data[12:14], "big") & _FLAG_BITS,
            "window": int.from_bytes(data[14:16], "big"),
            "payload": data[TCP_HEADER:], "checksum_ok": checked}


# ---- the sequence space ---------------------------------------------------

def seq_add(seq, n):
    """`seq + n`, in the modular sequence space."""
    return (_int(seq, "a sequence number") + _int(n, "a count")) & _MASK


def seq_before(a, b):
    """Whether `a` is behind `b` in the modular space, the wrap included."""
    return ((_int(b, "a sequence number") - _int(a, "a sequence number")) & _MASK) < SEQ_HALF


def initial_seq(seed):
    """The sequence number a connection starts at, spread over all 32 bits."""
    value = _int(seed, "a seed") & _MASK
    value = (value * 2654435761 + 40503) & _MASK
    value ^= value >> 13
    value = (value * 2654435761) & _MASK
    value ^= value >> 17
    return value & _MASK


# ---- the state machine ----------------------------------------------------

class Connection:
    """One end of a connection: a port, a peer, a state and its own log."""

    def __init__(self, local_port, local_ip=None, remote=None, state="closed",
                 seed=0, window=WINDOW_MAX):
        """A connection on `local_port`, in `state`, whose ISN is `initial_seq(seed)`."""
        self._local_port = _port(local_port, "the local port")
        self._local_ip = None if local_ip is None else _ip_text(local_ip,
                                                                "the local address")
        self._remote = None if remote is None else _pair(remote)
        self._state = _state(state)
        self._iss = initial_seq(seed)
        self._window = _count(window, "the window", 0, WINDOW_MAX)
        self._events = []
        self._steps = 0

    def _log(self, state, event, flags, now):
        """One transition, as it happened; a step of its own when no tick was given."""
        when = self._steps if now is None else _count(now, "now")
        self._events.append((state, event, flags, when))
        self._steps += 1

    def _next_seq(self):
        """The sequence number this side would put on the wire next."""
        return seq_add(self._iss, 1)

    def _reply(self, segment, flags, ack, seq):
        """A segment answering `segment`, on this connection's ports."""
        return {"src_port": self._local_port, "dst_port": segment["src_port"],
                "seq": seq, "ack": ack, "flags": flags, "window": self._window,
                "payload": b""}

    def _decide(self, segment):
        """The table: what this state does with this segment, or nothing."""
        flags = segment["flags"]
        state = self._state
        if state == "listen":
            if flags & SYN and not flags & ACK and not segment["payload"]:
                return ("syn_received",
                        self._reply(segment, SYN | ACK, seq_add(segment["seq"], 1),
                                    self._iss), "syn_received")
            return None
        if state == "syn_sent":
            if flags & RST:
                return ("closed", None, "refused")
            if (flags & SYN and flags & ACK
                    and segment["ack"] == self._next_seq()):
                return ("established",
                        self._reply(segment, ACK, seq_add(segment["seq"], 1),
                                    self._next_seq()), "established")
            return None
        if state == "syn_received":
            if flags & RST:
                return None
            if (flags & ACK and not flags & SYN
                    and segment["ack"] == self._next_seq()):
                return ("established", None, "established")
            return None
        if state == "established":
            if flags & RST:
                return None
            if flags & SYN:
                if segment["payload"]:
                    return None
                return ("established",
                        self._reply(segment, ACK, seq_add(segment["seq"], 1),
                                    self._next_seq()), "duplicate")
            if segment["payload"]:
                return ("established",
                        self._reply(segment, ACK,
                                    seq_add(segment["seq"], len(segment["payload"])),
                                    self._next_seq()), "data")
            return None
        return None

    def open(self, remote_ip, remote_port):
        """Active open: move to `syn_sent` and hand back the SYN to send."""
        if self._state != "closed":
            raise TcpError("open of a connection in state %r: only a closed one "
                           "opens" % (self._state,))
        self._remote = (_ip_text(remote_ip, "the remote address"),
                        _port(remote_port, "the remote port"))
        segment = {"src_port": self._local_port, "dst_port": self._remote[1],
                   "seq": self._iss, "ack": 0, "flags": SYN, "window": self._window,
                   "payload": b""}
        self._state = "syn_sent"
        self._log("syn_sent", "syn_sent", flags_text(SYN), None)
        return {"state": "syn_sent", "reply": segment, "event": "syn_sent"}

    def listen(self):
        """Passive open: move to `listen`, waiting for a SYN to answer."""
        if self._state != "closed":
            raise TcpError("listen of a connection in state %r: only a closed one "
                           "listens" % (self._state,))
        self._state = "listen"
        self._log("listen", "listen", "", None)
        return {"state": "listen", "reply": None, "event": "listen"}

    def step(self, segment, now=None):
        """One segment in, one decision out: `{"state", "reply", "event"}`."""
        seg = _segment(segment)
        if seg["dst_port"] != self._local_port:
            raise TcpError("this connection answers on port %d, not %d"
                           % (self._local_port, seg["dst_port"]))
        if self._remote is not None and seg["src_port"] != self._remote[1]:
            raise TcpError("this connection's peer is on port %d, not %d"
                           % (self._remote[1], seg["src_port"]))
        verdict = self._decide(seg)
        if verdict is None:
            reply = None
            if not seg["flags"] & RST:
                reply = self._reply(seg, RST, seg["ack"], self._next_seq())
            self._log(self._state, "rejected",
                      "" if reply is None else flags_text(RST), now)
            return {"state": self._state, "reply": reply, "event": "rejected"}
        state, reply, event = verdict
        self._state = state
        self._log(state, event,
                  "" if reply is None else flags_text(reply["flags"]), now)
        return {"state": state, "reply": reply, "event": event}

    def state(self):
        """The state this connection is in."""
        return self._state

    def log(self):
        """Every transition this connection made, in order."""
        return tuple(self._events)
