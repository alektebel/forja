"""OS From Scratch — stage 5: The syscall boundary, and the pointer you did not check.

A user program cannot call the kernel; it can only hand it numbers. One of those
numbers is an address, and that address is the whole stage: it is a *user's*
number until the kernel has translated every page of the range it names, with the
access the call needs and the user bit this machine's walk insists on. Everything
before that walk is arithmetic; everything after it is memory somebody else owns,
and a kernel that dereferences first and checks later reads whatever was in RAM.

The boundary has two directions and the stage turns on not confusing them. A
caller that got the *call* wrong — a number that is not a number, arguments that
are not a tuple — is refused with an exception, because there is no answer to
give somebody who is not calling. Everything a *user* can do wrong is answered:
`EFAULT` for a pointer that is not a mapped user range, `EBADF` for a descriptor
that is not open, `EINVAL` for a length or an argument that is not one, `ENOSYS`
for a number no call names. And because every answer is a *decision*, the audit
line is written **before** the act, carrying the promise — the value the call is
about to return, or the errno word it is about to return. A line written after
the fact is a description; a line written before it is a promise a reader can
check, which is the only reason to keep one.

    SYSCALLS    the four calls this stage answers, numbered from 1 in this order
    ERRNOS      the closed errno vocabulary, words and never numbers
    number      a call's number, or a refusal naming a name that is not one
    user_range  the check every pointer goes through: True or False, never a fault
    copy_in     `n` bytes of a user range, or a refusal naming the range
    copy_out    bytes written into a user range, or a refusal naming the range
    dispatch    one call, answered: `{"nr", "name", "value", "errno"}`
    audit_line  one line of the promise ledger, written before the act

`SyscallError` is the family a caller's mistake raises. `dispatch` never raises
for a mistake a user made; `copy_in` and `copy_out` refuse, so a kernel function
that is not the dispatcher cannot dereference a user pointer by accident either.

DESIGN DECISION — why is a caller's mistake *raised* while a user's mistake is
*returned*?
Because they are not the same kind of event. A negative call number or an
argument list that is not a tuple means the thing calling is not a user program
calling the kernel — there is no errno to hand back to it, and pretending there
is would let a kernel bug look like a user's. A pointer that is not mapped, an fd
that is not open, a length that is not a length: those arrive from a program that
is speaking the protocol correctly and getting it wrong, and the kernel's whole
job is to decide — a decision that arrives as an exception cannot be reported to
anybody. So the boundary has exactly two exits, and which one a mistake takes is
decided by *who* made it.

DESIGN DECISION — why does `user_range` answer `True`/`False` instead of
returning the frame it found, or raising the fault it caught?
Because the caller does not want the translation, it wants a yes or no, and
because a fault here is not exceptional: a user handing the kernel a bad pointer
is the normal case this whole stage exists to survive. The check walks every page
of `[addr, addr + n)` itself and swallows what the machine says; it never returns
an address, so no caller can accidentally dereference the answer.

DESIGN DECISION — why check *every* page, and why is the top of the address space
part of the check?
The classic bug is checking the first page and assuming the rest, which is right
until a range straddles a page nobody mapped — and then the kernel reads the next
frame's bytes, which belong to somebody else. The other classic is trusting
arithmetic: this machine's walk does not refuse a virtual page *outside* the
address space, it reads whatever entries happen to sit at the frame boundary next
to a table, so a vpage of `-1` or of `2 ** 18` can translate to a present page
nobody installed. A range that reaches past `ADDRESS_WIDTH` is therefore not a
range, and a negative address is not one either.

DESIGN DECISION — why is the audit line written before the act rather than after
it?
A line written after the act can only describe what happened; it is a log, and a
log cannot be wrong. A line written before it is a *prediction* — this call is
about to return this value, or this errno word — and the moment the kernel writes
it, the kernel has committed to something a reader can check against what really
came back. That is the only form of the line that can catch a dispatcher that
decides one thing and does another, so `predict` is a value for an `act` and an
errno word for a `refuse`, and a line whose two halves disagree is refused.

DESIGN DECISION — why is `number("writee")` a refusal while `dispatch(9, ...)` is
`ENOSYS`?
Because a *name* is written by a programmer and a *number* arrives from a user
program. A kernel function called with a name that is not a call is a bug in the
kernel's own table, and it should be loud, with the spelling it probably meant;
a number that names nothing is a user asking for something this machine does not
have, and the honest answer is `ENOSYS`. Both are refusals to act; only one of
them can be told to the process that asked — and that is the whole shape of this
stage in one pair of calls.

DESIGN DECISION — why do `copy_in` and `copy_out` refuse with an exception
instead of answering `EFAULT`?
Because they are not the dispatcher. Their contract is "here is a user range, do
the copy": a caller that passes a range which is not one has already lost the
ability to report it to anybody, and a copy that silently answers "zero bytes" or
"bad pointer as a number" is a copy whose caller can forget to look at the answer.
`dispatch` is the one function that must answer with an errno, so it is the one
function that asks `user_range` itself and turns the answer into `EFAULT`.

TODO: implement `number`, `user_range`, `copy_in`, `copy_out`, `dispatch` and
`audit_line`.
"""

import machine

SYSCALLS = ("write", "getpid", "yield", "frames")

ERRNOS = ("EFAULT", "EBADF", "EINVAL", "ENOSYS", "EPERM", "ENOENT", "ENOSPC",
          "EMFILE", "EAGAIN")


class SyscallError(ValueError):
    """A call the *caller* got wrong: not a call, or a pointer that is not a user
    range when a copy is made by hand."""


def number(name):
    """The number of a system call, from 1, in `SYSCALLS` order.

    A name that is not a word, or that names no call in the table, is refused —
    naming the offender and, within Levenshtein distance 2, the call that was
    probably meant.
    """
    raise NotImplementedError("stage 5: implement number()")



def user_range(mmu, space, addr, n, access="read"):
    """Whether every page of `[addr, addr + n)` is a user page with `access`.

    It answers `True` or `False`, it never raises, and it never touches a byte of
    the range: a range that is negative, that reaches past `ADDRESS_WIDTH`, or
    that names no page at all, is not a range.
    """
    raise NotImplementedError("stage 5: implement user_range()")



def copy_in(mmu, space, addr, n):
    """`n` bytes copied out of a user range, or a refusal naming the range."""
    raise NotImplementedError("stage 5: implement copy_in()")



def copy_out(mmu, space, addr, data):
    """`data` written into a user range, answering how many bytes went.

    The range is checked by `user_range` first and refused as a whole when it is
    not a writable user range, so no byte moves before the check.
    """
    raise NotImplementedError("stage 5: implement copy_out()")



def dispatch(nr, args, *, mmu, space, pid, pool=None, console=None, tick=0,
             audit=None):
    """One system call, answered: `{"nr", "name", "value", "errno"}`.

    Exactly one of `value` and `errno` is `None`. The calls are
    `write(fd, addr, n)`, `getpid()`, `yield()` and `frames()`, and everything a
    user can get wrong comes back as an errno word; only something that is not a
    call at all — a negative number, arguments that are not a tuple — raises. The
    audit line, when one is being kept, is written before the act and carries the
    value or the errno the call is about to answer with.
    """
    raise NotImplementedError("stage 5: implement dispatch()")



def audit_line(pid, tick, nr, name, args, decision, predict):
    """One line of the audit, written before the act.

    `args` is the call's argument tuple, `decision` is `"act"` or `"refuse"`, and
    `predict` is the promise: the value the call is about to return, or the errno
    word it is about to return.
    """
    raise NotImplementedError("stage 5: implement audit_line()")
