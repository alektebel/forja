"""Sandbox & Capabilities From Scratch — stage 10: An agent, its policy, and the answer to what it touched.

The capstone, and the first stage that is a whole *agent* rather than one rule:
a principal, a plan of raw calls, and one run that walks the plan through the
guard stage 8 built, answers what happened to each call, and then answers the
question the course exists for — what did it touch, from the audit and the
world's own record and not from the plan. Nothing here re-decides anything: the
policy is stage 2's, the six questions and the line are stage 8's, the report is
stage 9's. This stage owns the *loop* and the clock, and nothing else.

    DEFAULT_CALLS   how many calls a run may make before its cap stops it
    RunError        a plan, a limit or a clock this stage refuses
    run             one plan walked through one guard, and what it touched

DESIGN DECISION — why does the run hand each call straight to the guard, and
never read it with `parse_call` first?
    Because a call this world cannot grant is still a *call*, and the decision it
    deserves is a word from the closed vocabulary (`unknown`, for a tool nobody
    has), not a refusal that ends the run. `parse_call` is the *plan builder's*
    stricter gate — a plan that names a tool nobody has is a broken plan — while a
    decision about one call at run time is data the loop keeps going with. A gate
    in front of the guard would also make `unknown` a reason no run could ever
    write, which is exactly the reason the course's vocabulary exists to carry.

DESIGN DECISION — why is the clock the run's own, and why is it advanced *after*
each call?
    Because a tick here is a count, never a wall-clock reading (`fleet.Clock`),
    and what a call *cost* is knowable from its tool's declaration. The guard asks
    the run's clock for the tick of each line, so the run advances it by the
    tool's `cost.ticks` once the call is behind it — a run of `read_file`,
    `http_get`, `write_file` therefore stamps its lines at ticks 0, 1 and 3, and
    two runs of the same plan agree, tick for tick. A declaration this world
    cannot read costs nothing rather than crashing the clock: teleport is a
    refusal, not a reason to stop counting.

DESIGN DECISION — why is a denial for one reason a walk-on and a denial for
another a stop?
    Because a policy is not a crash. `capability`, `jail`, `host` and `secret` are
    the policy answering "no" to a question it was built to answer, and the run
    keeps going: the line says `denied`, the observation says why, and the plan's
    later calls still happen. A spent limit is different in kind — it is the world
    saying it will not pay — so a `limit` denial *and* the run's own call cap both
    stop the run, with `stopped_by = "limit"`: a call that cannot be paid for is a
    line, not a spin.

DESIGN DECISION — why are `report` and `touched` stage 9's answer over the sink's
*whole* contents and the world's whole record?
    Because both records are cumulative. The sink the run writes into may already
    hold lines from an earlier run, and the filesystem, the wire and the vault
    hold everything they have ever been made to touch. A report recomputed over
    this run's slice of that sink would subtract a prefix of the world and could
    not be cross-checked against it — the one property that makes "what did it
    touch" a proof. The run reads its own sink back with `parse_line` and hands
    stage 9 every line it finds, so the report is the report of the world in front
    of it.

DESIGN DECISION — why are `calls` the decisions and `observations` what each
call handed back?
    Because they are two halves of one call and line up by position: `calls[i]` is
    the decision stage 8 reached, and `observations[i]` is what the call handed
    back — the frozen six keys, with `value` the act's own answer and `None` for
    every denial. A reader who wants the reason reads `calls`; a reader who wants
    the act's answer reads `observations`; and neither has to be reconstructed
    from the other.

TODO: implement `run`.
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


class RunError(s1.SandboxError):
    """A plan, a limit or a clock this run refuses.

    The refusal names the offender: a plan that is not a sequence of call
    mappings (by index and shape), a `limit` that is not a positive int, or a
    `clock` that is not a `fleet.Clock`. A question the *policy* can answer is a
    decision, never a refusal; this is only for the shapes nothing can be said
    about.
    """


def run(principal, plan, *, vfs, wire, vault, meter, audit, clock=None,
        limit=DEFAULT_CALLS):
    """Walk `plan` through one guard, in order, and answer what it touched.

    Returns §3.6's mapping over `RUN_KEYS` — the decisions, the observations, and
    stage 9's report, touched and audit over the sink's whole contents — and
    raises `RunError` for a plan that is not a sequence of call mappings, a
    `limit` that is not a positive int, or a `clock` that is not a `fleet.Clock`.
    """
    raise NotImplementedError("stage 10: implement run()")
