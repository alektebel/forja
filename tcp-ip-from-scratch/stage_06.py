"""TCP/IP From Scratch — stage 6: The window, and the acknowledgement that covers everything behind it.

The handshake of the stage before says two stacks agree to talk; it says nothing
about how much either of them can take. That is the window, and it is the first
number in this course that is a *decision* rather than a field: the receiver
looks at what it has already taken, what it is holding out of order, and what it
is still willing to hold, and says the one number that describes all three; the
sender looks at that number and may put no more than it in flight.

The acknowledgement is the other half, and it is cumulative. One number covers
every byte before it — which is why an out-of-order segment is not an error and
not a hole in the stream: it is held, and the acknowledgement stays where the
*contiguous* stream ends. There are three things a receiver can do with a
segment and each is a different sentence: a segment at the front is the stream,
a segment ahead of the front is a wait, and a segment it already has is
acknowledged again with the same number and stored exactly once. A receiver that
acknowledges the last segment it *saw* rather than the last one it can *prove*
is contiguous hands the peer a number that skips the hole, and the bytes in the
hole are lost with nobody noticing.

Neither class here owns a wire. The sender says what may go out now; the receiver
says what arrived; the caller is the one that puts the bytes on the link and
brings them back. That is what keeps this stage a decision table rather than a
simulator, and it is why `MSS` is eight bytes: small enough that a window of
eight is one segment and twenty-four is three, so a check can count segments
instead of estimating them.

DESIGN DECISION — why does the receiver learn where the stream begins from its
first segment, when the sender is told its own initial sequence number?
Because the sender chose its number and the receiver never did. `Sender` takes an
`iss`; `Receiver` cannot, so the only place a receiver can find the beginning of
the stream is the first segment that arrives — and a receiver that expected zero
would hand nothing up after a handshake in which the peer picked any other
number. The first segment, and only the first, defines the front; from there on
the front moves by the arithmetic of contiguous bytes.

DESIGN DECISION — why is a duplicate segment acknowledged again instead of
dropped silently?
Because the peer cannot tell silence from a lost acknowledgement, and the
duplicate is usually *caused* by that: a peer whose acknowledgement was lost
retransmits, and a receiver that says nothing makes it retransmit forever. So a
segment the receiver already has is acknowledged with the number it already gave
— the same number, because nothing moved — and is not stored twice, because the
stream would then contain those bytes twice and the number would not admit it.

DESIGN DECISION — why is the window measured in bytes and why does it shrink?
Because the field on the wire is bytes and the resource behind it is bytes, and
because a receiver that reports its capacity instead of its free space promises
space it does not have. After one eight-byte segment is held out of order in a
capacity of eight, the window is zero: the peer may send nothing more until the
gap is filled, and that zero is the only thing standing between this receiver and
an unbounded buffer.

DESIGN DECISION — why does the sender count what *this* acknowledgement moved
rather than the total acknowledged?
Because a duplicate acknowledgement is a signal. `"acked"` is how far this
acknowledgement moved the window and `"again"` is `True` when it moved nothing,
which is the only way a caller can see the peer asking for a retransmission
without re-deriving it from two numbers it kept itself. The total is a number the
sender can add up whenever it wants; the movement is a fact about one call.

DESIGN DECISION — why does an acknowledgement for a sequence number above
everything sent raise, when a bad checksum does not?
Because they are different kinds of fact. A peer's bytes that do not check out
are a verdict about content, and stage 5 reports them; an acknowledgement of a
segment this sender never sent is not a peer's opinion, it is a caller's mistake
— the in-flight table cannot be searched for something that was never in it.

    MSS           the most one segment carries; eight bytes on purpose
    Receiver      what arrived, what is waiting, what is owed
    Sender        what may go out now, and what is still unacknowledged
    WindowError   the family every refusal here belongs to

`Receiver.accept` returns `{"acked", "buffered", "delivered", "window"}` and
`Sender.acknowledge` returns `{"acked", "again", "in_flight"}`; both classes keep
a log of the decisions they made, in order, as dicts.

TODO: implement every method of `Receiver` and `Sender`.
"""

import stage_05

MSS = 8


class WindowError(ValueError):
    """A segment or a window this stage cannot honour, named as what is wrong."""


class Receiver:
    """The other end of a stream: what arrived, what is waiting, what is owed.

    A `Receiver` owns no wire: `accept(segment)` is handed a segment and returns
    the acknowledgement, and the caller is the one that sends it.
    """

    def __init__(self, local_port, capacity=8, mss=MSS):
        """A receiver on `local_port` with `capacity` bytes of window.

        The local port is a port; `mss` is at least one byte; and a capacity
        below one `mss` is a refusal, because a window that cannot hold the
        smallest segment the peer can send is not a window.
        """
        raise NotImplementedError("stage 6: implement Receiver.__init__()")

    def accept(self, segment):
        """`{"acked", "buffered", "delivered", "window"}` for one segment in.

        `acked` is always an int, and always the next expected sequence number: a
        segment at the front is appended and everything now contiguous behind it
        is covered by the one number, a segment ahead of the front is buffered (a
        wait, not an error), a segment the receiver already has is acknowledged
        again with the same number and not stored twice, and a segment that does
        not fit the window is acknowledged with the current number and dropped.
        `"buffered"` is how many segments are held, `"delivered"` how many bytes
        this call handed up, and `"window"` the bytes still free.
        """
        raise NotImplementedError("stage 6: implement Receiver.accept()")

    def window(self):
        """The bytes this receiver is still willing to hold."""
        raise NotImplementedError("stage 6: implement Receiver.window()")

    def buffered(self):
        """The segments held out of order, as `(seq, payload)`, in order."""
        raise NotImplementedError("stage 6: implement Receiver.buffered()")

    def delivered(self):
        """The stream handed up so far, in order."""
        raise NotImplementedError("stage 6: implement Receiver.delivered()")

    def log(self):
        """Every decision this receiver made, in order, as dicts."""
        raise NotImplementedError("stage 6: implement Receiver.log()")


class Sender:
    """This end of a stream: what may go out now, and what is unacknowledged.

    A `Sender` owns no wire either: `queue` says how a `bytes` payload is cut
    into segments, `next_segments` says which of them the window allows out, and
    `acknowledge` is the only thing that moves the window forward.
    """

    def __init__(self, local_port, remote_port, iss=0, window=8, mss=MSS):
        """A sender from `local_port` to `remote_port`, with `window` bytes.

        Both ports are ports, `iss` is a sequence number, `mss` is at least one
        byte, and a window that is negative or that the 16-bit field cannot hold
        raises, naming it.
        """
        raise NotImplementedError("stage 6: implement Sender.__init__()")

    def queue(self, data):
        """The `mss`-sized segments `data` implies, the last one short.

        Each segment carries the seven fields `stage_05` froze, at the sequence
        number it will be sent at, and the queue is what `next_segments` hands
        out from. A payload that is not `bytes` raises, naming it.
        """
        raise NotImplementedError("stage 6: implement Sender.queue()")

    def next_segments(self, count):
        """At most `count` segments that fit in the window, in order.

        A segment that does not fit the window does not go out and stops the
        call, because the queue is in sequence order and the window is a bytes
        budget: a sender that put more in flight than the window allows would be
        sending into a buffer the peer said it does not have.
        """
        raise NotImplementedError("stage 6: implement Sender.next_segments()")

    def acknowledge(self, ack):
        """`{"acked", "again", "in_flight"}` — the cumulative acknowledgement.

        Everything whose last byte is at or before `ack` leaves the in-flight
        table; `"acked"` is the number of bytes this acknowledgement moved, so an
        acknowledgement that moves nothing is `"again": True`. An acknowledgement
        of a sequence number this sender never reached raises, naming it.
        """
        raise NotImplementedError("stage 6: implement Sender.acknowledge()")

    def in_flight(self):
        """The bytes handed over and not yet acknowledged."""
        raise NotImplementedError("stage 6: implement Sender.in_flight()")

    def sent(self):
        """`(seq, length)` for every segment in flight, in order."""
        raise NotImplementedError("stage 6: implement Sender.sent()")

    def log(self):
        """Every decision this sender made, in order, as dicts."""
        raise NotImplementedError("stage 6: implement Sender.log()")
