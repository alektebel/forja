"""Concurrent Servers From Scratch — stage 1: The connection as a state machine.

A server is not a `for` loop over reads. It is a policy about who gets the
processor next, and the thing it holds is a *connection*: something that is not
yet readable, then readable, then owed a reply, then not writable yet, then
done — five phases, and every one of them a fact about the wire rather than a
line of the loop. This stage builds the smallest honest version of that: one
connection, carried as data in a dict, moved one step at a time by the caller.
It is the ladder's root because the four models above it (blocking, thread,
reactor, event loop) disagree about nothing except *who* calls `step_conn` and
in what order.

The world is `link.py`, and it is provided: a `Client` scripted with the requests
it sends, a `Connection` the server accepts and answers, bytes carried one
`MAX_CHUNK` at a time, and a bounded outbox whose short write is backpressure
rather than an error. Nothing here calls the server; the server calls the link,
and the link keeps the log every later stage is graded against. The link is also
the only clock: `Link.step()` is the one thing that moves a byte, which is why a
stage that cannot move anything must say so with an event instead of spinning.

Two facts about the protocol decide most of the code below. A request is *one
line ending in `\\n`*, and a reply is that line with `REPLY_PREFIX` in front of
it — so the machine may not answer until it has a whole line, and it may not
assume a line arrives in one read, because `MAX_CHUNK` is how much one move
carries and not how long a request may be. And a client sends its next request
only once it has drained the answer to the one before, so a machine that is
waiting for the drain and a machine whose client is done look alike on the wire;
telling those two apart is this stage's real decision.

    STATES       the five phases, in the order a well-behaved connection meets
                 them: new → reading → writing → reading → … → closing → closed
    REPLY_PREFIX the one byte of protocol stages 1–8 speak
    open_conn    the machine for a connection, in `"new"`
    step_conn    one move: read, write, or the honest `"idle"`
    finish       `closing → closed`: hand the connection back to the link
    stats        requests, replies, bytes_read, bytes_written — from the machine

`ServerError` is the family, and every refusal names the offender: the id the
link never made, the limit that is not 1 to `MAX_CHUNK`, the phase no machine
has, the connection that is another link's, the `finish` from a phase that is not
`"closing"`. A verdict about what the *client* did is never an exception: a spent
patience, a partial line and a full outbox are phases and events.

DESIGN DECISION — what does the connection's state carry, and who owns it?
Every function hands back a *fresh* dict: `"state"` (the phase), `"conn"` (the
link's own connection object), `"buffer"` (the line assembled so far), `"out"`
(the reply the outbox has not taken yet) and the four counters `stats` reports.
A step returns that dict plus `"event"`, `"reply"` and `"bytes"`, so `state =
step_conn(link, state)` is the whole of driving a connection and `stats(state)`
answers about the machine and not about a copy of it. Nothing is kept at module
level and nothing is written into the caller's dict.

DESIGN DECISION — why is `"idle"` an event rather than an error, and why is a
zero-byte read not one either?
Because "nothing to read now" is the commonest thing that happens to a server:
the client is still typing, the outbox is full, the reply is in flight and the
next request arrives only after the drain. `link.read` answers `b""` for exactly
that, and a machine that treats `b""` as a failure is a machine that cannot wait
— which is every server there is. `"idle"` also makes the step count honest: a
model that steps when nothing can move is a busy-wait, and this event is how the
count says so.

DESIGN DECISION — when is the reply staged, and why is the reply line rebuilt
per line?
Only when the buffer ends in `\\n`: a request is one line, so a reply written
before the whole line was read is an answer to half a question — the framing bug
every stream protocol has. The buffer is *rebuilt* (emptied) the moment its line
is answered, because the reply the client is owed is the line that was just read
and not the conversation so far; a buffer that is kept across requests turns the
second answer into the first one repeated. `REPLY_PREFIX` is applied once, at
the moment the line becomes a reply, and never again while the outbox takes it
in pieces.

DESIGN DECISION — why does the machine never close a connection itself, and how
does it know the client has no more requests?
`finish` is the only thing that closes, and only from `"closing"`: reaching
`"closing"` is how the read side says the client has nothing left to send and
has taken every byte it was written, and a connection closed before that is a
reply dropped after the server had already answered. Since a client that is
about to send its next request looks idle on the wire, the machine asks the world
the only question with an answer — is there a further request in this client's
script? — and the link being the one that scripts the client is exactly why that
is honest rather than a guess.

DESIGN DECISION — why does a step take a `limit`, and why does the reply not
have to fit the outbox?
`limit` is a *move* budget, `MAX_CHUNK` at most, because the link carries bytes
in pieces and a server that read a request in one call would be a server that
assumed the line arrived whole. A reply longer than the outbox is the same fact
one direction over: the world takes what it can and hands back a count, and a
server that ignores that count reports bytes it never delivered. So the tail
stays in `"out"` and the machine stays in `"writing"` — the deferred write is
made a phase here and a number in stage 8.

TODO: implement `open_conn`, `step_conn`, `finish` and `stats`.
"""

from link import MAX_CHUNK

#: The five phases of one connection, in the order a well-behaved one meets
#: them. `new → reading → writing → reading → …` for the client's requests, then
#: `closing → closed` once `finish` has handed the connection back to the link.
STATES = ("new", "reading", "writing", "closing", "closed")

#: The one byte of protocol stages 1–8 speak: the reply is the request line with
#: this in front of it. It is a `str` because it is a protocol character, and it
#: is a single byte so that the reply is one byte longer than the line and never
#: two; a check that sees the prefix twice sees a server that rebuilt a reply it
#: had already built.
REPLY_PREFIX = "+"


class ServerError(ValueError):
    """A connection this stage will not open, step or close, named as what is wrong.

    It is the family for every shape the machine cannot honour: a connection id
    the link never made, a limit that is not 1 to `MAX_CHUNK`, a phase no state
    machine has, a connection that belongs to another link, and a `finish` from a
    phase that is not `"closing"`. A verdict about what the *client* did is never
    an exception here: a spent patience, a partial line and a full outbox are all
    phases or events, and a check asserts them as values.
    """


def open_conn(link, cid):
    """The machine for connection `cid`, in the `"new"` phase.

    `link.connection(cid)` is the validation and the whole of it: a `cid` that is
    not an int, or is not a connection this link made, is refused naming what was
    given. The `"state"` handed back is the machine's own dict — a fresh one
    every time, so that nothing the caller keeps is ever the stage's to write.
    """
    raise NotImplementedError("stage 1: implement open_conn()")


def step_conn(link, state, *, limit=MAX_CHUNK):
    """One move of one connection: read the request, or write the reply.

    The answer is `{"state", "event", "reply", "bytes"}` *and* the machine's own
    fields, because this is the whole of driving a connection: `state =
    step_conn(link, state)`, and `stats(state)` when the run is over. One move
    per call and never two — `"read"` takes up to `limit` bytes of the request
    into the buffer, `"write"` hands what the outbox will take of the staged
    reply to the link, `"accepted"` is the `new → reading` step, and `"idle"` is
    the honest answer when there is nothing to read or nowhere to write: closing
    a connection, or reading `b""` as a failure, is the mistake this event exists
    to make impossible.

    A request is one line, so a reply is staged only once the buffer ends in
    `"\\n"` — `limit` is how much one *move* carries (`MAX_CHUNK` at most), never
    how long a request may be, and a line that arrives in three moves is read in
    three. The reply the outbox cannot take stays in the state as `"out"`, and
    the machine stays in `"writing"` until the link has carried it; a connection
    the link has closed (the client's patience spent) leaves the machine in
    `"closing"` rather than forever hoping to write.
    """
    raise NotImplementedError("stage 1: implement step_conn()")


def finish(link, state):
    """`closing → closed`: the connection is handed back to the link, once.

    This is the one transition the machine does not make while stepping, and it
    is deliberately not a step: a connection is closed from `"closing"` and from
    nowhere else, because reaching `"closing"` is exactly the read side saying
    that the client has no request left and has taken every answer. Closing is
    idempotent — a machine already `"closed"` answers `"idle"` and changes
    nothing — and any other phase is refused, naming it.
    """
    raise NotImplementedError("stage 1: implement finish()")


def stats(state):
    """What this machine has done: `{"requests", "replies", "bytes_read",
    "bytes_written"}`.

    A request is counted when its line is whole and its reply staged, a reply
    when the last of its bytes has been written — so a client that dropped
    before its answer moved leaves the two numbers different, which is the
    point. `bytes_read` and `bytes_written` are what the link's own calls moved,
    so a check can hold them against `link.stats()` and notice a machine that
    believed it wrote what the outbox never took.
    """
    raise NotImplementedError("stage 1: implement stats()")
