"""Concurrent Servers From Scratch — stage 1: The connection as a state machine.

SOLUTION. `link.py` hands out a connection that is readable, writable, owed and
closable; this stage is the smallest thing that can be *driven* on top of it —
one connection, one dict, one move per call — and it exists because the rest of
the course is four models that disagree about nothing except who steps next. A
model that is not a state machine reads a request it never finished accepting,
so the phase is the data here and the moves are one at a time.

The whole of it: `new` is a machine that has not looked at the wire yet;
`reading` assembles one line out of however many moves the link needs; `writing`
puts the answer into the bounded outbox, deferring what does not fit; `closing`
is the read side saying the client has no request left and has taken every
answer; and `finish` is the only thing that closes a connection. Nothing here
sleeps, spins or guesses: a move that cannot happen is `"idle"`, which is what a
reactor (stage 4) reads as "not ready" and what a blocking server (stage 2) reads
as "the client is not done with me yet".
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


def _phase(state):
    """The phase of a state mapping, refusing anything that is not one of them."""
    phase = state.get("state") if isinstance(state, dict) else state
    if not isinstance(state, dict) or phase not in STATES:
        raise ServerError("a state is a dict in one of %r, not %r" % (STATES, phase))
    return phase


def _conn(link, state):
    """The connection of a state, refusing one that is not this link's."""
    conn = state.get("conn") if isinstance(state, dict) else None
    if conn is None or link.connection(conn.id) is not conn:
        raise ServerError("connection %r is not this link's"
                          % (getattr(conn, "id", conn),))
    return conn


def _limit(limit):
    """A move's byte budget: an int of 1 to `MAX_CHUNK`, or a refusal naming it."""
    if (isinstance(limit, bool) or not isinstance(limit, int)
            or not 1 <= limit <= MAX_CHUNK):
        raise ServerError("a move carries 1 to %d bytes, not %r"
                          % (MAX_CHUNK, limit))
    return limit


def _machine(phase, conn, buffer=b"", out=b"", requests=0, replies=0,
             bytes_read=0, bytes_written=0):
    """A fresh machine: the canonical fields, in the canonical order.

    Every function here builds its answer with this, so the dict a caller gets
    has the same eight keys in the same order whether it came from `open_conn`,
    from a step or from `finish` — and nothing a step added on the way survives
    into the next state.
    """
    return {"state": phase, "conn": conn, "buffer": buffer, "out": out,
            "requests": requests, "replies": replies, "bytes_read": bytes_read,
            "bytes_written": bytes_written}


def _fresh(state, phase, event, **changed):
    """The machine again, fresh, with the phase and the event this move produced."""
    fields = {"buffer": state["buffer"], "out": state["out"],
              "requests": state["requests"], "replies": state["replies"],
              "bytes_read": state["bytes_read"],
              "bytes_written": state["bytes_written"]}
    fields.update(changed)
    fresh = _machine(phase, state["conn"], **fields)
    fresh["event"] = event
    return fresh


def _report(state, phase, event, reply=b"", bytes=0, **changed):
    """A step's answer: the fresh machine, plus what this one move moved."""
    fresh = _fresh(state, phase, event, **changed)
    fresh["reply"] = reply
    fresh["bytes"] = bytes
    return fresh


def _finished(link, conn):
    """Whether this connection has nothing left in either direction.

    The read side is over when the client has arrived, has no bytes the server
    has not taken, has nothing owed, has taken every byte it was written and has
    no further request to hand over. The link scripts the client's requests, so
    that last part is the only honest signal there is: a server that guessed "no
    more requests" from an empty socket would close a connection between two of
    them.
    """
    if conn.arrival > link.now():
        return False
    if link.readable(conn) or link.owed(conn) or link.drainable(conn) or conn.outbox:
        return False
    return conn.request + 1 >= len(conn.client.requests)


def open_conn(link, cid):
    """The machine for connection `cid`, in the `"new"` phase.

    `link.connection(cid)` is the validation and the whole of it: a `cid` that is
    not an int, or is not a connection this link made, is refused naming what was
    given. The `"state"` handed back is the machine's own dict — a fresh one
    every time, so that nothing the caller keeps is ever the stage's to write.
    """
    if isinstance(cid, bool) or not isinstance(cid, int):
        raise ServerError("a connection id is an int, not %r" % (cid,))
    conn = link.connection(cid)
    if conn is None:
        raise ServerError("no connection %r is on this link" % (cid,))
    return _machine("new", conn)


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
    phase = _phase(state)
    conn = _conn(link, state)
    _limit(limit)
    if phase == "closed":
        return _report(state, "closed", "idle")
    if conn.closed or phase == "closing":
        return _report(state, "closing", "idle")
    if phase == "new":
        return _report(state, "reading", "accepted")
    if phase == "writing":
        if not link.writable(conn):
            return _report(state, "writing", "idle")
        out = state["out"]
        written = link.write(conn, out)
        left = out[written:]
        return _report(state, "reading" if not left else "writing", "write",
                       reply=out[:written], bytes=written, out=left,
                       bytes_written=state["bytes_written"] + written,
                       replies=state["replies"] + (0 if left else 1))
    if link.readable(conn):
        chunk = link.read(conn, limit)
        buffer = state["buffer"] + chunk
        bytes_read = state["bytes_read"] + len(chunk)
        if not buffer.endswith(b"\n"):
            return _report(state, "reading", "read", buffer=buffer,
                           bytes_read=bytes_read, bytes=len(chunk))
        return _report(state, "writing", "read", buffer=b"",
                       out=REPLY_PREFIX.encode() + buffer,
                       requests=state["requests"] + 1, bytes_read=bytes_read,
                       bytes=len(chunk))
    if _finished(link, conn):
        return _report(state, "closing", "idle")
    return _report(state, "reading", "idle")


def finish(link, state):
    """`closing → closed`: the connection is handed back to the link, once.

    This is the one transition the machine does not make while stepping, and it
    is deliberately not a step: a connection is closed from `"closing"` and from
    nowhere else, because reaching `"closing"` is exactly the read side saying
    that the client has no request left and has taken every answer. Closing is
    idempotent — a machine already `"closed"` answers `"idle"` and changes
    nothing — and any other phase is refused, naming it.
    """
    phase = _phase(state)
    conn = _conn(link, state)
    if phase == "closed":
        return _fresh(state, "closed", "idle")
    if phase != "closing":
        raise ServerError("connection %d is closed from %r, not from %r"
                          % (conn.id, "closing", phase))
    link.close(conn)
    return _fresh(state, "closed", "close")


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
    _phase(state)
    return {"requests": state["requests"], "replies": state["replies"],
            "bytes_read": state["bytes_read"],
            "bytes_written": state["bytes_written"]}
