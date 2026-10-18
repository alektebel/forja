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

PROOF_KEYS = ("objects", "hashes", "git_verdict")
AUDIT_KEYS = ("verdict", "reasons")
VERDICTS = ("pass", "git_disagrees", "refusal")


def run_all(repo):
    """The ladder end to end on a fresh repo; the evidence answered."""
    raise NotImplementedError("stage 10: implement run_all()")


def verify(repo):
    """Real git over the exported repo; the verdict and its reasons."""
    raise NotImplementedError("stage 10: implement verify()")
