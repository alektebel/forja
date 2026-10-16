"""Concurrent Servers From Scratch — stage 8: Backpressure, and the write that has to be deferred.

SOLUTION. Stage 1's machine kept the tail of a short write in `out` and hid the
count; stage 4's reactor wrote every reply in a single move because every reply
in its workload fitted the outbox. This stage takes the world's own sentence
seriously — `write` hands back the bytes the outbox took and the rest is the
caller's — and makes the deferred part *data*: the connection's state carries the
reply in flight (`pending`) and how many of its bytes have reached the outbox
(`offset`), so a reply that takes five turns is a reply whose progress the caller
can read turn by turn, rather than a local variable a loop loses.

`send` is that one move: it hands over the bytes still owed, honours the count
the world gave back, and answers with `sent`, `deferred` and `drained`. It never
widens the outbox and never offers the world bytes it cannot take — `write` is
called only when the world says there is room — so the link's own log stays
quiet and the bytes the clients received are exactly the answers this server
reports.

`serve_backpressure` is a reactor over that move: the ready set is stage 4's, the
poll happens once a turn, and the link is stepped once a turn, which is why
`steps` and `ticks` are the same number here. The one place it is deliberately
*not* a reactor is the write path: it serves one reply at a time, in the order
the replies were staged, and a reply keeps the head of that queue until its
client has taken it whole. A fair write path would give every pending reply a
byte a turn and there would be no number to report; a single one is what makes
one slow reader cost every client behind it — head-of-line blocking, which is
`stalled`, the connections whose reply the whole run never moved at all.
"""

import stage_01
import stage_04
from link import Client, Connection, Link

#: The turns one run takes before it gives up and reports what it did. A budget
#: spent with work left is an outcome and not an exception: the result says how
#: far it got, and `stalled` names the replies that never moved.
DEFAULT_BUDGET = 256


class ServerError(ValueError):
    """A state, a reply or a server this stage will not send through.

    It is the family for every shape `send` and `serve_backpressure` cannot
    honour: a `link` that is not the world, a `state` that is not a mapping of a
    connection, a phase, a read buffer, a pending reply and an offset, a phase
    that is not one of stage 1's, a reply that is not bytes, a reply that is not
    one line, a `server` that is not a dict of a link and its clients, and a
    `budget` that is not a whole number of turns. A verdict about what the client
    or the wire did — an outbox with no room, a connection the world has closed,
    a reply still waiting behind another — is never an exception here: it is
    `sent`, `deferred`, `drained` and `stalled` in the result.
    """


def _link(link):
    """The world this stage sends through, refusing anything that is not one."""
    if not isinstance(link, Link):
        raise ServerError("a server sends through the link, not %r" % (link,))
    return link


def _conn(link, state):
    """The connection a state carries, refusing a state that is not a mapping."""
    if not isinstance(state, dict):
        raise ServerError("a connection's state is a mapping, not %r" % (state,))
    conn = state.get("conn")
    if not isinstance(conn, Connection) or link.connection(conn.id) is not conn:
        raise ServerError("connection %r is not this link's"
                          % (getattr(conn, "id", conn),))
    return conn


def _phase(state, conn):
    """The phase a reply is written from, or a refusal naming what was given.

    The phases are stage 1's, and a send is a *writing* move: the state says a
    reply has been built and is waiting for the outbox. A state caught in another
    phase is a caller sending something it never staged, and a phase that is not
    one of `STATES` is a state this course never built.
    """
    phase = state.get("phase")
    if phase not in stage_01.STATES:
        raise ServerError("a state's phase is one of %r, not %r"
                          % (list(stage_01.STATES), phase))
    if phase != "writing":
        raise ServerError("connection %d is sent to from the %r phase: a reply is "
                          "written from %r" % (conn.id, phase, "writing"))
    return phase


def _carried(state):
    """The buffer, the reply in flight and the offset, or a refusal naming them."""
    buffer = state.get("buffer")
    if not isinstance(buffer, bytes):
        raise ServerError("a state's read buffer is bytes, not %r" % (buffer,))
    pending = state.get("pending")
    if not isinstance(pending, bytes):
        raise ServerError("a state's pending reply is bytes, not %r" % (pending,))
    offset = state.get("offset")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ServerError("a state's offset is a byte count, not %r" % (offset,))
    if offset > len(pending):
        raise ServerError("a state's offset is %d and its reply is %d byte(s) long"
                          % (offset, len(pending)))
    return buffer, pending, offset


def _reply(data, pending):
    """The reply a send is asked to hand over, or a refusal naming what was given.

    A fresh reply — a connection whose `pending` is empty — is one whole line of
    the protocol this course speaks, so bytes that are empty or do not end in a
    newline are refused: a reply is built from a request line and a reply that is
    not a line is not one. The tail of a reply already in flight is *not* a line
    and is not asked to be one.
    """
    if not isinstance(data, bytes):
        raise ServerError("a reply is bytes, not %r" % (data,))
    if not pending and not data.endswith(b"\n"):
        raise ServerError("a reply is one line ending in a newline, not %r"
                          % (data,))
    return data


def _state(conn, phase, buffer=b"", pending=b"", offset=0):
    """A fresh connection state: the canonical five fields, in the canonical order."""
    return {"conn": conn, "phase": phase, "buffer": buffer, "pending": pending,
            "offset": offset}


def _server(server):
    """The world and the clients a run is handed, refusing anything else.

    The bundle is the one every model in this course takes — the link, the
    clients the link was built from, and the request lines they send — and only
    the first two are read here, because the link owns the third. A server that
    is not a dict, whose link is not the world, or whose clients are not a
    non-empty sequence of `Client`s is refused naming what was given, exactly as
    stage 4 refuses it: one workload, one bundle, whichever model drives it.
    """
    if not isinstance(server, dict):
        raise ServerError("a server is a dict of its link and its clients, not %r"
                          % (server,))
    link = server.get("link")
    if not isinstance(link, Link):
        raise ServerError("a server's link is the world, not %r" % (link,))
    clients = server.get("clients")
    if not isinstance(clients, (tuple, list)) or not clients:
        raise ServerError("a server's clients are a non-empty sequence, not %r"
                          % (clients,))
    for client in clients:
        if not isinstance(client, Client):
            raise ServerError("a server's client is a Client, not %r" % (client,))
    return link, tuple(clients)


def _budget(budget):
    """A turn budget: a whole number of turns, zero or more, or a refusal."""
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
        raise ServerError("a budget is a whole number of turns, not %r" % (budget,))
    return budget


def send(link, state, data):
    """One move of one connection's reply: hand over what the outbox will take.

    `state` is the connection's state: `{"conn", "phase", "buffer", "pending",
    "offset"}`, where `pending` is the reply in flight and `offset` is how many
    of its bytes have reached the outbox. A state whose `pending` is empty starts
    a new reply from `data`, which is then one whole line; a state whose
    `pending` is non-empty is halfway through the reply it already holds, and
    `data` must be exactly the bytes still owed, `pending[offset:]`. Handing the
    same whole reply over again after part of it has gone is a caller that lost
    the offset — the state kept it and the caller did not — and is refused naming
    what was given, because a client that sees a reply's opening bytes twice is
    a client reading a corrupted answer.

    The answer is `{"state", "sent", "deferred", "drained"}`: the state again,
    fresh, with the fields moved on; `sent` the bytes the outbox took this call;
    `deferred` the bytes still owed afterwards; and `drained` whether the whole
    reply has now reached the outbox. Nothing raises because the world took
    nothing: an outbox with no room and a connection the client has dropped both
    answer `sent` of zero with the reply still owed, which is the fact `stalled`
    is computed from. `write` is called only when the world says there is room,
    so the link never records a drop this server offered it, and the outbox is
    never widened: its bound is the world's, and the state is where the rest of
    the reply waits.
    """
    _link(link)
    conn = _conn(link, state)
    _phase(state, conn)
    buffer, pending, offset = _carried(state)
    _reply(data, pending)
    if pending:
        tail = pending[offset:]
        if data != tail:
            raise ServerError(
                "the reply on connection %d is %d byte(s) on its way and %r is "
                "not the %d byte(s) still owed"
                % (conn.id, offset, data, len(tail)))
    else:
        pending, offset, tail = data, 0, data
    sent = 0
    if tail and link.writable(conn):
        sent = link.write(conn, tail)
    offset += sent
    owed = len(pending) - offset
    if owed:
        return {"state": _state(conn, "writing", buffer, pending, offset),
                "sent": sent, "deferred": owed, "drained": False}
    return {"state": _state(conn, "reading", buffer, b"", 0),
            "sent": sent, "deferred": 0, "drained": True}


def _read(link, state):
    """One read move of one connection: take bytes, and stage the reply when the line is whole.

    A request is one line ending in a newline and a read carries at most
    `MAX_CHUNK` of it, so the state keeps what has arrived so far and a line that
    comes in three moves is assembled in three. The reply is staged the moment
    the line is whole — stage 1's `REPLY_PREFIX` and the line — and the phase
    becomes `"writing"`: the read side then waits for the write side to hand the
    reply over, and *that* is the one thing this state does differently from
    stage 1's machine, whose write move never told its caller how much of the
    reply was still outstanding. A connection in the `"writing"` phase is
    therefore not read at all: the state carries one reply at a time, and a
    request that arrives while its predecessor is still in flight waits in the
    world until the write side is done with it. Only a connection the poll named
    readable is serviced, so a read that brings back `b""` — a line still on its
    way — leaves the buffer exactly as it was.
    """
    conn = state["conn"]
    if state["phase"] == "writing":
        return state
    buffer = state["buffer"] + link.read(conn)
    if not buffer.endswith(b"\n"):
        return _state(conn, "reading", buffer, b"", 0)
    return _state(conn, "writing", b"", stage_01.REPLY_PREFIX.encode() + buffer, 0)


def _over(link, state):
    """Whether the world has nothing left for this connection, in either direction.

    The question is the world's own readiness, asked once at the end of a turn:
    no request bytes the server has not taken, nothing owed, nothing on its way
    into the outbox, and nothing in the inbox the client has not drained. Those
    four are the whole of it, and every other fact a connection here carries is
    downstream of them: a reply still in `pending` is a reply the link has not
    carried yet — `owed` before its first byte, `outbox` after it — or one the
    client has not taken, which is `drainable`; and a half-read line is the bytes
    `readable` still reports. A client with another request to make keeps its
    connection open for the same reason: the link scripts the client's requests,
    so the next one is readable the moment the last answer is drained, and
    nothing here has to be guessed from an empty socket.
    """
    conn = state["conn"]
    return not (link.readable(conn) or link.owed(conn) or link.drainable(conn)
                or conn.outbox)


def _admit(link, states):
    """Everyone the listener is holding: accepted, in the reading phase.

    `accept()` is the listener's own move and the only way a client enters the
    run, and accepting is not a turn: the loop admits before it polls, so a
    client that arrived while the last turn was being stepped is read by this
    one like everybody else. The state starts in `"reading"`, because the `"new"`
    phase is the accept itself and this call is the move that took it.
    """
    while True:
        conn = link.accept()
        if conn is None:
            return
        states[conn.id] = _state(conn, "reading")


def _write(link, states, queue, answers, deferred):
    """One write move: the reply at the head of the queue, an outbox-full of it.

    The queue holds the connections whose replies were staged, in the order they
    were staged, and the head keeps its place until its client has taken the
    whole answer. That serialisation is the decision this stage is about: a fast
    client behind a slow one is not helped by being fast, because the write path
    is serving somebody else. A reply whose connection the world has closed can
    never move, so it leaves the head instead of blocking the queue forever — and
    the state keeps its `pending`, which is exactly what `stalled` is read from.
    One move per turn and no more, so at most one outbox-full is handed over per
    turn and the turn count means what it says.
    """
    while queue and states[queue[0]]["conn"].closed:
        queue.pop(0)
    if not queue:
        return
    state = states[queue[0]]
    conn = state["conn"]
    if state["pending"]:
        move = send(link, state, state["pending"][state["offset"]:])
        states[queue[0]] = move["state"]
        if move["deferred"]:
            deferred.add(conn.client.name)
        if move["drained"]:
            answers[conn.client.name].append(state["pending"])
        return
    if not link.drainable(conn) and not conn.outbox:
        queue.pop(0)


def _live(link, states, queue):
    """Whether anything can still move: a client to accept, a reply to carry or take.

    The run is over when the listener holds nobody, no reply on the queue belongs
    to a connection the world has not closed, and no connection still has a
    request to read or a reply waiting to be taken. Anything else is a reason to
    spend another turn — including a reply that is fully written and still in a
    client's inbox, because this loop is over when the clients have their answers
    and not when the server has typed them.
    """
    if link.waiting():
        return True
    for cid in queue:
        if not states[cid]["conn"].closed:
            return True
    for state in states.values():
        if state["conn"].closed:
            continue
        if not _over(link, state):
            return True
    return False


def _retire(link, states):
    """Close every connection whose read side is over, once, in accept order.

    A connection reaches this when it has nothing left to read and has taken
    every answer it was owed: `"closing"` is the state's word for it and
    `"closed"` is what it is once the link has been told. Nothing is closed
    before that — the client's next request is the link's to hand over — and a
    connection the world has already closed is left exactly as it is, because
    the reply still in its state is what `stalled` reports.
    """
    for cid in sorted(states):
        state = states[cid]
        conn = state["conn"]
        if conn.closed or not _over(link, state):
            continue
        link.close(conn)
        states[cid] = _state(conn, "closed")


def _stalled(states):
    """The ids of the connections whose reply never reached the outbox, in id order.

    A connection is stalled when the run ends with a reply still in its state of
    which not one byte was ever written: the world closed the connection
    underneath it — a client whose patience ran out while its reply waited behind
    somebody else's — or the budget ran out before its turn came. A reply that
    moved some bytes is not stalled, it is on its way; and a reply that was
    written and taken leaves no pending behind, so it cannot be counted twice.
    """
    return tuple(cid for cid in sorted(states)
                 if states[cid]["pending"] and not states[cid]["offset"])


def serve_backpressure(server, *, budget=DEFAULT_BUDGET):
    """A reactor whose writes are one reply at a time, and what that costs.

    `server` is the bundle every model in this course drives — `{"link",
    "clients", "requests"}` — and the answer is `{"answers", "steps", "ticks",
    "deferred", "stalled"}`. `answers` is every client's reply lines in the order
    they were written, and a reply counts when its last byte has reached the
    outbox and not when its request was read: a reply the budget left half
    written is not an answer the world carried. `deferred` names the clients
    whose reply had to be handed over in more than one turn, in accept order, and
    `stalled` the clients whose reply the whole run never moved at all.

    One turn: accept everyone the listener holds, poll `ready_set` for what can
    be read, take one read move per readable connection — staging a reply is the
    read side's job and waiting for the outbox is the write side's — then write
    the reply at the head of the write queue, an outbox-full of it, retire the
    connections whose read side is over, and step the link once if anything can
    still move. The link is the only thing that moves a byte here, so `steps` and
    `ticks` are the same count, and a spent budget is an outcome rather than an
    exception: the result reports what was written, what had to be deferred, and
    what never left the server at all.
    """
    link, clients = _server(server)
    limit = _budget(budget)
    states = {}                                   # cid -> the connection's state
    queue = []                                    # cids with a reply staged, in order
    answers = {client.name: [] for client in clients}
    deferred = set()
    steps = 0
    while steps < limit:
        _admit(link, states)
        readable = stage_04.ready_set(
            link, tuple(state["conn"] for state in states.values()))[0]
        for cid in readable:
            staged = _read(link, states[cid])
            if staged["phase"] == "writing":
                queue.append(cid)
            states[cid] = staged
        _write(link, states, queue, answers, deferred)
        _retire(link, states)
        if not _live(link, states, queue):
            break
        link.step(1)
        steps += 1
    return {"answers": {name: tuple(lines) for name, lines in answers.items()},
            "steps": steps,
            "ticks": link.now(),
            "deferred": tuple(client.name for client in clients
                              if client.name in deferred),
            "stalled": tuple(link.connection(cid).client.name
                             for cid in _stalled(states))}


