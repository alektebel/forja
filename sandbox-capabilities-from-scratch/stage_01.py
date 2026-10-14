"""Sandbox & Capabilities From Scratch — stage 1: The capability, and the tool that declares it.

An agent's power is not what its tools can do; it is the intersection of what the
tools declare, what the principal granted, and what the world will still afford.
So this stage fixes what a *tool* declares, before anything is granted, jailed,
dialled, charged or audited: a name, a description, the capabilities it demands,
what one call costs, and what kind of thing it acts on — and nothing else.

Every later stage reads these declarations and none of them re-reads a tool out
of its own invention: stage 2 intersects the demand with a grant, stage 5 charges
the cost, stage 8 asks the kind whether a target is a path to jail, a host to
reach or a process to run inside one, and stage 9 looks a tool up by name to say
which capabilities a run actually used. A declaration whose shape is decided
per-stage is a policy two stages disagree about, and the whole course rests on
the opposite.

    TOOL_KEYS       the five fields a declaration carries, in writing order
    CALL_KEYS       the three fields a call carries, in writing order
    COST_DEFAULTS   what a cost counter defaults to when a declaration omits it
    SandboxError    the course's one refusal family (a ValueError)
    ToolError       what a declaration or a call that is not one raises
    capability      one name from the vocabulary, or a refusal with a suggestion
    parse_tool      a tool declaration, materialised without bending the caller's
    declares        the demand a tool declares, as one sorted tuple
    parse_call      a call to a tool this world has, with the fields its kind carries

DESIGN DECISION — why is a demand set that is *empty* refused rather than read as
"this tool needs nothing"?
    Because the two readings are undecidable at the call site and only one of them
    is ever intended. A declaration with `capabilities=()` either means a tool that
    genuinely reaches nothing — which no tool in a real catalogue is — or a field
    somebody forgot to write, and the policy that trusts the first reading hands
    the tool's whole power to every principal. A tool that reaches nothing is
    spelled by its `target_kind` being `"none"` *and* its demand being honest
    about what it reads; an empty demand is a hole, so it is refused, and the
    refusal says which of the two it thinks you wrote.

DESIGN DECISION — why must a demand set be *sorted*, *deduplicated*, and refused
when it repeats?
    Because a set is a value and a list is a mistake waiting to happen. A demand
    carries no order: `("fs:read", "net:connect")` and `("net:connect",
    "fs:read")` are the same demand, and a program that compares them positionally
    answers differently depending on how somebody typed a tuple. So `declares`
    hands back a sorted tuple, and a repeat is refused rather than folded — a
    caller who wrote `("fs:read", "fs:read")` does not know they wrote a set, and
    the next thing they write is `len(caps) == 1`. The same reasoning fixes the
    order of `TOOL_KEYS` and `CALL_KEYS`: an order is a claim, so it is written
    down once, in one place, in the order a reader compares.

DESIGN DECISION — why does `parse_call` read the tool's *declaration* instead of
just checking the name?
    Because "is this tool in the catalogue" and "can this world read what it
    demands" are different questions, and the second one is the one that decides
    whether a call is a call. `teleport` is in the catalogue and demands
    `"fs:teleport"` — a capability the vocabulary does not have — so a call to it
    is refused *here*, before a plan that names it is ever run, rather than
    surviving until a grant is computed and then failing as a missing capability
    nobody can grant. A call to a tool whose declaration this world cannot read is
    not a call, and the run never starts.

DESIGN DECISION — why is a target on a tool whose kind is `"none"` refused rather
than ignored?
    For the same reason stage 3's jail resolves before it decides: the ignored
    field is invisible right up to the moment it matters. `env_dump` reads the
    environment and acts on nothing; a call that names a target for it has
    confused it with `read_file` — and the caller, reading the refusal, fixes the
    tool name, whereas a world that quietly dropped the target would have run
    `env_dump` while the caller believed their file was read. A target is a field
    the *kind* carries, and a field the kind does not carry is refused by name.

DESIGN DECISION — why does a `value` require `fs:write` or `proc:spawn`?
    Because a value is the one field whose meaning is *an effect*, and a tool that
    writes a file or runs a command is the only kind of tool whose value reaches
    something. A `read_file` call with a `value="tomato"` has not been refused;
    it has been silently ignored, and the caller's intent is now a field nobody
    reads. Deriving the rule from the tool's *capabilities* rather than from its
    name means a tool this course has never seen still gets the check right.

DESIGN DECISION — why is the refusal family a `ValueError`?
    Because everything it refuses is *data* the caller handed over: a name that is
    not a capability, a declaration with a foreign field, a cost that is a bool, a
    call to a tool nobody has. `agents-from-scratch` — this course's prerequisite
    C2 — raises `SandboxError(Exception)` about a real filesystem it resolved with
    `os.path.realpath`, where the failure is a runtime fault in the world. Here
    the filesystem, the wire and the vault are all modelled, so a refusal is a
    verdict on a value and belongs to the family Python already catches for that.
    Same name, same rules, different subject — and every stage derives its own
    narrower class from this one so a single `except SandboxError` still sees a
    broken course in any of the ten.

TODO: implement `capability`, `parse_tool`, `declares` and `parse_call`.
"""

from collections.abc import Mapping
from types import MappingProxyType

import tools

#: The five fields a declaration carries, in the order a declaration writes them.
#: A field outside this tuple is a typo, and a typo is refused by name.
TOOL_KEYS = ("name", "description", "capabilities", "cost", "target_kind")

#: The three fields a call carries, in the order a call writes them.
CALL_KEYS = ("tool", "target", "value")

#: What a counter of `tools.COST_KEYS` costs when a declaration omits it. A call
#: that costs nothing at all is a call nobody counted, so cpu and ticks default
#: to one: an omitted counter is a default, not a free one.
COST_DEFAULTS = MappingProxyType({"cpu": 1, "memory": 0, "ticks": 1})


class SandboxError(ValueError):
    """The course's one refusal family.

    Every stage derives its own refusal from this one (`ToolError` here, then
    `GrantError`, `JailError`, `HostError`, `LimitError`, `SecretError`,
    `AuditError`, `CallError`, `ReportError` and stage 10's `RunError`), so a
    caller can catch a broken course with one `except SandboxError` and still
    read a narrower `except` at the site that knows what it is doing.
    """


class ToolError(SandboxError):
    """A capability, a declaration, a demand or a call this stage refuses.

    The refusal always names the offender — the capability, the field, the
    counter, the tool — and, when the offender is within edit distance two of a
    real name, the real name too, because this vocabulary is exactly where a typo
    silently becomes a default.
    """


def capability(name):
    """One name from the world's vocabulary, or a refusal that names it.

    A name outside `tools.CAPABILITIES` is refused, and a name within edit
    distance two of a real one is refused *with* that name, so a typo is one edit
    away from a fix rather than one search away from a mystery.
    """
    raise NotImplementedError("stage 1: implement capability()")


def parse_tool(name, fields):
    """A tool declaration, materialised, without bending the caller's mapping.

    `fields` is a mapping over `TOOL_KEYS`; a key outside it is refused by name,
    `description` defaults to `""`, `target_kind` to `"none"`, an absent counter
    of `cost` to its `COST_DEFAULTS` value, and `capabilities` to a sorted,
    deduplicated tuple — refusing a repeat, an empty demand, a name the
    vocabulary does not have, and a demand handed over as a `str`. The returned
    mapping carries exactly `TOOL_KEYS`, in that order.
    """
    raise NotImplementedError("stage 1: implement parse_tool()")


def declares(tool):
    """The demand a tool declares: a sorted, deduplicated tuple of capabilities.

    Refuses a declaration that is not a mapping, one that does not carry
    `capabilities` at all, a demand that repeats a name, a demand that is empty,
    and a demand that names a capability this world does not have — every refusal
    naming the offender.
    """
    raise NotImplementedError("stage 1: implement declares()")


def parse_call(call):
    """A call to a tool this world has, with the fields its kind carries.

    `call` is a mapping over `CALL_KEYS`; a key outside it is refused by name,
    `target` and `value` default to `""`, the tool must be in `tools.TOOLS` and
    its declaration must be one this world can read (`declares`). A `target` is
    required when the tool's `target_kind` is not `"none"` and refused when it is;
    a `value` is refused unless the tool demands `fs:write` or `proc:spawn`. The
    returned mapping carries exactly `CALL_KEYS`, in that order.
    """
    raise NotImplementedError("stage 1: implement parse_call()")
