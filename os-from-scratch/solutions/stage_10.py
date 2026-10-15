"""OS From Scratch — stage 10: The capstone: the userland, and the kernel's own ledger.

Nine stages have built a kernel that can be trusted one promise at a time. This
one runs a *userland* on top of it — five programs from the world's own fixture
set, a shell's worth of syscalls, files with owners and modes, a pipe, a fork —
and then asks the only question that matters in the end: does the kernel's own
account of what happened agree with the world's records?

Every op in `userland.OPS` becomes one syscall: stage 5's `write` for the
console, and this stage's twelve from number 10 — `read`, `open`, `close`,
`fork`, `wait`, `exit`, `anon`, `loop`, `limit`, `uid`, `pipe` and `dup2` — for
everything else. `write` is one call number with two implementations chosen by
the fd, which is what a real kernel does and what keeps a pipe write inside the
same arity and pointer rules as a console write.

The audit line is written before each act, the log line after it, and `report`
folds both at the end instead of counting as it goes: that is what makes
`cross_check` a comparison of three parties rather than of a record with itself.
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

#: this stage's twelve calls, from number 10, with the arity each one takes
_CALLS = (("read", 3), ("open", 2), ("close", 1), ("fork", 0), ("wait", 1),
          ("exit", 1), ("anon", 1), ("loop", 1), ("limit", 2), ("uid", 1),
          ("pipe", 0), ("dup2", 2))

#: where this stage's numbering starts, and where stage 5's ends
_MINE = 10
_STAGE5 = 4

#: stage 5's four calls and the arity the boundary holds each of them to
_STAGE5_ARITY = (("write", 3), ("getpid", 0), ("yield", 0), ("frames", 0))

#: a pipe holds this many bytes, and a write into a full one is `EAGAIN`
_PIPE_CAP = 32

#: the fd the console is; every other fd is a record in a task's own slots
_CONSOLE = 1

#: the resource a run's own tick budget is charged as, in the log's tag
_RUN_OUT = "ticks"

#: a log line: what the userland asked for, and what the world did about it
_LOG_KEYS = ("tick", "pid", "op", "outcome", "errno", "value", "frames", "free",
             "ticks", "limit")

#: what `cross_check` compares, side by side
_KEYS = ("tasks", "frames_in_use", "frames_free", "console_bytes",
         "durable_sha", "ticks")

#: the outcomes that count as a task this run started
_STARTED = ("spawn", "fork")


class KernelError(ValueError):
    """A run this kernel refuses: a script, a resource, a limit, a fixture."""


def _count(value, what, low=0):
    """A non-negative int, refused by name: the one shape this kernel counts."""
    if isinstance(value, bool) or not isinstance(value, int) or value < low:
        raise KernelError("%s is an int of at least %d, not %r"
                          % (what, low, value))
    return value


def _is_int(value):
    """A number this kernel counts with: an int, and not a bool."""
    return isinstance(value, int) and not isinstance(value, bool)


def _arity_of(name):
    """The arity this kernel holds a stage 5 call to, or None if it is not one."""
    for call, arity in _STAGE5_ARITY:
        if call == name:
            return arity
    return None


def _script(script):
    """The pairs a run starts with, validated: `(program, uid or None)`."""
    if isinstance(script, (str, bytes)) or not isinstance(script, (tuple, list)):
        raise KernelError("a script is a sequence of (program, uid) pairs, not %s"
                          % (type(script).__name__,))
    pairs = []
    for entry in script:
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            raise KernelError("a script is a sequence of (program, uid) pairs, "
                              "not %r" % (entry,))
        name, owner = entry
        if name not in userland.PROGRAMS:
            raise KernelError("this userland has no program %r; it has %s"
                              % (name, ", ".join(userland.program_names())))
        if owner is not None:
            owner = _count(owner, "a program's uid")
        pairs.append((name, owner))
    return tuple(pairs)


def _used(task, resource):
    """What this task already holds of `resource`, as the task itself records it.

    Frames and ticks are on the task — `frames` is its space, `ticks` is what it
    has been charged. Children are not: the table that holds them counts them, so
    the caller asks with the count the task would reach.
    """
    if resource == "frames":
        return len(task["frames"])
    if resource == "ticks":
        return task["ticks"]
    return 0


def limits_of(task):
    """A task's limits, as the three resources, copied.

    `{"frames": int, "children": int, "ticks": int}` — the shape
    `DEFAULT_LIMITS` froze in stage 6. Refuses a task whose limits are not a
    mapping of those three, because a limit nobody can count is not a limit.
    """
    if not isinstance(task, dict) or not isinstance(task.get("limits"), dict):
        raise KernelError("a task carries its limits, not %r" % (task,))
    limits = task["limits"]
    found = {}
    for resource in userland.RESOURCES:
        if resource not in limits:
            raise KernelError("a task's limits name all of %s; this one has no %r"
                              % (", ".join(userland.RESOURCES), resource))
        found[resource] = _count(limits[resource], "the %s limit" % (resource,))
    return found


def apply_limit(task, resource, value):
    """Set one limit on a task: the `limit` op, and the dict that records it.

    Answers `{"resource", "value", "limits"}` with the task's limits *after* the
    change. Refuses a resource this kernel does not have, and a value that is not
    a non-negative int — a task whose budget is negative has no budget at all.
    """
    if resource not in userland.RESOURCES:
        raise KernelError("this kernel has no resource %r; it has %s"
                          % (resource, ", ".join(userland.RESOURCES)))
    value = _count(value, "a limit")
    limits = limits_of(task)
    limits[resource] = value
    task["limits"] = limits
    return {"resource": resource, "value": value, "limits": limits}


def admit(task, resource, want):
    """May this task take `want` more of `resource`? — asked *before* the work.

    Answers `{"allowed": bool, "reason": word}` where the word is the resource
    when the answer is no and the empty string when it is yes. It never raises
    for a limit that is spent and never moves a frame: a task over its budget is
    an outcome, not a caller's error. A caller that turns that outcome into an
    errno names it: frames and children are `ENOSPC`, ticks are `EAGAIN`.
    """
    if resource not in userland.RESOURCES:
        raise KernelError("this kernel has no resource %r; it has %s"
                          % (resource, ", ".join(userland.RESOURCES)))
    want = _count(want, "how much of a resource")
    limits = limits_of(task)
    allowed = _used(task, resource) + want <= limits[resource]
    return {"allowed": allowed, "reason": "" if allowed else resource}


def fds(task):
    """The fd numbers a task holds open, ascending and distinct.

    A task's open files are records in its own slots — the slot the program named
    in the op that opened it — so this is a read of the task and not of the
    kernel. A task with no space, no slots or no open files answers `()`.
    """
    if not isinstance(task, dict) or not isinstance(task.get("slots"), dict):
        return ()
    numbers = set()
    for record in task["slots"].values():
        if isinstance(record, dict) and _is_int(record.get("fd")):
            numbers.add(record["fd"])
    return tuple(sorted(numbers))


def record_of(task, number):
    """The open-file record a task holds under this fd, or None."""
    if not isinstance(task, dict) or not isinstance(task.get("slots"), dict):
        return None
    for record in task["slots"].values():
        if isinstance(record, dict) and record.get("fd") == number:
            return record
    return None


def next_fd(task):
    """The lowest fd above the console that this task does not hold."""
    number = _CONSOLE + 1
    held = set(fds(task))
    while number in held:
        number += 1
    return number


def _stage5_handlers():
    """One handler per call of stage 5's, each bound to its own name."""
    table = {}
    for call, _arity in _STAGE5_ARITY:
        table[call] = _bound_to(call)
    return table


def _bound_to(name):
    """A handler that answers one of stage 5's four through the boundary."""
    def handler(run, task, args, tick):
        entry = run.entry_for_name(name)
        answer = stage_05.dispatch(
            entry["nr"], args, mmu=run.mmu, space=task["space"], pid=task["pid"],
            pool=run.pool, console=run.console, tick=tick, audit=run.audit)
        return {"value": answer["value"], "errno": answer["errno"], "ticks": 0}
    return handler


def _mine_handlers():
    """One handler per call this stage adds."""
    return {"read": _read, "open": _open, "close": _close, "fork": _fork,
            "wait": _wait, "exit": _exit, "anon": _anon, "loop": _loop,
            "limit": _limit, "uid": _uid, "pipe": _pipe, "dup2": _dup2}


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
    names = stage_05.SYSCALLS
    if not isinstance(names, (tuple, list)) or len(names) == 0:
        raise KernelError("stage 5's calls are a non-empty sequence, not %r"
                          % (names,))
    handlers = _stage5_handlers()
    table = {}
    seen = {}
    for name in names:
        if name not in handlers:
            raise KernelError("stage 5 has no call %r; its four are %s"
                              % (name, ", ".join(call for call, _a in _STAGE5_ARITY)))
        if name in seen:
            raise KernelError("stage 5 numbers %r twice: %r and %r"
                              % (name, seen[name], len(table) + 1))
        nr = len(table) + 1
        seen[name] = nr
        table[nr] = {"nr": nr, "name": name, "arity": _arity_of(name),
                     "handler": handlers[name]}
    for name, _arity in _STAGE5_ARITY:
        if name not in seen:
            raise KernelError("stage 5's calls are missing %r: a table without "
                              "it is not this kernel's" % (name,))
    mine = _mine_handlers()
    for index, (name, arity) in enumerate(_CALLS):
        nr = _MINE + index
        table[nr] = {"nr": nr, "name": name, "arity": arity, "handler": mine[name]}
    return table


# --- the twelve calls this stage answers ---------------------------------------

def _read(run, task, args, tick):
    """`read(fd, addr, n)`: bytes out of a file or a pipe, into a user range."""
    fd, addr, n = args
    if not _is_int(fd) or not _is_int(addr) or not _is_int(n) or n < 0:
        return run.refuse(task, tick, 10, args, "EINVAL")
    record = record_of(task, fd)
    if record is None:
        return run.refuse(task, tick, 10, args, "EBADF")
    if record.get("kind") == "file":
        data = stage_09.read_file(run.fs, record["ino"])
        chunk = data[record["offset"]:record["offset"] + n]
        if chunk and not run.writable(task, addr, len(chunk)):
            return run.refuse(task, tick, 10, args, "EFAULT")
        run.promise(task, tick, 10, args, "act", len(chunk))
        if chunk:
            stage_05.copy_out(run.mmu, task["space"], addr, chunk)
            record["offset"] += len(chunk)
        return {"value": len(chunk), "errno": None, "ticks": 0}
    if record.get("kind") != "pipe" or record.get("end") != "read":
        return run.refuse(task, tick, 10, args, "EBADF")
    pipe = record["pipe"]
    chunk = bytes(pipe["buf"][:n])
    if not chunk:
        return run.refuse(task, tick, 10, args, "EAGAIN")
    if not run.writable(task, addr, len(chunk)):
        return run.refuse(task, tick, 10, args, "EFAULT")
    run.promise(task, tick, 10, args, "act", len(chunk))
    stage_05.copy_out(run.mmu, task["space"], addr, chunk)
    del pipe["buf"][:len(chunk)]
    return {"value": len(chunk), "errno": None, "ticks": 0}


def _open(run, task, args, tick):
    """`open(path, flags)`: a path pointer, an owner, a mode, and a record."""
    addr, flags = args
    if not _is_int(addr) or not _is_int(flags):
        return run.refuse(task, tick, 11, args, "EINVAL")
    if flags not in (userland.OPEN_READ, userland.OPEN_WRITE):
        return run.refuse(task, tick, 11, args, "EINVAL")
    text = run.string_at(task, addr)
    if text is None:
        return run.refuse(task, tick, 11, args, "EFAULT")
    try:
        inode = stage_09.lookup(run.fs, text)
    except stage_09.FsError:
        return run.refuse(task, tick, 11, args, "ENOENT")
    if inode["kind"] == "dir" or inode["kind"] != "file":
        return run.refuse(task, tick, 11, args, "EINVAL")
    if not _may(task["uid"], inode, flags):
        return run.refuse(task, tick, 11, args, "EPERM")
    record = {"fd": next_fd(task), "kind": "file", "ino": inode["ino"],
              "offset": 0}
    run.install(task, record)
    run.promise(task, tick, 11, args, "act", record["fd"])
    return {"value": record["fd"], "errno": None, "ticks": 0, "into": record}


def _close(run, task, args, tick):
    """`close(fd)`: the record leaves the task's slots, and nothing else happens."""
    (fd,) = args
    if not _is_int(fd):
        return run.refuse(task, tick, 12, args, "EINVAL")
    record = record_of(task, fd)
    if record is None:
        return run.refuse(task, tick, 12, args, "EBADF")
    run.forget(task, record)
    run.promise(task, tick, 12, args, "act", 0)
    return {"value": 0, "errno": None, "ticks": 0}


def _fork(run, task, args, tick):
    """`fork()`: the table copies frames, the kernel copies the program."""
    allowed = admit(task, "children", len(run.procs.children(task)) + 1)
    if not allowed["allowed"]:
        return run.refuse(task, tick, 13, args, "ENOSPC",
                          limit="children")
    try:
        child = run.procs.fork(task)
    except stage_06.ProcessError:
        return run.refuse(task, tick, 13, args, "EINVAL")
    run.adopt(task, child)
    run.promise(task, tick, 13, args, "act", child["pid"])
    return {"value": child["pid"], "errno": None, "ticks": 0}


def _wait(run, task, args, tick):
    """`wait(pid)`: reap a child, or block where a wakeup cannot be lost."""
    (pid,) = args
    if not _is_int(pid):
        return run.refuse(task, tick, 14, args, "EINVAL")
    try:
        answer = run.procs.wait(task, None)
    except stage_06.ProcessError:
        return run.refuse(task, tick, 14, args, "EINVAL")
    if "reaped" not in answer:
        run.rewind(task)
        run.await_child(task, tick)
        return {"value": None, "errno": None, "ticks": 0, "blocked": True}
    run.promise(task, tick, 14, args, "act", answer["status"])
    return {"value": answer["status"], "errno": None, "ticks": 0}


def _exit(run, task, args, tick):
    """`exit(status)`: a zombie that keeps its status and releases its frames."""
    (status,) = args
    if not _is_int(status):
        return run.refuse(task, tick, 15, args, "EINVAL")
    run.promise(task, tick, 15, args, "act", status)
    run.end(task, status, tick)
    return {"done": True, "value": status, "errno": None, "ticks": 0}


def _anon(run, task, args, tick):
    """`anon(pages)`: fresh frames at untouched vpages, or not one of them."""
    (pages,) = args
    if not _is_int(pages) or pages <= 0:
        return run.refuse(task, tick, 16, args, "EINVAL")
    allowed = admit(task, "frames", run.pages_cost(task, pages))
    if not allowed["allowed"]:
        return run.refuse(task, tick, 16, args, "ENOSPC", limit="frames")
    base = run.map_anon(task, pages)
    if base is None:
        return run.refuse(task, tick, 16, args, "ENOSPC", limit="frames")
    run.promise(task, tick, 16, args, "act", base)
    return {"value": base, "errno": None, "ticks": 0}


def _loop(run, task, args, tick):
    """`loop(n)`: n ticks of work, cut off where the task's own budget ends."""
    (n,) = args
    if not _is_int(n) or n < 0:
        return run.refuse(task, tick, 17, args, "EINVAL")
    limits = limits_of(task)
    spent = min(n, max(limits["ticks"] - task["ticks"] - 1, 0))
    run.promise(task, tick, 17, args, "act", spent)
    return {"done": spent < n, "value": spent, "errno": None, "ticks": spent}


def _limit(run, task, args, tick):
    """`limit(resource, value)`: the task's own budget, set by the task."""
    resource, value = args
    if not isinstance(resource, str):
        return run.refuse(task, tick, 18, args, "EINVAL")
    try:
        answer = apply_limit(task, resource, value)
    except KernelError:
        return run.refuse(task, tick, 18, args, "EINVAL")
    run.promise(task, tick, 18, args, "act", answer["value"])
    return {"value": answer["value"], "errno": None, "ticks": 0}


def _uid(run, task, args, tick):
    """`uid(value)`: who this task is, from now on."""
    (value,) = args
    if not _is_int(value) or value < 0:
        return run.refuse(task, tick, 19, args, "EINVAL")
    task["uid"] = value
    run.promise(task, tick, 19, args, "act", value)
    return {"value": value, "errno": None, "ticks": 0}


def _pipe(run, task, args, tick):
    """`pipe()`: one buffer, two records, and the read end as the answer."""
    pipe = {"buf": bytearray(), "cap": _PIPE_CAP}
    read = {"fd": next_fd(task), "kind": "pipe", "end": "read", "pipe": pipe}
    run.install(task, read)
    write = {"fd": next_fd(task), "kind": "pipe", "end": "write", "pipe": pipe}
    run.install(task, write)
    run.promise(task, tick, 20, args, "act", read["fd"])
    return {"value": read["fd"], "errno": None, "ticks": 0,
            "pair": (read, write)}


def _dup2(run, task, args, tick):
    """`dup2(old, new)`: another name for the same open file, under a new fd."""
    old, new = args
    if not _is_int(old) or not _is_int(new) or new <= _CONSOLE:
        return run.refuse(task, tick, 21, args, "EINVAL")
    record = record_of(task, old)
    if record is None:
        return run.refuse(task, tick, 21, args, "EBADF")
    taken = record_of(task, new)
    if taken is not None:
        run.forget(task, taken)
    copy = dict(record)
    copy["fd"] = new
    run.install(task, copy)
    run.promise(task, tick, 21, args, "act", new)
    return {"value": new, "errno": None, "ticks": 0, "into": copy}


def _may(uid, inode, flags):
    """Whether this uid may open this inode: root, or the owner, or the others."""
    bit = 0o400 if flags == userland.OPEN_READ else 0o200
    if uid == userland.ROOT_UID:
        return True
    if uid == inode["uid"]:
        return bool(inode["mode"] & bit)
    return bool(inode["mode"] & (bit >> 6))


# --- the kernel that runs a script ---------------------------------------------

class _Ledger:
    """A disk that also remembers what it was told to write.

    `Disk.durable_sha` is the world's answer to "what is on the disk"; this is
    the kernel's answer to "what did I ask to be put there", computed with the
    device's own mixing rule (a byte contributes its value and its sector index)
    so the two numbers are comparable without one being a copy of the other.
    """

    def __init__(self, disk):
        self.disk = disk
        self.written = {}
        self.order = []
        self.barriers = 0

    def __getattr__(self, name):
        return getattr(self.disk, name)

    def read(self, index):
        return self.disk.read(index)

    def write(self, index, data):
        self.written[index] = bytes(data)
        self.order.append(index)
        return self.disk.write(index, data)

    def barrier(self):
        self.barriers += 1
        return self.disk.barrier()

    def sha(self):
        """The digest of the image this ledger believes it wrote."""
        digest = 0
        blank = bytes(self.disk.sector_size)
        for index in range(self.disk.sectors):
            for byte in self.written.get(index, blank):
                digest = (digest * 31 + byte + index) & 0xFFFFFFFF
        return digest


class _Run:
    """One kernel, one boot, one script: the records and the machines behind them."""

    def __init__(self, files, ticks, quantum):
        self.ram = machine.RAM()
        self.pool = stage_02.Frames(
            self.ram, stage_01.usable_frames(machine.boot_map("clean")))
        self.mmu = machine.MMU(self.ram)
        self.console = devices.Console()
        self.timer = machine.Timer()
        self.ledger = _Ledger(devices.Disk())
        self.geometry = stage_09.format_disk(self.ledger, files)
        self.fs = stage_09.mount(self.ledger)["fs"]
        self.procs = stage_06.Processes(self.mmu, self.pool)
        self.sched = stage_07.Scheduler(quantum)
        self.audit = []
        self.log = []
        self.budget = ticks
        self.table = syscall_table()
        self.running = {}        # pid -> {"ops", "ip", "vtop", "arena", "done"}
        self.tasks = {}          # pid -> task, the mapping the scheduler reads
        self.line(None, 0, "boot", "boot", None, self.pool.free_count(), None, 0)

    # -- the records ------------------------------------------------------------

    def entry_for(self, nr):
        """The table entry for a call's number, refused by name when absent."""
        if nr not in self.table:
            raise KernelError("this kernel has no syscall %r" % (nr,))
        return self.table[nr]

    def entry_for_name(self, name):
        """The table entry for a call's name."""
        for entry in self.table.values():
            if entry["name"] == name:
                return entry
        raise KernelError("this kernel's table has no %r" % (name,))

    def promise(self, task, tick, nr, args, decision, predict, limit=None):
        """The audit line, written before the act it describes."""
        entry = self.entry_for(nr)
        self.audit.append(stage_05.audit_line(
            task["pid"], tick, nr, entry["name"], args, decision, predict))

    def line(self, task, tick, op, outcome, errno, value, limit, ticks):
        """One line of the log: exactly one of errno and value is set."""
        self.log.append({"tick": tick, "pid": task["pid"] if task else 0,
                         "op": op, "outcome": outcome, "errno": errno,
                         "value": value,
                         "frames": len(task["frames"]) if task else 0,
                         "free": self.pool.free_count(), "ticks": ticks,
                         "limit": limit})

    def refuse(self, task, tick, nr, args, errno, limit=None, op=None):
        """A refusal at the boundary: the promise, and the answer it predicts.

        The log line is `settle`'s: one op, one line, whether the answer was a
        value or an errno word.
        """
        self.promise(task, tick, nr, args, "refuse", errno)
        return {"value": None, "errno": errno, "ticks": 0, "limit": limit}

    def assert_line(self, task, tick, op, errno, limit=None):
        """A refusal no call number owns: an op this vocabulary does not have."""
        self.line(task, tick, op, "refuse", errno, None, limit, 1)

    def fail(self, task, tick, nr, args, errno, op, limit=None):
        """A refusal from an op: the promise, the line, and the answer."""
        return self.settle(task, tick, nr, args,
                           self.refuse(task, tick, nr, args, errno, limit), op=op)

    # -- the machine behind a task ----------------------------------------------

    def writable(self, task, addr, n):
        """Whether a user range this kernel is about to write is one."""
        return stage_05.user_range(self.mmu, task["space"], addr, n, "write")

    def readable(self, task, addr, n):
        """Whether a user range this kernel is about to read is one."""
        return stage_05.user_range(self.mmu, task["space"], addr, n, "read")

    def string_at(self, task, addr):
        """A NUL-terminated string out of a user range, or None if it is not one."""
        out = bytearray()
        for offset in range(machine.PAGE_SIZE):
            if not self.readable(task, addr + offset, 1):
                return None
            byte = stage_05.copy_in(self.mmu, task["space"], addr + offset, 1)
            if byte == b"\x00":
                return out.decode("utf-8", "replace")
            out += byte
        return None

    def arena(self, task, data):
        """`data` copied into the task's first page, as an `(address, length)`."""
        program = self.running[task["pid"]]
        length = len(data)
        if program["arena"] + length > machine.PAGE_SIZE:
            return None
        addr = stage_06.USER_BASE + program["arena"]
        frame = self.frame_at(task, addr)
        if frame is None:
            return None
        self.ram.write(machine.addr_of(frame) + (addr % machine.PAGE_SIZE), data)
        program["arena"] += length
        return (addr, length)

    def frame_at(self, task, addr):
        """The physical frame a user address lands in, or None."""
        entry = stage_03.lookup(task["space"], addr)
        return entry[0] if entry is not None else None

    def pages_cost(self, task, pages):
        """The frames a run of fresh pages needs: the pages, plus fresh tables."""
        root = task["space"]["root"]
        start = self.running[task["pid"]]["vtop"]
        fresh = set()
        for page in range(pages):
            vaddr = start + page * machine.PAGE_SIZE
            if self.mmu.entry(root, vaddr) == 0:
                fresh.add(vaddr // machine.PAGE_SIZE // machine.ENTRIES)
        return pages + len(fresh)

    def map_anon(self, task, pages):
        """Map `pages` fresh pages, or unmap every one of them and answer None."""
        program = self.running[task["pid"]]
        space = task["space"]
        base = program["vtop"]
        mapped = []
        try:
            for page in range(pages):
                vaddr = base + page * machine.PAGE_SIZE
                frame = self.pool.alloc(1)[0]
                stage_03.map_page(self.mmu, self.pool, space, vaddr, frame,
                                  machine.WRITE | machine.USER)
                mapped.append((vaddr, frame))
        except (stage_02.FramesError, stage_03.SpaceError):
            for vaddr, _frame in mapped:
                entry = stage_03.unmap_page(self.mmu, space, vaddr)
                self.pool.free(entry["frame"])
            return None
        program["vtop"] = base + pages * machine.PAGE_SIZE
        task["frames"] = stage_03.space_frames(space)
        return base

    # -- the task's own records -------------------------------------------------

    def install(self, task, record):
        """Put an open-file record in the task's slots under its own number."""
        slots = task["slots"]
        if not isinstance(slots, dict):
            slots = {}
            task["slots"] = slots
        name = "fd%d" % (record["fd"],)
        slots[name] = record
        return name

    def forget(self, task, record):
        """Drop every slot that holds this record: one file, many names."""
        dropped = []
        for name, value in list(task["slots"].items()):
            if value is record:
                del task["slots"][name]
                dropped.append(name)
        return tuple(dropped)

    def adopt(self, parent, child):
        """A forked child inherits the parent's program, its ip and its files."""
        program = dict(self.running[parent["pid"]])
        program["slots"] = {name: dict(value) if isinstance(value, dict) else value
                            for name, value in parent["slots"].items()}
        child["slots"] = program["slots"]
        self.running[child["pid"]] = program
        self.tasks[child["pid"]] = child
        self.sched.add(child)
        return child

    def rewind(self, task):
        """Put the op the task is on back, so it runs again after the wakeup."""
        program = self.running[task["pid"]]
        if program["ip"] > 0:
            program["ip"] -= 1

    def await_child(self, task, tick):
        """Sleep on `wait`'s queue with the condition checked on both sides."""
        stage_07.wait_on(self.sched, task, "wait", self.has_zombie)
        self.line(task, tick, "wait", "block", None, None, None, 1)

    def has_zombie(self, task):
        """Whether a child of this task has already ended."""
        return any(other["ppid"] == task["pid"] and other["state"] == "zombie"
                   for other in self.procs.tasks.values())

    def end(self, task, status, tick, ticks=1):
        """A task ends: the table releases its frames and leaves a zombie."""
        self.procs.exit(task, status)
        self.sched.remove(task)
        self.running[task["pid"]]["done"] = True
        self.line(task, tick, "exit", "act", None, status, None, ticks)
        if task["ppid"] != 0:
            self.sched.wake("wait", task["pid"])

    def stop(self, task, reason, tick, limit=None):
        """The kernel ends a task: the budget is spent, and the log says so."""
        self.procs.exit(task, 0)
        self.sched.remove(task)
        self.running[task["pid"]]["done"] = True
        self.line(task, tick, "stop", "stop", None, reason, limit, 0)
        if task["ppid"] != 0:
            self.sched.wake("wait", task["pid"])

    # -- one call ---------------------------------------------------------------

    def call(self, task, tick, nr, args):
        """One syscall through the boundary: stage 5's, or this stage's."""
        entry = self.entry_for(nr)
        if nr <= _STAGE5:
            answer = stage_05.dispatch(
                nr, args, mmu=self.mmu, space=task["space"], pid=task["pid"],
                pool=self.pool, console=self.console, tick=tick,
                audit=self.audit)
            return {"value": answer["value"], "errno": answer["errno"],
                    "ticks": 0}
        if len(args) != entry["arity"]:
            self.promise(task, tick, nr, args, "refuse", "EINVAL")
            return {"value": None, "errno": "EINVAL", "ticks": 0}
        return entry["handler"](self, task, args, tick)

    def settle(self, task, tick, nr, args, answer, op=None):
        """Store what an op asked to keep, and write the line the op owes."""
        entry = self.entry_for(nr)
        name = op or entry["name"]
        spent = 1 + answer["ticks"]
        if answer.get("blocked"):
            return 1
        if answer["errno"] is None:
            self.line(task, tick, name, "act", None, answer["value"],
                      answer.get("limit"), spent)
        else:
            self.line(task, tick, name, "refuse", answer["errno"], None,
                      answer.get("limit"), spent)
        return spent

    def slot_of(self, task, name):
        """The fd a slot names, or None when it is not an fd record."""
        value = task["slots"].get(name)
        if isinstance(value, dict) and _is_int(value.get("fd")):
            return value["fd"]
        return None

    def buffer_of(self, task, name):
        """The `(address, length)` a slot holds, or None when it is not one."""
        value = task["slots"].get(name)
        if isinstance(value, tuple) and len(value) == 2:
            return value
        return None

    # -- running a script -------------------------------------------------------

    def start(self, ops, owner, limits, tick):
        """One task per (program, uid) pair, queued in the order it was asked for."""
        task = self.procs.spawn(ppid=0, uid=owner, limits=limits)
        self.running[task["pid"]] = {"ops": ops, "ip": 0,
                                     "vtop": stage_06.USER_BASE + machine.PAGE_SIZE,
                                     "arena": 0, "done": False}
        self.tasks[task["pid"]] = task
        self.sched.add(task)
        self.line(task, tick, "spawn", "spawn", None, task["pid"], None, 0)
        return task

    def one_op(self, task, tick):
        """One op, one tick, and the answer recorded either way."""
        program = self.running[task["pid"]]
        if program["done"] or program["ip"] >= len(program["ops"]):
            self.end(task, 0, tick, ticks=0)
            return 0
        allowed = admit(task, "ticks", 1)
        if not allowed["allowed"]:
            self.stop(task, _RUN_OUT, tick, limit=_RUN_OUT)
            return 0
        op = program["ops"][program["ip"]]
        program["ip"] += 1
        task["ticks"] += 1
        name = op.get("op") if isinstance(op, dict) else None
        if name not in userland.OPS:
            self.assert_line(task, tick, str(name), "ENOSYS")
            return 1
        return _OP_HANDLERS()[name](self, task, op, tick)


# --- the ops, one syscall each -------------------------------------------------

def _op_write(run, task, op, tick):
    """`write`: the console through the boundary, a pipe through the kernel.

    One call number, two implementations, chosen by the fd — and the arity, the
    pointer check and the promise are the same on both paths.
    """
    fd = op.get("fd")
    if isinstance(fd, str):
        fd = run.slot_of(task, fd)
        if fd is None:
            return run.fail(task, tick, 1, (), "EBADF", "write")
    holder = op.get("from")
    if holder is not None:
        pair = run.buffer_of(task, holder)
        if pair is None:
            return run.fail(task, tick, 1, (), "EINVAL", "write")
        addr, length = pair
    else:
        data = op.get("bytes")
        if not isinstance(data, (bytes, bytearray)):
            return run.fail(task, tick, 1, (), "EINVAL", "write")
        pair = run.arena(task, bytes(data))
        if pair is None:
            return run.fail(task, tick, 1, (), "ENOSPC", "write")
        addr, length = pair
    args = (fd, addr, length)
    if fd == _CONSOLE:
        return run.settle(task, tick, 1, args,
                          run.call(task, tick, 1, args), op="write")
    record = record_of(task, fd)
    if record is None or record.get("kind") != "pipe" \
            or record.get("end") != "write":
        return run.fail(task, tick, 1, args, "EBADF", "write")
    pipe = record["pipe"]
    if len(pipe["buf"]) + length > pipe["cap"]:
        return run.fail(task, tick, 1, args, "EAGAIN", "write")
    if not run.readable(task, addr, length):
        return run.fail(task, tick, 1, args, "EFAULT", "write")
    run.promise(task, tick, 1, args, "act", length)
    pipe["buf"] += stage_05.copy_in(run.mmu, task["space"], addr, length)
    run.line(task, tick, "write", "act", None, length, None, 1)
    return 1


def _op_read(run, task, op, tick):
    """`read`: into a slot, which keeps the buffer the bytes landed in."""
    fd = op.get("fd")
    if isinstance(fd, str):
        fd = run.slot_of(task, fd)
        if fd is None:
            return run.fail(task, tick, 10, (), "EBADF", "read")
    count = op.get("n")
    if not _is_int(count) or count < 0:
        return run.fail(task, tick, 10, (), "EINVAL", "read")
    program = run.running[task["pid"]]
    if program["arena"] + count > machine.PAGE_SIZE:
        return run.fail(task, tick, 10, (), "ENOSPC", "read")
    addr = stage_06.USER_BASE + program["arena"]
    args = (fd, addr, count)
    answer = run.call(task, tick, 10, args)
    if answer["errno"] is None:
        program["arena"] += answer["value"]
        name = op.get("into")
        if isinstance(name, str):
            task["slots"][name] = (addr, answer["value"])
    return run.settle(task, tick, 10, args, answer, op="read")


def _op_open(run, task, op, tick):
    """`open`: the path becomes a pointer, and the pointer is what is checked."""
    path = op.get("path")
    flags = op.get("flags")
    if not isinstance(path, str) or not _is_int(flags):
        return run.fail(task, tick, 11, (), "EINVAL", "open")
    pair = run.arena(task, path.encode("utf-8") + b"\x00")
    if pair is None:
        return run.fail(task, tick, 11, (), "ENOSPC", "open")
    args = (pair[0], flags)
    answer = run.call(task, tick, 11, args)
    if answer["errno"] is None:
        name = op.get("into")
        if isinstance(name, str):
            task["slots"][name] = answer["into"]
    return run.settle(task, tick, 11, args, answer, op="open")


def _op_close(run, task, op, tick):
    """`close`: the record goes, and every slot that held it goes with it."""
    fd = op.get("fd")
    if isinstance(fd, str):
        fd = run.slot_of(task, fd)
    if not _is_int(fd):
        return run.fail(task, tick, 12, (), "EBADF", "close")
    return run.settle(task, tick, 12, (fd,),
                      run.call(task, tick, 12, (fd,)), op="close")


def _op_pipe(run, task, op, tick):
    """`pipe`: two records, one buffer, two slots."""
    answer = run.call(task, tick, 20, ())
    if answer["errno"] is None:
        names = op.get("into")
        if isinstance(names, (tuple, list)) and len(names) == 2:
            task["slots"][names[0]] = answer["pair"][0]
            task["slots"][names[1]] = answer["pair"][1]
    return run.settle(task, tick, 20, (), answer, op="pipe")


def _op_dup2(run, task, op, tick):
    """`dup2`: another fd for the same open file."""
    old = op.get("old")
    if isinstance(old, str):
        old = run.slot_of(task, old)
    new = op.get("new")
    if not _is_int(old) or not _is_int(new):
        return run.fail(task, tick, 21, (), "EBADF", "dup2")
    return run.settle(task, tick, 21, (old, new),
                      run.call(task, tick, 21, (old, new)), op="dup2")


def _op_fork(run, task, op, tick):
    """`fork`: the child's pid, in the slot the op named."""
    answer = run.call(task, tick, 13, ())
    if answer["errno"] is None:
        name = op.get("into")
        if isinstance(name, str):
            task["slots"][name] = answer["value"]
    return run.settle(task, tick, 13, (), answer, op="fork")


def _op_wait(run, task, op, tick):
    """`wait`: the status of a reaped child, or a tick spent blocked."""
    answer = run.call(task, tick, 14, (0,))
    if answer["errno"] is None and not answer.get("blocked"):
        name = op.get("into")
        if isinstance(name, str):
            task["slots"][name] = answer["value"]
    return run.settle(task, tick, 14, (0,), answer, op="wait")


def _op_exit(run, task, op, tick):
    """`exit`: the last op a task runs, whatever the program has after it."""
    status = op.get("status")
    if not _is_int(status):
        return run.fail(task, tick, 15, (), "EINVAL", "exit")
    run.call(task, tick, 15, (status,))
    return 1


def _op_anon(run, task, op, tick):
    """`anon`: the address of the pages that were mapped, in the op's slot."""
    args = (op.get("pages"),)
    answer = run.call(task, tick, 16, args)
    if answer["errno"] is None:
        name = op.get("into")
        if isinstance(name, str):
            task["slots"][name] = answer["value"]
    return run.settle(task, tick, 16, args, answer, op="anon")


def _op_loop(run, task, op, tick):
    """`loop`: ticks of work, charged one at a time against the task's budget."""
    args = (op.get("n"),)
    answer = run.call(task, tick, 17, args)
    spent = run.settle(task, tick, 17, args, answer, op="loop")
    if answer.get("done"):
        run.stop(task, _RUN_OUT, tick, limit=_RUN_OUT)
    return spent


def _op_limit(run, task, op, tick):
    """`limit`: the `limit` op, and the dict that records it."""
    args = (op.get("resource"), op.get("value"))
    return run.settle(task, tick, 18, args, run.call(task, tick, 18, args),
                      op="limit")


def _op_uid(run, task, op, tick):
    """`uid`: who the task is from here on."""
    args = (op.get("value"),)
    return run.settle(task, tick, 19, args, run.call(task, tick, 19, args),
                      op="uid")


def _op_handlers():
    """Every op the world's vocabulary has, and the handler that runs it."""
    return {"write": _op_write, "read": _op_read, "open": _op_open,
            "close": _op_close, "pipe": _op_pipe, "dup2": _op_dup2,
            "fork": _op_fork, "wait": _op_wait, "exit": _op_exit,
            "anon": _op_anon, "loop": _op_loop, "limit": _op_limit,
            "uid": _op_uid}


_OP_HANDLERS = _op_handlers


# --- the two readings of one run -----------------------------------------------

def _record(kernel, key):
    """One of the kernel's records, refused by name when it is not there."""
    if not isinstance(kernel, dict) or key not in kernel:
        raise KernelError("a kernel carries a %r record, and this one has none"
                          % (key,))
    return kernel[key]


def report(kernel):
    """The kernel's own account, recomputed from its log and its audit.

    `{"tasks", "syscalls", "frames_in_use", "frames_free", "console_bytes",
    "durable_sha", "ticks", "limits_hit"}` — how many tasks ran, how many
    syscalls were answered, the frames held and free, the bytes the console
    accepted, the checksum of what the kernel *believes* it wrote to the disk,
    the ticks charged, and how many times each limit was hit. Nothing here is a
    counter the run kept: every number is folded out of the log and the audit.
    """
    log = _record(kernel, "log")
    audit = _record(kernel, "audit")
    tasks = 0
    ticks = 0
    frees = 0
    console_bytes = 0
    held = {}
    limits_hit = {}
    for line in log:
        for key in _LOG_KEYS:
            if key not in line:
                raise KernelError("a log line is missing %r: %r" % (key, line))
        if line["op"] in _STARTED and line["outcome"] in ("spawn", "act"):
            tasks += 1
        ticks += line["ticks"]
        frees = line["free"]
        held[line["pid"]] = line["frames"]
        if line["limit"] and line["outcome"] in ("refuse", "stop"):
            limits_hit[line["limit"]] = limits_hit.get(line["limit"], 0) + 1
    counters = _record(kernel, "counters")
    records = counters.get("records") if isinstance(counters, dict) else None
    if records is None or not hasattr(records, "sha"):
        raise KernelError("the kernel's counters have no 'records' to read: %r"
                          % (counters,))
    console_bytes = sum(line["predict"] for line in audit
                        if line["name"] == "write" and line["decision"] == "act"
                        and line["args"] and line["args"][0] == _CONSOLE)
    return {"tasks": tasks, "syscalls": len(audit),
            "frames_in_use": sum(held.values()), "frames_free": frees,
            "console_bytes": console_bytes,
            "durable_sha": records.sha(),
            "ticks": ticks, "limits_hit": limits_hit}


def cross_check(kernel):
    """`report`, against the machine's records, key by key.

    Compares `tasks`, `frames_in_use`, `frames_free`, `console_bytes`,
    `durable_sha` and `ticks` with what `RAM`, the pool, `Console` and `Disk`
    recorded, and returns the disagreements as `{key: (report said, world said)}`
    — empty when the kernel told the truth. Refuses a kernel that is missing a
    record either side needs, because a key that is not in both is not a
    disagreement, it is a bug in the question.
    """
    _record(kernel, "log")
    _record(kernel, "audit")
    said = report(kernel)
    procs = _record(kernel, "tasks")
    pool = _record(kernel, "pool")
    console = _record(kernel, "console")
    disk = _record(kernel, "disk")
    counters = _record(kernel, "counters")
    if "records" not in counters:
        raise KernelError("the kernel's counters have no 'records' to read")
    timer = _record(kernel, "ticks")
    world = {"tasks": sum(1 for entry in procs.log()
                          if entry["op"] in _STARTED),
             "frames_in_use": len(pool.used()),
             "frames_free": pool.free_count(),
             "console_bytes": len(console.bytes()),
             "durable_sha": disk.durable_sha(),
             "ticks": timer.ticks}
    return {key: (said[key], world[key]) for key in _KEYS
            if said[key] != world[key]}


def run(script, *, files=userland.FILES, uid=userland.ROOT_UID, ticks=128,
        quantum=3, limits=None):
    """Format a disk, boot a pool, run a script, and answer with the kernel.

    One task per `(program, uid)` pair, run in order, each through the syscall
    boundary of stage 5 and the scheduler of stage 7; the ops are the world's
    (`userland.PROGRAMS`) and `uid` is the owner a pair does not name. The answer
    is the kernel dict the other two read: `{"tasks", "log", "console", "pool",
    "disk", "audit", "ticks", "counters"}`. Refuses a script that is not a
    sequence of pairs, an unknown program, and a `ticks` or `quantum` that no
    scheduler could run.
    """
    pairs = _script(script)
    default_uid = _count(uid, "a uid")
    budget = _count(ticks, "a tick budget", 1)
    quantum = _count(quantum, "a quantum", 1)
    try:
        kernel = _Run(files, budget, quantum)
    except stage_09.FsError as error:
        raise KernelError("the disk the kernel formatted cannot be mounted: %s"
                          % (error,))
    for name, owner in pairs:
        kernel.start(userland.program(name),
                     default_uid if owner is None else owner,
                     limits, kernel.timer.ticks)
    while kernel.timer.ticks < budget:
        step = kernel.sched.step(kernel.timer.ticks, kernel.tasks)
        pid = step["ran"]
        if pid is None:
            break
        task = kernel.tasks.get(pid)
        if task is None:
            break
        kernel.timer.advance(kernel.one_op(task, kernel.timer.ticks))
    for pid in sorted(kernel.tasks):
        if not kernel.running[pid]["done"]:
            kernel.stop(kernel.tasks[pid], _RUN_OUT, kernel.timer.ticks,
                        limit=_RUN_OUT)
    for pid in sorted(kernel.tasks):
        if pid in kernel.procs.tasks:
            kernel.procs.tasks.pop(pid)
            kernel.line(kernel.tasks[pid], kernel.timer.ticks, "reap", "reap",
                        None, pid, None, 0)
    return {"tasks": kernel.procs, "log": tuple(kernel.log),
            "console": kernel.console, "pool": kernel.pool,
            "disk": kernel.ledger.disk, "audit": tuple(kernel.audit),
            "ticks": kernel.timer,
            "counters": {"mmu": kernel.mmu, "ram": kernel.ram,
                         "records": kernel.ledger}}
