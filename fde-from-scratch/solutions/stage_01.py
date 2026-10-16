"""FDE From Scratch — stage 1: The assertion, the session and the row.

The world hands back a verified claim set and a row; this stage is the two
mappings in between. Claims become a principal — rights from the roles the
groups carry, a clearance that is the highest of those roles, a tenant the
subject owns. A principal becomes a session, which is a subject, the principal,
an audience and two ticks. A principal and a row become a verdict, and the
verdict is one of two reasons rather than a bare `False`. Nothing here is a
place: every tick is the caller's, and the world's own log is what says whether
this stage asked it anything at all.
"""

import estate
from estate import CLASSIFICATIONS as _CLASSIFICATIONS

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
    """A shape this stage cannot accept, or a principal it will not build."""


def _mapping(value, what):
    """`value` as a mapping, or the mistake naming what arrived."""
    if not isinstance(value, dict):
        raise AuthError("the %s is a %s, not a mapping" % (what, type(value).__name__))
    return value


def _field(mapping, key, what):
    """`mapping[key]`, or the mistake naming the key that is missing."""
    if key not in mapping:
        raise AuthError("the %s carries no %r" % (what, key))
    return mapping[key]


def _whole(value, what):
    """`value` as a whole number; a `bool` is not one here, exactly as in the world."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise AuthError("the %s is %r, not a whole number" % (what, value))
    return value


def _text(value, what):
    """`value` as a string, or the mistake naming what arrived."""
    if not isinstance(value, str):
        raise AuthError("the %s is %r, not a string" % (what, value))
    return value


def _names(value, what):
    """`value` as a tuple of names: a bare string is one name, and one name is not a tuple."""
    if not isinstance(value, (tuple, list)):
        raise AuthError("%s is a tuple of names, not %r" % (what, value))
    for name in value:
        if not isinstance(name, str):
            raise AuthError("a name is a string, and %r is not" % (name,))
    return tuple(value)


def _directory(idp, *asks):
    """The customer's directory, or the mistake: it must answer what this stage asks."""
    for name in asks:
        if not callable(getattr(idp, name, None)):
            raise AuthError("the directory is a %s, and this stage asks an IdP for %s()"
                            % (type(idp).__name__, name))
    return idp


def _holder(principal):
    """The subject a session is opened for, from a principal that names its groups."""
    principal = _mapping(principal, "principal")
    subject = _text(_field(principal, "subject", "principal"), "the principal's subject")
    _names(_field(principal, "groups", "principal"), "the principal's groups")
    return subject


def _terms(audience, tick, lifetime):
    """The audience and the two ticks a session is opened with, each one checked.

    Every shape this stage can judge on its own is judged before the customer's
    directory is asked anything, so a session that was never going to exist does
    not leave a verification in the world's log.
    """
    audience = _text(audience, "the audience")
    if not audience:
        raise AuthError("a session needs an audience, and this one is empty")
    tick = _whole(tick, "the opening tick")
    lifetime = _whole(lifetime, "the lifetime")
    if lifetime <= 0:
        raise AuthError("a session's lifetime is a positive number of ticks, and %d "
                        "is not" % (lifetime,))
    return audience, tick, lifetime


def _session(principal, audience, tick, lifetime):
    """One `SESSION_KEYS` record, or the mistake that stops it being one."""
    subject = _holder(principal)
    audience, tick, lifetime = _terms(audience, tick, lifetime)
    return {"subject": subject, "principal": dict(principal), "audience": audience,
            "opened_at": tick, "expires_at": tick + lifetime}


def _subject_of(tenant, groups, idp):
    """The subject the directory itself answers for a claim set's tenant and groups.

    The world puts the subject beside the claims rather than inside them, so a
    claim set that arrives without one still names somebody: the customer's
    directory is asked which of its subjects carries exactly this tenant and
    exactly these groups, and the first one it lists is the answer. A claim set
    the directory cannot place names nobody, and that is a refusal naming the
    tenant and the groups that found no subject.
    """
    for subject in idp.users():
        record = idp.user(subject)
        if record["tenant"] == tenant and tuple(record["groups"]) == groups:
            return subject
    raise AuthError("no subject of %r carries the groups %r, so the claim set places "
                    "nobody" % (tenant, groups))


def principal(claims, idp):
    """The `PRINCIPAL_KEYS` record a verified claim set describes.

    The claims are the source and the directory is the second reader: the groups
    the claim set names are looked up for their roles, the subject is the one the
    claim set carries or the one the directory answers for its tenant and groups,
    and a subject the directory has deactivated is refused here — an assertion
    that was verified a tick before a deactivation is not a licence to work.

    The tenant is the *subject's own* in the directory, never one of their groups'
    and never a claim set's: a claim set is a statement about a subject, and which
    customer that subject belongs to is a fact the directory already holds. The
    clearance is the highest of the roles' clearances, and a role the course does
    not know contributes nothing rather than everything.
    """
    claims = _mapping(claims, "claim set")
    idp = _directory(idp, "users", "user", "group")
    claim_tenant = _text(_field(claims, "tenant", "claim set"), "the claim set's tenant")
    groups = _names(_field(claims, "groups", "claim set"), "the claim set's groups")
    records = [idp.group(name) for name in groups]
    named = claims.get("subject")
    if named is None:
        subject = _subject_of(claim_tenant, groups, idp)
    else:
        subject = _text(named, "the claim set's subject")
    record = idp.user(subject)
    if not record["active"]:
        raise AuthError("the subject %r is inactive in the directory, so no principal "
                        "is built for them" % (subject,))
    roles = []
    for group in records:
        for role in group["roles"]:
            if role not in roles:
                roles.append(role)
    clearance = 0
    for role in roles:
        grant = ROLE_CLEARANCE.get(role, 0)
        if grant > clearance:
            clearance = grant
    return {"subject": subject, "groups": groups, "roles": tuple(roles),
            "tenant": record["tenant"], "clearance": clearance}


def open_session(idp, assertion, audience, tick, lifetime):
    """Open a session for the subject of an assertion the directory has verified.

    The assertion goes through `IdP.verify` first and a session is never built
    from one that raised: the signature, the issuer, the audience and the expiry
    are the world's own verdicts and this function has none of its own about
    them. What it does own is the subject the claim set is about — the assertion
    carries it beside the claims, and the principal is built with it so that two
    subjects the directory cannot tell apart by tenant and groups are still two
    subjects.
    """
    idp = _directory(idp, "verify")
    assertion = _mapping(assertion, "assertion")
    audience, tick, lifetime = _terms(audience, tick, lifetime)
    subject = _text(_field(assertion, "subject", "assertion"), "the assertion's subject")
    claims = idp.verify(assertion, audience, tick)
    who = principal(dict(claims, subject=subject), idp)
    return _session(who, audience, tick, lifetime)


def session_valid(session, tick):
    """Whether a session still outlives `tick`: `tick < expires_at`, and nothing else.

    One comparison, so the tick at which a session stops being usable is its
    `expires_at` and not the tick before it. The opening tick is on the record
    for the reader rather than for this rule: the world's own `verify` is what
    refuses an assertion minted in the future, and a session that was opened is
    a session.
    """
    session = _mapping(session, "session")
    keys = tuple(session)
    if keys != SESSION_KEYS:
        raise AuthError("a session carries %r, not %r" % (keys, SESSION_KEYS))
    tick = _whole(tick, "the tick")
    return tick < _whole(session["expires_at"], "the session's expiry")


def rights(principal):
    """The rights a principal's roles carry, in the order `RIGHTS` spells them.

    Two roles union rather than concatenate, a role repeated grants its rights
    once, and a role the table does not know grants nothing at all — the same
    closed table the clearance is read from. The order is the constant's own,
    never the directory's, so one principal answers the same tuple on every tick.
    """
    held = []
    for role in _names(_field(_mapping(principal, "principal"), "roles", "principal"),
                       "roles"):
        for right in ROLE_RIGHTS.get(role, ()):
            if right not in held:
                held.append(right)
    return tuple(right for right in RIGHTS if right in held)


def _tenant_of(principal):
    """The tenant a principal is from, refused unless it names one."""
    principal = _mapping(principal, "principal")
    return _text(_field(principal, "tenant", "principal"), "the principal's tenant")


def _clearance_of(principal):
    """The clearance a principal carries: one of the course's own, and nothing wider."""
    principal = _mapping(principal, "principal")
    clearance = _whole(_field(principal, "clearance", "principal"),
                       "the principal's clearance")
    if not 0 <= clearance < len(_CLASSIFICATIONS):
        raise AuthError("a clearance is one of 0 to %d, and this one is %d"
                        % (len(_CLASSIFICATIONS) - 1, clearance))
    return clearance


def _row_parts(row):
    """The tenant a row belongs to and the classification's position in the course's order."""
    row = _mapping(row, "row")
    tenant = _text(_field(row, "tenant", "row"), "the row's tenant")
    classification = _field(row, "classification", "row")
    if classification not in _CLASSIFICATIONS:
        raise AuthError("the row's classification is %r, not one of %r"
                        % (classification, _CLASSIFICATIONS))
    return tenant, _CLASSIFICATIONS.index(classification)


def refuse_reason(principal, row):
    """Which of the two things refused `principal` this row, or `None` if neither.

    The tenant is asked first, so a row of another tenant is refused for its
    tenant even when the clearance would have let it through: `northwind-2` is
    not `northwind`, and a comparison that starts with or ignores case would read
    one customer's rows as the other's. Only then is the clearance asked, against
    the *position* of the row's classification in the course's own order.
    """
    tenant, index = _row_parts(row)
    if tenant != _tenant_of(principal):
        return "tenant"
    if index > _clearance_of(principal):
        return "clearance"
    return None


def row_visible(principal, row):
    """Whether the row is one this principal may read: no reason, no refusal."""
    return refuse_reason(principal, row) is None


def visible_rows(estate, principal):
    """The ids of the rows a principal may read, sorted — never the unfiltered fetch.

    `Estate.query` is the customer's own store answering one classification at a
    time with everything it holds under that name, across both tenants, and it is
    deliberately not filtered for the caller. This function asks it only for the
    classifications the clearance reaches and then keeps nothing the principal's
    own tenant would not have: the answer is what survived, and an empty answer
    stays empty rather than falling back to what the store handed over.
    """
    if not callable(getattr(estate, "query", None)):
        raise AuthError("the estate is a %s, and this stage queries an Estate"
                        % (type(estate).__name__,))
    clearance = _clearance_of(principal)
    found = []
    for name in _CLASSIFICATIONS[:clearance + 1]:
        for row in estate.query("classification", value=name):
            if refuse_reason(principal, row) is None:
                found.append(row["id"])
    return tuple(sorted(found))


class Sessions:
    """The sessions this stage holds, one per subject, in a store of its own.

    No session is written anywhere the world can see: the customer's directory
    knows nothing about who is currently working, so this object is the whole of
    what a session is, and a deactivation is the only thing in the course that
    closes one. A second `open` for a subject replaces the first — the newest
    assertion is the one being used — and every tick here is the caller's.
    """

    def __init__(self):
        """An empty store: no subject holds a session yet."""
        self._held = {}

    def open(self, principal, audience, tick, lifetime):
        """Hold a session for this principal and answer it."""
        session = _session(principal, audience, tick, lifetime)
        self._held[session["subject"]] = session
        return dict(session)

    def close(self, subject):
        """Close `subject`'s session and answer the subjects it closed: `()` when none."""
        subject = _text(subject, "the subject")
        if subject in self._held:
            del self._held[subject]
            return (subject,)
        return ()

    def current(self, subject, tick):
        """The session `subject` holds and that still outlives `tick`, or `None`."""
        subject = _text(subject, "the subject")
        tick = _whole(tick, "the tick")
        session = self._held.get(subject)
        if session is None or not session_valid(session, tick):
            return None
        return dict(session)

    def held(self):
        """Every subject holding a session, sorted — a session that has run out is still held."""
        return tuple(sorted(self._held))

    def expired(self, tick):
        """Every subject whose session has run out at `tick`, sorted."""
        tick = _whole(tick, "the tick")
        return tuple(sorted(subject for subject, session in self._held.items()
                            if not session_valid(session, tick)))

    def by_group(self, name):
        """Every subject holding a session who is in group `name`, sorted."""
        name = _text(name, "the group name")
        return tuple(sorted(subject for subject, session in self._held.items()
                            if name in session["principal"]["groups"]))


def apply_scim(idp, op, tick, sessions):
    """Apply one directory operation and answer the record it touched.

    The directory does the work and refuses what it refuses — an unknown
    operation, a stranger, a field it does not hold — and this function adds the
    one thing the directory cannot know: what a deactivation means for the
    sessions this stage is holding. The record's own `active` is what is read, so
    an `update` that clears it closes them exactly as the `deactivate` operation
    does, and a refused operation leaves the sessions untouched because the world
    raised before anything here happened.
    """
    _whole(tick, "the directory tick")
    idp = _directory(idp, "scim")
    if not isinstance(sessions, Sessions):
        raise AuthError("the sessions are a %s, and a directory change closes sessions "
                        "in a Sessions" % (type(sessions).__name__,))
    record = idp.scim(op)
    if not record["active"]:
        sessions.close(record["subject"])
    return record
