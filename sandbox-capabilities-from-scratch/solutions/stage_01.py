"""stage_01.py — the capability, and the tool that declares it.

Sandbox & Capabilities From Scratch — stage 1: The capability, and the tool that declares it

An agent's power is not what its tools can do; it is the intersection of what the
tools declare, what the principal granted, and what the world will still afford.
Before anything else this course has to fix what a tool *declares*: a name, a
description, the capabilities it demands, what one call costs, and what kind of
thing it acts on — and nothing else. Two vocabularies, one demand read as one
sorted tuple, and a refusal that names the offender every time a declaration
repeats a capability, demands nothing, or names one this world does not have.

    TOOL_KEYS / CALL_KEYS   the fields of a declaration and of a call
    COST_DEFAULTS           what a counter defaults to when a declaration omits it
    SandboxError / ToolError   the course's refusal family, and this stage's
    capability              one name from the vocabulary, with a suggestion
    parse_tool              a declaration, materialised
    declares                the demand, as one sorted tuple
    parse_call              a call to a tool this world has
"""

from collections.abc import Mapping
from types import MappingProxyType

import tools

#: The five fields a declaration carries, in the order a declaration writes them.
TOOL_KEYS = ("name", "description", "capabilities", "cost", "target_kind")

#: The three fields a call carries, in the order a call writes them.
CALL_KEYS = ("tool", "target", "value")

#: What a counter of `tools.COST_KEYS` costs when a declaration omits it.
COST_DEFAULTS = MappingProxyType({"cpu": 1, "memory": 0, "ticks": 1})

#: The distance within which a name the vocabulary does not have is assumed to be
#: a typo for one it does.
_NEAR = 2

#: The capabilities whose tools read a call's `value`: a writer writes it, and a
#: process tool runs it as its command.
_VALUE_CARRIERS = ("fs:write", "proc:spawn")


class SandboxError(ValueError):
    """The course's one refusal family, as `stage_01` declares it."""


class ToolError(SandboxError):
    """A capability, a declaration, a demand or a call this stage refuses."""


def _levenshtein(left, right):
    """The edit distance between two short names, the plain way."""
    if left == right:
        return 0
    previous = list(range(len(right) + 1))
    for i, lchar in enumerate(left, 1):
        current = [i]
        for j, rchar in enumerate(right, 1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (0 if lchar == rchar else 1),
            ))
        previous = current
    return previous[-1]


def _near(name, known):
    """`" (did you mean 'x'?)"` for the closest known name, or `""`."""
    if not isinstance(name, str):
        return ""
    best, best_distance = None, _NEAR + 1
    for candidate in sorted(known):
        distance = _levenshtein(name, candidate)
        if distance < best_distance:
            best, best_distance = candidate, distance
    if best is None or best_distance > _NEAR:
        return ""
    return " (did you mean %r?)" % (best,)


def _int_counter(value, what):
    """A non-negative int, refusing a bool and a float by name."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolError("%s must be an int, got %r" % (what, value))
    if value < 0:
        raise ToolError("%s must not be negative, got %r" % (what, value))
    return value


def capability(name):
    """One name from the world's vocabulary, or a refusal that names it."""
    if not isinstance(name, str):
        raise ToolError("a capability must be a str, got %r" % (name,))
    if name not in tools.CAPABILITIES:
        raise ToolError("no such capability: %r%s"
                        % (name, _near(name, tools.CAPABILITIES)))
    return name


def _demand(raw):
    """A demand set: a sorted tuple of real capabilities, or a refusal."""
    if isinstance(raw, str):
        raise ToolError(
            "a demand must be a tuple of capabilities, not the str %r: iterating "
            "it would read one character at a time" % (raw,))
    if not isinstance(raw, (tuple, list)):
        raise ToolError("a demand must be a tuple of capabilities, got %r"
                        % (raw,))
    demanded = []
    for name in raw:
        cap = capability(name)
        if cap in demanded:
            raise ToolError(
                "the demand repeats %r: a demand is a set, and a set with a "
                "repeat is a caller who does not know that" % (cap,))
        demanded.append(cap)
    if not demanded:
        raise ToolError(
            "a tool that demands nothing is a hole in the policy: this demand is "
            "empty, and 'this tool needs nothing' cannot be told apart from "
            "'nobody wrote it down' at the call site")
    return tuple(sorted(demanded))


def declares(tool):
    """The demand a tool declares: a sorted, deduplicated tuple of capabilities."""
    if not isinstance(tool, Mapping):
        raise ToolError("a tool declaration must be a mapping, got %r" % (tool,))
    if "capabilities" not in tool:
        raise ToolError(
            "a tool declaration must carry 'capabilities', got a mapping with %s"
            % (", ".join(sorted(map(repr, tool))) or "no fields",))
    return _demand(tool["capabilities"])


def _cost(raw):
    """A cost over `tools.COST_KEYS`, every counter materialised."""
    if not isinstance(raw, Mapping):
        raise ToolError("a tool's 'cost' must be a mapping over %s, got %r"
                        % ("/".join(tools.COST_KEYS), raw))
    for key in raw:
        if key not in tools.COST_KEYS:
            raise ToolError("%r is not a counter of a cost%s"
                            % (key, _near(key, tools.COST_KEYS)))
    cost = {}
    for key in tools.COST_KEYS:
        value = raw.get(key, COST_DEFAULTS[key])
        cost[key] = _int_counter(value, "a cost's %r" % (key,))
    return cost


def parse_tool(name, fields):
    """A tool declaration, materialised, without bending the caller's mapping."""
    if not isinstance(name, str):
        raise ToolError("a tool's name must be a str, got %r" % (name,))
    if not isinstance(fields, Mapping):
        raise ToolError("a tool declaration must be a mapping, got %r"
                        % (fields,))
    for key in fields:
        if key not in TOOL_KEYS:
            raise ToolError("%r is not a field of a tool%s"
                            % (key, _near(key, TOOL_KEYS)))
    if "name" in fields and fields["name"] != name:
        raise ToolError("the declaration names %r but is being parsed as %r"
                        % (fields["name"], name))
    description = fields.get("description", "")
    if not isinstance(description, str):
        raise ToolError("a tool's 'description' must be a str, got %r"
                        % (description,))
    kind = fields.get("target_kind", "none")
    if kind not in tools.TARGET_KINDS:
        raise ToolError("no such target kind: %r%s"
                        % (kind, _near(kind, tools.TARGET_KINDS)))
    if "capabilities" not in fields:
        raise ToolError(
            "a tool declaration must carry 'capabilities': %r declares no demand "
            "and no kind can be decided without one" % (name,))
    return {
        "name": name,
        "description": description,
        "capabilities": _demand(fields["capabilities"]),
        "cost": _cost(fields.get("cost", {})),
        "target_kind": kind,
    }


def parse_call(call):
    """A call to a tool this world has, with the fields its kind carries."""
    if not isinstance(call, Mapping):
        raise ToolError("a call must be a mapping, got %r" % (call,))
    for key in call:
        if key not in CALL_KEYS:
            raise ToolError("%r is not a field of a call%s"
                            % (key, _near(key, CALL_KEYS)))
    if "tool" not in call:
        raise ToolError("a call must name a tool, got a mapping with %s"
                        % (", ".join(sorted(map(repr, call))) or "no fields",))
    name = call["tool"]
    if not isinstance(name, str):
        raise ToolError("a call's 'tool' must be a str, got %r" % (name,))
    if name not in tools.TOOLS:
        raise ToolError("no such tool: %r%s" % (name, _near(name, tools.TOOLS)))
    declaration = tools.TOOLS[name]
    demand = declares(declaration)
    kind = declaration["target_kind"]
    target = call.get("target", "")
    if not isinstance(target, str):
        raise ToolError("a call's 'target' must be a str, got %r" % (target,))
    if kind == "none":
        if target:
            raise ToolError(
                "%r acts on nothing: a target on it is a field the kind does not "
                "carry" % (name,))
    elif not target:
        raise ToolError("%r acts on a %s and needs a target, got none"
                        % (name, kind))
    value = call.get("value", "")
    if not isinstance(value, str):
        raise ToolError("a call's 'value' must be a str, got %r" % (value,))
    if value and not any(cap in _VALUE_CARRIERS for cap in demand):
        raise ToolError(
            "%r writes nothing and runs nothing: a value on it is a field the "
            "tool does not read" % (name,))
    return {"tool": name, "target": target, "value": value}
