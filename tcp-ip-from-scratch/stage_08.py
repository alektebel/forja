"""TCP/IP From Scratch — stage 8: The retransmission, and the timer that doubles.

The window of the stage before says how much may be in flight; it says nothing
about what to do when some of it never arrives. That is a timer, and the shape of
this stage is that a connection keeps exactly *one* of them — for the oldest
segment still unacknowledged. A timer per segment would give every segment its
own deadline, they would fire out of order, and the doubling would be lost in the
noise; one timer for the oldest segment makes the backoff a number a check can
count.

The acknowledgement is what stops it, and only an acknowledgement that *covers*
the segment the timer was armed for stops it: a duplicate acknowledgement moves
nothing, and a timer that restarted on every acknowledgement would guarantee the
oldest segment was never retransmitted. A connection that has tried
`MAX_TRIES` times does not raise — it *gives up*, which is an outcome to report.

`run` is the proof: a real `Wire`, a real `Host`, a payload, and a peer scripted
here (the world's peers are passive). It drives the payload across the wire tick
by tick and reports what happened, reading the wire's own log for the frames that
were dropped and delivered rather than trusting its own count of them.

DESIGN DECISION — why does the timeout double instead of staying fixed?
Because the thing that is not arriving is, most likely, the thing that is
congested: a fixed timeout sends the same retransmission again into the same
full link, and again, and the link stays full. Doubling is the smallest change
that backs off, and the cap at `MAX_TIMEOUT` keeps the wait from growing past a
useful horizon. The stage exists because the arithmetic of the backoff is
observable — the due ticks are 2, 6, 14, 30 — and a stack that skipped the
doubling would look correct everywhere its numbers are not counted.

DESIGN DECISION — why one timer for the oldest segment rather than one per
segment?
Because an acknowledgement is cumulative. One number covers everything before
it, so the only segment whose fate is still unknown *and* whose retransmission
would be useful is the oldest one: once it is acknowledged, everything behind it
is too, and the timer can be armed for the next oldest with no loss. A stack with
a timer per segment retransmits segments already acknowledged and floods the link
it is trying to help.

DESIGN DECISION — why does a connection that runs out of tries report `expired`
instead of raising?
Because giving up is a decision about a peer, and this course returns decisions
about peers as data. An exception would make a caller's control flow the place
the outcome is decided, and `run`'s whole job is to report the outcome — that
the payload never arrived — as one more number in its answer.

DESIGN DECISION — why does `run` read the wire's log instead of counting what it
sent?
Because a stack that counts its own sends cannot tell a segment the link dropped
from one that crossed and was lost later, and the two call for different
behaviour. The wire is the tie-breaker this course grades against: `dropped` is
`Wire`'s number, `delivered` is `Wire`'s number, and a `run` that reports its own
belief is a ledger that stops at the last retransmission.

    Timer          one retransmission timer, for the oldest unacknowledged segment
    Reliable       a sender and that timer, together
    run            the little session that proves the doubling on a real wire
    RetransmitError the family every refusal here belongs to

`Timer.fired` answers `{"seq", "tries", "timeout"}` while the tries are not
spent and `{"expired": True}` when they are; `Reliable.tick` answers
`{"resent", "expired", "due"}`; `run` answers
`{"sent", "resent", "acked", "ticks", "delivered", "dropped", "expired"}`.

TODO: implement `Timer`, `Reliable` and `run`.
"""

INITIAL_TIMEOUT = 2
MAX_TIMEOUT = 16
MAX_TRIES = 4
BACKOFF = 2


class RetransmitError(ValueError):
    """A timer or a connection this stage cannot honour, named as what is wrong."""


class Timer:
    """One retransmission timer, for the oldest segment still unacknowledged."""

    def __init__(self, timeout=INITIAL_TIMEOUT, backoff=BACKOFF, tries=MAX_TRIES):
        """A timer that waits `timeout` ticks, doubles by `backoff`, tries `tries`."""
        raise NotImplementedError("stage 8: implement Timer.__init__()")

    def start(self, seq, now):
        """Arm the timer for the segment that begins at `seq`, from `now`."""
        raise NotImplementedError("stage 8: implement Timer.start()")

    def due(self, now):
        """The tick this timer fires at, or `None` when it is not armed."""
        raise NotImplementedError("stage 8: implement Timer.due()")

    def fired(self, now):
        """The timer went off: the segment to send again, or `{"expired": True}`."""
        raise NotImplementedError("stage 8: implement Timer.fired()")

    def acknowledged(self, ack, now):
        """An acknowledgement arrived: `{"stopped", "again"}`."""
        raise NotImplementedError("stage 8: implement Timer.acknowledged()")

    def log(self):
        """Every event this timer saw, in order, as dicts."""
        raise NotImplementedError("stage 8: implement Timer.log()")


class Reliable:
    """A sender plus the one timer that decides when its oldest segment is late."""

    def __init__(self, sender, timer, peer):
        """A stage 6 sender, its timer, and the thing a segment goes out through."""
        raise NotImplementedError("stage 8: implement Reliable.__init__()")

    def send(self, data, now):
        """Queue `data`, put what the window allows in flight, arm the timer."""
        raise NotImplementedError("stage 8: implement Reliable.send()")

    def received(self, segment, now):
        """An acknowledgement arrived: move the window, stop or keep the timer."""
        raise NotImplementedError("stage 8: implement Reliable.received()")

    def tick(self, now):
        """One tick of the clock: fire the timer, then push what now fits."""
        raise NotImplementedError("stage 8: implement Reliable.tick()")

    def give_up(self, now):
        """Whether the tries are spent and this connection has stopped trying."""
        raise NotImplementedError("stage 8: implement Reliable.give_up()")

    def log(self):
        """Every decision this connection made, in order, as dicts."""
        raise NotImplementedError("stage 8: implement Reliable.log()")


def run(wire, host, peer_mac, peer_ip, data, *, rules=None, max_ticks=64,
        wire_rules=None):
    """Drive one payload across one wire and report what the wire did."""
    raise NotImplementedError("stage 8: implement run()")
