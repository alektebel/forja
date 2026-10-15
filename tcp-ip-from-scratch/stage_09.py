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

TODO: implement `close`, `step_close`, `half_open` and `time_wait_over`.
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


class CloseError(ValueError):
    """A close this machine cannot make, named as what is wrong with it."""


def close(conn, now):
    """Send this connection's FIN, and move it to the state that puts it in."""
    raise NotImplementedError("stage 9: implement close()")


def step_close(conn, segment, now):
    """One segment in, one transition out, for a connection that is closing."""
    raise NotImplementedError("stage 9: implement step_close()")


def half_open(conn):
    """Whether exactly one direction of this connection is closed, and not both."""
    raise NotImplementedError("stage 9: implement half_open()")


def time_wait_over(conn, now):
    """Whether the wait this connection entered has run out at the tick `now`."""
    raise NotImplementedError("stage 9: implement time_wait_over()")
