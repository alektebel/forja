"""TCP/IP From Scratch — stage 6: The window, and the acknowledgement that covers everything behind it.

See `stage_06.py` for the surface and the design decisions; this is the receiver
that decides and the sender that is allowed to.
"""

import stage_05

#: The most one segment of this course carries. Eight bytes is small on purpose:
#: a window of eight is one segment and a window of twenty-four is three, so a
#: check can count what is in flight instead of estimating it.
MSS = 8

#: The seven fields stage 5 froze a segment to. A receiver's segment is a
#: segment: the window is a fact about a *connection*, not about a wire, and
#: neither class in this stage owns one.
_SEGMENT_KEYS = ("src_port", "dst_port", "seq", "ack", "flags", "window", "payload")


class WindowError(ValueError):
    """A segment or a window this stage cannot honour, named as what is wrong."""


# ---- the small conversions every entry point shares -----------------------

def _int(value, what):
    """An int, or a refusal naming what was given instead."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise WindowError("%s is an int, not %r" % (what, value))
    return value


def _count(value, what, low=0, high=None):
    """An int inside its range, or a refusal naming the offender."""
    number = _int(value, what)
    if number < low:
        raise WindowError("%s is %d, and the least it can be is %d"
                          % (what, number, low))
    if high is not None and number > high:
        raise WindowError("%s is %d, and the most it can be is %d"
                          % (what, number, high))
    return number


def _port(value, what):
    """A port number, or a refusal naming what was given."""
    number = _int(value, what)
    if number < 1 or number > stage_05.WINDOW_MAX:
        raise WindowError("%s is a port 1..%d, not %d"
                          % (what, stage_05.WINDOW_MAX, number))
    return number


def _segment(segment):
    """The seven fields stage 5 froze, or a refusal naming the one that is wrong."""
    if not isinstance(segment, dict):
        raise WindowError("a segment is a dict of its fields, not %r"
                          % (type(segment).__name__,))
    for key in _SEGMENT_KEYS:
        if key not in segment:
            raise WindowError("a segment has a %r field, and this one does not: %r"
                              % (key, sorted(segment)))
    _int(segment["seq"], "a segment's seq")
    if not isinstance(segment["payload"], bytes):
        raise WindowError("a segment's payload is bytes, not %r"
                          % (type(segment["payload"]).__name__,))
    return segment


# ---- the receiver ---------------------------------------------------------

class Receiver:
    """The other end of a stream: what arrived, what is waiting, what is owed.

    A `Receiver` owns no wire: `accept(segment)` is handed a segment and returns
    the acknowledgement, and the caller is the one that sends it.
    """

    def __init__(self, local_port, capacity=8, mss=MSS):
        """A receiver on `local_port` with `capacity` bytes of window."""
        self._local_port = _port(local_port, "the local port")
        self._mss = _count(mss, "the mss", 1)
        self._capacity = _count(capacity, "the capacity")
        if self._capacity < self._mss:
            raise WindowError("a receiver's capacity is at least one mss: %d is "
                              "below %d" % (self._capacity, self._mss))
        self._next = None
        self._buffered = []
        self._stream = b""
        self._events = []

    def _flush(self):
        """Hand up everything the buffer now holds contiguously; its length."""
        handed = 0
        while True:
            found = None
            for held in self._buffered:
                if held[0] == self._next:
                    found = held
                    break
            if found is None:
                return handed
            self._buffered.remove(found)
            self._stream += found[1]
            handed += len(found[1])
            self._next = stage_05.seq_add(self._next, len(found[1]))

    def accept(self, segment):
        """`{"acked", "buffered", "delivered", "window"}` for one segment in.

        `acked` is always an int and always the next expected sequence number:
        a segment at the front of the stream is appended and everything now
        contiguous behind it is covered by the one number; a segment ahead of the
        front is buffered (out of order is a wait, not an error); a segment the
        receiver already has is acknowledged again with the same number and not
        stored twice; and a segment that does not fit the window is acknowledged
        with the current number and dropped.
        """
        seg = _segment(segment)
        payload = seg["payload"]
        if len(payload) > self._capacity:
            raise WindowError("a segment's payload is at most the window, %d "
                              "bytes, not %d" % (self._capacity, len(payload)))
        if self._next is None:
            self._next = seg["seq"]
        seq = seg["seq"]
        handed = 0
        if seq == self._next:
            self._stream += payload
            handed += len(payload)
            self._next = stage_05.seq_add(self._next, len(payload))
            handed += self._flush()
            event = "delivered"
        elif payload and stage_05.seq_before(self._next, seq):
            if any(held_seq == seq for held_seq, _ in self._buffered):
                event = "repeat"
            elif len(payload) > self.window():
                event = "refused"
            else:
                self._buffered.append((seq, payload))
                event = "buffered"
        else:
            event = "repeat"
        self._events.append({"seq": seq, "length": len(payload), "event": event,
                             "acked": self._next})
        return {"acked": self._next, "buffered": len(self._buffered),
                "delivered": handed, "window": self.window()}

    def window(self):
        """The bytes this receiver is still willing to hold, in bytes."""
        held = sum(len(payload) for _, payload in self._buffered)
        return self._capacity - held

    def buffered(self):
        """The segments held out of order, as `(seq, payload)`, in order."""
        return tuple(sorted(self._buffered, key=lambda held: held[0]))

    def delivered(self):
        """The stream handed up so far, in order."""
        return self._stream

    def log(self):
        """Every decision this receiver made, in order, as dicts."""
        return tuple(self._events)


# ---- the sender -----------------------------------------------------------

class Sender:
    """This end of a stream: what may go out now, and what is still unacknowledged.

    A `Sender` owns no wire either: `queue` says how a `bytes` payload is cut
    into segments, `next_segments` says which of them the window allows out, and
    `acknowledge` is the only thing that moves the window forward.
    """

    def __init__(self, local_port, remote_port, iss=0, window=8, mss=MSS):
        """A sender from `local_port` to `remote_port`, with `window` bytes."""
        self._local_port = _port(local_port, "the local port")
        self._remote_port = _port(remote_port, "the remote port")
        self._iss = _int(iss, "an initial sequence number")
        self._mss = _count(mss, "the mss", 1)
        self._window = _count(window, "the window", 0, stage_05.WINDOW_MAX)
        self._next = stage_05.seq_add(self._iss, 0)
        self._pending = []
        self._flight = []
        self._events = []

    def _cut(self, payload):
        """One segment of the queue, at the sequence number it will be sent at."""
        segment = {"src_port": self._local_port, "dst_port": self._remote_port,
                   "seq": self._next, "ack": 0, "flags": stage_05.PSH,
                   "window": self._window, "payload": payload}
        self._next = stage_05.seq_add(self._next, len(payload))
        self._pending.append(segment)
        return segment

    def queue(self, data):
        """The `mss`-sized segments `data` implies, the last one short."""
        if not isinstance(data, bytes):
            raise WindowError("a payload is bytes, not %r" % (type(data).__name__,))
        queued = []
        for start in range(0, len(data), self._mss):
            queued.append(self._cut(data[start:start + self._mss]))
        self._record("queue", len(queued), len(data))
        return tuple(queued)

    def next_segments(self, count):
        """At most `count` segments that fit in the window, in order.

        A segment that does not fit the window the peer reported does not go out
        and does not hold back the queue behind it: it stops this call, because
        the queue is in sequence order and the window is a bytes budget, not a
        promise about which segment goes next.
        """
        number = _count(count, "a count", 0)
        out = []
        for segment in list(self._pending):
            if len(out) >= number:
                break
            if len(segment["payload"]) > self._window - self.in_flight():
                break
            self._pending.remove(segment)
            self._flight.append((segment["seq"], segment["payload"]))
            out.append(segment)
        self._record("next", len(out),
                     sum(len(segment["payload"]) for segment in out))
        return tuple(out)

    def acknowledge(self, ack):
        """`{"acked", "again", "in_flight"}` — the cumulative acknowledgement.

        Everything whose last byte is at or before `ack` leaves the in-flight
        table; `"acked"` is the number of bytes *this* acknowledgement moved, so
        an acknowledgement that moves nothing is `"again": True` — a duplicate
        acknowledgement is a signal, not a progress report.
        """
        number = _int(ack, "an acknowledgement")
        if number != self._next and stage_05.seq_before(self._next, number):
            raise WindowError("this sender has sent up to %d, not %d"
                              % (self._next, number))
        moved = 0
        gone = 0
        kept = []
        for seq, payload in self._flight:
            if stage_05.seq_before(stage_05.seq_add(seq, len(payload)), number):
                moved += len(payload)
                gone += 1
            else:
                kept.append((seq, payload))
        self._flight = kept
        self._record("ack", gone, moved)
        return {"acked": moved, "again": moved == 0, "in_flight": self.in_flight()}

    def in_flight(self):
        """The bytes handed over and not yet acknowledged."""
        return sum(len(payload) for _, payload in self._flight)

    def sent(self):
        """`(seq, length)` for every segment in flight, in order."""
        return tuple((seq, len(payload)) for seq, payload in self._flight)

    def _record(self, event, segments, count):
        """One decision, as it happened."""
        self._events.append({"event": event, "segments": segments, "bytes": count})

    def log(self):
        """Every decision this sender made, in order, as dicts."""
        return tuple(self._events)
