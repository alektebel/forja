"""Concurrent Servers From Scratch — stage 6: Callbacks as data, and the one that must not run.

Every model so far answers a request inside the turn that reads it. A real server
does something else: it reads a line, puts the answer on a *queue* — a callback
to run when the loop gets to it — and goes back to the loop, which is free to do
something else first. That queue is this stage, and it is the last step between
L2 and libuv, because once a pending answer is data in a table, cancellation is a
table operation, a future (stage 7) is a promise to settle later, and the loop
that drains the table *is* the event loop.

So this stage is a table and a loop over it. `Handles` is the table: `register`
issues a handle and stores the callback as the 4-tuple `(handle, name, fn,
args)`, `ready` is the handles still to run in registration order, `take` pops
one, and `cancel` retires one without running it. `serve_callbacks` is the loop:
each turn it accepts whoever has arrived, reads every readable connection's
bytes, splits them into lines, registers one callback per line, retires the
connections whose client is done, dispatches exactly one callback, and gives the
link one tick.

The world is `link.py`, as in every stage of L2: the server calls the link, the
link keeps the log, and only `Link.step()` moves a byte. The three facts this
stage turns into code are these. A callback is **data**, never a closure over the
loop: the connection it will answer and the line it will answer with travel in
its `args`, and the loop's own variables are overwritten on the next iteration —
a callback that reached for them would answer the last connection of the turn
with the last line of the turn. A callback is a verdict about a connection that
**may have moved on**: between the turn that read the line and the turn that
would write the answer, the client's patience can run out and the link closes
the connection, and then the answer must not be written at all. And the loop's
work is *dispatch*, so a turn is one dispatch — the reads and the tick that come
with it — which is what makes a `budget` a bound on callbacks rather than on
bytes.

    Handles          the table of callbacks, in registration order, with
                     cancellation: register, cancel, ready, take
    serve_callbacks  the loop: read a line, register a callback, dispatch one
    ServerError      the family every refusal belongs to

`ServerError` is the family, and every refusal names the offender: a name that is
not a name, a callback that is not callable, a handle this table never issued, a
server that is not a server, a budget that is not a positive count of turns. A
verdict about what the *world* did is never an exception — a connection whose
client gave up, a callback the loop cancelled, and a callback whose connection
had closed are all results, and the check asserts them as values.

DESIGN DECISION — why is a callback a 4-tuple in a table instead of a closure
over the loop?
A closure is what everybody writes first, and it is what makes the loop's own
variables part of the callback's behaviour: `handles.append(lambda: answer(conn,
line))` captures `conn` and `line` *by reference*, so by the time the callback
runs, both may belong to the next connection of the turn. The bug is invisible
until two connections are served in one turn, and then it is silent: the last
client's line is answered twice and the first client's answer never comes. The
4-tuple makes the per-connection state `args` — data the callback carries, which
nothing the loop does afterwards can change. Everything else in this stage
follows from that one choice: the table can be inspected, cancelled, and asked
for its order, because a callback is a value and not a stack frame.

DESIGN DECISION — why is a callback whose connection has closed a `skipped`
verdict rather than an exception?
Because it is the *common* case, not the exceptional one: a client that waited
too long for an answer it can no longer be given has done nothing wrong, and a
server that raises for it is a server that has to wrap every dispatch in a
`try`. Worse, an exception here would have to be caught somewhere, and the
natural place to catch it — around the loop — ends the whole run because one
client hung up. So the verdict is returned: the callback is taken out of the
table, its name goes into `skipped`, and the loop goes on. The name matters as
much as the count, because "a callback was skipped" is not a fact anybody can
act on and "gamma's callback for its first request was skipped" is.

DESIGN DECISION — why does `ready()` leave cancelled handles out, and why is
`take` a separate move from `ready`?
A table that keeps a cancelled callback "for the record" is a table that runs it
later: the caller cancelled it and then the loop, reading its own order list,
found it again. So cancelling removes it from the count of what can run, and
`ready` is the only thing the loop is allowed to look at when it decides what is
next. Splitting `ready` from `take` is the same decision one step further: `ready`
is a question ("what is there") and `take` is a move ("give me that one and drop
it"), so a loop that dispatches pops exactly one callback rather than iterating a
list it is mutating — the classic bug of skipping every second element. Asking
for a handle there is nothing for is a verdict, `None`; asking with something
that is not a handle at all is a shape, and that is refused.

DESIGN DECISION — why does the loop dispatch one callback per turn, and what is
the budget a budget of?
If a turn drained the whole table, the callback that runs last would run in the
same tick as the one that runs first, and the queue would be a fiction: nothing
could ever happen in between, so nothing could ever cancel a callback, close a
connection under one, or have a run that stops with callbacks still queued. One
dispatch per turn makes the queue the thing the stage is about, and makes `steps`
a count of callbacks dispatched. `budget` then bounds turns, which is a bound on
work and not on time — and a budget spent with callbacks still in the table is an
outcome, not an exception. The loop says what it did with them: the callbacks it
never reached are cancelled by name when their connection is fine, and skipped
when it has closed, so nothing is quietly kept and run on some later turn that
never comes.

DESIGN DECISION — when is a connection finished, and why is that not "when its
reply was written"?
Because writing a reply is not delivering it. `Link.write` puts bytes in the
outbox and `Link.step` carries them into the client's inbox, where they sit until
the client's own drain schedule takes them — a client that reads every fourth
tick holds its answer for four ticks. A loop that closes the connection as soon
as the write returned cuts that client off mid-answer, and the server's own
report would not show it: the link's `bytes_drained` is the number that does. So
finished means three things at once — the client has no more requests to send,
the link has nothing to read, owe or carry, and the client has drained everything
it was sent — and the loop is over when its own connections are all closed *and*
the listener is holding nobody, because a client that arrives on a later tick is
still a client to serve.

TODO: implement `Handles` (`__init__`, `register`, `cancel`, `ready`, `take`) and
`serve_callbacks`.
"""


class ServerError(ValueError):
    """A shape this stage will not honour, named as what is wrong.

    It is the family for a name that is not a name, a callback that is not
    callable, a handle this table never issued, a server that is not a server,
    and a budget that is not a positive count of turns. A verdict about what the
    *world* did is never an exception: a connection whose client's patience ran
    out, a callback the loop cancelled and a callback whose connection had
    closed are all results, and the check asserts them as values.
    """


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
        raise NotImplementedError("stage 6: implement Handles.__init__()")

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
        raise NotImplementedError("stage 6: implement Handles.register()")

    def cancel(self, handle):
        """Retire the callback `handle` without running it; True once, then False.

        Cancelling is a decision about a callback, not about a connection, so it
        is the caller's move and the table has no opinion about why. A handle
        this table never issued is a refusal naming it — a cancellation that
        silently did nothing is a callback that runs after the code that tried to
        stop it. Cancelling a handle that is already gone answers `False`: the
        first cancel is the one that changed the table.
        """
        raise NotImplementedError("stage 6: implement Handles.cancel()")

    def ready(self):
        """The handles still to run, in registration order, as a fresh tuple.

        Cancelled and already-taken handles are not here: a callback the caller
        retired is a callback the loop must not dispatch, and a table that kept
        it "for the record" would be a table that runs it. The order is the
        registration order and never the order of cancelling or taking, because
        the order of callbacks is the order a server promised its clients.
        """
        raise NotImplementedError("stage 6: implement Handles.ready()")

    def take(self, handle):
        """Pop the callback `handle` and hand back its 4-tuple, or `None`.

        `None` is the answer for every handle there is nothing to hand back for:
        one that was already taken, one that was cancelled, and one that was
        never issued. That is a verdict and not a refusal — asking for what is
        not there is how a loop says "nothing for me this time" — while a handle
        that is not a handle at all is a shape and is refused.
        """
        raise NotImplementedError("stage 6: implement Handles.take()")


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
    raise NotImplementedError("stage 6: implement serve_callbacks()")
