"""stage_05.py — the limits, and the charge that is all or nothing.

Sandbox & Capabilities From Scratch — stage 5: The limits, and the charge that is all or nothing

A tool's cost is a claim about the world, and a limit is what the world will
still afford — so the question a run asks before it acts is not "is this
allowed?" but "does what is left fit what this call needs?", asked *before* the
work and answered the same way whether it is asked once or twice. The world's
`Meter` counts and does not judge: `spend()` is raw on purpose, so a counter may
read past its limit and the only reader that hides that is `left()`, floored at
zero. This stage is the judgement on top of that meter: a question that spends
nothing, a charge that is all or nothing, and the tool's own terms as one more
reading of the same four counters.

    LimitError      what a cost, a reading or a calls count this stage refuses
    left            limits - spent, per counter, floored at zero
    fits            a read-only question: does this cost fit, calls included?
    charge          all or nothing: spend it, or refuse and spend nothing
    affordable      the same question in a tool's own terms, as data
"""

from collections.abc import Mapping

import stage_01
import tools

#: The distance within which a counter a cost does not have is assumed to be a
#: typo for one it does.
_NEAR = 2

#: The calls counter a `Cost` does not carry: the fourth counter, which a call
#: always spends whatever its tool costs. One tool call is one call.
_ONE_CALL = 1


class LimitError(stage_01.SandboxError):
    """A cost, a reading or a calls count this stage refuses.

    Everything that raises is the *caller's* mistake — a cost that is not a
    mapping over `tools.COST_KEYS`, a counter that is a bool, a float, a
    negative or a non-int, a calls count that is not a positive int, or a charge
    that does not fit. The policy's own answer — a call the meter cannot pay for
    — is *data*, returned by `affordable`, because a denial is a normal outcome
    of a run and the loop has to keep going.
    """


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


def _counter(value, what):
    """A non-negative int, refusing a bool and a float by name."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise LimitError("%s must be an int, got %r" % (what, value))
    if value < 0:
        raise LimitError("%s must not be negative, got %r" % (what, value))
    return value


def _calls(value):
    """How many calls a charge covers: a positive int, refused by name."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise LimitError("calls must be an int, got %r" % (value,))
    if value < 1:
        raise LimitError("calls must be positive, got %r" % (value,))
    return value


def _needs(cost, calls):
    """The four counters a charge of `cost` over `calls` calls would need.

    A cost is a mapping over `tools.COST_KEYS` and nothing else: a counter the
    vocabulary does not have is refused by name, a counter left out is zero —
    exactly what `Meter.spend` does with the same mapping, so a question and a
    charge can never disagree about what a cost means.
    """
    if not isinstance(cost, Mapping):
        raise LimitError("a cost must be a mapping over %s, got %r"
                         % ("/".join(tools.COST_KEYS), cost))
    for key in cost:
        if key not in tools.COST_KEYS:
            raise LimitError("%r is not a counter of a cost%s"
                             % (key, _near(key, tools.COST_KEYS)))
    needs = {}
    for key in tools.COST_KEYS:
        needs[key] = _counter(cost.get(key, 0), "a cost's %r" % (key,))
    needs["calls"] = _calls(calls)
    return needs


def _short(needs, remaining):
    """The counters whose need is more than what is left, in declared order."""
    return tuple(key for key in tools.LIMIT_KEYS
                 if needs[key] > remaining[key])


def left(meter):
    """What the meter has left, per counter, floored at zero.

    `Meter.left()` is the reading this stage publishes: a raw `spend()` may take
    a counter past its limit, and the arithmetic that follows must not go
    negative — a reading of zero says "nothing left" and is honest about it,
    while `used()` still carries the truth.
    """
    return meter.left()


def fits(meter, cost, *, calls=1):
    """Does this cost, over this many calls, fit what is left? A question only.

    Reads the meter and spends nothing: `meter.used()` is the same mapping after
    this call as it was before, however many times it is asked. A cost that fits
    exactly — a need equal to what is left — is allowed, and one unit more is
    not; the comparison is `>`, because a `>=` here would hand out one free unit
    per call, which is how a limit leaks.
    """
    needs = _needs(cost, calls)
    remaining = meter.left()
    return not _short(needs, remaining)


def charge(meter, cost, *, calls=1):
    """Spend the cost and the calls, all of it or none of it.

    Every one of the four counters is checked before anything is spent, so a
    charge that fails on one counter leaves the other three exactly as they
    were: a partial charge is how a limit leaks. When nothing fits, the refusal
    names *every* counter that does not fit, each with what it needs and what is
    left, because a caller who fixes one counter at a time has to be told each
    time. Otherwise the world does the counting and `used()` comes back.
    """
    needs = _needs(cost, calls)
    remaining = meter.left()
    short = _short(needs, remaining)
    if short:
        raise LimitError(
            "a charge of %d call(s) does not fit: %s"
            % (calls, "; ".join("%s needs %d and %d is left"
                                % (key, needs[key], remaining[key])
                                for key in short)))
    return meter.spend(cost, calls=calls)


def affordable(meter, tool):
    """Can the meter pay for one call of this tool? Data, not an exception.

    The tool's own terms: its `cost` plus the one call every call spends, so
    this is `fits(meter, tool["cost"], calls=1)` with the answer spelled the way
    a decision needs it — `reason` from the closed vocabulary (`"granted"` or
    `"limit"`) and `short` the sorted names of the counters that do not fit,
    empty when nothing is short.
    """
    if not isinstance(tool, Mapping):
        raise LimitError("a tool must be a mapping carrying 'cost', got %r"
                         % (tool,))
    if "cost" not in tool:
        raise LimitError("a tool must carry 'cost', got a mapping with %s"
                         % (", ".join(sorted(map(repr, tool))) or "no fields",))
    needs = _needs(tool["cost"], _ONE_CALL)
    remaining = meter.left()
    short = tuple(sorted(_short(needs, remaining)))
    if short:
        return {"allowed": False, "reason": "limit", "short": short}
    return {"allowed": True, "reason": "granted", "short": ()}
