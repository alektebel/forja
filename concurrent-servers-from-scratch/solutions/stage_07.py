"""Concurrent Servers From Scratch — stage 7: Futures and async/await as a desugaring.

SOLUTION. The desugaring, written out: `Future` is one answer settled once,
`await_` is the decision between "wait" and "value" that the `await` keyword
makes for you, `chain` drives a single coroutine and `Loop` drives many — and the
loop is the same event loop stages 4 to 6 built, with the order supplied by the
caller and a budget in steps. There is no `async def` in this file because there
is nothing left for it to do: a coroutine here is a step function, so it can be
called by anybody, in any order, and every claim this stage makes is a value a
check can compare.

Three facts decide most of the code. A future is settled *once*: a promise that
can change its answer is a promise whose second resumption is invisible, so
`settle` refuses the second one and says what the future already holds. `value()`
is the reading that raises and `result()` the reading that does not, and the
difference is the two callers a promise has — one that has asked `done()` and
wants to be told it asked too late, and one that must not be blown up by asking
at all. And a step function's answer is a *shape*: `{"wait": True}` or
`{"value": …}`, exactly one key each, so "still waiting" can never be confused
with "answered with something falsy" — which is why `await_` on a future settled
with `None` is a value and not a wait.

`serve_async` puts the loop under the world: every client the link is holding is
accepted, each connection gets a coroutine that drives stage 1's machine to
`"closing"` and then closes the connection, and the driver steps the link between
the loop's turns because `Link.step()` is the only thing that moves a byte. The
result keeps the four orders apart — answering, completion, spawn, and the
request the link is still holding — because a model that conflates them cannot be
compared with another model, and comparison is what stage 10 is for.
"""

from link import Client, Link

import stage_01 as s1

#: The longest chain `chain` drives before it reports the coroutine as still
#: waiting: `MAX_CHAIN` steps. A coroutine that has not answered by then is
#: waiting on the world rather than on itself, and the world is the loop's
#: business — `Loop.run` takes a budget, `chain` has nothing to budget against.
MAX_CHAIN = 64

#: The two states a chain can end in, in the order a coroutine meets them: a
#: coroutine that answered `{"wait": True}` is `"waiting"`, and one that answered
#: a value is `"done"`. The names are the tuple's, so a check can pin them
#: without reaching into the code that produced them.
CHAIN_STATES = ("waiting", "done")


class ServerError(ValueError):
    """A future, a coroutine or a loop this stage will not drive, named as what is wrong.

    It is the family for every shape the desugaring cannot honour: a second
    `settle` on a future that already holds an answer, a `value()` before there is
    one, an `await_` of something that is not a `Future`, a coroutine that answers
    neither `{"wait": True}` nor `{"value": …}`, a script that names a coroutine
    that was never spawned, a budget that is not a whole number of steps, and a
    server bundle that is not one. A verdict about an *answer* is never an
    exception: an unsettled future, a coroutine still waiting and a client whose
    request never went out are all values this stage returns.
    """


def _answer(answer):
    """A step function's answer, as `(waiting, value)`, or a refusal naming it.

    A coroutine answers exactly two shapes and nothing else: `{"wait": True}` —
    one key, holding `True` itself and not merely something truthy — and
    `{"value": …}`. Anything else is a shape this driver cannot read, so it is
    refused with the answer in the message instead of guessed at: a driver that
    guessed would report a coroutine as answered that never answered anything.
    """
    if not isinstance(answer, dict):
        raise ServerError("a coroutine answers with a dict, not %r" % (answer,))
    if tuple(answer) == ("wait",) and answer["wait"] is True:
        return True, None
    if tuple(answer) == ("value",):
        return False, answer["value"]
    raise ServerError("a coroutine answers {'wait': True} or {'value': ...}, "
                      "not %r" % (answer,))


def _budget(budget):
    """A run's budget: a whole number of steps of at least one, or a refusal.

    `True` is refused although it is an `int`, because a budget of `True` is a
    bug that runs for exactly one step and then looks like a budget honoured.
    """
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
        raise ServerError("a budget is a whole number of steps, at least one, "
                          "not %r" % (budget,))
    return budget


class Future:
    """One answer, settled exactly once, read in two ways: `value` or `result`.

    A future is not a value with a flag on it; it is the *promise* that the value
    will be there, which is why `done()` is a question of its own and why the two
    reads disagree: `value()` raises while the future is unsettled, and `result()`
    answers `{"done": False, "value": None}` instead. The value is any object —
    including `None` and `b""` — so a future is done because it was *settled* and
    never because its answer happens to look empty.
    """

    def __init__(self):
        """A future with no answer yet: not settled, and holding nothing.

        Every future starts here, and the two fields are the whole object: whether
        it has been settled, and what it was settled with. Nothing else in this
        stage writes them, and nothing reads the value without asking first.
        """
        self._settled = False
        self._value = None

    def settle(self, value):
        """Give the future its answer — once, and never again.

        This is the move that resumes whatever awaited the future, so a second
        `settle` is refused with `ServerError` naming the answer the future
        already holds: two settlements are two resumptions, and a coroutine that
        runs its second half twice is the failure a promise exists to prevent.
        `None` and `b""` are values like any other.
        """
        if self._settled:
            raise ServerError("a future is settled once: this one already holds "
                              "%r" % (self._value,))
        self._settled = True
        self._value = value

    def done(self):
        """Whether the future has been settled — the question `await_` asks.

        It answers about the *settlement*, not about the value: a future settled
        with `None` is done, and one holding `b""` is done too.
        """
        return self._settled

    def value(self):
        """The answer, refusing to invent one while the future is unsettled.

        This is the read for a caller that has already asked `done()` — and the
        refusal, naming that the future is unsettled, is how such a caller finds
        out that it asked too early. A caller that must not raise uses `result()`.
        """
        if not self._settled:
            raise ServerError("a future is unsettled: there is no value to read "
                              "until it is settled")
        return self._value

    def result(self):
        """`{"done", "value"}` — the non-raising read, in that order.

        While the future is unsettled the answer is `{"done": False, "value":
        None}`: there is nothing to raise about, because the question was "did it
        settle", not "what is the answer". This is the shape a callback is handed
        and the shape a check compares.
        """
        return {"done": self._settled,
                "value": self._value if self._settled else None}


def await_(future):
    """`await` as a function: `{"wait": True}` until settled, then `{"value": …}`.

    The answer is a *step function's* answer, so this one function is the whole of
    the desugaring: a coroutine awaiting a future is a step function that returns
    exactly this, the loop reads `"wait"` as "not ready, come back" and `"value"`
    as "here is the answer, and never come back". An unsettled future yields
    exactly `{"wait": True}` — not a value, not a flag, not polling — and a settled
    one yields the value itself, `None` and `b""` included. Anything that is not a
    `Future` is refused, naming it.
    """
    if not isinstance(future, Future):
        raise ServerError("await_ awaits a Future, not %r" % (future,))
    if not future.done():
        return {"wait": True}
    return {"value": future.value()}


def chain(coro):
    """Drive one coroutine's chain of steps to its answer, or to `MAX_CHAIN`.

    `coro` is a coroutine — a step function — and `chain` calls it one step at a
    time: `{"wait": True}` means there is more chain to come, `{"value": …}` means
    this is the answer. The result is `{"state", "value", "steps"}`: `"state"` is
    `"done"` with the value the coroutine answered, or `"waiting"` with `None`
    after `MAX_CHAIN` steps, and `"steps"` is how many times the coroutine was
    called. A coroutine that answers neither shape — and anything that is not
    callable — is refused, naming what was given.
    """
    if not callable(coro):
        raise ServerError("a coroutine is a step function, not %r" % (coro,))
    steps = 0
    while steps < MAX_CHAIN:
        waiting, value = _answer(coro())
        steps = steps + 1
        if not waiting:
            return {"state": CHAIN_STATES[1], "value": value, "steps": steps}
    return {"state": CHAIN_STATES[0], "value": None, "steps": steps}


class Loop:
    """The driver: coroutines as step functions, an order, and a step count.

    `script` is the order the loop visits its coroutines, cycled: a sequence of
    the names `spawn` was given, or `None` for round-robin from the spawn order.
    That order is *data the caller supplies* — this stage never invents an
    interleaving — and a script that names a coroutine that was never spawned is
    refused, naming it. A coroutine that has answered a value is finished and is
    never called again; a wait costs a step and changes nothing.
    """

    def __init__(self, script=None):
        """A loop with a visit order and no coroutines yet.

        `script` is `None` for round-robin from the spawn order, or a sequence of
        coroutine names giving the order to visit them in, cycled. A script that
        is a bare string, or holds something that is not a non-empty name, is
        refused, naming what was given: the order is a list of names and nothing
        else.
        """
        if script is None:
            self._script = None
        elif not isinstance(script, (tuple, list)):
            raise ServerError("a script is a sequence of coroutine names, not %r"
                              % (script,))
        else:
            for name in script:
                if not isinstance(name, str) or not name:
                    raise ServerError("a script names coroutines with non-empty "
                                      "strings, not %r" % (name,))
            self._script = tuple(script)
        self._entries = []
        self._cursor = 0
        self._values = {}
        self._finished = []

    def spawn(self, name, coro):
        """Register the step function `coro` under `name`; the handle is its order.

        A name is a non-empty string that no other coroutine has been spawned
        with, and a coroutine is callable; anything else is refused, naming the
        offender. The handle is 1 for the first spawn, 2 for the next, and so on
        — the spawn order the default script is the round-robin of.
        """
        if not isinstance(name, str) or not name:
            raise ServerError("a coroutine's name is a non-empty string, not %r"
                              % (name,))
        if not callable(coro):
            raise ServerError("a coroutine is a step function, not %r" % (coro,))
        for entry in self._entries:
            if entry["name"] == name:
                raise ServerError("two coroutines share the name %r" % (name,))
        self._entries.append({"name": name, "coro": coro, "done": False,
                              "value": None})
        return len(self._entries)

    def run(self, *, budget):
        """Drive the coroutines for at most `budget` steps, and say where they got to.

        One step is one coroutine called once. The answer is `{"values", "steps",
        "order", "done"}`: `"values"` is every value a coroutine has answered,
        keyed by name *in completion order*, `"order"` the same names as a tuple
        in the same order, `"steps"` what this run cost, and `"done"` whether
        every coroutine has answered. A wait is a step like any other, a finished
        coroutine is not called again, and a budget that is not a whole number of
        steps of at least one is refused, naming it.
        """
        _budget(budget)
        order = self._order()
        steps = 0
        while steps < budget:
            index = self._next(order)
            if index is None:
                break
            entry = self._entries[index]
            waiting, value = _answer(entry["coro"]())
            steps = steps + 1
            if waiting:
                continue
            entry["done"] = True
            entry["value"] = value
            self._values[entry["name"]] = value
            self._finished.append(entry["name"])
        return {"values": dict(self._values), "steps": steps,
                "order": tuple(self._finished), "done": self._all_done()}

    def _order(self):
        """The loop's cycle: the script's names in the script's order, or spawn order.

        The script is resolved against the coroutines that were actually spawned,
        so a name no `spawn` ever took is a refusal and not a silently shorter
        order — a check that wrote the order down wants to know it was used.
        Coroutines the script does not name are never visited, which is what a
        script with a client missing from it means.
        """
        if self._script is None:
            return tuple(range(len(self._entries)))
        order = []
        for name in self._script:
            for index, entry in enumerate(self._entries):
                if entry["name"] == name:
                    order.append(index)
                    break
            else:
                raise ServerError("the script names %r, which was never spawned"
                                  % (name,))
        return tuple(order)

    def _next(self, order):
        """The next coroutine to run: the first unfinished one, from the cursor on.

        The cursor is what makes the round-robin round: it is left pointing one
        past the coroutine that just ran, so a finished coroutine costs nothing
        and a wait does not hand the next step to the same coroutine twice in a
        row. Nothing unfinished and nothing at all are the same answer — `None`.
        """
        if not order:
            return None
        for offset in range(len(order)):
            index = order[(self._cursor + offset) % len(order)]
            if not self._entries[index]["done"]:
                self._cursor = (self._cursor + offset + 1) % len(order)
                return index
        return None

    def _all_done(self):
        """Whether every coroutine has answered a value."""
        for entry in self._entries:
            if not entry["done"]:
                return False
        return True


def _server_link(server):
    """The link of a server bundle, refusing a bundle that is not one.

    The bundle is the one stages 2 to 6 are handed — `{"link", "clients",
    "requests"}` — and it is checked rather than trusted: the link is a `Link`,
    the clients are the world's own `Client` objects, and each one's `requests`
    are that client's script and not a second list that could disagree with it.
    """
    if not isinstance(server, dict):
        raise ServerError("a server is a dict like {'link', 'clients', "
                          "'requests'}, not %r" % (server,))
    for key in ("link", "clients", "requests"):
        if key not in server:
            raise ServerError("a server is missing %r" % (key,))
    link = server["link"]
    if not isinstance(link, Link):
        raise ServerError("a server's link is a Link, not %r" % (link,))
    clients = server["clients"]
    if not isinstance(clients, (tuple, list)) or not clients:
        raise ServerError("a server's clients are a non-empty sequence of "
                          "Clients, not %r" % (clients,))
    for client in clients:
        if not isinstance(client, Client):
            raise ServerError("a server's client is a Client, not %r" % (client,))
    requests = server["requests"]
    if not isinstance(requests, dict):
        raise ServerError("a server's requests are a mapping from a name to its "
                          "lines, not %r" % (requests,))
    for client in clients:
        lines = requests.get(client.name)
        if not isinstance(lines, (tuple, list)) or tuple(lines) != client.requests:
            raise ServerError("the lines of %r are its own script, not %r"
                              % (client.name, lines))
    return link


def _accepted(link):
    """Every client the link is holding, in accept order, as a fresh tuple.

    Accepting is the server's move and this is all of it: the backlog is emptied
    now, oldest client first, so each accepted connection can be given its
    coroutine before the loop starts. A client that has not arrived yet is not in
    the backlog, so it is not served by this run — and saying so is what
    `starved` is for.
    """
    conns = []
    while True:
        conn = link.accept()
        if conn is None:
            break
        conns.append(conn)
    return tuple(conns)


def _connection(link, conn, log):
    """One connection as a coroutine: stage 1's machine stepped, and then closed.

    The coroutine answers `{"wait": True}` for every step the machine still has to
    take, and its value when the machine is `"closed"` is the last reply it wrote
    — `b""` for a client that dropped before it was answered. Each reply is
    recorded only once its *last* byte is out, so a reply the bounded outbox takes
    in two writes is one answer and not two; the record is `(name, reply)` in the
    order the replies went out, which is the answering order `serve_async`
    reports.
    """
    carry = {"machine": s1.open_conn(link, conn.id), "pieces": [], "answers": [],
             "written": 0}

    def step():
        machine = carry["machine"]
        machine = s1.step_conn(link, machine)
        if machine["event"] == "write":
            carry["pieces"].append(machine["reply"])
            if machine["replies"] > carry["written"]:
                carry["written"] = machine["replies"]
                answer = b"".join(carry["pieces"])
                carry["pieces"] = []
                carry["answers"].append(answer)
                log.append((conn.client.name, answer))
        if machine["state"] == "closing":
            machine = s1.finish(link, machine)
        carry["machine"] = machine
        if machine["state"] == "closed":
            return {"value": carry["answers"][-1] if carry["answers"] else b""}
        return {"wait": True}

    return step


def _starved(link, conn):
    """Whether the link is still holding this connection's request, unanswered.

    This is the only honest definition at a budget's end: the request went in (or
    is still going in) and no reply has started, so the model owes this client an
    answer. A connection that was answered and is waiting for its slow reader to
    drain it is *not* starved — the link is holding an answer, not a question —
    and neither is one the client itself dropped.
    """
    if conn.closed:
        return False
    return link.readable(conn) or link.owed(conn)


def serve_async(server, *, script=None, budget=256):
    """The server again, driven by the loop: one coroutine per connection.

    `server` is the world and its scripted clients — `{"link", "clients",
    "requests"}`, the bundle stages 2 to 6 are handed as well. Every client the
    link is holding is accepted and given a coroutine that drives stage 1's
    machine to `"closing"` and then closes the connection. The driver takes the
    loop's turns, one step at a time, and steps the link between them, because
    `Link.step()` is the only thing in this world that moves a byte.

    The answer is `{"answers", "steps", "ticks", "served", "starved", "order",
    "values"}`: `"answers"` is each client's replies in accept order, `"steps"`
    what the driver cost, `"ticks"` the link's own clock, `"served"` the
    completion order, `"starved"` the clients whose request the link is still
    holding, `"order"` the answering order — one entry per reply that went out —
    and `"values"` the answers in completion order. `script` is the loop's visit
    order and `budget` is in steps: a budget spent with work left is a result and
    not an exception, and `starved` is what says so.
    """
    link = _server_link(server)
    _budget(budget)
    loop = Loop(script)
    log = []
    conns = _accepted(link)
    for conn in conns:
        loop.spawn(conn.client.name, _connection(link, conn, log))
    steps = 0
    finished = ()
    values = {}
    while steps < budget:
        turn = loop.run(budget=1)
        steps = steps + (turn["steps"] or 1)
        link.step(1)
        finished = turn["order"]
        values = turn["values"]
        if turn["done"] and link.done():
            break
    answers = {}
    for conn in conns:
        answers[conn.client.name] = tuple(reply for name, reply in log
                                          if name == conn.client.name)
    return {"answers": answers, "steps": steps, "ticks": link.stats()["ticks"],
            "served": finished,
            "starved": tuple(conn.client.name for conn in conns
                             if _starved(link, conn)),
            "order": tuple(name for name, _ in log),
            "values": tuple(values[name] for name in finished)}
