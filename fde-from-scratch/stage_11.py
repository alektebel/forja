"""FDE From Scratch — stage 11: From a vague ask to a scoped four weeks.

Everything up to here has been a machine doing what a document said. This stage
is the document. A room full of people says things — an ask, a constraint, a
metric somebody already tracks, an objection, something deliberately ruled out —
and the FDE's job is the translation between what was said and what four weeks
of engineering can honestly promise. That translation is a data structure, and
this stage builds it: a transcript of statements in, a plan out, and every gap
between the two named rather than smoothed over.

The whole stage turns on one habit. A plan that quietly drops the ask nobody
owns, or the metric nobody ever measured, is smaller than the ask and looks
complete; a plan that keeps the requirement and says `no-owner` is the document
the customer can argue with. So a problem is never a deletion, the owner is the
speaker or nothing at all, and the priority is the word the customer chose.

    STATEMENT_KEYS    the six fields of one statement, in the order it is read
    KINDS             what a statement may be: ask, constraint, metric, objection, scope-out
    REQUIREMENT_KEYS  the six fields of a requirement, in order
    PRIORITIES        must, should, could — strongest first
    UNITS             the units a baseline may be measured in
    METRIC_KEYS       the four fields of a metric, in order
    PLAN_KEYS         the eight fields of the plan, in order
    WEEK_CAPACITY     how many requirements one week of the four holds
    MIN_WORDS         the fewest words an ask can be made of and still be one
    SCOPE_PROBLEMS    every gap a plan reports, in the order it reports them
    ScopeError        a transcript or a plan this course cannot read
    requirements      (transcript) -> the requirements, req-01, req-02… in order
    workstreams       (requirements) -> (owner, (ids)) sorted by owner
    schedule          (workstreams, weeks) -> weeks of owners in fill order
    metrics           (transcript) -> the metrics the customer already tracks
    scope             (transcript, customer, weeks) -> the plan
    sow               (plan) -> the text the customer is asked to sign

A statement is a mapping in `STATEMENT_KEYS` order. Its `kind` decides what it
is: an `ask`, a `constraint` and a `metric` are requirements, an `objection` is
context, and a `scope-out` is exile — a requirement whose text is exactly a
scope-out statement's text is the customer saying this was already ruled out. A
`metric` statement's `metric` field is a `METRIC_KEYS` mapping, while an ask's or
a constraint's is the metric's *name* or `None`. A requirement that has no owner,
no metric, or fewer than `MIN_WORDS` words is still a requirement, and its gap is
reported in `PLAN_KEYS["problems"]` as a `(problem, requirement id)` pair.

DESIGN DECISION — why does a requirement with a gap stay in the plan?
Because the plan is the thing the customer reads back. Dropping the ask with no
owner makes the document look finished and the scoping look smaller than it is,
and the gap — the thing somebody has to go and fix — disappears at exactly the
moment it becomes the FDE's job. Keeping it costs one line and turns a silent
omission into the first agenda item.

DESIGN DECISION — why is the priority read from the customer's own words rather
than from the seat the speaker sits in?
Because a title is not evidence about the work; it is evidence about the org
chart. An executive who says "maybe we should look at this" and an intern who
says "we must fix this" have told the FDE two different things, and an FDE who
reads the org chart instead of the sentence builds the wrong four weeks. The
sentence is what was said; the seat is what an outsider assumes.

DESIGN DECISION — why is a requirement's owner `None` rather than the FDE?
Because the FDE is the one owner that means nothing: nobody at the customer has
agreed to anything, and the work has no one to be handed to. Writing this
stage's own author into the field would fill the column and hide the gap that
`no-owner` exists to raise, and the whole handoff story of this course is about
the customer owning their own work.

DESIGN DECISION — why does `schedule` answer exactly `weeks` tuples even when the
work does not fit?
Because a schedule is a statement about capacity, not a wish. The weeks the
caller asked for are the weeks the customer has, so the answer has that length
and the overflow is not squeezed in — a week that holds four requirements is a
week nobody can plan against. The overflow is not lost either: it is what
`out-of-capacity` counts, and the plan reports it with the number.

TODO: implement
"""

import estate

STATEMENT_KEYS = ("speaker", "role", "kind", "text", "amount_cents", "metric")

KINDS = ("ask", "constraint", "metric", "objection", "scope-out")

REQUIREMENT_KEYS = ("id", "text", "kind", "owner", "priority", "metric")

PRIORITIES = ("must", "should", "could")

UNITS = ("minutes", "cents", "percent", "tickets")

METRIC_KEYS = ("name", "baseline", "target", "unit")

PLAN_KEYS = ("customer", "requirements", "problems", "workstreams", "weeks",
             "metrics", "out_of_scope", "metrics_without_baseline")

WEEK_CAPACITY = 3

MIN_WORDS = 4

SCOPE_PROBLEMS = ("no-owner", "no-metric", "vague", "unknown-kind",
                  "metric-no-baseline", "out-of-capacity",
                  "scope-out-as-requirement")


class ScopeError(estate.EstateError):
    """A statement, a transcript or a plan this course cannot read, named field by field."""


def requirements(transcript):
    """The requirements of `transcript`, `req-01`, `req-02`… in statement order.

    A requirement is a statement whose `kind` is an ask, a constraint or a
    metric; the id counts the requirements and not the statements, so an
    objection in the middle consumes no id. The owner is the speaker who asked —
    `None` when the transcript recorded none, which is what `no-owner` is for —
    and the priority is the statement's own words.
    """
    raise NotImplementedError("stage 11: implement requirements()")


def workstreams(requirements):
    """The requirements grouped by owner: `(owner, (ids))`, sorted by owner.

    A requirement with no owner is in no workstream: an owner is what a
    workstream is. A requirement record that cannot be one — not a mapping, or
    missing a field — raises `ScopeError` naming it.
    """
    raise NotImplementedError("stage 11: implement workstreams()")


def schedule(workstreams, weeks):
    """`weeks` weeks of at most `WEEK_CAPACITY` requirements, in fill order.

    Each week answers the owners that fill it, in the order the requirements'
    own ids fill it, and a week with nothing left is an empty tuple. The answer
    is always `weeks` long, whatever is left over.
    """
    raise NotImplementedError("stage 11: implement schedule()")


def metrics(transcript):
    """The metrics the customer already tracks, in `METRIC_KEYS` order.

    A metric comes from a statement whose kind is `metric`; the metric an ask is
    judged by is a name on that ask and not a metric of the customer's record.
    """
    raise NotImplementedError("stage 11: implement metrics()")


def scope(transcript, customer, weeks):
    """The plan: `PLAN_KEYS`, with every gap in the transcript named.

    Every requirement the transcript produced is in the plan, every gap is a
    `(problem, requirement id)` pair in `SCOPE_PROBLEMS` order, and the
    must-haves the weeks cannot hold are reported with their count.
    """
    raise NotImplementedError("stage 11: implement scope()")


def sow(plan):
    """`plan` as the text the customer is asked to sign: one plan, one string.

    The customer's name, the requirements in their own order, the gaps, the
    metrics with their baselines, and the out-of-scope list — rendered the same
    way twice, because a document two runs disagree about is not a document.
    """
    raise NotImplementedError("stage 11: implement sow()")
