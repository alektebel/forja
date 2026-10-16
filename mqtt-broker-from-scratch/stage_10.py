"""MQTT Broker From Scratch — stage 10: One scenario, twice, and the reader's verdict.

Nine stages have each answered one question about one packet. This one runs all
of them at once, on the world's transport, and then asks the only question that
cannot be answered by reading the code: is the broker's own account of what it did
true? A broker that believes it delivered a message the transport never carried
goes on believing it forever unless something compares the two accounts, and
nothing inside the broker can be that something — the trace it keeps and the
report it counts come from the same hand.

So the capstone is three accounts of one run. The first is the trace: every byte
the broker writes goes through `Trace.wrote` with the tick of the write, and
`read_frames` — stage 1's fixed header with stage 2's strings on top of it, the
reader the whole course has been building towards — reads that trace back with no
byte left over. A frame the reader refuses is a frame that should not have been
written. The second is the report: the thirteen counts of `REPORT_KEYS`,
recomputed from the trace, the sessions, the trie and the ledger whenever it is
asked for, never accumulated beside them. The third is the transport's own log,
which knows nothing of packets and cannot be talked into agreeing: `cross_check`
holds the numbers both accounts can state against one another and *names* the ones
that differ rather than resolving them.

A run is written as a scenario: a callable that builds its own transport, listens,
connects its clients, says their packets, and answers the broker it drove. That
shape is what makes the stage's last claim checkable — `replay` runs the scenario
again from nothing and answers the new run's bytes, and two replays of one
scenario that do not write identical bytes are proof that a `set`, an unordered
dict or a wall clock reached the wire, because a deterministic broker writing the
same packets twice has nothing else left to differ about.

    BROKER_KEYS                        the eleven fields of a run's state, in order
    REPORT_KEYS                        the thirteen counts a report carries, in order
    Trace.wrote(tick, data)            record a write at the tick it happened, answer the bytes
    Trace.frames()                     -> [(tick, bytes)], in the order they were written
    Trace.bytes()                      -> every byte the broker wrote, in order
    read_frames(data, pos=0)           -> ([(type, flags, body)], pos after the last frame)
    cross_check(report, transport)     -> {"agree": bool, "disagreements": [...]}
    replay(scenario)                   -> the bytes a fresh run of the scenario wrote
    Broker(transport, name="broker", grants=None)
    Broker.accepted()                  -> the streams that completed a CONNECT, in order
    Broker.receive(stream, data)       -> the frames written in answer to one arrival
    Broker.step(ticks=1)               -> the tick, after endings, deadlines and the flush
    Broker.report()                    -> REPORT_KEYS, counted from the trace and the sessions
    Broker.trace()                     -> the trace this broker wrote

`receive` hands back the bodies of the frames that answer the arrival being read,
and nothing else: a delivery routed to a second subscriber, a will, a re-send —
every frame the turn's caller is not the audience for — waits in its own stream's
outbound buffer and goes out on the broker's next `step`. A read that stops inside
a frame answers nothing and keeps the bytes, so the caller offers them again after
the next step and the frame is read once; a frame the course's reader refuses is
refused here, naming the bytes that arrived.

DESIGN DECISION — why is the trace read back rather than counted as it is written?
Because a counter and the thing it counts are one mistake away from disagreeing
forever. If the report were kept as running totals, every bug that wrote a frame
without counting it, or counted one it never wrote, would be invisible: the report
would be the broker's belief about itself, and a belief cannot be checked against
the thing believed. Reading the trace back with the course's own reader makes the
report a *measurement* of what was written, and it makes the reader itself part of
the test — a broker whose QoS 2 framebuilding is wrong writes a trace its own
reader refuses, and fails before any report is counted.

DESIGN DECISION — why does `cross_check` report disagreements instead of
resolving them?
Because there is nothing honest to resolve them with. The two accounts are not
the same code and cannot see the same facts: the transport knows bytes and streams
and nothing about sessions, filters or decisions, so the only keys worth comparing
are the ones both can state — the streams it opened, and the bytes it took towards
its clients. When those differ, one of the two is wrong and this function does not
know which; a resolver would have to pick, and picking the broker's own number
would make the check agree with the bug. So the answer is a verdict and a list of
name-and-both-numbers strings, and the caller decides what to do with a broker
whose account of itself is not its transport's account of it.

DESIGN DECISION — why does one turn write into two places — the caller's hand and
the stream's own buffer?
Because a turn has exactly one caller and many audiences. The frames that answer
the arrival being read go back to whoever offered those bytes, which is how a
client's own wire is kept in order without the broker stepping the clock; every
frame for anybody else has no wire to go to yet and waits for a `step` to carry
it. Writing both kinds into the caller's answer would put one client's delivery on
another client's wire, and a reader on the far end would then have to explain
bytes it was never meant to see — the mistake this whole course is written to
avoid, appearing in the capstone's own plumbing.

DESIGN DECISION — why must a scenario be a callable that answers the broker it
drove, and not a list of packets?
Because determinism has to be demonstrated, not promised. A scenario that rebuilds
its transport, its clients and its broker from nothing each time is the only shape
in which "the same bytes twice" is a real question: everything that could leak
across runs — a module-level cache, a dict that remembers its last iteration
order, a broker that kept a counter — is reset by construction, and `replay`
compares the two runs' writes. A scripted list of packets would prove the list is
stable, which nobody doubted, and would hide every one of those leaks.

DESIGN DECISION — why does a refused publish get no answer at all?
Because MQTT has no packet that says so. There is no "your PUBLISH was refused" in
the protocol, and a broker that invented one would be writing a byte a client
could not parse; the same silence that stage 9's ledger exists to compensate for.
So a refused publish is routed nowhere and stored nowhere, and the only trace that
it ever arrived is the line stage 9 wrote before the decision — a QoS 1 publish
gets no PUBACK, a QoS 2 publish gets no PUBREC, and the client is left to
retransmit until it gives up. The alternative, acknowledging a message that was
refused, would tell the client exactly the opposite of the truth.

TODO: implement `Trace`, `read_frames`, `cross_check`, `replay` and `Broker` in
this file: the trace with the tick of each write, the reader built from stage 1's
header, the report counted from that trace and the sessions, the cross-check
against the transport's log, and the whole broker running the scenario twice.
"""

import grants
import stage_01
import stage_02
import stage_03
import stage_04
import stage_05
import stage_06
import stage_07
import stage_08
import stage_09
import streams

BROKER_KEYS = ("client", "stream", "buffers", "sessions", "trie", "retained",
               "inflight", "queued", "decisions", "trace", "tick")

REPORT_KEYS = ("streams", "sessions", "subscriptions", "deliveries", "qos0",
               "qos1", "qos2", "redeliveries", "queued", "dropped", "refusals",
               "frames", "bytes")


class Trace:
    """Every byte the broker wrote, in the order it wrote them, with its tick."""

    def __init__(self):
        """Nothing written yet: no frames, no bytes, no ticks."""
        raise NotImplementedError("stage 10: implement Trace.__init__()")

    def wrote(self, tick, data):
        """Record `data` as written at `tick`, and answer the same bytes.

        The tick is the caller's — the trace reads no clock of its own, and the
        tick it records is the tick of the *write* and not of the read that
        follows it, because a trace stamped when it is read dates every frame the
        same way and cannot tell a re-send from a first transmission.
        """
        raise NotImplementedError("stage 10: implement Trace.wrote()")

    def frames(self):
        """Every write, as `[(tick, bytes)]`, in the order it happened: a copy.

        A caller that appends to what it was handed changed nothing of the
        trace's, because what a trace holds is evidence.
        """
        raise NotImplementedError("stage 10: implement Trace.frames()")

    def bytes(self):
        """Every byte written, in order: one run, as one buffer."""
        raise NotImplementedError("stage 10: implement Trace.bytes()")


def read_frames(data, pos=0):
    """Every frame in `data` from `pos`, as `([(type, flags, body)], pos_after)`.

    Stage 1 judges each fixed header and says where its body starts; the body is
    the `length` bytes after it. The buffer is walked to its end, and the position
    that comes back is where the last frame ended, so a caller that concatenates
    every write of a run and reads it once can require that position to be the
    buffer's own length: no byte left over, and no byte read twice.

    A buffer that stops inside a frame is stage 1's `Incomplete`, carrying exactly
    the bytes that have not arrived, so a caller that keeps the buffer and offers
    it again after the next step reads the frame once — which is the whole of
    reassembly, and the reason a length that arrives in pieces needs no special
    case anywhere above this line.
    """
    raise NotImplementedError("stage 10: implement read_frames()")


def cross_check(report, transport):
    """The report and the transport's own account, held together key by key.

    Only the keys both accounts can state are compared, because they are the only
    ones a disagreement can be *about*: the streams the transport opened, which
    the broker counts as the streams that completed a CONNECT, and the bytes it
    took towards its clients, which the broker counts as every byte it wrote. The
    transport knows nothing of sessions and the broker is not a transcript of the
    transport's log, so everything else is left alone rather than guessed at.

    The answer is `{"agree": bool, "disagreements": [...]}`: a verdict and a list
    of strings, each naming the key and both numbers, so a disagreement is
    reported and never resolved by preferring one account to the other.
    """
    raise NotImplementedError("stage 10: implement cross_check()")


def replay(scenario):
    """Run a scenario once and answer the bytes that run wrote.

    A scenario is a callable that builds its own transport, listens, connects its
    clients and answers the broker it drove; two calls are two whole runs of one
    script, and the only thing worth comparing about them is the trace. Two
    replays that write the same bytes are what a deterministic broker looks like;
    a `set`, an unordered dict or a clock of the broker's own shows up here and
    nowhere else in the course.
    """
    raise NotImplementedError("stage 10: implement replay()")


class Broker:
    """One broker, on one transport, with one policy and one trace of its own."""

    def __init__(self, transport, name="broker", grants=None):
        """A broker listening as `name` on `transport`, holding nothing yet.

        The state is the eleven fields of `BROKER_KEYS`, and `grants` is the
        world's table or `None` — a broker with no table has no policy at all and
        writes no decisions, which is a different thing from a table that grants
        nothing.
        """
        raise NotImplementedError("stage 10: implement Broker.__init__()")

    def accepted(self):
        """The streams that have completed a CONNECT, in the order they did."""
        raise NotImplementedError("stage 10: implement Broker.accepted()")

    def receive(self, stream, data):
        """The frames this broker wrote in answer to `data`, as a list.

        `data` is what one arrival at the server's end of `stream` carried: the
        broker keeps it beside whatever arrived before and reads frames out of the
        whole buffer, so a packet split across two arrivals is read once it is
        whole and nothing before it is read twice. A buffer that stops inside a
        frame answers nothing and keeps its bytes, and a frame the course's own
        reader refuses is refused here, naming the bytes that arrived.

        The list is the frames that answer the arrival being read; every frame
        written for another stream waits for the next `step`.
        """
        raise NotImplementedError("stage 10: implement Broker.receive()")

    def step(self, ticks=1):
        """Move the clock `ticks`, do the broker's own work, and answer the tick.

        One step is one turn of the whole broker: the connections the caller ended
        without telling it, the deliveries whose deadline has passed, the
        keep-alives that have run out — a will is owed to each of those — the
        messages a resumed session took back, and the last chunk of whatever the
        broker still owes each stream. Nothing here reads a clock: the tick is the
        transport's, and the transport only moves when a caller moves it.
        """
        raise NotImplementedError("stage 10: implement Broker.step()")

    def report(self):
        """The thirteen counts of `REPORT_KEYS`, counted from the trace and the sessions.

        Every number is derived at the moment it is asked for: the frames and the
        bytes from the trace, the deliveries and their QoS from the frames' own
        nibbles, what is queued and what is dropped from the sessions' queues and
        the buffers of the streams that are gone, and the refusals from the
        ledger. Nothing is kept in a counter beside the thing it counts, because a
        report that is a belief cannot be checked against what was written.
        """
        raise NotImplementedError("stage 10: implement Broker.report()")

    def trace(self):
        """The trace this broker wrote, for a caller that wants the bytes."""
        raise NotImplementedError("stage 10: implement Broker.trace()")
