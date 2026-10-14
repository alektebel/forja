"""stage_10.py — an agent, its policy, and the answer to what it touched.

Sandbox & Capabilities From Scratch — stage 10: An agent, its policy, and the answer to what it touched

The capstone: one principal, one plan of raw calls, and one run that walks the
plan through the guard stage 8 built. `run` owns the *loop* and the clock and
nothing else — the policy is stage 2's `policy_for`, the six questions and the
line are stage 8's `Guard`, the report is stage 9's over the sink read back with
stage 7's `parse_line`. It never reads a call with `parse_call` first: a tool
nobody has is a decision (`unknown`), not a broken plan, and a gate in front of
the guard would make one of the seven reasons a word no run could write.

The clock is `fleet.Clock`, counted and never timed: the guard asks it for each
line's tick, and the run advances it by the tool's own `cost.ticks` once the call
is behind it, so `read_file`, `http_get` and `write_file` stamp their lines at
ticks 0, 1 and 3 and two runs of one plan agree, tick for tick.

A denial is the policy answering and not a crash: the run walks past `capability`,
`jail`, `host` and `secret` and keeps going, but a `limit` denial — or the run's
own call cap — stops it, because a call the world will not pay for is a line and
not a spin.

    DEFAULT_CALLS   how many calls a run may make before its cap stops it
    RUN_KEYS        the seven fields a run returns, in writing order
    RunError        a plan, a limit or a clock this run refuses
    run             one plan walked through one guard, and what it touched
"""

from collections.abc import Mapping, Sequence

from fleet import Clock

import tools

import stage_01 as s1
import stage_02 as s2
import stage_07 as s7
import stage_08 as s8
import stage_09 as s9

#: The cap on how many calls one run may make. It matches the world's own
#: `tools.DEFAULT_LIMITS["calls"]`, so a plan of a few calls never stops for a
#: cap nobody asked about and one plan still meets the wall.
DEFAULT_CALLS = 8

#: The seven fields a run returns, in the order a run writes them.
RUN_KEYS = ("calls", "observations", "report", "touched", "audit", "clock",
            "stopped_by")

#: The reason a spent limit carries, read from stage 7's own vocabulary so the
#: word the run stops on is the word the line is written with.
_LIMIT = s7.REASONS[5]


class RunError(s1.SandboxError):
    """A plan, a limit or a clock this run refuses.

    The refusal names the offender: a plan that is not a sequence of call
    mappings (by index and shape), a `limit` that is not a positive int, or a
    `clock` that is not a `fleet.Clock`. A question the *policy* can answer is a
    decision, never a refusal; this is only for the shapes nothing can be said
    about.
    """


def _plan_steps(plan):
    """The plan as the run walks it, or a refusal that names the offender.

    A plan is a *sequence* of call mappings — a tuple or a list, never a string
    (which would be walked one character at a time) and never a mapping (which is
    not a sequence). The steps are handed back as they were given, not copied:
    the run reads them and never writes them, so running a plan leaves it exactly
    as it was found.
    """
    if isinstance(plan, (str, bytes)) or not isinstance(plan, Sequence):
        raise RunError(
            "run(): a plan must be a sequence of calls, got %r: a plan is a "
            "tuple or a list of call mappings" % (type(plan).__name__,))
    steps = []
    for index, call in enumerate(plan):
        if not isinstance(call, Mapping):
            raise RunError(
                "run(): the plan's call %d is %r, not a mapping: every step of a "
                "plan is a call" % (index, type(call).__name__))
        steps.append(call)
    return steps


def _limit(limit):
    """The call cap, or a refusal naming the value that is not a positive int."""
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise RunError("run(): the limit must be a positive int, got %r"
                       % (limit,))
    if limit < 1:
        raise RunError("run(): the limit must be at least 1, got %r" % (limit,))
    return limit


def _clock(clock):
    """J1's clock, injected or fresh: a run counts ticks and never reads one."""
    if clock is None:
        return Clock()
    if not isinstance(clock, Clock):
        raise RunError(
            "run(): the clock must be a fleet.Clock, got %r: a run's ticks are "
            "counted, never timed" % (type(clock).__name__,))
    return clock


def _ticks(name):
    """What one call of a tool costs in ticks, or nothing if unreadable.

    The cost is asked for the way stage 1 reads a declaration (`parse_tool`), so
    a tool this world does not have costs nothing and a declaration this world
    cannot read — `teleport`, whose demand is outside the vocabulary — costs
    nothing too, rather than crashing the clock the line is stamped with.
    """
    if not isinstance(name, str):
        return 0
    declaration = tools.TOOLS.get(name)
    if declaration is None:
        return 0
    try:
        return s1.parse_tool(name, declaration)["cost"]["ticks"]
    except s1.SandboxError:
        return 0


def run(principal, plan, *, vfs, wire, vault, meter, audit, clock=None,
        limit=DEFAULT_CALLS):
    """Walk `plan` through one guard, in order, and answer what it touched.

    The plan is validated (a sequence of call mappings), the limit is validated
    (a positive int), the clock is the injected `fleet.Clock` or a fresh one, and
    the policy is stage 2's for the principal. Then each call, in order: if the
    cap has already been reached the call never happens — not decided, not
    written, in no tuple — and `stopped_by` is `"limit"`; otherwise the guard
    decides it, writes its line and acts, the decision and the observation are
    collected, the clock is advanced by the call's own `cost.ticks`, and a `limit`
    denial stops the run. Every other denial is walked past.

    The report and `touched` are stage 9's, recomputed over the sink's *whole*
    contents (read back with stage 7's `parse_line`) and cross-checked against the
    world's own record, because the records are cumulative. `clock` is the run's
    last tick; `stopped_by` is the reason that ended it, else `None`.
    """
    steps = _plan_steps(plan)
    limit = _limit(limit)
    clock = _clock(clock)
    policy = s2.policy_for(principal)
    guard = s8.Guard(policy, vfs=vfs, wire=wire, vault=vault, meter=meter,
                     audit=audit, clock=clock.now)

    calls = []
    observations = []
    made = 0
    stopped_by = None
    for call in steps:
        if made >= limit:
            stopped_by = _LIMIT
            break
        decision = guard.decide(call)
        observation = guard.invoke(call)
        calls.append(decision)
        observations.append(observation)
        made += 1
        clock.tick(_ticks(call["tool"]))
        if observation["reason"] == _LIMIT:
            stopped_by = _LIMIT
            break

    entries = tuple(s7.parse_line(text) for text in audit.lines())
    return {
        "calls": tuple(calls),
        "observations": tuple(observations),
        "report": s9.report(entries, meter=meter, vfs=vfs, wire=wire,
                            vault=vault),
        "touched": s9.touched(entries),
        "audit": entries,
        "clock": clock.now(),
        "stopped_by": stopped_by,
    }
