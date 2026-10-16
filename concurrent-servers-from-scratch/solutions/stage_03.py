"""Concurrent Servers From Scratch — stage 3: Threads, and the interleaving the check chooses.

SOLUTION. Stage 2 serves one client at a time and the slow client stops everyone;
the repair is not a thread library but a *choice*: N connections, each carried by
a step function, and the order they take turns in is data the caller hands in.
This stage owns that choice twice over — `Scheduler` is the mechanism (spawn,
ready, step, run) and `serve_threads` is the policy (one thread per connection
over stage 1's machine) — and the `script` the check passes is the interleaving
the check chose.

A thread here owns no stack: it is called once per turn, keeps its memory in the
context it was spawned with, and answers `"more"`, `"blocked"` or `"done"`. The
scheduler knows nothing about links — that is exactly what makes it reusable —
and `serve_threads` is the model that does know: a turn is one move of one
connection's machine, and a turn with nothing to move spends itself on the link's
tick, because a thread per connection cannot wait for the client's drain without
someone spending a turn on time. So `"blocked"` is never a client's verdict in
this model; it is the scheduler's verdict about a thread waiting for a turn
nobody will take, and a run that ends with every remaining thread blocked says so
with their names instead of spinning.
"""

import link
import stage_01

#: The three answers a step function may give: it has more to do, it is waiting
#: for something another thread must do, or it has finished. Nothing else — a
#: step function that forgets to answer is refused rather than counted.
STEP_STATES = ("more", "blocked", "done")

#: What the scheduler calls a thread between turns: it can run now, it is waiting
#: on the round, or it is done. `"more"` becomes `"ready"`; the other two answers
#: *are* the states they leave behind. The two vocabularies are kept apart on
#: purpose: `step` reports both, so a check holds them against each other instead
#: of inferring one from the other.
THREAD_STATES = ("ready", "blocked", "done")

#: The three pieces of the bundle `serve_threads` drives: the world, the clients
#: in the order they arrived, and the request lines each client will send.
_SERVER_KEYS = ("link", "clients", "requests")


class ServerError(ValueError):
    """A thread the scheduler will not spawn, a turn it will not take, a bundle it cannot drive.

    It is the family for every shape this stage cannot honour: a name that is not
    a non-empty string, a step function that is not callable, a name already
    spawned, a script that is not a sequence of names, a turn for a thread nobody
    spawned or for one that has finished, a step function that answers something
    that is not one of `STEP_STATES`, a `budget` that is not a count of turns, and
    a `server` whose three pieces do not describe one workload. A verdict about
    what the *threads* did is never an exception: a blocked thread, a deadlocked
    round and a budget spent are all returned, and a check asserts them as values.
    """


def _text(value, what):
    """A name: a non-empty string, or a refusal naming what was given."""
    if not isinstance(value, str) or not value:
        raise ServerError("%s is a non-empty string, not %r" % (what, value))
    return value


def _script(script):
    """The turn order as a tuple of names, or `()` for plain round-robin.

    A script is data the caller chooses, so it is validated once, here: it must be
    a tuple or a list of non-empty strings, and every entry must be one. Whether
    the names exist is not knowable yet — threads are spawned after — so that
    refusal belongs to the turn itself.
    """
    if script is None:
        return ()
    if not isinstance(script, (tuple, list)):
        raise ServerError("a script is a sequence of thread names, not %r" % (script,))
    for entry in script:
        if not isinstance(entry, str) or not entry:
            raise ServerError("a script names threads: %r is not a name" % (entry,))
    return tuple(script)


def _budget(budget):
    """A run's step bound: an int of at least zero, or a refusal naming it."""
    if isinstance(budget, bool) or not isinstance(budget, int):
        raise ServerError("a budget is a number of steps, not %r" % (budget,))
    if budget < 0:
        raise ServerError("a budget is at least zero steps, not %r" % (budget,))
    return budget


class _Thread:
    """One spawned step function: its handle, its name, and where it is between turns."""

    def __init__(self, handle, name, fn, args):
        self.handle = handle
        self.name = name
        self.fn = fn
        self.args = args
        self.state = "ready"

    def __repr__(self):
        return "_Thread(%d, %r, %s)" % (self.handle, self.name, self.state)


class Scheduler:
    """N step functions, and whose turn it is — chosen by the caller, not by luck.

    A thread is a step function: `spawn` takes it, `step` calls it once, and what
    it answers (`"more"`, `"blocked"`, `"done"`) is the whole of its state between
    turns. There is no stack, no thread library and no clock of its own: the
    interleaving is a `script` of names, or round-robin in spawn order, and the
    caller can hold either one against the run's own result.

    The scheduler is deliberately ignorant of the world it may be driving: it
    never steps a link and never looks at a connection, so `serve_threads` here —
    and stage 7's `Loop`, which is the same loop desugared — can put whatever
    policy they like on top of the same four methods.
    """

    def __init__(self, script=None):
        """A scheduler over no threads, with the interleaving the caller chose.

        `script` is a tuple of thread names: the turn each entry of the run takes,
        in order. A script that runs out is not an error — the rest of the run is
        round-robin from the spawn order — so a script is the prefix the check
        chose and never a ceiling. Without a script every turn is round-robin.
        """
        self.script = _script(script)
        self.threads = []
        self._by_name = {}
        self._cursor = 0
        self._script_at = 0
        self._offered = set()

    def spawn(self, name, fn, *args):
        """Spawn `name`'s step function and hand back its handle, from 1 upwards.

        `fn` is called as `fn(*args)` — once per turn, and whatever it keeps
        between turns it keeps in those arguments, since it has no stack — and it
        answers one of `STEP_STATES`. The handle is the thread's identity in
        `ready()` and in every `step()` answer: handles are given in spawn order
        and never reused, so a handle is stable even when a thread spawns another
        one mid-run. A name that is not a non-empty string, a `fn` that is not
        callable, and a name already spawned are each refused naming what was
        given — a script picks a turn by *name*, so two threads may not share one.
        """
        _text(name, "a thread's name")
        if not callable(fn):
            raise ServerError("a thread's step function is callable, not %r" % (fn,))
        if name in self._by_name:
            raise ServerError("a thread named %r is already spawned" % (name,))
        thread = _Thread(len(self.threads) + 1, name, fn, args)
        self.threads.append(thread)
        self._by_name[name] = thread
        return thread.handle

    def ready(self):
        """The handles that can run now, in spawn order.

        A thread is ready when it has neither finished nor answered `"blocked"`:
        `"blocked"` is exactly "not now", and a thread given a turn it cannot use
        is a thread the scheduler is spinning on. Blocked is a *round* verdict
        rather than a death sentence, so a thread that answered `"blocked"` is
        ready again once every remaining thread has had its turn: the others'
        work — or the turn each of them spends on the world — is what a waiter is
        waiting for.
        """
        return tuple(thread.handle for thread in self.threads
                     if thread.state == "ready")

    def step(self):
        """The next turn: one step function called once, or one turn skipped.

        Whose turn it is comes from the script while it has entries left and from
        the round-robin afterwards. The answer is `{"handle", "name", "state",
        "yielded"}`: `yielded` is what the step function itself answered — one of
        `STEP_STATES` — and `state` is where that answer leaves the thread
        (`"more"` → `"ready"`, the other two themselves). A thread that is already
        blocked is *skipped*: the turn is offered, nothing is called, and `yielded`
        is `None`, which is how a caller can tell a turn that was spent from a
        turn that was taken.

        Three shape mismatches are refusals rather than verdicts, each naming the
        offender: a script entry that names a thread nobody spawned, a turn for a
        thread that has already finished — the script's rhythm and the run's no
        longer agree, and carrying on would quietly report an order nobody chose —
        and a step function that answers something that is not one of
        `STEP_STATES`. A turn when there is no thread left at all is refused too:
        there is nothing to run, and that is not a verdict about content.
        """
        thread = self._next()
        if thread.state == "done":
            raise ServerError("the turn is for %r, which has finished" % (thread.name,))
        if thread.state == "blocked":
            self._offer(thread)
            return {"handle": thread.handle, "name": thread.name,
                    "state": thread.state, "yielded": None}
        answered = thread.fn(*thread.args)
        if answered not in STEP_STATES:
            raise ServerError("a step function answers one of %r, not %r"
                              % (list(STEP_STATES), answered))
        thread.state = "ready" if answered == "more" else answered
        self._offer(thread)
        return {"handle": thread.handle, "name": thread.name,
                "state": thread.state, "yielded": answered}

    def run(self, *, budget):
        """Run the threads until they are done, blocked everywhere, or out of budget.

        The answer is `{"finished", "steps", "order", "blocked"}`: `order` is the
        names in the order the threads *finished* — the answering order, not the
        spawn order — and `blocked` is who was waiting when the run stopped.
        `finished` is `True` only when every thread answered `"done"`.

        Two ways to stop early, and neither is an exception. A round in which every
        remaining thread answered `"blocked"` is a deadlock: no thread can run,
        and the turns a waiter waits for are not coming — the run returns the
        names instead of spinning. `budget` bounds the step count and is checked
        *before* a turn and never after, so a run that hits the bound took exactly
        `budget` steps; a skipped turn is not a step, because nothing was called.

        The script is consulted only while a turn is left to take, so a script
        longer than the work is harmless; one that names a finished thread *while
        work remains* is the refusal `step` describes, and it is raised rather than
        absorbed because the rest of the run would otherwise come out in an order
        nobody chose.
        """
        _budget(budget)
        steps = 0
        order = []
        while True:
            remaining = [thread for thread in self.threads
                         if thread.state != "done"]
            if not remaining:
                return {"finished": True, "steps": steps,
                        "order": tuple(order), "blocked": ()}
            stuck = self._stuck()
            if stuck is not None:
                return {"finished": False, "steps": steps,
                        "order": tuple(order), "blocked": stuck}
            if steps >= budget:
                return {"finished": False, "steps": steps,
                        "order": tuple(order), "blocked": ()}
            turn = self.step()
            if turn["yielded"] is None:
                continue
            steps += 1
            if turn["state"] == "done":
                order.append(turn["name"])

    def _next(self):
        """Whose turn it is: the script's next entry, or the round-robin's next thread."""
        if self._script_at < len(self.script):
            name = self.script[self._script_at]
            self._script_at += 1
            thread = self._by_name.get(name)
            if thread is None:
                raise ServerError("the script names %r, which is not spawned"
                                  % (name,))
            return thread
        return self._round_robin()

    def _round_robin(self):
        """The next thread that can run now, or — if none can — the oldest waiter.

        The cursor walks the spawn order one turn at a time and is kept on the
        instance, so a thread spawned in the middle of a run takes its place in
        the order like any other. A blocked thread is stepped over: only when
        *every* remaining thread is blocked does the walk hand back a waiter, which
        is the skipped turn a caller sees as `yielded is None`.
        """
        waiting = None
        for offset in range(len(self.threads)):
            index = (self._cursor + offset) % len(self.threads)
            thread = self.threads[index]
            if thread.state == "done":
                continue
            if thread.state == "ready":
                self._cursor = (index + 1) % len(self.threads)
                return thread
            if waiting is None:
                waiting = (index, thread)
        if waiting is not None:
            self._cursor = (waiting[0] + 1) % len(self.threads)
            return waiting[1]
        raise ServerError("no thread is left to run: every thread has finished")

    def _offer(self, thread):
        """Record the turn, and start a new round once every remaining thread had one.

        A round that blocked everywhere is *not* cleared: it is the verdict `run`
        reports, and erasing it here would hide it before anyone could read it.
        """
        self._offered.add(thread.handle)
        left = {other.handle for other in self.threads if other.state != "done"}
        if self._offered >= left and self._stuck() is None:
            self._offered = set()
            for other in self.threads:
                if other.state == "blocked":
                    other.state = "ready"

    def _stuck(self):
        """The names of the waiters when every thread that is left is one, else `None`."""
        remaining = [thread for thread in self.threads if thread.state != "done"]
        if remaining and all(thread.state == "blocked" for thread in remaining):
            return tuple(thread.name for thread in remaining)
        return None


def _bundle(server):
    """The link and the clients of a `server`, or a refusal naming what is wrong.

    The bundle is the workload as data: the world, the scripted clients in the
    order they arrived, and the request lines each client will send. Everything
    this stage cannot drive is refused here, once, before a thread is spawned — a
    missing key, a link that is not the world's own link, a client the link does
    not have in that place, a name with no scripted requests, a request that is
    not `bytes`. The one thing *not* checked is whether the scripted requests
    match what the client will actually send: the link is the arbiter of that, and
    a model that trusted the bundle over the world would be grading itself.
    """
    if not isinstance(server, dict):
        raise ServerError("a server is a mapping carrying %r, not %r"
                          % (list(_SERVER_KEYS), server))
    for key in _SERVER_KEYS:
        if key not in server:
            raise ServerError("a server carries %r, and this one has no %r"
                              % (list(_SERVER_KEYS), key))
    world = server["link"]
    clients = server["clients"]
    requests = server["requests"]
    if not isinstance(world, link.Link):
        raise ServerError("a server's link is a Link, not %r" % (world,))
    if not isinstance(clients, (tuple, list)) or not clients:
        raise ServerError("a server's clients are a non-empty sequence, not %r"
                          % (clients,))
    if not isinstance(requests, dict):
        raise ServerError("a server's requests are a mapping of name to lines, "
                          "not %r" % (requests,))
    conns = world.conns()
    if len(conns) != len(clients):
        raise ServerError("the link carries %d client(s) and the server names %d"
                          % (len(conns), len(clients)))
    for conn, client in zip(conns, clients):
        name = getattr(client, "name", None)
        if name != conn.client.name:
            raise ServerError("connection %d belongs to %r, not to %r"
                              % (conn.id, conn.client.name, name))
        if name not in requests:
            raise ServerError("no request line is scripted for %r" % (name,))
        lines = requests[name]
        if not isinstance(lines, (tuple, list)) or not lines:
            raise ServerError("the requests of %r are a non-empty sequence, not %r"
                              % (name, lines))
        for line in lines:
            if not isinstance(line, bytes):
                raise ServerError("a request of %r is bytes, not %r"
                                  % (name, line))
    return world, tuple(clients)


def _accept(world, conn):
    """Take this thread's own connection off the backlog, if it is the world's next.

    `Link.accept()` hands back the *oldest* client waiting, so a thread may only
    accept when its own connection is at the head of the backlog; otherwise this
    turn buys the world a tick instead. That keeps the accept order the world's
    own — the order the clients arrived — whatever order the script serves them in,
    and it is also what a client that has not arrived yet waits on.
    """
    waiting = world.waiting()
    if not waiting or waiting[0] != conn.id:
        return False
    return world.accept() is not None


def _turn(context):
    """One turn of one client's thread: accept, one move, or the world's tick.

    The context is the thread's memory — the link, its own connection, stage 1's
    machine, the reply it is halfway through writing, and the lists it reports
    into — because a step function has no stack to keep anything in.

    A turn does one thing: it takes the connection off the backlog (once), it makes
    one move of the machine, or — when the machine has nothing to move — it gives
    the link a tick. The tick is the model's wait: a client that is draining its
    inbox at its own pace, or an outbox the link has not carried yet, is waited out
    by spending turns on time rather than by spinning on `read`, and each of those
    turns is counted, which is why this model's step count says what it cost. The
    thread is `"done"` when the machine has reached `closing` — every request
    answered and every answer taken — and `finish` is the move that closes the
    connection; it never answers `"blocked"`, because a thread that blocked would
    need somebody else to spend the turns it is no longer spending.
    """
    world = context["link"]
    conn = context["conn"]
    if context["machine"] is None:
        if not _accept(world, conn):
            world.step(1)
            return "more"
        context["machine"] = stage_01.open_conn(world, conn.id)
    machine = context["machine"]
    answered = machine["replies"]
    move = stage_01.step_conn(world, machine)
    context["machine"] = move
    if move["event"] == "write":
        context["pending"] += move["reply"]
        if move["replies"] > answered:
            context["answers"].append(context["pending"])
            context["pending"] = b""
            context["order"].append(conn.client.name)
    if move["event"] == "idle":
        if move["state"] == "closing":
            context["machine"] = stage_01.finish(world, move)
            return "done"
        world.step(1)
        return "more"
    return "more"


def serve_threads(server, *, script=None, budget=256):
    """The same server as `serve_blocking`, one thread per connection.

    `server` is the bundle stage 2 drives — `{"link", "clients", "requests"}`: the
    world, the scripted clients in the order they arrived, and the request lines
    each will send. One thread is spawned per client, named after it, and each
    thread owns stage 1's machine for its own connection: a turn is one move of
    that machine, and a turn with no move to make spends itself on the link's tick.
    The script names clients, so it *is* the interleaving — `("slow", "fast",
    "fast", …)` is a run in which the slow client answers first — and without one
    the turns are round-robin from the accept order.

    The answer is `serve_blocking`'s — `{"answers", "steps", "ticks", "served",
    "starved"}` — plus `"order"`: the names in the order the answers went out.
    `served` says who finished, `order` says when each answer was delivered, so the
    interleaving the script chose is visible in the result rather than inferred
    from it; `starved` is the clients the budget left unanswered, `ticks` is what
    the link's clock spent on waiting, and `answers` is what this model wrote — a
    reply the outbox never took is caught by the link's own log, not by this dict.
    """
    world, clients = _bundle(server)
    scheduler = Scheduler(script)
    answers = {client.name: [] for client in clients}
    order = []
    for conn in world.conns():
        context = {"link": world, "conn": conn, "machine": None, "pending": b"",
                   "answers": answers[conn.client.name], "order": order}
        scheduler.spawn(conn.client.name, _turn, context)
    run = scheduler.run(budget=budget)
    served = run["order"]
    return {"answers": {name: tuple(lines) for name, lines in answers.items()},
            "steps": run["steps"], "ticks": world.now(), "served": served,
            "starved": tuple(name for name in answers if name not in served),
            "order": tuple(order)}
