"""Concurrent Servers From Scratch — stage 8: Backpressure, and the write that has to be deferred.

Stage 1 gave a connection a bounded outbox and said the truth about it: `write`
hands back how many bytes the outbox took, and a short write is *data*, not an
error. Stage 4's reactor then serviced every ready connection once a turn, and
every reply went out in one move because every reply in that stage's workload was
smaller than the outbox. This stage takes the promise seriously: a reply that is
bigger than `MAX_CHUNK`, and a reply bigger than the outbox, are written over
several turns, and the connection's state — not a local variable, not a closure —
carries what is left.

`send` is one move of one connection's reply: it hands over the bytes still owed,
counts what the world took, and answers with `sent`, `deferred` and `drained`.
`serve_backpressure` is a reactor-shaped loop around it — the ready set is
stage 4's, the poll is once a turn, the link is stepped once a turn — whose write
side is deliberately one reply at a time. That is the decision this stage exists
for: with a single write path, one reply that cannot be finished blocks every
reply behind it, and the number of turns a client's answer spends waiting for a
turn it never gets is exactly what `stalled` reports.

TODO: implement `send` and `serve_backpressure` in stage_08.py.

DESIGN DECISION — where does the part of the reply the outbox could not take go?

The world's `write` returns a count, and the caller owns the rest. It must not
live in a local variable of the loop — a loop that keeps a reply "in flight" in a
local is a loop that loses it the moment another connection is serviced — and it
must not be grown into the outbox, which is the world's bound and not the
server's to widen. So the connection's state carries the reply being written and
how far it has got: `pending` (the reply in flight, whole, while it is unfinished)
and `offset` (how many of its bytes have reached the outbox). The bytes still owed
are `pending[offset:]`, `deferred` is their count, and a state whose `pending` is
empty is a connection with nothing owed — the same state a reply starts from.

DESIGN DECISION — why is a second `send` of the same reply a refusal?

A reply that takes several turns is a reply whose caller has to remember the
offset across turns. A caller that hands over the same bytes again — the whole
reply, after part of it has already reached the outbox — is a caller that has lost
the offset, and a server that repeats a reply's opening bytes is a server whose
client sees a corrupted answer. So a `send` on a connection whose `pending` is
non-empty must hand over exactly the bytes still owed: `pending[offset:]`, the
tail the state itself implies. Anything else is refused, naming what was given,
because a refusal here is cheap and a doubled reply is not.

DESIGN DECISION — does a server that defers writes service every connection each turn?

It cannot, and pretending otherwise is what hides the subject. The write side of
this loop is one reply at a time, in the order the replies were staged: the
connection at the head of that queue gets one outbox-full per turn until its
client has taken the whole answer, and only then does the next reply start. Serve
every pending connection a byte each turn and head-of-line blocking disappears —
and with it the honest number a student should see, because the client behind the
slow one is waiting for a turn the server has not got. `stalled` names the
connections the whole budget left with a reply that never moved: that is the same
fact as "one slow reader costs everyone behind it", expressed as a count instead
of an apology.

DESIGN DECISION — what does `send` do when the world takes nothing?

It answers, rather than raising. An outbox with no room and a connection the
world has closed because the client's patience ran out are both facts about the
client and the wire, and this course returns a verdict about content: `sent` is
zero, `deferred` has not moved and `drained` is `False`. Only a shape mismatch
raises — a state that is not a mapping with a connection, a `data` that is not
bytes, a connection that is not this link's — and those raise `ServerError`
naming the offender. A server that never widens the outbox and never calls `write`
with an empty outbox offers the world nothing it cannot take, so the link's own
log stays quiet: `drops` is zero, and the bytes that reached the clients are
exactly the answers the result reports.
"""

from link import MAX_CHUNK

#: The turn budget a run starts from: a spent budget is an outcome this stage
#: reports, so the default only has to be big enough to finish a workload.
DEFAULT_BUDGET = 256


class ServerError(ValueError):
    """A state, a reply or a server this stage will not send through.

    It is the family for every shape `send` and `serve_backpressure` cannot
    honour: a `state` that is not a mapping, a state whose connection is not this
    link's, a state whose `pending` is not bytes or whose `offset` is not an int,
    a `data` that is not bytes, a `server` that is not the dict of the contract,
    and a `budget` that is not a whole number of turns. A verdict about what the
    client or the wire did — an outbox with no room, a connection the client
    dropped, a reply still waiting behind another — is never an exception here:
    it is `sent`, `deferred`, `drained` and `stalled` in the result.
    """


def send(link, state, data):
    """One move of one connection's reply: hand over what the outbox will take.

    `state` is the connection's state: `{"conn", "phase", "buffer", "pending",
    "offset"}` — stage 1's connection, the phase a move is taken from, the bytes
    of a request line read but never finished, the reply in flight and how far it
    has got. A `send` is a *writing* move: the state must be in the `"writing"`
    phase when it is handed over, and it goes back to `"reading"` once the whole
    reply has reached the outbox, because a connection owed nothing is a
    connection whose next move is a read. `pending` is the reply in flight and
    `offset` is how many of its bytes have reached the outbox. A state whose
    `pending` is empty starts a new reply from `data`; a state whose `pending` is
    non-empty is halfway through the reply it already holds, and `data` must then
    be exactly the bytes still owed, `pending[offset:]` — the same reply handed
    over a second time is a caller that lost the offset, and is refused naming
    what was given.

    The answer is `{"state", "sent", "deferred", "drained"}`: the state again
    (fresh, with `pending` and `offset` moved on), `sent` the bytes the outbox
    took this call, `deferred` the bytes still owed afterwards, and `drained`
    whether the whole reply has now reached the outbox. `MAX_CHUNK` is not the
    limit here — the state is — so a reply bigger than the outbox takes turns,
    and a reply bigger than `MAX_CHUNK` takes turns even when the outbox is roomy.
    """
    raise NotImplementedError("stage 8: implement send()")


def serve_backpressure(server, *, budget=DEFAULT_BUDGET):
    """A reactor whose writes are one reply at a time, and what that costs.

    `server` is the bundle every model in this course drives — `{"link",
    "clients", "requests"}` — and the answer is `{"answers", "steps", "ticks",
    "deferred", "stalled"}`. `answers` is every client's reply lines in the order
    they were written, and a reply counts when its last byte has reached the
    outbox and not when its request was read: a reply the budget left half
    written is not an answer the world carried. `deferred` names the clients
    whose reply had to be handed over in more than one turn, in accept order, and
    `stalled` the clients whose reply the whole budget never moved at all — the
    head-of-line blocking this stage exists to put a number on.

    One turn: accept everyone the listener holds, poll `ready_set` for what can
    be read, take one read move per readable connection, and write the reply at
    the head of the write queue — one outbox-full of it — if the world has room.
    A reply stays at the head until its client has taken it whole, so the replies
    behind it wait for it rather than sharing the turns; the link is stepped once
    per turn, and `steps` and `ticks` are the same count because nothing here
    moves a byte outside `Link.step()`. A spent budget is an outcome, not an
    exception: the result reports what was written and what never moved.
    """
    raise NotImplementedError("stage 8: implement serve_backpressure()")
