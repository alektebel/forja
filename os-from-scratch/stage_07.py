"""OS From Scratch — stage 7: The scheduler, and the wakeup that never came.

The scheduler is a function of the tick and the tasks it is handed, and the whole
stage is the difference between two ways of sleeping. `block` is the naive one and
it is here on purpose: it enqueues a task on a wait queue and marks it blocked,
and it never looks back — so a wakeup that landed between the caller's own
condition check and that call finds nobody waiting, and the task sleeps forever.
`wait_on` is the same sleep with one more look: it evaluates the condition,
enqueues only when it is false, and evaluates it again *after* the enqueue, so a
wakeup that arrived in between is still seen and the task is taken straight back
off the queue and stays ready. Those three steps in that order are the fix, and
`enqueueing before checking`, `the condition evaluated only once` and `block used
instead of wait_on` are the three ways to lose it anyway.

The other half is the pick. A ready task is chosen by
`(priority - waited // AGEING, queue position)`, lowest first: ageing is what
stops a low-priority task from never running at all, and the queue position is
what makes the run queue FIFO among equals. `waited` is the ticks a task has spent
in the run queue without being picked, and it starts again at zero the moment the
task is enqueued. The quantum is the ticks a task runs before it goes to the back
of the queue; nothing here is timed, the tick is handed in, and a tick on which
nothing was ready is a tick in the trace all the same.

    AGEING      the ticks of waiting that buy one point of priority
    Scheduler   the run queue, the wait queues, and the pick
    wait_on     the sleep that checks, enqueues, and checks again

`Scheduler` keeps pids in its queues and the task dicts it was handed in
`self.tasks`; `step`/`run` refresh that view from the `tasks` mapping they are
given, so a caller that replaces a task's dict mid-run is seen. `queues()` is the
world's view of both queues — the run queue under `"ready"`, every wait queue
under its own name — and `log()` is the kernel's own ledger, every enqueue,
dequeue, block, wake and tick it decided. A blocked, zombie or dead task is never
scheduled, and a task this scheduler does not hold cannot block, be removed or be
picked.

DESIGN DECISION — why is the buggy `block` shipped at all?
Because the mistake this stage exists for is not a missing line, it is a
*caller's* line, and the only honest way to teach it is to ship both forms and let
the check run the same race through each. A course that shipped only `wait_on`
would teach the API and not the failure; the failure is what every later stage
inherits, because a scheduler that cannot lose a wakeup is what makes a device
interrupt and a blocked pipe safe.

DESIGN DECISION — why does `wait_on` re-check after the enqueue, rather than
check and enqueue as one indivisible step?
Because this machine has no lock yet — two CPUs and the critical section are
stage 8 — and pretending a check and an enqueue cannot be separated is exactly the
lie that loses the wakeup. The re-check is cheap and it is enough: whatever landed
between the two evaluations leaves the condition true, and the task takes itself
back off the queue. It is also why the caller must not evaluate the condition
itself first and then call `block`: the window the caller opens is the one nothing
inside `wait_on` can close.

DESIGN DECISION — why is the pick `(priority - waited // AGEING, queue
position)` when a priority number would be enough?
A strict priority picks the same task for ever, which is a scheduler that never
runs the low-priority task at all — starvation, invisible in a short trace and
absolute in a long one. Ageing buys a point of priority for every `AGEING` ticks
of waiting, so the low-priority task eventually wins, and the queue position
breaks the ties among equals in arrival order. Both halves are observable: the
check runs a priority-0 task beside a priority-8 one for eight ticks (the
priority-8 one starves) and for seventy-two (it runs exactly once).

DESIGN DECISION — why is the tick handed to `step` rather than read from a clock?
Because a scheduler that reads a clock cannot be graded: `machine.Timer` exists
and is *the* way time passes in this course, but who advances it is the caller,
and a `step` that consulted it would be a different function each run. The tick
argument is what makes the pick, the quantum and the trace a pure function of the
run, and it is why nothing in this stage sleeps, polls or times out.

DESIGN DECISION — why does `wake` take a value it does not use to choose anybody?
Because a wakeup in this machine is an *event*, not a search: it wakes the tasks
that were waiting on that queue at that moment, in pid order, and the value is the
thing the caller will compare against its own state — the sector, the sequence
number, the byte — which is exactly what the lost-wakeup bug gets wrong. Making
`wake` filter by value would hide the bug: the task that sleeps after the event
would be skipped either way, and the check could not tell the two apart.

TODO: implement `AGEING`, `SchedError`, `Scheduler` and `wait_on`.
"""

AGEING = 8


class SchedError(ValueError):
    """A caller's mistake about a queue: a pid, a tick, a name, a quantum."""


class Scheduler:
    """The run queue, the wait queues, and the pick.

    The run queue is a list of pids in arrival order; `waits` maps a wait queue's
    name to the pids sleeping on it, also in arrival order. `running` is the pid
    executing right now (``None`` when nobody is), `left` is the ticks it still
    has in its quantum, `waited` is how long each ready pid has waited without
    being picked, and `switches` counts the times the task that ran changed.
    """

    def __init__(self, quantum=3):
        """A scheduler whose tasks run `quantum` ticks before the queue rotates."""
        raise NotImplementedError("stage 7: implement Scheduler.__init__()")

    def add(self, task):
        """Put a task in the run queue, ready to be picked.

        A pid this scheduler already holds is refused: a task is queued once, and
        a queue that holds the same pid twice runs it twice for one arrival.
        """
        raise NotImplementedError("stage 7: implement Scheduler.add()")

    def remove(self, task):
        """Take a task out of the scheduler: off the run queue and off every wait.

        A task the scheduler does not hold is refused naming its pid; a task that
        was waiting is dropped from its queue, so no later `wake` can wake what is
        no longer there.
        """
        raise NotImplementedError("stage 7: implement Scheduler.remove()")

    def block(self, task, reason):
        """Sleep, the naive way: enqueue and block, and never look back.

        This is the bug the stage exists for and it is deliberately available. A
        wakeup that arrived between the caller's condition check and this call
        finds nobody on the queue, and the task is not woken by it — which is why
        `wait_on` exists, and why the check that matters is the caller's, not this
        one's.
        """
        raise NotImplementedError("stage 7: implement Scheduler.block()")

    def wake(self, queue, value):
        """Wake every task waiting on `queue` at this moment, in pid order.

        They come off the queue and go to the back of the run queue, ready to be
        picked — which is why the caller may wake a queue more than once and a
        task woken once is never woken by the second call.
        """
        raise NotImplementedError("stage 7: implement Scheduler.wake()")

    def step(self, tick, tasks):
        """Run the next ready task for one tick and say who that was.

        `tasks` is the caller's table of live tasks, `pid -> task`; the scheduler
        refreshes its own view from it, so a task whose state or priority changed
        is seen at the tick it changed. A blocked, zombie or dead task is never
        scheduled, and a tick on which nothing was ready runs nobody.
        """
        raise NotImplementedError("stage 7: implement Scheduler.step()")

    def run(self, ticks, tasks):
        """Every tick of a run: the trace, the switches, the ticks per pid.

        A tick where nothing was ready is in the trace as ``None``, and a task
        that was in the run queue for the whole run without ever being picked is
        `starved` — which is what ageing is for and what a run short enough to
        starve one proves.
        """
        raise NotImplementedError("stage 7: implement Scheduler.run()")

    def queues(self):
        """The run queue and the wait queues, by name.

        `"ready"` is the run queue in arrival order — the order the next tick
        picks in among equals — and every wait queue is under its own name, also
        in arrival order. A queue nobody waits on is not a queue.
        """
        raise NotImplementedError("stage 7: implement Scheduler.queues()")

    def log(self):
        """The kernel's own ledger, in the order it wrote it."""
        raise NotImplementedError("stage 7: implement Scheduler.log()")


def wait_on(sched, task, queue, condition):
    """Sleep until `condition(task)` holds, and do not lose the wakeup in between.

    The three steps, in this order, are the whole fix: evaluate the condition;
    enqueue the task only if it is false; evaluate it *again* after the enqueue,
    and take the task back off the queue if it is true now. A caller that checks
    and then sleeps — `block` — loses a wakeup that landed between those two
    moments, and the task never runs again.
    """
    raise NotImplementedError("stage 7: implement wait_on()")
