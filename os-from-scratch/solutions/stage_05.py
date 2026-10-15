"""OS From Scratch — stage 5: The syscall boundary, and the pointer you did not check.

Everything a user program can hand the kernel is a number, and one of those
numbers is an address: `user_range` is the one door that address goes through.
It walks every page of `[addr, addr + n)` itself, with the access the call needs
and the user bit this machine's walk insists on, and answers `True` or `False` —
never a translation, never a fault, never a byte. A range that is negative or
that reaches past `ADDRESS_WIDTH` is not a range, and the machine will happily
answer a translation for it if nobody says so, because a walk that runs off the
end of a table reads the next frame's entries.

`dispatch` is the other half, and it is the stage's one exit: a user's mistake
comes back as an errno word, a caller's mistake raises, and the difference is
decided by *who* made it. The audit line, when an audit is being kept, is written
before the act and predicts the answer, so a kernel that decides one thing and
does another has a witness.
"""

import machine

SYSCALLS = ("write", "getpid", "yield", "frames")

ERRNOS = ("EFAULT", "EBADF", "EINVAL", "ENOSYS", "EPERM", "ENOENT", "ENOSPC",
          "EMFILE", "EAGAIN")

#: the arguments each call takes, in `SYSCALLS` order
_ARITY = (3, 0, 0, 0)

#: the top of the virtual address space: two levels of tables of `ENTRIES`
#: entries, each entry naming a frame of `PAGE_SIZE` bytes
_ADDRESS_WIDTH = machine.PAGE_SIZE * machine.ENTRIES * machine.ENTRIES


class SyscallError(ValueError):
    """A call the *caller* got wrong: not a call, or a pointer that is not a user
    range when a copy is made by hand."""


def number(name):
    """The number of a system call, from 1, in `SYSCALLS` order."""
    if name not in SYSCALLS:
        near = machine._near(name, SYSCALLS)
        hint = " (did you mean %r?)" % (near,) if near else ""
        raise SyscallError("%r is not a system call%s" % (name, hint))
    return SYSCALLS.index(name) + 1


def user_range(mmu, space, addr, n, access="read"):
    """Whether every page of `[addr, addr + n)` is a user page with `access`."""
    if not isinstance(space, dict) or "root" not in space:
        return False
    if isinstance(addr, bool) or not isinstance(addr, int) or addr < 0:
        return False
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        return False
    end = addr + n
    if end > _ADDRESS_WIDTH:
        return False
    if n == 0:
        return True
    root = space["root"]
    if isinstance(root, bool) or not isinstance(root, int):
        return False
    page = addr - addr % machine.PAGE_SIZE
    while page < end:
        try:
            mmu.translate(root, page, access, user=True)
        except machine.PageFault:
            return False
        except machine.MachineError:
            return False
        page += machine.PAGE_SIZE
    return True


def copy_in(mmu, space, addr, n):
    """`n` bytes copied out of a user range, or a refusal naming the range."""
    if (isinstance(addr, bool) or not isinstance(addr, int)
            or isinstance(n, bool) or not isinstance(n, int)):
        raise SyscallError("a copy is an address and a count, not %r of %r"
                           % (addr, n))
    if not user_range(mmu, space, addr, n, "read"):
        raise SyscallError("the range %#x..%#x is not a readable user range"
                           % (addr, addr + n))
    return mmu.load(space["root"], addr, n)


def copy_out(mmu, space, addr, data):
    """`data` written into a user range, answering how many bytes went."""
    if not isinstance(data, (bytes, bytearray)):
        raise SyscallError("a copy is bytes, not %s" % (type(data).__name__,))
    if isinstance(addr, bool) or not isinstance(addr, int):
        raise SyscallError("a copy is an address and a count, not %r of %r"
                           % (addr, len(data)))
    data = bytes(data)
    if not user_range(mmu, space, addr, len(data), "write"):
        raise SyscallError("the range %#x..%#x is not a writable user range"
                           % (addr, addr + len(data)))
    mmu.store(space["root"], addr, data)
    return len(data)


def _answer(nr, name, value, errno):
    """What a call answers: exactly one of `value` and `errno` is `None`."""
    return {"nr": nr, "name": name, "value": value, "errno": errno}


def _record(pid, tick, nr, name, args, decision, predict, audit):
    """Write the line before the act — and nothing at all when none is kept."""
    if audit is not None:
        audit.append(audit_line(pid, tick, nr, name, args, decision, predict))


def dispatch(nr, args, *, mmu, space, pid, pool=None, console=None, tick=0,
             audit=None):
    """One system call, answered: `{"nr", "name", "value", "errno"}`."""
    if isinstance(nr, bool) or not isinstance(nr, int) or nr < 0:
        raise SyscallError("a system call number is a non-negative int, not %r"
                           % (nr,))
    if not isinstance(args, tuple):
        raise SyscallError("the arguments of a call are a tuple, not %s"
                           % (type(args).__name__,))
    if audit is not None and not isinstance(audit, list):
        raise SyscallError("an audit is a list of lines, not %s"
                           % (type(audit).__name__,))
    name = SYSCALLS[nr - 1] if 1 <= nr <= len(SYSCALLS) else "unknown"
    value = None
    errno = None
    if name == "unknown":
        errno = "ENOSYS"
    elif len(args) != _ARITY[nr - 1]:
        errno = "EINVAL"
    elif name == "getpid":
        value = pid
    elif name == "yield":
        value = 0
    elif name == "frames":
        if pool is None:
            errno = "EINVAL"
        else:
            value = pool.free_count()
    elif name == "write":
        fd, addr, n = args
        if any(isinstance(arg, bool) or not isinstance(arg, int) for arg in args):
            errno = "EINVAL"
        elif fd != 1:
            errno = "EBADF"
        elif n < 0:
            errno = "EINVAL"
        elif console is None:
            errno = "EINVAL"
        elif not user_range(mmu, space, addr, n, "read"):
            errno = "EFAULT"
        else:
            value = n
    if errno is not None:
        _record(pid, tick, nr, name, args, "refuse", errno, audit)
        return _answer(nr, name, None, errno)
    _record(pid, tick, nr, name, args, "act", value, audit)
    if name == "write":
        console.write(copy_in(mmu, space, addr, n))
    return _answer(nr, name, value, None)


def audit_line(pid, tick, nr, name, args, decision, predict):
    """One line of the audit, written before the act."""
    if not isinstance(args, tuple):
        raise SyscallError("a call's arguments are a tuple, not %s"
                           % (type(args).__name__,))
    if decision not in ("act", "refuse"):
        raise SyscallError("a decision is 'act' or 'refuse', not %r" % (decision,))
    if decision == "act" and (isinstance(predict, bool)
                              or not isinstance(predict, int)):
        raise SyscallError("an act predicts a value, not %r" % (predict,))
    if decision == "refuse" and not isinstance(predict, str):
        raise SyscallError("a refusal predicts an errno word, not %r" % (predict,))
    return {"pid": pid, "tick": tick, "nr": nr, "name": name, "args": args,
            "decision": decision, "predict": predict}
