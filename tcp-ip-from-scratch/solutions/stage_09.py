"""TCP/IP From Scratch — stage 9: The close, and the state you wait in.

A connection that never closes holds a socket the other side has already
released, and the half of TCP that ends a stream is not a shorter version of the
half that opens one: it is a second state machine over the same connection. The
handshake of stage 5 knows five states and none of them is *closing*; the moment
one side decides to stop sending, the two ends walk a different ladder —
`fin_wait_1`, `fin_wait_2`, `closing`, `time_wait` on the side that closed first,
`close_wait` and `last_ack` on the side that was told — and every step of it is a
segment the other end has to answer.

The two questions this stage exists for are the two a real stack answers with a
*state* rather than with an `if`. `fin_wait_2` is neither open nor gone: this
side has stopped sending and the peer has not, so a segment carrying a payload is
still the peer's stream arriving and is still acknowledged — that is what
half-open means. And `time_wait` is not a sleep: it is a state with a deadline,
entered at a tick, left by a *question* (`time_wait_over(conn, now)`), and a
connection in it answers a fresh `SYN` for the same pair with a reset, because
the peer that has not yet learned about the close is exactly the peer a fresh
`SYN` comes from.

Nothing here runs: `close` hands back the FIN to put on the wire, `step_close`
takes a segment and returns what it decided, and time passes only when the caller
says which tick it is. Every transition is reported as an event from a closed
vocabulary — the state's own name, or `"rejected"` — so a caller reads the
transition instead of guessing it from the segment that came back.

DESIGN DECISION — why is closing a second machine over the same `Connection`
instead of more rows in the handshake's table?
Because the two tables answer different questions. The handshake's rows are about
*agreeing* on a connection, and a `FIN` in any of its five states fits no row at
all; the close's rows are about *ending* one, and an opening `SYN` fits none of
theirs. Folding them together would make every state carry a ruling about both,
and the state a connection is in is exactly what this stage is about. The
`Connection` is shared, so the port it answers on, its log and its sequence space
are the same objects throughout; only the table that reads them changes.

DESIGN DECISION — why is a payload still taken in `fin_wait_2`, and refused the
moment `close` returns?
Because the FIN closes *this* side's sending direction and nothing else, and
`fin_wait_1` is the window before the peer has acknowledged it. Until that
acknowledgement arrives the close is a claim this side has made and the peer has
not answered, so this stage takes nothing new on it — a segment arriving in
`fin_wait_1` is reported as `"rejected"` and the peer is left to retransmit once
the state settles. Once the acknowledgement is in, the connection is genuinely
half-open — one direction shut, the other still the peer's — and its data is
still the peer's stream, still acknowledged with a number that covers exactly
what arrived. A side that goes on taking data after its own close is complete is
the bug this stage names.

DESIGN DECISION — why is `TIME_WAIT` a question about a tick rather than a
timer?
Because a timer is a process and this course has none: `time_wait_over(conn,
now)` asks whether the tick it was handed is at or past the tick `time_wait` was
entered plus `TIME_WAIT_TICKS`, and nothing sleeps. The tick the state was
entered is the one that matters, and it is the state's own entry, not the tick
the connection was created at, which is what measuring from zero would say: a
connection that lingered in `fin_wait_1` would then wait less than the state it
is in promises.

DESIGN DECISION — why is a fresh `SYN` in `time_wait` answered with a reset?
Because the only peer that sends a fresh `SYN` for a pair this side is still
winding down is a peer that has not yet learned about the close, and answering it
with a new handshake would let the old connection's segments be read against the
new one's sequence space. So the connection says no — a bare `RST`, from its own
next sequence number — until the wait is over, and only then accepts the `SYN`
and hands the pair back to the handshake as `syn_received`.

DESIGN DECISION — why does the FIN carry no payload and no acknowledgement?
Because a segment does not carry the stream's history and this stage does not
keep one: the sequence number a FIN would acknowledge is a fact about the bytes
the *peer* sent, and that belongs to stage 6's receiver rather than to a machine
whose whole subject is the state. What the FIN does carry is the one thing the
close is about — its own sequence number, which consumes one of the sequence
space's numbers exactly as a `SYN` does, and that one is counted by both ends:
the acknowledgement of a FIN is its sequence number plus one.

    TIME_WAIT_TICKS  how long a connection waits in `time_wait`, in ticks
    CLOSE_STATES     the seven states of a close, in the ladder's own order
    CloseError       the family every refusal here belongs to
    close            the FIN, and the state it puts this side in
    step_close       one segment in, one transition out
    half_open        whether exactly one direction of this connection is closed
    time_wait_over   whether the wait the state entered has run out at a tick

`close` and `step_close` answer `{"state", "segment", "event"}` — the state the
connection is in now, the segment to send (or `None`) and the name of the
transition, so a caller reads the same three facts in both directions.

TODO: implement `CloseError`, `close`, `step_close`, `half_open` and
`time_wait_over`.
"""

import stage_05

from stage_05 import ACK, FIN, RST, SYN, seq_add

#: How long a connection holds `time_wait`: eight ticks, measured from the tick
#: the state was entered, because the wait is a state with a deadline rather
#: than a timer that runs.
TIME_WAIT_TICKS = 8

#: The seven states of a close, in the ladder's own order: the four the side
#: that closed first walks, the two the side that was told walks, and the one
#: both end in.
CLOSE_STATES = ("fin_wait_1", "fin_wait_2", "closing", "time_wait",
                "close_wait", "last_ack", "closed")

#: The states in which exactly one direction of the connection is closed: this
#: side's FIN has been acknowledged and the peer's has not (`fin_wait_2`), or
#: the peer's has arrived and this side's has not (`close_wait`). A payload
#: arriving in one of these is still the peer's stream and is still taken.
_HALF_OPEN = ("fin_wait_2", "close_wait")

#: The seven fields stage 5 froze a segment to, in the order the header carries
#: them. A segment is these seven facts and nothing else: the two addresses its
#: checksum is about are a fact about a datagram.
_SEGMENT_KEYS = ("src_port", "dst_port", "seq", "ack", "flags", "window", "payload")


class CloseError(ValueError):
    """A close this machine cannot make, named as what is wrong with it."""


# ---- the small conversions every entry point shares -----------------------

def _int(value, what):
    """An int, or a refusal naming what was given instead."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise CloseError("%s is an int, not %r" % (what, value))
    return value


def _tick(now):
    """A tick that has happened, or a refusal naming the one that has not."""
    if isinstance(now, bool) or not isinstance(now, int):
        raise CloseError("a tick is an int, not %r" % (now,))
    if now < 0:
        raise CloseError("a tick is 0 or later, not %d" % (now,))
    return now


def _segment(segment):
    """The seven fields stage 5 froze, or a refusal naming the one that is wrong."""
    if not isinstance(segment, dict):
        raise CloseError("a segment is a dict of its fields, not %r"
                         % (type(segment).__name__,))
    for key in _SEGMENT_KEYS:
        if key not in segment:
            raise CloseError("a segment has a %r field, and this one does not: %r"
                             % (key, sorted(segment)))
    for key in ("src_port", "dst_port", "seq", "ack", "flags", "window"):
        _int(segment[key], "a segment's %s" % (key,))
    if not isinstance(segment["payload"], bytes):
        raise CloseError("a segment's payload is bytes, not %r"
                         % (type(segment["payload"]).__name__,))
    if segment["flags"] & ACK and segment["ack"] == 0:
        raise CloseError("a segment with the ack bit set acknowledges something, "
                         "not %d" % (segment["ack"],))
    return segment


# ---- the segments this machine answers with -------------------------------

def _reply(conn, segment, flags, seq, ack=0):
    """A segment answering `segment`, on this connection's two ports."""
    return {"src_port": conn._local_port, "dst_port": segment["src_port"],
            "seq": seq, "ack": ack, "flags": flags, "window": conn._window,
            "payload": b""}


def _acknowledge(conn, segment):
    """The ACK that answers `segment`, counting the FIN it carries as one number."""
    return _reply(conn, segment, ACK, conn._next_seq(),
                  seq_add(segment["seq"], 1))


def _data_ack(conn, segment):
    """The ACK that covers the payload `segment` brought, and nothing after it."""
    return _reply(conn, segment, ACK, conn._next_seq(),
                  seq_add(segment["seq"], len(segment["payload"])))


def _fin(conn):
    """The FIN this side sends: its own next sequence number, and nothing else."""
    if conn._remote is None:
        raise CloseError("this connection has no peer, so there is nobody to "
                         "send a FIN to: %r" % (conn._remote,))
    return {"src_port": conn._local_port, "dst_port": conn._remote[1],
            "seq": conn._next_seq(), "ack": 0, "flags": FIN,
            "window": conn._window, "payload": b""}


# ---- the ledger -----------------------------------------------------------

def _move(conn, state, event, reply, now):
    """A transition that arrives somewhere: the state, its tick, and the log."""
    conn._state = state
    conn._close_now = now
    conn._log(state, event,
              "" if reply is None else stage_05.flags_text(reply["flags"]), now)
    return {"state": state, "segment": reply, "event": event}


def _stay(conn, event, reply, now):
    """A transition that answers and stays where it is: the state is not re-entered."""
    conn._log(conn._state, event,
              "" if reply is None else stage_05.flags_text(reply["flags"]), now)
    return {"state": conn._state, "segment": reply, "event": event}


def _reject(conn, reply, now):
    """A segment this state does not answer: the state stays, the tick is logged."""
    return _stay(conn, "rejected", reply, now)


# ---- the close machine ----------------------------------------------------

def close(conn, now):
    """Send this connection's FIN, and move it to the state that puts it in."""
    now = _tick(now)
    state = conn.state()
    if state == "closed":
        raise CloseError("close of a connection in state 'closed': it is already "
                         "closed")
    if state in CLOSE_STATES and state != "close_wait":
        raise CloseError("close of a connection in state %r: it is already "
                         "closing" % (state,))
    if state not in ("established", "close_wait"):
        raise CloseError("close of a connection in state %r: only an established "
                         "connection, or one whose peer has closed, closes"
                         % (state,))
    fin = _fin(conn)
    conn._fin_seq = fin["seq"]
    if state == "close_wait":
        return _move(conn, "last_ack", "last_ack", fin, now)
    return _move(conn, "fin_wait_1", "fin_wait_1", fin, now)


def step_close(conn, segment, now):
    """One segment in, one transition out, for a connection that is closing."""
    now = _tick(now)
    seg = _segment(segment)
    state = conn.state()
    if state == "closed":
        raise CloseError("a segment for a connection in state 'closed': there is "
                         "nothing left to move")
    if state != "established" and state not in CLOSE_STATES:
        raise CloseError("this connection is in state %r, which is not one this "
                         "machine closes" % (state,))
    if seg["dst_port"] != conn._local_port:
        raise CloseError("this connection answers on port %d, not %d"
                         % (conn._local_port, seg["dst_port"]))
    if conn._remote is not None and seg["src_port"] != conn._remote[1]:
        raise CloseError("this connection's peer is on port %d, not %d"
                         % (conn._remote[1], seg["src_port"]))
    flags = seg["flags"]

    if state == "established":
        if flags & FIN:
            return _move(conn, "close_wait", "close_wait", _acknowledge(conn, seg),
                         now)
        return _reject(conn, None, now)

    if state == "fin_wait_1":
        settled = flags & ACK and seg["ack"] == seq_add(conn._fin_seq, 1)
        if flags & FIN:
            if settled:
                return _move(conn, "time_wait", "time_wait", _acknowledge(conn, seg),
                             now)
            return _move(conn, "closing", "closing", _acknowledge(conn, seg), now)
        if settled:
            return _move(conn, "fin_wait_2", "fin_wait_2", None, now)
        return _reject(conn, None, now)

    if state == "fin_wait_2":
        if flags & FIN:
            return _move(conn, "time_wait", "time_wait", _acknowledge(conn, seg),
                         now)
        if seg["payload"]:
            return _stay(conn, "data", _data_ack(conn, seg), now)
        return _reject(conn, None, now)

    if state == "closing":
        if flags & ACK and seg["ack"] == seq_add(conn._fin_seq, 1):
            return _move(conn, "time_wait", "time_wait", None, now)
        return _reject(conn, None, now)

    if state == "close_wait":
        if seg["payload"]:
            return _stay(conn, "data", _data_ack(conn, seg), now)
        return _reject(conn, None, now)

    if state == "last_ack":
        if flags & ACK and seg["ack"] == seq_add(conn._fin_seq, 1):
            return _move(conn, "closed", "closed", None, now)
        return _reject(conn, None, now)

    # time_wait: the wait is a state, and a fresh SYN is a peer that has not
    # learned about the close yet.
    if flags & SYN:
        if time_wait_over(conn, now):
            return _move(conn, "syn_received", "syn_received",
                         _reply(conn, seg, SYN | ACK, conn._iss,
                                seq_add(seg["seq"], 1)), now)
        return _reject(conn, _reply(conn, seg, RST, conn._next_seq(), seg["ack"]),
                       now)
    return _reject(conn, None, now)


def half_open(conn):
    """Whether exactly one direction of this connection is closed, and not both."""
    return conn.state() in _HALF_OPEN


def time_wait_over(conn, now):
    """Whether the wait this connection entered has run out at the tick `now`."""
    now = _tick(now)
    state = conn.state()
    if state != "time_wait":
        raise CloseError("time_wait_over of a connection in state %r: only a "
                         "connection in time_wait is waiting" % (state,))
    return now >= conn._close_now + TIME_WAIT_TICKS
