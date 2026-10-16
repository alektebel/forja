"""MQTT Broker From Scratch — stage 9: Grants, denials, and the line written before the act.

See `stage_09.py` for the surface and the design decisions; this is the policy
that answers "may this client do this here", and the ledger that writes the line
before the act.

Two things the reader needs before the bodies. The world's names are imported
directly — `Grants`, `GrantsError`, `DECISION_KEYS`, `ALLOWED`, `REASONS`,
`line` — because the contract's own signature gives the name `grants` to the
*table*: `allowed_publish(grants, client_id, topic)` and
`decide(grants, client_id, action, topic, tick)`. So inside these functions
`grants` is the table, and this file never needs the module as a module. And
everything this stage refuses rather than answers is a `GrantsError`: the table
is the world's, so one exception family covers the whole of the policy.
"""

import stage_03

from grants import (ACTIONS, ALLOWED, DECISION_KEYS, Grants, GrantsError,
                    REASONS, line)


def _table(policy):
    """`policy` as a `Grants` table, or a refusal naming what arrived."""
    if not isinstance(policy, Grants):
        raise GrantsError("a policy must be a grants.Grants table, not %s"
                          % (type(policy).__name__,))
    return policy


def _tick(tick):
    """The tick a decision is written at: a count of zero or more, never a bool."""
    if isinstance(tick, bool) or not isinstance(tick, int):
        raise GrantsError("a tick must be an int, not %s (%r)"
                          % (type(tick).__name__, tick))
    if tick < 0:
        raise GrantsError("the tick of a decision is zero or more, not %d"
                          % (tick,))
    return tick


def _malformed(patterns):
    """The first of `patterns` that could never be a filter, or None.

    The world's table holds strings and not filters: an operator may write
    `a/#/b` and the table will take it, because whether it can be matched at all
    is stage 3's judgment. A pattern that fails it is a fact about the table
    rather than a mistake of the client's, which is why it is a reason code and
    not an exception — and why only the patterns actually consulted are judged:
    another client's unreadable pattern is not this client's problem.
    """
    for pattern in patterns:
        try:
            stage_03.validate_filter(pattern)
        except stage_03.TopicError:
            return pattern
    return None


def _reaches_level(pattern_level, name_level):
    """Whether one level of a grant reaches one level of a request."""
    if pattern_level == "#":
        return True
    if pattern_level == "+":
        return name_level != "#"
    return name_level == pattern_level


def _covers(pattern, name):
    """Whether the grant `pattern` reaches everything the request `name` reaches.

    Component by component, through stage 3's own split, and never by comparing
    the two strings: `a/b` does not reach `a/bc`, `+` is exactly one level (`a/+`
    reaches `a/`, and neither `a` nor `a/x/y`), and `#` reaches its own level and
    everything under it (`a/#` reaches `a`). A grant whose first level is a
    wildcard never reaches a `$` topic, which is the rule stage 3's matcher keeps
    and the reason a grant of `#` is not a grant of the broker's own tree.
    """
    reached = stage_03.levels(pattern)
    wanted = stage_03.levels(name)
    if stage_03.is_wildcard(reached[0]) and wanted[0].startswith("$"):
        return False
    if "#" in reached:
        reached = reached[:-1]
        if len(wanted) < len(reached):
            return False
    elif len(wanted) != len(reached):
        return False
    for index, level in enumerate(reached):
        if not _reaches_level(level, wanted[index]):
            return False
    return True


def _reaches(patterns, name):
    """Whether any of `patterns` reaches the request `name`."""
    for pattern in patterns:
        if _covers(pattern, name):
            return True
    return False


def _reason(action, name):
    """Why `name` cannot be a request at all, or None.

    The empty name has its own reason. A publish topic holding a wildcard level
    is `wildcard`, because a wildcard is a subscription's business and no grant
    could make it publishable; a filter holding one is legal, so for a subscribe
    request the wildcard goes through `validate_filter` like everything else.
    Whatever stage 3 refuses — a `#` that is not last, a wildcard glued to text,
    a name above the maximum — is `malformed`: the request is not the kind of
    name it claims to be.
    """
    if not name:
        return "empty"
    wild = any(stage_03.is_wildcard(level) for level in stage_03.levels(name))
    if action == "publish":
        if wild:
            return "wildcard"
        try:
            stage_03.validate_topic(name)
        except stage_03.TopicError:
            return "malformed"
        return None
    try:
        stage_03.validate_filter(name)
    except stage_03.TopicError:
        return "malformed"
    return None


def _verdict(policy, client_id, action, name):
    """`(allowed, reason)` for one request, from the table and the ceiling both.

    The order is the whole design: the request's own shape first, then the
    table's readability, then the client's grant, then the ceiling — so a client
    with no grant is told it has none, and only a client whose own grant reaches
    is ever told about the broker's ceiling. What the client may do is what its
    grant reaches *and* what the ceiling still affords.
    """
    policy = _table(policy)
    if not isinstance(name, str):
        raise GrantsError("a %s must name a topic as a str, not %s"
                          % (action, type(name).__name__,))
    reason = _reason(action, name)
    if reason is not None:
        return False, reason
    own = policy.client(client_id)[action]
    ceiling = policy.ceiling()[action]
    if _malformed(own) or _malformed(ceiling):
        return False, "malformed"
    if not _reaches(own, name):
        return False, "no-grant"
    if not _reaches(ceiling, name):
        return False, "ceiling"
    return True, ALLOWED


def allowed_publish(grants, client_id, topic):
    """Whether `client_id` may publish to `topic`, as `(allowed, reason)`.

    `grants` is the world's `Grants` table — the client's own patterns for
    publishing, and the broker's ceiling. `topic` is the topic the client wants
    to publish to, as the wire would carry it. The answer is a value and not an
    exception, because this is a question about content: `(True, "allowed")`, or
    `(False, reason)` with one of the reasons the world names.
    """
    return _verdict(grants, client_id, "publish", topic)


def allowed_subscribe(grants, client_id, filter):
    """Whether `client_id` may subscribe to `filter`, as `(allowed, reason)`.

    The request is a filter, so `+` and `#` are legal in it — and a grant only
    covers it when every topic it could match is one the grant reaches, which is
    why `a/+` never covers the request `a/#`.
    """
    return _verdict(grants, client_id, "subscribe", filter)


def decide(grants, client_id, action, topic, tick):
    """One request as the decision the line is written from, at `tick`.

    The decision is a dict whose keys are `DECISION_KEYS`, in that order: `tick`,
    `client`, `action`, `topic`, `allowed`, `reason`. An action outside the
    world's two, a tick that is not a count, a client that is not a name and a
    table that is not a table all raise, naming what arrived; a request that is
    merely not allowed is a decision like any other.
    """
    if action not in ACTIONS:
        raise GrantsError("%r is not an action: the actions are %r"
                          % (action, ACTIONS))
    _tick(tick)
    allowed, reason = _verdict(grants, client_id, action, topic)
    return {"tick": tick, "client": client_id, "action": action, "topic": topic,
            "allowed": allowed, "reason": reason}


class Ledger:
    """Every decision this broker made, and the line each one was written as.

    A ledger starts empty, and only `before` adds to it: the line is written
    first and answered, so an act that happened without a line is impossible and
    a line that no act followed is visible. The ledger holds the decisions and
    writes their lines again on demand, which is what keeps a line from drifting
    away from the decision it belongs to.
    """

    def __init__(self):
        """A ledger with no lines in it yet."""
        self._decisions = []

    def before(self, decision):
        """Write `decision`'s line, hold it, and answer it — before the act.

        `decision` is refused exactly as the world's `line` refuses it, and a
        decision that was refused leaves no line behind. A copy of the decision
        is what is held, so what the caller does to its own dict afterwards
        cannot rewrite the evidence.
        """
        text = line(decision)
        self._decisions.append(dict(decision))
        return text

    def lines(self):
        """The lines written, in the order they were written."""
        return tuple(line(decision) for decision in self._decisions)

    def denials(self):
        """The decisions that refused, in the order they were written."""
        return tuple(decision for decision in self._decisions
                     if not decision["allowed"])

    def allowed(self):
        """The decisions that allowed, in the order they were written."""
        return tuple(decision for decision in self._decisions
                     if decision["allowed"])

    def report(self):
        """The lines counted by outcome and by reason, from the lines themselves.

        The four keys are `lines`, `allowed`, `denied` and `by-reason`; the last
        is a count for every reason the world names, in the world's order, so two
        reports of two different runs have the same shape.
        """
        allowed = len(self.allowed())
        by_reason = {reason: 0 for reason in REASONS}
        for decision in self._decisions:
            by_reason[decision["reason"]] += 1
        return {"lines": len(self._decisions), "allowed": allowed,
                "denied": len(self.denials()), "by-reason": by_reason}
