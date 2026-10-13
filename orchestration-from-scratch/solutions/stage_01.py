"""Orchestration From Scratch — stage 1: The subtask and the graph.

The finished implementation. The reasoning — why a key the shape does not have
is refused instead of defaulted, why a missing key is a documented default and
which default belongs to this stage, why the graph comes back read-only, and
why a cycle is not this stage's refusal — lives in the DESIGN DECISION blocks of
`stage_01.py`.
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

#: The value a key takes when the shape does not spell it, materialised in the
#: record so that nothing downstream has to guess. Immutable: a shared default
#: anyone could edit is a default that changes under a caller's feet.
_DEFAULTS = types.MappingProxyType({
    "depends": (),
    "ticks": DEFAULT_TICKS,
    "tokens": DEFAULT_TOKENS,
    "effect": False,
})

#: How many single-character edits away a key may be and still be named as the
#: key that was probably meant: two covers a doubled letter and a swapped pair.
_NEAR = 2


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


def _require_mapping(source, what):
    """A subtask is a mapping of keys to values; a list, a string or a `Subtask`
    is not one."""
    if not isinstance(source, Mapping):
        raise OrchestrationError("%s must be a mapping, got %r"
                                 % (what, type(source).__name__))
    return source


def _distance(left, right):
    """The number of single-character insertions, deletions and substitutions
    between two words: the classic table of ints, no float, no early exit a
    transposition could slip past. Two words that differ in every letter are as
    far apart as the longer one is long, never further."""
    table = [[j for j in range(len(right) + 1)]]
    for i in range(1, len(left) + 1):
        row = [i]
        for j in range(1, len(right) + 1):
            cost = 0 if left[i - 1] == right[j - 1] else 1
            row.append(min(table[i - 1][j] + 1, row[j - 1] + 1,
                           table[i - 1][j - 1] + cost))
        table.append(row)
    return table[len(left)][len(right)]


def _nearest(key):
    """The key `key` was probably meant, or `None` when it is nowhere near one.

    Ties go to the earliest key in `SUBTASK_KEYS`, so the suggestion is a
    function of the typo alone and two runs suggest the same key.
    """
    best, fewest = None, None
    for candidate in SUBTASK_KEYS:
        edits = _distance(key, candidate)
        if fewest is None or edits < fewest:
            best, fewest = candidate, edits
    if best is not None and fewest <= _NEAR:
        return best
    return None


def _reject_unknown_keys(mapping, what):
    """A key the shape does not have is refused, and when it is one edit from a
    real key the real key is named.

    `**raw` into the dataclass is the mistake this stage exists for: `tickz=9`
    would be dropped, `ticks` would take its default, and a plan that says nine
    would run at one with nobody the wiser.
    """
    for key in mapping:
        if key in SUBTASK_KEYS:
            continue
        guessed = _nearest(key) if isinstance(key, str) else None
        if guessed is None:
            raise OrchestrationError("%s has no key %r; its keys are %r"
                                     % (what, key, SUBTASK_KEYS))
        raise OrchestrationError("%s has no key %r; did you mean %r? its keys "
                                 "are %r" % (what, key, guessed, SUBTASK_KEYS))
    return mapping


def _require_text(value, what):
    """A string that says something: an id, an actor or an instruction. A blank
    id is a node with no name, and two blank ids are the same node."""
    if not isinstance(value, str):
        raise OrchestrationError("%s must be a str, got %r" % (what, value))
    if not value.strip():
        raise OrchestrationError("%s must not be blank, got %r" % (what, value))
    return value


def _require_spelled(mapping, key, what):
    """A key the shape must have: present, or the node is not one. The refusal
    names the key, because that is the one thing the caller has to write."""
    if key not in mapping:
        raise OrchestrationError("%s must spell %r: a subtask without it is not "
                                 "one" % (what, key))
    return mapping[key]


def _require_count(value, what):
    """A count: a real `int` and not negative. `bool` is refused although
    `isinstance(True, int)` is true — `True` is a flag, and a flag that passes
    as the count 1 is a cost nobody wrote."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise OrchestrationError("%s must be an int, got %r" % (what, value))
    if value < 0:
        raise OrchestrationError("%s must be >= 0, got %r" % (what, value))
    return value


def _require_depends(value, what):
    """The ids a node waits for: a sequence of ids, in the order the plan wrote
    them. The order is data — stage 2's `dependencies` is what sorts and
    deduplicates — and a string is not a sequence of ids."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise OrchestrationError("%s must be a sequence of ids, got %r"
                                 % (what, value))
    depends = []
    for index, node_id in enumerate(value):
        if not isinstance(node_id, str) or not node_id.strip():
            raise OrchestrationError("%s[%d] must be a str id, got %r"
                                     % (what, index, node_id))
        depends.append(node_id)
    return tuple(depends)


def parse_subtask(raw):
    """One raw subtask into a frozen `Subtask`, every default materialised.

    A missing key is the documented default — a node that does not say what it
    costs is not an error — but an *unknown* key is refused: `{"ticks": 1,
    "tickz": 9}` is a plan that says nine and would run at one.
    """
    mapping = _reject_unknown_keys(_require_mapping(raw, "a subtask"), "a subtask")
    node_id = _require_text(_require_spelled(mapping, "id", "a subtask"),
                            "a subtask id")
    agent = _require_text(_require_spelled(mapping, "agent", "a subtask"),
                          "a subtask agent")
    prompt = _require_text(_require_spelled(mapping, "prompt", "a subtask"),
                           "a subtask prompt")
    depends = _require_depends(mapping.get("depends", _DEFAULTS["depends"]),
                               "a subtask depends")
    ticks = _require_count(mapping.get("ticks", _DEFAULTS["ticks"]), "ticks")
    tokens = _require_count(mapping.get("tokens", _DEFAULTS["tokens"]), "tokens")
    effect = mapping.get("effect", _DEFAULTS["effect"])
    if not isinstance(effect, bool):
        raise OrchestrationError("a subtask effect must be a bool, got %r"
                                 % (effect,))
    if node_id in depends:
        raise OrchestrationError("a subtask depends on itself: %r names its own "
                                 "id, so it can never start" % (node_id,))
    return Subtask(id=node_id, agent=agent, prompt=prompt, depends=depends,
                   ticks=ticks, tokens=tokens, effect=effect)


def _node(node_id, body):
    """One node of a graph: the body, under the key that names it.

    A graph's ids are its keys, so the key is the id whichever way the body
    spells it: a body that spells a *different* id names one node twice, and
    that is refused naming both. A body that spells no id at all is simply the
    node under its key.
    """
    body = _require_mapping(body, "the subtask %r" % (node_id,))
    spelled = body.get("id", node_id)
    if spelled != node_id:
        raise OrchestrationError(
            "the graph's key %r carries the id %r: a graph's ids are its keys, "
            "so this node is named twice" % (node_id, spelled))
    fields = dict(body)
    fields["id"] = node_id
    return parse_subtask(fields)


def _entries(raw):
    """The `(id, body)` pairs of a raw graph, in one order.

    A job file writes a graph either way: as a mapping of id to subtask — the
    canonical form, and the one `graphs.py`'s fixtures use — or as a sequence of
    subtasks each carrying its own `id`. Both are the same data, and only the
    sequence can repeat an id, because a mapping's keys cannot. The mapping form
    is walked in sorted key order, so which offender a refusal names first is a
    function of the plan and not of the order somebody wrote its keys in.
    """
    if isinstance(raw, Mapping):
        for key in raw:
            if not isinstance(key, str):
                raise OrchestrationError("a graph key must be a str id, got %r"
                                         % (key,))
        return [(key, raw[key]) for key in sorted(raw)]
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise OrchestrationError("a graph must be a mapping of id to subtask or "
                                 "a sequence of subtasks, got %r"
                                 % (type(raw).__name__,))
    entries = []
    for index, body in enumerate(raw):
        what = "the subtask at index %d" % (index,)
        body = _require_mapping(body, what)
        node_id = _require_text(_require_spelled(body, "id", what), "its id")
        entries.append((node_id, body))
    return entries


def parse_graph(raw):
    """A raw graph into a read-only mapping of id to `Subtask`.

    A graph is its nodes, so an empty one has nothing to run; a node that spells
    an id other than its key names one node twice; a dependency the graph does
    not have and a node that depends on itself are both nodes that can never
    start. Each is refused here, naming the id.

    What is *not* refused here is a cycle: every node of `graphs["cycles"]`
    exists and every id in it is spelled right, and the order it has none of is
    stage 2's refusal. A graph this stage would not accept is not a graph; a
    graph it accepts may still have no order.
    """
    nodes = {}
    for node_id, body in _entries(raw):
        if node_id in nodes:
            raise OrchestrationError("a graph names the id %r twice: every node "
                                     "id must be distinct" % (node_id,))
        nodes[node_id] = _node(node_id, body)
    if not nodes:
        raise OrchestrationError("a graph must have at least one node: an empty "
                                 "graph has nothing to run")
    for node_id in sorted(nodes):
        for dependency in nodes[node_id].depends:
            if dependency not in nodes:
                raise OrchestrationError(
                    "the subtask %r depends on %r, which the graph does not "
                    "have" % (node_id, dependency))
    return types.MappingProxyType({node_id: nodes[node_id]
                                   for node_id in sorted(nodes)})
