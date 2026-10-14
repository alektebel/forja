"""Sandbox & Capabilities From Scratch — stage 5: The limits, and the charge that is all or nothing.

A call costs something before it touches anything, and the world will only
afford so much. So this stage is the judgement on top of the world's `Meter`,
which counts and does not police: four counters — cpu, memory, ticks and the
calls themselves — a question asked *before* the work, and one charge that
either happens whole or does not happen at all.

What a caller may ask is exactly four things, and the order in which they are
asked is the design: `left` is the reading (limits minus spent, floored at
zero), `fits` is the read-only question, `charge` is the all-or-nothing spend,
and `affordable` is the same question in a tool's own terms. Stage 8 asks
`affordable` once per call and turns its answer into a denial; nothing else in
the course reads the counters at all.

    LimitError    what a cost, a reading or a calls count this stage refuses
    left          limits - spent, per counter, floored at zero
    fits          a read-only question: does this cost fit, calls included?
    charge        all or nothing: spend it, or refuse and spend nothing
    affordable    the same question in a tool's own terms, as data

DESIGN DECISION — why must `fits` be read-only, and why does the check ask it
twice?
    Because a question that mutates its subject cannot be asked twice, and a
    policy that asks it twice is exactly what a run does. If `fits` spent as a
    side effect — or if it were written as `charge` inside a `try` — then asking
    "does this fit?" would *use up* the very budget the answer was about, and
    the second question would answer differently from the first. A caller
    deciding whether to act has to be able to look without touching, so `fits`
    reads `meter.left()` and nothing else, and the check pins that by comparing
    `meter.used()` before and after two consecutive calls.

DESIGN DECISION — why is `charge` all or nothing rather than "spend what fits"?
    Because a partial charge is a charge nobody can undo, and the counters are
    not fungible: a call that spends its cpu and then finds the memory gone has
    already changed the state the caller asked about. So all four counters are
    compared with what is left *before* a single one is spent, and a charge that
    fails on the last counter leaves the first three exactly as they were. When
    it fails, the refusal names every counter that does not fit — with what it
    needs and what is left — because a caller who is told about one counter at a
    time fixes one counter at a time.

DESIGN DECISION — why is the comparison `>` and never `>=`?
    Because a limit checked with `>=` hands out one free unit per call: "does 8
    fit in 8?" would be answered "no", and the run stops one call early — or,
    written the other way round, "does 9 fit in 8?" is answered "yes" and the
    limit is not a limit. A cost that fits *exactly* — a need equal to what is
    left — is allowed; one unit more is not. The boundary is the whole stage, so
    it is written once, in one place, and the check asks both sides of it.

DESIGN DECISION — why is `left` floored at zero while `used()` keeps the truth?
    Because the two readings answer different questions and both are needed. A
    raw `Meter.spend` may take a counter past its limit — the world is not the
    policy engine and does not stop it — and once it has, `limits - spent` is a
    negative number that no caller can act on. Floored at zero, `left` says
    "nothing left" in the only arithmetic that makes sense, while `used()` still
    carries what was actually spent, so a check can tell an overspent counter
    from an untouched one. A reader that hid the overspend, or that refused it,
    would be the world policing itself.

DESIGN DECISION — why does `charge` raise while `affordable` returns?
    Because they answer to different owners. `charge` is called by somebody who
    has already decided the call fits, so "this does not fit" is that caller's
    own mistake and belongs to the course's one refusal family, naming the
    counters. `affordable` is asked *before* the decision, and its answer is the
    policy's: a denial is a normal outcome of a run and the loop has to keep
    going, so it comes back as data — `{"allowed", "reason", "short"}`, with
    `reason` from the closed vocabulary and `short` the sorted counters that do
    not fit. A limit of zero is a cap like any other: it fits nothing.

TODO: implement `left`, `fits`, `charge` and `affordable`.
"""

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


def left(meter):
    """What the meter has left, per counter, floored at zero.

    `Meter.left()` is the reading this stage publishes: a raw `spend()` may take
    a counter past its limit, and the arithmetic that follows must not go
    negative — a reading of zero says "nothing left" and is honest about it,
    while `used()` still carries the truth.
    """
    raise NotImplementedError("stage 5: implement left()")


def fits(meter, cost, *, calls=1):
    """Does this cost, over this many calls, fit what is left? A question only.

    Reads the meter and spends nothing: `meter.used()` is the same mapping after
    this call as it was before, however many times it is asked. A cost that fits
    exactly — a need equal to what is left — is allowed, and one unit more is
    not; the comparison is `>`, because a `>=` here would hand out one free unit
    per call, which is how a limit leaks.
    """
    raise NotImplementedError("stage 5: implement fits()")


def charge(meter, cost, *, calls=1):
    """Spend the cost and the calls, all of it or none of it.

    Every one of the four counters is checked before anything is spent, so a
    charge that fails on one counter leaves the other three exactly as they
    were: a partial charge is how a limit leaks. When nothing fits, the refusal
    names *every* counter that does not fit, each with what it needs and what is
    left, because a caller who fixes one counter at a time has to be told each
    time. Otherwise the world does the counting and `used()` comes back.
    """
    raise NotImplementedError("stage 5: implement charge()")


def affordable(meter, tool):
    """Can the meter pay for one call of this tool? Data, not an exception.

    The tool's own terms: its `cost` plus the one call every call spends, so
    this is `fits(meter, tool["cost"], calls=1)` with the answer spelled the way
    a decision needs it — `reason` from the closed vocabulary (`"granted"` or
    `"limit"`) and `short` the sorted names of the counters that do not fit,
    empty when nothing is short.
    """
    raise NotImplementedError("stage 5: implement affordable()")
