"""TCP/IP From Scratch — stage 5: The handshake, and the state machine that has to know where it is.

A frame carries bytes and a datagram carries a protocol number; neither of them
carries a *conversation*. A conversation is a piece of state on both ends, and
the only thing that says which piece is the segment's own ports and its own
flags. That is why this stage is a state machine and not a parser with a reply:
`closed` has nothing to say, `listen` is waiting for exactly one kind of segment,
`syn_sent` is waiting for one acknowledgement of one number it chose itself, and
`established` is the only state that takes data.

The segment is 20 bytes of header and its payload, and everything in it is a
number the stage has to *produce*, not read: the sequence number it starts at (a
connection's ISN is not zero, or two connections collide), the acknowledgement
that counts the peer's SYN as one sequence number, and the window it offers. The
checksum is the part that surprises readers: it covers the segment **and a
twelve-byte pseudo-header** carrying the source and destination addresses — which
a segment does not carry. A header checksum is a fact about one header; a
transport checksum is a fact about two endpoints.

The other half of the stage is arithmetic that stops being arithmetic at 2**32.
`seq_add` wraps, and `seq_before` is the comparison a real stack needs: "is this
number behind that one?" is a question about the *distance forward*, not about
which int is smaller, and the two answers disagree exactly when the space wraps —
which is the one case a naive stack gets wrong and a busy connection reaches
every few gigabytes.

DESIGN DECISION — why is `step` a table and not a pile of `if`s?
Because the state is the thing being tested. A table says, for every state and
every kind of segment, what becomes true and what goes back; a pile of conditions
says what happens *if* this branch was reached, which is a different sentence
every time somebody adds a condition. The table is also the only way to answer
the question the stage's title asks: a segment that fits no row is not a segment
this connection agreed to, so it gets a refusal and the state does not move.

DESIGN DECISION — why does a rejected segment leave the state alone, and why is
RST never answered with RST?
Because a refusal is information about one segment, not about the connection. If
a rejected segment moved the state, the *next* segment would be judged against a
state that never existed, which is how a stack convinces itself a handshake
happened. And an RST answering an RST is two stacks resetting each other on a
loop that no timer in this course can break.

DESIGN DECISION — why does `pack` need the two addresses, when the segment does
not carry them?
Because the checksum covers them. `pack(segment, src, dst)` and
`unpack(data, src, dst)` take the addresses the pseudo-header is about, and
`unpack` reports `checksum_ok` as `None` when it was not given them: a segment
whose checksum was never checked is not a segment that checked out, and a stage
that answered `True` without the addresses would be a stage that accepts
anything. The alternative — carrying the addresses inside the segment dict — would
make a segment something a segment is not.

DESIGN DECISION — why is `seq_before` written as it is, when `<` looks right?
Because `<` compares two ints and the sequence space is a ring. The distance
forward from `a` to `b` is `(b - a) mod 2**32`, and `a` is behind `b` exactly when
that distance is less than half the space; at 2**32 - 1 the next number is 1, and
`2**32 - 1 < 1` is `False`. Every test that never wraps passes with `<`, and the
wrap is the only case this function exists for.

DESIGN DECISION — why does the check read `.log()` instead of the reply?
Because the reply is what the caller would send, and the log is what this
connection decided — including the decisions whose reply is `None`. A transition
that sent nothing and a transition that never happened are the same silence in
the reply and two different records in the log, and the state a connection is in
is exactly what a check has to be able to prove.

    TCP_HEADER    the 20 bytes of a header with no options
    TCP_OFFSET    the data offset that says "no options", as a nibble
    SEQ_MAX       the sequence space; SEQ_HALF is half of it, where "behind"
                  stops having an answer
    WINDOW_MAX    the most a 16-bit window field can say
    FIN SYN RST PSH ACK   the six flag bits, in the order the header lists them
    STATES        the five states this machine has
    WELL_KNOWN    the three ports a name stands for
    flags_text    a flag word as the words the header's own order gives
    pack          the header and payload, with the pseudo-header checksum
    unpack        the segment's eight facts, refusing what cannot be a segment
    seq_add       the modular sum
    seq_before    the modular comparison, the wrap included
    initial_seq   the sequence number a seed stands for
    Connection    one end of a connection: its port, its peer, its state and the
                  transitions it can prove it made

`TcpError` is the family, and every refusal names the offender: the number nobody
knows, the name nobody knows, the state nobody has, the dict that is not a
segment, the port that is not this connection's, the ack bit with a zero
acknowledgement.

TODO: implement `flags_text`, `pack`, `unpack`, `seq_add`, `seq_before`,
`initial_seq` and every method of `Connection`.
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


class TcpError(ValueError):
    """A segment this stack cannot build or read, named as what is wrong with it."""


def flags_text(flags):
    """`"SYN,ACK"` — the flags that are set, named in the header's own order.

    The vocabulary is closed and the order is fixed, because a check compares a
    transition's flags to a string; a flag bit nobody has raises, naming it.
    """
    raise NotImplementedError("stage 5: implement flags_text()")


def pack(segment, src=None, dst=None):
    """The 20-byte header and its payload, with the pseudo-header checksum.

    `segment` is the seven fields of `_SEGMENT_KEYS`'s shape; `src` and `dst` are
    the two addresses the checksum is about, and without both of them nothing can
    be packed, because the checksum covers bytes the segment does not carry.
    """
    raise NotImplementedError("stage 5: implement pack()")


def unpack(data, src=None, dst=None):
    """The segment's eight facts, refusing what cannot be a segment.

    `{"src_port", "dst_port", "seq", "ack", "flags", "window", "payload",
    "checksum_ok"}` — `flags` as the flag word, `payload` as everything after the
    header. `data` shorter than `TCP_HEADER`, a data offset that is not
    `TCP_OFFSET` and a zero port raise; the checksum is *reported*: `False` when
    the twelve pseudo-header bytes made from `src`/`dst` do not check out, and
    `None` when no addresses were handed over to check it against.
    """
    raise NotImplementedError("stage 5: implement unpack()")


def seq_add(seq, n):
    """`seq + n` in the modular sequence space: the wrap is the arithmetic."""
    raise NotImplementedError("stage 5: implement seq_add()")


def seq_before(a, b):
    """Whether `a` is behind `b` in the modular sequence space, wrap included."""
    raise NotImplementedError("stage 5: implement seq_before()")


def initial_seq(seed):
    """The sequence number a connection seeded with `seed` starts at.

    Deterministic, in the whole 32-bit space, and never the seed itself: two
    connections that picked the same small number would be two connections a peer
    cannot tell apart. A seed that is not an int raises, naming it.
    """
    raise NotImplementedError("stage 5: implement initial_seq()")


class Connection:
    """One end of a connection: a port, a peer, a state, and its own log.

    A `Connection` has no wire and no clock of its own: `step(segment, now)` is
    handed a segment dict and the tick it happened at, and returns the decision
    the caller packs and sends.
    """

    def __init__(self, local_port, local_ip=None, remote=None, state="closed",
                 seed=0, window=WINDOW_MAX):
        """A connection on `local_port`, in `state`, whose ISN is `initial_seq(seed)`.

        `local_ip` and `remote` (an `(address, port)` pair) are optional and are
        what a caller that knows them should hand over; the local port may be a
        number or a name from `WELL_KNOWN`, and an unknown port, an unknown state
        name, a seed that is not an int and a window outside `0..WINDOW_MAX` all
        raise, naming the offender.
        """
        raise NotImplementedError("stage 5: implement Connection.__init__()")

    def open(self, remote_ip, remote_port):
        """Active open: `{"state", "reply", "event"}` with the SYN to send.

        Only a closed connection opens; the state becomes `syn_sent`, the peer is
        remembered, and the reply is this side's SYN carrying this side's ISN.
        """
        raise NotImplementedError("stage 5: implement Connection.open()")

    def listen(self):
        """Passive open: `{"state", "reply", "event"}` with no reply.

        Only a closed connection listens; the state becomes `listen`, and the SYN
        this side will answer with is the one `step` builds when it arrives.
        """
        raise NotImplementedError("stage 5: implement Connection.listen()")

    def step(self, segment, now=None):
        """One segment in, one decision out: `{"state", "reply", "event"}`.

        The decision table is the stage: `listen` answers a SYN with SYN,ACK and
        its own ISN; `syn_sent` completes on the SYN,ACK that acknowledges its ISN
        and is refused by RST; `syn_received` completes on that acknowledgement;
        `established` acknowledges a payload and answers a duplicate SYN; and a
        segment that fits no row of the state it arrived in gets RST — except an
        RST, which gets silence — with the state left exactly where it was. `now`
        is the tick the transition is recorded at.
        """
        raise NotImplementedError("stage 5: implement Connection.step()")

    def state(self):
        """The state this connection is in."""
        raise NotImplementedError("stage 5: implement Connection.state()")

    def log(self):
        """Every transition this connection made, in order, as tuples."""
        raise NotImplementedError("stage 5: implement Connection.log()")
