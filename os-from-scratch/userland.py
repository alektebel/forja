"""The userland, as data: the programs a kernel is asked to run.

A kernel that cannot run anything is a very fast way to print characters, so the
last stage has to run programs. On real hardware those programs are ELF files
full of machine code; here they are **scripts of syscalls**, which is the same
thing at the level that matters: a sequence of requests, each of which the kernel
may answer, refuse or fail to find.

A script is a tuple of dicts. Every dict has an `"op"`, and the vocabulary is
closed — a kernel that meets an op it does not know refuses the program by name
rather than guessing:

| op | fields | what it asks for |
|---|---|---|
| `open` | `path`, `flags` (0 read, 1 write), `into` | an fd, stored in the named slot |
| `close` | `fd` | the fd to be released |
| `read` | `fd`, `n`, `into` | up to `n` bytes, stored in the named slot |
| `write` | `fd`, `from` or `bytes` | bytes out: a slot's contents, or a literal |
| `pipe` | `into` | two fds (a reader and a writer), in the two named slots |
| `dup2` | `fd`, `onto` | the named fd to become a copy of `onto` |
| `fork` | `into` | a second task, and its pid in the named slot |
| `wait` | `pid` (optional) | a child's exit status |
| `exit` | `status` | the task to end |
| `anon` | `pages`, `into` | that many fresh frames mapped into the task, and the address |
| `loop` | `n` | `n` ticks of work, and nothing else |
| `limit` | `resource` (of `RESOURCES`), `value` | a resource limit for this task |
| `uid` | `value` | the credentials to run as (`0` is root) |

Operands are either literals (`1`, `b"hello\\n"`, `"/etc/motd"`) or the **name of
a slot** (`"fd"`, `"buf"`, `"pid"`), which is how a program uses the result of
one request in the next. Slots are per task, and a slot that was never filled is
a refusal, never a zero.

`FILES` is the filesystem the course's own formatter is asked to build — a
logical tree, kept here so that the *contents* of a filesystem are a fixture and
its *format* stays the exercise. `SHELL` is what a shell would type: a sequence
of programs, in order, with the uid each one runs as.
"""

class ProgramError(ValueError):
    """Raised for anything the *caller* of this module got wrong."""


#: the resource names a `limit` may name, and what each one bounds
RESOURCES = ("frames", "children", "ticks")

#: uid 0 is root; everything else is an ordinary user
ROOT_UID = 0

#: the ops this vocabulary has. A kernel that meets another one refuses the
#: program by name, which is why this tuple is here and not in the kernel.
OPS = ("open", "close", "read", "write", "pipe", "dup2", "anon", "fork",
       "wait", "exit", "loop", "limit", "uid")

#: the two flags `open` understands
OPEN_READ = 0
OPEN_WRITE = 1

PROGRAMS = {
    # writes five bytes to the console and ends
    "echo": (
        {"op": "write", "fd": 1, "bytes": b"hi\n"},
        {"op": "exit", "status": 0},
    ),
    # opens a file, reads it, prints it, closes it — piped through its own fds
    "cat": (
        {"op": "open", "path": "/etc/motd", "flags": OPEN_READ, "into": "fd"},
        {"op": "read", "fd": "fd", "n": 64, "into": "buf"},
        {"op": "write", "fd": 1, "from": "buf"},
        {"op": "close", "fd": "fd"},
        {"op": "exit", "status": 0},
    ),
    # forks, writes from the child, reaps it, and ends
    "spawn": (
        {"op": "fork", "into": "pid"},
        {"op": "write", "fd": 1, "bytes": b"child\n"},
        {"op": "wait", "into": "status"},
        {"op": "exit", "status": 0},
    ),
    # three ticks of work, forever: the limit case a scheduler exists for
    "hog": (
        {"op": "limit", "resource": "ticks", "value": 12},
        {"op": "loop", "n": 64},
        {"op": "exit", "status": 0},
    ),
    # maps more frames than its own limit allows: refused before the frames move
    "greedy": (
        {"op": "limit", "resource": "frames", "value": 8},
        {"op": "anon", "pages": 64, "into": "addr"},
        {"op": "exit", "status": 0},
    ),
    # a user with no business reading root's file tries to read it
    "nosy": (
        {"op": "uid", "value": 1001},
        {"op": "open", "path": "/root/secret", "flags": OPEN_READ, "into": "fd"},
        {"op": "exit", "status": 0},
    ),
    # two fds in one task: write into a pipe, read it back out
    "piped": (
        {"op": "pipe", "into": ("rd", "wr")},
        {"op": "write", "fd": "wr", "bytes": b"through\n"},
        {"op": "read", "fd": "rd", "n": 16, "into": "buf"},
        {"op": "write", "fd": 1, "from": "buf"},
        {"op": "exit", "status": 0},
    ),
    # a program a kernel does not have: the refusal itself is the fixture
    "unknown": (
        {"op": "teleport", "into": "x"},
        {"op": "exit", "status": 0},
    ),
}

#: what a shell would type, in order: `(program, uid)` pairs
SHELL = (
    ("echo", ROOT_UID),
    ("cat", ROOT_UID),
    ("spawn", ROOT_UID),
    ("piped", ROOT_UID),
    ("nosy", 1001),
)

#: the tree the course's formatter writes: `(path, kind, mode, uid, content)`
#: where `kind` is `"dir"` or `"file"` and a directory's content is empty
FILES = (
    ("/", "dir", 0o755, ROOT_UID, b""),
    ("/etc", "dir", 0o755, ROOT_UID, b""),
    ("/etc/motd", "file", 0o644, ROOT_UID, b"welcome\n"),
    ("/root", "dir", 0o700, ROOT_UID, b""),
    ("/root/secret", "file", 0o600, ROOT_UID, b"not for you\n"),
    ("/home", "dir", 0o755, ROOT_UID, b""),
    ("/home/user", "dir", 0o755, 1001, b""),
    ("/home/user/notes", "file", 0o644, 1001, b"mine\n"),
    ("/tmp", "dir", 0o777, ROOT_UID, b""),
)


def program(name):
    """One program's script, refused by name when it is not one.

    Every call hands back a fresh tuple of fresh dicts: a kernel that edits the
    script it was handed must not edit the fixture the next check reads. The
    *ops* are deliberately not validated here — `"unknown"` is a fixture with an
    op no kernel has, and refusing it is the kernel's job, not this module's.
    """
    if name not in PROGRAMS:
        near = _near(name, tuple(PROGRAMS))
        hint = f" (did you mean {near!r}?)" if near else ""
        raise ProgramError(f"no program named {name!r}{hint}")
    return tuple(dict(step) for step in PROGRAMS[name])


def program_names():
    """The names of the programs, sorted: the vocabulary a caller may pass."""
    return tuple(sorted(PROGRAMS))


def files():
    """The logical tree, as fresh tuples: `(path, kind, mode, uid, content)`."""
    return tuple((path, kind, mode, uid, bytes(content))
                 for path, kind, mode, uid, content in FILES)


def _near(name, names):
    """The one suggestion rule in this course: within Levenshtein distance 2."""
    best, best_d = None, 3
    for candidate in names:
        d = _levenshtein(str(name), str(candidate))
        if d < best_d:
            best, best_d = candidate, d
    return best


def _levenshtein(a, b):
    if a == b:
        return 0
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]
