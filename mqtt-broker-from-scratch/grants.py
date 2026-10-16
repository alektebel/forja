"""MQTT Broker From Scratch — the grants.

Who may say what, as data. A broker's access control is configuration: a client's
patterns for publishing and for subscribing, and the broker's own ceiling — the
widest any client may reach. This module holds that table, its refusal
vocabulary, and the exact shape of the decision line; it holds no opinion about
matching, intersection or when a line is written, because that is the course's
job (stage 9) and the reason the policy is not the world's.

DESIGN DECISION — why is the ceiling separate from the clients' grants?
Because the two are intersected rather than unioned, and a table that cannot
express the difference makes that bug unwritable — which sounds like a kindness
and is the opposite. With the ceiling beside the clients, a broker that widens
one client's power while narrowing the other's has to say so in code, and the
check can hold it to the intersection: what a client may do is what its own
grants allow *and* what the ceiling still affords, never the sum.

DESIGN DECISION — why is the refusal vocabulary closed here rather than decided
by the course?
Because a report whose reasons are free text cannot be counted, and this course's
whole method is counting. `REASONS` is the whole of what a denial may say — the
client has no grant, the ceiling does not reach that far, the topic cannot be
published to at all, or the pattern was not a pattern — and a decision whose
reason is outside it is not a decision the report can hold. A broker that invents
a friendlier word for "denied" is a broker whose audit nobody can grep.

DESIGN DECISION — why is the decision line's shape fixed here, and written before
the act?
Because a line written afterwards can always be made to agree with what happened,
which makes it worthless as evidence. The shape is fixed — six fields, in order,
one line — so that two decisions of the same kind compare equal, and the
ordering rule (the line first, then the act it allows) is what makes a line that
is missing the *interesting* event: the act never happened. This is the
discipline `sandbox-capabilities-from-scratch` keeps for an agent's tools,
applied to a protocol instead of a filesystem.
"""

ACTIONS = ("publish", "subscribe")

ALLOWED = "allowed"

REASONS = (ALLOWED, "no-grant", "ceiling", "wildcard", "empty", "malformed")

DECISION_KEYS = ("tick", "client", "action", "topic", "allowed", "reason")


class GrantsError(ValueError):
    """A grant table this module refuses to build, named as what is wrong."""


def _patterns(value, what):
    """A tuple of non-empty pattern strings, or a refusal naming what arrived."""
    if isinstance(value, (str, bytes)) or not hasattr(value, "__iter__"):
        raise GrantsError("%s must be a sequence of patterns, not %s"
                          % (what, type(value).__name__))
    patterns = tuple(value)
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern:
            raise GrantsError("%s holds %r, and a pattern is a non-empty string"
                              % (what, pattern))
    return patterns


class Grants:
    """The whole policy: what each client may do, and the ceiling over all of them.

    Public methods: `client(client_id)` answers that client's grants — an unknown
    client has none, which is a fact and not an error — and `ceiling()` answers
    the widest reach any client may have. Both hand back copies, so a caller that
    edits what it was given changes nothing here.
    """

    def __init__(self, table=None, ceiling=None):
        table = dict(table or {})
        self._table = {}
        for client_id, grants in table.items():
            if not isinstance(client_id, str) or not client_id:
                raise GrantsError("a client's name is a non-empty string, not %r"
                                  % (client_id,))
            self._table[client_id] = self._actions(grants, "the grants of %r"
                                                   % (client_id,))
        self._ceiling = self._actions(ceiling or {}, "the ceiling")

    def _actions(self, grants, what):
        if not isinstance(grants, dict):
            raise GrantsError("%s must be a dict of actions, not %s"
                              % (what, type(grants).__name__))
        for action in grants:
            if action not in ACTIONS:
                raise GrantsError("%s names %r, and the actions are %r"
                                  % (what, action, ACTIONS))
        return {action: _patterns(grants.get(action, ()), "%s: %s" % (what, action))
                for action in ACTIONS}

    def client(self, client_id):
        """One client's grants as `{"publish": (...), "subscribe": (...)}`."""
        if not isinstance(client_id, str):
            raise GrantsError("a client's name must be a str, not %s"
                              % (type(client_id).__name__,))
        grants = self._table.get(client_id)
        if grants is None:
            return {action: () for action in ACTIONS}
        return {action: tuple(grants[action]) for action in ACTIONS}

    def ceiling(self):
        """The widest reach any client may have, in the same shape."""
        return {action: tuple(self._ceiling[action]) for action in ACTIONS}

    def clients(self):
        """Every client the table names, in the order it was given."""
        return tuple(self._table)


def line(decision):
    """One decision as the fixed six-field line, or a refusal naming what is missing.

    The fields are `DECISION_KEYS`, in that order, joined by single spaces as
    `key=value` pairs: a line a reader can cut, count and compare without parsing
    it, and which two runs of one scenario must produce byte-identically.
    """
    if not isinstance(decision, dict):
        raise GrantsError("a decision must be a dict, not %s"
                          % (type(decision).__name__,))
    for key in DECISION_KEYS:
        if key not in decision:
            raise GrantsError("a decision with no %r in it (the keys are %r)"
                              % (key, DECISION_KEYS))
    allowed = decision["allowed"]
    if not isinstance(allowed, bool):
        raise GrantsError("a decision's allowed is True or False, not %r"
                          % (allowed,))
    reason = decision["reason"]
    if reason not in REASONS:
        raise GrantsError("a decision's reason is one of %r, not %r"
                          % (REASONS, reason))
    if allowed and reason != ALLOWED:
        raise GrantsError("a decision that allows its act says %r, not %r"
                          % (ALLOWED, reason))
    if not allowed and reason == ALLOWED:
        raise GrantsError("a denial may not say %r: the reasons for refusing are "
                          "%r" % (ALLOWED, REASONS[1:]))
    return " ".join("%s=%s" % (key, decision[key]) for key in DECISION_KEYS)
