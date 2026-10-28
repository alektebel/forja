"""FDE From Scratch — course manifest.

Twelve graded stages between a customer's reality and a deployment that survives
it. The world is provided and complete and frozen: `estate.py` is the customer —
an identity provider that signs assertions with its own digest and moves its
directory only through SCIM, a relational store whose rows carry a tenant, an
owner and a classification, a corpus of scanned paperwork that is *dirty* on
purpose, an audit line written for every act, and a `stats()` that recomputes
every counter from its own log; `network.py` is the basement — an egress policy
per zone where an empty tuple means a zone reaches nothing outside itself, an
internal registry, a bundle that is the only way an image can cross the air gap,
the nodes a deployment may target and a catalogue of local model variants;
`meter.py` is the pulse — one span per call with the cost computed by the meter
from its own price table, and a count of the minutes a *resolved* ticket saved,
per team, per model, per day.

The thesis of the whole course is one sentence, and every stage's check asserts
it: AN FDE BUILDS THE SMALLEST THING THAT SURVIVES THE CUSTOMER'S OWN REALITY —
A BOUNDARY THAT IS ENFORCED BY THE SYSTEM RATHER THAN REMEMBERED BY THE AUTHOR,
AN ARTIFACT THAT IS CHECKED AGAINST THE CUSTOMER'S OWN RECORD RATHER THAN
AGAINST A BELIEF. Each stage exists because the one before it left a hole:
nothing else can be built until "who is asking" and "which rows may they see" are
answerable; the environment decides what is even installable, so no egress, no
unpinned image and no bundle miss; the data is dirty, and a model fed dirty data
fails quietly; a retriever that ignores the caller leaks exactly what the
contract forbids; the agent is useless until it can touch the system of record —
safely, with the secret that never leaves the vault; one raw PII token on the
wire ends the deal, so masking is proved by scanning what was sent rather than by
asserting that it was masked; legal accountability sits with a person, so the
machine must stop at a gate and wait; some data is too hot to move, so the model
goes to the data and the headroom is counted in the customer's GPU memory; renewal
is an ROI conversation, and an unattributed token is a lost argument; a generic
benchmark convinces nobody, so the verdict is measured on the customer's own
tickets in shadow traffic; the translation between revenue and engineering *is*
the job, so a vague ask becomes a scoped four weeks with owners and metrics; and
leverage is measured by how little the customer needs you, so the runbook is
drilled and the admin is somebody else.

The failures worth preventing are the ones that look like success: a clearance
taken from a role's name and a tenant compared with `startswith`, so
`northwind-2` reads `northwind`'s rows; an image referenced by tag where only a
digest may cross the air gap, and a plan refused by `validate` and executed
anyway, which the world's own log is what catches; `1.234,56` read as 123456
cents by a US-only rule and a missing field defaulted to `0` instead of being
reported; a retriever that filters *after* the limit, so a small limit is a leak;
a lease secret in the audit line and a redeemed lease redeemed again; the same
counter for two different values, so a restore hands back the wrong one; an
effect written twice after a resume, the classic exactly-once bug; a headroom
rule counted against the node's RAM instead of its GPU memory, and a refused
submission left occupying a queue slot; minutes saved attributed to unresolved
tickets, so ROI is invented; the candidate's answer reaching the user, which is
the one mistake stage 10 exists to catch; a vague ask promoted to `must` because
the speaker is an executive; a rollback skipped on a failed step and a `dry_run`
that mutates the system it was only reading.

Standard library only, offline, deterministic, **ints only** (every count, price,
tick, size, ratio and basis point — there is no float literal anywhere in this
course): no `time`, no `threading`, no `asyncio`, no `random`, no `os`, no
`uuid`, no `socket`, no `subprocess`, no `secrets`, no `shutil`, no `tempfile`,
no `pathlib`, and no `math`, `statistics`, `decimal` or `fractions` either. The
clock is the caller's, a deadline is a tick compared with a tick the caller
supplied, and the world is never written by the course: a stage calls `Estate`,
`IdP`, `Network` and `Meter` and remembers what it needs in a structure it owns,
and the world's log is how the check proves the stage did not smuggle a write.

This is the enterprise end of the catalogue and the deployment that has to hold
the others at once: `rag-from-scratch` and `vector-index-from-scratch` are the
retrieval half, `mcp-from-scratch` and `agents-from-scratch` the tool half,
`evals-from-scratch` and `eval-framework-from-scratch` the measurement half,
`sandbox-capabilities-from-scratch` the boundary half and
`durable-execution-from-scratch` the workflow half. Here they are assembled for a
customer who will not read the source — one estate, one basement, one meter, and
twelve answers checked against the customer's own record and the customer's own
log.

    python3 codecraft/cli.py run fde-from-scratch
"""

from codecraft.api import stage

TITLE = "FDE From Scratch"
DESCRIPTION = ("An enterprise AI deployment as data: a principal built only from "
               "verified claims and the rows that principal may see, an air-gapped "
               "manifest whose digests are the only thing that crosses the bundle, "
               "a hybrid store that reconciles dirty scanned paperwork against the "
               "customer's own rows, retrieval that filters before it answers, "
               "legacy tools behind leases whose secrets never leave the vault, a "
               "masker that is proved by scanning what it sent, a workflow that "
               "stops at a gate and waits for a human, a model placed where its "
               "headroom fits, an ROI dashboard recounted from the meter's own "
               "spans, a verdict from shadow traffic on the customer's tickets, a "
               "scoped four weeks with owners and metrics, and a tested runbook "
               "with an admin who is not you.")

LEVEL = "advanced"
ORDER = 29


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "fde-from-scratch"

    S1_AUDIENCE = "north-app"

    S1_RIGHTS = ("rows:read", "rows:write", "tools:call", "admin")

    S1_ROLE_RIGHTS = {
        "viewer": ("rows:read",),
        "analyst": ("rows:read",),
        "engineer": ("rows:read", "tools:call"),
        "admin": ("rows:read", "rows:write", "tools:call", "admin"),
    }

    S1_ROLE_CLEARANCE = {"viewer": 0, "analyst": 2, "engineer": 2, "admin": 3}

    S1_REFUSALS = ("tenant", "clearance", "inactive", "no-session")

    S1_SESSION_KEYS = ("subject", "principal", "audience", "opened_at", "expires_at")

    S1_CLASSES = ("public", "internal", "confidential", "restricted")

    def _repo(start=None):
        for candidate_start in (os.environ.get("FDE_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set FDE_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s1_verified(idp, subject, audience=S1_AUDIENCE, tick=0, lifetime=10):
        """The claim set `IdP.verify` answers for `subject`: the stage's own input."""
        return idp.verify(idp.assertion(subject, audience, tick, lifetime), audience,
                          tick + 1)

    def _s1_person(stage, idp, subject):
        """A principal, built the way the stage's own `open_session` builds one."""
        return stage.principal(_s1_verified(idp, subject), idp)

    def _s1_row(row_id, tenant, classification, owner="ada"):
        """One `estate.ROW_KEYS` row, in order, for the row questions."""
        return {"id": row_id, "tenant": tenant, "owner": owner,
                "classification": classification, "po": "PO-9001",
                "text": "invoice for %s" % (row_id,), "amount_cents": 123456, "day": 3}

    def _s1_asker(tenant, clearance):
        """The little a row question needs of a principal: a tenant and a clearance."""
        return {"tenant": tenant, "clearance": clearance}

    def _s1_want(rows, who):
        """The check's own answer to "which rows may this principal read"."""
        return tuple(sorted(row["id"] for row in rows
                            if row["tenant"] == who["tenant"]
                            and S1_CLASSES.index(row["classification"]) <= who["clearance"]))

    def _s1_workload(stage, world):
        """One whole pass of the stage over fixtures built here, as one tuple."""
        idp = world.IdP.build(7)
        records = world.Estate.build(7)
        answers = []
        for subject in ("ada", "grace", "alan", "edsger", "barbara", "linus", "margaret"):
            who = _s1_person(stage, idp, subject)
            answers.append((who["subject"], who["groups"], who["roles"], who["tenant"],
                            who["clearance"], stage.rights(who), idp.roles_of(subject)))
        sessions = stage.Sessions()
        sessions.open(_s1_person(stage, idp, "grace"), S1_AUDIENCE, 2, 6)
        sessions.open(_s1_person(stage, idp, "ada"), S1_AUDIENCE, 0, 10)
        live = sessions.current("ada", 9)
        answers.append((sessions.held(), sessions.expired(7), sessions.expired(8),
                        sessions.expired(10), sessions.by_group("engineering"),
                        sessions.by_group("support"), stage.session_valid(live, 9),
                        stage.session_valid(live, 10)))
        for subject in ("barbara", "edsger", "linus"):
            who = _s1_person(stage, idp, subject)
            answers.append((subject, stage.visible_rows(records, who)))
        closed = stage.apply_scim(idp, {"op": "deactivate", "subject": "ada",
                                        "field": None, "value": None}, 5, sessions)
        answers.append((closed["subject"], closed["active"], closed["scim_version"],
                        sessions.held(), sessions.current("grace", 7)["expires_at"],
                        records.stats()["audits"]))
        return tuple(answers)

    def _s1_mixed(stage, world):
        """A directory whose groups are not all its users' tenants, or the table's roles."""
        groups = ({"name": "mixed", "roles": ("analyst", "sweeper"), "tenant": "contoso"},
                  {"name": "north-support", "roles": ("viewer",), "tenant": "northwind"},
                  {"name": "twin-support", "roles": ("viewer",), "tenant": "northwind"})
        users = ({"subject": "ada", "name": "Ada Lovelace",
                  "groups": ("mixed", "north-support", "twin-support"),
                  "tenant": "northwind", "active": True, "scim_version": 1},
                 {"subject": "vic", "name": "Vic Vance", "groups": ("mixed",),
                  "tenant": "northwind", "active": True, "scim_version": 1},
                 {"subject": "zoe", "name": "Zoe Zeta", "groups": ("mixed",),
                  "tenant": "contoso", "active": True, "scim_version": 1})
        idp = world.IdP(users, groups, "mixed-secret")
        assert idp.user("ada")["groups"] == ("mixed", "north-support", "twin-support"), (
            "the fixture's premise changed: the record no longer carries more groups than a "
            "claim set may name")
        whole = stage.principal({"tenant": "northwind",
                                 "groups": ("mixed", "north-support", "twin-support"),
                                 "subject": "ada"}, idp)
        assert whole["roles"] == ("analyst", "sweeper", "viewer"), (
            "the roles are the claim set's groups' own, in group order, a role two groups "
            "carry written once, and a role the table does not know still carried: %r"
            % (whole["roles"],))
        assert whole["clearance"] == 2, (
            "a role the table does not know stands at nothing, so the highest is the "
            "analyst's: %r" % (whole["clearance"],))
        assert stage.rights(whole) == ("rows:read",), (
            "a group whose role the table does not know adds no right: %r"
            % (stage.rights(whole),))
        assert whole["tenant"] == "northwind", (
            "the tenant is the subject's own in the directory and not their group's, and "
            "this one carried %r" % (whole["tenant"],))
        vic = stage.principal({"tenant": "northwind", "groups": ("mixed",),
                               "subject": "vic"}, idp)
        assert vic["tenant"] == "northwind", (
            "a subject whose only group belongs to another tenant is still their own "
            "tenant's: %r" % (vic["tenant"],))
        zoe = stage.principal({"tenant": "northwind", "groups": ("mixed",),
                               "subject": "zoe"}, idp)
        assert zoe["tenant"] == "contoso", (
            "the tenant is the directory's answer for the subject and not the claim set's: "
            "%r" % (zoe["tenant"],))
        narrow = stage.principal({"tenant": "northwind", "groups": ("north-support",),
                                  "subject": "ada"}, idp)
        assert narrow["roles"] == ("viewer",), (
            "the claim set's groups are what the roles come from, not the record's, and "
            "this one answered %r" % (narrow["roles"],))
        assert stage.rights(narrow) == ("rows:read",), (
            "a claim set that narrows its groups narrows its rights: %r"
            % (stage.rights(narrow),))

    def _s1_constants(s, world):
        assert tuple(s.SESSION_KEYS) == S1_SESSION_KEYS, (
            "a session carries %r, and the stage says %r"
            % (S1_SESSION_KEYS, tuple(s.SESSION_KEYS)))
        assert tuple(s.RIGHTS) == S1_RIGHTS, (
            "the four rights, in this order, are what every refusal prints: %r" % (s.RIGHTS,))
        assert tuple(s.ROLE_CLEARANCE) == ("viewer", "analyst", "engineer", "admin"), (
            "the clearance table holds the directory's four roles, in this order: %r"
            % (tuple(s.ROLE_CLEARANCE),))
        for role in sorted(S1_ROLE_CLEARANCE):
            assert s.ROLE_CLEARANCE[role] == S1_ROLE_CLEARANCE[role], (
                "%s stands at %r, and the contract says %r"
                % (role, S1_ROLE_CLEARANCE[role], s.ROLE_CLEARANCE.get(role)))
        for role in sorted(S1_ROLE_RIGHTS):
            assert s.ROLE_RIGHTS[role] == S1_ROLE_RIGHTS[role], (
                "%s carries %r, and the table says %r"
                % (role, S1_ROLE_RIGHTS[role], s.ROLE_RIGHTS.get(role)))
        assert sorted(s.ROLE_RIGHTS) == sorted(S1_ROLE_RIGHTS), (
            "the table holds the customer's own roles: %r" % (sorted(s.ROLE_RIGHTS),))
        assert tuple(s.REFUSALS) == S1_REFUSALS, (
            "the closed vocabulary of refusals is %r, and the stage says %r"
            % (S1_REFUSALS, tuple(s.REFUSALS)))
        assert issubclass(s.AuthError, world.EstateError), (
            "AuthError must be a kind of estate.EstateError, and its bases are %r"
            % (s.AuthError.__mro__,))
        assert issubclass(s.AuthError, ValueError), (
            "a caller's `except ValueError` must still catch it: %r" % (s.AuthError.__mro__,))

    def _s1_rights(s):
        assert s.rights({"roles": ("engineer",)}) == ("rows:read", "tools:call"), (
            "an engineer reads rows and calls tools: %r"
            % (s.rights({"roles": ("engineer",)}),))
        assert s.rights({"roles": ("admin", "viewer")}) == tuple(S1_RIGHTS), (
            "two roles union to the whole rights tuple, in RIGHTS order: %r"
            % (s.rights({"roles": ("admin", "viewer")}),))
        assert s.rights({"roles": ()}) == (), (
            "a principal with no roles carries no right: %r" % (s.rights({"roles": ()}),))
        assert s.rights({"roles": ("visitor",)}) == (), (
            "a role the table does not know grants nothing: %r"
            % (s.rights({"roles": ("visitor",)}),))
        assert s.rights({"roles": ("analyst", "analyst")}) == ("rows:read",), (
            "a role repeated grants its rights once: %r"
            % (s.rights({"roles": ("analyst", "analyst")}),))
        assert s.rights({"roles": ("admin",)}) == tuple(S1_RIGHTS), (
            "an admin carries every right, in RIGHTS order: %r"
            % (s.rights({"roles": ("admin",)}),))
        _refuses(s.AuthError, "a principal that is a string", lambda: s.rights("admin"),
                 names=("str",))
        _refuses(s.AuthError, "a principal with no roles key",
                 lambda: s.rights({"subject": "diego"}), names=("roles",))
        _refuses(s.AuthError, "roles as one string rather than a tuple",
                 lambda: s.rights({"roles": "admin"}), names=("admin",))
        _refuses(s.AuthError, "roles as a whole number rather than a tuple",
                 lambda: s.rights({"roles": 3}), names=("3",))
        _refuses(s.AuthError, "a role name that is not a string",
                 lambda: s.rights({"roles": ("admin", 3)}), names=("3",))

    def _s1_principals(s, world):
        idp = world.IdP.build(7)
        ada = _s1_person(s, idp, "ada")
        assert tuple(ada) == world.PRINCIPAL_KEYS, (
            "a principal carries %r, and the world's own order is %r"
            % (tuple(ada), world.PRINCIPAL_KEYS))
        assert ada["subject"] == "ada", (
            "the principal is about the subject the claim set is about: %r"
            % (ada["subject"],))
        assert ada["tenant"] == "northwind", (
            "the tenant is the subject's own: %r" % (ada["tenant"],))
        assert ada["groups"] == ("engineering",), (
            "the principal carries the groups the claim set named: %r" % (ada["groups"],))
        assert ada["roles"] == ("analyst", "engineer"), (
            "the roles come from the groups that carry them, deduplicated in group order: %r"
            % (ada["roles"],))
        assert ada["clearance"] == 2, (
            "the clearance is the highest of the roles': %r" % (ada["clearance"],))
        assert s.rights(ada) == ("rows:read", "tools:call"), (
            "the rights come from the roles: %r" % (s.rights(ada),))
        barbara = _s1_person(s, idp, "barbara")
        assert (barbara["groups"], barbara["roles"], barbara["clearance"]) == ((), (), 0), (
            "a subject in no group carries no role and clears nothing: %r"
            % ((barbara["groups"], barbara["roles"], barbara["clearance"]),))
        assert s.rights(barbara) == (), (
            "a principal with no role carries no right: %r" % (s.rights(barbara),))
        edsger = _s1_person(s, idp, "edsger")
        assert edsger["roles"] == ("analyst", "engineer", "admin"), (
            "two groups' roles come in the groups' order: %r" % (edsger["roles"],))
        assert edsger["clearance"] == 3, (
            "an admin's clearance is the widest: %r" % (edsger["clearance"],))
        assert s.rights(edsger) == tuple(S1_RIGHTS), (
            "an admin carries every right: %r" % (s.rights(edsger),))
        linus = _s1_person(s, idp, "linus")
        assert (linus["tenant"], linus["roles"], linus["clearance"]) == ("contoso",
                                                                        ("viewer",), 0), (
            "the other tenant's subject is that tenant's, with that tenant's roles: %r"
            % ((linus["tenant"], linus["roles"], linus["clearance"]),))
        twin = s.principal({"tenant": "contoso", "groups": ("contoso-support",)}, idp)
        assert twin["subject"] == "linus", (
            "a claim set with no subject of its own names the directory's first answer for "
            "its tenant and groups, and this one named %r" % (twin["subject"],))
        assert s.rights(ada) == ("rows:read", "tools:call"), (
            "the rights come from the roles: %r" % (s.rights(ada),))
        _refuses(world.EstateError, "a claim set whose groups the directory does not know",
                 lambda: s.principal({"tenant": "northwind", "groups": ("sales",),
                                      "subject": "ada"}, idp), names=("sales",))
        _refuses(s.AuthError, "a claim set whose tenant the directory does not know",
                 lambda: s.principal({"tenant": "other-corp", "groups": ("support",)},
                                     idp), names=("other-corp",))
        _refuses(s.AuthError, "a claim set whose groups place nobody",
                 lambda: s.principal({"tenant": "northwind", "groups": ("auditors",)},
                                     idp), names=("northwind",))
        idp.deactivate("grace")
        claims = {"tenant": "northwind", "groups": ("support",), "subject": "grace"}
        _refuses(s.AuthError, "a claim set for a subject the directory has deactivated",
                 lambda: s.principal(claims, idp), names=("grace", "inactive"))
        _refuses(s.AuthError, "a claim set that is a string",
                 lambda: s.principal("claims", idp), names=("str",))
        _refuses(s.AuthError, "a claim set with no tenant",
                 lambda: s.principal({"groups": ()}, idp), names=("tenant",))
        _refuses(s.AuthError, "a claim set whose groups are one string",
                 lambda: s.principal({"tenant": "northwind", "groups": "engineering"}, idp),
                 names=("engineering",))
        _refuses(s.AuthError, "a directory that is not a directory",
                 lambda: s.principal({"tenant": "northwind", "groups": ()}, "idp"),
                 names=("str",))

    def _s1_open(s, world):
        idp = world.IdP.build(7)
        before = idp.stats()
        session = s.open_session(idp, idp.assertion("grace", S1_AUDIENCE, 2, 10),
                                 S1_AUDIENCE, 2, 10)
        assert tuple(session) == S1_SESSION_KEYS, (
            "a session carries %r, and open_session handed back %r"
            % (S1_SESSION_KEYS, tuple(session)))
        assert (session["subject"], session["audience"], session["opened_at"],
                session["expires_at"]) == ("grace", S1_AUDIENCE, 2, 12), (
            "the session is the assertion's subject, the audience it was verified for, and "
            "a lifetime after the caller's tick: %r" % (dict(session),))
        assert session["principal"]["subject"] == "grace", (
            "the session carries the principal it was opened for: %r"
            % (session["principal"].get("subject"),))
        assert idp.stats()["verified"] == before["verified"] + 1, (
            "the assertion goes through the directory's own verify, and its count moved by "
            "%d" % (idp.stats()["verified"] - before["verified"],))
        margaret = s.open_session(idp, idp.assertion("margaret", S1_AUDIENCE, 0, 10),
                                  S1_AUDIENCE, 0, 10)
        assert margaret["subject"] == "margaret", (
            "the session's subject is the assertion's own and not the directory's first "
            "answer for its tenant and groups, and it was %r" % (margaret["subject"],))
        assert margaret["principal"]["tenant"] == "contoso", (
            "the other tenant's session is the other tenant's: %r"
            % (margaret["principal"]["tenant"],))
        thin = idp.assertion("grace", S1_AUDIENCE, 0, 10)
        trimmed = dict(thin, signature="0" * 64)
        _refuses(world.EstateError, "an assertion whose signature does not recompute",
                 lambda: s.open_session(idp, trimmed, S1_AUDIENCE, 0, 10),
                 names=("signature",))
        _refuses(world.EstateError, "an assertion offered to an audience it was not signed for",
                 lambda: s.open_session(idp, thin, "contoso-app", 0, 10),
                 names=("signature",))
        elsewhere = s.open_session(idp, idp.assertion("grace", "contoso-app", 0, 10),
                                   "contoso-app", 0, 10)
        assert (elsewhere["audience"], elsewhere["subject"]) == ("contoso-app", "grace"), (
            "the session carries the audience the assertion was verified for: %r"
            % (dict(elsewhere),))
        _refuses(world.EstateError, "an assertion that has already expired",
                 lambda: s.open_session(idp, idp.assertion("grace", S1_AUDIENCE, 0, 4),
                                        S1_AUDIENCE, 9, 10), names=("9",))
        before = idp.stats()
        _refuses(s.AuthError, "an assertion with no subject",
                 lambda: s.open_session(idp, {"issuer": "idp.northwind"}, S1_AUDIENCE, 0, 10),
                 names=("subject",))
        _refuses(s.AuthError, "a session whose lifetime is zero",
                 lambda: s.open_session(idp, thin, S1_AUDIENCE, 0, 0), names=("0",))
        _refuses(s.AuthError, "an assertion that is a string",
                 lambda: s.open_session(idp, "sandbox", S1_AUDIENCE, 0, 10), names=("str",))
        _refuses(s.AuthError, "a directory that is not a directory",
                 lambda: s.open_session("idp", thin, S1_AUDIENCE, 0, 10), names=("str",))
        assert idp.stats() == before, (
            "a session refused before the assertion was ever verified asked the directory "
            "anyway: %r" % (idp.stats(),))

    def _s1_sessions(s, world):
        idp = world.IdP.build(7)
        grace = _s1_person(s, idp, "grace")
        ada = _s1_person(s, idp, "ada")
        sessions = s.Sessions()
        assert (sessions.held(), sessions.expired(0)) == ((), ()), (
            "a fresh store holds nobody: %r" % (sessions.held(),))
        later = sessions.open(grace, S1_AUDIENCE, 2, 6)
        assert (later["subject"], later["audience"], later["opened_at"],
                later["expires_at"]) == ("grace", S1_AUDIENCE, 2, 8), (
            "a session is its subject, its audience, the tick it opened and a lifetime "
            "later: %r" % (dict(later),))
        assert later["principal"] == grace, (
            "the session carries the principal it was opened for: %r" % (later["principal"],))
        assert s.session_valid(later, 7) is True, (
            "a session is good one tick before its expiry, and this one was not")
        assert s.session_valid(later, 8) is False, (
            "a session is dead at its own expires_at, and this one was alive at 8")
        assert s.session_valid(later, 9) is False, (
            "a session stays dead after its expiry, and this one was alive at 9")
        sessions.open(ada, S1_AUDIENCE, 0, 10)
        assert sessions.held() == ("ada", "grace"), (
            "the subjects holding a session come back sorted: %r" % (sessions.held(),))
        assert sessions.expired(7) == (), (
            "a session that has not run out yet is not expired: %r" % (sessions.expired(7),))
        assert sessions.expired(8) == ("grace",), (
            "the session that expires first is the first to be expired: %r"
            % (sessions.expired(8),))
        assert sessions.expired(10) == ("ada", "grace"), (
            "both sessions have run out by tick 10: %r" % (sessions.expired(10),))
        assert sessions.current("ada", 9)["opened_at"] == 0, (
            "the session is current while it lives: %r" % (sessions.current("ada", 9),))
        assert sessions.current("ada", 10) is None, (
            "a session that has run out is not current at its expires_at")
        assert sessions.current("barbara", 9) is None, (
            "a subject holding no session has no current session")
        assert sessions.by_group("engineering") == ("ada",), (
            "a session is found by a group its principal is in: %r"
            % (sessions.by_group("engineering"),))
        assert sessions.by_group("support") == ("grace",), (
            "the other session's group finds the other subject: %r"
            % (sessions.by_group("support"),))
        assert sessions.by_group("financials") == (), (
            "a group nobody holding a session is in answers nobody: %r"
            % (sessions.by_group("financials"),))
        newest = sessions.open(ada, S1_AUDIENCE, 8, 10)
        assert newest["opened_at"] == 8, (
            "the second session for a subject is the one that was just opened: %r"
            % (newest,))
        assert sessions.current("ada", 12)["opened_at"] == 8, (
            "the store kept the older session of the two, so a second open did not replace "
            "the first: %r" % (sessions.current("ada", 12),))
        assert sessions.close("grace") == ("grace",), (
            "close names the subject whose session it closed: %r" % (sessions.close("grace"),))
        assert sessions.close("grace") == (), (
            "closing a subject who holds nothing names nobody: %r"
            % (sessions.close("grace"),))
        assert sessions.held() == ("ada",), (
            "the closed subject's session is gone and the other is still held: %r"
            % (sessions.held(),))
        _refuses(s.AuthError, "a session opened for a principal with no subject",
                 lambda: sessions.open({"groups": ()}, S1_AUDIENCE, 0, 10),
                 names=("subject",))
        _refuses(s.AuthError, "a session opened for a principal with no groups",
                 lambda: sessions.open({"subject": "ada"}, S1_AUDIENCE, 0, 10),
                 names=("groups",))
        _refuses(s.AuthError, "a session opened for a principal that is a string",
                 lambda: sessions.open("ada", S1_AUDIENCE, 0, 10), names=("str",))
        _refuses(s.AuthError, "a session with no audience",
                 lambda: sessions.open(ada, "", 0, 10), names=("audience",))
        _refuses(s.AuthError, "a session whose lifetime is zero",
                 lambda: sessions.open(ada, S1_AUDIENCE, 0, 0), names=("0",))
        _refuses(s.AuthError, "a session whose lifetime is a string",
                 lambda: sessions.open(ada, S1_AUDIENCE, 0, "10"), names=("10",))
        _refuses(s.AuthError, "a session opened at a tick that is not a whole number",
                 lambda: sessions.open(ada, S1_AUDIENCE, "0", 10), names=("0",))
        _refuses(s.AuthError, "a session asked about at a tick that is not a whole number",
                 lambda: sessions.current("ada", "9"), names=("9",))
        _refuses(s.AuthError, "a subject whose name is not a string",
                 lambda: sessions.close(7), names=("7",))
        _refuses(s.AuthError, "a session opened for a principal whose subject is not a string",
                 lambda: sessions.open({"subject": 7, "groups": ()}, S1_AUDIENCE, 0, 10),
                 names=("7",))
        _refuses(s.AuthError, "a group name that is not a string",
                 lambda: sessions.by_group(7), names=("7",))
        _refuses(s.AuthError, "a session record missing a field",
                 lambda: s.session_valid({"subject": "ada"}, 0), names=("subject",))
        _refuses(s.AuthError, "a session record whose fields are in another order",
                 lambda: s.session_valid({"principal": ada, "subject": "ada",
                                          "audience": S1_AUDIENCE, "opened_at": 0,
                                          "expires_at": 10}, 0), names=("expires_at",))
        _refuses(s.AuthError, "a session that is a string",
                 lambda: s.session_valid("ada", 0), names=("str",))
        _refuses(s.AuthError, "a session whose expiry is not a whole number",
                 lambda: s.session_valid(dict(later, expires_at="8"), 7), names=("8",))

    def _s1_rows(s, world):
        grid = tuple(tuple(s.refuse_reason(_s1_asker("northwind", clearance),
                                           _s1_row("row-%d" % (index,), "northwind", name))
                           is None
                           for index, name in enumerate(S1_CLASSES))
                     for clearance in range(len(S1_CLASSES)))
        want = tuple(tuple(index <= clearance for index in range(len(S1_CLASSES)))
                     for clearance in range(len(S1_CLASSES)))
        assert grid == want, (
            "a row is visible on the position of its classification against the clearance, "
            "so the sixteen cells are %r, and this stage answered them %r" % (want, grid))
        assert s.refuse_reason(_s1_asker("northwind", 0),
                               _s1_row("row-1", "northwind", "internal")) == "clearance", (
            "a row above the clearance is refused for the clearance, not with a `False` and "
            "not for the tenant")
        assert s.refuse_reason(_s1_asker("northwind", 3),
                               _s1_row("row-1", "northwind", "restricted")) is None, (
            "the widest clearance reads the narrowest classification of its own tenant")
        assert s.refuse_reason(_s1_asker("northwind", 3),
                               _s1_row("row-1", "northwind-2", "public")) == "tenant", (
            "a tenant that merely starts with the customer's name is another tenant")
        assert s.refuse_reason(_s1_asker("northwind", 3),
                               _s1_row("row-1", "Northwind", "public")) == "tenant", (
            "a tenant compared case-insensitively reads another customer's rows")
        assert s.refuse_reason(_s1_asker("northwind", 0),
                               _s1_row("row-1", "contoso", "restricted")) == "tenant", (
            "a row of another tenant is refused for its tenant even when the clearance "
            "refuses it too, because the tenant is asked first")
        _refuses(s.AuthError, "a row that is not a mapping",
                 lambda: s.refuse_reason(_s1_asker("northwind", 0), "row-1"), names=("str",))
        _refuses(s.AuthError, "a row with no tenant",
                 lambda: s.refuse_reason(_s1_asker("northwind", 0),
                                         {"classification": "public"}), names=("tenant",))
        _refuses(s.AuthError, "a row whose classification is not one of the course's",
                 lambda: s.refuse_reason(_s1_asker("northwind", 3),
                                         _s1_row("row-1", "northwind", "secret")),
                 names=("secret",))
        _refuses(s.AuthError, "a principal that is a string",
                 lambda: s.refuse_reason("ada", _s1_row("row-1", "northwind", "public")),
                 names=("str",))
        _refuses(s.AuthError, "a principal with no tenant",
                 lambda: s.refuse_reason({"clearance": 0},
                                         _s1_row("row-1", "northwind", "public")),
                 names=("tenant",))
        _refuses(s.AuthError, "a principal with no clearance",
                 lambda: s.refuse_reason({"tenant": "northwind"},
                                         _s1_row("row-1", "northwind", "public")),
                 names=("clearance",))
        _refuses(s.AuthError, "a clearance above the customer's own list",
                 lambda: s.refuse_reason(_s1_asker("northwind", 4),
                                         _s1_row("row-1", "northwind", "public")), names=("4",))
        _refuses(s.AuthError, "a clearance that is a string",
                 lambda: s.refuse_reason(_s1_asker("northwind", "3"),
                                         _s1_row("row-1", "northwind", "public")), names=("3",))
        _refuses(s.AuthError, "a clearance that is a bool",
                 lambda: s.refuse_reason(_s1_asker("northwind", True),
                                         _s1_row("row-1", "northwind", "public")),
                 names=("True",))
        assert s.row_visible(_s1_asker("northwind", 0),
                             _s1_row("row-1", "northwind", "public")) is True, (
            "row_visible is `True` for the row with no refusal")
        assert s.row_visible(_s1_asker("northwind", 0),
                             _s1_row("row-1", "northwind", "internal")) is False, (
            "row_visible is `False` for the row with a refusal")

    def _s1_visible(s, world):
        records = world.Estate.build(7)
        idp = world.IdP.build(7)
        barbara = _s1_person(s, idp, "barbara")
        edsger = _s1_person(s, idp, "edsger")
        linus = _s1_person(s, idp, "linus")
        before = records.stats()
        answer = s.visible_rows(records, barbara)
        after = records.stats()
        assert answer == _s1_want(records.rows(), barbara), (
            "a viewer reads the public rows of their own tenant, and this stage answered %r "
            "where the rows say %r" % (answer, _s1_want(records.rows(), barbara)))
        assert after["queries"] - before["queries"] == 1, (
            "a clearance of 0 reaches one classification, so the store is asked once, and "
            "it was asked %d times" % (after["queries"] - before["queries"],))
        before = records.stats()
        wide = s.visible_rows(records, edsger)
        after = records.stats()
        assert wide == _s1_want(records.rows(), edsger), (
            "the widest clearance reads every classification of its own tenant: %r"
            % (wide,))
        assert after["queries"] - before["queries"] == 4, (
            "a clearance of 3 reaches four classifications, so the store is asked four "
            "times and not more, and it was asked %d times"
            % (after["queries"] - before["queries"],))
        assert after["rows_returned"] - before["rows_returned"] > len(wide), (
            "the store handed back %d rows and %d ids went out, so the unfiltered fetch is "
            "what this function returned"
            % (after["rows_returned"] - before["rows_returned"], len(wide)))
        assert s.visible_rows(records, linus) == _s1_want(records.rows(), linus), (
            "another tenant's principal reads their own tenant's rows, which are not ours: "
            "%r" % (s.visible_rows(records, linus),))
        before = records.stats()
        _refuses(s.AuthError, "an estate that is not an estate",
                 lambda: s.visible_rows("records", barbara), names=("str",))
        _refuses(s.AuthError, "a principal whose clearance is not one of the course's",
                 lambda: s.visible_rows(records, _s1_asker("northwind", 9)), names=("9",))
        assert records.stats() == before, (
            "a refused visible_rows asked the estate anyway: %r" % (records.stats(),))
        _refuses(s.AuthError, "a principal with no tenant",
                 lambda: s.visible_rows(records, {"clearance": 3}), names=("tenant",))
        ours = (_s1_row("row-b", "northwind", "public"),
                _s1_row("row-a", "northwind", "internal"),
                _s1_row("row-f", "northwind-2", "public"))
        theirs = (_s1_row("row-c", "contoso", "public"),)
        small = world.Estate(ours + theirs, ())
        assert s.visible_rows(small, _s1_asker("northwind", 1)) == ("row-a", "row-b"), (
            "the ids come back sorted, and only the principal's own tenant's: %r"
            % (s.visible_rows(small, _s1_asker("northwind", 1)),))
        assert s.visible_rows(small, _s1_asker("northwind", 0)) == ("row-b",), (
            "a viewer reads the public row and not the internal one: %r"
            % (s.visible_rows(small, _s1_asker("northwind", 0)),))
        closed = world.Estate((_s1_row("row-d", "northwind", "internal"),
                               _s1_row("row-e", "contoso", "public")), ())
        assert s.visible_rows(closed, _s1_asker("northwind", 0)) == (), (
            "an empty answer stays empty: the unfiltered fetch must not be handed back when "
            "the filter kept nothing, and this returned %r"
            % (s.visible_rows(closed, _s1_asker("northwind", 0)),))

    def _s1_scim(s, world):
        idp = world.IdP.build(7)
        records = world.Estate.build(7)
        sessions = s.Sessions()
        sessions.open(_s1_person(s, idp, "ada"), S1_AUDIENCE, 0, 10)
        sessions.open(_s1_person(s, idp, "grace"), S1_AUDIENCE, 0, 10)
        assert sessions.held() == ("ada", "grace"), (
            "the fixture's premise changed: the store does not hold both sessions")
        before = idp.stats()
        record = s.apply_scim(idp, {"op": "deactivate", "subject": "ada", "field": None,
                                    "value": None}, 5, sessions)
        assert tuple(record) == world.USER_KEYS, (
            "the answer is the directory record the operation touched, and it carries %r"
            % (tuple(record),))
        assert (record["subject"], record["active"]) == ("ada", False), (
            "the record is the one the world changed: %r" % (record,))
        assert idp.stats()["scim"] == before["scim"] + 1, (
            "the directory applied exactly one operation, and its own count moved by %d"
            % (idp.stats()["scim"] - before["scim"],))
        assert idp.user("ada")["active"] is False, (
            "the directory was left unchanged by the SCIM call")
        assert sessions.held() == ("grace",), (
            "a deactivation closes that subject's session, and the store still holds %r"
            % (sessions.held(),))
        assert records.stats()["audits"] == 0, (
            "nothing in this stage writes an audit line into the customer's estate")
        record = s.apply_scim(idp, {"op": "update", "subject": "grace", "field": "active",
                                    "value": False}, 6, sessions)
        assert (record["active"], sessions.held()) == (False, ()), (
            "an update that clears active is a deactivation too, and the store holds %r"
            % (sessions.held(),))
        sessions.open(_s1_person(s, idp, "alan"), S1_AUDIENCE, 0, 10)
        s.apply_scim(idp, {"op": "update", "subject": "ada", "field": "active",
                           "value": True}, 7, sessions)
        assert sessions.held() == ("alan",), (
            "reactivating a subject closes nothing, and the store holds %r"
            % (sessions.held(),))
        s.apply_scim(idp, {"op": "group-add", "subject": "alan", "field": "groups",
                           "value": "auditors"}, 8, sessions)
        assert sessions.held() == ("alan",), (
            "a directory operation that is not a deactivation closes nothing, and the store "
            "holds %r" % (sessions.held(),))
        before = idp.stats()
        _refuses(world.EstateError, "a SCIM operation for a stranger",
                 lambda: s.apply_scim(idp, {"op": "deactivate", "subject": "nobody",
                                            "field": None, "value": None}, 9, sessions),
                 names=("nobody",))
        _refuses(world.EstateError, "a SCIM operation that is not one of the directory's",
                 lambda: s.apply_scim(idp, {"op": "promote", "subject": "alan",
                                            "field": None, "value": None}, 9, sessions),
                 names=("promote",))
        assert sessions.held() == ("alan",), (
            "a refused operation closed a session: %r" % (sessions.held(),))
        assert idp.stats() == before, (
            "a refused operation left a line in the directory's own log: %r" % (idp.stats(),))
        going = {"op": "group-remove", "subject": "alan", "field": "groups",
                 "value": "auditors"}
        _refuses(s.AuthError, "a directory tick that is not a whole number",
                 lambda: s.apply_scim(idp, going, "9", sessions), names=("9",))
        _refuses(s.AuthError, "a store that is not a Sessions",
                 lambda: s.apply_scim(idp, going, 9, "sessions"), names=("str",))
        _refuses(s.AuthError, "a directory that is not a directory",
                 lambda: s.apply_scim("idp", going, 9, sessions), names=("str",))
        assert sessions.held() == ("alan",), (
            "a refused apply_scim touched the store: %r" % (sessions.held(),))
        assert idp.stats() == before, (
            "a refused apply_scim asked the directory anyway: %r" % (idp.stats(),))

    def _s1_twice(s, world):
        one = _s1_workload(s, world)
        two = _s1_workload(s, world)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function of "
            "its inputs")

    import stage_01 as s
    import estate as world
    _s1_constants(s, world)
    _s1_rights(s)
    _s1_principals(s, world)
    _s1_mixed(s, world)
    _s1_open(s, world)
    _s1_sessions(s, world)
    _s1_rows(s, world)
    _s1_visible(s, world)
    _s1_scim(s, world)
    _s1_twice(s, world)

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "fde-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("FDE_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set FDE_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _manifest(images, **overrides):
        """A deployment manifest for the customer's own namespace, field by field."""
        manifest = {"name": "north-app", "namespace": "northwind-app", "images": images,
                    "node_zone": "app", "replicas": 2, "env": ("LOG_LEVEL=info",)}
        manifest.update(overrides)
        return manifest

    def _bundle(net):
        """The digests the customer's bundle physically carries: what can be pulled."""
        return tuple(image["digest"] for image in net.images() if net.pullable(image))

    def _leaky(net):
        """The customer's basement with one thing wrong: `app` reaches `public`."""
        return net.__class__(dict(net.rules(), app=("registry", "public")), net.images(),
                             _bundle(net), net.nodes(), net.models())

    def _zoned(net, zones):
        """The customer's network keeping only the machines of `zones`."""
        return net.__class__(net.rules(), net.images(), _bundle(net),
                             tuple(node for node in net.nodes() if node["zone"] in zones),
                             net.models())

    def _problems(answer):
        """A refusal's own `(problem, offender)` tuple, or the mistake named."""
        assert isinstance(answer, dict), (
            "a refusal is a mapping, and this is %s" % (type(answer).__name__,))
        got = answer["problems"]
        assert isinstance(got, tuple), (
            "problems are a tuple of (problem, offender) pairs, not %r" % (got,))
        return got

    def _deployable(net):
        """The images the customer's bundle actually carries, and the one it does not."""
        images = net.images()
        good = tuple(image for image in images if net.pullable(image))[:2]
        absent = [image for image in images if not net.pullable(image)][0]
        return good, absent

    def _placed(s, net, good, tick=2):
        """A namespace, a plan and its deployment, on the network it was made for."""
        steps, problems = s.plan(_manifest(good), net)
        assert problems == (), (
            "a plan for a good manifest has no problems, and it has %r" % (problems,))
        return steps, s.deploy(steps, net, "northwind-app", tick)

    def _constants(s, world):
        assert tuple(s.MANIFEST_KEYS) == ("name", "namespace", "images", "node_zone",
                                          "replicas", "env"), (
            "a manifest's six fields, in this order, are what a refusal prints: %r"
            % (s.MANIFEST_KEYS,))
        assert tuple(s.PROBLEMS) == ("bad-namespace", "bad-replicas", "unknown-image",
                                     "unpinned-digest", "not-in-bundle", "no-node",
                                     "would-egress", "duplicate-image"), (
            "the eight problems, in this order, are how a refusal reads: %r"
            % (s.PROBLEMS,))
        assert tuple(s.STEPS) == ("pull", "install", "start"), (
            "a plan is made of these three actions, in this order: %r" % (s.STEPS,))
        assert tuple(s.DEPLOY_KEYS) == ("namespace", "installed", "running", "steps_done",
                                        "verdict"), (
            "a deployment answers with these five fields, in this order: %r"
            % (s.DEPLOY_KEYS,))
        assert issubclass(s.DeployError, world.EstateError), (
            "DeployError must be a kind of estate.EstateError, and its bases are %r"
            % (s.DeployError.__mro__,))
        assert issubclass(s.DeployError, ValueError), (
            "a caller's `except ValueError` must still catch it: %r"
            % (s.DeployError.__mro__,))

    def _validate(s, world, net):
        images = net.images()
        good, absent = _deployable(net)

        answer = s.validate(_manifest(good), net)
        assert tuple(answer) == ("ok", "problems", "images", "egress"), (
            "validate answers with these four fields, in this order: %r" % (tuple(answer),))
        assert answer["ok"] is True, (
            "a manifest of bundle images validates, and this one was refused: %r"
            % (_problems(answer),))
        assert _problems(answer) == (), (
            "an accepted manifest has no problems, and this one has %r"
            % (_problems(answer),))
        assert tuple(answer["images"]) == good, (
            "an accepted manifest resolves the registry's own records in manifest order:"
            " %r" % (answer["images"],))
        assert tuple(answer["egress"]) == (("app", "registry"), ("app", "storage")), (
            "the egress is the (zone, destination) pairs the manifest would reach: %r"
            % (answer["egress"],))
        assert net.log() == () and net.stats()["attempts"] == 0, (
            "validating a manifest reached out: the network's log is %r" % (net.log(),))
        assert net.images() == images, (
            "validate wrote to the customer's own registry: %r" % (net.images(),))

        for own in (world.ESTATE_NAME, "northwind-2", "northwind-app"):
            accepted = s.validate(_manifest(good, namespace=own), net)
            assert accepted["ok"] is True, (
                "%r is the customer's own namespace, and it was refused: %r"
                % (own, _problems(accepted)))
        for strange in ("contoso-app", "northwindevil", "NORTHWIND", "Northwind-app",
                        "north"):
            refused = s.validate(_manifest(good, namespace=strange), net)
            assert _problems(refused) == (("bad-namespace", strange),), (
                "a namespace that is not the customer's is bad-namespace naming it: %r"
                % (_problems(refused),))
            assert refused["ok"] is False, (
                "%r is not the customer's namespace, and it validated" % (strange,))

        for replicas in (0, -1):
            refused = s.validate(_manifest(good, replicas=replicas), net)
            assert _problems(refused) == (("bad-replicas", replicas),), (
                "replicas %d is not a deployment, and it must name the count: %r"
                % (replicas, _problems(refused)))
        one = s.validate(_manifest(good, replicas=1), net)
        assert one["ok"] is True, (
            "one replica is a deployment, and it was refused: %r" % (_problems(one),))

        unknown = {"name": "nope", "tag": "1.0", "digest": "0" * 64}
        refused = s.validate(_manifest((unknown,)), net)
        assert _problems(refused) == (("unknown-image", "nope:1.0"),), (
            "an image the registry does not hold is unknown-image naming the image: %r"
            % (_problems(refused),))
        forged = dict(good[0], digest="1" * 64)
        refused = s.validate(_manifest((forged,)), net)
        assert _problems(refused) == (
            ("unpinned-digest", "%s:%s" % (forged["name"], forged["tag"])),), (
                "a digest the customer's review did not pin is unpinned-digest naming "
                "the image: %r" % (_problems(refused),))
        assert refused["images"] == (), (
            "a forged image resolves to nothing, and this one resolved: %r"
            % (refused["images"],))
        refused = s.validate(_manifest((absent,)), net)
        assert _problems(refused) == (("not-in-bundle", absent["digest"]),), (
            "an image the bundle does not carry cannot cross the air gap: %r"
            % (_problems(refused),))
        assert refused["images"] == (absent,), (
            "the registry holds it, so it resolves: %r" % (refused["images"],))
        refused = s.validate(_manifest((good[0], good[0])), net)
        assert _problems(refused) == (("duplicate-image", good[0]["digest"]),), (
            "the same image twice is one problem, naming it: %r" % (_problems(refused),))
        doubled = s.validate(_manifest((unknown, dict(unknown, name="nope2"))), net)
        assert _problems(doubled) == (("unknown-image", "nope:1.0"),), (
            "one problem per kind, naming the first offender: %r" % (_problems(doubled),))

        refused = s.validate(_manifest(good, node_zone="dmz"), net)
        assert _problems(refused) == (("no-node", "dmz"),), (
            "a zone the network does not have is no-node naming the zone: %r"
            % (_problems(refused),))
        assert refused["egress"] == (), (
            "a zone the network does not have reaches nothing: %r" % (refused["egress"],))
        refused = s.validate(_manifest(good), _zoned(net, ("data",)))
        assert _problems(refused) == (("no-node", "app"),), (
            "a zone no machine stands in is no-node naming the zone: %r"
            % (_problems(refused),))

        leaky = _leaky(net)
        refused = s.validate(_manifest(good), leaky)
        assert _problems(refused) == (("would-egress", "public"),), (
            "a zone that reaches the public internet is refused, naming what it "
            "reaches: %r" % (_problems(refused),))
        assert ("app", "public") in refused["egress"], (
            "the egress the manifest would reach carries it: %r" % (refused["egress"],))
        assert leaky.log() == (), (
            "validate reached out to find out, and the log says %r" % (leaky.log(),))

        everything = s.validate(_manifest((unknown, forged, absent, absent),
                                          namespace="contoso", replicas=0), leaky)
        assert _problems(everything) == (
            ("bad-namespace", "contoso"), ("bad-replicas", 0),
            ("unknown-image", "nope:1.0"), ("unpinned-digest", "north-api:1.4.0"),
            ("not-in-bundle", absent["digest"]), ("would-egress", "public"),
            ("duplicate-image", absent["digest"])), (
            "problems come back in PROBLEMS order, not in the order they were found: %r"
            % (_problems(everything),))

        _refuses(s.DeployError, "a manifest that is a string",
                 lambda: s.validate("north-app", net), names=("str",))
        _refuses(s.DeployError, "a manifest with a field missing",
                 lambda: s.validate({"name": "north-app"}, net),
                 names=("name", "node_zone"))
        _refuses(s.DeployError, "a manifest whose keys are in another order",
                 lambda: s.validate({"namespace": "northwind-app", "name": "north-app",
                                     "images": good, "node_zone": "app", "replicas": 1,
                                     "env": ()}, net), names=("replicas",))
        _refuses(s.DeployError, "a name that is empty",
                 lambda: s.validate(_manifest(good, name=""), net), names=("name",))
        _refuses(s.DeployError, "a namespace that is not a string",
                 lambda: s.validate(_manifest(good, namespace=2), net),
                 names=("namespace",))
        _refuses(s.DeployError, "replicas that are a bool",
                 lambda: s.validate(_manifest(good, replicas=True), net),
                 names=("replicas",))
        _refuses(s.DeployError, "images that are a list",
                 lambda: s.validate(_manifest([good[0]]), net), names=("list",))
        _refuses(s.DeployError, "an env that is not a tuple",
                 lambda: s.validate(_manifest(good, env="LOG_LEVEL=info"), net),
                 names=("env",))
        _refuses(s.DeployError, "an env line that is not a string",
                 lambda: s.validate(_manifest(good, env=(7,)), net), names=("str",))
        _refuses(s.DeployError, "an image reference that is not a mapping",
                 lambda: s.validate(_manifest(("north-api",)), net), names=("str",))
        _refuses(s.DeployError, "an image reference with no digest",
                 lambda: s.validate(_manifest(({"name": "north-api", "tag": "1.4.0"},)),
                                    net), names=("digest",))

    def _plan(s, net):
        good, absent = _deployable(net)
        d0, d1 = good[0]["digest"], good[1]["digest"]

        steps, problems = s.plan(_manifest(good), net)
        assert problems == (), (
            "a plan for a good manifest has no problems, and it has %r" % (problems,))
        assert steps == (("pull", d0), ("pull", d1), ("install", d0), ("install", d1),
                         ("start", "north-app:app-1:0"),
                         ("start", "north-app:app-2:0")), (
            "a plan pulls the pinned digests, installs them and starts one instance per "
            "replica, in that order: %r" % (steps,))
        assert net.log() == (), (
            "planning a manifest reached out, and the log says %r" % (net.log(),))
        actions = [action for action, subject in steps]
        assert actions.index("pull") < actions.index("install"), (
            "the plan installs before it pulls: %r" % (steps,))

        for replicas in (1, 3, 5):
            more, _ = s.plan(_manifest(good, replicas=replicas), net)
            starts = [subject for action, subject in more if action == "start"]
            assert len(starts) == replicas, (
                "%d replicas start %d instances: %r" % (replicas, len(starts), more))
            assert len(set(starts)) == replicas, (
                "two replicas of one deployment share an instance name: %r" % (starts,))
            assert [action for action, subject in more][-1] == "start", (
                "a plan starts what it installed, and this one ends with %r" % (more[-1],))

        empty, refused = s.plan(_manifest((absent,)), net)
        assert empty == (), (
            "a refused manifest has no steps to run, and this one has %r" % (empty,))
        assert refused == _problems(s.validate(_manifest((absent,)), net)), (
            "a refused plan carries the manifest's own problems: %r" % (refused,))

    def _deploy(s, net):
        good, absent = _deployable(net)
        d0, d1 = good[0]["digest"], good[1]["digest"]
        steps, _ = s.plan(_manifest(good), net)
        zero = {"attempts": 0, "allowed": 0, "blocked": 0, "pulls": 0, "installs": 0}

        refused = s.deploy((), net, "northwind-app", 1)
        assert tuple(refused) == s.DEPLOY_KEYS, (
            "a deployment answers with the five DEPLOY_KEYS: %r" % (tuple(refused),))
        assert refused == {"namespace": "northwind-app", "installed": (), "running": (),
                           "steps_done": 0, "verdict": "refused"}, (
            "a refused plan deploys nothing and runs nothing: %r" % (refused,))
        assert net.stats() == zero and net.log() == (), (
            "a refused plan attempted something: the log says %r" % (net.log(),))

        deployed = s.deploy(steps, net, "northwind-app", 2)
        assert tuple(deployed) == s.DEPLOY_KEYS, (
            "a deployment answers with the five DEPLOY_KEYS: %r" % (tuple(deployed),))
        assert deployed["verdict"] == "deployed", (
            "a plan of bundle images deploys: %r" % (deployed,))
        assert deployed["namespace"] == "northwind-app", (
            "the deployment carries the namespace it was told: %r" % (deployed,))
        assert deployed["installed"] == tuple(sorted((d0, d1))), (
            "the deployment installed its images, as a sorted tuple of digests: %r"
            % (deployed["installed"],))
        assert deployed["running"] == ("north-app:app-1:0", "north-app:app-2:0"), (
            "the deployment runs one instance per replica: %r" % (deployed["running"],))
        assert deployed["steps_done"] == len(steps), (
            "every step of a good plan ran: %r of %r"
            % (deployed["steps_done"], len(steps)))

        stats = net.stats()
        assert (stats["pulls"], stats["installs"]) == (2, 2), (
            "the world logged one pull and one install per image: %r" % (stats,))
        assert (stats["attempts"], stats["blocked"]) == (0, 0), (
            "the deployment reached out, and the world says %r" % (stats,))
        log = net.log()
        assert [(line["action"], line["target"]) for line in log] == [
            ("pull", d0), ("pull", d1), ("install", d0), ("install", d1)], (
            "the world's log shows the plan's own order: %r" % (log,))
        assert [line["reason"] for line in log if line["action"] == "install"] == [
            "app-1", "app-2"], (
            "the digests were installed onto the nodes the plan's starts named: %r"
            % (log,))
        assert [line["zone"] for line in log if line["action"] == "install"] == [
            "app", "app"], (
            "an install goes to a node of the deployment's own zone: %r" % (log,))
        assert [line["reason"] for line in log if line["action"] == "pull"] == [
            "%s:%s" % (good[0]["name"], good[0]["tag"]),
            "%s:%s" % (good[1]["name"], good[1]["tag"])], (
            "a pull crosses the air gap by name and tag, for a digest that was pinned: %r"
            % (log,))
        assert [line["tick"] for line in log] == [2, 2, 2, 2], (
            "every line the world wrote carries the caller's tick: %r" % (log,))

        partial = net.__class__.build(7)
        stopped = s.deploy((("pull", d0), ("pull", absent["digest"])), partial,
                           "northwind-app", 3)
        assert stopped["verdict"] == "refused" and stopped["installed"] == (), (
            "a step the world refuses stops the deployment: %r" % (stopped,))
        assert stopped["steps_done"] == 1, (
            "only the steps that ran are counted, and this counted %r" % (stopped,))
        assert partial.stats()["pulls"] == 1, (
            "the log shows the one pull that crossed the air gap: %r" % (partial.log(),))
        unknown = net.__class__.build(7)
        nowhere = s.deploy((("pull", "0" * 64),), unknown, "northwind-app", 3)
        assert nowhere["verdict"] == "refused" and unknown.log() == (), (
            "a pull of a digest the registry does not hold never reaches the world: %r"
            % (nowhere,))
        blind = s.deploy((("install", d0),), net.__class__.build(7), "northwind-app", 4)
        assert blind == {"namespace": "northwind-app", "installed": (), "running": (),
                         "steps_done": 0, "verdict": "refused"}, (
            "an install with no instance naming a node has no zone to install into: %r"
            % (blind,))

        reverse_net = net.__class__.build(7)
        reversed_steps, _ = s.plan(_manifest((good[1], good[0])), reverse_net)
        reversed_state = s.deploy(reversed_steps, reverse_net, "northwind-app", 2)
        assert reversed_state["installed"] == tuple(sorted((d0, d1))), (
            "installed is the digests sorted, whatever order the plan named them: %r"
            % (reversed_state["installed"],))

        _refuses(s.DeployError, "a plan that is not a sequence",
                 lambda: s.deploy("pull", net, "northwind-app", 1), names=("str",))
        _refuses(s.DeployError, "a step that is not a pair",
                 lambda: s.deploy((("pull",),), net, "northwind-app", 1), names=("action",))
        _refuses(s.DeployError, "an action that is not one of STEPS",
                 lambda: s.deploy((("fly", d0),), net, "northwind-app", 1), names=("fly",))
        _refuses(s.DeployError, "a subject that is not a string",
                 lambda: s.deploy((("pull", 7),), net, "northwind-app", 1),
                 names=("subject",))
        _refuses(s.DeployError, "a namespace that is not a string",
                 lambda: s.deploy((), net, 2, 1), names=("namespace",))
        _refuses(s.DeployError, "a tick that is not an int",
                 lambda: s.deploy((), net, "northwind-app", "2"), names=("tick",))
        _refuses(s.DeployError, "a tick before zero",
                 lambda: s.deploy((), net, "northwind-app", -1), names=("tick",))

    def _verify(s, net):
        good, absent = _deployable(net)
        d0, d1 = good[0]["digest"], good[1]["digest"]
        steps, deployed = _placed(s, net, good)

        answer = s.verify(deployed, net)
        assert tuple(answer) == ("ok", "problems"), (
            "verify answers with ok and problems, in this order: %r" % (tuple(answer),))
        assert answer["ok"] is True and answer["problems"] == (), (
            "a deployment the world's log agrees with verifies: %r" % (answer,))

        forged = dict(deployed, running=())
        assert s.verify(forged, net)["ok"] is False, (
            "a deployment that claims more than the log shows verified: %r"
            % (s.verify(forged, net),))
        assert s.verify(forged, net)["problems"] == (("not-running", "app-1"),
                                                     ("not-running", "app-2")), (
            "an install with no instance running on its node is not-running, per node: %r"
            % (s.verify(forged, net)["problems"],))
        moved = dict(deployed, running=("north-app:data-1:0",))
        assert s.verify(moved, net)["problems"] == (("wrong-zone", "data-1"),
                                                    ("not-running", "app-1"),
                                                    ("not-running", "app-2")), (
            "an instance on another zone's node is wrong-zone, naming the node: %r"
            % (s.verify(moved, net)["problems"],))
        nowhere = dict(deployed, running=("north-app:nope-9:0",))
        assert s.verify(nowhere, net)["problems"] == (("wrong-zone", "nope-9"),
                                                      ("not-running", "app-1"),
                                                      ("not-running", "app-2")), (
            "an instance on a node no machine has is wrong-zone: %r"
            % (s.verify(nowhere, net)["problems"],))
        bare = dict(deployed, running=("app-2",))
        assert s.verify(bare, net)["problems"] == (("not-running", "app-1"),), (
            "an instance named for its node runs on that node, per node: %r"
            % (s.verify(bare, net)["problems"],))
        extra = dict(deployed, installed=deployed["installed"] + ("0" * 64,))
        assert s.verify(extra, net)["problems"] == (("not-pulled", "0" * 64),
                                                    ("not-in-bundle", "0" * 64)), (
            "a digest the log never pulled is not-pulled, and one the bundle never "
            "carried is not-in-bundle: %r" % (s.verify(extra, net)["problems"],))
        short = dict(deployed, installed=(absent["digest"],))
        assert s.verify(short, net)["problems"] == (("not-pulled", absent["digest"]),
                                                    ("not-in-bundle", absent["digest"])), (
            "a state that claims an image the bundle never carried is both: %r"
            % (s.verify(short, net)["problems"],))

        planted = net.__class__.build(7)
        planted_steps, planted_state = _placed(s, planted, good)
        planted.install(d0, "data-1", 9)
        assert s.verify(planted_state, planted)["problems"] == (
            ("wrong-zone", "data-1"), ("not-running", "data-1")), (
            "an install onto another zone's node is wrong-zone: %r"
            % (s.verify(planted_state, planted)["problems"],))

        leaked = _leaky(net.__class__.build(7))
        leaked_state = s.deploy(steps, leaked, "northwind-app", 2)
        assert s.verify(leaked_state, leaked)["ok"] is True, (
            "deploying reaches nothing by itself, and the log says %r"
            % (leaked.log(),))
        leaked.attempt("app", "public", 9)
        assert s.verify(leaked_state, leaked)["problems"] == (
            ("public-attempted", "public"),), (
            "a reach-out the policy allowed is public-attempted: %r"
            % (s.verify(leaked_state, leaked)["problems"],))
        blocked = net.__class__.build(7)
        blocked_steps, blocked_state = _placed(s, blocked, good)
        blocked.attempt("app", "public", 9)
        assert s.verify(blocked_state, blocked)["ok"] is True, (
            "an attempt the policy blocked did not reach the internet: %r"
            % (s.verify(blocked_state, blocked)["problems"],))

        _refuses(s.DeployError, "a deployment that is a string",
                 lambda: s.verify("deployed", net), names=("str",))
        _refuses(s.DeployError, "a deployment with a field missing",
                 lambda: s.verify({"namespace": "northwind-app"}, net),
                 names=("running",))
        _refuses(s.DeployError, "a verdict that is not one of them",
                 lambda: s.verify(dict(deployed, verdict="done"), net), names=("done",))
        _refuses(s.DeployError, "installed that is not a tuple",
                 lambda: s.verify(dict(deployed, installed=[d0]), net),
                 names=("installed",))
        _refuses(s.DeployError, "a steps_done before zero",
                 lambda: s.verify(dict(deployed, steps_done=-1), net),
                 names=("steps_done",))

    def _rollback(s, net):
        good, absent = _deployable(net)
        steps, deployed = _placed(s, net, good)
        rolled = s.rollback(deployed)
        assert tuple(rolled) == s.DEPLOY_KEYS, (
            "a rollback answers with the five DEPLOY_KEYS: %r" % (tuple(rolled),))
        assert rolled == {"namespace": deployed["namespace"],
                          "installed": deployed["installed"], "running": (),
                          "steps_done": deployed["steps_done"],
                          "verdict": "rolled-back"}, (
            "a rollback stops everything, keeps what was installed, and says so: %r"
            % (rolled,))
        assert s.rollback(rolled) == rolled, (
            "rolling a rolled-back deployment back again is the same answer: %r vs %r"
            % (s.rollback(rolled), rolled))
        stopped = s.rollback({"namespace": "northwind-app", "installed": (), "running": (),
                              "steps_done": 0, "verdict": "refused"})
        assert stopped["verdict"] == "rolled-back" and stopped["running"] == (), (
            "even a refused plan can be rolled back: %r" % (stopped,))
        assert net.stats()["attempts"] == 0, (
            "rolling back reached out, and the world says %r" % (net.stats(),))
        _refuses(s.DeployError, "a deployment that is a string",
                 lambda: s.rollback("deployed"), names=("str",))
        _refuses(s.DeployError, "a deployment whose namespace is a number",
                 lambda: s.rollback(dict(deployed, namespace=2)), names=("namespace",))
        _refuses(s.DeployError, "a deployment with a field missing",
                 lambda: s.rollback({"namespace": "northwind-app"}), names=("verdict",))

    def _twice(s, net):
        good, absent = _deployable(net)
        first = s.validate(_manifest(good), net)
        assert s.validate(_manifest(good), net) == first, (
            "two runs of one manifest are two answers: %r vs %r"
            % (s.validate(_manifest(good), net), first))
        assert s.plan(_manifest(good), net) == s.plan(_manifest(good), net), (
            "two runs of one manifest are two plans: %r vs %r"
            % (s.plan(_manifest(good), net), s.plan(_manifest(good), net)))
        refused = s.validate(_manifest(good, namespace="contoso", replicas=0), net)
        assert s.validate(_manifest(good, namespace="contoso", replicas=0),
                          net) == refused, (
            "two runs of one refusal are two refusals: %r vs %r"
            % (s.validate(_manifest(good, namespace="contoso", replicas=0), net), refused))
        first_net = net.__class__.build(7)
        second_net = net.__class__.build(7)
        steps, _ = s.plan(_manifest(good), first_net)
        assert s.plan(_manifest(good), second_net) == (steps, ()), (
            "two basements of one seed are two plans: %r"
            % (s.plan(_manifest(good), second_net),))
        one = s.deploy(steps, first_net, "northwind-app", 2)
        two = s.deploy(steps, second_net, "northwind-app", 2)
        assert one == two, (
            "two runs of one deployment are two basements: %r vs %r" % (one, two))
        assert s.verify(one, first_net) == s.verify(two, second_net), (
            "two runs of one verification are two answers: %r vs %r"
            % (s.verify(one, first_net), s.verify(two, second_net)))
        assert s.rollback(one) == s.rollback(two), (
            "two runs of one rollback are two answers: %r vs %r"
            % (s.rollback(one), s.rollback(two)))

    import stage_02 as s
    import estate as world
    import network as netmod
    net = netmod.Network.build(7)
    _constants(s, world)
    _validate(s, world, net)
    _plan(s, net)
    _deploy(s, net)
    _rollback(s, net)
    _verify(s, net)
    _twice(s, net)

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "fde-from-scratch"

    CORPUS = (
        ("doc-1", "Bal tic  Steel", 123456, "EUR", 12, "PO-1001", ()),
        ("doc-2", "Iberia Logistics", 98765, "USD", 13, "PO-1002", ()),
        ("doc-3", "Northwind Parts", 123456, "EUR", 14, "PO-1003", ()),
        ("doc-4", "Oslo Fasteners", None, None, 15, "PO-1004", ("amount-missing",)),
        ("doc-5", "Danube Tooling", 765432, "EUR", 16, "PO-1005", ()),
        ("doc-6", "Baltic Steel Ltd", 23456, "EUR", 17, "PO-1006", ()),
        ("doc-7", "Aalborg Cement", None, "EUR", 5, "PO-0977", ("amount-ambiguous",)),
        ("doc-8", "Trondheim Verksted", 4500050, "SEK", 18, "PO-1007",
         ("currency-unknown",)),
    )

    VERDICTS_OF_CORPUS = (
        ("doc-1", "matched", "row-01", ()),
        ("doc-2", "matched", "row-02", ()),
        ("doc-3", "matched", "row-03", ()),
        ("doc-4", "unmatched", None, ("no-amount",)),
        ("doc-5", "matched", "row-05", ()),
        ("doc-6", "mismatch", "row-06", ("vendor",)),
        ("doc-7", "unmatched", None, ("no-amount",)),
        ("doc-8", "mismatch", "row-07", ("amount", "vendor", "day")),
    )

    ROW_OF = {"doc-1": "row-01", "doc-2": "row-02", "doc-3": "row-03", "doc-5": "row-05",
              "doc-6": "row-06", "doc-8": "row-07"}

    AMOUNTS = (
        ("1.234,56 EUR", 123456),
        ("1,234.56 EUR", 123456),
        ("1234,56 EUR", 123456),
        ("987.65 USD", 98765),
        ("234 EUR", 23400),
    )

    def _repo(start=None):
        for candidate_start in (os.environ.get("FDE_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set FDE_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _document(document_id, text, source="scanner-z", pages=1):
        """A document shaped the way the estate shapes them, around a text."""
        return {"id": document_id, "source": source, "pages": pages, "text": text,
                "scanned": True}

    def _invoice(po, vendor, amount, day):
        """The labelled lines of a scan, as the customer's scanner leaves them."""
        return ("INVOICE\n%s\nVendor: %s\nAmount: %s\nDate: %s\n"
                % (po, vendor, amount, day))

    def _row(row_id, po, vendor, cents, day, tenant, classification):
        """A row of the customer's store, shaped the way the estate shapes them."""
        return {"id": row_id, "tenant": tenant, "owner": "alan",
                "classification": classification, "po": po,
                "text": "%s invoice for %s" % (vendor, po), "amount_cents": cents,
                "day": day}

    def _constants(s, world):
        assert tuple(s.RECORD_KEYS) == ("id", "vendor", "amount_cents", "currency",
                                        "day", "po", "text"), (
            "a record is these seven fields in this order: %r" % (s.RECORD_KEYS,))
        assert tuple(s.PARSE_PROBLEMS) == ("amount-missing", "amount-ambiguous",
                                           "vendor-missing", "day-missing",
                                           "po-missing", "currency-unknown"), (
            "every problem prints in this order: %r" % (s.PARSE_PROBLEMS,))
        assert tuple(s.CURRENCIES) == ("EUR", "USD", "GBP"), (
            "the customer prices in these three currencies: %r" % (s.CURRENCIES,))
        assert tuple(s.VERDICTS) == ("matched", "mismatch", "unmatched"), (
            "the three verdicts, in this order: %r" % (s.VERDICTS,))
        assert tuple(s.MISMATCHES) == ("amount", "vendor", "day", "po"), (
            "a record may differ from its row on these fields, in this order: %r"
            % (s.MISMATCHES,))
        assert tuple(s.STORE_KEYS) == ("records", "postings", "counts", "acls"), (
            "the hybrid store is these four halves: %r" % (s.STORE_KEYS,))
        assert issubclass(s.EtlError, world.EstateError), (
            "EtlError must be a kind of estate.EstateError, and its bases are %r"
            % (s.EtlError.__mro__,))
        assert issubclass(s.EtlError, ValueError), (
            "a caller's `except ValueError` must still catch it: %r"
            % (s.EtlError.__mro__,))

    def _readings(s, world):
        estate = world.Estate.build(7)
        documents = {document["id"]: document for document in estate.documents()}
        for document_id, vendor, cents, currency, day, po, problems in CORPUS:
            document = documents[document_id]
            record, found = s.parse(document)
            assert tuple(record) == s.RECORD_KEYS, (
                "%s parsed into the keys %r, not a RECORD_KEYS record"
                % (document_id, tuple(record)))
            assert record["id"] == document_id, (
                "the record keeps the document's own id: %r" % (record["id"],))
            assert record["text"] == document["text"], (
                "the record keeps the scan's own text: %r" % (record["text"],))
            assert record["vendor"] == vendor, (
                "the vendor of %s is %r and it read %r"
                % (document_id, vendor, record["vendor"]))
            assert record["amount_cents"] == cents, (
                "the amount of %s is %r cents and it read %r"
                % (document_id, cents, record["amount_cents"]))
            assert record["currency"] == currency, (
                "the currency of %s is %r and it read %r"
                % (document_id, currency, record["currency"]))
            assert record["day"] == day, (
                "the day of %s is %r and it read %r" % (document_id, day, record["day"]))
            assert record["po"] == po, (
                "the PO of %s is %r and it read %r" % (document_id, po, record["po"]))
            assert tuple(found) == problems, (
                "the problems of %s, in PARSE_PROBLEMS order, are %r and it read %r"
                % (document_id, problems, tuple(found)))

    def _money(s, world):
        for amount, cents in AMOUNTS:
            record, problems = s.parse(_document(
                "doc-cents", _invoice("PO-2001", "Baltic Steel", amount, "12/03")))
            assert record["amount_cents"] == cents, (
                "the amount line %r holds %r cents and it read %r"
                % (amount, cents, record["amount_cents"]))
            assert tuple(problems) == (), (
                "the amount line %r is no problem at all and it read %r"
                % (amount, tuple(problems)))
        for ambiguous, currency in (("1.234 EUR", "EUR"), ("987.6 EUR", "EUR"),
                                    ("1234,567 EUR", "EUR"), ("12,", None)):
            record, problems = s.parse(_document(
                "doc-cents", _invoice("PO-2001", "Baltic Steel", ambiguous, "12/03")))
            assert record["amount_cents"] is None, (
                "the amount line %r does not settle on two decimals, and it read %r "
                "rather than refusing to guess" % (ambiguous, record["amount_cents"]))
            assert tuple(problems) == ("amount-ambiguous",), (
                "the amount line %r is amount-ambiguous and it read %r"
                % (ambiguous, tuple(problems)))
            assert record["currency"] == currency, (
                "an amount line with no code on it has no currency at all — %r read "
                "%r rather than an empty string" % (ambiguous, record["currency"]))
        for missing in ("", "TBD"):
            record, problems = s.parse(_document(
                "doc-cents", _invoice("PO-2001", "Baltic Steel", missing, "12/03")))
            assert record["amount_cents"] is None, (
                "an amount the scanner left unreadable is None and never a zero: %r "
                "read %r cents" % (missing, record["amount_cents"]))
            assert "amount-missing" in tuple(problems), (
                "the amount line %r is amount-missing and it read %r"
                % (missing, tuple(problems)))

    def _fields(s, world):
        def read(text):
            return s.parse(_document("doc-fields", text))

        record, problems = read(_invoice("PO-2002", "", "12,34 EUR", "12/03"))
        assert record["vendor"] is None, (
            "a Vendor line with nothing after it is a missing vendor, and it read %r"
            % (record["vendor"],))
        assert tuple(problems) == ("vendor-missing",), (
            "the empty vendor line is vendor-missing and it read %r"
            % (tuple(problems),))

        record, problems = read("INVOICE\nPO-2003\nAmount: 12,34 EUR\nDate: 12/03\n")
        assert tuple(problems) == ("vendor-missing",), (
            "a scan with no Vendor line at all is vendor-missing and it read %r"
            % (tuple(problems),))

        record, problems = read(_invoice("PO-2004", "Baltic Steel", "12,34 EUR", "12"))
        assert record["day"] is None, (
            "a Date that is not a DD/MM date is no day at all, and it read %r"
            % (record["day"],))
        assert tuple(problems) == ("day-missing",), (
            "the scan without a date is day-missing and it read %r" % (tuple(problems),))

        record, problems = read("INVOICE\nPO-2005\nVendor: Baltic Steel\n"
                                "Amount: 12,34 SEK\nDate: l3/O3\n")
        assert record["day"] == 13, (
            "the day's digits are repaired the way the PO's are, and it read %r"
            % (record["day"],))
        assert record["currency"] == "SEK", (
            "the currency is read as the scan wrote it, and it read %r"
            % (record["currency"],))
        assert tuple(problems) == ("currency-unknown",), (
            "a currency the customer does not price in is reported, and it read %r"
            % (tuple(problems),))

        record, problems = read(_invoice("PO-1O1I", "Baltic Steel", "12,34 EUR",
                                         "12/03"))
        assert record["po"] == "PO-1011", (
            "the PO's digit run is repaired — O is a zero and I is a one — and it "
            "read %r" % (record["po"],))

        record, problems = read(_invoice("PO-abc", "Baltic Steel", "12,34 EUR",
                                         "12/03"))
        assert record["po"] is None, (
            "a PO whose digit run repairs to no digits is no PO, and it read %r"
            % (record["po"],))
        assert tuple(problems) == ("po-missing",), (
            "the scan with no readable PO is po-missing and it read %r"
            % (tuple(problems),))

        record, problems = read(_invoice("PO-S002", "Baltic Steel", "12,34 EUR",
                                         "12/03"))
        assert record["po"] is None and tuple(problems) == ("po-missing",), (
            "the confusions the scanners make are a closed table — `S` is not a "
            "five — and this PO read %r as %r" % (record["po"], tuple(problems)))

        record, problems = read("INVOICE\nAmount: 12,3 ZZZ\n")
        assert tuple(problems) == ("amount-ambiguous", "vendor-missing", "day-missing",
                                   "po-missing", "currency-unknown"), (
            "a scan missing everything reports every problem it has, in "
            "PARSE_PROBLEMS order, and it read %r" % (tuple(problems),))
        assert (record["vendor"], record["amount_cents"], record["day"],
                record["po"]) == (None, None, None, None), (
            "a field the reading could not settle is None and not defaulted, and it "
            "read %r" % (record,))
        assert record["currency"] == "ZZZ", (
            "an unknown currency is still read as written, and it read %r"
            % (record["currency"],))

        _refuses(s.EtlError, "a document that is a string", lambda: s.parse("INVOICE"),
                 names=("str",))
        _refuses(s.EtlError, "a document with a key missing",
                 lambda: s.parse({"id": "doc-short"}), names=("id",))
        _refuses(s.EtlError, "a document whose text is not a string",
                 lambda: s.parse(_document("doc-broken", None)), names=("doc-broken",))

    def _tokens(s):
        assert tuple(s.tokens("Invoice, INVOICE: Baltic Steel!")) == ("invoice", "baltic",
                                                                     "steel"), (
            "tokens are lowercase and deduplicated in first-seen order, and it read %r"
            % (tuple(s.tokens("Invoice, INVOICE: Baltic Steel!")),))
        assert tuple(s.tokens("PO-1001 1.234,56")) == ("po1001", "123456"), (
            "punctuation is dropped rather than ending a word, and digits are kept: "
            "it read %r" % (tuple(s.tokens("PO-1001 1.234,56")),))
        assert tuple(s.tokens("Baltic steel BALTIC Steel steel")) == ("baltic", "steel"), (
            "a token repeats once whatever case it arrived in, and it read %r"
            % (tuple(s.tokens("Baltic steel BALTIC Steel steel")),))
        assert tuple(s.tokens("")) == () and tuple(s.tokens("... ,,, !!!")) == (), (
            "a text with no word in it has no token, and it read %r/%r"
            % (tuple(s.tokens("")), tuple(s.tokens("... ,,, !!!"))))
        assert (tuple(s.tokens("Invoice, INVOICE: Baltic Steel!"))
                == tuple(s.tokens("Invoice, INVOICE: Baltic Steel!"))), (
            "tokens is a function of its text")
        _refuses(s.EtlError, "a text that is not a string", lambda: s.tokens(1001),
                 names=("int",))

    def _reconcile(s, world):
        estate = world.Estate.build(7)
        documents = {document["id"]: document for document in estate.documents()}
        for document_id, verdict, row_id, detail in VERDICTS_OF_CORPUS:
            record, found = s.parse(documents[document_id])
            assert s.reconcile(record, estate) == (verdict, row_id, detail), (
                "%s reconciles as %r and it answered %r"
                % (document_id, (verdict, row_id, detail),
                   s.reconcile(record, estate)))
        twin, found = s.parse(documents["doc-3"])
        assert s.reconcile(twin, estate)[1] == "row-03", (
            "the customer's own duplicate rows — row-03 and row-25 both claim "
            "PO-1003 with the same amount — collapse to the lowest id, and it "
            "answered %r" % (s.reconcile(twin, estate)[1],))

        record, found = s.parse(_document("doc-nothing", "INVOICE\nVendor: X\nAmount:\n"))
        assert s.reconcile(record, estate) == ("unmatched", None, ("no-po",)), (
            "a record with neither a PO nor an amount is quarantined as no-po, and "
            "it answered %r" % (s.reconcile(record, estate),))
        record, found = s.parse(_document("doc-unreadable", _invoice(
            "PO-1001", "Baltic Steel", "", "12/03")))
        assert s.reconcile(record, estate) == ("unmatched", None, ("no-amount",)), (
            "a record whose amount the scanner left unreadable is quarantined as "
            "no-amount even though its row exists, and it answered %r"
            % (s.reconcile(record, estate),))
        record, found = s.parse(_document("doc-no-row", _invoice(
            "PO-9999", "Baltic Steel", "12,34 EUR", "12/03")))
        assert s.reconcile(record, estate) == ("unmatched", None, ("no-row",)), (
            "a record no row answers is quarantined as no-row, and it answered %r"
            % (s.reconcile(record, estate),))

        rows = (_row("row-90", "PO-3001", "Baltic Steel", 100000, 3, world.ESTATE_NAME,
                     "internal"),
                _row("row-91", "PO-3001", "Baltic Steel", 200000, 3, world.ESTATE_NAME,
                     "internal"))
        disputed = world.Estate(rows, ())
        claim, found = s.parse(_document("doc-claim", _invoice(
            "PO-3001", "Baltic Steel", "1000,00 EUR", "03/03")))
        _refuses(s.EtlError, "two rows that share a PO and disagree on the amount",
                 lambda: s.reconcile(claim, disputed),
                 names=("PO-3001", "row-90", "row-91"))

        agree = (_row("row-92", "PO-3002", "Baltic Steel", 100000, 3, world.ESTATE_NAME,
                      "internal"),
                 _row("row-93", "PO-3002", "Baltic Steel", 100000, 9, world.ESTATE_NAME,
                      "internal"))
        collapsed = world.Estate(agree, ())
        record, found = s.parse(_document("doc-collapse", _invoice(
            "PO-3002", "Baltic Steel", "1000,00 EUR", "03/03")))
        assert s.reconcile(record, collapsed) == ("matched", "row-92", ()), (
            "rows that share a PO and agree on the amount are one row — the lowest "
            "id — and the other one gets no second opinion: it answered %r"
            % (s.reconcile(record, collapsed),))

        _refuses(s.EtlError, "a record that is a string",
                 lambda: s.reconcile("doc-1", estate), names=("str",))
        _refuses(s.EtlError, "a record with a key missing",
                 lambda: s.reconcile({"id": "doc-1"}, estate), names=("id",))
        _refuses(s.EtlError, "something that is not an estate",
                 lambda: s.reconcile(twin, "the estate"), names=("record", "str"))

    def _store(s, world):
        estate = world.Estate.build(7)
        documents = estate.documents()
        before = estate.stats()
        store = s.hybrid_load(estate, documents)
        after = estate.stats()
        assert tuple(store) == s.STORE_KEYS, (
            "the store is a STORE_KEYS mapping, and it has %r" % (tuple(store),))
        records = store["records"]
        assert tuple(record["id"] for record in records) == tuple(sorted(ROW_OF)), (
            "the store holds the records that reconciled, in id order, and it holds %r"
            % (tuple(record["id"] for record in records),))
        for record in records:
            assert tuple(record) == s.RECORD_KEYS, (
                "every record in the store is a RECORD_KEYS record, and %r has %r"
                % (record["id"], tuple(record)))
        assert store["acls"] == {record_id: (estate.row(ROW_OF[record_id])["tenant"],
                                             estate.row(ROW_OF[record_id])["classification"])
                                 for record_id in ROW_OF}, (
            "a record's ACL is the (tenant, classification) of the row it reconciled "
            "to — a mismatch reconciled just as much as a matched — and the store "
            "says %r" % (store["acls"],))
        assert tuple(store["acls"]) == tuple(sorted(ROW_OF)), (
            "the ACLs are read record by record, in id order: %r"
            % (tuple(store["acls"]),))
        census = store["counts"]
        assert tuple(census) == s.VERDICTS, (
            "the census is read verdict by verdict, in VERDICTS order: %r"
            % (tuple(census),))
        assert {verdict: tuple(census[verdict]) for verdict in s.VERDICTS} == {
            "matched": ("doc-1", "doc-2", "doc-3", "doc-5"),
            "mismatch": ("doc-6", "doc-8"),
            "unmatched": ("doc-4", "doc-7")}, (
            "the census accounts for every document under its verdict, in id order, "
            "and it says %r" % (census,))
        assert census["unmatched"] == {"doc-4": ("amount-missing",),
                                       "doc-7": ("amount-ambiguous",)}, (
            "the census carries the problems of the documents it quarantined, and it "
            "says %r" % (census["unmatched"],))
        postings = store["postings"]
        for token, found in postings.items():
            assert tuple(found) == tuple(sorted(found)), (
                "a posting is a sorted tuple of record ids, and %r points at %r"
                % (token, found))
            assert set(found) <= set(ROW_OF), (
                "every posting points at a record the store holds, and %r points at %r"
                % (token, found))
        assert postings["steel"] == ("doc-1", "doc-6"), (
            "a posting names every searchable record whose text carries the word, and "
            "steel points at %r" % (postings.get("steel"),))
        assert postings["bal"] == ("doc-1",) and postings["baltic"] == ("doc-6",), (
            "the split vendor's halves are its own tokens: bal points at %r and "
            "baltic at %r" % (postings.get("bal"), postings.get("baltic")))
        assert postings["vendor"] == tuple(sorted(ROW_OF)), (
            "the postings are built over the records that reconciled and over nothing "
            "else: vendor points at %r" % (postings.get("vendor"),))
        assert tuple(postings) == tuple(sorted(postings)), (
            "the postings are read token by token, in token order: %r"
            % (tuple(postings),))
        assert store == s.hybrid_load(estate, estate.documents()), (
            "two loads of one estate are one store")
        assert s.hybrid_load(estate, tuple(reversed(documents))) == store, (
            "the store is a function of the estate and the corpus, and not of the "
            "order the documents happen to arrive in")
        assert after["queries"] == before["queries"], (
            "the load reads the rows through the estate's own accessors and asks it "
            "nothing else: its query count went from %d to %d"
            % (before["queries"], after["queries"]))
        assert (after["audits"], after["rows_returned"]) == (before["audits"],
                                                            before["rows_returned"]), (
            "a load writes nothing to the estate: its log went from %r to %r"
            % (before, after))
        _refuses(s.EtlError, "a corpus that is not a collection",
                 lambda: s.hybrid_load(estate, "documents"), names=("str",))
        _refuses(s.EtlError, "a corpus handed in as a mapping of documents",
                 lambda: s.hybrid_load(estate, {"doc-1": documents[0]}),
                 names=("dict",))
        _refuses(s.EtlError, "a corpus loaded from something that is not an estate",
                 lambda: s.hybrid_load("estate", documents), names=("corpus", "str"))
        _refuses(s.EtlError, "one document twice in one corpus",
                 lambda: s.hybrid_load(estate, (documents[0], documents[0])),
                 names=("doc-1",))

    def _report(s, world):
        estate = world.Estate.build(7)
        store = s.hybrid_load(estate, estate.documents())
        answer = s.report(store)
        assert tuple(answer) == ("counts", "by_verdict", "problems"), (
            "a report carries counts, by_verdict and problems, in that order: %r"
            % (tuple(answer),))
        assert tuple(answer["counts"]) == s.VERDICTS, (
            "the counts are counted verdict by verdict, in VERDICTS order: %r"
            % (tuple(answer["counts"]),))
        assert answer["counts"] == {"matched": 4, "mismatch": 2, "unmatched": 2}, (
            "the corpus reconciles to four matched, two mismatched and two "
            "quarantined, and the report counts %r" % (answer["counts"],))
        assert sum(answer["counts"].values()) == len(estate.documents()), (
            "the report counts every document exactly once, and it counted %d of %d"
            % (sum(answer["counts"].values()), len(estate.documents())))
        assert answer["by_verdict"] == {"matched": ("doc-1", "doc-2", "doc-3", "doc-5"),
                                        "mismatch": ("doc-6", "doc-8"),
                                        "unmatched": ("doc-4", "doc-7")}, (
            "the report names the documents of every verdict, the quarantined ones "
            "included, and it says %r" % (answer["by_verdict"],))
        assert tuple(answer["problems"]) == s.PARSE_PROBLEMS, (
            "the problems are reported problem by problem, in PARSE_PROBLEMS order: %r"
            % (tuple(answer["problems"]),))
        assert answer["problems"]["amount-missing"] == ("doc-4",), (
            "the scan with the empty amount line is reported as amount-missing, and "
            "it is reported as %r" % (answer["problems"]["amount-missing"],))
        assert answer["problems"]["amount-ambiguous"] == ("doc-7",), (
            "the scan whose amount line settles on three digits is reported as "
            "amount-ambiguous, and it is reported as %r"
            % (answer["problems"]["amount-ambiguous"],))
        assert answer["problems"]["currency-unknown"] == ("doc-8",), (
            "the scan written in a currency the customer does not price in is "
            "reported as currency-unknown, and it is reported as %r"
            % (answer["problems"]["currency-unknown"],))
        assert answer["problems"]["vendor-missing"] == (), (
            "a problem no document has is reported empty rather than dropped: %r"
            % (answer["problems"]["vendor-missing"],))

        rows = (_row("row-94", "PO-4001", "Baltic Steel", 100000, 3,
                     world.OTHER_TENANT, "internal"),)
        mine = world.Estate(rows, ())
        corpus = (_document("doc-z", _invoice("PO-4001", "Baltic Steel", "1000,00 SEK",
                                              "03/03")),
                  _document("doc-a", _invoice("PO-9999", "Baltic Steel", "1000,00 SEK",
                                              "03/03")))
        mine_store = s.hybrid_load(mine, corpus)
        assert mine_store["acls"] == {"doc-z": (world.OTHER_TENANT, "internal")}, (
            "the ACL is the row's own, whatever tenant that row belongs to, and the "
            "store says %r" % (mine_store["acls"],))
        answer = s.report(mine_store)
        assert answer["by_verdict"] == {"matched": ("doc-z",), "mismatch": (),
                                        "unmatched": ("doc-a",)}, (
            "a record that reconciled badly is still in the store's account and a "
            "record no row answers is still in the report, and it says %r"
            % (answer["by_verdict"],))
        assert answer["counts"] == {"matched": 1, "mismatch": 0, "unmatched": 1}, (
            "the report counts the corpus it was given, and it counted %r"
            % (answer["counts"],))
        assert answer["problems"]["currency-unknown"] == ("doc-a", "doc-z"), (
            "a document that reconciled and still carries a problem is named by that "
            "problem too, and the ids of one problem come back sorted whatever "
            "verdicts they fell under: it says %r"
            % (answer["problems"]["currency-unknown"],))

        _refuses(s.EtlError, "a store that is a string", lambda: s.report("store"),
                 names=("str",))
        _refuses(s.EtlError, "a store with one of its four halves missing",
                 lambda: s.report({key: store[key]
                                   for key in ("records", "postings", "counts")}),
                 names=("acls",))
        _refuses(s.EtlError, "a census with a verdict missing",
                 lambda: s.report(dict(store, counts={"matched": {}, "mismatch": {}})),
                 names=("unmatched",))
        _refuses(s.EtlError, "a census that is not a mapping",
                 lambda: s.report(dict(store, counts={"matched": {}, "mismatch": {},
                                                      "unmatched": ("doc-4",)})),
                 names=("unmatched",))

    def _twice(s, world):
        estate = world.Estate.build(7)
        documents = estate.documents()
        one = s.hybrid_load(estate, documents)
        two = s.hybrid_load(estate, estate.documents())
        assert one == two, (
            "two loads of one estate are one store: %r vs %r" % (one, two))
        assert s.report(one) == s.report(two), (
            "two loads of one estate report two reports: %r vs %r"
            % (s.report(one), s.report(two)))
        for document in documents:
            first = s.parse(document)
            second = s.parse(document)
            assert first == second, (
                "reading %s twice gives two readings: %r vs %r"
                % (document["id"], first, second))
            assert s.reconcile(first[0], estate) == s.reconcile(second[0], estate), (
                "reconciling %s twice gives two verdicts: %r vs %r"
                % (document["id"], s.reconcile(first[0], estate),
                   s.reconcile(second[0], estate)))

    import estate as world
    import stage_03 as s
    _constants(s, world)
    _readings(s, world)
    _money(s, world)
    _fields(s, world)
    _tokens(s)
    _reconcile(s, world)
    _store(s, world)
    _report(s, world)
    _twice(s, world)

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "fde-from-scratch"

    S4_AUDIENCE = "north-app"

    S4_HIT_KEYS = ("id", "score", "tokens")

    S4_SCORE_UNIT = 1

    S4_ABSTENTIONS = ("no-hits", "below-threshold", "all-refused")

    S4_MIN_SCORE = 2

    S4_ANSWER_KEYS = ("query", "citations", "texts", "refused", "abstained", "reason")

    S4_AUDIT_KEYS = ("tick", "actor", "action", "target", "verdict", "reason")

    def _repo(start=None):
        for candidate_start in (os.environ.get("FDE_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set FDE_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s4_rows():
        """Four of the customer's rows: two tenants, and one of them `restricted`.

        The second tenant is here on purpose — `contoso`'s row is the one a northwind
        administrator's clearance reaches and their tenant does not, so isolation is
        demonstrated by the fixture rather than assumed by it.
        """
        return (
            {"id": "row-01", "tenant": "northwind", "owner": "ada",
             "classification": "public", "po": "PO-2001",
             "text": "Baltic Steel invoice for PO-2001", "amount_cents": 123456, "day": 12},
            {"id": "row-02", "tenant": "northwind", "owner": "grace",
             "classification": "internal", "po": "PO-2002",
             "text": "Iberia Logistics invoice for PO-2002", "amount_cents": 98765, "day": 13},
            {"id": "row-03", "tenant": "contoso", "owner": "linus",
             "classification": "restricted", "po": "PO-2003",
             "text": "Contoso Supply invoice for PO-2003", "amount_cents": 500000, "day": 14},
            {"id": "row-04", "tenant": "northwind", "owner": "edsger",
             "classification": "confidential", "po": "PO-2004",
             "text": "Oslo Fasteners invoice for PO-2004", "amount_cents": 777, "day": 15},
        )

    def _s4_document(document_id, po, vendor, amount, day):
        """One clean scan: the four fields stage 3 reads, with none of the dirt."""
        return {"id": document_id, "source": "scan", "pages": 1,
                "text": "INVOICE\n%s\nVendor: %s\nAmount: %s EUR\nDate: %s\n"
                        % (po, vendor, amount, day),
                "scanned": True}

    def _s4_documents():
        """Four scans, one per row, each naming its own vendor and amount."""
        return (_s4_document("doc-a", "PO-2001", "Baltic Steel", "1.234,56", "12/03"),
                _s4_document("doc-b", "PO-2002", "Iberia Logistics", "987,65", "13/03"),
                _s4_document("doc-c", "PO-2003", "Contoso Supply", "5.000,00", "14/03"),
                _s4_document("doc-d", "PO-2004", "Oslo Fasteners", "7,77", "15/03"))

    def _s4_estate(world):
        """The fixture every section runs against: four scans reconciled to four rows."""
        return world.Estate(_s4_rows(), _s4_documents())

    def _s4_store(etl, world):
        """The estate and the store stage 3's own load builds for it."""
        estate = _s4_estate(world)
        return estate, etl.hybrid_load(estate, estate.documents())

    def _s4_idp(world):
        """A directory with one administrator at each of the customer's two tenants."""
        groups = ({"name": "north-auditors", "roles": ("admin",), "tenant": "northwind"},
                  {"name": "contoso-auditors", "roles": ("admin",), "tenant": "contoso"})
        users = ({"subject": "ada2", "name": "Ada Two", "groups": ("north-auditors",),
                  "tenant": "northwind", "active": True, "scim_version": 1},
                 {"subject": "linus2", "name": "Linus Two", "groups": ("contoso-auditors",),
                  "tenant": "contoso", "active": True, "scim_version": 1})
        return world.IdP(users, groups, "stage-four-secret")

    def _s4_person(auth, idp, subject, tick=0, lifetime=10):
        """A principal built the way the course builds one: verified claims, then stage 1."""
        claims = idp.verify(idp.assertion(subject, S4_AUDIENCE, tick, lifetime),
                            S4_AUDIENCE, tick + 1)
        return auth.principal(claims, idp)

    def _s4_plain(who, tenant, clearance=3, roles=("admin",)):
        """A principal no directory would issue: a tenant and a clearance, and nothing else.

        A hand-built principal is how the check asks what the tenant comparison is
        made of: `northwind-2` carries a clearance that reaches every row in the
        fixture and is still not the customer.
        """
        return {"subject": who, "groups": (), "roles": roles, "tenant": tenant,
                "clearance": clearance}

    def _s4_scrambled(store):
        """The same store with every part of it written the other way round.

        The ranking is a function of what a store *holds*, so a store whose records,
        index tuples and ACL map happen to be in the opposite order must answer the
        same rows in the same order.
        """
        return {"records": tuple(reversed(store["records"])),
                "postings": {token: tuple(reversed(store["postings"][token]))
                             for token in store["postings"]},
                "counts": store["counts"],
                "acls": {rid: store["acls"][rid]
                         for rid in sorted(store["acls"], reverse=True)}}

    def _s4_may(world, store, principal, record_id):
        """The check's own answer to "may this principal read this record", or the reason.

        Read out of the pair the store kept exactly the way stage 1's rule reads a
        row: the tenant first and exactly, then the classification's *position* in the
        customer's own order against the clearance.
        """
        tenant, classification = store["acls"][record_id]
        if tenant != principal["tenant"]:
            return "tenant"
        if world.CLASSIFICATIONS.index(classification) > principal["clearance"]:
            return "clearance"
        return None

    def _s4_split(world, store, principal, hits):
        """The check's own `(allowed, refusals)` for these hits, in the order they came."""
        allowed = []
        refusals = []
        for hit in hits:
            reason = _s4_may(world, store, principal, hit["id"])
            if reason is None:
                allowed.append(hit)
            else:
                refusals.append((hit["id"], reason))
        return tuple(allowed), tuple(refusals)

    def _s4_texts(store, citations):
        """The texts of the cited ids, read straight out of the store's records."""
        held = {record["id"]: record["text"] for record in store["records"]}
        return tuple(held[record_id] for record_id in citations)

    def _s4_constants(s, world):
        """The four constants and the two closed vocabularies, in their own order."""
        assert tuple(s.HIT_KEYS) == S4_HIT_KEYS, (
            "a hit carries the id, the score and the tokens it carries, in order, and the "
            "stage says %r" % (tuple(s.HIT_KEYS),))
        assert s.SCORE_UNIT == S4_SCORE_UNIT, (
            "a distinct query token a record carries is worth one point, and the stage says "
            "%r" % (s.SCORE_UNIT,))
        assert tuple(s.ABSTENTIONS) == S4_ABSTENTIONS, (
            "the three reasons are printed in the order they are consulted, and the stage "
            "says %r" % (tuple(s.ABSTENTIONS),))
        assert s.MIN_SCORE == S4_MIN_SCORE, (
            "the threshold between a weak ranking and an answer is %d, and the stage says "
            "%r" % (S4_MIN_SCORE, s.MIN_SCORE))
        assert tuple(s.ANSWER_KEYS) == S4_ANSWER_KEYS, (
            "an answer carries the query, the citations, their texts, the refusals, the "
            "abstention and its reason, in order, and the stage says %r"
            % (tuple(s.ANSWER_KEYS),))
        assert issubclass(s.RagError, world.EstateError), (
            "a caller's `except estate.EstateError` must still catch this stage's refusal, "
            "and %r is not one" % (s.RagError,))
        assert issubclass(s.RagError, ValueError), (
            "a shape the retrieval cannot read is a bad value, and %r is not one"
            % (s.RagError,))
        _refuses(s.RagError, "a retrieval over something that is not a store",
                 lambda: s.search("a store", "invoice", 1), names=("store",))

    def _s4_search(s, etl, world):
        """`search`: distinct tokens, the id tie-break, the index's order and the limit."""
        estate, store = _s4_store(etl, world)
        assert store["acls"] == {"doc-a": ("northwind", "public"),
                                 "doc-b": ("northwind", "internal"),
                                 "doc-c": ("contoso", "restricted"),
                                 "doc-d": ("northwind", "confidential")}, (
            "the fixture's premise changed: the store's ACLs are no longer the pairs stage "
            "3's reconciliation took from the rows, and they are %r" % (store["acls"],))
        every = s.search(store, "invoice", 10)
        assert tuple(hit["id"] for hit in every) == ("doc-a", "doc-b", "doc-c", "doc-d"), (
            "every record carrying the query's one token is a hit, ordered by id ascending, "
            "and this one answered %r" % (tuple(hit["id"] for hit in every),))
        assert all(tuple(hit) == S4_HIT_KEYS for hit in every), (
            "a hit carries %r, in order, and one of them carried %r"
            % (S4_HIT_KEYS, tuple(every[0])))
        assert all(hit["score"] == 1 and hit["tokens"] == ("invoice",) for hit in every), (
            "one token carried once is a score of one and a one-token list, and the hits "
            "came back %r" % (every,))
        assert all(hit["score"] == len(hit["tokens"]) * s.SCORE_UNIT for hit in every), (
            "a hit's score is `SCORE_UNIT` for every token it lists, and %r does not add up"
            % (every,))
        assert s.search(store, "invoice invoice", 10) == every, (
            "a token the query repeats is one distinct token, so the ranking does not "
            "change: %r" % (s.search(store, "invoice invoice", 10),))
        for empty in ("", "   ", "..."):
            assert s.search(store, empty, 10) == (), (
                "a query of no tokens retrieves nothing at all, and %r answered %r"
                % (empty, s.search(store, empty, 10)))
        assert s.search(store, "zebra", 10) == (), (
            "a query no record carries retrieves nothing, and it answered %r"
            % (s.search(store, "zebra", 10),))
        one = s.search(store, "po2001", 10)
        assert one == ({"id": "doc-a", "score": 1, "tokens": ("po2001",)},), (
            "a query one record carries is one hit, and it answered %r" % (one,))
        assert s.search(store, "po2001", 99) == one, (
            "a limit past the end of a ranking is the whole ranking, not an error: %r"
            % (s.search(store, "po2001", 99),))
        assert s.search(store, "po2001", 1) == one, (
            "a limit of exactly the ranking is the whole ranking: %r"
            % (s.search(store, "po2001", 1),))
        assert s.search(store, "po2001", 0) == (), (
            "a limit of zero is no rows rather than an error, and it answered %r"
            % (s.search(store, "po2001", 0),))
        assert s.search(store, "invoice oslo", 1) == (
            {"id": "doc-d", "score": 2, "tokens": ("invoice", "oslo")},), (
            "the limit is applied to the finished ranking rather than to the order the index "
            "handed the hits over in, and a limit of one answered %r"
            % (s.search(store, "invoice oslo", 1),))
        assert tuple(hit["id"] for hit in s.search(store, "invoice", 2)) == ("doc-a", "doc-b"), (
            "the limit is applied to the ranking last, so a limit of two is the best two: %r"
            % (tuple(hit["id"] for hit in s.search(store, "invoice", 2)),))
        assert s.search(store, "steel baltic", 10) == (
            {"id": "doc-a", "score": 2, "tokens": ("steel", "baltic")},), (
            "a hit's tokens are the query tokens it carries, in the order the query put "
            "them in, and it answered %r" % (s.search(store, "steel baltic", 10),))
        assert s.search(store, "baltic steel", 10) == (
            {"id": "doc-a", "score": 2, "tokens": ("baltic", "steel")},), (
            "the query's own order is what a hit's tokens follow, and it answered %r"
            % (s.search(store, "baltic steel", 10),))
        tie = s.search(store, "po2002 steel", 10)
        assert tie == ({"id": "doc-a", "score": 1, "tokens": ("steel",)},
                       {"id": "doc-b", "score": 1, "tokens": ("po2002",)}), (
            "two hits with one token each are ordered by id ascending rather than by the "
            "order the query or the index produced them in, and they came back %r" % (tie,))
        ranked = s.search(store, "oslo invoice", 10)
        assert [hit["id"] for hit in ranked] == ["doc-d", "doc-a", "doc-b", "doc-c"], (
            "the ranking is by score descending and then by id ascending, so a record "
            "carrying two of the query's tokens comes first, and it ranked %r"
            % ([hit["id"] for hit in ranked],))
        assert ranked[0] == {"id": "doc-d", "score": 2, "tokens": ("oslo", "invoice")}, (
            "the best hit carries both tokens in the query's order, and it carried %r"
            % (ranked[0],))
        scrambled = _s4_scrambled(store)
        for query in ("invoice", "oslo invoice", "po2003 invoice", "po2002 steel", "zebra"):
            assert s.search(scrambled, query, 10) == s.search(store, query, 10), (
                "the ranking is a function of what the store holds, and the same store "
                "written the other way round ranked %r differently" % (query,))
        _refuses(s.RagError, "a limit below zero",
                 lambda: s.search(store, "invoice", -1), names=("-1",))
        _refuses(s.RagError, "a limit that is not a whole number",
                 lambda: s.search(store, "invoice", "1"), names=("limit",))
        _refuses(s.RagError, "a limit that is a bool",
                 lambda: s.search(store, "invoice", True), names=("limit",))
        _refuses(s.RagError, "a query that is not a string",
                 lambda: s.search(store, 7, 1), names=("query",))
        assert estate.stats()["audits"] == 0, (
            "a retrieval wrote to the customer's audit trail: %r" % (estate.stats(),))

    def _s4_filter(s, auth, etl, world):
        """`filtered`: the tenant-then-clearance grid, stage 1's rule, and no text."""
        estate, store = _s4_store(etl, world)
        hits = s.search(store, "invoice", 10)
        admin = _s4_plain("ada2", "northwind")
        viewer = _s4_plain("grace", "northwind", clearance=0, roles=("viewer",))
        engineer = _s4_plain("ada", "northwind", clearance=2)
        other = _s4_plain("linus2", "contoso")
        outsider = _s4_plain("zoe", "northwind-2")
        for who in (admin, viewer, engineer, other, outsider):
            allowed, refusals = s.filtered(store, who, hits)
            want_allowed, want_refusals = _s4_split(world, store, who, hits)
            assert allowed == want_allowed, (
                "the rows %r may read are the rows whose ACL pair stage 1's rule does not "
                "refuse, and the filter allowed %r where the rule allows %r"
                % (who["subject"], allowed, want_allowed))
            assert refusals == want_refusals, (
                "the rows %r may not read are refused with stage 1's own reason, and the "
                "filter refused %r where the rule refuses %r"
                % (who["subject"], refusals, want_refusals))
        assert s.filtered(store, admin, hits) == (
            ({"id": "doc-a", "score": 1, "tokens": ("invoice",)},
             {"id": "doc-b", "score": 1, "tokens": ("invoice",)},
             {"id": "doc-d", "score": 1, "tokens": ("invoice",)}),
            (("doc-c", "tenant"),)), (
            "a northwind administrator's clearance reaches the contoso record's restricted "
            "classification and their tenant does not, so the refusal is `tenant`, and the "
            "filter answered %r" % (s.filtered(store, admin, hits),))
        assert s.filtered(store, other, hits) == (
            ({"id": "doc-c", "score": 1, "tokens": ("invoice",)},),
            (("doc-a", "tenant"), ("doc-b", "tenant"), ("doc-d", "tenant"))), (
            "the customer's second tenant is isolated in both directions: a contoso "
            "administrator reads the contoso record and is refused the three northwind ones "
            "for their tenant, and the filter answered %r"
            % (s.filtered(store, other, hits),))
        assert s.filtered(store, outsider, hits)[1] == (
            ("doc-a", "tenant"), ("doc-b", "tenant"), ("doc-c", "tenant"),
            ("doc-d", "tenant")), (
            "`northwind-2` is not `northwind`, so a clearance that reaches every row is "
            "still refused every row for its tenant, and it was %r"
            % (s.filtered(store, outsider, hits)[1],))
        assert s.filtered(store, admin, ()) == ((), ()), (
            "no hits is no answer and no refusal, and it answered %r"
            % (s.filtered(store, admin, ()),))
        assert s.filtered(store, admin, list(hits)) == s.filtered(store, admin, hits), (
            "the same hits as a list are the same hits, and they filtered to %r"
            % (s.filtered(store, admin, list(hits)),))
        ranked = s.search(store, "oslo invoice", 10)
        assert s.filtered(store, admin, ranked)[0] == (
            {"id": "doc-d", "score": 2, "tokens": ("oslo", "invoice")},
            {"id": "doc-a", "score": 1, "tokens": ("invoice",)},
            {"id": "doc-b", "score": 1, "tokens": ("invoice",)}), (
            "the allowed hits keep the ranking's order rather than the id order, and they "
            "came back %r" % (s.filtered(store, admin, ranked)[0],))
        _refuses(s.RagError, "a principal that is not a mapping",
                 lambda: s.filtered(store, "ada2", ()), names=("principal",))
        _refuses(s.RagError, "hits that are not a sequence",
                 lambda: s.filtered(store, admin, "abc"), names=("hits",))
        _refuses(s.RagError, "a hit that is not a HIT_KEYS record",
                 lambda: s.filtered(store, admin, ({"id": "doc-a"},)),
                 names=("score", "tokens"))
        thin = dict(store, acls={"doc-a": store["acls"]["doc-a"]})
        _refuses(s.RagError, "a hit the store keeps no ACL for",
                 lambda: s.filtered(thin, admin, hits), names=("doc-b",))
        half = dict(store, acls=dict(store["acls"]))
        half["acls"]["doc-a"] = ("northwind",)
        _refuses(s.RagError, "an ACL that is not a pair",
                 lambda: s.filtered(half, admin, hits), names=("doc-a",))
        numbered = dict(store, acls=dict(store["acls"]))
        numbered["acls"]["doc-a"] = (7, "public")
        _refuses(s.RagError, "an ACL whose tenant is not a string",
                 lambda: s.filtered(numbered, admin, hits), names=("doc-a",))
        spelled = dict(store, acls=dict(store["acls"]))
        spelled["acls"]["doc-a"] = ("northwind", 7)
        _refuses(s.RagError, "an ACL whose classification is not a string",
                 lambda: s.filtered(spelled, admin, hits), names=("doc-a",))
        secret = dict(store, acls=dict(store["acls"]))
        secret["acls"]["doc-a"] = ("northwind", "secret")
        _refuses(auth.AuthError,
                 "an ACL whose classification is not one of the customer's",
                 lambda: s.filtered(secret, admin, hits), names=("secret",))
        assert estate.stats()["audits"] == 0, (
            "a filter wrote to the customer's audit trail: %r" % (estate.stats(),))

    def _s4_species(s, etl, world):
        """The shapes a store, an answer and an audit are read as, and their refusals."""
        estate, store = _s4_store(etl, world)
        admin = _s4_plain("ada2", "northwind")
        reordered = {"acls": store["acls"], "records": store["records"],
                     "counts": store["counts"], "postings": store["postings"]}
        made = {"query": "invoice", "citations": (), "texts": (), "refused": (),
                "abstained": False, "reason": None}
        before = estate.stats()
        _refuses(s.RagError, "a store handed in with its four halves in another order",
                 lambda: s.search(reordered, "invoice", 1), names=("keys",))
        _refuses(s.RagError, "a store that is not a mapping",
                 lambda: s.filtered("a store", admin, ()), names=("store",))
        _refuses(s.RagError, "a store whose ACL map is not a mapping",
                 lambda: s.filtered(dict(store, acls=[]), admin, ()), names=("acls",))
        _refuses(s.RagError, "a store whose index is not a mapping",
                 lambda: s.search(dict(store, postings=()), "invoice", 1),
                 names=("postings",))
        _refuses(s.RagError, "an answer for an estate that is not one",
                 lambda: s.answer("an estate", admin, store, "invoice", 1, 5),
                 names=("Estate",))
        _refuses(s.RagError,
                 "an answer for an estate that is not one, over a store that is not one "
                 "either",
                 lambda: s.answer("an estate", admin, reordered, "invoice", 1, 5),
                 names=("Estate",))
        _refuses(s.RagError, "an answer with a negative limit",
                 lambda: s.answer(estate, admin, store, "invoice", -1, 5), names=("-1",))
        _refuses(s.RagError, "an answer with a query that is not a string",
                 lambda: s.answer(estate, admin, store, 7, 1, 5), names=("query",))
        _refuses(s.RagError, "an answer with a tick that is not a whole number",
                 lambda: s.answer(estate, admin, store, "invoice", 1, "5"), names=("tick",))
        _refuses(s.RagError, "an answer over a store whose halves are in another order",
                 lambda: s.answer(estate, admin, reordered, "invoice", 1, 5),
                 names=("keys",))
        _refuses(s.RagError, "an audit of an answer that is not a mapping",
                 lambda: s.audit_answer(estate, admin, "an answer", 5), names=("answer",))
        _refuses(s.RagError, "an audit of an answer missing a field",
                 lambda: s.audit_answer(estate, admin, {"query": "invoice"}, 5),
                 names=("citations",))
        _refuses(s.RagError, "an audit of an answer whose abstention is not a bool",
                 lambda: s.audit_answer(estate, admin, dict(made, abstained="no"), 5),
                 names=("abstained",))
        _refuses(s.RagError, "an audit of an answer whose citations are not a tuple",
                 lambda: s.audit_answer(estate, admin, dict(made, citations="doc-a"), 5),
                 names=("citations",))
        _refuses(s.RagError, "an audit for an estate that is not one",
                 lambda: s.audit_answer("an estate", admin, made, 5), names=("Estate",))
        _refuses(s.RagError, "an audit of a principal with no subject",
                 lambda: s.audit_answer(estate, {"tenant": "northwind"}, made, 5),
                 names=("subject",))
        _refuses(s.RagError, "an audit with a tick that is not a whole number",
                 lambda: s.audit_answer(estate, admin, made, "5"), names=("tick",))
        assert estate.stats() == before, (
            "a refused answer or audit wrote to the customer's estate anyway: %r"
            % (estate.stats(),))
        assert estate.stats()["audits"] == 0, (
            "a refusal wrote an audit line of its own: %r" % (estate.stats(),))

    def _s4_answer(s, etl, world):
        """`answer`: the filter before the limit, the three abstentions and their order."""
        estate, store = _s4_store(etl, world)
        admin = _s4_plain("ada2", "northwind")
        viewer = _s4_plain("grace", "northwind", clearance=0, roles=("viewer",))
        other = _s4_plain("linus2", "contoso")
        outsider = _s4_plain("zoe", "northwind-2")
        a = s.answer(estate, admin, store, "oslo invoice", 10, 5)
        assert tuple(a) == S4_ANSWER_KEYS, (
            "an answer carries %r, in order, and this one carried %r"
            % (S4_ANSWER_KEYS, tuple(a)))
        assert a["query"] == "oslo invoice", (
            "the answer carries the question it answered, and it carried %r" % (a["query"],))
        assert a["citations"] == ("doc-d", "doc-a", "doc-b"), (
            "the answer cites the best rows the caller may read, in rank order, and it cited "
            "%r" % (a["citations"],))
        assert a["texts"] == _s4_texts(store, a["citations"]), (
            "the texts are the cited records' own texts in that order, and they were %r"
            % (a["texts"],))
        assert a["refused"] == (("doc-c", "tenant"),), (
            "the rows the caller may not read are `(record id, reason)` pairs in rank order, "
            "and the answer refused %r" % (a["refused"],))
        assert a["abstained"] is False and a["reason"] is None, (
            "an answer that cited rows did not abstain, and this one answered %r/%r"
            % (a["abstained"], a["reason"]))
        narrow = s.answer(estate, admin, store, "po2003 invoice", 1, 5)
        assert narrow["citations"] == ("doc-a",), (
            "the filter runs over the whole ranking before the limit, so a limit of one "
            "cites the best row the caller may read and not the best row in the store: %r"
            % (narrow["citations"],))
        assert narrow["refused"] == (("doc-c", "tenant"),), (
            "a limit of one does not shorten the refusals the filter found in the whole "
            "ranking, and it reported %r" % (narrow["refused"],))
        assert narrow["abstained"] is False and narrow["reason"] is None, (
            "a limit of one is a citation and not an abstention, and it answered %r/%r"
            % (narrow["abstained"], narrow["reason"]))
        assert s.answer(estate, admin, store, "po2003 invoice", 2, 5)["citations"] == (
            "doc-a", "doc-b"), (
            "a limit of two is the best two rows the caller may read: %r"
            % (s.answer(estate, admin, store, "po2003 invoice", 2, 5)["citations"],))
        full = s.answer(estate, admin, store, "po2003 invoice", 3, 5)
        assert full["citations"] == ("doc-a", "doc-b", "doc-d"), (
            "a limit of three is every row the caller may read, and it cited %r"
            % (full["citations"],))
        assert s.answer(estate, admin, store, "po2003 invoice", 99, 5) == full, (
            "a limit past the ranking is the whole ranking, and it answered %r"
            % (s.answer(estate, admin, store, "po2003 invoice", 99, 5),))
        zero = s.answer(estate, admin, store, "oslo invoice", 0, 5)
        assert zero["citations"] == () and zero["texts"] == (), (
            "a caller who asked for no rows is cited nothing, and this one was cited %r"
            % (zero["citations"],))
        assert zero["abstained"] is False and zero["reason"] is None, (
            "a limit of zero is not a refusal, and the answer said %r/%r"
            % (zero["abstained"], zero["reason"]))
        assert zero["refused"] == (("doc-c", "tenant"),), (
            "a limit of zero still reports the whole ranking's refusals: %r"
            % (zero["refused"],))
        weak = s.answer(estate, admin, store, "invoice", 10, 5)
        assert weak["abstained"] is True and weak["reason"] == "below-threshold", (
            "no row carrying the query's one token reaches `MIN_SCORE`, so the answer "
            "abstains `below-threshold` rather than citing weak rows, and it said %r/%r"
            % (weak["abstained"], weak["reason"]))
        assert weak["citations"] == () and weak["texts"] == (), (
            "an abstention cites nothing, and this one cited %r" % (weak["citations"],))
        assert weak["refused"] == (("doc-c", "tenant"),), (
            "an abstention still reports what it refused: %r" % (weak["refused"],))
        for empty in ("zebra", "", "..."):
            nothing = s.answer(estate, admin, store, empty, 10, 5)
            assert nothing["abstained"] is True and nothing["reason"] == "no-hits", (
                "a query that retrieved nothing is `no-hits`, and %r answered %r/%r"
                % (empty, nothing["abstained"], nothing["reason"]))
            assert nothing["citations"] == () and nothing["refused"] == (), (
                "nothing retrieved is nothing cited and nothing refused, and %r answered %r"
                % (empty, nothing))
        refused = s.answer(estate, outsider, store, "oslo invoice", 10, 5)
        assert refused["abstained"] is True and refused["reason"] == "all-refused", (
            "a ranking every one of whose rows was refused is `all-refused`, and it said %r"
            % (refused["reason"],))
        assert refused["citations"] == (), (
            "an abstention over refused rows cites nothing: %r" % (refused["citations"],))
        both = s.answer(estate, outsider, store, "invoice", 10, 5)
        assert both["abstained"] is True and both["reason"] == "below-threshold", (
            "a ranking that is both too weak to answer with and entirely refused is "
            "`below-threshold`, because that is the reason decided first, and it said %r"
            % (both["reason"],))
        assert both["refused"] == (("doc-a", "tenant"), ("doc-b", "tenant"),
                                   ("doc-c", "tenant"), ("doc-d", "tenant")), (
            "an abstention still reports every refusal in the ranking's order: %r"
            % (both["refused"],))
        mixed = s.answer(estate, other, store, "oslo invoice", 10, 5)
        assert mixed["citations"] == ("doc-c",) and mixed["abstained"] is False, (
            "`MIN_SCORE` decides whether an answer abstains and is not a filter over the "
            "hits: one hit above it is enough to answer, so a contoso administrator is "
            "cited the contoso row while the better northwind rows are refused, and the "
            "answer said %r" % (mixed,))
        assert mixed["refused"] == (("doc-d", "tenant"), ("doc-a", "tenant"),
                                    ("doc-b", "tenant")), (
            "the refusals keep the ranking's order, the refused rows first: %r"
            % (mixed["refused"],))
        short = s.answer(estate, viewer, store, "po2003 invoice", 1, 5)
        assert short["citations"] == ("doc-a",), (
            "a viewer at clearance zero is cited the public row and nothing else: %r"
            % (short["citations"],))
        assert short["refused"] == (("doc-c", "tenant"), ("doc-b", "clearance"),
                                    ("doc-d", "clearance")), (
            "the refusals come back in rank order with stage 1's own reasons, and they were "
            "%r" % (short["refused"],))
        flags = estate.stats()
        assert flags["queries"] == 0 and flags["rows_returned"] == 0, (
            "an answer reads the store and never the estate's own unfiltered fetch, and the "
            "world's log says %r" % (flags,))
        lost = dict(store, records=tuple(record for record in store["records"]
                                         if record["id"] != "doc-d"))
        _refuses(s.RagError, "an answer over a store that lost a record its index still holds",
                 lambda: s.answer(estate, admin, lost, "oslo invoice", 10, 5),
                 names=("doc-d",))
        mute = dict(store, records=tuple(dict(record, text=None)
                                         if record["id"] == "doc-a" else record
                                         for record in store["records"]))
        _refuses(s.RagError, "an answer over a record whose text is not there",
                 lambda: s.answer(estate, admin, mute, "steel baltic", 10, 5),
                 names=("doc-a",))

    def _s4_audit(s, etl, world):
        """The one audit line per answer, what it carries, and what a refusal leaves."""
        estate, store = _s4_store(etl, world)
        admin = _s4_plain("ada2", "northwind")
        viewer = _s4_plain("grace", "northwind", clearance=0, roles=("viewer",))
        texts = tuple(record["text"] for record in store["records"])
        before = estate.stats()
        a = s.answer(estate, admin, store, "oslo invoice", 10, 5)
        after = estate.stats()
        assert after["audits"] == before["audits"] + 1, (
            "every answer leaves exactly one line in the customer's audit trail and this "
            "one left %d" % (after["audits"] - before["audits"],))
        assert after["queries"] == before["queries"], (
            "an answer queried the estate's own unfiltered fetch: %r" % (after,))
        line = estate.log()[-1]
        assert tuple(line) == S4_AUDIT_KEYS, (
            "an audit line carries %r, in order, and this one carried %r"
            % (S4_AUDIT_KEYS, tuple(line)))
        assert line == {"tick": 5, "actor": "ada2", "action": "answer",
                        "target": "oslo invoice", "verdict": "answered",
                        "reason": "3 used, 1 refused"}, (
            "the line carries who asked, that the stage answered, the question, and the "
            "rows used and refused as counts, and it wrote %r" % (line,))
        for text in texts:
            assert text not in str(tuple(line.values())), (
                "an audit line carries no row's text, and this one carries %r" % (text,))
        for record_id in ("doc-a", "doc-c"):
            assert record_id not in str(tuple(line.values())), (
                "an audit line carries counts rather than record ids, and this one carries "
                "%r" % (record_id,))
        assert s.audit_answer(estate, admin, a, 6) == {
            "tick": 6, "actor": "ada2", "action": "answer", "target": "oslo invoice",
            "verdict": "answered", "reason": "3 used, 1 refused"}, (
            "auditing an answer by hand writes the same line, and it wrote %r"
            % (s.audit_answer(estate, admin, a, 6),))
        assert estate.stats()["audits"] == after["audits"] + 1, (
            "an answered question audited twice wrote one line too few: %r"
            % (estate.stats(),))
        s.answer(estate, admin, store, "invoice", 10, 7)
        assert estate.log()[-1] == {"tick": 7, "actor": "ada2", "action": "answer",
                                    "target": "invoice", "verdict": "abstained",
                                    "reason": "0 used, 1 refused"}, (
            "an abstention is audited like any other answer, with the rows it used and the "
            "rows it refused, and it wrote %r" % (estate.log()[-1],))
        s.answer(estate, admin, store, "zebra", 10, 8)
        assert estate.log()[-1] == {"tick": 8, "actor": "ada2", "action": "answer",
                                    "target": "zebra", "verdict": "abstained",
                                    "reason": "0 used, 0 refused"}, (
            "an answer that retrieved nothing is still one audit line, with nothing used "
            "and nothing refused, and it wrote %r" % (estate.log()[-1],))
        s.answer(estate, viewer, store, "po2003 invoice", 1, 9)
        assert estate.log()[-1] == {"tick": 9, "actor": "grace", "action": "answer",
                                    "target": "po2003 invoice", "verdict": "answered",
                                    "reason": "1 used, 3 refused"}, (
            "the line reports what the filter refused over the whole ranking, not what the "
            "caller's limit reached, and it wrote %r" % (estate.log()[-1],))
        assert estate.stats()["audits"] == 5, (
            "five answers were asked and five lines are in the trail, and the estate counts "
            "%r" % (estate.stats(),))
        trace = estate.stats()
        _refuses(s.RagError, "an answer with a negative limit",
                 lambda: s.answer(estate, admin, store, "oslo invoice", -2, 9),
                 names=("-2",))
        _refuses(s.RagError, "an audit of an answer that is not one",
                 lambda: s.audit_answer(estate, admin, {"query": "oslo invoice"}, 9),
                 names=("citations",))
        assert estate.stats() == trace, (
            "a refused answer or audit left a trace in the customer's estate: %r"
            % (estate.stats(),))

    def _s4_isolation(s, auth, etl, world):
        """Two administrators the customer's own directory issued: one per tenant."""
        estate, store = _s4_store(etl, world)
        idp = _s4_idp(world)
        north = _s4_person(auth, idp, "ada2")
        contoso = _s4_person(auth, idp, "linus2")
        assert (north["tenant"], north["clearance"]) == ("northwind", 3), (
            "the fixture's premise changed: the northwind administrator is %r"
            % ((north["tenant"], north["clearance"]),))
        assert (contoso["tenant"], contoso["clearance"]) == ("contoso", 3), (
            "the fixture's premise changed: the contoso administrator is %r"
            % ((contoso["tenant"], contoso["clearance"]),))
        assert idp.stats()["verified"] == 2, (
            "both administrators were built from the directory's own verified claims, and "
            "the directory counts %r" % (idp.stats(),))
        hits = s.search(store, "invoice", 10)
        north_rows = tuple(hit["id"] for hit in s.filtered(store, north, hits)[0])
        contoso_rows = tuple(hit["id"] for hit in s.filtered(store, contoso, hits)[0])
        assert north_rows == ("doc-a", "doc-b", "doc-d"), (
            "the northwind administrator reads the northwind rows, and they filtered to %r"
            % (north_rows,))
        assert contoso_rows == ("doc-c",), (
            "the contoso administrator reads the contoso row, and they filtered to %r"
            % (contoso_rows,))
        assert not set(north_rows) & set(contoso_rows), (
            "two tenants must not share a single record, and these two share %r"
            % (sorted(set(north_rows) & set(contoso_rows)),))
        assert set(north_rows) | set(contoso_rows) == {record["id"]
                                                       for record in store["records"]}, (
            "between them the two tenants' administrators account for every record the "
            "store holds, and together they read %r" % (sorted(set(north_rows) |
                                                                set(contoso_rows)),))
        assert s.answer(estate, north, store, "invoice", 10, 1)["refused"] == (
            ("doc-c", "tenant"),), (
            "the northwind administrator's refusal of the contoso record is its tenant, "
            "and the answer refused %r"
            % (s.answer(estate, north, store, "invoice", 10, 1)["refused"],))
        assert s.answer(estate, contoso, store, "oslo invoice", 10, 1)["citations"] == (
            "doc-c",), (
            "the contoso administrator is cited the contoso record and nothing else, and "
            "the answer cited %r"
            % (s.answer(estate, contoso, store, "oslo invoice", 10, 1)["citations"],))
        refused = s.answer(estate, contoso, store, "oslo invoice", 10, 1)["refused"]
        assert refused == (("doc-d", "tenant"), ("doc-a", "tenant"), ("doc-b", "tenant")), (
            "every northwind row is refused to the contoso administrator for its tenant, "
            "and the answer refused %r" % (refused,))

    def _s4_workload(s, auth, etl, world):
        """One whole pass of the stage over fixtures built here, as one tuple."""
        estate, store = _s4_store(etl, world)
        idp = _s4_idp(world)
        answers = []
        for subject in ("ada2", "linus2"):
            who = _s4_person(auth, idp, subject)
            for query in ("invoice", "oslo invoice", "po2003 invoice", "po2002 steel",
                          "invoice invoice", "zebra", "..."):
                for limit in (0, 1, 10):
                    answer = s.answer(estate, who, store, query, limit, 3)
                    line = s.audit_answer(estate, who, answer, 4)
                    answers.append((subject, query, limit, tuple(answer),
                                    tuple(answer.values()), tuple(line),
                                    tuple(line.values())))
            answers.append(s.search(store, "oslo invoice", 10))
            answers.append(s.search(_s4_scrambled(store), "po2003 invoice", 2))
            answers.append(s.filtered(store, who, s.search(store, "invoice", 10)))
        answers.append(estate.stats())
        answers.append(estate.log())
        return tuple(answers)

    def _s4_twice(s, auth, etl, world):
        """The last section: one workload, two runs, one answer — the world's log included."""
        one = _s4_workload(s, auth, etl, world)
        two = _s4_workload(s, auth, etl, world)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function of "
            "its inputs: the world's own counters were %r and then %r" % (one[-2], two[-2]))

    import estate as world
    import stage_01 as auth
    import stage_03 as etl
    import stage_04 as s
    _s4_constants(s, world)
    _s4_search(s, etl, world)
    _s4_filter(s, auth, etl, world)
    _s4_species(s, etl, world)
    _s4_answer(s, etl, world)
    _s4_audit(s, etl, world)
    _s4_isolation(s, auth, etl, world)
    _s4_twice(s, auth, etl, world)

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "fde-from-scratch"

    S5_AUDIENCE = "north-app"

    S5_TOOL_KEYS = ("name", "verb", "table", "arguments", "limits")

    S5_VERBS = ("read", "write")

    S5_LEASE_KEYS = ("name", "expires_at", "redeemed")

    S5_REASONS = ("no-right", "no-lease", "lease-expired", "lease-redeemed", "rate-limited",
                  "bad-arguments", "unknown-tool", "read-only")

    S5_TOOLS = (
        {"name": "orders.read", "verb": "read", "table": "orders",
         "arguments": ("po",), "limits": 4},
        {"name": "orders.write", "verb": "write", "table": "orders",
         "arguments": ("po", "amount_cents"), "limits": 2},
        {"name": "invoices.read", "verb": "read", "table": "invoices",
         "arguments": ("source",), "limits": 3},
    )

    S5_SECRET = "northwind-credential-2f9c"

    S5_LEASES = {"orders.read": S5_SECRET + "-orders-read",
                 "orders.write": S5_SECRET + "-orders-write",
                 "invoices.read": S5_SECRET + "-invoices-read"}

    def _repo(start=None):
        for candidate_start in (os.environ.get("FDE_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set FDE_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    class _Ledger:
        """A vault double: it hands over the lease it was told to and remembers being asked.

        A vault is an argument of `call`, so the lease that comes back is data like any
        other. This is how the check reaches a lease a real vault would never mint — one
        already past its deadline, one already spent, one handed over for another name —
        without pretending that a real vault would hand one over.
        """

        def __init__(self, lease):
            self._lease = dict(lease)
            self.asked = []

        def lease(self, name, ttl, tick):
            """The one lease this double holds, whatever name it was asked for."""
            self.asked.append(("lease", name, tick))
            return dict(self._lease)

        def redeem(self, lease, tick):
            """The lease as redeemed, and a note that the redemption was asked for."""
            self.asked.append(("redeem", lease["name"], tick))
            return dict(lease, redeemed=True)

    def _person(one, idp, subject, tick=1):
        """A principal for `subject`, built from an assertion the directory signed."""
        claims = idp.verify(idp.assertion(subject, S5_AUDIENCE, 0, 10), S5_AUDIENCE, tick)
        return one.principal(claims, idp)

    def _rows_for(records, po):
        """The estate's own rows for one purchase order, read out of the world directly."""
        return tuple(row for row in records.rows() if row["po"] == po)

    def _documents_from(records, source):
        """The estate's own scanned invoices from one source, read out of the world."""
        return tuple(document for document in records.documents()
                     if document["source"] == source)

    def _snapshot(records):
        """The customer's rows as plain tuples, for comparing one run with the next."""
        return tuple(tuple(sorted(row.items())) for row in records.rows())

    def _one_call(s, estate, records, who, tools, vault, calls, name, args, tick):
        """One tool call, and the single audit line it must have written for itself.

        The line is checked at the call because every call writes exactly one: a call
        that wrote none and a call that wrote two are both bugs the customer's auditor
        finds, and both are easier to see here than in a total at the end.
        """
        before = len(records.log())
        result, reason = s.call(records, who, tools, vault, calls, name, args, tick)
        wrote = records.log()[before:]
        assert len(wrote) == 1, (
            "every call writes exactly one audit line, and the call to %r wrote %d"
            % (name, len(wrote)))
        line = wrote[0]
        assert tuple(line) == estate.AUDIT_KEYS, (
            "an audit line carries %r, not %r" % (tuple(line), estate.AUDIT_KEYS))
        assert line["tick"] == tick, (
            "the audit line does not carry the tick the call was made at: %r"
            % (line["tick"],))
        assert line["actor"] == who["subject"], (
            "the audit line does not name the subject the call was made for: %r"
            % (line["actor"],))
        assert line["action"] == name, (
            "the audit line does not name the tool that was called: %r" % (line["action"],))
        return result, reason, line

    def _refused(s, estate, records, who, tools, vault, calls, name, args, tick, want,
                 offender):
        """The refusal a call must answer, its one line, and the world left as it was.

        A refusal is the case this stage exists for, so it is checked the whole way down:
        a reason out of the closed vocabulary, an answer of nothing, `refused` on the
        line, the offender named on the line, and no trace in the world beyond the one
        line the contract asks for.
        """
        stats = records.stats()
        rows = _snapshot(records)
        before = len(records.log())
        result, reason, line = _one_call(s, estate, records, who, tools, vault, calls,
                                         name, args, tick)
        assert reason == want, (
            "the call to %r is refused as %r, and it answered %r" % (name, want, reason))
        assert reason in s.REASONS, (
            "a refusal answers %r, which is not one of the closed vocabulary %r"
            % (reason, s.REASONS))
        assert result is None, (
            "a refused call answers nothing, and the call to %r answered %r"
            % (name, result))
        assert line["verdict"] == "refused", (
            "a refused call carries the verdict %r, and refused is the verdict"
            % (line["verdict"],))
        assert line["reason"] == reason, (
            "the audit line's reason is %r and the refusal was %r"
            % (line["reason"], reason))
        assert offender in (line["action"], line["target"]), (
            "the refusal of %r does not name %r on its audit line: %r"
            % (name, offender, line))
        after = records.stats()
        assert after["queries"] == stats["queries"], (
            "a refused call fetched from the estate, and a refusal must not reach the table")
        assert after["rows_returned"] == stats["rows_returned"], (
            "a refused call read rows out of the estate, and a refusal must not read one")
        assert after["rows"] == stats["rows"] and after["documents"] == stats["documents"], (
            "a refused call changed the shape of the estate: %r" % (after,))
        assert _snapshot(records) == rows, (
            "a refused call changed the customer's rows, and nothing in this course writes "
            "the estate")
        assert len(records.log()) == before + 1 and after["audits"] == stats["audits"] + 1, (
            "a refused call writes the one audit line the contract asks for, and %d lines "
            "appeared" % (after["audits"] - stats["audits"],))
        return line

    def _constants(s, estate):
        """The stage's own vocabulary, and the catalogue over the estate's two tables."""
        assert tuple(s.TOOL_KEYS) == S5_TOOL_KEYS, (
            "a tool record's keys are %r, not %r" % (tuple(s.TOOL_KEYS), S5_TOOL_KEYS))
        assert tuple(s.VERBS) == S5_VERBS, (
            "the verbs are %r, not %r" % (tuple(s.VERBS), S5_VERBS))
        assert tuple(s.LEASE_KEYS) == S5_LEASE_KEYS, (
            "a lease's keys are %r, not %r" % (tuple(s.LEASE_KEYS), S5_LEASE_KEYS))
        assert tuple(s.REASONS) == S5_REASONS, (
            "the refusals are %r, not %r" % (tuple(s.REASONS), S5_REASONS))
        assert len(set(s.REASONS)) == len(S5_REASONS), (
            "the refusal vocabulary repeats itself: %r" % (s.REASONS,))
        assert "secret" not in " ".join(s.LEASE_KEYS), (
            "a lease carries %r, and a lease never carries the secret" % (s.LEASE_KEYS,))
        assert issubclass(s.MCPError, estate.EstateError), (
            "MCPError is not a kind of estate.EstateError, so a caller's except stops "
            "catching a broken course")
        assert issubclass(s.MCPError, ValueError), (
            "MCPError is not a kind of ValueError, and every refusal in the world is one")
        assert isinstance(s.TOOLS, tuple), (
            "the catalogue is a %s, and a catalogue is a tuple" % (type(s.TOOLS).__name__,))
        assert [tuple(tool) for tool in s.TOOLS] == [S5_TOOL_KEYS for _ in S5_TOOLS], (
            "the catalogue's tools carry %r, not %r"
            % ([tuple(tool) for tool in s.TOOLS], [S5_TOOL_KEYS for _ in S5_TOOLS]))
        assert tuple(dict(tool) for tool in s.TOOLS) == S5_TOOLS, (
            "the catalogue is not the three tools over this estate's own two tables: %r"
            % (tuple(dict(tool) for tool in s.TOOLS),))
        for tool in s.TOOLS:
            assert isinstance(tool["limits"], int) and not isinstance(tool["limits"], bool), (
                "the per-tick limit of %r is %r, and a limit is a whole number of calls"
                % (tool["name"], tool["limits"]))
            assert tool["limits"] > 0, (
                "the tool %r may never be called: its limit is %r"
                % (tool["name"], tool["limits"]))

    def _reading(s, estate):
        """The vault: what it hands over, what it refuses, and what it writes down."""
        vault = s.Vault(dict(S5_LEASES))
        assert tuple(vault.log()) == (), (
            "the vault keeps a line before it is asked anything: %r" % (vault.log(),))
        assert [vault.secret_of(name) for name in sorted(S5_LEASES)] == [
            S5_LEASES[name] for name in sorted(S5_LEASES)], (
            "the vault does not answer the secret it holds under a name")
        assert len({vault.secret_of(name) for name in S5_LEASES}) == len(S5_LEASES), (
            "two names answer one secret, and a vault holds one secret per name")

        minted = vault.lease("orders.read", 5, 10)
        assert tuple(minted) == s.LEASE_KEYS, (
            "a lease carries %r, not %r" % (tuple(minted), s.LEASE_KEYS))
        assert minted == {"name": "orders.read", "expires_at": 15, "redeemed": False}, (
            "a lease minted at tick 10 for 5 ticks is %r, and it expires at tick + ttl"
            % (minted,))
        assert S5_SECRET not in repr(minted), (
            "the lease carries the secret: %r" % (minted,))
        assert vault.log()[-1] == ("lease", "orders.read", 10, "leased"), (
            "the vault's line for a minted lease is %r" % (vault.log()[-1],))
        assert vault.lease("orders.read", 1, 0)["expires_at"] == 1, (
            "a lease minted at tick 0 for one tick expires at another tick")
        assert vault.lease("orders.read", 3, 7)["expires_at"] == 10, (
            "a lease's deadline is not the tick it was minted at plus its lifetime")

        live = vault.lease("orders.read", 4, 0)
        assert vault.redeem(live, 3) == {"name": "orders.read", "expires_at": 4,
                                         "redeemed": True}, (
            "redeeming a live lease does not mark it: the tick before its deadline is "
            "inside it")
        assert vault.log()[-1] == ("redeem", "orders.read", 3, "redeemed"), (
            "the vault's line for a redeemed lease is %r" % (vault.log()[-1],))
        late = vault.lease("orders.read", 4, 0)
        _refuses(s.MCPError, "a lease redeemed at its own deadline",
                 lambda: vault.redeem(late, 4), names=("orders.read", "4"))
        assert vault.log()[-1] == ("redeem", "orders.read", 4, "expired"), (
            "the tick at a lease's deadline is past it, and the vault's line says %r"
            % (vault.log()[-1],))

        spent = vault.lease("orders.read", 4, 0)
        assert vault.redeem(spent, 1)["redeemed"] is True, (
            "redeeming a minted lease does not mark it redeemed")
        _refuses(s.MCPError, "a lease redeemed twice",
                 lambda: vault.redeem(spent, 2), names=("orders.read", "redeemed"))
        assert vault.log()[-1] == ("redeem", "orders.read", 2, "spent"), (
            "the vault's line for a lease spent twice is %r" % (vault.log()[-1],))

        _refuses(s.MCPError, "a secret the vault does not hold",
                 lambda: vault.secret_of("payroll.read"), names=("payroll.read",))
        _refuses(s.MCPError, "a lease over a name the vault does not hold",
                 lambda: vault.lease("payroll.read", 4, 0), names=("payroll.read",))
        assert vault.log()[-1] == ("lease", "payroll.read", 0, "unknown"), (
            "the vault's line for a name it does not hold is %r" % (vault.log()[-1],))
        _refuses(s.MCPError, "a lease with no lifetime",
                 lambda: vault.lease("orders.read", 0, 0), names=("0",))
        _refuses(s.MCPError, "a lease with a negative lifetime",
                 lambda: vault.lease("orders.read", -3, 0), names=("-3",))
        _refuses(s.MCPError, "a lifetime that is not a count",
                 lambda: vault.lease("orders.read", "five", 0), names=("five",))
        _refuses(s.MCPError, "a vault built over something that is not a mapping",
                 lambda: s.Vault("orders.read"), names=("str",))
        _refuses(s.MCPError, "a lease that is not a lease record",
                 lambda: vault.redeem({"name": "orders.read"}, 1), names=("redeemed",))
        _refuses(s.MCPError, "a lease whose flag is not a flag",
                 lambda: vault.redeem(dict(minted, redeemed="no"), 1), names=("no",))
        _refuses(s.MCPError, "a tick that is not a whole number",
                 lambda: vault.redeem(minted, "1"), names=("1",))

        for line in vault.log():
            assert isinstance(line, tuple) and len(line) == 4, (
                "a line the vault kept is %r, not an (action, name, tick, verdict) line"
                % (line,))
            assert S5_SECRET not in repr(line), (
                "the vault wrote down the secret it holds: %r" % (line,))
            for secret in S5_LEASES.values():
                assert secret not in repr(line), (
                    "the vault wrote down one of its secrets: %r" % (line,))

    def _catalogue(s):
        """`describe`: the validated records, and every shape it must refuse by name."""
        catalogue = s.describe(s.TOOLS)
        assert isinstance(catalogue, tuple), (
            "the catalogue is a %s, and describe answers a tuple"
            % (type(catalogue).__name__,))
        assert [tuple(tool) for tool in catalogue] == [s.TOOL_KEYS for _ in catalogue], (
            "a described tool carries %r, not %r"
            % ([tuple(tool) for tool in catalogue], [s.TOOL_KEYS for _ in catalogue]))
        assert tuple(dict(tool) for tool in catalogue) == S5_TOOLS, (
            "describe does not answer the catalogue it was given: %r"
            % (tuple(dict(tool) for tool in catalogue),))
        assert [tool["name"] for tool in catalogue] == list(S5_LEASES), (
            "the catalogue's tool names are %r, not %r"
            % ([tool["name"] for tool in catalogue], list(S5_LEASES)))
        assert catalogue[0] is not s.TOOLS[0], (
            "describe answers the caller's own records, so a caller can rewrite the "
            "catalogue under it")
        _refuses(s.MCPError, "a catalogue that is not a tuple",
                 lambda: s.describe("orders.read"), names=("orders.read",))
        _refuses(s.MCPError, "a catalogue of things that are not records",
                 lambda: s.describe(("orders.read",)), names=("orders.read", "str"))
        _refuses(s.MCPError, "a tool missing its per-tick limit",
                 lambda: s.describe(({"name": "orders.read", "verb": "read",
                                      "table": "orders", "arguments": ("po",)},)),
                 names=("limits", ))
        _refuses(s.MCPError, "a tool whose verb this stage does not have",
                 lambda: s.describe((dict(S5_TOOLS[0], verb="delete"),)),
                 names=("orders.read", "delete"))
        _refuses(s.MCPError, "a tool over a table this estate does not have",
                 lambda: s.describe((dict(S5_TOOLS[0], table="payroll"),)),
                 names=("payroll",))
        _refuses(s.MCPError, "a tool with an argument this estate's tables do not have",
                 lambda: s.describe((dict(S5_TOOLS[0], arguments=("vendor",)),)),
                 names=("vendor",))
        _refuses(s.MCPError, "a tool whose limit is not a count",
                 lambda: s.describe((dict(S5_TOOLS[0], limits="many"),)), names=("many",))
        _refuses(s.MCPError, "a tool that may never be called",
                 lambda: s.describe((dict(S5_TOOLS[0], limits=0),)), names=("0",))
        _refuses(s.MCPError, "a tool whose arguments are one bare name",
                 lambda: s.describe((dict(S5_TOOLS[0], arguments="po"),)),
                 names=("po", "tuple"))

    def _rights(s, one, estate):
        """`authorized`: the principal's rights against the tool's own verb, never the verb."""
        records = estate.Estate.build(7)
        idp = estate.IdP.build(7)
        tools = {tool["name"]: tool for tool in s.describe(s.TOOLS)}
        edsger = _person(one, idp, "edsger")
        grace = _person(one, idp, "grace")
        barbara = _person(one, idp, "barbara")
        assert one.rights(grace) == ("rows:read",), (
            "this check's viewer is not the viewer the directory makes: %r"
            % (one.rights(grace),))
        assert one.rights(barbara) == (), (
            "this check's principal with no groups carries rights: %r"
            % (one.rights(barbara),))
        assert [s.authorized(edsger, tool) for tool in s.describe(s.TOOLS)] == [True, True,
                                                                                True], (
            "an admin may call every tool, and %r is refused one" % (edsger["subject"],))
        assert [s.authorized(barbara, tool) for tool in s.describe(s.TOOLS)] == [False,
                                                                                False,
                                                                                False], (
            "a principal with no rights may call no tool, and this one is allowed some")
        assert s.authorized(grace, tools["orders.read"]) is True, (
            "a viewer may call a read tool over the order table")
        assert s.authorized(grace, tools["invoices.read"]) is True, (
            "a viewer may call a read tool over the scanned invoices")
        assert s.authorized(grace, tools["orders.write"]) is False, (
            "a viewer is authorized to write, so the verb is being read as a permission")
        assert s.authorized(grace, dict(tools["orders.read"], verb="write")) is False, (
            "the same tool read as a write tool is authorized by a right the viewer does "
            "not hold")
        _refuses(s.MCPError, "a tool that is not a record",
                 lambda: s.authorized(grace, "orders.read"), names=("orders.read", "str"))
        _refuses(s.MCPError, "a tool whose verb this stage does not have",
                 lambda: s.authorized(grace, dict(tools["orders.read"], verb="delete")),
                 names=("delete",))
        _refuses(s.MCPError, "a principal that is not a mapping",
                 lambda: s.authorized("grace", tools["orders.read"]), names=("grace",))
        assert records.stats()["audits"] == 0 and records.stats()["queries"] == 0, (
            "asking about a right is not a call, and it wrote to the estate")

    def _counters(s):
        """`tick_calls` over the per-tick structures a caller could hand it."""
        assert s.tick_calls({}) == 0, (
            "an empty per-tick structure holds no calls, and it holds %r"
            % (s.tick_calls({}),))
        two_tools = {"orders.read": (7, 4), "invoices.read": (7, 2)}
        assert s.tick_calls(two_tools) == 6, (
            "a structure holding four calls to one tool and two to another holds six, and "
            "this one holds %r" % (s.tick_calls(two_tools),))
        _refuses(s.MCPError, "a per-tick structure that is not a mapping",
                 lambda: s.tick_calls([]), names=("list",))
        _refuses(s.MCPError, "an entry that is not a (tick, count) pair",
                 lambda: s.tick_calls({"orders.read": 2}), names=("orders.read", "2"))
        _refuses(s.MCPError, "an entry with three parts",
                 lambda: s.tick_calls({"orders.read": (7, 4, 1)}), names=("orders.read",))
        _refuses(s.MCPError, "an entry whose count is not a count",
                 lambda: s.tick_calls({"orders.read": (7, "four")}), names=("four",))
        _refuses(s.MCPError, "a structure keyed by something that is not a tool name",
                 lambda: s.tick_calls({7: (7, 4)}), names=("7",))

    def _allowed(s, one, estate):
        """An allowed call: the rows, the affected count, the budget, and one line each."""
        records = estate.Estate.build(7)
        idp = estate.IdP.build(7)
        edsger = _person(one, idp, "edsger")
        catalogue = s.describe(s.TOOLS)
        vault = s.Vault(dict(S5_LEASES))
        calls = {}
        rows = _snapshot(records)

        result, reason, line = _one_call(s, estate, records, edsger, catalogue, vault, calls,
                                         "orders.read", {"po": "PO-1001"}, 3)
        assert reason is None, (
            "an allowed call has no reason, and the call to orders.read answered %r"
            % (reason,))
        assert result == _rows_for(records, "PO-1001"), (
            "a read tool does not answer the rows its own argument selects: %r" % (result,))
        assert len(result) == 1, (
            "the read of one purchase order answered %d rows" % (len(result),))
        assert line["verdict"] == "allowed" and line["reason"] == "rows: 1", (
            "the audit line of an allowed read is %r, and it names the table it touched "
            "and the count it answered" % (line,))
        assert line["target"] == "orders", (
            "the audit line of an allowed call names %r rather than the table it touched"
            % (line["target"],))

        result, reason, line = _one_call(s, estate, records, edsger, catalogue, vault, calls,
                                         "invoices.read", {"source": "scanner-a"}, 3)
        assert reason is None and result == _documents_from(records, "scanner-a"), (
            "a read over the invoices answers the scanned documents its source selects: %r"
            % (result,))
        assert len(result) == 2 and line["reason"] == "rows: 2", (
            "the read of one scanner's invoices is %r, and the audit line says %r"
            % (result, line["reason"]))

        result, reason, line = _one_call(s, estate, records, edsger, catalogue, vault, calls,
                                         "orders.write", {"po": "PO-1003",
                                                          "amount_cents": 5000}, 3)
        assert reason is None, ("an admin's write is refused: %r" % (reason,))
        assert isinstance(result, int) and not isinstance(result, bool) and result == 2, (
            "a write answers the count of rows it affects, and the two rows that share "
            "PO-1003 make it %r" % (result,))
        assert line["reason"] == "rows affected: 2", (
            "the audit line of an allowed write is %r" % (line["reason"],))

        result, reason, line = _one_call(s, estate, records, edsger, catalogue, vault, calls,
                                         "orders.write", {"po": "PO-9999",
                                                          "amount_cents": 1}, 3)
        assert result == 0 and reason is None, (
            "a write over a purchase order nobody placed affects no row, and it answered "
            "%r with %r" % (result, reason))

        assert calls.get("orders.read") == (3, 1), (
            "the per-tick structure does not hold one call to orders.read at tick 3: %r"
            % (calls,))
        assert calls.get("invoices.read") == (3, 1), (
            "the per-tick structure does not hold one call to invoices.read at tick 3: %r"
            % (calls,))
        assert calls.get("orders.write") == (3, 2), (
            "the per-tick structure does not hold two calls to orders.write at tick 3: %r"
            % (calls,))
        assert s.tick_calls(calls) == 4, (
            "four calls happened and the structure holds %r" % (s.tick_calls(calls),))

        assert vault.log() == (("lease", "orders.read", 3, "leased"),
                               ("redeem", "orders.read", 3, "redeemed"),
                               ("lease", "invoices.read", 3, "leased"),
                               ("redeem", "invoices.read", 3, "redeemed"),
                               ("lease", "orders.write", 3, "leased"),
                               ("redeem", "orders.write", 3, "redeemed"),
                               ("lease", "orders.write", 3, "leased"),
                               ("redeem", "orders.write", 3, "redeemed")), (
            "an allowed call mints and redeems a lease over its own tool's name, and the "
            "vault's log is %r" % (vault.log(),))
        assert [line for line in vault.log()
                for secret in S5_LEASES.values() if secret in repr(line)] == [], (
            "the vault wrote a secret down while calls were made")
        assert _snapshot(records) == rows, (
            "the course wrote the customer's estate, and every call here only reads it")
        for line in records.log():
            assert S5_SECRET not in repr(line), (
                "a secret reached the estate's audit log: %r" % (line,))

    def _rejections(s, one, estate):
        """Every refusal `REASONS` names, in the order the contract decides them."""
        records = estate.Estate.build(7)
        idp = estate.IdP.build(7)
        catalogue = s.describe(s.TOOLS)
        edsger = _person(one, idp, "edsger")
        grace = _person(one, idp, "grace")
        barbara = _person(one, idp, "barbara")
        vault = s.Vault(dict(S5_LEASES))
        bare = s.Vault({"invoices.read": S5_LEASES["invoices.read"]})
        calls = {}
        rows = _snapshot(records)

        _refused(s, estate, records, edsger, catalogue, vault, calls, "payroll.read", {},
                 20, "unknown-tool", "payroll.read")
        assert calls == {}, (
            "a call to a tool that is not in the catalogue spent the per-tick budget: %r"
            % (calls,))
        assert vault.log() == (), (
            "a call to a tool that is not in the catalogue was sent to the vault: %r"
            % (vault.log(),))

        _refused(s, estate, records, barbara, catalogue, vault, calls, "orders.read",
                 {"po": "PO-1001"}, 20, "no-right", "orders.read")
        assert calls == {} and vault.log() == (), (
            "a call refused for want of a right spent a budget or a lease: %r, %r"
            % (calls, vault.log()))

        _refused(s, estate, records, grace, catalogue, vault, calls, "orders.write",
                 {"po": "PO-1001", "amount_cents": 1}, 20, "read-only", "orders.write")
        assert calls == {} and vault.log() == (), (
            "a write refused to a reader spent a budget or a lease: %r, %r"
            % (calls, vault.log()))
        _refused(s, estate, records, grace, catalogue, vault, calls, "orders.write",
                 {"nonsense": 1}, 20, "read-only", "orders.write")
        _refused(s, estate, records, barbara, catalogue, vault, calls, "payroll.read", {},
                 20, "unknown-tool", "payroll.read")

        _refused(s, estate, records, edsger, catalogue, bare, calls, "orders.read",
                 {"po": "PO-1001"}, 20, "no-lease", "orders.read")
        assert calls == {}, (
            "a call the vault would not mint a lease for spent the per-tick budget: %r"
            % (calls,))
        assert bare.log() == (("lease", "orders.read", 20, "unknown"),), (
            "a vault asked for a name it does not hold keeps the line %r" % (bare.log(),))

        dead = _Ledger({"name": "orders.read", "expires_at": 20, "redeemed": False})
        _refused(s, estate, records, edsger, catalogue, dead, calls, "orders.read",
                 {"po": "PO-1001"}, 20, "lease-expired", "orders.read")
        assert dead.asked == [("lease", "orders.read", 20)], (
            "a lease past its deadline was redeemed anyway: %r" % (dead.asked,))
        assert calls == {}, (
            "a call with a lease past its deadline spent the per-tick budget: %r" % (calls,))
        almost = _Ledger({"name": "orders.read", "expires_at": 21, "redeemed": False})
        result, reason, line = _one_call(s, estate, records, edsger, catalogue, almost,
                                         calls, "orders.read", {"po": "PO-1001"}, 20)
        assert reason is None and result == _rows_for(records, "PO-1001"), (
            "a lease that expires at the next tick is live at this one, and the call "
            "answered %r with %r" % (reason, result))
        assert almost.asked == [("lease", "orders.read", 20), ("redeem", "orders.read", 20)], (
            "a live lease is redeemed before the work: %r" % (almost.asked,))

        stale = _Ledger({"name": "orders.read", "expires_at": 40, "redeemed": True})
        _refused(s, estate, records, edsger, catalogue, stale, calls, "orders.read",
                 {"po": "PO-1001"}, 30, "lease-redeemed", "orders.read")
        assert stale.asked == [("lease", "orders.read", 30)], (
            "a lease already spent was redeemed again: %r" % (stale.asked,))
        wrong = _Ledger({"name": "invoices.read", "expires_at": 40, "redeemed": False})
        _refuses(s.MCPError, "a lease handed over for another name",
                 lambda: s.call(records, edsger, catalogue, wrong, calls, "orders.read",
                                {"po": "PO-1001"}, 30),
                 names=("invoices.read", "orders.read"))

        _refused(s, estate, records, edsger, catalogue, vault, calls, "orders.read",
                 {"nonsense": 1}, 30, "bad-arguments", "nonsense")
        _refused(s, estate, records, edsger, catalogue, vault, calls, "orders.read", {},
                 30, "bad-arguments", "po")
        _refused(s, estate, records, edsger, catalogue, vault, calls, "orders.read",
                 {"po": 7}, 30, "bad-arguments", "po")
        _refused(s, estate, records, edsger, catalogue, vault, calls, "orders.read",
                 {"po": ""}, 30, "bad-arguments", "po")
        _refused(s, estate, records, edsger, catalogue, vault, calls, "orders.read",
                 {"po": "PO-1001", "day": 12}, 30, "bad-arguments", "day")
        _refused(s, estate, records, edsger, catalogue, vault, calls, "orders.write",
                 {"po": "PO-1001", "amount_cents": 0}, 30, "bad-arguments", "amount_cents")
        _refused(s, estate, records, edsger, catalogue, vault, calls, "orders.write",
                 {"po": "PO-1001", "amount_cents": -5}, 30, "bad-arguments", "amount_cents")
        _refused(s, estate, records, edsger, catalogue, vault, calls, "orders.write",
                 {"po": "PO-1001", "amount_cents": True}, 30, "bad-arguments", "amount_cents")
        _refused(s, estate, records, edsger, catalogue, vault, calls, "orders.write",
                 {"po": "PO-1001", "amount_cents": "500"}, 30, "bad-arguments",
                 "amount_cents")
        _refused(s, estate, records, edsger, catalogue, vault, calls, "invoices.read",
                 {"source": "scanner-a", "po": "PO-1001"}, 30, "bad-arguments", "po")
        _refuses(s.MCPError, "arguments that are not a mapping",
                 lambda: s.call(records, edsger, catalogue, vault, calls, "orders.read",
                                "po=PO-1001", 30), names=("str",))

        for attempt in range(4):
            _refused(s, estate, records, edsger, catalogue, vault, calls, "orders.read",
                     {"nonsense": attempt}, 40, "bad-arguments", "nonsense")
        assert calls.get("orders.read") == (40, 0), (
            "four calls refused on their arguments left the budget at %r, and a refused "
            "call gives its count back" % (calls.get("orders.read"),))
        assert s.tick_calls(calls) == 0, (
            "the per-tick structure holds %r calls after four refusals that did no work"
            % (s.tick_calls(calls),))
        result, reason, line = _one_call(s, estate, records, edsger, catalogue, vault,
                                         calls, "orders.read", {"po": "PO-1001"}, 40)
        assert reason is None and s.tick_calls(calls) == 1, (
            "the budget four refused calls gave back was not spendable: %r, %r"
            % (reason, calls))

        limit = [tool for tool in catalogue if tool["name"] == "orders.read"][0]["limits"]
        for attempt in range(limit):
            result, reason, line = _one_call(s, estate, records, edsger, catalogue, vault,
                                             calls, "orders.read", {"po": "PO-1001"}, 50)
            assert reason is None, (
                "the call at number %d of a limit of %d was refused: %r"
                % (attempt + 1, limit, reason))
        assert s.tick_calls(calls) == limit, (
            "the per-tick limit of %d allowed %r calls" % (limit, s.tick_calls(calls)))
        _refused(s, estate, records, edsger, catalogue, vault, calls, "orders.read",
                 {"po": "PO-1001"}, 50, "rate-limited", "orders.read")
        assert s.tick_calls(calls) == limit, (
            "a call refused by the rate limit left the budget at %r, and the refused call "
            "gives its count back" % (s.tick_calls(calls),))
        assert vault.log()[-2:] == (("lease", "orders.read", 50, "leased"),
                                    ("redeem", "orders.read", 50, "redeemed")), (
            "a call refused by the rate limit did not spend a lease, and the lease is "
            "spent before the count is: %r" % (vault.log()[-4:],))
        _refused(s, estate, records, edsger, catalogue, vault, calls, "orders.read",
                 {"nonsense": 1}, 50, "rate-limited", "orders.read")

        result, reason, line = _one_call(s, estate, records, edsger, catalogue, vault,
                                         calls, "orders.read", {"po": "PO-1001"}, 51)
        assert reason is None, (
            "the next tick does not end the budget's memory: %r" % (reason,))
        assert calls.get("orders.read") == (51, 1), (
            "the per-tick structure still holds the calls of the tick before: %r" % (calls,))
        for attempt in range(limit - 1):
            result, reason, line = _one_call(s, estate, records, edsger, catalogue, vault,
                                             calls, "orders.read", {"po": "PO-1001"}, 51)
            assert reason is None, (
                "the call at number %d of a fresh tick's limit was refused: %r"
                % (attempt + 2, reason))
        _refused(s, estate, records, edsger, catalogue, vault, calls, "orders.read",
                 {"po": "PO-1001"}, 51, "rate-limited", "orders.read")
        result, reason, line = _one_call(s, estate, records, edsger, catalogue, vault,
                                         calls, "invoices.read", {"source": "scanner-a"}, 51)
        assert reason is None, (
            "a second tool is refused by the first tool's budget, and two tools never "
            "share one: %r" % (reason,))
        assert s.tick_calls(calls) == limit + 1, (
            "the structure holds the calls of two tools in one tick, and it holds %r"
            % (s.tick_calls(calls),))

        _refuses(s.MCPError, "a call with a per-tick structure that is not a mapping",
                 lambda: s.call(records, edsger, catalogue, vault, [], "orders.read",
                                {"po": "PO-1001"}, 60), names=("list",))
        _refuses(s.MCPError, "a call to a tool named by something that is not a name",
                 lambda: s.call(records, edsger, catalogue, vault, calls, 7, {}, 60),
                 names=("7",))
        _refuses(s.MCPError, "a call at a tick that is not a whole number",
                 lambda: s.call(records, edsger, catalogue, vault, calls, "orders.read",
                                {"po": "PO-1001"}, "60"), names=("60",))
        _refuses(s.MCPError, "a call for somebody who is not a principal",
                 lambda: s.call(records, "edsger", catalogue, vault, calls, "orders.read",
                                {"po": "PO-1001"}, 60), names=("edsger",))
        _refuses(s.MCPError, "a call to an estate that answers nothing",
                 lambda: s.call(object(), edsger, catalogue, vault, calls, "orders.read",
                                {"po": "PO-1001"}, 60), names=("object",))
        _refuses(s.MCPError, "a call with a vault that answers nothing",
                 lambda: s.call(records, edsger, catalogue, object(), calls, "orders.read",
                                {"po": "PO-1001"}, 60), names=("object",))
        _refuses(s.MCPError, "a call with a catalogue that is not a catalogue",
                 lambda: s.call(records, edsger, "orders.read", vault, calls, "orders.read",
                                {"po": "PO-1001"}, 60), names=("orders.read",))

        assert _snapshot(records) == rows, (
            "the whole workload wrote the customer's estate, and this course only reads it")
        assert idp.stats()["verified"] == 3 and idp.stats()["assertions"] == 3, (
            "a call went back to the directory for something the principal already "
            "carries: %r" % (idp.stats(),))
        assert records.stats()["queries"] == 0 and records.stats()["rows_returned"] == 0, (
            "a call fetched through the estate's own unfiltered query, and a tool reads "
            "the records its own argument selects")
        for line in records.log():
            assert line["reason"] in s.REASONS or line["verdict"] == "allowed", (
                "an audit line carries the reason %r, which is neither a refusal nor an "
                "allowed call" % (line["reason"],))
            assert S5_SECRET not in repr(line), (
                "a secret reached the estate's audit log: %r" % (line,))
            for secret in S5_LEASES.values():
                assert secret not in repr(line), (
                    "one of the vault's secrets reached the estate's audit log: %r"
                    % (line,))
        for line in vault.log():
            assert S5_SECRET not in repr(line), (
                "the vault wrote a secret down: %r" % (line,))

    def _found(result):
        """A call's answer as plain data, so two runs can be compared on it."""
        if isinstance(result, (tuple, list)):
            return tuple(tuple(sorted(record.items())) for record in result)
        return result

    def _twice(s, one, estate):
        """The whole workload, run twice: one fixture, one transcript, one answer."""
        def workload():
            records = estate.Estate.build(7)
            idp = estate.IdP.build(7)
            edsger = _person(one, idp, "edsger")
            grace = _person(one, idp, "grace")
            catalogue = s.describe(s.TOOLS)
            vault = s.Vault(dict(S5_LEASES))
            calls = {}
            transcript = []
            for name, args, who, tick in (
                    ("orders.read", {"po": "PO-1001"}, edsger, 3),
                    ("orders.write", {"po": "PO-1003", "amount_cents": 7}, edsger, 3),
                    ("orders.write", {"po": "PO-1003"}, edsger, 3),
                    ("orders.read", {"nonsense": 1}, edsger, 4),
                    ("orders.write", {"po": "PO-1001", "amount_cents": 3}, grace, 4),
                    ("nope.read", {}, edsger, 4),
                    ("invoices.read", {"source": "scanner-b"}, grace, 4),
                    ("orders.read", {"po": "PO-9999"}, edsger, 5)):
                result, reason = s.call(records, who, catalogue, vault, calls, name, args,
                                        tick)
                transcript.append((name, reason, _found(result)))
            transcript.append(("calls", tuple(sorted(calls.items()))))
            transcript.append(("held", s.tick_calls(calls)))
            transcript.append(("vault", tuple(vault.log())))
            transcript.append(("audit", tuple(tuple(line[key] for key in estate.AUDIT_KEYS)
                                              for line in records.log())))
            transcript.append(("rows", _snapshot(records)))
            return tuple(transcript)

        first = workload()
        second = workload()
        assert first == second, (
            "the same workload run twice answered differently, so this stage is not a "
            "function of its inputs")

    import estate
    import stage_01 as one
    import stage_05 as s

    _constants(s, estate)
    _reading(s, estate)
    _catalogue(s)
    _rights(s, one, estate)
    _counters(s)
    _allowed(s, one, estate)
    _rejections(s, one, estate)
    _twice(s, one, estate)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "fde-from-scratch"

    CARD = "4111 1111 1111 1111"

    BAD_CARD = "4111 1111 1111 1112"

    SSN = "123-45-6789"

    EMAIL = "ada@example.com"

    PHONE = "+34 600 123 456"

    TEXT = "Call %s about card %s or write to %s, tel %s." % (SSN, CARD, EMAIL, PHONE)

    MASKED = ("Call [[ssn:1]] about card [[card:1]] or write to [[email:1]], "
              "tel [[phone:1]].")

    SPANS = (
        {"kind": "ssn", "start": 5, "end": 16, "value": SSN},
        {"kind": "card", "start": 28, "end": 47, "value": CARD},
        {"kind": "email", "start": 60, "end": 75, "value": EMAIL},
        {"kind": "phone", "start": 81, "end": 96, "value": PHONE},
    )

    PAIRS = (("[[card:1]]", CARD), ("[[email:1]]", EMAIL), ("[[phone:1]]", PHONE),
             ("[[ssn:1]]", SSN))

    SORTED_KINDS = ("card", "email", "phone", "ssn")

    ONE_RUN = "111-11-1111-1111-117"          # sixteen digits, checksum good, an SSN inside

    SEVENTEEN = "41111111111111113"           # seventeen digits that pass their own checksum

    SEVENTEEN_SPAN = "ref %s end" % (SEVENTEEN,)

    FOUR_KINDS_REASON = "kinds=card,email,phone,ssn; masked=4; restored=4; leaks=0"

    def _repo(start=None):
        for candidate_start in (os.environ.get("FDE_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set FDE_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _ssns(count):
        """`count` distinct identity numbers, each in the one shape that is an SSN."""
        return tuple("999-99-%04d" % (index + 1,) for index in range(count))

    def _constants(s, world):
        assert tuple(s.KINDS) == ("ssn", "card", "email", "phone"), (
            "the four kinds, in this order, are what a masker keys its counters by: %r"
            % (s.KINDS,))
        assert tuple(s.DETECTION_KEYS) == ("kind", "start", "end", "value"), (
            "a detection is the kind, the span and the value it found, in this order: %r"
            % (s.DETECTION_KEYS,))
        assert s.PLACEHOLDER == "[[%s:%d]]", (
            "a placeholder carries the kind and a counter and nothing else: %r"
            % (s.PLACEHOLDER,))
        assert s.PLACEHOLDER % ("ssn", 1) == "[[ssn:1]]", (
            "the placeholder of the first identity number of a masker: %r"
            % (s.PLACEHOLDER % ("ssn", 1),))
        assert tuple(s.GUARD_KEYS) == ("masked", "mapping", "kinds", "leaks"), (
            "a forwarded call is recorded as what was sent, what it mapped, the kinds and "
            "the leaks: %r" % (s.GUARD_KEYS,))
        assert issubclass(s.GuardError, world.EstateError), (
            "GuardError must be a kind of estate.EstateError, and its bases are %r"
            % (s.GuardError.__mro__,))
        assert issubclass(s.GuardError, ValueError), (
            "a caller's `except ValueError` must still catch it: %r"
            % (s.GuardError.__mro__,))

    def _digits(s):
        assert s.digits("4111 1111-1111 x") == "411111111111", (
            "spaces and dashes are not digits and are dropped: %r"
            % (s.digits("4111 1111-1111 x"),))
        assert s.digits("O0Il1") == "01", (
            "the letters a scanner confuses with numerals are letters: %r"
            % (s.digits("O0Il1"),))
        assert s.digits("no numerals at all") == "", (
            "a text with no digit in it has no digits: %r"
            % (s.digits("no numerals at all"),))
        assert s.digits("") == "", (
            "the digits of nothing are nothing: %r" % (s.digits(""),))
        assert s.digits("\u0663") == "", (
            "only the ten the world writes are digits here: %r" % (s.digits("\u0663"),))
        _refuses(s.GuardError, "the digits of a number", lambda: s.digits(4111),
                 names=("int",))
        _refuses(s.GuardError, "the digits of nothing at all", lambda: s.digits(None),
                 names=("NoneType",))

    def _luhn(s):
        assert s.luhn("4111111111111111") is True, (
            "a well formed card passes its own check digit: %r"
            % (s.luhn("4111111111111111"),))
        assert s.luhn("4111111111111112") is False, (
            "one digit changed and the checksum fails: %r"
            % (s.luhn("4111111111111112"),))
        assert s.luhn("79927398713") is True, (
            "the classic check digit of 7992739871 is 3: %r" % (s.luhn("79927398713"),))
        assert s.luhn("5555555555554444") is True, (
            "a card whose doubled digits are all tens still adds up: %r"
            % (s.luhn("5555555555554444"),))
        assert s.luhn("79927398710") is False, (
            "the same digits with one transposed fail: %r" % (s.luhn("79927398710"),))
        assert s.luhn("0") is False, (
            "a single digit is not a checksum of anything: %r" % (s.luhn("0"),))
        assert s.luhn("") is False, (
            "an empty run must not come back as a pass: %r" % (s.luhn(""),))
        _refuses(s.GuardError, "a checksum of a number rather than of digits",
                 lambda: s.luhn(4111111111111111), names=("int",))
        _refuses(s.GuardError, "a run with a letter in it",
                 lambda: s.luhn("4111x111"), names=("'x'", "at 4"))

    def _detect(s):
        found = s.detect(TEXT)
        assert isinstance(found, tuple), (
            "the detections of a text are a tuple, not a %s" % (type(found).__name__,))
        assert [tuple(detection) for detection in found] == [s.DETECTION_KEYS
                                                             for _ in found], (
            "every detection carries its keys in the contract's order: %r"
            % ([tuple(detection) for detection in found],))
        assert found == SPANS, (
            "the three kinds of this text are found at the spans the text gives them: %r"
            % (found,))
        assert [detection for detection in found if detection["kind"] == "card"] == [
            dict(SPANS[1])], (
            "the card is one detection, not one per group: %r" % (found,))
        assert sorted(set(detection["kind"] for detection in found)) == sorted(s.KINDS), (
            "every kind of the catalogue is found in this text: %r" % (found,))
        spans = [(detection["start"], detection["end"]) for detection in found]
        assert [pair for index, pair in enumerate(spans)
                if index and pair[0] < spans[index - 1][1]] == [], (
            "two detections overlap, so one of them was masked out of the middle of the "
            "other: %r" % (spans,))
        assert [pair for index, pair in enumerate(spans)
                if index and pair[0] <= spans[index - 1][0]] == [], (
            "the detections are not in leftmost order: %r" % (spans,))
        assert [detection["value"] for detection in found
                if TEXT[detection["start"]:detection["end"]] != detection["value"]] == [], (
            "a detection quotes something other than the text under its own span: %r"
            % (found,))
        assert s.detect("card %s" % (BAD_CARD,)) == (), (
            "a sixteen-digit run that fails its checksum is not a card: %r"
            % (s.detect("card %s" % (BAD_CARD,)),))
        assert s.detect(ONE_RUN) == ({"kind": "card", "start": 0, "end": 20,
                                      "value": ONE_RUN},), (
            "the run that contains an identity number's own shape is one card: %r"
            % (s.detect(ONE_RUN),))
        assert s.detect(SEVENTEEN_SPAN) == (), (
            "seventeen digits are not a card, checksum or not: %r"
            % (s.detect(SEVENTEEN_SPAN),))
        assert s.detect(CARD) == ({"kind": "card", "start": 0, "end": 19, "value": CARD},), (
            "a phone-shaped run inside the card is not a second detection: %r"
            % (s.detect(CARD),))
        assert s.detect("n 123 45 6789 x") == (), (
            "an identity number is written with dashes; with spaces it is nothing: %r"
            % (s.detect("n 123 45 6789 x"),))
        assert s.detect("tel 600 123 456") == ({"kind": "phone", "start": 4, "end": 15,
                                                "value": "600 123 456"},), (
            "a grouped local number is a phone: %r" % (s.detect("tel 600 123 456"),))
        assert s.detect(SSN) == ({"kind": "ssn", "start": 0, "end": 11, "value": SSN},), (
            "one identity number alone: %r" % (s.detect(SSN),))
        two = _ssns(2)
        assert [detection["value"] for detection in s.detect("a %s b %s c" % two)] == list(two), (
            "two identity numbers are two detections, in the order they appear: %r"
            % (s.detect("a %s b %s c" % two),))
        assert s.detect("") == (), (
            "a text with nothing in it has no detection: %r" % (s.detect(""),))
        assert s.detect("nothing to mask here") == (), (
            "a text with no kind in it has no detection: %r"
            % (s.detect("nothing to mask here"),))
        _refuses(s.GuardError, "the detections of a number", lambda: s.detect(6789),
                 names=("int",))

    def _masker(s):
        masker = s.Masker()
        empty = s.Masker()
        assert empty.mapping() == () and empty.seen() == (), (
            "a masker that has seen nothing knows nothing: %r / %r"
            % (empty.mapping(), empty.seen()))
        masked, mapping = masker.mask(TEXT)
        assert masked == MASKED, (
            "the masked text is the text with every detection replaced: %r" % (masked,))
        assert [value for value in (SSN, CARD, EMAIL, PHONE) if value in masked] == [], (
            "the masked text still carries the value it masked: %r" % (masked,))
        assert mapping == PAIRS, (
            "the pairs are the ones this call replaced, sorted by placeholder: %r"
            % (mapping,))
        assert masker.mapping() == PAIRS, (
            "the masker's whole mapping is the pairs it made: %r" % (masker.mapping(),))
        assert masker.seen() == SORTED_KINDS, (
            "the kinds it has masked, sorted: %r" % (masker.seen(),))
        assert masker.mask(TEXT) == (masked, mapping), (
            "a masker is stable: the same text twice is the same bytes twice: %r"
            % (masker.mask(TEXT),))
        assert masker.mask(masked) == (masked, ()), (
            "a text that is already masked has nothing left to replace: %r"
            % (masker.mask(masked),))
        assert masker.restore(masked) == TEXT, (
            "restore is the inverse of mask for the text it masked: %r"
            % (masker.restore(masked),))
        assert masker.restore("no placeholders here") == "no placeholders here", (
            "restore touches a text it masked nothing in: %r"
            % (masker.restore("no placeholders here"),))
        unknown = masker.restore("%s and [[ssn:9]]" % (masked,))
        assert unknown == "%s and [[ssn:9]]" % (TEXT,), (
            "restore puts back its own placeholders and guesses at nothing else: %r"
            % (unknown,))
        again = masker.mask("again %s" % (CARD,))
        assert again == ("again [[card:1]]", (("[[card:1]]", CARD),)), (
            "a value seen before keeps its placeholder, and the answer is what this call "
            "replaced: %r" % (again,))
        twice = s.Masker()
        repeated = twice.mask("x %s y %s z" % (EMAIL, EMAIL))
        assert repeated == ("x [[email:1]] y [[email:1]] z",
                            (("[[email:1]]", EMAIL),)), (
            "one value in two places is one pair and the same placeholder twice: %r"
            % (repeated,))
        pair = _ssns(2)
        two = s.Masker()
        strict = two.mask("%s %s" % pair)
        assert strict == ("[[ssn:1]] [[ssn:2]]",
                          (("[[ssn:1]]", pair[0]), ("[[ssn:2]]", pair[1]))), (
            "two values of one kind never share a placeholder: %r" % (strict,))
        many = s.Masker()
        numbers = _ssns(11)
        masked_many, mapped_many = many.mask(" ".join(numbers))
        assert mapped_many == tuple(sorted(mapped_many)), (
            "the pairs come back in placeholder order: %r" % (mapped_many,))
        assert ("[[ssn:1]]", numbers[0]) in mapped_many and ("[[ssn:11]]",
                                                             numbers[10]) in mapped_many, (
            "the eleventh value of a kind is the eleventh placeholder: %r" % (mapped_many,))
        assert many.restore("[[ssn:11]]") == numbers[10], (
            "a placeholder that is a prefix of a longer one is not the longer one: %r"
            % (many.restore("[[ssn:11]]"),))
        assert many.restore("[[ssn:11]] [[ssn:1]]") == "%s %s" % (numbers[10], numbers[0]), (
            "the longer placeholder survives the shorter one's replacement: %r"
            % (many.restore("[[ssn:11]] [[ssn:1]]"),))
        assert many.restore(masked_many) == " ".join(numbers), (
            "eleven numbers go out and eleven come back: %r" % (many.restore(masked_many),))
        assert [placeholder for placeholder, value in mapping
                if s.digits(value) and s.digits(value) in placeholder] == [], (
            "a placeholder carries no digit of the value it hides: %r" % (mapping,))
        assert len(set(placeholder for placeholder, value in mapping)) == len(mapping), (
            "two values share one placeholder, so restoring gives the wrong one back: %r"
            % (mapping,))
        _refuses(s.GuardError, "the masking of a number", lambda: s.Masker().mask(4111),
                 names=("int",))
        _refuses(s.GuardError, "the restoring of nothing",
                 lambda: s.Masker().restore(None), names=("NoneType",))

    def _scan(s):
        masker = s.Masker()
        masked, mapping = masker.mask(TEXT)
        assert s.scan(masked, mapping) == (), (
            "nothing the masker replaced is still in the text it sent: %r"
            % (s.scan(masked, mapping),))
        assert s.scan(SSN, mapping) == (SSN,), (
            "a value left in the text is found: %r" % (s.scan(SSN, mapping),))
        assert s.scan("the whole of it: %s" % (TEXT,), mapping) == (CARD, EMAIL, PHONE,
                                                                    SSN), (
            "the answer is in the mapping's order, not in the text's: %r"
            % (s.scan("the whole of it: %s" % (TEXT,), mapping),))
        assert s.scan("%s and %s" % (CARD, CARD), mapping) == (CARD,), (
            "a value that appears twice is one value: %r"
            % (s.scan("%s and %s" % (CARD, CARD), mapping),))
        assert s.scan("", mapping) == (), (
            "nothing is in nothing: %r" % (s.scan("", mapping),))
        assert s.scan(masked, ()) == (), (
            "an empty mapping can find nothing: %r" % (s.scan(masked, ()),))
        made_up = (("[[x:1]]", "not-a-pattern-at-all"),)
        assert s.scan("a not-a-pattern-at-all here", made_up) == (
            "not-a-pattern-at-all",), (
            "the scan looks for the mapping's own values, not for the kind's shape: %r"
            % (s.scan("a not-a-pattern-at-all here", made_up),))
        _refuses(s.GuardError, "the scanning of a number", lambda: s.scan(5, mapping),
                 names=("int",))
        _refuses(s.GuardError, "a mapping that is not a sequence",
                 lambda: s.scan(masked, None), names=("NoneType",))
        _refuses(s.GuardError, "a mapping whose entries are not pairs",
                 lambda: s.scan(masked, ("[[ssn:1]]",)), names=("[[ssn:1]]",))
        _refuses(s.GuardError, "a pair that carries something other than a value",
                 lambda: s.scan(masked, (("[[ssn:1]]", 5),)),
                 names=("[[ssn:1]]", "int"))

    def _forward(s, world):
        records = world.Estate.build(7)
        seen = []

        def answer_for(sent):
            """The customer's own model, answering in the customer's own words."""
            seen.append(sent)
            return "the customer wrote: %s" % (sent,)

        guard = s.forward(TEXT, answer_for, s.Masker(), records, 9)
        assert tuple(guard) == s.GUARD_KEYS, (
            "a forwarded call is recorded with the contract's keys, in order: %r"
            % (tuple(guard),))
        assert guard["masked"] == MASKED, (
            "what was sent is the masked text and nothing else: %r" % (guard["masked"],))
        assert [value for value in (SSN, CARD, EMAIL, PHONE)
                if value in guard["masked"]] == [], (
            "the text that went out carries a value it should have masked: %r"
            % (guard["masked"],))
        assert seen == [guard["masked"]], (
            "the model saw something other than what was sent: %r" % (seen,))
        assert guard["mapping"] == PAIRS, (
            "the record carries the pairs that produced the outbound text: %r"
            % (guard["mapping"],))
        assert guard["kinds"] == SORTED_KINDS, (
            "the kinds masked, sorted: %r" % (guard["kinds"],))
        assert guard["leaks"] == (), (
            "the scan found something in the outbound text: %r" % (guard["leaks"],))
        log = records.log()
        assert len(log) == 1 and tuple(log[0]) == world.AUDIT_KEYS, (
            "one call writes exactly one audit line, in the world's own keys: %r" % (log,))
        line = log[0]
        assert (line["tick"], line["actor"], line["action"], line["target"],
                line["verdict"]) == (9, "guardrail", "forward", "answer_for", "sent"), (
            "the audit line names the tick, the actor, the act, the model and the "
            "verdict: %r" % (line,))
        assert line["reason"] == FOUR_KINDS_REASON, (
            "the reason carries the kinds and the counts and nothing else: %r"
            % (line["reason"],))
        assert [written for written in log
                if SSN in repr(written) or CARD in repr(written)
                or EMAIL in repr(written) or PHONE in repr(written)] == [], (
            "an audit line carries the value itself: %r" % (log,))
        assert records.stats()["audits"] == 1, (
            "the world's own log recounts one audit, not %r"
            % (records.stats()["audits"],))

        quiet = s.forward("a quiet sentence about nothing", lambda sent: "quiet",
                          s.Masker(), records, 10)
        assert quiet["masked"] == "a quiet sentence about nothing" and quiet["mapping"] == (
            ()) and quiet["kinds"] == () and quiet["leaks"] == (), (
            "a text with no kind in it is sent as it stands, with nothing masked: %r"
            % (quiet,))
        assert records.log()[-1]["reason"] == "kinds=none; masked=0; restored=0; leaks=0", (
            "a call that masked nothing says so: %r" % (records.log()[-1]["reason"],))
        assert records.log()[-1]["target"] == "<lambda>", (
            "the audit line names the callable it forwarded to: %r"
            % (records.log()[-1]["target"],))

        masker = s.Masker()
        already = masker.mask(TEXT)[0]
        again = s.forward(already, lambda sent: sent, masker, records, 11)
        assert again["masked"] == already and again["mapping"] == (), (
            "a text that arrives already masked replaces nothing, and the record says so: "
            "%r" % (again,))
        assert again["kinds"] == SORTED_KINDS and again["leaks"] == (), (
            "the masker still knows the kinds it handled, and the outbound text is "
            "clean: %r" % (again,))

        class Leaky(s.Masker):
            """A masker that answers a real mapping and masks nothing: the bug the scan is for."""

            def mask(self, text):
                return text, s.Masker.mask(self, text)[1]

        called = []

        def never(sent):
            called.append(sent)
            return "ok"

        before = records.stats()["audits"]
        refused = _refuses(s.GuardError, "a payload in which a value survived",
                           lambda: s.forward(TEXT, never, Leaky(), records, 12),
                           names=("card", "email", "phone", "ssn"))
        assert called == [], (
            "the model was called with a payload the scan had already found leaking: %r"
            % (called,))
        assert [value for value in (SSN, CARD, EMAIL, PHONE)
                if value in str(refused)] == [], (
            "the refusal quotes the value it refused to send: %r" % (str(refused),))
        assert records.stats()["audits"] == before + 1, (
            "a call refused for a leak left no audit line of its own: %r"
            % (records.log(),))
        assert records.log()[-1]["verdict"] == "refused", (
            "the audit line of a refused call does not say it was refused: %r"
            % (records.log()[-1],))
        assert records.log()[-1]["reason"] == (
            "kinds=card,email,phone,ssn; masked=4; restored=0; leaks=4"), (
            "the refused call's reason names the kinds and the counts, never a value: %r"
            % (records.log()[-1]["reason"],))
        assert [written for written in records.log()
                if SSN in repr(written) or CARD in repr(written)] == [], (
            "the refused call's own audit line carries the value it refused: %r"
            % (records.log(),))

        class Stubborn(s.Masker):
            """A masker whose restore does nothing, so a placeholder comes back unchanged."""

            def restore(self, text):
                return text

        before = records.stats()["audits"]
        _refuses(s.GuardError, "an answer whose placeholder could not be put back",
                 lambda: s.forward(TEXT, lambda sent: sent, Stubborn(), records, 13),
                 names=("[[card:1]]",))
        assert records.stats()["audits"] == before, (
            "a call that never reached the wire wrote an audit line: %r"
            % (records.log()[-1],))

        before = records.stats()["audits"]
        _refuses(s.GuardError, "a model answering something that is not a string",
                 lambda: s.forward(TEXT, lambda sent: 7, s.Masker(), records, 14),
                 names=("the model answered", "int"))
        assert records.stats()["audits"] == before, (
            "a call refused for its answer's shape wrote an audit line anyway: %r"
            % (records.log()[-1],))

        shapes = (
            ("a text that is not a string",
             lambda: s.forward(4111, answer_for, s.Masker(), records, 15), ("int",)),
            ("a model that cannot be called",
             lambda: s.forward(TEXT, "model", s.Masker(), records, 15), ("str",)),
            ("a masker that is not a Masker",
             lambda: s.forward(TEXT, answer_for, None, records, 15), ("NoneType",)),
            ("an estate with no audit line",
             lambda: s.forward(TEXT, answer_for, s.Masker(), None, 15), ("NoneType",)),
            ("a tick that is not a whole number",
             lambda: s.forward(TEXT, answer_for, s.Masker(), records, "9"), ("'9'",)),
            ("a tick that is a bool",
             lambda: s.forward(TEXT, answer_for, s.Masker(), records, True), ("True",)),
        )
        before = records.stats()["audits"]
        for what, call, names in shapes:
            _refuses(s.GuardError, what, call, names=names)
        assert records.stats()["audits"] == before, (
            "a call refused for the shape of its arguments wrote a line into the world's "
            "own log: %r" % (records.log()[before:],))

    def _once(s, world):
        """One whole run of the stage over its own fixture, as one comparable value."""
        records = world.Estate.build(7)
        masker = s.Masker()
        masked, mapping = masker.mask(TEXT)
        guard = s.forward(TEXT, lambda sent: "echo: %s" % (sent,), s.Masker(), records, 9)
        return (s.detect(TEXT), masked, mapping, masker.restore(masked),
                masker.mapping(), masker.seen(), s.scan("%s %s" % (TEXT, SSN), mapping),
                guard, records.log(), records.stats())

    def _twice(s, world):
        one = _once(s, world)
        two = _once(s, world)
        assert one == two, (
            "two runs of one fixture answered two different things, so a run is not a "
            "function of its inputs: %r vs %r" % (one, two))

    import stage_06 as s
    import estate as world
    _constants(s, world)
    _digits(s)
    _luhn(s)
    _detect(s)
    _masker(s)
    _scan(s)
    _forward(s, world)
    _twice(s, world)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "fde-from-scratch"

    PLAN = (
        {"name": "intake", "actor": "machine", "effect": "logged", "gate": None},
        {"name": "draft", "actor": "machine", "effect": "drafted", "gate": None},
        {"name": "sign", "actor": "human", "effect": "signed", "gate": "cfo"},
        {"name": "send", "actor": "machine", "effect": "sent", "gate": None},
    )

    FLAT = (
        {"name": "draft", "actor": "machine", "effect": "drafted", "gate": None},
        {"name": "file", "actor": "machine", "effect": None, "gate": None},
    )

    OPEN = ({"name": "sign", "actor": "human", "effect": None, "gate": None},)

    APPROVERS = ("cfo", "legal")

    GATE_LINES = (
        {"seq": 0, "tick": 3, "kind": "started", "ticket": "inv-1", "detail": None},
        {"seq": 1, "tick": 3, "kind": "step", "ticket": "inv-1", "detail": "intake"},
        {"seq": 2, "tick": 3, "kind": "effect", "ticket": "inv-1", "detail": "logged"},
        {"seq": 3, "tick": 3, "kind": "step", "ticket": "inv-1", "detail": "draft"},
        {"seq": 4, "tick": 3, "kind": "effect", "ticket": "inv-1", "detail": "drafted"},
        {"seq": 5, "tick": 3, "kind": "gate", "ticket": "inv-1", "detail": "cfo"},
    )

    ZERO_GATE_LINES = (
        {"seq": 0, "tick": 0, "kind": "started", "ticket": "inv-1", "detail": None},
        {"seq": 1, "tick": 0, "kind": "step", "ticket": "inv-1", "detail": "intake"},
        {"seq": 2, "tick": 0, "kind": "effect", "ticket": "inv-1", "detail": "logged"},
        {"seq": 3, "tick": 0, "kind": "step", "ticket": "inv-1", "detail": "draft"},
        {"seq": 4, "tick": 0, "kind": "effect", "ticket": "inv-1", "detail": "drafted"},
        {"seq": 5, "tick": 0, "kind": "gate", "ticket": "inv-1", "detail": "cfo"},
    )

    DONE_LINES = GATE_LINES + (
        {"seq": 6, "tick": 5, "kind": "approved", "ticket": "inv-1", "detail": "cfo"},
        {"seq": 7, "tick": 5, "kind": "effect", "ticket": "inv-1", "detail": "signed"},
        {"seq": 8, "tick": 5, "kind": "step", "ticket": "inv-1", "detail": "send"},
        {"seq": 9, "tick": 5, "kind": "effect", "ticket": "inv-1", "detail": "sent"},
        {"seq": 10, "tick": 5, "kind": "done", "ticket": "inv-1", "detail": None},
    )

    def _repo(start=None):
        for candidate_start in (os.environ.get("FDE_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set FDE_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    FLAT_LINES = (
        {"seq": 0, "tick": 0, "kind": "started", "ticket": "inv-1", "detail": None},
        {"seq": 1, "tick": 0, "kind": "step", "ticket": "inv-1", "detail": "draft"},
        {"seq": 2, "tick": 0, "kind": "effect", "ticket": "inv-1", "detail": "drafted"},
        {"seq": 3, "tick": 0, "kind": "step", "ticket": "inv-1", "detail": "file"},
        {"seq": 4, "tick": 0, "kind": "done", "ticket": "inv-1", "detail": None},
    )

    OPEN_LINES = (
        {"seq": 0, "tick": 0, "kind": "started", "ticket": "inv-1", "detail": None},
        {"seq": 1, "tick": 0, "kind": "gate", "ticket": "inv-1", "detail": None},
        {"seq": 2, "tick": 1, "kind": "approved", "ticket": "inv-1", "detail": "legal"},
        {"seq": 3, "tick": 1, "kind": "done", "ticket": "inv-1", "detail": None},
    )

    def _state(s, record, want, what):
        """One `STATE_KEYS` answer, as the keys in order and the values that belong."""
        assert isinstance(record, dict), (
            "%s answered a %s, and a state is a STATE_KEYS record"
            % (what, type(record).__name__))
        assert tuple(record) == s.STATE_KEYS, (
            "%s answered the keys %r, and a state carries %r"
            % (what, tuple(record), s.STATE_KEYS))
        assert record == want, "%s answered %r, and the state is %r" % (what, record, want)

    def _same_lines(got, want, what):
        """A journal, line by line, in order: the ledger this stage is checked against."""
        assert isinstance(got, tuple), (
            "%s answered a %s, and a journal is a tuple of lines"
            % (what, type(got).__name__))
        assert len(got) == len(want), (
            "%s wrote %d journal lines where this run calls for %d: %r"
            % (what, len(got), len(want), got))
        for index, line in enumerate(want):
            assert tuple(got[index]) == tuple(line), (
                "line %d of the journal carries the keys %r, and a line carries %r"
                % (index, tuple(got[index]), tuple(line)))
            assert got[index] == line, (
                "line %d of the journal is %r, and this run writes %r"
                % (index, got[index], line))

    def _plan_refusals(s):
        def make(plan, approvers=APPROVERS, deadline=5):
            return lambda: s.Workflow(plan, approvers, deadline)

        _refuses(s.WorkflowError, "a plan that is a list rather than a tuple",
                 make([dict(step) for step in PLAN]), names=("list",))
        _refuses(s.WorkflowError, "a plan with no steps in it",
                 make(()), names=("empty",))
        _refuses(s.WorkflowError, "a step that is a tuple rather than a record",
                 make((("intake", "machine"),)), names=("step 0", "tuple"))
        _refuses(s.WorkflowError, "a step with no gate field",
                 make(({"name": "intake", "actor": "machine", "effect": None},)),
                 names=("step 0",))
        _refuses(s.WorkflowError, "a step with a field a step does not have",
                 make(({"name": "intake", "actor": "machine", "effect": None,
                        "gate": None, "who": "me"},)), names=("step 0",))
        _refuses(s.WorkflowError, "an actor that is not one of ACTORS",
                 make(({"name": "intake", "actor": "robot", "effect": None,
                        "gate": None},)), names=("robot",))
        _refuses(s.WorkflowError, "a step with no name",
                 make(({"name": "", "actor": "machine", "effect": None,
                        "gate": None},)), names=("step 0",))
        _refuses(s.WorkflowError, "two steps of one plan with one name",
                 make((PLAN[0], PLAN[0])), names=("intake",))
        _refuses(s.WorkflowError, "a machine step that waits for an approver",
                 make(({"name": "draft", "actor": "machine", "effect": None,
                        "gate": "cfo"},)), names=("draft", "cfo"))
        _refuses(s.WorkflowError, "a gate that is not an approver's name",
                 make(({"name": "sign", "actor": "human", "effect": None,
                        "gate": 3},)), names=("sign",))
        _refuses(s.WorkflowError, "an effect that is not a name",
                 make(({"name": "draft", "actor": "machine", "effect": 7,
                        "gate": None},)), names=("draft",))
        _refuses(s.WorkflowError, "approvers as one string rather than a tuple",
                 make(PLAN, approvers="cfo"), names=("str",))
        _refuses(s.WorkflowError, "an approver that is not a name",
                 make(PLAN, approvers=("cfo", "")), names=("''",))
        _refuses(s.WorkflowError, "a deadline that is a string of ticks",
                 make(PLAN, deadline="5"), names=("'5'",))
        _refuses(s.WorkflowError, "a deadline of no ticks at all",
                 make(PLAN, deadline=0), names=("one or more",))
        _refuses(s.WorkflowError, "a deadline counted backwards",
                 make(PLAN, deadline=-2), names=("-2",))
        # An empty approver tuple is not a mistake: a workflow whose gate nobody may
        # open yet is a workflow the customer can still start and watch stop.
        s.Workflow(PLAN, (), 5)

    def _gate(s):
        flow = s.Workflow(PLAN, APPROVERS, 5)
        record = flow.start("inv-1", 3)
        _state(s, record, {"ticket": "inv-1", "state": "waiting-approval",
                           "steps": ("intake", "draft"), "next": "sign",
                           "approver": "cfo", "due_at": 8,
                           "effects": ("logged", "drafted")},
               "a ticket started at tick 3 with a deadline of 5 ticks")
        _same_lines(flow.journal(), GATE_LINES, "a ticket that stops at its gate")
        assert flow.pending(7) == ("inv-1",), (
            "a ticket due at 8 is still waiting at tick 7: %r" % (flow.pending(7),))
        assert flow.pending(8) == (), (
            "a ticket due at 8 waits for nobody at tick 8: %r" % (flow.pending(8),))
        flow.start("cli-9", 4)
        assert flow.pending(4) == ("cli-9", "inv-1"), (
            "pending answers the tickets in order: %r" % (flow.pending(4),))
        assert flow.pending(8) == ("cli-9",), (
            "the second ticket started at 4 is due at 9: %r" % (flow.pending(8),))
        assert flow.pending(9) == (), (
            "no ticket is pending at tick 9: %r" % (flow.pending(9),))
        _refuses(s.WorkflowError, "a ticket that is already in the workflow",
                 lambda: flow.start("inv-1", 5), names=("inv-1",))
        _refuses(s.WorkflowError, "a ticket that is not a name",
                 lambda: flow.start(3, 5), names=("3",))
        _refuses(s.WorkflowError, "a ticket with no name at all",
                 lambda: flow.start("", 5), names=("''",))
        _refuses(s.WorkflowError, "a tick that is not a tick",
                 lambda: flow.start("inv-3", "5"), names=("'5'",))
        _refuses(s.WorkflowError, "a tick before the clock started",
                 lambda: flow.start("inv-3", -1), names=("-1",))
        _refuses(s.WorkflowError, "a ticket nobody started",
                 lambda: flow.state("nope"), names=("nope",))
        _refuses(s.WorkflowError, "a ticket asked for as a number",
                 lambda: flow.state(7), names=("7",))
        # A gate nobody may open still stops the machine: that is the whole stage.
        closed = s.Workflow(PLAN, (), 5)
        assert closed.start("inv-1", 0)["state"] == "waiting-approval", (
            "a gate stops the machine even with an empty approver tuple: %r"
            % (closed.state("inv-1"),))
        assert tuple(line["kind"] for line in closed.journal()) == (
            "started", "step", "effect", "step", "effect", "gate"), (
                "the machine ran to the gate and no further: %r" % (closed.journal(),))
        _refuses(s.WorkflowError, "an approval with nobody in the approver tuple",
                 lambda: closed.approve("cfo", "inv-1", 1), names=("cfo",))
        # A plan with no gate at all is done before the caller can ask.
        flat = s.Workflow(FLAT, APPROVERS, 3)
        _state(s, flat.start("inv-1", 0),
               {"ticket": "inv-1", "state": "done", "steps": ("draft", "file"),
                "next": None, "approver": None, "due_at": 3, "effects": ("drafted",)},
               "a plan with no human step in it")
        _same_lines(flat.journal(), FLAT_LINES, "a plan with no human step in it")
        assert flat.pending(0) == (), (
            "a ticket that is done is not pending: %r" % (flat.pending(0),))
        # A human step with no gate of its own waits for the plan's whole tuple.
        opened = s.Workflow(OPEN, APPROVERS, 3)
        assert opened.start("inv-1", 0)["approver"] is None, (
            "a gate with no approver of its own waits for the tuple: %r"
            % (opened.state("inv-1"),))
        assert opened.pending(0) == ("inv-1",), (
            "the ticket stands at a gate nobody has answered: %r" % (opened.pending(0),))
        _state(s, opened.approve("legal", "inv-1", 1),
               {"ticket": "inv-1", "state": "done", "steps": ("sign",), "next": None,
                "approver": None, "due_at": 3, "effects": ()},
               "an approval from another approver of the tuple")
        _same_lines(opened.journal(), OPEN_LINES, "a gate the whole tuple may answer")

    DONE_STATE = {"ticket": "inv-1", "state": "done",
                  "steps": ("intake", "draft", "sign", "send"), "next": None,
                  "approver": None, "due_at": 8,
                  "effects": ("logged", "drafted", "signed", "sent")}

    GATE_STATE = {"ticket": "inv-1", "state": "waiting-approval",
                  "steps": ("intake", "draft"), "next": "sign", "approver": "cfo",
                  "due_at": 8, "effects": ("logged", "drafted")}

    def _constants(s, world):
        assert tuple(s.STEP_KEYS) == ("name", "actor", "effect", "gate"), (
            "a step of a plan carries these four fields, in this order: %r"
            % (s.STEP_KEYS,))
        assert tuple(s.STATE_KEYS) == ("ticket", "state", "steps", "next", "approver",
                                       "due_at", "effects"), (
            "a ticket's state carries these seven fields, in this order: %r"
            % (s.STATE_KEYS,))
        assert tuple(s.STATES) == ("draft", "waiting-approval", "approved", "rejected",
                                   "done", "escalated"), (
            "every state a ticket may hold, in this order: %r" % (s.STATES,))
        assert tuple(s.ACTORS) == ("machine", "human"), (
            "the two actors a step may name: %r" % (s.ACTORS,))
        assert tuple(s.JOURNAL_KEYS) == ("seq", "tick", "kind", "ticket", "detail"), (
            "a line of the journal carries these five fields, in this order: %r"
            % (s.JOURNAL_KEYS,))
        assert tuple(s.KINDS_OF_LINE) == ("started", "step", "gate", "approved",
                                          "rejected", "escalated", "effect", "done"), (
            "every kind of line the journal may carry, in this order: %r"
            % (s.KINDS_OF_LINE,))
        assert issubclass(s.WorkflowError, world.EstateError), (
            "WorkflowError must be a kind of estate.EstateError, and its bases are %r"
            % (s.WorkflowError.__mro__,))
        assert issubclass(s.WorkflowError, ValueError), (
            "a caller's `except ValueError` must still catch it: %r"
            % (s.WorkflowError.__mro__,))

    def _verdicts(s):
        flow = s.Workflow(PLAN, APPROVERS, 5)
        flow.start("inv-1", 3)
        before = flow.journal()
        handed = flow.journal()
        handed[0]["detail"] = "tampered"
        assert flow.journal() == before, (
            "a caller editing a line it was handed changed the workflow's own journal: %r"
            % (flow.journal(),))
        _refuses(s.WorkflowError, "an approval from somebody the plan does not list",
                 lambda: flow.approve("cto", "inv-1", 5), names=("cto",))
        _refuses(s.WorkflowError, "an approval from the wrong approver of the tuple",
                 lambda: flow.approve("legal", "inv-1", 5), names=("legal", "cfo"))
        _refuses(s.WorkflowError, "an approver that is not a name",
                 lambda: flow.approve(3, "inv-1", 5), names=("3",))
        _refuses(s.WorkflowError, "an approval of a ticket nobody started",
                 lambda: flow.approve("cfo", "nope", 5), names=("nope",))
        assert flow.journal() == before, (
            "a refused approval wrote to the journal, and a refusal leaves no trace: %r"
            % (flow.journal(),))
        assert flow.state("inv-1") == GATE_STATE, (
            "a refused approval moved the ticket: %r" % (flow.state("inv-1"),))
        _state(s, flow.approve("cfo", "inv-1", 5), DONE_STATE,
               "an approval from the gate's own approver")
        _same_lines(flow.journal(), DONE_LINES, "the run this whole stage is about")
        assert s.effects_of(flow.journal(), "inv-1") == ("logged", "drafted", "signed",
                                                         "sent"), (
            "the effects were applied in the order the plan runs them: %r"
            % (s.effects_of(flow.journal(), "inv-1"),))
        _refuses(s.WorkflowError, "an approval of a ticket that is already done",
                 lambda: flow.approve("cfo", "inv-1", 5), names=("inv-1", "done"))
        _refuses(s.WorkflowError, "a rejection of a ticket that is already done",
                 lambda: flow.reject("cfo", "inv-1", 5), names=("done",))
        # A rejection is the other verdict of the same act, and it is final.
        refused = s.Workflow(PLAN, APPROVERS, 5)
        refused.start("inv-1", 3)
        _state(s, refused.reject("cfo", "inv-1", 4),
               {"ticket": "inv-1", "state": "rejected", "steps": ("intake", "draft"),
                "next": None, "approver": None, "due_at": 8,
                "effects": ("logged", "drafted")},
               "a rejection by the gate's own approver")
        _same_lines(refused.journal(), GATE_LINES + (
            {"seq": 6, "tick": 4, "kind": "rejected", "ticket": "inv-1",
             "detail": "cfo"},), "a gate that was refused")
        assert refused.pending(4) == (), (
            "a rejected ticket is not pending: %r" % (refused.pending(4),))
        _refuses(s.WorkflowError, "an approval of a ticket that was rejected",
                 lambda: refused.approve("cfo", "inv-1", 4), names=("rejected",))
        _refuses(s.WorkflowError, "a second verdict on a rejected ticket",
                 lambda: refused.reject("cfo", "inv-1", 4), names=("rejected",))
        assert refused.advance(9) == (), (
            "a rejected ticket is over and is never escalated: %r"
            % (refused.advance(9),))
        assert refused.state("inv-1")["state"] == "rejected", (
            "nothing after a refused gate runs, and the ticket stays rejected: %r"
            % (refused.state("inv-1"),))

    def _deadline(s):
        early = s.Workflow(PLAN, APPROVERS, 5)
        early.start("inv-1", 0)
        _state(s, early.approve("cfo", "inv-1", 4),
               {"ticket": "inv-1", "state": "done",
                "steps": ("intake", "draft", "sign", "send"), "next": None,
                "approver": None, "due_at": 5,
                "effects": ("logged", "drafted", "signed", "sent")},
               "an approval one tick before the deadline")
        late = s.Workflow(PLAN, APPROVERS, 5)
        late.start("inv-1", 0)
        before = late.journal()
        _refuses(s.WorkflowError, "an approval at exactly due_at",
                 lambda: late.approve("cfo", "inv-1", 5),
                 names=("inv-1", "due at tick 5", "tick 5"))
        _refuses(s.WorkflowError, "an approval past due_at",
                 lambda: late.approve("cfo", "inv-1", 6), names=("inv-1", "due at tick 5"))
        _refuses(s.WorkflowError, "a rejection at exactly due_at",
                 lambda: late.reject("cfo", "inv-1", 5), names=("inv-1", "due at tick 5"))
        assert late.journal() == before, (
            "a refusal at the deadline wrote to the journal: %r" % (late.journal(),))
        assert late.advance(4) == (), (
            "no ticket is escalated before its deadline: %r" % (late.advance(4),))
        escalated = late.advance(5)
        assert len(escalated) == 1, (
            "advance answers one record per ticket whose state changed: %r"
            % (escalated,))
        _state(s, escalated[0], {"ticket": "inv-1", "state": "escalated",
                                 "steps": ("intake", "draft"), "next": None,
                                 "approver": None, "due_at": 5,
                                 "effects": ("logged", "drafted")},
               "a ticket escalated by the caller's own tick")
        _same_lines(late.journal(), ZERO_GATE_LINES + (
            {"seq": 6, "tick": 5, "kind": "escalated", "ticket": "inv-1",
             "detail": None},), "an escalated ticket")
        assert late.advance(9) == (), (
            "advance answers what changed, and an escalated ticket does not change "
            "again: %r" % (late.advance(9),))
        assert late.pending(6) == (), (
            "an escalated ticket waits for nobody: %r" % (late.pending(6),))
        _refuses(s.WorkflowError, "an approval after the escalation",
                 lambda: late.approve("cfo", "inv-1", 6), names=("inv-1",))
        # The escalation happens in ticket order, not in the order they started.
        two = s.Workflow(PLAN, APPROVERS, 5)
        two.start("b", 0)
        two.start("a", 0)
        changed = two.advance(5)
        assert tuple(record["ticket"] for record in changed) == ("a", "b"), (
            "advance answers the tickets in ticket order: %r"
            % (tuple(record["ticket"] for record in changed),))
        assert tuple(line["ticket"] for line in two.journal()[-2:]) == ("a", "b"), (
            "and writes them in ticket order too: %r" % (two.journal()[-2:],))
        done = s.Workflow(PLAN, APPROVERS, 2)
        done.start("inv-1", 0)
        done.approve("cfo", "inv-1", 1)
        assert done.advance(9) == (), (
            "a ticket that finished is never escalated by a later tick: %r"
            % (done.advance(9),))

    def _seqs(records, what):
        assert tuple(line["seq"] for line in records) == tuple(range(len(records))), (
            "%s: the journal's seq numbers are its own order and restart for nobody: %r"
            % (what, tuple(line["seq"] for line in records)))

    def _ledger(s):
        flow = s.Workflow(PLAN, APPROVERS, 5)
        flow.start("inv-1", 3)
        flow.approve("cfo", "inv-1", 5)
        _same_lines(flow.journal(), DONE_LINES, "the run a restart has to survive")
        # A journal that stopped at the gate replays to exactly that state and writes
        # nothing: there is nothing left to do.
        again = s.resume(GATE_LINES, PLAN, APPROVERS, 5, 9)
        _state(s, again.state("inv-1"), GATE_STATE,
               "the state a journal describes all by itself")
        _same_lines(again.journal(), GATE_LINES, "a journal that was already closed")
        assert again.pending(9) == (), (
            "the resumed ticket is past its deadline at tick 9: %r" % (again.pending(9),))
        # Carrying on from a resumed workflow writes the very lines the first run
        # wrote, and the seq of the new lines continues where the old ones stopped.
        _state(s, again.approve("cfo", "inv-1", 5), DONE_STATE,
               "an approval on a resumed workflow")
        _same_lines(again.journal(), DONE_LINES, "a resumed run carried to the end")
        # A journal cut after an effect — the tick a crash lands on — must not apply
        # that effect again, and must carry the machine on from where it stopped.
        cut = s.resume(GATE_LINES[:5], PLAN, APPROVERS, 5, 3)
        _same_lines(cut.journal(), GATE_LINES, "a journal cut after an effect")
        assert s.effects_of(cut.journal(), "inv-1") == ("logged", "drafted"), (
            "resume re-applied an effect the journal already carried: %r"
            % (s.effects_of(cut.journal(), "inv-1"),))
        # A journal cut after its first line replays the whole plan, once each.
        fresh = s.resume(GATE_LINES[:1], PLAN, APPROVERS, 5, 3)
        _same_lines(fresh.journal(), GATE_LINES, "a journal cut after its first line")
        assert s.effects_of(fresh.journal(), "inv-1") == ("logged", "drafted"), (
            "a replay applied an effect twice: %r"
            % (s.effects_of(fresh.journal(), "inv-1"),))
        # A journal cut after an approval, with the effect of the human step already
        # written: the rest of the plan still runs, and only once.
        rest = s.resume(DONE_LINES[:8], PLAN, APPROVERS, 5, 6)
        assert rest.journal()[:8] == DONE_LINES[:8], (
            "resume rewrote the lines it was handed: %r" % (rest.journal()[:8],))
        _seqs(rest.journal(), "a journal resumed after an approved step's effect")
        assert rest.state("inv-1") == DONE_STATE, (
            "the resumed ticket never reached the end of the plan: %r"
            % (rest.state("inv-1"),))
        assert s.effects_of(rest.journal(), "inv-1") == ("logged", "drafted", "signed",
                                                         "sent"), (
            "the effects of the whole plan, applied once each: %r"
            % (s.effects_of(rest.journal(), "inv-1"),))
        # A half-written tail is refused by index and text, never replayed on a guess.
        _refuses(s.WorkflowError, "a journal whose last line is a step",
                 lambda: s.resume(DONE_LINES[:4], PLAN, APPROVERS, 5, 3),
                 names=("3", "draft", "step"))
        _refuses(s.WorkflowError, "a journal whose last line is an approval",
                 lambda: s.resume(DONE_LINES[:7], PLAN, APPROVERS, 5, 3),
                 names=("6", "cfo", "approved"))
        # A journal with a hole in it is not a journal.
        _refuses(s.WorkflowError, "a journal missing a line in the middle",
                 lambda: s.resume(DONE_LINES[:3] + DONE_LINES[4:], PLAN, APPROVERS, 5, 3),
                 names=("3", "4"))
        _refuses(s.WorkflowError, "a journal that is a list rather than a tuple",
                 lambda: s.resume(list(DONE_LINES), PLAN, APPROVERS, 5, 3),
                 names=("list",))
        _refuses(s.WorkflowError, "a line that is not a record",
                 lambda: s.resume((("started",),), PLAN, APPROVERS, 5, 3),
                 names=("line 0",))
        _refuses(s.WorkflowError, "a line of a kind the journal does not have",
                 lambda: s.resume(DONE_LINES[:6] + ({"seq": 6, "tick": 3,
                                                     "kind": "cancelled",
                                                     "ticket": "inv-1",
                                                     "detail": None},),
                                  PLAN, APPROVERS, 5, 3),
                 names=("line 6", "cancelled"))
        _refuses(s.WorkflowError, "a resume with a plan of its own that is not a plan",
                 lambda: s.resume(GATE_LINES, (), APPROVERS, 5, 3), names=("empty",))
        _refuses(s.WorkflowError, "a resume at a tick that is not a tick",
                 lambda: s.resume(GATE_LINES, PLAN, APPROVERS, 5, "9"), names=("'9'",))
        # An empty journal describes a workflow with nothing in it yet.
        empty = s.resume((), PLAN, APPROVERS, 5, 0)
        assert empty.journal() == (), (
            "a workflow resumed from no lines has written no lines: %r" % (empty.journal(),))
        assert empty.pending(0) == (), (
            "and no ticket is pending in it: %r" % (empty.pending(0),))
        _refuses(s.WorkflowError, "a ticket of a workflow resumed from no lines",
                 lambda: empty.state("inv-1"), names=("inv-1",))
        # `effects_of` is the ledger read back, and it reports what the lines say.
        assert s.effects_of(DONE_LINES, "inv-1") == ("logged", "drafted", "signed",
                                                     "sent"), (
            "the effects of one ticket, in journal order: %r"
            % (s.effects_of(DONE_LINES, "inv-1"),))
        assert s.effects_of(DONE_LINES, "cli-9") == (), (
            "a ticket the journal never names has no effects: %r"
            % (s.effects_of(DONE_LINES, "cli-9"),))
        assert s.effects_of(DONE_LINES[:8], "inv-1") == ("logged", "drafted", "signed"), (
            "the ledger answers for a journal this short too: %r"
            % (s.effects_of(DONE_LINES[:8], "inv-1"),))
        twice = DONE_LINES + ({"seq": 11, "tick": 5, "kind": "effect",
                               "ticket": "inv-1", "detail": "sent"},)
        assert s.effects_of(twice, "inv-1") == ("logged", "drafted", "signed", "sent",
                                                "sent"), (
            "the ledger reports two lines, it does not quietly dedupe them: %r"
            % (s.effects_of(twice, "inv-1"),))
        _refuses(s.WorkflowError, "an effect asked for by a ticket that is not a name",
                 lambda: s.effects_of(DONE_LINES, 3), names=("3",))
        _refuses(s.WorkflowError, "an effect asked for out of a list of lines",
                 lambda: s.effects_of(list(DONE_LINES), "inv-1"), names=("list",))

    def _one_run(s):
        """One whole fixture, run once: what two ticks of the same inputs must answer."""
        flow = s.Workflow(PLAN, APPROVERS, 5)
        flow.start("inv-1", 3)
        flow.start("cli-9", 3)
        flow.approve("cfo", "inv-1", 5)
        opened = s.Workflow(OPEN, APPROVERS, 3)
        opened.start("cli-9", 0)
        opened.reject("legal", "cli-9", 1)
        late = s.Workflow(PLAN, APPROVERS, 5)
        late.start("inv-9", 0)
        escalated = late.advance(5)
        again = s.resume(flow.journal()[:6], PLAN, APPROVERS, 5, 5)
        again.approve("cfo", "inv-1", 5)
        return (flow.journal(), flow.state("inv-1"), flow.state("cli-9"), flow.pending(4),
                tuple(record["state"] for record in escalated), late.journal(),
                opened.journal(), opened.state("cli-9"), again.journal(),
                s.effects_of(again.journal(), "inv-1"))

    def _twice(s):
        one = _one_run(s)
        two = _one_run(s)
        for index, (left, right) in enumerate(zip(one, two)):
            assert left == right, (
                "the same fixture, run twice, answers two different things at %d: "
                "%r vs %r" % (index, left, right))

    import stage_07 as s
    import estate as world
    _constants(s, world)
    _plan_refusals(s)
    _gate(s)
    _verdicts(s)
    _deadline(s)
    _ledger(s)
    _twice(s)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "fde-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("FDE_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set FDE_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _machine(node, **overrides):
        """The world's own machine, with the named fields replaced."""
        record = dict(node)
        record.update(overrides)
        return record

    def _record(net, variant, **overrides):
        """A catalogue record with the named fields replaced, in the world's key order."""
        record = dict(net.model(variant))
        record.update(overrides)
        return record

    def _without(record, key):
        """The record with one field gone: a shape the stage must refuse."""
        short = dict(record)
        del short[key]
        return short

    def _constants(s, world):
        assert tuple(s.FIT_REASONS) == ("unknown-model", "unknown-node", "no-gpu",
                                        "gpu-memory", "unknown-quant", "zone"), (
            "the six fit reasons, in the order every refusal prints them: %r"
            % (s.FIT_REASONS,))
        assert s.HEADROOM == 90, (
            "a model may take 90 percent of the card: %r" % (s.HEADROOM,))
        assert s.QUEUE_MAX == 4, (
            "the queue holds four submissions: %r" % (s.QUEUE_MAX,))
        assert s.BUDGET_TICKS == 3, (
            "a submission may wait three ticks: %r" % (s.BUDGET_TICKS,))
        assert tuple(s.SUBMISSION_KEYS) == ("name", "tokens", "tick", "state", "waiting"), (
            "the five fields of a submission, in this order: %r" % (s.SUBMISSION_KEYS,))
        assert tuple(s.SERVE_REASONS) == ("no-capacity", "budget", "egress",
                                          "unknown-model"), (
            "the four reasons a scheduler refuses a submission with: %r"
            % (s.SERVE_REASONS,))
        assert issubclass(s.EdgeError, world.EstateError), (
            "EdgeError must be a kind of estate.EstateError, and its bases are %r"
            % (s.EdgeError.__mro__,))
        assert issubclass(s.EdgeError, ValueError), (
            "a caller's `except ValueError` must still catch it: %r"
            % (s.EdgeError.__mro__,))

    def _fits(s, net):
        gpu1 = net.node("gpu-1")
        awq = net.model("north-8b-awq")
        assert s.fits(awq, gpu1) == (True, None), (
            "6144 MB on a card of 8192 fits, and the answer was %r" % (s.fits(awq, gpu1),))
        card = _machine(gpu1, gpu_memory_mb=8000)
        exact = _record(net, "north-8b-awq", memory_mb=7200)
        over = _record(net, "north-8b-awq", memory_mb=7201)
        assert s.fits(exact, card) == (True, None), (
            "exactly 90 percent of the card fits, and 7200 MB on 8000 MB was %r"
            % (s.fits(exact, card),))
        assert s.fits(over, card) == (False, "gpu-memory"), (
            "one megabyte past 90 percent does not fit, and 7201 MB on 8000 MB was %r"
            % (s.fits(over, card),))
        assert s.fits(net.model("north-70b-awq"), gpu1) == (False, "gpu-memory"), (
            "a 42000 MB variant on an 8192 MB card does not fit: %r"
            % (s.fits(net.model("north-70b-awq"), gpu1),))
        assert s.fits(net.model("north-8b-gguf-q8"), gpu1) == (False, "gpu-memory"), (
            "9216 MB on an 8192 MB card does not fit: %r"
            % (s.fits(net.model("north-8b-gguf-q8"), gpu1),))
        assert s.fits(net.model("north-8b-gguf-q8"), net.node("gpu-2")) == (True, None), (
            "the same variant fits the bigger card of the same zone: %r"
            % (s.fits(net.model("north-8b-gguf-q8"), net.node("gpu-2")),))
        assert s.fits(awq, net.node("mgmt-1")) == (False, "no-gpu"), (
            "a machine with no card runs nothing: %r" % (s.fits(awq, net.node("mgmt-1")),))
        assert s.fits(awq, _machine(net.node("mgmt-1"), gpu_memory_mb=65536)) == (
            False, "no-gpu"), (
            "a machine with no card has nothing to fit into, whatever its memory says: %r"
            % (s.fits(awq, _machine(net.node("mgmt-1"), gpu_memory_mb=65536)),))
        assert s.fits(awq, _machine(gpu1, gpus=-1)) == (False, "no-gpu"), (
            "a card count below zero is still no card at all: %r"
            % (s.fits(awq, _machine(gpu1, gpus=-1)),))
        assert s.fits(awq, _machine(net.node("app-2"), memory_mb=65536)) == (
            False, "no-gpu"), (
            "the node's own RAM is not a card: %r"
            % (s.fits(awq, _machine(net.node("app-2"), memory_mb=65536)),))
        strange = _record(net, "north-8b-awq", quant="int8")
        assert s.fits(strange, gpu1) == (False, "unknown-quant"), (
            "a quantisation of the catalogue's own list only: %r" % (s.fits(strange, gpu1),))
        huge = _record(net, "north-8b-awq", quant="int8", memory_mb=100000)
        assert s.fits(huge, gpu1) == (False, "unknown-quant"), (
            "the quantisation is judged before the memory, and a variant with both wrong "
            "was %r" % (s.fits(huge, gpu1),))
        assert s.fits("north-8b-awq", gpu1) == (False, "unknown-model"), (
            "a name is not a record this function holds a catalogue for: %r"
            % (s.fits("north-8b-awq", gpu1),))
        assert s.fits(awq, "gpu-1") == (False, "unknown-node"), (
            "a node named rather than given is unknown here too: %r" % (s.fits(awq, "gpu-1"),))
        assert s.fits("north-8b-awq", "gpu-1") == (False, "unknown-model"), (
            "with both arguments names, the model's own reason comes first: %r"
            % (s.fits("north-8b-awq", "gpu-1"),))
        _refuses(s.EdgeError, "a model that is a list",
                 lambda: s.fits([awq], gpu1), names=("model", "not a mapping"))
        _refuses(s.EdgeError, "a model missing its memory_mb",
                 lambda: s.fits(_without(awq, "memory_mb"), gpu1),
                 names=("model", "memory_mb"))
        _refuses(s.EdgeError, "a model carrying a field of its own",
                 lambda: s.fits(_record(net, "north-8b-awq", zone="gpu"), gpu1),
                 names=("model",))
        _refuses(s.EdgeError, "a node missing its gpus",
                 lambda: s.fits(awq, _without(gpu1, "gpus")), names=("node", "gpus"))
        _refuses(s.EdgeError, "a card whose memory is a word",
                 lambda: s.fits(awq, _machine(gpu1, gpu_memory_mb="eight")),
                 names=("gpu_memory_mb",))
        _refuses(s.EdgeError, "a machine whose card count is a word",
                 lambda: s.fits(awq, _machine(gpu1, gpus="one")), names=("gpus",))
        _refuses(s.EdgeError, "a model whose memory is a bool",
                 lambda: s.fits(_record(net, "north-8b-awq", memory_mb=True), gpu1),
                 names=("memory_mb",))

    def _place(s, net):
        gpu1 = net.node("gpu-1")
        chosen = s.place(net.models(), net.usable("gpu"), "gpu")
        assert chosen == (net.model("north-8b-fp16"), net.node("gpu-2"), None), (
            "the best variant the GPU zone can run is the 88-quality fp16 on the bigger "
            "card, and place answered %r" % (chosen,))
        assert s.place(net.models(), net.usable("mgmt"), "mgmt") == (None, None, "no-gpu"), (
            "the management zone's machine has no card: %r"
            % (s.place(net.models(), net.usable("mgmt"), "mgmt"),))
        assert s.place(net.models(), net.usable("app"), "app") == (None, None, "no-gpu"), (
            "no machine of the app zone has a card: %r"
            % (s.place(net.models(), net.usable("app"), "app"),))
        assert s.place(net.models(), net.usable("data"), "data") == (None, None, "no-gpu"), (
            "the data zone's machine has no card either: %r"
            % (s.place(net.models(), net.usable("data"), "data"),))
        assert s.place(net.models(), (gpu1,), "app") == (None, None, "zone"), (
            "a card exists, but not in the zone that was asked for: %r"
            % (s.place(net.models(), (gpu1,), "app"),))
        assert s.place(net.models(), (), "gpu") == (None, None, "unknown-node"), (
            "no machines at all is not a placement: %r"
            % (s.place(net.models(), (), "gpu"),))
        assert s.place((), net.nodes(), "gpu") == (None, None, "unknown-model"), (
            "no models at all is not a placement either: %r"
            % (s.place((), net.nodes(), "gpu"),))
        assert s.place(("north-8b-awq",), net.nodes(), "gpu") == (None, None,
                                                                  "unknown-model"), (
            "a catalogue of names is a catalogue this function cannot read: %r"
            % (s.place(("north-8b-awq",), net.nodes(), "gpu"),))
        assert s.place(net.models(), ("gpu-1",), "gpu") == (None, None, "unknown-node"), (
            "a machine named rather than given is unknown here too: %r"
            % (s.place(net.models(), ("gpu-1",), "gpu"),))
        assert s.place((net.model("north-70b-awq"),), net.usable("gpu"), "gpu") == (
            None, None, "gpu-memory"), (
            "the only variant is too big for every card in the zone: %r"
            % (s.place((net.model("north-70b-awq"),), net.usable("gpu"), "gpu"),))
        awkward = _record(net, "north-8b-awq", quant="int8", memory_mb=100000)
        assert s.place((awkward,), net.usable("gpu"), "gpu") == (None, None,
                                                                 "unknown-quant"), (
            "the best variant's quantisation is the reason it cannot run there: %r"
            % (s.place((awkward,), net.usable("gpu"), "gpu"),))
        quick = _record(net, "north-8b-awq", name="quick", tokens_per_tick=901)
        slow = _record(net, "north-8b-awq", name="slow", tokens_per_tick=700)
        assert s.place((slow, quick), (gpu1,), "gpu")[0] is quick, (
            "equal quality is decided by the higher tokens_per_tick: %r"
            % (s.place((slow, quick), (gpu1,), "gpu"),))
        assert s.place((quick, slow), (gpu1,), "gpu")[0] is quick, (
            "the throughput tie-break does not depend on the order the models arrived "
            "in: %r" % (s.place((quick, slow), (gpu1,), "gpu"),))
        a_low = _record(net, "north-8b-awq", name="a-low", quality=70)
        z_high = _record(net, "north-8b-awq", name="z-high", quality=70)
        assert s.place((z_high, a_low), (gpu1,), "gpu")[0] is a_low, (
            "equal quality and throughput are decided by the name: %r"
            % (s.place((z_high, a_low), (gpu1,), "gpu"),))
        assert s.place((a_low, z_high), (gpu1,), "gpu")[0] is a_low, (
            "the name tie-break does not depend on the order either: %r"
            % (s.place((a_low, z_high), (gpu1,), "gpu"),))
        top = _record(net, "north-8b-awq", name="top", quality=99)
        assert s.place((quick, top), (gpu1,), "gpu")[0] is top, (
            "quality decides before throughput: %r" % (s.place((quick, top), (gpu1,), "gpu"),))
        assert s.place((top, quick), (gpu1,), "gpu")[0] is top, (
            "and it decides before the name: %r" % (s.place((top, quick), (gpu1,), "gpu"),))
        together = (net.model("north-70b-awq"), awkward)
        assert s.place(together, net.usable("gpu"), "gpu") == (None, None, "gpu-memory"), (
            "the reason is the best variant's own, and the 92-quality one is refused for "
            "its memory rather than the last one tried for its quantisation: %r"
            % (s.place(together, net.usable("gpu"), "gpu"),))
        _refuses(s.EdgeError, "a model whose quality is a word",
                 lambda: s.place((_record(net, "north-8b-awq", quality="high"),),
                                 net.usable("gpu"), "gpu"), names=("quality",))
        _refuses(s.EdgeError, "a zone the customer's network does not have",
                 lambda: s.place(net.models(), net.nodes(), "nowhere"), names=("nowhere",))
        _refuses(s.EdgeError, "models given as one record instead of a tuple",
                 lambda: s.place(net.model("north-8b-awq"), net.nodes(), "gpu"),
                 names=("models",))
        _refuses(s.EdgeError, "nodes given as one record instead of a tuple",
                 lambda: s.place(net.models(), net.node("gpu-1"), "gpu"), names=("nodes",))
        _refuses(s.EdgeError, "a model record missing a field",
                 lambda: s.place((_without(net.model("north-8b-awq"), "quality"),),
                                 net.usable("gpu"), "gpu"), names=("model", "quality"))
        _refuses(s.EdgeError, "a node record missing a field",
                 lambda: s.place(net.models(), (_without(gpu1, "zone"),), "gpu"),
                 names=("node", "zone"))

    def _fresh(s, net, name="north-8b-awq", node="gpu-1", zone="gpu"):
        """A scheduler wired the way a deployment is: the catalogue's own records."""
        return s.Scheduler(net.model(name), net.node(node), net, zone)

    def _queueing(s, net):
        sch = _fresh(s, net)
        offered = sch.submit("t-1", 900, 0)
        assert tuple(offered) == tuple(s.SUBMISSION_KEYS), (
            "a submission carries its five fields in this order: %r" % (offered,))
        assert offered == {"name": "t-1", "tokens": 900, "tick": 0, "state": "queued",
                           "waiting": 0}, (
            "an accepted submission is queued, having waited nothing yet: %r" % (offered,))
        assert tuple(sch.queue()) == (offered,), (
            "the submission comes back from the queue just as it was offered: %r"
            % (sch.queue(),))
        assert sch.served() == () and sch.refused() == (), (
            "nothing has been served and nothing refused yet: %r, %r"
            % (sch.served(), sch.refused()))
        sch.submit("t-2", 900, 2)
        assert tuple(entry["waiting"] for entry in sch.queue()) == (2, 0), (
            "a queued submission reports the ticks it has waited at the newest tick the "
            "scheduler has been told about: %r" % (sch.queue(),))
        served = sch.drain(2)
        assert tuple(served[0]) == tuple(s.SUBMISSION_KEYS), (
            "a served submission carries the same five fields: %r" % (served,))
        assert served == ({"name": "t-1", "tokens": 900, "tick": 0, "state": "served",
                           "waiting": 2},), (
            "one drain spends 900 tokens, so the first submission finishes and the second "
            "is untouched: %r" % (served,))
        assert sch.served() == ("t-1",), (
            "the names served, in service order: %r" % (sch.served(),))
        still = sch.queue()
        assert len(still) == 1 and still[0]["name"] == "t-2", (
            "the submission that did not finish is still queued: %r" % (still,))
        last = sch.drain(3)
        assert last == ({"name": "t-2", "tokens": 900, "tick": 2, "state": "served",
                         "waiting": 1},), (
            "the next tick serves the next submission, and says how long it waited: %r"
            % (last,))
        assert sch.queue() == () and sch.served() == ("t-1", "t-2"), (
            "the queue is empty and both names are served: %r, %r"
            % (sch.queue(), sch.served()))
        two = _fresh(s, net)
        two.submit("a", 900, 0)
        two.submit("b", 900, 0)
        assert two.drain(1) == ({"name": "a", "tokens": 900, "tick": 0, "state": "served",
                                 "waiting": 1},), (
            "one drain serves at most tokens_per_tick, never the whole queue: %r"
            % (two.drain(1),))
        assert two.drain(2) == ({"name": "b", "tokens": 900, "tick": 0, "state": "served",
                                 "waiting": 2},), (
            "the second submission is served by the second tick: %r" % (two.drain(2),))
        slow = _fresh(s, net)
        offered = slow.submit("twice", 1800, 0)
        assert offered["state"] == "queued", (
            "two ticks of tokens is within the budget: %r" % (offered,))
        assert slow.drain(1) == (), (
            "a submission larger than one tick is not served by one tick: %r"
            % (slow.drain(1),))
        waiting = slow.queue()
        assert len(waiting) == 1 and waiting[0]["waiting"] == 1, (
            "the unserved part waits, and the queue says so: %r" % (waiting,))
        done = slow.drain(2)
        assert done == ({"name": "twice", "tokens": 1800, "tick": 0, "state": "served",
                         "waiting": 2},), (
            "a submission is served once its own last token is spent: %r" % (done,))
        stale = _fresh(s, net)
        stale.submit("s-1", 100, 5)
        late = stale.submit("s-2", 100, 1)
        assert late["waiting"] == 4, (
            "the ticks a submission has waited are measured at the newest tick the "
            "scheduler has been told about, not at its own: %r" % (late,))
        assert tuple(entry["waiting"] for entry in stale.queue()) == (0, 4), (
            "and the queue reports the two of them the same way: %r" % (stale.queue(),))

    def _refusing(s, net, pub):
        edge = _fresh(s, net)
        allowed = edge.submit("edge", 2700, 0)
        assert allowed["state"] == "queued", (
            "three ticks of waiting is the budget itself, and is accepted: %r" % (allowed,))
        beyond = edge.submit("beyond", 1, 1)
        assert beyond == {"name": "beyond", "tokens": 1, "tick": 1, "state": "refused",
                          "waiting": 0}, (
            "one token past the budget is refused, and says so: %r" % (beyond,))
        assert edge.refused() == (("beyond", "budget"),), (
            "a refused submission is remembered with its reason, in refusal order: %r"
            % (edge.refused(),))
        assert [entry["name"] for entry in edge.queue()] == ["edge"], (
            "the refused submission took no queue slot: %r" % (edge.queue(),))
        lonely = _fresh(s, net)
        refused = lonely.submit("over", 2701, 0)
        assert refused["state"] == "refused" and lonely.queue() == (), (
            "a submission too large to be served inside the budget is refused: %r, %r"
            % (refused, lonely.queue()))
        full = _fresh(s, net)
        for index in range(4):
            seat = full.submit("f-%d" % index, 675, 0)
            assert seat["state"] == "queued", (
                "the queue holds four submissions, and the one numbered %d was not "
                "queued: %r" % (index, seat))
        fifth = full.submit("fifth", 675, 0)
        assert fifth["state"] == "refused" and fifth["waiting"] == 0, (
            "a fifth submission is refused rather than queued: %r" % (fifth,))
        assert full.refused() == (("fifth", "no-capacity"),), (
            "the full queue's own reason comes before the wait this submission would "
            "have had (four 675-token seats are already four ticks of work): %r"
            % (full.refused(),))
        assert len(full.queue()) == 4 and "fifth" not in [e["name"] for e in full.queue()], (
            "a refusal takes no queue slot: %r" % (full.queue(),))
        egress = s.Scheduler(net.model("north-8b-awq"), net.node("gpu-1"), pub, "gpu")
        assert egress.drain(9) == (), (
            "a scheduler with nothing queued drains nothing: %r" % (egress.drain(9),))
        refused = egress.submit("t-1", 900, 2)
        assert refused == {"name": "t-1", "tokens": 900, "tick": 2, "state": "refused",
                           "waiting": 0}, (
            "a zone that reaches public serves nothing at all, and a refusal reports no "
            "waiting even at a tick before the newest one it has been told about: %r"
            % (refused,))
        assert egress.refused() == (("t-1", "egress"),), (
            "the refusal names the zone's own reason: %r" % (egress.refused(),))
        assert egress.queue() == () and egress.drain(1) == () and egress.served() == (), (
            "nothing was queued and nothing was dequeued: %r, %r, %r"
            % (egress.queue(), egress.drain(1), egress.served()))
        assert pub.stats()["attempts"] == 0, (
            "the refusal is a lookup and not a reach-out, so the network recorded "
            "nothing: %r" % (pub.stats(),))
        ghost = s.Scheduler("north-99b", "gpu-1", net, "gpu")
        refused = ghost.submit("t-1", 900, 0)
        assert refused["state"] == "refused", (
            "a model the catalogue does not hold cannot serve: %r" % (refused,))
        assert ghost.refused() == (("t-1", "unknown-model"),), (
            "and the reason is the one a model the catalogue does not hold carries: %r"
            % (ghost.refused(),))
        assert ghost.drain(1) == () and ghost.queue() == (), (
            "a scheduler with no model to run serves nothing: %r, %r"
            % (ghost.drain(1), ghost.queue()))
        foreign = _record(net, "north-8b-awq", name="ghost")
        refused = s.Scheduler(foreign, net.node("gpu-1"), net, "gpu").submit("t-1", 900, 0)
        assert refused["state"] == "refused", (
            "a record the catalogue does not hold is the same unknown model: %r"
            % (refused,))
        named = s.Scheduler("north-8b-awq", "gpu-1", net, "gpu")
        seat = named.submit("t-1", 900, 0)
        assert seat["state"] == "queued", (
            "a name the catalogue does hold is resolved into its record: %r" % (seat,))

    def _wiring(s, net):
        awq = net.model("north-8b-awq")
        gpu1 = net.node("gpu-1")
        _refuses(s.EdgeError, "a zone that is not one of the customer's",
                 lambda: s.Scheduler(awq, gpu1, net, "nowhere"), names=("nowhere",))
        _refuses(s.EdgeError, "a network that cannot answer this stage",
                 lambda: s.Scheduler(awq, gpu1, None, "gpu"), names=("network", "reaches"))
        _refuses(s.EdgeError, "a node the network does not hold",
                 lambda: s.Scheduler(awq, "gpu-9", net, "gpu"), names=("gpu-9",))
        _refuses(s.EdgeError, "a node of another zone",
                 lambda: s.Scheduler(awq, net.node("mgmt-1"), net, "gpu"),
                 names=("mgmt-1", "is in 'mgmt'", "serves 'gpu'"))
        _refuses(s.EdgeError, "a model that does not fit its node",
                 lambda: s.Scheduler(net.model("north-70b-awq"), gpu1, net, "gpu"),
                 names=("north-70b-awq", "gpu-1", "gpu-memory"))
        _refuses(s.EdgeError, "a node record missing a field",
                 lambda: s.Scheduler(awq, _without(gpu1, "zone"), net, "gpu"),
                 names=("node", "zone"))
        guards = _fresh(s, net)
        _refuses(s.EdgeError, "a submission with an empty name",
                 lambda: guards.submit("", 10, 0), names=("empty",))
        _refuses(s.EdgeError, "a submission of no tokens",
                 lambda: guards.submit("zero", 0, 0), names=("zero", "tokens"))
        _refuses(s.EdgeError, "a submission of a word for tokens",
                 lambda: guards.submit("word", "ten", 0), names=("ten",))
        _refuses(s.EdgeError, "a submission of a bool for tokens",
                 lambda: guards.submit("bool", True, 0), names=("tokens",))
        _refuses(s.EdgeError, "a tick that is a word",
                 lambda: guards.submit("late", 10, "zero"), names=("tick",))
        _refuses(s.EdgeError, "a submission whose name is not a string",
                 lambda: guards.submit(7, 10, 0), names=("name",))
        guards.submit("late", 10, 5)
        _refuses(s.EdgeError, "a drain at a tick before a queued submission's own",
                 lambda: guards.drain(4), names=("late", "5", "4"))
        _refuses(s.EdgeError, "a drain at a tick that is a word",
                 lambda: guards.drain("four"), names=("tick",))

    _PUBLIC = {"mgmt": ("telemetry",), "app": ("registry", "storage"), "data": (),
               "gpu": ("public",)}

    def _world(net, pub):
        zero = {"attempts": 0, "allowed": 0, "blocked": 0, "pulls": 0, "installs": 0}
        assert net.stats() == zero, (
            "this stage asks the customer's network questions and writes nothing: %r"
            % (net.stats(),))
        assert tuple(net.log()) == (), (
            "the network's own log is empty after all of it: %r" % (net.log(),))
        assert pub.stats() == zero and tuple(pub.log()) == (), (
            "a refused submission left no trace in the world's own record: %r, %r"
            % (pub.stats(), pub.log()))

    def _workload(s, world_network):
        """One whole run of this stage: every answer it gives, in one tuple."""
        net = world_network.Network.build(7)
        pub = world_network.Network(_PUBLIC, net.images(), (), net.nodes(), net.models())
        pairs = []
        for model in net.models():
            for node in net.nodes():
                pairs.append(s.fits(model, node))
        placed = [s.place(net.models(), net.nodes(), zone) for zone in world_network.ZONES]
        placed.append(s.place(net.models(), net.usable("gpu"), "gpu"))
        sch = s.Scheduler("north-8b-awq", "gpu-1", net, "gpu")
        transcript = [sch.submit("a", 900, 0), sch.submit("b", 1800, 1),
                      sch.submit("c", 2701, 1), sch.queue(), sch.drain(2), sch.queue(),
                      sch.drain(3), sch.drain(4), sch.queue(), sch.served(), sch.refused()]
        egress = s.Scheduler("north-8b-awq", "gpu-1", pub, "gpu")
        transcript.append(egress.submit("x", 900, 0))
        transcript.append(egress.refused())
        return (tuple(pairs), tuple(placed), tuple(transcript), net.stats(), pub.stats())

    def _twice(s, world_network):
        one = _workload(s, world_network)
        two = _workload(s, world_network)
        assert len(one[0]) == 30, (
            "the workload judges every variant against every machine: %r" % (len(one[0]),))
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function of "
            "its input: %r vs %r" % (one, two))

    import stage_08 as s
    import estate as world
    import network
    net = network.Network.build(7)
    pub = network.Network(_PUBLIC, net.images(), (), net.nodes(), net.models())
    _constants(s, world)
    _fits(s, net)
    _place(s, net)
    _queueing(s, net)
    _refusing(s, net, pub)
    _wiring(s, net)
    _world(net, pub)
    _twice(s, network)

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "fde-from-scratch"

    SPANS = (
        (0, "support", "north-8b-awq", 1000, 200, 2, "T-1", True),
        (1, "support", "north-8b-awq", 500, 100, 2, "T-2", False),
        (2, "support", "north-70b-awq", 200, 20, 2, "T-1", True),
        (3, "finance", "hosted-frontier", 100, 10, 3, "F-9", False),
        (4, "research", "north-8b-awq", 100, 0, 1, "", True),
        (8, "support", "north-8b-awq", 1000, 200, 2, "T-1", True),
        (9, "finance", "hosted-frontier", 100, 10, 3, "F-9", False),
        (16, "support", "north-8b-awq", 1000, 0, 1, "T-3", True),
        (17, "support", "north-8b-awq", 500, 0, 1, "T-4", True),
        (18, "support", "north-8b-awq", 0, 0, 1, "T-5", True),
        (5, "procurement", "north-8b-awq", 0, 0, 1, "P-1", True),
        (13, "procurement", "north-8b-awq", 0, 0, 1, "P-2", True),
    )

    def _repo(start=None):
        for candidate_start in (os.environ.get("FDE_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set FDE_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _pulse(world):
        """The fixture meter: four teams over three days, and one it cannot bill.

        `research` is a team the customer's own `MINUTES_SAVED` does not carry, and the
        two `procurement` spans are recorded last so that the meter's own order and the
        tick order are not the same order.
        """
        pulse = world.Meter()
        for span in SPANS:
            pulse.span(span[0], span[1], span[2], span[3], span[4], span[5], span[6],
                       span[7])
        return pulse

    def _zero(world):
        """A meter whose spend is free: nothing cost anything, a ticket was resolved."""
        pulse = world.Meter()
        pulse.span(0, "procurement", "north-8b-awq", 0, 0, 0, "P-1", True)
        return pulse

    def _empty(world):
        """A meter with no spans in it at all."""
        return world.Meter()

    def _unresolved(world):
        """A meter that spent cents on a ticket and resolved nothing at all."""
        pulse = world.Meter()
        pulse.span(0, "finance", "hosted-frontier", 100, 10, 3, "F-9", False)
        return pulse

    ROLLED = (
        {"team": "finance", "model": "hosted-frontier", "spans": 2, "cost_cents": 42,
         "minutes_saved": 0, "resolved": 0},
        {"team": "procurement", "model": "north-8b-awq", "spans": 2, "cost_cents": 0,
         "minutes_saved": 80, "resolved": 2},
        {"team": "research", "model": "north-8b-awq", "spans": 1, "cost_cents": 1,
         "minutes_saved": 0, "resolved": 0},
        {"team": "support", "model": "north-70b-awq", "spans": 1, "cost_cents": 21,
         "minutes_saved": 12, "resolved": 1},
        {"team": "support", "model": "north-8b-awq", "spans": 6, "cost_cents": 63,
         "minutes_saved": 60, "resolved": 5},
    )

    DAY0 = (
        {"team": "finance", "model": "hosted-frontier", "spans": 1, "cost_cents": 21,
         "minutes_saved": 0, "resolved": 0},
        {"team": "procurement", "model": "north-8b-awq", "spans": 1, "cost_cents": 0,
         "minutes_saved": 40, "resolved": 1},
        {"team": "research", "model": "north-8b-awq", "spans": 1, "cost_cents": 1,
         "minutes_saved": 0, "resolved": 0},
        {"team": "support", "model": "north-70b-awq", "spans": 1, "cost_cents": 21,
         "minutes_saved": 12, "resolved": 1},
        {"team": "support", "model": "north-8b-awq", "spans": 2, "cost_cents": 27,
         "minutes_saved": 12, "resolved": 1},
    )

    DAY2 = (
        {"team": "support", "model": "north-8b-awq", "spans": 3, "cost_cents": 18,
         "minutes_saved": 36, "resolved": 3},
    )

    DASH0 = {"day": 0, "teams": ("finance", "procurement", "research", "support"),
             "cost_cents": 70, "minutes_saved": 52, "resolved": 2,
             "cost_per_resolution_cents": 35, "roi_percent": 3342}

    DASH1 = {"day": 1, "teams": ("finance", "procurement", "support"),
             "cost_cents": 39, "minutes_saved": 52, "resolved": 2,
             "cost_per_resolution_cents": 19, "roi_percent": 6000}

    DASH2 = {"day": 2, "teams": ("support",), "cost_cents": 18, "minutes_saved": 36,
             "resolved": 3, "cost_per_resolution_cents": 6, "roi_percent": 9000}

    DASH_NONE = {"day": 9, "teams": (), "cost_cents": 0, "minutes_saved": 0,
                 "resolved": 0, "cost_per_resolution_cents": 0, "roi_percent": None}

    def _constants(s, world):
        assert tuple(s.ROLLUP_KEYS) == ("team", "model", "spans", "cost_cents",
                                        "minutes_saved", "resolved"), (
            "a rollup row is these six fields in this order: %r" % (s.ROLLUP_KEYS,))
        assert tuple(s.DASHBOARD_KEYS) == ("day", "teams", "cost_cents", "minutes_saved",
                                           "resolved", "cost_per_resolution_cents",
                                           "roi_percent"), (
            "a dashboard is these seven fields in this order: %r"
            % (s.DASHBOARD_KEYS,))
        assert tuple(s.ANOMALY_KEYS) == ("team", "day", "cost_cents", "baseline_cents",
                                         "ratio_percent"), (
            "an anomaly is these five fields in this order: %r" % (s.ANOMALY_KEYS,))
        assert s.RATE_CENTS_PER_MINUTE == 45, (
            "a saved minute is worth the customer's own 45 cents: %r"
            % (s.RATE_CENTS_PER_MINUTE,))
        assert s.ROI_BASIS == 100, (
            "a ratio is a percentage, so the basis is 100: %r" % (s.ROI_BASIS,))
        assert issubclass(s.MetricError, world.EstateError), (
            "MetricError must be a kind of estate.EstateError, and its bases are %r"
            % (s.MetricError.__mro__,))
        assert issubclass(s.MetricError, ValueError), (
            "a caller's `except ValueError` must still catch it: %r"
            % (s.MetricError.__mro__,))

    def _keys(s, rows, what):
        for row in rows:
            assert tuple(row) == tuple(s.ROLLUP_KEYS), (
                "%s is built with the keys %r, and ROLLUP_KEYS says %r"
                % (what, tuple(row), tuple(s.ROLLUP_KEYS)))

    def _rollup(s, world):
        rows = s.rollup(_pulse(world))
        assert tuple(rows) == ROLLED, (
            "the rollup of four teams over three days is not what was counted: %r"
            % (rows,))
        _keys(s, rows, "a rollup row")
        pairs = [(row["team"], row["model"]) for row in rows]
        assert pairs == sorted(pairs), (
            "rollups are sorted by (team, model), and these are %r" % (pairs,))
        assert s.rollup(_empty(world)) == (), (
            "a meter with no spans rolls up to nothing: %r" % (s.rollup(_empty(world)),))

    def _team_day(s, world):
        day_one = (
            {"team": "finance", "model": "hosted-frontier", "spans": 1,
             "cost_cents": 21, "minutes_saved": 0, "resolved": 0},
            {"team": "procurement", "model": "north-8b-awq", "spans": 1,
             "cost_cents": 0, "minutes_saved": 40, "resolved": 1},
            {"team": "support", "model": "north-8b-awq", "spans": 1, "cost_cents": 18,
             "minutes_saved": 12, "resolved": 1},
        )
        pulse = _pulse(world)
        rows = s.team_day(pulse, 0)
        assert tuple(rows) == DAY0, (
            "day 0's rows are its own day's spans and nobody else's: %r" % (rows,))
        _keys(s, rows, "a team_day row")
        assert tuple(s.team_day(pulse, 1)) == day_one, (
            "day 1 is the spans of ticks 8 to 15, counted on their own: %r"
            % (s.team_day(pulse, 1),))
        assert tuple(s.team_day(pulse, 2)) == DAY2, (
            "day 2's rows are its own day's spans only: %r" % (s.team_day(pulse, 2),))
        assert s.team_day(pulse, 3) == (), (
            "a day no span reached is an empty tuple, not a row of zeros: %r"
            % (s.team_day(pulse, 3),))
        assert s.team_day(_empty(world), 0) == (), (
            "an empty meter has no rows for any day: %r"
            % (s.team_day(_empty(world), 0),))

    def _dashboard(s, world):
        pulse = _pulse(world)
        for day, want in ((0, DASH0), (1, DASH1), (2, DASH2), (9, DASH_NONE)):
            got = s.dashboard(pulse, day)
            assert tuple(got) == tuple(s.DASHBOARD_KEYS), (
                "a dashboard is built with the keys %r, and DASHBOARD_KEYS says %r"
                % (tuple(got), tuple(s.DASHBOARD_KEYS)))
            assert got == want, (
                "the dashboard of day %d is not what its own spans were counted to "
                "be: %r" % (day, got))
        blank = dict(DASH_NONE)
        blank["day"] = 3
        assert s.dashboard(pulse, 3) == blank, (
            "a day with no spans is a full record of zeros carrying the day it was "
            "asked about: %r" % (s.dashboard(pulse, 3),))
        assert s.dashboard(_empty(world), 7) == dict(blank, day=7), (
            "an empty meter still answers a dashboard for the day it was asked about: "
            "%r" % (s.dashboard(_empty(world), 7),))
        free = s.dashboard(_zero(world), 0)
        assert free["minutes_saved"] == 40 and free["cost_cents"] == 0, (
            "a free resolution still saves the customer's minutes: %r" % (free,))
        assert free["roi_percent"] is None, (
            "zero cents of spend has no return to report, however many minutes it "
            "saved: %r" % (free,))
        assert free["cost_per_resolution_cents"] == 0, (
            "a resolution that cost nothing costs nothing each: %r" % (free,))
        unpaid = s.dashboard(_unresolved(world), 0)
        assert unpaid == {"day": 0, "teams": ("finance",), "cost_cents": 21,
                          "minutes_saved": 0, "resolved": 0,
                          "cost_per_resolution_cents": 0, "roi_percent": 0}, (
            "a day that spent and resolved nothing costs nothing per resolution and "
            "returns nothing, rather than raising: %r" % (unpaid,))

    def _anomalies(s, world):
        pulse = _pulse(world)
        finance = {"team": "finance", "day": 0, "cost_cents": 21,
                   "baseline_cents": 21, "ratio_percent": 100}
        support = {"team": "support", "day": 0, "cost_cents": 48,
                   "baseline_cents": 28, "ratio_percent": 171}
        for entry in s.anomalies(pulse, 0, 150):
            assert tuple(entry) == tuple(s.ANOMALY_KEYS), (
                "an anomaly is built with the keys %r, and ANOMALY_KEYS says %r"
                % (tuple(entry), tuple(s.ANOMALY_KEYS)))
        assert tuple(s.anomalies(pulse, 0, 150)) == (support,), (
            "support is the only team at 150% of its own mean on day 0: %r"
            % (s.anomalies(pulse, 0, 150),))
        assert tuple(s.anomalies(pulse, 0, 100)) == (finance, support), (
            "at the threshold a team exactly at its own mean is in the report, and the "
            "answer is sorted by team: %r" % (s.anomalies(pulse, 0, 100),))
        assert tuple(s.anomalies(pulse, 0, 171)) == (support,), (
            "support is at exactly 171% of its mean, so 171 is still inclusive: %r"
            % (s.anomalies(pulse, 0, 171),))
        assert s.anomalies(pulse, 0, 172) == (), (
            "one percent past support's own ratio is past the report: %r"
            % (s.anomalies(pulse, 0, 172),))
        assert tuple(s.anomalies(pulse, 2, 60)) == (
            dict(support, day=2, cost_cents=18, ratio_percent=64),), (
            "the day asked about is the day compared and the day echoed: %r"
            % (s.anomalies(pulse, 2, 60),))
        assert tuple(s.anomalies(pulse, 3, 0)) == (
            dict(finance, day=3, cost_cents=0, ratio_percent=0),
            dict(support, day=3, cost_cents=0, ratio_percent=0)), (
            "a day a team has no span in still costs that team nothing, and zero "
            "percent of a mean is met: %r" % (s.anomalies(pulse, 3, 0),))
        teams = [entry["team"] for entry in s.anomalies(pulse, 0, 0)]
        assert teams == ["finance", "support"], (
            "research has one day of history and procurement's mean is zero, so "
            "neither has a baseline to stand out from: %r" % (teams,))
        assert s.anomalies(_empty(world), 0, 100) == (), (
            "a meter with no spans has no team to stand out: %r"
            % (s.anomalies(_empty(world), 0, 100),))

    def _unattributed(s, world):
        pulse = _pulse(world)
        assert s.unattributed(pulse, ("support",)) == (
            (3, "finance", "F-9"), (4, "research", ""), (9, "finance", "F-9"),
            (5, "procurement", "P-1"), (13, "procurement", "P-2")), (
            "the spans of every team the caller did not name, in the meter's own span "
            "order — the procurement spans were recorded after the finance span of "
            "tick 9, and a span whose ticket is empty is still a stranger's span: %r"
            % (s.unattributed(pulse, ("support",)),))
        assert s.unattributed(pulse, ("support", "finance", "procurement",
                                      "research")) == (), (
            "a span whose team the caller named is not unattributed: %r"
            % (s.unattributed(pulse, ("support", "finance", "procurement",
                                      "research")),))
        assert s.unattributed(pulse, ()) == tuple(
            (span[0], span[1], span[6]) for span in SPANS), (
            "with no team named, every span is named, in the meter's own order: %r"
            % (s.unattributed(pulse, ()),))
        assert s.unattributed(_empty(world), ("support",)) == (), (
            "an empty meter has no stranger's span to name: %r"
            % (s.unattributed(_empty(world), ("support",)),))

    def _refusals(s, world):
        pulse = _pulse(world)
        _refuses(s.MetricError, "a meter that cannot answer spans()",
                 lambda: s.rollup(42), names=("42",))
        _refuses(s.MetricError, "a meter that is a string",
                 lambda: s.rollup("pulse"), names=("pulse",))
        _refuses(s.MetricError, "a day that is not a whole number",
                 lambda: s.team_day(pulse, "day"), names=("day",))
        _refuses(s.MetricError, "a bool where a day belongs",
                 lambda: s.dashboard(pulse, True), names=("True",))
        _refuses(s.MetricError, "a dashboard asked of something that is no meter",
                 lambda: s.dashboard(0, 0), names=("0",))
        _refuses(s.MetricError, "a threshold that is not a whole number",
                 lambda: s.anomalies(pulse, 0, "150"), names=("150",))
        _refuses(s.MetricError, "a day that is not a whole number, among the anomalies",
                 lambda: s.anomalies(pulse, "day", 100), names=("day",))
        both = _refuses(s.MetricError, "a day and a threshold both wrong",
                        lambda: s.anomalies(pulse, "day", "150"), names=("day",))
        assert "150" not in str(both), (
            "the day is read before the threshold, so the day's refusal is the one "
            "that comes back: %r" % (str(both),))
        _refuses(s.MetricError, "a negative threshold, which would flag every team",
                 lambda: s.anomalies(pulse, 0, -5), names=("-5",))
        _refuses(s.MetricError, "a single team name where a tuple of them belongs",
                 lambda: s.unattributed(pulse, "support"), names=("support",))
        _refuses(s.MetricError, "a team name that is not a string",
                 lambda: s.unattributed(pulse, ("support", 7)), names=("7",))
        _refuses(s.MetricError, "a tuple of teams asked of something that is no meter",
                 lambda: s.unattributed(None, ()), names=("None",))
        ordering = _refuses(s.MetricError, "a meter and a day both wrong",
                            lambda: s.team_day("pulse", "day"), names=("pulse",))
        assert "day" not in str(ordering), (
            "the meter is what a call reads first, so its refusal is the one that "
            "comes back: %r" % (str(ordering),))

    def _ledger(s, world, estate):
        pulse = _pulse(world)
        spans_before = pulse.spans()
        before = pulse.stats()
        rows = s.rollup(pulse)
        day = s.team_day(pulse, 0)
        board = s.dashboard(pulse, 0)
        s.anomalies(pulse, 0, 100)
        s.unattributed(pulse, ("support",))
        _refuses(s.MetricError, "a day that is not a whole number, mid-run",
                 lambda: s.team_day(pulse, "day"), names=("day",))
        assert pulse.stats() == before, (
            "the metric stage wrote into the customer's own meter: %r vs %r"
            % (pulse.stats(), before))
        assert pulse.spans() == spans_before, (
            "the meter's own log grew while it was being read: %r spans became %r"
            % (len(spans_before), len(pulse.spans())))
        assert sum(row["cost_cents"] for row in rows) == before["cost_cents"], (
            "the rollup's cents are the meter's own cents, recounted span by span: "
            "%r vs %r" % (sum(row["cost_cents"] for row in rows), before["cost_cents"]))
        assert sum(row["spans"] for row in rows) == before["spans"], (
            "every span lands in exactly one rollup row: %r vs %r"
            % (sum(row["spans"] for row in rows), before["spans"]))
        assert board["cost_cents"] == sum(
            span["cost_cents"] for span in spans_before
            if span["tick"] // estate.TICKS_PER_DAY == 0), (
            "the dashboard's cost is its own day's spans and no others: %r" % (board,))
        assert sum(row["cost_cents"] for row in day) == board["cost_cents"], (
            "a day's rows and that day's dashboard count the same cents: %r vs %r"
            % (sum(row["cost_cents"] for row in day), board))
        days = sorted({span["tick"] // estate.TICKS_PER_DAY for span in spans_before})
        assert sum(s.dashboard(pulse, one)["cost_cents"]
                   for one in days) == before["cost_cents"], (
            "the days of the meter partition its cents, and one dashboard per day "
            "adds back up to the meter's own counter: %r" % (days,))

    def _twice(s, world):
        def readings():
            pulse = _pulse(world)
            return (s.rollup(pulse),
                    tuple(s.team_day(pulse, day) for day in (0, 1, 2, 3)),
                    tuple(s.dashboard(pulse, day) for day in (0, 1, 2, 9)),
                    tuple(s.anomalies(pulse, day, ratio) for day in (0, 2, 3)
                          for ratio in (0, 100, 171, 172)),
                    s.unattributed(pulse, ("support",)))

        one = readings()
        two = readings()
        assert one == two, (
            "the same meter read twice gives two answers, so a run is not a function "
            "of its inputs: %r vs %r" % (one, two))

    import stage_09 as s
    import estate
    import meter
    _constants(s, estate)
    _rollup(s, meter)
    _team_day(s, meter)
    _dashboard(s, meter)
    _anomalies(s, meter)
    _unattributed(s, meter)
    _refusals(s, meter)
    _ledger(s, meter, estate)
    _twice(s, meter)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "fde-from-scratch"

    IDS = ("c-3", "c-1", "c-6", "c-2", "c-5", "c-4")

    TEAMS = ("support", "finance", "procurement", "support", "finance", "procurement")

    CLASSES = ("po", "amount", "vendor", "po", "amount", "vendor")

    INCUMBENT_PLAN = ("ok", "ok", "wrong", "ok", "ok", "wrong")

    CANDIDATE_PLAN = ("ok", "wrong", None, "ok", "ok", None)

    WRONG = "PO-0000"

    SEEN = "seen: "

    SAMPLE = 30

    def _repo(start=None):
        for candidate_start in (os.environ.get("FDE_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set FDE_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _fixtures(world):
        """Six of the customer's own rows as cases: their dirty text, their PO."""
        picked = world.rows()[:6]
        texts = tuple(row["text"] for row in picked)
        expected = tuple(row["po"] for row in picked)
        cases = tuple({"id": IDS[index], "team": TEAMS[index], "text": texts[index],
                       "expected": expected[index], "class": CLASSES[index]}
                      for index in range(len(texts)))
        return cases, expected, texts

    def _table(texts, expected, plan):
        """What a model answers, keyed by the case's text: a label, `WRONG`, or nothing."""
        table = {}
        for index, text in enumerate(texts):
            if plan[index] == "ok":
                table[text] = expected[index]
            elif plan[index] == "wrong":
                table[text] = WRONG
        return table

    def _model(table):
        def answer(text):
            return table.get(text, None)
        return answer

    def _replay(text):
        return SEEN + text

    def _counted(texts, calls):
        def replay(text):
            calls.append(text)
            return SEEN + text
        return replay

    def _with(record, key, value):
        """A copy of `record` with `key` set to `value`, its place in the order kept."""
        copy = dict(record)
        copy[key] = value
        return copy

    def _without(record, key):
        """A copy of `record` without `key`."""
        return {name: record[name] for name in record if name != key}

    def _constants(s, world):
        assert tuple(s.CASE_KEYS) == ("id", "team", "text", "expected", "class"), (
            "a case carries its id, team, text, expected answer and class, in this "
            "order: %r" % (s.CASE_KEYS,))
        assert tuple(s.SHADOW_KEYS) == ("id", "incumbent", "candidate", "user_sees",
                                        "same"), (
            "a shadow row carries the case, both models' answers, what the user saw and "
            "whether they agreed, in this order: %r" % (s.SHADOW_KEYS,))
        assert tuple(s.GRADE_KEYS) == ("model", "correct", "total", "accuracy_bp"), (
            "a mark carries its model, its correct count, the cases it answered and its "
            "accuracy: %r" % (s.GRADE_KEYS,))
        assert tuple(s.AGREEMENT_KEYS) == ("agree", "disagree", "agreement_bp"), (
            "a calibration carries its agreements, its disagreements and its basis "
            "points: %r" % (s.AGREEMENT_KEYS,))
        assert tuple(s.VERDICTS) == ("ship", "hold", "reject"), (
            "the three words a verdict can be: %r" % (s.VERDICTS,))
        assert tuple(s.VERDICT_REASONS) == ("below-target", "judge-unreliable",
                                            "sample-too-small", "candidate-worse"), (
            "the four reasons a verdict carries, in the order they are decided: %r"
            % (s.VERDICT_REASONS,))
        assert s.MIN_SAMPLE == 30, (
            "a sample below 30 cases holds every verdict, and MIN_SAMPLE is %r"
            % (s.MIN_SAMPLE,))
        assert s.MIN_AGREEMENT_BP == 8000, (
            "a judge below 8000 basis points holds every verdict, and "
            "MIN_AGREEMENT_BP is %r" % (s.MIN_AGREEMENT_BP,))
        assert issubclass(s.EvalError, world.EstateError), (
            "EvalError must be a kind of estate.EstateError, and its bases are %r"
            % (s.EvalError.__mro__,))
        assert issubclass(s.EvalError, ValueError), (
            "a caller's `except ValueError` must still catch it: %r"
            % (s.EvalError.__mro__,))

    def _shadow(s, cases, texts, expected):
        table = _table(texts, expected, INCUMBENT_PLAN)
        others = _table(texts, expected, CANDIDATE_PLAN)
        calls = []
        rows = s.shadow(cases, _model(table), _model(others), _counted(texts, calls))
        assert isinstance(rows, tuple), (
            "a shadow run answers a tuple of rows, and this is a %s"
            % (type(rows).__name__,))
        assert len(rows) == len(cases), (
            "one row per case: %d rows for %d cases" % (len(rows), len(cases)))
        assert calls == list(texts), (
            "the replay is asked once per case, with the case's own text, and it was "
            "asked %r" % (calls,))
        for index, row in enumerate(rows):
            text = texts[index]
            assert tuple(row) == tuple(s.SHADOW_KEYS), (
                "a shadow row's keys, in order, are %r, and this one is %r"
                % (tuple(s.SHADOW_KEYS), tuple(row)))
            assert row["id"] == IDS[index], (
                "the rows follow the cases' own order: row %d is for %r, and it is for %r"
                % (index, IDS[index], row["id"]))
            assert row["incumbent"] == table.get(text), (
                "the incumbent's own answer for %r is %r, and the row carries %r"
                % (text, table.get(text), row["incumbent"]))
            assert row["candidate"] == others.get(text), (
                "the candidate's own answer for %r is %r, and the row carries %r"
                % (text, others.get(text), row["candidate"]))
            assert row["user_sees"] == SEEN + text, (
                "the user sees the replay's answer %r, never the candidate's %r"
                % (SEEN + text, others.get(text)))
            assert isinstance(row["same"], bool), (
                "same is a bool, and this row carries %r" % (row["same"],))
        assert tuple(row["same"] for row in rows) == (True, False, False, True, True,
                                                      False), (
            "same says whether the two models' answers were equal, and here they are %r"
            % ([(table.get(text), others.get(text)) for text in texts],))

    def _grade(s, cases, texts, expected):
        table = _table(texts, expected, INCUMBENT_PLAN)
        others = _table(texts, expected, CANDIDATE_PLAN)
        rows = s.shadow(cases, _model(table), _model(others), _replay)
        grades = s.grade(rows, cases)
        assert isinstance(grades, tuple), (
            "grade answers a tuple of marks, and this is a %s" % (type(grades).__name__,))
        assert tuple(record["model"] for record in grades) == ("candidate", "incumbent"), (
            "the marks are sorted by model, so the candidate's come first: %r"
            % ([record["model"] for record in grades],))
        for record in grades:
            assert tuple(record) == tuple(s.GRADE_KEYS), (
                "a mark's keys, in order, are %r, and this one is %r"
                % (tuple(s.GRADE_KEYS), tuple(record)))
        assert grades[0] == {"model": "candidate", "correct": 3, "total": 4,
                             "accuracy_bp": 7500}, (
            "the candidate answered four of the six cases and got three of them right, "
            "so its mark is %r" % (grades[0],))
        assert grades[1] == {"model": "incumbent", "correct": 4, "total": 6,
                             "accuracy_bp": 6666}, (
            "the incumbent answered all six cases and got four of them right, so its "
            "mark is %r" % (grades[1],))
        silent = _model({})
        empty = s.grade(s.shadow(cases, silent, silent, _replay), cases)
        assert tuple(record["total"] for record in empty) == (0, 0), (
            "a model that answered nothing is measured on nothing, and these are %r"
            % (empty,))
        assert tuple(record["accuracy_bp"] for record in empty) == (0, 0), (
            "a model that answered nothing has no accuracy to report, and these are %r"
            % (empty,))

    def _calibrate(s, cases, texts, expected):
        labels = {}
        for index, text in enumerate(texts):
            labels[text] = expected[index]
        exact = s.calibrate(_model(labels), cases)
        assert tuple(exact) == tuple(s.AGREEMENT_KEYS), (
            "a calibration's keys, in order, are %r, and this one is %r"
            % (tuple(s.AGREEMENT_KEYS), tuple(exact)))
        assert exact == {"agree": 6, "disagree": 0, "agreement_bp": 10000}, (
            "a judge that agrees with every label agrees at ten thousand basis points: %r"
            % (exact,))
        five = dict(list(labels.items())[:5])
        assert s.calibrate(_model(five), cases) == {"agree": 5, "disagree": 1,
                                                    "agreement_bp": 8333}, (
            "five agreements of six are 8333 basis points, and a case the judge did not "
            "answer is a disagreement")
        half = dict(list(labels.items())[:3])
        assert s.calibrate(_model(half), cases) == {"agree": 3, "disagree": 3,
                                                    "agreement_bp": 5000}, (
            "three agreements of six are half the sample, in basis points")
        assert s.calibrate(_model({}), cases) == {"agree": 0, "disagree": 6,
                                                  "agreement_bp": 0}, (
            "a judge that answered no case agreed with no label, and it is still scored "
            "on the whole labelled sample")
        assert s.calibrate(_model(labels), ()) == {"agree": 0, "disagree": 0,
                                                   "agreement_bp": 0}, (
            "an empty labelled sample has nothing to agree with, and no division by it")

    def _verdict(s, cases, texts, expected):
        table = _table(texts, expected, INCUMBENT_PLAN)
        others = _table(texts, expected, CANDIDATE_PLAN)
        rows = s.shadow(cases, _model(table), _model(others), _replay)
        grades = s.grade(rows, cases)
        reliable = {"agree": 8, "disagree": 2, "agreement_bp": 8000}
        unreliable = {"agree": 7999, "disagree": 2001, "agreement_bp": 7999}
        assert s.verdict(grades, reliable, SAMPLE, 7500) == ("ship", None), (
            "a candidate at exactly the target ships: %r"
            % (s.verdict(grades, reliable, SAMPLE, 7500),))
        assert s.verdict(grades, reliable, SAMPLE, 7501) == ("reject", "below-target"), (
            "a candidate below a target the incumbent also missed is below target: %r"
            % (s.verdict(grades, reliable, SAMPLE, 7501),))
        worse = ({"model": "candidate", "correct": 3, "total": 5, "accuracy_bp": 6000},
                 {"model": "incumbent", "correct": 3, "total": 4, "accuracy_bp": 7000})
        assert s.verdict(worse, reliable, SAMPLE, 7000) == ("reject", "candidate-worse"), (
            "the incumbent met the target the candidate missed, at 7000 exactly: %r"
            % (s.verdict(worse, reliable, SAMPLE, 7000),))
        both_low = ({"model": "candidate", "correct": 3, "total": 5, "accuracy_bp": 6000},
                    {"model": "incumbent", "correct": 2, "total": 4, "accuracy_bp": 5000})
        assert s.verdict(both_low, reliable, SAMPLE, 7000) == ("reject", "below-target"), (
            "nobody reached the target, and that is not the candidate's fault alone: %r"
            % (s.verdict(both_low, reliable, SAMPLE, 7000),))
        assert s.verdict(grades, unreliable, SAMPLE, 7500) == ("hold", "judge-unreliable"), (
            "a judge at 7999 basis points is below MIN_AGREEMENT_BP and holds: %r"
            % (s.verdict(grades, unreliable, SAMPLE, 7500),))
        assert s.verdict(grades, unreliable, SAMPLE - 1, 7500) == ("hold",
                                                                   "judge-unreliable"), (
            "the judge is decided before the sample, so a small sample does not change "
            "its reason: %r" % (s.verdict(grades, unreliable, SAMPLE - 1, 7500),))
        assert s.verdict(grades, reliable, SAMPLE - 1, 7500) == ("hold", "sample-too-small"), (
            "29 cases are below MIN_SAMPLE and hold the verdict: %r"
            % (s.verdict(grades, reliable, SAMPLE - 1, 7500),))
        assert s.verdict(grades, reliable, SAMPLE - 1, 9999) == ("hold",
                                                                 "sample-too-small"), (
            "the sample is decided before the target is consulted at all: %r"
            % (s.verdict(grades, reliable, SAMPLE - 1, 9999),))
        assert s.verdict(grades, reliable, SAMPLE, 10000) == ("reject", "below-target"), (
            "with a sample of 30 the target is consulted, and at 10000 nothing ships: %r"
            % (s.verdict(grades, reliable, SAMPLE, 10000),))

    def _visible(s, cases, texts, expected):
        table = _table(texts, expected, INCUMBENT_PLAN)
        others = _table(texts, expected, CANDIDATE_PLAN)
        rows = s.shadow(cases, _model(table), _model(others), _replay)
        seen = s.user_visible(rows)
        assert isinstance(seen, tuple), (
            "user_visible answers a tuple of pairs, and this is a %s"
            % (type(seen).__name__,))
        assert tuple(pair[0] for pair in seen) == IDS, (
            "the answers come back in the cases' own order, which is not the id order: %r"
            % ([pair[0] for pair in seen],))
        for index, pair in enumerate(seen):
            assert pair == (IDS[index], SEEN + texts[index]), (
                "the answer the user saw for %r is the replay's %r, never the candidate's "
                "%r" % (IDS[index], SEEN + texts[index], others.get(texts[index])))

    def _refusals(s, cases, texts, expected):
        table = _table(texts, expected, INCUMBENT_PLAN)
        model = _model(table)
        silent = _model({})
        rows = s.shadow(cases, model, silent, _replay)
        grades = s.grade(rows, cases)
        reliable = {"agree": 8, "disagree": 2, "agreement_bp": 8000}
        _refuses(s.EvalError, "cases that are a list rather than a tuple",
                 lambda: s.shadow(list(cases), model, silent, _replay), names=("list",))
        _refuses(s.EvalError, "a case that is not a mapping",
                 lambda: s.shadow(("a case",), model, silent, _replay), names=("str",))
        _refuses(s.EvalError, "a case with no expected answer",
                 lambda: s.shadow((_without(cases[0], "expected"),), model, silent, _replay),
                 names=("expected",))
        _refuses(s.EvalError, "a case carrying a field of its own",
                 lambda: s.shadow((_with(cases[0], "tenant", "northwind"),), model, silent,
                                  _replay), names=("tenant",))
        _refuses(s.EvalError, "a case whose text is not text",
                 lambda: s.shadow((_with(cases[0], "text", 7),), model, silent, _replay),
                 names=("text",))
        _refuses(s.EvalError, "rows that are a list rather than a tuple",
                 lambda: s.grade(list(rows), cases), names=("list",))
        _refuses(s.EvalError, "a shadow row with no answer the user saw",
                 lambda: s.grade((_without(rows[0], "user_sees"),), cases),
                 names=("user_sees",))
        _refuses(s.EvalError, "a shadow row for a case the sample does not hold",
                 lambda: s.grade((_with(rows[0], "id", "c-9"),), cases), names=("c-9",))
        _refuses(s.EvalError, "labelled cases that are a list rather than a tuple",
                 lambda: s.calibrate(model, list(cases)), names=("list",))
        _refuses(s.EvalError, "a labelled case with no label to agree with",
                 lambda: s.calibrate(model, (_with(cases[0], "expected", None),)),
                 names=("c-3",))
        _refuses(s.EvalError, "a labelled case carrying a field of its own",
                 lambda: s.calibrate(model, (_with(cases[0], "tenant", "northwind"),)),
                 names=("tenant",))
        _refuses(s.EvalError, "a labelled case missing the case's text",
                 lambda: s.calibrate(model, (_without(cases[0], "text"),)),
                 names=("text",))
        _refuses(s.EvalError, "grades that are a list rather than a tuple",
                 lambda: s.verdict(list(grades), reliable, SAMPLE, 7500), names=("list",))
        _refuses(s.EvalError, "a grade that is not a mapping",
                 lambda: s.verdict(("candidate",), reliable, SAMPLE, 7500), names=("str",))
        _refuses(s.EvalError, "a model this verdict does not decide about",
                 lambda: s.verdict((grades[0], _with(grades[1], "model", "other")),
                                   reliable, SAMPLE, 7500), names=("other",))
        _refuses(s.EvalError, "the same model graded twice",
                 lambda: s.verdict((grades[0], dict(grades[0])), reliable, SAMPLE, 7500),
                 names=("candidate",))
        _refuses(s.EvalError, "no grade for the incumbent",
                 lambda: s.verdict((grades[0],), reliable, SAMPLE, 7500),
                 names=("incumbent",))
        _refuses(s.EvalError, "an agreement with no basis points",
                 lambda: s.verdict(grades, {"agree": 8, "disagree": 2}, SAMPLE, 7500),
                 names=("agreement_bp",))
        _refuses(s.EvalError, "a sample that is not a count",
                 lambda: s.verdict(grades, reliable, "30", 7500), names=("sample",))
        _refuses(s.EvalError, "a target that is not a count",
                 lambda: s.verdict(grades, reliable, SAMPLE, True), names=("target_bp",))
        _refuses(s.EvalError, "rows for user_visible that are a list",
                 lambda: s.user_visible(list(rows)), names=("list",))
        _refuses(s.EvalError, "a row for user_visible that is not a mapping",
                 lambda: s.user_visible(("a row",)), names=("str",))

    def _unwritable(record, before):
        after = record.stats()
        assert after == before, (
            "the estate's own counters moved while the stage measured it: %r, and it "
            "was %r" % (after, before))
        assert after["queries"] == 0 and after["audits"] == 0, (
            "an eval asks the customer's record nothing and writes it nothing: %r"
            % (after,))
        assert record.log() == (), (
            "the stage wrote into the customer's own log: %r" % (record.log(),))

    def _twice(s, cases, texts, expected):
        def once():
            table = _table(texts, expected, INCUMBENT_PLAN)
            others = _table(texts, expected, CANDIDATE_PLAN)
            rows = s.shadow(cases, _model(table), _model(others), _replay)
            grades = s.grade(rows, cases)
            agreement = s.calibrate(_model(table), cases)
            return (rows, grades, agreement,
                    s.verdict(grades, agreement, SAMPLE, 6000), s.user_visible(rows))

        one = once()
        two = once()
        assert one == two, (
            "two runs of one fixture are one answer, and these are two: %r vs %r"
            % (one, two))

    import stage_10 as s
    import estate as world
    _constants(s, world)
    record = world.Estate.build(7)
    cases, expected, texts = _fixtures(record)
    before = record.stats()
    _shadow(s, cases, texts, expected)
    _grade(s, cases, texts, expected)
    _calibrate(s, cases, texts, expected)
    _verdict(s, cases, texts, expected)
    _visible(s, cases, texts, expected)
    _refusals(s, cases, texts, expected)
    _unwritable(record, before)
    _twice(s, cases, texts, expected)

# --- stage 11 ----------------------------------------------------------------------
def check_11():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "fde-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("FDE_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set FDE_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _statement(speaker, role, kind, text, amount_cents=0, metric=None):
        """One statement of the customer's transcript, in `STATEMENT_KEYS` order."""
        return {"speaker": speaker, "role": role, "kind": kind, "text": text,
                "amount_cents": amount_cents, "metric": metric}

    def _metric(name, baseline, target, unit):
        """One metric the customer tracks, in `METRIC_KEYS` order."""
        return {"name": name, "baseline": baseline, "target": target, "unit": unit}

    TRANSCRIPT = (
        _statement("ada", "support-lead", "objection",
                   "The last vendor left us with nothing to show.", 120000),
        _statement("grace", "support-lead", "ask",
                   "We must cut invoice turnaround time in half.", 0,
                   "time to resolution"),
        _statement("grace", "support-lead", "metric",
                   "Tickets today take us three days to close.", 0,
                   _metric("ticket age", 12, 40, "tickets")),
        _statement("alan", "engineer", "constraint",
                   "Nothing should leave the basement without the bundle."),
        _statement(None, "vp", "ask", "Maybe procurement would like this as well."),
        _statement("linus", "intern", "ask",
                   "Deleting the old invoices would help us a lot.", 0,
                   "cleanup time"),
        _statement("vp", "vp", "scope-out", "Rebuild the ERP from scratch"),
        _statement("edsger", "engineer", "ask", "Rebuild the ERP from scratch", 0,
                   "project effort"),
        _statement("hanna", "analyst", "ask", "rebuild the erp from scratch", 0,
                   "project effort"),
        _statement("omar", "analyst", "ask",
                   "We must ship the analytics dashboard immediately.", 0,
                   "dashboard use"),
    )

    SOW_LINES = (
        "SOW — northwind: 3 weeks, 3 per week",
        "requirements:",
        "  req-01 [must] grace — We must cut invoice turnaround time in half. (metric: time to resolution)",
        "  req-02 [could] grace — Tickets today take us three days to close. (metric: ticket age)",
        "  req-03 [should] alan — Nothing should leave the basement without the bundle. (metric: none)",
        "  req-04 [could] unowned — Maybe procurement would like this as well. (metric: none)",
        "  req-05 [could] linus — Deleting the old invoices would help us a lot. (metric: cleanup time)",
        "  req-06 [could] edsger — Rebuild the ERP from scratch (metric: project effort)",
        "  req-07 [could] hanna — rebuild the erp from scratch (metric: project effort)",
        "  req-08 [must] omar — We must ship the analytics dashboard immediately. (metric: dashboard use)",
        "gaps:",
        "  no-owner: req-04",
        "  no-metric: req-03",
        "  no-metric: req-04",
        "  scope-out-as-requirement: req-06",
        "metrics:",
        "  ticket age (tickets): baseline 12, target 40",
        "out of scope:",
        "  - Rebuild the ERP from scratch",
    )

    EMPTY_SOW_LINES = (
        "SOW — northwind: 1 week, 3 per week",
        "requirements:",
        "  none",
        "gaps:",
        "  none",
        "metrics:",
        "  none",
        "out of scope:",
        "  none",
    )

    def _constants(s, world):
        assert tuple(s.STATEMENT_KEYS) == ("speaker", "role", "kind", "text",
                                           "amount_cents", "metric"), (
            "a statement is read in STATEMENT_KEYS order: %r" % (s.STATEMENT_KEYS,))
        assert tuple(s.KINDS) == ("ask", "constraint", "metric", "objection",
                                  "scope-out"), (
            "the kinds, in the contract's order: %r" % (s.KINDS,))
        assert tuple(s.REQUIREMENT_KEYS) == ("id", "text", "kind", "owner",
                                             "priority", "metric"), (
            "a requirement record carries REQUIREMENT_KEYS in order: %r"
            % (s.REQUIREMENT_KEYS,))
        assert tuple(s.PRIORITIES) == ("must", "should", "could"), (
            "the priorities, strongest first: %r" % (s.PRIORITIES,))
        assert tuple(s.UNITS) == ("minutes", "cents", "percent", "tickets"), (
            "the units a baseline may be measured in: %r" % (s.UNITS,))
        assert tuple(s.METRIC_KEYS) == ("name", "baseline", "target", "unit"), (
            "a metric record carries METRIC_KEYS in order: %r" % (s.METRIC_KEYS,))
        assert tuple(s.PLAN_KEYS) == ("customer", "requirements", "problems",
                                      "workstreams", "weeks", "metrics",
                                      "out_of_scope", "metrics_without_baseline"), (
            "a plan carries PLAN_KEYS in order: %r" % (s.PLAN_KEYS,))
        assert s.WEEK_CAPACITY == 3, (
            "a week holds three requirements, and the constant says %r"
            % (s.WEEK_CAPACITY,))
        assert s.MIN_WORDS == 4, (
            "an ask of fewer than four words is vague, and the constant says %r"
            % (s.MIN_WORDS,))
        assert tuple(s.SCOPE_PROBLEMS) == ("no-owner", "no-metric", "vague",
                                           "unknown-kind", "metric-no-baseline",
                                           "out-of-capacity",
                                           "scope-out-as-requirement"), (
            "the problems a plan reports, in the order it reports them: %r"
            % (s.SCOPE_PROBLEMS,))
        assert issubclass(s.ScopeError, world.EstateError), (
            "ScopeError must be a kind of estate.EstateError, and its bases are %r"
            % (s.ScopeError.__mro__,))
        assert issubclass(s.ScopeError, ValueError), (
            "a caller's `except ValueError` must still catch it: %r"
            % (s.ScopeError.__mro__,))

    def _with_role(s, text, role):
        """The priority a requirement of `text`, said by `role`, comes back with."""
        records = s.requirements((_statement("ada", role, "ask", text, 0, "m"),))
        assert len(records) == 1, (
            "one ask is one requirement: %r" % (records,))
        return records[0]["priority"]

    def _requirements(s):
        records = s.requirements(TRANSCRIPT)
        ids = tuple(record["id"] for record in records)
        assert ids == ("req-01", "req-02", "req-03", "req-04", "req-05", "req-06",
                       "req-07", "req-08"), (
            "the ids count the requirements in statement order, so the objection "
            "that opens the transcript consumes no id: %r" % (ids,))
        for record in records:
            assert tuple(record) == tuple(s.REQUIREMENT_KEYS), (
                "a requirement carries REQUIREMENT_KEYS in order, and this one is %r"
                % (tuple(record),))
        first = records[0]
        assert (first["text"], first["kind"], first["owner"], first["priority"],
                first["metric"]) == (
            "We must cut invoice turnaround time in half.", "ask", "grace", "must",
            "time to resolution"), (
            "the first requirement is the ask as it was said, owned by the speaker "
            "who asked it and prioritised by its own words: %r" % (first,))
        assert records[1]["kind"] == "metric", (
            "a statement about a measure stays a metric requirement instead of "
            "being read as an ask: %r" % (records[1]["kind"],))
        assert records[1]["metric"] == "ticket age", (
            "a metric requirement carries the metric's own name: %r"
            % (records[1]["metric"],))
        assert records[2]["metric"] is None, (
            "a constraint no metric is attached to carries None: %r"
            % (records[2]["metric"],))
        assert records[3]["owner"] is None, (
            "a statement the transcript recorded without a speaker has no owner — "
            "certainly not the role it was said in, and not this course's author: %r"
            % (records[3]["owner"],))
        assert records[3]["metric"] is None, (
            "an ask with no metric carries None: %r" % (records[3]["metric"],))
        assert records[4]["metric"] == "cleanup time", (
            "an ask judged by a metric carries that metric's own name: %r"
            % (records[4]["metric"],))
        assert s.requirements(()) == (), (
            "an empty transcript has no requirements: %r" % (s.requirements(()),))
        assert s.requirements(TRANSCRIPT) == records, (
            "the same transcript answered twice gives two requirements")

    def _priorities(s):
        executive = _with_role(s, "Maybe procurement would like this as well.", "vp")
        assert executive == "could", (
            "an executive's maybe is a could, and the seat decided it as %r"
            % (executive,))
        intern = _with_role(s, "We must ship the dashboard before the audit.",
                            "intern")
        assert intern == "must", (
            "an intern's must is a must, and the seat decided it as %r" % (intern,))
        assert intern == _with_role(s, "We must ship the dashboard before the audit.",
                                    "vp"), (
            "the seat is not the emphasis: two speakers, one ask, two answers")
        assert _with_role(s, "We should look at this, but we must stop the leak.",
                          "ceo") == "must", (
            "a must anywhere in the sentence outranks a should that came first")
        assert _with_role(s, "We SHOULD fix the audit gap.", "ceo") == "should", (
            "the words are matched whatever case the customer typed them in")
        assert _with_role(s, "The audit trail would be nice to keep.", "ceo") == (
            "could"), (
            "a sentence with neither word is the weakest priority there is")

    def _workstreams(s):
        records = s.requirements(TRANSCRIPT)
        expected = (("alan", ("req-03",)), ("edsger", ("req-06",)),
                    ("grace", ("req-01", "req-02")), ("hanna", ("req-07",)),
                    ("linus", ("req-05",)), ("omar", ("req-08",)))
        assert s.workstreams(records) == expected, (
            "the workstreams are grouped by owner, sorted by owner, and the ids "
            "inside one are sorted: %r" % (s.workstreams(records),))
        assert s.workstreams(tuple(reversed(records))) == expected, (
            "the order a caller hands the requirements in is not an answer: %r"
            % (s.workstreams(tuple(reversed(records))),))
        scheduled = tuple(identifier for _owner, ids in s.workstreams(records)
                          for identifier in ids)
        assert "req-04" not in scheduled, (
            "a requirement with no owner is in no workstream at all: %r"
            % (scheduled,))
        hand = ({"id": "req-02", "text": "x", "kind": "ask", "owner": "grace",
                 "priority": "could", "metric": None},
                {"id": "req-01", "text": "x", "kind": "ask", "owner": "alan",
                 "priority": "could", "metric": None})
        assert s.workstreams(hand) == (("alan", ("req-01",)),
                                       ("grace", ("req-02",))), (
            "records the caller built by hand are grouped the same way: %r"
            % (s.workstreams(hand),))
        assert s.workstreams(()) == (), (
            "no requirements, no workstreams: %r" % (s.workstreams(()),))

    def _schedule(s):
        assert s.schedule((("grace", ("req-01", "req-02")), ("alan", ("req-03",))),
                          2) == (("grace", "grace", "alan"), ()), (
            "one week holds WEEK_CAPACITY requirements and the next holds the rest: "
            "%r" % (s.schedule((("grace", ("req-01", "req-02")),
                                ("alan", ("req-03",))), 2),))
        fourth = (("a", ("req-01",)), ("b", ("req-02",)), ("c", ("req-03",)),
                  ("d", ("req-04",)))
        assert s.schedule(fourth, 2) == (("a", "b", "c"), ("d",)), (
            "a fourth requirement goes into the second week rather than a fourth "
            "slot in the first: %r" % (s.schedule(fourth, 2),))
        across = (("zed", ("req-02", "req-04")), ("abel", ("req-01", "req-03")))
        assert s.schedule(across, 2) == (("abel", "zed", "abel"), ("zed",)), (
            "the fill follows the requirement ids across the owners, not one "
            "workstream at a time: %r" % (s.schedule(across, 2),))
        assert s.schedule((), 3) == ((), (), ()), (
            "the answer is always `weeks` long, and a week with nothing left to "
            "fill is an empty tuple: %r" % (s.schedule((), 3),))
        records = s.requirements(TRANSCRIPT)
        assert s.schedule(s.workstreams(records), 3) == (
            ("grace", "grace", "alan"), ("linus", "edsger", "hanna"),
            ("omar",)), (
            "the plan's own three weeks are the first three requirements' worth, in "
            "their own order: %r" % (s.schedule(s.workstreams(records), 3),))

    def _metrics(s):
        found = s.metrics(TRANSCRIPT)
        assert found == ({"name": "ticket age", "baseline": 12, "target": 40,
                          "unit": "tickets"},), (
            "metrics are the statements about a measure the customer tracks: %r"
            % (found,))
        for record in found:
            assert tuple(record) == tuple(s.METRIC_KEYS), (
                "a metric carries METRIC_KEYS in order, and this one is %r"
                % (tuple(record),))
        names = [record["name"] for record in found]
        assert "time to resolution" not in names, (
            "a metric an ask is judged by is a name on that ask, not a metric of "
            "the customer's record: %r" % (names,))
        pair = (TRANSCRIPT[2],
                _statement("ada", "vp", "metric",
                           "The close takes two weeks today.", 0,
                           _metric("close time", None, 5, "minutes")))
        assert [record["name"] for record in s.metrics(pair)] == ["ticket age",
                                                                  "close time"], (
            "metrics keep the order the customer said them in: %r"
            % ([record["name"] for record in s.metrics(pair)],))
        assert s.metrics(TRANSCRIPT[:2]) == (), (
            "an ask and an objection are not statements about a measure: %r"
            % (s.metrics(TRANSCRIPT[:2]),))
        assert s.metrics(()) == (), (
            "an empty transcript has no metrics: %r" % (s.metrics(()),))

    def _plan(s):
        plan = s.scope(TRANSCRIPT, "northwind", 3)
        assert tuple(plan) == tuple(s.PLAN_KEYS), (
            "a plan carries PLAN_KEYS in order, and this one is %r" % (tuple(plan),))
        assert plan["customer"] == "northwind", (
            "the plan's customer is the one the caller named: %r"
            % (plan["customer"],))
        assert s.scope(TRANSCRIPT, "contoso", 3)["customer"] == "contoso", (
            "the customer is the name handed in, not the world's own estate: %r"
            % (s.scope(TRANSCRIPT, "contoso", 3)["customer"],))
        assert plan["requirements"] == s.requirements(TRANSCRIPT), (
            "the plan's requirements are the requirements: %r"
            % (plan["requirements"],))
        assert plan["problems"] == (("no-owner", "req-04"),
                                    ("no-metric", "req-03"),
                                    ("no-metric", "req-04"),
                                    ("scope-out-as-requirement", "req-06")), (
            "the problems are (problem, requirement id) pairs in SCOPE_PROBLEMS "
            "order, and a plan reports the gaps of the requirements it keeps: %r"
            % (plan["problems"],))
        ids = tuple(record["id"] for record in plan["requirements"])
        for _problem, offender in plan["problems"]:
            assert offender in ids, (
                "a problem names a requirement the plan still holds, and %r is not "
                "one of %r" % (offender, ids))
        assert plan["workstreams"] == s.workstreams(plan["requirements"]), (
            "the plan's workstreams are its requirements grouped by owner: %r"
            % (plan["workstreams"],))
        assert plan["weeks"] == (("grace", "grace", "alan"),
                                 ("linus", "edsger", "hanna"), ("omar",)), (
            "the plan's weeks fill from the requirements' own order: %r"
            % (plan["weeks"],))
        assert plan["metrics"] == s.metrics(TRANSCRIPT), (
            "the plan's metrics are the metrics: %r" % (plan["metrics"],))
        assert plan["out_of_scope"] == ("Rebuild the ERP from scratch",), (
            "a scope-out statement is exiled, not turned into a requirement: %r"
            % (plan["out_of_scope"],))
        exiled = [record for record in plan["requirements"]
                  if record["text"] == "Rebuild the ERP from scratch"]
        assert [record["kind"] for record in exiled] == ["ask"], (
            "the requirement that repeats a scope-out's text is the ask that "
            "repeated it, not the scope-out statement turned into work: %r"
            % (exiled,))
        assert "scope-out" not in [record["kind"]
                                   for record in plan["requirements"]], (
            "no requirement is of the kind scope-out: %r"
            % (plan["requirements"],))
        assert plan["metrics_without_baseline"] == (), (
            "a metric with a baseline is not a metric without one: %r"
            % (plan["metrics_without_baseline"],))
        assert ("scope-out-as-requirement", "req-06") in plan["problems"], (
            "a requirement whose text is exactly a scope-out statement's earns "
            "scope-out-as-requirement: %r" % (plan["problems"],))
        assert ("scope-out-as-requirement", "req-07") not in plan["problems"], (
            "the same words in another case are another statement: %r"
            % (plan["problems"],))
        odd = (TRANSCRIPT[0],
               _statement("ada", "vp", "wish",
                          "We would like a pony for the audit."),
               TRANSCRIPT[1])
        oddplan = s.scope(odd, "northwind", 2)
        assert oddplan["problems"] == (("unknown-kind", "wish"),), (
            "a kind this course does not know is a problem returned, not an "
            "exception raised and not a requirement: %r" % (oddplan["problems"],))
        assert [record["id"] for record in oddplan["requirements"]] == ["req-01"], (
            "the statement of an unknown kind consumes no id either: %r"
            % (oddplan["requirements"],))
        twice = (_statement("ada", "vp", "wish", "We would like a pony for the "
                                               "audit."),
                 _statement("ada", "vp", "wish", "We would like a second pony for "
                                                "the audit."))
        assert s.scope(twice, "northwind", 1)["problems"] == (
            ("unknown-kind", "wish"),), (
            "one gap stated twice is one problem: %r"
            % (s.scope(twice, "northwind", 1)["problems"],))
        kinds = (_statement("ada", "vp", "wish", "We would like a pony for the "
                                               "audit."),
                 _statement("ada", "vp", "budget", "We would like a pony for the "
                                                   "audit."))
        assert s.scope(kinds, "northwind", 1)["problems"] == (
            ("unknown-kind", "budget"), ("unknown-kind", "wish")), (
            "two unknown kinds are reported in the order of their own names: %r"
            % (s.scope(kinds, "northwind", 1)["problems"],))
        vague = (_statement("ada", "vp", "ask", "Fix the audit.", 0, "m"),)
        assert s.scope(vague, "northwind", 1)["problems"] == (("vague", "req-01"),), (
            "an ask of three words is vague: %r"
            % (s.scope(vague, "northwind", 1)["problems"],))
        crisp = (_statement("ada", "vp", "ask", "Fix the audit now.", 0, "m"),)
        assert s.scope(crisp, "northwind", 1)["problems"] == (), (
            "an ask of four words is not vague, and no other gap is invented: %r"
            % (s.scope(crisp, "northwind", 1)["problems"],))
        assert s.scope(vague, "northwind", 1)["requirements"] == (
            s.requirements(vague)), (
            "a requirement with a problem is still in the plan: %r"
            % (s.scope(vague, "northwind", 1)["requirements"],))
        measured = (TRANSCRIPT[2],
                    _statement("ada", "vp", "metric",
                               "The close takes two weeks today.", 0,
                               _metric("close time", None, 5, "minutes")))
        baseline_less = s.scope(measured, "northwind", 1)
        assert baseline_less["problems"] == (("metric-no-baseline", "req-02"),), (
            "a metric nobody measured earns metric-no-baseline on the requirement "
            "the metric statement became: %r" % (baseline_less["problems"],))
        assert baseline_less["metrics_without_baseline"] == ("close time",), (
            "and the plan names the metrics without a baseline: %r"
            % (baseline_less["metrics_without_baseline"],))
        assert baseline_less["metrics"][1]["baseline"] is None, (
            "a baseline nobody measured is None rather than zero: %r"
            % (baseline_less["metrics"][1],))

    def _capacity(s):
        def musts(count):
            return tuple(_statement("ada", "vp", "ask",
                                    "We must fix the audit gap number %d." % (index,),
                                    0, "m") for index in range(count))

        def coulds(count):
            return tuple(_statement("ada", "vp", "ask",
                                    "The invoices would help us a lot, item %d."
                                    % (index,), 0, "m") for index in range(count))

        assert s.scope(musts(3), "northwind", 1)["problems"] == (), (
            "three musts fit one week of three: %r"
            % (s.scope(musts(3), "northwind", 1)["problems"],))
        assert s.scope(musts(4), "northwind", 1)["problems"] == (
            ("out-of-capacity", "4 must-haves in 3 slots"),), (
            "one must more than the weeks hold is reported with the count: %r"
            % (s.scope(musts(4), "northwind", 1)["problems"],))
        assert s.scope(musts(6), "northwind", 2)["problems"] == (), (
            "six musts fit two weeks of three: %r"
            % (s.scope(musts(6), "northwind", 2)["problems"],))
        assert s.scope(musts(7), "northwind", 2)["problems"] == (
            ("out-of-capacity", "7 must-haves in 6 slots"),), (
            "and seven are one more than a scoping of two weeks may promise: %r"
            % (s.scope(musts(7), "northwind", 2)["problems"],))
        assert s.scope(coulds(4), "northwind", 1)["problems"] == (), (
            "a backlog the weeks do not hold is not an out-of-capacity must: %r"
            % (s.scope(coulds(4), "northwind", 1)["problems"],))
        assert s.scope(coulds(4), "northwind", 1)["weeks"] == (("ada", "ada",
                                                                "ada"),), (
            "and the fourth requirement is still not squeezed into the one week: %r"
            % (s.scope(coulds(4), "northwind", 1)["weeks"],))

    def _sow(s):
        plan = s.scope(TRANSCRIPT, "northwind", 3)
        text = s.sow(plan)
        assert text == "\n".join(SOW_LINES) + "\n", (
            "the SOW is this plan rendered, one way, line for line: %r" % (text,))
        assert text == s.sow(plan), (
            "the same plan rendered twice gives two documents")
        empty = s.sow(s.scope((), "northwind", 1))
        assert empty == "\n".join(EMPTY_SOW_LINES) + "\n", (
            "an empty plan says so in every section rather than dropping it: %r"
            % (empty,))
        assert "  req-04 [could] unowned — " in text, (
            "a requirement whose owner the transcript never recorded reads "
            "unowned, rather than a name this course supplied: %r" % (text,))
        assert s.sow(s.scope((), "contoso", 1)).startswith("SOW — contoso:"), (
            "the SOW names the customer the plan was built for, not the world's own "
            "estate: %r" % (s.sow(s.scope((), "contoso", 1)),))
        measured = (TRANSCRIPT[2],
                    _statement("ada", "vp", "metric",
                               "The close takes two weeks today.", 0,
                               _metric("close time", None, 5, "minutes")))
        rendered = s.sow(s.scope(measured, "northwind", 1))
        assert "  close time (minutes): no baseline, target 5\n" in rendered, (
            "a metric nobody measured renders as no baseline rather than as a zero "
            "the customer never gave, and its target still counts: %r" % (rendered,))
        two = (TRANSCRIPT[6],
               _statement("vp", "vp", "scope-out", "Rewrite the ledger"),
               _statement("vp", "vp", "scope-out", "Migrate the data centre"))
        lined = [line for line in s.sow(s.scope(two, "northwind", 1)).split("\n")
                 if line.startswith("  - ")]
        assert lined == ["  - Rebuild the ERP from scratch", "  - Rewrite the ledger",
                         "  - Migrate the data centre"], (
            "the SOW lists the out-of-scope statements in the order they were said: "
            "%r" % (lined,))

    def _refusals(s):
        good = _statement("ada", "vp", "ask", "We must fix the audit gap.", 0, "m")
        _refuses(s.ScopeError, "a transcript that is a string rather than a sequence",
                 lambda: s.requirements("we must fix it"), names=("transcript",))
        _refuses(s.ScopeError, "one statement where a transcript belongs",
                 lambda: s.scope(good, "northwind", 1), names=("transcript",))
        _refuses(s.ScopeError, "a statement that is a string",
                 lambda: s.requirements(("we must fix it",)),
                 names=("statement 1", "mapping"))
        _refuses(s.ScopeError, "a statement with no kind at all",
                 lambda: s.requirements(({"speaker": "ada", "role": "vp",
                                          "text": "We must fix it.",
                                          "amount_cents": 0, "metric": None},)),
                 names=("kind",))
        _refuses(s.ScopeError, "a kind that is not a string",
                 lambda: s.requirements((_statement("ada", "vp", 7,
                                                    "We must fix it.", 0, "m"),)),
                 names=("kind", "7"))
        _refuses(s.ScopeError, "a text that is not a string",
                 lambda: s.requirements((_statement("ada", "vp", "ask", None, 0,
                                                    "m"),)),
                 names=("text",))
        _refuses(s.ScopeError, "a speaker that is neither a name nor None",
                 lambda: s.requirements((_statement(7, "vp", "ask",
                                                    "We must fix it.", 0, "m"),)),
                 names=("speaker", "7"))
        _refuses(s.ScopeError, "an amount of cents that is negative",
                 lambda: s.requirements((_statement("ada", "vp", "ask",
                                                    "We must fix it.", -1, "m"),)),
                 names=("amount_cents", "-1"))
        _refuses(s.ScopeError, "an ask carrying a metric mapping where a name belongs",
                 lambda: s.requirements((_statement("ada", "vp", "ask",
                                                    "We must fix it.", 0,
                                                    _metric("m", 1, 2, "minutes")),)),
                 names=("metric",))
        _refuses(s.ScopeError, "an ask whose metric name is empty",
                 lambda: s.requirements((_statement("ada", "vp", "ask",
                                                    "We must fix it.", 0, ""),)),
                 names=("metric",))
        _refuses(s.ScopeError, "a metric statement whose metric is a name",
                 lambda: s.metrics((_statement("ada", "vp", "metric",
                                               "Tickets take three days today.", 0,
                                               "ticket age"),)),
                 names=("metric",))
        _refuses(s.ScopeError, "a unit that is not one of the customer's",
                 lambda: s.metrics((_statement("ada", "vp", "metric",
                                               "Tickets take three days today.", 0,
                                               _metric("ticket age", 3, 1, "days")),)),
                 names=("unit", "days"))
        _refuses(s.ScopeError, "a baseline that is negative",
                 lambda: s.metrics((_statement("ada", "vp", "metric",
                                               "Tickets take three days today.", 0,
                                               _metric("ticket age", -3, 1,
                                                       "tickets")),)),
                 names=("baseline", "-3"))
        _refuses(s.ScopeError, "a metric with no target of its own",
                 lambda: s.metrics((_statement("ada", "vp", "metric",
                                               "Tickets take three days today.", 0,
                                               {"name": "ticket age", "baseline": 3,
                                                "unit": "tickets"}),)),
                 names=("target",))
        _refuses(s.ScopeError, "a target that is not a count of anything",
                 lambda: s.metrics((_statement("ada", "vp", "metric",
                                               "Tickets take three days today.", 0,
                                               _metric("ticket age", 3, "soon",
                                                       "tickets")),)),
                 names=("target", "soon"))
        _refuses(s.ScopeError, "a customer that is not a name",
                 lambda: s.scope((), "", 1), names=("customer",))
        _refuses(s.ScopeError, "a scoping of no weeks",
                 lambda: s.scope((), "northwind", 0), names=("weeks", "0"))
        _refuses(s.ScopeError, "weeks as a string",
                 lambda: s.scope((), "northwind", "4"), names=("weeks", "'4'"))
        _refuses(s.ScopeError, "a schedule for no weeks",
                 lambda: s.schedule((), 0), names=("weeks",))
        _refuses(s.ScopeError, "a workstream that is not a pair",
                 lambda: s.schedule(("grace",), 1), names=("workstream 1",))
        _refuses(s.ScopeError, "a workstream whose owner is empty",
                 lambda: s.schedule((("", ("req-01",)),), 1), names=("owner",))
        _refuses(s.ScopeError, "workstreams that are a string",
                 lambda: s.workstreams("grace"), names=("requirements", "grace"))
        _refuses(s.ScopeError, "a requirement that is not a mapping",
                 lambda: s.workstreams(("req-01",)), names=("requirement 1",))
        _refuses(s.ScopeError, "a requirement with no owner field",
                 lambda: s.workstreams(({"id": "req-01", "text": "x", "kind": "ask",
                                         "priority": "could", "metric": None},)),
                 names=("owner",))
        _refuses(s.ScopeError, "a plan with no customer field",
                 lambda: s.sow({}), names=("customer",))
        plan = s.scope(TRANSCRIPT, "northwind", 3)
        broken = dict(plan)
        broken["requirements"] = ({"id": "req-01", "text": "We must fix it.",
                                   "kind": "ask", "owner": "ada",
                                   "priority": "must"},)
        _refuses(s.ScopeError, "a plan's requirement with no metric field",
                 lambda: s.sow(broken), names=("metric",))
        broken = dict(plan)
        broken["problems"] = ("no-owner",)
        _refuses(s.ScopeError, "a plan whose problems are not (problem, id) pairs",
                 lambda: s.sow(broken), names=("problem 1",))

    def _world(s, world):
        estate = world.Estate.build(11)
        before = estate.stats()
        log = estate.log()
        plan = s.scope(TRANSCRIPT, "northwind", 3)
        s.sow(plan)
        assert estate.stats() == before, (
            "the plan is a function of the transcript alone, and this scoping run "
            "asked the customer's record for %r" % (estate.stats(),))
        assert estate.log() == log, (
            "and it wrote nothing there either: %r" % (estate.log(),))

    def _twice(s):
        for transcript, weeks in ((TRANSCRIPT, 3), ((), 1), (TRANSCRIPT[:1], 2),
                                  (TRANSCRIPT[:4], 1)):
            one = s.scope(transcript, "northwind", weeks)
            two = s.scope(transcript, "northwind", weeks)
            assert one == two, (
                "%d statements scoped twice give two plans, so a run is not a "
                "function of its input" % (len(transcript),))
            assert s.sow(one) == s.sow(two), (
                "the same plan rendered twice gives two documents")
            assert s.requirements(transcript) == s.requirements(transcript), (
                "the same transcript answered twice gives two requirement tuples")
            assert s.schedule(one["workstreams"], weeks) == two["weeks"], (
                "the same workstreams scheduled twice give two weeks")

    import stage_11 as s
    import estate as world
    _constants(s, world)
    _requirements(s)
    _priorities(s)
    _workstreams(s)
    _schedule(s)
    _metrics(s)
    _plan(s)
    _capacity(s)
    _sow(s)
    _refusals(s)
    _world(s, world)
    _twice(s)

# --- stage 12 ----------------------------------------------------------------------
def check_12():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "fde-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("FDE_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set FDE_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    class Machine:
        """One system: the settings it answers with, and a record of what it was asked."""

        def __init__(self, broken=()):
            """A machine that is well, or one whose named targets are stuck."""
            self.settings = {"mode": "normal", "replicas": "1"}
            self.broken = tuple(broken)
            self.applies = 0
            self.calls = []

        def apply(self, action, target, value):
            """Answer what happened, and record that the machine was asked."""
            self.applies += 1
            self.calls.append((action, target, value))
            if target in self.broken:
                return "%s is stuck" % (target,)
            if action == "restart":
                return "%s up" % (target,)
            self.settings[target] = value
            return value

        def state(self):
            """Everything this machine is, as data."""
            return {"settings": dict(self.settings), "applies": self.applies}

    class Half:
        """A system with an answer and no `state()`: not a system at all."""

        def apply(self, action, target, value):
            """Answer something; the shape is what is wrong, not the answer."""
            return "%s %s" % (action, target)

    def _step(action, target, expect):
        """One fresh step record."""
        return {"action": action, "target": target, "expect": expect}

    def _procedure(name, when, actor, steps, rollback):
        """One fresh procedure record."""
        return {"name": name, "when": when, "actor": actor,
                "steps": tuple(steps), "rollback": tuple(rollback)}

    def _fault(procedure, step, answer):
        """One fresh fault record: a procedure, a step of it, and the answer it will get."""
        return {"procedure": procedure, "step": step, "answer": answer}

    def _catalogue():
        """The five procedures every fixture works from, freshly built each time.

        `registry-full` is the FDE's, two steps long; `payments-restart` is the
        customer's, with a two-step rollback; `logs-full` is the customer's with no
        rollback at all; `queue-wedge` has no steps; `stale-token` has no condition and
        two steps nobody can verify.
        """
        return (
            _procedure("registry-full", "the internal registry is full", "fde",
                       [_step("purge", "cache", "purged"),
                        _step("restart", "registry", "registry up")],
                       [_step("set", "mode", "normal")]),
            _procedure("payments-restart", "the payments service is down", "customer",
                       [_step("restart", "payments", "payments up")],
                       [_step("set", "mode", "normal"),
                        _step("restart", "payments", "payments up")]),
            _procedure("logs-full", "the log volume is full", "customer",
                       [_step("purge", "logs", "purged")], []),
            _procedure("queue-wedge", "the queue is wedged", "customer", [], []),
            _procedure("stale-token", "", "fde",
                       [_step("set", "mode", ""), _step("set", "mode", "")],
                       [_step("set", "mode", "normal")]),
        )

    def _runbook(s):
        """A runbook holding all five procedures, in catalogue order."""
        held = s.Runbook()
        for procedure in _catalogue():
            held.add(procedure)
        return held

    def _shape(record, keys, what):
        """The record carries exactly `keys`, in that order."""
        assert isinstance(record, dict), (
            "%s is a %s, not a record" % (what, type(record).__name__))
        assert tuple(record) == keys, (
            "%s carries %r, and its keys are %r" % (what, tuple(record), keys))

    def _constants(s, world):
        assert tuple(s.PROCEDURE_KEYS) == ("name", "when", "actor", "steps", "rollback"), (
            "a procedure's five fields, in this order, are what every record prints: %r"
            % (s.PROCEDURE_KEYS,))
        assert tuple(s.STEP_KEYS) == ("action", "target", "expect"), (
            "a step's three fields, in this order: %r" % (s.STEP_KEYS,))
        assert tuple(s.ACTORS) == ("customer", "fde"), (
            "a procedure is written for the customer or for the FDE: %r" % (s.ACTORS,))
        assert tuple(s.OUTCOMES) == ("recovered", "rolled-back", "uncovered", "failed"), (
            "a procedure is recovered, rolled back, uncovered or failed: %r"
            % (s.OUTCOMES,))
        assert tuple(s.DRILL_KEYS) == ("procedure", "fault", "outcome"), (
            "a drill row's three fields, in this order: %r" % (s.DRILL_KEYS,))
        assert tuple(s.FAULT_KEYS) == ("procedure", "step", "answer"), (
            "a fault's three fields — its procedure, its step, the answer it arms: %r"
            % (s.FAULT_KEYS,))
        assert tuple(s.ADMIN_KEYS) == ("actor", "action", "target", "value", "tick",
                                      "verdict"), (
            "an admin line's six fields, in this order: %r" % (s.ADMIN_KEYS,))
        assert tuple(s.RUN_KEYS) == ("procedure", "outcome", "steps_done",
                                     "rollback_done"), (
            "a run's four fields, in this order: %r" % (s.RUN_KEYS,))
        assert tuple(s.RUNBOOK_PROBLEMS) == ("no-when", "no-steps", "no-rollback",
                                             "duplicate-name", "no-expect"), (
            "the problems in the order `problems()` prints them, `no-expect` last: %r"
            % (s.RUNBOOK_PROBLEMS,))
        assert tuple(s.GAP_REASONS) == ("uncovered", "fde-only"), (
            "the two reasons a procedure is on the leverage list: %r" % (s.GAP_REASONS,))
        assert issubclass(s.RunbookError, world.EstateError), (
            "RunbookError must be a kind of estate.EstateError, and its bases are %r"
            % (s.RunbookError.__mro__,))
        assert issubclass(s.RunbookError, ValueError), (
            "a caller's `except ValueError` must still catch it: %r"
            % (s.RunbookError.__mro__,))

    def _adding(s):
        """What `add` answers, keeps, refuses, and never hands out."""
        held = s.Runbook()
        record = held.add(_procedure(
            "payments-restart", "the payments service is down", "customer",
            [_step("restart", "payments", "payments up")],
            [_step("set", "mode", "normal")]))
        _shape(record, s.PROCEDURE_KEYS, "the record add() answers")
        assert record["steps"] == (_step("restart", "payments", "payments up"),), (
            "a procedure's steps come back as an ordered tuple of step records, not as "
            "the list that was handed in: %r" % (record["steps"],))
        assert record["rollback"] == (_step("set", "mode", "normal"),), (
            "a procedure's rollback comes back the same way: %r" % (record["rollback"],))
        record["actor"] = "fde"
        assert held.self_serve() == ("payments-restart",), (
            "add() handed back the runbook's own record, so a caller rewriting it "
            "rewrote the procedure the runbook holds: %r" % (held.self_serve(),))
        again = held.add(_procedure(
            "payments-restart", "the payments service is down", "fde",
            [_step("restart", "payments", "payments up")], []))
        _shape(again, s.PROCEDURE_KEYS, "the record a duplicate add answers")
        assert again["actor"] == "customer", (
            "a duplicate name replaced the first record instead of keeping it: %r"
            % (again["actor"],))
        assert held.problems() == (("payments-restart", "duplicate-name"),), (
            "a duplicate name is reported once, and only as a duplicate: %r"
            % (held.problems(),))
        for procedure in _catalogue():
            held.add(procedure)
        assert held.procedures() == ("logs-full", "payments-restart", "queue-wedge",
                                     "registry-full", "stale-token"), (
            "procedures() answers the names sorted, and the order they were added in is "
            "not that order: %r" % (held.procedures(),))
        before = held.procedures()
        _refuses(s.RunbookError, "a procedure that is a string",
                 lambda: held.add("payments-restart"), names=("str",))
        _refuses(s.RunbookError, "a procedure with no rollback field",
                 lambda: held.add({"name": "x", "when": "the x is down", "actor": "fde",
                                   "steps": [_step("set", "mode", "normal")]}),
                 names=("rollback",))
        _refuses(s.RunbookError, "a procedure carrying a field it has no room for",
                 lambda: held.add({"name": "x", "when": "the x is down", "actor": "fde",
                                   "steps": [_step("set", "mode", "normal")],
                                   "rollback": (), "notes": "why"}), names=("notes",))
        _refuses(s.RunbookError, "a procedure written for an actor nobody has heard of",
                 lambda: held.add(_procedure("x", "the x is down", "vendor",
                                             [_step("set", "mode", "normal")], ())),
                 names=("vendor",))
        _refuses(s.RunbookError, "a procedure whose name is empty",
                 lambda: held.add(_procedure("", "the x is down", "fde",
                                             [_step("set", "mode", "normal")], ())),
                 names=("the procedure's name",))
        _refuses(s.RunbookError, "steps handed in as one string",
                 lambda: held.add({"name": "x", "when": "the x is down", "actor": "fde",
                                   "steps": "set mode normal", "rollback": ()}),
                 names=("tuple of step records",))
        _refuses(s.RunbookError, "a step carrying a field it has no room for",
                 lambda: held.add(_procedure(
                     "x", "the x is down", "fde",
                     [{"action": "set", "target": "mode", "expect": "normal",
                       "why": "because"}], ())), names=("why",))
        _refuses(s.RunbookError, "a step with no expect at all",
                 lambda: held.add(_procedure(
                     "x", "the x is down", "fde",
                     [{"action": "set", "target": "mode"}], ())), names=("expect",))
        _refuses(s.RunbookError, "a step whose action is empty",
                 lambda: held.add(_procedure("x", "the x is down", "fde",
                                             [_step("", "mode", "normal")], ())),
                 names=("step 1",))
        _refuses(s.RunbookError, "a step whose expect is not a string",
                 lambda: held.add(_procedure("x", "the x is down", "fde",
                                             [_step("set", "mode", 3)], ())),
                 names=("3",))
        assert held.procedures() == before, (
            "a refused procedure was kept anyway: %r" % (held.procedures(),))

    def _problems(s):
        """What the runbook cannot vouch for, in the order it prints it."""
        held = _runbook(s)
        assert held.problems() == (
            ("stale-token", "no-when"),
            ("queue-wedge", "no-steps"),
            ("logs-full", "no-rollback"),
            ("queue-wedge", "no-rollback"),
            ("stale-token", "no-expect")), (
            "one row per name and problem, in RUNBOOK_PROBLEMS order and then by name, "
            "with a step nobody can verify reported as no-expect: %r"
            % (held.problems(),))
        twin = _procedure("logs-full", "the log volume is full", "fde",
                          [_step("purge", "logs", "purged")],
                          [_step("set", "mode", "normal")])
        held.add(twin)
        held.add(twin)
        assert held.problems() == (
            ("stale-token", "no-when"),
            ("queue-wedge", "no-steps"),
            ("logs-full", "no-rollback"),
            ("queue-wedge", "no-rollback"),
            ("logs-full", "duplicate-name"),
            ("stale-token", "no-expect")), (
            "a name added twice more is one duplicate, and the record the runbook "
            "already held still answers for itself: %r" % (held.problems(),))
        assert held.self_serve() == ("logs-full", "payments-restart", "queue-wedge"), (
            "self_serve() answers the procedures written for the customer, sorted: %r"
            % (held.self_serve(),))

    def _run(s):
        """Every answer `run` gives, the trace it leaves, and what it refuses."""
        held = _runbook(s)
        well = Machine()
        record = held.run("registry-full", well, 0)
        _shape(record, s.RUN_KEYS, "the record run() answers")
        assert record == {"procedure": "registry-full", "outcome": "recovered",
                          "steps_done": 2, "rollback_done": 0}, (
            "a procedure whose every step answered its own expect is recovered, with "
            "both steps done and nothing rolled back: %r" % (record,))
        assert tuple(well.calls) == (("purge", "cache", "purged"),
                                     ("restart", "registry", "registry up")), (
            "every step is applied against the system, in order, with its own expect as "
            "the value: %r" % (well.calls,))
        assert well.state()["settings"]["cache"] == "purged", (
            "the step's expect is what the system was asked for, and what it set: %r"
            % (well.state(),))
        stuck = Machine(broken=("registry",))
        record = held.run("registry-full", stuck, 4)
        assert record == {"procedure": "registry-full", "outcome": "rolled-back",
                          "steps_done": 2, "rollback_done": 1}, (
            "a step that answered something else stops the run, and the rollback runs: "
            "%r" % (record,))
        assert tuple(stuck.calls) == (("purge", "cache", "purged"),
                                      ("restart", "registry", "registry up"),
                                      ("set", "mode", "normal")), (
            "no step after the failed one runs, and the rollback runs in its own order "
            "once the run has stopped: %r" % (stuck.calls,))
        logs = Machine(broken=("logs",))
        record = held.run("logs-full", logs, 5)
        assert record == {"procedure": "logs-full", "outcome": "failed",
                          "steps_done": 1, "rollback_done": 0}, (
            "a run that failed with no rollback at all is failed, not rolled back: %r"
            % (record,))
        assert tuple(logs.calls) == (("purge", "logs", "purged"),), (
            "there was no rollback to run, and nothing else was applied: %r"
            % (logs.calls,))
        paid = Machine(broken=("payments",))
        record = held.run("payments-restart", paid, 9)
        assert record == {"procedure": "payments-restart", "outcome": "rolled-back",
                          "steps_done": 1, "rollback_done": 2}, (
            "a rollback of two steps runs both of them: %r" % (record,))
        assert tuple(paid.calls) == (("restart", "payments", "payments up"),
                                     ("set", "mode", "normal"),
                                     ("restart", "payments", "payments up")), (
            "the rollback runs in the order it was written, after the step that failed: "
            "%r" % (paid.calls,))
        assert paid.state()["settings"]["mode"] == "normal", (
            "the rollback is what put the setting back: %r" % (paid.state(),))
        stale = Machine()
        record = held.run("stale-token", stale, 6)
        assert record == {"procedure": "stale-token", "outcome": "rolled-back",
                          "steps_done": 1, "rollback_done": 1}, (
            "a step whose expect is empty cannot be verified, so it is not a pass, and "
            "the run takes the failure path: %r" % (record,))
        assert tuple(stale.calls) == (("set", "mode", ""), ("set", "mode", "normal")), (
            "the unverified step was applied like any other, and the rollback ran after "
            "it: %r" % (stale.calls,))
        assert stale.state()["settings"]["mode"] == "normal", (
            "the rollback is what put the setting back: %r" % (stale.state(),))
        idle = Machine()
        record = held.run("queue-wedge", idle, 7)
        assert record == {"procedure": "queue-wedge", "outcome": "uncovered",
                          "steps_done": 0, "rollback_done": 0}, (
            "a procedure with no steps has nothing to run, and covers nothing: %r"
            % (record,))
        assert idle.calls == [], (
            "a procedure with no steps was applied to the system anyway: %r"
            % (idle.calls,))
        calm = Machine()
        _refuses(s.RunbookError, "a run of a name the runbook does not hold",
                 lambda: held.run("registry_full", calm, 0), names=("registry_full",))
        _refuses(s.RunbookError, "a run of a name that is not even a name",
                 lambda: held.run(["registry-full"], calm, 0),
                 names=("holds no procedure",))
        _refuses(s.RunbookError, "a run against something that is not a system",
                 lambda: held.run("logs-full", "machine", 0), names=("str",))
        _refuses(s.RunbookError, "a run with a name nobody holds and a system that is "
                 "not one, which is still refused by its name",
                 lambda: held.run("registry_full", "machine", 0),
                 names=("registry_full",))
        _refuses(s.RunbookError, "a run against a system with no state()",
                 lambda: held.run("logs-full", Half(), 0), names=("Half",))
        _refuses(s.RunbookError, "a run at a tick before zero",
                 lambda: held.run("logs-full", calm, -1), names=("-1",))
        _refuses(s.RunbookError, "a run at a tick that is not a tick at all",
                 lambda: held.run("logs-full", calm, "eight"), names=("eight",))
        assert calm.calls == [] and calm.applies == 0, (
            "a refused run touched the system: %r" % (calm.state(),))
        assert held.run("logs-full", calm, 0)["outcome"] == "recovered", (
            "a tick of zero is a tick the caller may supply: %r"
            % (held.run("logs-full", calm, 0),))

    def _drill(s):
        """The drill's rows, the faults it arms, and the leverage list it feeds."""
        held = _runbook(s)
        faults = (_fault("registry-full", 1, "registry is stuck"),
                  _fault("payments-restart", 0, "payments is stuck"),
                  _fault("logs-full", 0, "logs is stuck"))
        machine = Machine()
        report = held.drill(faults, machine, 8)
        assert isinstance(report, tuple), (
            "a drill report is a tuple of rows, and this one is a %s"
            % (type(report).__name__,))
        for row in report:
            _shape(row, s.DRILL_KEYS, "a drill row")
            assert row["outcome"] in s.OUTCOMES, (
                "a drill row's outcome comes from OUTCOMES: %r" % (row,))
        triples = tuple((row["procedure"], row["fault"], row["outcome"])
                        for row in report)
        assert triples == (("logs-full", 0, "failed"),
                           ("payments-restart", 0, "rolled-back"),
                           ("queue-wedge", None, "uncovered"),
                           ("registry-full", 1, "rolled-back"),
                           ("stale-token", None, "uncovered")), (
            "one row per (procedure, fault) with the row's fault the fault's own step, "
            "one None row per procedure no fault names, sorted by (procedure, fault): "
            "%r" % (triples,))
        assert machine.applies == 7, (
            "a fault replaces the answer of the step it names and the system is still "
            "called, so six step calls and one rollback ran: %r" % (machine.applies,))
        assert ("restart", "registry", "registry up") in machine.calls, (
            "the armed step is applied with its own expect, exactly as an unarmed one "
            "would be: %r" % (machine.calls,))
        assert held.run("registry-full", Machine(), 8)["outcome"] == "recovered", (
            "a drill changed the procedures it ran, so a plain run of one of them no "
            "longer recovers: %r" % (held.run("registry-full", Machine(), 8),))
        assert s.gaps(report, held) == (("queue-wedge", "uncovered"),
                                        ("registry-full", "fde-only"),
                                        ("stale-token", "uncovered")), (
            "the leverage list is what no fault exercised first, then what is still the "
            "FDE's, sorted: %r" % (s.gaps(report, held),))
        assert s.gaps((), held) == (("logs-full", "uncovered"),
                                    ("payments-restart", "uncovered"),
                                    ("queue-wedge", "uncovered"),
                                    ("registry-full", "uncovered"),
                                    ("stale-token", "uncovered")), (
            "with no faults at all nothing was exercised, so every procedure is a gap, "
            "and an untested FDE procedure is reported as untested: %r"
            % (s.gaps((), held),))
        one = Machine()
        _refuses(s.RunbookError, "faults given as one name rather than a tuple",
                 lambda: held.drill("registry-full", one, 8), names=("str",))
        _refuses(s.RunbookError, "a fault naming a procedure the runbook does not hold",
                 lambda: held.drill((_fault("registry", 0, "stuck"),), one, 8),
                 names=("registry",))
        _refuses(s.RunbookError, "a fault naming a step the procedure does not have",
                 lambda: held.drill((_fault("registry-full", 2, "stuck"),), one, 8),
                 names=("registry-full", "step 2", "2 step(s)"))
        _refuses(s.RunbookError, "a fault whose step is a string and not an index",
                 lambda: held.drill((_fault("logs-full", "0", "logs is stuck"),),
                                    one, 8), names=("logs-full", "step '0'"))
        _refuses(s.RunbookError, "a fault whose answer is not a string",
                 lambda: held.drill((_fault("logs-full", 0, 3),), one, 8), names=("3",))
        _refuses(s.RunbookError, "a fault carrying a field it has no room for",
                 lambda: held.drill(({"procedure": "logs-full", "step": 0,
                                      "answer": "logs is stuck", "why": "because"},),
                                    one, 8), names=("why",))
        _refuses(s.RunbookError, "a drill against something that is not a system",
                 lambda: held.drill((), "machine", 8), names=("str",))
        _refuses(s.RunbookError, "a drill at a tick before zero",
                 lambda: held.drill((), one, -1), names=("-1",))
        assert one.applies == 0 and one.calls == [], (
            "a refused drill touched the system: %r" % (one.state(),))
        _refuses(s.RunbookError, "a drill report that is a string",
                 lambda: s.gaps("report", held), names=("the drill report",))
        _refuses(s.RunbookError, "a drill row with no outcome",
                 lambda: s.gaps(({"procedure": "logs-full", "fault": 0},), held),
                 names=("outcome",))
        _refuses(s.RunbookError, "a drill row whose outcome is not one of OUTCOMES",
                 lambda: s.gaps(({"procedure": "logs-full", "fault": 0,
                                  "outcome": "shipped"},), held), names=("shipped",))
        _refuses(s.RunbookError, "gaps read against something that is not a runbook",
                 lambda: s.gaps((), "runbook"), names=("str",))

    def _admin(s):
        """The admin's rights, its log, and a dry run that leaves nothing behind."""
        machine = Machine()
        rights = {"ops": ("restart", "purge"), "viewer": ()}
        admin = s.Admin(machine, rights)
        first = admin.change("restart", "payments", "payments up", "ops", 3)
        _shape(first, s.ADMIN_KEYS, "the line change() answers")
        assert first == {"actor": "ops", "action": "restart", "target": "payments",
                         "value": "payments up", "tick": 3, "verdict": "applied"}, (
            "an actor holding the action's own right applies it, and the line says so: "
            "%r" % (first,))
        assert machine.applies == 1 and tuple(machine.calls) == (
            ("restart", "payments", "payments up"),), (
            "an applied change reaches the system once, with the value it was given: %r"
            % (machine.state(),))
        second = admin.change("purge", "cache", "purged", "viewer", 4)
        assert second == {"actor": "viewer", "action": "purge", "target": "cache",
                          "value": "purged", "tick": 4, "verdict": "refused"}, (
            "an actor whose rights do not carry the action's own right is refused: %r"
            % (second,))
        third = admin.change("restart", "payments", "payments up", "nobody", 5)
        assert third == {"actor": "nobody", "action": "restart", "target": "payments",
                         "value": "payments up", "tick": 5, "verdict": "refused"}, (
            "an actor the rights never mention holds nothing, and is refused: %r"
            % (third,))
        assert machine.applies == 1, (
            "a refused change reached the system: %r" % (machine.state(),))
        _refuses(s.RunbookError, "a change whose target is a number, by an actor who "
                 "would have been refused anyway",
                 lambda: admin.change("purge", 5, "purged", "viewer", 6), names=("5",))
        assert machine.applies == 1, (
            "a refused change touched the system: %r" % (machine.state(),))
        assert admin.log() == (first, second, third), (
            "log() answers one line per attempt, in the order the attempts were made, "
            "the refused ones included: %r" % (admin.log(),))
        for line in admin.log():
            _shape(line, s.ADMIN_KEYS, "a line in the log")
        fourth = admin.change("purge", "cache", "purged", "ops", 7)
        fourth["verdict"] = "refused"
        assert admin.log()[-1]["verdict"] == "applied", (
            "change() handed back the admin's own line, so rewriting it rewrote the "
            "log: %r" % (admin.log()[-1],))
        handed_out = admin.log()
        handed_out[-1]["verdict"] = "refused"
        assert admin.log()[-1]["verdict"] == "applied", (
            "log() handed out the admin's own lines, so rewriting one rewrote the "
            "log: %r" % (admin.log()[-1],))
        _refuses(s.RunbookError, "an admin over something that is not a system",
                 lambda: s.Admin("machine", rights), names=("str",))
        _refuses(s.RunbookError, "an admin over a system with no state()",
                 lambda: s.Admin(Half(), rights), names=("Half",))
        _refuses(s.RunbookError, "rights held as a tuple rather than a mapping",
                 lambda: s.Admin(Machine(), ("ops",)), names=("tuple",))
        _refuses(s.RunbookError, "one actor's rights as a bare action name",
                 lambda: s.Admin(Machine(), {"ops": "restart"}), names=("str",))
        _refuses(s.RunbookError, "an empty action in an actor's rights",
                 lambda: s.Admin(Machine(), {"ops": ("",)}), names=("ops",))
        box = Machine()
        operator = s.Admin(box, {"ops": ("restart", "purge")})
        operator.change("restart", "payments", "payments up", "ops", 3)
        lines = operator.log()
        state = box.state()
        calls = tuple(box.calls)
        twin = Machine()
        answer = operator.dry_run("restart", "payments", "payments up")
        assert answer == twin.apply("restart", "payments", "payments up"), (
            "dry_run() answers the string the system itself would answer: %r"
            % (answer,))
        assert operator.dry_run("purge", "cache", "purged") == "purged", (
            "a dry run of a setting answers what the system answers: %r"
            % (operator.dry_run("purge", "cache", "purged"),))
        assert box.state() == state and tuple(box.calls) == calls, (
            "the rehearsal ran against the system itself, and left it changed: %r, %r"
            % (box.state(), box.calls))
        assert operator.log() == lines, (
            "a dry run is not an attempt, and wrote a line into the log: %r"
            % (operator.log(),))
        _refuses(s.RunbookError, "a dry run whose value is a number",
                 lambda: operator.dry_run("restart", "payments", 5), names=("5",))
        _refuses(s.RunbookError, "a dry run with no target at all",
                 lambda: operator.dry_run("restart", "", "payments up"),
                 names=("the target",))

    def _workload(s):
        """One whole pass over the stage: a runbook, its runs, its drill, its admin."""
        held = _runbook(s)
        machine = Machine()
        faults = (_fault("registry-full", 1, "registry is stuck"),
                  _fault("payments-restart", 0, "payments is stuck"))
        runs = tuple(held.run(name, Machine(broken=("payments",)), index)
                     for index, name in enumerate(held.procedures()))
        report = held.drill(faults, machine, 3)
        operated = Machine()
        admin = s.Admin(operated, {"ops": ("restart",), "viewer": ()})
        lines = (admin.change("restart", "payments", "payments up", "ops", 1),
                 admin.change("purge", "cache", "purged", "ops", 2),
                 admin.change("restart", "payments", "payments up", "viewer", 3))
        rehearsed = admin.dry_run("restart", "payments", "payments up")
        return (held.procedures(), held.problems(), held.self_serve(), runs, report,
                s.gaps(report, held), lines, admin.log(), rehearsed, operated.state(),
                machine.state(), tuple(machine.calls))

    def _twice(s):
        one = _workload(s)
        two = _workload(s)
        assert one == two, (
            "two passes over the same procedures answered two different things, so a "
            "run is not a function of its input: %r vs %r" % (one, two))

    import stage_12 as s
    import estate as world
    _constants(s, world)
    _adding(s)
    _problems(s)
    _run(s)
    _drill(s)
    _admin(s)
    _twice(s)

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The assertion, the session and the row",
        tags=["identity", "sessions", "tenancy"],
        action="Write `principal`, `open_session`, `session_valid`, `rights`, "
               "`row_visible`, `refuse_reason`, `visible_rows`, `Sessions` and "
               "`apply_scim` in stage_01.py.",
        predict="What a principal is actually made of once an assertion has been "
                "verified, and which of the two things a refused row's reason is "
                "about.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="A deployment that cannot reach out",
        tags=["air-gap", "manifests", "egress"],
        action="Write `DeployError`, `validate`, `plan`, `deploy`, `rollback` and "
               "`verify` in stage_02.py.",
        predict="Why a plan that would reach `public` is refused before a single "
                "step runs, and how the world's own log proves it never did.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The invoice, the reconciliation and the hybrid store",
        tags=["etl", "reconciliation", "ocr"],
        action="Write `EtlError`, `parse`, `tokens`, `reconcile`, `hybrid_load` and "
               "`report` in stage_03.py.",
        predict="Which of a dirty amount's two separators is the decimal point, and "
                "what a record reports when its amount cannot be read at all.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="Retrieval that cannot leak a row",
        tags=["retrieval", "permissions", "audit"],
        action="Write `RagError`, `search`, `filtered`, `answer` and "
               "`audit_answer` in stage_04.py.",
        predict="Where filtering has to happen so that a small `limit` cannot leak a "
                "row, and what an answer says when everything it retrieved was "
                "refused.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The legacy system as tools, and the credentials that stay behind",
        tags=["tools", "leases", "rate-limits"],
        action="Write `MCPError`, `Vault`, `describe`, `authorized`, `tick_calls` "
               "and `call` in stage_05.py.",
        predict="What a tool call is authorized against before anything else "
                "happens, and how a lease is spent without its secret ever leaving "
                "the vault.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="Mask, forward, restore, and prove nothing leaked",
        tags=["pii", "masking", "guardrails"],
        action="Write `GuardError`, `digits`, `luhn`, `detect`, `Masker`, `scan` "
               "and `forward` in stage_06.py.",
        predict="Why a card that contains an SSN-shaped run is one detection rather "
                "than three, and what `forward` computes its leaks from.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The workflow that waits for a human",
        tags=["workflows", "approvals", "journals"],
        action="Write `WorkflowError`, `Workflow`, `resume` and `effects_of` in "
               "stage_07.py.",
        predict="What a step whose actor is `human` does to everything after it, and "
                "when an approval stops being accepted at all.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The model that fits the customer's GPU",
        tags=["inference", "placement", "capacity"],
        action="Write `EdgeError`, `fits`, `place` and `Scheduler` in stage_08.py.",
        predict="What the integer headroom rule accepts at exactly 90% of a node's "
                "GPU memory, and what a submission that would wait too long does to "
                "the queue.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="What the AI did for this team, in hours and cents",
        tags=["observability", "roi", "attribution"],
        action="Write `MetricError`, `rollup`, `team_day`, `dashboard`, `anomalies` "
               "and `unattributed` in stage_09.py.",
        predict="What a dashboard is recounted from, and what the ROI of a day whose "
                "cost is zero is.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="Shadow traffic and a verdict",
        tags=["evals", "shadow", "verdicts"],
        action="Write `EvalError`, `shadow`, `grade`, `calibrate`, `verdict` and "
               "`user_visible` in stage_10.py.",
        predict="Which answer the user is allowed to see in a shadow run, and which "
                "verdict reason is decided before the target is ever consulted.",
        check=check_10,
    ),
    stage(
        11,
        file="stage_11.py",
        title="From a vague ask to a scoped four weeks",
        tags=["discovery", "scoping", "requirements"],
        action="Write `ScopeError`, `requirements`, `workstreams`, `schedule`, "
               "`metrics` and `sow` in stage_11.py.",
        predict="What a requirement keeps even when its owner or its metric is "
                "missing, and where a priority actually comes from.",
        check=check_11,
    ),
    stage(
        12,
        file="stage_12.py",
        title="A runbook that is tested, and an admin who is not you",
        tags=["runbook", "handoff", "admin"],
        action="Write `RunbookError`, `Runbook`, `Admin` and `gaps` in stage_12.py.",
        predict="What `run` reports when a step's expectation fails and the rollback "
                "list is empty, and which procedures `gaps` refuses to call "
                "leverage.",
        check=check_12,
    ),
]
