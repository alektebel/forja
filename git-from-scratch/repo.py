"""git-from-scratch — the world: the repo as data.

Three modules, complete, provided:

* `repo.py` (this module): the virtual filesystem and the repository over
  it — a `Fs` whose paths are relative and whose directories are explicit,
  a `Repo` whose `.git` layout, refs and HEAD are doors a stage may walk,
  `object_write`/`object_read` (the object store the fixtures use, which
  stage 3 builds itself and the check holds against this one), `export`
  (materialise the repo into a real directory so the check's own `git` can
  judge it), and `counters()` (the store's own record).
* `objects.py`: the object grammar's provided half — the zlib wrap, the
  SHA-1, the fanout path, the header, the modes.
* `worktree.py`: the deterministic fixtures — the working tree, the staged
  index, the frozen author line, and a pack real git built.

The laws (`.l4-dev/CONTRACT.md` §1): a stage imports the world and earlier
stages only; every filesystem touch goes through the `Fs`; the hash rule is
`sha1("<type> <size>\\0" + body)`; sorted is sorted by bytes; a refusal is
a named exception.
"""

class GitError(Exception):
    """The refusal family: the offender is in the message."""


class Fs:
    """A virtual filesystem: relative paths, explicit directories."""

    def __init__(self):
        # path -> bytes for files; a set of directory paths ("" is the root)
        self._files = {}
        self._dirs = {""}
        self._exec = set()

    def _check(self, path, what):
        if not isinstance(path, str) or (not path and what != "list"):
            raise GitError("%s: a path is a non-empty string, not %r"
                           % (what, path))
        if path.startswith("/") or ".." in path.split("/"):
            raise GitError("%s: %r leaves the repo" % (what, path))

    def write(self, path, data, exec=False):
        """One file's bytes, its parent directories created; `exec` is the
        executable bit, the one mode bit git records."""
        self._check(path, "write")
        if path.endswith("/"):
            raise GitError("write: %r names a directory" % (path,))
        if not isinstance(data, (bytes, bytearray)):
            raise GitError("write: the data is bytes, not %r"
                           % (type(data).__name__,))
        if exec:
            self._exec.add(path)
        else:
            self._exec.discard(path)
        parts = path.split("/")
        for i in range(1, len(parts)):
            self._dirs.add("/".join(parts[:i]))
        self._files[path] = bytes(data)

    def read(self, path):
        """One file's bytes, or a refusal naming the path."""
        self._check(path, "read")
        if path not in self._files:
            raise GitError("read: no file %r" % (path,))
        return self._files[path]

    def mkdir(self, path):
        """One directory, its parents created."""
        self._check(path, "mkdir")
        path = path.rstrip("/")
        parts = path.split("/") if path else []
        for i in range(1, len(parts) + 1):
            self._dirs.add("/".join(parts[:i]))

    def is_exec(self, path):
        """Whether the file carries the executable bit."""
        self._check(path, "is_exec")
        return path in self._exec

    def exists(self, path):
        """Whether a file or a directory is there."""
        self._check(path, "exists")
        path = path.rstrip("/")
        return path in self._files or path in self._dirs

    def list(self, path):
        """The names under one directory, sorted; directories suffixed '/'."""
        self._check(path, "list")
        path = path.rstrip("/")
        if path not in self._dirs:
            raise GitError("list: no directory %r" % (path,))
        prefix = path + "/" if path else ""
        names = set()
        for file_path in self._files:
            if file_path.startswith(prefix) and "/" not in                     file_path[len(prefix):]:
                names.add(file_path[len(prefix):])
        for dir_path in self._dirs:
            if dir_path and dir_path.startswith(prefix) and "/" not in                     dir_path[len(prefix):]:
                names.add(dir_path[len(prefix):] + "/")
        return tuple(sorted(names))

    def remove(self, path):
        """One file or an empty directory, or a refusal naming the path."""
        self._check(path, "remove")
        path = path.rstrip("/")
        if path in self._files:
            del self._files[path]
            return
        if path in self._dirs:
            for other in list(self._files) + list(self._dirs):
                if other.startswith(path + "/"):
                    raise GitError("remove: %r is not empty" % (path,))
            self._dirs.discard(path)
            return
        raise GitError("remove: nothing at %r" % (path,))


class Repo:
    """A virtual filesystem wearing a .git: the layout, the doors."""

    def __init__(self, git_dir=".git"):
        self.git_dir = git_dir
        self.fs = Fs()
        self._hashed = 0
        self._written = 0
        self._read = 0

    # -- the doors -----------------------------------------------------------

    def head_read(self):
        """HEAD's bytes, or None when the repository is not initialised."""
        path = self.git_dir + "/HEAD"
        if not self.fs.exists(path):
            return None
        return self.fs.read(path)

    def head_write(self, target):
        """HEAD set to one target line, ending in a newline."""
        if not target.endswith("\n"):
            target = target + "\n"
        self.fs.write(self.git_dir + "/HEAD", target.encode())

    def ref_read(self, name):
        """One ref's sha, or None when it names nothing yet."""
        path = self.git_dir + "/" + name
        if not self.fs.exists(path):
            return None
        return self.fs.read(path).decode().strip()

    def ref_write(self, name, sha):
        """One ref set to a 40-hex sha."""
        if len(sha) != 40:
            raise GitError("ref_write: %r is not a 40-character sha" % (sha,))
        path = self.git_dir + "/" + name
        self.fs.write(path, (sha + "\n").encode())

    # -- the object store (provided for the fixtures; stage 3 rebuilds it) --

    def object_write(self, kind, body):
        """One object stored at its fanout path; the sha is the answer."""
        import objects as ob
        sha = ob.sha1(ob.header(kind, len(body)) + body)
        path = self.git_dir + "/" + ob.obj_path(sha)
        if not self.fs.exists(path):
            self._hashed += 1
            self._written += 1
            self.fs.write(path, ob.zlib_wrap(kind, body))
        return sha

    def object_read(self, sha):
        """One object's (type, body), or a refusal naming the sha."""
        import objects as ob
        path = self.git_dir + "/" + ob.obj_path(sha)
        if not self.fs.exists(path):
            raise GitError("object_read: no object %r" % (sha,))
        self._read += 1
        kind, body = ob.zlib_unwrap(self.fs.read(path))
        return kind, body

    # -- the judge's door ----------------------------------------------------

    def export(self, path):
        """Materialise the repo into a real directory (for the check's git)."""
        import os
        for dir_path in sorted(self.fs._dirs):
            full = os.path.join(path, dir_path) if dir_path else path
            os.makedirs(full, exist_ok=True)
        for file_path, data in sorted(self.fs._files.items()):
            full = os.path.join(path, file_path)
            with open(full, "wb") as handle:
                handle.write(data)

    def counters(self):
        """The store's own record: hashes, writes, reads."""
        return {"hashed": self._hashed, "written": self._written,
                "read": self._read}
