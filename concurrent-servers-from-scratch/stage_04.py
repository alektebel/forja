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

DESIGN DECISION — What does a turn service: every connection the reactor holds,
or only the ones the ready set named? A reactor that services everybody every
turn spends a move on a connection that has nothing to say — and a read of a
connection that is not readable returns `b""` for as long as it is asked, which
is the busy-wait this stage exists to make impossible. The turn services the
ready set, and the ready set is the only thing it services.

DESIGN DECISION — Who decides that a connection is ready: the reactor, or the
world? Reading a connection's fields directly is a reactor that has stopped using
the link and started guessing at it: `Link.readable`, `Link.writable` and
`Link.owed` are the world's own answers and they are the ones a ready set is
built from. A hand-rolled `conn.sent < len(conn.current())` would call a client
that has not arrived yet readable, and would call a closed connection writable.

DESIGN DECISION — When is readiness read: before the turn's moves, or after
them? A set computed after the moves names the connections that can move *next*
turn, not this one, and a connection serviced on that reading is serviced after
its moment has passed. The poll comes first, the moves come out of it, and the
tick comes last.

DESIGN DECISION — How many times does a turn step the link? Once. `Link.step()`
is the only thing that moves a byte or a clock, so stepping inside the
per-connection loop makes one turn N turns as far as the world is concerned, and
the step count stops describing the work. One step per turn is what makes `steps`
a comparably honest number between this model and the ones beside it.

DESIGN DECISION — When is the run over: the first empty ready set, or an empty
ready set with nobody owed? A connection whose reply the outbox could not take —
or a client the listener has not accepted yet — is not "nothing left to do", and
a run that stops there reports answers its clients never drained. The loop ends
when nothing is readable, nothing is writable and the listener is holding nobody,
which is the world's own way of saying the workload is over.

DESIGN DECISION — Are `steps` and `polls` the same number? No, and counting them
separately is the point: reading readiness costs nothing (a turn may poll twice
for free), while a turn is one tick of the world. A model that steps inside a
per-connection loop or twice per turn shows a gap between the two, and the check
holds them to `steps <= 2 * polls + 4` on a workload it knows.

TODO: implement `ready_set` and `serve_reactor` in the module below.
"""


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
    raise NotImplementedError("stage 4: implement ready_set()")


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
    raise NotImplementedError("stage 4: implement serve_reactor()")
