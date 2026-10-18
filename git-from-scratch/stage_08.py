"""Git From Scratch — stage 8: The log: history is parents, walked and
verified.

`git log` is the object store read as history: start at a sha, read the
commit, follow `parent`, repeat — newest first. The discipline is in what
the walk refuses: a sha that names no object, an object that claims to be
a commit but is not, a parent that names nothing, and — the one only a
walker can see — a cycle, a commit naming an ancestor already visited,
which turns history into a loop the pretty-printer never leaves.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why verify every commit's type as the walk passes it?
Because the parent sha is data, not proof: a tree whose bytes were
overwritten to name a parent would send the walk into an object that
cannot answer. Reading a sha is one door; reading it as a commit is the
contract — and the check plants a parent that is a tree to prove the
walk checks.

DESIGN DECISION — why is a cycle a refusal rather than a stop?
Because a cycle is not a shape history has: real git's commits form a DAG
by construction, and a walker that silently stopped would answer a
truncated history with no word of why. A refusal names the sha where the
loop closes — the one fact a user needs to fix the store.

DESIGN DECISION — why answer the whole walk as a tuple rather than an
iterator?
Because the walk's failures are its answers: a refusal on the tenth
commit leaves the caller with nine and no way to know. A tuple either
arrives whole or not at all, which is the same all-or-nothing every other
stage's answer carries.
"""

import repo as rp

LOG_KEYS = ("sha", "tree", "parent", "message")


def log(repo, sha):
    """The history from `sha`, newest first, every step verified."""
    raise NotImplementedError("stage 8: implement log()")
