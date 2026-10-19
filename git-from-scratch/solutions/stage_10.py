"""Git From Scratch — stage 10: The proof: real git opens what you wrote.

The nine stages built a store whose objects, trees, commits, index and
packs claim git's formats; this one hands the claim to git itself. `run_all`
walks the ladder end to end on a fresh repository — init, add, write-tree,
commit, log — and answers what was written; `verify` materialises the repo
with `EXPORT` and holds real `git fsck` and `git log` over the result. A
verdict is `pass` only when git answers clean, because the store's judge
was never this course.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why is git the judge and not the course's own checks?
Because the formats were never the point: the point is compatibility, and
compatibility has exactly one authority. Every earlier check proved the
stage's own rules; this one proves the *interop* — the file real git
wrote and the file this course wrote are the same file, read by the
program that defined the format.

DESIGN DECISION — why does `verify` refuse rather than score partial
compatibility?
Because a store git half-reads is worse than one git refuses: the user
believes the commit exists. A refusal names the git command and its first
complaint — the store's own defect, in the judge's words.

DESIGN DECISION — why does `run_all` answer the objects and hashes rather
than just the verdict?
Because the verdict is the end and the hashes are the evidence: the same
tree under the same fixture must hash `dc8f37d5…` in this course and in
real git, and a verdict that says pass without naming what it proved is
the prose the audit exists to refuse.
"""

import repo as rp
import worktree as wt
import stage_01 as s1
import stage_07 as s7
import stage_05 as s5
import stage_06 as s6
import stage_08 as s8


PROOF_KEYS = ("objects", "hashes", "git_verdict")
AUDIT_KEYS = ("verdict", "reasons")
VERDICTS = ("pass", "git_disagrees", "refusal")


def run_all(repo):
    """The ladder end to end on a fresh repo; the evidence answered."""
    s1.init(repo)
    for (path, mode, data) in wt.FIXTURE_TREE:
        repo.fs.write(path, data, exec=(mode == "100755"))
    record = s7.add(repo, [path for (path, _mode, _data) in wt.FIXTURE_TREE])
    tree_sha = s5.write_tree(repo)
    # the bootstrap commit the ladder hangs from
    import objects as ob
    empty_tree = repo.object_write("tree", b"")
    line = "%s %s" % (wt.AUTHOR, wt.TIMESTAMP)
    root_body = ("tree %s\nauthor %s\ncommitter %s\n\nroot\n"
                 % (empty_tree, line, line)).encode()
    root_sha = repo.object_write("commit", root_body)
    commit_sha = s6.commit_tree(repo, tree_sha, root_sha, wt.MESSAGE)
    repo.ref_write("refs/heads/main", commit_sha)   # the branch names it
    walk = s8.log(repo, commit_sha)
    return {"objects": {"tree": tree_sha, "commit": commit_sha,
                        "staged": len(record["entries"]),
                        "log": len(walk)},
            "hashes": {"tree": tree_sha, "commit": commit_sha},
            "git_verdict": "unverified"}


def verify(repo):
    """Real git over the exported repo; the verdict and its reasons."""
    import os
    import tempfile
    import subprocess
    tmp = tempfile.mkdtemp(prefix="l4-verify-")
    repo.export(tmp)
    git_dir = os.path.join(tmp, repo.git_dir)
    if not os.path.isdir(git_dir):
        # nothing was exported to judge: a refusal, not a disagreement —
        # git has no store to read, so its complaint would be about the
        # absence, not the content
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
        return {"verdict": "refusal",
                "reasons": ("no %s was exported" % (repo.git_dir,),)}
    reasons = []
    for command in (["git", "--git-dir=%s" % git_dir, "fsck", "--strict"],
                    ["git", "--git-dir=%s" % git_dir, "log", "--oneline"]):
        out = subprocess.run(command, capture_output=True, text=True)
        if out.returncode != 0:
            reasons.append("%s: %s" % (command[2],
                                       (out.stderr or out.stdout)
                                       .strip().split("\n")[0]))
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    if reasons:
        return {"verdict": "git_disagrees", "reasons": tuple(reasons)}
    return {"verdict": "pass", "reasons": ()}
