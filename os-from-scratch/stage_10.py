"""OS From Scratch — stage 10: The capstone: the userland, and the kernel's own ledger.

Nine stages have built a kernel that can be trusted one promise at a time. This
one runs a *userland* on top of it — five programs from the world's own fixture
set, a shell's worth of syscalls, files with owners and modes, a pipe, a fork —
and then asks the only question that matters in the end: **does the kernel's own
account of what happened agree with the world's records?**

Three parties keep a record, and they are deliberately not the same party:

    the log      what the userland asked for, one line per op the kernel ran
    the audit    what the kernel promised at the syscall boundary, written *before*
                 each act: the number, the name, the args, and the predicted answer
    the world    what the machine actually did — `RAM.write` and `RAM.log`,
                 `Console.log`, `Disk.durable_sha`, and the pool's own count

`report` recomputes the six numbers from the first two, `cross_check` reads the
third, and the answer is the list of disagreements — which is empty or the stage
has failed. The frames are the leak proof (`pool.free_count()` is back where it
started once every task has been reaped) and the console is the output proof.

The userland's ops are the world's: dicts with an `"op"` and operands that are
literals or **slot names**. Every op becomes a syscall through stage 5's boundary,
so a program never reaches into the kernel — and the boundary's own rules hold:
a pointer the task does not own is `EFAULT` before a byte moves, an fd that is not
open is `EBADF`, a load over a task's frame budget is refused by `admit` *before*
a frame is taken. A task's open files are records in its own slots, and `fds`
answers with their numbers, ascending.

    TABLE_KEYS    the four keys of a syscall table entry
    syscall_table stage 5's four calls plus this stage's twelve, from number 10
    limits_of     a task's limits, as the three resources
    apply_limit   the `limit` op: set a limit on a task
    admit         may this task take this much of this resource, before the work
    fds           the fd numbers a task holds, ascending
    run           format a disk, boot a pool, run a script, answer the kernel
    report        the six numbers, recomputed from the kernel's own records
    cross_check   the same six, against the machine's records, key by key

`KernelError` is the family. The refusals a *caller* makes — a script that is not
a sequence, a resource this kernel does not have, a limit that is not a count —
raise; everything the userland can do wrong is data, because that is what a
syscall boundary is for.

DESIGN DECISION — why is the audit line written *before* the act?
Because a line written afterwards is a description and a line written before it is
a promise. The kernel predicts the value it will return, or the errno word it is
about to return, and writes that down first; the caller can then compare the
prediction with what came back, and the comparison is the only evidence that the
kernel knew what it was doing rather than explaining it later. It also makes the
catalogue's worst mistake — a syscall that returns a value *and* an errno —
visible in the record itself: exactly one of the two columns is filled.

DESIGN DECISION — why do the userland's ops become syscalls instead of calling
the stages directly?
Because the boundary is the thing being proved. A userland that called
`stage_03.map_page` itself would be a kernel with no privilege separation at all,
and every pointer check stage 5 owns would be advice rather than a gate. Going
through `dispatch` costs an arity check, a pointer check and a return value, and
it buys the one property that makes the rest of this stage possible: the kernel's
own record of what the userland asked for is written by the same code that
answers it.

DESIGN DECISION — why is an empty pipe read `EAGAIN` instead of a block?
Because this course never sleeps. Blocking is stage 7's subject and it happens at
the *task* level, between ops; a syscall that blocked inside the kernel would need
a wakeup path, a queue and a definition of "the pipe became ready", and none of
those exist here. `EAGAIN` is the honest answer: nothing happened, ask again —
and a program that spins on it is a program that is telling the truth about a
kernel with no blocking read.

DESIGN DECISION — why does `admit` run before the work instead of after it?
Because the frames are the proof. A limit checked after an allocation has already
moved the frames, so the failure path has to unwind an allocation it may not be
able to describe, and the leak proof — the count coming back where it started —
is exactly what would break. `admit` answers `{"allowed", "reason"}` before the
work, so a refused `anon` leaves the pool exactly as it was, and the check reads
the pool on both sides of the refusal to prove it.

DESIGN DECISION — why does the uid check compare the task's uid to the file's uid
and not to its mode?
Because they are different facts: the mode's owner bits say what the *owner* may
do, and the uid says *who* the owner is. A check that compares a uid to a mode
looks like a permission check and is a comparison of two unrelated numbers, which
is why the `nosy` fixture exists — uid 1001 reading root's `0600` file must be
`EPERM`, and uid 0 must be allowed to read anything. This is the one security fact
this course insists on, and it is insisted on by fixture rather than by argument.

DESIGN DECISION — why recompute the report from the log at all, instead of
counting as it goes?
Because counters that are updated during the run are the kernel's beliefs, and the
ledger is most useful as an *independent* derivation: the log says what was asked
for and the audit says what was promised, and `report` walks both to produce the
six numbers. A report that incremented a field per act would agree with itself by
construction, and the whole point of this stage is that it must instead agree with
three sources that could disagree — the log, the audit and the machine.

TODO: implement `syscall_table`, `limits_of`, `apply_limit`, `admit`, `fds`,
`run`, `report` and `cross_check`.
"""

import machine
import devices
import userland
import stage_01
import stage_02
import stage_03
import stage_05
import stage_06
import stage_07
import stage_09

TABLE_KEYS = ("nr", "name", "arity", "handler")


class KernelError(ValueError):
    """A run this kernel refuses: a script, a resource, a limit, a fixture."""


def syscall_table():
    """Stage 5's four calls, then this stage's twelve, from number 10.

    The table is keyed by syscall number and every entry carries exactly
    `TABLE_KEYS`: `nr`, `name`, `arity` and `handler`. Stage 5's four are read
    from stage 5 itself — `write`, `getpid`, `yield` and `frames`, numbered from
    1 in its own order — and this stage adds `read`, `open`, `close`, `fork`,
    `wait`, `exit`, `anon`, `loop`, `limit`, `uid`, `pipe` and `dup2`, numbered
    from 10 in that order. Refuses a source table that is missing one of the four
    calls, or that numbers two of them the same.
    """
    raise NotImplementedError("stage 10: implement syscall_table()")



def limits_of(task):
    """A task's limits, as the three resources, copied.

    `{"frames": int, "children": int, "ticks": int}` — the shape
    `DEFAULT_LIMITS` froze in stage 6. Refuses a task whose limits are not a
    mapping of those three, because a limit nobody can count is not a limit.
    """
    raise NotImplementedError("stage 10: implement limits_of()")



def apply_limit(task, resource, value):
    """Set one limit on a task: the `limit` op, and the dict that records it.

    Answers `{"resource", "value", "limits"}` with the task's limits *after* the
    change. Refuses a resource this kernel does not have, and a value that is not
    a non-negative int — a task whose budget is negative has no budget at all.
    """
    raise NotImplementedError("stage 10: implement apply_limit()")



def admit(task, resource, want):
    """May this task take `want` more of `resource`? — asked *before* the work.

    Answers `{"allowed": bool, "reason": word}` where the word is the resource
    when the answer is no and the empty string when it is yes. It never raises
    for a limit that is spent and never moves a frame: a task over its budget is
    an outcome, not a caller's error.
    """
    raise NotImplementedError("stage 10: implement admit()")



def fds(task):
    """The fd numbers a task holds open, ascending and distinct.

    A task's open files are records in its own slots — the slot the program named
    in the op that opened it — so this is a read of the task and not of the
    kernel. A task with no space, no slots or no open files answers `()`.
    """
    raise NotImplementedError("stage 10: implement fds()")



def run(script, *, files=userland.FILES, uid=userland.ROOT_UID, ticks=128,
        quantum=3, limits=None):
    """Format a disk, boot a pool, run a script, and answer with the kernel.

    One task per `(program, uid)` pair, run in order, each through the syscall
    boundary of stage 5 and the scheduler of stage 7; the ops are the world's
    (`userland.PROGRAMS`) and `uid` is the owner of the disk's files unless a
    pair names its own. The answer is the kernel dict the other two read:
    `{"tasks", "log", "console", "pool", "disk", "audit", "ticks", "counters"}`.
    Refuses a script that is not a sequence of pairs, an unknown program, and a
    `ticks` or `quantum` that no scheduler could run.
    """
    raise NotImplementedError("stage 10: implement run()")



def report(kernel):
    """The kernel's own account, recomputed from its log and its audit.

    `{"tasks", "syscalls", "frames_in_use", "frames_free", "console_bytes",
    "durable_sha", "ticks", "limits_hit"}` — how many tasks ran, how many
    syscalls were answered, the frames held and free, the bytes the console
    accepted, the checksum of what the kernel *believes* it wrote to the disk,
    the ticks charged per task, and how many times each limit was hit. Nothing
    here is a counter the run kept.
    """
    raise NotImplementedError("stage 10: implement report()")



def cross_check(kernel):
    """`report`, against the machine's records, key by key.

    Compares `tasks`, `frames_in_use`, `frames_free`, `console_bytes`,
    `durable_sha` and `ticks` with what `RAM`, the pool, `Console` and `Disk`
    recorded, and returns the disagreements as `{key: (report said, world said)}`
    — empty when the kernel told the truth. Refuses a kernel that is missing a
    record either side needs, because a key that is not in both is not a
    disagreement, it is a bug in the question.
    """
    raise NotImplementedError("stage 10: implement cross_check()")
