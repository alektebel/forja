"""FDE From Scratch — stage 1: The assertion, the session and the row.

Twelve stages of an enterprise AI deployment, and this one is the rung the other
eleven stand on: before anything can be retrieved, deployed, redacted or handed
over, two questions have to have an answer that is enforced by the system rather
than remembered by whoever wrote the prompt. *Who is asking?* and *which rows
may they see?* The customer's directory will tell you who somebody is — it signs
assertions, it holds groups and it will deactivate a subject the day they leave —
but it will not tell you what those facts mean here. Meaning is the course's, and
this stage is where the course decides it.

An assertion is a claim set with a signature over it, and `IdP.verify` is the
only thing in the world that says the signature holds. Everything downstream of
that verdict is this stage's: the claims become a `PRINCIPAL_KEYS` record whose
`roles` come from the groups the claim set names, whose `rights` come from a
table that maps a role to the rights it carries, and whose `clearance` is the
highest of the roles' own. A principal is a dict, because it is passed to every
later stage as data and never as an object with behaviour of its own.

A session is the other half of the same question, and it is deliberately *not* a
place the directory knows about. The customer's identity provider has no idea who
is currently holding a session, so the course holds them: a subject, the
principal they were verified as, the audience they were verified for, and two
ticks. A session outlives nothing that a tick cannot end, and the one act that
closes one is the one the directory performs — a deactivation.

The last half of the stage is the row. The customer's store answers `Estate.query`
with everything under the shape you asked for, across both tenants and every
classification: it is the unfiltered fetch, and the reason `row_visible` exists at
all. A row is visible on its tenant **and** on its clearance, the tenant is asked
first, and a refusal names which of the two it was rather than answering `False`
to a question an auditor will ask again next quarter.

    SESSION_KEYS                                 the five fields of a session, in order
    RIGHTS                                       the four rights, in the order they are printed
    ROLE_RIGHTS                                  the rights each of the directory's roles carries
    ROLE_CLEARANCE                               the clearance each of those roles stands at
    REFUSALS                                     the closed vocabulary a refusal is spelled in
    AuthError                                    the shape this stage will not accept
    principal(claims, idp)                       -> PRINCIPAL_KEYS, from a claim set that verified
    open_session(idp, assertion, audience, tick, lifetime)   -> SESSION_KEYS
    session_valid(session, tick)                 -> bool, exactly `tick < expires_at`
    rights(principal)                            -> the rights tuple, in RIGHTS order
    row_visible(principal, row)                  -> bool
    refuse_reason(principal, row)                -> None | "tenant" | "clearance"
    visible_rows(estate, principal)              -> the ids of the rows they may read, sorted
    Sessions()                                   the sessions this stage holds
    Sessions.open(principal, audience, tick, lifetime)       -> SESSION_KEYS
    Sessions.close(subject)                      -> the subjects whose sessions it closed
    Sessions.current(subject, tick)              -> SESSION_KEYS | None
    Sessions.held()                              -> the subjects holding a session, sorted
    Sessions.expired(tick)                       -> the subjects whose session has run out, sorted
    Sessions.by_group(name)                      -> the subjects holding a session in that group
    apply_scim(idp, op, tick, sessions)          -> the directory record the operation touched

DESIGN DECISION — why is a principal built from a claim set rather than from an
assertion?
Because verification is not this stage's to do. `IdP.verify` owns the signature,
the issuer, the audience and the expiry, and it refuses each one by name; a stage
that took an assertion and reasoned about it would be a stage that could disagree
with the directory about whether somebody is who they say they are. What arrives
here has already been verified, so the only question left is what the claims
*mean* — which roles this tenant gives these groups, what clearance those roles
stand at — and a claim set that raised is a claim set from which no principal is
built at all.

DESIGN DECISION — why is a clearance a number at the top of a fixed order rather
than a second classification name?
Because a row has to be compared with a principal and there is no honest way to
compare two names from a table neither of them orders. `CLASSIFICATIONS` is the
customer's own order, and a clearance is a position in it: the highest position
any of a principal's roles reaches, so two roles never add up to more than the
widest of them, and a role the table does not know reaches nothing at all. The
comparison is then one `<` between two whole numbers — no set of readable
classifications, no string ordering, and nothing that changes meaning if the
customer inserts a fifth classification tomorrow.

DESIGN DECISION — why does a refused row answer with a reason instead of
`False`?
Because the two refusals are not the same refusal, and the follow-up question is
always "why". A row of another tenant and a row above the principal's clearance
both mean "no", but one of them means the isolation is holding and the other
means somebody's role is too small, and an auditor, a support ticket or the
customer's own admin system will ask which it was. `REFUSALS` is a closed
vocabulary for exactly this reason: a reason is data the caller can branch on,
where a `False` is a fact about this code and nothing about the world. It is also
the reason `row_visible` is not the primitive — it is `refuse_reason(...) is None`
and nothing more.

DESIGN DECISION — why is the tenant asked before the clearance?
Because an ordering is the only thing that makes two refusals out of one row
deterministic. A restricted row of another tenant is refused for *both* reasons,
and which one a caller is told is a decision this stage has to make rather than
discover; the tenant comes first because the tenant is the boundary the customer
paid for, and because a row you were never entitled to see is not a row whose
classification you had any business evaluating. The comparison itself is exact:
not case-folding, not a prefix, so `northwind-2` is not `northwind` and a row that
merely starts with the customer's name does not read as theirs.

DESIGN DECISION — why does this stage hold the sessions and the directory not?
Because the directory cannot hold them, and inventing a place for them there
would be writing to the customer's system. What a session needs is a subject, the
principal that was verified, an audience and two ticks — all of it this stage's
data, none of it the customer's — so the store is this stage's own, it lives
exactly as long as the object does, and the world's log stays proof that nothing
here wrote anything at all. The one thing the directory *does* decide is who may
still work, so `apply_scim` is where a deactivation closes a session: the
directory operation happens, and its effect on the sessions this stage is holding
is this stage's to apply.

TODO: implement `principal`, `open_session`, `session_valid`, `rights`,
`row_visible`, `refuse_reason`, `visible_rows`, `Sessions` and `apply_scim` in
this file: the principal built only from a verified claim set, the session and the
store that holds them, the two reasons a row can be refused, and the one directory
operation that closes a session.
"""

import estate

SESSION_KEYS = ("subject", "principal", "audience", "opened_at", "expires_at")

RIGHTS = ("rows:read", "rows:write", "tools:call", "admin")

ROLE_RIGHTS = {
    "viewer": ("rows:read",),
    "analyst": ("rows:read",),
    "engineer": ("rows:read", "tools:call"),
    "admin": ("rows:read", "rows:write", "tools:call", "admin"),
}

ROLE_CLEARANCE = {"viewer": 0, "analyst": 2, "engineer": 2, "admin": 3}

REFUSALS = ("tenant", "clearance", "inactive", "no-session")


class AuthError(estate.EstateError):
    """A shape this stage cannot accept, or a principal it will not build.

    A kind of `estate.EstateError`, so a caller that already catches the world's
    own refusals catches this stage's too, and a kind of `ValueError`, which is
    what the world's error is.
    """


def principal(claims, idp):
    """The `PRINCIPAL_KEYS` record a verified claim set describes.

    `claims` is what `IdP.verify` answered — a tenant and the groups the subject
    is in — and `idp` is the directory that gives those groups their roles. The
    groups are looked up, the roles are collected in the order the groups name
    them, the clearance is the highest of those roles' clearances, and the tenant
    is the subject's own.

    A claim set that names no subject of its own is placed by the directory: the
    first subject carrying exactly this tenant and exactly these groups is the
    one the claim set is about, because the world puts the subject beside the
    claims rather than inside them.

    A subject the directory does not know, or one it has deactivated, is refused
    naming them: an assertion verified a tick before a deactivation is not a
    licence to work, and a session is never opened for a stranger.
    """
    raise NotImplementedError("stage 1: implement principal()")


def open_session(idp, assertion, audience, tick, lifetime):
    """Open a session for the subject of an assertion the directory has verified.

    The assertion goes through `IdP.verify` before anything else, and a session is
    never built from one that raised. Refused, naming the offender: a bad
    signature (both digests), an expired assertion (both ticks), the wrong
    audience, an unknown issuer, a lifetime that is not a positive whole number.
    The answer is `SESSION_KEYS`, with `opened_at` the tick the caller brought.
    """
    raise NotImplementedError("stage 1: implement open_session()")


def session_valid(session, tick):
    """Whether a session still outlives `tick`.

    One comparison: `tick < expires_at`. The tick at which a session expires is
    the first tick at which it is no longer good, and nothing else about the
    record moves it — the opening tick is on the record for the reader.
    """
    raise NotImplementedError("stage 1: implement session_valid()")


def rights(principal):
    """The rights a principal's roles carry, in the order `RIGHTS` spells them.

    Two roles union rather than concatenate, a role repeated grants its rights
    once, and a role the table does not know grants nothing rather than
    everything. A shape that is not a principal — not a mapping, no `roles` key,
    a single role name where a tuple belongs — is refused naming what arrived.
    """
    raise NotImplementedError("stage 1: implement rights()")


def row_visible(principal, row):
    """Whether this principal may read this row: no reason, no refusal."""
    raise NotImplementedError("stage 1: implement row_visible()")


def refuse_reason(principal, row):
    """Which of the two things refused this principal this row, or `None`.

    The tenant is asked first — a row of another tenant is refused for its tenant
    even when the clearance would have allowed it, and the comparison is exact,
    not case-folding and not a prefix — and the clearance second, against the
    *position* of the row's classification in the course's own order.
    """
    raise NotImplementedError("stage 1: implement refuse_reason()")


def visible_rows(estate, principal):
    """The ids of the rows a principal may read, sorted.

    `Estate.query` answers with the store as it is, across both tenants, and this
    is the function that may not hand that back: what comes out is what survived
    `refuse_reason`, and an empty answer stays empty rather than falling back to
    the unfiltered fetch that produced it.
    """
    raise NotImplementedError("stage 1: implement visible_rows()")


class Sessions:
    """The sessions this stage holds, one per subject, in a store of its own.

    The world holds no sessions: this object is the whole of what a session is,
    it never writes anywhere, and the only thing in the course that closes one is
    a deactivation applied through `apply_scim`. Every tick is the caller's.
    """

    def __init__(self):
        """An empty store: no subject holds a session yet."""
        raise NotImplementedError("stage 1: implement Sessions.__init__()")

    def open(self, principal, audience, tick, lifetime):
        """Hold a session for this principal and answer it as `SESSION_KEYS`."""
        raise NotImplementedError("stage 1: implement Sessions.open()")

    def close(self, subject):
        """Close `subject`'s session, answering the subjects it closed: `()` when none."""
        raise NotImplementedError("stage 1: implement Sessions.close()")

    def current(self, subject, tick):
        """The session `subject` holds and that still outlives `tick`, or `None`."""
        raise NotImplementedError("stage 1: implement Sessions.current()")

    def held(self):
        """Every subject holding a session, sorted — expired or not."""
        raise NotImplementedError("stage 1: implement Sessions.held()")

    def expired(self, tick):
        """Every subject whose session has run out at `tick`, sorted."""
        raise NotImplementedError("stage 1: implement Sessions.expired()")

    def by_group(self, name):
        """Every subject holding a session who is in group `name`, sorted."""
        raise NotImplementedError("stage 1: implement Sessions.by_group()")


def apply_scim(idp, op, tick, sessions):
    """Apply one directory operation and answer the record it touched.

    The directory refuses what it refuses — an unknown operation, a stranger, a
    field it does not hold — and this function adds what the directory cannot
    know: a deactivation closes that subject's sessions, and nothing else does.
    A refused operation leaves the sessions exactly as they were, because the
    world raised before anything here happened.
    """
    raise NotImplementedError("stage 1: implement apply_scim()")
