"""Orchestration From Scratch — stage 4: The handoff that carries its own context.

What a child inherits from its dependencies, and what it must not: the accepted
results of the node's **own** dependencies, each cut to the budget that
dependency declared, in the one order two runs agree on. `graphs.py` says a
`tokens` is "the budget a dependency's result is cut to when it is handed on";
this stage is what spends it, and it is the difference between an agent that
continues the work and one that re-invents it.

DESIGN DECISION — a budget is a count of *what*, and where exactly does the cut
land?
    A token is one character of a result, and that is the whole of the
    arithmetic: `len` on the string, a slice at the budget, no other number
    anywhere. The alternatives are all worse than they look. A byte count
    measures a different number for the same text — `"héllo"` is five characters
    and six bytes — and cutting the bytes of a multi-byte character in half
    gives a string nobody wrote. Four-characters-per-token is a ratio, ratios
    need a division, and a division that is not exact has to be rounded, so the
    same plan is cut to a different length depending on where somebody put the
    `int()`. A budget is a ceiling and it is exact: three tokens are three
    characters, a result that fits goes on whole, and a budget of zero hands on
    nothing at all.

DESIGN DECISION — why does a child get its dependencies' results, and not every
ancestor's?
    Because a dependency is the only node that was asked for something this node
    needs, and the whole point of a graph is that the context travels along the
    edges. Handing a child `plan`'s result because `plan` happens to be upstream
    of `render` — when the child waits only for `index` — gives it the answer of
    a node it never asked, whose result it cannot check and did not budget for;
    on a diamond that is the other branch's work arriving as if it were its own.
    Handing over the whole transcript is the same mistake at scale: every prompt,
    every prior attempt, every review comment — a context nobody can afford,
    where the one result that matters is buried, and where a node that should
    ask for what it needs silently gets everything. The handoff is the node's
    own dependencies, each id taken once, sorted by id so that two runs — and
    two dependencies — are handed the same bytes in the same order.

DESIGN DECISION — what is a state, and which state makes a result part of the
handoff?
    A state is one of the six the execution model froze — `pending`, `running`,
    `awaiting`, `ok`, `failed`, `skipped` — or a record carrying that status and
    the text the node answered. Only `ok` contributes: a `running` dependency has
    no result yet, an `awaiting` one has not been allowed to produce one, a
    `failed` one has none that was accepted, and a `skipped` one never ran at
    all. This is where the reviewer's decision is spent — an accepted review is
    what makes a text a result — and a handoff that took a rejected draft, or a
    sibling's in-flight one, would carry exactly the work the reviewer threw
    away. A status outside the six is not a state this stage guesses at: it is
    refused, naming the node and the status, because a state table with a typo
    in it hands a child the wrong thing with no error anywhere. And only a
    record whose status is `ok` has a text this stage reads: a run is free to
    keep a draft, a reason or an attempt count in a record it has not accepted.

DESIGN DECISION — what separates two results, and what does a child see when
there are none?
    Every entry is labelled with the dependency it came from and the entries are
    joined by a newline — a child reads `index: …` and `render: …` and knows
    which is which; two results glued into one line are a sentence nobody wrote,
    and the child can no longer tell whose half is whose. Each `ok` dependency
    contributes exactly one entry, in sorted order, even when its result is
    empty: one entry per accepted result is a contract a reader can count. A
    handoff with nothing in it renders to the node's prompt, exactly — no
    separator, no header, no `None`. A child handed an empty block, or a line of
    punctuation meaning "there was nothing", spends its first tokens working out
    whether it is missing something, and the same file read by an agent that
    receives no block at all is read the way its author wrote it.

DESIGN DECISION — what does this stage refuse, and why is it not stage 1's
refusal?
    Everything that would make the handoff a lie. A graph that is not a mapping,
    or whose node is not a `Subtask`, means the plan was never parsed — a
    handoff computed from raw dicts is a handoff from a plan nobody validated. A
    node the graph does not have, or a dependency it does not have, means the
    question itself is about a graph that does not exist. A state value that is
    neither one of the six statuses nor a record, a record with no `status`, a
    status outside the six, a text that is not a string, and a budget that is
    not an int count (a float, a `bool`, a negative) are each refused by naming
    the node, the status or the budget at fault, because the reader of a refusal
    is a person with a state table open in an editor. It is `HandoffError`,
    derived from stage 1's `OrchestrationError`, so one `except` still catches a
    broken graph and a broken handoff.

TODO: implement `HandoffError`, `budgeted`, `handoff` and `render_prompt`.
"""

from collections.abc import Mapping

from stage_01 import OrchestrationError, Subtask

#: The six states of the frozen execution model, in the order a reader meets
#: them. A status outside this tuple is not a state this stage guesses at.
_STATUSES = ("pending", "running", "awaiting", "ok", "failed", "skipped")

#: What separates one dependency's result from the next, and the node's prompt
#: from the block of them: one character, and the same one both times.
_SEPARATOR = "\n"

#: The keys a state record carries: the status the node is in, and the text it
#: answered. A record may carry more; the handoff reads these two.
_STATUS_KEY = "status"
_TEXT_KEY = "text"


class HandoffError(OrchestrationError):
    """A handoff this stage refuses: a plan that was never parsed, a node or a
    dependency the graph does not have, a state that is not one of the six, a
    budget that is not an int count.

    Derived from stage 1's `OrchestrationError`, so one `except` catches a
    broken graph and a broken handoff, and every message names the node, the
    status or the budget at fault.
    """


def budgeted(text, tokens):
    """`text` cut to `tokens` characters, exactly, or the refusal that names the
    budget it was given."""
    raise NotImplementedError("stage 4: implement budgeted()")


def handoff(graph, states, node_id):
    """The accepted results of the node's own dependencies, each cut to the
    budget that dependency declared, in sorted order."""
    raise NotImplementedError("stage 4: implement handoff()")


def render_prompt(graph, states, node_id):
    """The node's prompt, and its handoff when it has one."""
    raise NotImplementedError("stage 4: implement render_prompt()")
