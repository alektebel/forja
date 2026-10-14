"""vfs.py — a filesystem as data, PROVIDED COMPLETE.

The course spans ten stages and every one of them needs a filesystem that can be
read, written, listed and removed from *without touching the real one*: a path is
a string, a file is its text, a directory is a set of paths, and every operation
leaves a record of what it was actually made to touch. Nothing here is timed,
nothing is threaded, and there is no `os`: the whole filesystem is a dictionary,
so two runs of the same call sequence are the same filesystem and a check can
assert the bytes instead of hoping.

It is **deliberately unguarded**, and that is the point: `read()` will hand over
`/etc/passwd` if the tree has it, `write()` will write anywhere the directories
allow, and no path is ever judged against a root. A sandbox is the thing the
course builds, so a filesystem that policed itself would be the answer.

It is also **deliberately unnormalising**. A path that carries an empty, `.` or
`..` component is refused rather than resolved: a real filesystem resolves
`/ws/../etc` the same way the course's own resolver must, and a world that
resolved it for you would be stage 3's answer handed over for free.

The names this module owns:

    VfsError         the module's one refusal family (a ValueError)
    DEFAULT_ROOT     "/home/agent" — the root the course's policy starts from
    SIBLING          "/home/agent-other" — the sibling root a string test lets through
    DEFAULT_FILES    the tree every fresh VFS starts from, path -> text
    DEFAULT_DIRS     the directories that tree needs
    VFS              the filesystem: read, write, remove, list, stat, exists,
                     paths, log, touched

Nothing here knows about jails, capabilities, policies or audits — that is the
course.
"""

from collections.abc import Mapping
from types import MappingProxyType

#: The root a policy is most likely to grant, and the one the course's fixtures
#: are written around.
DEFAULT_ROOT = "/home/agent"

#: The root that *starts with* the default one character for character. A
#: containment test written as `resolved.startswith(root)` hands this whole tree
#: over, which is why it is in the fixture set.
SIBLING = "/home/agent-other"

#: The tree every fresh filesystem starts from, path -> text. The dot-file holds
#: a secret that is also in `tools.SECRETS`, so a leak has somewhere to land.
DEFAULT_FILES = MappingProxyType({
    "/home/agent/notes.md": (
        "# Notes\n"
        "\n"
        "The deploy key lives in the environment, never in this file.\n"
        "Ask the vault for it and pass it to the tool that needs it.\n"
    ),
    "/home/agent/src/main.py": (
        "def main():\n"
        "    return 0\n"
        "\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    ),
    "/home/agent/logs/run.txt": (
        "tick 1 read_file notes.md 47 bytes\n"
        "tick 2 list_dir . 2 entries\n"
    ),
    "/home/agent/.env": (
        "DEPLOY_KEY=sk-live-9f31c2ab7d\n"
        "LOG_LEVEL=info\n"
    ),
    "/home/agent-other/notes.md": (
        "# Notes\n"
        "\n"
        "Another agent's notes. They were never yours to read.\n"
    ),
    "/etc/passwd": "root:x:0:0:root:/root:/bin/sh\n",
})

#: The directories `DEFAULT_FILES` needs, plus the parents a `list()` walks up
#: through: a filesystem whose `/home` is missing cannot list `/home/agent`.
DEFAULT_DIRS = (
    "/",
    "/etc",
    "/home",
    "/home/agent",
    "/home/agent/src",
    "/home/agent/logs",
    "/home/agent-other",
)


class VfsError(ValueError):
    """A path the filesystem will not touch, or a file it does not have.

    Raised for a path that is not a string, is not absolute, is empty, or
    carries an empty, `.` or `..` component; for a read of a file that is not
    there; for a `list` of something that is not a directory; for a `write` into
    a directory the tree does not have; and for a `remove` of a missing file.
    Every message names the path it refused.
    """


def _require_path(path):
    """The path this filesystem accepts, or a refusal that says why not.

    A path here is a string that names its components: absolute, with no empty
    component, and with no `.` or `..` in it. Resolving is the caller's job,
    because the caller is the thing being built.
    """
    if not isinstance(path, str):
        raise VfsError("a path must be a str, got %r" % (path,))
    if not path:
        raise VfsError("a path must not be empty: there is nothing to name")
    if not path.startswith("/"):
        raise VfsError("a path must be absolute, got %r" % (path,))
    if path == "/":
        return path
    for part in path.split("/")[1:]:
        if part == "":
            raise VfsError(
                "a path must not carry an empty component, got %r: %r spells a "
                "component twice" % (path, path))
        if part in (".", ".."):
            raise VfsError(
                "a path with a %r component reached the filesystem unresolved: "
                "%r — resolving a path is the caller's job" % (part, path))
    return path


def _require_text(value, what):
    if not isinstance(value, str):
        raise VfsError("%s must be a str, got %r" % (what, value))
    return value


def _parent(path):
    """The directory a path lives in, as a path (`/a` for `/a/b`, `/` for `/a`)."""
    head, _, tail = path.rpartition("/")
    return head if tail else "/"


class VFS:
    """A filesystem made of dictionaries, with a record of what it was asked to do.

    `files` is path -> text and `dirs` is an iterable of directory paths; both are
    copied on construction, so a `VFS` owns its tree and two of them never share
    a file. Every operation that changes or reads the tree appends to `log()`,
    and `touched()` is the sorted set of paths that log names: the world's own
    answer to "what was I made to touch", which is what the course's audit is
    checked against.

    A question is not a touch: `exists()` and `stat()` answer without touching
    anything, and an operation that refused (a read of a missing file) leaves no
    trace either — the log holds what happened, not what was attempted.
    """

    def __init__(self, files=None, dirs=None):
        source = DEFAULT_FILES if files is None else files
        if not isinstance(source, Mapping):
            raise VfsError("files must be a mapping of path to text, got %r"
                           % (type(source).__name__,))
        self._files = {}
        for path, text in source.items():
            self._files[_require_path(path)] = _require_text(
                text, "the text of %r" % (path,))
        self._dirs = set()
        for path in (DEFAULT_DIRS if dirs is None else dirs):
            self._dirs.add(_require_path(path))
        for path in self._files:
            parent = _parent(path)
            if parent not in self._dirs:
                raise VfsError(
                    "the fixture tree holds %r but not its directory %r"
                    % (path, parent))
        self._log = []

    # -- the questions (no touch, no log entry) ------------------------------

    def exists(self, path):
        """Is there a file at this path?"""
        return _require_path(path) in self._files

    def stat(self, path):
        """`{"path", "bytes", "lines"}` for a file, refusing a missing one."""
        path = _require_path(path)
        text = self._files.get(path)
        if text is None:
            raise VfsError("no such file: %r" % (path,))
        return {"path": path, "bytes": len(text),
                "lines": text.count("\n") + (0 if text.endswith("\n") or not text
                                             else 1)}

    # -- the operations (each one logs what it did) --------------------------

    def read(self, path):
        """The file's text, and a log entry saying it was read."""
        path = _require_path(path)
        text = self._files.get(path)
        if text is None:
            raise VfsError("no such file: %r" % (path,))
        self._log.append(("read", path, len(text)))
        return text

    def write(self, path, text):
        """Write the file, create it if it is not there, return its length."""
        path = _require_path(path)
        text = _require_text(text, "the text written to %r" % (path,))
        parent = _parent(path)
        if parent not in self._dirs:
            raise VfsError("cannot write %r: there is no directory %r"
                           % (path, parent))
        self._files[path] = text
        self._log.append(("write", path, len(text)))
        return len(text)

    def remove(self, path):
        """Delete the file and return its old length."""
        path = _require_path(path)
        if path not in self._files:
            raise VfsError("cannot remove %r: no such file" % (path,))
        text = self._files.pop(path)
        self._log.append(("remove", path, len(text)))
        return len(text)

    def list(self, path):
        """The sorted immediate children of a directory, and a log entry."""
        path = _require_path(path)
        if path not in self._dirs:
            raise VfsError("cannot list %r: not a directory" % (path,))
        prefix = path.rstrip("/") + "/"
        children = []
        for name in self._dirs:
            if name != path and name.startswith(prefix) and "/" not in name[len(prefix):]:
                children.append(name)
        for name in self._files:
            if name.startswith(prefix) and "/" not in name[len(prefix):]:
                children.append(name)
        self._log.append(("list", path, len(children)))
        return tuple(sorted(children))

    # -- the record ----------------------------------------------------------

    def log(self):
        """Every operation this filesystem performed, in order.

        Each entry is `(op, path, bytes)` with `op` one of `"read"`, `"write"`,
        `"list"` or `"remove"`: a tuple and not an object, because a check
        compares it to a hand-written list.
        """
        return tuple(self._log)

    def touched(self):
        """The sorted distinct paths this filesystem was made to touch."""
        return tuple(sorted({path for _, path, _ in self._log}))

    def paths(self):
        """Every file in the tree, sorted."""
        return tuple(sorted(self._files))

    def __repr__(self):
        return "<VFS %d file(s), %d dir(s), %d op(s)>" % (
            len(self._files), len(self._dirs), len(self._log))
