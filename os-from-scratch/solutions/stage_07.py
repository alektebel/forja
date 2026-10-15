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

`Scheduler` keeps pids in its queues and the task dicts it was handed in
`self.tasks`; `step`/`run` refresh that view from the `tasks` mapping they are
given, so a caller that replaces a task's dict mid-run is seen. `queues()` is the
world's view of both queues — the run queue under `"ready"`, every wait queue
under its own name — and `log()` is the kernel's own ledger, every enqueue,
dequeue, block, wake and tick it decided. A blocked, zombie or dead task is never
scheduled, and a task this scheduler does not hold cannot block, be removed or be
picked.
"""

AGEING = 8

_READY = "ready"
_RUNNING = "running"
_BLOCKED = "blocked"
_RUN_QUEUE = "ready"


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
        if isinstance(quantum, bool) or not isinstance(quantum, int):
            raise SchedError("a quantum is a number of ticks, not %r" % (quantum,))
        if quantum < 1:
            raise SchedError(
                "quantum %d: a task that is given no ticks never runs" % (quantum,))
        self.quantum = quantum
        self.running = None
        self.last = None
        self.switches = 0
        self.ready = []
        self.waits = {}
        self.tasks = {}
        self.waited = {}
        self.left = {}
        self.records = []

    # -- the doors every public method goes through -------------------------

    def _pid_of(self, task):
        """The pid of a task dict, or a refusal naming what is not one."""
        if not isinstance(task, dict):
            raise SchedError("a task is a dict, not %r" % (task,))
        if "pid" not in task:
            raise SchedError("a task without a pid cannot be queued: %r"
                             % (sorted(task),))
        pid = task["pid"]
        if isinstance(pid, bool) or not isinstance(pid, int):
            raise SchedError("a pid is an int, not %r" % (pid,))
        if pid < 0:
            raise SchedError("pid %d is negative, and a pid is a count" % (pid,))
        return pid

    def _name(self, queue):
        """A wait queue's name, or a refusal — an empty word names no queue.

        The run queue is the one queue whose name the kernel chose, so a caller
        cannot hand a wait queue that would answer to it.
        """
        if not isinstance(queue, str) or not queue:
            raise SchedError("a wait queue is named by a non-empty word, not %r"
                             % (queue,))
        if queue == _RUN_QUEUE:
            raise SchedError("%r is the run queue's own name, not a work queue"
                             % (queue,))
        return queue

    def _queued(self, task):
        """The pid of a task this scheduler holds, or a refusal naming it."""
        pid = self._pid_of(task)
        if pid not in self.tasks:
            raise SchedError("pid %d is not queued here" % (pid,))
        return pid

    def _tick(self, tick):
        """A tick is a non-negative int; the clock is the caller's."""
        if isinstance(tick, bool) or not isinstance(tick, int):
            raise SchedError("a tick is an int, not %r" % (tick,))
        if tick < 0:
            raise SchedError("tick %d is negative, and time does not run back"
                             % (tick,))
        return tick

    def _enqueue(self, pid):
        """Put a pid at the back of the run queue, fresh: it has not waited yet."""
        self.ready.append(pid)
        self.waited[pid] = 0

    def _drop(self, pid):
        """Take a pid off every wait queue and off the run queue."""
        for name in sorted(self.waits):
            waiters = self.waits[name]
            if pid in waiters:
                waiters.remove(pid)
            if not waiters:
                del self.waits[name]
        if pid in self.ready:
            self.ready.remove(pid)

    def _waiting_on(self, pid):
        """The queue a pid is sleeping on, or ``None``."""
        for name in sorted(self.waits):
            if pid in self.waits[name]:
                return name
        return None

    def _unblock(self, pid):
        """A task that is woken is ready again, at the back of the run queue."""
        self._drop(pid)
        self.tasks[pid]["state"] = _READY
        self._enqueue(pid)

    def _rotate(self, pid):
        """A task that used up its quantum goes to the back, ready again."""
        self.tasks[pid]["state"] = _READY
        self.ready.remove(pid)
        self.ready.append(pid)

    def _pick(self):
        """The ready task with the lowest `(priority - waited // AGEING, place)`."""
        best = None
        for place, pid in enumerate(self.ready):
            task = self.tasks[pid]
            if task["state"] != _READY:
                continue
            rank = (task["priority"] - self.waited[pid] // AGEING, place)
            if best is None or rank < best[0]:
                best = (rank, pid)
        return None if best is None else best[1]

    # -- the surface --------------------------------------------------------

    def add(self, task):
        """Put a task in the run queue, ready to be picked.

        A pid this scheduler already holds is refused: a task is queued once, and
        a queue that holds the same pid twice runs it twice for one arrival.
        """
        pid = self._pid_of(task)
        if pid in self.tasks:
            raise SchedError("pid %d is already this scheduler's" % (pid,))
        self.tasks[pid] = task
        self._enqueue(pid)
        self.records.append(("add", pid))

    def remove(self, task):
        """Take a task out of the scheduler: off the run queue and off every wait.

        A task the scheduler does not hold is refused naming its pid; a task that
        was waiting is dropped from its queue, so no later `wake` can wake what is
        no longer there.
        """
        pid = self._queued(task)
        self._drop(pid)
        del self.tasks[pid]
        if self.running == pid:
            self.running = None
        if self.last == pid:
            self.last = None
        self.records.append(("remove", pid))

    def block(self, task, reason):
        """Sleep, the naive way: enqueue and block, and never look back.

        This is the bug the stage exists for and it is deliberately available. A
        wakeup that arrived between the caller's condition check and this call
        finds nobody on the queue, and the task is not woken by it — which is why
        `wait_on` exists, and why the check that matters is the caller's, not this
        one's.
        """
        pid = self._queued(task)
        name = self._name(reason)
        waiting = self._waiting_on(pid)
        if waiting is not None:
            raise SchedError("pid %d is already waiting on %r" % (pid, waiting))
        self.tasks[pid] = task
        self._drop(pid)
        task["state"] = _BLOCKED
        self.waits.setdefault(name, []).append(pid)
        self.records.append(("block", pid, name))
        return {"pid": pid, "queue": name, "state": _BLOCKED}

    def wake(self, queue, value):
        """Wake every task waiting on `queue` at this moment, in pid order.

        They come off the queue and go to the back of the run queue, ready to be
        picked — which is why the caller may wake a queue more than once and a
        task woken once is never woken by the second call.
        """
        name = self._name(queue)
        sleeping = self.waits.pop(name, [])
        pids = tuple(sorted(sleeping))
        for pid in pids:
            self._unblock(pid)
        self.records.append(("wake", name, value, pids))
        return pids

    def step(self, tick, tasks):
        """Run the next ready task for one tick and say who that was.

        `tasks` is the caller's table of live tasks, `pid -> task`; the scheduler
        refreshes its own view from it, so a task whose state or priority changed
        is seen at the tick it changed. A blocked, zombie or dead task is never
        scheduled, and a tick on which nothing was ready runs nobody.
        """
        self._tick(tick)
        if not isinstance(tasks, dict):
            raise SchedError("the tasks a step runs are a mapping, not %r" % (tasks,))
        for pid, task in list(tasks.items()):
            if self._pid_of(task) != pid:
                raise SchedError("task %r is filed under pid %r" % (task["pid"], pid))
        self.tasks.update(tasks)
        if (self.running is not None
                and self.tasks[self.running]["state"] == _RUNNING):
            pid = self.running
        else:
            self.running = None
            pid = self._pick()
            if pid is not None:
                if pid != self.last:
                    self.switches += 1
                self.running = pid
                self.left[pid] = self.quantum
                self.tasks[pid]["state"] = _RUNNING
        if pid is None:
            self.last = None
            self.records.append(("run", tick, None))
            return {"ran": None, "switches": self.switches, "tick": tick}
        self.left[pid] -= 1
        if self.left[pid] == 0:
            self._rotate(pid)
            self.running = None
        for other in self.ready:
            if other != pid and self.tasks[other]["state"] == _READY:
                self.waited[other] += 1
        self.waited[pid] = 0
        self.last = pid
        self.records.append(("run", tick, pid))
        return {"ran": pid, "switches": self.switches, "tick": tick}

    def run(self, ticks, tasks):
        """Every tick of a run: the trace, the switches, the ticks per pid.

        A tick where nothing was ready is in the trace as ``None``, and a task
        that was in the run queue for the whole run without ever being picked is
        `starved` — which is what ageing is for and what a run short enough to
        starve one proves.
        """
        self._tick(ticks)
        trace = []
        per_pid = {}
        ready_all = None
        for tick in range(ticks):
            ran = self.step(tick, tasks)["ran"]
            trace.append((tick, ran))
            if ran is not None:
                per_pid[ran] = per_pid.get(ran, 0) + 1
            here = {pid for pid in self.ready
                    if self.tasks[pid]["state"] == _READY}
            ready_all = here if ready_all is None else ready_all & here
        starved = tuple(sorted(pid for pid in (ready_all or ())
                               if pid not in per_pid))
        return {"trace": tuple(trace), "switches": self.switches,
                "per_pid": per_pid, "starved": starved}

    def queues(self):
        """The run queue and the wait queues, by name.

        `"ready"` is the run queue in arrival order — the order the next tick
        picks in among equals — and every wait queue is under its own name, also
        in arrival order. A queue nobody waits on is not a queue.
        """
        queues = {_RUN_QUEUE: tuple(self.ready)}
        for name in sorted(self.waits):
            queues[name] = tuple(self.waits[name])
        return queues

    def log(self):
        """The kernel's own ledger, in the order it wrote it."""
        return tuple(self.records)


def wait_on(sched, task, queue, condition):
    """Sleep until `condition(task)` holds, and do not lose the wakeup in between.

    The three steps, in this order, are the whole fix: evaluate the condition;
    enqueue the task only if it is false; evaluate it *again* after the enqueue,
    and take the task back off the queue if it is true now. A caller that checks
    and then sleeps — `block` — loses a wakeup that landed between those two
    moments, and the task never runs again.
    """
    if not isinstance(sched, Scheduler):
        raise SchedError("a wait happens on a scheduler, not %r" % (sched,))
    pid = sched._pid_of(task)
    name = sched._name(queue)
    if not callable(condition):
        raise SchedError("a wait condition is a callable, not %r" % (condition,))
    if condition(task):
        return {"pid": pid, "queue": name, "state": task["state"], "checks": 1}
    sched.block(task, name)
    if condition(task):
        sched._unblock(pid)
        return {"pid": pid, "queue": name, "state": task["state"], "checks": 2}
    return {"pid": pid, "queue": name, "state": task["state"], "checks": 2}
