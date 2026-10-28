"""Orchestration From Scratch — course manifest.

Ten graded stages between a task that is too big for one agent and a run you can
replay. The world is provided: `fleet.py` is J1's, verbatim (the injected clock,
the immutable task and pool specs, the scripted workers that are honest about
what they cost), `agents.py` is the model as a callable (a scripted `Agent`
answering `Reply(text, tokens)` — attempt 1, 2, 3 … are the entries of its plan)
and `graphs.py` is the raw plans, before anything validates them.

The thesis of the whole course is one sentence, and every stage's check asserts
it: A BIG TASK IS A GRAPH OF SMALL ONES, AND THE GRAPH IS DATA. Every stage is
one decision about that graph — what a subtask is and what a typo in one must
refuse, which nodes may run now and why a wave is not a schedule, what a child
inherits from its dependencies, who is allowed to reject the work and what
happens to it then, what one failure costs the rest of the graph, and who signs
off *before* an effect lands. The failures worth preventing are the ones that
look like progress: a fast node waiting on a slow sibling in the same wave, a
handoff that carries the whole transcript, a rejection recorded and ignored, a
failed dependency whose children run anyway, a budget checked after the call,
and the classic — an approval that arrives after the effect.

Standard library only, offline, deterministic, **every number an int** (ticks
and tokens): no `time`, no `threading`, no `asyncio`, no unseeded randomness, no
module-level mutable state, and the clock is the injected `Clock`, so two runs of
the same graph with the same agents produce identical bytes.

    python3 codecraft/cli.py run orchestration-from-scratch
"""

from codecraft.api import stage

TITLE = "Orchestration From Scratch"
DESCRIPTION = ("A big task as a graph of small ones: parse a subtask so a typo "
               "refuses instead of defaulting and validate the graph a cycle "
               "would break, order it by the dependency each node declares, "
               "schedule by the states rather than by the wave, hand a child "
               "exactly its own dependencies' results inside their own budget, "
               "let a reviewer reject and a node rework with the reason, skip "
               "the transitive dependents of a failure without running them, ask "
               "for approval before an effect instead of after it, refuse a call "
               "the budget cannot pay for, recompute the report from the record, "
               "and run the whole orchestration to identical bytes twice.")
LEVEL = "advanced"
ORDER = 21

# --- the checks. Each one is self-contained: its fixtures are nested
# inside it because `course.py` is one namespace for ten stages.

import json
import os
import shutil
import sys
import tempfile


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "orchestration-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J2_REPO=/path/to/forja")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    from collections.abc import Mapping

    import dataclasses
    import graphs
    import stage_01 as s

    def subtask(**fields):
        """One hand-written raw subtask that parses unless the case says
        otherwise: the three required keys, then whatever the case is about."""
        bag = {"id": "render", "agent": "worker", "prompt": "render the pages"}
        bag.update(fields)
        return bag

    # ---- the vocabulary every later stage speaks --------------------------

    assert s.SUBTASK_KEYS == ("id", "agent", "prompt", "depends", "ticks",
                              "tokens", "effect"), (
        "this stage's keys are %r, not the seven the course defined"
        % (s.SUBTASK_KEYS,))
    assert graphs.SUBTASK_KEYS == s.SUBTASK_KEYS, (
        "the raw plans' keys are %r and this stage's are %r: the plans and the "
        "parser must speak one vocabulary"
        % (graphs.SUBTASK_KEYS, s.SUBTASK_KEYS))
    assert s.DEFAULT_TOKENS == 512, (
        "this stage's documented default for a node that does not say what it "
        "is worth is %r, not 512" % (s.DEFAULT_TOKENS,))
    assert issubclass(s.OrchestrationError, ValueError), (
        "%r is not a ValueError: the course's refusal is a named error a caller "
        "can catch, and every later stage derives its own from it"
        % (s.OrchestrationError,))
    assert dataclasses.is_dataclass(s.Subtask), (
        "%r is not a dataclass: the record is the course's vocabulary"
        % (s.Subtask,))
    assert s.Subtask.__dataclass_params__.frozen, (
        "%r is not frozen: a stage that parses a graph could then edit another "
        "stage's node in place" % (s.Subtask,))

    # ---- the mechanism, hand-computed on the smallest plan ----------------

    single = s.parse_graph(graphs.pick("single"))
    assert isinstance(single, Mapping), (
        "graphs['single'] parsed to %r, which is not a mapping" % (single,))
    assert tuple(single) == ("render",), (
        "graphs['single'] parsed to the ids %r, not ('render',)" % (tuple(single),))
    record = single["render"]
    assert isinstance(record, s.Subtask), (
        "the graph's value is %r, not a `Subtask` record" % (record,))
    assert record == s.Subtask(id="render", agent="worker",
                               prompt="render the page", depends=(),
                               ticks=2, tokens=8, effect=False), (
        "graphs['single'] parsed to %r, not the record its own plan spells: "
        "worker, 'render the page', nothing to wait for, 2 ticks, 8 tokens, no "
        "effect" % (record,))
    assert type(record.ticks) is int and type(record.tokens) is int, (
        "the counts parsed as %r and %r, not as ints"
        % (type(record.ticks), type(record.tokens)))
    assert type(record.effect) is bool, (
        "the effect parsed as %r: `effect` is a bool, and `False == 0` would "
        "hide a number behind the flag" % (type(record.effect),))
    assert type(record.depends) is tuple, (
        "depends parsed as %r, not a tuple: a frozen record's edges must not be "
        "a list another stage can edit" % (type(record.depends),))

    # the second level: a node waits for its own dependency, never for an
    # ancestor's
    chain = s.parse_graph(graphs.pick("chain"))
    assert tuple(chain) == ("index", "plan", "render"), (
        "graphs['chain'] parsed to the ids %r: a graph's ids are its keys and "
        "they come back sorted, whatever order the plan was written in"
        % (tuple(chain),))
    assert chain["plan"].depends == (), (
        "the chain's first node waits for %r, not for nothing"
        % (chain["plan"].depends,))
    assert chain["render"].depends == ("plan",), (
        "the chain's second node waits for %r, not ('plan',)"
        % (chain["render"].depends,))
    assert chain["index"].depends == ("render",), (
        "the chain's last node waits for %r, not ('render',): a node inherits "
        "nothing from its dependency's dependencies"
        % (chain["index"].depends,))
    assert chain["render"].ticks == 3 and chain["index"].ticks == 2, (
        "the chain's costs parsed as %r and %r, not 3 and 2: each node's own "
        "estimate is the node's"
        % (chain["render"].ticks, chain["index"].ticks))

    # a diamond: the plan's own dependency order, kept
    diamond = s.parse_graph(graphs.pick("diamond"))
    assert tuple(diamond) == ("index", "join", "plan", "render"), (
        "graphs['diamond'] parsed to the ids %r, not its four nodes sorted"
        % (tuple(diamond),))
    assert diamond["join"].depends == ("index", "render"), (
        "the diamond's join waits for %r, not the order its plan wrote: "
        "('index', 'render') — this stage keeps what the plan spelled, and "
        "stage 2's `dependencies` is what sorts and deduplicates"
        % (diamond["join"].depends,))
    assert diamond["index"].ticks == 5 and diamond["render"].ticks == 3, (
        "the diamond's branch costs parsed as %r and %r, not 5 and 3"
        % (diamond["index"].ticks, diamond["render"].ticks))

    # a plan's own order and repeats are data: nothing is sorted or deduplicated
    written = s.parse_subtask(subtask(id="join",
                                      depends=("render", "index", "render")))
    assert written.depends == ("render", "index", "render"), (
        "a plan that spelled ('render', 'index', 'render') parsed to %r: the "
        "order and the repeat are what the plan wrote, and normalising them here "
        "would hide a dependency a later stage has to see" % (written.depends,))
    from_list = s.parse_subtask(subtask(depends=["plan"]))
    assert from_list.depends == ("plan",), (
        "a plan that spelled its dependencies as the list ['plan'] parsed to %r, "
        "not the tuple ('plan',)" % (from_list.depends,))

    # ---- the defaults are this stage's, and a spelled value always wins ----

    bare = s.parse_subtask({"id": "render", "agent": "worker",
                            "prompt": "render the pages"})
    assert bare.depends == (), (
        "a node that does not say what it waits for waits for %r, not nothing"
        % (bare.depends,))
    assert bare.ticks == graphs.DEFAULT_TICKS, (
        "a node that does not say what it costs costs %r, not "
        "graphs.DEFAULT_TICKS (%r)" % (bare.ticks, graphs.DEFAULT_TICKS))
    assert bare.tokens == s.DEFAULT_TOKENS, (
        "a node that does not say what it is worth is worth %r, not this "
        "stage's documented default %r — graphs.DEFAULT_TOKENS (%r) is the "
        "number the fixture helpers bake into the shapes they build, not what a "
        "user's plan gets"
        % (bare.tokens, s.DEFAULT_TOKENS, graphs.DEFAULT_TOKENS))
    assert bare.effect is False, (
        "a node that does not say whether it changes the world parsed with "
        "effect=%r: an effect is claimed, never assumed, and an assumed effect "
        "would gate a node nobody meant to gate" % (bare.effect,))
    spelled = s.parse_subtask(subtask(ticks=0, tokens=0, effect=True))
    assert (spelled.ticks, spelled.tokens, spelled.effect) == (0, 0, True), (
        "a plan that spelled its own zeroes and its own effect parsed to %r: a "
        "value the plan spells always wins over the default" % (spelled,))

    # ---- boundaries: the empty graph, one node, the second level ----------

    for empty in ({}, []):
        message = _refuses(s.OrchestrationError, "the empty graph %r" % (empty,),
                           lambda empty=empty: s.parse_graph(empty))
        assert "empty" in message, (
            "the refusal of an empty graph does not say the graph is empty: %r"
            % (message,))

    # ---- the graph is a value: read-only, copied, id-ordered --------------

    try:
        single["index"] = record
    except TypeError:
        pass
    else:
        raise AssertionError(
            "the parsed graph is writable (`single['index'] = ...` worked): a "
            "validated graph must be read-only, or one stage can change what "
            "another stage was handed")
    try:
        record.ticks = 9
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError(
            "the record is not frozen: an assignment to %r went through"
            % (record,))
    assert hash(record) == hash(s.Subtask(id="render", agent="worker",
                                          prompt="render the page", depends=(),
                                          ticks=2, tokens=8, effect=False)), (
        "two equal records hash differently (%r): a frozen record is what lets a "
        "state table use a node as a key" % (record,))

    plan = graphs.pick("chain")
    parsed = s.parse_graph(plan)
    plan["render"]["ticks"] = 99
    plan["index"]["depends"] = ("render", "plan")
    assert parsed["render"].ticks == 3, (
        "editing the raw plan after parsing changed the parsed graph's cost to "
        "%r: the parser copies what it validates" % (parsed["render"].ticks,))
    assert parsed["index"].depends == ("render",), (
        "editing the raw plan after parsing changed the parsed graph's edges to "
        "%r: the parser copies what it validates" % (parsed["index"].depends,))

    one = s.parse_graph({"z": subtask(id="z"), "a": subtask(id="a")})
    two = s.parse_graph({"a": subtask(id="a"), "z": subtask(id="z")})
    assert tuple(one) == tuple(two) == ("a", "z"), (
        "two spellings of the same plan parsed to %r and %r: the ids come back "
        "sorted, so the order somebody wrote a plan's keys in cannot reach the "
        "run" % (tuple(one), tuple(two)))
    sequence = s.parse_graph([subtask(id="z"), subtask(id="a")])
    assert tuple(sequence) == ("a", "z"), (
        "the sequence form parsed to %r, not sorted" % (tuple(sequence),))
    assert dict(sequence) == dict(one), (
        "the sequence form and the mapping form of the same plan parsed "
        "differently: %r and %r" % (dict(sequence), dict(one)))
    keyless = s.parse_graph({"render": {"agent": "worker", "prompt": "run it"}})
    assert keyless["render"] == s.Subtask(id="render", agent="worker",
                                         prompt="run it", depends=(),
                                         ticks=graphs.DEFAULT_TICKS,
                                         tokens=s.DEFAULT_TOKENS, effect=False), (
        "a body that spells no id parsed to %r: the graph's key is the node's "
        "id whenever the body does not restate it" % (keyless["render"],))
    later = s.parse_graph({"b": {"agent": "worker", "prompt": "run b",
                                 "depends": ("a",)},
                           "a": {"agent": "worker", "prompt": "run a"}})
    assert later["b"].depends == ("a",), (
        "a dependency written before the node it names did not parse: %r"
        % (dict(later),))

    # ---- every provided fixture is parsed or refused, none is skipped -----

    counts = {"single": 1, "chain": 3, "diamond": 4, "review": 2, "gate": 2,
              "wide": 7, "deep": 5, "cycles": 2}
    assert set(counts) | {"orphan"} == set(graphs.ALL_GRAPH_NAMES), (
        "this check parses %r and refuses 'orphan', and the provided fixtures "
        "are %r: a fixture that is neither parsed nor refused is one nobody "
        "proved" % (sorted(counts), list(graphs.ALL_GRAPH_NAMES)))
    for name in sorted(counts):
        fixture = graphs.pick(name)
        printed = s.parse_graph(fixture)
        assert len(printed) == counts[name], (
            "graphs[%r] has %d nodes and parsed to %d"
            % (name, counts[name], len(printed)))
        assert tuple(printed) == tuple(sorted(printed)), (
            "graphs[%r] parsed to the ids %r, which are not sorted: a mapping's "
            "ids are read in a documented order" % (name, tuple(printed)))
        for node_id in sorted(fixture):
            raw = fixture[node_id]
            got = printed[node_id]
            assert (got.id, got.agent, got.prompt, got.depends, got.ticks,
                    got.tokens, got.effect) == (
                        raw["id"], raw["agent"], raw["prompt"],
                        tuple(raw["depends"]), raw["ticks"], raw["tokens"],
                        raw["effect"]), (
                "graphs[%r]'s node %r parsed to %r, not its own plan %r"
                % (name, node_id, got, raw))

    # ---- the probe: a cycle is stage 2's refusal, not this stage's --------

    cycles = s.parse_graph(graphs.pick("cycles"))
    assert tuple(cycles) == ("index", "render"), (
        "graphs['cycles'] parsed to %r, not its two nodes" % (tuple(cycles),))
    assert cycles["render"].depends == ("index",), (
        "graphs['cycles'] parsed with 'render' waiting for %r, not ('index',)"
        % (cycles["render"].depends,))
    assert cycles["index"].depends == ("render",), (
        "graphs['cycles'] parsed with 'index' waiting for %r, not ('render',): "
        "every id in the fixture exists, so this stage accepts it — that it has "
        "no order is stage 2's refusal" % (cycles["index"].depends,))

    # ---- a key the shape does not have is refused by naming the real one --

    for typo, meant in (("tickz", "ticks"), ("tokez", "tokens"),
                        ("depnds", "depends"), ("efect", "effect"),
                        ("pompt", "prompt"), ("aget", "agent")):
        message = _refuses(
            s.OrchestrationError, "a subtask with the key %r" % (typo,),
            lambda typo=typo: s.parse_subtask(subtask(**{typo: 1})))
        assert "'%s'" % typo in message, (
            "the refusal of %r does not name the key: %r" % (typo, message))
        assert "'%s'" % meant in message and "did you mean" in message, (
            "the refusal of %r is %r: a typo is refused by naming the key that "
            "was probably meant (%r), or the reader has to guess"
            % (typo, message, meant))
    message = _refuses(
        s.OrchestrationError, "a key that resembles no real key",
        lambda: s.parse_subtask(subtask(wibble=1)))
    assert "'wibble'" in message and "did you mean" not in message, (
        "the refusal of 'wibble' proposes a key anyway: %r — a suggestion nobody "
        "meant costs the reader more than no suggestion" % (message,))
    assert "'ticks'" in message and "'effect'" in message, (
        "the refusal of an unknown key does not list the keys that exist: %r"
        % (message,))
    message = _refuses(
        s.OrchestrationError, "a subtask key that is not a string",
        lambda: s.parse_subtask({"id": "render", "agent": "worker",
                                 "prompt": "render the pages", 7: 1}))
    assert "7" in message, (
        "the refusal of the key 7 does not name it: %r" % (message,))

    # ---- a required key, a field, a count and a flag ----------------------

    for key in ("id", "agent", "prompt"):
        bag = subtask()
        del bag[key]
        message = _refuses(s.OrchestrationError,
                           "a subtask that spells no %r" % (key,),
                           lambda bag=bag: s.parse_subtask(bag))
        assert "'%s'" % key in message, (
            "the refusal of a subtask that spells no %r does not name the key: "
            "%r" % (key, message))
    for bad in (5, None, ""):
        message = _refuses(s.OrchestrationError, "a subtask id of %r" % (bad,),
                           lambda bad=bad: s.parse_subtask(subtask(id=bad)))
        assert "id" in message, (
            "the refusal of the id %r does not name the field: %r"
            % (bad, message))
    message = _refuses(s.OrchestrationError, "a blank agent",
                       lambda: s.parse_subtask(subtask(agent="   ")))
    assert "agent" in message, (
        "the refusal of a blank agent does not name the field: %r" % (message,))
    message = _refuses(s.OrchestrationError, "a blank prompt",
                       lambda: s.parse_subtask(subtask(prompt="")))
    assert "prompt" in message, (
        "the refusal of a blank prompt does not name the field: %r" % (message,))
    for bad in (True, False, "1", None, (1,)):
        message = _refuses(s.OrchestrationError, "a ticks of %r" % (bad,),
                           lambda bad=bad: s.parse_subtask(subtask(ticks=bad)))
        assert "ticks" in message, (
            "the refusal of ticks=%r does not name the count: %r — `True` is a "
            "flag that passes `isinstance(True, int)` and is not a cost"
            % (bad, message))
    message = _refuses(s.OrchestrationError, "a negative ticks",
                       lambda: s.parse_subtask(subtask(ticks=-1)))
    assert "ticks" in message and "-1" in message, (
        "the refusal of ticks=-1 does not name the field and the value: %r"
        % (message,))
    for bad in (True, "8", None):
        message = _refuses(s.OrchestrationError, "a tokens of %r" % (bad,),
                           lambda bad=bad: s.parse_subtask(subtask(tokens=bad)))
        assert "tokens" in message, (
            "the refusal of tokens=%r does not name the count: %r"
            % (bad, message))
    for bad in (0, 1, "yes", None):
        message = _refuses(s.OrchestrationError, "an effect of %r" % (bad,),
                           lambda bad=bad: s.parse_subtask(subtask(effect=bad)))
        assert "effect" in message, (
            "the refusal of effect=%r does not name the flag: %r — `effect` is a "
            "bool, and 0 and 1 are numbers" % (bad, message))
    message = _refuses(s.OrchestrationError, "a depends that is a string",
                       lambda: s.parse_subtask(subtask(depends="plan")))
    assert "depends" in message, (
        "the refusal of depends='plan' does not name the field: %r — a string is "
        "not a sequence of ids, and walking it makes 'p', 'l', 'a', 'n' four "
        "dependencies" % (message,))
    message = _refuses(s.OrchestrationError, "a depends with a non-id in it",
                       lambda: s.parse_subtask(subtask(depends=("plan", 7))))
    assert "depends" in message and "7" in message, (
        "the refusal of depends=('plan', 7) does not name the field and the "
        "value: %r" % (message,))
    message = _refuses(s.OrchestrationError, "a blank dependency id",
                       lambda: s.parse_subtask(subtask(depends=("  ",))))
    assert "depends" in message, (
        "the refusal of a blank dependency id does not name the field: %r"
        % (message,))

    # ---- a node that waits for itself, at both entry points ---------------

    for raw in ({"id": "render", "agent": "worker", "prompt": "render",
                 "depends": ("render",)},
                {"id": "render", "agent": "worker",
                 "prompt": "render the pages", "depends": ("render",)}):
        message = _refuses(s.OrchestrationError, "a subtask that depends on itself",
                           lambda raw=raw: s.parse_subtask(raw))
        assert "'render'" in message, (
            "the refusal of a subtask that waits for itself does not name the "
            "id: %r" % (message,))
    message = _refuses(
        s.OrchestrationError, "a graph node that depends on itself",
        lambda: s.parse_graph({"render": {"agent": "worker", "prompt": "render",
                                          "depends": ("render",)}}))
    assert "'render'" in message, (
        "the refusal of a self-dependency inside a graph does not name the id: "
        "%r" % (message,))

    # ---- a subtask that is not a mapping ---------------------------------

    for bad in ("render", ["render"], 7, None,
                s.Subtask(id="render", agent="worker", prompt="run it",
                          depends=(), ticks=1, tokens=8, effect=False)):
        message = _refuses(s.OrchestrationError, "a subtask that is %r" % (bad,),
                           lambda bad=bad: s.parse_subtask(bad))
        assert "mapping" in message, (
            "the refusal of %r does not say a subtask is a mapping: %r"
            % (bad, message))

    # ---- a graph that is not a graph -------------------------------------

    message = _refuses(s.OrchestrationError,
                       "a graph that is neither a mapping nor a sequence",
                       lambda: s.parse_graph("render"))
    assert "mapping" in message, (
        "the refusal of a graph given as a string does not say what a graph is: "
        "%r" % (message,))
    message = _refuses(s.OrchestrationError, "a graph key that is not a string",
                       lambda: s.parse_graph({7: {"agent": "worker",
                                                  "prompt": "run 7"}}))
    assert "key" in message and "7" in message, (
        "the refusal of the graph key 7 does not name it as a key: %r"
        % (message,))
    message = _refuses(s.OrchestrationError, "a node whose body is not a mapping",
                       lambda: s.parse_graph({"render": "render the pages"}))
    assert "'render'" in message and "mapping" in message, (
        "the refusal of a node whose body is a string does not name the node and "
        "the mapping it wanted: %r" % (message,))
    message = _refuses(s.OrchestrationError, "a node whose body spells other id",
                       lambda: s.parse_graph({"renders": subtask(id="render")}))
    assert "'renders'" in message and "'render'" in message, (
        "the refusal of a node whose body escapes its key does not name both: "
        "%r" % (message,))
    message = _refuses(s.OrchestrationError, "the same id in two nodes",
                       lambda: s.parse_graph([subtask(id="render"),
                                              subtask(id="render")]))
    assert "'render'" in message, (
        "the refusal of a duplicated id does not name the id: %r" % (message,))
    assert "twice" in message or "duplicate" in message, (
        "the refusal of a duplicated id does not say the id is repeated: %r"
        % (message,))
    message = _refuses(s.OrchestrationError,
                       "a dependency the graph does not have (graphs['orphan'])",
                       lambda: s.parse_graph(graphs.pick("orphan")))
    assert "'plan'" in message and "'render'" in message, (
        "the refusal of graphs['orphan'] does not name the dependency that is "
        "missing and the node that wants it: %r" % (message,))
    message = _refuses(
        s.OrchestrationError, "an unknown dependency on a later node",
        lambda: s.parse_graph({"a": {"agent": "worker", "prompt": "run a"},
                               "b": {"agent": "worker", "prompt": "run b",
                                     "depends": ("a", "gone")}}))
    assert "'gone'" in message and "'b'" in message, (
        "the refusal of an unknown dependency does not name the missing id and "
        "the node that wants it: %r" % (message,))
    message = _refuses(s.OrchestrationError,
                       "a plan written with its two offenders offender-last",
                       lambda: s.parse_graph({"z": subtask(id="zzz"),
                                              "a": subtask(id="aaa")}))
    assert "'aaa'" in message, (
        "a plan with two bad nodes named %r: the offenders are examined in "
        "sorted key order, so which one is named first is a function of the plan "
        "and not of the order somebody happened to write its keys in"
        % (message,))

    print("check_01: the vocabulary — a raw plan parses to frozen records inside "
          "a read-only, id-sorted graph; the seven keys, the plan's own order, "
          "its repeats and its values are preserved, and the defaults are this "
          "stage's documented numbers (512, not the fixture helper's 8); a plan "
          "whose key is a typo, whose required key is missing, whose id, agent, "
          "prompt, count, flag or dependency is the wrong shape, that waits for "
          "itself, that is empty, that repeats an id, that escapes its key, or "
          "that names a dependency the graph does not have is refused by "
          "OrchestrationError, naming the offender; and graphs['cycles'] parses, "
          "because the order it has none of is stage 2's refusal and not this "
          "stage's")

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "orchestration-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J2_REPO=/path/to/forja")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import graphs
    import stage_01 as s1
    import stage_02 as s

    def refused(what, call):
        return _refuses(s1.OrchestrationError, what, call)

    def subtask(**fields):
        """One hand-written raw subtask that parses unless the case says
        otherwise."""
        bag = {"id": "render", "agent": "worker", "prompt": "render the pages"}
        bag.update(fields)
        return bag

    def parsed(name):
        """One provided fixture, through stage 1's own parser."""
        return s1.parse_graph(graphs.pick(name))

    def built(raw):
        return s1.parse_graph(raw)

    def record(node_id, depends=()):
        """One frozen node, for the graphs stage 1 would not parse (a cycle, an
        edge that leaves the graph): this stage reads records, so a check of its
        refusals must be able to hand it a broken one."""
        return s1.Subtask(id=node_id, agent="worker", prompt="run %s" % (node_id,),
                          depends=tuple(depends), ticks=1, tokens=8,
                          effect=False)

    # ---- the vocabulary every later stage speaks ---------------------------

    for name in ("dependencies", "waves", "would_cycle", "validate_order"):
        assert callable(getattr(s, name, None)), (
            "this stage does not declare %r: the order a dependency forces is "
            "those four names" % (name,))

    single, chain = parsed("single"), parsed("chain")
    diamond, deep = parsed("diamond"), parsed("deep")

    # ---- dependencies: the edge set, sorted and deduplicated --------------

    assert s.dependencies(chain, "plan") == (), (
        "the chain's first node waits for %r, not for nothing"
        % (s.dependencies(chain, "plan"),))
    assert type(s.dependencies(chain, "plan")) is tuple, (
        "a node that waits for nothing was answered with %r, not with a tuple"
        % (s.dependencies(chain, "plan"),))
    assert s.dependencies(chain, "render") == ("plan",), (
        "the chain's second node waits for %r, not ('plan',)"
        % (s.dependencies(chain, "render"),))
    assert type(s.dependencies(chain, "render")) is tuple, (
        "the dependencies came back as %r, not as a tuple: a list is an edge set "
        "a later stage can edit"
        % (type(s.dependencies(chain, "render")),))

    # the plan's own order and its own repeats, kept by stage 1 and normalised
    # here — the pair of facts the two stages exist to keep apart
    written = built({"alpha": subtask(id="alpha"), "beta": subtask(id="beta"),
                     "join": subtask(id="join",
                                     depends=("beta", "alpha", "beta"))})
    assert written["join"].depends == ("beta", "alpha", "beta"), (
        "stage 1 parsed the plan's own spelling to %r: the order and the repeat "
        "a job file wrote are data, and this stage reads the record it kept"
        % (written["join"].depends,))
    assert s.dependencies(written, "join") == ("alpha", "beta"), (
        "a plan that spelled ('beta', 'alpha', 'beta') answers with the "
        "dependencies %r: the edge set is {'alpha', 'beta'} — the repeat is one "
        "edge, and the order a dependency forces does not depend on how the file "
        "was written" % (s.dependencies(written, "join"),))
    assert s.dependencies(diamond, "join") == ("index", "render"), (
        "the diamond's join waits for %r, not for its two branches sorted"
        % (s.dependencies(diamond, "join"),))
    assert s.dependencies(deep, "index") == ("render",), (
        "the deep graph's fourth node waits for %r, not ('render',): a node "
        "waits for its own dependencies and never for their ancestors"
        % (s.dependencies(deep, "index"),))

    # ---- waves: the levels, with the numbers that prove them --------------

    assert s.waves(single) == (("render",),), (
        "a one-node graph's waves are %r, not one wave holding the node that "
        "waits for nothing" % (s.waves(single),))
    assert s.waves(chain) == (("plan",), ("render",), ("index",)), (
        "the chain's waves are %r: one node per wave, the first wave the node "
        "that waits for nothing" % (s.waves(chain),))
    assert s.waves(diamond) == (("plan",), ("index", "render"), ("join",)), (
        "the diamond's waves are %r, not something else: both branches share "
        "wave two, and their join belongs to wave three — a join placed beside "
        "the branches is a fast node waiting on a slow sibling in the same wave"
        % (s.waves(diamond),))
    assert s.waves(parsed("review")) == (("render",), ("review",)), (
        "the review graph is two waves, the work node first and the reviewer "
        "second: %r" % (s.waves(parsed("review")),))
    assert s.waves(parsed("gate")) == (("ask",), ("ship",)), (
        "the gate graph is the approval node first and the effect node second: "
        "%r" % (s.waves(parsed("gate")),))
    assert s.waves(deep) == (("fetch",), ("parse",), ("render",), ("index",),
                             ("publish",)), (
        "the deep graph's five levels are %r: five single-node waves, in the "
        "order the dependencies force" % (s.waves(deep),))
    assert s.waves(parsed("wide")) == (
        ("plan",),
        ("audit", "digest", "index", "notify", "purge", "render")), (
        "the wide graph's two levels are %r: the six leaves share wave two, "
        "sorted by id, whatever order the plan wrote them in"
        % (s.waves(parsed("wide")),))
    assert type(s.waves(single)) is tuple and type(s.waves(single)[0]) is tuple, (
        "the waves came back as %r of %r, not as a tuple of tuples"
        % (type(s.waves(single)), type(s.waves(single)[0])))

    # the diamond's join is *not* in its dependencies' wave, whichever branch
    # the plan wrote first
    assert "join" not in s.waves(diamond)[1], (
        "the diamond's join sits in wave two beside the branches it waits for: "
        "a node waits for every one of its dependencies, not for the first")
    assert s.waves(diamond)[2] == ("join",), (
        "the diamond's third wave is %r, not the join alone"
        % (s.waves(diamond)[2],))

    # a node whose two dependencies are two waves apart, written both ways:
    # neither the file's order nor a sorted order is the maximum
    levels = built({
        "plan": subtask(id="plan"),
        "alpha": subtask(id="alpha", depends=("plan",)),
        "beta": subtask(id="beta", depends=("alpha",)),
        "first": subtask(id="first", depends=("alpha", "beta")),
        "second": subtask(id="second", depends=("beta", "alpha")),
    })
    assert s.waves(levels) == (("plan",), ("alpha",), ("beta",),
                               ("first", "second")), (
        "a node that waits for 'alpha' (wave two) and 'beta' (wave three) "
        "belongs to wave four, whichever of its two edges the plan spelled "
        "first: the waves are %r, and a wave is one more than the *max* of a "
        "node's dependencies' waves — a first-dependency rule lands 'second' on "
        "wave three because 'alpha' sorts before 'beta'"
        % (s.waves(levels),))

    # boundaries: the first wave is the first, and no graph grows an empty wave
    assert s.waves(chain)[0] == ("plan",), (
        "the chain's first wave is %r, not the node that waits for nothing: a "
        "wave list that starts anywhere else is off by one" % (s.waves(chain)[0],))
    assert s.waves(deep)[0] == ("fetch",), (
        "the deep graph's first wave is %r, not its source node"
        % (s.waves(deep)[0],))
    assert len(s.waves(chain)) == 3 and len(s.waves(deep)) == 5, (
        "the chain is %d waves and the deep graph is %d: the number of waves is "
        "the longest chain of dependencies and nothing else"
        % (len(s.waves(chain)), len(s.waves(deep))))
    assert s.waves(diamond) == s.waves(parsed("diamond")), (
        "two parses of the same fixture produced two different wave lists: the "
        "order is a function of the graph alone")

    # every fixture that has an order: one wave per node, no node twice, in
    # sorted order, and the gate answers `None` for each of them
    for name in graphs.ALL_GRAPH_NAMES:
        if name in ("cycles", "orphan"):
            continue
        graph = parsed(name)
        levels = s.waves(graph)
        flat = [node_id for wave in levels for node_id in wave]
        assert len(flat) == len(graph), (
            "the waves of %r hold %d ids for %d nodes: %r"
            % (name, len(flat), len(graph), levels))
        assert len(set(flat)) == len(flat), (
            "the waves of %r list %r: a diamond's branch was visited twice"
            % (name, flat))
        assert sorted(flat) == sorted(graph), (
            "the waves of %r hold %r, not the graph's own nodes: a wave list "
            "that loses or invents an id is a plan that will not finish"
            % (name, sorted(flat)))
        for wave in levels:
            assert wave, (
                "one of the waves of %r is empty: %r" % (name, levels))
            assert tuple(sorted(wave)) == wave, (
                "a wave of %r is %r: the ids inside a wave come back sorted, so "
                "that two runs print the same schedule" % (name, wave))
        assert s.validate_order(graph) is None, (
            "validate_order(%r) answered %r: the gate refuses a graph with no "
            "order and has nothing to say about one that has"
            % (name, s.validate_order(graph)))

    # ---- a cycle is named, not counted ------------------------------------

    cycles = parsed("cycles")
    assert cycles["index"].depends == ("render",), (
        "stage 1 parsed graphs['cycles'] with index waiting for %r"
        % (cycles["index"].depends,))
    message = refused("graphs['cycles'] through validate_order",
                      lambda: s.validate_order(cycles))
    assert "'index' -> 'render' -> 'index'" in message, (
        "the refusal of graphs['cycles'] is %r: the cycle's path has to be "
        "spelled out — the nodes of a cycle stay pending together forever, and a "
        "message that only says the graph has no order, or counts the waves a "
        "sweep could place, tells a reader nothing about which edge to cut"
        % (message,))
    assert "order" in message, (
        "the refusal of graphs['cycles'] does not say what is wrong with the "
        "graph: %r" % (message,))
    assert refused("graphs['cycles'] again",
                   lambda: s.validate_order(cycles)) == message, (
        "two refusals of the same graph printed two different paths: the cycle "
        "a walk reports is a function of the graph")
    message = refused("graphs['cycles'] through waves", lambda: s.waves(cycles))
    assert "'index' -> 'render' -> 'index'" in message, (
        "waves(graphs['cycles']) answered %r: a graph with no order is refused "
        "here too, and never answered with the part of the wave list that could "
        "be computed — that schedule would silently lose the nodes nobody can "
        "run" % (message,))

    # a cycle of three, a cycle of one, and a cycle the walk enters above its
    # smallest id
    three = built({"a": subtask(id="a", depends=("c",)),
                   "b": subtask(id="b", depends=("a",)),
                   "c": subtask(id="c", depends=("b",))})
    message = refused("a three-node cycle", lambda: s.validate_order(three))
    assert "'a' -> 'c' -> 'b' -> 'a'" in message, (
        "the three-node cycle was refused as %r: the path must be a cycle a "
        "reader can follow edge by edge, starting from the smallest id on it"
        % (message,))
    loop = {"solo": record("solo", ("solo",))}
    message = refused("a graph with a self-loop", lambda: s.validate_order(loop))
    assert "'solo' -> 'solo'" in message, (
        "the self-loop was refused as %r: a node that waits for itself is a "
        "cycle of length one, and the graph stage 1 would refuse is still a "
        "graph this stage's walk can be handed" % (message,))
    tail = built({"aaa": subtask(id="aaa", depends=("zzz",)),
                  "zzz": subtask(id="zzz", depends=("yyy",)),
                  "yyy": subtask(id="yyy", depends=("zzz",))})
    message = refused("a cycle entered above its smallest id",
                      lambda: s.validate_order(tail))
    assert "'yyy' -> 'zzz' -> 'yyy'" in message, (
        "the cycle {yyy, zzz} was refused as %r: the walk entered it at 'zzz', "
        "through 'aaa', and the path still begins at the cycle's smallest id — "
        "otherwise the message is a function of the plan's key order"
        % (message,))

    # two cycles in one graph: the walk takes a node's dependencies in sorted
    # order, so which one is named does not depend on how the file was written
    ordered = built({
        "aaa": subtask(id="aaa", depends=("zzz", "bbb")),
        "bbb": subtask(id="bbb", depends=("ccc",)),
        "ccc": subtask(id="ccc", depends=("bbb",)),
        "yyy": subtask(id="yyy", depends=("zzz",)),
        "zzz": subtask(id="zzz", depends=("yyy",)),
    })
    message = refused("a graph with two cycles",
                      lambda: s.validate_order(ordered))
    assert "'bbb' -> 'ccc' -> 'bbb'" in message, (
        "a graph with the cycles {bbb, ccc} and {yyy, zzz} was refused as %r: "
        "'aaa' was written depending on 'zzz' first, and the walk still takes "
        "its dependencies in sorted order, so the cycle it names — 'bbb' -> "
        "'ccc' — is a function of the graph and not of the file" % (message,))

    # ---- would_cycle: a question about the edit, not about the graph ------

    assert s.would_cycle(diamond, "plan", ("join",)) is True, (
        "making the diamond's 'plan' wait for 'join' was reported as no cycle: "
        "'plan' would then reach itself through 'join', 'index' and 'render'")
    assert s.would_cycle(diamond, "join", ("plan", "render")) is False, (
        "the diamond's join waiting for 'plan' and 'render' was reported as a "
        "cycle: that is the edit that keeps the graph runnable")
    assert s.would_cycle(diamond, "plan", ()) is False, (
        "an edit that removes every edge of 'plan' was reported as a cycle")
    assert s.would_cycle(diamond, "plan", ("plan",)) is True, (
        "an edit that makes 'plan' wait for itself was reported as no cycle: a "
        "self-dependency is a cycle of length one, and this stage is asked about "
        "edits a caller has not parsed yet")
    assert s.would_cycle(diamond, "render", ("index",)) is False, (
        "the diamond's two branches were reported as linked by making 'render' "
        "wait for 'index': siblings are not ancestors")
    assert s.would_cycle(chain, "plan", ("index",)) is True, (
        "making the chain's first node wait for its last was reported as no "
        "cycle: the walk is over the graph's own edges, not over a pair")
    assert s.would_cycle(chain, "index", ("render",)) is False, (
        "the chain's last node waiting for what it already waits for was "
        "reported as a cycle")
    assert s.would_cycle(chain, "index", ("plan",)) is False, (
        "the chain's last node waiting for 'plan' — a node with no dependencies "
        "of its own — was reported as a cycle")
    assert s.would_cycle(deep, "fetch", ("publish",)) is True, (
        "making the deep graph's source wait for its sink was reported as no "
        "cycle: it reaches itself through four edges")
    assert s.would_cycle(parsed("cycles"), "render", ("index",)) is True, (
        "graphs['cycles']'s own edit was reported as no cycle: this test may be "
        "asked about a graph whose order is already gone")
    assert s.would_cycle(parsed("cycles"), "render", ()) is False, (
        "cutting graphs['cycles']'s one edge was reported as a cycle: the edit "
        "is what is being tested, and that edit leaves an order")

    # the plausible wrong rule: "would the *graph* have a cycle?" — this graph
    # already has two, and the edit concerns a node in neither
    two_cycles = built({
        "a1": subtask(id="a1", depends=("a2",)),
        "a2": subtask(id="a2", depends=("a1",)),
        "b1": subtask(id="b1", depends=("b2",)),
        "b2": subtask(id="b2", depends=("b1",)),
        "c": subtask(id="c"),
    })
    assert s.would_cycle(two_cycles, "c", ("a1",)) is False, (
        "'c' waiting for 'a1' was reported as a cycle: 'a1' reaches 'a2' and "
        "stops — the graph already has two cycles, and the question is about the "
        "node being edited and not about the graph")
    assert s.would_cycle(two_cycles, "a1", ("c",)) is False, (
        "'a1' waiting for 'c' was reported as a cycle: 'c' waits for nothing")
    assert s.would_cycle(two_cycles, "a1", ("a2",)) is True, (
        "the one edit that *is* a cycle in this graph was reported as no cycle: "
        "'a2' waits for 'a1'")

    before = s.waves(diamond)
    assert s.would_cycle(diamond, "plan", ("join",)) is True
    assert diamond["plan"].depends == () and s.waves(diamond) == before, (
        "asking whether an edit would cycle changed the graph: the test is a "
        "question, and a caller that wanted it applied parses the edited plan")

    # ---- the refusals: the class, and the offender named ------------------

    message = refused("dependencies of a node the graph does not have",
                      lambda: s.dependencies(chain, "ghost"))
    assert "'ghost'" in message, (
        "the refusal of an unknown node does not name it: %r" % (message,))
    message = refused("dependencies of a node id that is not a string",
                      lambda: s.dependencies(chain, 7))
    assert "7" in message, (
        "the refusal of the node id 7 does not name it: %r" % (message,))

    for bad in ("render", [("render", None)], 7):
        message = refused("a graph that is %r" % (bad,),
                          lambda bad=bad: s.waves(bad))
        assert "mapping" in message, (
            "the refusal of %r does not say a graph is a mapping of id to "
            "Subtask: %r" % (bad, message))
    message = refused("a raw plan handed to waves",
                      lambda: s.waves(graphs.pick("chain")))
    assert "Subtask" in message and "'index'" in message, (
        "a raw plan was ordered as if stage 1 had parsed it: the refusal is %r, "
        "and it must name the node whose value is not a record" % (message,))
    message = refused("a graph key that is not a string",
                      lambda: s.waves({7: single["render"]}))
    assert "key" in message and "7" in message, (
        "the refusal of the graph key 7 does not name it as a key: %r"
        % (message,))

    for call in (lambda: s.waves({}), lambda: s.validate_order({}),
                 lambda: s.dependencies({}, "a"),
                 lambda: s.would_cycle({}, "a", ())):
        message = refused("the empty graph", call)
        assert "empty" in message, (
            "the refusal of an empty graph does not say the graph is empty: %r"
            % (message,))

    dangling = dict(chain)
    dangling["render"] = record("render", ("gone",))
    for call in (lambda: s.waves(dangling),
                 lambda: s.validate_order(dangling),
                 lambda: s.would_cycle(dangling, "plan", ())):
        message = refused("a dependency the graph does not have", call)
        assert "'gone'" in message and "'render'" in message, (
            "the refusal of a dangling edge does not name both the missing id "
            "and the node that wants it: %r" % (message,))
        assert "depends on" in message, (
            "the refusal of a dangling edge does not say which node depends on "
            "it: %r" % (message,))

    message = refused("would_cycle for a node the graph does not have",
                      lambda: s.would_cycle(diamond, "ghost", ("plan",)))
    assert "'ghost'" in message, (
        "the refusal of the unknown node 'ghost' does not name it: %r"
        % (message,))
    message = refused("an edit that names a dependency the graph does not have",
                      lambda: s.would_cycle(diamond, "plan", ("ghost",)))
    assert "'ghost'" in message and "'plan'" in message and "edit" in message, (
        "the refusal of an edit naming 'ghost' does not name the missing id and "
        "the node it was meant for: %r" % (message,))
    message = refused("a depends argument that is a string",
                      lambda: s.would_cycle(diamond, "plan", "join"))
    assert "sequence" in message, (
        "a string was walked as a sequence of ids: the refusal is %r, and it "
        "must say what a dependency list is — walked as a string, 'join' is "
        "'j', 'o', 'i', 'n'" % (message,))
    message = refused("a depends argument holding a non-id",
                      lambda: s.would_cycle(diamond, "plan", (7,)))
    assert "str id" in message and "7" in message, (
        "the refusal of depends=(7,) does not name the entry and what it should "
        "be: %r" % (message,))
    message = refused("a depends argument that is not a sequence",
                      lambda: s.would_cycle(diamond, "plan", 7))
    assert "sequence" in message, (
        "the refusal of depends=7 does not say a dependency list is a sequence "
        "of ids: %r" % (message,))

    print("check_02: the order a dependency forces — `dependencies` answers with "
          "the edge set (sorted, deduplicated, a tuple) and not the plan's own "
          "spelling; `waves` is a tuple of sorted waves whose first wave waits "
          "for nothing, in which a diamond's two branches share a level and "
          "their join takes the next, and in which a node's level is one more "
          "than the *max* of its dependencies' and not one more than its first; "
          "`validate_order` gates the acyclic fixtures and refuses "
          "graphs['cycles'] with the path 'index' -> 'render' -> 'index' spelled "
          "out, because a cycle is named by walking its edges and never detected "
          "by counting waves; and `would_cycle` answers about the node an edit "
          "concerns — a cycle elsewhere in the graph, a sibling, and an edit "
          "that removes edges all read as handled — while every refusal names "
          "the id, the pair or the key at fault")

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "orchestration-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J2_REPO=/path/to/forja")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _wave_rule(graph, states):
        """The plausible wrong answer, spelled out so this check can show it is
        wrong: the pending nodes of the lowest wave that is not entirely `ok`.

        This is what "filter the states table by wave index" means in code. It is a
        private oracle of the check and not a stage: stage 2 owns the graph's order,
        and this function is only ever handed the two acyclic fixtures the check
        contrasts.
        """
        levels = {}

        def level(node_id):
            if node_id not in levels:
                below = [level(dependency) for dependency in graph[node_id].depends]
                levels[node_id] = 1 + max(below) if below else 1
            return levels[node_id]

        table = dict(states)
        waiting = [level(node_id) for node_id in graph
                   if table.get(node_id, "pending") != "ok"]
        if not waiting:
            return ()
        turn = min(waiting)
        return tuple(sorted(node_id for node_id in graph
                            if level(node_id) == turn
                            and table.get(node_id, "pending") == "pending"))

    import graphs
    import stage_01 as s
    import stage_03 as t

    # ---- the surface: two functions, and two keyword-only counts ----------

    for name in ("runnable", "dispatchable"):
        assert callable(getattr(t, name, None)), (
            "stage_03 has no %s(): this stage is the two questions a dispatcher "
            "asks, `runnable` and `dispatchable`" % (name,))

    single = s.parse_graph(graphs.pick("single"))
    for args, kwargs, what in (
            ((single, {}, 0, 2), {}, "dispatchable(graph, states, 0, 2)"),
            ((single, {}, 0), {"limit": 2},
             "dispatchable(graph, states, 0, limit=2)")):
        try:
            t.dispatchable(*args, **kwargs)
        except TypeError:
            pass
        else:
            raise AssertionError(
                "%s was accepted: `running` and `limit` are keyword-only, "
                "because a bare pair of numbers tells the reader which of them "
                "is the cap only if they wrote the call" % (what,))
    try:
        t.dispatchable(single, {}, running=0)
    except TypeError:
        pass
    else:
        raise AssertionError(
            "dispatchable() ran without `limit`: a cap that is not a number is "
            "not the same as no cap at all")

    # ---- the mechanism, on a diamond with one slow branch -----------------
    #
    # graphs["diamond"] is plan -> {render, index} -> join. `pick` cuts `render`
    # to one tick (the branch that lands first), stretches `index` to five (the
    # branch that does not), and drops `join`'s edge to `index`, so the join
    # hangs off the fast branch alone. With that edge in place the join's
    # dependency set is the whole of its previous wave, and the wave rule and
    # this stage's rule would agree for the wrong reason.

    graph = s.parse_graph(graphs.pick("diamond", render={"ticks": 1},
                                      index={"ticks": 5},
                                      join={"depends": ("render",)}))
    assert tuple(graph) == ("index", "join", "plan", "render"), (
        "the fixture parsed to %r, not the diamond's four nodes sorted"
        % (tuple(graph),))
    assert graph["join"].depends == ("render",), (
        "the fixture's join waits for %r: the check cut it to the fast branch, "
        "and a join that still waits for both branches cannot tell the wave rule "
        "from this stage's" % (graph["join"].depends,))
    assert (graph["render"].ticks, graph["index"].ticks) == (1, 5), (
        "the fixture's branches cost %r and %r ticks, not 1 and 5: one branch "
        "has to land while the other is still running"
        % (graph["render"].ticks, graph["index"].ticks))

    assert t.runnable(graph, {}) == ("plan",), (
        "with nothing run, %r is runnable: only the root has every dependency "
        "ok (none), and an empty table is a run that has done nothing"
        % (t.runnable(graph, {}),))
    assert t.runnable(graph, {"plan": "ok"}) == ("index", "render"), (
        "with the plan ok, %r is runnable, not both branches in id order: a "
        "diamond's two branches are ready together"
        % (t.runnable(graph, {"plan": "ok"}),))

    in_flight = {"plan": "ok", "render": "ok", "index": "running"}
    assert t.runnable(graph, in_flight) == ("join",), (
        "with render ok and index still running, %r is runnable, not (): the "
        "join waits for the branch it depends on and for nothing else — the "
        "wave is not the schedule"
        % (t.runnable(graph, in_flight),))
    assert t.dispatchable(graph, in_flight, running=1, limit=3) == ("join",), (
        "with one node in flight under a cap of three, a free slot was left "
        "unused while the join was ready: %r"
        % (t.dispatchable(graph, in_flight, running=1, limit=3),))
    assert _wave_rule(graph, in_flight) == (), (
        "the wave rule answered %r where this stage answers ('join',): the check "
        "is written around the wrong answer differing here"
        % (_wave_rule(graph, in_flight),))
    assert graph["index"].ticks - graph["render"].ticks == 4, (
        "the two branches are %d ticks apart, not four: the wave rule costs the "
        "run exactly that"
        % (graph["index"].ticks - graph["render"].ticks,))

    # the slow branch lands: the same answer, arrived at four ticks late
    assert t.runnable(graph, {"plan": "ok", "render": "ok", "index": "ok"}) == ("join",), (
        "with both branches ok the join is %r"
        % (t.runnable(graph, {"plan": "ok", "render": "ok", "index": "ok"}),))

    # ---- the wrong answer survives a chain, and that is why it tempts -----

    chain = s.parse_graph(graphs.pick("chain"))
    for states, want in (({}, ("plan",)),
                         ({"plan": "ok"}, ("render",)),
                         ({"plan": "ok", "render": "running"}, ()),
                         ({"plan": "ok", "render": "ok"}, ("index",)),
                         ({"plan": "ok", "render": "running", "index": "pending"},
                          ())):
        got = t.runnable(chain, states)
        assert got == want, (
            "graphs['chain'] with the states %r answered %r, not %r"
            % (states, got, want))
        assert got == _wave_rule(chain, states), (
            "on graphs['chain'] this stage answers %r where the wave rule "
            "answers %r: a chain is the one shape where the wave rule survives, "
            "and a check that only walks a chain proves nothing"
            % (got, _wave_rule(chain, states)))

    # ---- the whole diamond: a branch back is not enough -------------------

    whole = s.parse_graph(graphs.pick("diamond"))
    assert t.runnable(whole, {"plan": "ok"}) == ("index", "render"), (
        "the whole diamond's branches are %r, not both"
        % (t.runnable(whole, {"plan": "ok"}),))
    assert t.runnable(whole, {"plan": "ok", "render": "ok"}) == ("index",), (
        "with render back and index not started, %r is runnable: the join waits "
        "for index too"
        % (t.runnable(whole, {"plan": "ok", "render": "ok"}),))
    assert t.runnable(whole, {"plan": "ok", "render": "ok", "index": "ok"}) == ("join",), (
        "with both branches back the join is the only node left to start")
    for cap in (1, 2, 9):
        assert t.dispatchable(whole, {"plan": "ok", "render": "ok"},
                              running=0, limit=cap) == ("index",), (
            "with render ok and index pending, a cap of %d handed out %r, not "
            "('index',): a node is never dispatched whose own dependency is not "
            "ok — the join is not ready while index is pending"
            % (cap, t.dispatchable(whole, {"plan": "ok", "render": "ok"},
                                   running=0, limit=cap)))
    assert t.dispatchable(whole, {"plan": "ok", "render": "ok",
                                  "index": "running"},
                          running=0, limit=9) == (), (
        "the join was dispatched while one of its dependencies was still "
        "running: %r"
        % (t.dispatchable(whole, {"plan": "ok", "render": "ok",
                                  "index": "running"}, running=0, limit=9),))

    # ---- only `ok` is done, for the dependency and for the node -----------

    review = s.parse_graph(graphs.pick("review"))
    assert t.runnable(review, {}) == ("render",), (
        "graphs['review'] with an empty table answered %r"
        % (t.runnable(review, {}),))
    for status in ("pending", "running", "awaiting", "failed", "skipped"):
        got = t.runnable(review, {"render": status})
        assert "review" not in got, (
            "'review' became runnable while its dependency 'render' was %r: "
            "`ok` is the only status that lets a dependent start, so a node "
            "merely dispatched (`running`), waiting on a person (`awaiting`) or "
            "gone (`failed`, `skipped`) locks its children as hard as an "
            "unstarted one — the `failed` case especially, because a failed "
            "node's child is a node that must not run" % (status,))
    assert t.runnable(review, {"render": "ok"}) == ("review",), (
        "with its dependency ok, graphs['review'] answered %r"
        % (t.runnable(review, {"render": "ok"}),))
    for status in ("running", "awaiting", "ok", "failed", "skipped"):
        got = t.runnable(review, {"render": "ok", "review": status})
        assert got == (), (
            "a node in state %r came back as runnable (%r): only `pending` may "
            "start, and `running` above all — a scheduler that hands out a node "
            "it already dispatched runs the same work twice" % (status, got))
    assert (t.runnable(review, {"render": "ok"})
            == t.runnable(review, {"render": "ok", "review": "pending"})
            == ("review",)), (
        "a table that leaves a node out is not the same table as one that says "
        "`pending`: %r and %r — a run spells what has happened, and everything "
        "else is pending"
        % (t.runnable(review, {"render": "ok"}),
           t.runnable(review, {"render": "ok", "review": "pending"})))

    # ---- boundaries: nothing to do, one slot, a saturated scheduler -------

    finished = {"plan": "ok", "render": "ok", "index": "ok"}
    assert t.runnable(chain, finished) == (), (
        "a finished chain still offers %r" % (t.runnable(chain, finished),))
    assert t.dispatchable(chain, finished, running=0, limit=3) == (), (
        "a finished chain dispatched something: %r"
        % (t.dispatchable(chain, finished, running=0, limit=3),))
    assert t.dispatchable(single, {}, running=0, limit=1) == ("render",), (
        "one node, one free slot, answered %r"
        % (t.dispatchable(single, {}, running=0, limit=1),))
    assert t.dispatchable(review, {"render": "ok"}, running=1, limit=1) == (), (
        "a full scheduler (`running == limit`) is the one call that answers with "
        "nothing while a node is ready: it answered %r"
        % (t.dispatchable(review, {"render": "ok"}, running=1, limit=1),))
    assert t.dispatchable(review, {"render": "ok"}, running=0, limit=3) == ("review",), (
        "a cap wider than the ready set hands out the ready set, not filler: %r"
        % (t.dispatchable(review, {"render": "ok"}, running=0, limit=3),))

    # ---- the cap: exactly `limit - running`, and a sorted prefix ----------

    wide = s.parse_graph(graphs.pick("wide"))
    wide_states = {"plan": "ok"}
    ready = t.runnable(wide, wide_states)
    assert ready == ("audit", "digest", "index", "notify", "purge", "render"), (
        "graphs['wide'] with its plan ok is runnable as %r, not its six leaves "
        "in id order" % (ready,))
    assert t.dispatchable(wide, wide_states, running=0, limit=2) == ("audit", "digest"), (
        "two free slots got %r, not the first two runnable ids in id order — and "
        "not the last two, and not the two the plan happens to name first"
        % (t.dispatchable(wide, wide_states, running=0, limit=2),))
    assert t.dispatchable(wide, wide_states, running=4, limit=6) == ("audit", "digest"), (
        "with four of six slots taken, two free slots got %r: `running` spends "
        "the cap, and the ids come from the front of the sorted set"
        % (t.dispatchable(wide, wide_states, running=4, limit=6),))
    for limit in (1, 2, 3, 5, 6, 7):
        for running in range(limit + 1):
            got = t.dispatchable(wide, wide_states, running=running, limit=limit)
            assert isinstance(got, tuple), (
                "dispatchable() answered with %r, not a tuple: the set of ids "
                "handed out is a value" % (type(got),))
            assert len(got) == min(limit - running, len(ready)), (
                "%d ids were handed out with %d running under a cap of %d: a "
                "call owes the run at most `limit - running`, and no fewer while "
                "nodes are ready" % (len(got), running, limit))
            assert got == ready[:limit - running], (
                "the ids handed out are %r, not the first %d of %r: the schedule "
                "is a prefix of the sorted runnable set"
                % (got, limit - running, ready))
            assert set(got) <= set(ready), (
                "%r is not a subset of the runnable set %r" % (got, ready))

    # ---- the effect gate is stage 7's, not this stage's -------------------

    gate = s.parse_graph(graphs.pick("gate"))
    assert gate["ship"].effect is True, (
        "graphs['gate']'s 'ship' is not an effect node: %r" % (gate["ship"],))
    assert t.runnable(gate, {"ask": "ok"}) == ("ship",), (
        "an `effect` node whose dependencies are ok answered %r: whether the "
        "world may change is stage 7's gate, and a scheduler that refuses effect "
        "nodes here stalls a plan whose approver has already said yes"
        % (t.runnable(gate, {"ask": "ok"}),))
    assert t.dispatchable(gate, {"ask": "ok"}, running=0, limit=1) == ("ship",), (
        "the effect node was not dispatchable even though its dependencies are "
        "ok: %r" % (t.dispatchable(gate, {"ask": "ok"}, running=0, limit=1),))
    assert t.runnable(gate, {}) == ("ask",), (
        "graphs['gate'] with an empty table answered %r, not ('ask',)"
        % (t.runnable(gate, {}),))

    # ---- a topological order is not needed to answer this question --------

    cyclic = s.parse_graph(graphs.pick("cycles"))
    assert t.runnable(cyclic, {}) == (), (
        "graphs['cycles'] answered %r: this stage's question is local — no node "
        "of a cycle has all its dependencies ok — and a scheduler that reaches "
        "for a topological order is doing stage 2's job twice and refusing a "
        "plan that is stage 2's to refuse" % (t.runnable(cyclic, {}),))
    assert t.dispatchable(cyclic, {}, running=0, limit=4) == (), (
        "graphs['cycles'] dispatched something: %r"
        % (t.dispatchable(cyclic, {}, running=0, limit=4),))

    # ---- two runs of the same table are one run ---------------------------

    written_one_way = {"plan": "ok", "render": "ok", "index": "running"}
    written_another = {"index": "running", "plan": "ok", "render": "ok"}
    before = dict(written_one_way)
    assert (t.runnable(graph, written_one_way)
            == t.runnable(graph, written_another) == ("join",)), (
        "the answer changed with the order the states table was written in "
        "(%r and %r): the schedule cannot depend on how a dict was built"
        % (t.runnable(graph, written_one_way),
           t.runnable(graph, written_another)))
    t.runnable(graph, written_one_way)
    t.dispatchable(graph, written_one_way, running=1, limit=3)
    assert written_one_way == before, (
        "the states table came back edited (%r, was %r): the caller's record of "
        "the run is not this stage's to write"
        % (written_one_way, before))
    # a graph handed over in another key order is the same graph: stage 1 sorts
    # the ids it parses, and this stage sorts the ones it is handed
    shuffled = {node_id: graph[node_id]
                for node_id in ("join", "plan", "render", "index")}
    assert tuple(shuffled) == ("join", "plan", "render", "index"), (
        "the check's own reshuffle did not take: %r" % (tuple(shuffled),))
    assert t.runnable(shuffled, {"plan": "ok"}) == ("index", "render"), (
        "a graph keyed in another order answered %r, not ('index', 'render'): "
        "the answer is a sorted set, and the order a mapping was built in is "
        "not a fact about the plan" % (t.runnable(shuffled, {"plan": "ok"}),))
    plan = graphs.pick("diamond")
    keep = {node_id: dict(body) for node_id, body in plan.items()}
    parsed = s.parse_graph(plan)
    t.runnable(parsed, {})
    t.dispatchable(parsed, {}, running=0, limit=2)
    assert plan == keep, (
        "the raw plan was edited by a question that only reads it: %r" % (plan,))

    # ---- every refusal names the offender --------------------------------

    message = _refuses(s.OrchestrationError, "a graph that is a list",
                       lambda: t.runnable([], {}))
    assert "a graph" in message and "list" in message, (
        "the refusal of a graph that is a list does not say what it got: %r"
        % (message,))
    message = _refuses(s.OrchestrationError, "a graph of raw plans",
                       lambda: t.runnable(dict(graphs.pick("single")), {}))
    assert "'render'" in message and "subtask" in message, (
        "the refusal of a graph whose values are raw plans does not name the "
        "node and say what a node is: %r" % (message,))
    mixed = dict(single)
    mixed[7] = single["render"]
    message = _refuses(s.OrchestrationError, "a graph keyed by 7",
                       lambda: t.runnable(mixed, {}))
    assert "7" in message and "string" in message, (
        "the refusal of a graph whose key is 7 does not name the key and say an "
        "id is a string: %r" % (message,))
    message = _refuses(s.OrchestrationError, "a states table that is a string",
                       lambda: t.runnable(single, "done"))
    assert "states" in message and "str" in message, (
        "the refusal of a states table that is a string does not say what it "
        "got: %r" % (message,))
    message = _refuses(s.OrchestrationError,
                       "a states table naming a node the graph does not have",
                       lambda: t.runnable(single, {"regner": "ok"}))
    assert "'regner'" in message and "not a node" in message, (
        "the refusal of a states table naming 'regner' does not name it and say "
        "the graph has no such node: %r" % (message,))
    message = _refuses(s.OrchestrationError, "a states table keyed by 7",
                       lambda: t.runnable(single, {7: "ok"}))
    assert "7" in message and "string" in message, (
        "the refusal of a states table keyed by 7 does not name the key: %r"
        % (message,))
    message = _refuses(s.OrchestrationError, "a status that is a typo for ok",
                       lambda: t.runnable(single, {"render": "done"}))
    assert "'done'" in message and "'render'" in message and "'ok'" in message, (
        "the refusal of the status 'done' does not name the node, the status and "
        "the statuses there are: %r" % (message,))
    message = _refuses(s.OrchestrationError, "a status that is a number",
                       lambda: t.runnable(single, {"render": 1}))
    assert "1" in message and "'render'" in message, (
        "the refusal of the status 1 does not name the node and the status: %r"
        % (message,))

    for count, call in (
            ("running=True",
             lambda: t.dispatchable(single, {}, running=True, limit=2)),
            ("running=-1",
             lambda: t.dispatchable(single, {}, running=-1, limit=2)),
            ("running='2'",
             lambda: t.dispatchable(single, {}, running="2", limit=4)),
            ("limit=None",
             lambda: t.dispatchable(single, {}, running=0, limit=None)),
            ("limit=True",
             lambda: t.dispatchable(single, {}, running=0, limit=True)),
            ("limit=0",
             lambda: t.dispatchable(single, {}, running=0, limit=0)),
            ("limit=-2",
             lambda: t.dispatchable(single, {}, running=0, limit=-2))):
        message = _refuses(s.OrchestrationError, count, call)
        named = count.split("=")[0]
        assert named in message, (
            "the refusal of %s does not name %s: %r" % (count, named, message))
        shown = count.split("=", 1)[1]
        assert shown in message, (
            "the refusal of %s does not print the offending value %s: %r"
            % (count, shown, message))
    message = _refuses(s.OrchestrationError, "more running than the cap allows",
                       lambda: t.dispatchable(wide, wide_states, running=4,
                                              limit=2))
    assert "4" in message and "2" in message and "limit" in message, (
        "the refusal of `running=4` under `limit=2` does not name both numbers: "
        "%r" % (message,))

    print("check_03: the wave is not the schedule — `runnable` is the pending "
          "nodes whose own dependencies are `ok`, on a diamond whose fast branch "
          "lands four ticks before its slow one, where the join starts while its "
          "sibling is still running and the wave rule (shown here) answers "
          "nothing; a missing state is `pending` and only `ok` is done; "
          "`dispatchable` hands out the first `limit - running` ids in id order "
          "and never a node whose dependency is not `ok`; tables and counts that "
          "do not name what they mean are refused by OrchestrationError")

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "orchestration-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J2_REPO=/path/to/forja")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import graphs
    import stage_01 as first
    import stage_04 as s

    def answered(text):
        """One accepted result as a state record: the status, and the text the
        node answered. This is the shape a run keeps for a node it accepted."""
        return {"status": "ok", "text": text}

    def record(node_id, depends, tokens=8, prompt=None, effect=False):
        """One frozen node, hand-built: the only way to build a graph stage 1
        would not have parsed, and the shape a state table's ids are read off."""
        return first.Subtask(id=node_id, agent="worker",
                             prompt=prompt or ("run %s" % node_id),
                             depends=tuple(depends), ticks=1, tokens=tokens,
                             effect=effect)

    # ---- the surface, and a refusal that is still this course's -----------

    for name in ("budgeted", "handoff", "render_prompt"):
        assert callable(getattr(s, name, None)), (
            "stage 4's surface is `budgeted`, `handoff` and `render_prompt`, and "
            "`%s` is %r" % (name, getattr(s, name, None)))
    assert s.HandoffError is not first.OrchestrationError, (
        "a broken handoff refuses with stage 1's own `OrchestrationError`: a "
        "caller cannot tell a handoff it may not make from a graph it may not run")
    assert issubclass(s.HandoffError, first.OrchestrationError), (
        "`HandoffError` is not an `OrchestrationError`: every stage derives its "
        "refusal from stage 1's, so one `except` catches a broken graph and a "
        "broken handoff")
    assert issubclass(s.HandoffError, ValueError), (
        "%r is not a ValueError; the course's refusals are the errors a caller "
        "can catch" % (s.HandoffError,))

    # ---- budgeted: the cut is exact, and it is characters -----------------

    text = "0123456789abcdefg"
    assert len(text) == 17
    cut = [s.budgeted(text, n) for n in (1, 2, 3, 4, 5, 6, 7)]
    assert cut == ["0", "01", "012", "0123", "01234", "012345", "0123456"], (
        "a budget of n characters came back as %r: a token is one character, so "
        "a budget of three is three characters — not three-quarters of one, not "
        "four characters per token, and not a multiple of four" % (cut,))
    assert s.budgeted(text, 0) == "", (
        "a budget of zero came back as %r: a budget of zero is handing on "
        "nothing, and a cut is not a rounding" % (s.budgeted(text, 0),))
    assert s.budgeted(text, 16) == text[:-1], (
        "a budget of 16 came back as %r, not the first 16 characters: the cut is "
        "at the budget, not one short of it" % (s.budgeted(text, 16),))
    assert s.budgeted(text, 17) == text, (
        "a result of exactly seventeen characters under a budget of seventeen "
        "came back as %r: a result that fits goes on whole"
        % (s.budgeted(text, 17),))
    assert s.budgeted(text, 18) == text and s.budgeted(text, 4096) == text, (
        "a budget larger than the result cut it to %r: a budget is a ceiling, and "
        "a result shorter than it is not padded out to it"
        % (s.budgeted(text, 18),))
    assert s.budgeted("", 0) == "" and s.budgeted("", 5) == "", (
        "an empty result came back as %r and %r, not as an empty string"
        % (s.budgeted("", 0), s.budgeted("", 5)))
    assert isinstance(s.budgeted(text, 3), str), (
        "budgeted() returned %r, and a handoff is text"
        % (type(s.budgeted(text, 3)).__name__,))
    assert s.budgeted("héllo", 2) == "hé", (
        "a budget of two cut 'héllo' to %r: a token is a character, and 'héllo' "
        "is %d bytes — a byte count measures a different string for the same "
        "text, and cuts a character in half"
        % (s.budgeted("héllo", 2), len("héllo".encode("utf-8"))))
    assert s.budgeted("日本語", 1) == "日" and len(s.budgeted("日本語", 2)) == 2, (
        "a budget of one cut '日本語' to %r: three characters, nine bytes, and a "
        "budget that counts anything but characters is not this stage's"
        % (s.budgeted("日本語", 1),))

    # ---- the mechanism, by value: the node's own dependencies, sorted -----

    raw = graphs.pick("diamond",
                      join={"depends": ("render", "index", "render")},
                      plan={"tokens": 4}, render={"tokens": 5}, index={"tokens": 3})
    graph = first.parse_graph(raw)
    assert graph["join"].depends == ("render", "index", "render"), (
        "the fixture this check is about no longer spells the join's dependencies "
        "the way the case needs: %r" % (graph["join"].depends,))
    states = {
        "plan": answered("PLANPLANPLANPLAN"),
        "index": answered("INDEXINDEXINDEX"),
        "render": answered("RENDERRENDERRENDER"),
        "join": "pending",
    }
    carried = s.handoff(graph, states, "join")
    assert carried == "index: IND\nrender: RENDE", (
        "the join waits for `index` (worth 3) and `render` (worth 5) and is "
        "handed %r: each dependency's accepted result, cut to *that "
        "dependency's* own budget, labelled with the id it came from, one entry "
        "per dependency, sorted by id, joined by a newline — and `render` is "
        "spelled twice in the plan, which is one dependency and one result"
        % (carried,))
    assert carried.count("\n") == 1, (
        "two results were handed on as %r: two entries are separated by one "
        "newline, so a child can tell where one result ended" % (carried,))
    assert "plan" not in carried and "PLAN" not in carried, (
        "the join's handoff is %r, and `plan` is an ancestor of both of its "
        "dependencies and not one of them: a child is handed its own "
        "dependencies' results, never every ancestor's and never the whole "
        "transcript" % (carried,))
    assert isinstance(carried, str), (
        "handoff() returned %r, and a handoff is text" % (type(carried).__name__,))

    rendered = s.render_prompt(graph, states, "join")
    assert rendered == "join the two results\nindex: IND\nrender: RENDE", (
        "the join is rendered as %r: its own prompt, then its handoff, separated "
        "by a newline — the prompt first, because an agent that reads its "
        "dependencies' answers before it reads what it was asked to do has been "
        "handed a transcript" % (rendered,))
    assert rendered.startswith(graph["join"].prompt + "\n"), (
        "the rendered prompt %r does not begin with the node's own prompt %r"
        % (rendered, graph["join"].prompt))

    # ---- boundaries: no dependency, no accepted result, nothing to hand on -

    assert s.handoff(graph, states, "plan") == "", (
        "a node with no dependencies was handed %r: there is nothing to hand on"
        % (s.handoff(graph, states, "plan"),))
    assert s.render_prompt(graph, states, "plan") == "plan the release", (
        "a node with no dependencies is rendered as %r: its own prompt, exactly "
        "— no separator, no empty block, no `None`, nothing that tells the agent "
        "something is missing" % (s.render_prompt(graph, states, "plan"),))
    assert "\n" not in s.render_prompt(graph, states, "plan"), (
        "a node with no dependencies is rendered with a newline in it: %r"
        % (s.render_prompt(graph, states, "plan"),))
    for status in ("pending", "running", "awaiting", "failed", "skipped"):
        both = {"index": status, "render": status}
        handed = s.handoff(graph, both, "join")
        assert handed == "", (
            "a dependency in the state %r was handed on as %r: only an accepted "
            "result is part of the handoff — a running node has none, an "
            "awaiting one is not allowed to produce one, a failed one has none "
            "that was accepted and a skipped one never ran"
            % (status, handed))
        assert s.render_prompt(graph, both, "join") == "join the two results", (
            "the join was rendered as %r with both of its dependencies in the "
            "state %r: nothing to hand on is rendered as nothing"
            % (s.render_prompt(graph, both, "join"), status))
    assert s.handoff(graph, {"index": {"status": "running",
                                       "text": "INDEXINDEXINDEX"},
                             "render": answered("RENDERRENDERRENDER")},
                     "join") == "render: RENDE", (
        "a `running` dependency's draft was handed on: a node that has not "
        "answered has no result, whatever its record holds under `text`")
    assert s.handoff(graph, {"index": answered("INDEXINDEXINDEX")},
                     "join") == "index: IND", (
        "a node the state table does not name was counted: the table names "
        "`index` and not `render`, `render` is therefore `pending`, and a "
        "pending node has nothing to hand on")
    assert s.handoff(graph, {"index": "ok", "render": answered("R")},
                     "join") == "index: \nrender: R", (
        "a node whose state is the bare status `ok` was handed on as %r: a bare "
        "status is a node with no text, and an accepted node with no text still "
        "contributes its own entry" % (s.handoff(graph, {"index": "ok",
                                                        "render": answered("R")},
                                                "join"),))
    assert s.handoff(graph, {"index": answered(""), "render": answered("")},
                     "join") == "index: \nrender: ", (
        "two dependencies whose accepted results are empty were handed on as %r: "
        "one entry per accepted dependency, in sorted order, even when the result "
        "is empty — a child that cannot count its dependencies' answers cannot "
        "tell an empty one from a missing one"
        % (s.handoff(graph, {"index": answered(""), "render": answered("")},
                     "join"),))
    assert s.handoff(graph, dict(states, ghost=answered("GHOSTGHOST"),
                                 wibble="not a state"), "join") == carried, (
        "a state table that names a node the graph does not have — with a status "
        "that is not one of the six — changed the join's handoff: the handoff "
        "reads the node's own dependencies and no other entry of the table")

    # ---- the chain: a real fixture, and the ancestor that is not one ------

    chain = first.parse_graph(graphs.pick("chain"))
    long = {"plan": answered("P" * 40), "render": answered("R" * 40),
            "index": answered("I" * 40)}
    assert chain["render"].tokens == 32 and chain["plan"].tokens == 16, (
        "the chain's own budgets changed: `render` is worth %r and `plan` %r, "
        "and this case needs 32 and 16"
        % (chain["render"].tokens, chain["plan"].tokens))
    assert s.handoff(chain, long, "render") == "plan: " + "P" * 16, (
        "the chain's `render`, worth 32 tokens, was handed %r: its dependency "
        "`plan` declared 16, and a result is cut to the budget of the node it "
        "came from — cut to the *child's* budget it is twice the context the "
        "plan was ever worth" % (s.handoff(chain, long, "render"),))
    assert s.handoff(chain, long, "index") == "render: " + "R" * 32, (
        "the chain's last node was handed %r: it waits for `render` (worth 32) "
        "and not for `plan`, and `plan`'s forty characters must not reach it"
        % (s.handoff(chain, long, "index"),))
    assert "plan" not in s.handoff(chain, long, "index") and \
        "P" * 16 not in s.handoff(chain, long, "index"), (
        "the chain's last node was handed its dependency's dependency: %r is "
        "`plan`'s result, and `index` does not depend on `plan`"
        % (s.handoff(chain, long, "index"),))
    assert s.handoff(chain, long, "plan") == "", (
        "the chain's first node was handed %r: it waits for nothing"
        % (s.handoff(chain, long, "plan"),))
    assert s.render_prompt(chain, long, "index") == (
        "index the pages\nrender: " + "R" * 32), (
        "the chain's last node is rendered as %r: its prompt, and only its own "
        "dependency's accepted result" % (s.render_prompt(chain, long, "index"),))
    assert s.handoff(chain, long, "plan") == s.handoff(chain, long, "plan"), (
        "two handoffs of the same node and the same states differ: a handoff is a "
        "function of its inputs")

    # ---- the state table is read, never written --------------------------

    before = dict(states)
    assert s.handoff(graph, states, "join") == carried, (
        "the same graph and the same states produced %r and then %r"
        % (carried, s.handoff(graph, states, "join")))
    assert dict(states) == before, (
        "rendering a handoff edited the state table it was handed: %r, not %r"
        % (dict(states), before))

    # ---- every refusal, by class and by the text that names the offender ---

    for call, what in (
            (lambda: s.handoff(graph, states, "gone"), "handoff()"),
            (lambda: s.render_prompt(graph, states, "gone"), "render_prompt()")):
        message = _refuses(s.HandoffError,
                           "%s of a node the graph does not have" % (what,), call)
        assert "'gone'" in message and "does not have" in message, (
            "the refusal of a node the graph does not have is %r: it must name "
            "the id and say the graph does not have it" % (message,))
    message = _refuses(s.HandoffError, "a handoff of the node None",
                       lambda: s.handoff(graph, states, None))
    assert "None" in message, (
        "the refusal of the node None does not name it: %r" % (message,))
    for bad in ("join", 7, ["join"]):
        message = _refuses(s.HandoffError, "a graph that is %r" % (bad,),
                           lambda bad=bad: s.handoff(bad, states, "join"))
        assert "mapping" in message and "subtask" in message, (
            "the refusal of the graph %r is %r: a graph is a mapping of id to "
            "subtask, and the refusal must say so" % (bad, message))
    message = _refuses(s.HandoffError, "a raw plan handed to the handoff",
                       lambda: s.handoff(graphs.pick("chain"), states, "render"))
    assert "'render'" in message and "Subtask" in message, (
        "the refusal of a raw plan handed to the handoff is %r: it must name the "
        "node and the `Subtask` it wanted" % (message,))
    broken = {"join": record("join", ("render", "gone")),
              "render": record("render", ())}
    message = _refuses(s.HandoffError, "a dependency the graph does not have",
                       lambda: s.handoff(broken, {"render": answered("R")},
                                         "join"))
    assert "'gone'" in message and "'join'" in message, (
        "the refusal of a dependency the graph does not have is %r: it must name "
        "the dependency that is missing and the node that waits for it"
        % (message,))
    for bad in ("ok", 7, None, ["join"]):
        message = _refuses(s.HandoffError, "a state table that is %r" % (bad,),
                           lambda bad=bad: s.handoff(graph, bad, "join"))
        assert "mapping" in message and "state" in message, (
            "the refusal of the state table %r is %r: the states are a mapping of "
            "node id to state, and the refusal must say so" % (bad, message))
    for bad in (7, None, ["ok", "text"], ("ok", "text")):
        message = _refuses(
            s.HandoffError, "the state %r" % (bad,),
            lambda bad=bad: s.handoff(graph, {"index": bad,
                                              "render": answered("R")}, "join"))
        assert "'index'" in message and type(bad).__name__ in message, (
            "the refusal of the state %r is %r: a state is one of the six, or a "
            "record, and the refusal must name the node and what it was handed"
            % (bad, message))
    for bad in ("done", "died", "OK", "", " ok"):
        message = _refuses(
            s.HandoffError, "the status %r" % (bad,),
            lambda bad=bad: s.handoff(graph, {"index": bad,
                                              "render": answered("R")}, "join"))
        assert "'index'" in message and repr(bad) in message, (
            "the refusal of the status %r is %r: the six states are all there is, "
            "and the refusal must name the node and the status"
            % (bad, message))
        message = _refuses(
            s.HandoffError, "a record in the status %r" % (bad,),
            lambda bad=bad: s.handoff(
                graph, {"index": {"status": bad, "text": "t"},
                        "render": answered("R")}, "join"))
        assert "'index'" in message and repr(bad) in message, (
            "the refusal of a record whose status is %r is %r: it must name the "
            "node and the status" % (bad, message))
    message = _refuses(
        s.HandoffError, "a state record that spells no status",
        lambda: s.handoff(graph, {"index": {"text": "t"},
                                  "render": answered("R")}, "join"))
    assert "'index'" in message and "status" in message and "text" in message, (
        "the refusal of a record with no `status` is %r: it must name the node "
        "and the key that is missing" % (message,))
    message = _refuses(
        s.HandoffError, "a state record whose text is not a string",
        lambda: s.handoff(graph, {"index": {"status": "ok", "text": 7},
                                  "render": answered("R")}, "join"))
    assert "'index'" in message and "'text'" in message and "str" in message, (
        "the refusal of a record whose `text` is not a string is %r: it must name "
        "the node, the key and what it got" % (message,))
    assert s.handoff(graph, {"index": {"status": "failed", "text": 7},
                             "render": answered("R")}, "join") == "render: R", (
        "a state record whose status is not `ok` was read for its text: a run may "
        "keep a draft, a reason or a count of attempts under `text`, and only an "
        "accepted record has a text this stage reads")

    for bad in (float(2), "8", None, (3,), True, False):
        message = _refuses(s.HandoffError, "the budget %r" % (bad,),
                           lambda bad=bad: s.budgeted(text, bad))
        assert "int" in message and repr(bad) in message, (
            "the refusal of the budget %r is %r: a budget is an int count of "
            "tokens, `True` is a flag that passes `isinstance(True, int)`, and a "
            "float has already been rounded somewhere else"
            % (bad, message))
    message = _refuses(s.HandoffError, "a negative budget",
                       lambda: s.budgeted(text, -1))
    assert "-1" in message and ">= 0" in message, (
        "the refusal of a negative budget is %r: it must name the budget and say "
        "what a budget may be" % (message,))
    for bad in (7, None, ["a"], ("a",), b"a"):
        message = _refuses(s.HandoffError, "a result that is %r" % (bad,),
                           lambda bad=bad: s.budgeted(bad, 3))
        assert "str" in message and type(bad).__name__ in message, (
            "the refusal of a result that is %r is %r: a result to hand on is a "
            "string, and the refusal must name what it got" % (bad, message))

    print("check_04: the handoff — a token is a character and the cut is exact "
          "(never a byte count, never a rounding, never a target), a child is "
          "handed the accepted results of its own dependencies and no ancestor's, "
          "each cut to the budget that dependency declared, labelled, sorted by "
          "id and separated; a dependency that is not `ok` contributes nothing, a "
          "node with nothing to hand on is rendered as exactly its own prompt, "
          "and every refusal — a node or a dependency the graph does not have, a "
          "plan nobody parsed, a state outside the six, a budget that is not an "
          "int — is a HandoffError that names the offender")

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "orchestration-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J2_REPO=/path/to/forja")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import agents
    import graphs
    import stage_01 as s1
    import stage_05 as s

    def verdict(text, tokens=0):
        """One reviewer's answer: the text it said and what the call cost."""
        return agents.Reply(text, tokens)

    # ---- the vocabulary: one bound, and the two verdicts the model knows --

    assert type(s.MAX_REWORK) is int, (
        "MAX_REWORK is %r, not an int count: a bound is a number of reworks, not "
        "a flag" % (s.MAX_REWORK,))
    assert s.MAX_REWORK == 2, (
        "MAX_REWORK is %r, not the two reworks the course documents"
        % (s.MAX_REWORK,))
    assert agents.VERDICTS == ("accept", "reject"), (
        "the model's verdicts are %r, not the two the course documents — this "
        "stage's acceptance is one of them" % (agents.VERDICTS,))

    # ---- accepts: exactly Reply.text, and only a verdict is a verdict ----

    assert s.accepts(verdict("accept")) is True, (
        "an acceptance was not accepted: `accepts(Reply('accept'))` answered %r"
        % (s.accepts(verdict("accept")),))
    assert s.accepts(verdict("reject")) is False, (
        "a rejection was read as an acceptance: `accepts(Reply('reject'))` "
        "answered %r — the whole stage is about the reviewer that can reject"
        % (s.accepts(verdict("reject")),))
    assert s.accepts(verdict("accept", 0)) is True, (
        "an acceptance that cost nothing (tokens=0) was not accepted: the verdict "
        "is `Reply.text`, and `tokens` is the cost of the call — stage 8 spends "
        "it, no stage reads a verdict from it")
    assert s.accepts(verdict("accept", 9)) is True, (
        "an acceptance that cost nine tokens was not accepted: a verdict read "
        "from `tokens` rejects a success that happened to be expensive")
    assert s.accepts(verdict("reject", 0)) is False, (
        "a rejection that cost nothing was accepted: a verdict read from `tokens` "
        "accepts a failure that happened to be cheap — the exact defect this "
        "stage exists to prevent")
    assert s.accepts(verdict("reject", 9)) is False, (
        "a rejection that cost nine tokens was accepted: the verdict is not the "
        "cost")
    assert s.accepts(verdict("accept but only for the cover")) is False, (
        "a text that merely contains 'accept' was read as an acceptance: the "
        "verdict is exactly `Reply.text`, not a substring of it")
    assert s.accepts(verdict("accept.")) is False, (
        "the text 'accept.' was read as an acceptance: the verdict is exactly "
        "`Reply.text`, compared against `VERDICTS`, not stripped or searched")
    assert s.accepts(verdict("Accept")) is False, (
        "the text 'Accept' was read as an acceptance: the verdict is exactly the "
        "text `VERDICTS` declares")
    assert s.accepts(verdict("the render is a stub")) is False, (
        "a `refuser`'s reason was read as an acceptance: a text that is not a "
        "verdict is a rejection, and its text is the reason a rework carries")
    assert s.accepts(verdict("")) is False, (
        "an empty text was read as an acceptance: an empty answer says nothing, "
        "and 'says nothing' is not 'accepts'")
    message = _refuses(s1.OrchestrationError, "accepts('accept')",
                       lambda: s.accepts("accept"))
    assert "Reply" in message, (
        "the refusal of a reply that is not a `Reply` does not say what it "
        "wanted: %r" % (message,))
    message = _refuses(s1.OrchestrationError, "accepts(None)",
                       lambda: s.accepts(None))
    assert "Reply" in message, (
        "the refusal of a `None` reply does not say what it wanted: %r"
        % (message,))

    # ---- the fixtures every later case is built on -----------------------

    review_graph = s1.parse_graph(graphs.pick("review"))
    render = review_graph["render"]
    assert render.id == "render" and render.prompt == "render the page", (
        "the `review` fixture's work node parsed to %r, not the render node this "
        "check reasons about" % (render,))
    single = s1.parse_graph(graphs.pick("single"))["render"]

    # ---- review_prompt: the attempt is in the prompt, and the node is ----

    assert s.review_prompt(render, 1) == "review render (attempt 1): render the page", (
        "review_prompt(render, 1) is %r, not the node's id, the attempt and its "
        "prompt" % (s.review_prompt(render, 1),))
    assert s.review_prompt(render, 2) == "review render (attempt 2): render the page", (
        "review_prompt(render, 2) is %r, not the second attempt of the same node"
        % (s.review_prompt(render, 2),))
    assert s.review_prompt(render, 1) != s.review_prompt(render, 2), (
        "the reviewer's prompt is the same for attempt 1 and attempt 2 (%r): the "
        "attempt is not in it, so a rework is reviewed as a fresh node"
        % (s.review_prompt(render, 1),))
    assert s.review_prompt(render, 3) == s.review_prompt(render, 3), (
        "two calls of review_prompt for the same node and attempt differ: the "
        "prompt must be a function of its arguments")
    assert s.review_prompt(single, 1) == "review render (attempt 1): render the page", (
        "the `single` fixture's node reviewed to %r, not the review of 'render'"
        % (s.review_prompt(single, 1),))
    assert s.review_prompt(review_graph["review"], 1) == (
        "review review (attempt 1): review the render"), (
        "review_prompt of the reviewer's own node is %r, not the node's own id "
        "and prompt" % (s.review_prompt(review_graph["review"], 1),))
    for bad in (0, -1, True, "1", None):
        message = _refuses(s1.OrchestrationError,
                           "review_prompt(render, %r)" % (bad,),
                           lambda bad=bad: s.review_prompt(render, bad))
        assert "attempt" in message, (
            "the refusal of the review attempt %r does not name it: %r"
            % (bad, message))
    message = _refuses(s1.OrchestrationError, "review_prompt('render', 1)",
                       lambda: s.review_prompt("render", 1))
    assert "Subtask" in message, (
        "the refusal of a node that is not a `Subtask` does not say what it "
        "wanted: %r" % (message,))

    # ---- rework_prompt: the same node, its own prompt, and the reason ----

    reason = "the render is a stub"
    reworked = s.rework_prompt(render, reason, 2)
    assert reworked == (
        "render the page\n(rework render, attempt 2, rejected: the render is a "
        "stub)"), (
        "rework_prompt(render, %r, 2) is %r, not the node's own prompt, the same "
        "node's id, the attempt and the reviewer's reason" % (reason, reworked))
    assert reworked.startswith(render.prompt), (
        "the rework prompt %r does not begin with the node's own prompt %r: a "
        "rework is the same node, told the same thing plus the reason"
        % (reworked, render.prompt))
    assert reason in reworked, (
        "the rework prompt %r does not carry the reviewer's reason %r: a rework "
        "that re-sends the original prompt gets the original result"
        % (reworked, reason))
    assert reworked != render.prompt, (
        "the rework prompt is the original prompt: the reviewer's reason was "
        "dropped, so the node is asked to fail the same way again")
    assert "render" in reworked, (
        "the rework prompt %r does not name the node it is re-dispatching"
        % (reworked,))
    assert s.rework_prompt(render, "a", 2) != s.rework_prompt(render, "b", 2), (
        "two different reasons produced the same rework prompt: the reason is "
        "not what changes between a rejection and a rework")
    assert s.rework_prompt(render, reason, 2) != s.rework_prompt(render, reason, 3), (
        "the rework prompt is the same for attempt 2 and attempt 3: the attempt "
        "is not in it")
    padded = s.rework_prompt(render, "  the reason  ", 2)
    assert "  the reason  " in padded, (
        "the reviewer's reason lost its surrounding spaces on the way to the "
        "next attempt (%r): the reason is data, carried verbatim, not normalised"
        % (padded,))
    for bad in (0, -1, True, None):
        message = _refuses(s1.OrchestrationError,
                           "rework_prompt(render, reason, %r)" % (bad,),
                           lambda bad=bad: s.rework_prompt(render, reason, bad))
        assert "attempt" in message, (
            "the refusal of the rework attempt %r does not name it: %r"
            % (bad, message))
    for bad in ("", "   ", None, 7):
        message = _refuses(s1.OrchestrationError,
                           "rework_prompt(render, %r, 2)" % (bad,),
                           lambda bad=bad: s.rework_prompt(render, bad, 2))
        assert "reason" in message, (
            "the refusal of the rework reason %r does not name it: %r"
            % (bad, message))
    message = _refuses(s1.OrchestrationError, "rework_prompt('render', reason, 2)",
                       lambda: s.rework_prompt("render", reason, 2))
    assert "Subtask" in message, (
        "the refusal of a node that is not a `Subtask` does not say what it "
        "wanted: %r" % (message,))

    # ---- next_attempt: the three decisions, and the bound ----------------

    accept = verdict("accept")
    reject = verdict("reject")
    assert s.next_attempt("running", accept, attempts=1) == "accepted", (
        "an accepted review of a running node decided %r, not 'accepted'"
        % (s.next_attempt("running", accept, attempts=1),))
    assert s.next_attempt("running", reject, attempts=1) == "rework", (
        "a rejection decided %r, not 'rework': a rejection recorded and then "
        "ignored leaves the node ok, and the run reports success about work "
        "nobody accepted" % (s.next_attempt("running", reject, attempts=1),))
    assert s.next_attempt("running", reject, attempts=1) != "accepted", (
        "a rejection was accepted: `next_attempt('running', Reply('reject'), "
        "attempts=1)` answered 'accepted' — the node stays ok")
    assert s.next_attempt("running", verdict("the render is a stub"), attempts=1) == (
        "rework"), (
        "a `refuser`'s reason decided %r, not 'rework': any text that is not the "
        "acceptance is a rejection, and its text is the reason"
        % (s.next_attempt("running", verdict("the render is a stub"), attempts=1),))
    assert s.next_attempt("running", verdict("accept", 0), attempts=1) == "accepted", (
        "an acceptance that cost nothing decided %r: the verdict is `Reply.text`, "
        "not `Reply.tokens`" % (s.next_attempt("running", verdict("accept", 0),
                                               attempts=1),))
    assert s.next_attempt("running", verdict("reject", 9), attempts=1) == "rework", (
        "a rejection that cost nine tokens decided %r: a verdict read from "
        "`tokens` reads a cheap call as an acceptance, and this one was not cheap"
        % (s.next_attempt("running", verdict("reject", 9), attempts=1),))

    # the bound, at both sides: the last rework the node may spend, and one past
    assert s.next_attempt("running", reject, attempts=s.MAX_REWORK) == "rework", (
        "a rejection at attempt MAX_REWORK (%d) decided %r, not 'rework': the "
        "bound fails the node one rework too early"
        % (s.MAX_REWORK, s.next_attempt("running", reject, attempts=s.MAX_REWORK)))
    assert s.next_attempt("running", reject, attempts=s.MAX_REWORK + 1) == "failed", (
        "a rejection at attempt MAX_REWORK + 1 (%d) decided %r, not 'failed': the "
        "rework is unbounded, and a node that never converges is never failed"
        % (s.MAX_REWORK + 1,
           s.next_attempt("running", reject, attempts=s.MAX_REWORK + 1)))
    assert s.next_attempt("running", reject, attempts=99) == "failed", (
        "a rejection at attempt 99 decided %r, not 'failed': the bound is not a "
        "bound" % (s.next_attempt("running", reject, attempts=99),))

    # ---- the mechanism on the `review` fixture, with values --------------

    judged = agents.reviewer("reject", "accept")
    decisions = []
    attempts = 0
    state = "running"
    prompt = None
    while True:
        attempts += 1
        prompt = s.review_prompt(render, attempts)
        reply = judged(prompt, attempt=attempts)
        decision = s.next_attempt(state, reply, attempts=attempts)
        decisions.append(decision)
        if decision != "rework":
            break
        prompt = s.rework_prompt(render, reply.text, attempts + 1)
        assert reply.text in prompt, (
            "the rework prompt %r dropped the reason %r the reviewer gave"
            % (prompt, reply.text))
    assert decisions == ["rework", "accepted"], (
        "a reviewer that rejects once and accepts the rework produced the "
        "decisions %r, not ['rework', 'accepted']: the node is dispatched twice"
        % (decisions,))
    assert attempts == 2, (
        "the node was dispatched %d times for one rejection and one acceptance, "
        "not twice" % (attempts,))
    assert judged.calls == 2, (
        "the reviewer was called %d times, not twice: not once (the rejection was "
        "not acted on) and not three times (a rejection counted as a new node)"
        % (judged.calls,))

    # two reworks is exactly what MAX_REWORK documents, and the third rejection
    # is the failure
    flaky = agents.flaky_agent("accept", failures=2)
    decisions = [s.next_attempt("running",
                                flaky(s.review_prompt(render, n), attempt=n),
                                attempts=n) for n in (1, 2, 3)]
    assert decisions == ["rework", "rework", "accepted"], (
        "a node that rejects twice and then accepts produced %r, not "
        "['rework', 'rework', 'accepted']: two reworks is where MAX_REWORK (%d) "
        "lets a node go" % (decisions, s.MAX_REWORK))
    doomed = agents.flaky_agent("accept", failures=3)
    decisions = [s.next_attempt("running",
                                doomed(s.review_prompt(render, n), attempt=n),
                                attempts=n) for n in (1, 2, 3)]
    assert decisions == ["rework", "rework", "failed"], (
        "a node that is rejected three times produced %r, not ['rework', "
        "'rework', 'failed']: the third attempt is the bound, and a fourth "
        "dispatch is the unbounded loop" % (decisions,))

    # ---- the probe: a rejection never leaves the node accepted -----------

    # The plausible wrong rule is "the review is recorded and the node stays
    # ok": `next_attempt` answers 'accepted' whatever the reviewer said. A
    # rejection must decide 'rework', and a review that arrives once the node is
    # already 'ok' must be refused — from both sides the ignored rejection is
    # impossible.
    assert s.next_attempt("running", verdict("reject"), attempts=1) != "accepted", (
        "a rejection was answered with 'accepted': the node stays ok")
    assert s.next_attempt("running", verdict("reject"), attempts=2) != "accepted", (
        "a second rejection was answered with 'accepted': the node stays ok")
    assert s.next_attempt("running", verdict("reject"),
                          attempts=s.MAX_REWORK + 1) == "failed", (
        "the bound was not reached: a reviewer that always rejects never fails "
        "the node")
    for done in ("ok", "failed", "skipped", "pending", "awaiting"):
        message = _refuses(s1.OrchestrationError,
                           "a review of a node that is %r" % (done,),
                           lambda done=done: s.next_attempt(done, reject, attempts=1))
        assert repr(done) in message, (
            "the refusal of a review in state %r does not name the state: %r"
            % (done, message))
    for bad in (0, -1, True, "1", None):
        message = _refuses(s1.OrchestrationError,
                           "next_attempt(..., attempts=%r)" % (bad,),
                           lambda bad=bad: s.next_attempt("running", reject,
                                                          attempts=bad))
        assert "attempts" in message, (
            "the refusal of attempts=%r does not name the count: %r"
            % (bad, message))
    message = _refuses(s1.OrchestrationError, "next_attempt('running', 'reject')",
                       lambda: s.next_attempt("running", "reject", attempts=1))
    assert "Reply" in message, (
        "the refusal of a review of something that is not a `Reply` does not say "
        "what it wanted: %r" % (message,))

    print("check_05: the reviewer — a verdict read exactly from `Reply.text` "
          "(never `tokens`), an acceptance that lets the result through and a "
          "rejection that re-dispatches the same node with the reviewer's reason "
          "in its prompt, bounded by MAX_REWORK so that a node rejected past the "
          "bound is failed and a review of a node whose verdict is already "
          "written is refused by name")

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "orchestration-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J2_REPO=/path/to/forja")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import graphs
    import stage_01 as one
    import stage_06 as s

    assert s.OrchestrationError is one.OrchestrationError, (
        "this stage refuses with %r and the course's refusal is %r: one `except` "
        "has to catch a broken graph and a broken state mapping"
        % (s.OrchestrationError, one.OrchestrationError))

    def graph_of(name, **overrides):
        """One fixture, parsed by stage 1: the graph this stage walks is the
        validated one, and the fixture's own values are the plan's."""
        return one.parse_graph(graphs.pick(name, **overrides))

    def refuses(what, call):
        return _refuses(one.OrchestrationError, what, call)

    # ---- the mechanism, hand-computed on the deepest plan ------------------

    # `deep` is five levels: fetch -> parse -> render -> index -> publish. A
    # failure of `fetch` can be computed from by nobody.
    deep = graph_of("deep")
    assert tuple(deep) == ("fetch", "index", "parse", "publish", "render"), (
        "graphs['deep'] parsed to the ids %r, not its five nodes sorted"
        % (tuple(deep),))
    assert s.skip_set(deep, "fetch") == ("index", "parse", "publish", "render"), (
        "a failure of `fetch` takes down %r: `parse` directly, and then "
        "`render`, `index` and `publish` at the second, third and fourth level. "
        "A walk that stops at the direct dependents keeps three of those nodes, "
        "and each of them is dispatched against a dependency that failed"
        % (s.skip_set(deep, "fetch"),))

    # the same failure seen one level at a time: every node of a chain is the
    # direct dependent of the one before it, and only the last takes nothing
    # with it.
    assert s.skip_set(deep, "parse") == ("index", "publish", "render"), (
        "a failure of `parse` takes down %r, not `render` and the two below it"
        % (s.skip_set(deep, "parse"),))
    assert s.skip_set(deep, "render") == ("index", "publish"), (
        "a failure of `render` takes down %r, not `index` and `publish`"
        % (s.skip_set(deep, "render"),))
    assert s.skip_set(deep, "index") == ("publish",), (
        "a failure of `index` takes down %r, not `publish`"
        % (s.skip_set(deep, "index"),))
    assert s.skip_set(deep, "publish") == (), (
        "a failure of the last node of the plan takes down %r, not nothing: it "
        "is nobody's dependency" % (s.skip_set(deep, "publish"),))

    # ---- the boundaries ----------------------------------------------------

    assert s.skip_set(deep, ()) == (), (
        "no failure takes nothing down, and the empty case came back %r"
        % (s.skip_set(deep, ()),))
    assert s.skip_set(deep, []) == (), (
        "an empty list of failures takes nothing down, and it came back %r"
        % (s.skip_set(deep, []),))
    assert s.skip_set(deep, {"render"}) == s.skip_set(deep, "render"), (
        "one failure given as a set came back %r and given as an id %r"
        % (s.skip_set(deep, {"render"}), s.skip_set(deep, "render")))
    assert s.skip_set(deep, ("render", "render")) == ("index", "publish"), (
        "a failure named twice came back %r, not `index` and `publish`: the same "
        "id twice is one failure" % (s.skip_set(deep, ("render", "render")),))

    single = graph_of("single")
    assert s.skip_set(single, "render") == (), (
        "the single-node plan is nobody's dependency, and its failure came back "
        "%r" % (s.skip_set(single, "render"),))
    assert s.propagate(single, {"render": "running"}, "render", "failed") == (
        {"render": "failed"}), (
        "the single-node plan after its only node failed is %r, not that node "
        "with the status the caller named"
        % (s.propagate(single, {"render": "running"}, "render", "failed"),))

    # ---- the sibling: the wave is not the unit -----------------------------

    # `diamond` is plan -> {render, index} -> join. `render` and `index` share a
    # wave, and only `join` waits on either of them.
    diamond = graph_of("diamond")
    assert s.skip_set(diamond, "index") == ("join",), (
        "a failure of `index` takes down %r, not exactly `join`"
        % (s.skip_set(diamond, "index"),))
    assert s.skip_set(diamond, "render") == ("join",), (
        "a failure of `render` takes down %r, not exactly `join`"
        % (s.skip_set(diamond, "render"),))
    assert "render" not in s.skip_set(diamond, "index"), (
        "`render` is `index`'s sibling, not its dependent: a failure of `index` "
        "does not take it down, and %r does"
        % (s.skip_set(diamond, "index"),))
    assert "index" not in s.skip_set(diamond, "render"), (
        "`index` is `render`'s sibling: %r takes it down"
        % (s.skip_set(diamond, "render"),))
    assert s.skip_set(diamond, "plan") == ("index", "join", "render"), (
        "a failure of `plan` takes down %r, not the whole plan"
        % (s.skip_set(diamond, "plan"),))
    assert s.skip_set(diamond, "join") == (), (
        "the join of the diamond is nobody's dependency, and its failure came "
        "back %r" % (s.skip_set(diamond, "join"),))

    # both branches dispatched when `index` dies: `join`, already `running`, is
    # skipped, and `render` — the same wave, a different branch — is still `ok`.
    states = {"plan": "ok", "render": "ok", "index": "running", "join": "running"}
    after = s.propagate(diamond, states, "index", "failed")
    assert after == {"plan": "ok", "render": "ok", "index": "failed",
                     "join": "skipped"}, (
        "with `index` failed after it was dispatched, the states are %r: "
        "`index` is `failed`, `join` — dispatched too, and waiting on `index` — "
        "is `skipped`, and `render`, the failure's sibling, is still `ok`"
        % (after,))
    assert states == {"plan": "ok", "render": "ok", "index": "running",
                      "join": "running"}, (
        "propagate edited the caller's own states: %r" % (states,))
    assert type(after) is dict, (
        "the new states are %r, not a plain dict: the caller's mapping is an "
        "input, and the one that comes back is this stage's own value"
        % (type(after),))

    # ---- a node that already finished is not overwritten -------------------

    for finished in ("ok", "failed", "skipped"):
        before = {"plan": "ok", "render": "ok", "index": "running",
                  "join": finished}
        got = s.propagate(diamond, before, "index", "failed")["join"]
        assert got == finished, (
            "`join` had already finished %r and came back %r: a status that "
            "overwrites a node which already finished erases work the record "
            "already carries" % (finished, got))
    for unfinished in ("pending", "running", "awaiting"):
        before = {"plan": "ok", "render": "ok", "index": "running",
                  "join": unfinished}
        got = s.propagate(diamond, before, "index", "failed")["join"]
        assert got == "skipped", (
            "`join` was %r when its dependency `index` failed and came back %r: "
            "a dependent that was dispatched (`running`) or is `awaiting` an "
            "approval is skipped too, because its result would be computed from "
            "a dependency that never finished" % (unfinished, got))

    # ---- which statuses cascade -------------------------------------------

    before = {"plan": "ok", "render": "ok", "index": "running", "join": "pending"}
    assert s.propagate(diamond, before, "index", "ok") == (
        {"plan": "ok", "render": "ok", "index": "ok", "join": "pending"}), (
        "a node that reaches `ok` takes nothing down: %r"
        % (s.propagate(diamond, before, "index", "ok"),))
    assert s.propagate(diamond, before, "index", "skipped") == (
        {"plan": "ok", "render": "ok", "index": "skipped", "join": "skipped"}), (
        "a node that is `skipped` takes its dependents down with it — the work "
        "downstream of it is downstream of the failure too — and the states came "
        "back %r" % (s.propagate(diamond, before, "index", "skipped"),))
    for quiet in ("pending", "running", "awaiting"):
        got = s.propagate(diamond, before, "index", quiet)["join"]
        assert got == "pending", (
            "a node that reaches %r has failed at nothing, and `join` came back "
            "%r instead of waiting" % (quiet, got))

    # ---- every node, sorted, and never the caller's mapping ----------------

    unseen = s.propagate(diamond, {"index": "running"}, "index", "failed")
    assert unseen == {"index": "failed", "join": "skipped", "plan": "pending",
                      "render": "pending"}, (
        "with the states naming only `index`, the new states are %r: every node "
        "of the graph, with the ones nobody mentioned still `pending`"
        % (unseen,))
    assert list(unseen) == ["index", "join", "plan", "render"], (
        "the new mapping's ids are %r, not the graph's own sorted ids: a "
        "mapping whose order follows whoever built it serialises differently "
        "for the same run" % (list(unseen),))

    shuffled = {"render": diamond["render"], "join": diamond["join"],
                "plan": diamond["plan"], "index": diamond["index"]}
    ordered = s.propagate(shuffled, {"index": "running"}, "index", "failed")
    assert list(ordered) == ["index", "join", "plan", "render"], (
        "a graph handed in as a plain dict in the caller's order came back with "
        "its ids in %r: the states are a function of the graph and not of the "
        "order its keys happen to be written in" % (list(ordered),))
    assert ordered == unseen, (
        "the same plan written in a different key order gave %r instead of %r"
        % (ordered, unseen))

    # ---- a cycle is walked once, and the failed node is not in its own set --

    cycles = one.parse_graph(graphs.pick("cycles"))
    assert s.skip_set(cycles, "render") == ("index",), (
        "in graphs['cycles'] the dependents of `render` are `index`, and then "
        "`render` again — the node that failed is not in its own skip set — and "
        "the walk came back %r" % (s.skip_set(cycles, "render"),))
    assert s.propagate(cycles, {"render": "running", "index": "running"},
                       "render", "failed") == {"index": "skipped",
                                               "render": "failed"}, (
        "the cycle after `render` failed is %r, not `render` failed with its one "
        "dependent skipped"
        % (s.propagate(cycles, {"render": "running", "index": "running"},
                       "render", "failed"),))

    # ---- the whole wave of a wide plan --------------------------------------

    wide = graph_of("wide")
    assert s.skip_set(wide, "plan") == ("audit", "digest", "index", "notify",
                                        "purge", "render"), (
        "a failure of `plan` takes down all six of its leaves, and it came back "
        "%r" % (s.skip_set(wide, "plan"),))
    assert s.skip_set(wide, "index") == (), (
        "every leaf of graphs['wide'] depends on `plan` and on nothing else, so "
        "a failure of `index` takes down %r, not the rest of its wave"
        % (s.skip_set(wide, "index"),))
    states = {"plan": "ok", "render": "ok", "index": "running", "notify": "ok",
              "audit": "pending", "digest": "awaiting", "purge": "running"}
    assert s.propagate(wide, states, "index", "failed") == (
        {"plan": "ok", "render": "ok", "index": "failed", "notify": "ok",
         "audit": "pending", "digest": "awaiting", "purge": "running"}), (
        "a failure of `index` leaves its five siblings exactly as they were, and "
        "the states came back %r" % (s.propagate(wide, states, "index", "failed"),))

    # ---- every refusal, by class and by the offender it names ---------------

    message = refuses("a graph that is not a mapping",
                      lambda: s.skip_set("deep", "fetch"))
    assert "skip_set" in message and "mapping" in message, (
        "the refusal of a graph given as a string does not say what a graph is "
        "and which function wanted one: %r" % (message,))

    message = refuses("a graph that is not a mapping",
                      lambda: s.propagate("diamond", {}, "index", "failed"))
    assert "propagate" in message and "mapping" in message, (
        "propagate's own refusal of a graph given as a string does not say what "
        "a graph is and which function wanted one: %r" % (message,))
    assert "skip_set" not in message, (
        "propagate's refusal names skip_set as the function that wanted a "
        "graph: %r" % (message,))

    message = refuses("a `failed` that is neither an id nor a collection",
                      lambda: s.skip_set(deep, 7))
    assert "skip_set" in message and "int" in message, (
        "the refusal of `failed=7` does not name what it got and the function "
        "that wanted an id or a collection of them: %r" % (message,))

    message = refuses("a failure list with a number in it",
                      lambda: s.skip_set(deep, ["fetch", 7]))
    assert "failed[1]" in message and "7" in message, (
        "the refusal of an entry of `failed` that is not an id does not name the "
        "entry and the value: %r" % (message,))

    message = refuses("an id the graph does not have",
                      lambda: s.skip_set(deep, "gone"))
    assert "skip_set" in message and "'gone'" in message, (
        "the refusal of a failure of a node the graph does not have does not "
        "name the id: %r" % (message,))

    message = refuses("two unknown ids, the later one written first",
                      lambda: s.skip_set(deep, ("zzz", "aaa")))
    assert "'aaa'" in message, (
        "a plan with two unknown ids named %r: the offenders are examined in "
        "sorted order, so which one is named is a function of the ids and not of "
        "the order somebody wrote them in" % (message,))

    message = refuses("states that are not a mapping",
                      lambda: s.propagate(diamond, [], "index", "failed"))
    assert "propagate" in message and "mapping" in message, (
        "the refusal of states given as a list does not say what the states are: "
        "%r" % (message,))

    message = refuses("a status that is not a state",
                      lambda: s.propagate(diamond, {}, "index", "sunk"))
    assert "propagate" in message and "'sunk'" in message, (
        "the refusal of the status 'sunk' does not name it: %r" % (message,))
    assert "skipped" in message and "awaiting" in message, (
        "the refusal of a status that is not a state does not list the states: "
        "%r" % (message,))

    message = refuses("a node the graph does not have",
                      lambda: s.propagate(diamond, {}, "gone", "failed"))
    assert "propagate" in message and "'gone'" in message, (
        "the refusal of an unknown node does not name the id: %r" % (message,))
    assert "skip_set" not in message, (
        "propagate's own refusal names `skip_set`: %r" % (message,))

    message = refuses("states naming a node the graph does not have",
                      lambda: s.propagate(diamond, {"ghost": "ok"}, "index",
                                          "failed"))
    assert "propagate" in message and "'ghost'" in message, (
        "the refusal of a state for a node the graph does not have does not "
        "name the id: %r" % (message,))

    message = refuses("a state that is not a state",
                      lambda: s.propagate(diamond, {"join": "sunk"}, "index",
                                          "failed"))
    assert "propagate" in message and "'join'" in message, (
        "the refusal of the state 'sunk' for `join` does not name the node and "
        "the value: %r" % (message,))
    assert "'sunk'" in message and "pending" in message, (
        "the refusal of a state that is not a state does not name the value and "
        "list the states: %r" % (message,))

    print("check_06: the failure — a node that fails takes its transitive "
          "dependents and only them: not its wave, not its siblings, not the "
          "whole graph; a dependent that was already dispatched or is awaiting "
          "an approval is skipped too, a node that already finished keeps what "
          "it finished with, every node of the graph comes back in one fresh "
          "id-sorted mapping, and a graph that is not a mapping, a failure that "
          "is not an id, a status that is not a state and a state for a node the "
          "graph does not have are refused naming the offender; "
          "graphs['cycles'] is walked once")

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "orchestration-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J2_REPO=/path/to/forja")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import agents
    import graphs
    import stage_01 as s1
    import stage_07 as s

    # ---- the vocabulary: one gate, two answers ---------------------------

    assert agents.APPROVALS == ("approve", "deny"), (
        "the model's approvals are %r, not ('approve', 'deny'): this stage "
        "reads the human's answer from the model" % (agents.APPROVALS,))
    gate = s1.parse_graph(graphs.pick("gate"))
    assert gate["ship"].effect is True and gate["ask"].effect is False, (
        "graphs['gate'] is not the fixture this check reads: %r"
        % (graphs.pick("gate"),))
    assert gate["ship"].depends == ("ask",), (
        "graphs['gate'] no longer puts the effect behind its approver: %r"
        % (gate["ship"],))

    # ---- the plan-level question: which nodes are gated at all -----------

    assert s.needs_approval(gate, "ship") is True, (
        "the effect 'ship' is not reported as gated: an effect must have its "
        "approval answered before it is dispatched")
    assert s.needs_approval(gate, "ask") is False, (
        "the approver 'ask' is reported as gated: only an effect needs an "
        "approval")
    single = s1.parse_graph(graphs.pick("single"))
    assert s.needs_approval(single, "render") is False, (
        "a lone worker is reported as gated")
    chain = s1.parse_graph(graphs.pick("chain"))
    assert s.needs_approval(chain, "index") is False, (
        "a node that waits for its dependency is reported as gated: waiting "
        "for work is not waiting for an approval")
    assert s.needs_approval(gate, "ask") is False, (
        "the answer to the plan-level question is not a bool")

    # ---- the prompt: the plan, and never a result ------------------------

    prompt = s.approval_prompt(gate["ship"])
    assert prompt == "approve the effect 'ship'? ship the release", (
        "the approval prompt is %r, not the effect's id and the instruction it "
        "will run: by the time there is a result to describe, the effect has "
        "already landed" % (prompt,))
    assert s.approval_prompt(gate["ship"]) == prompt, (
        "two calls built two different approval prompts")
    message = _refuses(
        s.OrchestrationError,
        "an approval asked about a node that is not an effect",
        lambda: s.approval_prompt(gate["ask"]))
    assert "'ask'" in message, (
        "the refusal of a prompt for a node that is not an effect does not "
        "name it: %r" % (message,))

    # ---- the answer: approve and deny both answer ------------------------

    for text in agents.APPROVALS:
        assert s.answers(agents.Reply(text)) is True, (
            "%r is one of %r and is not read as an answer"
            % (text, agents.APPROVALS))
    assert s.answers(agents.Reply("deny", tokens=3)) is True, (
        "a denial is not read as an answer: a denial is a decision, and "
        "reading it as 'no answer yet' holds the effect forever")
    for text in ("APPROVE", "Approved", "approve please", "deny it", "yes",
                 "no", "", "0", "1"):
        assert s.answers(agents.Reply(text)) is False, (
            "%r is not one of %r and is answered anyway: an approval is a "
            "text, matched exactly" % (text, agents.APPROVALS))
    assert s.answers(agents.Reply("maybe", tokens=1)) is False, (
        "a reply whose tokens are not zero is answered although its text is "
        "not an approval: a count is what the call cost, not what it meant")
    message = _refuses(
        s.OrchestrationError,
        "an approval answered by something that is not a reply",
        lambda: s.answers(agents.bad_shape("string")("ask to ship")))
    assert "'done'" in message, (
        "the refusal of an answer that is not a reply does not name what "
        "arrived: %r" % (message,))

    # ---- the gate on the run: it holds the dispatch ----------------------

    assert s.gate_status(gate, {"ask": "ok", "ship": "pending"}, "ship") == "clear", (
        "an effect whose approval has answered 'ok' is not cleared for "
        "dispatch")
    assert s.gate_status(gate, {"ask": "pending", "ship": "pending"}, "ask") == "none", (
        "a node that is not an effect is gated: only an effect waits for an "
        "approval")
    assert s.gate_status(single, {"render": "ok"}, "render") == "none", (
        "a lone worker's gate is not 'none'")
    # an approver that has not answered yet: nothing is dispatched, and the
    # gate says so in the one text a caller can catch
    approver = agents.approver("approve", tokens=8)
    assert approver.calls == 0, (
        "the approver was called before the gate was asked")
    for state in ("pending", "running", "awaiting"):
        message = _refuses(
            s.OrchestrationError,
            "an effect dispatched while its approval is %r" % (state,),
            lambda: s.gate_status(gate, {"ask": state, "ship": "pending"},
                                  "ship"))
        assert "effect-before-approval" in message, (
            "the refusal of a dispatch with the approval %r does not carry "
            "the identifying text: %r" % (state, message))
        assert "'ship'" in message and "'ask'" in message, (
            "the refusal of the dispatch does not name the effect and the "
            "approval it waits for: %r" % (message,))
        assert "'%s'" % (state,) in message, (
            "the refusal does not name the state the approval is in: %r"
            % (message,))
        assert "after" not in message, (
            "the refusal of an effect that has not been dispatched reads as "
            "if it had: the approval arrived after the effect is one case, "
            "not the only one")
    message = _refuses(
        s.OrchestrationError,
        "an effect whose approval nobody has even asked (no states at all)",
        lambda: s.gate_status(gate, {}, "ship"))
    assert "'pending'" in message and "effect-before-approval" in message, (
        "an empty run does not hold the dispatch at the approval's default "
        "state: %r" % (message,))
    assert approver.calls == 0, (
        "the effect was dispatched — the approver was asked to bless work "
        "that had already happened")

    # the classic defect: the approval arrives after the effect
    for state in ("running", "ok"):
        message = _refuses(
            s.OrchestrationError,
            "an effect that reached %r while its approval was awaiting"
            % (state,),
            lambda: s.gate_status(gate, {"ask": "awaiting", "ship": state},
                                  "ship"))
        assert "effect-before-approval" in message, (
            "the classic defect — an effect that reached %r before its "
            "approval answered — is not refused with the identifying text: %r"
            % (state, message))
        assert "'%s'" % (state,) in message, (
            "the refusal does not name the state the effect reached: %r"
            % (message,))
        assert "after" in message, (
            "the refusal does not say the approval arrived after the effect: "
            "%r" % (message,))

    # a denial is a decision, not a failure of the effect
    status = s.gate_status(gate, {"ask": "ok", "ship": "skipped"}, "ship")
    assert status == "denied", (
        "an effect whose approval answered and which was not made is %r, not "
        "'denied': the run records the decision (the effect node ends "
        "'skipped') and the gate's word for it is a decision — 'failed' would "
        "send somebody to repair an effect that was never supposed to happen"
        % (status,))

    # an approval that never answered: the gate is shut, without a decision
    for state in ("failed", "skipped"):
        assert s.gate_status(gate, {"ask": state, "ship": "skipped"},
                             "ship") == "held", (
            "an approval that %r never answered does not hold the gate shut"
            % (state,))
    assert s.gate_status(gate, {"ask": "skipped", "ship": "pending"},
                         "ship") == "held", (
        "a held gate reports something other than 'held'")

    # the four statuses, and nothing else
    seen = {
        s.gate_status(single, {}, "render"),
        s.gate_status(gate, {"ask": "ok", "ship": "pending"}, "ship"),
        s.gate_status(gate, {"ask": "ok", "ship": "skipped"}, "ship"),
        s.gate_status(gate, {"ask": "failed", "ship": "skipped"}, "ship"),
    }
    assert seen == {"none", "clear", "held", "denied"}, (
        "the gate's vocabulary is %r, not ('none', 'clear', 'held', 'denied'): "
        "a status a caller has never heard of is a status a caller ignores"
        % (seen,))

    # ---- the probe: an effect nobody can stop ----------------------------

    bare = s1.parse_graph(graphs.pick("gate", ship={"depends": ()}))
    message = _refuses(
        s.OrchestrationError,
        "an effect none of whose dependencies is an approver",
        lambda: s.needs_approval(bare, "ship"))
    assert "'ship'" in message and "approver" in message, (
        "the refusal of an effect with no approval does not name the effect "
        "and what the graph failed to put behind it: %r" % (message,))
    message = _refuses(
        s.OrchestrationError,
        "an effect with no approval, asked at the gate",
        lambda: s.gate_status(bare, {"ship": "pending"}, "ship"))
    assert "'ship'" in message, (
        "the gate's refusal of an effect with no approval does not name it: %r"
        % (message,))
    rolled = s1.parse_graph(graphs.pick("gate", ask={"agent": "worker"}))
    message = _refuses(
        s.OrchestrationError,
        "an effect whose dependency is work and not an approval",
        lambda: s.needs_approval(rolled, "ship"))
    assert "'ship'" in message, (
        "an effect gated by a worker — a dependency that can be 'ok' and has "
        "no opinion — is not refused, naming the effect: %r" % (message,))

    # ---- the two boundaries: an empty graph's node, two approvals --------

    two = s1.parse_graph({
        "a": {"id": "a", "agent": "approver", "prompt": "ask a"},
        "b": {"id": "b", "agent": "approver", "prompt": "ask b"},
        "ship": {"id": "ship", "agent": "worker", "prompt": "ship it",
                 "depends": ("b", "a"), "effect": True}})
    assert two["ship"].depends == ("b", "a"), (
        "the plan's own dependency order is not preserved: %r"
        % (two["ship"].depends,))
    message = _refuses(
        s.OrchestrationError,
        "an effect with two approvals",
        lambda: s.needs_approval(two, "ship"))
    assert "'ship'" in message and "('a', 'b')" in message, (
        "the refusal of two approvals does not name the effect and both "
        "approvals in sorted order: %r" % (message,))
    message = _refuses(s.OrchestrationError, "a node the graph does not have",
                       lambda: s.needs_approval(gate, "ship2"))
    assert "'ship2'" in message, (
        "the refusal of an unknown node does not name it: %r" % (message,))
    message = _refuses(
        s.OrchestrationError,
        "a gate asked about a node the graph does not have",
        lambda: s.gate_status(gate, {}, "gone"))
    assert "'gone'" in message, (
        "the gate's refusal of an unknown node does not name it: %r"
        % (message,))

    # ---- the gate reads the run and does not write it --------------------

    states = {"ask": "ok", "ship": "pending"}
    snapshot = dict(states)
    assert s.gate_status(gate, states, "ship") == "clear"
    assert states == snapshot, (
        "the gate wrote to the states it was handed: a gate that edits the "
        "states is a gate that dispatches, and what a run does with the answer "
        "is the run's business")

    print("check_07: the approval — an effect is gated by the approver it "
          "depends on, and the gate refuses a dispatch whose approval has not "
          "answered (pending, running, awaiting) with 'effect-before-approval', "
          "naming the effect and the approval; an effect that reached running "
          "or ok while its approval was awaiting is refused as the approval "
          "arriving after the effect; a denial is an answer, and the gate's "
          "word for a denied effect is 'denied' — a decision, never 'failed'; "
          "an approval that never answered holds the gate shut; an effect with "
          "no approver — or two, or one that is work — is refused naming the "
          "effect; and the prompt carries the plan, exactly, because there is "
          "no result yet")

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "orchestration-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J2_REPO=/path/to/forja")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import agents
    import graphs
    import stage_01 as s1
    import stage_08 as s

    def line(state):
        """The run's line, checked as what it is: a tuple of two exact ints."""
        got = s.budget_line(state)
        assert type(got) is tuple, (
            "budget_line(%r) is %r, not a tuple: a line is a pair, and a list is "
            "a thing a caller can edit" % (state, got))
        assert len(got) == 2, (
            "budget_line(%r) is %r, which is not a pair: the line is what was "
            "spent and what the run was allowed to spend" % (state, got))
        assert all(type(number) is int for number in got), (
            "budget_line(%r) is %r: a line is a pair of ints, never a float and "
            "never a percentage" % (state, got))
        return tuple(got)

    def drive(graph, order, budget, scripts, states):
        """§3's loop with only the budget's part of it: the question is asked
        before the call, the number is written down after it, and a node the
        budget refuses is filed `skipped` — never called, and never an exception
        thrown into the loop."""
        state = {"budget": budget}
        for node_id in order:
            node = graph[node_id]
            if not s.affordable(state, node):
                states[node_id] = "skipped"
                continue
            reply = scripts[node_id](node.prompt)
            state["spent"] = s.spend(state, reply)
            states[node_id] = "ok"
        return state

    def scripts_for(graph, tokens=None):
        """One scripted call per node, costing exactly what the node declared
        unless the case says otherwise: `Agent.calls` is how this check proves a
        call the budget refused never happened."""
        return {node_id: agents.worker("done with %s" % node_id,
                                       tokens=(graph[node_id].tokens
                                               if tokens is None else tokens))
                for node_id in graph}

    # ---- the surface: the refusal is this course's, one `except` away -----

    assert issubclass(s.BudgetExhausted, s1.OrchestrationError), (
        "%r is not an OrchestrationError: the course's refusals share a base so "
        "that one `except` catches a broken graph and an exhausted budget"
        % (s.BudgetExhausted,))
    assert issubclass(s.BudgetExhausted, ValueError), (
        "%r is not a ValueError: it derives from stage 1's refusal"
        % (s.BudgetExhausted,))

    # ---- the mechanism, hand-computed on graphs['chain'] ------------------

    chain = s1.parse_graph(graphs.pick("chain"))
    assert (chain["plan"].tokens, chain["render"].tokens,
            chain["index"].tokens) == (16, 32, 24), (
        "the chain's own budgets parsed as %r, %r and %r, not 16, 32 and 24"
        % (chain["plan"].tokens, chain["render"].tokens,
           chain["index"].tokens))

    state = {"budget": 64}                       # a run that has not spent yet
    assert line(state) == (0, 64), (
        "a run that has not spent anything reads as %r, not (0, 64): `spent` is "
        "the ledger's one default, and an empty ledger is zero" % (line(state),))
    assert s.affordable(state, chain["plan"]) is True, (
        "a 16-token node against an unspent 64-token run is affordable")
    state["spent"] = s.spend(state, agents.worker("plan the release",
                                                 tokens=16)("plan the release"))
    assert state["spent"] == 16, (
        "the total after the first call is %r, not the exact 16 the call cost"
        % (state["spent"],))
    assert line(state) == (16, 64), (
        "the line after a 16-token call is %r, not (16, 64)" % (line(state),))
    assert s.affordable(state, chain["render"]) is True, (
        "32 more against 48 left is affordable: 16 + 32 = 48 <= 64")
    state["spent"] = s.spend(state, agents.worker("render the pages",
                                                  tokens=32)("render the pages"))
    assert state["spent"] == 48, (
        "the total after the second call is %r, not the exact 48: 16 + 32, not "
        "32 — a ledger that reports each call as if it were the first never adds "
        "up" % (state["spent"],))
    assert s.affordable(state, chain["index"]) is False, (
        "the chain's third node is worth 24 and 48 are spent of 64: it is short "
        "by 8, and the rule that says otherwise is comparing the node's budget "
        "against the run's total (24 <= 64)")
    assert line(state) == (48, 64), (
        "the refused node moved the ledger to %r: asking the question costs "
        "nothing, and 48 of 64 is not 72" % (line(state),))
    assert s.spend({"spent": 48, "budget": 64}, agents.Reply("done", 0)) == 48, (
        "a free call moved the ledger: the total after a call that cost nothing "
        "is what was already spent")
    assert s.spend({"spent": 7, "budget": 64}, agents.Reply("done", 0)) == 7, (
        "a free call reported %r, not the 7 the run had already spent: `spend` "
        "answers the run's total after the call, never the call's own cost"
        % (s.spend({"spent": 7, "budget": 64}, agents.Reply("done", 0)),))

    # the same run, as a loop: the refused node is a status, not a traceback
    scripts = scripts_for(chain)
    states = {}
    state = drive(chain, ("plan", "render", "index"), 64, scripts, states)
    assert states == {"plan": "ok", "render": "ok", "index": "skipped"}, (
        "the chain under 64 tokens ended in the states %r, not one `skipped` "
        "node the budget never called" % (states,))
    assert state["spent"] == 48 and line(state) == (48, 64), (
        "the chain's ledger ended at %r, not 48 of 64" % (state,))
    assert scripts["index"].calls == 0, (
        "the node the budget refused was called %d times: the question is asked "
        "before the call, so a `no` costs the run no call at all"
        % (scripts["index"].calls,))
    assert (scripts["plan"].calls, scripts["render"].calls) == (1, 1), (
        "the two nodes that fit were called %d and %d times, not once each"
        % (scripts["plan"].calls, scripts["render"].calls))

    # ---- the probe: the node's budget against what is LEFT, not the total --

    wide = s1.parse_graph(graphs.pick("wide"))
    assert sum(wide[node_id].tokens for node_id in wide) == 88, (
        "the wide graph's nodes are worth %r in total, not 88: this check's "
        "numbers are computed by hand"
        % (sum(wide[node_id].tokens for node_id in wide),))
    order = ("plan",) + tuple(sorted(node_id for node_id in wide
                                     if node_id != "plan"))
    scripts = scripts_for(wide)
    states = {}
    state = drive(wide, order, 64, scripts, states)
    assert states == {"plan": "ok", "audit": "ok", "digest": "ok",
                      "index": "ok", "notify": "ok", "purge": "skipped",
                      "render": "skipped"}, (
        "the wide graph under 64 tokens ended in the states %r: the plan is 16, "
        "then audit 16, digest 8, index 16 and notify 8 fit exactly (64), and "
        "purge and render do not" % (states,))
    assert state["spent"] == 64 and line(state) == (64, 64), (
        "the wide run's ledger ended at %r, not the exact (64, 64): the leaf "
        "that fits the line exactly is affordable, and the two that do not are "
        "not paid for" % (state,))
    assert [node_id for node_id in order if scripts[node_id].calls] == [
        "plan", "audit", "digest", "index", "notify"], (
        "the run called %r: the nodes the budget refused must never be called"
        % ([node_id for node_id in order if scripts[node_id].calls],))
    assert scripts["purge"].calls == 0 and scripts["render"].calls == 0, (
        "the two refused leaves were called %d and %d times"
        % (scripts["purge"].calls, scripts["render"].calls))

    # the wrong rule, stated as the check's own arithmetic: every node of the
    # wide graph declares at most 16 tokens, and 16 <= 64 is true of every one
    # of them, so a rule that compares a node's budget against the run's total
    # runs all seven and spends 88
    short = {"spent": 56, "budget": 64}
    assert wide["render"].tokens == 16 <= short["budget"], (
        "this probe needs a node whose own budget fits the run's total")
    assert s.affordable(short, wide["render"]) is False, (
        "a 16-token node against 8 tokens left is affordable: the rule compares "
        "the node's budget against what is left (56 + 16 = 72 > 64), not against "
        "the run's total (16 <= 64)")
    assert sum(wide[node_id].tokens for node_id in order) == 88, (
        "the rule that compares against the total would have spent 88")
    assert state["spent"] == 64, (
        "the wide run spent %r: 88 is the total-comparison rule's bill, and 64 "
        "is the rule that reads what is left" % (state["spent"],))

    # ---- boundaries: the empty ledger, the exact fit, the zero budget -----

    single = s1.parse_graph(graphs.pick("single"))
    assert single["render"].tokens == 8, (
        "graphs['single']'s node is worth %r, not the 8 this check computes with"
        % (single["render"].tokens,))
    assert line({"budget": 8}) == (0, 8), (
        "an unspent 8-token run reads as %r, not (0, 8): `spent` is the ledger's "
        "one default" % (line({"budget": 8}),))
    assert s.affordable({"budget": 8}, single["render"]) is True, (
        "a node worth exactly the run's whole budget is affordable: 0 + 8 <= 8, "
        "and the leaf that fits the line exactly is the boundary this stage "
        "turns on")
    assert s.affordable({"budget": 8}, chain["plan"]) is False, (
        "a 16-token node against an 8-token run is affordable: it is short "
        "before the run has spent anything")
    assert line({"spent": 0, "budget": 0}) == (0, 0), (
        "a run allowed to spend nothing reads as %r, not the exact (0, 0)"
        % (line({"spent": 0, "budget": 0}),))
    free = s1.parse_graph(graphs.pick("single", tokens=0))
    assert s.affordable({"budget": 0}, free["render"]) is True, (
        "a free node against a budget of zero is affordable: 0 + 0 <= 0")
    assert s.affordable({"budget": 0}, chain["plan"]) is False, (
        "a 16-token node against a budget of zero is affordable")
    fits = s1.parse_graph(graphs.pick("single", tokens=4))
    over = s1.parse_graph(graphs.pick("single", tokens=5))
    assert s.affordable({"spent": 60, "budget": 64}, fits["render"]) is True, (
        "the fourth token of a 64-token run with 60 spent is affordable")
    assert s.affordable({"spent": 60, "budget": 64}, over["render"]) is False, (
        "the fifth token of the same line is affordable: the boundary is the "
        "exact fit, never `>=`")

    # ---- the budget is read after the call, and the call already happened --

    honest = {"spent": 60, "budget": 64}
    assert s.spend(honest, agents.Reply("done", 16)) == 76, (
        "a call that cost 16 against 60 spent left the run at %r, not the exact "
        "76: the call happened, so the number is a fact and not a refusal"
        % (s.spend(honest, agents.Reply("done", 16)),))
    assert line({"spent": 76, "budget": 64}) == (76, 64), (
        "a run over its budget reads as %r, not the exact (76, 64): the line "
        "says over by twelve instead of dividing 76 by 64"
        % (line({"spent": 76, "budget": 64}),))
    assert s.affordable({"spent": 76, "budget": 64}, free["render"]) is False, (
        "a free node against an exhausted line is affordable: the run is over "
        "its budget and the next question's answer is `no`")

    # ---- the refusal is a value for the loop ... --------------------------

    assert s.affordable(short, wide["render"]) is False, (
        "`affordable` must answer the loop a bool, not raise: the loop files a "
        "`skipped` state and goes on")
    assert s.affordable(short, wide["render"]) is not None, (
        "`affordable` answered None, which is not a decision")
    assert s.affordable({"budget": 64}, chain["index"]) is True, (
        "a 24-token node against an unspent 64-token run is affordable")

    # ---- ... and the four facts that make the exception a state ------------

    exhausted = {"spent": 61, "budget": 65}
    try:
        s._require_affordable(exhausted, chain["index"])
    except s.BudgetExhausted as raised:
        refusal = raised
    else:
        raise AssertionError(
            "a 24-token node against 4 tokens left was not refused: the "
            "look-before-you-call form of the rule must raise BudgetExhausted")
    message = str(refusal)
    assert refusal.node == "index" and refusal.cost == 24, (
        "the refusal carries node=%r and cost=%r, not 'index' and 24: the facts "
        "are the node's own id and budget, and catching the refusal is filing it"
        % (refusal.node, refusal.cost))
    assert refusal.spent == 61 and refusal.budget == 65, (
        "the refusal carries spent=%r and budget=%r, not the line's 61 and 65"
        % (refusal.spent, refusal.budget))
    assert "'index'" in message, (
        "the refusal does not name the node: %r" % (message,))
    assert "24" in message and "61" in message and "65" in message, (
        "the refusal does not name the cost and both numbers of the line: %r"
        % (message,))
    assert "short by 20" in message, (
        "the refusal does not name the shortfall: a 24-token node with 4 tokens "
        "left is short by 20, and the message says %r" % (message,))
    entry = {"node": refusal.node, "status": "skipped", "tokens": refusal.cost}
    assert entry == {"node": "index", "status": "skipped", "tokens": 24}, (
        "the refusal's own facts do not read as the state entry: %r" % (entry,))
    assert s._require_affordable({"spent": 40, "budget": 64},
                                 chain["index"]) is chain["index"], (
        "the refusal form of the rule refused a node that fits: it returns the "
        "node when the call may be made")
    try:
        s._require_affordable({"budget": 8}, chain["plan"])
    except s.BudgetExhausted as refused_first:
        assert refused_first.cost == 16 and refused_first.spent == 0, (
            "the refusal at the very first node carries cost=%r and spent=%r, "
            "not 16 and 0" % (refused_first.cost, refused_first.spent))
        assert "short by 8" in str(refused_first), (
            "the refusal of a 16-token node against an 8-token run says %r, not "
            "that it is short by 8" % (str(refused_first),))
    else:
        raise AssertionError(
            "a 16-token node against an 8-token run was not refused")

    # a refusal that escapes is not a state: this stage's own rule never raises
    # out of `affordable`, and the run above proved it by finishing
    assert states["purge"] == "skipped" and states["render"] == "skipped", (
        "the two nodes the budget refused are not states in the run: %r"
        % (states,))

    # ---- every refusal the stage defines ----------------------------------

    for bad in ("64", ("budget", 8), ["budget", 8], 7, None):
        message = _refuses(s1.OrchestrationError,
                           "a budget state that is %r" % (bad,),
                           lambda bad=bad: s.budget_line(bad))
        assert "mapping" in message, (
            "the refusal of the state %r does not say a state is a mapping: %r"
            % (bad, message))
    message = _refuses(s1.OrchestrationError, "a state key that is not one",
                       lambda: s.budget_line({"budget": 64, "spend": 40}))
    assert "'spend'" in message and "'spent'" in message and "'budget'" in message, (
        "the refusal of the key 'spend' is %r: a key the shape does not have is "
        "a typo and is refused, naming it and the keys the state may carry — "
        "read as a default it would spend from zero" % (message,))
    message = _refuses(s1.OrchestrationError, "a state that does not say its "
                       "budget",
                       lambda: s.spend({"spent": 0}, agents.Reply("done", 1)))
    assert "'budget'" in message, (
        "the refusal of a state that does not spell 'budget' does not name the "
        "key: %r" % (message,))
    message = _refuses(s1.OrchestrationError,
                       "the loop's question about a state that spells no budget",
                       lambda: s.affordable({"spent": 0}, chain["plan"]))
    assert "'budget'" in message, (
        "the question the loop asks does not read the line through the same "
        "door: %r" % (message,))
    for bad in (True, False, "64", -1, None):
        message = _refuses(s1.OrchestrationError,
                           "a budget of %r" % (bad,),
                           lambda bad=bad: s.budget_line({"budget": bad}))
        assert "'budget'" in message and repr(bad) in message, (
            "the refusal of the budget %r does not name the key and the value: "
            "%r" % (bad, message))
    for bad in (True, "40", 2.5, -1):
        message = _refuses(s1.OrchestrationError,
                           "a spent of %r" % (bad,),
                           lambda bad=bad: s.budget_line({"spent": bad,
                                                          "budget": 64}))
        assert "'spent'" in message and repr(bad) in message, (
            "the refusal of the spent value %r does not name the key and the "
            "value: %r" % (bad, message))

    for shape, named in (("string", "'str'"), ("no_tokens", "'SimpleNamespace'"),
                         ("bad_tokens", "'0'"), ("negative", "-1")):
        message = _refuses(
            s1.OrchestrationError, "the model's %r answer" % (shape,),
            lambda shape=shape: s.spend({"budget": 64},
                                        agents.bad_shape(shape)("a prompt")))
        assert named in message, (
            "the refusal of the model's %r answer does not name the answer it "
            "was handed: %r" % (shape, message))
        if shape in ("string", "no_tokens"):
            assert "Reply" in message, (
                "the refusal of the model's %r answer does not say what an "
                "answer is: %r — an answer that is not a record has no cost to "
                "charge the run for" % (shape, message))
        else:
            assert "tokens" in message, (
                "the refusal of the model's %r answer does not name the field "
                "at fault: %r" % (shape, message))
    message = _refuses(s1.OrchestrationError, "an answer whose tokens is a bool",
                       lambda: s.spend({"budget": 64},
                                       agents.Reply("done", True)))
    assert "True" in message, (
        "the refusal of a `True` cost does not name it: %r — a flag is not a "
        "count, although `isinstance(True, int)` says otherwise" % (message,))
    message = _refuses(s1.OrchestrationError, "an answer whose tokens is a float",
                       lambda: s.spend({"budget": 64},
                                       agents.Reply("done", 2.5)))
    assert "2.5" in message, (
        "the refusal of a float cost does not name it: %r" % (message,))
    try:
        s.spend({"budget": 64}, agents.bad_shape("string")("a prompt"))
    except s.BudgetExhausted:
        raise AssertionError(
            "a malformed answer was refused as a budget exhaustion: the budget "
            "is not exhausted, the answer is not one")
    except s1.OrchestrationError as refused_shape:
        assert "Reply" in str(refused_shape)
    else:
        raise AssertionError("a malformed answer was charged to the run")

    raw = graphs.pick("single")["render"]
    message = _refuses(s1.OrchestrationError, "a raw plan passed as a node",
                       lambda: s.affordable({"budget": 64}, raw))
    assert "'render'" in message and "Subtask" in message, (
        "the refusal of a raw plan does not name the node it describes and the "
        "record it wanted: %r — a raw mapping is not a parsed node, and this "
        "stage is not a second parser" % (message,))
    for bad in ("render", 7, None, ["render"]):
        message = _refuses(s1.OrchestrationError, "a node that is %r" % (bad,),
                           lambda bad=bad: s.affordable({"budget": 64}, bad))
        assert "Subtask" in message, (
            "the refusal of the node %r does not say what a node is: %r"
            % (bad, message))
    lying = s1.Subtask(id="render", agent="worker", prompt="run it", depends=(),
                       ticks=1, tokens=True, effect=False)
    message = _refuses(s1.OrchestrationError, "a node whose budget is a bool",
                       lambda: s.affordable({"budget": 64}, lying))
    assert "'render'" in message and "True" in message, (
        "the refusal of a hand-built node whose budget is `True` names %r: the "
        "node's own count is a count the stage checks, not one it trusts"
        % (message,))
    negative = s1.Subtask(id="render", agent="worker", prompt="run it",
                          depends=(), ticks=1, tokens=-4, effect=False)
    message = _refuses(s1.OrchestrationError, "a node whose budget is negative",
                       lambda: s.affordable({"budget": 64}, negative))
    assert "-4" in message, (
        "the refusal of a negative node budget does not name it: %r" % (message,))

    print("check_08: the budget is asked before the call and written after it — "
          "`affordable` compares the node's own budget against what is left of "
          "the run's (16 then 48 of 64 on the chain, five of the wide graph's "
          "seven nodes and exactly 64 spent), never against the run's total; "
          "`spend` answers the run's exact total after a call and never refuses "
          "a call that already happened; `budget_line` is a pair of ints and "
          "never a float or a percentage; and the refusal is a value the loop "
          "files as a state, with `BudgetExhausted` carrying the node, the cost "
          "and the line's two numbers for the caller that has no loop")

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "orchestration-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J2_REPO=/path/to/forja")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import inspect

    import graphs
    import stage_01
    import stage_09 as s

    def task(node_id, *depends):
        """One raw subtask of a plan built here: a worker, nothing to wait for
        but what it is given, and no effect."""
        return {"id": node_id, "agent": "worker", "prompt": "run %s" % node_id,
                "depends": tuple(depends), "ticks": 1, "tokens": 8,
                "effect": False}

    def plan(*rows):
        """A parsed plan from `(id, depends…)` rows: the shapes the provided
        fixtures cannot express, such as a node whose two dependencies live two
        levels apart."""
        return stage_01.parse_graph({row[0]: task(*row) for row in rows})

    def log(*rows):
        """A record written the way the loop writes one: through `record`, one
        line per decision, in the order the decisions were taken."""
        return tuple(s.record(*row) for row in rows)

    def refusal(what, call, *needles):
        """The message of the `RecordError` `call` must raise, with every piece
        of identifying text `needles` named in it."""
        message = _refuses(s.RecordError, what, call)
        for needle in needles:
            assert needle in message, (
                "the refusal of %s does not name %r: %r" % (what, needle, message))
        return message

    def counted(graph, events, states, *, ticks, tokens):
        """The report, asserted to be every `RUN_KEYS` key in order and ints
        throughout, and handed back for the values it carries."""
        got = s.report(graph, events, states, ticks=ticks, tokens=tokens)
        assert isinstance(got, dict) and tuple(got) == s.RUN_KEYS, (
            "the report is not a dict of RUN_KEYS in order: %r" % (got,))
        for key in ("nodes", "waves", "dispatched", "reviewed", "approved",
                    "rejected", "skipped", "failed", "ticks", "tokens"):
            assert isinstance(got[key], int) and not isinstance(got[key], bool), (
                "the report's %r is %r, not an int count: every number in this "
                "course is an int" % (key, got[key]))
        return got

    diamond = stage_01.parse_graph(graphs.pick("diamond"))
    shuffled = {node_id: diamond[node_id]
                for node_id in ("render", "index", "join", "plan")}
    single = stage_01.parse_graph(graphs.pick("single"))
    chain = stage_01.parse_graph(graphs.pick("chain"))
    leafed = stage_01.parse_graph(graphs.fan("plan", "render", "index"))
    gate = stage_01.parse_graph(graphs.pick("gate"))
    crossed = plan(("a",), ("b", "a"), ("c", "b"), ("d", "a", "c"))

    # --- the record's shape is fixed --------------------------------------

    assert s.EVENT_KEYS == ("tick", "node", "kind", "actor", "status", "tokens"), (
        "EVENT_KEYS is not the record's six fields in the contract's order, so a "
        "reader that unpacks a line reads the wrong field: %r" % (s.EVENT_KEYS,))
    assert s.RUN_KEYS == ("graph", "nodes", "waves", "dispatched", "reviewed",
                          "approved", "rejected", "skipped", "failed", "ticks",
                          "tokens"), (
        "RUN_KEYS is not the report's eleven keys in that order, so two runs of "
        "one plan are not comparable key by key: %r" % (s.RUN_KEYS,))
    assert isinstance(s.EVENT_KEYS, tuple) and isinstance(s.RUN_KEYS, tuple), (
        "a key tuple that can be edited is not a shape: %r, %r"
        % (type(s.EVENT_KEYS).__name__, type(s.RUN_KEYS).__name__))
    assert issubclass(s.RecordError, stage_01.OrchestrationError), (
        "the record's refusal is not derived from OrchestrationError, so one "
        "`except` no longer catches a broken graph and a broken record")

    # --- record: one entry, the six fields, no text ------------------------

    entry = s.record(3, "render", "dispatch", "worker", "running")
    assert tuple(entry) == s.EVENT_KEYS and set(entry) == set(s.EVENT_KEYS), (
        "the line's keys are %r and not exactly EVENT_KEYS in that order: a line "
        "that carries a field the record does not have is the field the report "
        "cannot count" % (list(entry),))
    assert entry == {"tick": 3, "node": "render", "kind": "dispatch",
                     "actor": "worker", "status": "running", "tokens": 0}, (
        "the line is not the six fields it was handed — and a decision that costs "
        "nothing costs 0, not a missing key: %r" % (entry,))
    assert s.record(0, "plan", "result", "planner", "ok", 21)["tokens"] == 21, (
        "the line dropped the tokens the call cost, so the report's total is not "
        "the run's spend")
    assert s.record(0, "plan", "result", "planner", "ok", 21)["tick"] == 0, (
        "tick 0 — the first tick of every run — is not carried by the line")
    assert s.record(3, "render", "dispatch", "worker", "running") == entry, (
        "two lines about the same decision are not equal: a record is compared "
        "line by line by two runs")
    marks = s.record(4, None, "done", "orchestrator", "done")
    assert marks["node"] is None and marks["tokens"] == 0, (
        "the run's own last line does not read as the run's: %r" % (marks,))
    try:
        entry["tick"] = 9
    except TypeError:
        pass
    else:
        raise AssertionError(
            "a line of the record is writable: %r — a record a later stage can "
            "edit is a record that can be made to agree with any report" % (entry,))
    parameters = list(inspect.signature(s.record).parameters.values())
    for parameter in parameters:
        assert parameter.kind is not inspect.Parameter.VAR_KEYWORD, (
            "record takes **%s, so a line can carry the prompt, the result or "
            "the reason a reviewer gave — the text a record must never keep"
            % (parameter.name,))
        assert parameter.name in s.EVENT_KEYS, (
            "record has a parameter %r that is not one of EVENT_KEYS %r: a field "
            "the record has no key for is a field no counter can see"
            % (parameter.name, s.EVENT_KEYS))

    # --- record: the vocabulary, refused with the offender named -----------

    refusal("a kind the record does not have",
            lambda: s.record(1, "render", "exploded", "worker", "ok"),
            "exploded", "dispatch", "budget")
    refusal("a status the kind cannot say",
            lambda: s.record(1, "render", "review", "reviewer", "reject"),
            "review", "reject", "rework")
    refusal("a result word the worker does not have",
            lambda: s.record(1, "render", "result", "worker", "succeeded"),
            "succeeded", "ok")
    refusal("a `done` line that names a node",
            lambda: s.record(1, "render", "done", "orchestrator", "done"),
            "done", "render")
    for missing in (None, "", "   "):
        refusal("a dispatch line that names no node",
                lambda missing=missing: s.record(1, missing, "dispatch", "worker",
                                                 "running"),
                "dispatch")
    refusal("a tick that is the flag True",
            lambda: s.record(True, "render", "dispatch", "worker", "running"),
            "True", "tick")
    refusal("a negative tick",
            lambda: s.record(-1, "render", "dispatch", "worker", "running"),
            "-1", "tick")
    refusal("a tick that is a string",
            lambda: s.record("3", "render", "dispatch", "worker", "running"),
            "'3'", "tick")
    refusal("a tick that is a float",
            lambda: s.record(1.5, "render", "dispatch", "worker", "running"),
            "1.5", "tick")
    refusal("tokens that are a float",
            lambda: s.record(1, "render", "result", "worker", "ok", 2.5),
            "2.5", "tokens")
    refusal("tokens that are the flag True",
            lambda: s.record(1, "render", "result", "worker", "ok", True),
            "True", "tokens")
    refusal("a negative token count",
            lambda: s.record(1, "render", "result", "worker", "ok", -5),
            "-5", "tokens")
    refusal("an actor that is not a name",
            lambda: s.record(1, "render", "dispatch", 7, "running"),
            "7", "actor")
    refusal("a blank actor",
            lambda: s.record(1, "render", "dispatch", "  ", "running"),
            "actor")

    # --- the mechanism, on a record built by hand --------------------------

    # `plan` and `render` finish, `index` dies (a node that did not make it),
    # and the join of the two branches is skipped without ever running. Nine
    # lines, four nodes, three levels.
    spent = log(
        (0, "plan", "dispatch", "planner", "running"),
        (0, "plan", "result", "planner", "ok", 5),
        (1, "render", "dispatch", "worker", "running"),
        (1, "index", "dispatch", "worker", "running"),
        (4, "render", "result", "worker", "ok", 7),
        (4, "render", "review", "reviewer", "accepted", 2),
        (6, "index", "result", "worker", "died", 9),
        (6, "join", "skip", "orchestrator", "skipped"),
        (6, None, "done", "orchestrator", "done"))
    outcomes = {"plan": "ok", "render": "ok", "index": "failed", "join": "skipped"}
    report = counted(shuffled, spent, outcomes, ticks=6, tokens=23)
    assert report == {
        "graph": ("index", "join", "plan", "render"), "nodes": 4, "waves": 3,
        "dispatched": 3, "reviewed": 1, "approved": 0, "rejected": 0,
        "skipped": 1, "failed": 1, "ticks": 6, "tokens": 23}, (
        "the report of a nine-line record is not the nine decisions it took — "
        "four nodes, three levels, three dispatched, one reviewed, one skipped "
        "(the join never ran), one failed (index died), the highest tick 6 and "
        "the 23 tokens its lines cost: %r" % (report,))

    # a node that took two dispatches and two reviews is *one* node dispatched
    # and one reviewed: the rework the reviewer asked for is not a second node.
    rework = log(
        (0, "plan", "dispatch", "planner", "running"),
        (1, "plan", "result", "planner", "ok", 3),
        (1, "render", "dispatch", "worker", "running"),
        (3, "render", "result", "worker", "ok", 11),
        (3, "render", "review", "reviewer", "rework", 2),
        (3, "render", "dispatch", "worker", "running"),
        (5, "render", "result", "worker", "ok", 13),
        (5, "render", "review", "reviewer", "accepted", 2),
        (5, "index", "dispatch", "worker", "running"),
        (7, "index", "result", "worker", "ok", 4),
        (7, None, "done", "orchestrator", "done"))
    report = counted(chain, rework, {"plan": "ok", "render": "ok", "index": "ok"},
                     ticks=7, tokens=35)
    assert report == {
        "graph": ("index", "plan", "render"), "nodes": 3, "waves": 3,
        "dispatched": 3, "reviewed": 1, "approved": 0, "rejected": 1,
        "skipped": 0, "failed": 0, "ticks": 7, "tokens": 35}, (
        "three nodes and eleven lines: the rework was counted as a second node "
        "(or as a second dispatch), and the reviewer's own calls are not in the "
        "35 tokens the lines cost — dispatched 3, reviewed 1, rejected 1, "
        "ticks 7, tokens 35: %r" % (report,))

    # a node whose review ran out: the *last* word on it is what leaves it
    # failed, even though its first line put it in the air.
    exhausted = log(
        (0, "plan", "dispatch", "planner", "running"),
        (1, "plan", "result", "planner", "ok", 3),
        (1, "render", "dispatch", "worker", "running"),
        (3, "render", "result", "worker", "ok", 11),
        (3, "render", "review", "reviewer", "rework", 2),
        (3, "render", "dispatch", "worker", "running"),
        (6, "render", "result", "worker", "ok", 13),
        (6, "render", "review", "reviewer", "failed", 2),
        (6, None, "done", "orchestrator", "done"))
    report = counted(plan(("plan",), ("render", "plan")), exhausted,
                     {"plan": "ok", "render": "failed"}, ticks=6, tokens=31)
    assert (report["failed"], report["rejected"], report["dispatched"],
            report["reviewed"]) == (1, 1, 2, 1), (
        "a node whose rework ran out is one node failed and one node rejected, "
        "dispatched twice but dispatched once: %r" % (report,))

    # the gate: an approval asked and answered, and a denial that decides not to
    # make the effect — the effect is skipped, and the denial is a rejection of
    # the node that was asked.
    approved = log(
        (0, "ask", "dispatch", "approver", "running"),
        (0, "ask", "approval", "approver", "awaiting"),
        (0, "ask", "approval", "approver", "approve", 6),
        (1, "ship", "dispatch", "worker", "running"),
        (4, "ship", "result", "worker", "ok", 12),
        (4, None, "done", "orchestrator", "done"))
    report = counted(gate, approved, {"ask": "ok", "ship": "ok"}, ticks=4,
                     tokens=18)
    assert (report["approved"], report["rejected"], report["dispatched"],
            report["skipped"], report["failed"]) == (1, 0, 2, 0, 0), (
        "a node the approver approved is one node approved (the ask and the "
        "answer are two lines and one node), and the effect behind it ran: %r"
        % (report,))
    denied = log(
        (0, "ask", "dispatch", "approver", "running"),
        (0, "ask", "approval", "approver", "awaiting"),
        (0, "ask", "approval", "approver", "deny", 6),
        (0, "ship", "skip", "orchestrator", "skipped"),
        (0, None, "done", "orchestrator", "done"))
    report = counted(gate, denied, {"ask": "ok", "ship": "skipped"}, ticks=0,
                     tokens=6)
    assert (report["approved"], report["rejected"], report["dispatched"],
            report["skipped"], report["failed"]) == (0, 1, 1, 1, 0), (
        "a denied approval is a rejection of the node that was asked and a skip "
        "of the effect it stopped — not a failure of the effect: %r" % (report,))

    # the budget's own line: a call the budget would not pay for is a node that
    # never ran, whoever stopped it.
    broke = log(
        (0, "plan", "budget", "orchestrator", "skipped"),
        (0, None, "done", "orchestrator", "done"))
    report = counted(chain, broke, {"plan": "skipped"}, ticks=0, tokens=0)
    assert (report["skipped"], report["failed"], report["dispatched"]) == (1, 0, 0), (
        "a node the budget refused is a node that never ran — the record calls "
        "it skipped and so do the states, and no dispatch line was written: %r"
        % (report,))

    # --- boundaries: the empty record, and the plans that fix the levels ----

    empty = counted(single, (), {}, ticks=0, tokens=0)
    assert empty == {"graph": ("render",), "nodes": 1, "waves": 1,
                     "dispatched": 0, "reviewed": 0, "approved": 0,
                     "rejected": 0, "skipped": 0, "failed": 0, "ticks": 0,
                     "tokens": 0}, (
        "a run that took no decision is not the zero report of the plan it was "
        "about — all six counters 0, and the plan's own two numbers and its "
        "identity: %r" % (empty,))
    quiet = counted(leafed, (), {}, ticks=0, tokens=0)
    assert (quiet["nodes"], quiet["waves"]) == (3, 2), (
        "a root and two leaves under it is three nodes and two levels, not three: "
        "%r" % (quiet,))
    deep = counted(crossed, (), {}, ticks=0, tokens=0)
    assert (deep["nodes"], deep["waves"]) == (4, 4), (
        "'d' waits on 'a' and on 'c', and 'c' is only placed in the third level, "
        "so the plan has four levels — a count read off the number of "
        "dependencies, or a walk that places a node as soon as one dependency is "
        "done, says three: %r" % (deep,))
    assert deep["graph"] == ("a", "b", "c", "d"), (
        "the plan's identity is its node ids in sorted order: %r" % (deep["graph"],))
    assert tuple(s.report(shuffled, spent, outcomes, ticks=6, tokens=23)) == s.RUN_KEYS, (
        "the report's keys are RUN_KEYS in that order, whatever order the plan "
        "or the record were written in")

    # --- the report refuses what it was handed, naming the offender ---------

    texted = list(spent)
    texted[5] = dict(texted[5], reason="the render is too dark")
    refusal("a line that carries the reviewer's reason",
            lambda: s.report(diamond, texted, outcomes, ticks=6, tokens=23),
            "reason", "never keep", "index 5")
    prompty = list(spent)
    prompty[0] = dict(prompty[0], prompt="plan the release")
    refusal("a line that carries the prompt",
            lambda: s.report(diamond, prompty, outcomes, ticks=6, tokens=23),
            "prompt", "never keep")
    refusal("a line that is not a mapping",
            lambda: s.report(diamond, ["render"], {}, ticks=0, tokens=0),
            "index 0", "mapping")
    refusal("a line that carries no actor",
            lambda: s.report(diamond, [{"tick": 0, "node": "plan",
                                        "kind": "dispatch", "status": "running",
                                        "tokens": 0}], {}, ticks=0, tokens=0),
            "index 0", "'actor'")
    refusal("a line whose kind the record does not have",
            lambda: s.report(diamond, [dict(spent[0], kind="exploded")], {},
                             ticks=0, tokens=0),
            "index 0", "exploded")
    refusal("a line whose status its kind cannot say",
            lambda: s.report(diamond, [dict(spent[1], status="reject")], {},
                             ticks=0, tokens=0),
            "index 0", "reject", "result")
    refusal("a line that names a node the plan does not have",
            lambda: s.report(diamond, spent + (s.record(6, "ghost", "skip",
                                                        "orchestrator", "skipped"),),
                             outcomes, ticks=6, tokens=23),
            "index 9", "ghost")

    # the effect a gate stops waits for its answer with no line of its own: a
    # node the record never names may be `awaiting`.
    waiting = log(
        (0, "ask", "dispatch", "approver", "running"),
        (0, "ask", "approval", "approver", "awaiting"),
        (0, None, "done", "orchestrator", "done"))
    report = counted(gate, waiting, {"ask": "awaiting", "ship": "awaiting"},
                     ticks=0, tokens=0)
    assert (report["dispatched"], report["approved"], report["skipped"]) == (1, 0, 0), (
        "a gate asked and not answered is one node dispatched and none approved, "
        "and the effect behind it is still waiting: %r" % (report,))

    # --- the run's own account against the record ---------------------------

    stalled = log(
        (0, "plan", "dispatch", "planner", "running"),
        (1, "plan", "result", "planner", "ok", 3),
        (1, "render", "dispatch", "worker", "running"),
        (3, "render", "result", "worker", "ok", 11),
        (3, "render", "review", "reviewer", "rework", 2),
        (3, None, "done", "orchestrator", "done"))
    refusal("a node a rework left in the air claimed ok",
            lambda: s.report(chain, stalled, {"plan": "ok", "render": "ok"},
                             ticks=3, tokens=16),
            "render", "'ok'", "running")
    refusal("a node asked and unanswered claimed running",
            lambda: s.report(gate, waiting, {"ask": "running", "ship": "awaiting"},
                             ticks=0, tokens=0),
            "ask", "'running'", "awaiting")
    refusal("a state word the course does not have",
            lambda: s.report(diamond, spent, dict(outcomes, join="done"),
                             ticks=6, tokens=23),
            "join", "'done'", "pending")
    refusal("a node a line is about claimed pending",
            lambda: s.report(diamond, spent, dict(outcomes, plan="pending"),
                             ticks=6, tokens=23),
            "plan", "'pending'", "'ok'")
    refusal("a node the record never names claimed running",
            lambda: s.report(single, (), {"render": "running"}, ticks=0, tokens=0),
            "render", "'running'", "pending")
    refusal("a node the record says was skipped claimed ok",
            lambda: s.report(diamond, spent, dict(outcomes, join="ok"), ticks=6,
                             tokens=23),
            "join", "'ok'", "skipped")
    refusal("a node the record says failed claimed ok",
            lambda: s.report(diamond, spent, dict(outcomes, index="ok"), ticks=6,
                             tokens=23),
            "index", "'ok'", "failed")
    refusal("a state for a node the plan does not have",
            lambda: s.report(single, (), {"ghost": "ok"}, ticks=0, tokens=0),
            "ghost", "plan")
    refusal("a states argument that is not a mapping",
            lambda: s.report(single, (), ["ok"], ticks=0, tokens=0),
            "mapping")

    # --- the two totals: the caller's claim, the record's count -------------

    refusal("a ticks total the record contradicts",
            lambda: s.report(diamond, spent, outcomes, ticks=9, tokens=23),
            "ticks", "9", "6")
    refusal("a tokens total the record contradicts",
            lambda: s.report(diamond, spent, outcomes, ticks=6, tokens=99),
            "tokens", "99", "23")
    refusal("a tokens total that is not even a count",
            lambda: s.report(diamond, spent, outcomes, ticks=6, tokens="23"),
            "tokens", "'23'")

    # --- a plan the report cannot number ------------------------------------

    cycles = stage_01.parse_graph(graphs.pick("cycles"))
    refusal("a plan whose nodes wait on each other",
            lambda: s.report(cycles, (), {}, ticks=0, tokens=0),
            "index", "cycle")

    # --- determinism: one record, one report --------------------------------

    first = s.report(diamond, spent, outcomes, ticks=6, tokens=23)
    second = s.report(diamond, spent, outcomes, ticks=6, tokens=23)
    assert first == second and tuple(first) == s.RUN_KEYS, (
        "two reports of one record are not the same report, so two runs of one "
        "plan cannot be compared byte for byte: %r vs %r" % (first, second))
    assert first["graph"] == tuple(sorted(diamond)), (
        "the report's identity for a plan is the plan's node ids in sorted order, "
        "so a plan written in another order is the same plan: %r"
        % (first["graph"],))
    assert not any(isinstance(value, float) for value in first.values()), (
        "the report carries a float, and every number in this course is an int "
        "count: %r" % (first,))

    print("check_09: the record — seven kinds of decision, six fields, no text, "
          "frozen, and a line's shape and vocabulary refused at the offender's "
          "name; the report — eleven keys in order, every counter a set of node "
          "ids so a rework counts once, `ticks` the highest tick and `tokens` the "
          "sum of what the lines cost, both recomputed and both checked against "
          "the totals the caller claimed, `nodes` and `waves` the plan's own and "
          "the levels walked here (a fan's two leaves share a wave and a node "
          "behind two dependencies lands where the slower one puts it), the states "
          "checked node by node against the record's last word (a rework left in "
          "the air, a gate asked and unanswered, a line's node claimed pending, a "
          "node the record never names claimed running or ok, a state word the "
          "course does not have — and the effect a gate stops allowed to wait as "
          "`awaiting` with no line of its own), the empty "
          "record, the single node, `graphs['cycles']` refused by naming a node "
          "that is still waiting, and a line that carries the prompt, the result "
          "or a rejection's reason refused by naming the key — the text a record "
          "must never keep")

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    EVENT_KEYS = ("tick", "node", "kind", "actor", "status", "tokens")

    def _repo(start=None):
        for candidate_start in (os.environ.get("J2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "orchestration-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J2_REPO=/path/to/forja")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import agents
    import fleet
    import graphs
    import stage_01
    import stage_05
    import stage_07
    import stage_09
    import stage_10 as s

    def task(node_id, *depends, **fields):
        """One raw subtask of a plan built here."""
        raw = {"id": node_id, "agent": "worker", "prompt": "run %s" % node_id,
               "depends": tuple(depends), "ticks": 1, "tokens": 8,
               "effect": False}
        raw.update(fields)
        return raw

    def plan(*rows):
        return stage_01.parse_graph({row["id"]: row for row in rows})

    def fixture(name):
        return stage_01.parse_graph(graphs.GRAPHS[name])

    def lines(*rows):
        """Hand-written record lines, in `EVENT_KEYS` order."""
        return tuple(dict(zip(EVENT_KEYS, row)) for row in rows)

    def recorded(result):
        """The run's lines, read through `EVENT_KEYS` and nothing else."""
        events = result["events"]
        assert isinstance(events, tuple), (
            "a run's record is a tuple of lines, so two runs compare as values: "
            "%r" % (type(events).__name__,))
        for entry in events:
            assert tuple(entry) == EVENT_KEYS, (
                "a line of the record carries exactly %r, got %r"
                % (EVENT_KEYS, tuple(entry)))
        return tuple(dict(entry) for entry in events)

    def report_of(result, **expected):
        got = result["report"]
        assert tuple(got) == stage_09.RUN_KEYS, (
            "the report carries exactly %r, got %r" % (stage_09.RUN_KEYS, tuple(got)))
        for key, value in expected.items():
            assert got[key] == value, (
                "the report's %s is %r, not %r" % (key, got[key], value))
        assert got["ticks"] == result["clock"], (
            "the run's clock ended at %r and the report's highest tick is %r: "
            "the clock is the run's record of the ticks it spent"
            % (result["clock"], got["ticks"]))
        assert got["tokens"] == sum(entry["tokens"] for entry in result["events"]), (
            "the report's tokens are not the sum of what the lines cost: %r"
            % (got["tokens"],))
        return got

    def states_of(result, **expected):
        got = result["states"]
        assert isinstance(got, dict), (
            "a run's states are a mapping of id to state, got %r"
            % (type(got).__name__,))
        for node_id, status in sorted(got.items()):
            assert isinstance(status, str), (
                "the state of %r is %r, and a state is one of the six words"
                % (node_id, status))
        assert sorted(got) == sorted(expected) or not expected, (
            "the states name %r, not %r" % (sorted(got), sorted(expected)))
        for node_id, status in expected.items():
            assert got.get(node_id) == status, (
                "the run's state for %r is %r, not %r"
                % (node_id, got.get(node_id), status))
        return got

    def refuses_no_float(value, where="the run"):
        if isinstance(value, float):
            raise AssertionError(
                "%s carries the float %r: every number in this course is an int "
                "count" % (where, value))
        if isinstance(value, dict):
            for key, item in value.items():
                refuses_no_float(key, where)
                refuses_no_float(item, where)
        elif isinstance(value, (tuple, list)):
            for item in value:
                refuses_no_float(item, where)

    # --- the chain, line by line --------------------------------------------

    chain = fixture("chain")
    script = {"planner": agents.planner("a plan", tokens=2),
              "worker": agents.worker("rendered", "indexed", tokens=4)}
    chained = s.run(chain, script, clock=fleet.Clock())
    assert chained["clock"] == 6 and isinstance(chained["clock"], int), (
        "a chain of one, three and two ticks is six ticks: %r" % (chained["clock"],))
    assert recorded(chained) == lines(
        (0, "plan", "dispatch", "planner", "running", 0),
        (1, "plan", "result", "planner", "ok", 2),
        (1, "render", "dispatch", "worker", "running", 0),
        (4, "render", "result", "worker", "ok", 4),
        (4, "index", "dispatch", "worker", "running", 0),
        (6, "index", "result", "worker", "ok", 4),
        (6, None, "done", "run", "done", 0)), (
        "the chain's record is not the one its costs force, dispatch at 0, 1 and "
        "4, result at 1, 4 and 6, done last: %r" % (recorded(chained),))
    states_of(chained, plan="ok", render="ok", index="ok")
    report_of(chained, graph=("index", "plan", "render"), nodes=3, waves=3,
              dispatched=3, reviewed=0, approved=0, rejected=0, skipped=0,
              failed=0, ticks=6, tokens=10)
    assert chained["handoffs"] == {
        "plan": "plan the release",
        "render": "render the pages\nplan: a plan",
        "index": "index the pages\nrender: rendered"}, (
        "each node is handed its own dependencies' accepted results, cut to "
        "their budgets: %r" % (chained["handoffs"],))
    refuses_no_float(chained)

    # the second level: `index` cannot start before `render` is back
    dispatch_ticks = [entry["tick"] for entry in chained["events"]
                      if entry["kind"] == "dispatch"]
    assert dispatch_ticks == [0, 1, 4], (
        "the three nodes of a chain are dispatched one after the other, 0, 1 and "
        "4: %r" % (dispatch_ticks,))

    # a plan parsed twice is the same plan, and the same run
    again = s.run(fixture("chain"),
                  {"planner": agents.planner("a plan", tokens=2),
                   "worker": agents.worker("rendered", "indexed", tokens=4)},
                  clock=fleet.Clock())
    assert again == chained, (
        "two runs of one fixture are not equal, so a run is a function of "
        "something other than its graph and its agents: %r vs %r"
        % (again, chained))

    # a run with no clock of its own starts one at zero, and the clock it is
    # given is advanced to the next thing that can change the state
    class Watched(fleet.Clock):
        """The injected clock, with the ticks it was moved by written down."""

        def __init__(self):
            fleet.Clock.__init__(self)
            self.calls = []

        def tick(self, n=1):
            self.calls.append(n)
            return fleet.Clock.tick(self, n)

    fresh = s.run(fixture("chain"), script)
    assert fresh == chained, (
        "a run with no clock of its own starts a fresh one at zero, so it is the "
        "same run: %r vs %r" % (fresh["clock"], chained["clock"]))
    watched = Watched()
    paced = s.run(fixture("chain"), script, clock=watched)
    assert paced == chained, (
        "the clock changes when the run moves it, never what the run computes: "
        "%r vs %r" % (paced["clock"], chained["clock"]))
    assert watched.calls == [1, 3, 2], (
        "the clock is advanced to the next thing that can change the state — one "
        "tick to the plan, three to the render, two to the index — and never "
        "walked a tick at a time: %r" % (watched.calls,))

    # the single node: the boundary with nothing to wait for and nothing after
    single = fixture("single")
    alone = s.run(single, {"worker": agents.worker("rendered", tokens=4)},
                  clock=fleet.Clock())
    assert recorded(alone) == lines(
        (0, "render", "dispatch", "worker", "running", 0),
        (2, "render", "result", "worker", "ok", 4),
        (2, None, "done", "run", "done", 0)), (
        "a single node is dispatched, is back after its own two ticks and the run "
        "is done: %r" % (recorded(alone),))
    states_of(alone, render="ok")
    report_of(alone, graph=("render",), nodes=1, waves=1, dispatched=1, ticks=2,
              tokens=4, skipped=0, failed=0, reviewed=0)
    assert alone["handoffs"] == {"render": "render the page"}, (
        "a root node has no handoff and is handed its own prompt: %r"
        % (alone["handoffs"],))

    # the empty plan is the plan's own refusal, and it reaches the runner
    message = _refuses(stage_01.OrchestrationError, "an empty plan",
                       lambda: s.run(plan(), {}))
    assert "at least one node" in message, (
        "an empty plan is refused by naming what it does not have: %r" % (message,))
    message = _refuses(stage_01.OrchestrationError, "a plan with a cycle",
                       lambda: s.run(fixture("cycles"), {}))
    assert "index" in message and "render" in message, (
        "a plan whose nodes wait on each other is refused by naming the cycle: "
        "%r" % (message,))

    # --- the gate: the ask, the answer, and the effect -----------------------

    gate = fixture("gate")
    asker = agents.approver("approve", tokens=1)
    shipper = agents.worker("shipped", tokens=2)
    approved = s.run(gate, {"approver": asker, "worker": shipper},
                     clock=fleet.Clock())
    assert recorded(approved) == lines(
        (0, "ask", "approval", "approver", "awaiting", 0),
        (0, "ask", "approval", "approver", "approve", 1),
        (0, "ship", "dispatch", "worker", "running", 0),
        (3, "ship", "result", "worker", "ok", 2),
        (3, None, "done", "run", "done", 0)), (
        "an approved effect is asked first, answered at the same tick, and only "
        "then dispatched and run: %r" % (recorded(approved),))
    states_of(approved, ask="ok", ship="ok")
    report_of(approved, graph=("ask", "ship"), nodes=2, waves=2, dispatched=1,
              reviewed=0, approved=1, rejected=0, skipped=0, failed=0, ticks=3,
              tokens=3)
    assert approved["handoffs"] == {"ship": "ship the release\nask: approve"}, (
        "the effect is handed its approval's own answer, and the gate node is not "
        "counted as work: %r" % (approved["handoffs"],))
    assert (asker.calls, shipper.calls) == (1, 1), (
        "the gate is asked once and the effect is called once: %r"
        % ((asker.calls, shipper.calls),))

    denier = agents.approver("deny", tokens=1)
    denied_worker = agents.worker("shipped", tokens=2)
    denied = s.run(gate, {"approver": denier, "worker": denied_worker},
                   clock=fleet.Clock())
    assert recorded(denied) == lines(
        (0, "ask", "approval", "approver", "awaiting", 0),
        (0, "ask", "approval", "approver", "deny", 1),
        (0, "ship", "skip", "run", "skipped", 0),
        (0, None, "done", "run", "done", 0)), (
        "a denied effect is never dispatched: the answer is a decision, the "
        "effect is skipped, and the run is over at tick 0: %r"
        % (recorded(denied),))
    states_of(denied, ask="ok", ship="skipped")
    report_of(denied, graph=("ask", "ship"), nodes=2, waves=2, dispatched=0,
              reviewed=0, approved=0, rejected=1, skipped=1, failed=0, ticks=0,
              tokens=1)
    assert denied_worker.calls == 0, (
        "an effect whose approval denied it is never called: %r"
        % (denied_worker.calls,))
    assert denied["handoffs"] == {}, (
        "a node that never ran was handed nothing: %r" % (denied["handoffs"],))

    # --- the gate's ordering, with a spy on stage 7 --------------------------

    order = []
    real_gate = stage_07.gate_status

    def spy_gate(graph, states, node_id):
        order.append(("gate", node_id))
        return real_gate(graph, states, node_id)

    def spy_asker(prompt, attempt):
        order.append(("ask", prompt))
        return agents.Reply("approve", 1)

    def spy_worker(prompt, attempt):
        order.append(("run", prompt))
        return agents.Reply("shipped", 2)

    stage_07.gate_status = spy_gate
    try:
        spied = s.run(gate, {"approver": agents.Agent(spy_asker, label="approver"),
                             "worker": agents.Agent(spy_worker, label="worker")},
                      clock=fleet.Clock())
    finally:
        stage_07.gate_status = real_gate
    assert [step for step, _ in order] == ["ask", "gate", "run"], (
        "the approval is asked, and the gate is consulted for the effect, before "
        "the effect's own call — never after it: %r" % (order,))
    assert order[0][1] == stage_07.approval_prompt(gate["ship"]), (
        "the approver is asked the question stage 7 builds about the effect, got "
        "%r" % (order[0][1],))
    assert order[1][1] == "ship" and order[2][1].startswith("ship the release"), (
        "the gate decides about `ship` and the effect is handed its prompt: %r"
        % (order,))
    states_of(spied, ask="ok", ship="ok")

    # an effect dispatched with its approval unanswered is the refusal stage 7
    # owns — the run must never produce one, and the spy proves it was asked.

    # --- the cap is not a formality -----------------------------------------

    wide = fixture("wide")
    fan_agents = {"planner": agents.planner("a plan", tokens=1),
                  "worker": agents.worker("did it", tokens=1)}
    capped = s.run(wide, fan_agents, clock=fleet.Clock(), limit=4)
    assert capped["clock"] == 6, (
        "the six leaves of the fan run four at a time: two rounds and six ticks, "
        "not %r" % (capped["clock"],))
    one_at_a_time = s.run(fixture("wide"),
                          {"planner": agents.planner("a plan", tokens=1),
                           "worker": agents.worker("did it", tokens=1)},
                          clock=fleet.Clock(), limit=1)
    assert one_at_a_time["clock"] == 15, (
        "the same fan one node at a time costs fifteen ticks, not %r: a run that "
        "ignores the cap pays for the cap it was given only in the number it "
        "reports" % (one_at_a_time["clock"],))
    assert recorded(one_at_a_time) == lines(
        (0, "plan", "dispatch", "planner", "running", 0),
        (1, "plan", "result", "planner", "ok", 1),
        (1, "audit", "dispatch", "worker", "running", 0),
        (3, "audit", "result", "worker", "ok", 1),
        (3, "digest", "dispatch", "worker", "running", 0),
        (5, "digest", "result", "worker", "ok", 1),
        (5, "index", "dispatch", "worker", "running", 0),
        (10, "index", "result", "worker", "ok", 1),
        (10, "notify", "dispatch", "worker", "running", 0),
        (11, "notify", "result", "worker", "ok", 1),
        (11, "purge", "dispatch", "worker", "running", 0),
        (12, "purge", "result", "worker", "ok", 1),
        (12, "render", "dispatch", "worker", "running", 0),
        (15, "render", "result", "worker", "ok", 1),
        (15, None, "done", "run", "done", 0)), (
        "with a cap of one the second level waits for every sibling: the order "
        "is audit, digest, index, notify, purge, render, by id and not by "
        "cost: %r" % (recorded(one_at_a_time),))
    states_of(one_at_a_time, plan="ok", audit="ok", digest="ok", index="ok",
              notify="ok", purge="ok", render="ok")
    report_of(one_at_a_time, dispatched=7, ticks=15, tokens=7, waves=2, nodes=7)
    assert (capped["states"] == one_at_a_time["states"]
            and capped["handoffs"] == one_at_a_time["handoffs"]), (
        "the cap changes when a node runs, never what it is handed or what it "
        "ends as: %r vs %r" % (capped["states"], one_at_a_time["states"]))

    # the fast branch, the slow sibling, and the join that waits for both
    diamond = fixture("diamond")
    joined = s.run(diamond, {"planner": agents.planner("a plan", tokens=1),
                             "worker": agents.worker("did it", tokens=1)},
                   clock=fleet.Clock(), limit=2)
    assert recorded(joined)[:9] == lines(
        (0, "plan", "dispatch", "planner", "running", 0),
        (1, "plan", "result", "planner", "ok", 1),
        (1, "index", "dispatch", "worker", "running", 0),
        (1, "render", "dispatch", "worker", "running", 0),
        (4, "render", "result", "worker", "ok", 1),
        (6, "index", "result", "worker", "ok", 1),
        (6, "join", "dispatch", "worker", "running", 0),
        (7, "join", "result", "worker", "ok", 1),
        (7, None, "done", "run", "done", 0)), (
        "the diamond's branches start together at 1, the fast one lands at 4, and "
        "the join waits for the slow one at 6: %r" % (recorded(joined)[:9],))
    report_of(joined, dispatched=4, ticks=7, tokens=4, waves=3)
    states_of(joined, plan="ok", index="ok", render="ok", join="ok")
    assert joined["handoffs"]["join"] == (
        "join the two results\nindex: did it\nrender: did it"), (
        "the join is handed both branches' results, in id order: %r"
        % (joined["handoffs"]["join"],))

    # --- the review, the rework and the failure ------------------------------

    judge = agents.reviewer("reject", "accept", tokens=1)
    reviewed = s.run(fixture("chain"),
                     {"planner": agents.planner("a plan", tokens=2),
                      "worker": agents.worker("rendered", "indexed", tokens=4)},
                     clock=fleet.Clock(), reviewer=judge)
    assert recorded(reviewed)[:7] == lines(
        (0, "plan", "dispatch", "planner", "running", 0),
        (1, "plan", "result", "planner", "ok", 2),
        (1, "plan", "review", "reviewer", "rework", 1),
        (1, "plan", "dispatch", "planner", "running", 0),
        (2, "plan", "result", "planner", "ok", 2),
        (2, "plan", "review", "reviewer", "accepted", 1),
        (2, "render", "dispatch", "worker", "running", 0)), (
        "a rejected result is re-dispatched at the same tick and the next attempt "
        "is accepted: %r" % (recorded(reviewed)[:7],))
    states_of(reviewed, plan="ok", render="ok", index="ok")
    report_of(reviewed, dispatched=3, reviewed=3, rejected=3, failed=0, ticks=12,
              tokens=26)
    assert reviewed["handoffs"]["plan"] == (
        "plan the release\n(rework plan, attempt 2, rejected: reject)"), (
        "the prompt a node was last handed is stage 5's rework prompt, carrying "
        "the reviewer's reason: %r" % (reviewed["handoffs"]["plan"],))
    assert judge.calls == 6, (
        "three nodes, each reviewed twice: %r" % (judge.calls,))

    refuser = agents.refuser("the diff is empty", tokens=1)
    failed = s.run(fixture("chain"),
                   {"planner": agents.planner("a plan", tokens=2),
                    "worker": agents.worker("rendered", "indexed", tokens=4)},
                   clock=fleet.Clock(), reviewer=refuser)
    assert recorded(failed) == lines(
        (0, "plan", "dispatch", "planner", "running", 0),
        (1, "plan", "result", "planner", "ok", 2),
        (1, "plan", "review", "refuser", "rework", 1),
        (1, "plan", "dispatch", "planner", "running", 0),
        (2, "plan", "result", "planner", "ok", 2),
        (2, "plan", "review", "refuser", "rework", 1),
        (2, "plan", "dispatch", "planner", "running", 0),
        (3, "plan", "result", "planner", "ok", 2),
        (3, "plan", "review", "refuser", "failed", 1),
        (3, "index", "skip", "run", "skipped", 0),
        (3, "render", "skip", "run", "skipped", 0),
        (3, None, "done", "run", "done", 0)), (
        "a reviewer that never accepts fails the node on the third rejection "
        "(MAX_REWORK reworks), and its dependents are skipped without being "
        "dispatched: %r" % (recorded(failed),))
    states_of(failed, plan="failed", render="skipped", index="skipped")
    report_of(failed, dispatched=1, reviewed=1, rejected=1, skipped=2, failed=1,
              ticks=3, tokens=9)
    assert failed["handoffs"] == {
        "plan": "plan the release\n(rework plan, attempt 3, rejected: the diff "
                "is empty)"}, (
        "only the node that ran was handed anything: %r" % (failed["handoffs"],))

    # the sibling that must still run, and the dependent that must not
    branch = plan(task("plan", prompt="plan the batch"),
                  task("left", "plan", prompt="do the left half"),
                  task("right", "plan", prompt="do the right half"),
                  task("join", "left", prompt="join the halves"))

    def one_half(prompt, attempt):
        """A reviewer that rejects the left branch for ever and accepts the rest,
        so exactly one node fails and the graph's shape decides the rest."""
        if "left" in prompt:
            return agents.Reply("reject", 1)
        return agents.Reply("accept", 1)

    halves = agents.worker("did it", tokens=4)
    branched = s.run(branch, {"worker": halves}, clock=fleet.Clock(),
                     reviewer=agents.Agent(one_half, label="reviewer"))
    states_of(branched, plan="ok", left="failed", right="ok", join="skipped")
    report_of(branched, dispatched=3, reviewed=3, rejected=1, skipped=1,
              failed=1)
    assert "join" in [entry["node"] for entry in branched["events"]
                      if entry["kind"] == "skip"], (
        "the failed node's dependent is skipped by a line of its own: %r"
        % (recorded(branched),))
    assert "right" not in [entry["node"] for entry in branched["events"]
                           if entry["kind"] == "skip"], (
        "the sibling of a failure is not its dependent: %r" % (recorded(branched),))
    assert halves.calls == 5, (
        "the sibling runs as often as anyone else (three attempts on the left "
        "branch, one on the right, one on the plan): %r" % (halves.calls,))

    # --- the gate holds the effect ------------------------------------------

    held = plan(
        task("prep", prompt="prepare the batch"),
        task("ask", "prep", agent="approver", prompt="ask to ship"),
        task("ship", "ask", prompt="ship it", ticks=3, tokens=16, effect=True))
    keeper = agents.approver("approve", tokens=1)
    preparer = agents.worker("prepared", tokens=2)
    stopped = s.run(held, {"approver": keeper, "worker": preparer},
                    clock=fleet.Clock(), reviewer=refuser)
    ship_worker = agents.worker("shipped", tokens=3)
    assert states_of(stopped, prep="failed", ask="skipped",
                     ship="skipped")["ship"] == "skipped"
    assert stage_07.gate_status(held, stopped["states"], "ship") == "held", (
        "the gate that stops the effect says so: %r"
        % (stage_07.gate_status(held, stopped["states"], "ship"),))
    assert keeper.calls == 0, (
        "the gate is never asked when the run cannot reach it, and an effect is "
        "never dispatched on an answer nobody gave: %r" % (keeper.calls,))
    assert "ship" not in stopped["handoffs"], (
        "an effect the gate held was handed nothing, because it never ran: %r"
        % (stopped["handoffs"],))
    assert ship_worker.calls == 0, (
        "the effect's own worker was never called: %r" % (ship_worker.calls,))
    # the run cannot pay for the ask either: the gate is skipped before the
    # question reaches anybody, and the effect goes with it.
    poorgate = s.run(fixture("gate"),
                     {"approver": agents.approver("approve", tokens=1),
                      "worker": agents.worker("shipped", tokens=2)},
                     clock=fleet.Clock(), budget=0)
    assert recorded(poorgate) == lines(
        (0, "ask", "approval", "approver", "awaiting", 0),
        (0, "ask", "budget", "run", "skipped", 0),
        (0, "ship", "skip", "run", "skipped", 0),
        (0, None, "done", "run", "done", 0)), (
        "a run that cannot pay for the answer never calls the approver: the "
        "refusal is a state, and the effect is skipped behind it: %r"
        % (recorded(poorgate),))
    states_of(poorgate, ask="skipped", ship="skipped")
    report_of(poorgate, dispatched=0, approved=0, skipped=2, ticks=0, tokens=0)

    # --- the effect that waits for its approval and for its work ------------

    gated_work = plan(
        task("work", prompt="do the work", ticks=2, tokens=16),
        task("ask", agent="approver", prompt="ask to ship"),
        task("ship", "ask", "work", prompt="ship it", ticks=3, tokens=16,
             effect=True))
    both = agents.approver("approve", tokens=1)
    doer = agents.worker("did it", tokens=2)
    waited = s.run(gated_work, {"approver": both, "worker": doer},
                   clock=fleet.Clock())
    assert recorded(waited) == lines(
        (0, "ask", "approval", "approver", "awaiting", 0),
        (0, "ask", "approval", "approver", "approve", 1),
        (0, "work", "dispatch", "worker", "running", 0),
        (2, "work", "result", "worker", "ok", 2),
        (2, "ship", "dispatch", "worker", "running", 0),
        (5, "ship", "result", "worker", "ok", 2),
        (5, None, "done", "run", "done", 0)), (
        "an effect that waits for work and for its approval is asked first, held "
        "while the work finishes, and dispatched only when both are done: %r"
        % (recorded(waited),))
    states_of(waited, ask="ok", ship="ok", work="ok")
    report_of(waited, nodes=3, waves=2, dispatched=2, approved=1, ticks=5,
              tokens=5)
    assert waited["handoffs"]["ship"] == (
        "ship it\nask: approve\nwork: did it"), (
        "the effect is handed the approval's answer and the work it waits for, in "
        "id order: %r" % (waited["handoffs"]["ship"],))

    # the human can be handed to the run instead of being looked up in the plan
    override = agents.approver("approve", tokens=1)
    handed = s.run(gate, {"worker": agents.worker("shipped", tokens=2)},
                   clock=fleet.Clock(), approver=override)
    assert (handed["states"], override.calls) == ({"ask": "ok", "ship": "ok"}, 1), (
        "an `approver` given to the run answers for the gate, so the plan needs "
        "no approver label of its own: %r" % (handed["states"],))
    assert [entry["actor"] for entry in handed["events"]
            if entry["kind"] == "approval"] == ["approver", "approver"], (
        "the record says who answered, which is the agent's own label: %r"
        % ([entry["actor"] for entry in handed["events"]],))

    # an injected clock that does not start at zero moves the whole run with it
    started = fleet.Clock(4)
    shifted = s.run(fixture("chain"),
                    {"planner": agents.planner("a plan", tokens=2),
                     "worker": agents.worker("rendered", "indexed", tokens=4)},
                    clock=started)
    assert shifted["clock"] == 4 + chained["clock"], (
        "a run counted on a clock that starts at four ends four ticks later, and "
        "its ticks are the clock's readings: %r" % (shifted["clock"],))
    assert recorded(shifted) == tuple(
        dict(entry, tick=entry["tick"] + 4) for entry in chained["events"]), (
        "every line of the run moves with the clock it was given: %r"
        % (recorded(shifted),))
    assert started.ticks == chained["clock"], (
        "the run advances the clock it was given, by the work it did: %r"
        % (started.ticks,))

    # the agent is told which attempt it is answering
    counters = agents.Agent(
        lambda prompt, attempt: agents.Reply("answered %d" % attempt, 1),
        label="worker")

    def once(prompt, attempt):
        """Rejects the render's first attempt and accepts everything else."""
        if "render" in prompt and attempt == 1:
            return agents.Reply("reject", 0)
        return agents.Reply("accept", 0)

    told = s.run(fixture("chain"),
                 {"planner": agents.planner("planned", tokens=1),
                  "worker": counters},
                 clock=fleet.Clock(), reviewer=agents.Agent(once, label="judge"))
    assert told["handoffs"]["index"] == "index the pages\nrender: answered 2", (
        "a reworked node's second attempt is the agent's second entry, and the "
        "result that reaches its dependent is the one that was accepted: %r"
        % (told["handoffs"].get("index"),))
    assert "answered 1" not in told["handoffs"]["index"], (
        "the rejected attempt's result is not the one handed on: %r"
        % (told["handoffs"]["index"],))

    # the reviewer is asked stage 5's question, and the record names it
    asked = []
    real_review_prompt = stage_05.review_prompt

    def judge_fn(prompt, attempt):
        asked.append((prompt, attempt))
        return agents.Reply("reject" if "left" in prompt else "accept", 1)

    judging = s.run(branch, {"worker": agents.worker("did it", tokens=4)},
                    clock=fleet.Clock(),
                    reviewer=agents.Agent(judge_fn, label="judge"))
    states_of(judging, plan="ok", left="failed", right="ok", join="skipped")
    allowed = set()
    for node_id in branch:
        for try_number in (1, 2, 3):
            allowed.add(real_review_prompt(branch[node_id], try_number))
    assert asked and all(prompt in allowed for prompt, _ in asked), (
        "every review is asked stage 5's own question about the node and the "
        "attempt: %r" % (asked,))
    assert {(attempt) for _, attempt in asked} == {1, 2, 3}, (
        "the reviewer is told which attempt it is judging, so a script can "
        "answer by attempt: %r" % (asked,))
    assert {entry["actor"] for entry in judging["events"]
            if entry["kind"] == "review"} == {"judge"}, (
        "a review line names the agent that reviewed: %r"
        % ([entry["actor"] for entry in judging["events"]],))

    # completions that fall due in one tick are taken in id order, not in the
    # order they were dispatched
    out_of_order = plan(
        task("root", prompt="root it"),
        task("mid", "root", prompt="the middle"),
        task("zzz", "root", prompt="the last by name", ticks=6),
        task("aaa", "mid", prompt="the first by name", ticks=5))
    ticked = s.run(out_of_order, {"worker": agents.worker("did it", tokens=1)},
                   clock=fleet.Clock(), limit=2)
    results = [(entry["tick"], entry["node"]) for entry in ticked["events"]
               if entry["kind"] == "result"]
    assert results[-2:] == [(7, "aaa"), (7, "zzz")], (
        "two nodes that are back at the same tick are filed in id order, not in "
        "the order they were dispatched: %r" % (results,))
    states_of(ticked, root="ok", mid="ok", zzz="ok", aaa="ok")

    # --- the budget, asked before the call ----------------------------------

    broke = s.run(fixture("chain"),
                  {"planner": agents.planner("a plan", tokens=2),
                   "worker": agents.worker("rendered", "indexed", tokens=4)},
                  clock=fleet.Clock(), budget=33)
    assert recorded(broke) == lines(
        (0, "plan", "dispatch", "planner", "running", 0),
        (1, "plan", "result", "planner", "ok", 2),
        (1, "render", "budget", "run", "skipped", 0),
        (1, "index", "skip", "run", "skipped", 0),
        (1, None, "done", "run", "done", 0)), (
        "a node the run cannot pay for is refused before the call, as a state and "
        "not as a crash, and its dependents follow it: %r" % (recorded(broke),))
    states_of(broke, plan="ok", render="skipped", index="skipped")
    report_of(broke, dispatched=1, reviewed=0, skipped=2, failed=0, ticks=1,
              tokens=2)
    assert broke["handoffs"] == {"plan": "plan the release"}, (
        "a node the budget refused was never handed a prompt: %r"
        % (broke["handoffs"],))

    rich = s.run(fixture("chain"),
                 {"planner": agents.planner("a plan", tokens=2),
                  "worker": agents.worker("rendered", "indexed", tokens=4)},
                 clock=fleet.Clock(), budget=41)
    assert states_of(rich, plan="ok", render="ok", index="ok")
    report_of(rich, dispatched=3, skipped=0, failed=0, ticks=6, tokens=10)
    assert (rich["states"], rich["clock"]) == (chained["states"], chained["clock"])

    # --- two runs, identical bytes ------------------------------------------

    for name, table, kwargs in (
            ("chain", {"planner": agents.planner("a plan", tokens=2),
                       "worker": agents.worker("rendered", "indexed", tokens=4)},
             {}),
            ("gate", {"approver": agents.approver("approve", tokens=1),
                      "worker": agents.worker("shipped", tokens=2)}, {}),
            ("wide", {"planner": agents.planner("a plan", tokens=1),
                      "worker": agents.worker("did it", tokens=1)}, {"limit": 3}),
            ("diamond", {"planner": agents.planner("a plan", tokens=1),
                         "worker": agents.worker("did it", tokens=1)}, {})):
        first = s.run(fixture(name), table, clock=fleet.Clock(), **kwargs)
        second = s.run(fixture(name), table, clock=fleet.Clock(), **kwargs)
        assert first == second, (
            "two runs of %r are not equal, so a run depends on an identity or an "
            "insertion order: %r vs %r" % (name, first["states"], second["states"]))
        refuses_no_float(first, "the run of %r" % (name,))
        assert first["states"] is not second["states"], (
            "two runs share one states mapping, so a second run can edit the "
            "first: %r" % (first["states"],))
    assert s.run(chain, script, clock=fleet.Clock()) == chained, (
        "the same agents and a fresh clock are the same run: the clock is "
        "injected, never read")

    # --- the refusals -------------------------------------------------------

    def refuses(what, call, *text):
        message = _refuses(stage_01.OrchestrationError, what, call)
        for want in text:
            assert want in message, (
                "%s was refused without naming %r: %r" % (what, want, message))
        return message

    both = {"approver": agents.approver("approve"), "worker": agents.worker("x")}
    refuses("a plan whose node has no agent",
            lambda: s.run(gate, {"worker": agents.worker("x")},
                          clock=fleet.Clock()),
            "ask", "approver", "no agent")
    early = agents.worker("prepared", tokens=1)
    refuses("an actor that is not an Agent",
            lambda: s.run(plan(task("prep", prompt="prepare"),
                               task("ask", "prep", agent="approver",
                                    prompt="ask to ship"),
                               task("ship", "ask", prompt="ship it", ticks=3,
                                    effect=True)),
                          {"approver": "the boss", "worker": early},
                          clock=fleet.Clock()),
            "agents['approver']", "Agent")
    assert early.calls == 0, (
        "an actors table holding something that is not an Agent is refused before "
        "the first tick, not after the work in front of the gate has run: %r"
        % (early.calls,))
    refuses("an agents table that is not a mapping",
            lambda: s.run(gate, [("approver", agents.approver("approve"))],
                          clock=fleet.Clock()),
            "mapping")
    refuses("a cap of zero",
            lambda: s.run(gate, both, clock=fleet.Clock(), limit=0),
            "run(): limit", "cap")
    refuses("a cap that is a flag",
            lambda: s.run(gate, both, clock=fleet.Clock(), limit=True),
            "run(): limit", "int count")
    refuses("a negative cap",
            lambda: s.run(gate, both, clock=fleet.Clock(), limit=-1),
            "run(): limit", ">= 0")
    refuses("a budget that is not a count",
            lambda: s.run(gate, both, clock=fleet.Clock(), budget="40"),
            "run(): budget", "int count")
    refuses("a negative budget",
            lambda: s.run(gate, both, clock=fleet.Clock(), budget=-1),
            "run(): budget", ">= 0")
    refuses("a reviewer that is not an Agent",
            lambda: s.run(gate, both, clock=fleet.Clock(), reviewer="me"),
            "run(): reviewer", "Agent")
    refuses("an approver that is not an Agent",
            lambda: s.run(gate, both, clock=fleet.Clock(), approver=0),
            "run(): approver", "Agent")
    refuses("a clock that is not fleet.Clock",
            lambda: s.run(gate, both, clock=0),
            "run(): the clock", "fleet.Clock", "counted")
    refuses("a graph that is not a mapping",
            lambda: s.run([{"id": "ship"}], both, clock=fleet.Clock()),
            "mapping of id to subtask")
    refuses("a plan nobody parsed",
            lambda: s.run(graphs.pick("gate"), both, clock=fleet.Clock()),
            "not a subtask", "parse_graph")
    refuses("a plan whose id is not a string",
            lambda: s.run({1: task("ship")}, both, clock=fleet.Clock()),
            "node id is a string")
    untouched = agents.worker("nothing", tokens=1)
    refuses("an effect with no approval",
            lambda: s.run(plan(task("prep", prompt="prepare"),
                               task("ship", "prep", effect=True)),
                          {"worker": untouched}, clock=fleet.Clock()),
            "ship", "no approval", "approver")
    assert untouched.calls == 0, (
        "a plan whose effect has nobody to approve it is refused before the "
        "first tick, not after the work in front of it has run: %r"
        % (untouched.calls,))
    refuses("an effect with two approvals",
            lambda: s.run(plan(task("one", agent="approver"),
                               task("two", agent="approver"),
                               task("ship", "one", "two", effect=True)),
                          both, clock=fleet.Clock()),
            "ship", "approvals")
    refuses("an approval answered with something that is not one",
            lambda: s.run(fixture("gate"),
                          {"approver": agents.worker("maybe"), "worker": agents.worker("x")},
                          clock=fleet.Clock()),
            "ask", "maybe", "approve", "deny")

    # --- the shape of what comes back ---------------------------------------

    assert set(chained) == {"states", "events", "report", "clock", "handoffs"}, (
        "a run answers with exactly the five keys the stage declares: %r"
        % (sorted(chained),))
    for key in ("states", "handoffs"):
        assert isinstance(chained[key], dict), (
            "a run's %s is a mapping, got %r" % (key, type(chained[key]).__name__))
    assert set(chained["handoffs"]) <= set(chained["states"]), (
        "a handoff names a node of the plan: %r" % (chained["handoffs"],))
    assert list(chained["states"]) == sorted(chained["states"]), (
        "the states are built in sorted id order, so two runs render the same "
        "bytes: %r" % (list(chained["states"]),))
    assert list(chained["handoffs"]) == sorted(chained["handoffs"]), (
        "the handoffs are built in sorted id order: %r" % (list(chained["handoffs"]),))
    assert s.DEFAULT_LIMIT == 4, (
        "the run's default cap is four, the cap `graphs['wide']` is shaped for: "
        "%r" % (s.DEFAULT_LIMIT,))

    print("check_10: the run end to end — §3's loop over the injected clock "
          "(dispatch at a tick, back at tick plus the node's own cost, the clock "
          "advanced only to the next thing that can change the state), the cap "
          "against a hand-computed fan (four at a time is six ticks, one at a "
          "time is fifteen and the second level waits), the gate asked and "
          "answered before the effect (a spy proving the ask and stage 7's "
          "verdict precede the effect's own call), a denied effect skipped with "
          "its worker never called, an effect held behind an approval that never "
          "answers (the approver's calls zero), a failure skipping its transitive "
          "dependent without dispatching it while its sibling runs, the budget "
          "refused as a state and never as a crash, the review reworking at most "
          "MAX_REWORK times and failing after that, the report recomputed from "
          "the record and its totals checked against the run's, two runs of one "
          "fixture equal value for value, the single node and the empty plan, "
          "and every refusal naming its offender")

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The subtask and the graph",
        tags=["subtask", "validation"],
        action="Write `SUBTASK_KEYS`, `parse_subtask` and `parse_graph` in "
               "stage_01.py.",
        predict="What a key the shape does not have should do — refuse, or take "
                "the documented default — and which of the two makes a typo'd "
                "graph run as if it were well formed.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The order a dependency forces",
        tags=["topological order", "cycles"],
        action="Write `dependencies`, `waves`, `would_cycle` and `validate_order` "
               "in stage_02.py.",
        predict="Why a diamond's two branches belong to the same wave and its "
                "join belongs to the next, and why a cycle has to be named "
                "rather than detected by counting waves.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The wave is not the schedule",
        tags=["scheduling", "concurrency"],
        action="Write `runnable` and `dispatchable` in stage_03.py.",
        predict="Whether a node in the second wave may start while a sibling "
                "from the first is still running — and what a scheduler that "
                "answers `no` costs on every graph wider than a chain.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The handoff that carries its own context",
        tags=["handoff", "context"],
        action="Write `budgeted`, `handoff` and `render_prompt` in stage_04.py.",
        predict="Which results a node is handed at dispatch — its own "
                "dependencies', or every ancestor's — and what an agent does "
                "with a context that is the whole transcript.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The reviewer that can reject",
        tags=["review", "rework"],
        action="Write `MAX_REWORK`, `review_prompt`, `accepts`, `rework_prompt` "
               "and `next_attempt` in stage_05.py.",
        predict="What a rejection has to change about the next attempt, and what "
                "a rejection that is recorded but never acted on looks like from "
                "the outside.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="One failure, and the rest of the graph",
        tags=["failure", "propagation"],
        action="Write `skip_set` and `propagate` in stage_06.py.",
        predict="Which nodes a failed node takes down with it — its direct "
                "dependents, everything downstream, or the whole wave — and why "
                "a sibling of the failure still has to run.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The approval, and the effect it stops",
        tags=["human-in-the-loop", "effects"],
        action="Write `approval_prompt`, `needs_approval`, `answers` and "
               "`gate_status` in stage_07.py.",
        predict="What an approval is worth after the effect has already "
                "happened, and why the gate has to hold the dispatch rather "
                "than report on it.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The budget, checked before the call",
        tags=["budget", "refusal"],
        action="Write `BudgetExhausted`, `spend`, `affordable` and `budget_line` "
               "in stage_08.py.",
        predict="What a budget overrun should be at the moment it is discovered "
                "— an exception into the loop, or a state the run accounts for — "
                "and which of the two a report can be recomputed from.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The record, and the report from it",
        tags=["record", "report"],
        action="Write `EVENT_KEYS`, `RUN_KEYS`, `record` and `report` in "
               "stage_09.py.",
        predict="Why the report has to be recomputed from the events, and what a "
                "record that carries the prompt text costs the run that has to "
                "keep it.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="Two runs, identical bytes",
        tags=["orchestration", "determinism"],
        action="Write `DEFAULT_LIMIT` and `run` in stage_10.py.",
        predict="Which decisions of a run are the graph's, which are the "
                "agents', and what has to be pinned for two runs of the same "
                "fixture to print the same bytes.",
        check=check_10,
    ),
]
