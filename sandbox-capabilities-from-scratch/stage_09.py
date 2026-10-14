"""Sandbox & Capabilities From Scratch — stage 9: The report, and the world's own record.

A run writes one audit line per call — allowed or denied — and the world writes
its own record of what it was actually made to touch. Those are two different
accounts, and this stage is the only place they meet. `report` recomputes twelve
counters **from the lines and the meter alone**, and then *decides* them against
`VFS.log()`, `Wire.dialled()` and `Vault.reads()`: every allowed path line must
be matched by a log entry at its target, every log entry no path line accounts
for must be inside an allowed process line's target (stage 3's component-wise
containment, because a scripted command works in a directory and touches things
inside it), a dial no host line claims is explained by an allowed process line,
and a handle the vault read must be claimed by a `secret:read` line — the handle
a `secret`-kind call names, or every handle at once for an `env_dump`. No touch
may be left that only a denied line asked for. When the two accounts disagree the
report refuses, naming the line and the record; `audit` walks the same ground and
reports `{"missing", "extra", "count"}` instead of raising, because a
disagreement is something to print, not something to crash on.

    REPORT_KEYS   the twelve fields a report carries, in writing order
    ReportError   a report, an entry, or a disagreement with the world this
                  stage refuses
    report        the twelve counters, recomputed from the lines and the meter,
                  then checked against the world's own record
    touched       the sorted distinct targets the allowed entries name, and
                  nothing else
    audit         the same walk, reporting the disagreement instead of raising

DESIGN DECISION — why is the report recomputed from the *lines* rather than from
the run's own memory of what it did?
    Because a run's memory is the thing under audit. The lines are records the run
    wrote before it acted, the world's three logs are records it did not write at
    all, and a report built from a fourth, unshared account could agree with
    itself while disagreeing with both. Recomputing from the lines and deciding
    against the world is what turns "what did it touch" from a claim into a proof:
    the numbers carry no information the records do not, and a counter that could
    not be backed by a record is a `ReportError` instead of a quietly wrong
    figure.

DESIGN DECISION — why does `audit` never raise, while `report` refuses?
    Because the two callers want opposite things from the same walk. `report` is
    part of a run's output and must refuse rather than emit numbers the world
    contradicts — a soft report is a report nobody can rely on. `audit` is what a
    reader runs *after* a disagreement to see it, so a raise there would destroy
    the very evidence it exists to show: it answers with the offending line and
    the offending record, side by side, and `count` says how many entries were
    looked at. The walk is one function; only the ending differs.

DESIGN DECISION — why is a `list` line's `bytes` not compared against the
world's count?
    Because the count of a directory's children is a number nobody can write down
    before the listing runs, and asking would itself be a touch that entered the
    log the report is decided against. A listing moves no bytes, so its line says
    `bytes=0` and the world's own count stays in the world. Comparing them would
    make every correct `list_dir` line a disagreement, and the mistake this stage
    is written to catch is exactly that comparison, not its absence.

DESIGN DECISION — why is `secrets` a number rather than a set of handles?
    Because the handle a secret was read under is a *position* the world already
    keeps: `Vault.reads()` holds the handles, in order, and the vault is the
    tie-breaker a report is decided against. A report that carried the handle set
    would be repeating the world's record in the agent's words — a claim about
    the world standing next to the world itself — where a count can only ever be
    checked by walking that record. A `secret`-kind line already names the handle
    it read, and a `none`-kind call like `env_dump` reads every handle at once, so
    the claim is decided from the lines and only the *number* of reads has to be
    reported: what the report owes the reader is how many reads it accounted for.

DESIGN DECISION — why must `touched` be the *allowed* targets and nothing else?
    Because `touched` is the plain-language answer to "what did it touch", and a
    denied call touched nothing — it was answered before the world was asked. A
    `touched` that included the denied targets would say the sandbox reached
    things it refused, which is precisely the falsehood the world's records exist
    to expose. The distinction is the course's thesis in one function: the set
    the policy allowed is the set the world acted on, and a denied target belongs
    to neither.

TODO: implement `report`, `touched` and `audit`.
"""

from stage_01 import SandboxError
from stage_03 import inside
from stage_07 import AUDIT_KEYS, DECISIONS, REASONS

#: The twelve fields a report carries, in the order a report writes them.
REPORT_KEYS = ("principal", "calls", "allowed", "denied", "capabilities", "paths",
               "bytes", "hosts", "secrets", "cpu", "memory", "ticks")


class ReportError(SandboxError):
    """A report, an entry, or a disagreement with the world this stage refuses.

    The refusal names the offender: the index and the spelling of an entry this
    stage cannot read, or the line and the record the world and the lines
    disagree about.
    """


def report(entries, *, meter, vfs, wire, vault):
    """The twelve counters, recomputed from the lines and the meter, checked
    against the world's own record.

    `entries` is the sequence of mappings `stage_07.parse_line` returns, each
    carrying exactly `AUDIT_KEYS`. The report carries exactly `REPORT_KEYS`, in
    order, and refuses with `ReportError` naming the entry index and the offender
    for an entry it cannot read, and naming the line and the record when the
    world and the lines disagree.
    """
    raise NotImplementedError("stage 9: implement report()")


def touched(entries):
    """The sorted distinct targets the allowed entries name, and nothing else.

    A denied entry names a target the sandbox refused, so it is not something the
    run touched; a `touched` that carried it would answer a question nobody asked.
    """
    raise NotImplementedError("stage 9: implement touched()")


def audit(entries, *, vfs, wire, vault):
    """The same walk as `report`, reporting the disagreement instead of raising.

    Answers `{"missing": the records no allowed line accounts for, "extra": the
    allowed lines the record does not hold, "count": the number of entries}`, each
    item pairing the line and the record it disagrees with.
    """
    raise NotImplementedError("stage 9: implement audit()")
