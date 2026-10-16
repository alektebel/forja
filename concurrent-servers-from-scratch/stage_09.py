"""Concurrent Servers From Scratch — stage 9: The Redis case study: a command loop with per-connection state.

Every stage before this one speaks the same protocol — a line in, the same line
back with a `+` in front of it — and that protocol has no memory: a request is
answered out of itself and nothing a client says changes anything for the next
one. Redis's protocol does not work that way. `SET` is remembered, `EXPIRE`
expires, `QUIT` ends the conversation, and the same connection asks its next
question against what its last answer did.

So this stage is where the state lands, and the whole subject is *which* state
lands where. The store belongs to the server: two connections that `SET` and
`GET` the same key are talking about the same key, and a client that opens a
second connection does not find a second world. The input buffer belongs to the
connection: two clients' half-read commands never mix, each connection counts its
own queries, and only one of them can have asked to quit. Getting that split
wrong is not a crash — it is a `GET` that sees a key nobody set, which is exactly
the kind of failure this course is about.

`parse` is the first layer, and its job is the *shape* of a line: a line is bytes,
it ends in a newline, and only then does it have a command and arguments at all.
`execute` is the second, and its job is the *content* of a command: an unknown
command, a wrong count of arguments and an `INCR` of something that is not a
number are verdicts it returns as error lines, because a client that types
nonsense is a fact about the client, not a broken program. `serve_commands` is
the third: the loop that reads bytes off the link, cuts them into whole lines,
executes them in the order they were written, and keeps the tail of a command it
has only half of.

DESIGN DECISION — Where does a command that arrives in two reads live? In the
connection's own buffer, and nowhere else. A read is a piece of a stream and the
line is the unit the protocol has: the buffer accumulates what the link hands
over and a command is executed exactly when its line is whole, which means a
buffer that is cleared per read loses half the command and a buffer that is
parsed per read executes a command the client has not finished writing. The
buffer travels with the connection, so a client that is slow to write and a
client that is slow to read cannot end up sharing one.

DESIGN DECISION — Which state is the server's and which is the connection's? One
store for the whole run; a buffer, a query count, a quit flag, the answers still
owed and the phase of the connection's machine all belong to the connection. The
store is created once, before the loop, and no connection ever gets a copy of it:
a store per connection would answer `GET` from a key the other client set as a
miss, which is a bug that looks exactly like a client's mistake.

DESIGN DECISION — Is an unknown command an exception or a reply? A reply — the
error line — every time. Nothing about a client's typing can make a server fail,
and a loop that raises where it could answer turns one client's typo into every
other client's outage. The same goes for a wrong count of arguments and for an
`INCR` of a value that is not an integer: they are answers, and the only
exceptions in this stage are about the *shape* of what the module itself was
handed.

DESIGN DECISION — How is an expiry recorded, and how is it checked? As a deadline
in ticks on the injected clock — `EXPIRE key n` stores `now + n` — because this
course has no wall clock and a tick is the only unit of time there is; and it is
checked on the way *out* of the store, at `GET`, `DEL`, `INCR` and `KEYS` alike.
An expired key is a miss *and* is forgotten: a key that is hidden but left in the
dict is a key `KEYS` still counts and a `DEL` still finds, which is the same bug
wearing a different hat.

DESIGN DECISION — How many commands does one read execute? Every whole line in
what was read, in the order the client wrote them, and not one command more. A
client may pipeline two requests into one write, and a loop that treats the read
as one command answers the first and silently drops the second; a loop that
treats the whole read as one line loses the argument boundaries. Each complete
line is parsed and executed on its own, and the partial tail after the last whole
line is kept.

DESIGN DECISION — When is the connection closed after `QUIT`? Only once the
`+BYE` has been drained. `QUIT` raises the connection's quit flag and answers
`+BYE`; the connection then has nothing further to read, and it is closed from
the `"closing"` phase — the same phase a connection reaches when its client has
run out of requests and has taken every answer. Closing it on the spot loses the
`+BYE` the client was promised, which the link's own drained-byte count proves.

TODO: implement `parse`, `execute` and `serve_commands` in the module below.
"""

#: The commands this server speaks. The protocol is closed: a word that is not in
#: here is answered with the error line and never with an exception, because a
#: client typing nonsense is a fact about a client, not a broken course.
COMMANDS = ("SET", "GET", "DEL", "INCR", "EXPIRE", "KEYS", "QUIT")


class ServerError(ValueError):
    """A line this stage will not parse, or a command it will not run as asked.

    It is the family for every *shape* this stage cannot honour: a line that is
    not bytes or does not end in a newline, a command token that is not ascii, a
    store that is not a dict, a state that does not carry the tick it is run at,
    a server whose link is not the world or whose clients are not `Client`s, and
    a budget that is not a whole number of turns. Every *verdict about content*
    is a reply instead: an unknown command, a wrong count of arguments, an `INCR`
    of a value that is not a number and a `GET` of a key whose deadline has
    passed are all answered with the error line, and a check reads them as bytes.
    """


def parse(line):
    """The command and its arguments, as a whole line spells them.

    The line is bytes and it ends in `"\\n"` — that is what makes it whole, and a
    line without one is the tail of a read that stopped in the middle of a
    command, which is a shape this function will not guess at: it is refused
    naming the offender, and keeping it is the loop's job, not this function's.
    The newline comes off, and so does a `"\\r"` if the client wrote one, and what
    is left is split on runs of whitespace: the first token is the command and
    the rest are its arguments, as bytes and untouched, because a value is the
    client's bytes and this stage never has an opinion about them.

    The command is upper-cased here once, so the rest of the stage compares it
    against `COMMANDS` without a second spelling of every name. A blank line
    names no command, which this function reports honestly as the empty command
    and the loop answers as one it does not know — an empty line is a client's
    mistake to hear about, not this module's to raise about.
    """
    raise NotImplementedError("stage 9: implement parse()")


def execute(store, command, args, *, conn):
    """The reply line(s) one command is answered with, against a store and a state.

    `store` is the server's and it maps a key to `(value, deadline)`: the value is
    the client's own bytes and the deadline is a tick of the injected clock or
    `None` for a key that does not expire. `conn` is this connection's state, and
    the only two things read out of it are `now` — the tick being answered at —
    and `queries`, this connection's count, which every command of every kind
    moves, an unknown one and a refused one included, because a query is a query.

    The reply is one of the protocol's shapes and nothing else: `+OK` for `SET`,
    a bulk string for `GET` and `$-1` for a miss, an integer for `DEL`, `INCR` and
    `EXPIRE`, `+BYE` for `QUIT`, and one error line for an unknown command, a
    wrong count of arguments or a value that is not a number. `KEYS` is the one
    command whose answer does not fit one key: it is a bulk string holding the
    live keys in byte order, one space between them — the smallest thing the
    protocol's own shapes can carry, and a shape a check can pin exactly.

    `SET` clears any deadline the key had (a fresh value is a fresh key), `INCR`
    keeps it (the value changed, the key did not), and `EXPIRE` arms one at
    `now + ticks` — so a deadline is always a tick on the same clock, and an
    expired key answers `:0` to a `DEL` and `:0` to an `EXPIRE`, because by then
    there is nothing there to arm. `QUIT` is the only command whose effect is on
    the connection rather than the store: it raises the state's `quit` flag, and
    closing the connection is the loop's move, taken once the `+BYE` has been
    drained, never this function's.
    """
    raise NotImplementedError("stage 9: implement execute()")


def serve_commands(server, *, budget=256):
    """The command loop: every client's lines executed against one store.

    The result is the five things this stage has to say about a run, in order:
    `answers`, every client's reply lines byte for byte in the order they were
    delivered; `steps`, the turns of this loop; `ticks`, the link's own reading at
    the end; `store`, the server's store as it was left — each key with the value
    the client set and the deadline in ticks `EXPIRE` armed, or `None`; and
    `connections`, one entry per connection the server made state for, holding its
    phase, its own `queries` count, whether it asked to quit, and the bytes of a
    command it read but never finished.

    One turn: admit everyone the listener holds, ask the world which connections
    are ready, service *those* and no others — one move each — retire every
    connection that has nothing left in either direction, and step the link once.
    Nothing moves outside `Link.step()`, so a turn with nothing ready still steps,
    and only a run with nothing readable, nothing writable and nobody left in the
    listener is over.

    The store is one dict for the whole loop, so two clients asking about the same
    key ask about the same key; the buffer, the query count and the quit flag
    belong to a connection and never move between them. `budget` is in turns: a
    budget spent with work left is an outcome, not an exception, and the run says
    what it did by reporting the store and the connections it left behind.
    """
    raise NotImplementedError("stage 9: implement serve_commands()")
