"""Git From Scratch — a repository's object store over a provided fixture.

Ten graded stages from the CodeCrafters corpus (`codecrafters-reference/git/`),
extended to ten along the store's own spine, the way the rest of this
repository teaches a mechanism: the world is data and holds the ground truth,
a stage is a file you write, a check is what happens to it, and real `git`
is the judge — because compatibility has exactly one authority.

What the course is about, in one line: *a directory becomes a store whose
every byte a program that defined the format can read.*

    the repository: a `.git` is a layout, and HEAD is a promise
    the blob, read: a header, then its body
    the blob, written: the hash is the content's name
    the tree, read: sorted entries with modes
    the tree, written: the whole working tree, bottom-up
    the commit: a tree, a parent, and a frozen line
    the index: staging is a record, not a copy
    the log: history is parents, walked and verified
    the packfile: many objects, one file, deltas to apply
    the proof: real git opens what you wrote

The house laws hold here (`.l4-dev/CONTRACT.md` §1): standard library only,
no `float` literal, no `random`, no clock, no thread, no socket — and, this
course's own additions, the world is read-only, the store's names are law
(`KNOWN_BLOBS` carries real git's hashes), and a stage never calls git
itself: the judge is the check's, never the student's.

What the course does **not** do is shell out. There is no `git` behind
`init`, no real filesystem behind `repo.fs`: the fixture is data, the pack
is bytes real git built and the course reads, and the whole course is
deterministic enough that two runs against the same fixture produce the
same shas.

    python3 codecraft/cli.py run git-from-scratch
"""

from codecraft.api import stage

TITLE = "Git From Scratch"
DESCRIPTION = ("A repository's object store, byte for byte the store real "
               "git reads: ten stages that lay out a `.git` and keep HEAD's "
               "promise, read and write blobs whose names are their content's "
               "hash, walk and write trees in git's own sort, freeze a commit "
               "line with its parent, stage an index whose record git's own "
               "ls-files reads back, walk the log and refuse its cycles, "
               "unpack a packfile real git built down to its deltas, and hand "
               "the whole store to `git fsck` — with the judge the check's, "
               "never the student's.")

LEVEL = "advanced"
ORDER = 35


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "git-from-scratch"

    S1_HEAD_STATUS = ("objects", "refs", "HEAD")

    def _repo(start=None):
        for candidate_start in (os.environ.get("L4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "repo.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L4_REPO=/path/to/forja")

    def _git(*args, cwd=None):
        out = subprocess.run(list(args), capture_output=True, text=True,
                             cwd=cwd)
        return out.returncode, (out.stdout + out.stderr).strip()

    def _s1_surface(s):
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("rp", "ob", "wt"):
                continue
            public.add(name)
        assert public == {"HEAD_STATUS", "init"}, (
            "the stage's public surface is %s and §3.1 pins HEAD_STATUS, init"
            % ", ".join(sorted(public)))

    def _s1_layout(s, rp, wt):
        repo = rp.Repo()
        got = s.init(repo)
        assert s.HEAD_STATUS == S1_HEAD_STATUS, (
            "HEAD_STATUS is %r and §3.1 pins %r"
            % (s.HEAD_STATUS, S1_HEAD_STATUS))
        assert got is not None, "init answers the layout"
        fs = repo.fs
        for name in S1_HEAD_STATUS:
            assert fs.exists(repo.git_dir + "/" + name), (
                "the layout is missing %r" % (name,))
        assert fs.exists(repo.git_dir + "/refs/heads"), (
            "refs/heads exists beneath refs")
        assert repo.head_read() == wt.HEAD_TARGET.encode(), (
            "HEAD is %r, the promise is %r" % (repo.head_read(), wt.HEAD_TARGET))
        assert repo.head_read().endswith(b"\n"), "HEAD ends in a newline"

    def _s1_idempotent(s, rp):
        repo = rp.Repo()
        s.init(repo)
        repo.ref_write("refs/heads/main", "a" * 40)
        repo.head_write("ref: refs/heads/feature\n")
        s.init(repo)
        assert repo.ref_read("refs/heads/main") == "a" * 40, (
            "a second init erased a ref")
        assert repo.head_read() == b"ref: refs/heads/feature\n", (
            "a second init rewrote HEAD: %r" % (repo.head_read(),))

    def _s1_git_judge(s, rp, tmp):
        repo = rp.Repo()
        s.init(repo)
        repo.export(tmp)
        rc, text = _git("git", "rev-parse", "--git-dir", cwd=tmp)
        assert rc == 0, "real git refuses the layout: %s" % (text,)

    import repo as rp
    import worktree as wt
    import stage_01 as s
    _s1_surface(s)
    _s1_layout(s, rp, wt)
    _s1_idempotent(s, rp)
    tmp = tempfile.mkdtemp(prefix="l4-judge-")
    try:
        _s1_git_judge(s, rp, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "git-from-scratch"

    S2_KEYS = ("read_header", "cat_file")

    def _repo(start=None):
        for candidate_start in (os.environ.get("L4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "repo.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L4_REPO=/path/to/forja")

    def _refuses(exc, call, *must_name):
        try:
            got = call()
        except exc as err:
            for name in must_name:
                assert name in str(err), (
                    "the refusal names neither %r: %s" % (name, err))
            return
        raise AssertionError("was accepted (%r); it must refuse" % (got,))

    def _s2_surface(s):
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("rp", "ob", "wt"):
                continue
            public.add(name)
        assert public == {"read_header", "cat_file"}, (
            "the stage's public surface is %s and §3.2 pins read_header, "
            "cat_file" % ", ".join(sorted(public)))

    def _s2_reads(s, rp, ob, wt):
        import stage_01 as s1
        repo = rp.Repo()
        s1.init(repo)
        for (data, _pinned) in wt.KNOWN_BLOBS:
            sha = repo.object_write("blob", data)
            kind, size = s.read_header(repo, sha)
            assert (kind, size) == ("blob", len(data)), (
                "the header of %r says (%r, %r)" % (data[:10], kind, size))
            assert s.cat_file(repo, sha) == data, (
                "cat-file answers something else")

    def _s2_refuses(s, rp, ob):
        repo = rp.Repo()
        _refuses(rp.GitError, lambda: s.cat_file(repo, "f" * 40),
                 "no object", "f" * 40)
        _refuses(rp.GitError, lambda: s.read_header(repo, "f" * 40),
                 "no object")
        tree_sha = repo.object_write("tree", b"")
        _refuses(rp.GitError, lambda: s.cat_file(repo, tree_sha), "tree")
        # a header that lies about its size
        import zlib
        raw = zlib.compress(b"blob 99\x00short")
        sha = ob.sha1(b"blob 99\x00short")
        repo.fs.write(repo.git_dir + "/" + ob.obj_path(sha), raw)
        _refuses((rp.GitError, ValueError),
                 lambda: s.read_header(repo, sha), "99", "5")

    import repo as rp
    import objects as ob
    import worktree as wt
    import stage_02 as s
    _s2_surface(s)
    _s2_reads(s, rp, ob, wt)
    _s2_refuses(s, rp, ob)

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "git-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "repo.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L4_REPO=/path/to/forja")

    def _s3_surface(s):
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("rp", "ob", "wt"):
                continue
            public.add(name)
        assert public == {"hash_object"}, (
            "the stage's public surface is %s and §3.3 pins hash_object"
            % ", ".join(sorted(public)))

    def _s3_hashes(s, rp, wt):
        import stage_01 as s1
        repo = rp.Repo()
        s1.init(repo)
        for (data, pinned) in wt.KNOWN_BLOBS:
            sha = s.hash_object(repo, data)
            if pinned:
                assert sha == pinned, (
                    "the hash of %r is %s, real git says %s"
                    % (data[:12], sha, pinned))
            assert len(sha) == 40 and sha == sha.lower(), (
                "a sha is 40 lowercase hex: %r" % (sha,))
        written = repo.counters()["written"]
        assert written == 3, "three distinct bodies, %d written" % (written,)
        again = s.hash_object(repo, b"hello world\n")
        assert repo.counters()["written"] == written, (
            "the same body wrote a second file")

    def _s3_agrees_with_world(s, rp, ob):
        import stage_01 as s1
        repo = rp.Repo()
        s1.init(repo)
        body = b"the stage and the store must write one file"
        stage_sha = s.hash_object(repo, body)
        stage_file = repo.fs.read(repo.git_dir + "/" + ob.obj_path(stage_sha))
        world_sha = repo.object_write("blob", body)
        assert stage_sha == world_sha, (
            "the stage names it %s, the store %s" % (stage_sha, world_sha))
        # the world's write was a dedup hit; prove the bytes via a fresh repo
        other = rp.Repo()
        other.object_write("blob", body)
        world_file = other.fs.read(
            other.git_dir + "/" + ob.obj_path(world_sha))
        assert stage_file == world_file, (
            "the stage's bytes differ from the store's")

    import repo as rp
    import worktree as wt
    import stage_03 as s
    _s3_surface(s)
    _s3_hashes(s, rp, wt)
    _s3_agrees_with_world(s, rp, __import__("objects"))

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "git-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "repo.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L4_REPO=/path/to/forja")

    def _build_fixture_tree(rp, s1):
        """The CodeCrafters test's own shape: file1, dir1/(a,b), dir2/(c)."""
        repo = rp.Repo()
        s1.init(repo)
        def entry(mode, name, sha_hex):
            return (mode.encode() + b" " + name.encode() + b"\x00"
                    + bytes.fromhex(sha_hex))
        dir1_blob_a = repo.object_write("blob", b"file_in_dir_1\n")
        dir1_blob_b = repo.object_write("blob", b"file_in_dir_2\n")
        dir2_blob = repo.object_write("blob", b"file_in_dir_3\n")
        file1 = repo.object_write("blob", b"file1\n")
        dir1 = repo.object_write(
            "tree", entry("100644", "file_in_dir_1", dir1_blob_a)
            + entry("100644", "file_in_dir_2", dir1_blob_b))
        dir2 = repo.object_write("tree", entry("100644", "file_in_dir_3",
                                               dir2_blob))
        # write in a deliberately unsorted order; the format door answers as-is
        root = repo.object_write(
            "tree", entry("100644", "file1", file1)
            + entry("40000", "dir1", dir1) + entry("40000", "dir2", dir2))
        return repo, root, {"dir1": dir1, "dir2": dir2,
                            "file1": file1}

    def _s4_surface(s):
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("rp", "ob", "wt"):
                continue
            public.add(name)
        assert public == {"ls_tree", "ls_tree_names"}, (
            "the stage's public surface is %s and §3.4 pins ls_tree, "
            "ls_tree_names" % ", ".join(sorted(public)))

    def _s4_entries(s, rp, s1):
        repo, root, shas = _build_fixture_tree(rp, s1)
        entries = s.ls_tree(repo, root)
        assert [name for (_m, name, _s) in entries] == \
            ["file1", "dir1", "dir2"], entries
        for (mode, name, sha_hex) in entries:
            assert mode in ("100644", "40000"), mode
            kind, _body = repo.object_read(sha_hex)
            assert kind == ("tree" if mode == "40000" else "blob"), (
                "%s names a %s" % (name, kind))
        # the names door answers the file's order — git's ls-tree prints
        # what the tree holds
        names = s.ls_tree_names(repo, root)
        assert names == ("file1", "dir1", "dir2"), names
        return repo, root

    def _s4_git_judge(s, rp, repo, root):
        tmp = tempfile.mkdtemp(prefix="l4-judge04-")
        try:
            repo.export(tmp)
            out = subprocess.run(
                ["git", "--git-dir=%s/.git" % tmp, "ls-tree", "--name-only",
                 root], capture_output=True, text=True)
            assert out.returncode == 0, out.stderr
            git_names = tuple(out.stdout.strip().split("\n"))
            assert git_names == s.ls_tree_names(repo, root), (
                "git prints %r, the stage %r" % (git_names,
                                                 s.ls_tree_names(repo, root)))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _s4_refuses(s, rp):
        repo = rp.Repo()
        bad = repo.object_write("tree", b"77777 x\x00" + bytes(20))
        try:
            s.ls_tree(repo, bad)
        except Exception as err:
            assert "77777" in str(err), err
        else:
            raise AssertionError("a bad mode was accepted")

    import repo as rp
    import stage_01 as s1
    import stage_04 as s
    _s4_surface(s)
    repo, root = _s4_entries(s, rp, s1)
    _s4_git_judge(s, rp, repo, root)
    _s4_refuses(s, rp)

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "git-from-scratch"

    GIT_TREE_HASH = "dc8f37d5391c796596d392ee13019dca66ca471a"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "repo.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L4_REPO=/path/to/forja")

    def _s5_surface(s):
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("rp", "ob", "wt", "s3", "s4"):
                continue
            public.add(name)
        assert public == {"entry_sort_key", "write_tree"}, (
            "the stage's public surface is %s and §3.5 pins entry_sort_key, "
            "write_tree" % ", ".join(sorted(public)))

    def _s5_write(s, rp, wt, s1):
        repo = rp.Repo()
        s1.init(repo)
        for (path, mode, data) in wt.FIXTURE_TREE:
            repo.fs.write(path, data, exec=(mode == "100755"))
        sha = s.write_tree(repo)
        assert sha == GIT_TREE_HASH, (
            "the fixture tree hashes %s, real git says %s" % (sha, GIT_TREE_HASH))
        # every blob the fixture names is in the store
        for (path, _mode, data) in wt.FIXTURE_TREE:
            kind, body = repo.object_read(_hash_of("blob", data))
            assert body == data, path
        # the executable's mode travels
        entries = dict((name, mode) for (mode, name, _s)
                       in __import__("stage_04").ls_tree(repo, sha))
        assert entries.get("bin") == "40000", entries
        # the extended fixture: a file whose name sorts against "docs/" --
        # "docs-x" (0x2d) sorts before "docs/" (0x2f), so a naive sort or no
        # sort writes a tree whose hash is not git's
        repo.fs.write("docs-x", b"x" + chr(10).encode())
        extended = s.write_tree(repo)
        assert extended == "dc6ff76c3dd3853525f42c39828a0482f68d8fac", (
            "the extended fixture hashes %s, real git says "
            "dc6ff76c3dd3853525f42c39828a0482f68d8fac" % (extended,))
        return repo, sha

    def _hash_of(kind, body):
        import objects as ob
        return ob.sha1(ob.header(kind, len(body)) + body)

    def _s5_sort_key(s):
        assert s.entry_sort_key("bar", False) == "bar"
        assert s.entry_sort_key("bar", True) == "bar/"
        # the rule git applies: "bar." sorts before "bar/" (0x2e < 0x2f)
        assert s.entry_sort_key("bar.", False) < s.entry_sort_key("bar", True)

    import repo as rp
    import worktree as wt
    import stage_01 as s1
    import stage_05 as s
    _s5_surface(s)
    _s5_sort_key(s)
    _s5_write(s, rp, wt, s1)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "git-from-scratch"

    GIT_COMMIT_HASH = "86a3245e33ce48347a7a7b0560493f8f8ad2a1dd"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "repo.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L4_REPO=/path/to/forja")

    def _s6_surface(s):
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("rp", "ob", "wt"):
                continue
            public.add(name)
        assert public == {"commit_tree"}, (
            "the stage's public surface is %s and §3.6 pins commit_tree"
            % ", ".join(sorted(public)))

    def _s6_commits(s, rp, wt, s1):
        repo = rp.Repo()
        s1.init(repo)
        empty_tree = repo.object_write("tree", b"")
        line = "%s %s" % (wt.AUTHOR, wt.TIMESTAMP)
        root_body = ("tree %s\nauthor %s\ncommitter %s\n\nroot\n"
                     % (empty_tree, line, line)).encode()
        root = repo.object_write("commit", root_body)
        tree = repo.object_write("tree", b"")
        sha = s.commit_tree(repo, tree, root, wt.MESSAGE)
        assert sha == GIT_COMMIT_HASH, (
            "the commit hashes %s, real git says %s" % (sha, GIT_COMMIT_HASH))
        kind, body = repo.object_read(sha)
        assert kind == "commit"
        text = body.decode()
        assert ("tree %s" % tree) in text
        assert ("parent %s" % root) in text
        assert ("author %s %s" % (wt.AUTHOR, wt.TIMESTAMP)) in text
        assert ("committer %s %s" % (wt.AUTHOR, wt.TIMESTAMP)) in text
        assert text.endswith("\n%s\n" % wt.MESSAGE)
        return repo, tree, root, sha

    def _s6_refuses(s, rp):
        repo = rp.Repo()
        tree = repo.object_write("tree", b"")
        _missing = "f" * 40
        try:
            s.commit_tree(repo, _missing, _missing, "x")
        except Exception as err:
            assert _missing in str(err), err
        else:
            raise AssertionError("a missing tree was accepted")
        try:
            s.commit_tree(repo, tree, tree, "x")
        except Exception as err:
            assert "commit" in str(err), err
        else:
            raise AssertionError("a tree-as-parent was accepted")

    def _s6_git_judge(repo, sha):
        tmp = tempfile.mkdtemp(prefix="l4-judge06-")
        try:
            repo.export(tmp)
            out = subprocess.run(
                ["git", "--git-dir=%s/.git" % tmp, "cat-file", "-p", sha],
                capture_output=True, text=True)
            assert out.returncode == 0, out.stderr
            assert "author A Student" in out.stdout, out.stdout
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    import repo as rp
    import worktree as wt
    import stage_01 as s1
    import stage_06 as s
    _s6_surface(s)
    repo, _tree, _root, sha = _s6_commits(s, rp, wt, s1)
    _s6_refuses(s, rp)
    _s6_git_judge(repo, sha)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "git-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "repo.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L4_REPO=/path/to/forja")

    def _s7_surface(s):
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("rp", "ob", "wt", "s3"):
                continue
            public.add(name)
        assert public == {"INDEX_KEYS", "read_index", "write_index", "add"}, (
            "the stage's public surface is %s and §3.7 pins INDEX_KEYS, "
            "read_index, write_index, add" % ", ".join(sorted(public)))
        assert s.INDEX_KEYS == ("entries", "stats"), s.INDEX_KEYS

    def _s7_stages(s, rp, wt, s1):
        repo = rp.Repo()
        s1.init(repo)
        for (path, mode, data) in wt.FIXTURE_TREE:
            repo.fs.write(path, data, exec=(mode == "100755"))
        record = s.add(repo, ["README.md", "bin/", ".gitignore"])
        assert set(record) == set(s.INDEX_KEYS), sorted(record)
        entries = record["entries"]
        assert len(entries) == 3, entries
        modes = dict((path, mode) for (mode, _sha, path) in entries)
        assert modes.get("bin/run.sh") == "100755", modes
        assert modes.get("README.md") == "100644", modes
        # staging twice answers one entry
        s.add(repo, ["README.md"])
        assert len(s.read_index(repo)) == 3, s.read_index(repo)
        return repo

    def _s7_git_judge(repo):
        tmp = tempfile.mkdtemp(prefix="l4-judge07-")
        try:
            repo.export(tmp)
            out = subprocess.run(
                ["git", "--git-dir=%s/.git" % tmp, "ls-files", "--stage"],
                capture_output=True, text=True)
            assert out.returncode == 0, "git refuses the index: %s" % out.stderr
            lines = tuple(out.stdout.strip().split("\n"))
            assert len(lines) == 3, lines
            assert any("100755" in line and "bin/run.sh" in line
                       for line in lines), lines
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _s7_corrupt(s, rp, s1, ob):
        repo = rp.Repo()
        s1.init(repo)
        repo.fs.write("a.txt", b"one\n")
        s.add(repo, ["a.txt"])
        raw = repo.fs.read(".git/index")
        # a corrupted magic
        repo.fs.write(".git/index", b"XXXX" + raw[4:])
        try:
            s.read_index(repo)
        except Exception as err:
            assert "DIRC" in str(err), err
        else:
            raise AssertionError("a wrong magic was accepted")
        # a corrupted version: recompute the trailing sha so only the
        # version check can refuse
        import hashlib
        fixed = raw[:4] + b"\x00\x00\x00\x09" + raw[8:-20]
        repo.fs.write(".git/index", fixed + hashlib.sha1(fixed).digest())
        refused = None
        try:
            s.read_index(repo)
        except Exception as err:
            refused = str(err)
        assert refused and "9" in refused, (
            "version 9 was %s" % (refused and refused or "accepted",))
        # a corrupted trailing sha
        repo.fs.write(".git/index", raw[:-20] + bytes(20))
        try:
            s.read_index(repo)
        except Exception as err:
            assert "sha" in str(err).lower(), err
        else:
            raise AssertionError("a broken checksum was accepted")

    def _s7_refuses(s, rp, s1):
        repo = rp.Repo()
        s1.init(repo)
        repo.fs.write("x" * 5000, b"data")
        try:
            s.add(repo, ["x" * 5000])
        except Exception as err:
            assert "5000" in str(err) or "cap" in str(err).lower() or \
                "4095" in str(err), err
        else:
            raise AssertionError("a too-long path was accepted")

    import repo as rp
    import worktree as wt
    import stage_01 as s1
    import stage_07 as s
    _s7_surface(s)
    repo = _s7_stages(s, rp, wt, s1)
    _s7_git_judge(repo)
    _s7_corrupt(s, rp, s1, __import__("objects"))
    _s7_refuses(s, rp, s1)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "git-from-scratch"

    S8_LOG_KEYS = ("sha", "tree", "parent", "message")

    def _repo(start=None):
        for candidate_start in (os.environ.get("L4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "repo.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L4_REPO=/path/to/forja")

    def _s8_surface(s):
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("rp", "ob", "wt"):
                continue
            public.add(name)
        assert public == {"LOG_KEYS", "log"}, (
            "the stage's public surface is %s and §3.8 pins LOG_KEYS, log"
            % ", ".join(sorted(public)))
        assert s.LOG_KEYS == S8_LOG_KEYS, s.LOG_KEYS

    def _s8_walks(s, rp, wt, s1):
        repo = rp.Repo()
        s1.init(repo)
        empty_tree = repo.object_write("tree", b"")
        line = "%s %s" % (wt.AUTHOR, wt.TIMESTAMP)
        root = repo.object_write(
            "commit", ("tree %s\nauthor %s\ncommitter %s\n\nroot\n"
                       % (empty_tree, line, line)).encode())
        tree = repo.object_write("tree", b"")
        child = repo.object_write(
            "commit", ("tree %s\nparent %s\nauthor %s\ncommitter %s\n\nthe "
                       "fixture commit\n" % (tree, root, line, line)).encode())
        walk = s.log(repo, child)
        assert len(walk) == 2, walk
        assert walk[0]["sha"] == child and walk[0]["parent"] == root
        assert walk[0]["message"] == "the fixture commit"
        assert walk[1]["sha"] == root and walk[1]["parent"] is None
        assert walk[1]["message"] == "root"
        for step in walk:
            assert set(step) == set(S8_LOG_KEYS), sorted(step)
        return repo, child, root, empty_tree

    def _s8_refuses(s, rp, repo, child, root, empty_tree):
        # a missing parent: a commit naming an object that is not there
        line = "%s %s" % ("A", "1750000000 +0000")
        orphan_parent = repo.object_write("commit", (
            "tree %s\nparent %s\nauthor %s\ncommitter %s\n\norphan\n"
            % (empty_tree, "f" * 40, line, line)).encode())
        # remove the fake parent's... the parent is missing entirely: the walk
        # from orphan_parent refuses naming f*40
        try:
            s.log(repo, orphan_parent)
        except Exception as err:
            assert "f" * 8 in str(err), err
        else:
            raise AssertionError("a missing parent was accepted")
        # a parent that a commit is not: the walk checks the kind, not the sha
        tree_child = repo.object_write("commit", (
            "tree %s\nparent %s\nauthor %s\ncommitter %s\n\ntree parent\n"
            % (empty_tree, empty_tree, line, line)).encode())
        try:
            s.log(repo, tree_child)
        except Exception as err:
            assert "tree" in str(err), err
        else:
            raise AssertionError("a tree parent was accepted")

    def _s8_cycle(s, rp, ob, wt, s1):
        """A cycle the store was corrupted into: A's parent rewritten to name
        B after B named A — the walk must refuse naming where it loops."""
        repo = rp.Repo()
        s1.init(repo)
        empty_tree = repo.object_write("tree", b"")
        line = "%s %s" % ("A", "1750000000 +0000")
        a_body = ("tree %s\nparent P\nauthor %s\ncommitter %s\n\na\n"
                  % (empty_tree, line, line)).encode()
        a_sha = ob.sha1(ob.header("commit", len(a_body)) + a_body)
        b_body = ("tree %s\nparent %s\nauthor %s\ncommitter %s\n\nb\n"
                  % (empty_tree, a_sha, line, line)).encode()
        b_sha = repo.object_write("commit", b_body)
        # A is written with its parent naming B; then the store's A is
        # rewritten so the walk from A goes A -> B -> A's file (which names B)
        repo.fs.write(repo.git_dir + "/" + ob.obj_path(a_sha),
                      ob.zlib_wrap("commit", a_body.replace(b"parent P",
                                                            b"parent " + b_sha.encode())))
        try:
            s.log(repo, a_sha)
        except Exception as err:
            assert "loop" in str(err).lower() or a_sha[:8] in str(err), err
        else:
            raise AssertionError("a cycle was accepted")

    import repo as rp
    import worktree as wt
    import stage_01 as s1
    import stage_08 as s
    import objects as ob
    _s8_surface(s)
    repo, child, root, empty_tree = _s8_walks(s, rp, wt, s1)
    _s8_refuses(s, rp, repo, child, root, empty_tree)
    _s8_cycle(s, rp, ob, wt, s1)

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "git-from-scratch"

    S9_PACK_KEYS = ("count", "objects")

    S9_PACK_SHAS = (
        ("commit", "1ceec4ddadeb".__class__ and None),  # replaced below
    )

    EXPECTED = [
        ("commit", None), ("tree", None), ("blob", None), ("tree", None),
        ("blob", None), ("tree", None), ("blob", None), ("blob", None),
    ]

    def _repo(start=None):
        for candidate_start in (os.environ.get("L4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "repo.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L4_REPO=/path/to/forja")

    def _pv(n):
        """The delta header's plain varint, built for the scripts below."""
        out = bytearray()
        while True:
            b = n & 0x7F
            n >>= 7
            if n:
                out.append(b | 0x80)
            else:
                out.append(b)
                return bytes(out)

    def _s9_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("rp", "ob", "wt"):
                continue
            public.add(name)
        assert public == {"PACK_KEYS", "apply_delta", "read_pack"}, (
            "the stage's public surface is %s and §4.0 pins PACK_KEYS, "
            "apply_delta, read_pack" % ", ".join(sorted(public)))
        assert s.PACK_KEYS == S9_PACK_KEYS, (
            "PACK_KEYS is %r and §4.0 pins %r" % (s.PACK_KEYS, S9_PACK_KEYS))
        assert all(callable(getattr(s, n))
                   for n in ("apply_delta", "read_pack")), (
            "apply_delta and read_pack are the ways in")

    def _s9_apply_delta(s):
        """The script applied: copies and inserts, every lie refused."""
        import repo as rp
        base = b"hello world"
        assert s.apply_delta(base, _pv(len(base)) + _pv(8)
                             + bytes([8]) + b"goodbye!") == b"goodbye!", (
            "an insert-only script appends its bytes")
        assert s.apply_delta(base, _pv(len(base)) + _pv(8)
                             + bytes([0x91, 0x00, 0x05])
                             + bytes([3]) + b"!!!") == b"hello!!!", (
            "a copy then an insert rebuilds the base's head")
        # the size-0 copy means 0x10000 — a script the fixture's deltas use
        big = b"x" * 0x10000
        assert s.apply_delta(big, _pv(len(big)) + _pv(0x10000)
                             + bytes([0x90, 0x00])) == big, (
            "a size-0 copy reads 0x10000 bytes")
        # each script's refusal is its own: the range, the insert's length,
        # the result size and opcode 0 are caught one at a time, so no other
        # check can mask a missing guard
        for what, script, why in (
                ("a base size that lies", _pv(99) + _pv(8)
                 + bytes([8]) + b"goodbye!", "the base is 99 bytes, it is"),
                ("a copy past the base", _pv(len(base)) + _pv(3)
                 + bytes([0x91, 0x08, 0xFF]), "a copy reads"),
                ("an insert shorter than it claims", _pv(len(base)) + _pv(3)
                 + bytes([8]) + b"abc", "the script has 3"),
                ("a result size that lies", _pv(len(base)) + _pv(99)
                 + bytes([8]) + b"goodbye!", "the result is 99 bytes"),
                ("opcode 0", _pv(len(base)) + _pv(8)
                 + bytes([0, 8]) + b"goodbye!", "opcode 0x00")):
            try:
                s.apply_delta(base, script)
            except rp.GitError as err:
                assert why in str(err), "%s: %r lacks %r" % (what, str(err), why)
            else:
                raise AssertionError("%s was accepted" % (what,))

    def _s9_read_pack(s, rp, wt, s1, ob):
        """The fixture pack: nine counted, every sha real git's."""
        repo = rp.Repo()
        s1.init(repo)
        r = s.read_pack(repo, wt.FIXTURE_PACK)
        assert set(r) >= set(S9_PACK_KEYS), (
            "the pack's keys carry PACK_KEYS: %s" % sorted(r))
        assert r["count"] == 9, r["count"]
        kinds = tuple(kind for kind, _body in r["objects"])
        assert kinds == ("commit", "commit", "tree", "blob", "tree", "blob",
                         "tree", "blob", "blob"), kinds
        names = {ob.sha1(ob.header(kind, len(body)) + body)
                 for kind, body in r["objects"]}
        # every object answers the name real git gave the same bytes: the two
        # commits, their trees, and the blobs — pinned from real git's own
        # verify-pack, and the delta objects' names fall out of the header
        for sha in ("13a5a40c86fa6af97bbd2697ad87d1f7f6d9cfe3",
                    "1ceec4ddadeb6aebc56ad6d108ad5f3d3638c71a",
                    "d5193732026b11c817e4bf9320d0f8506d925695",
                    "95a1fe834d4523c228c9deefcb9cf7f6395216aa",
                    "261a3f32f50c66c606899c7a54a83efe78c89544",
                    "66e9a0d2f63c60d180b5ff437a8231611adaddc6",
                    "e658b1d76ac4aae681c9461c80c1b5713114c301",
                    "af17f6cc87e4d5e4adec0018cbb73d3e2bd008c8",
                    "33ba8ae41849d97467cab7e989e55db16643463b"):
            assert sha in names, sha
        # the tail sha is the pack's self-claim: one flipped byte refuses
        torn = wt.FIXTURE_PACK[:-1] + bytes([wt.FIXTURE_PACK[-1] ^ 0x01])
        try:
            s.read_pack(repo, torn)
        except rp.GitError as err:
            assert "sha" in str(err).lower(), err
        else:
            raise AssertionError("a torn pack was accepted")
        # a bad magic and a bad version refuse before any object is read
        for what, data, why in (
                ("a bad magic", b"XXXX" + wt.FIXTURE_PACK[4:], "PACK"),
                ("a bad version", wt.FIXTURE_PACK[:4]
                 + (9).to_bytes(4, "big") + wt.FIXTURE_PACK[8:], "version")):
            try:
                s.read_pack(repo, data)
            except rp.GitError as err:
                assert why in str(err), "%s: %r lacks %r" % (what, str(err), why)
            else:
                raise AssertionError("%s was accepted" % (what,))
        # an ofs-delta whose base is past the pack's start: one blob, then a
        # delta whose backward distance reaches before the first object
        import hashlib
        import zlib
        body = zlib.compress(b"blob")
        header = bytes([0x60 | 4])            # type 6 (ofs), size 4, one byte
        script = zlib.compress(_pv(len(b"blob")) + _pv(4) + bytes([4])
                               + b"blob")
        pack = (b"PACK" + (2).to_bytes(4, "big") + (2).to_bytes(4, "big")
                + header + body
                + bytes([0x60 | 4]) + bytes([200]) + script)
        pack += hashlib.sha1(pack).digest()
        try:
            s.read_pack(repo, pack)
        except rp.GitError as err:
            assert "ofs-delta" in str(err), "%s: %r" % ("an ofs-delta past the objects", str(err))
        else:
            raise AssertionError("an ofs-delta past the objects was accepted")

    """Every assertion the contract's §3.9 makes about this stage."""
    import objects as ob
    import repo as rp
    import stage_01 as s1
    import stage_09 as s
    import worktree as wt
    _s9_surface(s)
    _s9_apply_delta(s)
    _s9_read_pack(s, rp, wt, s1, ob)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "git-from-scratch"

    S10_PROOF_KEYS = ("objects", "hashes", "git_verdict")

    S10_AUDIT_KEYS = ("verdict", "reasons")

    S10_VERDICTS = ("pass", "git_disagrees", "refusal")

    TREE_SHA = "dc8f37d5391c796596d392ee13019dca66ca471a"

    COMMIT_SHA = "1f484a9e3bfd72054f14a2a5f6dc53aa24eb7699"

    def _repo(start=None):
        for candidate_start in (os.environ.get("L4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "repo.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set L4_REPO=/path/to/forja")

    def _s10_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("rp", "ob", "wt"):
                continue
            if name.startswith("s") and name[1:].isdigit():
                continue          # an earlier stage, imported under its alias
            public.add(name)
        assert public == {"PROOF_KEYS", "AUDIT_KEYS", "VERDICTS", "run_all",
                          "verify"}, (
            "the stage's public surface is %s and §4.0 pins PROOF_KEYS, "
            "AUDIT_KEYS, VERDICTS, run_all, verify"
            % ", ".join(sorted(public)))
        assert s.PROOF_KEYS == S10_PROOF_KEYS, (
            "PROOF_KEYS is %r and §4.0 pins %r"
            % (s.PROOF_KEYS, S10_PROOF_KEYS))
        assert s.AUDIT_KEYS == S10_AUDIT_KEYS, (
            "AUDIT_KEYS is %r and §4.0 pins %r"
            % (s.AUDIT_KEYS, S10_AUDIT_KEYS))
        assert s.VERDICTS == S10_VERDICTS, (
            "VERDICTS is %r and §4.0 pins the closed three %r"
            % (s.VERDICTS, S10_VERDICTS))
        assert all(callable(getattr(s, n)) for n in ("run_all", "verify")), (
            "run_all and verify are the ways in")

    def _s10_run_all(s, rp):
        """The ladder end to end; the hashes are real git's own."""
        import stage_01 as s1
        repo = rp.Repo()
        proof = s.run_all(repo)
        assert set(proof) >= set(S10_PROOF_KEYS), (
            "the proof's keys carry PROOF_KEYS: %s" % sorted(proof))
        assert proof["hashes"]["tree"] == TREE_SHA, (
            "the tree is %r, real git named it %r"
            % (proof["hashes"]["tree"][:12], TREE_SHA[:12]))
        assert proof["hashes"]["commit"] == COMMIT_SHA, (
            "the commit is %r, real git named it %r"
            % (proof["hashes"]["commit"][:12], COMMIT_SHA[:12]))
        assert proof["objects"]["staged"] == 6, (
            "the fixture stages six entries: %r" % (proof["objects"]["staged"],))
        assert proof["objects"]["log"] == 2, (
            "the walk is two commits: %r" % (proof["objects"]["log"],))

    def _s10_verify(s, rp):
        """Real git over the exported repo: the verdict and its reasons."""
        repo = rp.Repo()
        s.run_all(repo)
        r = s.verify(repo)
        assert set(r) >= set(S10_AUDIT_KEYS), (
            "the audit's keys carry AUDIT_KEYS: %s" % sorted(r))
        assert r["verdict"] == "pass" and r["reasons"] == (), (
            "git opens the ladder's repo clean: %r" % (r,))
        # a corrupted object: git is the judge, and fsck's word is the
        # verdict — a store git refuses is git_disagrees with the complaint
        # named, whatever the course's own checks thought
        corrupt = rp.Repo()
        s.run_all(corrupt)
        obj_path = ".git/objects/%s/%s" % (TREE_SHA[:2], TREE_SHA[2:])
        raw = corrupt.fs.read(obj_path)
        corrupt.fs.write(obj_path, raw[:20] + bytes([raw[20] ^ 0xFF]) + raw[21:])
        r = s.verify(corrupt)
        assert r["verdict"] == "git_disagrees", (
            "a store git refuses is git_disagrees: %r" % (r["verdict"],))
        assert r["reasons"] and "fsck" in str(r["reasons"]), r["reasons"]
        # a repo that was never built is a refusal, not a git disagreement:
        # nothing was exported, so there is no store for git to judge
        fresh = rp.Repo()
        r = s.verify(fresh)
        assert r["verdict"] == "refusal", (
            "an uninitialised repo is a refusal: %r" % (r["verdict"],))
        assert r["reasons"], "the refusal names what was missing"

    """Every assertion the contract's §3.10 makes about this stage."""
    import repo as rp
    import stage_10 as s
    _s10_surface(s)
    _s10_run_all(s, rp)
    _s10_verify(s, rp)

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title='The repository: a `.git` is a layout, and HEAD is a promise',
        tags=['init', 'layout', 'HEAD'],
        action="Write `init`, `ref_write` and the layout's refusals in stage_01.py.",
        predict="Which directories a repository cannot be a repository without, and why HEAD's promise is the one byte the rest of the store leans on.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title='The blob, read: a header, then its body',
        tags=['blob', 'zlib', 'header'],
        action="Write `object_read`, `header`, `zlib_unwrap` and `sha1` in stage_02.py.",
        predict="What a header is for when the content is compressed, and why the refusals are the reader's half of the format.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The blob, written: the hash is the content's name",
        tags=['hash-object', 'sha1', 'write'],
        action="Write `object_write` and `hash_object` in stage_03.py.",
        predict='Why the name is computed and never chosen, and what a write that does not change the name must do.',
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title='The tree, read: sorted entries with modes',
        tags=['ls-tree', 'sorting', 'modes'],
        action="Write `ls_tree` and `ls_tree_names` in stage_04.py.",
        predict="Why a tree's entries sort the way they do, and what a mode tells the reader before any content is read.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title='The tree, written: the whole working tree, bottom-up',
        tags=['write-tree', 'recursion', 'gitignore'],
        action="Write `write_tree` and `entry_sort_key` in stage_05.py.",
        predict='How a working tree becomes trees bottom-up, and why the sort lives in the writer and not the reader.',
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title='The commit: a tree, a parent, and a frozen line',
        tags=['commit-tree', 'parents', 'timestamps'],
        action="Write `commit_tree` and the frozen line's rules in stage_06.py.",
        predict="What a frozen line pins and why the parent is the commit's one choice.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title='The index: staging is a record, not a copy',
        tags=['index', 'staging', 'binary-format'],
        action="Write `add`, `read_index` and the entry's binary shape in stage_07.py.",
        predict='Why staging is a record rather than a copy, and what a trailing sha protects.',
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title='The log: history is parents, walked and verified',
        tags=['log', 'walk', 'cycles'],
        action="Write `log` and `LOG_KEYS` in stage_08.py.",
        predict='Why a cycle is a refusal rather than a stop, and how a walk verifies the store it reads.',
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title='The packfile: many objects, one file, deltas to apply',
        tags=['packfile', 'deltas', 'varint'],
        action="Write `read_pack`, `apply_delta` and `PACK_KEYS` in stage_09.py.",
        predict='Why deltas are applied against bases the pack itself names, and what a tail sha promises.',
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title='The proof: real git opens what you wrote',
        tags=['proof', 'fsck', 'interop'],
        action="Write `run_all`, `verify`, `PROOF_KEYS`, `AUDIT_KEYS` and `VERDICTS` in stage_10.py.",
        predict="Why git is the judge and not the course's own checks, and what a refusal means when there is no store to judge.",
        check=check_10,
    ),
]
