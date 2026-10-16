"""FDE From Scratch — stage 7: The workflow that waits for a human.

Every other stage in this course answers a question. This one has to *stop*.
Legal accountability sits with a person, and a person is unavailable, asleep and
busy: the machine reaches the step where a human must sign, and nothing after
that step runs — not on this tick, not on the next one, not because the caller
asked twice. That is the whole stage, and everything else in it exists to make
that stop survivable: a plan whose steps say who runs them, a journal of what
already happened, and a way back into a workflow that was cut in half by a
restart.

The customer's own paperwork is what a workflow moves, and the customer's own
person is what authorizes it. So the approval is data: an approver named in the
plan's approver tuple answers the gate, the answer is written down with the tick
it was given, and the machine carries on from the step after the gate — or from
the end of the plan, whichever the plan has left. A rejection is the other
verdict of the same act, and it is final: the steps after a refused gate never
run, and a rejected ticket never reaches `done`, because the reason the stage
exists is that a person said no.

The deadline is not the world's and not the stage's: it is the caller's, an int
of ticks counted from the ticket's own start, and the caller advances it. That is
what makes this stage testable and what makes it honest — a workflow that read a
clock could not be replayed, and a workflow that escalated on its own could not
be reasoned about. `advance(tick)` is where a deadline becomes a fact: past
`due_at` the ticket is `escalated`, no approval is accepted afterwards, and the
refusal says which ticket, which deadline and which tick.

The journal is the artifact. Every line carries its own `seq`, the lines are
append-only, and a workflow's state is a reading of them — which is what makes
the last promise of the stage checkable rather than a matter of trust. A
restarted process hands the journal and the plan back to `resume`, and the
workflow returns to the state the lines describe; the effects the journal already
carries are *not* applied again, however the replay goes, because a ledger is
worth exactly what it prevents. `effects_of` is the ledger read back: the names
of the effects one ticket's lines carry, in the order the lines carry them.

    STEP_KEYS                            one step of a plan, in order
    STATE_KEYS                           one ticket's state, in order
    STATES                               every state a ticket may hold
    ACTORS                               who runs a step: "machine" or "human"
    JOURNAL_KEYS                         one line of the journal, in order
    KINDS_OF_LINE                        every kind of line the journal may carry
    WorkflowError(estate.EstateError)    a refusal about a plan, a ticket or a journal
    Workflow(plan, approvers, deadline)
    Workflow.start(ticket, tick)         -> STATE_KEYS, at the first gate or the end
    Workflow.advance(tick)               -> the tickets whose deadline passed, in order
    Workflow.approve(approver, ticket, tick) -> STATE_KEYS, past the gate
    Workflow.reject(approver, ticket, tick)  -> STATE_KEYS, and nothing after it runs
    Workflow.state(ticket)               -> STATE_KEYS
    Workflow.pending(tick)               -> the tickets still standing at a gate
    Workflow.journal()                   -> every line written, in order
    resume(journal, plan, approvers, deadline, tick) -> Workflow
    effects_of(journal, ticket)          -> the effect names the journal carries

A plan is a tuple of `STEP_KEYS` records: a `name`, the `actor` who runs it, the
`effect` it applies when it runs (`None` when it applies nothing) and the `gate`
a human step waits for (`None` when any approver of the tuple may answer it). A
ticket is a name; its `due_at` is its own start tick plus the workflow's
deadline, and the gate is over at `tick >= due_at`, so a ticket is answered while
`tick < due_at` and escalated at exactly `due_at` and after. Every refusal names
the offender — the step, the ticket, the approver, the tick — and every answer is
a `STATE_KEYS` record or a tuple of them, never a bare truth.

DESIGN DECISION — why is the journal a sequence of lines rather than a snapshot
of the state?
Because a snapshot cannot say *when* something happened, and this stage's whole
job is knowing what has already happened and what may not happen twice. A state
snapshot answered "where is the ticket" and lost "the effect was applied at tick
9 and must not be applied again"; the lines keep both, in the order they
occurred, and they are what `resume` replays. A journal is also the only artifact
here that a human auditor reads.

DESIGN DECISION — why does the gate stop the machine instead of queueing the
next step for later?
Because a person is not a slow function. A queue that the machine drains on the
next tick would make the gate a delay rather than a decision, and the decision is
the point: the plan's steps after a human step must be unreachable by any amount
of ticking, and they are — `advance` may escalate an overdue ticket but it may
never approve one. The gate is also where the accountability of the whole stage
lives: the journal line naming the approver and the tick is the record that a
person, not a process, let the work continue.

DESIGN DECISION — why does `resume` refuse a journal whose last line is a `step`
or an `approved` line, instead of replaying it?
Because both are boundaries that the same call closes and no call ever leaves
open: after a `step` line the workflow writes that step's `effect` line (when it
has one) and then the next line, and after an `approved` line it writes what the
approval unlocked — an effect, another step, another gate, or `done`. A journal
that ends on either was cut in half between two writes and says nothing about
which half happened, so the honest answer is a refusal naming the line's index
and text, not a guess about whether the effect was applied. Every other tail is
replayable, and `resume` replays it.

DESIGN DECISION — why must an approval name the gate's own approver as well as
belong to the approver tuple?
Because the tuple is who this workflow listens to, and the `gate` is who this
step waits for, and they answer two different questions. A workflow where any
listed approver could answer any gate would make `gate` decoration and would let
a junior signature satisfy a step drafted for the CFO; a workflow that ignored
the tuple would let a name nobody authorized approve anything at all. Both are
checked, in that order, and both refusals name the approver that arrived.

DESIGN DECISION — why does `effects_of` read a journal rather than the workflow
that wrote it?
Because the question worth asking is what the *ledger* says, not what the object
remembers. A resumed workflow that re-applied an effect it had already recorded
would answer `Workflow.state()` from its own memory and agree with itself; the
journal is the artifact that survives the restart, and reading the effects out of
it is what makes the exactly-once rule visible from outside the workflow.

TODO: implement everything below: the six constants are already their real values,
and every function and method is a docstring plus one `raise NotImplementedError`.
"""

import estate

STEP_KEYS = ("name", "actor", "effect", "gate")

STATE_KEYS = ("ticket", "state", "steps", "next", "approver", "due_at", "effects")

STATES = ("draft", "waiting-approval", "approved", "rejected", "done", "escalated")

ACTORS = ("machine", "human")

JOURNAL_KEYS = ("seq", "tick", "kind", "ticket", "detail")

KINDS_OF_LINE = ("started", "step", "gate", "approved", "rejected", "escalated",
                 "effect", "done")


class WorkflowError(estate.EstateError):
    """A refusal about a workflow: a plan, a ticket, a tick or a journal."""


class Workflow:
    """One customer's plan, the tickets running through it, and its own journal."""

    def __init__(self, plan, approvers, deadline):
        """Hold the plan, the approvers a gate listens to, and the deadline's ticks.

        The plan is a tuple of `STEP_KEYS` records with distinct names; the
        approvers are a tuple of names, possibly empty (a gate then never opens);
        the deadline is one or more ticks, counted from each ticket's own start.
        """
        raise NotImplementedError("stage 7: implement Workflow.__init__()")

    def start(self, ticket, tick):
        """Begin a ticket at `tick`, run its machine, and answer the `STATE_KEYS`.

        The ticket's `due_at` is `tick` plus the workflow's deadline. Steps whose
        actor is `machine` run here, in plan order; the first `human` step stops
        the machine at a gate and is answered by `approve` or `reject`, never by
        ticking. A ticket with no gate reaches `done` here, with its effects
        applied exactly once.
        """
        raise NotImplementedError("stage 7: implement Workflow.start()")

    def advance(self, tick):
        """Escalate every ticket whose deadline has passed, in ticket order.

        A ticket standing at a gate with `tick >= due_at` becomes `escalated`:
        the gate is over, no approval is accepted afterwards, and the ticket is
        no longer pending. Answers one `STATE_KEYS` record per ticket whose state
        changed, in ticket order — the empty tuple when nothing was due.
        """
        raise NotImplementedError("stage 7: implement Workflow.advance()")

    def approve(self, approver, ticket, tick):
        """The gate's own approver lets the step run, and answers the `STATE_KEYS`.

        Refuses, naming the offender, a ticket that is not standing at a gate, a
        tick at or past `due_at`, an approver outside the plan's approver tuple,
        and an approver the gate does not wait for. Otherwise it runs the human
        step, applies its effect if it has one, and carries the machine on to the
        next gate or to `done`.
        """
        raise NotImplementedError("stage 7: implement Workflow.approve()")

    def reject(self, approver, ticket, tick):
        """The gate's own approver refuses the step, and answers the `STATE_KEYS`.

        Refused under the same conditions as `approve`. Otherwise the ticket is
        `rejected`, and nothing after the refused gate ever runs: `rejected` is
        final and no path from it reaches `done`.
        """
        raise NotImplementedError("stage 7: implement Workflow.reject()")

    def state(self, ticket):
        """One ticket's `STATE_KEYS`: what ran, what is next, and who is waited for."""
        raise NotImplementedError("stage 7: implement Workflow.state()")

    def pending(self, tick):
        """The tickets still standing at a gate whose deadline has not passed.

        Sorted, and never a ticket that is `done`, `rejected` or `escalated` —
        `tick` is what makes the answer honest, because a ticket whose deadline
        has already passed at `tick` is not waiting for anybody any more.
        """
        raise NotImplementedError("stage 7: implement Workflow.pending()")

    def journal(self):
        """Every line this workflow wrote, in seq order, as its own copies."""
        raise NotImplementedError("stage 7: implement Workflow.journal()")


def resume(journal, plan, approvers, deadline, tick):
    """The `Workflow` a journal describes, with its effects applied exactly once.

    Reads the lines in order and replays them into a fresh workflow: the same
    plan, the same approvers, the same deadline, and the state the lines describe
    at `tick`. An effect line already in the journal is never applied again,
    whatever the replay does, and a journal cut in half — one whose last line is
    a `step` or an `approved` line, the two boundaries a call always closes — is
    refused, naming the line's index and text, rather than replayed on a guess.
    """
    raise NotImplementedError("stage 7: implement resume()")


def effects_of(journal, ticket):
    """The effect names the journal carries for one ticket, in journal order.

    The ledger read back: what the lines say was applied, in the order they say
    it, so that a caller can hold the workflow's own answer against it.
    """
    raise NotImplementedError("stage 7: implement effects_of()")
