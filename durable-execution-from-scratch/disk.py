"""disk.py — a disk with a sync barrier, PROVIDED COMPLETE.

The whole course rests on this file, so it is given, and it is small. A disk is a
mapping from path to text with exactly one rule: **a write is not durable until
it is synced.**

The rule is what makes a crash a *reproducible* failure instead of a race. Real
storage loses, on a power cut, whatever was written and not flushed — and a
program that reads back its own unflushed write cannot tell the difference
between "this happened" and "this is in my cache". Here the two are separate
methods: `read` shows what the program can see (synced *plus* volatile, because a
program that reads what it just wrote must see it), and `synced` shows what a
crash would keep.

    disk = Disk()
    disk.write("/log", "a")
    disk.synced("/log")          # ""    — nothing is durable yet
    disk.sync()
    disk.write("/log", "b")
    disk.crash()                 # (("/log", "b"),) — "a" survived, "b" did not
    disk.read("/log")            # "a"

`replace` stages a whole-file rewrite (a checkpoint) rather than an append, and
it is equally volatile: after a `replace` the path reads the new text, and after
a crash without a sync it reads the old one — never a mixture, because a
checkpoint that is half-written is the failure stage 8 exists to refuse.

Nothing here reads the real filesystem, a clock or a random source: the disk is
an object, the tick is a number the caller passes, and every method is a function
of what was written before it. That is what makes "what would a crash cost right
now?" a question a check can ask with an answer it can assert.

    DEFAULT_JOURNAL  the path the course writes its journal to
    Disk             the disk itself
    DiskError        a path, or a write, this disk refuses
"""

#: Where a run's journal lives. The course's provided world owns the path,
#: because a path is a fact about the disk and not about any one stage.
DEFAULT_JOURNAL = "/var/log/durable/journal"


class DiskError(ValueError):
    """A path or a write this disk refuses.

    Every refusal names the path, or the value that was not text: a disk that
    quietly coerced a non-string write is a disk whose journal cannot be parsed
    back, and the failure would surface three stages later.
    """


def _path(value):
    """A path: a non-empty `str` beginning with `/`.

    A relative path is refused rather than resolved: the course has one
    directory of things, and a path that depends on where a program was started
    is a path that makes two runs differ.
    """
    if not isinstance(value, str) or not value.startswith("/") or len(value) < 2:
        raise DiskError(
            "a path must be a str beginning with '/', got %r" % (value,))
    return value


def _text(value, what):
    """A write's payload: a `str`. Bytes would smuggle in an encoding, and the
    course counts characters everywhere else."""
    if not isinstance(value, str):
        raise DiskError("%s must be a str, got %s" % (what, type(value).__name__))
    return value


class Disk:
    """A disk as a mapping from path to text, with a volatile buffer.

    `write` appends, `replace` stages a rewrite, `sync` makes everything so far
    durable, and `crash` throws away exactly what was not. Every method returns
    something a caller can assert on, so that no test has to trust a
    side effect: `write` and `replace` return the length the path would read,
    `sync` returns how many characters it flushed, and `crash` returns the pairs
    it lost, sorted by path.
    """

    def __init__(self):
        self._durable = {}   # path -> text, what a crash keeps
        self._buffer = []    # [(path, "write" | "replace", text)], in order

    # --- writing ---------------------------------------------------------
    def write(self, path, text):
        """Append `text` to `path`, in the volatile buffer.

        Returns the length `path` reads right now — which is not the same as the
        length a crash would keep. See `sync`.
        """
        _path(path)
        _text(text, "a write")
        self._buffer.append((path, "write", text))
        return self.size(path)

    def replace(self, path, text):
        """Stage a whole-file rewrite of `path`, in the volatile buffer.

        Not an append: a reader sees `text` and nothing else, and a crash before
        the next `sync` leaves the previous content exactly as it was.
        """
        _path(path)
        _text(text, "a replace")
        self._buffer.append((path, "replace", text))
        return self.size(path)

    def sync(self):
        """Flush the volatile buffer: everything written so far is now durable.

        Returns the number of characters flushed, so a caller can tell a sync
        that mattered from one that had nothing to do.
        """
        flushed = 0
        for path, how, text in self._buffer:
            if how == "write":
                self._durable[path] = self._durable.get(path, "") + text
                flushed += len(text)
            else:
                flushed += len(self._durable.get(path, ""))
                self._durable[path] = text
        self._buffer = []
        return flushed

    def crash(self):
        """Discard the volatile buffer and report what was lost.

        Returns `((path, text), ...)`, sorted by path: what a crash at this
        moment would have thrown away. A crash with nothing volatile returns
        `()`, and that is the only crash that loses nothing.
        """
        lost = {}
        for path, how, text in self._buffer:
            if how == "write":
                lost[path] = lost.get(path, "") + text
            else:
                lost[path] = text
        self._buffer = []
        return tuple((path, lost[path]) for path in sorted(lost) if lost[path])

    # --- reading ---------------------------------------------------------
    def read(self, path):
        """What the program sees: what is durable, plus what is still volatile.

        A path that was never written reads as the empty string.
        """
        _path(path)
        text = self._durable.get(path, "")
        for entry_path, how, entry_text in self._buffer:
            if entry_path != path:
                continue
            text = text + entry_text if how == "write" else entry_text
        return text

    def synced(self, path):
        """What a crash would keep for `path`.

        The one method a process that woke up after a crash may believe.
        """
        _path(path)
        return self._durable.get(path, "")

    def files(self):
        """Every path the disk knows — durable or still volatile — sorted."""
        names = set(self._durable)
        for path, _how, _text in self._buffer:
            names.add(path)
        return tuple(sorted(names))

    def size(self, path):
        """How many characters `read(path)` would return."""
        return len(self.read(path))

    def durable(self, path, text):
        """Is `text` already inside what a crash would keep for `path`?"""
        _path(path)
        _text(text, "the text to look for")
        return text in self._durable.get(path, "")

    def volatile(self):
        """The paths with unflushed writes, sorted — the crash's shopping list."""
        names = set()
        for path, _how, _text in self._buffer:
            names.add(path)
        return tuple(sorted(names))

    def __repr__(self):
        return "<Disk %d path(s), %d volatile write(s)>" % (
            len(self.files()), len(self._buffer))
