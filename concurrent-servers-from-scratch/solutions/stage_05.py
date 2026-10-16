"""Concurrent Servers From Scratch — stage 5: The event loop and its timers.

SOLUTION. A reactor waits for bytes; an event loop waits for bytes *and for
time*, and time does not arrive as readiness — it arrives as a deadline. So this
stage is two things which are the same thing twice: `Timers`, the monotonic queue
those deadlines live in, on the clock it is handed and never on a clock it reads;
and `serve_with_timeouts`, the loop that arms one when a connection goes idle and
closes that connection when the deadline comes due while it still is idle. The
close is the point: a connection is closed *while its client still has requests
left*, which is a timeout, and a timeout is a different object from a finish. A
finish says the read side is over and every answer has been taken; a timeout says
the client stopped reading, and the answer it never took is exactly why the two
are not the same thing.

Why the clock is injected, and why the queue is a heap rather than a sorted list:
the whole course reports steps and ticks instead of seconds, so `Timers` reads
`now()` off whatever object it was handed — in `serve_with_timeouts` that is the
link's own clock, which moves one tick at a time and only when `Link.step` moves
it. Deadlines are pushed in `(when, handle)` order and popped from the front, so
the queue is never re-sorted: a deadline that is due stays in front of one that is
not, and two equal deadlines come out in handle order, which is the order they
were armed in. `due()` compares `<=` rather than `<`, because a deadline is a tick
the clock has *reached*: the difference between the two is a whole tick of
idleness, and a check pins both sides of it.

The loop itself is stage 1's machine, driven round-robin, plus the three things a
loop with timers needs — and none of them is a thread: at most one accept per
turn, a deadline armed on the tick a connection goes idle, and that deadline
disarmed the moment the connection has something to do again. The last one is
what keeps a serviced connection from being closed by a deadline it earned while
it was idle: a stale timer that outlives its window closes a connection that has
since answered, and that is the mistake this stage exists to make impossible.
"""

import heapq

import link
import stage_01

#: How many ticks a connection may sit idle before the loop closes it. Eight is
#: the contract's default: long enough that a merely slow client — the one that
#: drains every fourth tick — is not timed out, and short enough that a client
#: that has stopped reading does not hold the loop forever.
DEFAULT_IDLE = 8

#: The turns one run takes before it gives up and reports what it has done. A
#: budget spent with work left is an outcome and not an exception: the loop says
#: how far it got, and `served` and `timed_out` say what is still open.
DEFAULT_BUDGET = 256


class ServerError(ValueError):
    """A server, a deadline, a handle or a clock this stage will not use.

    It is the family for every shape the stage cannot honour, and every refusal
    names the offender: a `server` that is not the dict of the contract (`link`,
    `clients`, `requests`), a `link` that is not a `link.Link`, an `idle` or a
    `budget` that is not a positive int, a clock that answers no `now()`, a
    deadline that is not an int tick count, a timer name that is not a non-empty
    string, and a handle that is not an int. A verdict about what a *client* did
    is never an exception: a client that stops reading is a timeout reported in
    `timed_out`, and cancelling a handle that is not live is `False`.
    """


def _when(when):
    """A deadline: an int tick count on the injected clock, or a refusal.

    It may be any int, including one the clock has already passed; a deadline in
    the past is due now rather than an error, because a loop that arms a window
    after the work that spent it has happened is a loop that still means it.
    """
    if isinstance(when, bool) or not isinstance(when, int):
        raise ServerError("a deadline is an int tick count, not %r" % (when,))
    return when


def _name(name):
    """A timer's name: the non-empty string a run has to report, or a refusal."""
    if not isinstance(name, str) or not name:
        raise ServerError("a timer's name is a non-empty string, not %r" % (name,))
    return name


def _handle(handle):
    """A timer handle: the int `arm` handed out, or a refusal naming it."""
    if isinstance(handle, bool) or not isinstance(handle, int):
        raise ServerError("a timer handle is an int, not %r" % (handle,))
    return handle


class Timers:
    """The deadlines of one loop, in one monotonic queue on one clock.

    A timer is a deadline, a name and a handle — data, never a callback — and the
    queue is a heap keyed on `(when, handle)`, so timers come out in the order
    they are due and, between two that are due at the same tick, in the order they
    were armed. The queue is never re-sorted and never rescanned: `arm` pushes,
    `due` pops from the front while the clock has reached the deadline, and
    `next_at` drops the front entries of timers that have been cancelled.

    Nothing here moves a clock. `arm` takes a tick count, `due` asks the injected
    clock what tick it is, and a timer armed in the past — a deadline the clock
    has already passed — is simply due now, which is the only reading of a
    deadline that a loop arming a spent window can rely on.
    """

    def __init__(self, clock):
        """A queue on `clock`, empty, refusing anything that answers no `now()`."""
        if not callable(getattr(clock, "now", None)):
            raise ServerError("a clock answers now(), not %r" % (clock,))
        self._clock = clock
        self._queue = []
        self._live = {}
        self._last = 0

    def arm(self, when, name):
        """Arm `name` for the tick `when`, and hand back the handle.

        Handles are ints that only ever grow, one per armed timer, so a handle is
        also a timer's place in the queue when two deadlines are equal: two
        timers armed for the same tick come due in the order they were armed,
        which is what a loop that arms one deadline per connection relies on to
        be able to say *which* connection timed out first.
        """
        _when(when)
        _name(name)
        self._last += 1
        heapq.heappush(self._queue, (when, self._last, name))
        self._live[self._last] = (when, name)
        return self._last

    def cancel(self, handle):
        """Disarm the timer `handle`, and answer whether it was still live.

        A handle armed and cancelled is not due, not next and not in the queue any
        more: this is the whole of "a cancelled timer never fires". Cancelling a
        handle that has already fired or was never armed is `False` rather than a
        refusal, because the caller asking about a timer that is gone is asking a
        question and not making a mistake.
        """
        _handle(handle)
        if handle not in self._live:
            return False
        del self._live[handle]
        return True

    def due(self):
        """Every timer the clock has reached, as `((handle, name), ...)`.

        In `(when, handle)` order and removed from the queue as it goes, so a
        second call with the clock where it was answers `()`: `due()` is a pop and
        not a scan, and a timer that is returned once can never be returned again.
        The comparison is `<=`: a deadline is due on the tick itself, not on the
        tick after it.
        """
        now = self._clock.now()
        fired = []
        while self._queue and self._queue[0][0] <= now:
            when, handle, name = heapq.heappop(self._queue)
            if handle in self._live:
                del self._live[handle]
                fired.append((handle, name))
        return tuple(fired)

    def next_at(self):
        """The earliest deadline still armed, or `None` when there is none.

        Cancelled timers do not count, and neither does the order they were armed
        in: the answer is the smallest deadline, which is the front of the queue
        once the entries of the timers that are gone have been dropped. A deadline
        the clock has already reached is still reported — it is the earliest
        deadline, not the earliest future one — so a loop can ask "how long until
        the next thing happens?" and get the deadline it is already late for.
        """
        while self._queue and self._queue[0][1] not in self._live:
            heapq.heappop(self._queue)
        if not self._queue:
            return None
        return self._queue[0][0]


def _server(server):
    """The world of a `server` dict, refusing anything that is not one of them.

    The dict is the one every model in this course takes: the link that carries
    the bytes, the clients the link scripts, and the requests those clients send.
    Only the link is used here — the link owns both the clients and the requests —
    so a dict that is missing one of the three is refused for what it is missing
    rather than tripped over later, and the refusal names the key.
    """
    if not isinstance(server, dict):
        raise ServerError("a server is a dict of link, clients and requests, not %r"
                          % (server,))
    missing = tuple(key for key in ("link", "clients", "requests")
                    if key not in server)
    if missing:
        raise ServerError("a server carries link, clients and requests, and this "
                          "one is missing %r" % (", ".join(missing),))
    world = server["link"]
    if not isinstance(world, link.Link):
        raise ServerError("a server's link is a link.Link, not %r" % (world,))
    return world


def _count(value, what):
    """A count of at least one — `idle` ticks, `budget` turns — or a refusal."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ServerError("%s is an int of at least 1, not %r" % (what, value))
    return value


def _settled(state):
    """Whether this connection is over: the machine closed it, or the loop did.

    Two things can end a connection and they are not the same thing. `finish` is
    the read side saying the client has nothing left to send and has taken every
    answer; the timeout closes a connection whose client has stopped reading.
    Either way the machine is not stepped again — a `step_conn` on a connection
    the link has closed is an `"idle"` step, and a loop that took it for a finish
    would report a client as served when nobody served it.
    """
    return state["state"] == "closed" or state["conn"].closed


def _over(world, machines):
    """Whether the run is over: the listener holds nobody, and nothing is open.

    The backlog counts as much as the machines do: a client that has not arrived
    yet is still the listener's to hand over, and a loop that stopped because the
    connections it happened to hold were settled would leave that client's
    requests unanswered for no reason at all.
    """
    return (not world.waiting()
            and all(_settled(state) for state in machines.values()))


def serve_with_timeouts(server, *, idle=DEFAULT_IDLE, budget=DEFAULT_BUDGET):
    """The event loop: one turn of every connection, and a deadline per idle one.

    A turn is: at most one `accept`, one move for each connection the loop holds
    (stage 1's `step_conn`, and `finish` the moment a machine reaches `"closing"`),
    a deadline armed on the tick a connection goes idle and disarmed on the tick it
    has something to do again, the deadlines that have come due, and one
    `Link.step`. `steps` counts the turns and `ticks` is the clock's own reading,
    because both are honest numbers and neither is a duration.

    `answers` is what the server answered, per client in accept order: a client the
    loop never got to — an arrival past the budget — answers with an empty tuple
    rather than being left out, so two runs of one workload have the same shape.
    `served` is the clients whose conversation ran to a finish, in completion
    order, and `timed_out` the clients the loop closed for idling, in the order
    their deadlines came due. A client in `timed_out` is not a client in `served`:
    its answer is in `answers` if the server wrote one, and the link's log says the
    client never drained it — which is what a timeout *is*, and why closing an idle
    connection is not a finish.

    A `budget` spent with work left returns early, naming what it did and did not
    do; nothing here raises because a client stopped reading, and nothing here
    reads a clock other than the link's.
    """
    world = _server(server)
    wait = _count(idle, "idle")
    limits = _count(budget, "budget")

    timers = Timers(world.clock)
    machines = {}          # name -> the machine driving that connection
    alarms = {}            # name -> the handle of the timeout armed for it
    staged = {}            # name -> the reply bytes not all handed over yet
    replies = {conn.client.name: [] for conn in world.conns()}
    served = []            # the clients that reached a finish, in order
    timed_out = []         # the clients closed for idling, in deadline order
    steps = 0

    while steps < limits:
        steps += 1

        conn = world.accept()
        if conn is not None:
            name = conn.client.name
            machines[name] = stage_01.open_conn(world, conn.id)
            alarms[name] = None
            staged[name] = b""

        for name in machines:
            state = machines[name]
            if _settled(state):
                continue
            move = stage_01.step_conn(world, state)
            machines[name] = move
            staged[name] += move["reply"]
            if move["state"] == "closing":
                machines[name] = stage_01.finish(world, move)
                served.append(name)
            elif move["event"] == "write" and not move["out"]:
                replies[name].append(staged[name])
                staged[name] = b""

        for name in machines:
            busy = _settled(machines[name]) or not world.idle(machines[name]["conn"])
            if busy:
                if alarms[name] is not None:
                    timers.cancel(alarms[name])
                    alarms[name] = None
            elif alarms[name] is None:
                alarms[name] = timers.arm(world.now() + wait, name)

        for handle, name in timers.due():
            world.close(machines[name]["conn"])
            timed_out.append(name)

        if _over(world, machines):
            break
        world.step(1)

    return {"answers": {name: tuple(replies[name]) for name in replies},
            "steps": steps,
            "ticks": world.now(),
            "timed_out": tuple(timed_out),
            "served": tuple(served)}