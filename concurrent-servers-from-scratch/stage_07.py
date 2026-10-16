"""Concurrent Servers From Scratch — stage 7: Futures and async/await as a desugaring.

`async` and `await` are not a runtime, they are a *desugaring*. A coroutine is a
step function that answers `{"wait": True}` while it cannot go on and
`{"value": …}` when it can; `await` is a function that decides which of the two a
future has earned; and the loop that calls those step functions is the very event
loop stages 4 to 6 already built. This stage writes that desugaring out in full,
with **no `async def` anywhere** and `asyncio` banned outright, because the thing
worth knowing is that a promise, a yield and a driver are three pieces of *data*
— and that the loop was never the magic part.

The three pieces, in the order they meet. A `Future` is one answer, settled once:
a second `settle` is a refusal, `value()` before it is settled is a refusal, and
`result()` is how a caller asks *without* an exception — `{"done", "value"}`, the
question a `then` callback asks. `await_` is the whole of the `await` keyword:
handed a settled future it answers `{"value": …}`, handed one that is not it
answers `{"wait": True}`, and that dict is exactly a step function's answer, so a
coroutine written by hand is `lambda: await_(future)` and nothing else. `chain` is
the smallest driver there is — one coroutine, stepped to its answer — and `Loop`
is the real one: many coroutines, an order the *check* chooses, and a budget in
steps.

Then the server, which is the point of the whole course: `serve_async` accepts
every client the link is holding, gives each connection a coroutine that drives
stage 1's state machine, and lets the loop drive them. Nothing here is a thread
and nothing here sleeps: `Link.step()` is the only thing that moves a byte, so
the driver steps the world between turns, and every number in the result — the
steps, the ticks, the four orders — is recomputable from what the link logged.

DESIGN DECISION — why is a coroutine a step function answering a dict, instead of
an `async def` and a real `await`?
    Because the loop is the subject and `async def` hides it. A coroutine that is
    a step function can be called by anybody, in any order, any number of times —
    which is exactly what a check needs in order to *choose* the interleaving —
    and "am I ready" stops being a language feature and becomes a dict this stage
    can assert on. `asyncio` is banned here for the same reason `threading` was
    banned in stage 3: a course that cannot step its own concurrency cannot
    report a step count, and the step count is the only honest score there is.

DESIGN DECISION — why is a future settled exactly once, and what does `result()`
buy that `value()` does not?
    A promise that can change its answer is not a promise: a coroutine that
    resumed on the first settlement could be resumed again on the second, and the
    bug reads as "the callback ran twice" long after the second `settle` went in.
    Settling once, and *refusing* the second with the value the future already
    holds in the message, makes that impossible rather than unlikely. And the two
    reads are two different questions: `value()` is for the caller that has
    already asked `done()` and wants to be told when it was wrong, while
    `result()` is for the caller that must not raise — `{"done": False, "value":
    None}` is an answer about an unsettled future, and every callback written
    against a promise needs that answer.

DESIGN DECISION — what is `chain` for, when `Loop` already drives coroutines, and
why does it have a bound?
    `chain` is the one-coroutine case, and it is where the desugaring is easiest
    to see: a coroutine that answers `{"wait": True}` forever is a coroutine
    waiting on a future nobody settled, and a coroutine that answers on its first
    call is an `await` on a settled one. The bound is because `chain` has no world
    to drive: it cannot settle anything, so a coroutine that never answers would
    step forever, and "waiting" is the honest verdict after `MAX_CHAIN` steps
    rather than a hang. Bounded waiting is the loop's job, and the loop has a
    budget; the chain's job is to say where one coroutine got to.

DESIGN DECISION — why does the loop take its order as data (a `script`), and what
does it owe a coroutine that answered `{"wait": True}`?
    Because the interleaving is the one thing a model must not invent: it is what
    the check chooses and what the step count is a count *of*. The default is
    round-robin from the spawn order, which is what a thread scheduler does; a
    script is the same loop with the order supplied — and it makes the difference
    between "answered first" and "spawned first" observable, which is the whole
    reason `values` and `order` are reported in completion order rather than in
    spawn order. A wait is a *step that moved nothing* and is therefore counted
    like any other; a coroutine that has answered a value is never called again,
    because the second call is the mistake this stage exists to make impossible.

DESIGN DECISION — why is a connection a coroutine that drives stage 1's machine,
rather than a state machine of its own?
    Because the machine is already written, already checked, and knows the two
    things this stage's coroutine must not re-learn: when a line is whole and when
    the read side is over. What a coroutine adds is *where it waits* — the machine
    says `"idle"`, the coroutine turns that into `{"wait": True}`, and closing is
    the last step. So the two stages are the same server at two resolutions: stage
    1 hands out one move at a time and lets the caller choose, and this stage
    hands out one coroutine per connection and lets the loop choose.

DESIGN DECISION — why does `serve_async` report four orders and not one, and what
is `starved`?
    "Answered", "finished" and "spawned" are three different orders and a result
    that conflates them cannot be held against another model: a reply goes out
    when its last byte is in the outbox, but the connection is not finished until
    the client has taken it, and a slow reader makes those two orders differ while
    the spawn order differs from both. `order` is the answering order, `served`
    the completion order, `values` the answers in completion order — and `starved`
    is not "everybody who is not served": it is the client whose *request the link
    is still holding* when the budget ran out, which is the only definition a
    budgeted run can honestly report.

TODO: implement `Future`, `await_`, `chain`, `Loop` and `serve_async`.
"""

#: The longest chain `chain` drives before it reports the coroutine as still
#: waiting: `MAX_CHAIN` steps. A coroutine that has not answered by then is
#: waiting on the world rather than on itself, and the world is the loop's
#: business — `Loop.run` takes a budget, `chain` has nothing to budget against.
MAX_CHAIN = 64

#: The two states a chain can end in, in the order a coroutine meets them: a
#: coroutine that answered `{"wait": True}` is `"waiting"`, and one that answered
#: a value is `"done"`. The names are the tuple's, so a check can pin them
#: without reaching into the code that produced them.
CHAIN_STATES = ("waiting", "done")


class ServerError(ValueError):
    """A future, a coroutine or a loop this stage will not drive, named as what is wrong.

    It is the family for every shape the desugaring cannot honour: a second
    `settle` on a future that already holds an answer, a `value()` before there is
    one, an `await_` of something that is not a `Future`, a coroutine that answers
    neither `{"wait": True}` nor `{"value": …}`, a script that names a coroutine
    that was never spawned, a budget that is not a whole number of steps, and a
    server bundle that is not one. A verdict about an *answer* is never an
    exception: an unsettled future, a coroutine still waiting and a client whose
    request never went out are all values this stage returns.
    """


class Future:
    """One answer, settled exactly once, read in two ways: `value` or `result`.

    A future is not a value with a flag on it; it is the *promise* that the value
    will be there, which is why `done()` is a question of its own and why the two
    reads disagree: `value()` raises while the future is unsettled, and `result()`
    answers `{"done": False, "value": None}` instead. The value is any object —
    including `None` and `b""` — so a future is done because it was *settled* and
    never because its answer happens to look empty.
    """

    def __init__(self):
        """A future with no answer yet: not settled, and holding nothing.

        Every future starts here, and the two fields are the whole object: whether
        it has been settled, and what it was settled with. Nothing else in this
        stage writes them, and nothing reads the value without asking first.
        """
        raise NotImplementedError("stage 7: implement Future.__init__()")

    def settle(self, value):
        """Give the future its answer — once, and never again.

        This is the move that resumes whatever awaited the future, so a second
        `settle` is refused with `ServerError` naming the answer the future
        already holds: two settlements are two resumptions, and a coroutine that
        runs its second half twice is the failure a promise exists to prevent.
        `None` and `b""` are values like any other.
        """
        raise NotImplementedError("stage 7: implement Future.settle()")

    def done(self):
        """Whether the future has been settled — the question `await_` asks.

        It answers about the *settlement*, not about the value: a future settled
        with `None` is done, and one holding `b""` is done too.
        """
        raise NotImplementedError("stage 7: implement Future.done()")

    def value(self):
        """The answer, refusing to invent one while the future is unsettled.

        This is the read for a caller that has already asked `done()` — and the
        refusal, naming that the future is unsettled, is how such a caller finds
        out that it asked too early. A caller that must not raise uses `result()`.
        """
        raise NotImplementedError("stage 7: implement Future.value()")

    def result(self):
        """`{"done", "value"}` — the non-raising read, in that order.

        While the future is unsettled the answer is `{"done": False, "value":
        None}`: there is nothing to raise about, because the question was "did it
        settle", not "what is the answer". This is the shape a callback is handed
        and the shape a check compares.
        """
        raise NotImplementedError("stage 7: implement Future.result()")


def await_(future):
    """`await` as a function: `{"wait": True}` until settled, then `{"value": …}`.

    The answer is a *step function's* answer, so this one function is the whole of
    the desugaring: a coroutine awaiting a future is a step function that returns
    exactly this, the loop reads `"wait"` as "not ready, come back" and `"value"`
    as "here is the answer, and never come back". An unsettled future yields
    exactly `{"wait": True}` — not a value, not a flag, not polling — and a settled
    one yields the value itself, `None` and `b""` included. Anything that is not a
    `Future` is refused, naming it.
    """
    raise NotImplementedError("stage 7: implement await_()")


def chain(coro):
    """Drive one coroutine's chain of steps to its answer, or to `MAX_CHAIN`.

    `coro` is a coroutine — a step function — and `chain` calls it one step at a
    time: `{"wait": True}` means there is more chain to come, `{"value": …}` means
    this is the answer. The result is `{"state", "value", "steps"}`: `"state"` is
    `"done"` with the value the coroutine answered, or `"waiting"` with `None`
    after `MAX_CHAIN` steps, and `"steps"` is how many times the coroutine was
    called. A coroutine that answers neither shape — and anything that is not
    callable — is refused, naming what was given.
    """
    raise NotImplementedError("stage 7: implement chain()")


class Loop:
    """The driver: coroutines as step functions, an order, and a step count.

    `script` is the order the loop visits its coroutines, cycled: a sequence of
    the names `spawn` was given, or `None` for round-robin from the spawn order.
    That order is *data the caller supplies* — this stage never invents an
    interleaving — and a script that names a coroutine that was never spawned is
    refused, naming it. A coroutine that has answered a value is finished and is
    never called again; a wait costs a step and changes nothing.
    """

    def __init__(self, script=None):
        """A loop with a visit order and no coroutines yet.

        `script` is `None` for round-robin from the spawn order, or a sequence of
        coroutine names giving the order to visit them in, cycled. A script that
        is a bare string, or holds something that is not a non-empty name, is
        refused, naming what was given: the order is a list of names and nothing
        else.
        """
        raise NotImplementedError("stage 7: implement Loop.__init__()")

    def spawn(self, name, coro):
        """Register the step function `coro` under `name`; the handle is its order.

        A name is a non-empty string that no other coroutine has been spawned
        with, and a coroutine is callable; anything else is refused, naming the
        offender. The handle is 1 for the first spawn, 2 for the next, and so on
        — the spawn order the default script is the round-robin of.
        """
        raise NotImplementedError("stage 7: implement Loop.spawn()")

    def run(self, *, budget):
        """Drive the coroutines for at most `budget` steps, and say where they got to.

        One step is one coroutine called once. The answer is `{"values", "steps",
        "order", "done"}`: `"values"` is every value a coroutine has answered,
        keyed by name *in completion order*, `"order"` the same names as a tuple
        in the same order, `"steps"` what this run cost, and `"done"` whether
        every coroutine has answered. A wait is a step like any other, a finished
        coroutine is not called again, and a budget that is not a whole number of
        steps of at least one is refused, naming it.
        """
        raise NotImplementedError("stage 7: implement Loop.run()")


def serve_async(server, *, script=None, budget=256):
    """The server again, driven by the loop: one coroutine per connection.

    `server` is the world and its scripted clients — `{"link", "clients",
    "requests"}`, the bundle stages 2 to 6 are handed as well. Every client the
    link is holding is accepted and given a coroutine that drives stage 1's
    machine to `"closing"` and then closes the connection. The driver takes the
    loop's turns, one step at a time, and steps the link between them, because
    `Link.step()` is the only thing in this world that moves a byte.

    The answer is `{"answers", "steps", "ticks", "served", "starved", "order",
    "values"}`: `"answers"` is each client's replies in accept order, `"steps"`
    what the driver cost, `"ticks"` the link's own clock, `"served"` the
    completion order, `"starved"` the clients whose request the link is still
    holding, `"order"` the answering order — one entry per reply that went out —
    and `"values"` the answers in completion order. `script` is the loop's visit
    order and `budget` is in steps: a budget spent with work left is a result and
    not an exception, and `starved` is what says so.
    """
    raise NotImplementedError("stage 7: implement serve_async()")
