"""Sandbox & Capabilities From Scratch — course manifest.

Ten graded stages between an agent that is trusted with whatever its tools can do
and an agent whose power is the *intersection* of three things: what its tools
declare, what its principal granted, and what the world will still afford. The
world is provided: `fleet.py` is J1's verbatim (the injected clock, and nothing
else this course needs from it), `vfs.py` is a filesystem made of dictionaries
that normalises nothing and records every path it was made to touch, and
`tools.py` is the environment — nine tools that each declare the capabilities
they demand and what one call costs, five hosts, three secrets, five principals'
grants and roots, five raw plans, and the four objects that *do* something:
`Meter`, `Wire`, `Vault` and `Audit`, each keeping its own record of what it was
asked for.

The thesis of the whole course is one sentence, and every stage's check asserts
it: AN AGENT'S POWER IS NOT WHAT ITS TOOLS CAN DO, IT IS THE INTERSECTION OF WHAT
THE TOOLS DECLARE, WHAT THE PRINCIPAL GRANTED, AND WHAT THE WORLD WILL STILL
AFFORD — AND THE AUDIT LINE IS THE ONLY PROOF OF WHICH ONE SAID NO. Every stage is
one decision about that intersection: what a tool declares and which refusals a
bad declaration earns, what a grant is and why the answer is a difference rather
than a boolean, how a path resolves before it is judged and why a string prefix
is not a jail, why a host pattern nobody can read is not a policy, what a limit
charges and why the charge is all or nothing before the work, why a secret's
fingerprint may travel while its value may not, what an audit line carries and
why its reason vocabulary is closed, how a call is decided in one order and why a
denied call must not reach the world at all, which numbers are recomputed from
the lines and cross-checked against the world's own record, and what a run's
answer to "what did it touch" actually is. The failures worth preventing are the
ones that look like success: a grant that permits everything because it was
tested for truth, a jail that lets the sibling root through, a limit checked with
`>=`, a denied call that charged the meter, an audit line written after the act,
a report whose numbers came from the run's memory, and a secret that reached the
model base64-encoded with nobody noticing.

Standard library only, offline, deterministic, **ints only** (counters, bytes,
ticks — no floats anywhere): no `time`, no `threading`, no `asyncio`, no `os`, no
sockets, no subprocesses, no unseeded randomness, no module-level mutable state.
Nothing here touches the real filesystem, a real network or a real secret: the
filesystem, the wire and the vault are all modelled as data, a dial is a method
that appends to a list, and a denial is a value the loop keeps going with. That
is why this course can be checked to the byte — and why `agents-from-scratch`
(J4's prerequisite C2), which jails a *real* directory with `os.path.realpath`,
is the course this one stands on: the rules are the same, the subject and the
failures are not.

    python3 codecraft/cli.py run sandbox-capabilities-from-scratch
"""

from codecraft.api import stage

TITLE = "Sandbox & Capabilities From Scratch"
DESCRIPTION = ("An agent's power as the intersection of declared, granted and "
               "affordable: a capability set demanded by each tool and refused by "
               "name when the vocabulary does not have it, a principal's grant "
               "whose answer is the difference and not a boolean, a path jail that "
               "resolves before it decides and never lets the sibling root through, "
               "a network policy of exact hosts with no wildcard a reader cannot "
               "evaluate, cpu/memory/ticks limits charged all or nothing before the "
               "work, secrets that reach the model only as a fingerprint and leak "
               "in none of four encodings, an audit line per call with a closed "
               "reason vocabulary written before the act, a call decided in one "
               "order that a denial never reaches the world through, a report "
               "recomputed from the lines and cross-checked against the world's own "
               "records, and a run whose answer to what it touched is its audit and "
               "not its plan.")
LEVEL = "advanced"
ORDER = 23


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "sandbox-capabilities-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J4_REPO=/path/to/forja")

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

    import stage_01 as s
    import tools as world

    # ---- the vocabulary every later stage speaks --------------------------

    assert s.TOOL_KEYS == ("name", "description", "capabilities", "cost",
                           "target_kind"), (
        "this stage's declaration fields are %r, not the five the course "
        "defined" % (s.TOOL_KEYS,))
    assert s.CALL_KEYS == ("tool", "target", "value"), (
        "this stage's call fields are %r, not the three the course defined"
        % (s.CALL_KEYS,))
    assert isinstance(s.COST_DEFAULTS, Mapping) and tuple(s.COST_DEFAULTS) == (
        "cpu", "memory", "ticks"), (
        "COST_DEFAULTS is %r, not a mapping over the three counters in order"
        % (s.COST_DEFAULTS,))
    assert tuple(s.COST_DEFAULTS.values()) == (1, 0, 1), (
        "an omitted cost counter defaults to %r: a call that costs nothing at all "
        "is a call nobody counted" % (s.COST_DEFAULTS,))
    assert issubclass(s.SandboxError, ValueError), (
        "%r is not a ValueError: the course's refusal is a named error a caller "
        "can catch, and every later stage derives its own from it"
        % (s.SandboxError,))
    assert issubclass(s.ToolError, s.SandboxError), (
        "%r is not a %s: one `except SandboxError` must still catch a broken "
        "declaration" % (s.ToolError, s.SandboxError.__name__))

    # ---- capability: one name, a suggestion, and no second meaning --------

    for name in world.CAPABILITIES:
        assert s.capability(name) == name, (
            "the vocabulary's own name %r is not accepted by `capability`" % (name,))
    message = _refuses(s.ToolError, "a capability that is a typo",
                       lambda: s.capability("fs:reed"))
    assert "fs:reed" in message and "fs:read" in message, (
        "the refusal of 'fs:reed' does not name it and suggest the real "
        "capability: %r" % (message,))
    message = _refuses(s.ToolError, "a capability the world does not have",
                       lambda: s.capability("fs:teleport"))
    assert "fs:teleport" in message, (
        "the refusal of 'fs:teleport' does not name it: %r" % (message,))
    message = _refuses(s.ToolError, "a capability that is not a str",
                       lambda: s.capability(7))
    assert "str" in message and "7" in message, (
        "the refusal of a non-str capability does not name its shape and the "
        "offender: %r" % (message,))
    message = _refuses(s.ToolError, "a capability nobody could have meant",
                       lambda: s.capability("frobnicate"))
    assert "frobnicate" in message and "did you mean" not in message, (
        "the refusal of 'frobnicate' suggests a name anyway: a suggestion that is "
        "not close is a lie, and the distance is two: %r" % (message,))
    message = _refuses(s.ToolError, "a capability in the wrong case",
                       lambda: s.capability("FS:read"))
    assert "FS:read" in message, (
        "the refusal of 'FS:read' does not name it: a name is not folded, or the "
        "policy would match in production and not in the check" % (message,))

    # ---- declares: the demand, as one sorted tuple ------------------------

    assert s.declares(world.TOOLS["read_file"]) == ("fs:read",), (
        "read_file demands %r, not one capability"
        % (s.declares(world.TOOLS["read_file"]),))
    assert s.declares(world.TOOLS["debug_dump"]) == ("fs:read", "net:connect"), (
        "debug_dump's demand reads %r, not two capabilities in sorted order"
        % (s.declares(world.TOOLS["debug_dump"]),))
    assert s.declares({"capabilities": ("net:connect", "fs:read")}) == (
        "fs:read", "net:connect"), (
        "a demand written in the other order reads %r: a demand carries no order, "
        "and a program that compares them positionally answers differently "
        "depending on how somebody typed a tuple"
        % (s.declares({"capabilities": ("net:connect", "fs:read")}),))
    assert s.declares({"capabilities": ["fs:delete"]}) == ("fs:delete",), (
        "a demand handed over as a list is not read as a demand")
    message = _refuses(s.ToolError, "a demand that repeats a capability",
                       lambda: s.declares({"capabilities": ("fs:read",
                                                            "fs:read")}))
    assert "fs:read" in message, (
        "the refusal of a repeated demand does not name it: %r" % (message,))
    message = _refuses(s.ToolError, "a demand that is empty",
                       lambda: s.declares({"capabilities": ()}))
    assert "hole" in message, (
        "the refusal of an empty demand does not say what an empty demand is: %r"
        % (message,))
    message = _refuses(s.ToolError, "a declaration with no capabilities at all",
                       lambda: s.declares({"description": "x"}))
    assert "capabilities" in message, (
        "the refusal of a declaration with no demand does not name the missing "
        "field: %r" % (message,))
    message = _refuses(s.ToolError, "a demand handed over as a str",
                       lambda: s.declares({"capabilities": "fs:read"}))
    assert "fs:read" in message, (
        "the refusal of a str demand does not name it: %r" % (message,))
    message = _refuses(s.ToolError, "a demand that is not a sequence at all",
                       lambda: s.declares({"capabilities": 3}))
    assert "demand" in message and "3" in message, (
        "the refusal of a demand that is a number does not name the field and "
        "the offender: %r" % (message,))
    message = _refuses(s.ToolError, "a declaration that is not a mapping",
                       lambda: s.declares(("fs:read",)))
    assert "mapping" in message and "got a mapping" not in message, (
        "the refusal of a declaration handed over as a tuple claims to have got "
        "a mapping: %r" % (message,))
    message = _refuses(s.ToolError, "a declaration that is not a mapping at all",
                       lambda: s.declares(7))
    assert "mapping" in message and "7" in message, (
        "the refusal of the declaration 7 does not name its shape and the "
        "offender: %r" % (message,))
    message = _refuses(s.ToolError, "the world's own teleport",
                       lambda: s.declares(world.TOOLS["teleport"]))
    assert "fs:teleport" in message, (
        "the refusal of the teleport declaration does not name the capability "
        "that does not exist: %r" % (message,))
    fixture = {"capabilities": ("fs:read",)}
    s.declares(fixture)
    assert fixture == {"capabilities": ("fs:read",)}, (
        "`declares` bent the caller's declaration: %r" % (fixture,))

    # ---- parse_tool: the record, its defaults, its refusals ---------------

    record = s.parse_tool("reader", {"capabilities": ("fs:read",)})
    assert tuple(record) == s.TOOL_KEYS, (
        "a parsed declaration carries %r, not exactly TOOL_KEYS in order"
        % (tuple(record),))
    assert record == {"name": "reader", "description": "",
                      "capabilities": ("fs:read",),
                      "cost": {"cpu": 1, "memory": 0, "ticks": 1},
                      "target_kind": "none"}, (
        "a minimal declaration parses to %r, not to its defaults" % (record,))
    assert tuple(record["cost"]) == world.COST_KEYS, (
        "a parsed cost carries %r, not every counter in declared order"
        % (tuple(record["cost"]),))
    cost = s.parse_tool("reader", {"capabilities": ("fs:read",),
                                   "cost": {"memory": 8}})["cost"]
    assert cost == {"cpu": 1, "memory": 8, "ticks": 1}, (
        "a cost with one counter spelled materialises as %r: an omitted counter "
        "is a default, not a free one" % (cost,))
    record = s.parse_tool("reader", {"capabilities": ("fs:read",),
                                     "description": "reads one file",
                                     "target_kind": "path"})
    assert record["description"] == "reads one file" and record["target_kind"] == "path", (
        "a declaration that spells its description and kind does not keep them: %r"
        % (record,))
    message = _refuses(s.ToolError, "a declaration with a foreign field",
                       lambda: s.parse_tool("reader", {"targetkind": "path",
                                                       "capabilities": ("fs:read",)}))
    assert "targetkind" in message and "target_kind" in message, (
        "the refusal of the field 'targetkind' does not name it and suggest the "
        "real one: %r" % (message,))
    message = _refuses(s.ToolError, "a target kind that is not one of the four",
                       lambda: s.parse_tool("reader", {"capabilities": ("fs:read",),
                                                       "target_kind": "socket"}))
    assert "socket" in message, (
        "the refusal of the target kind 'socket' does not name it: %r" % (message,))
    message = _refuses(s.ToolError, "a target kind that is a typo",
                       lambda: s.parse_tool("reader", {"capabilities": ("fs:read",),
                                                       "target_kind": "patth"}))
    assert "patth" in message and "path" in message, (
        "the refusal of 'patth' does not name it and suggest 'path': %r"
        % (message,))
    for bad, spelling in (({"cpu": True}, "True"),
                          ({"cpu": 1.5}, "1.5"),
                          ({"cpu": -1}, "-1"),
                          ({"cpu": "1"}, "'1'")):
        message = _refuses(s.ToolError, "a cost counter that is %s" % (spelling,),
                           lambda bad=bad: s.parse_tool(
                               "reader", {"capabilities": ("fs:read",),
                                          "cost": bad}))
        assert "cpu" in message and spelling in message, (
            "the refusal of a %s cost counter does not name the counter and the "
            "offender: %r" % (spelling, message))
    message = _refuses(s.ToolError, "a cost with a counter that is not one",
                       lambda: s.parse_tool("reader", {"capabilities": ("fs:read",),
                                                       "cost": {"cpux": 1}}))
    assert "cpux" in message and "cpu" in message, (
        "the refusal of the counter 'cpux' does not name it and suggest 'cpu': %r"
        % (message,))
    message = _refuses(s.ToolError, "a cost that is not a mapping",
                       lambda: s.parse_tool("reader", {"capabilities": ("fs:read",),
                                                       "cost": 3}))
    assert "cost" in message, (
        "the refusal of a non-mapping cost does not name the field: %r"
        % (message,))
    message = _refuses(s.ToolError, "a tool name that is not a str",
                       lambda: s.parse_tool(7, {"capabilities": ("fs:read",)}))
    assert "str" in message and "7" in message, (
        "the refusal of the tool name 7 does not name the offender: %r"
        % (message,))
    message = _refuses(s.ToolError, "a declaration that is not a mapping",
                       lambda: s.parse_tool("reader", 3))
    assert "mapping" in message and "3" in message, (
        "the refusal of a declaration that is a number does not name its shape: "
        "%r" % (message,))
    message = _refuses(s.ToolError, "a description that is not a str",
                       lambda: s.parse_tool("reader", {"capabilities": ("fs:read",),
                                                       "description": 3}))
    assert "description" in message, (
        "the refusal of a non-str description does not name the field: %r"
        % (message,))
    message = _refuses(s.ToolError, "a declaration with no demand",
                       lambda: s.parse_tool("reader", {"description": "x"}))
    assert "capabilities" in message, (
        "the refusal of a declaration with no demand does not name the field: %r"
        % (message,))
    message = _refuses(s.ToolError, "a declaration parsed under another name",
                       lambda: s.parse_tool("writer",
                                            {"name": "reader",
                                             "capabilities": ("fs:read",)}))
    assert "reader" in message and "writer" in message, (
        "the refusal of a declaration parsed under the wrong name does not name "
        "both: %r" % (message,))
    message = _refuses(s.ToolError, "a demand that repeats, through parse_tool",
                       lambda: s.parse_tool("reader",
                                            {"capabilities": ("fs:read",
                                                              "fs:read")}))
    assert "fs:read" in message, (
        "the refusal of a repeated demand through parse_tool does not name it: "
        "%r" % (message,))
    fields = {"capabilities": ("fs:read",), "cost": {"cpu": 2}}
    before = repr(sorted(fields.items()))
    s.parse_tool("reader", fields)
    assert repr(sorted(fields.items())) == before, (
        "parse_tool bent the caller's mapping: %r" % (fields,))

    # ---- the fixtures: the world's own tools parse to what the world ships --

    for name in sorted(world.TOOLS):
        if name == "teleport":
            message = _refuses(s.ToolError, "the teleport tool",
                               lambda name=name: s.parse_tool(
                                   name, world.tool(name)))
            assert "fs:teleport" in message, (
                "the teleport tool is not refused for the capability it demands: "
                "%r" % (message,))
            continue
        assert s.parse_tool(name, world.tool(name)) == dict(world.TOOLS[name]), (
            "%s does not parse to the record the world ships" % (name,))

    # ---- parse_call: the fields a kind carries ---------------------------

    call = s.parse_call({"tool": "read_file",
                         "target": "/home/agent/notes.md"})
    assert tuple(call) == s.CALL_KEYS, (
        "a parsed call carries %r, not exactly CALL_KEYS in order" % (tuple(call),))
    assert call == {"tool": "read_file", "target": "/home/agent/notes.md",
                    "value": ""}, (
        "a minimal call parses to %r, not to its defaults" % (call,))
    assert s.parse_call({"tool": "env_dump"}) == {"tool": "env_dump",
                                                  "target": "", "value": ""}, (
        "a call to a tool that acts on nothing does not default both fields")
    assert s.parse_call({"tool": "http_get", "target": "api.internal"}) == {
        "tool": "http_get", "target": "api.internal", "value": ""}, (
        "a call to a host tool does not keep its target")
    message = _refuses(s.ToolError, "a path tool with no target",
                       lambda: s.parse_call({"tool": "read_file"}))
    assert "read_file" in message and "target" in message, (
        "the refusal of a target-less read_file does not name the tool and the "
        "missing target: %r" % (message,))
    message = _refuses(s.ToolError, "a target on a tool that acts on nothing",
                       lambda: s.parse_call({"tool": "env_dump",
                                             "target": "/home/agent/.env"}))
    assert "env_dump" in message and "target" in message, (
        "the refusal of a target on env_dump does not name the tool and the "
        "field: %r" % (message,))
    message = _refuses(s.ToolError, "a value on a tool that writes nothing",
                       lambda: s.parse_call({"tool": "read_file",
                                             "target": "/home/agent/notes.md",
                                             "value": "tomato"}))
    assert "read_file" in message, (
        "the refusal of a value on read_file does not name the tool: %r"
        % (message,))
    assert s.parse_call({"tool": "write_file",
                         "target": "/home/agent/report.md",
                         "value": "published\n"})["value"] == "published\n", (
        "a value on a writer is not carried")
    assert s.parse_call({"tool": "shell", "target": "/home/agent",
                         "value": "ls"})["value"] == "ls", (
        "a value on a process tool is not carried")
    message = _refuses(s.ToolError, "a call that names no tool",
                       lambda: s.parse_call({"target": "/home/agent/notes.md"}))
    assert "tool" in message, (
        "the refusal of a call with no tool does not name the field: %r"
        % (message,))
    message = _refuses(s.ToolError, "a call to a tool nobody has",
                       lambda: s.parse_call({"tool": "read_fil",
                                             "target": "/x"}))
    assert "read_fil" in message and "read_file" in message, (
        "the refusal of 'read_fil' does not name it and suggest 'read_file': %r"
        % (message,))
    message = _refuses(s.ToolError, "a call with a foreign field",
                       lambda: s.parse_call({"tool": "env_dump", "toolz": 1}))
    assert "toolz" in message and "tool" in message, (
        "the refusal of the call field 'toolz' does not name it and suggest the "
        "real one: %r" % (message,))
    message = _refuses(s.ToolError, "a call whose tool is not a str",
                       lambda: s.parse_call({"tool": 7}))
    assert "str" in message and "7" in message, (
        "the refusal of the tool name 7 does not name the offender: %r"
        % (message,))
    message = _refuses(s.ToolError, "a call that is not a mapping",
                       lambda: s.parse_call(("read_file",)))
    assert "mapping" in message, (
        "the refusal of a non-mapping call does not name its shape: %r"
        % (message,))
    message = _refuses(s.ToolError, "a target that is not a str",
                       lambda: s.parse_call({"tool": "read_file", "target": 3}))
    assert "target" in message, (
        "the refusal of a non-str target does not name the field: %r" % (message,))
    message = _refuses(s.ToolError, "a value that is not a str",
                       lambda: s.parse_call({"tool": "write_file",
                                             "target": "/x", "value": 3}))
    assert "value" in message, (
        "the refusal of a non-str value does not name the field: %r" % (message,))

    # ---- the declaration gate: a call to a tool nobody can grant ---------

    message = _refuses(s.ToolError, "a call to the world's teleport",
                       lambda: s.parse_call({"tool": "teleport",
                                             "target": "/home/agent/notes.md"}))
    assert "fs:teleport" in message, (
        "a call to teleport is not refused for the capability its declaration "
        "demands: a plan that names a tool no grant can cover must be refused "
        "before the run starts, not survive until a grant is computed: %r"
        % (message,))

    # ---- the plans: what parses, and what must not ------------------------

    for name in sorted(world.PLANS):
        if name == "broken":
            continue
        for entry in world.plan(name):
            parsed = s.parse_call(entry)
            assert parsed["tool"] == entry["tool"], (
                "the plan %r no longer parses to its own tool" % (name,))
    message = _refuses(s.ToolError, "the first call of the broken plan",
                       lambda: s.parse_call(world.plan("broken")[0]))
    assert "fs:teleport" in message, (
        "the broken plan's teleport call is not refused: %r" % (message,))
    unresolved = s.parse_call(world.plan("broken")[1])
    assert unresolved == {"tool": "read_file",
                          "target": "/home/agent/../etc/passwd", "value": ""}, (
        "the broken plan's second call must parse: a `..` in a path is stage 3's "
        "business, and this stage must not pretend to have resolved it: %r"
        % (unresolved,))

    print("check_01: the vocabulary — six capabilities, five declaration fields "
          "and three call fields in declared order; a demand read as one sorted "
          "tuple and refused when it repeats, empties or names a capability the "
          "world does not have; declarations that materialise their defaults, "
          "refuse a foreign field, a bool, a float and a negative counter by "
          "name, and parse every tool the world ships to the record it ships; "
          "and calls whose target and value are decided by the tool's kind and "
          "its demand, with a call to `teleport` refused for its declaration "
          "before its target is looked at")

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "sandbox-capabilities-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J4_REPO=/path/to/forja")

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

    import stage_01 as one
    import stage_02 as s
    import tools as world

    # ---- the policy keys and the family ----------------------------------

    assert s.POLICY_KEYS == ("principal", "root", "capabilities", "hosts"), (
        "this stage's policy fields are %r, not the four the course defined"
        % (s.POLICY_KEYS,))
    assert issubclass(s.GrantError, s.SandboxError), (
        "%r is not a %s: one `except SandboxError` must still catch a grant this "
        "stage refuses" % (s.GrantError, s.SandboxError.__name__))
    assert issubclass(s.GrantError, ValueError), (
        "%r is not a ValueError: the course's refusal is a named error a caller "
        "can catch" % (s.GrantError,))

    # ---- grant: the value, its order, its refusals -----------------------

    record = s.grant("intern", ())
    assert tuple(record) == ("principal", "capabilities"), (
        "a grant carries %r, not exactly its two keys in order" % (tuple(record),))
    assert record == {"principal": "intern", "capabilities": ()}, (
        "a grant with no capabilities carries %r, not the empty tuple: a "
        "principal with nothing is the most important fixture in the course"
        % (record,))
    assert isinstance(record["capabilities"], tuple), (
        "a grant's capabilities are %r, not a tuple"
        % (record["capabilities"],))
    assert s.grant("builder", ("proc:spawn", "fs:read")) == {
        "principal": "builder", "capabilities": ("fs:read", "proc:spawn")}, (
        "a grant written in the other order reads %r: a grant is a set, and a "
        "program that compares them positionally answers differently depending on "
        "how somebody typed a tuple" % (s.grant("builder", ("proc:spawn", "fs:read")),))
    assert s.grant("auditor", ["fs:read"]) == {"principal": "auditor",
                                               "capabilities": ("fs:read",)}, (
        "a grant handed over as a list is not read as a grant")
    message = _refuses(s.GrantError, "a blank principal",
                       lambda: s.grant("  ", ("fs:read",)))
    assert "principal" in message and "'  '" in message, (
        "the refusal of a blank principal does not name the field and the "
        "offender: %r" % (message,))
    message = _refuses(s.GrantError, "an empty principal",
                       lambda: s.grant("", ("fs:read",)))
    assert "principal" in message, (
        "the refusal of an empty principal does not name the field: %r" % (message,))
    message = _refuses(s.GrantError, "a principal that is not a str",
                       lambda: s.grant(7, ("fs:read",)))
    assert "str" in message and "7" in message, (
        "the refusal of the principal 7 does not name its shape and the offender: "
        "%r" % (message,))
    message = _refuses(s.GrantError, "a grant that repeats a capability",
                       lambda: s.grant("analyst", ("fs:read", "fs:read")))
    assert "fs:read" in message, (
        "the refusal of a repeated capability does not name it: %r" % (message,))
    message = _refuses(s.GrantError, "a set handed over as a str",
                       lambda: s.grant("analyst", "fs:read"))
    assert "fs:read" in message and "str" in message, (
        "the refusal of the str 'fs:read' does not name it and its shape: a str "
        "is iterable, and a grant read one character at a time is the bug this "
        "stage exists for: %r" % (message,))
    message = _refuses(s.GrantError, "a set that is not a sequence at all",
                       lambda: s.grant("analyst", 7))
    assert "7" in message, (
        "the refusal of the capabilities 7 does not name the offender: %r"
        % (message,))
    message = _refuses(s.GrantError, "a capability that is a typo",
                       lambda: s.grant("analyst", ("fs:reed",)))
    assert "fs:reed" in message and "fs:read" in message, (
        "the refusal of 'fs:reed' does not name it and suggest the real "
        "capability: %r" % (message,))
    message = _refuses(s.GrantError, "a capability the world does not have",
                       lambda: s.grant("analyst", ("fs:teleport",)))
    assert "fs:teleport" in message, (
        "the refusal of 'fs:teleport' does not name it: %r" % (message,))

    # ---- granted: the principal's own tuple, or nothing ------------------

    assert world.GRANTS["intern"] == (), (
        "the world's own intern fixture holds %r, not nothing"
        % (world.GRANTS["intern"],))
    assert s.granted(world.GRANTS, "intern") == (), (
        "the intern's grant reads %r, not the empty tuple: a principal with "
        "nothing must not read as 'no restriction'"
        % (s.granted(world.GRANTS, "intern"),))
    assert isinstance(s.granted(world.GRANTS, "intern"), tuple), (
        "the intern's grant is %r, not a tuple" % (s.granted(world.GRANTS, "intern"),))
    assert s.granted(world.GRANTS, "auditor") == ("fs:read",), (
        "the auditor's grant reads %r, not one capability"
        % (s.granted(world.GRANTS, "auditor"),))
    assert s.granted(world.GRANTS, "nobody") == (), (
        "a principal the grants do not name holds %r: it holds nothing, and "
        "refusing it here is `policy_for`'s job"
        % (s.granted(world.GRANTS, "nobody"),))
    assert s.granted({}, "nobody") == (), (
        "an empty grants table does not read as every principal holding nothing")
    message = _refuses(s.GrantError, "a principal that is not a str",
                       lambda: s.granted(world.GRANTS, 7))
    assert "str" in message and "7" in message, (
        "the refusal of the principal 7 does not name the offender: %r"
        % (message,))
    message = _refuses(s.GrantError, "a grants table that is not a mapping",
                       lambda: s.granted(7, "intern"))
    assert "mapping" in message and "7" in message, (
        "the refusal of the grants table 7 does not name its shape and the "
        "offender: %r" % (message,))

    # ---- effective, missing, permits: the intersection -------------------

    demand = world.tool("debug_dump")
    assert one.declares(demand) == ("fs:read", "net:connect"), (
        "the world's debug_dump no longer demands two capabilities: %r"
        % (one.declares(demand),))
    assert s.effective(world.GRANTS, "analyst", demand) == ("fs:read",
                                                            "net:connect"), (
        "the analyst holds both halves and the tool demands both: effective is %r"
        % (s.effective(world.GRANTS, "analyst", demand),))
    assert s.missing(world.GRANTS, "analyst", demand) == (), (
        "the analyst covers debug_dump and nothing is missing: %r"
        % (s.missing(world.GRANTS, "analyst", demand),))
    assert s.permits(world.GRANTS, "analyst", demand) is True, (
        "the analyst holds both of debug_dump's capabilities and does not permit "
        "it")
    assert s.effective(world.GRANTS, "builder", demand) == ("fs:read",), (
        "the builder holds one half of debug_dump's demand and effective is %r"
        % (s.effective(world.GRANTS, "builder", demand),))
    assert s.missing(world.GRANTS, "builder", demand) == ("net:connect",), (
        "the half-grant of debug_dump is %r, not exactly the missing capability"
        % (s.missing(world.GRANTS, "builder", demand),))
    assert s.permits(world.GRANTS, "builder", demand) is False, (
        "the builder holds one half of the demand and permits the whole tool")
    read_file = world.tool("read_file")
    assert s.effective(world.GRANTS, "intern", read_file) == (), (
        "the intern holds nothing and effective is %r"
        % (s.effective(world.GRANTS, "intern", read_file),))
    assert s.missing(world.GRANTS, "intern", read_file) == ("fs:read",), (
        "the intern's missing capability is %r"
        % (s.missing(world.GRANTS, "intern", read_file),))
    assert s.permits(world.GRANTS, "intern", read_file) is False, (
        "the intern holds nothing and permits a read")
    assert s.missing(world.GRANTS, "nobody", demand) == ("fs:read",
                                                         "net:connect"), (
        "`missing` for a principal the grants do not name is %r, not the whole "
        "demand: a principal with nothing is a value, not a configuration error, "
        "and the refusal belongs to `policy_for`"
        % (s.missing(world.GRANTS, "nobody", demand),))

    # a principal holding exactly one capability must not permit two
    one_capability = {"p": ("fs:read",)}
    assert s.permits(one_capability, "p", demand) is False, (
        "a principal holding exactly one capability permits a tool that demands "
        "two: this is the `bool(granted(...))` mistake")
    assert s.missing(one_capability, "p", demand) == ("net:connect",), (
        "a one-capability principal's missing half is %r"
        % (s.missing(one_capability, "p", demand),))
    assert s.effective(one_capability, "p", demand) == ("fs:read",), (
        "a one-capability principal's intersection is %r"
        % (s.effective(one_capability, "p", demand),))
    both = {"p": ("fs:read", "net:connect")}
    assert s.permits(both, "p", demand) is True, (
        "a principal holding both capabilities does not permit the tool")

    # the difference is a sorted, repeat-free tuple
    raw = {"capabilities": ("proc:spawn", "secret:read", "fs:write", "fs:delete")}
    difference = s.missing({}, "p", raw)
    assert isinstance(difference, tuple), (
        "`missing` returns %r, not a tuple" % (difference,))
    assert difference == ("fs:delete", "fs:write", "proc:spawn", "secret:read"), (
        "`missing` returns %r, not the difference sorted" % (difference,))
    assert list(difference) == sorted(set(difference)), (
        "`missing` returns %r, which is not sorted or repeats a capability"
        % (difference,))
    assert s.effective({}, "p", raw) == (), (
        "a principal holding nothing has no intersection with a four-capability "
        "demand: %r" % (s.effective({}, "p", raw),))
    assert s.effective({"p": ("fs:write", "net:connect")}, "p", raw) == (
        "fs:write",), (
        "the intersection of a four-capability demand and a two-capability grant "
        "is %r" % (s.effective({"p": ("fs:write", "net:connect")}, "p", raw),))

    # a raw declaration and a parsed record are both readable
    assert s.missing(world.GRANTS, "intern", {"capabilities": ("fs:read",)}) == (
        "fs:read",), (
        "a raw declaration mapping is not read by `missing`")
    parsed = one.parse_tool("reader", {"capabilities": ("net:connect", "fs:read"),
                                       "target_kind": "path"})
    assert s.effective(world.GRANTS, "analyst", parsed) == ("fs:read",
                                                           "net:connect"), (
        "a parsed record is not read by `effective`")

    # the caller's own mapping is not bent
    caller = {"p": ("fs:read",)}
    s.granted(caller, "p")
    s.missing(caller, "p", demand)
    s.effective(caller, "p", demand)
    s.permits(caller, "p", demand)
    assert caller == {"p": ("fs:read",)}, (
        "the six functions bent the caller's grants mapping: %r" % (caller,))
    before = repr(sorted(world.GRANTS.items()))
    s.missing(world.GRANTS, "builder", demand)
    s.effective(world.GRANTS, "auditor", demand)
    assert repr(sorted(world.GRANTS.items())) == before, (
        "a function bent the world's own grants table")

    # ---- policy_for: the four fields, the fixtures, the refusals ---------

    policy = s.policy_for("intern")
    assert tuple(policy) == s.POLICY_KEYS, (
        "a policy carries %r, not exactly POLICY_KEYS in order" % (tuple(policy),))
    assert policy == {"principal": "intern", "root": "/home/agent/src",
                      "capabilities": (), "hosts": ()}, (
        "the intern's policy is %r: its root is narrower and it holds nothing and "
        "reaches nothing" % (policy,))
    assert world.ALLOWED["auditor"] == ("*",), (
        "the world's own auditor allowlist is %r, not the one wildcard"
        % (world.ALLOWED["auditor"],))
    assert s.policy_for("auditor") == {"principal": "auditor",
                                       "root": "/home/agent",
                                       "capabilities": ("fs:read",),
                                       "hosts": ("*",)}, (
        "the auditor's policy is %r: it holds `fs:read` and no `net:connect`, "
        "while its hosts entry is the wildcard" % (s.policy_for("auditor"),))
    assert s.policy_for("builder")["capabilities"] == world.GRANTS["builder"], (
        "a policy re-sorts the fixture's capabilities (%r, not %r): a policy "
        "reports what the world configured, in the order it configured it"
        % (s.policy_for("builder")["capabilities"], world.GRANTS["builder"]))
    assert s.policy_for("intern", grants={}, hosts={"intern": ()},
                        roots={"intern": "/home/agent"})["capabilities"] == (), (
        "a principal known only through the roots and the hosts is not known to "
        "`policy_for`: the three fixtures are one set of principals")
    message = _refuses(s.GrantError, "a principal nobody configured",
                       lambda: s.policy_for("audit"))
    assert "audit" in message and "auditor" in message, (
        "the refusal of 'audit' does not name it and suggest 'auditor': %r"
        % (message,))
    message = _refuses(s.GrantError, "a principal nobody could have meant",
                       lambda: s.policy_for("zebra"))
    assert "zebra" in message and "did you mean" not in message, (
        "the refusal of 'zebra' suggests a name anyway: a suggestion that is not "
        "close is a lie, and the distance is two: %r" % (message,))
    message = _refuses(s.GrantError, "a principal exactly three edits away",
                       lambda: s.policy_for("anal"))
    assert "anal" in message and "did you mean" not in message, (
        "the refusal of 'anal' suggests 'analyst': a name exactly three edits "
        "away is not a typo, and the distance is two: %r" % (message,))
    message = _refuses(s.GrantError, "a principal that is not a str",
                       lambda: s.policy_for(7))
    assert "7" in message, (
        "the refusal of the principal 7 does not name the offender: %r"
        % (message,))
    message = _refuses(s.GrantError, "a root that is not absolute",
                       lambda: s.policy_for("intern",
                                            roots={"intern": "relative/path"}))
    assert "intern" in message and "relative/path" in message, (
        "the refusal of the relative root does not name the principal and the "
        "offender: %r" % (message,))
    message = _refuses(s.GrantError, "a root that is empty",
                       lambda: s.policy_for("intern", roots={"intern": ""}))
    assert "root" in message, (
        "the refusal of an empty root does not name the field: %r" % (message,))
    message = _refuses(s.GrantError, "a root that is not a str",
                       lambda: s.policy_for("intern", roots={"intern": 7}))
    assert "7" in message, (
        "the refusal of the root 7 does not name the offender: %r" % (message,))
    message = _refuses(s.GrantError, "a principal with no root entry",
                       lambda: s.policy_for("intern", roots={}))
    assert "intern" in message and "root" in message, (
        "the refusal of a principal with no root entry does not name the "
        "principal and the missing field: %r" % (message,))
    message = _refuses(s.GrantError, "hosts handed over as a str",
                       lambda: s.policy_for("intern",
                                            hosts={"intern": "api.internal:443"}))
    assert "api.internal:443" in message and "str" in message, (
        "the refusal of a hosts entry that is a str does not name it and its "
        "shape: iterating it would read one character at a time: %r" % (message,))
    message = _refuses(s.GrantError, "a host spec that is not a str",
                       lambda: s.policy_for("intern",
                                            hosts={"intern": ("api.internal:443", 7)}))
    assert "7" in message, (
        "the refusal of the host spec 7 does not name the offender: %r"
        % (message,))
    message = _refuses(s.GrantError, "a hosts entry that is not a sequence",
                       lambda: s.policy_for("intern", hosts={"intern": 7}))
    assert "7" in message and "intern" in message, (
        "the refusal of the hosts entry 7 does not name the principal and the "
        "offender: %r" % (message,))
    message = _refuses(s.GrantError, "capabilities handed over as a str",
                       lambda: s.policy_for("intern", grants={"intern": "fs:read"}))
    assert "fs:read" in message and "str" in message, (
        "the refusal of a policy's capabilities handed over as a str does not "
        "name it and its shape: %r" % (message,))
    message = _refuses(s.GrantError, "capabilities that are not a sequence",
                       lambda: s.policy_for("intern", grants={"intern": 7}))
    assert "7" in message and "intern" in message, (
        "the refusal of the capabilities 7 does not name the principal and the "
        "offender: %r" % (message,))
    message = _refuses(s.GrantError, "a policy capability the world has not got",
                       lambda: s.policy_for("intern",
                                            grants={"intern": ("fs:teleport",)}))
    assert "fs:teleport" in message, (
        "the refusal of 'fs:teleport' in a policy does not name it: %r"
        % (message,))
    message = _refuses(s.GrantError, "a grants table that is not a mapping",
                       lambda: s.policy_for("intern", grants=3))
    assert "mapping" in message and "3" in message, (
        "the refusal of the grants table 3 does not name its shape and the "
        "offender: %r" % (message,))

    # the contents of a root and of a host spec are stage 3's and stage 4's
    assert s.policy_for("intern", roots={"intern": "/home/agent/../agent"})[
        "root"] == "/home/agent/../agent", (
        "`policy_for` resolved or normalised a root: resolving is stage 3's job")
    assert s.policy_for("intern", hosts={"intern": ("*.internal",)})[
        "hosts"] == ("*.internal",), (
        "`policy_for` judged a host spec: whether a wildcard in the middle is a "
        "policy is stage 4's rule")

    # the tables are not bent
    tables = ({"intern": ()}, {"intern": ("*",)}, {"intern": "/home/agent"})
    before = repr(tables)
    s.policy_for("intern", grants=tables[0], hosts=tables[1], roots=tables[2])
    assert repr(tables) == before, (
        "`policy_for` bent one of the three tables it was handed: %r" % (tables,))

    print("check_02: the grant — a principal's capabilities as one sorted tuple "
          "and a blank principal, a repeat, a str and an unknown name each "
          "refused by name; `intern`'s empty grant read as nothing and never as "
          "'no restriction'; the intersection, the difference and `permits` "
          "deciding `debug_dump` against `builder`'s half-grant; and the four "
          "policy fields assembled from the three fixtures, with a principal "
          "nobody configured refused by name and the contents of a root and a "
          "host spec left to stage 3 and stage 4")

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "sandbox-capabilities-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J4_REPO=/path/to/forja")

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

    import stage_01
    import stage_03 as s
    import tools as world
    import vfs as fs

    root = fs.DEFAULT_ROOT
    sibling = fs.SIBLING

    # ---- the family and the path constants --------------------------------

    assert root == "/home/agent" and sibling == "/home/agent-other", (
        "the world's roots are not the fixtures this stage is written around: %r "
        "and %r" % (root, sibling))
    assert issubclass(s.JailError, stage_01.SandboxError), (
        "%r is not a %s: one `except SandboxError` must still catch a path "
        "outside a jail" % (s.JailError, stage_01.SandboxError.__name__))
    assert issubclass(s.JailError, ValueError), (
        "%r is not a ValueError: the course's refusal is a named error a caller "
        "can catch" % (s.JailError,))
    assert s.SEPARATOR == "/", (
        "SEPARATOR is %r, not the character a path is split on" % (s.SEPARATOR,))
    assert (s.CURRENT, s.PARENT) == (".", ".."), (
        "the component names are %r, not the two a path carries"
        % ((s.CURRENT, s.PARENT),))

    # ---- resolve: the normalisation ---------------------------------------

    assert s.resolve(root, "/home/agent") == "/home/agent", (
        "an absolute path does not resolve to itself: %r"
        % (s.resolve(root, "/home/agent"),))
    assert s.resolve(root, "/home/agent/") == "/home/agent", (
        "a trailing slash is not a component and must drop: %r"
        % (s.resolve(root, "/home/agent/"),))
    assert s.resolve(root, "/home/agent/./notes.md") == "/home/agent/notes.md", (
        "a `.` in the middle is kept as a component: %r"
        % (s.resolve(root, "/home/agent/./notes.md"),))
    assert s.resolve(root, "/home/agent//src///main.py") == (
        "/home/agent/src/main.py"), (
        "empty components are not dropped: %r"
        % (s.resolve(root, "/home/agent//src///main.py"),))
    assert s.resolve(root, "/home/agent/../../etc") == "/etc", (
        "`..` is clamped to the root instead of applied: %r"
        % (s.resolve(root, "/home/agent/../../etc"),))
    assert s.resolve(root, "/home/agent/../../etc/passwd") == "/etc/passwd", (
        "`/home/agent/../../etc/passwd` does not resolve to `/etc/passwd`: %r"
        % (s.resolve(root, "/home/agent/../../etc/passwd"),))
    assert s.resolve(root, "/home/agent/../etc/passwd") == "/home/etc/passwd", (
        "one `..` pops one component: `/home/agent/../etc/passwd` is "
        "`/home/etc/passwd`, which is still outside the root: %r"
        % (s.resolve(root, "/home/agent/../etc/passwd"),))
    assert s.resolve(root, "/home/agent/../../../..") == "/", (
        "popping past `/` does not stay at `/`: %r"
        % (s.resolve(root, "/home/agent/../../../.."),))
    assert s.resolve(root, "/") == "/", (
        "the root path does not resolve to itself: %r"
        % (s.resolve(root, "/"),))
    assert s.resolve("/", "/home/agent/../../etc") == "/etc", (
        "a request against the filesystem root does not resolve: %r"
        % (s.resolve("/", "/home/agent/../../etc"),))
    assert s.resolve(root, "/etc/passwd") == "/etc/passwd", (
        "resolve decides containment; it must not refuse a path outside the root: "
        "%r" % (s.resolve(root, "/etc/passwd"),))

    message = _refuses(s.JailError, "a requested path that is not a str",
                       lambda: s.resolve(root, 7))
    assert "str" in message and "7" in message, (
        "the refusal of the request 7 does not name its shape and the offender: "
        "%r" % (message,))
    message = _refuses(s.JailError, "an empty request",
                       lambda: s.resolve(root, ""))
    assert "empty" in message, (
        "the refusal of an empty request does not say why: %r" % (message,))
    message = _refuses(s.JailError, "a relative request",
                       lambda: s.resolve(root, "a/b"))
    assert "a/b" in message and "absolute" in message, (
        "the refusal of the relative request 'a/b' does not name it and say it "
        "must be absolute: %r" % (message,))
    message = _refuses(s.JailError, "a root that is not a str",
                       lambda: s.resolve(7, "/home/agent"))
    assert "str" in message and "7" in message, (
        "the refusal of the root 7 does not name its shape and the offender: %r"
        % (message,))
    message = _refuses(s.JailError, "a root that is empty",
                       lambda: s.resolve("", "/home/agent"))
    assert "empty" in message, (
        "the refusal of an empty root does not say why: %r" % (message,))
    message = _refuses(s.JailError, "a root that is relative",
                       lambda: s.resolve("home/agent", "/home/agent"))
    assert "home/agent" in message, (
        "the refusal of the relative root does not name it: %r" % (message,))
    message = _refuses(s.JailError, "a root that carries a '.'",
                       lambda: s.resolve("/home/agent/./x", "/home/agent"))
    assert "component" in message and "/home/agent/./x" in message, (
        "the refusal of a root with a '.' does not name the path: %r" % (message,))
    message = _refuses(s.JailError, "a root that carries a '..'",
                       lambda: s.resolve("/home/agent/../agent", "/home/agent"))
    assert "component" in message and "/home/agent/../agent" in message, (
        "the refusal of a root with a '..' does not name the path: %r"
        % (message,))

    # ---- inside: components, never strings --------------------------------

    assert s.inside(root, root) is True, (
        "a root does not contain itself: the fixture `/home/agent` is outside "
        "its own jail")
    assert s.inside(root, "/home/agent/notes.md") is True, (
        "a file under the root is not inside it: %r"
        % (s.inside(root, "/home/agent/notes.md"),))
    assert s.inside(root, "/home/agent/src/main.py") is True, (
        "a file two components deep is not inside the root: %r"
        % (s.inside(root, "/home/agent/src/main.py"),))
    assert s.inside(root, "/home/agent-other/notes.md") is False, (
        "the sibling root %r is inside %r: this is the escape that is a string "
        "test, and `startswith` hands it over" % (sibling, root))
    assert s.inside(root, "/home/agent-other") is False, (
        "the sibling root %r is inside %r: its characters start with the root's, "
        "and its components do not" % (sibling, root))
    assert s.inside(root, "/home/agentx") is False, (
        "'/home/agentx' starts with '/home/agent' and is not inside it: a "
        "containment test on components must see the extra 'x'")
    assert s.inside(root, "/home") is False, (
        "the parent of the root is inside it: %r"
        % (s.inside(root, "/home"),))
    assert s.inside(root, "/") is False, (
        "the filesystem root is inside `/home/agent`: %r"
        % (s.inside(root, "/"),))
    assert s.inside("/home/agent/src", "/home/agent") is False, (
        "the parent of a root is inside it: %r"
        % (s.inside("/home/agent/src", "/home/agent"),))
    assert s.inside(sibling, sibling) is True, (
        "the sibling root does not contain itself")
    assert s.inside(sibling, "/home/agent-other/notes.md") is True, (
        "a file under the sibling root is not inside it: %r"
        % (s.inside(sibling, "/home/agent-other/notes.md"),))
    assert s.inside(sibling, "/home/agent/notes.md") is False, (
        "the default root is inside the sibling root: %r"
        % (s.inside(sibling, "/home/agent/notes.md"),))
    assert s.inside("/home//agent", "/home/agent") is True, (
        "an empty component is not dropped before the comparison: "
        "'/home//agent' does not read the same as '/home/agent'")

    message = _refuses(s.JailError, "a inside-root that is not a str",
                       lambda: s.inside(7, "/home/agent"))
    assert "str" in message and "7" in message, (
        "the refusal of the root 7 does not name its shape and the offender: %r"
        % (message,))
    message = _refuses(s.JailError, "a inside-root that is relative",
                       lambda: s.inside("home/agent", "/home/agent"))
    assert "home/agent" in message, (
        "the refusal of the relative root does not name it: %r" % (message,))
    message = _refuses(s.JailError, "an inside-root that carries a '..'",
                       lambda: s.inside("/home/agent/../agent", "/home/agent"))
    assert "component" in message and "/home/agent/../agent" in message, (
        "the refusal of a root with a '..' does not name the path: %r"
        % (message,))
    message = _refuses(s.JailError, "a resolved path that carries a '..'",
                       lambda: s.inside(root, "/home/agent/../etc"))
    assert "component" in message and "/home/agent/../etc" in message, (
        "the refusal of an unresolved path does not name the path: %r"
        % (message,))
    message = _refuses(s.JailError, "a resolved path that is not a str",
                       lambda: s.inside(root, 7))
    assert "str" in message and "7" in message, (
        "the refusal of the resolved path 7 does not name its shape: %r"
        % (message,))

    # ---- jail: resolve, then decide, then name all three -------------------

    assert s.jail(root, "/home/agent") == "/home/agent", (
        "the root itself is not inside its own jail: %r"
        % (s.jail(root, "/home/agent"),))
    assert s.jail(root, "/home/agent/./notes.md") == "/home/agent/notes.md", (
        "jail returns the raw request instead of the resolved path: %r"
        % (s.jail(root, "/home/agent/./notes.md"),))
    assert s.jail(root, "/home/agent/../agent/notes.md") == (
        "/home/agent/notes.md"), (
        "a path that wanders out and back is not resolved before deciding: %r"
        % (s.jail(root, "/home/agent/../agent/notes.md"),))
    assert s.jail(sibling, "/home/agent-other/notes.md") == (
        "/home/agent-other/notes.md"), (
        "a clean request inside the sibling root is not returned resolved: %r"
        % (s.jail(sibling, "/home/agent-other/notes.md"),))
    assert s.jail(world.ROOTS["intern"], "/home/agent/src/main.py") == (
        "/home/agent/src/main.py"), (
        "the intern's root %r does not jail its own file: %r"
        % (world.ROOTS["intern"], s.jail(world.ROOTS["intern"],
                                         "/home/agent/src/main.py")))

    message = _refuses(s.JailError, "the sibling root",
                       lambda: s.jail(root, "/home/agent-other/notes.md"))
    assert "/home/agent-other/notes.md" in message and root in message, (
        "the refusal of the sibling escape does not name both the request and "
        "the root: %r" % (message,))
    message = _refuses(s.JailError, "the passwd escape",
                       lambda: s.jail(root, "/home/agent/../etc/passwd"))
    assert ("/home/agent/../etc/passwd" in message
            and "/home/etc/passwd" in message and root in message), (
        "the refusal of `/home/agent/../etc/passwd` does not name the request, "
        "what it resolved to, and the root it is outside of: %r" % (message,))
    message = _refuses(s.JailError, "the broken plan's escape",
                       lambda: s.jail(root, world.plan("broken")[1]["target"]))
    assert "/home/etc/passwd" in message, (
        "the broken plan's `..` path is not refused with the resolved escape: %r"
        % (message,))
    message = _refuses(s.JailError, "a file above the intern's root",
                       lambda: s.jail(world.ROOTS["intern"],
                                      "/home/agent/notes.md"))
    assert world.ROOTS["intern"] in message, (
        "the refusal of a path above the intern's root does not name the root: "
        "%r" % (message,))
    message = _refuses(s.JailError, "a jail whose root is not normalised",
                       lambda: s.jail("/home/agent/../agent",
                                      "/home/agent/notes.md"))
    assert "/home/agent/../agent" in message, (
        "the refusal of a jail with a `..` in its root does not name the root: "
        "%r" % (message,))

    print("check_03: the path jail — a request resolved with `.` dropped and "
          "`..` applied, containment decided on components so that the sibling "
          "root never starts with the root, a root that is not already "
          "normalised refused rather than compared, and `jail` returning the "
          "resolved path or refusing with the request, the resolution and the "
          "root all named")

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "sandbox-capabilities-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J4_REPO=/path/to/forja")

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

    import stage_04 as s
    import tools as world

    # ---- the one spec, and the one refusal family -------------------------

    assert s.WILDCARD == "*", (
        "the wildcard spec reads %r: the one spec that means 'any host the world "
        "knows' is written `*` and nothing else" % (s.WILDCARD,))
    assert issubclass(s.SandboxError, ValueError), (
        "%r is not a ValueError: the course's refusal is a named error a caller "
        "can catch, and every later stage derives its own from it"
        % (s.SandboxError,))
    assert issubclass(s.HostError, s.SandboxError), (
        "%r is not a %s: one `except SandboxError` must still catch a broken "
        "network policy" % (s.HostError, s.SandboxError.__name__))

    # ---- parse_host: one spec, read one way -------------------------------

    assert s.parse_host("*") == ("*", 0), (
        "the wildcard spec reads %r: it is a host named `*` on no port at all, "
        "not a host on a guessed port" % (s.parse_host("*"),))
    assert s.parse_host("api.internal:443") == ("api.internal", 443), (
        "a `host:port` spec does not read as its two halves: %r"
        % (s.parse_host("api.internal:443"),))
    assert s.parse_host("api.internal:8443") == ("api.internal", 8443), (
        "a spec on a second port reads %r: the port is part of the host's "
        "identity, not a detail a default may overwrite"
        % (s.parse_host("api.internal:8443"),))
    for spec in ("api.internal:443", "registry.internal:5000",
                 "metrics.internal:9090", "public.example.com:443",
                 "db.internal:5432", "*"):
        if spec == "*":
            assert s.parse_host(spec) == ("*", 0), (
                "the world's own fixture spec %r does not read as the wildcard"
                % (spec,))
            continue
        name, text = spec.split(":")
        assert s.parse_host(spec) == (name, int(text)), (
            "the world's own fixture spec %r does not read as %r"
            % (spec, (name, int(text))))
    for principal in sorted(world.ALLOWED):
        for spec in world.ALLOWED[principal]:
            pair = s.parse_host(spec)
            assert pair == (("*", 0) if spec == "*" else (spec.split(":")[0],
                                                          int(spec.split(":")[1]))), (
                "the allowlist spec %r of principal %r reads %r"
                % (spec, principal, pair))

    message = _refuses(s.HostError, "a spec with no port",
                       lambda: s.parse_host("api.internal"))
    assert "api.internal" in message and "hole" in message, (
        "the refusal of a spec with no port does not name it and say what a "
        "missing port is: %r" % (message,))
    message = _refuses(s.HostError, "a spec on port zero",
                       lambda: s.parse_host("api.internal:0"))
    assert "api.internal:0" in message and "0" in message, (
        "the refusal of a spec on port zero does not name it: %r" % (message,))
    message = _refuses(s.HostError, "a spec whose port is not a number",
                       lambda: s.parse_host("api.internal:abc"))
    assert "api.internal" in message and "abc" in message, (
        "the refusal of the port 'abc' does not name it and the spec that "
        "carried it: %r" % (message,))
    message = _refuses(s.HostError, "a spec on a negative port",
                       lambda: s.parse_host("api.internal:-443"))
    assert "-443" in message, (
        "the refusal of a negative port does not name the offender: %r"
        % (message,))
    message = _refuses(s.HostError, "a spec whose port carries a sign",
                       lambda: s.parse_host("api.internal:+443"))
    assert "+443" in message, (
        "the refusal of the signed port '+443' does not name the offender: %r"
        % (message,))
    message = _refuses(s.HostError, "a spec whose port carries a space",
                       lambda: s.parse_host("api.internal: 443"))
    assert "api.internal: 443" in message, (
        "the refusal of a spec with a space in its port does not name it: %r"
        % (message,))
    message = _refuses(s.HostError, "a spec with two colons",
                       lambda: s.parse_host("api.internal:443:80"))
    assert "api.internal:443:80" in message, (
        "the refusal of a spec with two colons does not name it: %r" % (message,))
    message = _refuses(s.HostError, "a spec with no host",
                       lambda: s.parse_host(":443"))
    assert ":443" in message, (
        "the refusal of a spec with no host does not name it: %r" % (message,))
    message = _refuses(s.HostError, "an empty spec", lambda: s.parse_host(""))
    assert "empty" in message and "'*'" in message, (
        "the refusal of an empty spec does not say what an empty spec is and "
        "what the wildcard is spelled like: %r" % (message,))
    message = _refuses(s.HostError, "a spec that is not a str",
                       lambda: s.parse_host(7))
    assert "str" in message and "7" in message, (
        "the refusal of the spec 7 does not name its shape and the offender: %r"
        % (message,))

    message = _refuses(s.HostError, "a wildcard in the middle of a spec",
                       lambda: s.parse_host("*.internal"))
    assert "*.internal" in message and "*" in message, (
        "the refusal of '*.internal' does not name it: a wildcard a reader "
        "cannot evaluate is not a policy, and it is refused rather than matched "
        "as a pattern: %r" % (message,))
    message = _refuses(s.HostError, "a wildcard on the port side of a spec",
                       lambda: s.parse_host("api.*"))
    assert "api.*" in message, (
        "the refusal of 'api.*' does not name it: %r" % (message,))
    message = _refuses(s.HostError, "a wildcard in front of a port",
                       lambda: s.parse_host("*:443"))
    assert "*:443" in message, (
        "the refusal of '*:443' does not name it: the wildcard is the whole spec "
        "or it is not a spec: %r" % (message,))

    message = _refuses(s.HostError, "an upper-case host in a spec",
                       lambda: s.parse_host("API.internal:443"))
    assert "API.internal" in message, (
        "the refusal of 'API.internal:443' does not name it: this world's host "
        "names are lower case, and a name is refused rather than folded: %r"
        % (message,))
    assert "case" in message or "fold" in message, (
        "the refusal of an upper-case host does not say what is wrong with it: "
        "%r" % (message,))
    message = _refuses(s.HostError, "the world's own host in the wrong case",
                       lambda: s.parse_host("db.Internal:5432"))
    assert "db.Internal" in message, (
        "the refusal of 'db.Internal:5432' does not name it: %r" % (message,))

    # ---- allows: the pair, exactly ----------------------------------------

    assert s.allows(world.ALLOWED["analyst"], "api.internal", 443) is True, (
        "the analyst's own allowlist does not grant api.internal:443")
    assert s.allows(world.ALLOWED["analyst"], "api.internal", 8443) is False, (
        "api.internal:8443 is allowed although it is a different port from "
        "api.internal:443: the port is part of the identity, and a match that "
        "ignores it is a policy that grants ports nobody wrote down")
    assert s.allows(world.ALLOWED["analyst"], "registry.internal", 5000) is False, (
        "the analyst reaches registry.internal:5000 although the allowlist does "
        "not name it")
    assert s.allows(world.ALLOWED["analyst"], "api.internal.evil.com", 443) is False, (
        "api.internal.evil.com is allowed by an allowlist naming api.internal: a "
        "suffix rule is not a policy")
    assert s.allows(world.ALLOWED["analyst"], "evil-api.internal", 443) is False, (
        "evil-api.internal is allowed by an allowlist naming api.internal: a "
        "prefix or substring rule is not a policy")
    assert s.allows(world.ALLOWED["analyst"], "db.internal", 5432) is False, (
        "the analyst reaches db.internal:5432 although no principal's allowlist "
        "names it")
    assert s.allows(world.ALLOWED["builder"], "api.internal", 443) is True, (
        "the builder's allowlist does not grant its first spec")
    assert s.allows(world.ALLOWED["builder"], "registry.internal", 5000) is True, (
        "the builder's allowlist does not grant its second spec")
    assert s.allows(world.ALLOWED["builder"], "api.internal", 8443) is False, (
        "a two-spec allowlist grants a port neither spec names")
    for principal in ("intern", "vaultkeeper"):
        for name in sorted(world.HOSTS):
            assert s.allows(world.ALLOWED[principal], name,
                            world.HOSTS[name]["port"]) is False, (
                "the %s holds no net:connect and names no host, yet %s is "
                "allowed: an empty allowlist means none, never 'no restriction'"
                % (principal, name))
    assert s.allows((), "api.internal", 443) is False, (
        "an empty allowlist grants a host")
    assert s.allows(world.ALLOWED["auditor"], "db.internal", 5432) is True, (
        "the auditor is allowed every host the world knows, and db.internal:5432 "
        "is one of them")
    assert s.allows(world.ALLOWED["auditor"], "evil.internal", 443) is True, (
        "the single spec '*' must grant every host: whether the *world* has it "
        "is `reachable`'s question, not this one's")
    assert s.allows(world.ALLOWED["auditor"], "api.internal", 8443) is True, (
        "the single spec '*' must grant every port too")
    assert not any(spec.split(":")[0] == "db.internal"
                   for specs in world.ALLOWED.values() for spec in specs), (
        "a principal's allowlist now names db.internal: the fixture this stage "
        "is judged on is a real host no policy reads")

    message = _refuses(s.HostError, "an allowlist handed over as a str",
                       lambda: s.allows("api.internal:443", "api.internal", 443))
    assert "api.internal:443" in message and "allowlist" in message, (
        "the refusal of an allowlist handed over as a str does not name it and "
        "say what it is: iterating it reads one character at a time: %r"
        % (message,))
    message = _refuses(s.HostError, "an allowlist that is not a sequence",
                       lambda: s.allows(7, "api.internal", 443))
    assert "7" in message and "allowlist" in message, (
        "the refusal of the allowlist 7 does not name its shape and the "
        "offender: %r" % (message,))
    message = _refuses(s.HostError, "an allowlist that is a mapping",
                       lambda: s.allows({"api.internal:443": 1},
                                        "api.internal", 443))
    assert "allowlist" in message, (
        "the refusal of a mapping allowlist does not say what it is: %r"
        % (message,))
    message = _refuses(s.HostError, "a wildcard in the middle of an allowlist",
                       lambda: s.allows(("*.internal",), "api.internal", 443))
    assert "*.internal" in message, (
        "an unreadable spec inside an allowlist is not refused by name: a policy "
        "a reader cannot evaluate must be refused wherever it is read: %r"
        % (message,))
    message = _refuses(s.HostError, "a spec with no port inside an allowlist",
                       lambda: s.allows(("api.internal",), "api.internal", 443))
    assert "api.internal" in message and "hole" in message, (
        "the refusal of a spec with no port inside an allowlist does not name it: "
        "%r" % (message,))
    message = _refuses(s.HostError, "an allowlist carrying a non-str spec",
                       lambda: s.allows(("api.internal:443", 7),
                                        "api.internal", 443))
    assert "7" in message, (
        "the refusal of a non-str spec inside an allowlist does not name the "
        "offender: %r" % (message,))

    message = _refuses(s.HostError, "a host that is not a str",
                       lambda: s.allows((), 7, 443))
    assert "str" in message and "7" in message, (
        "the refusal of the host 7 does not name its shape and the offender: %r"
        % (message,))
    message = _refuses(s.HostError, "an empty host",
                       lambda: s.allows((), "", 443))
    assert "empty" in message, (
        "the refusal of an empty host does not say so: %r" % (message,))
    message = _refuses(s.HostError, "a port that is not an int",
                       lambda: s.allows((), "api.internal", "443"))
    assert "'443'" in message, (
        "the refusal of the port '443' does not name the offender: %r"
        % (message,))
    message = _refuses(s.HostError, "a port of zero",
                       lambda: s.allows((), "api.internal", 0))
    assert "0" in message, (
        "the refusal of port zero does not name the offender: %r" % (message,))
    message = _refuses(s.HostError, "a negative port",
                       lambda: s.allows((), "api.internal", -1))
    assert "-1" in message, (
        "the refusal of port -1 does not name the offender: %r" % (message,))
    message = _refuses(s.HostError, "a port that is a bool",
                       lambda: s.allows((), "api.internal", True))
    assert "True" in message, (
        "the refusal of the port True does not name the offender: `True` is an "
        "int in Python and is not a port: %r" % (message,))
    message = _refuses(s.HostError, "an upper-case host asked about",
                       lambda: s.allows(world.ALLOWED["analyst"], "API.INTERNAL",
                                        443))
    assert "API.INTERNAL" in message, (
        "the refusal of an upper-case host does not name it: a comparison that "
        "folded the name would match here and fail in production: %r"
        % (message,))

    # ---- reachable: allowed, and in the world ----------------------------

    wire = world.Wire()
    assert s.reachable(wire, world.ALLOWED["analyst"], "api.internal", 443) is True, (
        "api.internal:443 is both allowed and in the catalogue, and is not "
        "reachable")
    assert s.reachable(wire, world.ALLOWED["analyst"], "api.internal", 8443) is False, (
        "api.internal:8443 is reachable although the catalogue answers on 443 "
        "and the allowlist names 443")
    assert s.reachable(wire, world.ALLOWED["analyst"], "registry.internal", 5000) is False, (
        "the analyst reaches registry.internal:5000 although the allowlist does "
        "not name it")
    assert s.reachable(wire, world.ALLOWED["auditor"], "db.internal", 5432) is True, (
        "the auditor is allowed every host and db.internal:5432 is in the "
        "catalogue, so it is reachable — the host whose allowlist entry no "
        "principal's list names but whose reachability the world decides")
    assert s.reachable(wire, world.ALLOWED["auditor"], "evil.internal", 443) is False, (
        "a policy of '*' reaches a host the catalogue does not have: a policy "
        "cannot grant a host that does not exist, and this is the question the "
        "world is consulted for")
    assert s.reachable(wire, world.ALLOWED["auditor"], "public.example.com", 8443) is False, (
        "public.example.com:8443 is reachable although the catalogue answers on "
        "443")
    assert s.reachable(wire, world.ALLOWED["builder"], "registry.internal", 5000) is True, (
        "the builder's own allowed pair is not reachable")
    assert s.reachable(wire, world.ALLOWED["intern"], "api.internal", 443) is False, (
        "the intern reaches api.internal:443 although it names no host")
    assert s.reachable(wire, (), "api.internal", 443) is False, (
        "an empty allowlist reaches a host")
    assert s.reachable(wire, world.ALLOWED["auditor"], "db.internal", 443) is False, (
        "db.internal:443 is reachable although the catalogue answers on 5432")
    message = _refuses(s.HostError, "an upper-case host on the wire",
                       lambda: s.reachable(wire, world.ALLOWED["auditor"],
                                           "API.internal", 443))
    assert "API.internal" in message, (
        "`reachable` answered about an upper-case host instead of refusing it: "
        "the pair is validated the same way at every door: %r" % (message,))
    message = _refuses(s.HostError, "a port of zero on the wire",
                       lambda: s.reachable(wire, world.ALLOWED["auditor"],
                                           "api.internal", 0))
    assert "0" in message, (
        "`reachable` answered about port zero instead of refusing it: %r"
        % (message,))
    message = _refuses(s.HostError, "an allowlist handed over as a str, on the "
                                    "wire",
                       lambda: s.reachable(wire, "api.internal:443",
                                           "api.internal", 443))
    assert "api.internal:443" in message and "allowlist" in message, (
        "`reachable` read an allowlist handed over as a str character by "
        "character: %r" % (message,))
    assert wire.dialled() == (), (
        "asking whether a host is reachable dialled it: the world's record now "
        "holds a dial nobody made, and a question is not a touch: %r"
        % (wire.dialled(),))

    # ---- target: the world's own record ----------------------------------

    for name in sorted(world.HOSTS):
        port = world.HOSTS[name]["port"]
        record = s.target(wire, world.ALLOWED["auditor"], name, port)
        assert tuple(record) == ("host", "port", "bytes"), (
            "the record for %s carries %r, not the world's three fields in order"
            % (name, tuple(record)))
        assert record == world.host(name, port), (
            "the record for %s is %r, not the record the world ships: %r"
            % (name, record, world.host(name, port)))
        assert record["bytes"] == world.HOSTS[name]["bytes"], (
            "the bytes of %s read %r and not the world's own %r: bytes taken "
            "from the policy are a number the wire never agreed to"
            % (name, record["bytes"], world.HOSTS[name]["bytes"]))
    record = s.target(wire, world.ALLOWED["analyst"], "db.internal", 5432)
    assert record == {"host": "db.internal", "port": 5432, "bytes": 256}, (
        "a pair no principal's allowlist names does not resolve to the world's "
        "record: %r — `target` answers what the world has, and `reachable` "
        "answers whether it may be reached" % (record,))
    record = s.target(wire, world.ALLOWED["auditor"], "api.internal", 443)
    record["bytes"] = 0
    assert s.target(wire, world.ALLOWED["auditor"],
                    "api.internal", 443)["bytes"] == 512, (
        "bending the returned record bent the world's own: every call must hand "
        "back a fresh record")
    assert wire.dialled() == (), (
        "resolving a target dialled it: %r" % (wire.dialled(),))

    message = _refuses(s.HostError, "a host the catalogue does not have",
                       lambda: s.target(wire, world.ALLOWED["auditor"],
                                        "api.internel", 443))
    assert "api.internel" in message, (
        "the refusal of 'api.internel' does not name the offender: %r"
        % (message,))
    assert "api.internal" in message, (
        "the refusal of 'api.internel' carries no suggestion of the host the "
        "world does have: the refusal must be the world's own: %r" % (message,))
    message = _refuses(s.HostError, "a known host on a port the world does not "
                                    "answer on",
                       lambda: s.target(wire, world.ALLOWED["auditor"],
                                        "api.internal", 8443))
    assert "api.internal" in message and "8443" in message and "443" in message, (
        "the refusal of api.internal:8443 does not name the host, the port it "
        "asked for and the port the world has: %r" % (message,))
    message = _refuses(s.HostError, "a port that is not an int, as a target",
                       lambda: s.target(wire, world.ALLOWED["auditor"],
                                        "api.internal", "443"))
    assert "443" in message, (
        "the refusal of the port '443' does not name the offender: %r"
        % (message,))
    message = _refuses(s.HostError, "an upper-case host as a target",
                       lambda: s.target(wire, world.ALLOWED["auditor"],
                                        "API.internal", 443))
    assert "API.internal" in message, (
        "the refusal of the target 'API.internal' does not name it: %r"
        % (message,))
    assert "case" in message or "fold" in message, (
        "an upper-case target is not refused for being folded-away data: %r"
        % (message,))
    message = _refuses(s.HostError, "a target read with an unreadable allowlist",
                       lambda: s.target(wire, ("*.internal",),
                                        "api.internal", 443))
    assert "*.internal" in message, (
        "`target` read past a policy this stage cannot evaluate: a wildcard a "
        "reader cannot evaluate is refused wherever the policy is read: %r"
        % (message,))

    print("check_04: the network policy — one spec read as a `(host, port)` pair "
          "or the whole spec `*`, with a missing port, a port that is not a "
          "positive int and a wildcard mixed with anything else refused by name; "
          "an allowlist matched exactly on the pair and never folded, never "
          "prefix- or suffix-matched, with the empty list meaning none and `*` "
          "meaning every host the world knows; `reachable` the intersection of "
          "that with the world's own catalogue and never a dial; and `target` "
          "the world's record, bytes and refusals both, for a pair no policy "
          "names as well as for one every policy does")

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "sandbox-capabilities-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J4_REPO=/path/to/forja")

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

    import stage_01 as base
    import stage_05 as s
    import tools as world

    # ---- the family -------------------------------------------------------

    assert issubclass(s.LimitError, base.SandboxError), (
        "%r is not a %s: one `except SandboxError` must still catch a broken "
        "charge" % (s.LimitError, base.SandboxError.__name__))
    assert issubclass(s.LimitError, ValueError), (
        "%r is not a ValueError: the course's refusal is a named error a caller "
        "can catch" % (s.LimitError,))

    # ---- left: limits - spent, floored at zero ----------------------------

    meter = world.Meter()
    reading = s.left(meter)
    assert isinstance(reading, Mapping), (
        "`left` reads %r, not a mapping over the four counters" % (reading,))
    assert tuple(reading) == world.LIMIT_KEYS, (
        "`left` reads %r, not the four counters in declared order"
        % (tuple(reading),))
    assert reading == dict(world.DEFAULT_LIMITS), (
        "a fresh meter does not read its own limits: %r" % (reading,))
    assert reading is not meter.limits, (
        "`left` handed back the meter's own limits mapping, so a caller that "
        "bends its reading bends the meter")
    reading["cpu"] = 0
    assert s.left(meter)["cpu"] == world.DEFAULT_LIMITS["cpu"], (
        "`left` did not hand back a fresh reading, so one caller's edit became "
        "the next caller's limits")
    meter.spend({"cpu": 10, "memory": 8, "ticks": 2})
    assert s.left(meter) == {"cpu": 54, "memory": 65528, "ticks": 30, "calls": 7}, (
        "a spent meter reads %r, not limits - spent per counter"
        % (s.left(meter),))

    spent = world.Meter({"cpu": 4, "memory": 4, "ticks": 4, "calls": 4})
    spent.spend({"cpu": 10, "memory": 0, "ticks": 0})
    assert s.left(spent) == {"cpu": 0, "memory": 4, "ticks": 4, "calls": 3}, (
        "a raw spend took cpu past its limit and `left` reads %r: a counter "
        "past its cap reads zero, not a negative number no caller can act on"
        % (s.left(spent),))
    assert spent.used() == {"cpu": 10, "memory": 0, "ticks": 0, "calls": 1}, (
        "the world's own record of what was spent is %r" % (spent.used(),))
    assert s.left(spent)["cpu"] == 0, (
        "an overspent counter does not read zero: a floored reading is how a "
        "caller sees an overspend without the arithmetic going negative")

    # ---- fits: a question, asked twice, that spends nothing ---------------

    question = world.Meter()
    before = question.used()
    exact = {"cpu": 64, "memory": 65536, "ticks": 32}
    assert s.fits(question, exact, calls=8) is True, (
        "a cost that fits exactly (need == left) is not allowed: the boundary "
        "is `>`, and a `>=` refuses the last call a run can afford")
    assert question.used() == before, (
        "asking `fits` spent something: a question that mutates its subject "
        "cannot be asked twice")
    assert s.fits(question, exact, calls=8) is True, (
        "the second asking of a question that fits answered differently")
    assert question.used() == before, (
        "asking `fits` twice spent something: a caller deciding whether to act "
        "has to be able to look without touching")
    assert s.fits(question, {"cpu": 64, "memory": 65535, "ticks": 32}, calls=8) is True
    assert s.fits(question, {"cpu": 65}, calls=8) is False, (
        "a cost needing one cpu more than is left fits: the comparison handed "
        "out a free unit")
    assert s.fits(question, {"cpu": 64, "memory": 65536, "ticks": 32}, calls=9) is False, (
        "a ninth call fits a meter with eight calls left: the `calls` counter is "
        "the fourth one and a call always spends it")
    assert s.fits(question, {"cpu": 999}, calls=8) is False
    assert question.used() == before, (
        "a refused question spent something")

    spent_meter = world.Meter()
    spent_meter.spend({"cpu": 30, "memory": 0, "ticks": 0})
    assert s.fits(spent_meter, {"cpu": 40}) is False, (
        "`fits` read the limits and not what is left: 34 cpu remains, and a "
        "cost of 40 must not fit")
    assert s.fits(spent_meter, {"cpu": 34}) is True, (
        "a cost that fits what is left after a spend does not fit")

    one = world.Meter({"cpu": 1, "memory": 1, "ticks": 1, "calls": 1})
    assert s.fits(one, {"cpu": 1, "memory": 1, "ticks": 1}, calls=1) is True, (
        "a cost that exactly fills a one-unit meter is refused")
    assert s.fits(one, {"cpu": 2}, calls=1) is False, (
        "one unit over the cap is allowed")
    assert s.fits(one, {}, calls=1) is True, (
        "a cost with no counters at all over one call does not fit a meter with "
        "one of everything: an omitted counter is zero, and the one call is one")
    assert s.fits(one, {}, calls=2) is False, (
        "two calls fit a meter with one call left")

    zero = world.Meter({"cpu": 0, "memory": 0, "ticks": 0, "calls": 1})
    assert s.fits(zero, {"memory": 5}, calls=1) is False, (
        "a counter whose limit is zero was read as no limit: a zero cap is a "
        "cap, and it fits nothing")
    empty = world.Meter({"cpu": 0, "memory": 0, "ticks": 0, "calls": 1})
    assert s.fits(empty, {}, calls=1) is True, (
        "a cost that omits every counter does not need none of them: a counter "
        "left out is zero, not a default the charge does not spend")
    nothing = s.charge(empty, {})
    assert nothing == {"cpu": 0, "memory": 0, "ticks": 0, "calls": 1}, (
        "a charge of nothing over one call spent %r" % (nothing,))

    # ---- charge: all or nothing ------------------------------------------

    charged = world.Meter()
    used = s.charge(charged, {"cpu": 2, "memory": 64, "ticks": 2}, calls=3)
    assert isinstance(used, Mapping), (
        "`charge` returned %r, not the meter's new reading" % (used,))
    assert used == {"cpu": 2, "memory": 64, "ticks": 2, "calls": 3}, (
        "a charge of a cost over three calls reads %r, not the cost and the "
        "three calls" % (used,))
    assert charged.used() == used, (
        "`charge` did not spend what it returned: the world says %r"
        % (charged.used(),))
    assert s.charge(charged, {"cpu": 1}) == {"cpu": 3, "memory": 64, "ticks": 2,
                                             "calls": 4}, (
        "a charge whose calls are not spelled does not spend one call")
    assert charged.used()["calls"] == 4, (
        "a charge of a call did not count the call: %r" % (charged.used(),))

    wide = world.Meter({"cpu": 64, "memory": 0, "ticks": 0, "calls": 8})
    assert s.charge(wide, {"cpu": 30})["calls"] == 1, (
        "a charge of one call counted another counter's need as its calls: %r"
        % (s.charge(wide, {"cpu": 30}),))

    cap = world.Meter({"cpu": 1, "memory": 1, "ticks": 1, "calls": 1})
    assert s.charge(cap, {"cpu": 1, "memory": 1, "ticks": 1}) == {
        "cpu": 1, "memory": 1, "ticks": 1, "calls": 1}, (
        "a charge that fits exactly did not spend: a cost that fits by zero is "
        "a cost that fits")

    wall = world.Meter({"cpu": 8, "memory": 8, "ticks": 8, "calls": 8})
    untouched = wall.used()
    message = _refuses(s.LimitError, "a charge one counter short",
                       lambda: s.charge(wall, {"cpu": 4, "memory": 99, "ticks": 4},
                                        calls=2))
    assert wall.used() == untouched, (
        "a charge that failed on one counter spent another: %r — a partial "
        "charge is how a limit leaks" % (wall.used(),))
    assert "memory needs 99 and 8 is left" in message, (
        "the refusal of a charge that does not fit does not name the counter "
        "with what it needs and what is left: %r" % (message,))
    assert "cpu" not in message, (
        "the refusal names a counter that fits: %r" % (message,))

    message = _refuses(s.LimitError, "a charge nothing fits",
                       lambda: s.charge(wall, {"cpu": 9, "memory": 99, "ticks": 9},
                                        calls=9))
    for counter in ("cpu", "memory", "ticks", "calls"):
        assert counter in message, (
            "the refusal does not name %r, one of the four counters that do not "
            "fit: %r" % (counter, message))
    assert "cpu needs 9 and 8 is left" in message, (
        "the refusal does not name cpu's need and what is left, in that order: "
        "%r" % (message,))
    assert "calls needs 9 and 8 is left" in message, (
        "the refusal does not name the calls counter's need and what is left: "
        "%r" % (message,))
    assert wall.used() == untouched, (
        "a charge that nothing fits spent something anyway: %r" % (wall.used(),))

    message = _refuses(s.LimitError, "a charge into a zero cap",
                       lambda: s.charge(zero, {"memory": 5}))
    assert "memory" in message, (
        "the refusal of a charge into a zero cap does not name the counter: %r"
        % (message,))

    # ---- affordable: the same question in a tool's own terms --------------

    fresh = world.Meter()
    answer = s.affordable(fresh, world.tool("read_file"))
    assert isinstance(answer, Mapping), (
        "`affordable` returned %r, not a mapping" % (answer,))
    assert tuple(answer) == ("allowed", "reason", "short"), (
        "`affordable` answers with %r, not the three keys in declared order"
        % (tuple(answer),))
    assert answer == {"allowed": True, "reason": "granted", "short": ()}, (
        "a tool a fresh meter can pay for answers %r" % (answer,))
    assert s.affordable(fresh, world.tool("shell")) == {
        "allowed": True, "reason": "granted", "short": ()}, (
        "the dearest tool the world ships does not fit its own meter")
    assert fresh.used() == dict.fromkeys(world.LIMIT_KEYS, 0), (
        "asking `affordable` spent something: %r" % (fresh.used(),))

    tight = world.Meter({"cpu": 1, "memory": 1, "ticks": 1, "calls": 1})
    denied = s.affordable(tight, world.tool("write_file"))
    assert tuple(denied) == ("allowed", "reason", "short"), (
        "a denial answers with %r, not the three keys in declared order"
        % (tuple(denied),))
    assert denied == {"allowed": False, "reason": "limit",
                      "short": ("cpu", "memory", "ticks")}, (
        "a tool that does not fit answers %r"
        % (s.affordable(tight, world.tool("write_file")),))

    no_calls = world.Meter({"cpu": 64, "memory": 65536, "ticks": 32, "calls": 0})
    assert s.affordable(no_calls, world.tool("read_file")) == {
        "allowed": False, "reason": "limit", "short": ("calls",)}, (
        "a meter with no calls left does not deny for the calls counter: %r"
        % (s.affordable(no_calls, world.tool("read_file")),))

    one_call = world.Meter({"cpu": 64, "memory": 65536, "ticks": 32, "calls": 1})
    assert s.affordable(one_call, world.tool("read_file")) == {
        "allowed": True, "reason": "granted", "short": ()}, (
        "a tool whose cost fits and whose one call fits answers %r: the tool's "
        "terms are its cost plus one call"
        % (s.affordable(one_call, world.tool("read_file")),))

    two_short = world.Meter({"cpu": 1, "memory": 4096, "ticks": 3, "calls": 0})
    assert s.affordable(two_short, world.tool("shell")) == {
        "allowed": False, "reason": "limit", "short": ("calls", "cpu")}, (
        "`short` is %r, not the sorted names of the counters that do not fit"
        % (s.affordable(two_short, world.tool("shell"))["short"],))

    all_short = world.Meter({"cpu": 1, "memory": 1, "ticks": 1, "calls": 1})
    all_short.spend({}, calls=1)
    assert s.affordable(all_short, world.tool("shell")) == {
        "allowed": False, "reason": "limit",
        "short": ("calls", "cpu", "memory", "ticks")}, (
        "`short` with all four counters short is %r, not the four names sorted"
        % (s.affordable(all_short, world.tool("shell"))["short"],))

    nought = world.Meter({"cpu": 0, "memory": 0, "ticks": 0, "calls": 0})
    assert s.affordable(nought, world.tool("read_file")) == {
        "allowed": False, "reason": "limit", "short": ("calls", "cpu", "ticks")}, (
        "a limit of zero was read as no limit: %r"
        % (s.affordable(nought, world.tool("read_file")),))

    over = world.Meter({"cpu": 4, "memory": 4, "ticks": 4, "calls": 4})
    over.spend({"cpu": 40, "memory": 0, "ticks": 0})
    assert s.affordable(over, world.tool("read_file")) == {
        "allowed": False, "reason": "limit", "short": ("cpu",)}, (
        "an overspent counter does not deny: %r"
        % (s.affordable(over, world.tool("read_file")),))
    assert over.used() == {"cpu": 40, "memory": 0, "ticks": 0, "calls": 1}, (
        "asking `affordable` moved an overspent meter: %r" % (over.used(),))

    # ---- the fixtures -----------------------------------------------------

    for name in sorted(world.TOOLS):
        verdict = s.affordable(world.Meter(), world.tool(name))
        assert verdict["allowed"] is True, (
            "a fresh meter cannot pay for %s: %r" % (name, verdict))

    run = world.Meter()
    for _ in range(world.DEFAULT_LIMITS["calls"]):
        s.charge(run, world.tool("read_file")["cost"])
    assert s.affordable(run, world.tool("read_file")) == {
        "allowed": False, "reason": "limit", "short": ("calls",)}, (
        "a meter of DEFAULT_LIMITS ran %r one-call tools and then answered %r: "
        "the ninth call is denied for the counter it exhausts"
        % (world.DEFAULT_LIMITS["calls"],
           s.affordable(run, world.tool("read_file"))))

    # ---- the refusals -----------------------------------------------------

    for bad, spelling in (({"cpu": True}, "True"),
                          ({"cpu": 1.5}, "1.5"),
                          ({"cpu": -1}, "-1"),
                          ({"cpu": "1"}, "'1'")):
        for name, call in (("fits", lambda bad=bad: s.fits(world.Meter(), bad)),
                           ("charge", lambda bad=bad: s.charge(world.Meter(), bad))):
            message = _refuses(s.LimitError, "%s a cost counter that is %s"
                               % (name, spelling), call)
            assert "cpu" in message and spelling in message, (
                "the refusal of a %s cost counter through %s does not name the "
                "counter and the offender: %r" % (spelling, name, message))
    message = _refuses(s.LimitError, "a cost that is not a mapping",
                       lambda: s.fits(world.Meter(), 3))
    assert "mapping" in message and "3" in message, (
        "the refusal of a cost of 3 does not name its shape and the offender: %r"
        % (message,))
    message = _refuses(s.LimitError, "a cost with an unknown counter",
                       lambda: s.charge(world.Meter(), {"cpux": 1}))
    assert "cpux" in message and "did you mean 'cpu'" in message, (
        "the refusal of the counter 'cpux' does not name it and suggest 'cpu': "
        "%r" % (message,))
    message = _refuses(s.LimitError, "a cost counter nobody could have meant",
                       lambda: s.fits(world.Meter(), {"zzzz": 1}))
    assert "zzzz" in message and "did you mean" not in message, (
        "the refusal of 'zzzz' suggests a name anyway: a suggestion that is not "
        "close is a lie, and the distance is two: %r" % (message,))
    for name, call in (("fits", lambda calls: s.fits(world.Meter(), {"cpu": 1},
                                                     calls=calls)),
                       ("charge", lambda calls: s.charge(world.Meter(), {"cpu": 1},
                                                         calls=calls))):
        for bad, spelling in ((0, "0"), (-1, "-1"), (1.5, "1.5"), (True, "True")):
            message = _refuses(s.LimitError, "%s a calls count that is %s"
                               % (name, spelling),
                               lambda call=call, bad=bad: call(bad))
            assert "calls" in message and spelling in message, (
                "the refusal of a calls count of %s through %s does not name the "
                "counter and the offender: %r" % (spelling, name, message))
    message = _refuses(s.LimitError, "a tool that is not a mapping",
                       lambda: s.affordable(world.Meter(), 3))
    assert "mapping" in message and "3" in message, (
        "the refusal of the tool 3 does not name its shape and the offender: %r"
        % (message,))
    message = _refuses(s.LimitError, "a tool that carries no cost",
                       lambda: s.affordable(world.Meter(), {"name": "reader"}))
    assert "cost" in message, (
        "the refusal of a tool with no cost does not name the missing field: %r"
        % (message,))

    safe = world.Meter()
    _refuses(s.LimitError, "a cost that is not a mapping",
             lambda: s.charge(safe, 3))
    assert safe.used() == dict.fromkeys(world.LIMIT_KEYS, 0), (
        "a refused charge spent something: %r" % (safe.used(),))

    print("check_05: the four counters — a floored reading, a question that "
          "spends nothing and answers both sides of the boundary, a charge that "
          "is all or nothing and names every counter that does not fit, and the "
          "same question in a tool's own terms as `{\"allowed\", \"reason\", "
          "\"short\"}` — with a cost that is not a mapping, a bool, a float, a "
          "negative, a non-int, an unknown counter and a calls count that is "
          "not a positive int all refused by name, and a limit of zero read as "
          "the cap it is")

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "sandbox-capabilities-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J4_REPO=/path/to/forja")

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

    import base64

    import stage_01
    import stage_06 as s
    import tools as world
    import vfs as worldfs

    # ---- the encodings, and the family a refusal belongs to ---------------

    assert s.ENCODINGS == ("plain", "base64", "hex", "reversed"), (
        "this stage's encodings are %r, not the four the course defined, in "
        "declared order" % (s.ENCODINGS,))
    assert isinstance(s.ENCODINGS, tuple), (
        "ENCODINGS is a %s: a vocabulary handed over as a str is a vocabulary "
        "nobody can compare, and `in` on it is a substring test"
        % (type(s.ENCODINGS).__name__,))
    assert issubclass(s.SecretError, stage_01.SandboxError), (
        "%r is not a %s: one `except SandboxError` must still catch a secret "
        "this stage refuses" % (s.SecretError, stage_01.SandboxError.__name__))

    # ---- digest: a fingerprint, and not cryptography ----------------------

    assert s.digest("") == 0, (
        "the fingerprint of the empty value is %r: a sum over no characters is "
        "nothing" % (s.digest(""),))
    weighted = 1 * ord("a") + 2 * ord("b")
    assert s.digest("ab") == weighted, (
        "`digest('ab')` is %r, not %d: the fingerprint is "
        "`sum((i + 1) * ord(char) for i, char in enumerate(value))` — every "
        "character weighted by its position, so the same two characters in the "
        "other order are a different value" % (s.digest("ab"), weighted))
    key = world.SECRETS["deploy-key"]["value"]
    expected = sum((index + 1) * ord(char) for index, char in enumerate(key))
    fingerprint = s.digest(key)
    assert fingerprint == expected, (
        "the deploy key fingerprints as %r, not as %d"
        % (fingerprint, expected))
    assert isinstance(fingerprint, int) and not isinstance(fingerprint, bool), (
        "the fingerprint is %r: a digest is an int count of the value's "
        "characters, and a float that happens to compare equal is not one"
        % (fingerprint,))
    assert s.digest("A") != s.digest("a"), (
        "the fingerprint of 'A' equals the fingerprint of 'a': a value is not "
        "folded, or two different values would fingerprint as one")
    message = _refuses(s.SecretError, "a value that is not a str",
                       lambda: s.digest(7))
    assert "str" in message and "7" in message, (
        "the refusal of the value 7 does not name its shape and the offender: %r"
        % (message,))

    # ---- observe: the identity travels, the value does not ----------------

    vault = world.Vault()
    observed = s.observe(vault, "deploy-key")
    assert tuple(observed) == ("handle", "present", "bytes", "digest"), (
        "an observation carries %r, not exactly the four fields the course "
        "defined, in order — a fifth field is a field the value can leave in"
        % (tuple(observed),))
    assert observed["handle"] == "deploy-key", (
        "the observation names the handle %r" % (observed["handle"],))
    assert observed["present"] is True, (
        "the vault holds 'deploy-key' but the observation says present is %r"
        % (observed["present"],))
    assert observed["bytes"] == len(key), (
        "the observation says the value is %r bytes long, and it is %d"
        % (observed["bytes"], len(key)))
    assert observed["digest"] == expected, (
        "the observation's digest is %r, not the value's own fingerprint %d"
        % (observed["digest"], expected))
    assert vault.reads() == ("deploy-key",), (
        "observing 'deploy-key' left %r in the vault's record: the value is read "
        "once, fingerprinted and dropped, and the record is how a reader knows it"
        % (vault.reads(),))
    shown = repr(observed)
    for spelling in (key, key[::-1], key.encode().hex(),
                     base64.b64encode(key.encode()).decode()):
        assert spelling not in shown, (
            "the observation spells the value out as %r: what travels is the "
            "handle, the length and a fingerprint, and the value never does"
            % (spelling,))

    class BentVault:
        """A vault whose metadata does not equal the value's own length, so that
        measuring the value yourself and asking the vault are two answers."""

        def __init__(self):
            self.seen = []

        def holds(self, handle):
            return handle == "demo"

        def meta(self, handle):
            return {"handle": handle, "bytes": 4096}

        def read(self, handle):
            self.seen.append(handle)
            return "demo-secret"

    bent = BentVault()
    shown = s.observe(bent, "demo")
    assert shown == {"handle": "demo", "present": True, "bytes": 4096,
                     "digest": s.digest("demo-secret")}, (
        "observing a vault that reports 4096 bytes for 'demo' gave %r: the "
        "length is the world's own reading and not a measurement taken here"
        % (shown,))
    assert bent.seen == ["demo"], (
        "the vault was read %r times for one observation: a fingerprint needs "
        "one read, and the record is the proof of how many it was"
        % (bent.seen,))
    message = _refuses(world.VaultError, "a handle the vault does not hold",
                       lambda: s.observe(world.Vault(), "no-such-handle"))
    assert "no-such-handle" in message, (
        "an unknown handle is not left to the world's refusal by name: %r"
        % (message,))
    message = _refuses(world.VaultError, "a handle that is not a str",
                       lambda: s.observe(world.Vault(), 7))
    assert "str" in message and "7" in message, (
        "the handle 7 does not reach the world's refusal that names it: %r"
        % (message,))

    # ---- reveal: the one door, and the policy that opens it ---------------

    vault = world.Vault()
    open_policy = {"principal": "vaultkeeper", "root": "/home/agent",
                   "capabilities": world.GRANTS["vaultkeeper"], "hosts": ()}
    opened = s.reveal(open_policy, vault, "deploy-key")
    assert tuple(opened) == ("allowed", "reason", "value"), (
        "an allowed reveal carries %r, not exactly the three fields the course "
        "defined, in order" % (tuple(opened),))
    assert opened == {"allowed": True, "reason": "granted", "value": key}, (
        "a policy holding `secret:read` answered %r, not the value behind the "
        "handle" % (opened,))
    assert vault.reads() == ("deploy-key",), (
        "the one door read the handle %r times: a value becomes a str here and "
        "nowhere else, and once is how many reads that costs"
        % (vault.reads(),))

    vault = world.Vault()
    shut_policy = {"principal": "analyst", "root": "/home/agent",
                   "capabilities": world.GRANTS["analyst"], "hosts": ()}
    assert ("fs:read" in shut_policy["capabilities"]
            and "secret:read" not in shut_policy["capabilities"]), (
        "the fixture policy is not the one this check needs: it must hold "
        "`fs:read` and not `secret:read`")
    denied = s.reveal(shut_policy, vault, "deploy-key")
    assert tuple(denied) == ("allowed", "reason", "missing"), (
        "a denial carries %r, not exactly the three fields the course defined, "
        "in order — a denial carries the reason and nothing else"
        % (tuple(denied),))
    assert denied == {"allowed": False, "reason": "capability",
                      "missing": ("secret:read",)}, (
        "a policy whose capabilities are %r did not deny with the missing "
        "capability named: %r — `fs:read` is not `secret:read`"
        % (shut_policy["capabilities"], denied))
    assert "value" not in denied and key not in repr(denied), (
        "the denial carries the value it refused: %r" % (denied,))
    assert vault.reads() == (), (
        "a refused reveal left %r in the vault's record: the grant is decided "
        "before the world is asked anything, so `nothing was read` is checkable "
        "rather than promised" % (vault.reads(),))
    nothing = s.reveal({"principal": "intern", "root": "/home/agent/src",
                        "capabilities": (), "hosts": ()},
                       world.Vault(), "deploy-key")
    assert nothing == {"allowed": False, "reason": "capability",
                       "missing": ("secret:read",)}, (
        "a principal holding nothing did not deny: %r" % (nothing,))
    unseen = s.reveal(shut_policy, world.Vault(), "no-such-handle")
    assert unseen == {"allowed": False, "reason": "capability",
                      "missing": ("secret:read",)}, (
        "a denial for a handle the vault does not hold is %r: the grant is "
        "decided before the world is asked, so an unknown handle cannot turn a "
        "denial into a refusal" % (unseen,))
    message = _refuses(world.VaultError, "the open door on an unknown handle",
                       lambda: s.reveal(open_policy, world.Vault(),
                                        "no-such-handle"))
    assert "no-such-handle" in message, (
        "the open door on an unknown handle is not the world's refusal by name: "
        "%r" % (message,))

    message = _refuses(s.SecretError, "a policy that is not a mapping",
                       lambda: s.reveal(["capabilities"], world.Vault(),
                                        "deploy-key"))
    assert "mapping" in message and "['capabilities']" in message, (
        "the refusal of a list handed over as a policy does not name its shape "
        "and the offender: %r" % (message,))
    message = _refuses(s.SecretError, "a policy with no capability set",
                       lambda: s.reveal({"principal": "vaultkeeper"},
                                        world.Vault(), "deploy-key"))
    assert "capabilities" in message, (
        "the refusal of a policy with no capability set does not name the "
        "missing field: %r" % (message,))
    message = _refuses(s.SecretError, "a capability set spelled as a typo",
                       lambda: s.reveal({"capabilites": ("secret:read",)},
                                        world.Vault(), "deploy-key"))
    assert ("capabilites" in message and "did you mean" in message
            and "'capabilities'" in message), (
        "the refusal of the field 'capabilites' does not name it and suggest the "
        "real one: %r" % (message,))
    message = _refuses(s.SecretError, "a policy field nobody could have meant",
                       lambda: s.reveal({"cap": ("secret:read",)},
                                        world.Vault(), "deploy-key"))
    assert "cap" in message and "did you mean" not in message, (
        "the refusal of the field 'cap' suggests a name anyway: a suggestion nine "
        "edits away is not a typo, and the distance is two: %r" % (message,))
    message = _refuses(s.SecretError, "a capability set written as a str",
                       lambda: s.reveal({"capabilities": "secret:read"},
                                        world.Vault(), "deploy-key"))
    assert "secret:read" in message and "str" in message, (
        "a capability set handed over as the str 'secret:read' is not refused: "
        "`in` on a str is a substring test, so this policy would open the very "
        "door it names one character at a time: %r" % (message,))
    message = _refuses(s.SecretError, "a capability set that is a number",
                       lambda: s.reveal({"capabilities": 7}, world.Vault(),
                                        "deploy-key"))
    assert "7" in message, (
        "the refusal of the capability set 7 does not name the offender: %r"
        % (message,))

    # ---- the six spellings, one at a time ---------------------------------

    values = {"deploy-key": key,
              "api-token": world.SECRETS["api-token"]["value"],
              "db-password": world.SECRETS["db-password"]["value"]}
    password = values["db-password"]

    def spellings_of(value):
        padded = base64.b64encode(value.encode()).decode()
        digits = value.encode().hex()
        return (value, padded, padded.rstrip("="), digits, digits.upper(),
                value[::-1])

    for value, handle in ((key, "deploy-key"), (password, "db-password")):
        assert len(value) > 4, (
            "the fixture value %r is short enough that a test on one of its "
            "characters would agree with a test on the value, and this check "
            "would not be decidable" % (value,))
        for spelling in spellings_of(value):
            text = "before %s after" % (spelling,)
            found = s.leaks(text, values)
            assert found == (handle,), (
                "a text carrying %r of the %s reported %r, not the handle: a "
                "detector that knows one spelling of a value has already lost to "
                "the others" % (spelling, handle, found))
            redacted = s.redact(text, values)
            assert redacted == "before <redacted:%s> after" % (handle,), (
                "redacting %r of the %s gave %r, not the handle in place of the "
                "whole spelling with the rest of the text left alone"
                % (spelling, handle, redacted))

    # ---- the file the secret is also written in ---------------------------

    env = worldfs.VFS().read("/home/agent/.env")
    assert key in env, (
        "the .env fixture no longer holds the deploy key: this stage's second "
        "place for a leak to land is gone")
    assert s.leaks(env, values) == ("deploy-key",), (
        "the deploy key written in .env was not found: %r"
        % (s.leaks(env, values),))
    redacted = s.redact(env, values)
    assert "DEPLOY_KEY=<redacted:deploy-key>" in redacted, (
        "redacting .env gave %r, not the handle where the value was" % (redacted,))
    assert "LOG_LEVEL=info" in redacted, (
        "redacting .env removed more than the secret: %r" % (redacted,))
    assert s.leaks(redacted, values) == (), (
        "the redacted .env still carries a spelling of the value: %r"
        % (s.leaks(redacted, values),))
    assert s.redact(redacted, values) == redacted, (
        "redacting a redacted text changed it again, into %r: a run redacts its "
        "own output as often as it likes" % (s.redact(redacted, values),))

    # ---- what a detector must report, and what it must not ----------------

    both = "the key %s and the password %s" % (key, password)
    assert s.leaks(both, values) == ("db-password", "deploy-key"), (
        "a text carrying two secrets reported %r: the handles come back sorted, "
        "so two runs of the same detector agree" % (s.leaks(both, values),))
    twice = "%s and again as %s" % (key,
                                    base64.b64encode(key.encode()).decode())
    assert s.leaks(twice, values) == ("deploy-key",), (
        "a value written twice reported %r: the answer is the handles found, "
        "each of them once" % (s.leaks(twice, values),))
    assert s.leaks("a b c", {"short": "ab"}) == (), (
        "a text carrying the characters of a value but not the value reported a "
        "leak: the test is on the whole value and not on one of its characters")
    assert s.leaks("<redacted:deploy-key>", values) == (), (
        "the redaction's own placeholder reported a leak: the handle is not the "
        "value, and a detector that searches for handles searches for the wrong "
        "thing")
    handle_text = "the handle deploy-key names a secret"
    changed = s.redact(handle_text, {"deploy-key": key})
    assert changed == handle_text, (
        "redacting a text that merely names the handle changed it into %r: what "
        "is replaced is the value, and not the handle" % (changed,))
    assert s.leaks(handle_text, {"deploy-key": key}) == (), (
        "a text that names the handle was reported as carrying the value")

    # ---- nothing to do is not an error ------------------------------------

    assert s.redact("", values) == "", (
        "redacting the empty text gave %r" % (s.redact("", values),))
    assert s.redact("nothing to see here", values) == "nothing to see here", (
        "redacting a text with no value in it gave %r"
        % (s.redact("nothing to see here", values),))
    assert s.redact("nothing to see here", {}) == "nothing to see here", (
        "redacting with an empty mapping gave %r"
        % (s.redact("nothing to see here", {}),))
    assert s.redact("nothing to see here", {"deploy-key": key}) == (
        "nothing to see here"), (
        "redacting a text a value does not occur in gave %r"
        % (s.redact("nothing to see here", {"deploy-key": key}),))
    assert s.leaks("", values) == (), (
        "the empty text reported %r" % (s.leaks("", values),))
    assert s.leaks("nothing to see here", values) == (), (
        "a text with no value in it reported %r"
        % (s.leaks("nothing to see here", values),))
    assert s.leaks("", {}) == (), (
        "an empty text with an empty mapping reported %r" % (s.leaks("", {}),))
    assert s.leaks("nothing to see here", {"deploy-key": key}) == (), (
        "a text a value does not occur in reported %r"
        % (s.leaks("nothing to see here", {"deploy-key": key}),))
    assert isinstance(s.leaks("", values), tuple), (
        "`leaks` answered a %s: the answer is the handles, as a tuple, and not a "
        "boolean a caller has to interpret"
        % (type(s.leaks("", values)).__name__,))
    fixture = {"deploy-key": key}
    before = repr(sorted(fixture.items()))
    s.redact("the key %s" % (key,), fixture)
    assert repr(sorted(fixture.items())) == before, (
        "`redact` bent the caller's mapping: %r" % (fixture,))

    # ---- a text, a values, a value and a handle of the wrong shape --------

    message = _refuses(s.SecretError, "a text that is not a str, to the redactor",
                       lambda: s.redact(7, values))
    assert "str" in message and "7" in message, (
        "the refusal of the text 7 does not name its shape and the offender: %r"
        % (message,))
    message = _refuses(s.SecretError, "a text that is not a str, to the detector",
                       lambda: s.leaks(7, values))
    assert "str" in message and "7" in message, (
        "the refusal of the text 7 to the detector does not name the offender: "
        "%r" % (message,))
    message = _refuses(s.SecretError, "values that are not a mapping",
                       lambda: s.redact("a text", ["deploy-key"]))
    assert "mapping" in message and "['deploy-key']" in message, (
        "the refusal of a list handed over as values does not name its shape and "
        "the offender: %r" % (message,))
    message = _refuses(s.SecretError, "values that are not a mapping, to the "
                                      "detector",
                       lambda: s.leaks("a text", ["deploy-key"]))
    assert "mapping" in message, (
        "the detector does not refuse values that are not a mapping: %r"
        % (message,))
    message = _refuses(s.SecretError, "a value that is not a str",
                       lambda: s.redact("a text", {"deploy-key": 7}))
    assert "deploy-key" in message and "7" in message, (
        "the refusal of the value 7 does not name the handle and the offender: "
        "%r" % (message,))
    message = _refuses(s.SecretError, "a value that is empty",
                       lambda: s.leaks("a text", {"deploy-key": ""}))
    assert "deploy-key" in message and "empty" in message, (
        "an empty value is not refused: it occurs everywhere, so redacting it "
        "would rewrite the whole text and detecting it would find it in every "
        "one: %r" % (message,))
    message = _refuses(s.SecretError, "a handle that is not a str",
                       lambda: s.redact("a text", {7: "a value"}))
    assert "str" in message and "7" in message, (
        "the refusal of the handle 7 does not name its shape and the offender: "
        "%r" % (message,))

    print("check_06: the four encodings in declared order, and a redactor and a "
          "detector that know all six spellings of a value — padded and stripped "
          "base64, lower and upper hex, and the reversed value; a fingerprint "
          "that is a weighted sum of the value's characters and says it is not "
          "cryptography; an observation that carries the handle, the vault's own "
          "length and that fingerprint and never the value; one door a value may "
          "leave through, denying `fs:read` as data and naming the missing "
          "capability while leaving the vault's own record untouched; and the "
          "deploy key found in the `.env` file the world ships and cleaned of it")

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "sandbox-capabilities-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J4_REPO=/path/to/forja")

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

    import tools as world

    import stage_07 as s

    canon = ("2 principal=analyst tool=read_file "
             "target=/home/agent/notes.md decision=allowed reason=granted "
             "bytes=42")

    # ---- the vocabulary, and the family ----------------------------------

    assert s.REASONS == ("granted", "unknown", "capability", "jail", "host",
                         "limit", "secret"), (
        "this stage's reasons are %r, not the seven the course defined, in order"
        % (s.REASONS,))
    assert s.DECISIONS == ("allowed", "denied"), (
        "this stage's decisions are %r, not the two the course defined, in order"
        % (s.DECISIONS,))
    assert s.AUDIT_KEYS == ("tick", "principal", "tool", "target", "decision",
                            "reason", "bytes"), (
        "this stage's audit fields are %r, not the seven the course defined, in "
        "order" % (s.AUDIT_KEYS,))
    assert issubclass(s.SandboxError, ValueError), (
        "%r is not a ValueError: the course's refusal is a named error a caller "
        "can catch, and every later stage derives its own from it"
        % (s.SandboxError,))
    assert issubclass(s.AuditError, s.SandboxError), (
        "%r is not a %s: one `except SandboxError` must still catch a broken line"
        % (s.AuditError, s.SandboxError.__name__))

    # ---- line: the hand-computed line, every key, no trailing space ------

    written = s.line(2, principal="analyst", tool="read_file",
                     target="/home/agent/notes.md", decision="allowed",
                     reason="granted", bytes=42)
    assert written == canon, (
        "a call that touched 42 bytes writes %r, not the line the course defined "
        "(%r)" % (written, canon))
    assert not written.endswith(" "), (
        "the line ends in a trailing space: a line is fields separated by single "
        "spaces, not padded with one")
    assert written.count("=") == len(s.AUDIT_KEYS) - 1, (
        "the line carries %d `key=value` pairs, not one per key of AUDIT_KEYS: %r"
        % (written.count("="), written))

    blank = s.line(1, principal="intern", tool="env_dump", target="",
                   decision="denied", reason="capability", bytes=0)
    assert blank == ("1 principal=intern tool=env_dump target=- "
                     "decision=denied reason=capability bytes=0"), (
        "an absent target is written as %r: every key is always written, and the "
        "marker says the position is a position and not a silence" % (blank,))

    # ---- line: the refusals, each naming the offender --------------------

    for bad, spelling in ((True, "True"), (-1, "-1"), (2.5, "2.5"), ("2", "'2'")):
        message = _refuses(s.AuditError, "a tick that is %s" % (spelling,),
                           lambda bad=bad: s.line(
                               bad, principal="analyst", tool="read_file",
                               target="/home/agent/notes.md",
                               decision="allowed", reason="granted", bytes=42))
        assert "tick" in message and spelling in message, (
            "the refusal of a %s tick does not name the field and the offender: %r"
            % (spelling, message))
    for bad, spelling in ((True, "True"), (-1, "-1"), ("42", "'42'")):
        message = _refuses(s.AuditError, "a bytes that is %s" % (spelling,),
                           lambda bad=bad: s.line(
                               2, principal="analyst", tool="read_file",
                               target="/home/agent/notes.md",
                               decision="allowed", reason="granted", bytes=bad))
        assert "bytes" in message and spelling in message, (
            "the refusal of a %s byte count does not name the field and the "
            "offender: %r" % (spelling, message))
    message = _refuses(s.AuditError, "a principal that is not a str",
                       lambda: s.line(2, principal=7, tool="read_file",
                                      target="/home/agent/notes.md",
                                      decision="allowed", reason="granted",
                                      bytes=42))
    assert "principal" in message and "7" in message, (
        "the refusal of a non-str principal does not name the field and the "
        "offender: %r" % (message,))
    message = _refuses(s.AuditError, "a principal that is empty",
                       lambda: s.line(2, principal="", tool="read_file",
                                      target="/home/agent/notes.md",
                                      decision="allowed", reason="granted",
                                      bytes=42))
    assert "principal" in message, (
        "the refusal of an empty principal does not name the field: %r"
        % (message,))
    message = _refuses(s.AuditError, "a principal with a space in it",
                       lambda: s.line(2, principal="an alyst", tool="read_file",
                                      target="/home/agent/notes.md",
                                      decision="allowed", reason="granted",
                                      bytes=42))
    assert "principal" in message and "an alyst" in message, (
        "the refusal of a principal with a space does not name the field and the "
        "offender: %r" % (message,))
    message = _refuses(s.AuditError, "a tool with a space in it",
                       lambda: s.line(2, principal="analyst", tool="read file",
                                      target="/home/agent/notes.md",
                                      decision="allowed", reason="granted",
                                      bytes=42))
    assert "tool" in message and "read file" in message, (
        "the refusal of a tool with a space does not name the field and the "
        "offender: %r" % (message,))
    message = _refuses(s.AuditError, "an empty tool",
                       lambda: s.line(2, principal="analyst", tool="",
                                      target="/home/agent/notes.md",
                                      decision="allowed", reason="granted",
                                      bytes=42))
    assert "tool" in message, (
        "the refusal of an empty tool does not name the field: %r" % (message,))
    message = _refuses(s.AuditError, "a target that is not a str",
                       lambda: s.line(2, principal="analyst", tool="read_file",
                                      target=7, decision="allowed",
                                      reason="granted", bytes=42))
    assert "target" in message and "7" in message, (
        "the refusal of a non-str target does not name the field and the "
        "offender: %r" % (message,))
    message = _refuses(s.AuditError, "a target with a space in it",
                       lambda: s.line(2, principal="analyst", tool="read_file",
                                      target="/home/agent/note s.md",
                                      decision="allowed", reason="granted",
                                      bytes=42))
    assert "target" in message and "/home/agent/note s.md" in message, (
        "the refusal of a target with a space does not name the field and the "
        "offender: a space smuggled into a target is a second field to a reader: "
        "%r" % (message,))
    message = _refuses(s.AuditError, "the marker itself as a target",
                       lambda: s.line(2, principal="analyst", tool="read_file",
                                      target="-", decision="allowed",
                                      reason="granted", bytes=42))
    assert "target" in message, (
        "the refusal of a `-` target does not name the field: the marker is a "
        "target the reader cannot tell from its absence: %r" % (message,))
    message = _refuses(s.AuditError, "a decision that is not a str",
                       lambda: s.line(2, principal="analyst", tool="read_file",
                                      target="/home/agent/notes.md",
                                      decision=7, reason="granted", bytes=42))
    assert "str" in message and "7" in message, (
        "the refusal of a non-str decision does not name the field and the "
        "offender: %r" % (message,))
    message = _refuses(s.AuditError, "a decision that is a typo",
                       lambda: s.line(2, principal="analyst", tool="read_file",
                                      target="/home/agent/notes.md",
                                      decision="denyed", reason="granted",
                                      bytes=42))
    assert "denyed" in message and "denied" in message, (
        "the refusal of the decision 'denyed' does not name it and suggest "
        "'denied': %r" % (message,))
    message = _refuses(s.AuditError, "a decision nobody could have meant",
                       lambda: s.line(2, principal="analyst", tool="read_file",
                                      target="/home/agent/notes.md",
                                      decision="xyzzy", reason="granted",
                                      bytes=42))
    assert "xyzzy" in message and "did you mean" not in message, (
        "the refusal of the decision 'xyzzy' suggests a name anyway: a suggestion "
        "that is not close is a lie, and the distance is two: %r" % (message,))
    message = _refuses(s.AuditError, "a reason that is the decision word",
                       lambda: s.line(2, principal="analyst", tool="read_file",
                                      target="/home/agent/notes.md",
                                      decision="denied", reason="denied",
                                      bytes=42))
    assert "denied" in message, (
        "the refusal of the reason 'denied' does not name it: 'denied' is a "
        "decision, a decision says what and a reason says why: %r" % (message,))
    message = _refuses(s.AuditError, "a reason that is a decision word misspelled",
                       lambda: s.line(0, principal="a", tool="read_file",
                                      target="/home/agent/notes.md",
                                      decision="denied", reason="denyed",
                                      bytes=0))
    assert "denyed" in message and "denied" in message, (
        "the refusal of the reason 'denyed' does not name it and suggest the word "
        "of the audit it meant: the suggestion is over the audit's whole word "
        "set, so a caller who confused the two axes is handed the word that "
        "exists: %r" % (message,))
    message = _refuses(s.AuditError, "a reason that is a whole sentence",
                       lambda: s.line(2, principal="analyst", tool="read_file",
                                      target="/home/agent/notes.md",
                                      decision="denied", reason="not allowed",
                                      bytes=42))
    assert "not allowed" in message, (
        "the refusal of the reason 'not allowed' does not name it: a free-text "
        "reason is a reason nobody can count: %r" % (message,))
    message = _refuses(s.AuditError, "a reason that is a typo",
                       lambda: s.line(2, principal="analyst", tool="read_file",
                                      target="/home/agent/notes.md",
                                      decision="denied", reason="grante",
                                      bytes=42))
    assert "grante" in message and "granted" in message, (
        "the refusal of the reason 'grante' does not name it and suggest "
        "'granted': %r" % (message,))
    message = _refuses(s.AuditError, "a reason nobody could have meant",
                       lambda: s.line(2, principal="analyst", tool="read_file",
                                      target="/home/agent/notes.md",
                                      decision="denied", reason="xyzzy",
                                      bytes=42))
    assert "xyzzy" in message and "did you mean" not in message, (
        "the refusal of the reason 'xyzzy' suggests a name anyway: %r" % (message,))

    message = _refuses(s.AuditError, "a reason that is not a str",
                       lambda: s.line(2, principal="analyst", tool="read_file",
                                      target="/home/agent/notes.md",
                                      decision="denied", reason=7, bytes=42))
    assert "str" in message and "7" in message, (
        "the refusal of a non-str reason does not name the field and the "
        "offender: %r" % (message,))

    # ---- parse_line: the round trip, every pair --------------------------

    for decision in s.DECISIONS:
        for reason in s.REASONS:
            text = s.line(7, principal="analyst", tool="read_file",
                          target="/home/agent/notes.md", decision=decision,
                          reason=reason, bytes=13)
            parsed = s.parse_line(text)
            assert tuple(parsed) == s.AUDIT_KEYS, (
                "a parsed %s/%s line carries %r, not exactly AUDIT_KEYS in order"
                % (decision, reason, tuple(parsed)))
            assert parsed == {"tick": 7, "principal": "analyst",
                              "tool": "read_file",
                              "target": "/home/agent/notes.md",
                              "decision": decision, "reason": reason,
                              "bytes": 13}, (
                "the %s/%s line round-trips to %r, not to the entry it was "
                "written from" % (decision, reason, parsed))
    absent = s.parse_line(s.line(9, principal="intern", tool="env_dump",
                                 target="", decision="denied",
                                 reason="capability", bytes=0))
    assert absent["target"] == "" and absent["bytes"] == 0, (
        "the marker does not read back as an empty target: %r" % (absent,))

    # ---- parse_line: the refusals, by index and by text ------------------

    def refuses(text, what):
        return _refuses(s.AuditError, what, lambda: s.parse_line(text))

    message = refuses(7, "a line that is not a str")
    assert "str" in message and "7" in message, (
        "the refusal of a line that is a number does not name its shape and the "
        "offender: %r" % (message,))
    extra = canon + " extra=1"
    message = refuses(extra, "a line with one field too many")
    assert "8" in message and extra in message, (
        "the refusal of a line with an extra field does not name the count and "
        "the text: %r" % (message,))
    short = canon.replace(" tool=read_file", "")
    message = refuses(short, "a line with one field too few")
    assert "6" in message and short in message, (
        "the refusal of a line with a missing field does not name the count and "
        "the text: %r" % (message,))
    unknown = canon.replace("tool=read_file", "took=read_file")
    message = refuses(unknown, "a line whose key is not the one at its index")
    assert "index 2" in message and "took" in message and unknown in message, (
        "the refusal of the key 'took' does not name the index, the offender and "
        "the text: %r" % (message,))
    swapped = canon.replace("decision=allowed reason=granted",
                            "reason=granted decision=allowed")
    message = refuses(swapped, "a line whose keys are out of order")
    assert "index 4" in message and swapped in message, (
        "the refusal of a line whose keys are reordered does not name the index "
        "and the text: %r" % (message,))
    naked = canon.replace("tool=read_file", "read_file")
    message = refuses(naked, "a field that is not a key=value pair")
    assert "read_file" in message and naked in message, (
        "the refusal of a field with no `=` does not name the field and the "
        "text: %r" % (message,))
    message = refuses(canon.replace("decision=allowed", "decision=denyed"),
                      "a line whose decision is a typo")
    assert "denyed" in message and "denied" in message, (
        "the refusal of the decision 'denyed' read back does not name it and "
        "suggest 'denied': %r" % (message,))
    message = refuses(canon.replace("reason=granted", "reason=denied"),
                      "a line whose reason is the decision word")
    assert "denied" in message, (
        "the refusal of the reason 'denied' read back does not name it: %r"
        % (message,))
    message = refuses(canon.replace("principal=analyst", "principal="),
                      "a line whose principal is empty")
    assert "principal" in message, (
        "the refusal of an empty principal read back does not name the field: %r"
        % (message,))
    message = refuses(canon.replace("tool=read_file", "tool="),
                      "a line whose tool is empty")
    assert "tool" in message, (
        "the refusal of an empty tool read back does not name the field: %r"
        % (message,))
    message = refuses(canon.replace("bytes=42", "bytes=True"),
                      "a line whose byte count is a bool")
    assert "bytes" in message and "True" in message, (
        "the refusal of the byte count 'True' does not name the field and the "
        "offender: %r" % (message,))
    message = refuses(canon.replace("bytes=42", "bytes=-1"),
                      "a line whose byte count is negative")
    assert "bytes" in message and "-1" in message, (
        "the refusal of the negative byte count does not name the field and the "
        "offender: %r" % (message,))
    message = refuses(canon.replace("2 principal", "two principal"),
                      "a line whose tick is not an int")
    assert "tick" in message and "two" in message, (
        "the refusal of a non-int tick does not name the field and the offender: "
        "%r" % (message,))
    message = refuses(canon.replace("target=/home/agent/notes.md", "target="),
                      "a line whose target is empty instead of the marker")
    assert "target" in message and "-" in message, (
        "the refusal of an empty target does not name the field and the marker "
        "that was wanted: %r" % (message,))

    # ---- write_line: the count, the order, and the sink ------------------

    entry = {"bytes": 42, "reason": "granted", "decision": "allowed",
             "target": "/home/agent/notes.md", "tool": "read_file",
             "principal": "analyst", "tick": 2}
    sink = world.Audit()
    assert s.write_line(sink, entry) == 1, (
        "write_line does not return the count the sink reported")
    assert sink.lines() == (canon,), (
        "write_line wrote %r: the fields are written in AUDIT_KEYS order, never "
        "in the caller's mapping order (%r)" % (sink.lines(), tuple(entry)))
    second = {"tick": 3, "principal": "intern", "tool": "env_dump", "target": "",
              "decision": "denied", "reason": "capability", "bytes": 0}
    assert s.write_line(sink, second) == 2, (
        "the second line's count is not the sink's own count")
    assert sink.lines()[1] == ("3 principal=intern tool=env_dump target=- "
                               "decision=denied reason=capability bytes=0"), (
        "the second line is %r: every key is written, and an absent target is a "
        "position" % (sink.lines()[1],))
    assert s.parse_line(sink.lines()[0]) == {"tick": 2, "principal": "analyst",
                                            "tool": "read_file",
                                            "target": "/home/agent/notes.md",
                                            "decision": "allowed",
                                            "reason": "granted", "bytes": 42}, (
        "a line write_line wrote does not read back: it wrote a line it would "
        "refuse to parse")

    class _Spy:
        """A sink whose `lines()` is a trap: `write_line` must not read it."""

        def __init__(self):
            self.written = []

        def record(self, text):
            self.written.append(text)
            return len(self.written)

        def lines(self):
            raise AssertionError(
                "write_line read the sink back to count it: the count is "
                "`record`'s own answer, and a second question has a different "
                "answer the moment two writers interleave")

    spy = _Spy()
    assert s.write_line(spy, entry) == 1 and spy.written == [canon], (
        "write_line did not append the canonical line through the sink: %r"
        % (spy.written,))

    empty = world.Audit()
    message = _refuses(s.AuditError, "an entry that is not a mapping",
                       lambda: s.write_line(empty, ("tick", 2)))
    assert "mapping" in message, (
        "the refusal of a non-mapping entry does not name its shape: %r"
        % (message,))
    message = _refuses(s.AuditError, "an entry with a foreign field",
                       lambda: s.write_line(empty, dict(entry, tickk=2)))
    assert "tickk" in message and "did you mean" in message and "'tick'" in message, (
        "the refusal of the entry field 'tickk' does not name it and suggest the "
        "real one: %r" % (message,))
    missing = {key: value for key, value in entry.items() if key != "bytes"}
    message = _refuses(s.AuditError, "an entry that omits a key",
                       lambda: s.write_line(empty, missing))
    assert "bytes" in message, (
        "the refusal of an entry with no `bytes` does not name the missing key: "
        "%r" % (message,))
    message = _refuses(s.AuditError, "an entry whose bytes is a bool",
                       lambda: s.write_line(empty, dict(entry, bytes=True)))
    assert "bytes" in message and "True" in message, (
        "the refusal of an entry whose bytes is True does not name the field and "
        "the offender: %r" % (message,))
    message = _refuses(s.AuditError, "an entry whose decision is a typo",
                       lambda: s.write_line(empty, dict(entry, decision="denyed")))
    assert "denyed" in message, (
        "the refusal of an entry whose decision is 'denyed' does not name it: %r"
        % (message,))
    message = _refuses(s.AuditError, "an entry whose target is empty and unspelled",
                       lambda: s.write_line(empty, dict(entry, target="-")))
    assert "target" in message, (
        "the refusal of a `-` target does not name the field: %r" % (message,))
    assert empty.lines() == (), (
        "write_line appended %r: a line it would refuse to parse is a line it "
        "must never write" % (empty.lines(),))

    print("check_07: the audit line — seven keys always written in AUDIT_KEYS "
          "order, a hand-computed line with no trailing space, an absent target "
          "spelled `-`, a closed vocabulary whose first reason is `granted` and "
          "whose decisions are not reasons; a `bytes` that is a bool and every "
          "field that is empty, misplaced or a sentence refused by name, with a "
          "suggestion inside two edits and none beyond it; a reader that is the "
          "exact inverse and refuses by index and by text; and a writer that "
          "validates before it records, writes the caller's mapping in "
          "AUDIT_KEYS order, and returns the sink's own count")

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "sandbox-capabilities-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J4_REPO=/path/to/forja")

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

    import stage_01 as s1
    import stage_07 as s7
    import stage_08 as s
    import tools as world
    import vfs as fs

    # ---- the constants, and the family -----------------------------------

    assert s.DECISION_KEYS == ("allowed", "reason", "target", "bytes", "detail"), (
        "a decision is %r, not the five fields the course defined, in order"
        % (s.DECISION_KEYS,))
    assert s.OBSERVATION_KEYS == ("tool", "target", "decision", "reason", "bytes",
                                  "value"), (
        "an observation is %r, not the six fields the course froze, in order"
        % (s.OBSERVATION_KEYS,))
    assert issubclass(s.CallError, s1.SandboxError), (
        "%r is not a %s: one `except SandboxError` must still catch a broken call"
        % (s.CallError, s1.SandboxError.__name__))
    assert issubclass(s.CallError, ValueError), (
        "%r is not a ValueError: the course's refusals are value errors"
        % (s.CallError,))
    assert s7.REASONS == ("granted", "unknown", "capability", "jail", "host",
                          "limit", "secret"), (
        "stage 7's reasons moved; stage 8 must speak its closed vocabulary, not "
        "a second one: %r" % (s7.REASONS,))
    assert s7.DECISIONS == ("allowed", "denied"), (
        "stage 7's decisions moved: %r" % (s7.DECISIONS,))

    # ---- a policy, and a fresh world for every question ------------------

    ANALYST = {"principal": "analyst", "root": "/home/agent",
               "capabilities": ("fs:read", "net:connect"),
               "hosts": ("api.internal:443",)}
    BUILDER = {"principal": "builder", "root": "/home/agent",
               "capabilities": ("fs:read", "fs:write", "fs:delete", "proc:spawn"),
               "hosts": ("api.internal:443", "registry.internal:5000")}
    INTERN = {"principal": "intern", "root": "/home/agent/src",
              "capabilities": (), "hosts": ()}
    KEEPER = {"principal": "vaultkeeper", "root": "/home/agent",
              "capabilities": ("fs:read", "secret:read"), "hosts": ()}

    def decide(call, policy=ANALYST, meter=None):
        return s.decide(call, policy, vfs=fs.VFS(), wire=world.Wire(),
                        meter=meter or world.Meter(), vault=world.Vault())

    def call_decide(call, policy=ANALYST):
        return s.decide(call, policy, vfs=fs.VFS(), wire=world.Wire(),
                        meter=world.Meter(), vault=world.Vault())

    def denial(call, policy=ANALYST, meter=None):
        got = decide(call, policy, meter)
        assert isinstance(got, dict) and got["allowed"] is False, (
            "a call the policy must refuse was not denied as data: %r" % (got,))
        assert set(got) == set(s.DECISION_KEYS), (
            "a decision carries %r, not exactly DECISION_KEYS" % (sorted(got),))
        assert got["bytes"] == 0, (
            "a denial predicts %r bytes; every denial is 0" % (got["bytes"],))
        assert got["reason"] in s7.REASONS, (
            "the denial's reason %r is outside the closed vocabulary"
            % (got["reason"],))
        return got

    # ---- 1: unknown -------------------------------------------------------

    got = denial({"tool": "nope", "target": "/home/agent/notes.md"})
    assert got["reason"] == "unknown", ("an unknown tool answers %r, not "
                                        "`unknown`" % (got["reason"],))
    assert got["detail"].get("tool") == "nope", (
        "the `unknown` denial does not name the tool it did not find: %r"
        % (got["detail"],))
    got = denial({"tool": "nope", "target": "API.internal"})
    assert got["reason"] == "unknown" and got["target"] == "API.internal", (
        "an unknown tool was not the first no: %r" % (got,))

    # ---- 2: capability ----------------------------------------------------

    got = denial({"tool": "read_file", "target": "/home/agent/src/main.py"},
                 INTERN)
    assert got["reason"] == "capability" and got["detail"]["missing"] == ("fs:read",), (
        "a short grant answers %r, not `capability` with the missing demand: %r"
        % (got["reason"], got))
    assert got["target"] == "/home/agent/src/main.py", (
        "a denial before the jail must carry the call's raw target: %r" % (got,))
    got = denial({"tool": "debug_dump", "target": "/home/agent/notes.md"}, BUILDER)
    assert got["reason"] == "capability" and got["detail"]["missing"] == ("net:connect",), (
        "the half-grant of debug_dump answers %r, not `capability` with "
        "`net:connect`: %r" % (got["reason"], got))
    got = denial({"tool": "teleport", "target": "/home/agent/notes.md"}, ANALYST)
    assert got["reason"] == "capability" and "fs:teleport" in repr(got["detail"]), (
        "a tool whose demand this world cannot read must be `capability`, never "
        "`unknown`, and name the demand: %r" % (got,))

    # ---- the first no wins: capability beats jail and limit ---------------

    got = denial({"tool": "read_file", "target": "/home/agent-other/notes.md"},
                 INTERN, world.Meter({"cpu": 0, "memory": 0, "ticks": 0,
                                      "calls": 0}))
    assert got["reason"] == "capability", (
        "a call with a short grant, an outside path and an empty meter answered "
        "%r; the grant is question 2 and the first no wins" % (got["reason"],))

    # ---- 3: jail ----------------------------------------------------------

    got = denial({"tool": "read_file", "target": "/home/agent-other/notes.md"})
    assert got["reason"] == "jail", (
        "the sibling root answered %r, not `jail` — a jail is not a string test"
        % (got["reason"],))
    assert got["target"] == "/home/agent-other/notes.md", (
        "the jail denial's target is %r, not the resolved path" % (got["target"],))
    assert got["detail"].get("target") == "/home/agent-other/notes.md", (
        "the jail detail does not name the refused target: %r" % (got["detail"],))
    assert got["detail"].get("root") == "/home/agent", (
        "the jail detail does not name the root: %r" % (got["detail"],))
    got = denial({"tool": "read_file",
                  "target": "/home/agent/../agent-other/notes.md"})
    assert got["reason"] == "jail" and got["target"] == "/home/agent-other/notes.md", (
        "the decision's target for a jailed call is the resolved path, not the "
        "raw one: %r" % (got,))
    assert got["detail"]["target"] == "/home/agent/../agent-other/notes.md", (
        "the jail detail must carry the refused request, not the resolution: %r"
        % (got["detail"],))
    got = denial({"tool": "read_file", "target": "/etc/passwd"})
    assert got["reason"] == "jail" and got["target"] == "/etc/passwd", (
        "/etc/passwd answered %r, not `jail`" % (got["reason"],))
    got = denial({"tool": "shell", "target": "/home/agent-other", "value": "ls"},
                 BUILDER)
    assert got["reason"] == "jail", (
        "a process tool's working directory answered %r, not `jail`"
        % (got["reason"],))

    # ---- 4: host ----------------------------------------------------------

    got = denial({"tool": "http_get", "target": "db.internal"})
    assert got["reason"] == "host", (
        "a host the policy does not reach answered %r, not `host`"
        % (got["reason"],))
    assert got["target"] == "db.internal", (
        "a host denial's target is %r, not the host's name" % (got["target"],))
    assert got["detail"].get("specs") == ("api.internal:443",), (
        "the host detail does not name the policy's specs: %r" % (got["detail"],))
    assert got["detail"].get("wildcard") is False, (
        "the host detail does not answer the wildcard question: %r"
        % (got["detail"],))
    got = denial({"tool": "http_get", "target": "nowhere.internal"})
    assert got["reason"] == "host", (
        "a host the catalogue does not have answered %r, not `host`"
        % (got["reason"],))

    # ---- 5: limit ---------------------------------------------------------

    small = world.Meter({"cpu": 0, "memory": 0, "ticks": 0, "calls": 0})
    got = denial({"tool": "read_file", "target": "/home/agent/notes.md"},
                 ANALYST, small)
    assert got["reason"] == "limit", (
        "a cost the meter cannot pay answered %r, not `limit`" % (got["reason"],))
    assert set(got["detail"]["short"]) == {"cpu", "ticks", "calls"}, (
        "the `limit` detail does not carry stage 5's own `short`: %r"
        % (got["detail"],))
    assert small.used() == {"cpu": 0, "memory": 0, "ticks": 0, "calls": 0}, (
        "deciding spent the meter: the charge is at act time, never here")

    # ---- 6: secret --------------------------------------------------------

    got = denial({"tool": "get_secret", "target": "nope"}, KEEPER)
    assert got["reason"] == "secret" and got["detail"].get("handle") == "nope", (
        "a handle the vault does not hold answered %r, not `secret` naming the "
        "handle: %r" % (got["reason"], got))
    assert got["target"] == "nope", got
    allowed = decide({"tool": "get_secret", "target": "deploy-key"}, KEEPER)
    assert allowed["allowed"] is True and allowed["reason"] == "granted", (
        "a handle the vault holds was not granted: %r" % (allowed,))
    assert allowed["bytes"] == 0, (
        "a secret travels as a fingerprint, so its prediction is 0, not %r"
        % (allowed["bytes"],))
    assert allowed["target"] == "deploy-key", allowed
    allowed = decide({"tool": "env_dump"}, KEEPER)
    assert allowed["allowed"] is True and allowed["target"] == "", (
        "the one `none` tool asks nobody and carries no target: %r" % (allowed,))

    # ---- the bytes prediction, checked against the world's own numbers ----

    notes = fs.VFS().stat("/home/agent/notes.md")["bytes"]
    got = decide({"tool": "read_file", "target": "/home/agent/notes.md"})
    assert got["allowed"] and got["bytes"] == notes, (
        "a read predicts %r bytes, not the file's own %d" % (got["bytes"], notes))
    got = decide({"tool": "read_file", "target": "/home/agent/./notes.md"})
    assert got["allowed"] and got["bytes"] == notes, (
        "a read of a path that has to be resolved predicts wrongly: %r" % (got,))
    assert got["target"] == "/home/agent/notes.md", (
        "an allowed call's target is %r, not the resolved path" % (got["target"],))
    got = decide({"tool": "write_file", "target": "/home/agent/report.md",
                  "value": "published\n"}, BUILDER)
    assert got["allowed"] and got["bytes"] == 10, (
        "a write predicts %r bytes, not its value's length" % (got["bytes"],))
    run = fs.VFS().stat("/home/agent/logs/run.txt")["bytes"]
    got = decide({"tool": "remove_file", "target": "/home/agent/logs/run.txt"},
                 BUILDER)
    assert got["allowed"] and got["bytes"] == run, (
        "a remove predicts %r bytes, not the file's old length" % (got["bytes"],))
    got = decide({"tool": "list_dir", "target": "/home/agent"})
    assert got["allowed"] and got["bytes"] == 0, (
        "a listing moves no bytes, so its prediction is 0, not %r"
        % (got["bytes"],))
    got = decide({"tool": "http_get", "target": "api.internal"})
    assert got["allowed"] and got["bytes"] == 512, (
        "a host tool predicts %r bytes, not the catalogue's own number"
        % (got["bytes"],))
    got = decide({"tool": "shell", "target": "/home/agent", "value": "ls"},
                 BUILDER)
    assert got["allowed"] and got["bytes"] == 0, (
        "what a scripted command will touch is not knowable, so a process tool's "
        "prediction is 0, not %r" % (got["bytes"],))

    # ---- a fresh decision every time --------------------------------------

    first = decide({"tool": "read_file", "target": "/home/agent/notes.md"})
    second = decide({"tool": "read_file", "target": "/home/agent/notes.md"})
    assert first == second and first is not second, (
        "decide handed back the same mapping twice: a decision is fresh data")

    # ---- CallError: the shapes nothing can be said about ------------------

    message = _refuses(s.CallError, "a call that is not a mapping",
                       lambda: call_decide(("tick", 2)))
    assert "must be a mapping" in message, (
        "the refusal of a non-mapping call does not say the call's shape is the "
        "mistake: %r" % (message,))
    message = _refuses(s.CallError, "a call that names no tool",
                       lambda: call_decide({"target": "/home/agent/notes.md"}))
    assert "tool" in message, (
        "the refusal of a call with no tool does not name the field: %r"
        % (message,))
    for bad, spelling in ((5, "int"), (None, "NoneType")):
        message = _refuses(s.CallError, "a tool that is %r" % (bad,),
                           lambda bad=bad: call_decide({"tool": bad}))
        assert "tool" in message and spelling in message, (
            "the refusal of a %r tool does not name the field and its type: %r"
            % (bad, message))
    message = _refuses(s.CallError, "a target that is not a str",
                       lambda: call_decide({"tool": "read_file", "target": 5}))
    assert "target" in message, (
        "the refusal of a non-str target does not name the field: %r"
        % (message,))
    message = _refuses(s.CallError, "a value that is not a str",
                       lambda: call_decide({"tool": "write_file",
                                            "target": "/home/agent/x",
                                            "value": 5}))
    assert "value" in message, (
        "the refusal of a non-str value does not name the field: %r"
        % (message,))
    message = _refuses(s.CallError, "a policy that is not a mapping",
                       lambda: call_decide({"tool": "read_file",
                                            "target": "/home/agent/notes.md"},
                                           "nope"))
    assert "must be a mapping" in message, (
        "the refusal of a non-mapping policy does not say the policy's shape is "
        "the mistake: %r" % (message,))
    short = {"principal": "analyst", "capabilities": ("fs:read",),
             "hosts": ()}
    message = _refuses(s.CallError, "a policy missing a field",
                       lambda: call_decide({"tool": "read_file",
                                            "target": "/home/agent/notes.md"},
                                           short))
    assert "root" in message, (
        "the refusal of a policy with no `root` does not name the field: %r"
        % (message,))
    message = _refuses(s.CallError, "a host name with an upper-case letter",
                       lambda: call_decide({"tool": "http_get",
                                            "target": "API.internal"}))
    assert "API.internal" in message or "host" in message, (
        "the refusal of an upper-case host target does not name the offender: %r"
        % (message,))
    message = _refuses(s.CallError, "an empty host target",
                       lambda: call_decide({"tool": "http_get", "target": ""}))
    assert "host" in message, (
        "the refusal of an empty host target does not name the field: %r"
        % (message,))
    message = _refuses(s.CallError, "a target on the one `none` tool",
                       lambda: call_decide({"tool": "env_dump",
                                            "target": "/home/agent/notes.md"}))
    assert "target" in message and "env_dump" in message, (
        "the refusal of a target on env_dump does not name the tool and the "
        "field: %r" % (message,))

    # ---- a denial touches nothing and spends nothing ----------------------

    class PoisonVFS(fs.VFS):
        def read(self, path):
            raise AssertionError("a denied call reached VFS.read")

        def write(self, path, text):
            raise AssertionError("a denied call reached VFS.write")

        def remove(self, path):
            raise AssertionError("a denied call reached VFS.remove")

        def list(self, path):
            raise AssertionError("a denied call reached VFS.list")

    class PoisonWire(world.Wire):
        def dial(self, host, port):
            raise AssertionError("a denied call reached Wire.dial")

    class PoisonVault(world.Vault):
        def read(self, handle):
            raise AssertionError("a denied call reached Vault.read")

        def handles(self):
            raise AssertionError("a denied call reached Vault.handles")

    empty = world.Meter({"cpu": 0, "memory": 0, "ticks": 0, "calls": 0})
    for call, policy, meter in (
            ({"tool": "nope", "target": "/home/agent/notes.md"}, ANALYST, None),
            ({"tool": "read_file", "target": "/home/agent/notes.md"}, INTERN, None),
            ({"tool": "teleport", "target": "/home/agent/notes.md"}, ANALYST, None),
            ({"tool": "read_file", "target": "/etc/passwd"}, ANALYST, None),
            ({"tool": "http_get", "target": "db.internal"}, ANALYST, None),
            ({"tool": "read_file", "target": "/home/agent/notes.md"}, ANALYST, empty),
            ({"tool": "get_secret", "target": "nope"}, KEEPER, None)):
        vfs, wire, vault = PoisonVFS(), PoisonWire(), PoisonVault()
        use = meter or world.Meter()
        audit = world.Audit()
        guard = s.Guard(policy, vfs=vfs, wire=wire, vault=vault, meter=use,
                        audit=audit)
        obs = guard.invoke(call)
        assert obs["decision"] == "denied", (
            "a denied call's observation says %r" % (obs["decision"],))
        assert obs["value"] is None, (
            "a denial carries the reason and nothing else: value is %r"
            % (obs["value"],))
        assert set(obs) == set(s.OBSERVATION_KEYS), (
            "the observation carries %r, not exactly OBSERVATION_KEYS"
            % (sorted(obs),))
        assert use.used() == {"cpu": 0, "memory": 0, "ticks": 0, "calls": 0}, (
            "a denied call charged the meter: %r" % (use.used(),))
        assert vfs.log() == () and wire.dialled() == () and vault.reads() == (), (
            "a denied call left a record behind: %r %r %r"
            % (vfs.log(), wire.dialled(), vault.reads()))
        assert len(audit.lines()) == 1, (
            "a denied call wrote %d lines, not the one intent it must leave"
            % (len(audit.lines()),))
        entry = s7.parse_line(audit.lines()[0])
        assert entry["decision"] == "denied", (
            "the line of a denial says %r" % (entry["decision"],))
        assert entry["reason"] == obs["reason"] and entry["bytes"] == 0, (
            "the line of a denial does not carry its reason and a zero count: %r"
            % (entry,))
        assert entry["target"] == obs["target"] and entry["tool"] == call["tool"], (
            "the line of a denial names the wrong call: %r" % (entry,))

    # ---- the act, through the world, and the line before it ---------------

    text = fs.VFS().read("/home/agent/notes.md")
    vfs, wire, vault, meter, audit = (fs.VFS(), world.Wire(), world.Vault(),
                                      world.Meter(), world.Audit())
    guard = s.Guard(ANALYST, vfs=vfs, wire=wire, vault=vault, meter=meter,
                    audit=audit)
    obs = guard.invoke({"tool": "read_file", "target": "/home/agent/notes.md"})
    assert set(obs) == set(s.OBSERVATION_KEYS), sorted(obs)
    assert obs["decision"] == "allowed" and obs["reason"] == "granted", obs
    assert obs["value"] == text and obs["bytes"] == notes, (
        "a read's observation carries %r/%r, not the text and its length"
        % (obs["value"], obs["bytes"]))
    assert vfs.log() == (("read", "/home/agent/notes.md", notes),), (
        "the world's own record is %r, not the read it was made to do"
        % (vfs.log(),))
    entry = s7.parse_line(audit.lines()[0])
    assert entry == {"tick": 0, "principal": "analyst", "tool": "read_file",
                     "target": "/home/agent/notes.md", "decision": "allowed",
                     "reason": "granted", "bytes": notes}, entry
    assert obs["bytes"] == vfs.log()[0][2], (
        "the prediction and the world's own number disagree: %r vs %r"
        % (obs["bytes"], vfs.log()[0][2]))

    vfs, meter, audit = fs.VFS(), world.Meter(), world.Audit()
    guard = s.Guard(ANALYST, vfs=vfs, wire=world.Wire(), vault=world.Vault(),
                    meter=meter, audit=audit)
    obs = guard.invoke({"tool": "read_file", "target": "/home/agent/./notes.md"})
    assert obs["value"] == text and obs["target"] == "/home/agent/notes.md", (
        "the act ran against %r, not the resolved target: %r"
        % (obs["target"], obs))
    assert vfs.log() == (("read", "/home/agent/notes.md", notes),), (
        "the act touched %r, not the resolved path" % (vfs.log(),))

    vfs, meter, audit = fs.VFS(), world.Meter(), world.Audit()
    guard = s.Guard(BUILDER, vfs=vfs, wire=world.Wire(), vault=world.Vault(),
                    meter=meter, audit=audit)
    obs = guard.invoke({"tool": "write_file", "target": "/home/agent/report.md",
                        "value": "published\n"})
    assert obs["bytes"] == 10 and obs["value"] == 10, obs
    assert vfs.log() == (("write", "/home/agent/report.md", 10),), (
        "the write's own record is %r" % (vfs.log(),))
    assert meter.used() == {"cpu": 2, "memory": 64, "ticks": 2, "calls": 1}, (
        "a write's cost was not charged exactly once: %r" % (meter.used(),))
    assert s7.parse_line(audit.lines()[0])["bytes"] == 10, (
        "the line's byte count disagrees with the world's own number")

    vfs, meter, audit = fs.VFS(), world.Meter(), world.Audit()
    guard = s.Guard(BUILDER, vfs=vfs, wire=world.Wire(), vault=world.Vault(),
                    meter=meter, audit=audit)
    obs = guard.invoke({"tool": "remove_file", "target": "/home/agent/logs/run.txt"})
    assert obs["bytes"] == run and obs["value"] == run, obs
    assert vfs.log() == (("remove", "/home/agent/logs/run.txt", run),), (
        "the remove's own record is %r" % (vfs.log(),))

    vfs, wire, audit = fs.VFS(), world.Wire(), world.Audit()
    expected = len(vfs.list("/home/agent"))
    vfs = fs.VFS()
    guard = s.Guard(BUILDER, vfs=vfs, wire=wire, vault=world.Vault(),
                    meter=world.Meter(), audit=audit)
    obs = guard.invoke({"tool": "shell", "target": "/home/agent", "value": "ls"})
    assert obs["value"] == {"command": "ls", "op": "list",
                            "target": "/home/agent", "bytes": expected}, (
        "the shell's observation is %r, not the world's own record" % (obs["value"],))
    assert vfs.log() == (("list", "/home/agent", expected),), vfs.log()
    assert obs["bytes"] == 0, (
        "a process tool predicts 0 bytes, not %r" % (obs["bytes"],))

    wire, audit = world.Wire(), world.Audit()
    guard = s.Guard(ANALYST, vfs=fs.VFS(), wire=wire, vault=world.Vault(),
                    meter=world.Meter(), audit=audit)
    obs = guard.invoke({"tool": "http_get", "target": "api.internal"})
    assert obs["value"] == {"host": "api.internal", "port": 443, "bytes": 512}, (
        "the dial's observation is %r, not the wire's own record" % (obs["value"],))
    assert wire.dialled() == (("api.internal", 443),), wire.dialled()
    assert obs["bytes"] == 512, obs

    vault, audit = world.Vault(), world.Audit()
    guard = s.Guard(KEEPER, vfs=fs.VFS(), wire=world.Wire(), vault=vault,
                    meter=world.Meter(), audit=audit)
    obs = guard.invoke({"tool": "get_secret", "target": "deploy-key"})
    assert set(obs["value"]) == {"handle", "present", "bytes", "digest"}, obs["value"]
    assert obs["value"]["handle"] == "deploy-key" and obs["value"]["present"] is True, obs
    assert "sk-live-9f31c2ab7d" not in repr(obs), (
        "the observation carries the secret's value: %r" % (obs,))
    assert vault.reads() == ("deploy-key",), vault.reads()
    assert s7.parse_line(audit.lines()[0])["principal"] == "vaultkeeper", audit.lines()

    vault, audit = world.Vault(), world.Audit()
    guard = s.Guard(KEEPER, vfs=fs.VFS(), wire=world.Wire(), vault=vault,
                    meter=world.Meter(), audit=audit)
    obs = guard.invoke({"tool": "env_dump"})
    assert isinstance(obs["value"], tuple), (
        "`env_dump` hands back a tuple of observations, got %r" % (obs["value"],))
    assert len(obs["value"]) == len(vault.handles()) == 3, obs["value"]
    for item in obs["value"]:
        assert set(item) == {"handle", "present", "bytes", "digest"}, item
    assert "sk-live-9f31c2ab7d" not in repr(obs), (
        "the environment dump carries a secret's value: %r" % (obs,))
    assert len(vault.reads()) == 3, (
        "`env_dump` read %d handles, not the whole environment" % (len(vault.reads()),))

    # ---- the tick: the clock's, or the line count -------------------------

    audit = world.Audit()
    guard = s.Guard(ANALYST, vfs=fs.VFS(), wire=world.Wire(),
                    vault=world.Vault(), meter=world.Meter(), audit=audit)
    guard.invoke({"tool": "list_dir", "target": "/home/agent"})
    guard.invoke({"tool": "list_dir", "target": "/home/agent"})
    ticks = [s7.parse_line(one)["tick"] for one in audit.lines()]
    assert ticks == [0, 1], (
        "with no clock the tick is the line count, so two calls stamp 0 and 1, "
        "not %r" % (ticks,))
    audit = world.Audit()
    guard = s.Guard(ANALYST, vfs=fs.VFS(), wire=world.Wire(),
                    vault=world.Vault(), meter=world.Meter(), audit=audit,
                    clock=lambda: 7)
    guard.invoke({"tool": "list_dir", "target": "/home/agent"})
    assert s7.parse_line(audit.lines()[0])["tick"] == 7, (
        "the injected clock's tick was not stamped: %r" % (audit.lines(),))

    # ---- Guard delegates, and the free `invoke` is the act ----------------

    guard = s.Guard(ANALYST, vfs=fs.VFS(), wire=world.Wire(),
                    vault=world.Vault(), meter=world.Meter(), audit=world.Audit())
    assert guard.decide({"tool": "read_file",
                         "target": "/home/agent/notes.md"})["allowed"] is True, (
        "Guard.decide does not answer §3.1's questions")
    obs = s.invoke(guard, {"tool": "read_file", "target": "/home/agent/notes.md"})
    assert obs["decision"] == "allowed" and obs["value"] == text, (
        "the free `invoke` did not perform the act: %r" % (obs,))
    assert repr(guard).startswith("<Guard"), (
        "Guard.__repr__ is not a readable one: %r" % (repr(guard),))

    print("check_08: the composer — six questions in order with the first no "
          "deciding, a denial returned as data that touches nothing and spends "
          "nothing while still writing its line before the act, a byte "
          "prediction that is the world's own number, and a frozen observation "
          "whose `value` is `None` for every denial")

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "sandbox-capabilities-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J4_REPO=/path/to/forja")

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

    import tools as world
    import vfs as fs

    import stage_07 as s7
    import stage_09 as s

    def entry(tick, principal, tool, target, decision, reason, bytes):
        """One audit entry, built the only way the course builds one."""
        return s7.parse_line(s7.line(tick, principal=principal, tool=tool,
                                     target=target, decision=decision,
                                     reason=reason, bytes=bytes))

    def fresh(secrets=None):
        """A fresh world, with nothing in any of the three records yet."""
        return {"vfs": fs.VFS(), "wire": world.Wire(),
                "vault": world.Vault(secrets), "meter": world.Meter()}

    def call(box, entries):
        return s.report(entries, meter=box["meter"], vfs=box["vfs"],
                        wire=box["wire"], vault=box["vault"])

    def sweep(box, entries):
        return s.audit(entries, vfs=box["vfs"], wire=box["wire"],
                       vault=box["vault"])

    # ---- the vocabulary, and the family ----------------------------------

    assert s.REPORT_KEYS == ("principal", "calls", "allowed", "denied",
                             "capabilities", "paths", "bytes", "hosts", "secrets",
                             "cpu", "memory", "ticks"), (
        "this stage's report fields are %r, not the twelve the course defined, "
        "in order" % (s.REPORT_KEYS,))
    assert issubclass(s.SandboxError, ValueError), (
        "%r is not a ValueError: the course's refusal is a named error a caller "
        "can catch" % (s.SandboxError,))
    assert issubclass(s.ReportError, s.SandboxError), (
        "%r is not a %s: one `except SandboxError` must still catch a broken "
        "report" % (s.ReportError, s.SandboxError.__name__))

    # ---- an empty run is a report of zeros, not an error ------------------

    empty = s.report((), meter=world.Meter(), vfs=fs.VFS(), wire=world.Wire(),
                     vault=world.Vault())
    assert tuple(empty) == s.REPORT_KEYS, (
        "the report's fields are %r, not REPORT_KEYS in order: a report is read "
        "by position as often as by name" % (tuple(empty),))
    assert empty == {"principal": "", "calls": 0, "allowed": 0, "denied": 0,
                     "capabilities": (), "paths": (), "bytes": 0, "hosts": (),
                     "secrets": 0, "cpu": 0, "memory": 0, "ticks": 0}, (
        "an empty run reports %r: a run that touched nothing is a report of "
        "zeros, not an error" % (empty,))

    # ---- the twelve counters, from the lines and the meter ----------------

    box = fresh()
    text = box["vfs"].read("/home/agent/notes.md")
    box["meter"].spend({"cpu": 5, "memory": 7, "ticks": 3})
    read = entry(0, "analyst", "read_file", "/home/agent/notes.md", "allowed",
                 "granted", len(text))
    report = call(box, (read,))
    assert tuple(report) == s.REPORT_KEYS, (
        "the report's fields are %r, not REPORT_KEYS in order" % (tuple(report),))
    assert report["principal"] == "analyst" and report["calls"] == 1, (
        "the principal and the call count come from the lines: %r" % (report,))
    assert report["allowed"] == 1 and report["denied"] == 0, (
        "the decisions are counted from the lines, not assumed: %r" % (report,))
    assert report["capabilities"] == ("fs:read",), (
        "the capabilities are the allowed calls' own demand, looked up in the "
        "catalogue: %r" % (report["capabilities"],))
    assert report["paths"] == ("/home/agent/notes.md",), (
        "the paths are the allowed path calls' targets: %r" % (report["paths"],))
    assert report["bytes"] == len(text), (
        "the bytes are the allowed entries' own counts: %r" % (report["bytes"],))
    assert report["hosts"] == () and report["secrets"] == 0, (
        "a run that dialled nothing and read no secret reports neither: %r"
        % (report,))
    assert (report["cpu"], report["memory"], report["ticks"]) == (5, 7, 3), (
        "cpu, memory and ticks are the meter's own counters, not the entries': %r"
        % (report,))
    assert s.touched((read,)) == ("/home/agent/notes.md",), (
        "touched is the sorted distinct allowed targets: %r"
        % (s.touched((read,)),))

    # a capability used twice is one capability, not two
    box = fresh()
    text = box["vfs"].read("/home/agent/notes.md")
    count = len(box["vfs"].list("/home/agent"))
    two = (entry(0, "analyst", "read_file", "/home/agent/notes.md", "allowed",
                 "granted", len(text)),
           entry(1, "analyst", "list_dir", "/home/agent", "allowed", "granted", 0))
    report = call(box, two)
    assert report["capabilities"] == ("fs:read",), (
        "two allowed calls that demand the same capability report it once, sorted: "
        "%r" % (report["capabilities"],))
    assert report["paths"] == ("/home/agent", "/home/agent/notes.md"), (
        "the paths are sorted across the allowed calls: %r" % (report["paths"],))
    assert report["bytes"] == len(text), (
        "a list line's bytes is 0, so it adds nothing: %r" % (report["bytes"],))
    assert count != 0, (
        "the check's own fixture is wrong: /home/agent has no children to list")
    assert sweep(box, two)["missing"] == () and sweep(box, two)["extra"] == (), (
        "a report whose lines and world agree is not an audit disagreement: %r"
        % (sweep(box, two),))

    # two distinct capabilities are reported in sorted order, and a process
    # tool's target is a path the run touched
    box = fresh()
    text = box["vfs"].read("/home/agent/notes.md")
    box["vfs"].list("/home/agent")
    mixed = (entry(0, "builder", "read_file", "/home/agent/notes.md", "allowed",
                   "granted", len(text)),
             entry(1, "builder", "shell", "/home/agent", "allowed", "granted", 0))
    report = call(box, mixed)
    assert report["capabilities"] == ("fs:read", "proc:spawn"), (
        "two different demands are reported sorted: %r"
        % (report["capabilities"],))
    assert report["paths"] == ("/home/agent", "/home/agent/notes.md"), (
        "a process tool's target is a path in the report: %r"
        % (report["paths"],))
    assert report["bytes"] == len(text), (
        "a process tool's line carries no bytes, so it adds none: %r"
        % (report["bytes"],))

    # touched is sorted, not in the order the calls happened
    box = fresh()
    first = box["vfs"].read("/home/agent/notes.md")
    second = box["vfs"].read("/home/agent/.env")
    ordered = (entry(0, "analyst", "read_file", "/home/agent/notes.md",
                     "allowed", "granted", len(first)),
               entry(1, "analyst", "read_file", "/home/agent/.env", "allowed",
                     "granted", len(second)))
    assert s.touched(ordered) == ("/home/agent/.env", "/home/agent/notes.md"), (
        "touched is sorted, not in the order the calls happened: %r"
        % (s.touched(ordered),))
    assert call(box, ordered)["paths"] == ("/home/agent/.env",
                                           "/home/agent/notes.md"), (
        "the report's paths are sorted too: %r" % (call(box, ordered),))

    # ---- a denied entry is not something the run touched ------------------

    box = fresh()
    text = box["vfs"].read("/home/agent/notes.md")
    pair = (entry(0, "analyst", "read_file", "/home/agent/notes.md", "allowed",
                  "granted", len(text)),
            entry(1, "analyst", "read_file", "/etc/passwd", "denied", "jail", 0))
    report = call(box, pair)
    assert report["calls"] == 2 and report["allowed"] == 1, (
        "a denied call is still a call: %r" % (report,))
    assert report["denied"] == 1, (
        "a denied call is counted as denied: %r" % (report,))
    assert report["paths"] == ("/home/agent/notes.md",), (
        "a denied entry is not counted in paths — it names a target the sandbox "
        "refused, and the run touched the other one: %r" % (report["paths"],))
    assert "/etc/passwd" not in report["paths"], (
        "the denied target reached the report's paths: %r" % (report["paths"],))
    assert s.touched(pair) == ("/home/agent/notes.md",), (
        "touched includes the denied target: %r" % (s.touched(pair),))

    # a denied call's target is in none of the three records, and the report
    # still agrees with the world
    box = fresh()
    text = box["vfs"].read("/home/agent/notes.md")
    denied_host = (entry(0, "analyst", "read_file", "/home/agent/notes.md",
                         "allowed", "granted", len(text)),
                   entry(1, "analyst", "http_get", "db.internal", "denied",
                         "host", 0))
    report = call(box, denied_host)
    assert report["hosts"] == () and report["denied"] == 1, (
        "a denied host call is not in the report's hosts: %r" % (report,))
    assert box["wire"].dialled() == (), (
        "the denied call reached the wire: %r" % (box["wire"].dialled(),))

    # ---- the cross-check: the world is the tie-breaker --------------------

    # a line the world does not hold
    box = fresh()
    text = box["vfs"].read("/home/agent/notes.md")
    invented = entry(0, "analyst", "read_file", "/home/agent/never-touched.md",
                     "allowed", "granted", len(text))
    report_out = sweep(box, (invented,))
    assert report_out["extra"] and report_out["extra"][0][0]["target"] == (
        "/home/agent/never-touched.md"), (
        "a line the world does not hold is an extra, paired with no record: %r"
        % (report_out,))
    assert report_out["count"] == 1, (
        "the audit's count is the number of entries looked at: %r"
        % (report_out,))
    message = _refuses(s.ReportError, "a line the world does not hold",
                       lambda: call(box, (invented,)))
    assert "never-touched" in message, (
        "the refusal of an invented line does not name it: %r" % (message,))

    # a record no line accounts for
    box = fresh()
    box["vfs"].list("/home/agent")
    report_out = sweep(box, ())
    assert report_out["missing"] and report_out["count"] == 0, (
        "a touch with no line is reported as missing, not raised: %r"
        % (report_out,))
    assert report_out["missing"][0][1][1] == "/home/agent", (
        "the missing item pairs the record it is: %r" % (report_out["missing"],))
    message = _refuses(s.ReportError, "a world touched with no line",
                       lambda: call(box, ()))
    assert "no allowed line accounts for" in message, (
        "the refusal of an unaccounted record does not say so: %r" % (message,))

    # a byte count the world contradicts
    box = fresh()
    text = box["vfs"].read("/home/agent/notes.md")
    wrong = entry(0, "analyst", "read_file", "/home/agent/notes.md", "allowed",
                  "granted", len(text) + 1)
    report_out = sweep(box, (wrong,))
    assert report_out["extra"] and report_out["extra"][0][1] is not None, (
        "a line whose bytes the world contradicts pairs the line and the record: "
        "%r" % (report_out,))
    message = _refuses(s.ReportError, "a byte count the world contradicts",
                       lambda: call(box, (wrong,)))
    assert "notes.md" in message, (
        "the refusal of a byte mismatch does not name the line: %r" % (message,))

    # a `list` line's bytes is 0 and is not compared against the world's count
    box = fresh()
    count = len(box["vfs"].list("/home/agent"))
    listed = entry(0, "analyst", "list_dir", "/home/agent", "allowed", "granted",
                   0)
    report = call(box, (listed,))
    assert report["paths"] == ("/home/agent",), (
        "a list line's target is a path the run touched: %r" % (report["paths"],))
    assert count != 0, (
        "the check's own fixture is wrong: /home/agent has no children to list")

    # a process tool's target is the directory it worked in, and what it touched
    # is inside it: `cat` inside `/home/agent` logs a read of a file in there
    box = fresh()
    box["vfs"].read("/home/agent/notes.md")
    shelled = entry(0, "builder", "shell", "/home/agent", "allowed", "granted", 0)
    report = call(box, (shelled,))
    assert report["paths"] == ("/home/agent",), (
        "a process tool's target is a path the report names: %r"
        % (report["paths"],))
    assert sweep(box, (shelled,))["missing"] == () and sweep(
        box, (shelled,))["extra"] == (), (
        "a file inside an allowed process target is explained by the shell line: "
        "%r" % (sweep(box, (shelled,)),))

    # a log entry outside every process target, with no path line to explain it
    box = fresh()
    box["vfs"].read("/etc/passwd")
    message = _refuses(
        s.ReportError, "a touch outside every process target",
        lambda: call(box, (entry(0, "builder", "shell", "/home/agent", "allowed",
                                 "granted", 0),)))
    assert "passwd" in message, (
        "a log entry outside every process target is not named: %r" % (message,))

    # a path a denied line names is not excused by a process target: a denial
    # adds nothing, even where an allowed call legitimately touched the same tree
    box = fresh()
    box["vfs"].read("/home/agent/notes.md")
    shelled = entry(0, "builder", "shell", "/home/agent", "allowed", "granted", 0)
    denied = entry(1, "builder", "read_file", "/home/agent/notes.md", "denied",
                   "capability", 0)
    message = _refuses(
        s.ReportError, "a path only a denied line named",
        lambda: call(box, (shelled, denied)))
    assert "notes.md" in message, (
        "a denied path the record nonetheless holds is not named: %r"
        % (message,))

    # a host the wire never dialled
    box = fresh()
    dialled = box["wire"].dial("api.internal", 443)
    host = entry(0, "analyst", "http_get", "api.internal", "allowed", "granted",
                 dialled["bytes"])
    report = call(box, (host,))
    assert report["hosts"] == ("api.internal",) and report["bytes"] == (
        dialled["bytes"]), (
        "the allowed host call reports the host it dialled: %r" % (report,))
    unseen = entry(0, "analyst", "http_get", "db.internal", "allowed", "granted",
                   1)
    message = _refuses(s.ReportError, "a host the wire never dialled",
                       lambda: call(fresh(), (unseen,)))
    assert "db.internal" in message, (
        "the refusal of an undialled host does not name it: %r" % (message,))

    # a dial no host line claims is explained by an allowed process line, and a
    # dial no line explains at all is a disagreement
    box = fresh()
    box["wire"].dial("api.internal", 443)
    report = call(box, (entry(0, "builder", "shell", "/home/agent", "allowed",
                              "granted", 0),))
    assert report["hosts"] == (), (
        "a dialed host with no host line is not counted as a host the run got: %r"
        % (report["hosts"],))
    box = fresh()
    box["wire"].dial("api.internal", 443)
    message = _refuses(s.ReportError, "a dial with no allowed process line",
                       lambda: call(box, ()))
    assert "api.internal" in message, (
        "a dial no allowed line explains is not named: %r" % (message,))

    # the secret count is the allowed calls', not the vault's handles
    box = fresh()
    value = box["vault"].read("deploy-key")
    secret = entry(0, "vaultkeeper", "get_secret", "deploy-key", "allowed",
                   "granted", len(value))
    report = call(box, (secret,))
    assert report["secrets"] == 1, (
        "one allowed call demanding secret:read is one secret read: %r"
        % (report["secrets"],))
    assert report["paths"] == () and report["hosts"] == (), (
        "a secret call acts on neither a path nor a host: %r" % (report,))
    assert len(box["vault"].handles()) != report["secrets"], (
        "the vault holds three handles and read one: the count is the calls', "
        "not the handles' — a check whose fixture made them equal would miss it")
    message = _refuses(
        s.ReportError, "a secret count the vault disagrees with",
        lambda: call(fresh(), (entry(0, "vaultkeeper", "get_secret",
                                     "deploy-key", "allowed", "granted", 13),)))
    assert "deploy-key" in message, (
        "the refusal of an unread secret does not name the line: %r" % (message,))
    wrong_box = fresh({"deploy-key": "x"})
    wrong_box["vault"].read("deploy-key")
    message = _refuses(
        s.ReportError, "a read handle the line does not name",
        lambda: call(wrong_box, (entry(0, "vaultkeeper", "get_secret",
                                       "api-token", "allowed", "granted", 1),)))
    assert "api-token" in message, (
        "the refusal of a handle mismatch does not name the line: %r" % (message,))

    # one allowed env_dump reads every handle at once, and the claim rule
    # explains all three reads from the one line: secrets is one, not three
    box = fresh()
    for handle in box["vault"].handles():
        box["vault"].read(handle)
    dump = entry(0, "vaultkeeper", "env_dump", "", "allowed", "granted", 0)
    report = call(box, (dump,))
    assert report["secrets"] == 1, (
        "an env_dump is one call demanding secret:read: %r" % (report["secrets"],))
    assert len(box["vault"].reads()) == 3, (
        "the check's own fixture is wrong: the vault read three handles")
    assert sweep(box, (dump,))["missing"] == () and sweep(
        box, (dump,))["extra"] == (), (
        "a `none`-kind call that demanded secret:read claims every handle the "
        "vault holds: %r" % (sweep(box, (dump,)),))

    # a read no allowed line claims is a disagreement
    box = fresh()
    box["vault"].read("deploy-key")
    message = _refuses(s.ReportError, "a read no allowed line claims",
                       lambda: call(box, ()))
    assert "deploy-key" in message, (
        "an unclaimed read is not named: %r" % (message,))

    # a denied target the world nevertheless recorded
    box = fresh()
    box["vfs"].read("/home/agent/notes.md")
    denied_only = entry(0, "analyst", "read_file", "/home/agent/notes.md",
                        "denied", "capability", 0)
    message = _refuses(s.ReportError, "a denied call the world nonetheless touched",
                       lambda: call(box, (denied_only,)))
    assert "no allowed line accounts for" in message, (
        "a denied target in the record is a record no allowed line accounts for: "
        "%r" % (message,))

    # ---- the entry rules --------------------------------------------------

    message = _refuses(s.ReportError, "an entry that is not a mapping",
                       lambda: call(fresh(), (("read_file",),)))
    assert "0" in message and "mapping" in message, (
        "the refusal of a non-mapping entry does not name the index and the "
        "shape: %r" % (message,))

    box = fresh()
    text = box["vfs"].read("/home/agent/notes.md")
    good = dict(entry(0, "analyst", "read_file", "/home/agent/notes.md",
                      "allowed", "granted", len(text)))
    foreign = dict(good, toolz="x")
    message = _refuses(s.ReportError, "an entry with a foreign field",
                       lambda: call(box, (foreign,)))
    assert "toolz" in message and "0" in message, (
        "the refusal of the foreign field 'toolz' does not name it and the index: "
        "%r" % (message,))

    missing = dict(good)
    del missing["reason"]
    message = _refuses(s.ReportError, "an entry that omits a key",
                       lambda: call(box, (missing,)))
    assert "reason" in message, (
        "the refusal of an omitted key does not name it: %r" % (message,))

    bad_decision = dict(good, decision="allowd")
    message = _refuses(s.ReportError, "a decision outside the vocabulary",
                       lambda: call(box, (bad_decision,)))
    assert "allowd" in message and "did you mean 'allowed'" in message, (
        "the refusal of 'allowd' does not name it and suggest 'allowed': %r"
        % (message,))

    far = dict(good, decision="zzzz")
    message = _refuses(s.ReportError, "a decision nobody could have meant",
                       lambda: call(box, (far,)))
    assert "zzzz" in message and "did you mean" not in message, (
        "a name further than two edits earns no suggestion: a suggestion that is "
        "not close is a lie: %r" % (message,))

    bad_reason = dict(good, reason="denied")
    message = _refuses(s.ReportError, "a reason that is a decision",
                       lambda: call(box, (bad_reason,)))
    assert "denied" in message, (
        "the refusal of the reason 'denied' does not name it: a decision is not a "
        "reason" % (message,))

    for what, value, said in (("a bool", True, "is not a byte count"),
                              ("a negative", -1, "must not be negative")):
        bad_bytes = dict(good, bytes=value)
        message = _refuses(s.ReportError, "a bytes that is %s" % (what,),
                           lambda: call(box, (bad_bytes,)))
        assert said in message, (
            "the refusal of a bytes written as %r says %r, not that it %s: %r"
            % (value, message, said, message))

    second = entry(1, "builder", "list_dir", "/home/agent", "allowed", "granted",
                   0)
    message = _refuses(s.ReportError, "a principal that is not the run's",
                       lambda: call(fresh(), (good, second)))
    assert "1" in message and "builder" in message and "analyst" in message, (
        "the refusal of a second principal does not name the index and both: %r"
        % (message,))

    later = dict(entry(1, "analyst", "read_file", "/home/agent/notes.md",
                       "allowed", "granted", len(text)))
    later["reason"] = "not-a-reason"
    message = _refuses(s.ReportError, "a malformed entry after a good one",
                       lambda: call(box, (good, later)))
    assert "entry 1" in message and "not-a-reason" in message, (
        "a refusal must name the entry's own index and offender: %r" % (message,))

    message = _refuses(
        s.ReportError, "an allowed line naming a tool the catalogue does not have",
        lambda: call(fresh(), (entry(0, "analyst", "frobnicate", "/x", "allowed",
                                     "granted", 0),)))
    assert "frobnicate" in message and "not one this world has" in message, (
        "the refusal of an invented tool does not name it and say where it was "
        "looked for: %r" % (message,))

    # ---- touched: distinct, sorted, allowed only --------------------------

    box = fresh()
    text = box["vfs"].read("/home/agent/notes.md")
    box["vfs"].read("/home/agent/notes.md")
    twice = (entry(0, "analyst", "read_file", "/home/agent/notes.md", "allowed",
                   "granted", len(text)),
             entry(1, "analyst", "read_file", "/home/agent/notes.md", "allowed",
                   "granted", len(text)))
    assert s.touched(twice) == ("/home/agent/notes.md",), (
        "touched is distinct: two reads of one file are one thing touched: %r"
        % (s.touched(twice),))
    assert s.touched(()) == (), (
        "an empty run touched nothing: %r" % (s.touched((),),))

    # ---- audit reports, and never raises ----------------------------------

    box = fresh()
    assert sweep(box, None) == {"missing": (), "extra": (), "count": 0}, (
        "audit raised or refused on a value it cannot even iterate")

    garbage = [None, ("read_file",), {"tick": 0, "principal": "a", "tool": "x"}]
    report_out = sweep(box, garbage)
    assert report_out["count"] == 3, (
        "audit counts every entry it was handed, readable or not: %r"
        % (report_out,))
    assert len(report_out["extra"]) == 3 and report_out["missing"] == (), (
        "an entry audit cannot read is an extra, not an exception: %r"
        % (report_out,))

    unreadable = dict(good, bytes=True)
    report_out = sweep(box, (unreadable,))
    assert report_out["extra"] and report_out["count"] == 1, (
        "audit reports an entry it cannot read instead of raising: %r"
        % (report_out,))

    report_out = sweep(fresh(), (entry(0, "analyst", "frobnicate", "/x",
                                       "allowed", "granted", 0),))
    assert report_out["extra"] and report_out["extra"][0][1] is None, (
        "audit reports an allowed line naming a tool nobody has, paired with no "
        "record: %r" % (report_out,))

    print("check_09: the twelve report fields in declared order; a report "
          "recomputed from the lines and the meter with an empty run as zeros; "
          "denied entries counted but never in `paths` or `touched`; the world's "
          "three records as the tie-breaker, refusing a line the world does not "
          "hold and a record no line accounts for, comparing bytes only where a "
          "world op carries a length; and `audit` reporting the disagreement — "
          "the line and the record side by side — where `report` refuses")

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "sandbox-capabilities-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J4_REPO=/path/to/forja")

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

    import fleet

    import tools as world
    import vfs as fs

    import stage_01 as s1
    import stage_07 as s7
    import stage_08 as s8
    import stage_09 as s9
    import stage_10 as s

    RUN_KEYS = ("calls", "observations", "report", "touched", "audit", "clock",
                "stopped_by")

    def fresh(limits=None, secrets=None):
        """A fresh world, a fresh sink, and nothing in any record yet."""
        return {"vfs": fs.VFS(), "wire": world.Wire(),
                "vault": world.Vault(secrets), "meter": world.Meter(limits),
                "audit": world.Audit()}

    def ticks_of(result):
        return [entry["tick"] for entry in result["audit"]]

    def entries_of(box):
        return tuple(s7.parse_line(text) for text in box["audit"].lines())

    # ---- the constant, the keys and the family ----------------------------

    assert s.DEFAULT_CALLS == 8, (
        "the run's default call cap is %r, not the eight the world's own meter "
        "starts with" % (s.DEFAULT_CALLS,))
    assert s.RUN_KEYS == RUN_KEYS, (
        "the run's seven fields are %r, not the house shape in order"
        % (s.RUN_KEYS,))
    assert issubclass(s.RunError, s1.SandboxError), (
        "%r is not a %s: one `except SandboxError` must still catch a broken run"
        % (s.RunError, s1.SandboxError.__name__))
    assert issubclass(s.RunError, ValueError), (
        "%r is not a ValueError: the course's refusal is a named error a caller "
        "can catch" % (s.RunError,))

    # ---- two runs of one plan agree, field for field ----------------------

    box = fresh()
    first = s.run("analyst", world.plan("publish"), **box)
    other = fresh()
    second = s.run("analyst", world.plan("publish"), **other)
    assert tuple(first) == RUN_KEYS, (
        "the run's fields are %r, not the house shape in order" % (tuple(first),))
    assert first == second, (
        "two runs of one plan disagree: %r vs %r" % (first, second))
    assert len(first["calls"]) == len(first["observations"]) == 3, (
        "one observation per call was not kept: %r" % (first,))
    assert [entry["reason"] for entry in first["calls"]] == [
        "granted", "granted", "capability"], (
        "the decisions are not the run's own, in order: %r" % (first["calls"],))
    assert first["stopped_by"] is None, (
        "a run of denials and grants did not stop: %r" % (first["stopped_by"],))

    # ---- the clock: the run's, advanced by what each call cost ------------

    assert ticks_of(first) == [0, 1, 3], (
        "a read_file/http_get/write_file run must stamp its lines at ticks 0, 1 "
        "and 3 — the tick is logical time, not a line number: %r"
        % (ticks_of(first),))
    assert first["clock"] == 5, (
        "the run's last tick is the sum of its calls' costs, not %r"
        % (first["clock"],))

    # ---- calls are the decisions; observations are what came back ---------

    assert all(tuple(decision) == s8.DECISION_KEYS for decision in first["calls"]), (
        "`calls` are not stage 8's decisions: %r" % (first["calls"],))
    assert all(tuple(observation) == s8.OBSERVATION_KEYS
               for observation in first["observations"]), (
        "`observations` are not the frozen six keys: %r"
        % (first["observations"],))
    assert all(observation["value"] is None
               for observation in first["observations"]
               if observation["decision"] == "denied"), (
        "a denial handed back a value: %r" % (first["observations"],))

    # ---- report, touched and audit are stage 9's over the whole sink ------

    entries = entries_of(box)
    assert first["audit"] == entries, (
        "the run's audit is not the sink read back with `parse_line`: %r"
        % (first["audit"],))
    assert first["report"] == s9.report(entries, meter=box["meter"],
                                        vfs=box["vfs"], wire=box["wire"],
                                        vault=box["vault"]), (
        "the run's report is not stage 9's answer over its own lines: %r"
        % (first["report"],))
    assert first["touched"] == s9.touched(entries), (
        "the run's touched is not stage 9's answer over its own lines: %r"
        % (first["touched"],))

    # a second run on one sink reports every line, not its own slice
    grown = s.run("analyst", world.plan("publish"), **box)
    whole = entries_of(box)
    assert len(whole) == 6 and len(grown["calls"]) == 3, (
        "the sink is cumulative: %d line(s), this run made %d call(s)"
        % (len(whole), len(grown["calls"])))
    assert grown["audit"] == whole, (
        "the run's audit is its own slice of a cumulative sink, not the whole: "
        "%r" % (grown["audit"],))
    assert grown["report"] == s9.report(whole, meter=box["meter"],
                                        vfs=box["vfs"], wire=box["wire"],
                                        vault=box["vault"]), (
        "the report is not stage 9's answer over the sink's whole contents: %r"
        % (grown["report"],))
    assert grown["report"]["calls"] == 6, (
        "a report that subtracts a prefix of the world cannot be cross-checked: "
        "%r" % (grown["report"],))
    assert grown["touched"] == s9.touched(whole), (
        "touched is not stage 9's answer over the whole sink: %r"
        % (grown["touched"],))

    # ---- an empty plan is a run of zeros, not an error --------------------

    box = fresh()
    empty = s.run("analyst", (), **box)
    assert empty == {"calls": (), "observations": (),
                     "report": s9.report((), meter=box["meter"], vfs=box["vfs"],
                                         wire=box["wire"], vault=box["vault"]),
                     "touched": (), "audit": (), "clock": 0, "stopped_by": None}, (
        "an empty plan is a run that touched nothing: %r" % (empty,))

    # ---- the cap stops before the call is made ----------------------------

    box = fresh()
    capped = s.run("analyst", world.plan("publish"), limit=1, **box)
    assert capped["stopped_by"] == "limit", (
        "the cap stopped nothing: %r" % (capped["stopped_by"],))
    assert len(capped["calls"]) == 1 and len(capped["observations"]) == 1, (
        "the call after the cap was decided: %r" % (capped,))
    assert len(capped["audit"]) == 1 and len(box["audit"].lines()) == 1, (
        "the call after the cap was written: %r" % (capped["audit"],))
    assert all(entry["tool"] != "http_get" for entry in capped["audit"]), (
        "the capped call wrote a line: %r" % (capped["audit"],))
    assert box["wire"].dialled() == (), (
        "the capped call reached the world: %r" % (box["wire"].dialled(),))
    assert capped["clock"] == 1, (
        "the run stopped at tick %r, not the one its single call cost"
        % (capped["clock"],))

    # ---- a limit that is not a positive int is refused, naming it ---------

    for bad in (0, -1, True, None, "8"):
        message = _refuses(
            s.RunError, "a limit of %r" % (bad,),
            lambda given=bad: s.run("analyst", (), limit=given, **fresh()))
        assert repr(bad) in message, (
            "the refusal of the limit %r does not name it: %r" % (bad, message))

    # ---- a plan that is not a sequence of call mappings is refused --------

    message = _refuses(s.RunError, "a plan that is a string",
                       lambda: s.run("analyst", "notes", **fresh()))
    assert "str" in message, (
        "the refusal of a string plan does not name its shape: %r" % (message,))
    message = _refuses(s.RunError, "a plan that is a mapping",
                       lambda: s.run("analyst", {"tool": "read_file"}, **fresh()))
    assert "dict" in message, (
        "the refusal of a mapping plan does not name its shape: %r" % (message,))
    message = _refuses(s.RunError, "a plan that is not iterable",
                       lambda: s.run("analyst", None, **fresh()))
    assert "NoneType" in message, (
        "the refusal of a non-plan does not name its shape: %r" % (message,))
    message = _refuses(s.RunError, "a plan with a non-mapping step",
                       lambda: s.run("analyst", (("read_file",),), **fresh()))
    assert "0" in message and "tuple" in message, (
        "the refusal of a non-mapping step does not name its index and shape: %r"
        % (message,))

    # ---- a denial that is not a limit is walked past ----------------------

    box = fresh()
    refused = s.run("intern", world.plan("notes"), **box)
    assert refused["stopped_by"] is None, (
        "the run stopped on a capability denial: %r" % (refused["stopped_by"],))
    assert [entry["reason"] for entry in refused["calls"]] == [
        "capability", "capability"], (
        "the run did not walk past two capability denials: %r"
        % (refused["calls"],))
    assert refused["touched"] == (), (
        "a run of denials touched something: %r" % (refused["touched"],))
    assert box["vfs"].log() == () and box["wire"].dialled() == (), (
        "a denied call reached the world: %r %r"
        % (box["vfs"].log(), box["wire"].dialled()))
    assert box["meter"].used() == dict.fromkeys(world.LIMIT_KEYS, 0), (
        "a denied call spent something: %r" % (box["meter"].used(),))
    assert refused["clock"] == 2, (
        "the clock did not advance past the denials: %r" % (refused["clock"],))

    # ---- a spent limit stops the run at its first call --------------------

    box = fresh(limits=dict.fromkeys(world.LIMIT_KEYS, 0))
    poor = s.run("analyst", world.plan("publish"), **box)
    assert poor["stopped_by"] == "limit", (
        "a meter that cannot pay did not stop the run: %r"
        % (poor["stopped_by"],))
    assert len(poor["calls"]) == 1 and poor["calls"][0]["reason"] == "limit", (
        "the first call was not the one the meter refused: %r" % (poor["calls"],))
    assert poor["report"]["denied"] == 1 and poor["clock"] == 1, (
        "the run stopped at the first call but did not report or stamp it: %r"
        % (poor,))
    assert box["meter"].used() == dict.fromkeys(world.LIMIT_KEYS, 0), (
        "a denied call charged the meter: %r" % (box["meter"].used(),))

    # ---- an unknown tool stays a decision, not a refusal ------------------

    box = fresh()
    ghost = s.run("analyst", [{"tool": "frobnicate", "target": "/x"}], **box)
    assert ghost["calls"][0]["reason"] == "unknown", (
        "an unknown tool was not left a decision: %r" % (ghost["calls"],))
    assert ghost["calls"][0]["allowed"] is False, (
        "an unknown tool was allowed: %r" % (ghost["calls"],))
    assert len(box["audit"].lines()) == 1 and ghost["clock"] == 0, (
        "an unknown tool's line and its zero cost were not kept: %r" % (ghost,))

    # ---- the broken plan answers capability, then jail --------------------

    box = fresh()
    broken = s.run("analyst", world.plan("broken"), **box)
    assert [entry["reason"] for entry in broken["calls"]] == [
        "capability", "jail"], (
        "the broken plan's two refusals are not capability and jail: %r"
        % (broken["calls"],))
    assert broken["stopped_by"] is None, (
        "the broken plan stopped: %r" % (broken["stopped_by"],))
    assert broken["clock"] == 1, (
        "an unreadable declaration (teleport) cost the clock something: %r"
        % (broken["clock"],))
    assert box["vfs"].log() == (), (
        "a refused call reached the filesystem: %r" % (box["vfs"].log(),))

    # ---- the plan is not mutated by having been run -----------------------

    plan = world.plan("publish")
    before = [dict(step) for step in plan]
    s.run("analyst", plan, **fresh())
    assert [dict(step) for step in plan] == before and len(plan) == 3, (
        "the run rewrote the caller's plan: %r" % (plan,))

    # ---- the clock is the run's: injected, or refused ---------------------

    box = fresh()
    shared = fleet.Clock(start=4)
    injected = s.run("analyst", world.plan("notes"), clock=shared, **box)
    assert ticks_of(injected) == [4, 5], (
        "an injected clock was ignored: %r" % (ticks_of(injected),))
    assert injected["clock"] == 6, (
        "the injected clock's last reading is not the run's clock: %r"
        % (injected["clock"],))
    message = _refuses(s.RunError, "a clock that is not a fleet.Clock",
                       lambda: s.run("analyst", (), clock=5, **fresh()))
    assert "int" in message or "Clock" in message, (
        "the refusal of a non-clock does not name it: %r" % (message,))

    # ---- the secret plan: no value, but a counted read --------------------

    box = fresh()
    deployed = s.run("vaultkeeper", world.plan("deploy"), **box)
    values = tuple(secret["value"] for secret in world.SECRETS.values())
    sink = box["audit"].text() + repr(deployed)
    assert all(value not in sink for value in values), (
        "a secret value reached the run's output: %r" % (sink,))
    assert deployed["report"]["secrets"] > 0, (
        "the run read a secret but the report did not count it: %r"
        % (deployed["report"],))
    assert deployed["report"] == s9.report(entries_of(box), meter=box["meter"],
                                           vfs=box["vfs"], wire=box["wire"],
                                           vault=box["vault"]), (
        "the secret plan's report does not agree with the world's own record "
        "even though it must: %r" % (deployed["report"],))
    assert len(box["vault"].reads()) > 1, (
        "the check's own fixture is wrong: `env_dump` did not read the whole "
        "environment")

    print("check_10: the capstone — a plan of raw calls walked through the guard "
          "with the call cap and the meter stopping the run while every other "
          "denial is walked past, the clock advanced by each tool's cost, an "
          "unknown tool left a decision, two runs equal field for field, the "
          "report recomputed from the sink's whole contents, and no secret value "
          "anywhere in a run's output")

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The capability, and the tool that declares it",
        tags=["capability", "declaration"],
        action="Write `SandboxError`, `ToolError`, `COST_DEFAULTS`, `capability`, "
               "`parse_tool`, `declares` and `parse_call` in stage_01.py.",
        predict="What a tool has to declare before anything can be decided about a "
                "call to it — and why a demand set that is empty, repeated or "
                "outside the vocabulary must be refused rather than repaired.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The grant, and the intersection that decides",
        tags=["grants", "acl"],
        action="Write `GrantError`, `grant`, `granted`, `missing`, `effective`, "
               "`permits` and `policy_for` in stage_02.py.",
        predict="What a principal holding one capability permits, and why the "
                "answer to 'may this tool run' is a difference of two sets rather "
                "than a boolean anybody could have got wrong quietly.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The path jail, and the escape that is a string test",
        tags=["paths", "containment"],
        action="Write `JailError`, `resolve`, `inside` and `jail` in stage_03.py.",
        predict="What `/home/agent/../etc/passwd` resolves to, what a `.` in the "
                "middle of a path does to the decision, and whether "
                "`/home/agent-other` is inside `/home/agent`.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The network policy, and the host nobody can read",
        tags=["network", "hosts"],
        action="Write `HostError`, `parse_host`, `allows`, `reachable` and "
               "`target` in stage_04.py.",
        predict="Whether a host pattern with a `*` in the middle is a policy, "
                "whether the port is part of the host's identity, and what a "
                "principal allowed every host may dial that the world has not got.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The limits, and the charge that is all or nothing",
        tags=["limits", "budget"],
        action="Write `LimitError`, `left`, `fits`, `charge` and `affordable` in "
               "stage_05.py.",
        predict="Whether a cost that fits exactly is affordable, what a check that "
                "spends is, and what happens to the other three counters when one "
                "of them does not fit.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="The secret that never reaches the model",
        tags=["secrets", "redaction"],
        action="Write `SecretError`, `ENCODINGS`, `digest`, `observe`, `reveal`, "
               "`redact` and `leaks` in stage_06.py.",
        predict="What may travel about a secret that may not travel itself, and "
                "which encodings a redactor that only knows the plain value has "
                "already lost to.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The audit line, and the reason that is a word",
        tags=["audit", "vocabulary"],
        action="Write `AuditError`, `REASONS`, `DECISIONS`, `AUDIT_KEYS`, `line`, "
               "`parse_line` and `write_line` in stage_07.py.",
        predict="What a line has to carry so that a reader who was not there can "
                "tell what was asked, of whom, and why it was refused — and why "
                "that why has to be a word from a closed set.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The call that never happens",
        tags=["policy", "enforcement"],
        action="Write `CallError`, `decide` and `Guard` (with `decide`, `invoke` "
               "and `__repr__`) in stage_08.py.",
        predict="Which of the six questions is asked first, what is written down "
                "before the act, and what a denied call leaves behind in the "
                "filesystem, the wire, the vault and the meter.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The report, and the world's own record",
        tags=["report", "cross-check"],
        action="Write `ReportError`, `REPORT_KEYS`, `report`, `touched` and "
               "`audit` in stage_09.py.",
        predict="Where each number of a report comes from, what an audit line can "
                "prove on its own, and which record decides whether it is telling "
                "the truth about what a run touched.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="An agent, its policy, and the answer to what it touched",
        tags=["capstone", "run"],
        action="Write `RunError`, `DEFAULT_CALLS` and `run` in stage_10.py.",
        predict="Which denial stops a run and which one does not, what two runs of "
                "the same plan have to agree about, and where the value of a "
                "secret is allowed to appear in everything a run produced.",
        check=check_10,
    ),
]
