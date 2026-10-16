"""Concurrent Servers From Scratch — course manifest.

Ten graded stages between an in-memory link and a server whose every decision can
be held against the link's own log. The world is provided and complete:
`link.py` is the link — a `Client` scripted with the requests it sends, a
`Connection` the server accepts and answers, bytes carried one `MAX_CHUNK` at a
time, a bounded `outbox` whose short write is backpressure rather than an error,
`read_every` for the slow client that stops a blocking server, `patience` for the
client that drops a link nobody answered, and a full event log (`accept`,
`listen`, `read`, `write`, `drop`, `drain`, `close`) that `stats()` recomputes
every number from; `fleet.py` is J1's file, byte for byte, and its `Clock` is this
course's wristwatch — a tick is one unit of work and there is no other clock.

The thesis of the whole course is one sentence, and every stage's check asserts
it: A SERVER IS A POLICY ABOUT WHO GETS THE PROCESSOR NEXT, AND WHAT THE LINK
LOGGED IS THE ONLY HONEST SCORE. Each stage exists because the one before it left
a hole: a server that is not a state machine reads a request it never finished
accepting; a blocking server stops everyone behind one slow client; a thread per
connection turns one interleaving nobody chose into the only one anybody can
debug; a reactor needs readiness as a set and a poll loop that never busy-waits;
an event loop needs timers in a queue that never re-sorts itself; callbacks as
data need a handle table, a cancellation, and the rule that a callback must not
run for a connection that is closed; futures and `async` / `await` are a
desugaring of that same loop, not another runtime; a server that cannot defer a
write drops the tail of the reply it was sent to deliver; the Redis case study is
a command loop with per-connection state and one honest number per connection;
and only one workload through all four models proves any of it, because that run
reports four step counts and the answers had better be identical.

The failures worth preventing are the ones that look like success: a request read
as if it were whole, an `accept` loop that keeps accepting while a connection
starves, a poll loop that spins because it never asked who was ready, a timer
queue that re-sorts on every tick, a future resumed twice, a dropped write
reported as sent, a command loop whose state leaks from one connection to the
next, a `for` loop counted as one scheduler step, and a model that reports what it
believed instead of what the link logged.

Standard library only, offline, deterministic, **ints only** (every tick, step,
byte count, chunk, handle, deadline and ratio — there is no float literal
anywhere in this course): no `time`, no `threading`, no `asyncio`, no `random`,
no `os`, no sockets, no subprocesses, no wall clock, no module-level mutable
state, and no `statistics`, `math`, `decimal` or `fractions` either. `threading`,
`asyncio` and `time` are banned because *they are the subject*: the interleaving
is data the check chooses, the clock is the link's, and the four models of the
same server are step functions the course runs itself. There is no `async def`
in this file and none in any stage. The link is the clock: time passes only
through `Link.step()` and the `now` a stage is handed, and every count the course
needs is an exact integer.

This is the second of `NETWORKING.md`'s three series, and it is the concurrency
half of the problem J1 stated for a queue and J3 for durability: J1 owns the
scheduler this course runs its thread model on, J3 owns what survives a crash,
and L2 owns the question in between — who gets the processor, and how do you know
you got it right without a race to point at.

    python3 codecraft/cli.py run concurrent-servers-from-scratch
"""

from codecraft.api import stage

TITLE = "Concurrent Servers From Scratch"
DESCRIPTION = ("Four models of one server against one link: a blocking server and "
               "the one slow client that stops everyone, a thread per connection "
               "over J1's scheduler with the interleaving the check chooses, a "
               "reactor whose readiness is a set and whose poll loop never "
               "busy-waits, and an event loop whose timers are one monotonic "
               "queue — then callbacks as data in a handle table with "
               "cancellation, futures and async/await as the same loop "
               "desugared, backpressure as a bounded outbox and a write that is "
               "deferred rather than dropped, the Redis case study as a command "
               "loop with per-connection state, and one workload through all "
               "four models whose four step counts and identical answers the "
               "link's own log is the tie-breaker for.")
LEVEL = "advanced"
ORDER = 27


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "concurrent-servers-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "link.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _drive(s, link, conn, *, limit=None, budget=64):
        """Drive one connection's machine — one step, then one tick — to `closing`.

        The interleaving is the check's and not the stage's: the machine is asked
        for a move, the world is then given a tick, and what came out of the client's
        inbox after that tick is recorded, since the client's own drain discards the
        bytes it took and the link's log keeps only their count.
        """
        state = s.open_conn(link, conn.id)
        phases = [state["state"]]
        events = ()
        inboxes = ()
        while state["state"] not in ("closing", "closed") and len(events) < budget:
            state = (s.step_conn(link, state) if limit is None
                     else s.step_conn(link, state, limit=limit))
            phases.append(state["state"])
            events = events + (state["event"],)
            link.step(1)
            inboxes = inboxes + (conn.inbox,)
        return {"state": state, "phases": tuple(phases), "events": events,
                "inboxes": inboxes, "steps": len(events), "stats": s.stats(state)}

    def _workload(s, l):
        """The whole workload, built from scratch: three clients on one fresh link.

        One request, two requests, and a slow reader with a one-byte chunk — every
        number in the result is recomputable from the world's own log, which is what
        the last section of the check holds the second run against.
        """
        link = l.Link((l.Client("fast", (b"ping\n",), read_every=2),
                       l.Client("two", (b"hello\n", b"again\n"), read_every=2),
                       l.Client("slow", (b"hi\n",), read_every=4, chunk=1)))
        runs = {}
        for _ in range(len(link)):
            conn = link.accept()
            run = _drive(s, link, conn)
            end = s.finish(link, run["state"])
            runs[conn.client.name] = {"phases": run["phases"], "events": run["events"],
                                      "inboxes": run["inboxes"], "steps": run["steps"],
                                      "stats": run["stats"], "state": end["state"],
                                      "event": end["event"]}
        return {"runs": runs, "link": link.stats(), "log": link.log()}

    import link as l
    import stage_01 as s

    # ---- the constants and the family -------------------------------------

    assert s.STATES == ("new", "reading", "writing", "closing", "closed"), (
        "the five phases in order, from a machine that has not looked at the "
        "wire to one the link has closed: %r" % (s.STATES,))
    assert s.REPLY_PREFIX == "+", (
        "stages 1-8 answer the request line with this one byte in front of it, "
        "and it is one byte: %r" % (s.REPLY_PREFIX,))
    assert issubclass(s.ServerError, ValueError), (
        "the family is a ValueError, so a caller's `except ValueError` keeps "
        "catching a broken course: %r" % (s.ServerError.__mro__,))
    assert l.MAX_CHUNK == 64, (
        "the world carries at most 64 bytes per move: %r" % (l.MAX_CHUNK,))

    # ---- open_conn --------------------------------------------------------

    link = l.Link((l.Client("solo", (b"ping\n",), read_every=2),))
    conn = link.connection(1)
    state = s.open_conn(link, 1)
    assert tuple(state) == ("state", "conn", "buffer", "out", "requests",
                            "replies", "bytes_read", "bytes_written"), (
        "a machine opens with its phase, its connection and the six fields it "
        "carries, in that order: %r" % (tuple(state),))
    assert state["state"] == s.STATES[0] == "new", (
        "and it opens in the first of the five phases: %r" % (state["state"],))
    assert state["conn"] is conn, (
        "the machine holds the link's own connection and not a copy of it: %r"
        % (state["conn"],))
    assert (state["buffer"], state["out"]) == (b"", b""), (
        "nothing has been read and no reply is staged: %r"
        % ((state["buffer"], state["out"]),))
    assert (state["requests"], state["replies"], state["bytes_read"],
            state["bytes_written"]) == (0, 0, 0, 0), (
        "and the machine has done nothing yet: %r" % (state,))
    assert tuple(s.stats(state)) == ("requests", "replies", "bytes_read",
                                     "bytes_written"), (
        "stats reports exactly the four counters, in order: %r" % (tuple(s.stats(state)),))
    assert s.stats(state) == {"requests": 0, "replies": 0, "bytes_read": 0,
                              "bytes_written": 0}, (
        "a fresh machine's counters are all zero: %r" % (s.stats(state),))
    assert link.stats()["events"] == 0, (
        "opening a machine is not a move: the link's log is still empty: %r"
        % (link.stats(),))

    _refuses(s.ServerError, "open_conn of an id the link never made",
             lambda: s.open_conn(link, 99), names=("99",))
    _refuses(s.ServerError, "open_conn of a name instead of an id",
             lambda: s.open_conn(link, "1"), names=("'1'",))
    _refuses(s.ServerError, "open_conn of True, which is an int and not an id",
             lambda: s.open_conn(link, True), names=("True",))
    _refuses(s.ServerError, "open_conn of None",
             lambda: s.open_conn(link, None), names=("None",))

    # ---- one request, one move at a time ----------------------------------

    step = s.step_conn(link, state)
    assert tuple(step) == ("state", "conn", "buffer", "out", "requests",
                           "replies", "bytes_read", "bytes_written",
                           "event", "reply", "bytes"), (
        "a step hands back the whole machine plus the three facts about the one "
        "move it made, in that order: %r" % (tuple(step),))
    assert (step["state"], step["event"]) == ("reading", "accepted"), (
        "the first step takes the connection into the reading phase: %r"
        % ((step["state"], step["event"]),))
    assert (step["reply"], step["bytes"]) == (b"", 0), (
        "and accepting a connection moves no byte: %r"
        % ((step["reply"], step["bytes"]),))
    assert step is not state and state["state"] == "new", (
        "the step is a fresh dict and the caller's is not written: %r" % (state,))
    assert link.stats()["events"] == 0, (
        "accepting a connection is the stage's business and not the link's: %r"
        % (link.stats(),))

    read = s.step_conn(link, step)
    assert (read["state"], read["event"]) == ("writing", "read"), (
        "the whole line arrives in one move, so the machine now owes a reply: %r"
        % ((read["state"], read["event"]),))
    assert (read["buffer"], read["out"]) == (b"", b"+ping\n"), (
        "the line becomes the reply and the buffer is rebuilt, not kept: %r"
        % ((read["buffer"], read["out"]),))
    assert (read["bytes"], read["bytes_read"], read["requests"]) == (5, 5, 1), (
        "five bytes were read, ten make one request and ten are counted: %r"
        % ((read["bytes"], read["bytes_read"], read["requests"]),))
    assert read["reply"] == b"" and link.stats()["bytes_written"] == 0, (
        "a read step writes nothing: %r wrote %r" % (read["event"], read["reply"]))

    write = s.step_conn(link, read)
    assert (write["state"], write["event"]) == ("reading", "write"), (
        "the reply goes out and the machine is ready for the next request: %r"
        % ((write["state"], write["event"]),))
    assert (write["reply"], write["bytes"]) == (b"+ping\n", 6), (
        "the reply is the line with the prefix in front of it, once, and it is "
        "one byte longer than the line: %r" % ((write["reply"], write["bytes"]),))
    assert (write["out"], write["replies"], write["bytes_written"]) == (b"", 1, 6), (
        "the outbox took all of it, so nothing is deferred and one reply is "
        "counted: %r" % ((write["out"], write["replies"], write["bytes_written"]),))
    assert link.stats()["bytes_written"] == 6, (
        "the six bytes are the link's own count of what it carried: %r"
        % (link.stats(),))
    assert link.stats()["drains"] == 0, (
        "and the client has not taken them yet: %r" % (link.stats(),))

    held = s.step_conn(link, write)
    assert (held["state"], held["event"], held["bytes"]) == ("reading", "idle", 0), (
        "the reply is in the outbox and the link has not carried it, so the read "
        "side is not over yet: %r"
        % ((held["state"], held["event"], held["bytes"]),))
    assert held["out"] == b"" and link.stats()["bytes_drained"] == 0, (
        "the reply belongs to the link now, and the client has still taken "
        "nothing: %r" % (link.stats(),))

    link.step(1)
    assert conn.inbox == b"+ping\n", (
        "the client's inbox holds the answer, prefixed exactly once: %r"
        % (conn.inbox,))
    assert link.stats()["drains"] == 0, (
        "a client that reads every second tick has not read on the first: %r"
        % (link.stats(),))

    idle = s.step_conn(link, write)
    assert (idle["state"], idle["event"], idle["bytes"]) == ("reading", "idle", 0), (
        "a client between its requests is idle — not an error, not a reply, and "
        "not a closed connection: %r" % ((idle["state"], idle["event"], idle["bytes"]),))
    assert (idle["reply"], idle["buffer"], idle["out"]) == (b"", b"", b""), (
        "nothing moved, so nothing is reported as moved: %r" % (idle,))
    assert idle is not write and write["state"] == "reading", (
        "and the state the machine was in is left alone: %r" % (write,))

    link.step(1)
    assert link.stats()["bytes_drained"] == 6, (
        "on the second tick the client takes the six bytes: %r" % (link.stats(),))

    over = s.step_conn(link, idle)
    assert (over["state"], over["event"]) == ("closing", "idle"), (
        "the client's one request is answered and drained, so the read side is "
        "over and the machine says so without closing anything: %r"
        % ((over["state"], over["event"]),))
    assert conn.closed is False and link.stats()["closes"] == 0, (
        "closing is `finish`'s move: stepping never closes: %r" % (link.stats(),))
    assert s.stats(over) == {"requests": 1, "replies": 1, "bytes_read": 5,
                             "bytes_written": 6}, (
        "one request read, one reply written, five bytes in and six out: %r"
        % (s.stats(over),))
    assert link.stats()["bytes_read"] == 5 and link.stats()["bytes_written"] == 6, (
        "and the link's own numbers are the stage's numbers: %r" % (link.stats(),))

    # ---- finish, and a closed machine that moves nothing ------------------

    end = s.finish(link, over)
    assert tuple(end) == ("state", "conn", "buffer", "out", "requests", "replies",
                          "bytes_read", "bytes_written", "event"), (
        "finish hands back the machine and its one event, and no reply or byte "
        "count, because it moved neither: %r" % (tuple(end),))
    assert (end["state"], end["event"]) == ("closed", "close"), (
        "closing -> closed, and the event says the connection was closed: %r"
        % ((end["state"], end["event"]),))
    assert conn.closed is True and link.stats()["closes"] == 1, (
        "the world closed the connection exactly once: %r" % (link.stats(),))

    again = s.finish(link, end)
    assert (again["state"], again["event"]) == ("closed", "idle"), (
        "closing a machine that is already closed changes nothing and says so: %r"
        % ((again["state"], again["event"]),))
    assert link.stats()["closes"] == 1, (
        "and it does not close the link's connection a second time: %r"
        % (link.stats(),))

    before = link.stats()
    dead = s.step_conn(link, end)
    assert (dead["state"], dead["event"], dead["reply"], dead["bytes"]) == (
        "closed", "idle", b"", 0), (
        "a closed connection moves nothing and is idle, whatever the link still "
        "holds: %r" % ((dead["state"], dead["event"], dead["reply"], dead["bytes"]),))
    assert link.stats() == before, (
        "a closed connection logs nothing either: %r vs %r" % (link.stats(), before))

    # ---- two requests: the buffer is rebuilt, not kept --------------------

    link = l.Link((l.Client("two", (b"hello\n", b"again\n"), read_every=2),))
    conn = link.connection(1)
    state = s.step_conn(link, s.open_conn(link, 1))
    assert (state["state"], state["event"]) == ("reading", "accepted"), (
        "the machine starts on the first of two requests: %r"
        % ((state["state"], state["event"]),))
    state = s.step_conn(link, state)
    assert (state["state"], state["buffer"], state["out"]) == ("writing", b"",
                                                               b"+hello\n"), (
        "the first line becomes the first reply and the buffer is emptied: %r"
        % (state,))
    assert conn.outbox == b"", (
        "and the link has been given nothing yet: %r" % (conn.outbox,))
    state = s.step_conn(link, state)
    assert (conn.outbox, state["out"], state["replies"]) == (b"+hello\n", b"", 1), (
        "the write step hands the reply to the link's outbox, whole: %r"
        % ((conn.outbox, state["out"], state["replies"]),))
    assert link.stats()["bytes_written"] == 7, (
        "seven bytes: the six of the line and the one prefix: %r" % (link.stats(),))

    link.step(1)
    assert conn.inbox == b"+hello\n", (
        "the client's inbox holds the first answer: %r" % (conn.inbox,))
    link.step(1)
    assert conn.inbox == b"" and link.stats()["bytes_drained"] == 7, (
        "and once it has drained the answer the next request is readable: %r"
        % (link.stats(),))

    state = s.step_conn(link, state)
    assert (state["state"], state["event"]) == ("writing", "read"), (
        "the second line is read and answered: %r"
        % ((state["state"], state["event"]),))
    assert (state["buffer"], state["out"]) == (b"", b"+again\n"), (
        "the second answer is the line just read, and the buffer the first line "
        "left behind is nowhere in it: %r" % ((state["buffer"], state["out"]),))
    assert (state["requests"], state["bytes_read"]) == (2, 12), (
        "two requests of six bytes each: %r" % ((state["requests"],
                                                 state["bytes_read"]),))
    state = s.step_conn(link, state)
    assert (conn.outbox, state["replies"], state["bytes_written"]) == (
        b"+again\n", 2, 14), (
        "and the second reply is the second line, prefixed once: %r"
        % ((conn.outbox, state["replies"], state["bytes_written"]),))
    link.step(1)
    assert conn.inbox == b"+again\n", (
        "the client sees the second answer and not the conversation so far: %r"
        % (conn.inbox,))
    link.step(1)
    assert link.stats()["bytes_drained"] == 14, (
        "both answers reached the client: %r" % (link.stats(),))

    over = s.step_conn(link, state)
    assert (over["state"], over["event"]) == ("closing", "idle"), (
        "the second and last request answered and drained is the read side "
        "over: %r" % ((over["state"], over["event"]),))
    assert s.stats(over) == {"requests": 2, "replies": 2, "bytes_read": 12,
                             "bytes_written": 14}, (
        "two lines read, two answers written: %r" % (s.stats(over),))
    end = s.finish(link, over)
    assert (end["state"], end["event"]) == ("closed", "close"), (
        "and the machine that read two lines closes like any other: %r"
        % ((end["state"], end["event"]),))
    assert s.stats(end) == s.stats(over), (
        "closing a connection does not change what the machine did: %r vs %r"
        % (s.stats(end), s.stats(over)))
    assert link.stats()["closes"] == 1 and link.stats()["drains"] == 2, (
        "one connection, closed once, after two drains: %r" % (link.stats(),))

    # ---- a line in three moves, and a reply the outbox only half takes -----

    link = l.Link((l.Client("long", (b"hello there\n",), read_every=2),))
    conn = link.connection(1)
    state = s.step_conn(link, s.open_conn(link, 1))
    one = s.step_conn(link, state, limit=4)
    assert (one["state"], one["event"], one["bytes"]) == ("reading", "read", 4), (
        "a four-byte move leaves a twelve-byte line unfinished, and the machine "
        "says read and not reply: %r"
        % ((one["state"], one["event"], one["bytes"]),))
    assert (one["buffer"], one["out"]) == (b"hell", b""), (
        "the bytes read so far are kept and no reply is staged yet: %r"
        % ((one["buffer"], one["out"]),))
    assert one["requests"] == 0 and link.stats()["bytes_written"] == 0, (
        "half a line is not a request and is not answered: %r" % (link.stats(),))

    two = s.step_conn(link, one, limit=4)
    assert (two["state"], two["event"], two["buffer"]) == (
        "reading", "read", b"hello th"), (
        "the second move appends to the buffer rather than replacing it: %r"
        % ((two["state"], two["event"], two["buffer"]),))

    three = s.step_conn(link, two, limit=4)
    assert (three["state"], three["event"]) == ("writing", "read"), (
        "the third move ends in the newline, and only now is the line whole: %r"
        % ((three["state"], three["event"]),))
    assert (three["buffer"], three["out"]) == (b"", b"+hello there\n"), (
        "the whole line becomes the reply and the buffer is emptied: %r"
        % ((three["buffer"], three["out"]),))
    assert (three["bytes"], three["requests"], three["bytes_read"]) == (4, 1, 12), (
        "four bytes this move and twelve in all, which is one request: %r"
        % ((three["bytes"], three["requests"], three["bytes_read"]),))

    first = s.step_conn(link, three)
    assert (first["state"], first["event"], first["reply"], first["bytes"]) == (
        "writing", "write", b"+hello t", 8), (
        "the outbox takes eight of the reply's thirteen bytes and the count says "
        "eight: %r" % ((first["state"], first["event"], first["reply"],
                        first["bytes"]),))
    assert (first["out"], first["replies"], first["bytes_written"]) == (
        b"here\n", 0, 8), (
        "the tail stays in the machine, and a reply that is not all the way out "
        "is not a reply yet: %r"
        % ((first["out"], first["replies"], first["bytes_written"]),))
    assert link.stats()["bytes_written"] == 8 and link.stats()["bytes_dropped"] == 0, (
        "a short write is not a dropped write: %r" % (link.stats(),))

    full = s.step_conn(link, first)
    assert (full["state"], full["event"], full["bytes"]) == ("writing", "idle", 0), (
        "with the outbox full the machine waits for the link instead of writing "
        "over what is already there: %r"
        % ((full["state"], full["event"], full["bytes"]),))
    assert link.stats()["bytes_dropped"] == 0, (
        "and nothing was dropped waiting either: %r" % (link.stats(),))

    link.step(1)
    assert conn.inbox == b"+hello t", (
        "the link carried exactly what the outbox took: %r" % (conn.inbox,))
    rest = s.step_conn(link, full)
    assert (rest["state"], rest["event"], rest["reply"], rest["bytes"]) == (
        "reading", "write", b"here\n", 5), (
        "the second write finishes the reply the first one started: %r"
        % ((rest["state"], rest["event"], rest["reply"], rest["bytes"]),))
    assert (rest["out"], rest["replies"], rest["bytes_written"]) == (b"", 1, 13), (
        "and only now is one reply counted: %r"
        % ((rest["out"], rest["replies"], rest["bytes_written"]),))
    assert s.stats(rest) == {"requests": 1, "replies": 1, "bytes_read": 12,
                             "bytes_written": 13}, (
        "the machine's numbers are the whole reply and the whole request: %r"
        % (s.stats(rest),))

    # ---- a client whose patience is spent ---------------------------------

    link = l.Link((l.Client("waits", (b"ping\n",), patience=1),))
    conn = link.connection(1)
    state = s.step_conn(link, s.open_conn(link, 1))
    owed = s.step_conn(link, state)
    assert (owed["state"], owed["event"], owed["out"]) == ("writing", "read",
                                                           b"+ping\n"), (
        "the reply is staged and the link is owed it: %r"
        % ((owed["state"], owed["event"], owed["out"]),))
    link.step(3)
    assert conn.closed is True and conn.cause == "patience", (
        "the client's patience runs out while the reply is still in the state: %r"
        % (conn.cause,))
    dropped = s.step_conn(link, owed)
    assert (dropped["state"], dropped["event"]) == ("closing", "idle"), (
        "a connection the link closed ends in closing rather than hoping to "
        "write forever: %r" % ((dropped["state"], dropped["event"]),))
    assert dropped["out"] == b"+ping\n", (
        "the undelivered reply is still in the state, which is what a timeout "
        "has to be honest about: %r" % (dropped["out"],))
    assert s.stats(dropped) == {"requests": 1, "replies": 0, "bytes_read": 5,
                                "bytes_written": 0}, (
        "the request was read and the reply was never written, and the two "
        "counters say so: %r" % (s.stats(dropped),))
    still = s.step_conn(link, dropped)
    assert (still["state"], still["event"]) == ("closing", "idle"), (
        "and a machine that has once reached closing stays closing, whatever "
        "the link still owes: %r" % ((still["state"], still["event"]),))
    assert (s.finish(link, still)["event"], link.stats()["closes"],
            link.stats()["bytes_drained"]) == ("close", 1, 0), (
        "closing a connection nobody delivered on is a close and nothing else: %r"
        % (link.stats(),))

    # ---- a request with no newline in it never becomes a line -------------

    link = l.Link((l.Client("half", (b"no newline here",), read_every=2),))
    conn = link.connection(1)
    state = s.step_conn(link, s.open_conn(link, 1))
    state = s.step_conn(link, state)
    assert (state["state"], state["event"], state["buffer"]) == (
        "reading", "read", b"no newline here"), (
        "the link hands over the fifteen bytes of a request that ends in no "
        "newline, and the machine keeps them: %r" % (state,))
    assert (state["out"], state["requests"]) == (b"", 0), (
        "and it stages no reply for a line that is not a line: %r"
        % ((state["out"], state["requests"]),))
    assert link.owed(conn) is True, (
        "the link is owed a reply, and the machine has to know that: %r"
        % (link.owed(conn),))
    stuck = s.step_conn(link, state)
    assert (stuck["state"], stuck["event"], stuck["bytes"]) == ("reading", "idle", 0), (
        "so it waits for the rest of the line instead of closing a request it "
        "never answered: %r"
        % ((stuck["state"], stuck["event"], stuck["bytes"]),))
    assert s.stats(stuck) == {"requests": 0, "replies": 0, "bytes_read": 15,
                              "bytes_written": 0}, (
        "fifteen bytes in, no request, no reply: %r" % (s.stats(stuck),))
    _refuses(s.ServerError, "finish from a machine that still owes a reply",
             lambda: s.finish(link, stuck), names=("'reading'", "1"))

    # ---- a client that has not arrived yet --------------------------------

    link = l.Link((l.Client("first", (b"one\n",)),
                   l.Client("second", (b"two\n",))), seed=2)
    conn = link.connection(2)
    assert (conn.arrival, link.now()) == (2, 0), (
        "the second client arrives on the second tick: %r at %r"
        % (conn.arrival, link.now()))
    state = s.step_conn(link, s.open_conn(link, 2))
    early = s.step_conn(link, state)
    assert (early["state"], early["event"], early["bytes"]) == ("reading", "idle", 0), (
        "a client that has not arrived has nothing to read and is not finished "
        "either: %r" % ((early["state"], early["event"], early["bytes"]),))
    link.step(2)
    arrived = s.step_conn(link, early)
    assert (arrived["state"], arrived["event"], arrived["bytes"]) == ("writing",
                                                                     "read", 4), (
        "once it has arrived its line is there to be read: %r"
        % ((arrived["state"], arrived["event"], arrived["bytes"]),))

    # ---- the refusals -----------------------------------------------------

    link = l.Link((l.Client("solo", (b"ping\n",)),))
    state = s.open_conn(link, 1)
    for bad in (0, l.MAX_CHUNK + 1, -1, True, "4", None):
        _refuses(s.ServerError, "step_conn with a limit of %r" % (bad,),
                 lambda bad=bad: s.step_conn(link, state, limit=bad),
                 names=(repr(bad),))
    assert s.step_conn(link, state, limit=1)["bytes"] == 0, (
        "one byte is a legal limit, and the accepted step still moves nothing")

    other = l.Link((l.Client("mine", (b"ping\n",)),))
    _refuses(s.ServerError, "step_conn with a connection of another link",
             lambda: s.step_conn(other, state), names=("1",))
    _refuses(s.ServerError, "finish with a connection of another link",
             lambda: s.finish(other, state), names=("1",))
    _refuses(s.ServerError, "step_conn in a phase no machine has",
             lambda: s.step_conn(link, dict(state, state="bogus")),
             names=("'bogus'",))
    _refuses(s.ServerError, "step_conn of something that is not a state",
             lambda: s.step_conn(link, "idle"), names=("'idle'",))
    _refuses(s.ServerError, "step_conn of a phase name where a state belongs",
             lambda: s.step_conn(link, "reading"), names=("'reading'",))
    _refuses(s.ServerError, "stats in a phase no machine has",
             lambda: s.stats(dict(state, state="bogus")), names=("'bogus'",))
    _refuses(s.ServerError, "stats of something that is not a state",
             lambda: s.stats("idle"), names=("'idle'",))
    _refuses(s.ServerError, "stats of a phase name where a state belongs",
             lambda: s.stats("reading"), names=("'reading'",))
    _refuses(s.ServerError, "finish from a machine that has not started",
             lambda: s.finish(link, state), names=("'new'", "1"))
    reading = s.step_conn(link, state)
    _refuses(s.ServerError, "finish from a machine that is still reading",
             lambda: s.finish(link, reading), names=("'reading'", "1"))

    # ---- the whole workload, twice ----------------------------------------

    first = _workload(s, l)
    second = _workload(s, l)
    assert first == second, (
        "two runs of the same workload are the same run, byte for byte: %r vs %r"
        % (first, second))
    assert tuple(first["runs"]) == ("fast", "two", "slow"), (
        "the three clients are served in the order they were accepted: %r"
        % (tuple(first["runs"]),))
    for name, run in sorted(first["runs"].items()):
        assert run["phases"][0] == "new" and run["phases"][-1] == "closing", (
            "%s's machine starts where it should and stops in closing: %r"
            % (name, run["phases"]))
        assert run["steps"] < 64, (
            "%s's machine reaches closing well inside the check's budget: %d"
            % (name, run["steps"]))
        assert run["state"] == "closed" and run["event"] == "close", (
            "%s's connection is closed by finish: %r"
            % (name, (run["state"], run["event"])))
        assert run["stats"]["requests"] == run["stats"]["replies"], (
            "%s's every request was answered, because no client dropped it: %r"
            % (name, run["stats"]))
        assert tuple(run) == ("phases", "events", "inboxes", "steps", "stats",
                              "state", "event"), (
            "%s's run reports the same seven facts, in order: %r"
            % (name, tuple(run)))
    assert first["runs"]["two"]["stats"] == {"requests": 2, "replies": 2,
                                            "bytes_read": 12, "bytes_written": 14}, (
        "the two-request client read both lines and was answered twice, and the "
        "second answer is not the first one repeated: %r"
        % (first["runs"]["two"]["stats"],))
    assert first["runs"]["slow"]["stats"] == {"requests": 1, "replies": 1,
                                             "bytes_read": 3, "bytes_written": 4}, (
        "the slow client's four-byte reply is one reply: %r"
        % (first["runs"]["slow"]["stats"],))
    seen = tuple(inbox for inbox in first["runs"]["fast"]["inboxes"] if inbox)
    assert seen == (b"+ping\n",), (
        "the one-request client saw its one answer, prefixed once, and nothing "
        "else: %r" % (seen,))
    assert next(inbox for inbox in first["runs"]["slow"]["inboxes"]
                if inbox) == b"+hi\n", (
        "and the slow client, taking a byte at a time, was still sent the whole "
        "reply before it started draining: %r" % (first["runs"]["slow"]["inboxes"],))
    assert first["link"]["bytes_read"] == 20, (
        "the four request lines that were sent are the twenty bytes the link "
        "handed over: %r" % (first["link"],))
    assert first["link"]["bytes_written"] == 24, (
        "the four replies are the twenty-four bytes the stage wrote: %r"
        % (first["link"],))
    assert first["link"]["bytes_drained"] == 24, (
        "and every one of them reached a client, because no machine closed a "
        "connection early: %r" % (first["link"],))
    assert first["link"]["closes"] == 3 and first["link"]["accepted"] == 3, (
        "three connections were accepted and three were closed: %r"
        % (first["link"],))
    assert first["link"]["drops"] == 0, (
        "nothing was queued that the outbox could not take: %r" % (first["link"],))
    assert len(first["log"]) == 22, (
        "the log's twenty-two events — three accepts, five reads, four writes, "
        "seven drains and three closes — are the record the second run "
        "repeats: %r" % (len(first["log"]),))

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "concurrent-servers-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "link.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _clients(l):
        """The check's own workload: the slow reader in front of three others.

        One request answered a byte every fourth tick, one answered at once, one with
        two requests so the model has to answer the same client twice, and one whose
        reply is longer than the outbox so the world carries it in two pieces.
        """
        return (l.Client("slow", (b"hi\n",), read_every=4, chunk=1),
                l.Client("fast", (b"ping\n",), read_every=1),
                l.Client("two", (b"hello\n", b"again\n"), read_every=2),
                l.Client("long", (b"hello there\n",), read_every=2))

    def _world(l, *, seed=0):
        """A fresh world with that workload, its arrivals staggered by `seed` ticks."""
        return l.Link(_clients(l), seed=seed)

    def _bundle(link):
        """The bundle stage 2 is handed: the world, its clients, and their lines."""
        clients = tuple(conn.client for conn in link.conns())
        return {"link": link, "clients": clients,
                "requests": {client.name: client.requests for client in clients}}

    def _run(s, link, *, budget=None):
        """One run of the model over the world, plus the world's own record.

        The bundle is built here and copied before the call, so the check can hold
        the model to writing nothing into what it was handed, and the link's log and
        stats are read after the call rather than trusted from the result.
        """
        server = _bundle(link)
        before = dict(server)
        result = (s.serve_blocking(server) if budget is None
                  else s.serve_blocking(server, budget=budget))
        return {"result": result, "before": before, "server": server,
                "stats": link.stats(), "log": link.log()}

    def _answered(result):
        """How many reply bytes the result says the server wrote, in all."""
        return sum(len(line) for lines in result["answers"].values() for line in lines)

    import link as l
    import stage_02 as s

    # ---- the family, and the bundle the model refuses ---------------------

    assert issubclass(s.ServerError, ValueError), (
        "the family is a ValueError, so a caller's `except ValueError` keeps "
        "catching a broken course: %r" % (s.ServerError.__mro__,))

    bundle = _bundle(_world(l))
    _refuses(s.ServerError, "a server that is not a dict at all",
             lambda: s.serve_blocking("server"), names=("'server'",))
    _refuses(s.ServerError, "a server with no requests key",
             lambda: s.serve_blocking({"link": bundle["link"],
                                       "clients": bundle["clients"]}),
             names=("'requests'",))
    _refuses(s.ServerError, "a server with no clients key",
             lambda: s.serve_blocking({"link": bundle["link"],
                                       "requests": bundle["requests"]}),
             names=("'clients'",))
    _refuses(s.ServerError, "a server whose link is not a Link",
             lambda: s.serve_blocking(dict(bundle, link=7)), names=("7",))
    _refuses(s.ServerError, "a server with an empty clients sequence",
             lambda: s.serve_blocking(dict(bundle, clients=())), names=("()",))
    _refuses(s.ServerError, "a server whose clients are names, not Clients",
             lambda: s.serve_blocking(dict(bundle, clients=tuple(bundle["requests"]))),
             names=("'slow'",))
    _refuses(s.ServerError, "a server naming fewer clients than the link holds",
             lambda: s.serve_blocking(dict(bundle, clients=bundle["clients"][:2])),
             names=("4", "2"))

    stranger = l.Link((l.Client("slow", (b"hi\n",)), l.Client("upstart", (b"ping\n",)),
                       l.Client("two", (b"hello\n",)), l.Client("long", (b"hi\n",))))
    _refuses(s.ServerError, "a server whose clients are not the link's own",
             lambda: s.serve_blocking(dict(bundle, clients=tuple(
                 conn.client for conn in stranger.conns()))),
             names=("1", "'fast'", "'upstart'"))
    _refuses(s.ServerError, "a server whose requests are not a mapping",
             lambda: s.serve_blocking(dict(bundle, requests=[])), names=("[]",))
    _refuses(s.ServerError, "a server with no lines for one of its clients",
             lambda: s.serve_blocking(dict(bundle, requests={"slow": (b"hi\n",)})),
             names=("'fast'",))
    _refuses(s.ServerError, "a server with an empty tuple of lines for a client",
             lambda: s.serve_blocking(dict(bundle, requests=dict(
                 bundle["requests"], fast=()))), names=("'fast'",))
    _refuses(s.ServerError, "a server with one bytes object where lines belong",
             lambda: s.serve_blocking(dict(bundle, requests=dict(
                 bundle["requests"], fast=b"ping\n"))), names=("fast", "b'ping\\n'"))
    _refuses(s.ServerError, "a request line that is text and not bytes",
             lambda: s.serve_blocking(dict(bundle, requests=dict(
                 bundle["requests"], fast=("ping\n",)))), names=("'ping\\n'",))

    for bad in (-1, True, "4", None):
        _refuses(s.ServerError, "a budget of %r" % (bad,),
                 lambda bad=bad: s.serve_blocking(_bundle(_world(l)), budget=bad),
                 names=(repr(bad),))

    # ---- one client at a time, to completion ------------------------------

    run = _run(s, _world(l))
    settled = run["result"]
    assert tuple(settled) == ("answers", "steps", "ticks", "served", "starved"), (
        "the five keys the contract names, in that order: %r" % (tuple(settled),))
    assert tuple(settled["answers"]) == ("slow", "fast", "two", "long"), (
        "every client of the bundle is answered by name, in the link's accept "
        "order, so two models' answers can be compared key for key: %r"
        % (tuple(settled["answers"]),))
    assert settled["answers"] == {"slow": (b"+hi\n",), "fast": (b"+ping\n",),
                                  "two": (b"+hello\n", b"+again\n"),
                                  "long": (b"+hello there\n",)}, (
        "each answer is the whole reply line, prefix and newline included, in the "
        "order it was written — and the long reply the outbox took in two pieces "
        "is one answer, not two: %r" % (settled["answers"],))
    assert settled["served"] == ("slow", "fast", "two", "long"), (
        "a blocking model finishes its clients in the order it accepted them, and "
        "all four are finished here: %r" % (settled["served"],))
    assert settled["starved"] == (), (
        "a run that finished starves nobody, whatever the slow client cost: %r"
        % (settled["starved"],))
    assert (settled["steps"], settled["ticks"]) == (33, 33), (
        "thirty-three turns, and thirty-three ticks of the world's clock: %r"
        % ((settled["steps"], settled["ticks"]),))
    assert settled["steps"] == settled["ticks"], (
        "one thread of control pays a tick for every turn it takes, which is why "
        "the two counts are the same number here: %r"
        % ((settled["steps"], settled["ticks"]),))

    assert run["server"] == run["before"], (
        "the bundle is the caller's and the model writes nothing into it: %r vs %r"
        % (run["server"], run["before"]))
    assert (run["stats"]["accepted"], run["stats"]["closes"]) == (4, 4), (
        "four connections accepted and all four closed by the model: %r"
        % (run["stats"],))
    assert (run["stats"]["bytes_read"], run["stats"]["bytes_written"],
            run["stats"]["bytes_drained"]) == (32, 37, 37), (
        "the link carried the thirty-two request bytes and all thirty-seven of "
        "the answers: %r" % (run["stats"],))
    assert (run["stats"]["drops"], run["stats"]["listened"]) == (0, 0), (
        "nothing was queued that the outbox could not take, and a blocking model "
        "never returns a connection to the backlog: %r" % (run["stats"],))
    assert (run["stats"]["events"], run["stats"]["ticks"]) == (29, 33), (
        "twenty-nine events are the record of the thirty-three ticks: %r"
        % (run["stats"],))
    assert _answered(settled) == run["stats"]["bytes_drained"] == 37, (
        "on a settled run every byte the server answered reached its client: %r "
        "vs %r" % (_answered(settled), run["stats"]["bytes_drained"]))

    order = tuple((entry["event"], entry["id"]) for entry in run["log"]
                  if entry["event"] in ("accept", "close"))
    assert order == (("accept", 1), ("close", 1), ("accept", 2), ("close", 2),
                     ("accept", 3), ("close", 3), ("accept", 4), ("close", 4)), (
        "one client at a time, from accept to close, and the next one only once "
        "the one in front is finished: %r" % (order,))
    assert tuple(entry["tick"] for entry in run["log"]
                 if entry["event"] == "accept") == (0, 17, 21, 27), (
        "the listener does not even look at the second client until the tick that "
        "closed the first, and the two behind it wait the same way: %r"
        % (tuple(entry["tick"] for entry in run["log"]
                 if entry["event"] == "accept"),))
    assert tuple((entry["tick"], entry["byte_count"]) for entry in run["log"]
                 if entry["event"] == "drain" and entry["id"] == 1) == (
        (4, 1), (8, 1), (12, 1), (16, 1)), (
        "the slow client takes its four-byte answer one byte every fourth tick, "
        "and those sixteen ticks are the wait everyone behind it served: %r"
        % (tuple((entry["tick"], entry["byte_count"]) for entry in run["log"]
                 if entry["event"] == "drain" and entry["id"] == 1),))

    # ---- a reply is one answer however many pieces the outbox takes -------

    long_line = b"x" * 20 + b"\n"
    big = l.Link((l.Client("big", (long_line,), read_every=1),), seed=0)
    big_run = _run(s, big)
    assert big_run["result"]["answers"]["big"] == (b"+" + long_line,), (
        "a reply of twenty-two bytes is one answer even though the outbox of "
        "eight takes it in three pieces: %r" % (big_run["result"]["answers"],))
    assert (big_run["stats"]["write_calls"], big_run["stats"]["bytes_written"],
            big_run["stats"]["bytes_drained"]) == (3, 22, 22), (
        "the case is about the pieces accumulating at all, so the outbox must "
        "really have taken it three times: %r" % (big_run["stats"],))
    assert (big_run["result"]["served"], big_run["result"]["starved"]) == (
        ("big",), ()), (
        "and that one client is finished, not starved: %r"
        % ((big_run["result"]["served"], big_run["result"]["starved"]),))
    assert big_run["result"]["steps"] == big_run["result"]["ticks"] == 6, (
        "six turns: accept, read, three writes, three drains and close: %r"
        % ((big_run["result"]["steps"], big_run["result"]["ticks"]),))

    idle = _run(s, _world(l), budget=0)
    assert idle["result"] == {"answers": {"slow": (), "fast": (), "two": (),
                                          "long": ()},
                              "steps": 0, "ticks": 0, "served": (),
                              "starved": ("slow", "fast", "two", "long")}, (
        "a budget of zero is legal and takes no turn at all: %r"
        % (idle["result"],))
    assert idle["stats"]["events"] == 0 and idle["stats"]["ticks"] == 0, (
        "and it moves neither a byte nor the clock: %r" % (idle["stats"],))

    # ---- a budget spent is an outcome, not an exception -------------------

    short = _run(s, _world(l), budget=6)
    assert (short["result"]["served"], short["result"]["starved"]) == (
        (), ("fast", "two", "long")), (
        "six steps accept the slow client and answer it, and the three behind it "
        "were never looked at — which is the whole subject of this stage: %r"
        % ((short["result"]["served"], short["result"]["starved"]),))
    assert short["result"]["answers"] == {"slow": (b"+hi\n",), "fast": (),
                                          "two": (), "long": ()}, (
        "the one client the budget reached is answered and the others are empty "
        "tuples rather than missing keys: %r" % (short["result"]["answers"],))
    assert (short["result"]["steps"], short["result"]["ticks"]) == (6, 6), (
        "a budget of six is six turns and six ticks: %r"
        % ((short["result"]["steps"], short["result"]["ticks"]),))
    assert (short["stats"]["accepted"], short["stats"]["closes"]) == (1, 0), (
        "one client accepted, nobody closed, and the model still returned a "
        "result instead of raising: %r" % (short["stats"],))

    reading = _run(s, _world(l), budget=2)
    assert reading["result"]["starved"] == ("slow", "fast", "two", "long"), (
        "a request that was read and never answered is starved too, and a "
        "blocking model that stopped mid-line has starved everyone: %r"
        % (reading["result"]["starved"],))
    assert reading["result"]["answers"]["slow"] == (), (
        "the request bytes are in the model's buffer and nothing has been "
        "answered from them: %r" % (reading["result"]["answers"],))
    assert reading["stats"]["bytes_read"] == 3, (
        "three request bytes were taken off the link and no reply written: %r"
        % (reading["stats"],))

    partial = _run(s, _world(l), budget=24)
    assert (partial["result"]["served"], partial["result"]["starved"]) == (
        ("slow", "fast"), ("two", "long")), (
        "the client with two requests is answered once and is still starved, "
        "because its second request is one the link holds and the server never "
        "answered: %r"
        % ((partial["result"]["served"], partial["result"]["starved"]),))
    assert partial["result"]["answers"]["two"] == (b"+hello\n",), (
        "and the one answer it did get is in the record: %r"
        % (partial["result"]["answers"],))

    half = _run(s, _world(l), budget=30)
    assert (half["result"]["answers"]["long"], half["stats"]["bytes_written"]) == (
        (), 32), (
        "the ten bytes of the longest reply the outbox could take are written and "
        "are not an answer, because the reply is not whole yet: %r vs %r"
        % (half["result"]["answers"]["long"], half["stats"]["bytes_written"]))
    assert half["result"]["starved"] == ("long",), (
        "so that client is still waiting for an answer it has not been given: %r"
        % (half["result"]["starved"],))

    early = _run(s, _world(l), budget=31)
    assert (early["result"]["served"], early["result"]["starved"]) == (
        ("slow", "fast", "two"), ()), (
        "a client whose answer was written but whose connection the budget "
        "stopped the model from closing is neither served nor starved — "
        "`starved` is not the complement of `served`: %r"
        % ((early["result"]["served"], early["result"]["starved"]),))
    assert _answered(early["result"]) == 37, (
        "all four answers were written: %r" % (_answered(early["result"]),))
    assert early["stats"]["bytes_drained"] == 32, (
        "and five of their bytes were still on the link when the model returned, "
        "which is exactly what an early return costs: %r" % (early["stats"],))

    assert _run(s, _world(l), budget=32)["result"]["served"] == (
        "slow", "fast", "two"), (
        "thirty-two steps deliver every byte and are still one turn short of "
        "closing the last client: %r"
        % (_run(s, _world(l), budget=32)["result"]["served"],))
    enough = _run(s, _world(l), budget=33)
    assert enough["result"] == settled, (
        "thirty-three steps are the settled run, and a bigger budget changes "
        "nothing about it: %r vs %r" % (enough["result"], settled))
    assert _run(s, _world(l))["result"] == _run(s, _world(l), budget=256)["result"], (
        "the default budget is the contract's 256 steps: the same run with and "
        "without the keyword")

    described = _world(l)
    lying = _bundle(described)
    lying["requests"] = {name: (b"something else\n",) for name in lying["requests"]}
    assert s.serve_blocking(lying, budget=256) == settled, (
        "the link is the arbiter of what the clients send: a bundle whose "
        "description disagrees with the link changes no answer: %r"
        % (s.serve_blocking(lying, budget=256),))

    # ---- arrivals that have not happened yet ------------------------------

    seeded = _run(s, _world(l, seed=16))
    assert (seeded["result"]["steps"], seeded["result"]["ticks"]) == (53, 53), (
        "waiting for clients that have not arrived costs turns like everything "
        "else: %r"
        % ((seeded["result"]["steps"], seeded["result"]["ticks"]),))
    assert (seeded["result"]["served"], seeded["result"]["starved"]) == (
        ("slow", "fast", "two", "long"), ()), (
        "and the same four clients still finish in the same order: %r"
        % ((seeded["result"]["served"], seeded["result"]["starved"]),))
    assert seeded["result"]["answers"] == settled["answers"], (
        "staggered arrivals change the ticks and not the answers: %r vs %r"
        % (seeded["result"]["answers"], settled["answers"]))
    assert tuple(entry["tick"] for entry in seeded["log"]
                 if entry["event"] == "accept") == (0, 17, 32, 48), (
        "a client whose tick has not come is waited for one turn at a time, so "
        "the third client is accepted only at the tick it arrives: %r"
        % (tuple(entry["tick"] for entry in seeded["log"]
                 if entry["event"] == "accept"),))
    assert tuple(entry["tick"] for entry in seeded["log"]
                 if entry["event"] == "close") == (17, 21, 39, 53), (
        "and every connection is still closed the moment the model notices it is "
        "finished: %r" % (tuple(entry["tick"] for entry in seeded["log"]
                                if entry["event"] == "close"),))

    waiting = _run(s, _world(l, seed=16), budget=20)
    assert (waiting["result"]["served"], waiting["result"]["starved"]) == (
        ("slow",), ("two", "long")), (
        "a budget spent waiting for an arrival the model cannot hurry leaves the "
        "clients behind unanswered: %r"
        % ((waiting["result"]["served"], waiting["result"]["starved"]),))
    assert waiting["result"]["answers"]["fast"] == (b"+ping\n",), (
        "the client between them was answered and not finished, so it is in "
        "neither tuple and its answer is still in the record: %r"
        % (waiting["result"]["answers"],))
    assert (waiting["result"]["steps"], waiting["result"]["ticks"]) == (20, 20), (
        "and every one of those twenty turns ticked the world once: %r"
        % ((waiting["result"]["steps"], waiting["result"]["ticks"]),))

    # ---- the whole workload, twice ----------------------------------------

    first = _run(s, _world(l))
    second = _run(s, _world(l))
    assert first["result"] == second["result"], (
        "two runs of the same workload are the same run, turn for turn: %r vs %r"
        % (first["result"], second["result"]))
    assert first["log"] == second["log"], (
        "and the link's own record repeats down to the tick of every event: %r "
        "vs %r" % (len(first["log"]), len(second["log"])))
    assert first["stats"] == second["stats"], (
        "the world's recomputed numbers agree as well: %r vs %r"
        % (first["stats"], second["stats"]))
    first["result"]["answers"]["slow"] = (b"+not the answer\n",)
    first["result"]["served"] = ("nobody",)
    third = _run(s, _world(l))
    assert third["result"] == second["result"], (
        "the result is the caller's to write into, so a model that hands back "
        "its own dictionary would let one run's caller change the next: %r vs %r"
        % (third["result"], second["result"]))

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "concurrent-servers-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "link.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _plan(answers, tally):
        """A step function that follows `answers`, then keeps giving the last one.

        Every call is appended to `tally`, arguments included, so a check can see both
        that the thread ran and what it was spawned with; a tally belongs to the one
        thread it counts, because the answer handed out depends on how many times
        *this* thread has been called. The last answer is the one it goes on giving,
        since a thread that has run out of plan has settled into one of the three
        states for good.
        """
        def turn(*args):
            tally.append(args)
            return answers[min(len(tally) - 1, len(answers) - 1)]
        return turn

    def _spawner(scheduler, name, plan, parent, child):
        """A step function that spawns `name` on its second turn, then follows `plan`.

        The spawn happens in the middle of a run: a scheduler that had closed over the
        threads it started with would never give the new one a turn at all, so the
        child's own calls are what the check holds it to.
        """
        def turn(*args):
            index = len(parent)
            parent.append(args)
            if index == 1:
                child.append(scheduler.spawn(name, _plan(("done",), child)))
            return plan[min(index, len(plan) - 1)]
        return turn

    def _server(l, pairs, **kwargs):
        """The three pieces of a `server`: the link, the clients, the scripted lines.

        `pairs` is `(name, requests, options)` per client, and the bundle's `requests`
        mapping is built from the same lines the clients were given: the worked
        example of what the stage is handed.
        """
        clients = tuple(l.Client(name, requests, **options)
                        for name, requests, options in pairs)
        world = l.Link(clients, **kwargs)
        return {"link": world, "clients": clients,
                "requests": {client.name: client.requests for client in clients}}

    def _main_pairs():
        """The check's three clients: two fast readers and one that reads a byte a tick.

        `c` is the slow client of stage 2 — four ticks between drains, one byte per
        drain — which is the client a blocking server cannot serve and a scheduled one
        can, and it is the client the script below answers first.
        """
        return (("a", (b"one\n",), {}),
                ("b", (b"two\n",), {}),
                ("c", (b"three\n",), {"read_every": 4, "chunk": 1}))

    def _workload(s, l, *, script=None, budget=256, **kwargs):
        """The whole workload, built from scratch: three clients on one fresh link.

        The result, the world's own stats, its log and its connections are all handed
        back together, because every number in the result has to be recomputable from
        the world: the model reports what it wrote, and the link recorded what it
        carried.
        """
        server = _server(l, _main_pairs(), **kwargs)
        result = s.serve_threads(server, script=script, budget=budget)
        world = server["link"]
        return {"server": server, "result": result, "stats": world.stats(),
                "log": world.log(), "conns": world.conns(), "world": world}

    import link as l
    import stage_03 as s

    # ---- the two vocabularies and the family ------------------------------

    assert s.STEP_STATES == ("more", "blocked", "done"), (
        "a step function answers one of three things — more to do, waiting on "
        "another thread, finished — and nothing else: %r" % (s.STEP_STATES,))
    assert s.THREAD_STATES == ("ready", "blocked", "done"), (
        "and the scheduler keeps its own three for what a thread is between "
        "turns: %r" % (s.THREAD_STATES,))
    assert issubclass(s.ServerError, ValueError), (
        "the family is a ValueError, so a caller's `except ValueError` keeps "
        "catching a broken course: %r" % (s.ServerError.__mro__,))
    assert l.MAX_CHUNK == 64, (
        "the world still carries at most 64 bytes per move: %r" % (l.MAX_CHUNK,))

    # ---- spawn: handles, names, and what is not a thread ------------------

    empty = s.Scheduler()
    assert tuple(empty.run(budget=4)) == ("finished", "steps", "order", "blocked"), (
        "a run reports its verdict, its count, its order and its waiters, in "
        "that order: %r" % (tuple(empty.run(budget=4)),))
    assert empty.run(budget=4) == {"finished": True, "steps": 0, "order": (),
                                   "blocked": ()}, (
        "a scheduler with nothing spawned is a run that finished with nothing to "
        "do: %r" % (empty.run(budget=4),))
    assert empty.ready() == (), (
        "and there is no thread to run: %r" % (empty.ready(),))

    tally = []
    sched = s.Scheduler()
    handles = (sched.spawn("one", _plan(("more",), tally)),
               sched.spawn("two", _plan(("more",), tally), "an argument"),
               sched.spawn("three", _plan(("done",), tally)))
    assert handles == (1, 2, 3), (
        "handles are handed out from one upwards, in the order the threads were "
        "spawned: %r" % (handles,))
    assert sched.ready() == (1, 2, 3), (
        "every spawned thread can run now, in spawn order: %r" % (sched.ready(),))
    assert tally == [], (
        "spawning a thread does not call it: %r" % (tally,))

    _refuses(s.ServerError, "spawn with an empty name",
             lambda: sched.spawn("", _plan(("more",), [])), names=("''",))
    _refuses(s.ServerError, "spawn with a name that is not a string",
             lambda: sched.spawn(4, _plan(("more",), [])), names=("4",))
    _refuses(s.ServerError, "spawn with None for a name",
             lambda: sched.spawn(None, _plan(("more",), [])), names=("None",))
    _refuses(s.ServerError, "spawn with a step function that is not callable",
             lambda: sched.spawn("fourth", "more"), names=("'more'",))
    _refuses(s.ServerError, "spawn of a name that is already spawned",
             lambda: sched.spawn("one", _plan(("more",), [])), names=("'one'",))
    assert sched.ready() == (1, 2, 3), (
        "and not one of those refusals spawned anything or took a name: %r"
        % (sched.ready(),))

    # ---- step: the round-robin, the answer, and the two vocabularies ------

    turns = [sched.step() for _ in range(4)]
    assert [turn["name"] for turn in turns] == ["one", "two", "three", "one"], (
        "without a script the turns are round-robin in spawn order, and they come "
        "back round: %r" % ([turn["name"] for turn in turns],))
    assert [turn["handle"] for turn in turns] == [1, 2, 3, 1], (
        "and a handle names the thread the name did: %r"
        % ([turn["handle"] for turn in turns],))
    first = turns[0]
    assert tuple(first) == ("handle", "name", "state", "yielded"), (
        "a turn reports the thread, the name, where the answer leaves it and the "
        "answer itself, in that order: %r" % (tuple(first),))
    assert (first["state"], first["yielded"]) == ("ready", "more"), (
        "`more` is the thread's own answer and `ready` is the scheduler's word "
        "for it: %r" % ((first["state"], first["yielded"]),))
    assert (turns[1]["state"], turns[1]["yielded"]) == ("ready", "more"), (
        "the second thread answered the same thing and is left in the same "
        "state: %r" % (turns[1],))
    assert (turns[2]["state"], turns[2]["yielded"]) == ("done", "done"), (
        "and a thread that answered `done` is done here too: %r"
        % ((turns[2]["state"], turns[2]["yielded"]),))
    assert tuple(tally[1]) == ("an argument",), (
        "a step function is called with the arguments it was spawned with, which "
        "is all the memory a thread without a stack has: %r" % (tally[1],))
    assert sched.ready() == (1, 2), (
        "a finished thread is never ready again: %r" % (sched.ready(),))

    # ---- run: the completion order, the count, and the budget -------------

    late_calls, early_calls = [], []
    sched = s.Scheduler()
    sched.spawn("late", _plan(("more", "more", "done"), late_calls))
    sched.spawn("early", _plan(("more", "done"), early_calls))
    run = sched.run(budget=16)
    assert tuple(run) == ("finished", "steps", "order", "blocked"), (
        "a run reports exactly its verdict, its count, its order and its "
        "waiters: %r" % (tuple(run),))
    assert run == {"finished": True, "steps": 5, "order": ("early", "late"),
                   "blocked": ()}, (
        "the order is the order the threads *finished* — `early` first although "
        "`late` was spawned first — and nothing was left waiting: %r" % (run,))
    assert (len(late_calls), len(early_calls)) == (3, 2), (
        "three turns went to the thread that needed three and two to the one that "
        "needed two: %r vs %r" % (late_calls, early_calls))
    assert run["steps"] == len(late_calls) + len(early_calls), (
        "so the count and the calls agree: %r vs %r"
        % (run["steps"], len(late_calls) + len(early_calls)))

    one_calls, two_calls = [], []
    sched = s.Scheduler()
    sched.spawn("one", _plan(("more", "more", "more", "done"), one_calls))
    sched.spawn("two", _plan(("more", "more", "more", "done"), two_calls))
    stopped = sched.run(budget=3)
    assert stopped == {"finished": False, "steps": 3, "order": (), "blocked": ()}, (
        "a budget spent with work left is a run that stopped and not a failure, "
        "and it says nothing was blocked because nothing was: %r" % (stopped,))
    assert len(one_calls) + len(two_calls) == 3, (
        "the budget is checked before the turn, so no fourth step was taken: %r"
        % (one_calls + two_calls,))
    assert sched.run(budget=16) == {"finished": True, "steps": 5,
                                    "order": ("one", "two"), "blocked": ()}, (
        "and the same scheduler carries on from where the budget stopped it")

    fresh = s.Scheduler()
    fresh.spawn("solo", _plan(("done",), []))
    assert fresh.run(budget=0) == {"finished": False, "steps": 0, "order": (),
                                   "blocked": ()}, (
        "a budget of zero takes no turn at all, so the thread that would have "
        "answered in one is still there: %r" % (fresh.run(budget=0),))

    _refuses(s.ServerError, "run with a budget of True",
             lambda: s.Scheduler().run(budget=True), names=("True",))
    _refuses(s.ServerError, "run with a budget that is not a count",
             lambda: s.Scheduler().run(budget="8"), names=("'8'",))
    _refuses(s.ServerError, "run with a negative budget",
             lambda: s.Scheduler().run(budget=-1), names=("-1",))

    odd = s.Scheduler()
    odd.spawn("odd", _plan((None,), []))
    _refuses(s.ServerError, "a step function that answers None",
             lambda: odd.step(), names=("None",))
    shouty = s.Scheduler()
    shouty.spawn("shouty", _plan(("MORE",), []))
    _refuses(s.ServerError, "a step function that answers 'MORE'",
             lambda: shouty.step(), names=("'MORE'",))

    over = s.Scheduler()
    over.spawn("only", _plan(("done",), []))
    assert over.step()["state"] == "done", (
        "one thread, one turn, and it is done")
    _refuses(s.ServerError, "a turn when every thread has finished",
             lambda: over.step())
    _refuses(s.ServerError, "a turn on a scheduler nobody has spawned into",
             lambda: s.Scheduler().step(), names=("no thread",))

    # ---- blocked: a skipped turn, a round, and a deadlock -----------------

    tally = []
    sched = s.Scheduler(("waiter", "waiter", "worker"))
    sched.spawn("waiter", _plan(("blocked",), tally))
    sched.spawn("worker", _plan(("more",), tally))
    blocked = sched.step()
    assert (blocked["name"], blocked["state"], blocked["yielded"]) == (
        "waiter", "blocked", "blocked"), (
        "a thread that answers `blocked` is blocked, and the answer is reported "
        "as what it yielded: %r" % (blocked,))
    assert sched.ready() == (2,), (
        "and a blocked thread is not one that can run now: %r" % (sched.ready(),))
    skipped = sched.step()
    assert (skipped["handle"], skipped["state"], skipped["yielded"]) == (
        1, "blocked", None), (
        "a scripted turn for a blocked thread is skipped — the turn is offered, "
        "nothing is called, and `yielded` is `None` — which is the difference "
        "between a turn spent and a turn taken: %r" % (skipped,))
    assert len(tally) == 1, (
        "so a skipped turn is not a step, and cannot be counted as one: %r"
        % (tally,))
    assert sched.step()["name"] == "worker", (
        "and the next scripted turn is still the next scripted turn")
    assert sched.ready() == (1, 2), (
        "every remaining thread has now been offered a turn, so the round is over "
        "and the waiter gets a fresh chance: %r" % (sched.ready(),))

    waiter_calls, worker_calls = [], []
    sched = s.Scheduler()
    sched.spawn("waiter", _plan(("blocked", "more", "done"), waiter_calls))
    sched.spawn("worker", _plan(("more", "done"), worker_calls))
    mixed = sched.run(budget=16)
    assert mixed == {"finished": True, "steps": 5, "order": ("worker", "waiter"),
                     "blocked": ()}, (
        "a thread that blocked once is not done: the other thread's work is what "
        "it was waiting for, and the next round calls it again: %r" % (mixed,))
    assert (len(waiter_calls), len(worker_calls)) == (3, 2), (
        "the waiter was called three times — blocked, more, done — so its block "
        "was cleared by the round and not by the verdict: %r" % (waiter_calls,))

    skip_waiter, skip_two, skip_three = [], [], []
    sched = s.Scheduler(script=("waiter", "two", "two", "waiter", "three"))
    sched.spawn("waiter", _plan(("blocked", "done"), skip_waiter))
    sched.spawn("two", _plan(("more", "done"), skip_two))
    sched.spawn("three", _plan(("more", "done"), skip_three))
    spend = sched.run(budget=16)
    assert spend == {"finished": True, "steps": 6,
                     "order": ("two", "waiter", "three"), "blocked": ()}, (
        "the script's fourth turn names a thread that is still blocked, and that "
        "turn is spent on nothing: the run takes six turns and not seven: %r"
        % (spend,))
    assert (len(skip_waiter), len(skip_two), len(skip_three)) == (2, 2, 2), (
        "every step function was called exactly as often as the script gave it a "
        "turn it could take, which is what the count of six counts: %r"
        % ((skip_waiter, skip_two, skip_three),))

    frozen = s.Scheduler()
    frozen.spawn("stuck-one", _plan(("blocked",), []))
    frozen.spawn("stuck-two", _plan(("blocked",), []))
    assert (frozen.step()["yielded"], frozen.step()["yielded"]) == (
        "blocked", "blocked"), (
        "two turns make both threads waiters, one turn each")
    sure = frozen.run(budget=0)
    assert sure == {"finished": False, "steps": 0, "order": (),
                    "blocked": ("stuck-one", "stuck-two")}, (
        "and the run asked next reports them before spending a turn of its own: a "
        "deadlock is a fact about the round and not about what is left of the "
        "budget: %r" % (sure,))

    tally = []
    sched = s.Scheduler()
    sched.spawn("stuck-one", _plan(("blocked",), tally))
    sched.spawn("stuck-two", _plan(("blocked",), tally))
    dead = sched.run(budget=64)
    assert dead == {"finished": False, "steps": 2, "order": (),
                    "blocked": ("stuck-one", "stuck-two")}, (
        "a round in which every remaining thread is blocked is a deadlock: the "
        "run returns the names of the waiters instead of spending its budget on "
        "them: %r" % (dead,))
    assert len(tally) == 2, (
        "each waiter was called exactly once before the verdict, and no turn was "
        "taken for a thread that could not use one: %r" % (tally,))

    alone = s.Scheduler()
    alone.spawn("only", _plan(("blocked",), []))
    lonely = alone.run(budget=8)
    assert lonely == {"finished": False, "steps": 1, "order": (),
                      "blocked": ("only",)}, (
        "one thread waiting for a turn nobody else can take is a deadlock too: "
        "the run reports it rather than spending its eight steps: %r" % (lonely,))

    survivor = s.Scheduler()
    survivor.spawn("waiter", _plan(("blocked",), []))
    survivor.spawn("helper", _plan(("done",), []))
    helped = survivor.run(budget=8)
    assert helped == {"finished": False, "steps": 2, "order": ("helper",),
                      "blocked": ("waiter",)}, (
        "and when the thread that ran did not unblock the waiter, the run ends "
        "with the waiter named and what did finish kept in the order: %r"
        % (helped,))

    # ---- the script is the interleaving -----------------------------------

    tally = []
    sched = s.Scheduler(("two", "one", "two"))
    sched.spawn("one", _plan(("more",), tally))
    sched.spawn("two", _plan(("more",), tally))
    turns = [sched.step() for _ in range(4)]
    assert [turn["name"] for turn in turns] == ["two", "one", "two", "one"], (
        "the script chooses the turn by name, entry by entry; `one` was spawned "
        "first and `two` goes first because the script says so: %r"
        % ([turn["name"] for turn in turns],))
    assert [turn["handle"] for turn in turns] == [2, 1, 2, 1], (
        "and a name picks the thread it was spawned for, not a position in the "
        "script: %r" % ([turn["handle"] for turn in turns],))
    assert len(tally) == 4, (
        "every one of those turns called its step function: %r" % (tally,))

    finished_script = s.Scheduler(("once", "once"))
    finished_script.spawn("once", _plan(("done",), []))
    assert finished_script.step()["state"] == "done", (
        "the one thread in this script answers done on its first turn")
    _refuses(s.ServerError, "a scripted turn for a thread that has finished",
             lambda: finished_script.step(), names=("'once'",))
    _refuses(s.ServerError, "a script that names a thread nobody spawned",
             lambda: s.Scheduler(("nobody",)).step(), names=("'nobody'",))
    _refuses(s.ServerError, "a script that is a string instead of a sequence of names",
             lambda: s.Scheduler("one"), names=("'one'",))
    _refuses(s.ServerError, "a script whose entry is not a name",
             lambda: s.Scheduler(("one", 3)), names=("3",))

    # ---- a thread spawned in the middle of a run --------------------------

    parent, child = [], []
    sched = s.Scheduler()
    sched.spawn("parent", _spawner(sched, "child", ("more", "more", "done"),
                                   parent, child))
    sched.spawn("other", _plan(("done",), []))
    grown = sched.run(budget=12)
    assert child[0] == 3, (
        "the thread spawned during the run was given the next handle, so handles "
        "are never reused and never renumbered: %r" % (child,))
    assert len(parent) == 3 and len(child) == 2, (
        "the parent ran three times and the child was called once after the turn "
        "that spawned it, so the round-robin found it: %r" % (child,))
    assert grown == {"finished": True, "steps": 5,
                     "order": ("other", "child", "parent"), "blocked": ()}, (
        "and the new thread finished inside the same run, in its place in the "
        "order: %r" % (grown,))

    # ---- the model: one workload, two interleavings -----------------------

    scripted = _workload(s, l, script=("a", "b", "c", "c"))
    result = scripted["result"]
    assert tuple(result) == ("answers", "steps", "ticks", "served", "starved",
                             "order"), (
        "the model reports serve_blocking's five facts plus the answering order, "
        "in that order: %r" % (tuple(result),))
    assert result["answers"] == {"a": (b"+one\n",), "b": (b"+two\n",),
                                 "c": (b"+three\n",)}, (
        "every client is answered with its own line, prefixed exactly once: %r"
        % (result["answers"],))
    assert tuple(result["answers"]) == ("a", "b", "c"), (
        "and every client is in the answers, in the order they arrived, whether "
        "it was answered or not: %r" % (tuple(result["answers"]),))
    assert result["order"] == ("c", "a", "b"), (
        "the script gave `c` the turns after the accepts, so the slow client's "
        "answer goes out first: %r" % (result["order"],))
    assert result["served"] == ("a", "b", "c"), (
        "who *finished* is a different question — the slow client is drained last "
        "— and `served` answers that one: %r" % (result["served"],))
    assert result["starved"] == (), (
        "no client was left unanswered: %r" % (result["starved"],))
    assert result["steps"] == 40 and result["ticks"] == 28, (
        "the run cost forty turns and the world spent twenty-eight ticks on "
        "waiting: %r" % (result,))

    round_robin = _workload(s, l)
    assert round_robin["result"]["order"] == ("a", "b", "c"), (
        "the same workload round-robin answers in the accept order instead, which "
        "is what makes the script the difference and not the workload: %r"
        % (round_robin["result"]["order"],))
    assert round_robin["result"]["served"] == ("b", "a", "c"), (
        "and who finished comes out in yet another order, because `a` waits on "
        "its drain while `b` closes: %r" % (round_robin["result"]["served"],))
    assert round_robin["result"]["answers"] == result["answers"], (
        "the interleaving changes the order and not one byte of the answers: %r "
        "vs %r" % (round_robin["result"]["answers"], result["answers"]))
    assert round_robin["result"]["steps"] == result["steps"], (
        "and it costs the same, because the work is the same: %r vs %r"
        % (round_robin["result"]["steps"], result["steps"]))
    assert round_robin["result"]["ticks"] == result["ticks"], (
        "the world spends its ticks on the same waits either way: %r vs %r"
        % (round_robin["result"]["ticks"], result["ticks"]))

    reads = tuple((entry["tick"], entry["id"], entry["byte_count"])
                  for entry in scripted["log"] if entry["event"] == "read")
    assert reads == ((0, 3, 6), (0, 1, 4), (0, 2, 4)), (
        "the world's own record shows whose request was read first, and it is the "
        "script's order rather than the accept order: %r" % (reads,))
    writes = tuple((entry["tick"], entry["id"], entry["byte_count"])
                   for entry in scripted["log"] if entry["event"] == "write")
    assert writes == ((0, 3, 7), (0, 1, 5), (0, 2, 5)), (
        "and the answers went out in the order the result reports them: %r"
        % (writes,))
    assert scripted["stats"] == {"ticks": 28, "events": 21, "accepted": 3,
                                 "listened": 0, "read_calls": 3, "write_calls": 3,
                                 "drops": 0, "drains": 9, "closes": 3,
                                 "bytes_read": 14, "bytes_written": 17,
                                 "bytes_dropped": 0, "bytes_drained": 17}, (
        "the link's numbers are the model's, to the byte: %r" % (scripted["stats"],))
    assert len(scripted["log"]) == 21, (
        "three accepts, three reads, three writes, nine drains and three closes "
        "are the twenty-one events the second run has to repeat: %r"
        % (len(scripted["log"]),))
    assert tuple(conn.client.name for conn in scripted["conns"]) == ("a", "b", "c"), (
        "the connections are the clients in the order they arrived: %r"
        % (tuple(conn.client.name for conn in scripted["conns"]),))
    assert all(conn.closed and conn.cause == "server" for conn in scripted["conns"]), (
        "every one of them is closed by the server, and none by a client that "
        "gave up waiting: %r"
        % ([(conn.closed, conn.cause) for conn in scripted["conns"]],))
    replied = sum(len(line) for lines in result["answers"].values()
                  for line in lines)
    assert replied == scripted["stats"]["bytes_drained"] == (
        scripted["stats"]["bytes_written"]), (
        "every byte the model reports as an answer is a byte the link carried and "
        "a client took: %r vs %r" % (replied, scripted["stats"]))
    assert result["ticks"] == scripted["stats"]["ticks"], (
        "and the ticks are the link's clock's: %r vs %r"
        % (result["ticks"], scripted["stats"]["ticks"]))

    # ---- the budget, on both sides of the last step -----------------------

    short = _workload(s, l, script=("a", "b", "c", "c"), budget=39)
    assert short["result"]["served"] == ("a", "b"), (
        "one turn short of forty leaves the slow client unserved, because its "
        "connection is closed by the last turn of the run: %r" % (short["result"],))
    assert short["result"]["starved"] == ("c",), (
        "and that is what `starved` means: the client the budget did not finish, "
        "named rather than counted: %r" % (short["result"]["starved"],))
    assert short["result"]["answers"] == scripted["result"]["answers"], (
        "its answer went out all the same, which is why `starved` is a verdict "
        "about the run and not about the bytes: %r" % (short["result"]["answers"],))
    assert (short["result"]["steps"], short["result"]["order"]) == (39, ("c", "a",
                                                                        "b")), (
        "the run stopped on the budget and not after it, with the answers it "
        "delivered in the script's order: %r" % (short["result"],))
    assert short["stats"]["closes"] == 2 and short["stats"]["bytes_drained"] == 17, (
        "two connections are closed and every byte is drained, and the third "
        "connection is left open — which is what the unserved client's thread "
        "would have closed on the turn the budget did not allow: %r"
        % (short["stats"],))

    answered = _workload(s, l, script=("a", "b", "c", "c"), budget=9)
    assert answered["result"]["answers"] == scripted["result"]["answers"], (
        "nine turns write all three answers — three accepts, three reads, three "
        "writes: %r" % (answered["result"]["answers"],))
    assert (answered["result"]["served"], answered["result"]["starved"]) == (
            (), ("a", "b", "c")), (
        "and not one client is served, because a client is served when its "
        "connection closes and nothing has been drained yet: %r"
        % (answered["result"],))
    assert answered["stats"]["bytes_written"] == 17 and (
        answered["stats"]["bytes_drained"] == 0), (
        "the link is the arbiter here: it carried all seventeen bytes of answer "
        "and the clients have taken none of them: %r" % (answered["stats"],))
    assert (answered["result"]["steps"], answered["result"]["ticks"]) == (9, 0), (
        "nine turns and not one tick, because every one of them moved a byte: %r"
        % (answered["result"],))

    nothing = _workload(s, l, budget=3)["result"]
    assert nothing == {"answers": {"a": (), "b": (), "c": ()}, "steps": 3,
                       "ticks": 0, "served": (), "starved": ("a", "b", "c"),
                       "order": ()}, (
        "three turns are three accepts and nothing else, so nothing is served, "
        "nobody's clock moved and every client is starved: %r" % (nothing,))

    # ---- the client with two requests, and the arrivals the world orders ---

    server = _server(l, (("two", (b"one\n", b"two\n"), {}),))
    twice = s.serve_threads(server, script=("two",) * 8)
    assert twice["answers"] == {"two": (b"+one\n", b"+two\n")}, (
        "a client with two requests is answered twice, in the order it asked: %r"
        % (twice["answers"],))
    assert twice["order"] == ("two", "two"), (
        "and the answering order lists an answer per reply rather than one entry "
        "per client: %r" % (twice["order"],))
    assert (twice["served"], twice["starved"]) == (("two",), ()), (
        "the one client finished and nothing was left unfinished: %r"
        % ((twice["served"], twice["starved"]),))
    assert (twice["steps"], twice["ticks"]) == (8, 2), (
        "eight turns: two requests, two replies, two drains and the waits between "
        "them: %r" % (twice,))
    assert server["link"].stats()["read_calls"] == 3, (
        "the link logged the second request becoming readable, which is what the "
        "server's next read is: %r" % (server["link"].stats(),))

    server = _server(l, (("long", (b"a long line here\n",), {}),))
    pieces = s.serve_threads(server)
    assert pieces["answers"] == {"long": (b"+a long line here\n",)}, (
        "a reply the outbox cannot take whole is one answer and not three: %r"
        % (pieces["answers"],))
    assert pieces["order"] == ("long",), (
        "and it is one entry in the answering order, because a reply is answered "
        "when its last byte is out and not when its first is: %r"
        % (pieces["order"],))
    writes = tuple(entry["byte_count"] for entry in server["link"].log()
                   if entry["event"] == "write")
    assert writes == (8, 8, 2), (
        "the world's log shows the three takes the eighteen bytes needed from an "
        "outbox of eight: %r" % (writes,))
    assert (pieces["served"], pieces["starved"]) == (("long",), ()), (
        "the connection closed once the whole reply was out and drained: %r"
        % (pieces,))
    assert (pieces["steps"], pieces["ticks"]) == (9, 3), (
        "nine turns, one per write and one per wait for the client to take what "
        "the outbox had already given it: %r" % (pieces,))

    staggered = _workload(s, l, seed=2,
                          script=("c", "b", "a", "c", "b", "a", "c", "b", "a"))
    assert staggered["result"]["served"] == ("a", "b", "c"), (
        "the accept order is the world's — the order the clients arrived, one "
        "every two ticks — whatever order the script names them in: %r"
        % (staggered["result"]["served"],))
    accept_ids = tuple(entry["id"] for entry in staggered["log"]
                       if entry["event"] == "accept")
    accept_ticks = tuple(entry["tick"] for entry in staggered["log"]
                         if entry["event"] == "accept")
    assert accept_ids == (1, 2, 3), (
        "and the log's accepts are in that order too: %r" % (accept_ids,))
    assert accept_ticks == (2, 3, 5), (
        "each accept waits for its own arrival and takes nobody else's place: a "
        "thread whose client has not arrived spends its turn on the world's clock, "
        "and a thread whose client is behind another's in the backlog spends it "
        "there too: %r" % (accept_ticks,))
    assert staggered["result"]["order"] == ("a", "b", "c"), (
        "the answers come out in the accept order and not in the script's rhythm, "
        "because the script names turns and the world decides readiness: %r"
        % (staggered["result"]["order"],))
    assert staggered["result"]["answers"] == result["answers"], (
        "the staggered run answers every client with its own line: %r"
        % (staggered["result"]["answers"],))
    assert (staggered["result"]["steps"], staggered["result"]["ticks"]) == (44, 32), (
        "waiting for three arrivals costs four turns and four ticks more than the "
        "same workload arriving at once: %r" % (staggered["result"],))

    # ---- the bundle, the budget and the script, refused by name -----------

    good = _server(l, (("solo", (b"ping\n",), {}),))
    _refuses(s.ServerError, "serve_threads of something that is not a server",
             lambda: s.serve_threads(["link", "clients", "requests"]),
             names=("link",))
    _refuses(s.ServerError, "serve_threads of a server with no requests",
             lambda: s.serve_threads({"link": good["link"],
                                      "clients": good["clients"]}),
             names=("'requests'",))
    _refuses(s.ServerError, "serve_threads of a server whose link is not the link",
             lambda: s.serve_threads(dict(good, link={})), names=("Link",))
    _refuses(s.ServerError, "serve_threads of a server with no clients",
             lambda: s.serve_threads(dict(good, clients=())), names=("()",))
    _refuses(s.ServerError, "serve_threads of a server whose clients are not a sequence",
             lambda: s.serve_threads(dict(good, clients=good["clients"][0])),
             names=("Client",))
    _refuses(s.ServerError, "serve_threads of a server whose requests are not a mapping",
             lambda: s.serve_threads(dict(good, requests=())), names=("()",))
    _refuses(s.ServerError, "serve_threads of a server with a client the link does not have",
             lambda: s.serve_threads(dict(good, clients=(l.Client("other", (b"x\n",)),))),
             names=("'other'", "1"))
    _refuses(s.ServerError, "serve_threads of a server naming more clients than the link has",
             lambda: s.serve_threads(dict(good, clients=good["clients"] * 2)),
             names=("2",))
    _refuses(s.ServerError, "serve_threads of a server with no request line for a client",
             lambda: s.serve_threads(dict(good, requests={})), names=("'solo'",))
    _refuses(s.ServerError, "serve_threads of a server whose requests are not a sequence",
             lambda: s.serve_threads(dict(good, requests={"solo": 42})),
             names=("'solo'", "42"))
    _refuses(s.ServerError, "serve_threads of a server whose request is not bytes",
             lambda: s.serve_threads(dict(good, requests={"solo": ("ping\n",)})),
             names=("'solo'",))
    _refuses(s.ServerError, "serve_threads with a budget that is not a count",
             lambda: s.serve_threads(good, budget=True), names=("True",))
    _refuses(s.ServerError, "serve_threads with a budget below zero",
             lambda: s.serve_threads(good, budget=-2), names=("-2",))
    _refuses(s.ServerError, "serve_threads with a script that is not a sequence of names",
             lambda: s.serve_threads(good, script="solo"), names=("'solo'",))
    _refuses(s.ServerError, "serve_threads with a script naming a client nobody spawned",
             lambda: s.serve_threads(good, script=("nobody",)), names=("'nobody'",))

    busy = _server(l, (("solo", (b"ping\n",), {}),
                       ("slow", (b"pong\n",), {"read_every": 4, "chunk": 1})))
    _refuses(s.ServerError, "serve_threads with a script naming a client that finished",
             lambda: s.serve_threads(busy, script=("solo",) * 6),
             names=("'solo'",))

    # ---- the whole workload, twice ----------------------------------------

    again = _workload(s, l, script=("a", "b", "c", "c"))
    assert again["result"] == scripted["result"], (
        "two runs of the same workload are the same run, byte for byte: %r vs %r"
        % (scripted["result"], again["result"]))
    assert again["log"] == scripted["log"], (
        "the world's log repeats too, event for event, which is the record the "
        "capstone will be graded against: %r vs %r"
        % (scripted["log"], again["log"]))
    assert again["stats"] == scripted["stats"], (
        "and so do the numbers recomputed from it: %r vs %r"
        % (scripted["stats"], again["stats"]))
    assert again["conns"][2].client.name == "c", (
        "the slow client is still the third connection of the second run: %r"
        % (again["conns"][2],))

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "concurrent-servers-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "link.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _cast(l):
        """The check's three clients: a quick one, one with two requests, a slow one."""
        return (l.Client("fast", (b"ping\n",), read_every=2),
                l.Client("two", (b"hello\n", b"again\n"), read_every=2),
                l.Client("slow", (b"hi\n",), read_every=4, chunk=1))

    def _server(l, clients, **kw):
        """The dict every model is handed: the link, its clients, and their lines."""
        return {"link": l.Link(clients, **kw), "clients": tuple(clients),
                "requests": {client.name: client.requests for client in clients}}

    def _react(s, l, clients, *, budget=256, **kw):
        """One reactor run over a fresh link, and the world it left behind."""
        server = _server(l, clients, **kw)
        return s.serve_reactor(server, budget=budget), server["link"]

    import link as l
    import stage_02 as blocking
    import stage_04 as s

    # ---- the family, and the world this stage reads ------------------------

    assert issubclass(s.ServerError, ValueError), (
        "the family is a ValueError, so a caller's `except ValueError` keeps "
        "catching a broken course: %r" % (s.ServerError.__mro__,))
    assert l.MAX_CHUNK == 64, (
        "the world carries at most 64 bytes per move: %r" % (l.MAX_CHUNK,))
    assert l.DEFAULT_OUTBOX == 8, (
        "the world's outbox holds eight bytes before a write is refused, which is "
        "more than any answer this check writes: %r" % (l.DEFAULT_OUTBOX,))

    # ---- ready_set: the two halves, in the order they were handed over -----

    link = l.Link((l.Client("early", (b"ping\n",), read_every=1),
                   l.Client("late", (b"pong\n",), read_every=1)), seed=4)
    first = link.connection(1)
    second = link.connection(2)
    ready = s.ready_set(link, (first, second))
    assert ready == ((1,), (1, 2)), (
        "the connection whose client has arrived has request bytes, so it is "
        "readable; the one whose client arrives on the fourth tick is not — and "
        "both outboxes have room: %r" % (ready,))
    assert isinstance(ready[0], tuple) and isinstance(ready[1], tuple), (
        "both halves are tuples, so a caller cannot edit the ready set it was "
        "handed: %r" % (ready,))
    assert s.ready_set(link, (first, second)) == ((1,), (1, 2)), (
        "reading readiness moves nothing: the same answer, twice, with no tick "
        "between them: %r" % (link.stats(),))
    assert link.now() == 0 and link.stats()["events"] == 0, (
        "polling the world is not a move and not a tick: %r" % (link.stats(),))
    assert s.ready_set(link, (second, first)) == ((1,), (2, 1)), (
        "both halves are in the order the connections were handed over and not "
        "in id order: %r" % (s.ready_set(link, (second, first)),))
    assert s.ready_set(link, ()) == ((), ()) and s.ready_set(link, []) == ((), ()), (
        "no connections is two empty tuples, whichever sequence is handed over: "
        "%r and %r" % (s.ready_set(link, ()), s.ready_set(link, [])))
    assert link.accept().id == 1 and link.waiting() == (2,), (
        "the listener hands over the client that has arrived and keeps the one "
        "that has not: %r" % (link.waiting(),))
    link.step(4)
    assert link.now() == 4 and link.accept().id == 2, (
        "four ticks move the clock to four and the second client into the "
        "listener's hands: %r, %r" % (link.now(), link.waiting()))
    assert s.ready_set(link, (first, second)) == ((1, 2), (1, 2)), (
        "the client that arrives on the fourth tick is readable on it, so both "
        "connections are in both halves: %r" % (s.ready_set(link, (first, second)),))

    moved = link.read(first)
    assert moved == b"ping\n" and link.owed(first), (
        "the whole request is taken in one read, so the link says this "
        "connection is owed a reply: %r" % (link.stats(),))
    assert s.ready_set(link, (first, second)) == ((2,), (1, 2)), (
        "a connection whose whole request has been taken is not readable any "
        "more, and is still writable: %r"
        % (s.ready_set(link, (first, second)),))
    link.read(second)
    assert s.ready_set(link, (first, second)) == ((), (1, 2)), (
        "with both requests taken nothing is readable and both outboxes still "
        "have room: %r" % (s.ready_set(link, (first, second)),))
    link.close(first)
    assert s.ready_set(link, (first, second)) == ((), (2,)), (
        "a closed connection is in neither half of the ready set: %r"
        % (s.ready_set(link, (first, second)),))

    # ---- ready_set: every way of handing it something it cannot compute ----

    _refuses(s.ServerError, "ready_set over something that is not the link",
             lambda: s.ready_set("the link", ()), names=("'the link'",))
    _refuses(s.ServerError, "ready_set over a bare connection",
             lambda: s.ready_set(link, second), names=("late",))
    _refuses(s.ServerError, "ready_set over a bare string",
             lambda: s.ready_set(link, "the conns"), names=("'the conns'",))
    _refuses(s.ServerError, "ready_set over None where the connections belong",
             lambda: s.ready_set(link, None), names=("None",))
    _refuses(s.ServerError, "ready_set over a connection the link never made",
             lambda: s.ready_set(link, (5,)), names=("5",))
    _refuses(s.ServerError, "ready_set over None among the connections",
             lambda: s.ready_set(link, (first, None)), names=("None",))
    _refuses(s.ServerError, "ready_set over a connection of another link",
             lambda: s.ready_set(link, (l.Link((l.Client("mine", (b"hi\n",)),))
                                        .connection(1),)), names=("1",))

    # ---- one workload, and everything the result owes the world ------------

    clients = _cast(l)
    result, world = _react(s, l, clients, budget=64)
    assert tuple(result) == ("answers", "steps", "polls", "ticks", "served",
                             "starved"), (
        "the result is stage 2's five keys with `polls` beside `steps`, in that "
        "order: %r" % (tuple(result),))
    assert tuple(result["answers"]) == ("fast", "two", "slow"), (
        "the answers are every client's, in the order the server was handed "
        "them: %r" % (tuple(result["answers"]),))
    assert result["answers"] == {"fast": (b"+ping\n",),
                                 "two": (b"+hello\n", b"+again\n"),
                                 "slow": (b"+hi\n",)}, (
        "every client's answers are the request lines with the one-byte prefix in "
        "front of them, in the order they were answered, and the two-request "
        "client's second answer is not its first: %r" % (result["answers"],))
    assert result["served"] == ("fast", "two", "slow"), (
        "the three clients are closed in the order they were accepted: %r"
        % (result["served"],))
    assert result["starved"] == (), (
        "every request was answered inside the budget, so nobody is starved: %r"
        % (result["starved"],))
    assert (result["steps"], result["polls"], result["ticks"]) == (17, 18, 17), (
        "seventeen turns of one poll and one tick each end this workload, and the "
        "last poll is the one that says so: steps %r, polls %r, ticks %r"
        % (result["steps"], result["polls"], result["ticks"]))
    assert result["ticks"] == result["steps"] == world.now(), (
        "a turn steps the link once and only once, so the reactor's turns and the "
        "world's ticks are the same number: %r, %r, %r"
        % (result["ticks"], result["steps"], world.now()))
    assert result["polls"] >= result["steps"], (
        "a turn polls at least once before it steps, so there are at least as "
        "many polls as turns: %r vs %r" % (result["polls"], result["steps"]))
    assert result["steps"] <= 2 * result["polls"] + 4, (
        "the reactor does not busy-wait: its turns are bounded by twice its polls "
        "plus the slack a poll loop needs to notice the world has settled — %r "
        "turns against %r polls" % (result["steps"], result["polls"]))
    numbers = world.stats()
    assert numbers["accepted"] == 3 and numbers["closes"] == 3, (
        "three clients were accepted and three connections closed: %r" % (numbers,))
    assert numbers["bytes_read"] == 20 and numbers["bytes_written"] == 24, (
        "the four request lines are twenty bytes in and their answers twenty-four "
        "out: %r" % (numbers,))
    assert numbers["bytes_drained"] == 24, (
        "and every answer reached the client it was written for, because the run "
        "did not stop early: %r" % (numbers,))
    assert numbers["drops"] == 0, (
        "nothing was queued that an outbox could not take: %r" % (numbers,))
    assert numbers["listened"] == 0, (
        "the reactor asks the link who is ready instead of putting a connection "
        "back in the listener's queue: %r" % (numbers,))
    written_answers = sum(len(line) for lines in result["answers"].values()
                          for line in lines)
    assert written_answers == numbers["bytes_drained"], (
        "the answers the reactor reports are whole reply lines and exactly the "
        "bytes the link carried into the clients' inboxes — %r bytes of answers "
        "against %r drained" % (written_answers, numbers["bytes_drained"]))

    # ---- two clients that finish in the same turn -------------------------

    twins, twin_world = _react(s, l, (l.Client("pair", (b"hi\n",), read_every=2),
                                      l.Client("mate", (b"yo\n",), read_every=2)))
    assert twins["served"] == ("pair", "mate"), (
        "two clients that finish in the same turn are served in the order they "
        "were accepted, and not in the order their names happen to sort in: %r"
        % (twins["served"],))
    assert twins["answers"] == {"pair": (b"+hi\n",), "mate": (b"+yo\n",)}, (
        "and both were answered: %r" % (twins["answers"],))
    assert (twins["steps"], twins["polls"], twins["ticks"]) == (3, 4, 3), (
        "three turns serve both of them, and the poll that ends the run is the "
        "fourth: steps %r, polls %r, ticks %r"
        % (twins["steps"], twins["polls"], twins["ticks"]))
    assert twin_world.stats()["closes"] == 2 and twin_world.done(), (
        "both connections were closed and the world settled: %r"
        % (twin_world.stats(),))

    # ---- the spine: the same answers, and a blocking server's step count ---

    blocked_server = _server(l, clients)
    blocked = blocking.serve_blocking(blocked_server)
    assert blocked["starved"] == (), (
        "the blocking server finishes this workload inside its budget, so the two "
        "models are being asked the same question: %r" % (blocked["starved"],))
    assert result["answers"] == blocked["answers"], (
        "the course's spine: one workload through two models answers every client "
        "byte for byte the same — %r against %r"
        % (result["answers"], blocked["answers"]))
    blocked_numbers = blocked_server["link"].stats()
    assert blocked_numbers["bytes_drained"] == numbers["bytes_drained"], (
        "and the same answer bytes reached the clients under both models: %r "
        "against %r" % (blocked_numbers, numbers))
    assert blocked["served"] == result["served"], (
        "both models served the same clients, in the same order: %r against %r"
        % (blocked["served"], result["served"]))
    assert blocked["steps"] > result["steps"], (
        "the same answers cost a blocking server more steps than a reactor, "
        "because it waits for the slow client: %r against %r"
        % (blocked["steps"], result["steps"]))

    # ---- the budget: a spent budget is an outcome, not an exception --------

    none, none_world = _react(s, l, clients, budget=0)
    assert (none["steps"], none["polls"], none["ticks"]) == (0, 0, 0), (
        "a budget of no turns takes no turn: %r"
        % ((none["steps"], none["polls"], none["ticks"]),))
    assert none["answers"] == {"fast": (), "two": (), "slow": ()}, (
        "and answers nobody, so every client's answers are the empty tuple: %r"
        % (none["answers"],))
    assert none["served"] == () and none["starved"] == ("fast", "two", "slow"), (
        "nobody is served and every client is starved: %r, %r"
        % (none["served"], none["starved"]))
    assert none_world.stats()["events"] == 0, (
        "a run that took no turn touched nothing, not even the listener: %r"
        % (none_world.stats(),))

    one, one_world = _react(s, l, clients, budget=1)
    assert one["answers"] == {"fast": (), "two": (), "slow": ()}, (
        "one turn reads the three request lines and stages three replies, but an "
        "answer is counted when its last byte reaches the outbox: %r"
        % (one["answers"],))
    assert one_world.stats()["bytes_written"] == 0, (
        "nothing has been written yet, which is what the link's own count says: "
        "%r" % (one_world.stats(),))
    assert (one["steps"], one["polls"]) == (1, 1), (
        "one turn is one poll and one step: %r"
        % ((one["steps"], one["polls"]),))
    assert one["starved"] == ("fast", "two", "slow"), (
        "and every client still has a request this run has not answered: %r"
        % (one["starved"],))

    short, short_world = _react(s, l, clients, budget=7)
    assert short["answers"] == {"fast": (b"+ping\n",),
                                "two": (b"+hello\n", b"+again\n"),
                                "slow": (b"+hi\n",)}, (
        "seven turns are enough to answer all three clients: %r"
        % (short["answers"],))
    assert short["served"] == ("fast", "two") and short["starved"] == (), (
        "a client whose answer has been written but not yet drained is neither "
        "served nor starved — its requests were answered: %r, %r"
        % (short["served"], short["starved"]))
    assert short_world.stats()["bytes_drained"] == 21, (
        "the slow reader has taken three of its four answer bytes when the budget "
        "runs out: %r" % (short_world.stats(),))
    assert short["polls"] == short["steps"] == 7, (
        "a budget that runs out stops the loop without a last poll to notice: %r, "
        "%r" % (short["polls"], short["steps"]))

    # ---- the listener: a client that has not arrived is not abandoned ------

    waiting, waiting_world = _react(
        s, l, (l.Client("early", (b"hi\n",), read_every=1),
               l.Client("late", (b"yo\n",), read_every=1)), budget=32, seed=5)
    assert waiting["answers"] == {"early": (b"+hi\n",), "late": (b"+yo\n",)}, (
        "the second client arrives on the fifth tick and the run is not over until "
        "it has been served: %r" % (waiting["answers"],))
    assert (waiting["steps"], waiting["polls"], waiting["ticks"]) == (8, 9, 8), (
        "two of those turns have nothing ready — the listener is holding a client "
        "and the reactor ticks rather than spinning: steps %r, polls %r, ticks %r"
        % (waiting["steps"], waiting["polls"], waiting["ticks"]))
    assert waiting["steps"] <= 2 * waiting["polls"] + 4, (
        "and waiting for a client that has not arrived is still not a busy-wait: "
        "%r turns against %r polls" % (waiting["steps"], waiting["polls"]))
    assert waiting["served"] == ("early", "late") and waiting["starved"] == (), (
        "both clients were served once they arrived: %r, %r"
        % (waiting["served"], waiting["starved"]))
    assert waiting_world.stats()["accepted"] == 2, (
        "and both were accepted, one of them four ticks after the other: %r"
        % (waiting_world.stats(),))

    # ---- an outbox of one byte: the tail is deferred, never dropped --------

    tiny, tiny_world = _react(s, l, clients, budget=64, outbox=1)
    assert tiny["answers"] == result["answers"], (
        "an outbox of one byte changes when the answers are written and not what "
        "they are: %r" % (tiny["answers"],))
    assert (tiny["steps"], tiny["polls"], tiny["ticks"]) == (17, 18, 17), (
        "and the turns are the same turns, because a shorter write is data and "
        "not a lost reply: %r" % ((tiny["steps"], tiny["polls"], tiny["ticks"]),))
    tiny_numbers = tiny_world.stats()
    assert tiny_numbers["write_calls"] == 24 and tiny_numbers["drops"] == 0, (
        "twenty-four writes carry the same twenty-four bytes, and the link drops "
        "nothing: %r" % (tiny_numbers,))
    assert tiny_numbers["bytes_drained"] == 24 and tiny_numbers["closes"] == 3, (
        "every byte reached a client and every connection was closed: %r"
        % (tiny_numbers,))

    # ---- refusals: the server a reactor will not run ----------------------

    _refuses(s.ServerError, "serve_reactor on something that is not a server",
             lambda: s.serve_reactor(("a", "link")), names=("'a'",))
    _refuses(s.ServerError, "serve_reactor with no link at all",
             lambda: s.serve_reactor({"clients": clients}), names=("None",))
    _refuses(s.ServerError, "serve_reactor with a link that is not the world",
             lambda: s.serve_reactor({"link": "the link", "clients": clients}),
             names=("'the link'",))
    _refuses(s.ServerError, "serve_reactor with no clients at all",
             lambda: s.serve_reactor({"link": l.Link(clients)}), names=("None",))
    _refuses(s.ServerError, "serve_reactor with clients that are not a sequence",
             lambda: s.serve_reactor({"link": l.Link(clients), "clients": "fast"}),
             names=("'fast'",))
    _refuses(s.ServerError, "serve_reactor with an empty list of clients",
             lambda: s.serve_reactor({"link": l.Link(clients), "clients": []}),
             names=("[]",))
    _refuses(s.ServerError, "serve_reactor with a client that is not a Client",
             lambda: s.serve_reactor({"link": l.Link(clients),
                                      "clients": ("fast",)}), names=("'fast'",))
    _refuses(s.ServerError, "a budget of one turn too few",
             lambda: s.serve_reactor(_server(l, clients), budget=-1),
             names=("-1",))
    _refuses(s.ServerError, "a budget of True, which is an int if you squint",
             lambda: s.serve_reactor(_server(l, clients), budget=True),
             names=("True",))
    _refuses(s.ServerError, "a budget that is not a number at all",
             lambda: s.serve_reactor(_server(l, clients), budget="many"),
             names=("'many'",))

    # ---- the whole workload, twice, equals and together -------------------

    other, other_world = _react(s, l, clients, budget=64)
    assert other == result, (
        "two runs of the same workload are the same run, byte for byte: %r vs %r"
        % (other, result))
    assert other_world.log() == world.log(), (
        "and the same events in the same order, which is what makes a step count "
        "worth reporting: %r vs %r"
        % (other_world.log(), world.log()))
    assert len(world.log()) == 22, (
        "the log's twenty-two events — three accepts, five reads, four writes, "
        "seven drains and three closes — are the record the second run repeats: %r"
        % (len(world.log()),))
    assert s.ready_set(world, tuple(world.conns())) == ((), ()), (
        "and the world it settles into is one no connection is ready in: %r"
        % (s.ready_set(world, tuple(world.conns())),))
    assert world.done(), (
        "every client drained every answer it was owed, which is how this model "
        "ends where a blocking one does: %r" % (world.stats(),))

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "concurrent-servers-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "link.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _session(l, clients, *, outbox=8, seed=0):
        """The dict of §4.2 — link, clients and requests — built from scratch.

        Every run gets its own world: two models sharing one `Link` is a mistake in
        the capstone, and a check that shared one would never see it.
        """
        world = l.Link(clients, outbox=outbox, seed=seed)
        return {"link": world, "clients": tuple(clients),
                "requests": {client.name: tuple(client.requests) for client in clients}}

    def _run(s, session, **kwargs):
        """One run of the loop, with the world's own record beside its result.

        The link is the arbiter: what the loop says it answered, what the log says it
        carried, what each client still holds in its inbox and how much of its script
        it never got to send are all here, so an assert can hold the two against each
        other instead of taking the loop's word for it.
        """
        world = session["link"]
        result = s.serve_with_timeouts(session, **kwargs)
        return {"result": result,
                "stats": world.stats(),
                "log": world.log(),
                "closed": {conn.client.name: (conn.closed, conn.cause)
                           for conn in world.conns()},
                "inbox": {conn.client.name: conn.inbox for conn in world.conns()},
                "counted": {conn.client.name: (conn.requests_done,
                                               len(conn.client.requests))
                            for conn in world.conns()}}

    def _wide(s, l, *, idle, **kwargs):
        """The two-client workload again, under a wider or narrower `idle`.

        One client answers and drains at once; the other has two requests and reads
        every thirty-second tick, so whether it is served or timed out is decided by
        the window and by nothing else about it.
        """
        return _run(s, _session(l, (l.Client("quick", (b"ping\n",), read_every=1),
                                    l.Client("stuck", (b"one\n", b"two\n"),
                                             read_every=32))),
                    idle=idle, **kwargs)

    def _paced(s, l, *, idle=8, **kwargs):
        """The workload that goes idle between its replies and is served anyway.

        `burst` reads every fourth tick: its reply reaches its inbox on one tick, it
        drains on the next tick that is a multiple of four, and that gap is an idle
        window — one the loop has to disarm when the drain comes, or the deadline
        earned during the gap closes a connection that has since answered.
        """
        return _run(s, _session(l, (l.Client("burst", (b"one\n", b"two\n", b"tri\n"),
                                              read_every=4),)),
                    idle=idle, **kwargs)

    def _staggered(s, l, *, seed=4, **kwargs):
        """Three clients arriving four ticks apart, and a listener that takes one a turn."""
        return _run(s, _session(l, (l.Client("first", (b"one\n",)),
                                    l.Client("second", (b"two\n",)),
                                    l.Client("third", (b"tri\n",))), seed=seed),
                    **kwargs)

    import fleet as f
    import link as l
    import stage_05 as s

    # ---- the constants and the family -------------------------------------

    assert s.DEFAULT_IDLE == 8, (
        "eight idle ticks is the contract's default: long enough that a slow "
        "client is not timed out and short enough that a stopped one is: %r"
        % (s.DEFAULT_IDLE,))
    assert s.DEFAULT_BUDGET == 256, (
        "and a run's default budget is 256 turns: %r" % (s.DEFAULT_BUDGET,))
    assert issubclass(s.ServerError, ValueError), (
        "the family is a ValueError, so a caller's `except ValueError` keeps "
        "catching a broken course: %r" % (s.ServerError.__mro__,))
    assert l.MAX_CHUNK == 64, (
        "the world carries at most 64 bytes per move: %r" % (l.MAX_CHUNK,))

    # ---- the queue, on the clock it is handed -----------------------------

    clock = f.Clock(start=0)
    timers = s.Timers(clock)
    assert timers.due() == (), (
        "a queue with nothing armed is due nothing: %r" % (timers.due(),))
    assert timers.next_at() is None, (
        "and the earliest deadline of an empty queue is None and not a number: %r"
        % (timers.next_at(),))

    late = timers.arm(7, "late")
    early = timers.arm(3, "early")
    assert (late, early) == (1, 2), (
        "handles are ints handed out one per timer, growing with every arm: %r"
        % ((late, early),))
    assert timers.next_at() == 3, (
        "next_at is the earliest deadline armed, not the one armed last: %r"
        % (timers.next_at(),))
    assert timers.due() == (), (
        "and nothing is due before the clock has reached its deadline: %r"
        % (timers.due(),))

    clock.tick(2)
    assert timers.due() == (), (
        "two ticks in, a deadline of three is still ahead: %r" % (timers.due(),))
    assert timers.next_at() == 3, (
        "and it is still the next one: %r" % (timers.next_at(),))
    clock.tick(1)
    assert timers.due() == ((early, "early"),), (
        "a deadline is due on the tick it names, and not one tick later: %r"
        % (timers.due(),))
    assert timers.due() == (), (
        "and due() removes what it hands back, so no timer is ever returned "
        "twice: %r" % (timers.due(),))
    assert timers.cancel(early) is False, (
        "a timer that has already fired is not live to cancel: %r"
        % (timers.cancel(early),))
    assert timers.next_at() == 7, (
        "the one timer left is the next deadline, whether it is early or late: %r"
        % (timers.next_at(),))
    clock.tick(4)
    assert timers.due() == ((late, "late"),), (
        "and it comes due on its own tick, four ticks on: %r" % (timers.due(),))
    assert timers.next_at() is None and timers.due() == (), (
        "a queue whose timers have all fired is empty again: %r"
        % ((timers.next_at(), timers.due()),))

    # ---- a deadline in the past, and two on the same tick -----------------

    clock = f.Clock(start=7)
    queue = s.Timers(clock)
    overdue = queue.arm(clock.now() - 4, "overdue")
    exactly = queue.arm(clock.now(), "exactly")
    assert queue.next_at() == 3, (
        "a timer armed in the past is the earliest deadline there is: %r"
        % (queue.next_at(),))
    assert queue.due() == ((overdue, "overdue"), (exactly, "exactly")), (
        "and both it and the one armed for the tick the clock is on are due now, "
        "earliest first: %r" % (queue.due(),))
    assert queue.due() == () and queue.next_at() is None, (
        "nothing armed after both have come due: %r"
        % ((queue.due(), queue.next_at()),))

    clock = f.Clock(start=7)
    queue = s.Timers(clock)
    first = queue.arm(11, "first")
    second = queue.arm(11, "second")
    third = queue.arm(9, "third")
    assert (first, second, third) == (1, 2, 3), (
        "handles keep growing across deadlines, however they are ordered: %r"
        % ((first, second, third),))
    assert queue.next_at() == 9, (
        "the earliest of three deadlines is the next one, whatever order they "
        "were armed in: %r" % (queue.next_at(),))
    clock.tick(2)
    assert queue.due() == ((third, "third"),), (
        "the deadline of nine fires first although it was armed last: %r"
        % (queue.due(),))
    clock.tick(2)
    assert queue.due() == ((first, "first"), (second, "second")), (
        "and two timers with one deadline come out in handle order, which is the "
        "order they were armed in: %r" % (queue.due(),))
    assert clock.now() == 11 and queue.next_at() is None, (
        "the clock has reached eleven and the queue is empty: %r"
        % ((clock.now(), queue.next_at()),))

    # ---- a cancelled timer is never due -----------------------------------

    clock = f.Clock(start=0)
    queue = s.Timers(clock)
    soon = queue.arm(2, "soon")
    far = queue.arm(5, "far")
    assert queue.next_at() == 2, (
        "two timers armed, the nearer deadline is next: %r" % (queue.next_at(),))
    assert queue.cancel(soon) is True, (
        "cancelling a live timer answers True: %r" % (queue.cancel(soon),))
    assert queue.cancel(soon) is False, (
        "cancelling it again answers False, because it is not there any more: %r"
        % (queue.cancel(soon),))
    assert queue.next_at() == 5, (
        "a cancelled timer is not the next deadline either: %r" % (queue.next_at(),))
    clock.tick(2)
    assert queue.due() == (), (
        "and it is not due on its own tick, which is the whole point of "
        "cancelling it: %r" % (queue.due(),))
    clock.tick(3)
    assert queue.due() == ((far, "far"),), (
        "while the timer that is still armed comes due when its tick arrives: %r"
        % (queue.due(),))
    assert queue.cancel(far) is False and queue.cancel(99) is False, (
        "a handle that has fired is gone, and one that was never armed is a "
        "question rather than a mistake: %r"
        % ((queue.cancel(far), queue.cancel(99)),))

    # ---- two queues, two clocks -------------------------------------------

    mine = f.Clock(start=0)
    theirs = f.Clock(start=0)
    ours = s.Timers(mine)
    foreign = s.Timers(theirs)
    assert ours.arm(3, "ours") == 1 and foreign.arm(3, "theirs") == 1, (
        "two queues keep their own handles")
    theirs.tick(3)
    assert foreign.due() == ((1, "theirs"),), (
        "a queue comes due on the clock it was handed: %r" % (foreign.due(),))
    assert ours.due() == () and mine.now() == 0, (
        "and not on a clock it was never given: %r at %r"
        % (ours.due(), mine.now()))
    mine.tick(3)
    assert ours.due() == ((1, "ours"),), (
        "the other queue follows its own clock: %r" % (ours.due(),))

    # ---- the refusals of the queue ----------------------------------------

    for bad in (None, 0, "clock", True):
        _refuses(s.ServerError, "Timers on a clock of %r" % (bad,),
                 lambda bad=bad: s.Timers(bad), names=(repr(bad),))

    clock = f.Clock(start=0)
    queue = s.Timers(clock)
    for bad in ("5", None, True):
        _refuses(s.ServerError, "arm with a deadline of %r" % (bad,),
                 lambda bad=bad: queue.arm(bad, "a"), names=(repr(bad),))
    for bad in (7, "", None, True):
        _refuses(s.ServerError, "arm with a name of %r" % (bad,),
                 lambda bad=bad: queue.arm(3, bad), names=(repr(bad),))
    for bad in ("1", None, True):
        _refuses(s.ServerError, "cancel of %r" % (bad,),
                 lambda bad=bad: queue.cancel(bad), names=(repr(bad),))
    assert queue.next_at() is None and queue.due() == () and clock.now() == 0, (
        "and not one of those refusals armed a timer or moved the clock: %r"
        % ((queue.next_at(), queue.due(), clock.now()),))

    # ---- the loop: one client, one request, one answer --------------------

    plain = _run(s, _session(l, (l.Client("solo", (b"ping\n",), read_every=1),)))
    result = plain["result"]
    assert tuple(result) == ("answers", "steps", "ticks", "timed_out", "served"), (
        "a run reports its five facts in the contract's order: %r"
        % (tuple(result),))
    assert result["answers"] == {"solo": (b"+ping\n",)}, (
        "the answer is the request line with the prefix in front of it, written "
        "once: %r" % (result["answers"],))
    assert result["served"] == ("solo",) and result["timed_out"] == (), (
        "a client that reads what it is sent is served and never timed out: %r"
        % ((result["served"], result["timed_out"]),))
    assert (result["steps"], result["ticks"]) == (4, 3), (
        "the loop took four turns — accept, read, write, close — and the last of "
        "them moved nothing, so `steps` is not `ticks`: %r"
        % ((result["steps"], result["ticks"]),))
    assert result["ticks"] == plain["stats"]["ticks"] == 3, (
        "`ticks` is the link's own reading and not the loop's belief about it: %r"
        % (plain["stats"],))
    assert tuple(entry["event"] for entry in plain["log"]) == (
        "accept", "read", "write", "drain", "close"), (
        "and the log says what the loop did: one accept, one read, one write, one "
        "drain and one close, in that order: %r" % (plain["log"],))
    assert plain["stats"]["bytes_written"] == plain["stats"]["bytes_drained"] == 6, (
        "the six bytes of the answer were written and six were drained, because "
        "the loop waited for the client instead of closing on it: %r"
        % (plain["stats"],))
    assert plain["stats"]["drops"] == 0 and plain["closed"] == {
        "solo": (True, "server")}, (
        "nothing was queued the outbox could not take, and the connection was "
        "closed by the server at a finish: %r" % ((plain["stats"], plain["closed"]),))
    assert sum(len(answer) for answer in result["answers"]["solo"]) == (
        plain["stats"]["bytes_drained"]), (
        "the answers' bytes are the bytes the client actually took: %r vs %r"
        % (result["answers"], plain["stats"]))

    # ---- the timeout: one client served, one closed for idling ------------

    timed = _run(s, _session(l, (l.Client("quick", (b"ping\n",), read_every=1),
                                 l.Client("stuck", (b"one\n", b"two\n"),
                                          read_every=32))))
    result = timed["result"]
    assert result["served"] == ("quick",) and result["timed_out"] == ("stuck",), (
        "one client is served to a finish while the other — the one that stopped "
        "reading — is timed out, and the two names never overlap: %r"
        % ((result["served"], result["timed_out"]),))
    assert result["answers"] == {"quick": (b"+ping\n",), "stuck": (b"+one\n",)}, (
        "both clients were answered, in accept order; the timed-out one's answer "
        "is in `answers` although it never reached the client: %r"
        % (result["answers"],))
    assert (result["steps"], result["ticks"]) == (13, 12), (
        "the idle client's deadline is the contract's default of eight ticks "
        "after its answer landed, and the loop stops on the tick it comes due: %r"
        % ((result["steps"], result["ticks"]),))
    assert timed["closed"]["stuck"] == (True, "server"), (
        "the timed-out connection is closed by the server — which is what a "
        "timeout is — and not by a finish: %r" % (timed["closed"]["stuck"],))
    assert timed["closed"]["quick"] == (True, "server"), (
        "and the served one is closed by the loop that finished it: %r"
        % (timed["closed"]["quick"],))
    assert timed["inbox"]["stuck"] == b"+one\n", (
        "the answer the timed-out client was never going to read is still in its "
        "inbox, which is exactly why the close is a timeout: %r"
        % (timed["inbox"]["stuck"],))
    assert timed["counted"]["stuck"] == (0, 2), (
        "that client had a second request in its script and the world never moved "
        "it on to it, because the answer to the first was never drained: %r"
        % (timed["counted"]["stuck"],))
    assert tuple(entry["event"] for entry in timed["log"]) == (
        "accept", "accept", "read", "write", "read", "drain", "close", "write",
        "close"), (
        "the log is the whole story: two accepts, then a read, a write, a drain "
        "and a close for the client that finished, then the other client's read "
        "and its write and finally one close with no drain in between: %r"
        % (timed["log"],))
    assert tuple(entry["id"] for entry in timed["log"]
                 if entry["event"] == "drain") == (1,), (
        "exactly one connection drained an answer, and it is the one that was "
        "served: %r" % (timed["log"],))
    assert tuple(entry["tick"] for entry in timed["log"]) == (
        0, 1, 1, 2, 2, 3, 3, 3, 12), (
        "and the ticks say when: the accepts, the request, the answer, the second "
        "request, the drain and the finish, and then a close eight ticks after "
        "the client that stopped reading took its last answer: %r"
        % (tuple(entry["tick"] for entry in timed["log"]),))
    assert timed["stats"]["bytes_drained"] == 6, (
        "six bytes — the single answer the quick client read — reached an inbox: %r"
        % (timed["stats"],))
    assert timed["stats"]["bytes_written"] == 11, (
        "eleven bytes were written for the two clients, and the five the timed-out "
        "one never drained are the difference: %r" % (timed["stats"],))
    assert timed["stats"]["closes"] == 2 and timed["stats"]["drains"] == 1, (
        "two connections were closed — one finished, one timed out — after one "
        "drain: %r" % (timed["stats"],))

    # ---- the connection the loop closed never becomes a finish ------------

    mixed = _run(s, _session(l, (l.Client("steady", (b"one\n", b"two\n", b"tri\n",
                                                  b"quad\n"), read_every=8),
                                 l.Client("stuck", (b"one\n", b"two\n"),
                                          read_every=32))))
    result = mixed["result"]
    assert result["timed_out"] == ("stuck",) and result["served"] == ("steady",), (
        "a run that outlives its own timeout — the steady client is still being "
        "served twenty ticks after the other one was closed — still reports the "
        "two verdicts apart: %r"
        % ((result["served"], result["timed_out"]),))
    assert not set(result["served"]) & set(result["timed_out"]), (
        "no client is ever both served and timed out, however long the loop "
        "carries on after the close: %r"
        % (result,))
    assert tuple(entry["tick"] for entry in mixed["log"]
                 if entry["event"] == "close") == (12, 32), (
        "the timed-out connection was closed at the twelfth tick and the served "
        "one at the thirty-second, and nothing touched the first one in "
        "between: %r" % (tuple(entry["tick"] for entry in mixed["log"]),))
    assert (result["steps"], result["ticks"]) == (33, 32), (
        "thirty-three turns and thirty-two ticks, because the last turn had "
        "nothing left to move: %r" % ((result["steps"], result["ticks"]),))
    assert result["answers"] == {"steady": (b"+one\n", b"+two\n", b"+tri\n",
                                            b"+quad\n"),
                                 "stuck": (b"+one\n",)}, (
        "the steady client was answered four times and the stopped one once: %r"
        % (result["answers"],))
    assert mixed["stats"]["drains"] == 4 and mixed["stats"]["closes"] == 2, (
        "four drains — one per answer the steady client took — and two closes: %r"
        % (mixed["stats"],))

    # ---- the window is the window, and not the client ---------------------

    narrow = _wide(s, l, idle=4)
    assert narrow["result"]["timed_out"] == ("stuck",), (
        "a four-tick window closes the client that stopped reading four ticks "
        "after it went idle: %r" % (narrow["result"],))
    assert (narrow["result"]["steps"], narrow["result"]["ticks"]) == (9, 8), (
        "which is the window and nothing about the client: %r"
        % ((narrow["result"]["steps"], narrow["result"]["ticks"]),))
    patient = _wide(s, l, idle=32)
    assert patient["result"]["timed_out"] == (), (
        "the same client is served under a window long enough for it to drain on "
        "its own schedule, so the timeout is the window's verdict: %r"
        % (patient["result"],))
    assert patient["result"]["served"] == ("quick", "stuck"), (
        "both clients are served, in accept order this time: %r"
        % (patient["result"]["served"],))
    assert (patient["result"]["steps"], patient["result"]["ticks"]) == (65, 64), (
        "and the run takes exactly the ticks its two drains need: %r"
        % ((patient["result"]["steps"], patient["result"]["ticks"]),))
    assert patient["result"]["answers"] == {"quick": (b"+ping\n",),
                                            "stuck": (b"+one\n", b"+two\n")}, (
        "the client that was timed out under the narrow window answers twice "
        "under this one: %r" % (patient["result"]["answers"],))

    # ---- the deadline is disarmed when the connection is serviced ---------

    paced = _paced(s, l)
    result = paced["result"]
    assert result["timed_out"] == (), (
        "a client that goes idle between its replies and drains them on its own "
        "schedule is never closed for idling, however often it idles: %r"
        % (result,))
    assert result["served"] == ("burst",) and result["answers"] == {
        "burst": (b"+one\n", b"+two\n", b"+tri\n")}, (
        "all three of its requests were answered, in the order they were sent: %r"
        % (result["answers"],))
    assert (result["steps"], result["ticks"]) == (13, 12), (
        "and the loop took exactly the turns its drains needed: %r"
        % ((result["steps"], result["ticks"]),))
    assert paced["stats"]["drains"] == 3 and paced["stats"]["closes"] == 1, (
        "three drains and one close, which is a conversation and not a timeout: %r"
        % (paced["stats"],))
    assert paced["stats"]["bytes_drained"] == paced["stats"]["bytes_written"] == 15, (
        "and every byte the server wrote was taken by the client: %r"
        % (paced["stats"],))

    # ---- a reply the outbox takes in two moves ----------------------------

    long = _run(s, _session(l, (l.Client("long", (b"hello there\n",), read_every=4),),
                            outbox=8))
    result = long["result"]
    assert result["answers"] == {"long": (b"+hello there\n",)}, (
        "a thirteen-byte reply leaves the outbox eight bytes at a time and is one "
        "answer all the same: %r" % (result["answers"],))
    assert long["stats"]["write_calls"] == 2, (
        "the link took it in two writes, which is what a short write is: %r"
        % (long["stats"],))
    assert (result["steps"], result["ticks"]) == (5, 4), (
        "the deferred tail takes a turn of its own: %r"
        % ((result["steps"], result["ticks"]),))
    assert long["stats"]["bytes_written"] == 13 and long["stats"]["bytes_drained"] == 13, (
        "and all thirteen bytes of the answer reached the client: %r"
        % (long["stats"],))

    # ---- a listener that takes one client a turn --------------------------

    staggered = _staggered(s, l)
    assert staggered["result"]["served"] == ("first", "second", "third"), (
        "three clients arriving four ticks apart are all served, in accept order: %r"
        % (staggered["result"]["served"],))
    assert staggered["result"]["answers"] == {"first": (b"+one\n",),
                                              "second": (b"+two\n",),
                                              "third": (b"+tri\n",)}, (
        "and each of them is answered its own line: %r"
        % (staggered["result"]["answers"],))
    assert (staggered["result"]["steps"], staggered["result"]["ticks"]) == (12, 11), (
        "the loop waits for every arrival, which is what the ticks are: %r"
        % ((staggered["result"]["steps"], staggered["result"]["ticks"]),))
    assert staggered["stats"]["accepted"] == 3 and staggered["stats"]["closes"] == 3, (
        "three connections accepted, three closed: %r" % (staggered["stats"],))

    # ---- a spent budget is an outcome, not an exception -------------------

    spent = _staggered(s, l, budget=6)
    result = spent["result"]
    assert result["steps"] == 6, (
        "a run stops after exactly the turns it was given and says so: %r"
        % (result["steps"],))
    assert result["served"] == ("first",) and result["timed_out"] == (), (
        "one client was far enough along to finish inside that budget, and "
        "nothing was timed out on its account: %r"
        % ((result["served"], result["timed_out"]),))
    assert tuple(result["answers"]) == ("first", "second", "third"), (
        "every client the listener holds is named in `answers`, reached or not: %r"
        % (tuple(result["answers"]),))
    assert result["answers"]["second"] == () and result["answers"]["third"] == (), (
        "and the two the budget never reached answer with nothing at all: %r"
        % (result["answers"],))
    assert spent["closed"]["second"] == (False, None) and spent["closed"]["third"] == (
        False, None), (
        "no connection was closed on the budget's account: %r" % (spent["closed"],))
    assert spent["stats"]["accepted"] == 2 and spent["stats"]["closes"] == 1, (
        "the listener had handed over two clients, one of which was served: %r"
        % (spent["stats"],))

    # ---- a listener with nobody to hand over ------------------------------

    world = l.Link((l.Client("early", (b"one\n",)),))
    world.accept()
    unhanded = _run(s, {"link": world, "clients": (world.conns()[0].client,),
                        "requests": {"early": (b"one\n",)}}, budget=4)
    assert unhanded["result"] == {"answers": {"early": ()}, "steps": 1, "ticks": 0,
                                  "timed_out": (), "served": ()}, (
        "a client the listener never handed over is not the loop's to serve, and "
        "one turn is enough to see that: %r" % (unhanded["result"],))

    # ---- the refusals of the loop -----------------------------------------

    world = l.Link((l.Client("solo", (b"ping\n",)),))
    server = {"link": world, "clients": (world.conns()[0].client,),
              "requests": {"solo": (b"ping\n",)}}
    for bad in (None, 7, "server", []):
        _refuses(s.ServerError, "serve_with_timeouts of %r" % (bad,),
                 lambda bad=bad: s.serve_with_timeouts(bad), names=(repr(bad),))
    for missing in ("link", "clients", "requests"):
        short = {key: value for key, value in server.items() if key != missing}
        _refuses(s.ServerError, "a server without %r" % (missing,),
                 lambda short=short: s.serve_with_timeouts(short),
                 names=("'%s'" % (missing,),))
    _refuses(s.ServerError, "a server whose link is a string",
             lambda: s.serve_with_timeouts(dict(server, link="world")),
             names=("'world'",))
    for bad in (0, -1, True, "8", None):
        _refuses(s.ServerError, "an idle of %r" % (bad,),
                 lambda bad=bad: s.serve_with_timeouts(server, idle=bad),
                 names=(repr(bad),))
        _refuses(s.ServerError, "a budget of %r" % (bad,),
                 lambda bad=bad: s.serve_with_timeouts(server, budget=bad),
                 names=(repr(bad),))
    assert world.stats()["events"] == 0 and world.stats()["ticks"] == 0, (
        "and a refused call never reached the world it was offered: %r"
        % (world.stats(),))

    # ---- two runs of one workload are one run -----------------------------

    first = _run(s, _session(l, (l.Client("quick", (b"ping\n",), read_every=1),
                                 l.Client("stuck", (b"one\n", b"two\n"),
                                          read_every=32))))
    second = _run(s, _session(l, (l.Client("quick", (b"ping\n",), read_every=1),
                                  l.Client("stuck", (b"one\n", b"two\n"),
                                           read_every=32))))
    assert first == second, (
        "two runs of one workload — timeouts, log and inboxes included — are the "
        "same run, byte for byte: %r vs %r" % (first, second))
    assert first["result"]["answers"] is not second["result"]["answers"], (
        "and each run hands back its own dict, never a shared one: %r"
        % (first["result"]["answers"],))
    assert _paced(s, l) == _paced(s, l), (
        "the workload that idles between its replies repeats too: %r"
        % (_paced(s, l)["result"],))
    assert _staggered(s, l) == _staggered(s, l), (
        "and so does the one whose arrivals are the link's own ticks: %r"
        % (_staggered(s, l)["result"],))

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "concurrent-servers-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "link.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def echo(*args):
        """A callback for the table's unit tests: it answers with what it was given."""
        return args

    def _serve(s, l, clients, *, budget=256, outbox=None, seed=0):
        """Serve one fresh link's clients and hand back everything the check pins.

        The server dict is the course's own — `{"link", "clients", "requests"}` — and
        the requests are the byte scripts the clients already hold, so the stage
        could read them from either place and the check holds it to the clients.
        """
        link = (l.Link(clients, seed=seed) if outbox is None
                else l.Link(clients, outbox=outbox, seed=seed))
        server = {"link": link, "clients": tuple(clients),
                  "requests": {client.name: client.requests for client in clients}}
        result = s.serve_callbacks(server, budget=budget)
        return {"result": result, "stats": link.stats(), "log": link.log(),
                "conns": link.conns(), "waiting": link.waiting(),
                "inboxes": {client.name: link.connection(cid).inbox
                            for cid, client in enumerate(clients, 1)}}

    def _record(run):
        """Everything about a run that a second run of the same workload must repeat.

        The connections themselves are the world's own objects and are equal only to
        themselves, so what a run is held to is what it *said*: the result, the
        link's recomputed numbers, the log, the inboxes and the backlog.
        """
        return {"result": run["result"], "stats": run["stats"], "log": run["log"],
                "inboxes": run["inboxes"], "waiting": run["waiting"]}

    import link as l
    import stage_06 as s

    # ---- the family and the shape of a callback ---------------------------

    assert issubclass(s.ServerError, ValueError), (
        "the family is a ValueError, so a caller's `except ValueError` keeps "
        "catching a broken course: %r" % (s.ServerError.__mro__,))
    assert l.MAX_CHUNK == 64 and l.DEFAULT_OUTBOX == 8, (
        "the world carries at most 64 bytes a move and its outbox holds eight, "
        "which is what the workloads below are shaped around: %r"
        % ((l.MAX_CHUNK, l.DEFAULT_OUTBOX),))

    table = s.Handles()
    assert table.ready() == (), (
        "a fresh table has nothing to run: %r" % (table.ready(),))
    assert isinstance(table.ready(), tuple), (
        "ready is a tuple and not a view of the table's own list: %r"
        % (table.ready(),))

    one = table.register("echo", echo, "one", 1)
    two = table.register("echo", echo, "two", 2)
    assert (one, two) == (1, 2), (
        "handles are issued from one upwards, one per registration, so the "
        "order of a table is the order of its handles: %r" % ((one, two),))
    assert table.ready() == (1, 2), (
        "ready is the registration order: %r" % (table.ready(),))

    first = table.take(one)
    second = table.take(two)
    assert first == (1, "echo", echo, ("one", 1)), (
        "a callback is the 4-tuple (handle, name, fn, args), with the args as a "
        "tuple and the function itself rather than a closure: %r" % (first,))
    assert (first[1] == second[1] == "echo" and first[2] is second[2]
            and first[3] != second[3]), (
        "two callbacks that differ only in their args differ only in their "
        "args: %r vs %r" % (first, second))
    assert first[2] is echo and first[3] == ("one", 1), (
        "the function a caller registered is the function the table hands back, "
        "and its args are the ones it was given: %r" % (first,))
    assert table.take(one) is None and table.take(99) is None, (
        "a handle that was taken and a handle the table never issued both "
        "answer None: %r, %r" % (table.take(one), table.take(99)))
    assert table.ready() == (), (
        "nothing is left to run once both were taken: %r" % (table.ready(),))

    # ---- cancel, and the count it changes --------------------------------

    table = s.Handles()
    keep = table.register("keep", echo)
    drop = table.register("drop", echo)
    gone = table.register("gone", echo)
    assert table.cancel(drop) is True, (
        "the first cancel of a handle the table issued answers True: %r"
        % (table.ready(),))
    assert table.cancel(drop) is False, (
        "cancelling twice is the same as once, so the second answers False and "
        "nothing about the table changed: %r" % (table.ready(),))
    assert table.ready() == (keep, gone), (
        "a cancelled callback is not in the count, and the ones that remain keep "
        "their registration order: %r" % (table.ready(),))
    assert table.take(drop) is None, (
        "taking a cancelled callback hands back None: %r" % (table.take(drop),))
    assert table.cancel(keep) is True and table.ready() == (gone,), (
        "cancelling the first of the two that remain leaves the other: %r"
        % (table.ready(),))
    assert table.take(gone) == (gone, "gone", echo, ()), (
        "the last one is taken as any other callback is: %r"
        % (table.take(gone),))
    assert table.cancel(gone) is False, (
        "a handle that was taken is not a handle that can be cancelled: %r"
        % (table.ready(),))
    assert table.ready() == (), (
        "and the table is empty, not full of handles kept for the record: %r"
        % (table.ready(),))

    other = s.Handles()
    assert other.register("echo", echo) == 1, (
        "a second table issues its own handles from one: nothing about the "
        "table lives at module level: %r" % (other.register("moved", echo),))

    # ---- the refusals -----------------------------------------------------

    message = _refuses(s.ServerError, "register with an empty name",
                       lambda: table.register("", echo), names=("''",))
    assert "name" in message and "string" in message, (
        "the refusal says what a name has to be: %r" % (message,))
    for bad in (None, 1, b"name", ("n",)):
        _refuses(s.ServerError, "register with a name of %r" % (bad,),
                 lambda bad=bad: table.register(bad, echo), names=(repr(bad),))
    for bad in (None, "echo", 0, (echo,)):
        _refuses(s.ServerError, "register with a callback of %r" % (bad,),
                 lambda bad=bad: table.register("echo", bad), names=(repr(bad),))

    for bad in (99, 0, 7):
        _refuses(s.ServerError, "cancel of handle %r, which was never issued" % (bad,),
                 lambda bad=bad: table.cancel(bad), names=(repr(bad),))
    for bad in ("1", b"1", True, None):
        _refuses(s.ServerError, "cancel of %r, which is not a handle" % (bad,),
                 lambda bad=bad: table.cancel(bad), names=(repr(bad),))
    message = _refuses(s.ServerError, "cancel of a handle that is not an int",
                       lambda: table.cancel("1"), names=("'1'",))
    assert "int" in message, (
        "a handle that is not an int is refused as a shape rather than looked "
        "up as an unknown handle: %r" % (message,))
    for bad in ("1", True, None):
        _refuses(s.ServerError, "take of %r, which is not a handle" % (bad,),
                 lambda bad=bad: table.take(bad), names=(repr(bad),))
    _refuses(s.ServerError, "take of the 0 that is not a handle",
             lambda: table.take(0), names=("0",))
    assert table.take(4242) is None, (
        "and take of a handle the table never issued is a verdict, not a "
        "refusal: %r" % (table.take(4242),))

    # ---- the server dict and the budget -----------------------------------

    link = l.Link((l.Client("solo", (b"ping\n",)),))
    server = {"link": link, "clients": (l.Client("solo", (b"ping\n",)),)}
    for bad in (None, 0, "server", [], ()):
        _refuses(s.ServerError, "serve_callbacks of %r" % (bad,),
                 lambda bad=bad: s.serve_callbacks(bad),
                 names=(repr(bad),))
    _refuses(s.ServerError, "a server dict with no link",
             lambda: s.serve_callbacks({"clients": server["clients"]}),
             names=("'link'",))
    _refuses(s.ServerError, "a server dict with no clients",
             lambda: s.serve_callbacks({"link": link}),
             names=("'clients'", "['link']"))
    for bad in (0, None, "link"):
        _refuses(s.ServerError, "a server whose link is %r" % (bad,),
                 lambda bad=bad: s.serve_callbacks({"link": bad,
                                                    "clients": server["clients"]}),
                 names=(repr(bad),))
    for bad in ((), [], "abc", 0):
        _refuses(s.ServerError, "a server whose clients are %r" % (bad,),
                 lambda bad=bad: s.serve_callbacks({"link": link, "clients": bad}),
                 names=(repr(bad),))
    _refuses(s.ServerError, "a server with a client that is not a Client",
             lambda: s.serve_callbacks({"link": link, "clients": (0,)}),
             names=("0",))
    _refuses(s.ServerError, "a server whose second client is not a Client",
             lambda: s.serve_callbacks(
                 {"link": link,
                  "clients": (l.Client("solo", (b"ping\n",)), 0)}),
             names=("0",))
    for bad in (0, -1, True, "4", None):
        _refuses(s.ServerError, "a budget of %r" % (bad,),
                 lambda bad=bad: s.serve_callbacks(server, budget=bad),
                 names=(repr(bad),))

    # ---- one workload: three clients, a queue of callbacks, one per turn ---

    clients = (l.Client("fast", (b"ping\n",), read_every=2),
               l.Client("two", (b"hello\n", b"again\n"), read_every=2),
               l.Client("slow", (b"hi\n",), read_every=4, chunk=1))
    run = _serve(s, l, clients)
    result = run["result"]
    assert tuple(result) == ("answers", "steps", "ran", "cancelled", "skipped"), (
        "the result is the five keys, in order: %r" % (tuple(result),))
    assert tuple(result["answers"]) == ("fast", "two", "slow"), (
        "answers is keyed by every client's name, in the order they were "
        "scripted: %r" % (tuple(result["answers"]),))
    assert result["answers"] == {"fast": (b"+ping\n",),
                                 "two": (b"+hello\n", b"+again\n"),
                                 "slow": (b"+hi\n",)}, (
        "each client received its own request line back with the prefix once, "
        "and the second answer is not the first one repeated: %r"
        % (result["answers"],))
    assert result["ran"] == ("fast:1", "two:1", "slow:1", "two:2"), (
        "the callbacks ran in registration order — a callback is named for the "
        "client and the request it answers: %r" % (result["ran"],))
    assert result["cancelled"] == () and result["skipped"] == (), (
        "nobody was cancelled and nobody had gone: %r"
        % ((result["cancelled"], result["skipped"]),))
    assert result["steps"] == 17, (
        "one turn per callback plus the turns the slow client's four-byte drain "
        "takes: %r" % (result["steps"],))
    stats = run["stats"]
    assert stats["ticks"] == result["steps"] == 17, (
        "every turn gives the link exactly one tick, so the two counts agree: %r"
        % ((stats["ticks"], result["steps"]),))
    assert (stats["accepted"], stats["closes"], stats["listened"]) == (3, 3, 0), (
        "three clients accepted, three connections closed by the loop, and none "
        "handed back to the listener: %r" % (stats,))
    assert (stats["bytes_read"], stats["bytes_written"],
            stats["bytes_drained"]) == (20, 24, 24), (
        "four request lines are twenty bytes, their four replies are "
        "twenty-four, and every one of those bytes reached a client: %r"
        % (stats,))
    assert (stats["drops"], stats["bytes_dropped"]) == (0, 0), (
        "no reply was written into an outbox that had no room for it: %r"
        % (stats,))
    assert stats["drains"] == 7, (
        "the fast client drains once, the two-request client twice and the slow "
        "one byte at a time four times: %r" % (stats,))
    assert len(run["log"]) == 22 and run["log"][0]["event"] == "accept", (
        "the log's twenty-two events are the record of this run: %r"
        % ([entry["event"] for entry in run["log"]],))
    assert run["inboxes"] == {"fast": b"", "two": b"", "slow": b""}, (
        "every client drained what it was owed: %r" % (run["inboxes"],))
    assert [conn.closed for conn in run["conns"]] == [True, True, True], (
        "every connection ended closed: %r" % (run["conns"],))
    assert run["waiting"] == (), (
        "and the listener holds nobody: %r" % (run["waiting"],))

    # ---- the callback that must not run -----------------------------------

    impatient = (l.Client("alpha", (b"one\n",), patience=1),
                 l.Client("beta", (b"two\n",), patience=1),
                 l.Client("gamma", (b"three\n",), patience=1))
    run = _serve(s, l, impatient)
    result = run["result"]
    assert result["skipped"] == ("gamma:1",), (
        "the client that gave up while its answer waited its turn is skipped, "
        "and skipped by name: %r" % (result["skipped"],))
    assert result["ran"] == ("alpha:1", "beta:1"), (
        "the two callbacks whose clients were still waiting ran: %r"
        % (result["ran"],))
    assert result["answers"] == {"alpha": (b"+one\n",), "beta": (b"+two\n",),
                                 "gamma": ()}, (
        "the skipped callback never ran, so its client received nothing, while "
        "the two callbacks that differ only in their args each answered their "
        "own client's line: %r" % (result["answers"],))
    assert result["cancelled"] == (), (
        "nothing was cancelled here: %r" % (result["cancelled"],))
    assert (run["stats"]["closes"], run["stats"]["bytes_written"]) == (3, 10), (
        "three connections closed — two by the loop and one by the client's "
        "patience — and only two replies were ever written: %r"
        % (run["stats"],))
    assert run["stats"]["bytes_drained"] == 10, (
        "the bytes that reached a client are the two replies, not the three "
        "requests: %r" % (run["stats"]["bytes_drained"],))
    assert run["conns"][2].closed and run["conns"][2].cause == "patience", (
        "the third connection is the one the client dropped: %r"
        % (run["conns"][2],))
    assert result["steps"] == 3, (
        "three turns: one callback dispatched per turn, and the third turn is "
        "the one that finds the connection gone: %r" % (result["steps"],))

    starved = _serve(s, l, impatient, budget=2)["result"]
    assert (starved["skipped"], starved["cancelled"]) == (("gamma:1",), ()), (
        "a budget that ends before the turn that would have found the "
        "connection gone still reports it as skipped and not as cancelled: %r"
        % ((starved["skipped"], starved["cancelled"]),))
    assert (starved["ran"], starved["answers"]["gamma"]) == (
        ("alpha:1", "beta:1"), ()), (
        "and the leftovers of a spent budget never run: %r"
        % ((starved["ran"], starved["answers"]),))
    assert starved["steps"] == 2, (
        "the budget is a count of turns, and it was spent: %r"
        % (starved["steps"],))

    # ---- the callbacks the budget never reached ---------------------------

    patient = (l.Client("alpha", (b"one\n",)),
               l.Client("beta", (b"two\n",)),
               l.Client("gamma", (b"three\n",)))
    spent = _serve(s, l, patient, budget=1)["result"]
    assert spent["cancelled"] == ("beta:1", "gamma:1"), (
        "the callbacks the loop never reached are cancelled, in registration "
        "order, and named: %r" % (spent["cancelled"],))
    assert spent["ran"] == ("alpha:1",) and spent["skipped"] == (), (
        "one turn dispatches one callback, and nobody's connection had closed: "
        "%r" % ((spent["ran"], spent["skipped"]),))
    assert spent["answers"] == {"alpha": (b"+one\n",), "beta": (), "gamma": ()}, (
        "a cancelled callback never ran, so its client received nothing: %r"
        % (spent["answers"],))
    assert spent["steps"] == 1, (
        "and the loop took exactly the one turn the budget allowed: %r"
        % (spent["steps"],))

    whole = _serve(s, l, patient)["result"]
    assert (whole["ran"], whole["cancelled"]) == (
        ("alpha:1", "beta:1", "gamma:1"), ()), (
        "with a budget to spare the three callbacks run in registration order "
        "and nothing is cancelled: %r" % ((whole["ran"], whole["cancelled"]),))
    assert whole["answers"] == {"alpha": (b"+one\n",), "beta": (b"+two\n",),
                                "gamma": (b"+three\n",)}, (
        "and each answered its own client's line: %r" % (whole["answers"],))
    assert whole["steps"] == 4, (
        "three dispatches and the turn that closes the last connection: %r"
        % (whole["steps"],))

    # ---- a line whose halves arrive in two moves --------------------------

    long_client = (l.Client("long", (b"x" * 100 + b"\n",)),)
    run = _serve(s, l, long_client, outbox=128)
    reply = b"+" + b"x" * 100 + b"\n"
    assert run["result"]["answers"] == {"long": (reply,)}, (
        "a request of 101 bytes arrives in two moves of the link, and the "
        "callback answers with the whole line and not the fragment: %r"
        % (run["result"]["answers"],))
    assert (run["stats"]["bytes_read"], run["stats"]["bytes_written"],
            run["stats"]["bytes_drained"]) == (101, 102, 102), (
        "101 bytes in, the 102 of the prefixed line out, and all of them "
        "drained: %r" % (run["stats"],))
    assert run["stats"]["read_calls"] == 2, (
        "the world carried the request in two moves, which is what makes the "
        "buffer the stage's own business: %r" % (run["stats"],))
    assert run["result"]["steps"] == 3, (
        "and one turn assembles both halves into the line: %r"
        % (run["result"]["steps"],))

    # ---- a request that never becomes a line ------------------------------

    halfline = _serve(s, l, (l.Client("half", (b"no newline here",), read_every=2),),
                      budget=5)
    assert halfline["result"] == {"answers": {"half": ()}, "steps": 5,
                                  "ran": (), "cancelled": (), "skipped": ()}, (
        "a request with no newline in it never becomes a line, so nothing is "
        "registered, nothing runs and the budget is what ends the loop: %r"
        % (halfline["result"],))
    assert (halfline["stats"]["bytes_read"], halfline["stats"]["bytes_written"],
            halfline["stats"]["closes"]) == (15, 0, 0), (
        "the fifteen bytes were handed over and no reply was written for a line "
        "that is not a line: %r" % (halfline["stats"],))
    assert halfline["inboxes"] == {"half": b""}, (
        "and the client was owed a reply it never got: %r" % (halfline["inboxes"],))

    # ---- a client that has not arrived yet --------------------------------

    staggered = (l.Client("first", (b"one\n",)),
                 l.Client("second", (b"two\n",)),
                 l.Client("third", (b"three\n",)))
    run = _serve(s, l, staggered, seed=2)
    assert run["result"]["answers"] == {"first": (b"+one\n",),
                                        "second": (b"+two\n",),
                                        "third": (b"+three\n",)}, (
        "a client that arrives on a later tick is served when it arrives, not "
        "dropped because the loop was finished with the first: %r"
        % (run["result"]["answers"],))
    assert run["result"]["ran"] == ("first:1", "second:1", "third:1"), (
        "each of the three was answered by its own callback: %r"
        % (run["result"]["ran"],))
    assert (run["result"]["steps"], run["stats"]["closes"]) == (6, 3), (
        "six turns — two per client, since the second arrives on the second "
        "tick and the third on the fourth — and three closes: %r"
        % ((run["result"]["steps"], run["stats"]["closes"]),))
    assert run["waiting"] == () and len(run["conns"]) == 3, (
        "the loop finishes when its backlog is empty and its own connections "
        "are closed: %r" % (run["waiting"],))

    # ---- two runs of the same workload are the same run -------------------

    first = _serve(s, l, clients)
    second = _serve(s, l, clients)
    assert _record(first) == _record(second), (
        "two runs of the same workload are the same run, byte for byte, log and "
        "inboxes included: %r vs %r" % (_record(first), _record(second)))
    one_more = _serve(s, l, impatient)
    other_one = _serve(s, l, impatient)
    assert _record(one_more) == _record(other_one), (
        "and so is the run in which a client gives up under a queued callback: "
        "%r vs %r" % (_record(one_more), _record(other_one)))
    fresh = _serve(s, l, patient, budget=1)["result"]
    again = _serve(s, l, patient, budget=1)["result"]
    assert fresh == again, (
        "and the run the budget cut short is the same run twice: %r vs %r"
        % (fresh, again))

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "concurrent-servers-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "link.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    class _Coroutine:
        """A scripted coroutine: a step function that waits, answers, and counts.

        It is the check's own, and it is a step function like every other: `waits` is
        how many calls it spends answering `{"wait": True}` before it answers
        `{"value": …}`, `calls` is how many times it was called at all — the number a
        loop that resumed a finished coroutine would run away — and `visits` is the
        shared list every call appends its own name to, which is how a check reads
        the visit order out of a run without asking the loop about it.
        """

        def __init__(self, waits=0, value=b"done", name=None, visits=None):
            self.waits = waits
            self.value = value
            self.name = name
            self.visits = visits
            self.calls = 0

        def __call__(self):
            self.calls += 1
            if self.visits is not None:
                self.visits.append(self.name)
            if self.calls <= self.waits:
                return {"wait": True}
            return {"value": self.value}

    def _world(l, clients, *, seed=0, outbox=None):
        """A server bundle: one link with those clients, and the lines each one sends."""
        if outbox is None:
            link = l.Link(clients, seed=seed)
        else:
            link = l.Link(clients, seed=seed, outbox=outbox)
        return {"link": link, "clients": tuple(clients),
                "requests": {client.name: client.requests for client in clients}}

    def _serve(l, s, clients, *, script=None, budget=256, seed=0, outbox=None,
               pre=0):
        """The whole server, built from scratch and driven once: the result and the world.

        `pre` is the ticks the world is given *before* the model is handed it, which
        is how a seeded client that arrives late is made to arrive first — the world
        moves when the check says so and never on its own. The link is handed back
        with its own log and numbers, so the model's claims can be held against them.
        """
        server = _world(l, clients, seed=seed, outbox=outbox)
        if pre:
            server["link"].step(pre)
        result = s.serve_async(server, script=script, budget=budget)
        link = server["link"]
        return {"result": result, "stats": link.stats(), "log": link.log(),
                "waiting": link.waiting(),
                "conns": tuple((conn.id, conn.client.name, conn.closed, conn.cause,
                                conn.inbox) for conn in link.conns())}

    def _three(l):
        """The workload's three clients: a fast one, a two-request one and a big reply.

        The third client's request is twelve bytes, so its thirteen-byte reply is
        longer than the world's outbox and arrives in two writes: a stage that counts
        the second piece — or both pieces — as an answer is caught here and nowhere
        else.
        """
        return (l.Client("fast", (b"ping\n",), read_every=2),
                l.Client("two", (b"hello\n", b"again\n"), read_every=2),
                l.Client("big", (b"hello there\n",), read_every=3))

    def _starving(l):
        """Three clients and a budget small enough to leave work behind.

        The slow client takes one byte per tick, so a run that stops while it is
        being drained leaves a connection that is neither readable nor owed anything
        and is still not starved: that is the difference between "not served" and "a
        request the link is still holding".
        """
        return (l.Client("fast", (b"ping\n",), read_every=2),
                l.Client("slow", (b"hi\n",), read_every=1, chunk=1),
                l.Client("last", (b"last\n",)))

    def _pair(l):
        """Two clients whose answering order the script can turn around."""
        return (l.Client("a", (b"one\n",), read_every=1),
                l.Client("b", (b"two\n",), read_every=4))

    def _nonsense(s):
        """A loop whose one coroutine answers a shape no driver can read."""
        loop = s.Loop()
        loop.spawn("nonsense", lambda: {"nonsense": True})
        return loop.run(budget=2)

    import link as l
    import stage_07 as s

    # ---- the constants and the family -------------------------------------

    assert s.MAX_CHAIN == 64, (
        "a chain is driven for sixty-four steps before it reports a coroutine "
        "as still waiting, which is the bound that keeps `chain` total: %r"
        % (s.MAX_CHAIN,))
    assert s.CHAIN_STATES == ("waiting", "done"), (
        "the two states a chain ends in, in the order a coroutine meets them: %r"
        % (s.CHAIN_STATES,))
    assert issubclass(s.ServerError, ValueError), (
        "the family is a ValueError, so a caller's `except ValueError` keeps "
        "catching a broken course: %r" % (s.ServerError.__mro__,))

    # ---- a future is settled once and read in two ways --------------------

    future = s.Future()
    assert future.done() is False, (
        "a future that has not been settled is not done: %r" % (future.done(),))
    assert tuple(future.result()) == ("done", "value"), (
        "the non-raising read answers with the two keys, in that order: %r"
        % (tuple(future.result()),))
    assert future.result() == {"done": False, "value": None}, (
        "and an unsettled future's result is a report and not a raise: %r"
        % (future.result(),))
    assert future.result() is not future.result(), (
        "every dict this stage hands back is fresh: %r" % (future.result(),))
    _refuses(s.ServerError, "value() of a future that is not settled",
             future.value, names=("unsettled",))

    assert future.settle(b"") is None, (
        "settling answers nothing at all: %r" % (future.settle(b""),))
    assert future.done() is True, (
        "a future settled with b'' is done, because done() is about the "
        "settlement and not about the answer looking empty: %r" % (future.done(),))
    assert future.value() == b"" and future.result() == {"done": True,
                                                        "value": b""}, (
        "and its value is the b'' it was settled with: %r" % (future.value(),))
    _refuses(s.ServerError, "a second settle of the same future",
             lambda: future.settle(b"again"), names=("once", "b''"))

    other = s.Future()
    other.settle(None)
    assert other.done() is True, (
        "a future settled with None is done too — the value is None and the "
        "settlement is not: %r" % (other.done(),))
    assert other.value() is None and other.result() == {"done": True,
                                                       "value": None}, (
        "and its value is None, which result() reports rather than hiding: %r"
        % (other.result(),))
    _refuses(s.ServerError, "a second settle of a future holding None",
             lambda: other.settle(None), names=("once", "None"))

    payload = [b"x"]
    third = s.Future()
    third.settle(payload)
    assert third.value() is payload, (
        "a future holds the object it was settled with, not a copy of it: %r"
        % (third.value(),))

    # ---- await_ is the whole of the await keyword -------------------------

    waiting = s.await_(s.Future())
    assert tuple(waiting) == ("wait",) and waiting["wait"] is True, (
        "an unsettled future is awaited by waiting — one key, and True itself "
        "rather than something merely truthy: %r" % (waiting,))

    answered = s.await_(future)
    assert tuple(answered) == ("value",) and answered["value"] == b"", (
        "a future settled with b'' is awaited by its value, because the answer "
        "is a shape and not a truth test: %r" % (answered,))
    assert s.await_(other) == {"value": None}, (
        "and a future settled with None is a value like any other: %r"
        % (s.await_(other),))
    assert s.await_(third)["value"] is payload, (
        "await_ hands the value itself back and not a copy: %r"
        % (s.await_(third)["value"],))
    again = s.await_(future)
    assert again == answered and again is not answered, (
        "and every answer is a fresh dict: %r vs %r" % (again, answered))
    _refuses(s.ServerError, "await_ of something that is not a future",
             lambda: s.await_({}), names=("{}",))
    _refuses(s.ServerError, "await_ of None",
             lambda: s.await_(None), names=("None",))

    # ---- chain drives one coroutine to its answer -------------------------

    one = s.chain(lambda: {"value": b"one"})
    assert tuple(one) == ("state", "value", "steps"), (
        "a chain reports the state it ended in, the value and the steps it "
        "took, in that order: %r" % (tuple(one),))
    assert (one["state"], one["value"], one["steps"]) == ("done", b"one", 1), (
        "a coroutine that answers on its first call is an await on a settled "
        "future: %r" % (one,))

    waits_three = _Coroutine(waits=3, value=b"three")
    three = s.chain(waits_three)
    assert (three["state"], three["value"], three["steps"]) == ("done",
                                                                b"three", 4), (
        "a coroutine that waits three times and then answers took four steps "
        "and is done: %r" % (three,))
    assert waits_three.calls == 4, (
        "and the chain called it exactly that many times: %r"
        % (waits_three.calls,))

    edge = _Coroutine(waits=63, value=b"edge")
    at_the_bound = s.chain(edge)
    assert (at_the_bound["state"], at_the_bound["steps"]) == ("done", 64), (
        "the sixty-fourth call of a chain is still made, so a coroutine that "
        "answers on it is done: %r" % (at_the_bound,))
    stuck = _Coroutine(waits=64, value=b"never")
    over = s.chain(stuck)
    assert (over["state"], over["value"], over["steps"]) == ("waiting", None,
                                                             64), (
        "a coroutine still waiting after sixty-four steps is waiting on the "
        "world, and the chain says so instead of hanging: %r" % (over,))
    assert (stuck.calls, stuck.value) == (64, b"never"), (
        "and the sixty-fifth call was never made: %r" % (stuck.calls,))

    pending = s.Future()
    on_future = s.chain(lambda: s.await_(pending))
    assert (on_future["state"], on_future["value"], on_future["steps"]) == (
        "waiting", None, s.MAX_CHAIN), (
        "awaiting a future nobody settled is a chain that never answers, which "
        "is what a wait looks like from the outside: %r" % (on_future,))
    pending.settle(b"late")
    after = s.chain(lambda: s.await_(pending))
    assert (after["state"], after["value"], after["steps"]) == ("done",
                                                                b"late", 1), (
        "and settling it makes the same coroutine a one-step chain: %r"
        % (after,))

    for bad in (5, "x", {"wait": True}):
        _refuses(s.ServerError, "chain of %r" % (bad,), lambda bad=bad:
                 s.chain(bad), names=(repr(bad),))
    for bad in (True, "wait", {"wait": 1}, {"wait": False},
                {"wait": True, "x": 1}, {"value": 1, "wait": True}):
        _refuses(s.ServerError, "chain of a coroutine answering %r" % (bad,),
                 lambda bad=bad: s.chain(lambda bad=bad: bad),
                 names=(repr(bad),))

    # ---- the loop: spawn, run, and the four orders it keeps apart ---------

    visits = []
    first, second = _Coroutine(name="a", waits=99, visits=visits), \
        _Coroutine(name="b", waits=99, visits=visits)
    loop = s.Loop()
    handle_a = loop.spawn("a", first)
    handle_b = loop.spawn("b", second)
    assert (handle_a, handle_b) == (1, 2), (
        "the handle of a spawn is its place in the spawn order: %r"
        % ((handle_a, handle_b),))
    turn = loop.run(budget=4)
    assert tuple(turn) == ("values", "steps", "order", "done"), (
        "a run reports the values, what it cost, the completion order and "
        "whether it is done, in that order: %r" % (tuple(turn),))
    assert (turn["steps"], turn["done"], turn["values"], turn["order"]) == (
        4, False, {}, ()), (
        "a round-robin turn is one coroutine called once, four waits are four "
        "steps, and a wait is not a value: %r" % (turn,))
    assert visits == ["a", "b", "a", "b"], (
        "the default order is round-robin from the spawn order, from the "
        "beginning of the cycle every time: %r" % (visits,))
    assert (first.calls, second.calls) == (2, 2), (
        "and every coroutine had its two turns: %r" % ((first.calls,
                                                        second.calls),))

    visits = []
    first, second = _Coroutine(name="a", waits=99, visits=visits), \
        _Coroutine(name="b", waits=99, visits=visits)
    loop = s.Loop(script=("b", "a"))
    loop.spawn("a", first)
    loop.spawn("b", second)
    assert loop.run(budget=4)["steps"] == 4 and visits == ["b", "a", "b", "a"], (
        "a script is the visit order, cycled: %r" % (visits,))

    slow, quick = _Coroutine(name="slow", waits=3, value=b"S"), \
        _Coroutine(name="quick", waits=1, value=b"Q")
    loop = s.Loop()
    loop.spawn("slow", slow)
    loop.spawn("quick", quick)
    done = loop.run(budget=8)
    assert (done["order"], tuple(done["values"]), done["steps"]) == (
        ("quick", "slow"), ("quick", "slow"), 6), (
        "the completion order is the order the coroutines *answered*, and the "
        "values are keyed in that same order and not in the spawn order: %r"
        % (done,))
    assert done["values"] == {"quick": b"Q", "slow": b"S"}, (
        "each name is keyed to the value its coroutine answered: %r"
        % (done["values"],))
    assert (slow.calls, quick.calls) == (4, 2), (
        "four turns for the coroutine that waited three times and two for the "
        "one that waited once: %r" % ((slow.calls, quick.calls),))
    finished = loop.run(budget=8)
    assert (finished["steps"], slow.calls, quick.calls) == (0, 4, 2), (
        "and a loop with nothing left to run spends nothing and calls nobody: "
        "%r" % (finished,))
    assert finished["order"] == ("quick", "slow") and finished["done"] is True, (
        "the completion order and the verdict survive the next run: %r"
        % (finished,))
    assert finished["values"] == done["values"] \
        and finished["values"] is not done["values"], (
        "and the values dict is a fresh one every run: %r vs %r"
        % (finished["values"], done["values"]))

    visits = []
    quick, slow = _Coroutine(name="quick", waits=1, value=b"Q"), \
        _Coroutine(name="slow", waits=1, value=b"S")
    loop = s.Loop(script=("slow", "quick"))
    loop.spawn("quick", quick)
    loop.spawn("slow", slow)
    assert loop.run(budget=4)["order"] == ("slow", "quick"), (
        "and the script decides which of two equally quick coroutines is "
        "answered first, whatever the spawn order says")

    once, never = _Coroutine(name="once", value=b"only", visits=visits), \
        _Coroutine(name="never", waits=99)
    loop = s.Loop()
    loop.spawn("once", once)
    loop.spawn("never", never)
    ran = loop.run(budget=10)
    assert (once.calls, never.calls, ran["done"]) == (1, 9, False), (
        "a coroutine that answered is never called again, and the loop is not "
        "done until the one that is still waiting answers: %r"
        % ((once.calls, never.calls, ran["done"]),))
    assert ran["order"] == ("once",) and ran["values"] == {"once": b"only"}, (
        "the finished coroutine is the whole of the completion order: %r"
        % (ran,))

    loop = s.Loop()
    stolen = loop.run(budget=4)["values"]
    stolen["ghost"] = b"no"
    assert loop.run(budget=4)["values"] == {}, (
        "the values dict is the caller's and not the loop's: %r"
        % (loop.run(budget=4)["values"],))

    assert s.Loop().run(budget=4) == {"values": {}, "steps": 0, "order": (),
                                      "done": True}, (
        "a loop with nothing spawned is done before it starts")

    for bad in ("", 5, None):
        _refuses(s.ServerError, "spawn with the name %r" % (bad,),
                 lambda bad=bad: s.Loop().spawn(bad, lambda: {"wait": True}),
                 names=(repr(bad),))
    for bad in (5, "x", None):
        _refuses(s.ServerError, "spawn of %r" % (bad,),
                 lambda bad=bad: s.Loop().spawn("name", bad),
                 names=(repr(bad),))
    named = s.Loop()
    named.spawn("same", lambda: {"value": b"x"})
    _refuses(s.ServerError, "a second spawn of the same name",
             lambda: named.spawn("same", lambda: {"value": b"y"}),
             names=("same",))
    for bad in (0, -1, True, "4", None):
        _refuses(s.ServerError, "run with a budget of %r" % (bad,),
                 lambda bad=bad: s.Loop().run(budget=bad), names=(repr(bad),))
    for bad in (5, b"ab", "ab", {"a": 1}):
        _refuses(s.ServerError, "a loop with the script %r" % (bad,),
                 lambda bad=bad: s.Loop(bad), names=(repr(bad),))
    assert s.Loop(None).run(budget=1) == s.Loop().run(budget=1), (
        "while None is no script at all, which is the round-robin default")
    for bad in (1, "", None, b"x"):
        _refuses(s.ServerError, "a script naming %r" % (bad,),
                 lambda bad=bad: s.Loop((bad,)), names=(repr(bad),))
    ghost = s.Loop(script=("nope",))
    ghost.spawn("here", lambda: {"value": b"x"})
    _refuses(s.ServerError, "a script naming a coroutine that was never spawned",
             lambda: ghost.run(budget=2), names=("nope",))
    _refuses(s.ServerError, "a coroutine that answers something else",
             lambda: _nonsense(s), names=("nonsense",))

    # ---- the server, driven by the loop -----------------------------------

    whole = _serve(l, s, _three(l), budget=256)
    result, stats = whole["result"], whole["stats"]
    assert tuple(result) == ("answers", "steps", "ticks", "served", "starved",
                             "order", "values"), (
        "the model reports the answers, its steps, the link's ticks, the "
        "completion order, the starved clients, the answering order and the "
        "values, in that order: %r" % (tuple(result),))
    assert tuple(result["answers"]) == ("fast", "two", "big"), (
        "the answers are keyed by every client the run accepted, in accept "
        "order: %r" % (tuple(result["answers"]),))
    assert result["answers"] == {"fast": (b"+ping\n",),
                                 "two": (b"+hello\n", b"+again\n"),
                                 "big": (b"+hello there\n",)}, (
        "every reply is its request line with the prefix in front of it, once, "
        "and the split reply is one answer and not two: %r"
        % (result["answers"],))
    assert result["served"] == ("fast", "big", "two"), (
        "the completion order is completion order — the two-request client "
        "finishes last though it was answered first — and not the spawn order: %r"
        % (result["served"],))
    assert result["starved"] == (), (
        "a run that finished has no client whose request the link is still "
        "holding: %r" % (result["starved"],))
    assert result["order"] == ("fast", "two", "big", "two"), (
        "the answering order has one entry per reply that went out, so the "
        "two-request client is in it twice: %r" % (result["order"],))
    assert result["order"] != result["served"], (
        "and the answering order is not the completion order — that is the "
        "whole reason both are reported: %r vs %r"
        % (result["order"], result["served"]))
    assert result["values"] == (b"+ping\n", b"+hello there\n", b"+again\n"), (
        "the values are the answers in completion order, and the two-request "
        "client's is the reply it finished on and not the one it started with: "
        "%r" % (result["values"],))
    assert result["values"] == tuple(result["answers"][name][-1]
                                     for name in result["served"]), (
        "which is exactly the last reply of each completed client: %r"
        % (result["values"],))
    assert (result["steps"], result["ticks"]) == (15, 15), (
        "the driver costs one step per turn and the world one tick per turn, "
        "and it stops the moment the answers have been drained: %r"
        % ((result["steps"], result["ticks"]),))
    assert result["ticks"] == stats["ticks"], (
        "the ticks are the link's own clock and not a count of the model's: %r"
        % (result["ticks"],))
    written = sum(len(reply) for replies in result["answers"].values()
                  for reply in replies)
    assert written == stats["bytes_written"] == stats["bytes_drained"] == 33, (
        "every byte the model wrote reached a client, and the link's own log "
        "says so: %r vs %r" % (written, stats))
    assert (stats["accepted"], stats["closes"], stats["drops"]) == (3, 3, 0), (
        "three connections accepted, three closed, nothing queued that the "
        "outbox could not take: %r" % (stats,))

    # ---- a budget spent with work left is a result, not an exception ------

    short = _serve(l, s, _starving(l), budget=8)
    left = short["result"]
    assert (left["steps"], left["ticks"]) == (8, 8), (
        "a budget is in steps, and eight steps is eight turns of the world: %r"
        % ((left["steps"], left["ticks"]),))
    assert left["served"] == () and left["values"] == () and left["order"] == (
        "fast", "slow"), (
        "answers that went out with no client finished are an answering order "
        "and no completion order at all: %r" % (left,))
    assert left["starved"] == ("last",), (
        "only the client whose request the link is still holding is starved; "
        "the two being drained are not, because the link holds *answers* for "
        "them: %r" % (left["starved"],))
    assert left["answers"] == {"fast": (b"+ping\n",), "slow": (b"+hi\n",),
                              "last": ()}, (
        "the two clients whose reply went out have an answer and the third has "
        "none, which is not the same as being finished: %r" % (left["answers"],))
    draining = tuple(conn[4] for conn in short["conns"])
    assert draining == (b"", b"hi\n", b""), (
        "the world's own record is the evidence for that: the slow client is "
        "still holding b'hi\\n' it has not taken, which is an answer and not a "
        "request: %r" % (draining,))
    assert not any(conn[2] for conn in short["conns"]), (
        "and no connection was closed either, so 'not served' and 'starved' are "
        "not the same set: %r" % (short["conns"],))

    tiny = _serve(l, s, _starving(l), budget=1)["result"]
    assert (tiny["steps"], tiny["served"], tiny["starved"], tiny["order"]) == (
        1, (), ("fast", "slow", "last"), ()), (
        "one step is one accepted connection and nothing else, so every "
        "request the link holds is starved and nothing has been answered: %r"
        % (tiny,))
    assert tiny["answers"] == {"fast": (), "slow": (), "last": ()}, (
        "and the answers name every accepted client even when it has none: %r"
        % (tiny["answers"],))

    # ---- the sentence the script is, and the client that dropped ----------

    plain = _serve(l, s, _pair(l), budget=64)["result"]
    turned = _serve(l, s, _pair(l), script=("b", "a"), budget=64)["result"]
    assert plain["order"] == ("a", "b") and turned["order"] == ("b", "a"), (
        "the script is the visit order the check chose, and the answering "
        "order follows it: %r vs %r" % (plain["order"], turned["order"]))
    assert plain["answers"] == turned["answers"] == {"a": (b"+one\n",),
                                                     "b": (b"+two\n",)}, (
        "and the same clients get the same answers either way: %r vs %r"
        % (plain["answers"], turned["answers"]))
    assert plain["served"] == turned["served"] == ("a", "b"), (
        "the completion order is what the readers' patience costs, not the "
        "order the loop chose: %r vs %r" % (plain["served"], turned["served"]))

    left_out = _serve(l, s, _pair(l), script=("b",), budget=8)["result"]
    assert left_out["served"] == ("b",) and left_out["starved"] == ("a",), (
        "a client the script never names is never visited, and its request is "
        "the link's to hold: %r" % (left_out,))
    assert left_out["answers"]["a"] == () and left_out["order"] == ("b",), (
        "so it is served nothing and answers nothing: %r"
        % (left_out["answers"],))

    dropped = _serve(l, s, (l.Client("gone", (b"ping\n",), patience=1),
                            l.Client("ok", (b"hi\n",))), budget=64)
    assert dropped["result"]["answers"] == {"gone": (), "ok": (b"+hi\n",)}, (
        "a client that dropped the link before its reply went out is served "
        "nothing: %r" % (dropped["result"]["answers"],))
    assert dropped["result"]["served"] == ("gone", "ok"), (
        "and it is still *finished* — the model closed a connection whose "
        "client walked away — so it is in the completion order: %r"
        % (dropped["result"]["served"],))
    assert dropped["result"]["values"] == (b"", b"+hi\n"), (
        "with no answer to report, which is b'' and not the other client's "
        "reply: %r" % (dropped["result"]["values"],))
    assert dropped["result"]["starved"] == (), (
        "a connection the client dropped is not a request the link is holding: "
        "%r" % (dropped["result"]["starved"],))
    causes = tuple(sorted(conn[3] for conn in dropped["conns"]))
    assert causes == ("patience", "server") and dropped["stats"]["closes"] == 2, (
        "the world's own record says one connection ended because the client's "
        "patience ran out: %r" % (causes,))

    # ---- the world may have moved before the model got it -----------------

    arrived = _serve(l, s, (l.Client("now", (b"one\n",)),
                            l.Client("late", (b"two\n",))), seed=2, pre=2,
                     budget=64)
    assert arrived["result"]["served"] == ("now", "late"), (
        "a client that arrived before the model was handed the world is served "
        "like any other: %r" % (arrived["result"]["served"],))
    assert arrived["result"]["ticks"] == arrived["result"]["steps"] + 2, (
        "and the two ticks the check spent are the link's, not the model's: %r"
        % (arrived["result"],))

    unarrived = _serve(l, s, (l.Client("now", (b"one\n",)),
                              l.Client("late", (b"two\n",))), seed=2, budget=8)
    assert unarrived["result"]["served"] == ("now",), (
        "a client that has not arrived when the model accepts is a client the "
        "model never held, so it is not served: %r"
        % (unarrived["result"]["served"],))
    assert unarrived["result"]["answers"] == {"now": (b"+one\n",)}, (
        "and it is not even in the answers, because the model reports the "
        "connections it accepted: %r" % (unarrived["result"]["answers"],))
    assert unarrived["result"]["starved"] == (), (
        "nor starved — a request the model never took is not a request it owes "
        "an answer to: %r" % (unarrived["result"]["starved"],))
    assert unarrived["waiting"] == (2,) and unarrived["result"]["steps"] == 8, (
        "the world still holds it on the backlog, and the run ends on the "
        "budget because a client nobody accepted never finishes: %r"
        % (unarrived,))

    # ---- the bundle is refused when it is not one -------------------------

    good = _world(l, (l.Client("solo", (b"ping\n",)),))
    for bad in (None, [], "server"):
        _refuses(s.ServerError, "serve_async of %r" % (bad,),
                 lambda bad=bad: s.serve_async(bad), names=(repr(bad),))
    _refuses(s.ServerError, "a server with no link",
             lambda: s.serve_async({"clients": good["clients"],
                                    "requests": good["requests"]}),
             names=("'link'",))
    _refuses(s.ServerError, "a server whose link is not one",
             lambda: s.serve_async({"link": "no", "clients": good["clients"],
                                    "requests": good["requests"]}),
             names=("'no'",))
    _refuses(s.ServerError, "a server with no clients",
             lambda: s.serve_async({"link": good["link"], "clients": (),
                                    "requests": {}}), names=("clients",))
    _refuses(s.ServerError, "a server whose client is not one",
             lambda: s.serve_async({"link": good["link"], "clients": ("solo",),
                                    "requests": good["requests"]}),
             names=("'solo'",))
    _refuses(s.ServerError, "a server whose requests are not a mapping",
             lambda: s.serve_async({"link": good["link"],
                                    "clients": good["clients"],
                                    "requests": []}), names=("requests",))
    _refuses(s.ServerError, "a server whose requests are not the clients' script",
             lambda: s.serve_async({"link": good["link"],
                                    "clients": good["clients"],
                                    "requests": {"solo": (b"other\n",)}}),
             names=("'solo'", "b'other\\n'"))
    for bad in (0, -1, True, "4", None):
        _refuses(s.ServerError, "serve_async with a budget of %r" % (bad,),
                 lambda bad=bad: s.serve_async(good, budget=bad),
                 names=(repr(bad),))

    # ---- the same workload twice ------------------------------------------

    first = _serve(l, s, _three(l), budget=256)
    second = _serve(l, s, _three(l), budget=256)
    assert first == second, (
        "two runs of the same workload are the same run, byte for byte, log "
        "and ticks included: %r vs %r" % (first, second))
    assert first["log"] == second["log"] and len(first["log"]) == 21, (
        "the link's own log is the record the second run repeats: %r"
        % (len(first["log"]),))
    third = _serve(l, s, _starving(l), budget=8)
    fourth = _serve(l, s, _starving(l), budget=8)
    assert third == fourth, (
        "and so is a budgeted run that leaves work behind: %r vs %r"
        % (third, fourth))
    assert third["result"]["starved"] == ("last",), (
        "the starved client is the same client in both runs: %r"
        % (third["result"]["starved"],))

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "concurrent-servers-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "link.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _cast(l):
        """The check's three clients: a quick one, one with two requests, a slow one."""
        return (l.Client("fast", (b"ping\n",), read_every=2),
                l.Client("two", (b"hello\n", b"again\n"), read_every=2),
                l.Client("slow", (b"hi\n",), read_every=4, chunk=1))

    def _server(l, clients, **kw):
        """The dict every model is handed: the link, its clients, and their lines."""
        return {"link": l.Link(clients, **kw), "clients": tuple(clients),
                "requests": {client.name: client.requests for client in clients}}

    def _run(s, l, clients, *, budget=64, **kw):
        """One backpressure run over a fresh link, and the world it left behind."""
        server = _server(l, clients, **kw)
        return s.serve_backpressure(server, budget=budget), server["link"]

    def _state(conn, phase="writing", buffer=b"", pending=b"", offset=0):
        """The connection's state, in the shape every caller of `send` hands over."""
        return {"conn": conn, "phase": phase, "buffer": buffer, "pending": pending,
                "offset": offset}

    def _pair(l, *, read_every=4, patience=16):
        """A slow reader at the head of the write path, and a quick client behind it."""
        return (l.Client("slow", (b"slow-one\n",), read_every=read_every, chunk=1),
                l.Client("quick", (b"ok\n",), read_every=1, patience=patience))

    import link as l
    import stage_01 as one
    import stage_08 as s

    # ---- the family, the world, and this stage's own default --------------

    assert issubclass(s.ServerError, ValueError), (
        "the family is a ValueError, so a caller's `except ValueError` keeps "
        "catching a broken course: %r" % (s.ServerError.__mro__,))
    assert l.MAX_CHUNK == 64 and l.DEFAULT_OUTBOX == 8, (
        "the world carries at most 64 bytes a move and its default outbox holds "
        "eight, which is smaller than the replies this check writes: %r, %r"
        % (l.MAX_CHUNK, l.DEFAULT_OUTBOX))
    assert s.DEFAULT_BUDGET == 256, (
        "a run takes the contract's 256 turns unless it is told otherwise: %r"
        % (s.DEFAULT_BUDGET,))

    # ---- send: one move of one reply, and what the world took -------------

    link = l.Link((l.Client("one", (b"PING\n",)),), outbox=4)
    link.step()
    conn = link.accept()
    reply = b"+PING\n"
    move = s.send(link, _state(conn), reply)
    assert tuple(move) == ("state", "sent", "deferred", "drained"), (
        "a send answers with the state, the bytes sent, the bytes deferred and "
        "whether the whole reply is out, in that order: %r" % (tuple(move),))
    assert tuple(move["state"]) == ("conn", "phase", "buffer", "pending", "offset"), (
        "the state is the connection, its phase, its read buffer, the reply in "
        "flight and the offset, in that order: %r" % (tuple(move["state"]),))
    assert (move["sent"], move["deferred"], move["drained"]) == (4, 2, False), (
        "an outbox of four takes four of this reply's six bytes and the state "
        "keeps the other two: %r" % (move,))
    assert move["state"]["pending"] == reply and move["state"]["offset"] == 4, (
        "the reply in flight is the whole reply and the offset is what the world "
        "took of it, not what is left of it: %r" % (move["state"],))
    assert move["state"]["phase"] == "writing", (
        "a reply that is still owed leaves the connection in the writing phase: "
        "%r" % (move["state"],))
    assert link.stats()["drops"] == 0 and link.stats()["write_calls"] == 1, (
        "the world was offered a reply it could take part of, which is a write "
        "and not a drop: %r" % (link.stats(),))
    _refuses(s.ServerError, "send handing the whole reply over a second time",
             lambda: s.send(link, move["state"], reply), names=("b'+PING\\n'",))
    full = s.send(link, move["state"], b"G\n")
    assert (full["sent"], full["deferred"], full["drained"]) == (0, 2, False), (
        "a full outbox takes nothing and the send says so instead of raising: %r"
        % (full,))
    assert link.stats()["drops"] == 0 and link.stats()["write_calls"] == 1, (
        "and the world was not offered the tail it has no room for: %r"
        % (link.stats(),))
    link.step(1)
    last = s.send(link, full["state"], b"G\n")
    assert (last["sent"], last["deferred"], last["drained"]) == (2, 0, True), (
        "a tick carries the outbox to the client and the tail follows on the next "
        "turn: %r" % (last,))
    assert last["state"]["pending"] == b"" and last["state"]["offset"] == 0, (
        "a reply that is out leaves nothing pending and nothing owed: %r"
        % (last["state"],))
    assert last["state"]["phase"] == "reading", (
        "and the connection is reading again, which is what stage 1's phases are "
        "for: %r" % (last["state"],))
    assert link.stats()["bytes_written"] == 6 and conn.inbox == b"", (
        "six bytes reached the outbox in three moves and the client took the four "
        "that arrived: %r, %r" % (link.stats(), conn.inbox))
    assert conn.outbox == b"G\n", (
        "with the reply's last two bytes still on their way: %r" % (conn.outbox,))
    boundary = s.send(link, _state(conn, pending=reply, offset=len(reply)), b"")
    assert (boundary["sent"], boundary["deferred"], boundary["drained"]) == (0, 0, True), (
        "a state whose offset is the reply's own length owes nothing, writes "
        "nothing and answers so: %r" % (boundary,))
    assert link.stats()["drops"] == 0, (
        "an empty tail is not offered to the world either: %r" % (link.stats(),))

    # ---- send: the verdicts that are not exceptions -----------------------

    dropped = l.Link((l.Client("gone", (b"hi\n",), patience=1),))
    dropped.step(1)
    gone = dropped.accept()
    dropped.read(gone)
    dropped.step(2)
    assert gone.closed and gone.cause == "patience", (
        "the client that stopped waiting dropped its own connection: %r, %r"
        % (gone.closed, gone.cause))
    stalled = s.send(dropped, _state(gone, pending=b"+hi\n", offset=1), b"hi\n")
    assert (stalled["sent"], stalled["deferred"], stalled["drained"]) == (0, 3, False), (
        "a connection the world has closed takes nothing, keeps what it was "
        "owed, and answers instead of raising: %r" % (stalled,))
    assert dropped.stats()["drops"] == 0, (
        "and the closed connection was not written to at all: %r"
        % (dropped.stats(),))

    # ---- send: every way of handing it something it cannot use ------------

    _refuses(s.ServerError, "send through something that is not the link",
             lambda: s.send("the link", _state(conn), b"+hi\n"),
             names=("'the link'",))
    _refuses(s.ServerError, "send with a state that is not a mapping",
             lambda: s.send(link, "the state", b"+hi\n"), names=("'the state'",))
    _refuses(s.ServerError, "send with a bare connection where the state belongs",
             lambda: s.send(link, conn, b"+hi\n"), names=("Connection",))
    _refuses(s.ServerError, "send with no connection at all",
             lambda: s.send(link, {"phase": "writing", "buffer": b"",
                                   "pending": b"", "offset": 0}, b"+hi\n"),
             names=("None",))
    _refuses(s.ServerError, "send with a connection of another link",
             lambda: s.send(link, _state(l.Link((l.Client("mine", (b"hi\n",)),))
                                         .connection(1)), b"+hi\n"), names=("1",))
    _refuses(s.ServerError, "send in a phase stage 1 never made",
             lambda: s.send(link, _state(conn, phase="paused"), b"+hi\n"),
             names=("'paused'", "'new'", "'closed'"))
    _refuses(s.ServerError, "send in the reading phase, with no reply staged",
             lambda: s.send(link, _state(conn, phase="reading"), b"+hi\n"),
             names=("reading",))
    _refuses(s.ServerError, "send with a read buffer that is not bytes",
             lambda: s.send(link, _state(conn, buffer="hi"), b"+hi\n"),
             names=("'hi'",))
    _refuses(s.ServerError, "send with a pending reply that is not bytes",
             lambda: s.send(link, _state(conn, pending="+hi\\n"), b"+hi\n"),
             names=("'+hi\\\\n'",))
    _refuses(s.ServerError, "send with an offset that is not a byte count",
             lambda: s.send(link, _state(conn, pending=b"+hi\n", offset="one"),
                            b"+hi\n"), names=("'one'",))
    _refuses(s.ServerError, "send with an offset of True, which is an int if you squint",
             lambda: s.send(link, _state(conn, pending=b"+hi\n", offset=True),
                            b"+hi\n"), names=("True",))
    _refuses(s.ServerError, "send with an offset before the start of the reply",
             lambda: s.send(link, _state(conn, pending=b"", offset=-1), b"+hi\n"),
             names=("-1",))
    _refuses(s.ServerError, "send with an offset past the end of the reply",
             lambda: s.send(link, _state(conn, pending=b"+hi\n", offset=9), b""),
             names=("9",))
    _refuses(s.ServerError, "send of something that is not bytes",
             lambda: s.send(link, _state(conn), "+hi\\n"), names=("'+hi\\\\n'",))
    _refuses(s.ServerError, "a fresh reply that is not one line",
             lambda: s.send(link, _state(conn), b"+hi"), names=("b'+hi'",))
    _refuses(s.ServerError, "a fresh reply of nothing at all",
             lambda: s.send(link, _state(conn), b""), names=("b''",))
    assert one.REPLY_PREFIX == "+" and one.STATES[0] == "new", (
        "this stage speaks stage 1's protocol and stage 1's phases: %r, %r"
        % (one.REPLY_PREFIX, one.STATES))

    # ---- one workload: the answers, the turns, and the world's own count ---

    clients = _cast(l)
    result, world = _run(s, l, clients, budget=64)
    assert tuple(result) == ("answers", "steps", "ticks", "deferred", "stalled"), (
        "the result is five keys, and `deferred` and `stalled` are the two this "
        "model adds: %r" % (tuple(result),))
    assert tuple(result["answers"]) == ("fast", "two", "slow"), (
        "the answers are every client's, in the order the server was handed "
        "them: %r" % (tuple(result["answers"]),))
    assert result["answers"] == {"fast": (b"+ping\n",),
                                 "two": (b"+hello\n", b"+again\n"),
                                 "slow": (b"+hi\n",)}, (
        "every client's answers are the request lines with the one-byte prefix in "
        "front of them, in the order they were written, and the two-request "
        "client's second answer is not its first: %r" % (result["answers"],))
    assert result["deferred"] == () and result["stalled"] == (), (
        "every reply fits the eight-byte outbox, so nothing had to be deferred "
        "and nothing was ever stuck: %r, %r"
        % (result["deferred"], result["stalled"]))
    assert (result["steps"], result["ticks"]) == (20, 20), (
        "this workload costs twenty turns, each of them one tick of the link: %r, "
        "%r" % (result["steps"], result["ticks"]))
    numbers = world.stats()
    assert result["ticks"] == numbers["ticks"] and world.now() == 20, (
        "a turn moves the link once, so the model's ticks and the world's clock "
        "are the same number: %r, %r" % (result["ticks"], numbers))
    assert numbers["accepted"] == 3 and numbers["closes"] == 3, (
        "three clients were accepted and three connections were closed: %r"
        % (numbers,))
    assert numbers["bytes_read"] == 20 and numbers["bytes_written"] == 24, (
        "the four request lines are twenty bytes in and their answers twenty-four "
        "out: %r" % (numbers,))
    written = sum(len(line) for lines in result["answers"].values()
                  for line in lines)
    assert written == numbers["bytes_written"] == numbers["bytes_drained"], (
        "the answers the result reports, the bytes the link carried into the "
        "outboxes and the bytes the clients drained are one number: %r, %r, %r"
        % (written, numbers["bytes_written"], numbers["bytes_drained"]))
    assert numbers["drops"] == 0 and numbers["listened"] == 0, (
        "nothing was offered to an outbox with no room, and the listener was not "
        "used: %r" % (numbers,))
    assert numbers["bytes_drained"] == 24 and world.done(), (
        "and the run ends where a blocking one does: every client drained every "
        "answer it was owed: %r" % (numbers,))

    # ---- the spine: the same answers as the reactor, at a different cost ---

    import stage_04 as reactor

    reacting = reactor.serve_reactor(_server(l, clients), budget=64)
    assert reacting["answers"] == result["answers"], (
        "one workload through two models answers every client byte for byte the "
        "same — %r against %r" % (reacting["answers"], result["answers"]))
    assert result["steps"] > reacting["steps"], (
        "and this model's serialised write path costs more turns than the "
        "reactor's, because a reply waits for the client ahead of it: %r against "
        "%r" % (result["steps"], reacting["steps"]))

    # ---- the deferred reply: an outbox of one byte, and the reply whole ----

    tiny, tiny_world = _run(s, l, clients, budget=64, outbox=1)
    assert tiny["answers"] == result["answers"], (
        "an outbox of one byte changes when the answers are written and not what "
        "they are: %r" % (tiny["answers"],))
    assert tiny["deferred"] == ("fast", "two", "slow"), (
        "every one of these replies is bigger than the outbox, so every one of "
        "them had to be handed over more than once: %r" % (tiny["deferred"],))
    assert tiny["stalled"] == (), (
        "and not one of them stuck: %r, with %r ticks" % (tiny["stalled"],
                                                          tiny["ticks"]))
    tiny_numbers = tiny_world.stats()
    assert tiny_numbers["write_calls"] == 24 and tiny_numbers["drops"] == 0, (
        "twenty-four writes carry the twenty-four answer bytes, one byte each, "
        "and the link drops nothing: %r" % (tiny_numbers,))
    assert [entry["byte_count"] for entry in tiny_world.events("write")] == [1] * 24, (
        "every write the link logged carried exactly the outbox's own bound of "
        "one byte, so no reply was ever counted as sent before the world took "
        "it: %r" % (tiny_world.events("write"),))
    assert tiny_numbers["bytes_written"] == 24 and tiny_numbers["bytes_drained"] == 24, (
        "and the same twenty-four bytes reached the clients: %r" % (tiny_numbers,))
    assert tiny_world.outbox_limit == 1, (
        "the server never widened the world's outbox to fit a reply: %r"
        % (tiny_world.outbox_limit,))

    # ---- by bytes, not by length: the reply arrives whole -----------------

    lonely = (l.Client("only", (b"hello\n",), read_every=64),)
    whole, whole_world = _run(s, l, lonely, budget=10, outbox=1)
    conn = whole_world.conns()[0]
    assert whole["answers"] == {"only": (b"+hello\n",)}, (
        "the reply's last byte reached the outbox on the seventh turn, so this is "
        "the answer the server wrote: %r" % (whole["answers"],))
    assert conn.inbox + conn.outbox == b"+hello\n", (
        "and the client that has not read for sixty-four ticks holds the whole "
        "reply, byte for byte, in its inbox and the outbox behind it: %r"
        % (conn.inbox + conn.outbox,))
    assert (whole["deferred"], whole["stalled"]) == (("only",), ()), (
        "a reply written one byte a turn is deferred and is not stuck: %r, %r"
        % (whole["deferred"], whole["stalled"]))
    whole_numbers = whole_world.stats()
    assert whole_numbers["bytes_written"] == 7 and whole_numbers["drains"] == 0, (
        "seven bytes were written, one per turn, and the slow reader has taken "
        "none of them yet: %r" % (whole_numbers,))
    assert whole["steps"] == 10 and whole_numbers["bytes_drained"] == 0, (
        "the budget stopped the run with the reply written and not yet taken: %r, "
        "%r" % (whole["steps"], whole_numbers))

    # ---- a request that takes two reads: the line is assembled, not swapped -

    long = (l.Client("long", (b"x" * 70 + b"\n",), read_every=1),)
    lined, lined_world = _run(s, l, long, budget=64)
    assert lined["answers"] == {"long": (b"+" + b"x" * 70 + b"\n",)}, (
        "a request of seventy-one bytes arrives in two reads — the world carries "
        "at most sixty-four a move — and the reply is built from the whole line "
        "and not from its last chunk: %r" % (lined["answers"],))
    assert lined["deferred"] == ("long",) and lined["stalled"] == (), (
        "the reply is seventy-two bytes, so it took several turns to write, and "
        "every one of them moved: %r, %r" % (lined["deferred"], lined["stalled"]))
    lined_numbers = lined_world.stats()
    assert lined_numbers["read_calls"] == 2 and lined_numbers["bytes_read"] == 71, (
        "the request took exactly two read moves and every byte of it was taken: "
        "%r" % (lined_numbers,))
    assert lined_numbers["bytes_written"] == 72 == lined_numbers["bytes_drained"], (
        "and all seventy-two answer bytes were written and reached the client: %r"
        % (lined_numbers,))
    assert (lined["steps"], lined["ticks"]) == (10, 10), (
        "ten turns, each of them one tick of the link: %r, %r"
        % (lined["steps"], lined["ticks"]))

    # ---- head-of-line blocking: the slow reader, and the one behind it -----

    held, held_world = _run(s, l, _pair(l), budget=256, outbox=1)
    assert held["stalled"] == ("quick",), (
        "the slow reader at the head of the write path holds it for the whole "
        "run, and the quick client waiting behind it never gets its turn: %r"
        % (held["stalled"],))
    assert held["answers"] == {"slow": (b"+slow-one\n",), "quick": ()}, (
        "the head's answer went out and the quick client's never reached the "
        "outbox at all: %r" % (held["answers"],))
    assert held["deferred"] == ("slow",), (
        "the head's reply is the one that had to be handed over in pieces, and "
        "`deferred` is not `stalled`: %r" % (held["deferred"],))
    held_numbers = held_world.stats()
    assert held_numbers["bytes_written"] == 10 == held_numbers["bytes_drained"], (
        "only the head's ten answer bytes were ever written, and only those "
        "reached a client: %r" % (held_numbers,))
    behind = held_world.conns()[1]
    assert behind.closed and behind.cause == "patience", (
        "the quick client's own patience is what ended its connection while its "
        "reply waited behind somebody else's: %r, %r"
        % (behind.closed, behind.cause))
    assert behind.inbox + behind.outbox == b"", (
        "and not one byte of its answer ever reached it: %r"
        % (behind.inbox + behind.outbox,))

    same, same_world = _run(s, l, _pair(l, read_every=1), budget=256, outbox=1)
    assert same["stalled"] == (), (
        "the same workload with the head reading every tick stalls nobody, so it "
        "is the slow reader and not the workload that `stalled` is measuring: %r"
        % (same["stalled"],))
    assert same["answers"] == {"slow": (b"+slow-one\n",), "quick": (b"+ok\n",)}, (
        "with the head out of its way the quick client behind it got its reply: "
        "%r" % (same["answers"],))
    assert same_world.stats()["bytes_drained"] == 14, (
        "both replies, fourteen bytes, reached the clients that were owed them: "
        "%r" % (same_world.stats(),))

    # ---- a dead head is stepped over, not a wall ---------------------------

    blocked = (l.Client("slow", (b"slow-one\n",), read_every=4, chunk=1),
               l.Client("doomed", (b"bye\n",), read_every=1, patience=3),
               l.Client("late", (b"late\n",), read_every=1))
    dead, dead_world = _run(s, l, blocked, budget=64)
    assert dead["answers"] == {"slow": (b"+slow-one\n",), "doomed": (),
                               "late": (b"+late\n",)}, (
        "the client whose patience runs out while its reply waits behind the "
        "head is answered nothing, and the client queued behind it is answered "
        "once the head is out of the way: %r" % (dead["answers"],))
    assert dead["stalled"] == ("doomed",) and dead["deferred"] == ("slow",), (
        "the reply that never moved is the stalled one, and the head's reply is "
        "the deferred one: %r, %r" % (dead["stalled"], dead["deferred"]))
    doomed = dead_world.conns()[1]
    assert doomed.closed and doomed.cause == "patience", (
        "the world closed that connection because its client stopped waiting, "
        "which is not a close this server asked for: %r, %r"
        % (doomed.closed, doomed.cause))
    assert doomed.inbox + doomed.outbox == b"", (
        "and not one byte of the reply it was owed ever reached it: %r"
        % (doomed.inbox + doomed.outbox,))
    dead_numbers = dead_world.stats()
    assert dead_numbers["bytes_written"] == 16 == dead_numbers["bytes_drained"], (
        "the head's ten answer bytes and the late client's six were written and "
        "taken, and the doomed reply's five never were: %r" % (dead_numbers,))
    assert (dead["steps"], dead["ticks"]) == (42, 42), (
        "the slow reader holds the head for forty turns, draining one byte every "
        "fourth tick, and the run ends when both live clients have their "
        "answers: %r, %r" % (dead["steps"], dead["ticks"]))

    # ---- the budget: a spent budget is an outcome, not an exception --------

    none, none_world = _run(s, l, clients, budget=0)
    assert (none["steps"], none["ticks"]) == (0, 0), (
        "a budget of no turns takes no turn: %r, %r"
        % (none["steps"], none["ticks"]))
    assert none["answers"] == {"fast": (), "two": (), "slow": ()}, (
        "and answers nobody, so every client's answers are the empty tuple: %r"
        % (none["answers"],))
    assert none["deferred"] == () and none["stalled"] == (), (
        "no reply was staged, so none was deferred and none is stuck: %r, %r"
        % (none["deferred"], none["stalled"]))
    assert none_world.stats()["events"] == 0, (
        "a run that took no turn touched nothing, not even the listener: %r"
        % (none_world.stats(),))

    half, half_world = _run(s, l, clients, budget=4, outbox=1)
    assert (half["steps"], half["ticks"]) == (4, 4), (
        "four turns of one tick each, budget in turns and not in ticks: %r, %r"
        % (half["steps"], half["ticks"]))
    assert half["answers"] == {"fast": (), "two": (), "slow": ()}, (
        "the head's reply is four bytes of its six when the budget runs out, and "
        "that is not an answer the world carried: %r" % (half["answers"],))
    assert half["deferred"] == ("fast",) and half["stalled"] == ("two", "slow"), (
        "the head moved and is therefore not stalled; the two replies queued "
        "behind it never moved at all: %r, %r"
        % (half["deferred"], half["stalled"]))
    assert half_world.stats()["bytes_written"] == 4, (
        "four bytes written, one per turn, and nothing else: %r"
        % (half_world.stats(),))

    # ---- a client that has not arrived yet is waited for -------------------

    seeded = (l.Client("early", (b"first\n",), read_every=1),
              l.Client("later", (b"second\n",), read_every=1))
    waited, waited_world = _run(s, l, seeded, budget=64, seed=8)
    assert waited["answers"] == {"early": (b"+first\n",), "later": (b"+second\n",)}, (
        "the second client becomes readable at tick eight, and the run waits for "
        "it instead of ending when the first one is closed: %r"
        % (waited["answers"],))
    assert waited_world.stats()["accepted"] == 2, (
        "the listener held the second client all the while and both were "
        "admitted: %r" % (waited_world.stats(),))
    assert (waited["steps"], waited["ticks"]) == (9, 9), (
        "nine turns: one for the first client, the seven the run spends waiting "
        "with nobody left, and one for the client that arrived: %r, %r"
        % (waited["steps"], waited["ticks"]))

    # ---- refusals: the server a run will not take -------------------------

    _refuses(s.ServerError, "serve_backpressure on something that is not a server",
             lambda: s.serve_backpressure(("a", "link")), names=("'a'",))
    _refuses(s.ServerError, "serve_backpressure with no link at all",
             lambda: s.serve_backpressure({"clients": clients}), names=("None",))
    _refuses(s.ServerError, "serve_backpressure with a link that is not the world",
             lambda: s.serve_backpressure({"link": "the link", "clients": clients}),
             names=("'the link'",))
    _refuses(s.ServerError, "serve_backpressure with no clients at all",
             lambda: s.serve_backpressure({"link": l.Link(clients)}), names=("None",))
    _refuses(s.ServerError, "serve_backpressure with clients that are not a sequence",
             lambda: s.serve_backpressure({"link": l.Link(clients),
                                           "clients": "fast"}), names=("'fast'",))
    _refuses(s.ServerError, "serve_backpressure with an empty list of clients",
             lambda: s.serve_backpressure({"link": l.Link(clients), "clients": []}),
             names=("[]",))
    _refuses(s.ServerError, "serve_backpressure with a client that is not a Client",
             lambda: s.serve_backpressure({"link": l.Link(clients),
                                           "clients": ("fast",)}), names=("'fast'",))
    _refuses(s.ServerError, "a budget of one turn too few",
             lambda: s.serve_backpressure(_server(l, clients), budget=-1),
             names=("-1",))
    _refuses(s.ServerError, "a budget of True, which is an int if you squint",
             lambda: s.serve_backpressure(_server(l, clients), budget=True),
             names=("True",))
    _refuses(s.ServerError, "a budget that is not a number at all",
             lambda: s.serve_backpressure(_server(l, clients), budget="many"),
             names=("'many'",))

    # ---- the whole workload, twice, equals and together -------------------

    other, other_world = _run(s, l, clients, budget=64)
    assert other == result, (
        "two runs of the same workload are the same run, byte for byte: %r vs %r"
        % (other, result))
    assert other_world.log() == world.log(), (
        "and the same events in the same order, which is what makes a step count "
        "worth reporting: %r vs %r" % (other_world.log(), world.log()))
    assert other_world.stats() == numbers == world.stats(), (
        "and the same numbers, recomputed from each run's own log: %r vs %r"
        % (other_world.stats(), world.stats()))
    assert other_world.done(), (
        "the run settles where a blocking one does: every answer drained and "
        "every connection closed: %r" % (other_world.stats(),))

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "concurrent-servers-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "link.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _conn(now=0, queries=0):
        """The two things `execute` asks a connection's state for: a tick, a count."""
        return {"now": now, "queries": queries}

    def _cast(l):
        """The check's three command clients, against one store.

        `fast` asks twice, a request at a time; `pair` pipelines two commands into one
        write, which is the read that must be two answers; and `slow` reads one byte
        per drain and `INCR`s the key `fast` set, so three clients have to agree about
        what the server holds.
        """
        return (l.Client("fast", (b"SET one 1\n", b"GET one\n"), read_every=2),
                l.Client("pair", (b"SET two 2\nGET two\n",), read_every=2),
                l.Client("slow", (b"INCR one\n",), read_every=4, chunk=1))

    def _server(l, clients, **kw):
        """The dict every model is handed: the link, its clients, and their lines."""
        return {"link": l.Link(clients, **kw), "clients": tuple(clients),
                "requests": {client.name: client.requests for client in clients}}

    def _run(s, l, clients, *, budget=64, **kw):
        """One command loop over a fresh link, and the world it left behind."""
        server = _server(l, clients, **kw)
        return s.serve_commands(server, budget=budget), server["link"]

    def _solo(s, l, lines, *, budget=64, **kw):
        """One client's lines through the loop, and the world it left behind."""
        return _run(s, l, (l.Client("solo", lines, read_every=1),), budget=budget, **kw)

    import link as l
    import stage_09 as s

    # ---- the family, the command table and the world's numbers -------------

    assert issubclass(s.ServerError, ValueError), (
        "the family is a ValueError, so a caller's `except ValueError` keeps "
        "catching a broken course: %r" % (s.ServerError.__mro__,))
    assert s.COMMANDS == ("SET", "GET", "DEL", "INCR", "EXPIRE", "KEYS", "QUIT"), (
        "the server speaks Redis's seven commands and no others, in that order: "
        "%r" % (s.COMMANDS,))
    assert l.MAX_CHUNK == 64 and l.DEFAULT_OUTBOX == 8, (
        "the world carries sixty-four bytes a move and an outbox holds eight, "
        "which is smaller than one bulk string's reply: %r, %r"
        % (l.MAX_CHUNK, l.DEFAULT_OUTBOX))

    # ---- parse: the shape of a line, and only a whole one ------------------

    assert s.parse(b"SET one 1\n") == ("SET", (b"one", b"1")), (
        "a whole line parses into its command and its arguments as bytes: %r"
        % (s.parse(b"SET one 1\n"),))
    assert s.parse(b"get one\n") == ("GET", (b"one",)), (
        "the command is upper-cased once here, so `get` is `GET`: %r"
        % (s.parse(b"get one\n"),))
    assert s.parse(b"SET\ttwo\r\n") == ("SET", (b"two",)), (
        "a `\\r` before the newline comes off and runs of whitespace collapse: %r"
        % (s.parse(b"SET\ttwo\r\n"),))
    assert s.parse(b"  SET   one   1  \n") == ("SET", (b"one", b"1")), (
        "and whitespace around the tokens is not an argument: %r"
        % (s.parse(b"  SET   one   1  \n"),))
    assert s.parse(b"KEYS\n") == ("KEYS", ()), (
        "a command with no arguments parses into an empty tuple of them: %r"
        % (s.parse(b"KEYS\n"),))
    assert s.parse(b"\n") == ("", ()), (
        "a blank line names no command — the empty command, which the command "
        "layer answers as one it does not know, is not an exception: %r"
        % (s.parse(b"\n"),))
    assert s.parse(b"SET v a b\n")[1] == (b"v", b"a", b"b"), (
        "arguments are kept exactly as the client wrote them, spaces and all: %r"
        % (s.parse(b"SET v a b\n"),))
    _refuses(s.ServerError, "parse of a line that is not bytes",
             lambda: s.parse("SET one 1\n"), names=("'SET one 1",))
    _refuses(s.ServerError, "parse of a bite of a line, with no newline",
             lambda: s.parse(b"SET one 1"), names=("b'SET one 1'",))
    _refuses(s.ServerError, "parse of a command token that is not ascii",
             lambda: s.parse(b"\xff\xfe a\n"), names=("\\xff",))

    # ---- execute: every reply shape, byte for byte -------------------------

    store = {}
    conn = _conn()
    assert s.execute(store, "SET", (b"a", b"1"), conn=conn) == b"+OK\r\n", (
        "`SET` is the simplest reply the protocol has: %r"
        % (s.execute(store, "SET", (b"a", b"1"), conn=conn),))
    assert store == {b"a": (b"1", None)}, (
        "and the store remembers the client's bytes, with no deadline: %r"
        % (store,))
    assert s.execute(store, "GET", (b"a",), conn=conn) == b"$1\r\n1\r\n", (
        "`GET` answers a bulk string: its length, its bytes, its terminator: %r"
        % (s.execute(store, "GET", (b"a",), conn=conn),))
    assert s.execute(store, "GET", [b"missing"], conn=conn) == b"$-1\r\n", (
        "a miss is the null bulk, and a caller may hand the arguments over as a "
        "list: %r" % (s.execute(store, "GET", [b"missing"], conn=conn),))
    assert s.execute(store, "DEL", (b"a",), conn=conn) == b":1\r\n", (
        "`DEL` answers the count it deleted: %r"
        % (s.execute(store, "DEL", (b"a",), conn=conn),))
    assert store == {} and s.execute(store, "DEL", (b"a",), conn=conn) == b":0\r\n", (
        "the key is gone and a second `DEL` counts nothing: %r, %r"
        % (store, s.execute(store, "DEL", (b"a",), conn=conn)))
    assert s.execute(store, "INCR", (b"n",), conn=conn) == b":1\r\n", (
        "`INCR` of a key that is not there is one: %r"
        % (s.execute(store, "INCR", (b"n",), conn=conn),))
    assert s.execute(store, "INCR", (b"n",), conn=conn) == b":2\r\n", (
        "and the second is two, which the store now holds: %r, %r"
        % (s.execute(store, "INCR", (b"n",), conn=conn), store))
    assert s.execute(store, "SET", (b"n", b"x"), conn=conn) == b"+OK\r\n", (
        "`SET` takes a value that is not a number: %r"
        % (s.execute(store, "SET", (b"n", b"x"), conn=conn),))
    assert (s.execute(store, "INCR", (b"n",), conn=conn)
            == b"-ERR value is not an integer or out of range\r\n"), (
        "`INCR` of a value that is not an integer is the error line, not `+OK` "
        "and not an exception: %r"
        % (s.execute(store, "INCR", (b"n",), conn=conn),))
    assert store == {b"n": (b"x", None)}, (
        "and the value it refused is left exactly as it was: %r" % (store,))
    assert s.execute(store, "SET", (b"n", b"1_0"), conn=conn) == b"+OK\r\n", (
        "the stage still stores whatever bytes a client sets: %r"
        % (s.execute(store, "SET", (b"n", b"1_0"), conn=conn),))
    assert (s.execute(store, "INCR", (b"n",), conn=conn)
            == b"-ERR value is not an integer or out of range\r\n"), (
        "`1_0` is not an integer, whatever `int()` would say about it: %r"
        % (s.execute(store, "INCR", (b"n",), conn=conn),))
    assert s.execute(store, "SET", (b"n", b"+5"), conn=conn) == b"+OK\r\n", (
        "nor is `+5`, which is a value `GET` reads back as bytes: %r"
        % (s.execute(store, "SET", (b"n", b"+5"), conn=conn),))
    assert (s.execute(store, "INCR", (b"n",), conn=conn)
            == b"-ERR value is not an integer or out of range\r\n"), (
        "and `INCR` refuses it too: %r"
        % (s.execute(store, "INCR", (b"n",), conn=conn),))
    keys = _conn()
    s.execute(store, "SET", (b"zed", b"1"), conn=keys)
    s.execute(store, "SET", (b"one", b"1"), conn=keys)
    s.execute(store, "SET", (b"mid", b"1"), conn=keys)
    assert s.execute(store, "KEYS", (), conn=keys) == b"$13\r\nmid n one zed\r\n", (
        "`KEYS` is one bulk holding the live keys in byte order, one space "
        "between them, and the store's own keys are the ones it holds: %r"
        % (s.execute(store, "KEYS", (), conn=keys),))
    empty = {}
    assert s.execute(empty, "KEYS", (), conn=_conn()) == b"$0\r\n\r\n", (
        "and a store with no live key is an empty bulk, not an empty tuple and "
        "not an exception: %r" % (s.execute(empty, "KEYS", (), conn=_conn()),))
    quit_conn = _conn()
    assert s.execute({}, "QUIT", (), conn=quit_conn) == b"+BYE\r\n", (
        "`QUIT` is answered like any other command: %r"
        % (s.execute({}, "QUIT", (), conn=quit_conn),))
    assert quit_conn["quit"] is True, (
        "and it raises this connection's own quit flag: %r" % (quit_conn,))
    assert s.execute({}, "FOO", (), conn=_conn()) == (
        b"-ERR unknown command 'FOO'\r\n"), (
        "an unknown command is the error line, never an exception: %r"
        % (s.execute({}, "FOO", (), conn=_conn()),))
    assert s.execute({}, "GET", (), conn=_conn()) == (
        b"-ERR wrong number of arguments for 'get' command\r\n"), (
        "a command with too few arguments is the error line, and it names the "
        "command in lower case: %r" % (s.execute({}, "GET", (), conn=_conn()),))
    assert s.execute({}, "KEYS", (b"one",), conn=_conn()) == (
        b"-ERR wrong number of arguments for 'keys' command\r\n"), (
        "so is one with too many, `KEYS` included: %r"
        % (s.execute({}, "KEYS", (b"one",), conn=_conn()),))
    assert s.execute({}, "QUIT", (b"now",), conn=_conn()) == (
        b"-ERR wrong number of arguments for 'quit' command\r\n"), (
        "and `QUIT` is not a command that takes an argument: %r"
        % (s.execute({}, "QUIT", (b"now",), conn=_conn()),))

    # ---- execute: expiry is a deadline on the injected clock ---------------

    aged = {}
    at0 = _conn(0)
    assert s.execute(aged, "EXPIRE", (b"k", b"2"), conn=at0) == b":0\r\n", (
        "there is nothing to arm, so `EXPIRE` counts nothing: %r"
        % (s.execute(aged, "EXPIRE", (b"k", b"2"), conn=at0),))
    s.execute(aged, "SET", (b"k", b"v"), conn=at0)
    assert s.execute(aged, "EXPIRE", (b"k", b"2"), conn=at0) == b":1\r\n", (
        "`EXPIRE` on a live key arms one deadline: %r"
        % (s.execute(aged, "EXPIRE", (b"k", b"2"), conn=at0),))
    assert aged == {b"k": (b"v", 2)}, (
        "and the deadline is a tick of the injected clock, `now + ticks`: %r"
        % (aged,))
    assert s.execute(aged, "GET", (b"k",), conn=_conn(1)) == b"$1\r\nv\r\n", (
        "one tick before the deadline the key is still there: %r"
        % (s.execute(aged, "GET", (b"k",), conn=_conn(1)),))
    assert s.execute(aged, "GET", (b"k",), conn=_conn(2)) == b"$-1\r\n", (
        "on the deadline's own tick it is a miss, not a hit: %r"
        % (s.execute(aged, "GET", (b"k",), conn=_conn(2)),))
    assert aged == {}, (
        "and the miss is *forgotten*, not merely hidden: %r" % (aged,))
    s.execute(aged, "SET", (b"k", b"v"), conn=at0)
    s.execute(aged, "EXPIRE", (b"k", b"9"), conn=at0)
    assert s.execute(aged, "GET", (b"k",), conn=_conn(8)) == b"$1\r\nv\r\n", (
        "a longer deadline keeps the key alive on the tick before it: %r"
        % (s.execute(aged, "GET", (b"k",), conn=_conn(8)),))
    assert s.execute(aged, "KEYS", (), conn=_conn(9)) == b"$0\r\n\r\n", (
        "and `KEYS` sweeps what the clock has reached rather than counting it: %r"
        % (s.execute(aged, "KEYS", (), conn=_conn(9)),))
    assert aged == {}, (
        "the sweep forgets the key for real: %r" % (aged,))
    s.execute(aged, "SET", (b"k", b"v"), conn=at0)
    s.execute(aged, "EXPIRE", (b"k", b"4"), conn=at0)
    assert s.execute(aged, "DEL", (b"k",), conn=_conn(9)) == b":0\r\n", (
        "an expired key is nothing for `DEL` to delete: %r"
        % (s.execute(aged, "DEL", (b"k",), conn=_conn(9)),))
    assert s.execute(aged, "SET", (b"k", b"v"), conn=at0) == b"+OK\r\n", (
        "a fresh `SET` is a fresh key: %r"
        % (s.execute(aged, "SET", (b"k", b"v"), conn=at0),))
    assert s.execute(aged, "EXPIRE", (b"k", b"4"), conn=at0) == b":1\r\n", (
        "so it can be armed again: %r"
        % (s.execute(aged, "EXPIRE", (b"k", b"4"), conn=at0),))
    assert s.execute(aged, "EXPIRE", (b"k", b"4"), conn=_conn(9)) == b":0\r\n", (
        "and there is nothing left to arm once the clock has passed it: %r"
        % (s.execute(aged, "EXPIRE", (b"k", b"4"), conn=_conn(9)),))
    assert s.execute(aged, "SET", (b"k", b"v"), conn=at0) == b"+OK\r\n", (
        "a `SET` over an armed key is still a `SET`: %r"
        % (s.execute(aged, "SET", (b"k", b"v"), conn=at0),))
    assert s.execute(aged, "EXPIRE", (b"k", b"9"), conn=at0) == b":1\r\n", (
        "which can be armed: %r" % (s.execute(aged, "EXPIRE", (b"k", b"9"), conn=at0),))
    assert s.execute(aged, "SET", (b"k", b"v2"), conn=at0) == b"+OK\r\n", (
        "and setting the key again clears the deadline with the old value: %r"
        % (s.execute(aged, "SET", (b"k", b"v2"), conn=at0),))
    assert aged == {b"k": (b"v2", None)}, (
        "a fresh value is a fresh key: %r" % (aged,))
    assert s.execute(aged, "SET", (b"n", b"1"), conn=at0) == b"+OK\r\n", (
        "the same store holds a counter: %r"
        % (s.execute(aged, "SET", (b"n", b"1"), conn=at0),))
    s.execute(aged, "EXPIRE", (b"n", b"9"), conn=at0)
    assert s.execute(aged, "INCR", (b"n",), conn=at0) == b":2\r\n", (
        "`INCR` counts it: %r" % (s.execute(aged, "INCR", (b"n",), conn=at0),))
    assert aged[b"n"] == (b"2", 9), (
        "and the value changed while the key, and its deadline, did not: %r"
        % (aged,))
    assert (s.execute(aged, "EXPIRE", (b"n", b"soon"), conn=at0)
            == b"-ERR value is not an integer or out of range\r\n"), (
        "a deadline that is not a number of ticks is refused the way a value that "
        "is not a number is: %r"
        % (s.execute(aged, "EXPIRE", (b"n", b"soon"), conn=at0),))
    assert aged[b"n"] == (b"2", 9), (
        "and the deadline it refused did not move: %r" % (aged,))

    # ---- execute: the connection's own query count -------------------------

    counted = _conn()
    assert counted["queries"] == 0, (
        "a connection starts having asked nothing: %r" % (counted,))
    s.execute({}, "SET", (b"c", b"1"), conn=counted)
    s.execute({}, "FOO", (), conn=counted)
    s.execute({}, "GET", (), conn=counted)
    assert counted["queries"] == 3, (
        "a command moves the count whether it was run, unknown or refused — a "
        "query is a query: %r" % (counted,))

    # ---- every shape this module refuses, naming the offender --------------

    _refuses(s.ServerError, "execute against something that is not the store",
             lambda: s.execute("the store", "GET", (b"a",), conn=_conn()),
             names=("'the store'",))
    _refuses(s.ServerError, "execute of something that is not a command name",
             lambda: s.execute({}, 9, (), conn=_conn()), names=("9",))
    _refuses(s.ServerError, "execute with arguments that are not a sequence",
             lambda: s.execute({}, "GET", "one", conn=_conn()), names=("'one'",))
    _refuses(s.ServerError, "execute with an argument that is not bytes",
             lambda: s.execute({}, "GET", ("one",), conn=_conn()), names=("'one'",))
    _refuses(s.ServerError, "execute against something that is not a connection",
             lambda: s.execute({}, "GET", (b"a",), conn=("now", 0)),
             names=("('now', 0)",))
    _refuses(s.ServerError, "execute against a state with no tick in it",
             lambda: s.execute({}, "GET", (b"a",), conn={"queries": 0}),
             names=("'now'",))
    _refuses(s.ServerError, "execute against a state whose tick is not a number",
             lambda: s.execute({}, "GET", (b"a",), conn={"now": "1", "queries": 0}),
             names=("'now'", "'1'"))
    _refuses(s.ServerError, "execute against a state that never counted a query",
             lambda: s.execute({}, "GET", (b"a",), conn={"now": 0, "queries": -1}),
             names=("'queries'", "-1"))
    _refuses(s.ServerError, "execute against a state whose count is a bool",
             lambda: s.execute({}, "GET", (b"a",), conn={"now": 0, "queries": True}),
             names=("'queries'", "True"))

    clients = _cast(l)
    _refuses(s.ServerError, "serve_commands on something that is not a server",
             lambda: s.serve_commands(("a", "link")), names=("('a', 'link')",))
    _refuses(s.ServerError, "serve_commands with no link in the bundle",
             lambda: s.serve_commands({"clients": clients, "requests": {}}),
             names=("'link'",))
    _refuses(s.ServerError, "serve_commands with no requests in the bundle",
             lambda: s.serve_commands({"link": l.Link(clients), "clients": clients}),
             names=("'requests'",))
    _refuses(s.ServerError, "serve_commands with a link that is not the world",
             lambda: s.serve_commands({"link": "the link", "clients": clients,
                                       "requests": {}}), names=("'the link'",))
    _refuses(s.ServerError, "serve_commands with clients that are not a sequence",
             lambda: s.serve_commands({"link": l.Link(clients), "clients": "fast",
                                       "requests": {}}), names=("'fast'",))
    _refuses(s.ServerError, "serve_commands with an empty list of clients",
             lambda: s.serve_commands({"link": l.Link(clients), "clients": [],
                                       "requests": {}}), names=("[]",))
    _refuses(s.ServerError, "serve_commands with a client that is not a Client",
             lambda: s.serve_commands({"link": l.Link(clients),
                                       "clients": ("fast",), "requests": {}}),
             names=("'fast'",))
    _refuses(s.ServerError, "serve_commands with requests that are not a mapping",
             lambda: s.serve_commands({"link": l.Link(clients), "clients": clients,
                                       "requests": []}), names=("[]",))
    _refuses(s.ServerError, "serve_commands with a request script that is not the "
             "client's own",
             lambda: s.serve_commands({"link": l.Link(clients), "clients": clients,
                                       "requests": {"fast": (b"hi\n",)}}),
             names=("'fast'",))
    _refuses(s.ServerError, "a budget of one turn too few",
             lambda: s.serve_commands(_server(l, clients), budget=-1),
             names=("-1",))
    _refuses(s.ServerError, "a budget of True, which is an int if you squint",
             lambda: s.serve_commands(_server(l, clients), budget=True),
             names=("True",))
    _refuses(s.ServerError, "a budget that is not a number at all",
             lambda: s.serve_commands(_server(l, clients), budget="many"),
             names=("'many'",))

    # ---- the whole workload, and everything the result owes the world ------

    result, world = _run(s, l, clients, budget=64)
    assert tuple(result) == ("answers", "steps", "ticks", "store", "connections"), (
        "the result's five keys, in the order the contract names them: %r"
        % (tuple(result),))
    assert tuple(result["answers"]) == ("fast", "pair", "slow"), (
        "the answers are every client's, in the order the server was handed them: "
        "%r" % (tuple(result["answers"]),))
    assert result["answers"] == {"fast": (b"+OK\r\n", b"$1\r\n2\r\n"),
                                 "pair": (b"+OK\r\n", b"$1\r\n2\r\n"),
                                 "slow": (b":2\r\n",)}, (
        "every client's answers are the reply lines it was written, byte for byte "
        "and in order — and the pair's one write is two answers: %r"
        % (result["answers"],))
    assert result["steps"] == 17 and result["ticks"] == 17, (
        "seventeen turns of one tick each end this workload: steps %r, ticks %r"
        % (result["steps"], result["ticks"]))
    assert result["ticks"] == world.now() == result["steps"], (
        "a turn steps the link once and only once, so the turns, the ticks and the "
        "link's own reading are the same number: %r, %r, %r"
        % (result["ticks"], world.now(), result["steps"]))
    assert result["store"] == {b"one": (b"2", None), b"two": (b"2", None)}, (
        "one store for the whole run: `fast` set `one`, `slow` incremented it to "
        "two, `pair` set `two` — and no key has a deadline: %r" % (result["store"],))
    assert tuple(result["connections"]) == ("fast", "pair", "slow"), (
        "a connection report per connection, in the order they were accepted: %r"
        % (tuple(result["connections"]),))
    assert tuple(result["connections"]["fast"]) == ("state", "queries", "quit",
                                                    "buffer"), (
        "and each report's four keys, in order: state, queries, quit, buffer: %r"
        % (tuple(result["connections"]["fast"]),))
    assert result["connections"] == {
        "fast": {"state": "closed", "queries": 2, "quit": False, "buffer": b""},
        "pair": {"state": "closed", "queries": 2, "quit": False, "buffer": b""},
        "slow": {"state": "closed", "queries": 1, "quit": False, "buffer": b""}}, (
        "every connection asked its own number of queries against the one store, "
        "nobody quit, nothing is left buffered, and every connection ended "
        "closed: %r" % (result["connections"],))
    numbers = world.stats()
    assert numbers["accepted"] == 3 and numbers["closes"] == 3, (
        "three clients were accepted and three connections closed: %r" % (numbers,))
    assert numbers["read_calls"] == 5 and numbers["write_calls"] == 5, (
        "five turns read a command and five wrote an answer, because each of the "
        "five commands took one move each way: %r" % (numbers,))
    assert numbers["bytes_read"] == 45 and numbers["bytes_written"] == 28, (
        "the five command lines are forty-five bytes in and their four replies "
        "twenty-eight out: %r" % (numbers,))
    assert numbers["bytes_drained"] == 28 and numbers["drops"] == 0, (
        "and every reply byte reached the client it was written for, because the "
        "run did not stop early: %r" % (numbers,))
    answered = sum(len(line) for lines in result["answers"].values()
                   for line in lines)
    assert answered == numbers["bytes_drained"], (
        "the answers the loop reports are exactly the bytes the link carried into "
        "the clients' inboxes — %r bytes of answers against %r drained"
        % (answered, numbers["bytes_drained"]))
    assert numbers["listened"] == 0, (
        "the command loop asks the link who is ready instead of putting a "
        "connection back in the listener's queue: %r" % (numbers,))
    assert world.done(), (
        "every client drained every answer it was owed, which is how this model "
        "ends: %r" % (world.stats(),))

    # ---- one store, two connections, two buffers ---------------------------

    big = b"SET big " + b"y" * 200 + b"\n"
    twins = (l.Client("long", (big,), read_every=1),
             l.Client("quick", (b"SET two 2\nGET two\n",), read_every=1))
    mid, mid_world = _run(s, l, twins, budget=2)
    assert mid["connections"]["long"]["buffer"] == big[:128], (
        "two turns of one move carry two chunks of sixty-four bytes of the long "
        "command, and the connection keeps them: %r"
        % (mid["connections"]["long"]["buffer"],))
    assert mid["connections"]["long"]["queries"] == 0, (
        "half a command is not a command, so nothing of it has been executed: %r"
        % (mid["connections"]["long"],))
    assert mid["connections"]["quick"]["buffer"] == b"", (
        "the other connection's own buffer is untouched by those bytes: %r"
        % (mid["connections"]["quick"],))
    assert mid["connections"]["quick"]["queries"] == 2, (
        "and its two pipelined commands are both executed, two turns into the "
        "run: %r" % (mid["connections"]["quick"],))
    assert mid["store"] == {b"two": (b"2", None)}, (
        "the two connections share one store, and only the finished command is in "
        "it: %r" % (mid["store"],))
    assert mid["answers"] == {"long": (), "quick": (b"+OK\r\n",)}, (
        "and the answers are each connection's own: %r" % (mid["answers"],))
    done, done_world = _run(s, l, twins, budget=64)
    assert done["answers"]["long"] == (b"+OK\r\n",), (
        "when the long command's line is complete it is executed exactly once — "
        "one answer, not two and not none: %r" % (done["answers"]["long"],))
    assert done["connections"]["long"]["queries"] == 1, (
        "and the connection counted exactly one query for it: %r"
        % (done["connections"]["long"],))
    assert done["store"][b"big"] == (b"y" * 200, None), (
        "with the value the client wrote, whole and in one piece: %r"
        % (done["store"][b"big"],))
    assert done["connections"]["quick"]["queries"] == 2, (
        "and the other connection's own count is still its own: %r"
        % (done["connections"]["quick"],))
    assert (done["steps"], done["ticks"]) == (6, 6), (
        "six turns carry the long command, answer both connections and close both "
        "of them: steps %r, ticks %r" % (done["steps"], done["ticks"]))
    assert done_world.stats()["bytes_drained"] == 17 and done_world.done(), (
        "every answer byte reached its client and the world settled: %r"
        % (done_world.stats(),))
    assert mid_world.stats()["bytes_drained"] == 5, (
        "the answer the short budget had staged was still carried to the client "
        "that budget wrote it for: %r" % (mid_world.stats(),))

    # ---- a tail is kept, never parsed --------------------------------------

    cut, cut_world = _solo(s, l, (b"SET a 1",))
    assert cut["connections"]["solo"]["buffer"] == b"SET a 1", (
        "a line with no newline is the tail of a command and it is kept exactly as "
        "it was read: %r" % (cut["connections"]["solo"],))
    assert cut["connections"]["solo"]["queries"] == 0, (
        "and it is never parsed, because it is not a line yet: %r"
        % (cut["connections"]["solo"],))
    assert cut["answers"] == {"solo": ()} and cut["store"] == {}, (
        "so a command the client never finished a line of was never run: %r, %r"
        % (cut["answers"], cut["store"]))
    assert cut["connections"]["solo"]["state"] == "closed", (
        "and the connection ends closed rather than waiting forever for a byte "
        "that is not coming: %r" % (cut["connections"]["solo"],))
    assert cut_world.stats()["closes"] == 1 and cut_world.done(), (
        "one connection, closed once: %r" % (cut_world.stats(),))
    tail, _ = _solo(s, l, (b"SET a 1\nGET a",))
    assert tail["answers"] == {"solo": (b"+OK\r\n",)}, (
        "a whole line followed by a tail executes the whole line and only it: %r"
        % (tail["answers"],))
    assert tail["store"] == {b"a": (b"1", None)}, (
        "the store holds what the line that was complete asked for: %r"
        % (tail["store"],))
    assert tail["connections"]["solo"]["buffer"] == b"GET a", (
        "and the tail is still there, unparsed, at the end: %r"
        % (tail["connections"]["solo"],))
    stuck, stuck_world = _solo(s, l, (b"SET a 1", b"GET a\n"), budget=6)
    assert stuck["connections"]["solo"]["buffer"] == b"SET a 1", (
        "a client that stops in the middle of a command and still has one to send "
        "keeps the run waiting for the byte that would finish the line: %r"
        % (stuck["connections"]["solo"],))
    assert stuck["connections"]["solo"]["queries"] == 0 and stuck["store"] == {}, (
        "and neither a command nor a key exists out of a line that is not whole: "
        "%r, %r" % (stuck["connections"]["solo"], stuck["store"]))
    assert (stuck["steps"], stuck["ticks"]) == (6, 6), (
        "the run is not over, so the budget is what ends it: steps %r, ticks %r"
        % (stuck["steps"], stuck["ticks"]))
    assert stuck["connections"]["solo"]["state"] == "reading", (
        "and the connection is still reading, not closed and not finished: %r"
        % (stuck["connections"]["solo"],))
    assert stuck_world.stats()["closes"] == 0 and stuck_world.stats()["bytes_read"] == 7, (
        "seven bytes read from a client that is still on the line: %r"
        % (stuck_world.stats(),))

    # ---- a turn reads before it writes -------------------------------------

    pipelined = b"SET a 1\nSET b " + b"q" * 60 + b"\n"
    early, _ = _solo(s, l, (pipelined,), budget=2)
    assert early["store"] == {b"a": (b"1", None), b"b": (b"q" * 60, None)}, (
        "two turns carry seventy-five bytes in two moves and execute both of the "
        "lines they complete, in order: %r" % (early["store"],))
    assert early["answers"] == {"solo": ()}, (
        "and neither answer is written before the client's bytes have been read: a "
        "turn reads what the client sent before it writes what it owes: %r"
        % (early["answers"],))
    assert early["connections"]["solo"]["state"] == "writing", (
        "the connection has both answers queued and the turns are what is left: %r"
        % (early["connections"]["solo"],))

    # ---- a pipelined read is two commands; QUIT drops the rest -------------

    piped, _ = _solo(s, l, (b"SET a 1\nINCR a\nGET a\n",))
    assert piped["answers"]["solo"] == (b"+OK\r\n", b":2\r\n", b"$1\r\n2\r\n"), (
        "three commands in one write are three answers, in the order they were "
        "written, against the store as each one left it: %r"
        % (piped["answers"],))
    assert piped["connections"]["solo"]["queries"] == 3, (
        "and three queries: %r" % (piped["connections"]["solo"],))
    bye, bye_world = _solo(s, l, (b"QUIT\n",))
    assert bye["answers"] == {"solo": (b"+BYE\r\n",)}, (
        "`QUIT` is answered with `+BYE`: %r" % (bye["answers"],))
    assert bye["connections"]["solo"]["quit"] is True, (
        "and the connection's own flag says it asked to quit: %r"
        % (bye["connections"]["solo"],))
    assert bye["connections"]["solo"]["state"] == "closed", (
        "and it is closed once its answer is drained: %r"
        % (bye["connections"]["solo"],))
    assert bye_world.stats()["bytes_drained"] == 6, (
        "the six bytes of `+BYE\\r\\n` reached the client before the close did, "
        "which is what proves the close waited for the drain: %r"
        % (bye_world.stats(),))
    assert bye_world.done(), (
        "and the world settled: %r" % (bye_world.stats(),))
    hushed, hushed_world = _solo(s, l, (b"SET a 1\nQUIT\nSET b 2\n",))
    assert hushed["answers"]["solo"] == (b"+OK\r\n", b"+BYE\r\n"), (
        "a client that quits mid-write is answered for what it said before it: %r"
        % (hushed["answers"],))
    assert hushed["store"] == {b"a": (b"1", None)}, (
        "and the commands after `QUIT` are never run, because the connection has "
        "no further say: %r" % (hushed["store"],))
    assert hushed["connections"]["solo"]["queries"] == 2, (
        "the two commands it was heard for are the two it counted: %r"
        % (hushed["connections"]["solo"],))
    assert hushed["connections"]["solo"]["buffer"] == b"", (
        "and the commands after `QUIT` are dropped with the rest of the buffer, "
        "not left half-read in it: %r" % (hushed["connections"]["solo"],))
    assert hushed_world.stats()["bytes_drained"] == 11, (
        "and both answers reached it: %r" % (hushed_world.stats(),))

    # ---- a reply the outbox cannot take is deferred, never dropped ---------

    fat, fat_world = _solo(s, l, (b"SET b " + b"z" * 20 + b"\n", b"GET b\n"),
                           budget=32)
    assert fat["answers"]["solo"] == (b"+OK\r\n", b"$20\r\n" + b"z" * 20 + b"\r\n"), (
        "a twenty-seven-byte reply is one answer, whole, however many writes it "
        "took: %r" % (fat["answers"]["solo"],))
    assert fat_world.stats()["write_calls"] == 5 and fat_world.stats()["drops"] == 0, (
        "the eight-byte outbox took it in four writes and the link dropped "
        "nothing: %r" % (fat_world.stats(),))
    assert fat_world.stats()["bytes_drained"] == 32 and fat_world.done(), (
        "all thirty-two answer bytes reached the client: %r"
        % (fat_world.stats(),))
    assert fat["connections"]["solo"]["queries"] == 2, (
        "and the connection counted its two commands: %r"
        % (fat["connections"]["solo"],))

    # ---- an expiry the loop's own clock has reached -------------------------

    ticking, ticking_world = _solo(
        s, l, (b"SET k v\n", b"EXPIRE k 40\n", b"KEYS\n", b"GET k\n"), budget=64)
    assert ticking["answers"]["solo"] == (b"+OK\r\n", b":1\r\n", b"$1\r\nk\r\n",
                                          b"$1\r\nv\r\n"), (
        "a deadline forty ticks out is still in the future, so `KEYS` names the key "
        "and `GET` reads it: %r" % (ticking["answers"]["solo"],))
    assert ticking["store"] == {b"k": (b"v", 42)}, (
        "the deadline is the tick the `EXPIRE` ran at — the second turn of this "
        "run — plus the forty ticks it was given: %r" % (ticking["store"],))
    assert ticking_world.stats()["bytes_drained"] == 23, (
        "and every one of those four answers reached the client: %r"
        % (ticking_world.stats(),))
    gone, gone_world = _solo(
        s, l, (b"SET k v\n", b"EXPIRE k 2\n", b"KEYS\n", b"GET k\n"), budget=64)
    assert gone["answers"]["solo"] == (b"+OK\r\n", b":1\r\n", b"$0\r\n\r\n",
                                       b"$-1\r\n"), (
        "a deadline two ticks out has passed by the third command, so `KEYS` names "
        "no key and `GET` misses: %r" % (gone["answers"]["solo"],))
    assert gone["store"] == {}, (
        "and the key is gone from the store, swept by the very command that had to "
        "say it was not there: %r" % (gone["store"],))
    assert gone_world.stats()["bytes_drained"] == 20, (
        "with every answer drained all the same: %r" % (gone_world.stats(),))
    armed, _ = _solo(s, l, (b"SET k v\n", b"EXPIRE k 2\n",), budget=3)
    assert armed["store"] == {b"k": (b"v", 4)}, (
        "with the run stopped after two commands, the key is armed and not yet "
        "expired: %r" % (armed["store"],))
    assert armed["connections"]["solo"]["queries"] == 2 and armed["steps"] == 3, (
        "two commands asked and a third turn's budget: %r, %r"
        % (armed["connections"]["solo"], armed["steps"]))

    # ---- the budget: a spent budget is an outcome --------------------------

    none, none_world = _run(s, l, clients, budget=0)
    assert (none["steps"], none["ticks"]) == (0, 0), (
        "a budget of no turns takes no turn: %r, %r"
        % (none["steps"], none["ticks"]))
    assert none["answers"] == {"fast": (), "pair": (), "slow": ()}, (
        "and answers nobody, so every client's answers are the empty tuple: %r"
        % (none["answers"],))
    assert none["store"] == {} and none["connections"] == {}, (
        "no client was accepted, so the server holds no key and made no "
        "connection's state: %r, %r" % (none["store"], none["connections"]))
    assert none_world.stats()["events"] == 0, (
        "a run that took no turn touched nothing, not even the listener: %r"
        % (none_world.stats(),))
    one, one_world = _run(s, l, clients, budget=1)
    assert one["answers"] == {"fast": (), "pair": (), "slow": ()}, (
        "one turn reads the three clients' bytes and executes four commands, but an "
        "answer is counted when its last byte reaches the outbox: %r"
        % (one["answers"],))
    assert one["store"] == {b"one": (b"2", None), b"two": (b"2", None)}, (
        "the commands of that one turn are already in the store: %r"
        % (one["store"],))
    assert one["connections"]["fast"]["state"] == "writing", (
        "and each connection is answering, not reading: %r"
        % (one["connections"],))
    assert (one["steps"], one["ticks"]) == (1, 1), (
        "one turn is one tick: %r, %r" % (one["steps"], one["ticks"]))
    assert one_world.stats()["bytes_written"] == 0, (
        "and nothing has been written yet, which is what the link's own count "
        "says: %r" % (one_world.stats(),))
    staged, staged_world = _run(s, l, clients, budget=2)
    assert {name: report["state"]
            for name, report in staged["connections"].items()} == {
                "fast": "writing", "pair": "writing", "slow": "writing"}, (
        "two turns in, every answer has reached the outbox and no client has "
        "drained one yet: a connection whose bytes the link has not carried away "
        "is still writing, not reading: %r" % (staged["connections"],))
    assert staged["answers"] == {"fast": (b"+OK\r\n",), "pair": (b"+OK\r\n",),
                                 "slow": (b":2\r\n",)}, (
        "and each connection's own answer is counted when its last byte reaches "
        "the outbox: %r" % (staged["answers"],))
    assert staged_world.stats()["bytes_drained"] == 10, (
        "the two clients that read every second tick have taken their answers by "
        "then, and the slow one has not: %r" % (staged_world.stats(),))

    # ---- the listener: a client that has not arrived is not abandoned ------

    waiting, waiting_world = _run(
        s, l, (l.Client("early", (b"SET e 1\n",), read_every=1),
               l.Client("late", (b"GET e\n",), read_every=1)), budget=32, seed=5)
    assert waiting["answers"] == {"early": (b"+OK\r\n",), "late": (b"$1\r\n1\r\n",)}, (
        "the second client arrives on the fifth tick, reads the key the first one "
        "set and is answered: %r" % (waiting["answers"],))
    assert waiting["store"] == {b"e": (b"1", None)}, (
        "against the one store they share: %r" % (waiting["store"],))
    assert (waiting["steps"], waiting["ticks"]) == (8, 8), (
        "and the run is not over until the client that had not arrived has been "
        "served: steps %r, ticks %r"
        % (waiting["steps"], waiting["ticks"]))
    assert waiting_world.stats()["accepted"] == 2 and waiting_world.done(), (
        "both clients were accepted, one of them five ticks after the other: %r"
        % (waiting_world.stats(),))

    # ---- the whole workload, twice, equals and together -------------------

    other, other_world = _run(s, l, clients, budget=64)
    assert other == result, (
        "two runs of the same workload are the same run, byte for byte: %r vs %r"
        % (other, result))
    assert other_world.log() == world.log(), (
        "and the same events in the same order, which is what makes a step count "
        "worth reporting: %r vs %r" % (other_world.log(), world.log()))
    assert len(world.log()) == 24, (
        "the log's twenty-four events — three accepts, five reads, five writes, "
        "eight drains and three closes — are the record the second run repeats: %r"
        % (len(world.log()),))

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "concurrent-servers-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "link.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The message of the refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return message
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _copy(runs):
        """A deep-enough copy of a `runs` to doctor one model's numbers."""
        copied = {}
        for model, run in runs.items():
            copied[model] = dict(run, answers={name: tuple(lines)
                                               for name, lines in run["answers"].items()},
                                 report=dict(run["report"]))
        return copied

    def _steps_of(runs, model):
        return runs[model]["steps"]

    import link
    import stage_10 as stage

    # ---- the four models, and the workload they all share -----------------

    assert stage.MODELS == ("blocking", "threads", "reactor", "event_loop"), (
        "the four models are the four stages that drive the world, in the order "
        "ties are broken: %r" % (stage.MODELS,))
    plan = stage.workload()
    assert sorted(plan) == ["budget", "clients", "requests", "script"], (
        "the workload is the clients, their lines, the budget and the script: %r"
        % (plan,))
    assert isinstance(plan["budget"], int) and not isinstance(plan["budget"], bool) \
        and plan["budget"] > 0, (
        "the budget is a whole number of turns: %r" % (plan["budget"],))
    assert plan["script"] is None, (
        "the thread model is driven round-robin on the course's own workload: %r"
        % (plan["script"],))
    names = tuple(client.name for client in plan["clients"])
    assert names == ("fast", "two", "slow", "long"), (
        "the course's four pressures are four clients, in this order: %r"
        % (names,))
    assert all(isinstance(client, link.Client) for client in plan["clients"]), (
        "a workload's clients are the world's clients: %r" % (plan["clients"],))
    assert plan["requests"] == {client.name: client.requests
                                for client in plan["clients"]}, (
        "and the lines are those clients' own requests, as data: %r"
        % (plan["requests"],))
    assert plan["requests"]["long"] == (b"x" * 120 + b"\n",), (
        "one client's request is longer than a move, so no model can finish it "
        "in a turn: %r" % (plan["requests"]["long"],))
    assert plan["clients"][2].read_every == 3 and plan["clients"][2].chunk == 2, (
        "one client reads two bytes every third tick: %r"
        % (plan["clients"][2],))
    second = stage.workload()
    assert {client.name: client.requests for client in second["clients"]} \
        == plan["requests"], (
        "the workload is the same workload every time it is asked for: %r"
        % (second["requests"],))

    # ---- four runs, four links, four accounts -----------------------------

    runs = stage.run_all()
    assert tuple(runs) == stage.MODELS, (
        "run_all reports every model, in MODELS order: %r" % (tuple(runs),))
    for model in stage.MODELS:
        run = runs[model]
        assert tuple(run) == ("answers", "steps", "ticks", "report"), (
            "%s's run carries the four keys in the contract's order: %r"
            % (model, tuple(run)))
        assert sorted(run) == ["answers", "report", "steps", "ticks"], (
            "%s's run is its answers, its cost and the link's own report: %r"
            % (model, sorted(run)))
        assert isinstance(run["report"], dict) and run["report"]["ticks"] >= 0, (
            "%s's report is the link's stats(): %r" % (model, run["report"]))
        assert run["report"]["ticks"] == run["ticks"], (
            "%s's own tick count and the link's are the same reading: %r vs %r"
            % (model, run["ticks"], run["report"]["ticks"]))
        assert tuple(run["answers"]) == names, (
            "%s answers every client of the workload, in the workload's order: "
            "%r" % (model, tuple(run["answers"])))
        delivered = sum(len(line) for lines in run["answers"].values()
                        for line in lines)
        assert delivered == run["report"]["bytes_drained"], (
            "%s's answers add up to the bytes the link says were drained, and "
            "each model ran on a link of its own: %r vs %r"
            % (model, delivered, run["report"]["bytes_drained"]))
        assert run["report"]["accepted"] == len(names), (
            "%s's own link accepted every client: %r"
            % (model, run["report"]["accepted"]))
        assert run["report"]["closes"] == len(names), (
            "%s closed every connection it accepted: %r"
            % (model, run["report"]["closes"]))
        assert run["report"]["drops"] == 0, (
            "%s never queued bytes the outbox could not take: %r"
            % (model, run["report"]["drops"]))
        assert run["report"]["bytes_written"] == 148, (
            "%s wrote the four replies the workload asks for, once each: %r"
            % (model, run["report"]["bytes_written"]))

    assert {model: runs[model]["steps"] for model in stage.MODELS} == {
        "blocking": 42, "threads": 54, "reactor": 19, "event_loop": 23}, (
        "the four step counts of this workload are the course's own numbers: %r"
        % ({model: runs[model]["steps"] for model in stage.MODELS},))
    assert len({runs[model]["ticks"] for model in stage.MODELS}) > 1, (
        "and the four models do not use up the same number of the world's ticks "
        "either: %r" % ({model: runs[model]["ticks"] for model in stage.MODELS},))

    # ---- the comparison is a report ---------------------------------------

    report = stage.compare(runs)
    assert tuple(report) == ("same_answers", "differences", "steps", "cheapest",
                             "tie_breaker"), (
        "compare reports the five things the contract names, in the contract's "
        "order: %r" % (tuple(report),))
    assert sorted(report) == ["cheapest", "differences", "same_answers", "steps",
                              "tie_breaker"], (
        "compare reports the five things the contract names: %r"
        % (sorted(report),))
    assert tuple(stage.cross_check(runs["reactor"])) == ("agree",
                                                         "disagreements"), (
        "cross_check answers with its verdict and its list, in that order: %r"
        % (tuple(stage.cross_check(runs["reactor"])),))
    assert report["same_answers"] is True, (
        "all four models delivered the same replies to all four clients: %r"
        % (report["differences"],))
    assert report["differences"] == (), (
        "so there is nothing to name: %r" % (report["differences"],))
    assert report["steps"] == {model: runs[model]["steps"]
                               for model in stage.MODELS}, (
        "every model's step count is reported, not only the winner's: %r"
        % (report["steps"],))
    assert report["cheapest"] == "reactor", (
        "on the course's own workload the reactor is the cheapest model by "
        "steps: %r" % (report["cheapest"],))
    assert report["steps"]["blocking"] > report["steps"][report["cheapest"]], (
        "and the blocking model is not the cheapest — one slow reader is enough "
        "to say so: %r" % (report["steps"],))
    assert report["tie_breaker"] == {"agree": True, "disagreements": ()}, (
        "the cheapest model's own account agrees with the link it ran on: %r"
        % (report["tie_breaker"],))
    for model in stage.MODELS:
        assert stage.cross_check(runs[model]) == {"agree": True,
                                                  "disagreements": ()}, (
            "%s's account agrees with the link by bytes, clients and ticks: %r"
            % (model, stage.cross_check(runs[model])))

    assert stage.compare(stage.run_all(models=("reactor",)))["cheapest"] \
        == "reactor", (
        "a report over one model is a report over that model")

    # ---- a tie is broken by MODELS order, not by the dict's ---------------

    tied = _copy(runs)
    tied["blocking"] = dict(tied["reactor"])
    assert tied["blocking"]["steps"] == tied["reactor"]["steps"], (
        "the fixture really is a tie: %r" % (tied["blocking"]["steps"],))
    assert stage.compare(tied)["cheapest"] == "blocking", (
        "two models with the same step count are broken by MODELS order and not "
        "by the order the caller built the dict in: %r"
        % (stage.compare(tied)["cheapest"],))
    reversed_tie = dict(reversed(list(tied.items())))
    assert stage.compare(reversed_tie)["cheapest"] == "blocking", (
        "and the same call with the dict built the other way round answers the "
        "same: %r" % (stage.compare(reversed_tie)["cheapest"],))

    # ---- a model that disagrees is a finding, not an exception ------------

    lying = _copy(runs)
    lines = lying["threads"]["answers"]["fast"]
    lying["threads"]["answers"]["fast"] = lines + (b"+extra\n",)
    found = stage.compare(lying)
    assert found["same_answers"] is False, (
        "a model that delivered one line more than the others is a "
        "disagreement: %r" % (found["same_answers"],))
    assert found["differences"] == (("threads", "fast", (b"+ping\n", b"+extra\n"),
                                     (b"+ping\n",)),), (
        "named by model, by client, by what arrived and by what the others "
        "delivered: %r" % (found["differences"],))
    assert found["steps"] == report["steps"], (
        "and a disagreement in the answers does not change the step counts: %r"
        % (found["steps"],))

    same_length = _copy(runs)
    same_length["threads"]["answers"]["fast"] = (b"+pinG\n",)
    swapped = stage.compare(same_length)
    assert swapped["differences"] == (("threads", "fast", (b"+pinG\n",),
                                      (b"+ping\n",)),), (
        "an answer of the same length and different bytes is a disagreement: a "
        "comparison by length would call it equal: %r" % (swapped["differences"],))

    missing = _copy(runs)
    del missing["event_loop"]["answers"]["long"]
    named = stage.compare(missing)
    assert named["same_answers"] is False, (
        "a model that never answered a client is a disagreement too: %r"
        % (named["same_answers"],))
    assert named["differences"] == (("event_loop", "long", None,
                                     (b"+" + plan["requests"]["long"][0],)),), (
        "and it is named with nothing at all where the answer should be: %r"
        % (named["differences"],))

    everything = _copy(runs)
    for model in ("threads", "reactor", "event_loop"):
        everything[model]["answers"] = dict.fromkeys(names, ())
    empty = stage.compare(everything)
    assert (empty["same_answers"], empty["differences"]) == \
        (False, (("threads", "fast", (), (b"+ping\n",)),
                 ("threads", "two", (), (b"+hello\n", b"+again\n")),
                 ("threads", "slow", (), (b"+hola\n",)),
                 ("threads", "long", (), (b"+" + b"x" * 120 + b"\n",)))), (
        "three models that answered nobody are three disagreements, one per "
        "client, each naming the first model that got it wrong: %r"
        % (empty["differences"],))

    # ---- the link is the tie-breaker, and a lie is a named key ------------

    reactor_run = runs["reactor"]
    one_off = _copy(runs)["reactor"]
    one_off["report"]["bytes_drained"] -= 1
    assert stage.cross_check(one_off) == {
        "agree": False, "disagreements": (("bytes_drained", 148, 147),)}, (
        "a model whose answers add up to more than the link drained is caught by "
        "the byte count: %r" % (stage.cross_check(one_off),))
    fewer = _copy(runs)["reactor"]
    fewer["report"]["closes"] -= 1
    assert stage.cross_check(fewer) == {
        "agree": False, "disagreements": (("clients", 4, 3),)}, (
        "a model that answered a client whose connection it never closed is "
        "caught by the connection count: %r" % (stage.cross_check(fewer),))
    late = _copy(runs)["reactor"]
    late["report"]["ticks"] += 1
    assert stage.cross_check(late) == {
        "agree": False, "disagreements": (("ticks", reactor_run["ticks"],
                                           reactor_run["ticks"] + 1),)}, (
        "a model that reports a clock the link never kept is caught by the tick "
        "count: %r" % (stage.cross_check(late),))
    both = _copy(runs)["reactor"]
    both["report"]["bytes_drained"] -= 2
    both["report"]["closes"] -= 1
    assert stage.cross_check(both)["disagreements"] == (
        ("bytes_drained", 148, 146), ("clients", 4, 3)), (
        "and two faults are two keys, in the order the keys are checked: %r"
        % (stage.cross_check(both)["disagreements"],))
    assert stage.cross_check(both)["agree"] is False, (
        "a run with any disagreement does not agree: %r"
        % (stage.cross_check(both),))

    # ---- the refusals -----------------------------------------------------

    _refuses(stage.ServerError, "run_all with a model that is not one of the four",
             lambda: stage.run_all(models=("ghost",)), names=("'ghost'",))
    _refuses(stage.ServerError, "run_all with no models at all",
             lambda: stage.run_all(models=()), names=("models",))
    _refuses(stage.ServerError, "run_all with a name instead of a sequence",
             lambda: stage.run_all(models="blocking"), names=("blocking",))
    _refuses(stage.ServerError, "run_all with one model named twice",
             lambda: stage.run_all(models=("blocking", "blocking")),
             names=("'blocking'", "twice"))
    _refuses(stage.ServerError, "compare of nothing",
             lambda: stage.compare({}), names=("runs",))
    _refuses(stage.ServerError, "compare of a model that is not one of the four",
             lambda: stage.compare({"ghost": runs["reactor"]}),
             names=("'ghost'",))
    _refuses(stage.ServerError, "compare of a run missing its report",
             lambda: stage.compare({"reactor": {"answers": {}, "steps": 1,
                                                "ticks": 1}}),
             names=("report",))
    _refuses(stage.ServerError, "compare of a run missing half of its keys",
             lambda: stage.compare({"reactor": {"answers": {}, "steps": 1}}),
             names=("ticks", "report"))
    _refuses(stage.ServerError, "cross_check of something that is not a run",
             lambda: stage.cross_check("a run"), names=("run",))
    _refuses(stage.ServerError, "cross_check of a run with no keys",
             lambda: stage.cross_check({}), names=("answers", "steps", "ticks",
                                                   "report"))
    _refuses(stage.ServerError, "cross_check of answers that are not a dict",
             lambda: stage.cross_check(dict(runs["reactor"], answers=[])),
             names=("answers",))
    _refuses(stage.ServerError, "cross_check of an answer that is not a tuple",
             lambda: stage.cross_check(dict(runs["reactor"],
                                            answers={"fast": b"+ping\n"})),
             names=("fast", "tuple"))
    _refuses(stage.ServerError, "cross_check of a line that is not bytes",
             lambda: stage.cross_check(dict(runs["reactor"],
                                            answers={"fast": ("+ping\n",)})),
             names=("fast", "bytes"))
    _refuses(stage.ServerError, "cross_check of a report that is not a dict",
             lambda: stage.cross_check(dict(runs["reactor"], report=[])),
             names=("report",))

    # ---- the whole comparison, twice --------------------------------------

    first = stage.run_all()
    second = stage.run_all()
    assert first == second, (
        "two runs of the same workload are the same run, four step counts and "
        "four reports included")
    assert stage.compare(first) == stage.compare(second), (
        "and so is the comparison of them: %r vs %r"
        % (stage.compare(first), stage.compare(second)))
    assert [first[model]["report"]["bytes_drained"] for model in stage.MODELS] \
        == [148, 148, 148, 148], (
        "every model delivered every byte of every answer: %r"
        % ([first[model]["report"]["bytes_drained"] for model in stage.MODELS],))

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The connection as a state machine",
        tags=["state-machine", "framing"],
        action="Write `ServerError`, `STATES`, `REPLY_PREFIX`, `open_conn`, "
               "`step_conn`, `finish` and `stats` in stage_01.py.",
        predict="Why a server is a state machine over a connection rather than a "
                "loop over reads, and what a send has to know before it may "
                "happen at all.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The blocking server, and the slow client",
        tags=["blocking", "starvation"],
        action="Write `serve_blocking` in stage_02.py.",
        predict="How many clients one model serves while one of them reads every "
                "fourth tick, and which of them the budget leaves unanswered.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="Threads, and the interleaving the check chooses",
        tags=["threads", "scheduler"],
        action="Write `Scheduler` (`__init__`, `spawn`, `ready`, `step`, `run`) "
               "and `serve_threads` in stage_03.py.",
        predict="What a thread has to give up to be a step function, and what a "
                "script buys a check that a thread library never could.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The reactor: readiness as a set, and no busy-waiting",
        tags=["reactor", "readiness"],
        action="Write `ready_set` and `serve_reactor` in stage_04.py.",
        predict="What the difference is between a turn and a poll, and why a "
                "loop that services what is ready still needs a clock.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The event loop and its timers",
        tags=["timers", "event-loop"],
        action="Write `Timers` (`__init__`, `arm`, `cancel`, `due`, `next_at`) "
               "and `serve_with_timeouts` in stage_05.py.",
        predict="Why a queue of deadlines can never be re-sorted, and when a "
                "connection idle for the last eight ticks is a timeout rather "
                "than a finish.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="Callbacks as data, and the one that must not run",
        tags=["callbacks", "handles"],
        action="Write `Handles` (`__init__`, `register`, `cancel`, `ready`, "
               "`take`) and `serve_callbacks` in stage_06.py.",
        predict="Why a callback about a connection that has since closed is a "
                "verdict and not an error, and where the state a callback needs "
                "has to travel.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="Futures and async/await as a desugaring",
        tags=["futures", "coroutines"],
        action="Write `Future` (`__init__`, `settle`, `done`, `value`, `result`), "
               "`await_`, `chain`, `Loop` (`__init__`, `spawn`, `run`) and "
               "`serve_async` in stage_07.py.",
        predict="What is left of `async` and `await` once the loop is written by "
                "hand, and why a promise that can be settled twice cannot be a "
                "promise.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="Backpressure, and the write that has to be deferred",
        tags=["backpressure", "outbox"],
        action="Write `send` and `serve_backpressure` in stage_08.py.",
        predict="What a server owes a client when the outbox takes four of the "
                "eleven bytes of its reply, and what head-of-line blocking looks "
                "like as a number.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The Redis case study: a command loop with per-connection state",
        tags=["redis", "command-loop"],
        action="Write `COMMANDS`, `parse`, `execute` and `serve_commands` in "
               "stage_09.py.",
        predict="Which state belongs to the server and which to the connection, "
                "and where a command split across two reads has to be kept.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="One workload, four models, and the steps it took",
        tags=["capstone", "step-counts"],
        action="Write `MODELS`, `workload`, `run_all`, `compare` and "
               "`cross_check` in stage_10.py.",
        predict="Which model this workload is cheapest for, and which of a "
                "model's own numbers the link's log disagrees with.",
        check=check_10,
    ),
]
