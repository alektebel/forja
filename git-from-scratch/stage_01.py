"""Git From Scratch — stage 1: The repository: a `.git` is a layout, and
HEAD is a promise.

Every object, ref and config a repository owns lives under `.git`, and
`init` is the command that says so: `objects/` for the store, `refs/` for
the names, and `HEAD` — one line, `"ref: refs/heads/main\\n"`, newline
included — promising which branch the next commit belongs to. A layout that
omits the newline is a line real git misreads; a second `init` that wipes
what it finds is a command that destroys history instead of finding it.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why is `init` idempotent rather than refusing?
Because the command's promise is "this repository exists with this layout",
not "this repository is new". Real git's own `init` on an existing
repository answers `Reinitialized existing` and keeps everything; a refusal
would make every later stage's setup brittle, and an erase would make it
destructive.

DESIGN DECISION — why does `HEAD_STATUS` name the layout instead of the
stage checking paths one by one?
Because the layout is the contract: a repository with an extra file is fine,
a repository missing `objects/` is not, and the check proves the *set* —
the three names the store cannot work without — rather than a snapshot of
whatever the implementation happened to create. The tuple is also the
check's refusal message: an init that forgets `refs/` fails with the name
in hand.

DESIGN DECISION — why does `HEAD` write through `repo.head_write` rather
than the stage's own `fs.write`?
Because HEAD is the one file whose *meaning* lives outside its bytes: the
ref doors (`head_read`, `ref_read`) parse the line, and writing it raw
would let stage 1 invent a dialect every later stage must then parse. One
door, one dialect — and the newline is the door's business, not the
caller's.
"""

import repo as rp

HEAD_STATUS = None


def init(repo):
    """The layout: objects/, refs/heads/, and HEAD's one promised line."""
    raise NotImplementedError("stage 1: implement init()")
