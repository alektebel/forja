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

import copy

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


def _text(value, what):
    """A non-empty string, or a refusal naming what arrived instead."""
    if not isinstance(value, str) or not value:
        raise RunbookError("%s is %r, and it is a non-empty string" % (what, value))
    return value


def _free_text(value, what):
    """A string, empty or not, or a refusal naming what arrived instead."""
    if not isinstance(value, str):
        raise RunbookError("%s is %r, and it is a string" % (what, value))
    return value


def _tick(tick, what):
    """A tick at or after zero, or a refusal naming what arrived instead."""
    if not isinstance(tick, int) or tick < 0:
        raise RunbookError("%s is %r, and a tick is an int at or after zero"
                           % (what, tick))
    return tick


def _system(system, what):
    """A system — `apply(action, target, value)` and `state()` — or a refusal."""
    if (not callable(getattr(system, "apply", None))
            or not callable(getattr(system, "state", None))):
        raise RunbookError("%s is a %s, and a system has apply(action, target, "
                           "value) and state()" % (what, type(system).__name__))
    return system


def _member(record, keys, what):
    """A mapping carrying exactly `keys`, or a refusal naming what is wrong."""
    if not isinstance(record, dict):
        raise RunbookError("%s is a %s, and it is a mapping with the keys %r"
                           % (what, type(record).__name__, keys))
    extra = sorted(set(record) - set(keys))
    if extra:
        raise RunbookError("%s carries %r, and its keys are %r"
                           % (what, extra, keys))
    for key in keys:
        if key not in record:
            raise RunbookError("%s has no %r, and its keys are %r"
                               % (what, key, keys))
    return record


def _step(step, what):
    """One STEP_KEYS record, or a refusal naming what is wrong with it."""
    step = _member(step, STEP_KEYS, what)
    return {"action": _text(step["action"], "%s action" % (what,)),
            "target": _text(step["target"], "%s target" % (what,)),
            "expect": _free_text(step["expect"], "%s expect" % (what,))}


def _steps(steps, what):
    """An ordered tuple of STEP_KEYS records, or a refusal naming what arrived."""
    if not isinstance(steps, (tuple, list)):
        raise RunbookError("%s are a %s, and steps are a tuple of step records"
                           % (what, type(steps).__name__))
    return tuple(_step(step, "step %d of %s" % (index + 1, what))
                 for index, step in enumerate(steps))


def _procedure(procedure):
    """One PROCEDURE_KEYS record, or a refusal naming what is wrong with it."""
    procedure = _member(procedure, PROCEDURE_KEYS, "a procedure")
    name = _text(procedure["name"], "the procedure's name")
    when = _free_text(procedure["when"], "the %s condition" % (name,))
    actor = procedure["actor"]
    if actor not in ACTORS:
        raise RunbookError("the procedure %s is written for %r, and an actor is "
                           "one of %r" % (name, actor, ACTORS))
    return {"name": name, "when": when, "actor": actor,
            "steps": _steps(procedure["steps"], "the %s steps" % (name,)),
            "rollback": _steps(procedure["rollback"], "the %s rollback" % (name,))}


def _complaints(procedure):
    """What this procedure cannot vouch for, as `(name, problem)` pairs."""
    name = procedure["name"]
    found = []
    if not procedure["when"]:
        found.append((name, "no-when"))
    if not procedure["steps"]:
        found.append((name, "no-steps"))
    if not procedure["rollback"]:
        found.append((name, "no-rollback"))
    for step in procedure["steps"]:
        if not step["expect"]:
            found.append((name, "no-expect"))
            break
    return found


class Runbook:
    """The procedures a customer owns, and what is wrong with them."""

    def __init__(self):
        """An empty runbook: no procedures, and nothing to report about them."""
        self._held = {}
        self._problems = {}

    def add(self, procedure):
        """Take one procedure, and answer the record the runbook now holds.

        A procedure already held under the same name is not replaced: the first
        record stands, and the second one is reported as a duplicate.
        """
        procedure = _procedure(procedure)
        name = procedure["name"]
        if name in self._held:
            self._problems[(name, "duplicate-name")] = None
            return dict(self._held[name])
        for complaint in _complaints(procedure):
            self._problems[complaint] = None
        self._held[name] = procedure
        return dict(procedure)

    def procedures(self):
        """Every name this runbook holds, sorted."""
        return tuple(sorted(self._held))

    def problems(self):
        """What this runbook cannot vouch for, as `(name, problem)` pairs.

        The pairs come back in `RUNBOOK_PROBLEMS` order, so a name with two
        problems appears twice, in that precedence.
        """
        return tuple(sorted(self._problems,
                            key=lambda row: (RUNBOOK_PROBLEMS.index(row[1]),
                                             row[0])))

    def run(self, name, system, tick):
        """One procedure against one system, as `RUN_KEYS`.

        Every step's `expect` is checked after the step; a step whose `expect` is
        empty is unverified, and an unverified step does not pass. On a failed
        expectation the rollback runs and the outcome is `rolled-back`, or
        `failed` when there is no rollback to run at all.
        """
        procedure = self._named(name)
        system = _system(system, "the system")
        _tick(tick, "the tick")
        return _execute(name, procedure, system, None)

    def drill(self, faults, system, tick):
        """Every fault against its procedure, and every procedure no fault names.

        A fault is armed by replacing the answer of the step it names — the system
        is still called — and the row's `fault` is that step. A procedure no fault
        names answers one row with `fault` `None` and the outcome `uncovered`.
        """
        armed = _faults(faults, self)
        system = _system(system, "the system")
        _tick(tick, "the tick")
        rows = []
        watched = set()
        for fault in armed:
            watched.add(fault["procedure"])
            procedure = self._held[fault["procedure"]]
            outcome = _execute(fault["procedure"], procedure, system,
                               (fault["step"], fault["answer"]))["outcome"]
            rows.append({"procedure": fault["procedure"], "fault": fault["step"],
                         "outcome": outcome})
        for name in self._held:
            if name not in watched:
                rows.append({"procedure": name, "fault": None,
                             "outcome": "uncovered"})
        return tuple(sorted(rows, key=_rank))

    def self_serve(self):
        """The procedures written for the customer, sorted: what they can do alone."""
        return tuple(sorted(name for name in self._held
                            if self._held[name]["actor"] == "customer"))

    def _named(self, name):
        """The procedure held under `name`, or a refusal naming what was asked for."""
        if not isinstance(name, str) or name not in self._held:
            raise RunbookError("the runbook holds no procedure named %r; it holds "
                               "%r" % (name, self.procedures()))
        return self._held[name]


def _execute(name, procedure, system, armed):
    """Run one procedure's steps, arming `(step index, answer)` when a fault did."""
    steps = procedure["steps"]
    if not steps:
        return {"procedure": name, "outcome": "uncovered", "steps_done": 0,
                "rollback_done": 0}
    done = 0
    for index, step in enumerate(steps):
        answer = system.apply(step["action"], step["target"], step["expect"])
        done += 1
        if armed is not None and index == armed[0]:
            answer = armed[1]
        if not step["expect"] or answer != step["expect"]:
            return _recover(name, system, procedure["rollback"], done)
    return {"procedure": name, "outcome": "recovered", "steps_done": done,
            "rollback_done": 0}


def _recover(name, system, rollback, done):
    """Run a procedure's rollback after a failed step, and say what came of it."""
    for step in rollback:
        system.apply(step["action"], step["target"], step["expect"])
    return {"procedure": name,
            "outcome": "rolled-back" if rollback else "failed",
            "steps_done": done,
            "rollback_done": len(rollback)}


def _faults(faults, runbook):
    """The faults a drill arms, or a refusal naming what is wrong with one."""
    if not isinstance(faults, (tuple, list)):
        raise RunbookError("the faults are a %s, and they are a tuple of faults"
                           % (type(faults).__name__,))
    armed = []
    for fault in faults:
        fault = _member(fault, FAULT_KEYS, "a fault")
        procedure = runbook._named(fault["procedure"])
        index = fault["step"]
        if (not isinstance(index, int) or index < 0
                or index >= len(procedure["steps"])):
            raise RunbookError("the fault on %s names step %r, and that procedure "
                               "has %d step(s)"
                               % (procedure["name"], index,
                                  len(procedure["steps"])))
        armed.append({"procedure": procedure["name"], "step": index,
                      "answer": _free_text(fault["answer"],
                                           "the answer of the fault on %s"
                                           % (procedure["name"],))})
    return tuple(armed)


def _report(drill_report):
    """The rows of a drill report, or a refusal naming what is wrong with one."""
    if not isinstance(drill_report, (tuple, list)):
        raise RunbookError("the drill report is a %s, and it is a tuple of rows"
                           % (type(drill_report).__name__,))
    rows = []
    for row in drill_report:
        row = _member(row, DRILL_KEYS, "a drill row")
        if row["outcome"] not in OUTCOMES:
            raise RunbookError("the drill row for %r says %r, and an outcome is "
                               "one of %r"
                               % (row["procedure"], row["outcome"], OUTCOMES))
        rows.append(row)
    return rows


def _rank(row):
    """A drill row's sort key: by procedure, and `None` before any step index."""
    return (row["procedure"], -1 if row["fault"] is None else row["fault"])


def _rights(rights):
    """A mapping of actor to the actions they may apply, or a refusal naming it."""
    if not isinstance(rights, dict):
        raise RunbookError("the rights are a %s, and they are a mapping of an "
                           "actor to the actions that actor may apply"
                           % (type(rights).__name__,))
    held = {}
    for actor in rights:
        _text(actor, "a rights actor")
        actions = rights[actor]
        if not isinstance(actions, (tuple, list)):
            raise RunbookError("the rights of %r are a %s, and they are a tuple "
                               "of actions" % (actor, type(actions).__name__))
        held[actor] = tuple(_text(action, "an action of %r" % (actor,))
                            for action in actions)
    return held


class Admin:
    """One system, the rights each operator holds, and a line for every attempt."""

    def __init__(self, system, rights):
        """Take the system to administer, and who may apply what to it."""
        self._system = _system(system, "the system")
        self._rights = _rights(rights)
        self._lines = []

    def change(self, action, target, value, actor, tick):
        """Apply one change for one actor, and answer the line this attempt wrote.

        An actor whose rights do not carry the action's own right is refused, and
        a refused attempt is a line in the log like any other.
        """
        action = _text(action, "the action")
        target = _text(target, "the target")
        value = _free_text(value, "the value")
        actor = _text(actor, "the actor")
        tick = _tick(tick, "the tick")
        if action in self._rights.get(actor, ()):
            self._system.apply(action, target, value)
            verdict = "applied"
        else:
            verdict = "refused"
        return self._file(actor, action, target, value, tick, verdict)

    def dry_run(self, action, target, value):
        """The string the system would answer, with the system itself untouched."""
        action = _text(action, "the action")
        target = _text(target, "the target")
        value = _free_text(value, "the value")
        rehearsal = _system(copy.deepcopy(self._system), "the system's copy")
        return rehearsal.apply(action, target, value)

    def log(self):
        """Every attempt this admin made, in the order it made them."""
        return tuple(dict(line) for line in self._lines)

    def _file(self, actor, action, target, value, tick, verdict):
        """One `ADMIN_KEYS` line: written to the log, and answered."""
        line = {"actor": actor, "action": action, "target": target, "value": value,
                "tick": tick, "verdict": verdict}
        self._lines.append(line)
        return dict(line)


def gaps(drill_report, runbook):
    """The leverage list: what no fault exercised, and what is still the FDE's.

    Answers `(procedure, reason)` pairs, sorted, with the reason one of
    `GAP_REASONS`. A procedure no fault exercised at all was never tested, and it
    is reported as `uncovered` even when it is also written for the FDE.
    """
    rows = _report(drill_report)
    if not isinstance(runbook, Runbook):
        raise RunbookError("the runbook is a %s, and gaps reads a Runbook"
                           % (type(runbook).__name__,))
    exercised = set(row["procedure"] for row in rows
                    if row["outcome"] != "uncovered")
    found = []
    for name in runbook.procedures():
        if name not in exercised:
            found.append((name, "uncovered"))
        elif runbook._held[name]["actor"] == "fde":
            found.append((name, "fde-only"))
    return tuple(sorted(found))
