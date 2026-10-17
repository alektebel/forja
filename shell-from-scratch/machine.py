"""Machine — the deterministic world every stage of this course runs inside.

The machine is a small operating system with no wall clock: a filesystem of
absolute string paths, an environment, a process table, a descriptor table per
process, signals that are delivered at step boundaries, and a scheduler whose
rule is not a race — on every step the *lowest* runnable pid runs, a process
blocked on a pipe yields, and when every runnable process is blocked and no
signal can free one, that is a deadlock the machine records rather than a hang.

Every door is counted (`stats()`), every call is recorded (`transcript()`), and
the only way time passes is `advance(ticks)`: *n* ticks, then every pending
signal is delivered and every runnable process takes one step. A refusal is a
`MachineError` naming the offender; a legal outcome that is bad news — a
deadlock, a signalled child, a full pipe — is data the caller reads back.
"""

MACHINE_VERSION = "machine-1"
SCALE = {"processes": 4096, "fds": 1024, "files": 512, "pipe_bytes": 65536,
         "ticks": 100000, "scripts": 8, "programs": 10}
MAX_STEPS = 100000              # the scheduler's budget for one wait()

#: Every door the ledger can count, seeded to zero so a check that diffs two
#: `stats()` snapshots never meets a key the first call after the snapshot
#: invented.
LEDGER = ("spawn", "fork", "exec", "exit", "wait", "pipe", "give", "open",
          "dup2", "close", "read", "write", "signal", "advance", "ticks",
          "steps", "deadlocks", "store", "append", "remove", "files",
          "exists", "load", "listing", "modes", "is_dir", "size", "env",
          "getenv", "setenv", "unsetenv", "cwd", "chdir", "fd", "fds", "argv",
          "state", "status", "parent_of", "processes", "reapable", "pending",
          "buffered", "terminal")

#: The signals whose default action ends the process, and what it answers.
_KILLING = ("HUP", "INT", "QUIT", "TERM")

#: The descriptor numbers every process is born with, on the terminal.
_STDIO = (0, 1, 2)


class MachineError(ValueError):
    """Raised for anything the *caller* of this module got wrong."""


def machine(seed=7):
    """A fresh, deterministic Machine; the seed is accepted and changes nothing."""
    return Machine()


class _File:
    """One file: bytes, a mode, and whether it is a directory."""

    def __init__(self, mode=0o644, directory=False):
        self.data = b""
        self.mode = mode
        self.directory = directory


class _Process:
    """One process: its argv, table, descriptors, and what it has answered."""

    def __init__(self, pid, parent, argv):
        self.pid = pid
        self.parent = parent
        self.argv = argv
        self.state = "running"
        self.status = None
        self.signalled = False
        self.signal = None
        self.fds = dict((number, {"kind": "terminal", "target": "terminal",
                                  "append": False, "at": 0})
                        for number in _STDIO)
        self.program = None
        self.pending = ()


class Machine:
    """The world: the filesystem, the environment, the table, and the record."""

    # --- construction -------------------------------------------------------

    def __init__(self):
        self._files = {"/": _File(0o755, True)}
        self._seed()
        self._env = {"HOME": "/home", "PATH": "/bin"}
        self._cwd = "/"
        self._processes = {}
        self._shell = _Process(0, None, ())
        self._next_pid = 1
        self._tick = 0
        self._terminal = b""
        self._transcript = ()
        self._stats = dict((name, 0) for name in LEDGER)
        self._pipes = {}
        self._next_pipe = 1
        self._deadlocks = ()

    def _seed(self):
        """The world's own population, and the one a glob has to be able to read.

        The filesystem is the fixture every stage shares: a home with files in
        it, a `/etc` with two, and names chosen so a `*` can be told from a `/`,
        a `?` from a letter, and one sorted order from another. A stage that
        needs a different population stores it; the machine never re-seeds.
        """
        for path, data in (("/home/readme.txt", b"shell from scratch\n"),
                           ("/home/notes.txt", b"the machine is the record\n"),
                           ("/home/z-a.txt", b"order matters\n"),
                           ("/home/.hidden", b"a name a glob can name\n"),
                           ("/etc/motd", b"welcome\n"),
                           ("/etc/hosts", b"localhost\n")):
            self._files[path] = _File(0o644, False)
            self._files[path].data = data
        for path in ("/home", "/etc"):
            self._files[path] = _File(0o755, True)

    def _note(self, call, *args):
        """One counted, recorded door: every accessor calls this exactly once."""
        self._stats[call] = self._stats.get(call, 0) + 1
        self._transcript = self._transcript + (
            {"tick": self._tick, "pid": self._cwd_pid(), "call": call,
             "args": args, "result": None},)

    def _record_only(self, call, *args):
        """A door the world hears but the ledger does not count.

        Reading the transcript is not a move in the world: it is *recorded*
        like any other door — the transcript is the machine's own memory, and
        a reading belongs in it — but the reading must not count the reading,
        because a check that diffs two `stats()` snapshots would then see the
        difference the reading itself made.
        """
        self._transcript = self._transcript + (
            {"tick": self._tick, "pid": self._cwd_pid(), "call": call,
             "args": args, "result": None},)

    def _cwd_pid(self):
        """The pid a door is recorded under: the shell's own is not in the table."""
        return None

    def _refuse(self, call, what, offender):
        """A refusal names its offender: the door, and what was wrong about it."""
        raise MachineError("%s: %s (%r)" % (call, what, offender))

    # --- the filesystem -----------------------------------------------------

    def files(self):
        """Every path the machine holds, sorted."""
        self._note("files")
        return tuple(sorted(self._files))

    def exists(self, path):
        """Whether `path` is held; a non-str path is refused."""
        self._note("exists", path)
        if not isinstance(path, str):
            self._refuse("exists", "a path is a string", path)
        return path in self._files

    def is_dir(self, path):
        """Whether `path` is a directory; a path the machine does not hold is not."""
        self._note("is_dir", path)
        if not isinstance(path, str):
            self._refuse("is_dir", "a path is a string", path)
        held = self._files.get(path)
        return bool(held and held.directory)

    def size(self, path):
        """The byte size of `path`, refusing a missing path naming it."""
        self._note("size", path)
        held = self._files.get(path) if isinstance(path, str) else None
        if held is None:
            self._refuse("size", "the machine holds no such file", path)
        if held.directory:
            self._refuse("size", "a directory has no size", path)
        return len(held.data)

    def load(self, path):
        """The bytes of `path`, refusing a missing path naming it."""
        self._note("load", path)
        held = self._files.get(path) if isinstance(path, str) else None
        if held is None:
            self._refuse("load", "the machine holds no such file", path)
        if held.directory:
            self._refuse("load", "a directory has no bytes", path)
        return held.data

    def store(self, path, data):
        """Write `data` over `path`, creating parent directories; answer the size."""
        self._note("store", path)
        if not isinstance(path, str) or not path.startswith("/"):
            self._refuse("store", "a path is an absolute string", path)
        if not isinstance(data, (bytes, bytearray)):
            self._refuse("store", "a file's contents are bytes", data)
        data = bytes(data)
        held = self._files.get(path)
        if held is not None and held.directory:
            self._refuse("store", "a directory holds no bytes", path)
        if held is None:
            self._mkdirs(path)
            held = self._files.setdefault(path, _File())
        held.data = data
        held.mode = 0o644
        return len(data)

    def append(self, path, data):
        """Add `data` to the end of `path`, creating it when it is not there."""
        self._note("append", path, len(bytes(data)) if isinstance(data,
                                                                  (bytes, bytearray)) else data)
        if not isinstance(path, str) or not path.startswith("/"):
            self._refuse("append", "a path is an absolute string", path)
        if not isinstance(data, (bytes, bytearray)):
            self._refuse("append", "a file's contents are bytes", data)
        held = self._files.get(path)
        if held is None:
            self._mkdirs(path)
            held = self._files.setdefault(path, _File())
        if held.directory:
            self._refuse("append", "a directory holds no bytes", path)
        held.data = held.data + bytes(data)
        return len(held.data)

    def remove(self, path):
        """Take `path` out of the filesystem, refusing one that is not there."""
        self._note("remove", path)
        if path not in self._files:
            self._refuse("remove", "the machine holds no such file", path)
        if path == "/":
            self._refuse("remove", "the root is not a file", path)
        del self._files[path]
        for name in tuple(self._files):
            if name.startswith(path + "/"):
                del self._files[name]

    def listing(self, path):
        """The names held directly inside `path`, sorted; a file refuses."""
        self._note("listing", path)
        held = self._files.get(path)
        if held is None:
            self._refuse("listing", "the machine holds no such directory", path)
        if not held.directory:
            self._refuse("listing", "a file has no listing", path)
        names = set()
        for name in self._files:
            if name.startswith(path if path.endswith("/") else path + "/"):
                rest = name[len(path if path.endswith("/") else path + "/"):]
                if rest and "/" not in rest:
                    names.add(rest)
        return tuple(sorted(names))

    def modes(self, path):
        """`0o755` for a directory, else the file's mode; a missing path refuses."""
        self._note("modes", path)
        held = self._files.get(path)
        if held is None:
            self._refuse("modes", "the machine holds no such file", path)
        return 0o755 if held.directory else held.mode

    def _mkdirs(self, path):
        """Create every parent directory `path` needs, and refuse a file in the way."""
        parts = path.strip("/").split("/")
        here = ""
        for part in parts[:-1]:
            here = here + "/" + part
            held = self._files.get(here)
            if held is None:
                self._files[here] = _File(0o755, True)
            elif not held.directory:
                self._refuse("store", "a file stands where a directory is due", here)

    # --- the environment ----------------------------------------------------

    def env(self):
        """The environment as `"NAME=value"` strings, sorted by name."""
        self._note("env")
        return tuple(sorted("%s=%s" % (name, self._env[name])
                            for name in self._env))

    def getenv(self, name):
        """The value of `name`, or `None` when it is not set."""
        self._note("getenv", name)
        if not isinstance(name, str):
            self._refuse("getenv", "a name is a string", name)
        return self._env.get(name)

    def setenv(self, name, value):
        """Set `name` to `value`; both are strings or the call refuses."""
        self._note("setenv", name)
        if not isinstance(name, str) or not name:
            self._refuse("setenv", "a name is a non-empty string", name)
        if not isinstance(value, str):
            self._refuse("setenv", "a value is a string", value)
        self._env[name] = value

    def unsetenv(self, name):
        """Take `name` out of the environment; one that is not there is not news."""
        self._note("unsetenv", name)
        if not isinstance(name, str):
            self._refuse("unsetenv", "a name is a string", name)
        self._env.pop(name, None)

    def cwd(self):
        """The shell's own working directory."""
        self._note("cwd")
        return self._cwd

    def chdir(self, path):
        """Move the shell's own working directory to `path`, which must be a directory."""
        self._note("chdir", path)
        held = self._files.get(path) if isinstance(path, str) else None
        if held is None or not held.directory:
            self._refuse("chdir", "the machine holds no such directory", path)
        self._cwd = path

    # --- the process table ---------------------------------------------------

    def _new_pid(self):
        """The next pid, or the refusal when the table is full."""
        if self._next_pid >= SCALE["processes"]:
            self._refuse("spawn", "the machine's process table is full",
                         SCALE["processes"])
        pid = self._next_pid
        self._next_pid += 1
        return pid

    def spawn(self, argv, argv0=None, parent=None):
        """Fork and exec in one call: a new process born to run `argv` now.

        `parent` is the pid the child is born to (`None` is the shell's own
        process); the child inherits the parent's descriptors, environment and
        working directory, and its program is the one `argv0` (default: the
        first word) names.
        """
        self._note("spawn", tuple(argv) if isinstance(argv, (tuple, list)) else argv,
                   argv0, parent)
        if isinstance(argv, str) or not isinstance(argv, (tuple, list)) or not argv:
            self._refuse("spawn", "an argv is a non-empty sequence of strings", argv)
        for word in argv:
            if not isinstance(word, str):
                self._refuse("spawn", "an argv holds strings", word)
        if parent is not None and parent not in self._processes:
            self._refuse("spawn", "no process holds the parent pid", parent)
        pid = self._new_pid()
        source = self._processes.get(parent) if parent is not None else None
        process = _Process(pid, parent, tuple(argv))
        if source is not None:
            process.fds = dict((number, dict(spec))
                               for number, spec in source.fds.items())
        self._processes[pid] = process
        self._stats["fork"] += 1
        name = argv0 if argv0 is not None else argv[0]
        self.exec(pid, argv, argv0)
        return pid

    def fork(self, parent):
        """A pid whose process is a copy of `parent`'s, with no program of its own."""
        self._note("fork", parent)
        source = self._processes.get(parent)
        if source is None:
            self._refuse("fork", "no process holds the parent pid", parent)
        pid = self._new_pid()
        process = _Process(pid, parent, source.argv)
        process.fds = dict((number, dict(spec))
                           for number, spec in source.fds.items())
        self._processes[pid] = process
        return pid

    def exec(self, pid, argv, argv0=None):
        """`pid` becomes the program `argv` names; its descriptors stay as they are."""
        self._note("exec", pid, tuple(argv) if isinstance(argv, (tuple, list))
                   else argv, argv0)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("exec", "no process holds the pid", pid)
        if isinstance(argv, str) or not isinstance(argv, (tuple, list)) or not argv:
            self._refuse("exec", "an argv is a non-empty sequence of strings", argv)
        process.argv = tuple(argv)
        process.program = argv0 if argv0 is not None else argv[0]
        self._stats["exec"] += 1

    def exit(self, pid, status):
        """`pid` answers `status`; the machine reaps nothing on the caller's behalf."""
        self._note("exit", pid, status)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("exit", "no process holds the pid", pid)
        if isinstance(status, bool) or not isinstance(status, int) \
                or not 0 <= status <= 255:
            self._refuse("exit", "a status is an int in 0..255", status)
        self._finish(process, status, False, None)

    def _finish(self, process, status, signalled, signal):
        """One process stops being runnable, with the answer it leaves behind."""
        process.state = "exited"
        process.status = status
        process.signalled = signalled
        process.signal = signal
        self._release(process)

    def _release(self, process):
        """A process that stops closes its descriptors, which may free its readers."""
        for number in sorted(process.fds):
            self._drop(process, number)
        process.fds = {}

    def _drop(self, process, number):
        """Take `number` away from `process`; a pipe whose writers are all gone closes.

        A pipe's liveness is a fact about its descriptors and not a list to keep
        in step: after a drop, the pipe is open exactly while some process still
        holds its write end — the shell's own write fd, or a child's.
        """
        spec = process.fds.pop(number, None)
        if spec is None or spec["kind"] != "pipe":
            return
        pipe = self._pipes.get(spec["target"])
        if pipe is None:
            return
        if not self._writers_of(spec["target"], process.pid):
            pipe["open"] = False

    def _writers_of(self, name, gone):
        """The pids other than `gone` that still hold a write end of `name`."""
        writers = []
        for pid, process in [(0, self._shell)] + sorted(self._processes.items()):
            if pid == gone or pid != 0 and process.state in ("exited", "waited"):
                continue
            for spec in process.fds.values():
                if spec["kind"] != "pipe" or not spec.get("write"):
                    continue
                pipe = self._pipe_of(spec["target"])
                if pipe is self._pipes.get(name):
                    writers.append(pid)
        return writers

    def wait(self, pid):
        """Run the machine until `pid` is reaped, and answer what it left behind.

        The scheduler runs under this call: as many rounds of `advance` as the
        process needs, within `MAX_STEPS`. A process that cannot make progress
        anywhere is a deadlock the machine records, and this answers the record
        instead of hanging.
        """
        self._note("wait", pid)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("wait", "no process holds the pid", pid)
        waited = self._processes.get(pid)
        steps = 0
        known = len(self._deadlocks)
        while waited.state == "running" and steps < MAX_STEPS:
            self.advance(1)
            steps += 1
            if len(self._deadlocks) > known:
                break
        if waited.state == "running":
            return {"pid": pid, "status": None, "signalled": False,
                    "signal": None, "core": False}
        waited.state = "waited"
        return {"pid": pid, "status": waited.status, "signalled": waited.signalled,
                "signal": waited.signal, "core": False}

    def reapable(self):
        """The pids that have exited and are not yet waited for, in pid order."""
        self._note("reapable")
        return tuple(sorted(pid for pid, process in self._processes.items()
                            if process.state == "exited"))

    def processes(self):
        """Every pid the table holds, sorted."""
        self._note("processes")
        return tuple(sorted(self._processes))

    def state(self, pid):
        """`"running"`, `"exited"`, `"stopped"` or `"waited"` for `pid`."""
        self._note("state", pid)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("state", "no process holds the pid", pid)
        return process.state

    def status(self, pid):
        """The status `pid` answered, or `None` before it has exited."""
        self._note("status", pid)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("status", "no process holds the pid", pid)
        return process.status

    def parent_of(self, pid):
        """The pid `pid` was born to, or `None` for the shell's own children."""
        self._note("parent_of", pid)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("parent_of", "no process holds the pid", pid)
        return process.parent

    def argv(self, pid):
        """The words `pid` was given, or `None` before an exec has named any."""
        self._note("argv", pid)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("argv", "no process holds the pid", pid)
        return process.argv

    # --- descriptors ----------------------------------------------------------

    def fds(self, pid):
        """The descriptor numbers `pid` holds, sorted."""
        self._note("fds", pid)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("fds", "no process holds the pid", pid)
        return tuple(sorted(process.fds))

    def fd(self, pid, number):
        """The record of one descriptor: `{"fd", "kind", "target", "append", "at"}`."""
        self._note("fd", pid, number)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("fd", "no process holds the pid", pid)
        spec = process.fds.get(number)
        if spec is None:
            self._refuse("fd", "the process holds no such descriptor", number)
        return dict(spec, fd=number)

    def open(self, pid, path, mode):
        """Open `path` for `pid` in `"read"`, `"write"` or `"append"`, answering the fd.

        A `"read"` of a path the machine does not hold, and any open of a
        directory, are refusals: the caller's mistake, not bad news in the world.
        A `"write"` or `"append"` of a path the machine does not hold makes the
        file, the way a shell's own `>` does — a redirection is a promise to
        produce the file, and a world that refused it could not keep one.
        """
        self._note("open", pid, path, mode)
        process = self._processes.get(pid) if pid else self._shell
        if process is None:
            self._refuse("open", "no process holds the pid", pid)
        if mode not in ("read", "write", "append"):
            self._refuse("open", "a mode is read, write or append", mode)
        held = self._files.get(path) if isinstance(path, str) else None
        if held is None:
            if mode == "read" or not isinstance(path, str):
                self._refuse("open", "the machine holds no such file", path)
            held = _File(0o644, False)
            self._files[path] = held
        if held.directory:
            self._refuse("open", "a directory cannot be opened as a file", path)
        if mode not in ("read", "write", "append"):
            self._refuse("open", "a mode is read, write or append", mode)
        number = self._free_fd(process)
        process.fds[number] = {"kind": "file", "target": path,
                               "append": mode == "append", "at": 0}
        return number

    def _free_fd(self, process):
        """The smallest descriptor number `process` does not hold."""
        number = 0
        while number in process.fds:
            number += 1
        if number >= SCALE["fds"]:
            self._refuse("open", "the process's descriptor table is full",
                         SCALE["fds"])
        return number

    def dup2(self, pid, source, target):
        """Make `target` a copy of `source` for `pid`, closing what was there."""
        self._note("dup2", pid, source, target)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("dup2", "no process holds the pid", pid)
        if source not in process.fds:
            self._refuse("dup2", "the process holds no such source descriptor",
                         source)
        if isinstance(target, bool) or not isinstance(target, int) \
                or not 0 <= target < SCALE["fds"]:
            self._refuse("dup2", "a target descriptor is an int the table holds",
                         target)
        process.fds[target] = dict(process.fds[source])
        return target

    def close(self, pid, number):
        """Take `number` away from `pid`; one it does not hold is a refusal."""
        self._note("close", pid, number)
        process = self._processes.get(pid) if pid else self._shell
        if process is None:
            self._refuse("close", "no process holds the pid", pid)
        if number not in process.fds:
            self._refuse("close", "the process holds no such descriptor", number)
        self._drop(process, number)

    def pipe(self):
        """A new pipe for the shell's own use, answering `(read_fd, write_fd)`.

        The ends are descriptors of the shell's own (a pid of `None`), which is
        what lets a plan hand them to children with `give`. The pipe itself is
        named after its read end, so a `give` can be asked for either end by
        number and find the one pipe behind both.
        """
        self._note("pipe")
        shell = self._shell_process()
        read_fd = self._free_fd(shell)
        shell.fds[read_fd] = {"kind": "pipe", "target": read_fd, "append": False,
                              "at": 0}
        write_fd = self._free_fd(shell)
        self._pipes[read_fd] = {"data": b"", "open": True,
                                "capacity": SCALE["pipe_bytes"],
                                "write_fd": write_fd}
        shell.fds[write_fd] = {"kind": "pipe", "target": write_fd, "append": False,
                               "at": 0, "write": True}
        return read_fd, write_fd

    def _shell_process(self):
        """The shell's own process record: pipes live here, not in the table.

        A check that counts the machine's processes counts the machine's
        *processes*, and the shell that drove them is not one of them.
        """
        return self._shell

    def give(self, pid, number, fd):
        """Hand `pid` the descriptor `fd` — a pipe end the shell was holding.

        `fd` is one of the two ends `pipe()` answered: the read end moves as it
        stands, and the write end carries the pipe's `at` watermark so a writer
        that arrives later appends rather than overwrites. Either way the
        descriptor is *transferred*: the shell does not keep a copy, which is
        why a pipe whose children have both died is closed.
        """
        self._note("give", pid, number, fd)
        shell = self._shell_process()
        spec = shell.fds.get(fd)
        if spec is None or spec["kind"] != "pipe":
            self._refuse("give", "no pipe end answers the descriptor", fd)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("give", "no process holds the pid", pid)
        if isinstance(number, bool) or not isinstance(number, int) \
                or not 0 <= number < SCALE["fds"]:
            self._refuse("give", "a descriptor number is an int the table holds",
                         number)
        target = spec["target"]
        pipe = self._pipe_of(target)
        if pipe is None:
            self._refuse("give", "no pipe end answers the descriptor", fd)
        writing = pipe["write_fd"] == fd
        at = len(pipe["data"]) if writing else 0
        process.fds[number] = {"kind": "pipe", "target": target, "append": False,
                               "at": at, "write": writing}
        del shell.fds[fd]
        return number

    def _pipe_of(self, name):
        """The pipe a descriptor's target names — the read end is the pipe itself.

        A write end carries its own number as its target, so a lookup by a
        write end resolves to the pipe it belongs to: the one whose read end
        the data sits behind.
        """
        if name in self._pipes:
            return self._pipes[name]
        for read_fd, pipe in self._pipes.items():
            if pipe.get("write_fd") == name:
                return pipe
        return None

    def read(self, pid, number, count):
        """Up to `count` bytes for `pid` from `number`; a blocked empty pipe yields.

        A pipe whose writers are all gone answers the bytes it still holds, then
        the end of input; a pipe that is empty with a live writer leaves the
        process blocked, which is how a deadlock is born.
        """
        self._note("read", pid, number, count)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("read", "no process holds the pid", pid)
        spec = process.fds.get(number)
        if spec is None:
            self._refuse("read", "the process holds no such descriptor", number)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            self._refuse("read", "a count is a small non-negative int", count)
        if spec["kind"] == "file":
            held = self._files[spec["target"]]
            data = held.data[spec["at"]:spec["at"] + count]
            spec["at"] += len(data)
            return data
        if spec["kind"] == "terminal":
            return b""
        pipe = self._pipe_of(spec["target"])
        data = pipe["data"][:count]
        pipe["data"] = pipe["data"][len(data):]
        spec["at"] += len(data)
        return data

    def write(self, pid, number, data):
        """`data` written for `pid` onto `number`; a full pipe blocks, a dead one refuses."""
        self._note("write", pid, number,
                   len(bytes(data)) if isinstance(data, (bytes, bytearray)) else data)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("write", "no process holds the pid", pid)
        spec = process.fds.get(number)
        if spec is None:
            self._refuse("write", "the process holds no such descriptor", number)
        if not isinstance(data, (bytes, bytearray)):
            self._refuse("write", "what a process writes is bytes", data)
        data = bytes(data)
        if spec["kind"] == "file":
            held = self._files[spec["target"]]
            if spec["append"]:
                held.data = held.data + data
            else:
                held.data = held.data[:spec["at"]] + data \
                    + held.data[spec["at"] + len(data):]
                spec["at"] += len(data)
            return len(data)
        if spec["kind"] == "terminal":
            self._terminal = self._terminal + data
            return len(data)
        pipe = self._pipe_of(spec["target"])
        if not pipe["open"]:
            self._refuse("write", "the pipe's reader is gone", number)
        if len(pipe["data"]) + len(data) > pipe["capacity"]:
            return 0
        pipe["data"] = pipe["data"] + data
        return len(data)

    def terminal(self):
        """The bytes the shell's own stdout has collected so far."""
        self._note("terminal")
        return self._terminal

    def buffered(self, read_fd):
        """The bytes still unread in the pipe `read_fd` names."""
        self._note("buffered", read_fd)
        shell = self._shell_process()
        spec = shell.fds.get(read_fd)
        if spec is None or spec["kind"] != "pipe":
            self._refuse("buffered", "the shell holds no such pipe end", read_fd)
        pipe = self._pipe_of(spec["target"])
        return pipe["data"]

    # --- signals ---------------------------------------------------------------

    def signal(self, pid, name):
        """Send `name` to `pid`; the name is the machine's own, and delivery waits."""
        self._note("signal", pid, name)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("signal", "no process holds the pid", pid)
        if name not in _SIGNAL_NAMES:
            self._refuse("signal", "no such signal", name)
        if process.state in ("exited", "waited"):
            return
        process.pending = process.pending + (name,)

    def pending(self, pid):
        """The signal names `pid` carries and has not been delivered yet."""
        self._note("pending", pid)
        process = self._processes.get(pid)
        if process is None:
            self._refuse("pending", "no process holds the pid", pid)
        return process.pending

    def advance(self, ticks=1):
        """The only way time passes: deliver signals, then step the runnable."""
        self._note("advance", ticks)
        if isinstance(ticks, bool) or not isinstance(ticks, int) \
                or ticks < 0 or ticks > SCALE["ticks"]:
            self._refuse("advance", "a tick count is a small non-negative int", ticks)
        for _ in range(ticks):
            self._tick += 1
            self._stats["ticks"] += 1
            self._deliver()
            self._step()

    def _deliver(self):
        """Every pending signal is delivered now, in the order it was sent."""
        for pid in sorted(self._processes):
            process = self._processes[pid]
            if process.state in ("exited", "waited"):
                process.pending = ()
                continue
            while process.pending:
                name = process.pending[0]
                process.pending = process.pending[1:]
                self._apply(pid, name)

    def _apply(self, pid, name):
        """What one delivered signal does to `pid` under the machine's own defaults."""
        process = self._processes[pid]
        if name in _KILLING:
            number = {"HUP": 1, "INT": 2, "QUIT": 3, "TERM": 15}[name]
            self._finish(process, 128 + number, True, name)
        elif name == "CHLD":
            pass
        elif name == "STOP":
            if process.state == "running":
                process.state = "stopped"
                process.signal = name
        elif name == "CONT":
            if process.state == "stopped":
                process.state = "running"
                process.signal = None

    def _step(self):
        """One round of the scheduler: the lowest runnable pid takes one step.

        A round where the one runnable process cannot consume anything — its
        program reads a pipe that is empty and whose writers live — is a
        process the machine can make no progress on; when a whole round leaves
        the world where it was, that is a deadlock, recorded once and counted.
        """
        runnable = [pid for pid, process in sorted(self._processes.items())
                    if process.state == "running" and process.program]
        if not runnable:
            return
        pid = runnable[0]
        process = self._processes[pid]
        before = (len(self._terminal), sum(len(pipe["data"])
                                           for pipe in self._pipes.values()))
        self._stats["steps"] += 1
        self._run_step(process)
        spent = getattr(process, "worked", 0) >= self._budget_of(process)
        if process.state == "running" and spent \
                and not self._progressed(process, before):
            self._record_deadlock([pid], self._blocked_fds(process))

    def _budget_of(self, process):
        """The step budget of the program `process` is running, or 0 for none."""
        import programs
        spec = programs.program(process.program)
        return spec["steps"] if spec else 0

    def _progressed(self, process, before):
        """Whether the world moved for `process` this round: bytes anywhere."""
        after = (len(self._terminal), sum(len(pipe["data"])
                                          for pipe in self._pipes.values()))
        return after != before

    def _blocked_fds(self, process):
        """The descriptors `process` was reading when the machine stopped."""
        return tuple(number for number, spec in sorted(process.fds.items())
                     if spec["kind"] == "pipe")

    def _run_step(self, process):
        """One step of `process`'s program: the machine runs the world's programs.

        The program's bytes are the world's own (`programs.py`), and a step is
        one unit of the cost `programs.program(name)["steps"]` priced. A program
        that cannot make progress — a `cat` with nothing to read — yields, and
        when nothing anywhere can run the machine records a deadlock.
        """
        import programs
        name = process.program
        if name not in programs.PROGRAM_NAMES:
            self._finish(process, 127, False, None)
            return
        spec = programs.program(name)
        if process.state != "running":
            return
        budget = spec["steps"]
        done = getattr(process, "worked", 0)
        process.worked = done + 1
        if process.worked < budget:
            return
        if spec["stdin"]:
            data = self._consume(process)
            if data is None:
                return
        else:
            data = b""
        self._run_program(process, name, spec, data)

    def _run_program(self, process, name, spec, data):
        """The program's own effect, once its step budget is spent.

        `data` is what the program read this round: what a streaming program
        transforms, and nothing for one that produces from its argv alone.
        """
        argv = process.argv
        args = argv[1:]
        if name == "echo":
            self.write(process.pid, 1, (" ".join(args) + "\n").encode())
            self._finish(process, 0, False, None)
        elif name == "pwd":
            self.write(process.pid, 1, (self._cwd + "\n").encode())
            self._finish(process, 0, False, None)
        elif name == "env":
            self.write(process.pid, 1,
                       "".join(line + "\n" for line in self.env()).encode())
            self._finish(process, 0, False, None)
        elif name == "true":
            self._finish(process, 0, False, None)
        elif name == "false":
            self._finish(process, 1, False, None)
        elif name == "tick":
            self._finish(process, 0, False, None)
        else:
            self._stream(process, name, args, data)

    def _stream(self, process, name, args, data):
        """The programs that read and write: `cat`, `head`, `grep`, `sort`, `wc`.

        The bytes were consumed by the step that called here (`_run_step`); a
        stream program transforms what it was handed and writes the answer.
        """
        out = self._transform(name, args, data)
        if out is None:
            return
        self.write(process.pid, 1, out)
        self._finish(process, 0, False, None)

    def _consume(self, process):
        """The bytes the program can read now, or `None` while it must wait.

        A program that names files in its argv reads those (`cat`, and the rest
        ignore the names); one that does not reads its own fd 0, which is a
        file, a pipe, or the terminal. An empty pipe with a live writer is the
        one answer that is not bytes: the program must wait.
        """
        named = [word for word in process.argv[1:] if not word.startswith("-")]
        if named and process.program == "cat" and self.exists(named[0]):
            return self.load(named[0])
        spec = process.fds.get(0)
        if spec is None:
            return b""
        if spec["kind"] == "file":
            return self.read(process.pid, 0, 1 << 20)
        pipe = self._pipe_of(spec["target"])
        if pipe is None:
            return b""
        if pipe["data"]:
            return self.read(process.pid, 0, 1 << 20)
        if not self._writers_of(spec["target"], process.pid):
            return b""
        return None

    def _transform(self, name, args, data):
        """The program's answer for the bytes it read, or `None` to wait."""
        lines = data.decode("utf-8", "replace").split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
        if name == "cat":
            return data
        if name == "head":
            count = 10
            if "-n" in args:
                where = args.index("-n")
                if where + 1 < len(args) and args[where + 1].isdigit():
                    count = int(args[where + 1])
            return "".join(line + "\n" for line in lines[:count]).encode()
        if name == "grep":
            pattern = args[0] if args else ""
            return "".join(line + "\n" for line in lines
                           if pattern in line).encode()
        if name == "sort":
            return "".join(line + "\n" for line in sorted(lines)).encode()
        if name == "wc":
            flag = "-l" if "-l" in args else ("-c" if "-c" in args else None)
            if flag == "-l":
                return ("%d\n" % (len(lines),)).encode()
            if flag == "-c":
                return ("%d\n" % (len(data),)).encode()
            return ("%d %d %d\n" % (len(lines), len(data.split()), len(data))).encode()
        return b""

    # --- the record --------------------------------------------------------------

    def transcript(self):
        """Every door call so far, in order: `{"tick", "pid", "call", "args", "result"}`.

        Reading the transcript is not a move in the world either, so the reading
        is recorded like any other door but not counted as work.
        """
        self._record_only("transcript")
        return self._transcript

    def stats(self):
        """The ledger: how many times each door was asked, and what the machine spent.

        Reading the ledger is not a move in the world, so the reading itself is
        not counted: a check that compares two `stats()` readings sees the world
        and not the reading of it.
        """
        return dict(self._stats)

    def deadlocks(self):
        """Every place the machine stopped: `{"pids", "fds", "tick"}` each.

        Reading the places is not a move in the world and is not counted: the
        ledger's own `deadlocks` counts the deadlock the machine *recorded*, and
        this door reads the list of them — one reading must not make another.
        """
        return self._deadlocks

    def _record_deadlock(self, pids, fds):
        """One deadlock is data: recorded once per situation, counted, answered.

        The same blocked process is one deadlock, not one per round: a situation
        already recorded for the same pids is not recorded again, so `deadlocks()`
        answers the places the machine stopped and not the rounds it spent there.
        """
        key = tuple(sorted(pids))
        for row in self._deadlocks:
            if row["pids"] == key:
                return
        self._deadlocks = self._deadlocks + (
            {"pids": key, "fds": tuple(fds), "tick": self._tick},)
        self._stats["deadlocks"] += 1


#: The machine's own signal names, which are the policy's and live here too so a
#: signal can be refused before the policy is imported.
_SIGNAL_NAMES = ("HUP", "INT", "QUIT", "TERM", "CHLD", "STOP", "CONT")
