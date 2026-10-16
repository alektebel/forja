"""Concurrent Servers From Scratch — stage 5: The event loop and its timers.

A reactor waits for bytes. An event loop waits for bytes *and for time*, and time
does not arrive as readiness — it arrives as a deadline. `Timers` is the queue
those deadlines live in: monotonic, on a clock it is handed rather than one it
reads, and answering three questions only — what is due, what is next, and what
has been disarmed. `serve_with_timeouts` is the loop that reads it: one turn of
every connection it holds, a deadline armed on the tick a connection goes idle,
and the close that deadline earns.

The close is the decision this stage exists for. A connection that has sat idle
for long enough is closed **while its client still has requests left**, and that
is a timeout — not a finish. A finish says the read side is over and every answer
has been taken; a timeout says the client stopped reading, and the answer it never
took is still in its inbox. The two are the same call to `Link.close` and
completely different verdicts, which is why a run reports `served` and `timed_out`
as two tuples and why they can never name the same client.

The world is still `link.py`: `Link.step()` is the only thing that moves a tick
or a byte, `Link.idle(conn)` is the world's own answer to "has this connection
anything for the server to do?", and the per-connection machine is stage 1's. What
this stage adds is the second input an event loop has and a reactor does not, and
the arithmetic of it is all in ticks:

    DEFAULT_IDLE  how many ticks of idleness close a connection, by default
    DEFAULT_BUDGET  how many turns a run takes before it reports what it did
    Timers        the deadlines of one loop, on the clock it was handed
    serve_with_timeouts  the loop: accept, step, arm, disarm, close, tick

`ServerError` is the family, and every refusal names the offender: a `server` that
is not the dict of the contract, a `link` that is not a `link.Link`, an `idle` or
a `budget` that is not a positive int, a clock that answers no `now()`, a deadline
that is not an int, a timer name that is not a non-empty string, a handle that is
not an int. A verdict about what a *client* did is never an exception: a client
that stops reading is a timeout, and a timer that is cancelled is simply gone.

DESIGN DECISION — why is the clock injected instead of read, and why is the queue
never sorted?
Because this entire course reports steps and ticks instead of seconds: the only
clock is the link's, `Link.step()` is the only thing that moves it, and a run that
repeated must repeat byte for byte. A queue that read a wall clock could not be
checked at all, and a sorted list would have to be re-sorted on every arm — while
the deadlines are already ordered by construction, so the honest structure is a
heap keyed on the deadline. `Timers` therefore takes whatever answers `now()` and
never asks who it is.

DESIGN DECISION — why does the queue key on `(when, handle)` and not on `when`
alone?
Because two connections can go idle on the same tick, both deserve their own
deadline, and a run has to be able to say *which* of them timed out first. Keying
on the pair keeps one timer per arm — two deadlines that are equal come out in the
order they were armed, which is the order the connections were taken — and it
makes the handle part of the answer rather than a secret index: `due()` hands back
`(handle, name)` pairs, and the name is whatever the loop wanted to be able to
report.

DESIGN DECISION — why does `due()` compare `<=` and remove what it returns,
instead of scanning for everything at or before now?
Because a deadline is a tick the clock has *reached*: the `<=` and the `<` differ
by a whole tick of idleness, and one tick is the boundary between "idle long
enough" and "not yet". And because a scan that filters without removing fires the
same timer on every turn — a timeout that closes a connection, and closes it
again, and again — so the pop is not an optimisation, it is the semantics: a timer
that has been returned can never be returned a second time.

DESIGN DECISION — when is the deadline armed, and what disarms it?
On the tick a connection goes idle and not on every turn: the window that times a
client out is a stretch of *consecutive* idle ticks, so a deadline re-armed every
turn would never expire and a deadline armed at the wrong tick would expire one
tick early. It is disarmed by the move that ends the idleness — and by the finish
or the timeout that ends the connection — because a deadline that outlives its
window closes a connection that has since answered, which is the mistake this
whole stage is a check against.

DESIGN DECISION — why is a timeout a close and not a finish, and what does the
loop keep to stay honest about it?
Because `finish` belongs to stage 1's machine and only from `"closing"`, which is
the read side saying the client has nothing left to send and has taken everything
it was sent. A client that has stopped reading reaches no such phase: its reply
may sit half-written or undrained forever. So the loop closes the connection
itself, records the name in `timed_out`, and keeps the two records apart — the
answer it did write stays in `answers` where the log can see that the client never
drained it.

TODO: implement `Timers` (`__init__`, `arm`, `cancel`, `due`, `next_at`) and
`serve_with_timeouts`.
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
        raise NotImplementedError("stage 5: implement Timers.__init__()")

    def arm(self, when, name):
        """Arm `name` for the tick `when`, and hand back the handle.

        Handles are ints that only ever grow, one per armed timer, so a handle is
        also a timer's place in the queue when two deadlines are equal: two
        timers armed for the same tick come due in the order they were armed,
        which is what a loop that arms one deadline per connection relies on to
        be able to say *which* connection timed out first.
        """
        raise NotImplementedError("stage 5: implement Timers.arm()")

    def cancel(self, handle):
        """Disarm the timer `handle`, and answer whether it was still live.

        A handle armed and cancelled is not due, not next and not in the queue any
        more: this is the whole of "a cancelled timer never fires". Cancelling a
        handle that has already fired or was never armed is `False` rather than a
        refusal, because the caller asking about a timer that is gone is asking a
        question and not making a mistake.
        """
        raise NotImplementedError("stage 5: implement Timers.cancel()")

    def due(self):
        """Every timer the clock has reached, as `((handle, name), ...)`.

        In `(when, handle)` order and removed from the queue as it goes, so a
        second call with the clock where it was answers `()`: `due()` is a pop and
        not a scan, and a timer that is returned once can never be returned again.
        The comparison is `<=`: a deadline is due on the tick itself, not on the
        tick after it.
        """
        raise NotImplementedError("stage 5: implement Timers.due()")

    def next_at(self):
        """The earliest deadline still armed, or `None` when there is none.

        Cancelled timers do not count, and neither does the order they were armed
        in: the answer is the smallest deadline, which is the front of the queue
        once the entries of the timers that are gone have been dropped. A deadline
        the clock has already reached is still reported — it is the earliest
        deadline, not the earliest future one — so a loop can ask "how long until
        the next thing happens?" and get the deadline it is already late for.
        """
        raise NotImplementedError("stage 5: implement Timers.next_at()")


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
    raise NotImplementedError("stage 5: implement serve_with_timeouts()")
