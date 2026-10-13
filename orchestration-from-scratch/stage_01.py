"""Orchestration From Scratch — stage 1: The subtask and the graph.

The first stage and the vocabulary every later one speaks: what a subtask is and
what a graph of them is, before anything orders, schedules or runs one.
`graphs.py` hands this stage raw plans — a mapping of node id to a subtask
written the way a user would write it — and this stage hands every later stage
the frozen record and the read-only graph they are written against.

DESIGN DECISION — why is a key the shape does not have refused, when a missing
key is only a default?
    Because the two mistakes read differently and behave identically. `{"ticks":
    1}` is understood: the node does not say what it costs, and the default is a
    decision somebody made and this stage documents. `{"ticks": 1, "tickz": 9}`
    is not understood: it says nine, and `**raw` into the dataclass would drop
    the nine and run at one — a plan whose cost is silently not its own. So the
    unknown key is refused, and when it is one edit from a real key the real key
    is named, because `tickz` is not a plan that is broken but a plan that is
    misspelled, and the cheapest fix is to say which key was meant.

DESIGN DECISION — why is this stage's default budget 512 and not
`graphs.DEFAULT_TOKENS` (8)?
    Because the two default for different authors. `graphs.DEFAULT_TOKENS` is
    what the fixture helpers bake into a shape they build on the fly: a number
    somebody chose while writing the fixtures, invisible to a reader of a plan.
    This stage's default is what a *user's* plan gets when it spells nothing —
    the value the course documents for "this node did not say what it is worth",
    and a value this stage owns so that changing a fixture helper cannot silently
    change how a job file parses.

DESIGN DECISION — why does `parse_graph` come back as a read-only mapping with
sorted ids, and not the dict it was handed?
    Because a validated graph is the input of every later stage. If it were a
    dict, stage 3's scheduler could add a node stage 5's reviewer never saw, and
    two stages would be reasoning about two different graphs — a divergence with
    no error and no message. `types.MappingProxyType` makes the graph a value: a
    stage that tries to edit it gets a `TypeError` at the attempt instead of a
    mystery three stages on. The ids are sorted for the same reason: a plan
    written in a different key order is the same plan, and sorting is what makes
    its parsed form the same value and every refusal name the same offender
    first.

DESIGN DECISION — why is a cycle *not* refused here, while a dependency the
graph does not have, and a node that depends on itself, are?
    Because the three are not the same kind of fact. An unknown dependency means
    the plan names something that is not in it — the graph is not a graph, and
    no later stage could even look that id up. A cycle means every node exists
    and every id is spelled right and the graph simply has no order; that is a
    fact about ordering, it is stage 2's refusal to make, and the course keeps
    `graphs["cycles"]` raw precisely so that this stage is asserted to accept it.
    Refusing a cycle here would also hide stage 2's own mistake: an order
    function that detects a cycle by counting waves needs the cycle to reach it.

DESIGN DECISION — why a frozen record with `depends` a tuple, and why is a count
never a `bool`?
    A subtask is shared: the scheduler holds it, the handoff reads it, the record
    reports on it, and two of those stages may hold the same object at once. A
    frozen record is a value — hashable, comparable by its fields, impossible to
    edit in place — so no stage can change another stage's view of the plan, and
    `depends` is a tuple for exactly the same reason: a list would let one stage's
    edit move another stage's edges. `bool` is refused as a count although
    `isinstance(True, int)` is true, because `True` is a flag: a plan that says
    `"ticks": True` says nothing about cost, and accepting it would charge the
    node one tick that nobody wrote.

DESIGN DECISION — why does every refusal name the id, the key or both?
    Because the reader of a refusal is a person with a plan open in an editor.
    "A graph is invalid" costs them a bisection; "the subtask 'render' depends on
    'plan', which the graph does not have" costs them one line. The same rule
    makes `parse_graph` take a graph written either as a mapping of id to subtask
    or as a sequence of subtasks each carrying its own `id` — both are the same
    data — and refuse a repeated id by naming it, because a graph with two nodes
    called `render` is a plan that will lose one of them somewhere downstream.

TODO: implement `SUBTASK_KEYS`, `DEFAULT_TOKENS`, `OrchestrationError`, `Subtask`,
`parse_subtask` and `parse_graph`.
"""

import types
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from graphs import DEFAULT_TICKS

#: The keys a raw subtask may carry, in the order a reader meets them. A key
#: outside this tuple is a typo, and a typo is not a default: it is refused,
#: naming the key that was probably meant.
SUBTASK_KEYS = ("id", "agent", "prompt", "depends", "ticks", "tokens", "effect")

#: What a node that does not say what it is worth is worth: the budget its
#: result is cut to when a dependency hands it on. This is the *plan's* default:
#: `graphs.DEFAULT_TOKENS` (8) is what the fixture helpers bake into a shape they
#: build on the fly, and a raw plan that spells nothing gets this one.
DEFAULT_TOKENS = 512


class OrchestrationError(ValueError):
    """A node, or a graph of them, that this course refuses.

    The base refusal: every later stage derives its own from this one, so one
    `except` catches a broken graph and a broken handoff, and every message names
    the id, the key or the pair at fault.
    """


@dataclass(frozen=True)
class Subtask:
    """One unit of a plan: who runs it, what it is told, what it waits for, what
    it costs, what it is worth and whether it changes the world.

    Frozen, so a parsed graph is shareable and hashable and no stage can edit a
    node in place; `depends` is a tuple for the same reason, and `ticks` and
    `tokens` are counts — never floats, and never the flag `True`.
    """

    id: str
    agent: str
    prompt: str
    depends: tuple
    ticks: int
    tokens: int
    effect: bool


def parse_subtask(raw):
    """One raw subtask into a frozen `Subtask`, every default materialised."""
    raise NotImplementedError("stage 1: implement parse_subtask()")


def parse_graph(raw):
    """A raw graph into a read-only mapping of id to `Subtask`."""
    raise NotImplementedError("stage 1: implement parse_graph()")
