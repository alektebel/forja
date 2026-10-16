"""FDE From Scratch — stage 07: The workflow that waits for a human.

The smallest machine that can stop: a plan of steps, the gate in it, an
append-only journal of what happened, and an approval that is the only thing
which may move the workflow past a person.
"""

import estate

STEP_KEYS = ("name", "actor", "effect", "gate")

STATE_KEYS = ("ticket", "state", "steps", "next", "approver", "due_at", "effects")

STATES = ("draft", "waiting-approval", "approved", "rejected", "done", "escalated")

ACTORS = ("machine", "human")

JOURNAL_KEYS = ("seq", "tick", "kind", "ticket", "detail")

KINDS_OF_LINE = ("started", "step", "gate", "approved", "rejected", "escalated",
                 "effect", "done")

_RESTING = ("waiting-approval", "rejected", "escalated", "done")
_OVER = ("rejected", "escalated", "done")
_UNCLOSED = ("step", "approved")


class WorkflowError(estate.EstateError):
    """A refusal about a workflow: a plan, a ticket, a tick or a journal."""


def _name(value, what):
    """A non-empty name, or a refusal naming what arrived instead."""
    if not isinstance(value, str) or not value:
        raise WorkflowError("%s must be a non-empty str, not %r" % (what, value))
    return value


def _tick(value, what):
    """A tick of the caller's clock: an int at or after zero, or a refusal."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise WorkflowError("%s must be an int, not %r" % (what, value))
    if value < 0:
        raise WorkflowError("%s is zero or more, not %d" % (what, value))
    return value


def _step_record(step, index):
    """One `STEP_KEYS` step of the plan, or a refusal naming the step and field."""
    if not isinstance(step, dict):
        raise WorkflowError("step %d of the plan is a %s, not a STEP_KEYS record"
                            % (index, type(step).__name__))
    if len(step) != len(STEP_KEYS) or any(key not in step for key in STEP_KEYS):
        raise WorkflowError("step %d of the plan carries the keys %r, and a step "
                            "is %r" % (index, tuple(step), STEP_KEYS))
    if not isinstance(step["name"], str) or not step["name"]:
        raise WorkflowError("step %d of the plan is named %r" % (index, step["name"]))
    name = step["name"]
    if step["actor"] not in ACTORS:
        raise WorkflowError("step %r runs as %r, and an actor is one of %r"
                            % (name, step["actor"], ACTORS))
    if step["effect"] is not None and not _named(step["effect"]):
        raise WorkflowError("step %r applies the effect %r, and an effect is a "
                            "name or None" % (name, step["effect"]))
    if step["gate"] is not None and not _named(step["gate"]):
        raise WorkflowError("step %r waits for the approver %r, and a gate is a "
                            "name or None" % (name, step["gate"]))
    if step["actor"] == "machine" and step["gate"] is not None:
        raise WorkflowError("step %r is a machine step that waits for %r: a gate "
                            "belongs to a human step" % (name, step["gate"]))
    return {"name": name, "actor": step["actor"], "effect": step["effect"],
            "gate": step["gate"]}


def _named(value):
    """True for a non-empty string, the only shape an effect or a gate may take."""
    return isinstance(value, str) and bool(value)


def _plan_steps(plan):
    """A tuple of `STEP_KEYS` steps with distinct names, or a refusal naming it."""
    if not isinstance(plan, tuple):
        raise WorkflowError("a plan is a tuple of steps, not %s"
                            % (type(plan).__name__,))
    if not plan:
        raise WorkflowError("a plan is one or more steps, and this one is empty")
    steps = tuple(_step_record(step, index) for index, step in enumerate(plan))
    seen = []
    for step in steps:
        if step["name"] in seen:
            raise WorkflowError("two steps of the plan are named %r" % (step["name"],))
        seen.append(step["name"])
    return steps


def _approver_tuple(approvers):
    """The gate's listeners: a tuple of names, possibly empty, or a refusal."""
    if not isinstance(approvers, tuple):
        raise WorkflowError("approvers is a tuple of names, not %s"
                            % (type(approvers).__name__,))
    for name in approvers:
        if not _named(name):
            raise WorkflowError("an approver is a non-empty name, not %r" % (name,))
    return approvers


def _ticks_deadline(deadline):
    """The ticks a ticket may wait at a gate: one or more, or a refusal."""
    if isinstance(deadline, bool) or not isinstance(deadline, int):
        raise WorkflowError("a deadline is an int of ticks, not %r" % (deadline,))
    if deadline < 1:
        raise WorkflowError("a deadline is one or more ticks, not %d" % (deadline,))
    return deadline


def _journal_lines(journal):
    """A journal's own lines in seq order, or a refusal naming the line."""
    if not isinstance(journal, tuple):
        raise WorkflowError("a journal is a tuple of lines, not %s"
                            % (type(journal).__name__,))
    lines = []
    for index, line in enumerate(journal):
        if not isinstance(line, dict) or any(key not in line for key in JOURNAL_KEYS):
            raise WorkflowError("line %d of the journal is not a JOURNAL_KEYS record: %r"
                                % (index, line))
        if line["seq"] != index:
            raise WorkflowError("line %d of the journal carries seq %r"
                                % (index, line["seq"]))
        if line["kind"] not in KINDS_OF_LINE:
            raise WorkflowError("line %d of the journal is a %r, and a line is one "
                                "of %r" % (index, line["kind"], KINDS_OF_LINE))
        lines.append({key: line[key] for key in JOURNAL_KEYS})
    return tuple(lines)


class Workflow:
    """One customer's plan, the tickets running through it, and its own journal."""

    def __init__(self, plan, approvers, deadline):
        """Hold the plan, the approvers a gate listens to, and the ticket's ticks."""
        self._plan = _plan_steps(plan)
        self._approvers = _approver_tuple(approvers)
        self._deadline = _ticks_deadline(deadline)
        self._tickets = {}
        self._journal = []

    def _line(self, kind, ticket, detail, tick):
        """Append one journal line: its `seq` is always the one after the last."""
        self._journal.append({"seq": len(self._journal), "tick": tick, "kind": kind,
                              "ticket": ticket, "detail": detail})

    def _state_of(self, ticket):
        """The `STATE_KEYS` record of one ticket, from what the workflow holds."""
        record = self._tickets[ticket]
        nxt = None
        if record["state"] not in _OVER and record["index"] < len(self._plan):
            nxt = self._plan[record["index"]]["name"]
        return {"ticket": ticket, "state": record["state"],
                "steps": tuple(record["steps"]), "next": nxt,
                "approver": record["approver"], "due_at": record["due_at"],
                "effects": tuple(record["effects"])}

    def _run_step(self, ticket, step, tick):
        """Run one step: the journal line, and the effect line when it has one."""
        record = self._tickets[ticket]
        record["index"] += 1
        record["steps"].append(step["name"])
        self._line("step", ticket, step["name"], tick)
        if step["effect"] is not None:
            record["effects"].append(step["effect"])
            self._line("effect", ticket, step["effect"], tick)

    def _carry(self, ticket, tick):
        """Run the machine forward until it rests: at a gate, or at the end."""
        record = self._tickets[ticket]
        while record["index"] < len(self._plan):
            step = self._plan[record["index"]]
            if step["actor"] == "human":
                record["state"] = "waiting-approval"
                record["approver"] = step["gate"]
                self._line("gate", ticket, step["gate"], tick)
                return
            self._run_step(ticket, step, tick)
        record["state"] = "done"
        record["approver"] = None
        self._line("done", ticket, None, tick)

    def _known(self, ticket):
        """The name of a ticket the workflow holds, or a refusal naming it."""
        ticket = _name(ticket, "a ticket")
        if ticket not in self._tickets:
            raise WorkflowError("no ticket named %r is in this workflow" % (ticket,))
        return ticket

    def _answer(self, approver, ticket, tick, verdict):
        """Answer the gate a ticket stands at: refuse in order, then record it."""
        tick = _tick(tick, "a tick")
        approver = _name(approver, "an approver")
        ticket = self._known(ticket)
        record = self._tickets[ticket]
        if tick >= record["due_at"]:
            raise WorkflowError("ticket %r was due at tick %d, so it cannot be %s "
                                "at tick %d" % (ticket, record["due_at"], verdict, tick))
        if record["state"] != "waiting-approval":
            raise WorkflowError("ticket %r is %r, and no gate waits for approval"
                                % (ticket, record["state"]))
        if approver not in self._approvers:
            raise WorkflowError("%r is not one of the approvers %r"
                                % (approver, self._approvers))
        step = self._plan[record["index"]]
        if step["gate"] is not None and approver != step["gate"]:
            raise WorkflowError("the gate at step %r waits for %r, and %r answered"
                                % (step["name"], step["gate"], approver))
        record["approver"] = None
        self._line(verdict, ticket, approver, tick)
        if verdict == "approved":
            record["state"] = "approved"
            record["index"] += 1
            record["steps"].append(step["name"])
            if step["effect"] is not None:
                record["effects"].append(step["effect"])
                self._line("effect", ticket, step["effect"], tick)
            self._carry(ticket, tick)
        else:
            record["state"] = "rejected"
        return self._state_of(ticket)

    def start(self, ticket, tick):
        """Begin a ticket at `tick`, and run its machine to a gate or the end."""
        tick = _tick(tick, "a tick")
        ticket = _name(ticket, "a ticket")
        if ticket in self._tickets:
            raise WorkflowError("ticket %r is already in this workflow" % (ticket,))
        self._tickets[ticket] = {"state": "draft", "steps": [], "index": 0,
                                 "effects": [], "due_at": tick + self._deadline,
                                 "approver": None}
        self._line("started", ticket, None, tick)
        self._carry(ticket, tick)
        return self._state_of(ticket)

    def advance(self, tick):
        """Escalate the tickets whose deadline has passed by `tick`, in order."""
        tick = _tick(tick, "a tick")
        changed = []
        for ticket in sorted(self._tickets):
            record = self._tickets[ticket]
            if record["state"] != "waiting-approval" or tick < record["due_at"]:
                continue
            record["state"] = "escalated"
            record["approver"] = None
            self._line("escalated", ticket, None, tick)
            changed.append(self._state_of(ticket))
        return tuple(changed)

    def approve(self, approver, ticket, tick):
        """Approve the gate a ticket stands at, and run what follows it."""
        return self._answer(approver, ticket, tick, "approved")

    def reject(self, approver, ticket, tick):
        """Reject the gate a ticket stands at: nothing after that gate ever runs."""
        return self._answer(approver, ticket, tick, "rejected")

    def state(self, ticket):
        """The `STATE_KEYS` record of one ticket, or a refusal naming it."""
        return self._state_of(self._known(ticket))

    def pending(self, tick):
        """The tickets still waiting at a gate whose deadline has not passed."""
        tick = _tick(tick, "a tick")
        return tuple(sorted(ticket for ticket in self._tickets
                            if self._tickets[ticket]["state"] == "waiting-approval"
                            and tick < self._tickets[ticket]["due_at"]))

    def journal(self):
        """Every line this workflow wrote, in order, as its own copies."""
        return tuple(dict(line) for line in self._journal)

    def _fold(self, line):
        """Replay one line into the ticket it names, applying no effect at all."""
        ticket = line["ticket"]
        kind = line["kind"]
        if kind == "started":
            if ticket in self._tickets:
                raise WorkflowError("line %d starts ticket %r twice"
                                    % (line["seq"], ticket))
            self._tickets[ticket] = {"state": "draft", "steps": [], "index": 0,
                                     "effects": [],
                                     "due_at": line["tick"] + self._deadline,
                                     "approver": None}
            return
        if ticket not in self._tickets:
            raise WorkflowError("line %d is a %r for ticket %r, which never started"
                                % (line["seq"], kind, ticket))
        record = self._tickets[ticket]
        if kind == "step":
            record["index"] += 1
            record["steps"].append(line["detail"])
        elif kind == "effect":
            record["effects"].append(line["detail"])
        elif kind == "gate":
            record["state"] = "waiting-approval"
            record["approver"] = line["detail"]
        elif kind == "approved":
            if record["index"] >= len(self._plan):
                raise WorkflowError("line %d approves ticket %r past the end of the "
                                    "plan" % (line["seq"], ticket))
            record["state"] = "approved"
            record["approver"] = None
            record["index"] += 1
            record["steps"].append(self._plan[record["index"] - 1]["name"])
        elif kind == "rejected":
            record["state"] = "rejected"
            record["approver"] = None
        elif kind == "escalated":
            record["state"] = "escalated"
            record["approver"] = None
        elif kind == "done":
            record["state"] = "done"
            record["approver"] = None

    def _replay(self, lines, tick):
        """Load a journal, then carry whatever it left mid-flight forward."""
        for line in lines:
            self._journal.append(dict(line))
            self._fold(line)
        for ticket in sorted(self._tickets):
            if self._tickets[ticket]["state"] not in _RESTING:
                self._carry(ticket, tick)


def resume(journal, plan, approvers, deadline, tick):
    """The workflow a journal describes, with every effect in it applied once."""
    tick = _tick(tick, "a tick")
    lines = _journal_lines(journal)
    if lines and lines[-1]["kind"] in _UNCLOSED:
        raise WorkflowError("the journal ends at line %d with the half-written %r "
                            "of ticket %r (%r), and the line that closes it was "
                            "never written"
                            % (len(lines) - 1, lines[-1]["kind"], lines[-1]["ticket"],
                               lines[-1]["detail"]))
    flow = Workflow(plan, approvers, deadline)
    flow._replay(lines, tick)
    return flow


def effects_of(journal, ticket):
    """The effect names a journal carries for one ticket, in journal order."""
    lines = _journal_lines(journal)
    ticket = _name(ticket, "a ticket")
    return tuple(line["detail"] for line in lines
                 if line["ticket"] == ticket and line["kind"] == "effect")
