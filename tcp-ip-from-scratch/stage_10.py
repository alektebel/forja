"""TCP/IP From Scratch — stage 10: The session, and the wire's own log as the tie-breaker.

Read `stage_01.py` through `stage_09.py` first: every one of them is a part of
this file, and this file is the only one that uses all of them at once.

The nine stages before this one each proved a layer on its own. This one runs
the whole stack over one wire and then refuses to believe its own paperwork: the
session reports what it thinks happened, `cross_check` asks the wire, and a
disagreement is the failure the stage exists to catch.

One session is one payload from one client to one server, in four movements:

* **resolve** the peer's address with ARP (stage 2), because a frame needs a MAC
  and nothing above the link can invent one;
* **shake hands** with two `stage_05.Connection`s, each stepped with the other's
  segment, wrapped in stage 3's datagram inside stage 1's frame;
* **move the payload** through stage 8's `Reliable`, so a wire that eats a
  segment is retransmitted over by the one timer that doubles, with stage 6's
  `Receiver` on the far side handing the bytes up in order;
* **close** with stage 9, both directions, until the states say `time_wait` and
  `closed`.

The session is both sides: the world's peers are passive by design, so a session
that wants an answer has to be the thing that gives it. Every frame it emits is
counted with the ordinal the wire handed back, and every frame it takes out of a
box is counted as a delivery. `report` recomputes the ledger from those counts,
and `cross_check` holds it against `Wire.sent()`, `Wire.dropped()`,
`Wire.delivered()` and the sends' ordinals — where the two disagree, the wire is
right.

DESIGN DECISION — the session keeps its own ledger, and the ledger is the only
thing a reader may believe: `Wire.sent()`, `Wire.delivered()` and `Wire.dropped()`
are the world's record, and a session that reported its intentions instead of its
outcomes would agree with the world by accident. So the ledger counts what went
out (with the ordinal the wire returned) and what came in (every frame this
session took out of a box), and `cross_check` is the one place the two accounts
meet.

DESIGN DECISION — a broadcast frame comes back to the host that sent it, and that
echo is not a delivery: the box keeps it, a stack does not hand it up, and
counting it would make every session with an ARP request in it agree with a wire
that never delivered anything.

DESIGN DECISION — `dropped` is inferred, never copied from the wire: a frame is
lost exactly when it was sent and never arrived, which on a wire whose latency is
one tick is `sent - delivered` once the session has settled. Reading the wire's
own count into the ledger would make the cross-check a tautology.

DESIGN DECISION — every scenario comes from `plan()` and none of them may raise:
a run whose wire eats everything is an outcome to report (`"received": False`,
`"expired": True`), not an exception to catch, because a session is a thing that
happens to a wire and the wire always gets a say.

DESIGN DECISION — the session drives both ends itself instead of hiding behind
one socket table: a table owns the connection behind each descriptor and offers
no way back to it, and the close (stage 9) needs that object for its ladder and
its `FIN` sequence. The table is proved where it belongs, in stage 7's own check,
and the pair here is the same two `stage_05.Connection`s for the handshake, the
payload and the close.

TODO: implement every function below. Read `stage_09.py`'s solution for the
shape of a stage that composes the ones before it.
"""

import stage_01
import stage_02
import stage_03
import stage_05
import stage_06
import stage_08
import stage_09
from hosts import MACS, NAMES, ip_of, mac_of
from wire import BROADCAST_MAC, Wire, WireError

#: The scenario's own keys: what `plan()` hands back and `open_session` demands.
SESSION_KEYS = ("peers", "payload", "rules", "ticks", "ports")

#: The ledger's keys, in the order `report` hands them over.
LEDGER_KEYS = ("sent", "received", "bytes", "handshake", "closed", "resent",
               "ticks", "delivered", "dropped", "expired", "events")

#: What the session spends before the payload starts: the ARP request, its reply,
#: the SYN, the SYN,ACK and the client's ACK. The sixth frame on the wire is the
#: first payload segment, which is how a scenario can name the segment a loss
#: should eat.
PROLOGUE_FRAMES = 5

#: The one protocol number this stage carries, and the name stage 3 reads back.
TCP = 6


class SessionError(ValueError):
    """A scenario, a peer or a port this stage cannot honour, named as what is wrong."""


# ---- the scenario ---------------------------------------------------------

def _int(value, what, low, high):
    """An int in `low..high`, or a refusal naming the offender."""
    raise NotImplementedError("stage 10: implement _int()")


def _peer(name, what):
    """One of the world's names, or a refusal naming what arrived instead."""
    raise NotImplementedError("stage 10: implement _peer()")


def _scenario(spec):
    """One scenario, validated and copied, so two runs cannot share a dict."""
    raise NotImplementedError("stage 10: implement _scenario()")


def plan(sessions=None):
    """The course's scenarios, as fresh copies, or the ones a caller hands over."""
    raise NotImplementedError("stage 10: implement plan()")


# ---- the objects one session runs on --------------------------------------

def open_session(link, client, server, payload, rules=None, ports=None):
    """Two hosts, two ends and the payload between them, on `link`."""
    raise NotImplementedError("stage 10: implement open_session()")


def _listening(name, port, remote):
    """The server's end: a connection in `listen`, waiting for the client's SYN."""
    raise NotImplementedError("stage 10: implement _listening()")


def _host(name, link):
    """One of the world's hosts, on this session's wire."""
    raise NotImplementedError("stage 10: implement _host()")


# ---- one frame out, one frame in ------------------------------------------

class Frames:
    """The thing a segment goes out through: a datagram, a frame, an ordinal."""

    def __init__(self, session, host, dst_mac, src_ip, dst_ip, note):
        """A session, the host whose box is the way out, and where it goes."""
        raise NotImplementedError("stage 10: implement Frames.__init__()")

    def send(self, segment):
        """Put one segment on the wire, and count the frame it became."""
        raise NotImplementedError("stage 10: implement Frames.send()")


def _read(session, host, src_ip, dst_ip, port):
    """Every segment in a host's box for this pair, and the frames it took."""
    raise NotImplementedError("stage 10: implement _read()")


def _client_frames(session, note):
    """A way out for the client: the server's MAC, the client's own address."""
    raise NotImplementedError("stage 10: implement _client_frames()")


def _server_frames(session, note):
    """A way out for the server, back towards the client."""
    raise NotImplementedError("stage 10: implement _server_frames()")


# ---- the four movements ---------------------------------------------------

def _resolve(session):
    """The client asks for the server's MAC, and the session answers as the server."""
    raise NotImplementedError("stage 10: implement _resolve()")


def _handshake(session):
    """The three segments, each end stepped with the other's."""
    raise NotImplementedError("stage 10: implement _handshake()")


def _transfer(session, budget):
    """Queue the payload and move it: window, wire, acknowledgement, timer."""
    raise NotImplementedError("stage 10: implement _transfer()")


def _shutdown(session, now):
    """The four-way close: FIN, ACK, FIN, ACK, with both ends stepped."""
    raise NotImplementedError("stage 10: implement _shutdown()")


def run(session, max_ticks=64):
    """One session, end to end, and the ledger it believes."""
    raise NotImplementedError("stage 10: implement run()")


# ---- the two accounts -----------------------------------------------------

def _wire_counts(session):
    """What the wire itself says happened, in the ledger's own vocabulary."""
    raise NotImplementedError("stage 10: implement _wire_counts()")


def report(session):
    """The session's own account, recomputed from its ledger."""
    raise NotImplementedError("stage 10: implement report()")


def cross_check(session):
    """The session's ledger against the wire's record: the wire is right."""
    raise NotImplementedError("stage 10: implement cross_check()")
