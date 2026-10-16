"""FDE From Scratch — stage 12: A runbook that is tested, and an admin who is not you.

Eleven stages have built things the FDE can demonstrate to a customer. This one
builds the two artifacts that decide whether the customer still needs the FDE
next quarter: a runbook somebody else can follow, and an administrative path
somebody else can drive.

The runbook is data first and a test second. A procedure is a name, the condition
it is for, the actor it is written for — `"customer"` or `"fde"` — an ordered
list of steps and a rollback list. `run` executes each step against the system it
is handed, checks that step's `expect` *after* the step, and, when the
expectation fails, runs the rollback and answers `rolled-back`. A run that failed
with an empty rollback answers `failed`, because "we undid it" and "there was
nothing to undo it with" are different claims and only one of them is true. A
step whose `expect` is empty is applied and then cannot be verified at all: the
run does not get to call that a pass, and the runbook reports it as a problem.

The test is the drill, and a drill injects a *fault*: a procedure, the index of a
step of that procedure, and the answer the system will be made to give at that
step. The system is still called — the fault does not reach into it, it replaces
what came back — which is what makes a drill a rehearsal of the runbook rather
than a rehearsal of the customer's luck. `drill` answers one row per `(procedure,
fault)`: that procedure run with that fault armed, the row's `fault` being the
fault's step. Every procedure no fault names gets one row with `fault` `None` and
the outcome `uncovered`, because the good news is not the product of a drill —
`uncovered` is. A procedure that no fault exercises has never been run for real,
and the only thing worse than a runbook nobody tested is a runbook everybody
believes was tested.

`gaps` turns that report, plus the runbook's own actors, into the leverage list:
the procedures no fault exercised, and the procedures still written for the FDE.
Leverage is measured by how little the customer needs you, so a procedure written
for the FDE is a gap even when it passes its drill, and a procedure both
untested and FDE-only is reported as untested first.

The admin is the second half of the same idea: the customer's operators need a
path that is theirs, and that path has to be auditable. `Admin.change` answers
`applied` only for an actor whose rights carry the action's own right, and writes
one `ADMIN_KEYS` line for every attempt, allowed or refused — the refused ones are
the ones an auditor asks about. `Admin.dry_run` answers the string the system
*would* give without touching the system at all: the rehearsal runs against a copy,
so an operator can see what would happen before anything happens.

    PROCEDURE_KEYS                     the five fields of a procedure, in order
    STEP_KEYS                          the three fields of a step, in order
    ACTORS                             the two actors a procedure can be written for
    OUTCOMES                           what a procedure can be, once it is exercised
    DRILL_KEYS                         the three fields of a drill row, in order
    FAULT_KEYS                         the three fields of a fault, in order
    ADMIN_KEYS                         the six fields of an admin line, in order
    RUN_KEYS                           the four fields of a run, in order
    RUNBOOK_PROBLEMS                   what a runbook cannot vouch for, in precedence order
    GAP_REASONS                        why a procedure is on the leverage list
    RunbookError                       every refusal this stage raises
    Runbook()                          an empty runbook: no procedures, no problems
    Runbook.add(procedure)             -> PROCEDURE_KEYS, the record the runbook holds
    Runbook.procedures()               -> the names it holds, sorted
    Runbook.problems()                 -> (name, problem) pairs, in RUNBOOK_PROBLEMS order
    Runbook.run(name, system, tick)    -> RUN_KEYS, one procedure against one system
    Runbook.drill(faults, system, tick)-> DRILL_KEYS rows, sorted by (procedure, fault)
    Runbook.self_serve()               -> the procedures written for the customer, sorted
    Admin(system, rights)              one system, and who may apply what to it
    Admin.change(action, target, value, actor, tick) -> ADMIN_KEYS, and one log line
    Admin.dry_run(action, target, value)             -> what the system would answer
    Admin.log()                        -> every attempt this admin made, in order
    gaps(drill_report, runbook)        -> (procedure, reason) pairs, sorted

A system is any object with `apply(action, target, value) -> str` and
`state() -> dict`: the stage calls it and never reaches into it. A step hands its
own `expect` to `apply` as the value — a step says what the target should answer —
and a rollback step is applied the same way and is not verified, because a
recovery that answers something other than what it hoped for is still the recovery
that ran.

DESIGN DECISION — why are `rolled-back` and `failed` different answers, when both
say the run did not work?
Because they are the two different things an operator has to do next. `rolled-back`
means the system was put back and the incident stands as it was; `failed` means the
procedure stopped half-applied with nothing to put anything back with, and that is
the answer that has to wake somebody up. Collapsing them into one outcome would hide
the only distinction the runbook exists to make — the runbook that cannot undo itself
is the runbook you must not hand over.

DESIGN DECISION — why does a fault replace the answer instead of breaking the
system?
Because a drill has to be reproducible, and breaking a real system is not. A fault
names one step of one procedure and the answer that step will be made to receive;
the system is still called, so the drill exercises the same code path as a real run
and the runbook sees exactly what a real fault would hand it, while the injected
answer is data the caller chose and can therefore be asserted. A drill that reached
into the system to make it fail would depend on the system's own internals, would
leave the system changed for every procedure after it, and could not be run twice
for the same result.

DESIGN DECISION — why is a step with an empty `expect` a failure rather than a
skip?
Because a skip is a pass with a footnote. If an unverified step let the run continue
and report `recovered`, the runbook would be claiming a recovery it never confirmed,
and the claim would be indistinguishable from one it did confirm — the exact
substitution this course exists to refuse. So the step is applied, the absence of an
expectation is recorded as a problem of the procedure, and the run takes the failure
path: a procedure that cannot be verified is not a procedure that passed.

DESIGN DECISION — why does `dry_run` rehearse against a copy rather than apply and
undo?
Because there is no undo. The protocol gives this stage `apply` and `state` and
nothing else: an action that has run cannot be un-run by anything the stage knows,
and reverse-engineering one from `state()` would be guessing at a system this stage
does not own. A copy can be asked exactly what the system would answer — same code,
same question — while the system itself is never touched, which is what makes the
answer a *rehearsal* rather than a change somebody has to remember to reverse.

DESIGN DECISION — why does a procedure that is both untested and FDE-only report
`uncovered`?
Because the untested fact is the one that changes the handoff. Both are gaps and
neither is good news, but `fde-only` says "the customer has not taken this over
yet", while `uncovered` says "nobody knows whether this works at all" — and handing
over a procedure nobody has ever exercised is how a customer inherits a runbook that
fails on its first real incident. The report names the worse gap, so the work list
starts where the risk is.

TODO: implement `Runbook`, `Admin` and `gaps` in this file: the runbook with its
records and its problems, the run that rolls back, the drill that arms a fault and
reports what nobody exercised, the admin with its rights and its log, and the
dry run that leaves the system exactly as it found it.
"""

import estate

PROCEDURE_KEYS = ("name", "when", "actor", "steps", "rollback")

STEP_KEYS = ("action", "target", "expect")

ACTORS = ("customer", "fde")

OUTCOMES = ("recovered", "rolled-back", "uncovered", "failed")

DRILL_KEYS = ("procedure", "fault", "outcome")

FAULT_KEYS = ("procedure", "step", "answer")

ADMIN_KEYS = ("actor", "action", "target", "value", "tick", "verdict")

RUN_KEYS = ("procedure", "outcome", "steps_done", "rollback_done")

RUNBOOK_PROBLEMS = ("no-when", "no-steps", "no-rollback", "duplicate-name", "no-expect")

GAP_REASONS = ("uncovered", "fde-only")


class RunbookError(estate.EstateError):
    """A procedure, a step, a fault, a system or a tick that cannot be that thing."""


class Runbook:
    """The procedures a customer owns, and what is wrong with them."""

    def __init__(self):
        """An empty runbook: no procedures, and nothing to report about them."""
        raise NotImplementedError("stage 12: implement Runbook.__init__()")

    def add(self, procedure):
        """Take one procedure, and answer the record the runbook now holds.

        A procedure already held under the same name is not replaced: the first
        record stands, and the second one is reported as a duplicate.
        """
        raise NotImplementedError("stage 12: implement Runbook.add()")

    def procedures(self):
        """Every name this runbook holds, sorted."""
        raise NotImplementedError("stage 12: implement Runbook.procedures()")

    def problems(self):
        """What this runbook cannot vouch for, as `(name, problem)` pairs.

        The pairs come back in `RUNBOOK_PROBLEMS` order, so a name with two
        problems appears twice, in that precedence.
        """
        raise NotImplementedError("stage 12: implement Runbook.problems()")

    def run(self, name, system, tick):
        """One procedure against one system, as `RUN_KEYS`.

        Every step's `expect` is checked after the step; a step whose `expect` is
        empty is unverified, and an unverified step does not pass. On a failed
        expectation the rollback runs and the outcome is `rolled-back`, or
        `failed` when there is no rollback to run at all.
        """
        raise NotImplementedError("stage 12: implement Runbook.run()")

    def drill(self, faults, system, tick):
        """Every fault against its procedure, and every procedure no fault names.

        A fault is armed by replacing the answer of the step it names — the system
        is still called — and the row's `fault` is that step. A procedure no fault
        names answers one row with `fault` `None` and the outcome `uncovered`.
        """
        raise NotImplementedError("stage 12: implement Runbook.drill()")

    def self_serve(self):
        """The procedures written for the customer, sorted: what they can do alone."""
        raise NotImplementedError("stage 12: implement Runbook.self_serve()")


class Admin:
    """One system, the rights each operator holds, and a line for every attempt."""

    def __init__(self, system, rights):
        """Take the system to administer, and who may apply what to it."""
        raise NotImplementedError("stage 12: implement Admin.__init__()")

    def change(self, action, target, value, actor, tick):
        """Apply one change for one actor, and answer the line this attempt wrote.

        An actor whose rights do not carry the action's own right is refused, and
        a refused attempt is a line in the log like any other.
        """
        raise NotImplementedError("stage 12: implement Admin.change()")

    def dry_run(self, action, target, value):
        """The string the system would answer, with the system itself untouched."""
        raise NotImplementedError("stage 12: implement Admin.dry_run()")

    def log(self):
        """Every attempt this admin made, in the order it made them."""
        raise NotImplementedError("stage 12: implement Admin.log()")


def gaps(drill_report, runbook):
    """The leverage list: what no fault exercised, and what is still the FDE's.

    Answers `(procedure, reason)` pairs, sorted, with the reason one of
    `GAP_REASONS`. A procedure no fault exercised at all was never tested, and it
    is reported as `uncovered` even when it is also written for the FDE.
    """
    raise NotImplementedError("stage 12: implement gaps()")
