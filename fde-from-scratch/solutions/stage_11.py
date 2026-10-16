"""FDE From Scratch — stage 11: From a vague ask to a scoped four weeks.

The solution: a transcript of statements in, a plan out, and the gaps in the
transcript reported rather than smoothed over. Every statement is validated
once, the requirements are numbered in statement order, priority is read from
the words the customer chose and never from the seat they sit in, `schedule`
fills the weeks it was given and no more, and `sow` renders one plan one way.

Nothing here touches the world: the plan is a function of the transcript alone,
which is why the check can run a whole scoping with the customer's estate open
and find its log untouched.
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

# The kinds that ask for work; an objection is context and a scope-out is exile.
_REQUIREMENT_KINDS = ("ask", "constraint", "metric")


class ScopeError(estate.EstateError):
    """A statement, a transcript or a plan this course cannot read, named field by field."""


def _words(text):
    """The lowercase word runs of `text`, in order, punctuation dropped."""
    words = []
    run = []
    for char in text:
        if char.isalnum():
            run.append(char)
        elif run:
            words.append("".join(run).lower())
            run = []
    if run:
        words.append("".join(run).lower())
    return tuple(words)


def _count(value, what):
    """A count of something: an int of at least zero, and not a `bool`."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ScopeError("%s is a count of at least zero, and it is %r" % (what, value))
    return value


def _count_or_none(value, what):
    """A count, or `None` for a number the customer has never measured."""
    if value is None:
        return None
    return _count(value, what)


def _mapping(value, what):
    """`value` as a mapping, or the shape mismatch that names it."""
    if not isinstance(value, dict):
        raise ScopeError("%s is a mapping, and it is %r" % (what, value))
    return value


def _keys(mapping, keys, what):
    """Every key of `keys` present in `mapping`, or the first one that is missing."""
    for key in keys:
        if key not in mapping:
            raise ScopeError("%s carries %r, and it has no %r" % (what, keys, key))
    return mapping


def _name(value, what):
    """A non-empty string, or the shape mismatch that names what arrived."""
    if not isinstance(value, str) or not value:
        raise ScopeError("%s is a non-empty string, and it is %r" % (what, value))
    return value


def _metric_record(value, what):
    """A `METRIC_KEYS` record, validated; `None` is a statement with no metric.

    A `baseline` of `None` is the customer saying nobody ever measured it: a
    fact about their record, and the only thing that earns `metric-no-baseline`.
    """
    if value is None:
        return None
    _keys(_mapping(value, what), METRIC_KEYS, what)
    _name(value["name"], "%s's name" % (what,))
    if value["unit"] not in UNITS:
        raise ScopeError("%s's unit is one of %r, and it is %r"
                         % (what, UNITS, value["unit"]))
    _count_or_none(value["baseline"], "%s's baseline" % (what,))
    _count_or_none(value["target"], "%s's target" % (what,))
    return {"name": value["name"], "baseline": value["baseline"],
            "target": value["target"], "unit": value["unit"]}


def _metric_name(value, what):
    """The metric an ask or a constraint is judged by: its name, or `None`.

    An ask names the metric it will be judged by; it does not carry a baseline,
    because a baseline belongs to the customer's record and not to the sentence
    somebody said in a meeting.
    """
    if value is None:
        return None
    return _name(value, what)


def _checked(statement, index):
    """One statement, validated: every `STATEMENT_KEYS` field, and the type it is.

    `speaker` may be `None` or empty — the transcript did not record who said it
    — and that is a gap the plan reports, not a shape this course invents an
    owner for. Everything else has to be the thing it claims to be.
    """
    what = "statement %d" % (index + 1,)
    _keys(_mapping(statement, what), STATEMENT_KEYS, what)
    for key in ("role", "kind", "text"):
        if not isinstance(statement[key], str):
            raise ScopeError("%s's %s is a string, and it is %r"
                             % (what, key, statement[key]))
    speaker = statement["speaker"]
    if speaker is not None and not isinstance(speaker, str):
        raise ScopeError("%s's speaker is a name or None, and it is %r"
                         % (what, speaker))
    _count_or_none(statement["amount_cents"], "%s's amount_cents" % (what,))
    if statement["kind"] == "metric":
        _metric_record(statement["metric"], "%s's metric" % (what,))
    elif statement["kind"] in _REQUIREMENT_KINDS:
        _metric_name(statement["metric"], "%s's metric" % (what,))
    return statement


def _statements(transcript):
    """The transcript's statements, validated, in the order they were said."""
    if not isinstance(transcript, (tuple, list)):
        raise ScopeError("a transcript is a tuple of statements, and it is %r"
                         % (transcript,))
    return tuple(_checked(statement, index)
                 for index, statement in enumerate(transcript))


def _priority(text):
    """`must`, `should` or `could`: the customer's own words, and nothing else.

    The emphasis is the word the customer chose — "must" anywhere in the
    sentence outranks a "should" that came first, and the case does not matter —
    and the seat the speaker sits in is never an emphasis at all.
    """
    lowered = text.lower()
    if "must" in lowered:
        return "must"
    if "should" in lowered:
        return "should"
    return "could"


def _requirement_records(requirements):
    """The requirement records of `requirements`, validated."""
    if not isinstance(requirements, (tuple, list)):
        raise ScopeError("requirements is a tuple of records, and it is %r"
                         % (requirements,))
    found = []
    for index, record in enumerate(requirements):
        what = "requirement %d" % (index + 1,)
        _keys(_mapping(record, what), REQUIREMENT_KEYS, what)
        _name(record["id"], "%s's id" % (what,))
        if not isinstance(record["kind"], str):
            raise ScopeError("%s's kind is a string, and it is %r"
                             % (what, record["kind"]))
        owner = record["owner"]
        if owner is not None and not isinstance(owner, str):
            raise ScopeError("%s's owner is a name or None, and it is %r"
                             % (what, owner))
        found.append(record)
    return tuple(found)


def _weeks(weeks):
    """A number of weeks this plan may be built for: a positive int."""
    if isinstance(weeks, bool) or not isinstance(weeks, int) or weeks < 1:
        raise ScopeError("weeks is a positive number of weeks, and it is %r"
                         % (weeks,))
    return weeks


def _stream_records(workstreams):
    """The `(owner, ids)` pairs of `workstreams`, validated."""
    if not isinstance(workstreams, (tuple, list)):
        raise ScopeError("workstreams is a tuple of (owner, ids) pairs, and it is %r"
                         % (workstreams,))
    found = []
    for index, entry in enumerate(workstreams):
        what = "workstream %d" % (index + 1,)
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            raise ScopeError("%s is an (owner, ids) pair, and it is %r"
                             % (what, entry))
        owner, ids = entry
        _name(owner, "%s's owner" % (what,))
        if not isinstance(ids, (tuple, list)):
            raise ScopeError("%s's ids are a tuple of requirement ids, and it is %r"
                             % (what, ids))
        for identifier in ids:
            _name(identifier, "%s's id" % (what,))
        found.append((owner, tuple(ids)))
    return tuple(found)


def _ordered(problems):
    """`(problem, offender)` pairs, one each, in `SCOPE_PROBLEMS` order.

    Deduplicated because a gap the customer stated twice is one gap, and sorted
    by the offender inside a problem, so two transcripts that said the same
    things in two orders still produce one plan's worth of problems.
    """
    return tuple(sorted(set(problems),
                        key=lambda pair: (SCOPE_PROBLEMS.index(pair[0]), pair[1])))


def _metric_line(metric):
    """One metric as the SOW states it: what it is now, and what it is for."""
    baseline = ("no baseline" if metric["baseline"] is None
                else "baseline %d" % (metric["baseline"],))
    target = ("no target" if metric["target"] is None
              else "target %d" % (metric["target"],))
    return "  %s (%s): %s, %s" % (metric["name"], metric["unit"], baseline,
                                  target)


def _plan_record(plan):
    """A plan carrying `PLAN_KEYS`, validated as far as `sow` reads it."""
    _keys(_mapping(plan, "a plan"), PLAN_KEYS, "a plan")
    _requirement_records(plan["requirements"])
    for index, pair in enumerate(plan["problems"]):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ScopeError("problem %d is a (problem, offender) pair, and it is %r"
                             % (index + 1, pair))
    for metric in plan["metrics"]:
        _metric_record(metric, "a metric")
    for text in plan["out_of_scope"]:
        _name(text, "an out-of-scope statement")
    return plan


def _numbered(statements):
    """Every statement with the id of the requirement it becomes, or `None`.

    The numbering counts the requirements and not the statements, so an
    objection in the middle consumes no id, and a metric statement keeps the id
    its own place in the transcript earned it.
    """
    numbered = []
    number = 0
    for index, statement in enumerate(statements):
        if statement["kind"] in _REQUIREMENT_KINDS:
            number += 1
            numbered.append((index, "req-%02d" % (number,), statement))
        else:
            numbered.append((index, None, statement))
    return tuple(numbered)


def _requirement_record(identifier, statement, index):
    """The `REQUIREMENT_KEYS` record one requirement statement becomes."""
    kind = statement["kind"]
    what = "statement %d's metric" % (index + 1,)
    if kind == "metric":
        metric = _metric_record(statement["metric"], what)
        name = metric["name"] if metric is not None else None
    else:
        name = _metric_name(statement["metric"], what)
    speaker = statement["speaker"]
    return {"id": identifier, "text": statement["text"], "kind": kind,
            "owner": speaker if speaker else None,
            "priority": _priority(statement["text"]), "metric": name}


def requirements(transcript):
    """The requirements of `transcript`, `req-01`, `req-02`… in statement order.

    A requirement is a statement whose `kind` is an ask, a constraint or a
    metric; an objection is context and a scope-out is exile. The owner is the
    speaker who asked — and `None` when the transcript did not record one,
    because the one owner that would mean nothing is this stage's own author.
    The priority comes from the statement's own words.
    """
    return tuple(_requirement_record(identifier, statement, index)
                 for index, identifier, statement
                 in _numbered(_statements(transcript))
                 if identifier is not None)


def workstreams(requirements):
    """The requirements grouped by owner: `(owner, (ids))`, sorted by owner.

    A requirement with no owner is in no workstream: an owner is what a
    workstream is, and inventing one to fill the tuple would hide exactly the
    gap `no-owner` exists to report. The ids inside a stream are sorted, so the
    order a caller happened to hand the requirements in is not an answer.
    """
    groups = {}
    for record in _requirement_records(requirements):
        owner = record["owner"]
        if owner is None:
            continue
        groups.setdefault(owner, []).append(record["id"])
    return tuple((owner, tuple(sorted(ids)))
                 for owner, ids in sorted(groups.items()))


def schedule(workstreams, weeks):
    """`weeks` weeks of at most `WEEK_CAPACITY` requirements, in fill order.

    Every `(id, owner)` pair of the workstreams is laid out in id order and cut
    into weeks of `WEEK_CAPACITY`; each week answers the owners that fill it, in
    the order they fill it, and a week with nothing left to fill is an empty
    tuple. The answer is always `weeks` long: work the weeks do not hold is not
    squeezed in, it is the plan's `out-of-capacity` to report.
    """
    count = _weeks(weeks)
    pairs = sorted((identifier, owner)
                   for owner, ids in _stream_records(workstreams)
                   for identifier in ids)
    built = []
    for index in range(count):
        start = index * WEEK_CAPACITY
        chunk = pairs[start:start + WEEK_CAPACITY]
        built.append(tuple(owner for _identifier, owner in chunk))
    return tuple(built)


def metrics(transcript):
    """The metrics the customer already tracks, in `METRIC_KEYS` order.

    A metric is a `METRIC_KEYS` record and it comes from a statement whose kind
    is `metric` — a statement *about* a measure. A metric an ask is judged by
    rides in that ask's requirement as a name and is not echoed here.
    """
    found = []
    for index, _identifier, statement in _numbered(_statements(transcript)):
        if statement["kind"] != "metric":
            continue
        metric = _metric_record(statement["metric"],
                                "statement %d's metric" % (index + 1,))
        if metric is not None:
            found.append(metric)
    return tuple(found)


def scope(transcript, customer, weeks):
    """The plan: `PLAN_KEYS`, with every gap in the transcript named.

    A requirement that has no owner, no metric or too few words to be anything
    stays in `requirements` *and* appears in `problems` — a plan that reports a
    gap and then quietly drops the requirement is smaller than the ask, which is
    the one thing a scoping document may never be. `out-of-capacity` counts the
    must-haves against `weeks * WEEK_CAPACITY`: a `should` or a `could` the weeks
    do not hold is a backlog, while a commitment the weeks do not hold is a
    promise this scoping cannot keep.
    """
    customer = _name(customer, "the customer's name")
    count = _weeks(weeks)
    statements = _statements(transcript)
    records = requirements(statements)
    found = metrics(statements)
    out_of_scope = tuple(statement["text"] for statement in statements
                         if statement["kind"] == "scope-out")
    problems = []
    for index, identifier, statement in _numbered(statements):
        kind = statement["kind"]
        if identifier is None:
            if kind not in KINDS:
                problems.append(("unknown-kind", kind))
        elif kind == "metric":
            metric = _metric_record(statement["metric"],
                                    "statement %d's metric" % (index + 1,))
            if metric is not None and metric["baseline"] is None:
                problems.append(("metric-no-baseline", identifier))
    for record in records:
        if record["owner"] is None:
            problems.append(("no-owner", record["id"]))
        if record["metric"] is None:
            problems.append(("no-metric", record["id"]))
        if len(_words(record["text"])) < MIN_WORDS:
            problems.append(("vague", record["id"]))
        if record["text"] in out_of_scope:
            problems.append(("scope-out-as-requirement", record["id"]))
    slots = count * WEEK_CAPACITY
    musts = len([record for record in records if record["priority"] == "must"])
    if musts > slots:
        problems.append(("out-of-capacity",
                         "%d must-haves in %d slots" % (musts, slots)))
    groups = workstreams(records)
    return {
        "customer": customer,
        "requirements": records,
        "problems": _ordered(problems),
        "workstreams": groups,
        "weeks": schedule(groups, count),
        "metrics": found,
        "out_of_scope": out_of_scope,
        "metrics_without_baseline": tuple(metric["name"] for metric in found
                                          if metric["baseline"] is None),
    }


def sow(plan):
    """`plan` as the text the customer is asked to sign: one plan, one string.

    Every section is rendered from the plan's own tuples in their own order, an
    empty section says so rather than vanishing, and a requirement whose owner
    the transcript never recorded reads `unowned` — never a name this course
    supplied, because the point of the section is what the customer still owes.
    """
    _plan_record(plan)
    weeks = len(plan["weeks"])
    lines = ["SOW — %s: %d week%s, %d per week"
             % (plan["customer"], weeks, "" if weeks == 1 else "s",
                WEEK_CAPACITY)]
    lines.append("requirements:")
    if plan["requirements"]:
        for record in plan["requirements"]:
            lines.append("  %s [%s] %s — %s (metric: %s)"
                         % (record["id"], record["priority"],
                            record["owner"] if record["owner"] else "unowned",
                            record["text"],
                            record["metric"] if record["metric"] else "none"))
    else:
        lines.append("  none")
    lines.append("gaps:")
    if plan["problems"]:
        for problem, offender in plan["problems"]:
            lines.append("  %s: %s" % (problem, offender))
    else:
        lines.append("  none")
    lines.append("metrics:")
    if plan["metrics"]:
        for metric in plan["metrics"]:
            lines.append(_metric_line(metric))
    else:
        lines.append("  none")
    lines.append("out of scope:")
    if plan["out_of_scope"]:
        for text in plan["out_of_scope"]:
            lines.append("  - %s" % (text,))
    else:
        lines.append("  none")
    return "\n".join(lines) + "\n"
