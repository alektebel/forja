"""Concurrent Servers From Scratch — stage 4: The reactor: readiness as a set, and no busy-waiting.

Stage 1 gave one connection a machine — accept, read, write, close — and stage 2
drove those machines one client at a time, so one slow reader stopped everyone
behind it. This stage drives every connection at once, and it never guesses who
can move: once a turn the world is asked which connections are ready, and only
those are serviced.

Readiness is data, and that is the whole idea. `ready_set(link, conns)` returns
two tuples of connection ids — the ones with request bytes the server has not
taken yet, and the ones whose outbox has room — and the loop it feeds reads the
world, services the set, retires what is finished and gives the link exactly one
tick per turn. `Link.step()` is the only thing in this world that moves a byte or
a clock, so the reactor reports `steps` (turns) and `polls` (readiness reads)
separately: a model that services every connection every turn, or steps once per
connection, cannot hide it.

Three facts a check holds this against: only a connection the poll named is
serviced, the link is stepped once per turn, and the run stops only when nothing
is readable, nothing is writable and the listener is holding nobody. Stop early
and the answers a client drained fall short of the answers the server wrote; step
twice a turn and the step count says so.
"""

import stage_01
from link import Client, Connection, Link


class ServerError(ValueError):
    """A reactor this stage will not run, or a ready set it will not compute.

    It is the family for every shape this stage cannot honour: a link that is not
    the world, a ready set asked for over something that is not a sequence of
    this link's connections, a server that is not a dict of a link and its
    clients, and a budget that is not a whole number of turns. A verdict about
    what a client did — a slow reader, a request still owed, a client not yet
    arrived — is never an exception here: it is the shape of the result, and a
    check reads `starved` and the link's own log for it.
    """


def _link(link):
    """The world this reactor runs on, refusing anything that is not one."""
    if not isinstance(link, Link):
        raise ServerError("a reactor runs on the link, not %r" % (link,))
    return link


def _conns(link, conns):
    """A sequence of this link's own connections, in the order it was handed over."""
    if not isinstance(conns, (tuple, list)):
        raise ServerError("conns is a sequence of connections, not %r" % (conns,))
    for conn in conns:
        if not isinstance(conn, Connection) or link.connection(conn.id) is not conn:
            raise ServerError("connection %r is not this link's"
                              % (getattr(conn, "id", conn),))
    return conns


def ready_set(link, conns):
    """The two halves of the ready set over `conns`: (readable ids, writable ids).

    The world answers both questions and nothing here guesses at them:
    `link.readable(conn)` is "this connection has request bytes the server has
    not taken yet" and `link.writable(conn)` is "this connection's outbox has
    room for at least one byte". A connection the link never made, a connection
    of another link, and a `conns` that is not a sequence of them are refused
    naming the offender, because a ready set computed over a stranger is a
    reactor servicing a connection it does not own.

    Both tuples are in the order `conns` was given, a connection may appear in
    both — it is exactly the connection a reactor services for a read and then,
    on the next turn, for a write — and a closed connection is in neither, since
    the link answers `False` to both questions once it is closed. Reading
    readiness costs nothing: it moves no byte and no tick, which is why a turn
    may poll more than once and why `serve_reactor` counts polls apart from
    steps.
    """
    _link(link)
    _conns(link, conns)
    readable = []
    writable = []
    for conn in conns:
        if link.readable(conn):
            readable.append(conn.id)
        if link.writable(conn):
            writable.append(conn.id)
    return (tuple(readable), tuple(writable))


def _server(server):
    """The world and the clients a reactor runs, refusing anything else.

    The server is the dict stage 1 and stage 2 hand around: the link, the
    clients the link was built from, and the requests they send. Only the link
    and the clients are read here — the requests are the link's to script — and a
    server that is not a dict, whose link is not the world, or whose clients are
    not a non-empty sequence of `Client`s is refused naming what was given.
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
    """A turn budget: a whole number of turns, or a refusal naming it."""
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
        raise ServerError("a budget is a whole number of turns, not %r" % (budget,))
    return budget


def _admit(link, machines):
    """Everyone the listener has been holding: accept, open, and take the first move.

    `link.accept()` is the listener's own move and the only way a client enters
    the run; the machine is opened by stage 1 and its `"new" → "reading"` step is
    taken here, because accepting a connection *is* a move of that connection and
    spending a whole turn on it would be a turn the reactor owes nobody.
    Accepting is not a turn either: the loop admits before it polls, so a client
    that arrived while the last turn was being stepped is serviced by this one
    like everybody else.
    """
    while True:
        conn = link.accept()
        if conn is None:
            return
        machines[conn.id] = stage_01.step_conn(link, stage_01.open_conn(link, conn.id))


def _turn(readable, writable):
    """The ids this turn services: the ready set, in accept order, once each.

    Both halves are already in accept order, so a connection that is both
    readable and writable keeps its place in it and is serviced once: one move
    per connection per turn is what makes the step count mean what it says.
    """
    order = []
    for cid in tuple(readable) + tuple(writable):
        if cid not in order:
            order.append(cid)
    return tuple(order)


def _move(link, machines, cid, answers, staged):
    """One move of one ready connection, and the answer it delivers, if any.

    Stage 1's machine does the moving; this records the one thing the result
    needs of it. A `"read"` event that leaves a whole reply staged in the machine
    is a request that has been answered, and the answer is counted when the last
    of its bytes has reached the outbox — when the machine's `"replies"` counter
    moves — and never when the line was read. An outbox that could only take part
    of the line, and a budget that runs out between the read and the write, both
    leave the answer out of the result: the answers this reactor reports are the
    ones it wrote, which is what the link's own `bytes_written` counts too.
    """
    before = machines[cid]["replies"]
    state = stage_01.step_conn(link, machines[cid])
    machines[cid] = state
    if state["event"] == "read" and state["out"]:
        staged[cid] = state["out"]
    elif state["replies"] > before:
        answers[state["conn"].client.name].append(staged.pop(cid))


def _retire(link, machines, served):
    """Every machine whose read side is over: `closing → closed`, and its name.

    A machine reaches `"closing"` when its client has nothing left to send and
    has taken every answer, and `finish` is the one move that is not a step: it
    hands the connection back to the link and the client is served. The
    retirement order is the accept order, because the machines are held in it.
    """
    for cid in tuple(machines):
        if machines[cid]["state"] == "closing":
            machines[cid] = stage_01.finish(link, machines[cid])
            served.append(machines[cid]["conn"].client.name)


def serve_reactor(server, *, budget=256):
    """Every client at once, serviced by readiness: the same answers a blocking
    server gives, and the steps it took.

    The shape is stage 2's — `{"answers", "steps", "ticks", "served", "starved"}`
    — with `"polls"` beside `"steps"`: `answers` is every client's reply lines in
    the order it was answered, `served` the clients closed, in that order,
    `starved` the clients that still had an unanswered request when the budget
    ran out, and `ticks` the link's own reading at the end. `steps` counts turns
    and `polls` counts ready-set computations; they are different numbers because
    a turn polls at least once and steps exactly once, and a check holds
    `steps <= 2 * polls + 4` on a workload it knows.

    One turn: admit everyone the listener holds, poll the world for the
    connections that are readable or writable, service *those* and no others —
    one move each — retire every machine whose read side is over, and step the
    link once. Nothing moves outside `Link.step()`, so a turn with nothing ready
    still steps, and only a run that has nothing readable, nothing writable and
    nobody left in the listener is over. The poll is taken after the previous
    turn's tick, and a tick carries every outbox down, so a live connection
    always has room to be written to when it is asked about: a reply that is owed
    is a connection in the writable half, never a connection nobody services.

    `budget` is in turns, not ticks: a budget spent with work left is an outcome
    the result reports in `starved`, never an exception. Nothing is guessed about
    the clients either — a slow reader is serviced like anyone else, one move per
    turn, which is exactly what a blocking server cannot do.
    """
    link, clients = _server(server)
    limit = _budget(budget)
    machines = {}
    answers = {client.name: [] for client in clients}
    staged = {}
    served = []
    steps = 0
    polls = 0
    while steps < limit:
        _admit(link, machines)
        readable, writable = ready_set(
            link, tuple(state["conn"] for state in machines.values()))
        polls += 1
        if not readable and not writable and not link.waiting():
            break
        for cid in _turn(readable, writable):
            _move(link, machines, cid, answers, staged)
        _retire(link, machines, served)
        link.step(1)
        steps += 1
    return {"answers": {name: tuple(lines) for name, lines in answers.items()},
            "steps": steps,
            "polls": polls,
            "ticks": link.now(),
            "served": tuple(served),
            "starved": tuple(client.name for client in clients
                             if len(answers[client.name]) < len(client.requests))}
