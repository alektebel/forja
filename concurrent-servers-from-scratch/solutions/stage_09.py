"""Concurrent Servers From Scratch — stage 9: The Redis case study: a command loop with per-connection state.

SOLUTION. Stages 1 to 8 speak one protocol — a line in, the line back with a `+`
in front of it — and that protocol has no state: every request is answered out of
itself. This stage is the one that does not fit that mould. A `SET` is remembered,
an `EXPIRE` is remembered *and* expires, a `QUIT` ends the conversation, and the
same connection asks the next question against what the last one answered. The
protocol is RESP-lite and the subject is the split it forces: **the store belongs
to the server and the buffer belongs to the connection.**

The three functions are the three layers of that split. `parse` turns one whole
line — and only a whole one — into a command and its arguments, judging the
*shape* of the line and refusing a bite of one by name. `execute` answers one
command against the server's store and one connection's state, judging its
*content*: an unknown command, a bad count of arguments and an `INCR` of a value
that is not a number are error lines this function *returns*, never exceptions
thrown at a loop that cannot do anything about them. `serve_commands` is the loop
that carries the bytes: it takes what the world has for each ready connection,
executes every whole line it now holds — in the order the client wrote them — and
keeps the tail for the read that completes it.

Nothing here is invented about who may move. Readiness is `stage_04.ready_set`, a
turn is one `Link.step(1)`, and a connection's phase is one of `stage_01.STATES`:
a command loop is the reactor with a command layer in front of the wire, which is
why this stage imports both rather than writing a third loop.
"""

import stage_01
import stage_04
from link import Client, Link

#: The commands this server speaks. The protocol is closed: a word that is not in
#: here is answered with the error line and never with an exception, because a
#: client typing nonsense is a fact about a client, not a broken course.
COMMANDS = ("SET", "GET", "DEL", "INCR", "EXPIRE", "KEYS", "QUIT")

#: The arguments each command takes, as `(command, count)` pairs. A tuple of
#: pairs is a constant a caller cannot edit; a `dict` at module level would be
#: state this file is not allowed to keep.
_ARITY = (("SET", 2), ("GET", 1), ("DEL", 1), ("INCR", 1), ("EXPIRE", 2),
          ("KEYS", 0), ("QUIT", 0))

#: The phases a command connection moves through, and they are stage 1's own
#: vocabulary: a command connection is the same machine — it reads, it writes, it
#: closes — with a buffer of whole lines and a queue of answers in front of the
#: wire. There is no `"new"` here (accepting the connection *is* the first move),
#: which is exactly how stage 4 admits a connection too.
_READING, _WRITING, _CLOSING, _CLOSED = (stage_01.STATES[1], stage_01.STATES[2],
                                         stage_01.STATES[3], stage_01.STATES[4])

#: The error line's prefix: everything this server refuses is one line of this.
_ERROR = b"-ERR "


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


# ---- the command layer: one line in, one reply out ------------------------

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
    if not isinstance(line, bytes):
        raise ServerError("a command line is bytes, not %r" % (line,))
    if not line.endswith(b"\n"):
        raise ServerError("a command line ends in a newline, not %r" % (line,))
    tokens = line[:-1].split()
    word = tokens[0] if tokens else b""
    try:
        command = word.decode("ascii").upper()
    except UnicodeDecodeError:
        raise ServerError("a command is spelled in ascii, not %r" % (word,))
    return (command, tuple(tokens[1:]))


def _store(store):
    """The server's store, refusing anything that is not the dict it lives in."""
    if not isinstance(store, dict):
        raise ServerError("a store is a dict of key to value, not %r" % (store,))
    return store


def _command(command):
    """A command's name, refusing a command that has none to compare."""
    if not isinstance(command, str):
        raise ServerError("a command is its name, not %r" % (command,))
    return command


def _args(args):
    """The arguments of a command: a sequence of bytes, or a refusal naming them."""
    if not isinstance(args, (tuple, list)):
        raise ServerError("a command's arguments are a sequence, not %r" % (args,))
    for value in args:
        if not isinstance(value, bytes):
            raise ServerError("an argument is bytes, not %r" % (value,))
    return tuple(args)


def _state(conn):
    """The connection state a command is run against, or a refusal naming it.

    A command is answered *for* a connection, and two numbers of that state are
    the world's own rather than this stage's invention: `now`, the tick of the
    injected clock the server is answering at, which is what `EXPIRE` records a
    deadline against and what `GET` checks one against; and `queries`, this
    connection's own count, which this function does not increment but the caller
    does. Both are asked for, so a caller that hands over a mapping without them
    is refused for the key it is missing instead of tripping over it later.
    """
    if not isinstance(conn, dict):
        raise ServerError("a command runs against a connection state, not %r"
                          % (conn,))
    for key in ("now", "queries"):
        value = conn.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ServerError("a connection state carries %r as a count of ticks, "
                              "and this one has %r" % (key, value))
    return conn


def _arity(command):
    """How many arguments a command takes, and it is in `_ARITY` or nowhere."""
    for name, count in _ARITY:
        if name == command:
            return count
    return None


def _integer(raw):
    """The number `raw` spells, or `None` when it spells something else.

    The rule is exact and it is Redis's: an optional `"-"`, then decimal digits
    and nothing else. `int()` would be more forgiving than the protocol is — it
    reads `1_0` as ten and `+5` as five — and an `INCR` that accepted either
    would store a value that no later `INCR` could read back as a number.
    """
    if not raw:
        return None
    body = raw[1:] if raw[:1] == b"-" else raw
    if not body:
        return None
    for byte in body:
        if not 48 <= byte <= 57:
            return None
    return int(body) * (-1 if raw[:1] == b"-" else 1)


def _bulk(value):
    """A bulk string: its length, its bytes, its terminator — `GET`'s reply shape."""
    return b"$" + str(len(value)).encode() + b"\r\n" + value + b"\r\n"


def _count(number):
    """An integer line: `DEL`, `INCR` and `EXPIRE` all answer with one."""
    return b":" + str(number).encode() + b"\r\n"


def _expired(entry, now):
    """Whether this entry's deadline has been reached on the injected clock."""
    return entry[1] is not None and entry[1] <= now


def _live(store, key, now):
    """The live entry for `key`, forgetting an expired one on the way out.

    This is the one place the store sheds a key whose deadline the clock has
    reached, and it sheds it *for real*: an expired key is a miss, and a miss
    that is still in the dict would be a key `KEYS` counts and a `DEL` finds.
    Every lookup in this stage goes through here, so `GET`, `DEL` and `INCR`
    cannot disagree about what the server holds.
    """
    entry = store.get(key)
    if entry is None:
        return None
    if _expired(entry, now):
        del store[key]
        return None
    return entry


def _sweep(store, now):
    """Forget every key whose deadline the clock has reached, oldest key first."""
    for key in [key for key, entry in store.items() if _expired(entry, now)]:
        del store[key]
    return store


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
    _store(store)
    _command(command)
    args = _args(args)
    state = _state(conn)
    state["queries"] = state["queries"] + 1
    now = state["now"]
    if command not in COMMANDS:
        return _ERROR + ("unknown command %r" % (command,)).encode() + b"\r\n"
    if len(args) != _arity(command):
        return _ERROR + ("wrong number of arguments for %r command"
                         % (command.lower(),)).encode() + b"\r\n"
    if command == "SET":
        store[args[0]] = (args[1], None)
        return b"+OK\r\n"
    if command == "GET":
        entry = _live(store, args[0], now)
        return b"$-1\r\n" if entry is None else _bulk(entry[0])
    if command == "DEL":
        entry = _live(store, args[0], now)
        if entry is None:
            return _count(0)
        del store[args[0]]
        return _count(1)
    if command == "INCR":
        key = args[0]
        entry = _live(store, key, now)
        if entry is None:
            number, deadline = 0, None
        else:
            number = _integer(entry[0])
            if number is None:
                return _ERROR + b"value is not an integer or out of range\r\n"
            deadline = entry[1]
        store[key] = (str(number + 1).encode(), deadline)
        return _count(number + 1)
    if command == "EXPIRE":
        ticks = _integer(args[1])
        if ticks is None:
            return _ERROR + b"value is not an integer or out of range\r\n"
        entry = _live(store, args[0], now)
        if entry is None:
            return _count(0)
        store[args[0]] = (entry[0], now + ticks)
        return _count(1)
    if command == "KEYS":
        return _bulk(b" ".join(sorted(_sweep(store, now))))
    state["quit"] = True
    return b"+BYE\r\n"


# ---- the loop: a command connection's state, and the turn that moves it ---

def _server(server):
    """The world and the clients a command loop runs, or a refusal naming it.

    The bundle is the one every model in this course is handed —
    `{"link", "clients", "requests"}` — and it is checked rather than trusted:
    the link is the world, the clients are the world's own `Client`s, and the
    requests the bundle names are each client's own script, so a description of
    the workload cannot quietly disagree with the one the link will run.
    """
    if not isinstance(server, dict):
        raise ServerError("a server is a dict of link, clients and requests, not %r"
                          % (server,))
    for key in ("link", "clients", "requests"):
        if key not in server:
            raise ServerError("a server carries link, clients and requests, and "
                              "this one has no %r" % (key,))
    link = server["link"]
    if not isinstance(link, Link):
        raise ServerError("a server's link is the world, not %r" % (link,))
    clients = server["clients"]
    if (isinstance(clients, (str, bytes)) or not isinstance(clients, (tuple, list))
            or not clients):
        raise ServerError("a server's clients are a non-empty sequence, not %r"
                          % (clients,))
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
    return link, tuple(clients)


def _budget(budget):
    """A turn budget: a whole number of turns, or a refusal naming it."""
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
        raise ServerError("a budget is a whole number of turns, not %r" % (budget,))
    return budget


def _open(conn):
    """A fresh command connection for `conn`: the phase, the buffer, the counts.

    Four things are this connection's and nothing else's: the phase of stage 1's
    machine it is in, the bytes of a command it has read but not finished, the
    answers it owes that the outbox has not taken, and its own `queries` count and
    quit flag. `sent` is how much of the answer at the head of the queue the
    outbox has already taken, and `now` is the tick the connection's last command
    was run at — stamped by the move that runs one, and starting at zero, the tick
    nothing has been answered at yet, so that a command always measures its
    deadline against the clock it actually ran on.
    """
    return {"state": _READING, "conn": conn, "buffer": b"", "queue": [], "sent": 0,
            "queries": 0, "quit": False, "now": 0}


def _admit(link, states):
    """Everyone the listener holds: accept, and open their state.

    Accepting is the listener's own move and it is not a turn: the loop admits
    before it polls, so a client that arrived while the last turn was being
    stepped is serviced by this one like everybody else.
    """
    while True:
        conn = link.accept()
        if conn is None:
            return
        states[conn.id] = _open(conn)


def _read(link, state, store):
    """Take what the world has, execute every whole line in it, keep the rest.

    This is the framing rule of the whole stage. What is read is appended to this
    connection's own buffer — so a command the link carried in two pieces is
    executed once, when the second piece completes its line — and then every
    complete line the buffer now holds is executed in the order it was written,
    against the server's store and this connection's state. Two commands in one
    read are two `execute` calls and two answers, never one.

    The loop stops at the first line that is not whole and *keeps* it: the buffer
    is the connection's, and a tail is the front of the next command, not a
    command. An empty line is a line like any other and the command layer answers
    it. Once `QUIT` has been executed there is nothing further this connection may
    say, so the rest of the buffer goes with it and the connection stops reading.
    """
    conn = state["conn"]
    state["buffer"] = state["buffer"] + link.read(conn)
    while True:
        head, marker, tail = state["buffer"].partition(b"\n")
        if not marker:
            return
        state["buffer"] = tail
        command, args = parse(head + marker)
        state["queue"].append(execute(store, command, args, conn=state))
        if state["quit"]:
            state["buffer"] = b""
            return


def _write(link, state, answers):
    """Hand the outbox what it will take of the answer at the head of the queue.

    An answer is one command's reply line(s) — kept whole, so that a reply the
    outbox cannot take in one go is written over the turns that follow and never
    truncated — and it is *recorded* when its last byte has reached the outbox,
    never when the command was read: the answers a run reports are the answers it
    delivered, and a budget that runs out between the read and the write is a
    reply this run did not deliver.
    """
    conn = state["conn"]
    head = state["queue"][0]
    state["sent"] = state["sent"] + link.write(conn, head[state["sent"]:])
    if state["sent"] >= len(head):
        answers[conn.client.name].append(head)
        state["queue"].pop(0)
        state["sent"] = 0


def _over(link, state):
    """Whether this connection has nothing left in either direction.

    Stage 1's `_finished`, in command-loop terms: the client has arrived, has no
    bytes the server has not taken, has taken every byte it was written, has
    nothing in the outbox and nothing of the server's still queued — and either
    asked to quit or has handed over its last request. That last clause is the
    one that matters: the link scripts a client's requests, so the only honest
    signal that there is no further request is the client falling silent.

    The link's own `owed` is deliberately not part of this. The link says a
    request is owed as soon as the request's *bytes* are in, and a tail that is
    not yet a line is in without being a command: a connection sitting on half a
    line is not waiting to be answered, it is waiting to be finished, and
    treating it as owed forever is a run that never ends.
    """
    conn = state["conn"]
    if link.readable(conn) or link.drainable(conn) or conn.outbox:
        return False
    if state["queue"]:
        return False
    return state["quit"] or conn.request + 1 >= len(conn.client.requests)


def _phase(link, state):
    """Where this connection is, in stage 1's phases, after the move it just took.

    `closing` when there is nothing left in either direction — `_over`'s verdict,
    and the only thing this stage ever closes a connection from — `writing` while
    an answer of its own is still in flight, in the queue or in the outbox, and
    `reading` otherwise, which is the phase a connection assembling a line and a
    connection waiting for a client's next request are both in. The order is the
    point: a connection with an answer to deliver is not over however quiet its
    client has gone, and one predicate — `_over` — has the last word on it, so
    the function that names the phase and the function that closes the connection
    can never disagree.
    """
    if _over(link, state):
        state["state"] = _CLOSING
    elif state["queue"] or state["conn"].outbox:
        state["state"] = _WRITING
    else:
        state["state"] = _READING
    return state["state"]


def _service(link, state, store, answers):
    """One move of one ready connection: read its commands, or write its answers.

    A turn gives each connection one move and which move it is is the state's own
    business: a connection with request bytes the server has not taken is read, a
    connection with an answer still queued is written to, and a connection that is
    neither is moved nowhere at all — an idle move, which is what a connection
    waiting for its client to drain or for a request that has not been written yet
    honestly is. The tick is taken into the state before either move, so a command
    executed this turn measures its deadlines against the clock it ran on.
    """
    state["now"] = link.now()
    if link.readable(state["conn"]):
        _read(link, state, store)
    elif state["queue"]:
        _write(link, state, answers)
    _phase(link, state)


def _retire(link, states):
    """Close every connection in the `"closing"` phase, once.

    This is stage 1's `finish` and the one transition the loop does not take while
    stepping: `"closing"` is reached when a client has nothing left to send and
    has taken every answer, and the connection is closed from there and nowhere
    else. A client that asked to quit arrives here the same way, and only after
    its `+BYE` has been drained — which is why the phase decides this and the quit
    flag does not.
    """
    for state in states.values():
        if state["state"] == _CLOSING:
            link.close(state["conn"])
            state["state"] = _CLOSED


def _turn(readable, writable):
    """The ids this turn services: the ready set, in accept order, once each.

    Both halves of the ready set are already in accept order, so a connection in
    both keeps its place in it and is serviced once: one move per connection per
    turn is what makes the turn count mean what it says.
    """
    order = []
    for cid in tuple(readable) + tuple(writable):
        if cid not in order:
            order.append(cid)
    return tuple(order)


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
    are ready (stage 4's own `ready_set`), service *those* and no others — one
    move each — retire every connection that has nothing left in either direction,
    and step the link once. Nothing moves outside `Link.step()`, so a turn with
    nothing ready still steps, and only a run with nothing readable, nothing
    writable and nobody left in the listener is over.

    The store is one dict for the whole loop, so two clients asking about the same
    key ask about the same key; the buffer, the query count and the quit flag
    belong to a connection and never move between them. `budget` is in turns: a
    budget spent with work left is an outcome, not an exception, and the run says
    what it did by reporting the store and the connections it left behind.
    """
    link, clients = _server(server)
    limit = _budget(budget)
    store = {}
    states = {}
    answers = {client.name: [] for client in clients}
    steps = 0
    while steps < limit:
        _admit(link, states)
        readable, writable = stage_04.ready_set(
            link, tuple(state["conn"] for state in states.values()))
        if not readable and not writable and not link.waiting():
            break
        for cid in _turn(readable, writable):
            _service(link, states[cid], store, answers)
        _retire(link, states)
        link.step(1)
        steps += 1
    return {"answers": {name: tuple(lines) for name, lines in answers.items()},
            "steps": steps,
            "ticks": link.now(),
            "store": dict(store),
            "connections": {state["conn"].client.name:
                            {"state": state["state"],
                             "queries": state["queries"],
                             "quit": state["quit"],
                             "buffer": state["buffer"]}
                            for state in states.values()}}
