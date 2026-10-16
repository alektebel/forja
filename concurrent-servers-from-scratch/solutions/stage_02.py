"""Concurrent Servers From Scratch — stage 2: The blocking server, and the slow client.

SOLUTION. One thread of control, one client at a time, and the client that reads
every fourth tick: the oldest model there is, and the one this course can put a
number on. `serve_blocking` is not a new connection machine — the machine is
stage 1's, and this stage is the *policy* around it: accept, read the line,
answer, wait for the client to drain it, close, next. Nothing here reads the
second client's request while the first is unanswered, and nothing here sleeps,
spins or guesses: the loop takes one turn per move and lets the link move one
tick per turn, because a single thread of control has nothing else to do while it
waits, and the wait is what the ticks are.

The bundle is `{"link", "clients", "requests"}` — the world, its scripted
clients, and the lines they send — and this stage adds nothing to it and reads
nothing else out of it. The result is the model's whole verdict: `answers` for
every client (the reply lines the server wrote, in order, an empty tuple for a
client the budget never reached), `steps` for the turns the loop took, `ticks`
for the link's clock at the end, `served` for the clients taken to completion in
that order, and `starved` for the clients whose requests were still unanswered.
A budget spent with work left is an *outcome*, not an exception: the model hands
back what it did, and the difference between the two tuples is the finding — one
slow reader costs every client behind it the whole budget.
"""

import stage_01
from link import Client, Link


class ServerError(ValueError):
    """A server bundle this stage will not serve, or a budget that is not a count.

    It is the family for every shape `serve_blocking` cannot honour: a `server`
    that is not a dict, one that is missing one of its three keys, a `"link"`
    that is not the world, a `"clients"` sequence that is empty or does not agree
    with the link's own connections, a `"requests"` mapping without one of those
    clients' lines, a request line that is not bytes, and a `budget` that is not
    a count of steps. A verdict about what the *clients* did is never an
    exception here: a client the budget never reached is `starved`, and a budget
    spent with work left is an outcome the caller reads out of the result.
    """


def _server(server):
    """The bundle, checked and handed back: `{"link", "clients", "requests"}`.

    The link is the arbiter of what is really in the world, so the bundle is
    held against it rather than trusted: the clients it names must be the link's
    own connections, in the link's own order, each with a non-empty tuple of
    request lines. It deliberately does not require a client's script to equal
    the link's own: the link scripts the client, and the bundle is a description
    of the same workload.
    """
    if not isinstance(server, dict):
        raise ServerError("a server is a dict of link, clients and requests, not %r"
                          % (server,))
    for key in ("link", "clients", "requests"):
        if key not in server:
            raise ServerError("a server bundles %r, and this one has %r"
                              % (key, tuple(server)))
    link = server["link"]
    clients = server["clients"]
    requests = server["requests"]
    if not isinstance(link, Link):
        raise ServerError("a server's link is a Link, not %r" % (link,))
    if not isinstance(clients, (tuple, list)) or not clients:
        raise ServerError("a server's clients are a non-empty sequence, not %r"
                          % (clients,))
    for client in clients:
        if not isinstance(client, Client):
            raise ServerError("a client is a Client, not %r" % (client,))
    conns = link.conns()
    if len(conns) != len(clients):
        raise ServerError("the link holds %d connection(s) and the bundle names "
                          "%d client(s)" % (len(conns), len(clients)))
    for index, client in enumerate(clients):
        if conns[index].client.name != client.name:
            raise ServerError("client %d of the link is %r and the bundle names %r"
                              % (index, conns[index].client.name, client.name))
    if not isinstance(requests, dict):
        raise ServerError("a server's requests are a mapping of name to lines, "
                          "not %r" % (requests,))
    for client in clients:
        lines = requests.get(client.name)
        if not lines:
            raise ServerError("%r has no request lines in the bundle"
                              % (client.name,))
        if not isinstance(lines, (tuple, list)):
            raise ServerError("%s's requests are a non-empty sequence, not %r"
                              % (client.name, lines))
        for line in lines:
            if not isinstance(line, bytes):
                raise ServerError("a request is bytes, not %r" % (line,))
    return link, tuple(clients), requests


def _budget(budget):
    """A step budget: a count of steps, zero or more, or a refusal naming it.

    Zero is a legal budget — it says the model may take no turn at all, and the
    whole workload comes back `starved`. That is the point of the stage: the
    budget is a fact about this run rather than a precondition of it.
    """
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
        raise ServerError("a budget is a count of steps, zero or more, not %r"
                          % (budget,))
    return budget


def _starved(link, answers):
    """The clients whose requests the server never answered, in accept order.

    A client is starved when the model wrote fewer replies for it than its script
    has lines — the link's own count of the requests — so a client whose request
    was read and answered, even one the budget stopped the model from draining
    and closing, is *not* starved, and a client the model never reached is. It is
    deliberately not "everyone who is not served": a client cut off mid-service
    is neither served nor starved, and the difference between the two tuples is
    the whole verdict of this stage.
    """
    return tuple(conn.client.name for conn in link.conns()
                 if len(answers[conn.client.name]) < len(conn.client.requests))


def serve_blocking(server, *, budget=256):
    """Serve the bundle's clients one at a time, to completion, inside a budget.

    The loop is the oldest server there is: take the oldest waiting client, drive
    its stage-1 machine until the client has nothing left to send and has taken
    every byte the server wrote, close it, and only then look at the next one.
    No second client's request is ever read while the first is unanswered, which
    is what makes the model *blocking* — and what makes a client that drains its
    inbox every fourth tick the whole story of the run.

    One turn is one move of the current connection, and every turn lets the link
    move one tick, because the model has nothing to do but wait while the world
    carries the bytes and the client drains them. `steps` counts turns and
    `ticks` is the link's clock at the end; on this model they are equal, and
    that equality is the cost of a single thread of control.

    `answers` carries every client of the bundle, in the link's accept order: the
    reply lines the server wrote for it, in order, as whole lines (a reply the
    outbox took in two pieces is one entry), and an empty tuple for a client the
    budget never reached. `served` is the order the clients were taken to
    completion — for a blocking model the accept order — and `starved` is the
    clients with a request the server never answered, again in accept order.

    `budget` is a count of *steps*: the loop takes a turn only while it has one
    left, so a budget spent with work left is a result rather than an exception,
    and the caller can tell from `served`, `starved` and the link's own
    `bytes_drained` exactly how far it got.
    """
    link, clients, requests = _server(server)
    _budget(budget)
    answers = {conn.client.name: () for conn in link.conns()}
    served = ()
    steps = 0
    current = None
    state = None
    staged = b""
    while (link.waiting() or current is not None) and steps < budget:
        steps += 1
        if current is None:
            current = link.accept()
            if current is None:
                link.step(1)
                continue
            state = stage_01.open_conn(link, current.id)
            staged = b""
        move = stage_01.step_conn(link, state)
        if move["replies"] > state["replies"]:
            name = current.client.name
            answers[name] = answers[name] + (staged + move["reply"],)
            staged = b""
        elif move["event"] == "write":
            staged = staged + move["reply"]
        state = move
        link.step(1)
        if state["state"] == "closing":
            stage_01.finish(link, state)
            served = served + (current.client.name,)
            current = None
            state = None
    return {"answers": answers, "steps": steps, "ticks": link.now(),
            "served": served, "starved": _starved(link, answers)}
