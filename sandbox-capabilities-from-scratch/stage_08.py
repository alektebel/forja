"""Sandbox & Capabilities From Scratch — stage 8: The call that never happens.

The composer: the first stage that *answers* rather than makes a rule. A call is
asked of the six stages below in their order — the catalogue, the grant, the jail,
the network, the meter, the secret — and the first "no" is the decision. Nothing
here re-implements a rule; every question is one of the earlier stages' own.

DESIGN DECISION — why is the order fixed, and why does the first "no" win?

The six questions are not a set, they are a sequence, and the order decides both
the answer and the *reason* a denial carries: a call naming a tool nobody has is
`unknown` even if it also points outside the root, a tool whose grant is short is
`capability` even if its target would also fail the jail, and a call whose demand
this world cannot even read is `capability` and never `unknown`. Reorder them and
two questions can agree that a call is refused while disagreeing about why, which
is the one thing an audit line exists to say. So the order is written down once,
and the decision returns on the first no.

DESIGN DECISION — why does `decide` return a denial instead of raising it?

A refusal is for what the *caller* got wrong — a call that is not a mapping, a
tool that is not a `str`, a target on a tool that carries none — and a denial is
for what the *policy* decided. A denial is not an error: it is what a policy is
*for*, and a run has to keep going after one. So `decide` raises `CallError` only
for the shapes nothing can be said about, and returns `{"allowed": False, ...}`
for everything the six questions can answer, with the reason from stage 7's
closed vocabulary.

DESIGN DECISION — why is the audit line written before the act, and why does a
denial write one too?

The line is the record of the *intent*, not of the outcome: a run that dies
mid-call leaves behind what it meant to do, and a call the policy refused is
exactly the call whose intent matters most. So `invoke` always decides, then
writes, then acts if allowed — and a denied call stops there, touching nothing
and spending nothing, with the line already holding the reason. The world's own
record is left to the act, so the two can be compared afterwards.

DESIGN DECISION — why predict `bytes`, and where does the prediction come from?

The line carries a byte count before the act has happened, so it must be a
prediction — and a prediction that is wrong is worse than none. `0` for every
denial, and for every tool whose target is not a byte count (a directory's shape,
a scripted command's effect, a secret's fingerprint). A `write` is its value's
length; a `read` or a `remove` of a file that is there is that file's size, asked
with `VFS.stat` — a question, not a touch, so the number can be checked against
the world's log afterwards; and a host tool's is the pair's declared bytes.

DESIGN DECISION — why compose rather than re-implement?

`jail`, `reachable`, `affordable`, `observe` and `line` already exist. A stage 8
that wrote its own containment test, or its own charge, would be a second policy
that can drift from the first, and the audit it wrote would no longer be the line
stage 7 defined. The composer's job is the *order* and the wiring, not the rules.

DESIGN DECISION — why is the observation frozen, and what does a denial carry?

Stages 9 and 10 are written against the observation, so its six fields are a
contract: `{"tool", "target", "decision", "reason", "bytes", "value"}`. `value`
is the act's own answer, and it is `None` for every denial — a denial carries the
reason and nothing else, never the file it refused. That is the whole point: the
audit can say the call was denied, and the observation cannot hand back what the
denial was protecting.

TODO: implement `decide`, the free `invoke`, and `Guard`, composing stages 1–7.
"""

from collections.abc import Mapping

import stage_01 as s1
import stage_02 as s2
import stage_03 as s3
import stage_04 as s4
import stage_05 as s5
import stage_06 as s6
import stage_07 as s7
import tools

#: The five fields a decision carries, in the order a decision writes them.
DECISION_KEYS = ("allowed", "reason", "target", "bytes", "detail")

#: The six fields an observation carries, in the order an observation writes them.
OBSERVATION_KEYS = ("tool", "target", "decision", "reason", "bytes", "value")


class CallError(s1.SandboxError):
    """A call this stage cannot read at all: not a mapping, no tool, or a field
    that is not a `str`. A question the *policy* can answer is a decision, never
    a refusal; this is only for the shapes nothing can be said about."""


def decide(call, policy, *, vfs, wire, meter, vault):
    """§3.1's six questions, in order, and the first "no" is the decision.

    Returns a fresh mapping over `DECISION_KEYS` — `{"allowed", "reason",
    "target", "bytes", "detail"}` — and raises `CallError` for a call nothing can
    be said about.
    """
    raise NotImplementedError("stage 8: implement decide()")


def invoke(guard, call):
    """Decide, write the line, then act if allowed — in that order, always."""
    raise NotImplementedError("stage 8: implement invoke()")


class Guard:
    """A policy and the world it decides against, with the line written first."""

    def __init__(self, policy, *, vfs, wire, vault, meter, audit, clock=None):
        self.policy = policy
        self.vfs = vfs
        self.wire = wire
        self.vault = vault
        self.meter = meter
        self.audit = audit
        self.clock = clock

    def decide(self, call):
        """§3.1's six questions, in order, against this guard's world."""
        raise NotImplementedError("stage 8: implement Guard.decide()")

    def invoke(self, call):
        """Decide, write the line, then act if allowed — through the world."""
        raise NotImplementedError("stage 8: implement Guard.invoke()")

    def __repr__(self):
        return "<Guard %r>" % (self.policy.get("principal", "?"),)
