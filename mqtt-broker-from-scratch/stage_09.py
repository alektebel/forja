"""MQTT Broker From Scratch — stage 9: Grants, denials, and the line written before the act.

Every stage so far has read or written bytes. This one reads none, and that is
the point of it. What a client may publish and what it may subscribe to is not on
the wire: it is a table an operator wrote, and the wire hears almost nothing
about it. MQTT has no packet for "your PUBLISH was refused" — a broker that drops
it says nothing at all, and the client is free to believe it was delivered — and
the one thing a broker can say is a SUBACK whose code is the failure, which is
why a denial has to be a decision this broker wrote down rather than a packet it
sent.

So the decision is a line. It carries who asked, for what, when, and what the
answer was, in the fixed shape of the world's `DECISION_KEYS`: two decisions of
the same kind are then the same string, an audit can be counted without being
parsed, and a run can be compared with the run before it. Its reason comes from a
closed vocabulary — there are six words a refusal may use and no seventh — and
the line is written *before* the act it allows, which turns the interesting event
into a line with no act after it, and makes an act with no line impossible.

The judgment itself reads two tables together. The first is the client's own
grants, one list of patterns for publishing and one for subscribing, and the
request is matched against them by *components*: stage 3's matcher, never
`startswith`, so `a/b` does not reach `a/bc`, `+` is exactly one level, and `#` is
its own level and everything under it. The second is the broker's ceiling — the
widest reach any client may have — and it is not advice: a grant narrows the
ceiling and never widens it, so what a client may do is the intersection of the
two. A topic its grant reaches but the ceiling does not is refused, and so is one
the ceiling reaches and its grant does not.

    DECISION_KEYS                                  the six fields of a decision, in line order
    allowed_publish(grants, client_id, topic)      -> (allowed, reason)
    allowed_subscribe(grants, client_id, filter)   -> (allowed, reason)
    decide(grants, client_id, action, topic, tick) -> the decision the line is written from
    Ledger.before(decision)                        -> the line, written before the act it allows
    Ledger.lines()                                 -> the lines written, in order
    Ledger.denials()                               -> the decision dicts that refused
    Ledger.allowed()                               -> the decision dicts that allowed
    Ledger.report()                                -> {"lines", "allowed", "denied", "by-reason"}

The six reasons are the world's and not this stage's: `allowed`, `no-grant` (this
client has no grant that reaches here), `ceiling` (its grant does, and the
broker's own reach ends sooner), `wildcard` and `empty` (the request cannot be a
topic at all, and stage 3's `validate_topic` is the judge), and `malformed` (a
pattern in the table is not a filter, and `validate_filter` is the judge). What
this stage refuses instead of answering is a `grants.GrantsError`: a table that
is not a table, an action that is not an action, a tick that is not a tick. Note
that the table is handed in a parameter named `grants` — the contract's own
signature — so inside these functions that name is the table and not the module.

DESIGN DECISION — why is a client's power the intersection of its grants and the
broker's ceiling, rather than their union?
Because a policy that can only add is a policy with no top. The two tables answer
different questions — "may this client do this" and "may anyone do this here" —
and the safe reading of two walls is that you must fit through both. Unioned,
a single careless grant (`#` for one client, say) silently overrides the
ceiling for that client, and the ceiling stops being a ceiling exactly where it
was needed. Intersected, a grant can only take reach away, which is what makes a
narrow grant a safe thing to hand out and makes the ceiling worth writing down.

DESIGN DECISION — why is the client's own grant judged before the ceiling, and
the request's shape before both?
Because the reason a client is given should be the smallest true one. A client
whose grant does not reach the topic has no grant for it, whatever the ceiling
says, and telling it about the broker's ceiling would be answering a question it
did not ask. A request that could not be a topic in the first place — a wildcard,
an empty name — is refused before either table is consulted, because no grant
could make it legal. And a pattern in the table that could never be a filter is
judged before both, because a table nobody can read grants nothing.

DESIGN DECISION — why is a denial a returned verdict with a reason code, while a
table that is not a table raises?
Because one is content and the other is a shape. "May this client publish here"
is a question about the world, and this course answers questions with values —
the pair `(allowed, reason)`, or a decision dict — so a refusal never escapes as
an exception a caller might not expect to catch. A `Grants` table handed a
non-table, an action outside the two this protocol has, a tick that is not a
count: those are callers breaking the interface, and they raise, naming what
arrived. The reason itself is never free text, because the report counts by
reason and a seventh word would be a count nobody can compare.

DESIGN DECISION — why does the ledger write the line before the act, and hold the
decision rather than the text?
Because a line written afterwards can always be made to agree with what happened,
and then it is not evidence. `before` computes the line first — a decision the
world's `line` refuses is not recorded at all — and answers it, so at the moment
the caller performs the act the line is already on the ledger. The ledger holds a
copy of the decision and writes the line again on demand, so what a caller does
to its own dict afterwards cannot rewrite what was written: the line is the
evidence, and evidence that can be edited from outside is a diary.

DESIGN DECISION — why does a grant of `#` not reach a `$SYS/…` topic?
Because a grant is judged by stage 3's matcher, and that matcher keeps MQTT's
`$` rule: a filter whose first level is a wildcard does not reach a topic whose
first level begins with `$`. The rule exists so that a wildcard subscription does
not silently swallow the broker's own housekeeping tree, and a grant is a
subscription-shaped thing: a client granted `#` that could publish into
`$SYS/broker/uptime` would be able to forge the broker's own reports. A grant of
`$SYS/#` still reaches it, because that literal first level is not a wildcard —
the rule is about the wildcard, not about the dollar.

TODO: implement `allowed_publish`, `allowed_subscribe`, `decide` and `Ledger` in
this file: the matcher's components through stage 3, the intersection with the
ceiling, the six reason codes, and the line written before the act.
"""

import stage_03

from grants import DECISION_KEYS


def allowed_publish(grants, client_id, topic):
    """Whether `client_id` may publish to `topic`, as `(allowed, reason)`.

    `grants` is the world's `Grants` table — the client's own patterns for
    publishing, and the broker's ceiling. `topic` is the topic the client wants
    to publish to, as the wire would carry it. The answer is a value and not an
    exception, because this is a question about content: `(True, "allowed")`, or
    `(False, reason)` with one of the reasons the world names.
    """
    raise NotImplementedError("stage 9: implement allowed_publish()")


def allowed_subscribe(grants, client_id, filter):
    """Whether `client_id` may subscribe to `filter`, as `(allowed, reason)`.

    The request is a filter, so `+` and `#` are legal in it — and a grant only
    covers it when every topic it could match is one the grant reaches, which is
    why `a/+` never covers the request `a/#`.
    """
    raise NotImplementedError("stage 9: implement allowed_subscribe()")


def decide(grants, client_id, action, topic, tick):
    """One request as the decision the line is written from, at `tick`.

    The decision is a dict whose keys are `DECISION_KEYS`, in that order: `tick`,
    `client`, `action`, `topic`, `allowed`, `reason`. It is what `Ledger.before`
    is handed, so the two answers a decision can carry — the verdict and the
    line — are the same fact written twice.
    """
    raise NotImplementedError("stage 9: implement decide()")


class Ledger:
    """Every decision this broker made, and the line each one was written as.

    A ledger starts empty, and only `before` adds to it: the line is written
    first and answered, so an act that happened without a line is impossible and
    a line that no act followed is visible. `lines`, `denials`, `allowed` and
    `report` all read the same decisions back.
    """

    def __init__(self):
        """A ledger with no lines in it yet."""
        raise NotImplementedError("stage 9: implement Ledger.__init__()")

    def before(self, decision):
        """Write `decision`'s line, hold it, and answer it — before the act.

        `decision` is refused exactly as the world's `line` refuses it, and a
        decision that was refused leaves no line behind.
        """
        raise NotImplementedError("stage 9: implement Ledger.before()")

    def lines(self):
        """The lines written, in the order they were written."""
        raise NotImplementedError("stage 9: implement Ledger.lines()")

    def denials(self):
        """The decisions that refused, in the order they were written."""
        raise NotImplementedError("stage 9: implement Ledger.denials()")

    def allowed(self):
        """The decisions that allowed, in the order they were written."""
        raise NotImplementedError("stage 9: implement Ledger.allowed()")

    def report(self):
        """The lines counted by outcome and by reason, from the lines themselves.

        The four keys are `lines`, `allowed`, `denied` and `by-reason`; the last
        is a count for every reason the world names, in the world's order, so two
        reports of two different runs have the same shape.
        """
        raise NotImplementedError("stage 9: implement Ledger.report()")
