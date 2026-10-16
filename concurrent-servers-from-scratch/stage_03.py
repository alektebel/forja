"""Concurrent Servers From Scratch — stage 3: Threads, and the interleaving the check chooses.

Stage 2 served one client at a time, to completion, and the slow client stopped
everyone behind it. The repair is not a thread library: it is *concurrency as a
choice* — N connections, each carried by something that does one small step and
gives the processor back, and an order that is data somebody handed in rather
than luck. That "something" is a *step function*: called once per turn, it owns
no stack, keeps whatever it needs between turns in the arguments it was spawned
with, and answers exactly one of `"more"`, `"blocked"` or `"done"`. This stage is
the machinery behind that word — `Scheduler` — and the policy that uses it, one
thread per connection over stage 1's state machine.

Why the interleaving is data: a real thread library hands the order to the
operating system, so the run that failed is not reproducible and the run that
passed is not evidence. Here the *script* is a tuple of thread names, the check
chooses it, and the result says what the choice cost — `steps` is the number of
turns taken and `order` is the order the answers went out. A blocked thread is a
verdict rather than an exception: a thread waiting for something another thread
must do is fine, and a round in which *every* remaining thread is waiting is a
deadlock, reported with the names.

`threading`, `asyncio` and `time` are banned in this course for exactly this
reason: the interleaving is the subject, the clock is the link's, and the model
is a loop the caller can drive. What a step function must *not* do: spin on a
read that will never return anything, close a connection it has not finished
answering, or keep its state in a module-level variable where the next run can
find it.

    STEP_STATES  the three answers a step function may give
    THREAD_STATES what the scheduler calls a thread between turns
    Scheduler    spawn, ready, step, run: N step functions and whose turn it is
    serve_threads  one thread per connection, with the script as the interleaving

`ServerError` is the family, and every refusal names the offender: the name that
is not a name, the step function that is not callable, the name already spawned,
the script entry nobody spawned, the turn for a thread that has finished, the
answer that is not one of `STEP_STATES`, the budget that is not a count, and the
`server` whose three pieces do not describe one workload. A verdict about what
the *threads* did — blocked, deadlocked, starved — is always returned, never
raised.

DESIGN DECISION — what does a thread keep, given that it has no stack?
The alternative is a closure or a module-level table, and both are worse in the
same way: a closure hides the state where a check cannot see it, and a module
table means two runs of the same workload are not two runs. So `spawn(name, fn,
*args)` calls `fn(*args)` and the state a thread carries between turns lives in
those arguments — for `serve_threads`, one context per connection holding stage
1's machine, the reply it is halfway through writing, and the lists it reports
into. A step function is then a plain function of its own memory, which is
exactly what makes it testable one turn at a time.

DESIGN DECISION — is `"blocked"` a death sentence or a round verdict?
It is a round verdict, and the difference is the whole point: a thread blocked
waiting for another thread's turn has to get that turn back once the others have
had theirs, or nothing would ever unblock it. So a blocked thread is skipped by
the round-robin, a scripted turn for one is spent without calling anything, and
the block is cleared when every remaining thread has been offered a turn — *unless*
the whole round blocked, which is a deadlock and is returned as
`{"finished": False, "blocked": (names…)}` rather than cleared away.

DESIGN DECISION — why does the scheduler know nothing about the link?
Because the two questions are separable, and keeping them apart is what makes
this stage reusable: `Scheduler` counts turns and holds state, and the world
moves only when a thread spends a turn on `Link.step()`. The alternative — a
scheduler that ticks the clock itself — would make `serve_threads` the only
model it can ever drive, and stage 7's loop, which is this same loop desugared,
would need its own copy.

DESIGN DECISION — who spends a turn when a connection's thread has nothing to move?
`serve_threads` spends it on the world's tick. A client drains its inbox on its
own schedule and the link carries an outbox only when the clock moves, so a
thread that had nothing to move and simply answered `"blocked"` would be waiting
for a turn that nobody has any reason to take. The tick is therefore the model's
wait — and because it is counted, a model that waits too much cannot hide it.

DESIGN DECISION — why report `"state"` and `"yielded"` when one is derived from the other?
Because the two vocabularies answer different questions: `"yielded"` is what the
step function said (`"more"`, `"blocked"`, `"done"`) and `"state"` is where the
scheduler records the thread (`"ready"`, `"blocked"`, `"done"`). A caller that
only has the second cannot tell a turn that was taken from a turn that was
skipped — a skipped turn yields `None` — and a check that cannot tell those apart
cannot see a thread counted as a step when it never ran.

TODO: implement `Scheduler` (`__init__`, `spawn`, `ready`, `step`, `run`) and
`serve_threads`.
"""

import link
import stage_01

#: The three answers a step function may give: it has more to do, it is waiting
#: for something another thread must do, or it has finished. Nothing else — a
#: step function that forgets to answer is refused rather than counted.
STEP_STATES = ("more", "blocked", "done")

#: What the scheduler calls a thread between turns: it can run now, it is waiting
#: on the round, or it is done. `"more"` becomes `"ready"`; the other two answers
#: *are* the states they leave behind. The two vocabularies are kept apart on
#: purpose: `step` reports both, so a check holds them against each other instead
#: of inferring one from the other.
THREAD_STATES = ("ready", "blocked", "done")


class ServerError(ValueError):
    """A thread the scheduler will not spawn, a turn it will not take, a bundle it cannot drive.

    It is the family for every shape this stage cannot honour: a name that is not
    a non-empty string, a step function that is not callable, a name already
    spawned, a script that is not a sequence of names, a turn for a thread nobody
    spawned or for one that has finished, a step function that answers something
    that is not one of `STEP_STATES`, a `budget` that is not a count of turns, and
    a `server` whose three pieces do not describe one workload. A verdict about
    what the *threads* did is never an exception: a blocked thread, a deadlocked
    round and a budget spent are all returned, and a check asserts them as values.
    """


class Scheduler:
    """N step functions, and whose turn it is — chosen by the caller, not by luck.

    A thread is a step function: `spawn` takes it, `step` calls it once, and what
    it answers (`"more"`, `"blocked"`, `"done"`) is the whole of its state between
    turns. There is no stack, no thread library and no clock of its own: the
    interleaving is a `script` of names, or round-robin in spawn order, and the
    caller can hold either one against the run's own result.

    The scheduler is deliberately ignorant of the world it may be driving: it
    never steps a link and never looks at a connection, so `serve_threads` here —
    and stage 7's `Loop`, which is the same loop desugared — can put whatever
    policy they like on top of the same four methods.
    """

    def __init__(self, script=None):
        """A scheduler over no threads, with the interleaving the caller chose.

        `script` is a tuple of thread names: the turn each entry of the run takes,
        in order. A script that runs out is not an error — the rest of the run is
        round-robin from the spawn order — so a script is the prefix the check
        chose and never a ceiling. Without a script every turn is round-robin.
        """
        raise NotImplementedError("stage 3: implement Scheduler.__init__()")

    def spawn(self, name, fn, *args):
        """Spawn `name`'s step function and hand back its handle, from 1 upwards.

        `fn` is called as `fn(*args)` — once per turn, and whatever it keeps
        between turns it keeps in those arguments, since it has no stack — and it
        answers one of `STEP_STATES`. The handle is the thread's identity in
        `ready()` and in every `step()` answer: handles are given in spawn order
        and never reused, so a handle is stable even when a thread spawns another
        one mid-run. A name that is not a non-empty string, a `fn` that is not
        callable, and a name already spawned are each refused naming what was
        given — a script picks a turn by *name*, so two threads may not share one.
        """
        raise NotImplementedError("stage 3: implement Scheduler.spawn()")

    def ready(self):
        """The handles that can run now, in spawn order.

        A thread is ready when it has neither finished nor answered `"blocked"`:
        `"blocked"` is exactly "not now", and a thread given a turn it cannot use
        is a thread the scheduler is spinning on. Blocked is a *round* verdict
        rather than a death sentence, so a thread that answered `"blocked"` is
        ready again once every remaining thread has had its turn: the others'
        work — or the turn each of them spends on the world — is what a waiter is
        waiting for.
        """
        raise NotImplementedError("stage 3: implement Scheduler.ready()")

    def step(self):
        """The next turn: one step function called once, or one turn skipped.

        Whose turn it is comes from the script while it has entries left and from
        the round-robin afterwards. The answer is `{"handle", "name", "state",
        "yielded"}`: `yielded` is what the step function itself answered — one of
        `STEP_STATES` — and `state` is where that answer leaves the thread
        (`"more"` → `"ready"`, the other two themselves). A thread that is already
        blocked is *skipped*: the turn is offered, nothing is called, and `yielded`
        is `None`, which is how a caller can tell a turn that was spent from a
        turn that was taken.

        Three shape mismatches are refusals rather than verdicts, each naming the
        offender: a script entry that names a thread nobody spawned, a turn for a
        thread that has already finished — the script's rhythm and the run's no
        longer agree, and carrying on would quietly report an order nobody chose —
        and a step function that answers something that is not one of
        `STEP_STATES`. A turn when there is no thread left at all is refused too:
        there is nothing to run, and that is not a verdict about content.
        """
        raise NotImplementedError("stage 3: implement Scheduler.step()")

    def run(self, *, budget):
        """Run the threads until they are done, blocked everywhere, or out of budget.

        The answer is `{"finished", "steps", "order", "blocked"}`: `order` is the
        names in the order the threads *finished* — the answering order, not the
        spawn order — and `blocked` is who was waiting when the run stopped.
        `finished` is `True` only when every thread answered `"done"`.

        Two ways to stop early, and neither is an exception. A round in which every
        remaining thread answered `"blocked"` is a deadlock: no thread can run,
        and the turns a waiter waits for are not coming — the run returns the
        names instead of spinning. `budget` bounds the step count and is checked
        *before* a turn and never after, so a run that hits the bound took exactly
        `budget` steps; a skipped turn is not a step, because nothing was called.

        The script is consulted only while a turn is left to take, so a script
        longer than the work is harmless; one that names a finished thread *while
        work remains* is the refusal `step` describes, and it is raised rather than
        absorbed because the rest of the run would otherwise come out in an order
        nobody chose.
        """
        raise NotImplementedError("stage 3: implement Scheduler.run()")


def serve_threads(server, *, script=None, budget=256):
    """The same server as `serve_blocking`, one thread per connection.

    `server` is the bundle stage 2 drives — `{"link", "clients", "requests"}`: the
    world, the scripted clients in the order they arrived, and the request lines
    each will send. One thread is spawned per client, named after it, and each
    thread owns stage 1's machine for its own connection: a turn is one move of
    that machine, and a turn with no move to make spends itself on the link's tick.
    The script names clients, so it *is* the interleaving — `("slow", "fast",
    "fast", …)` is a run in which the slow client answers first — and without one
    the turns are round-robin from the accept order.

    The answer is `serve_blocking`'s — `{"answers", "steps", "ticks", "served",
    "starved"}` — plus `"order"`: the names in the order the answers went out.
    `served` says who finished, `order` says when each answer was delivered, so the
    interleaving the script chose is visible in the result rather than inferred
    from it; `starved` is the clients the budget left unanswered, `ticks` is what
    the link's clock spent on waiting, and `answers` is what this model wrote — a
    reply the outbox never took is caught by the link's own log, not by this dict.
    """
    raise NotImplementedError("stage 3: implement serve_threads()")
