"""Concurrent Servers From Scratch — stage 6: Callbacks as data, and the one that must not run.

The four models before this one all answer a request inside the turn that reads
it. Real servers do not: they read a line, put the answer on a *queue* — a
callback to run when the loop gets to it — and return to the loop, which is free
to do something else first. That queue is this stage, and it is the last thing
between L2 and libuv: once a pending answer is data in a table, cancellation is a
table operation, futures (stage 7) are a promise to settle later, and the loop
that drains the table is the event loop.

The whole stage is therefore a *table* and a *loop over it*. `Handles` is the
table: `register` issues a handle and stores the callback as the 4-tuple
`(handle, name, fn, args)`; `ready` is the handles still to run, in registration
order; `take` pops one; `cancel` retires one without running it. `serve_callbacks`
is the loop: each turn it accepts whoever has arrived, reads every readable
connection's bytes, splits them into lines, registers one callback per line,
retires the connections whose client is done, dispatches exactly *one* callback,
and gives the link one tick.

Two facts decide the shapes below. A callback is **data**, never a closure over
the loop: the connection it will answer and the line it will answer with travel
in its `args`. The loop's own variables — `conn`, the chunk just read, the line
just split — are overwritten on the next iteration, so a callback that reached
for them would answer the *last* connection of the turn with the *last* line of
the turn: the classic late-binding bug, and the reason `answers` above is keyed
by the name the callback carries rather than by whatever the loop happens to
hold. And a callback is a verdict about a *connection that may have moved on*:
between the turn that read the line and the turn that would write the answer,
the client's patience may have run out and the link closed the connection. That
callback must not run — its reply would go into a closed connection, and the
closed connection is not an error, it is the normal outcome of a client that
gave up waiting. It is `skipped`, with its name in the result, and that is the
one rule this stage exists for.

A turn is the loop's unit of work, so `steps` counts dispatches and the reads and
the tick that come with them, and `budget` bounds turns. One consequence is worth
stating plainly: the loop's completion test is not "the reply was written" but
"the client drained it", because a connection closed while its reply still sits
in the client's inbox is a server that answered and delivered nothing — the
`bytes_drained` in the link's own log is what says so.

    Handles          the table of callbacks, in registration order, with
                     cancellation: register, cancel, ready, take
    serve_callbacks  the loop: read a line, register a callback, dispatch one
    ServerError      the family every refusal belongs to
"""

from link import Client, Link
from stage_01 import REPLY_PREFIX

#: The protocol's one byte, as the `bytes` a reply is built from. The prefix is
#: applied once, when the line becomes a reply, and never while it is carried.
_PREFIX = REPLY_PREFIX.encode("ascii")


class ServerError(ValueError):
    """A shape this stage will not honour, named as what is wrong.

    It is the family for a name that is not a name, a callback that is not
    callable, a handle this table never issued, a server that is not a server,
    and a budget that is not a positive count of turns. A verdict about what the
    *world* did is never an exception: a connection whose client's patience ran
    out, a callback the loop cancelled and a callback whose connection had
    closed are all results, and the check asserts them as values.
    """


def _handle(handle):
    """A handle this table could have issued: an int of at least one."""
    if isinstance(handle, bool) or not isinstance(handle, int):
        raise ServerError("a callback's handle is an int, not %r" % (handle,))
    if handle < 1:
        raise ServerError("a callback's handle is at least 1, not %r" % (handle,))
    return handle


def _budget(budget):
    """A budget: a positive count of turns, or a refusal naming what was given."""
    if isinstance(budget, bool) or not isinstance(budget, int):
        raise ServerError("a budget is an int, not %r" % (budget,))
    if budget < 1:
        raise ServerError("a budget is at least one turn, not %r" % (budget,))
    return budget


class Handles:
    """The callback table: handles in registration order, with cancellation.

    The table owns three facts and no others. `_order` is every handle this
    table has issued, in registration order, which is what makes `ready` an
    order and not a set. `_table` is the callbacks still to run, keyed by
    handle: `take` and `cancel` both remove from it, so a handle leaves the
    table exactly once. `_gone` is the handles that have left it, which is why
    cancelling twice is not an error and why a handle that was never issued is.

    Nothing here is a closure and nothing here is a loop variable: a callback
    is the 4-tuple `(handle, name, fn, args)`, and `args` is the whole of what
    the callback will know when it runs.
    """

    def __init__(self):
        """A table with nothing in it; handles are issued from one upwards."""
        self._order = []
        self._table = {}
        self._gone = set()
        self._next = 1

    def register(self, name, fn, *args):
        """Put the callback `(name, fn, args)` in the table; hand back its handle.

        Handles are issued from one upwards, one per registration, so the
        registration order of a table is the order of its handles. `name` is
        what the result will call this callback when it ran, was skipped or was
        cancelled, so it has to be a non-empty string; `fn` is what will be
        called with `args` when its turn comes, so it has to be callable.
        Registering the same name twice is allowed: two callbacks that differ
        only in `args` are still two callbacks, and that is the case the
        late-binding bug gets wrong.
        """
        if not isinstance(name, str) or not name:
            raise ServerError("a callback's name is a non-empty string, not %r"
                              % (name,))
        if not callable(fn):
            raise ServerError("a callback is callable, not %r" % (fn,))
        handle = self._next
        self._next += 1
        self._order.append(handle)
        self._table[handle] = (handle, name, fn, args)
        return handle

    def cancel(self, handle):
        """Retire the callback `handle` without running it; True once, then False.

        Cancelling is a decision about a callback, not about a connection, so it
        is the caller's move and the table has no opinion about why. A handle
        this table never issued is a refusal naming it — a cancellation that
        silently did nothing is a callback that runs after the code that tried to
        stop it. Cancelling a handle that is already gone answers `False`: the
        first cancel is the one that changed the table.
        """
        _handle(handle)
        if handle not in self._table:
            if handle in self._gone:
                return False
            raise ServerError("no callback was registered with handle %r"
                              % (handle,))
        self._table.pop(handle)
        self._gone.add(handle)
        return True

    def ready(self):
        """The handles still to run, in registration order, as a fresh tuple.

        Cancelled and already-taken handles are not here: a callback the caller
        retired is a callback the loop must not dispatch, and a table that kept
        it "for the record" would be a table that runs it. The order is the
        registration order and never the order of cancelling or taking, because
        the order of callbacks is the order a server promised its clients.
        """
        return tuple(handle for handle in self._order if handle in self._table)

    def take(self, handle):
        """Pop the callback `handle` and hand back its 4-tuple, or `None`.

        `None` is the answer for every handle there is nothing to hand back for:
        one that was already taken, one that was cancelled, and one that was
        never issued. That is a verdict and not a refusal — asking for what is
        not there is how a loop says "nothing for me this time" — while a handle
        that is not a handle at all is a shape and is refused.
        """
        _handle(handle)
        entry = self._table.pop(handle, None)
        if entry is None:
            return None
        self._gone.add(handle)
        return entry


def _server(server):
    """The link and the clients a server dict carries, or a refusal naming it."""
    if not isinstance(server, dict):
        raise ServerError("a server is a dict, not %r" % (server,))
    for key in ("link", "clients"):
        if key not in server:
            raise ServerError("a server has no %r, and %r is what it has"
                              % (key, sorted(server)))
    link = server["link"]
    if not isinstance(link, Link):
        raise ServerError("a server's link is a Link, not %r" % (link,))
    clients = server["clients"]
    if not isinstance(clients, (tuple, list)) or not clients:
        raise ServerError("a server's clients are a non-empty sequence, not %r"
                          % (clients,))
    for client in clients:
        if not isinstance(client, Client):
            raise ServerError("a server's client is a Client, not %r" % (client,))
    return link, tuple(clients)


def _answer(link, conn, line):
    """The callback body: write the reply for this connection, and say what went.

    Its whole world is its `args` — the link, the connection this callback was
    registered for, and the line it answers — which is what makes it data the
    loop can hold in a table. It returns the reply so that the loop can record
    it against *this* connection's name.
    """
    reply = _PREFIX + line
    link.write(conn, reply)
    return reply


def _name_of(conn):
    """What this connection's callback for the request in flight is called."""
    return "%s:%d" % (conn.client.name, conn.request + 1)


def _accept(link, serving):
    """Take every client the listener is holding, oldest first."""
    while True:
        conn = link.accept()
        if conn is None:
            return
        serving.append(conn)


def _read_lines(link, serving, handles, buffers):
    """Read what is readable, split it into lines, register one callback per line.

    The partial line each connection is holding travels in `buffers`, keyed by
    the connection's id, and not in a variable the next connection would
    overwrite: a line may arrive in pieces, and the pieces of two connections
    must never be assembled into one line. The line that is whole becomes a
    callback's `args`, which is where it stops being the loop's business.
    """
    for conn in serving:
        while link.readable(conn):
            line = buffers.get(conn.id, b"") + link.read(conn)
            while b"\n" in line:
                head, _, line = line.partition(b"\n")
                handles.register(_name_of(conn), _answer, link, conn, head + b"\n")
            buffers[conn.id] = line


def _finished(link, conn):
    """Whether this connection has nothing left to do in either direction.

    Three questions, and the third is the one that is easy to skip: the client
    has no more requests to send, the link has nothing to read, owing or carry —
    and the client has *drained* everything it was sent. A connection whose reply
    is still sitting in its inbox is not finished, because closing it there
    answers the request and delivers nothing, and the link's `bytes_drained` is
    the number that shows it.
    """
    if conn.inbox:
        return False
    if not link.idle(conn):
        return False
    return conn.request + 1 >= len(conn.client.requests)


def _retire(link, serving):
    """Close the connections whose client is done, and only those."""
    for conn in serving:
        if _finished(link, conn):
            link.close(conn)


def _dispatch(handles):
    """The one callback this turn runs: the oldest ready one, or `None`."""
    ready = handles.ready()
    if not ready:
        return None
    return handles.take(ready[0])


def serve_callbacks(server, *, budget=256):
    """Serve every client of `server` by registering a callback per request line.

    Returns `{"answers", "steps", "ran", "cancelled", "skipped"}`. `answers` is
    the replies each client received, in order, keyed by the client's name — the
    callback's own name, from its own `args`, and never the loop's last
    connection. `steps` is the turns the loop took, one per dispatch, so a
    `budget` spent with callbacks still queued is an outcome and not an
    exception. `ran` is the names of the callbacks that ran, in the order they
    ran, and that order is the registration order.

    `skipped` is the rule the stage exists for: a callback whose connection has
    since closed — the client's patience spent while the answer waited its turn
    — must not run, and is recorded here by name instead. It is not an error, it
    is what a server owes a client that has already gone. `cancelled` is the
    loop's own verdict on the callbacks it never reached: at the end of the
    budget every callback still in the table is taken, and one whose connection
    is fine is cancelled while one whose connection has closed is skipped, so
    no callback is ever quietly kept "for the record" and run later.
    """
    link, clients = _server(server)
    _budget(budget)
    handles = Handles()
    answers = {client.name: [] for client in clients}
    buffers = {}
    serving = []
    ran = ()
    cancelled = ()
    skipped = ()
    steps = 0
    while steps < budget:
        steps += 1
        _accept(link, serving)
        _read_lines(link, serving, handles, buffers)
        _retire(link, serving)
        entry = _dispatch(handles)
        if entry is not None:
            handle, name, fn, args = entry
            conn = args[1]
            if conn.closed:
                skipped += (name,)
            else:
                answers[conn.client.name].append(fn(*args))
                ran += (name,)
        link.step(1)
        if not link.waiting() and all(conn.closed for conn in serving):
            break
    for handle in handles.ready():
        entry = handles.take(handle)
        name = entry[1]
        if entry[3][1].closed:
            skipped += (name,)
        else:
            cancelled += (name,)
    return {"answers": {name: tuple(lines) for name, lines in answers.items()},
            "steps": steps,
            "ran": ran,
            "cancelled": cancelled,
            "skipped": skipped}
