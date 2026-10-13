"""graphs.py — the raw plans, before anything validates them, PROVIDED COMPLETE.

A big task is a graph of small ones, and the graph is data. This file is the
data: nine fixtures of the shape a job file carries — a node id to a raw subtask
dict — written the way a user would write them, not the way a validator would
accept them. Every id is a short, meaningful word (`render`, `index`, `ship`)
and every number is a small int, so a reader can count a fixture's nodes by eye:

`single` (1 node), `chain` (3 nodes), `diamond` (4 nodes), `review` (2 nodes),
`gate` (2 nodes), `wide` (7 nodes), `deep` (5 nodes), `cycles` (2 nodes) and
`orphan` (2 nodes).

Two of the nine are broken on purpose. `cycles` is a graph that parses and then
has no order — `render` waits for `index` and `index` waits for `render` — and
`orphan` is a graph that names a dependency the graph does not have (`render`
waits for `plan`). They are kept here so that a check asserts the *refusal* and
not a missing fixture: an absent fixture is a broken check, a refused one is the
course.

Nothing here validates, orders, schedules or runs anything. `parse_subtask` and
`parse_graph` are stage 1's, `validate_order` is stage 2's, and this module is
careful about exactly one thing: a fixture, a shape or an override that is not
what it says is refused here, naming the offender, so that a plan never silently
loses a node or a field. Nothing here reads a clock, a network or a file.
"""

import types

#: The keys a raw subtask carries. A key outside this tuple is what stage 1's
#: `parse_subtask` refuses, naming it: a typo that quietly becomes a default is
#: the failure this course exists to prevent.
SUBTASK_KEYS = ("id", "agent", "prompt", "depends", "ticks", "tokens", "effect")

#: What a node built on the fly (`chain`, `fan`) costs when it does not say.
DEFAULT_TICKS = 1

#: What a node built on the fly is worth to its dependents: the budget a
#: dependency's result is cut to when it is handed on.
DEFAULT_TOKENS = 8

#: The raw plans: the shape a job file carries, before anything validates it.
#: A fixture is a mapping of node id to raw subtask, and the two broken ones are
#: the two that must be refused — a cycle, and a dependency on a node that is
#: not there.
GRAPHS = types.MappingProxyType({
    "single": {
        "render": {"id": "render", "agent": "worker",
                   "prompt": "render the page", "depends": (),
                   "ticks": 2, "tokens": 8, "effect": False},
    },
    "chain": {
        "plan": {"id": "plan", "agent": "planner",
                 "prompt": "plan the release", "depends": (),
                 "ticks": 1, "tokens": 16, "effect": False},
        "render": {"id": "render", "agent": "worker",
                   "prompt": "render the pages", "depends": ("plan",),
                   "ticks": 3, "tokens": 32, "effect": False},
        "index": {"id": "index", "agent": "worker",
                  "prompt": "index the pages", "depends": ("render",),
                  "ticks": 2, "tokens": 24, "effect": False},
    },
    "diamond": {
        "plan": {"id": "plan", "agent": "planner",
                 "prompt": "plan the release", "depends": (),
                 "ticks": 1, "tokens": 16, "effect": False},
        "render": {"id": "render", "agent": "worker",
                   "prompt": "render the pages", "depends": ("plan",),
                   "ticks": 3, "tokens": 32, "effect": False},
        "index": {"id": "index", "agent": "worker",
                  "prompt": "index the pages", "depends": ("plan",),
                  "ticks": 5, "tokens": 32, "effect": False},
        "join": {"id": "join", "agent": "worker",
                 "prompt": "join the two results",
                 "depends": ("index", "render"),
                 "ticks": 1, "tokens": 24, "effect": False},
    },
    "review": {
        "render": {"id": "render", "agent": "worker",
                   "prompt": "render the page", "depends": (),
                   "ticks": 3, "tokens": 32, "effect": False},
        "review": {"id": "review", "agent": "reviewer",
                   "prompt": "review the render", "depends": ("render",),
                   "ticks": 1, "tokens": 8, "effect": False},
    },
    "gate": {
        "ask": {"id": "ask", "agent": "approver",
                "prompt": "ask to ship the release", "depends": (),
                "ticks": 1, "tokens": 8, "effect": False},
        "ship": {"id": "ship", "agent": "worker",
                 "prompt": "ship the release", "depends": ("ask",),
                 "ticks": 3, "tokens": 16, "effect": True},
    },
    "wide": {
        "plan": {"id": "plan", "agent": "planner",
                 "prompt": "plan the batch", "depends": (),
                 "ticks": 1, "tokens": 16, "effect": False},
        "render": {"id": "render", "agent": "worker",
                   "prompt": "render the pages", "depends": ("plan",),
                   "ticks": 3, "tokens": 16, "effect": False},
        "index": {"id": "index", "agent": "worker",
                  "prompt": "index the pages", "depends": ("plan",),
                  "ticks": 5, "tokens": 16, "effect": False},
        "notify": {"id": "notify", "agent": "worker",
                   "prompt": "notify the readers", "depends": ("plan",),
                   "ticks": 1, "tokens": 8, "effect": False},
        "audit": {"id": "audit", "agent": "worker",
                  "prompt": "audit the pages", "depends": ("plan",),
                  "ticks": 2, "tokens": 16, "effect": False},
        "digest": {"id": "digest", "agent": "worker",
                   "prompt": "digest the readers", "depends": ("plan",),
                   "ticks": 2, "tokens": 8, "effect": False},
        "purge": {"id": "purge", "agent": "worker",
                  "prompt": "purge the caches", "depends": ("plan",),
                  "ticks": 1, "tokens": 8, "effect": False},
    },
    "deep": {
        "fetch": {"id": "fetch", "agent": "worker",
                  "prompt": "fetch the sources", "depends": (),
                  "ticks": 1, "tokens": 8, "effect": False},
        "parse": {"id": "parse", "agent": "worker",
                  "prompt": "parse the sources", "depends": ("fetch",),
                  "ticks": 1, "tokens": 8, "effect": False},
        "render": {"id": "render", "agent": "worker",
                   "prompt": "render the pages", "depends": ("parse",),
                   "ticks": 2, "tokens": 16, "effect": False},
        "index": {"id": "index", "agent": "worker",
                  "prompt": "index the pages", "depends": ("render",),
                  "ticks": 2, "tokens": 16, "effect": False},
        "publish": {"id": "publish", "agent": "worker",
                    "prompt": "publish the index", "depends": ("index",),
                    "ticks": 1, "tokens": 8, "effect": False},
    },
    # the two that must be refused: every node exists and every id is spelled
    # right, and the graph still cannot run.
    "cycles": {
        "render": {"id": "render", "agent": "worker",
                   "prompt": "render the pages", "depends": ("index",),
                   "ticks": 1, "tokens": 8, "effect": False},
        "index": {"id": "index", "agent": "worker",
                  "prompt": "index the pages", "depends": ("render",),
                  "ticks": 1, "tokens": 8, "effect": False},
    },
    "orphan": {
        "render": {"id": "render", "agent": "worker",
                   "prompt": "render the pages", "depends": ("plan",),
                   "ticks": 1, "tokens": 8, "effect": False},
        "index": {"id": "index", "agent": "worker",
                  "prompt": "index the pages", "depends": ("render",),
                  "ticks": 1, "tokens": 8, "effect": False},
    },
})

#: The fixture names, sorted: the order a report lists them in.
ALL_GRAPH_NAMES = tuple(sorted(GRAPHS))


class GraphError(ValueError):
    """A fixture, a shape or an override the raw plans refuse.

    A refusal here is always about the *fixture helper* — a name that is not a
    fixture, a node a fixture does not have, a field a subtask does not have, an
    empty chain — and never about a graph's validity. Whether a graph is well
    formed is stage 1's refusal and whether it has an order is stage 2's, and
    that is why `cycles` and `orphan` are kept here raw.
    """


def _raw(node_id, depends):
    """One raw subtask for a shape built on the fly: a worker, a one-line
    prompt, the default estimate and budget, and no effect."""
    return {"id": node_id, "agent": "worker", "prompt": "run %s" % node_id,
            "depends": tuple(depends), "ticks": DEFAULT_TICKS,
            "tokens": DEFAULT_TOKENS, "effect": False}


def _require_id(shape, node_id):
    """One id of a shape built on the fly: a string, or the shape refuses."""
    if not isinstance(node_id, str):
        raise GraphError("%s: %r is not a string id" % (shape, node_id))
    return node_id


def _unique(shape, ids):
    """The ids of a shape built on the fly, checked once: every one a string and
    none repeated — a repeated id silently drops a node."""
    for index, node_id in enumerate(ids):
        _require_id(shape, node_id)
        if node_id in ids[:index]:
            raise GraphError("%s: %r repeats an id" % (shape, node_id))
    return tuple(ids)


def pick(name, **overrides):
    """One fixture by name, its fields overridden — `pick("chain")` is the
    chain itself, `pick("diamond", ticks=9)` is every one of its nodes costing
    nine ticks, and `pick("diamond", render={"ticks": 9})` is only `render`
    costing nine (a node's own fields win over the whole fixture's).

    The copy is fresh and mutable: a fixture is a raw plan, and editing one
    before stage 1 parses it is what the fixtures are for. A name that is not a
    fixture, a node the fixture does not have and a field a subtask does not
    have are refused here, naming the offender — a fixture that silently loses
    an override is the same failure as a typo'd key in a job file.
    """
    if not isinstance(name, str) or name not in GRAPHS:
        raise GraphError("pick(%r): want one of %r" % (name, ALL_GRAPH_NAMES))
    graph = {node_id: dict(node) for node_id, node in GRAPHS[name].items()}
    fields, nodes = {}, {}
    for key, value in overrides.items():
        if key in graph:
            if not isinstance(value, dict):
                raise GraphError("pick(%r, %s=%r): a node's override is a dict "
                                 "of fields" % (name, key, value))
            for field in value:
                if field not in SUBTASK_KEYS:
                    raise GraphError("pick(%r, %s=%r): %r is not one of %r"
                                     % (name, key, value, field, SUBTASK_KEYS))
            nodes[key] = value
        elif key in SUBTASK_KEYS:
            fields[key] = value
        else:
            raise GraphError("pick(%r, %s=%r): neither a node of %r nor a "
                             "subtask key" % (name, key, value, name))
    for key, value in fields.items():
        for node in graph.values():
            node[key] = value
    for node_id, value in nodes.items():
        graph[node_id].update(value)
    return graph


def chain(*ids):
    """A line of `ids`, built on the fly: every node depends on the one before
    it — `chain("plan", "render", "index")` is a three-node chain, and
    `chain("plan")` is a single node with nothing to wait for."""
    if not ids:
        raise GraphError("chain() needs at least one id")
    ids = _unique("chain()", ids)
    graph, previous = {}, ()
    for node_id in ids:
        graph[node_id] = _raw(node_id, previous)
        previous = (node_id,)
    return graph


def fan(root, *leaves):
    """`root` and the leaves that depend on it, built on the fly:
    `fan("plan", "render", "index")` is a three-node fan whose two leaves both
    wait for the plan — the shape a diamond's two branches start from."""
    if not leaves:
        raise GraphError("fan(%r) needs at least one leaf" % (root,))
    ids = _unique("fan()", (root,) + tuple(leaves))
    graph = {ids[0]: _raw(ids[0], ())}
    for leaf in ids[1:]:
        graph[leaf] = _raw(leaf, (ids[0],))
    return graph
