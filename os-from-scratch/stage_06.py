"""OS From Scratch — stage 6: The process, and the frame nobody gave back.

A process is the kernel's promise that memory, a root table, a set of second-level
tables and a program's data pages will be given back when the program ends. Every
frame a task holds is in one list — `task["frames"]` — because that list is what a
leak is proved against: the pool's own count before the task existed and the
pool's count after the task is gone must be the same number, and no amount of
believing otherwise survives the comparison.

The stage's second half is what one process owes another. `fork` copies: every
mapped page of the parent gets a frame of its own and the parent's bytes, so a
write in the child is invisible in the parent — sharing instead of copying is the
mistake this stage exists for, and it is invisible until somebody writes. `exit`
releases everything the task holds and leaves a zombie, because the exit code has
to survive until the parent asks for it; `wait` reaps that zombie and answers with
its status, or answers `{"blocked": True}` when the child is still alive, because
blocking is the scheduler's job and a kernel that sleeps here can never be woken.
A dying task's children are reparented to pid 0, which is the kernel: this course
has no init process, and pretending otherwise would be a lie in the ledger.

    USER_BASE       where a task's memory starts: the first page above zero
    STATES          ready, running, blocked, zombie, dead
    TASK_KEYS       the eleven keys of a task, in the order they are written
    DEFAULT_LIMITS  frames, children, ticks
    new_task        a task with no space and no frames
    images          the pages a task has mapped, as `(vpage, frame)`
    Processes       the table itself: spawn, fork, exec, exit, wait, and the ledger

Every limit is checked *before* a frame moves: a task that is over its frame limit
is refused while the pool is still untouched, which is a fact the check proves by
reading the pool's count on both sides of the refusal. `ProcessError` is the
family, and every refusal names the offender.

DESIGN DECISION — why is `frames` the task's own list, and not a number the pool
keeps?
Because a leak is a *difference*: the pool knows how many frames are free, and the
tasks say which frames they hold, and the only way to find the frame nobody gave
back is to make both lists public and compare them. A single counter cannot tell
a leak from a bug in the counter, and a task's frames — its root, its tables and
its mapped pages, in that order — are exactly what `space_frames` already answers
for the address space, so the list is a mirror, not a second bookkeeping.

DESIGN DECISION — why does `fork` copy every page instead of sharing it?
Sharing is cheaper and it is wrong: the parent and the child would see each
other's writes, and the first symptom would appear in a program that never asked
to communicate. Copy-on-write is the real answer and it costs a fault path, a
reference count per frame and a way to tell a shared frame from a private one —
which is stage 4's machinery plus bookkeeping this stage does not have. Copying is
the honest version of the promise "a process owns its memory", and its cost is
exactly what makes the leak visible.

DESIGN DECISION — why does `exec` keep the root and the tables and release only
the mapped pages?
Because the tables are the *shape* of the space, not the program: the task's root
is its identity as an address space after fork, and a second-level table that is
already there costs nothing to keep. Releasing and re-allocating identical tables
would churn the pool for no gain, and it would make `exec` fail on a pool with no
room for a table it did not need. What `exec` replaces is the data, and the data
is what it releases.

DESIGN DECISION — why does `exit` leave a zombie instead of removing the task?
Because the exit code is owed to the parent, and pid reuse before the parent has
asked would make `wait` unable to tell "the child I was waiting for" from "a new
task that happens to have its number". A zombie is a task with no frames, no
space and one number left to hand over; it stops being a task the moment its
parent reaps it. The children of a dying task go to pid 0 rather than to nobody:
an orphan nobody records is a task whose frames can never be accounted for.

DESIGN DECISION — why does `wait` answer `{"blocked": True}` instead of raising or
sleeping?
Sleeping is what a kernel without a scheduler does, and it is how a wakeup gets
lost: the task blocks on a condition that has already changed, and nothing in this
course ever wakes it. Raising would make "not yet" indistinguishable from "never",
so every caller would have to know which pids exist. A dict is data: the caller
decides what to do with a child that is alive, and a caller asking about a pid
that was never its child still gets a refusal, because that one is a bug.

DESIGN DECISION — why does `ledger` report the pool's own count?
Because the ledger's whole purpose is to be the comparison that finds a leak, and
a kernel that reports its own belief is comparing a belief to itself. `free` comes
from the pool, `frames_held` comes from the tasks, and `tasks` is how many the
kernel still has; a disagreement between the three is the evidence, so the three
have to be recorded by three different parties.

TODO: implement `new_task`, `images` and every method of `Processes`.
"""

import machine
import stage_03

USER_BASE = machine.PAGE_SIZE
STATES = ("ready", "running", "blocked", "zombie", "dead")
TASK_KEYS = ("pid", "ppid", "state", "space", "frames", "uid", "slots",
             "priority", "limits", "ticks", "exit_status")
DEFAULT_LIMITS = {"frames": 64, "children": 8, "ticks": 256}


class ProcessError(ValueError):
    """A process table this kernel cannot keep: a limit, a stranger, a zombie."""


def new_task(pid, ppid=0, uid=0, limits=None):
    """A task with no space, no frames, no ticks and no exit status.

    `limits` is copied, never shared: two tasks that were handed the same
    dictionary must not be able to change each other's limits, and a task built
    without one gets a fresh copy of `DEFAULT_LIMITS`. The task's `priority` is
    zero, its `slots` are empty and its state is `ready`.
    """
    raise NotImplementedError("stage 6: implement new_task()")


def images(task):
    """The pages a task has mapped, as `(vpage, frame)`, sorted by `vpage`.

    This is the list `fork` copies and `exec` releases; it reads the task's own
    mirror of its space, so a task that has exited — or never had a space —
    answers `()`.
    """
    raise NotImplementedError("stage 6: implement images()")



class Processes:
    """Every task this kernel knows, and the frames they hold.

    The table is keyed by pid, and pids are handed out in order from 1; pid 0 is
    the kernel, which has no task and never appears in the table.
    """

    def __init__(self, mmu, pool):
        """A table with no tasks, borrowing the machine's walk and the pool."""
        raise NotImplementedError("stage 6: implement Processes.__init__()")

    def spawn(self, ppid=0, uid=0, limits=None):
        """A fresh task with a fresh space and one page mapped at `USER_BASE`.

        Refuses when the new task's own frame limit cannot hold the space it is
        about to be given, when the parent is over its children limit, or when
        `ppid` names a task that does not exist.
        """
        raise NotImplementedError("stage 6: implement Processes.spawn()")

    def fork(self, parent):
        """A deep copy of a task: every mapped page copied into a fresh frame.

        Nothing is shared, the child's pid is the next free one, its `ppid` is
        the parent's pid, and its limits and slots are copied. Refuses a zombie
        parent, an unknown parent, or a parent over its children limit.
        """
        raise NotImplementedError("stage 6: implement Processes.fork()")

    def exec(self, task, pages=1):
        """A task with `pages` fresh frames at `USER_BASE` and up, in order.

        Every *mapped* frame is released first; the root and the tables stay.
        Refuses a zombie, a `pages` below one, and a task whose limit cannot hold
        what is about to be mapped — before a frame moves.
        """
        raise NotImplementedError("stage 6: implement Processes.exec()")

    def exit(self, task, status=0):
        """End a task: release every frame it holds, and leave it a zombie.

        The task's space is gone and its `exit_status` is `status`; its children
        are reparented to pid 0. Refuses a task that has already exited, because
        releasing its frames twice is how a pool loses frames it never got back.
        """
        raise NotImplementedError("stage 6: implement Processes.exit()")

    def wait(self, parent, pid=None):
        """Reap a zombie child, or say that there is nothing to reap yet.

        Answers `{"reaped": pid, "status": status}` for a zombie child and
        `{"blocked": True}` for a child that is still alive; with `pid=None` it
        reaps the lowest-numbered zombie child. Refuses a pid that is not this
        parent's child, and a parent that has no children at all.
        """
        raise NotImplementedError("stage 6: implement Processes.wait()")

    def children(self, task):
        """The pids of a task's children, ascending, zombies included."""
        raise NotImplementedError("stage 6: implement Processes.children()")

    def get(self, pid):
        """The task with this pid, or `None` — the table's own task, not a copy."""
        raise NotImplementedError("stage 6: implement Processes.get()")

    def ledger(self):
        """`{"frames_held": {pid: n}, "free": pool's count, "tasks": n}`.

        `frames_held` counts every frame each task holds — root, tables and
        mapped pages — and `free` is the pool's answer, never the kernel's.
        """
        raise NotImplementedError("stage 6: implement Processes.ledger()")

    def log(self):
        """Every act this table performed, in order, as dicts.

        One dict per act: `{"op", "pid", "frames", "free"}` with `op` one of
        `spawn`, `fork`, `exec`, `exit`, `wait` or `reap`, `frames` the frames
        the task holds *after* the act, and `free` the pool's count after it.
        """
        raise NotImplementedError("stage 6: implement Processes.log()")
