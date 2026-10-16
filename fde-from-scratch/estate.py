"""estate.py — the customer's estate: identity, tenancy, and the legacy record.

Provided, frozen, and never written by the course. This module is the customer:

* `IdP` is their identity provider — a directory of users and groups, an assertion
  it signs with its own secret (`sign`, `verify`), a SCIM-ish set of directory
  operations, and a log of everything it was asked and everything it decided;
* `Estate` is their data — the rows of a relational store that has been accumulating
  for thirty years, the scanned paperwork an OCR pass turned into text (dirty on
  purpose: split words, `0`/`O` and `1`/`l` confusions, a missing field, money
  written three ways), and the audit trail every act of the course is supposed to
  leave behind.

Nothing here is random and nothing here reads a clock: `Estate.build(seed)` and
`IdP.build(seed)` are functions of their seed, and every deadline in this course is a
tick the caller supplied. The module counts what it did and recomputes the counts
from its own log (`stats()`), because a number a module reports about itself would
otherwise agree with a claim about the module by construction.
"""

import hashlib

ESTATE_NAME = "northwind"
OTHER_TENANT = "contoso"
TICKS_PER_DAY = 8

ISSUER = "idp.northwind"
CLAIM_KEYS = ("issuer", "subject", "audience", "issued_at", "expires_at", "claims",
              "signature")
PRINCIPAL_KEYS = ("subject", "groups", "roles", "tenant", "clearance")
USER_KEYS = ("subject", "name", "groups", "tenant", "active", "scim_version")
GROUP_KEYS = ("name", "roles", "tenant")
SCIM_OP_KEYS = ("op", "subject", "field", "value")
SCIM_OPS = ("create", "update", "deactivate", "group-add", "group-remove")

CLASSIFICATIONS = ("public", "internal", "confidential", "restricted")
ROW_KEYS = ("id", "tenant", "owner", "classification", "po", "text", "amount_cents",
            "day")
DOCUMENT_KEYS = ("id", "source", "pages", "text", "scanned")
AUDIT_KEYS = ("tick", "actor", "action", "target", "verdict", "reason")

ESTATE_ERROR = "the estate refuses: %s"


class EstateError(ValueError):
    """The estate's own refusal: a shape it cannot accept, or a stranger at its door."""


def _need(mapping, keys, what):
    """Check a mapping's keys are exactly `keys`, in order, and answer it."""
    if not isinstance(mapping, dict):
        raise EstateError(ESTATE_ERROR % ("%s is a %s, not a mapping"
                                          % (what, type(mapping).__name__)))
    got = tuple(mapping)
    if got != tuple(keys):
        raise EstateError(ESTATE_ERROR % ("%s has the keys %r, not %r"
                                          % (what, got, tuple(keys))))
    return mapping


def _int(value, what):
    """Check a whole number and answer it (a `bool` is not a whole number here)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise EstateError(ESTATE_ERROR % ("%s is %r, not a whole number" % (what, value)))
    return value


def _text(value, what):
    """Check a string and answer it."""
    if not isinstance(value, str):
        raise EstateError(ESTATE_ERROR % ("%s is a %s, not a string"
                                          % (what, type(value).__name__)))
    return value


def digest(*parts):
    """The world's own hash: hex sha256 over the parts, `0x1f`-joined and encoded.

    A signature in this course is a fact rather than a metaphor because both sides
    compute this function: `sign` is `digest` with the secret in front, and `verify`
    recomputes it and compares.
    """
    joined = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def sign(secret, *parts):
    """The signature over `parts` with `secret` in front: `digest(secret, *parts)`."""
    _text(secret, "the signing secret")
    return digest(secret, *parts)


def _canonical_claims(claims):
    """A claim set as one string: keys sorted, tuple values comma-joined."""
    if not isinstance(claims, dict) or not claims:
        raise EstateError(ESTATE_ERROR % ("a claim set is a non-empty mapping, not %r"
                                          % (claims,)))
    pieces = []
    for key in sorted(claims):
        value = claims[key]
        if isinstance(value, (tuple, list)):
            value = ",".join(str(item) for item in value)
        pieces.append("%s=%s" % (key, value))
    return ";".join(pieces)


def _stream(seed):
    """A seed's deterministic integer stream — this module's only source of variety."""
    state = _int(seed, "the seed") % 2147483648
    while True:
        state = (state * 1103515245 + 12345) % 2147483648
        yield state


class IdP:
    """The customer's identity provider: a directory, a signing key and a log.

    `IdP(users, groups, secret)` takes the directory as data — `USER_KEYS` records and
    `GROUP_KEYS` records — and signs assertions with `secret`. Every assertion the
    directory mints, every verification it is asked for and every SCIM operation it
    applies is one line of `log()`, and `stats()` is recomputed from that log.
    """

    def __init__(self, users, groups, secret):
        if not isinstance(users, (tuple, list)) or not users:
            raise EstateError(ESTATE_ERROR % "an identity provider needs users")
        self._users = {}
        for user in users:
            record = _need(dict(user), USER_KEYS, "a user record")
            record["groups"] = tuple(record["groups"])
            self._users[record["subject"]] = record
        self._groups = {}
        for group in groups:
            record = _need(dict(group), GROUP_KEYS, "a group record")
            record["roles"] = tuple(record["roles"])
            self._groups[record["name"]] = record
        self._secret = _text(secret, "the signing secret")
        self._log = []

    # -- the directory ------------------------------------------------------
    def issuer(self):
        """The name this provider signs under."""
        return ISSUER

    def users(self):
        """Every subject in the directory, in insertion order."""
        return tuple(self._users)

    def groups(self):
        """Every group in the directory, in insertion order."""
        return tuple(self._groups)

    def user(self, subject):
        """The directory record for `subject`; a stranger is refused by name."""
        if subject not in self._users:
            raise EstateError(ESTATE_ERROR % ("no such subject %r" % (subject,)))
        return dict(self._users[subject])

    def group(self, name):
        """The directory record for group `name`; an unknown group is refused."""
        if name not in self._groups:
            raise EstateError(ESTATE_ERROR % ("no such group %r" % (name,)))
        return dict(self._groups[name])

    def roles_of(self, subject):
        """Every role `subject` carries through their groups, in group order."""
        record = self.user(subject)
        roles = []
        for name in record["groups"]:
            for role in self._groups[name]["roles"]:
                if role not in roles:
                    roles.append(role)
        return tuple(roles)

    def deactivate(self, subject):
        """Mark `subject` inactive and answer the record this call changed."""
        return self._scim({"op": "deactivate", "subject": subject,
                           "field": None, "value": None})

    def reactivate(self, subject):
        """Mark `subject` active again and answer the record this call changed."""
        return self._scim({"op": "update", "subject": subject, "field": "active",
                           "value": True})

    # -- assertions ---------------------------------------------------------
    def assertion(self, subject, audience, tick, lifetime):
        """Mint a signed assertion for `subject`, good for `lifetime` ticks.

        Refused, naming the offender: a stranger, a deactivated user, an empty
        audience, a lifetime that is not a positive whole number, a tick that is not
        a whole number.
        """
        record = self.user(subject)
        if not record["active"]:
            raise EstateError(ESTATE_ERROR % ("subject %r is deactivated" % (subject,)))
        _text(audience, "the audience")
        if not audience:
            raise EstateError(ESTATE_ERROR % "an assertion needs an audience")
        _int(tick, "the issuing tick")
        _int(lifetime, "the lifetime")
        if lifetime <= 0:
            raise EstateError(ESTATE_ERROR % ("the lifetime is %d, not a positive number"
                                              % (lifetime,)))
        claims = {"tenant": record["tenant"], "groups": tuple(record["groups"])}
        assertion = {
            "issuer": ISSUER,
            "subject": subject,
            "audience": audience,
            "issued_at": tick,
            "expires_at": tick + lifetime,
            "claims": claims,
            "signature": sign(self._secret, ISSUER, subject, audience, tick,
                              tick + lifetime, _canonical_claims(claims)),
        }
        self._write(tick, subject, "assertion", audience, "issued",
                    "expires at %d" % (tick + lifetime,))
        return assertion

    def verify(self, assertion, audience, tick):
        """Verify a signed assertion at `tick` and answer its claims.

        Refused, each naming the offender: a shape that is not `CLAIM_KEYS` in order;
        a signature that does not recompute (both digests named); an issuer that is
        not this provider; an audience that does not match; an assertion that is
        already expired at `tick` (`expires_at <= tick`). An `issued_at` in the
        future is legal here on purpose: what a session does with it is stage 1's.
        """
        _need(assertion, CLAIM_KEYS, "an assertion")
        _text(audience, "the audience")
        _int(tick, "the tick")
        wanted = sign(self._secret, assertion["issuer"], assertion["subject"], audience,
                      assertion["issued_at"], assertion["expires_at"],
                      _canonical_claims(assertion["claims"]))
        if wanted != assertion["signature"]:
            raise EstateError(ESTATE_ERROR % (
                "the signature is %s where %s was expected" % (assertion["signature"],
                                                               wanted)))
        if assertion["issuer"] != ISSUER:
            raise EstateError(ESTATE_ERROR % ("issuer %r is not %r"
                                              % (assertion["issuer"], ISSUER)))
        if assertion["audience"] != audience:
            raise EstateError(ESTATE_ERROR % ("audience %r is not %r"
                                              % (assertion["audience"], audience)))
        if assertion["expires_at"] <= tick:
            raise EstateError(ESTATE_ERROR % (
                "the assertion expired at %d, at tick %d"
                % (assertion["expires_at"], tick)))
        self._write(tick, assertion["subject"], "verify", audience, "verified",
                    "expires at %d" % (assertion["expires_at"],))
        return dict(assertion["claims"])

    # -- the directory operations ------------------------------------------
    def scim(self, op):
        """Apply one `SCIM_OPS` operation and answer the record it touched.

        `op` is a `SCIM_OP_KEYS` record. `create` takes a `value` that is a user
        record's fields, `update` takes a `field` of the record and its `value`,
        `deactivate` takes neither, and `group-add`/`group-remove` take
        `field="groups"` and a group's name as `value`. Every operation bumps the
        record's `scim_version`.
        """
        return self._scim(op)

    def _scim(self, op):
        _need(op, SCIM_OP_KEYS, "a SCIM operation")
        kind = op["op"]
        if kind not in SCIM_OPS:
            raise EstateError(ESTATE_ERROR % ("%r is not one of the SCIM operations %r"
                                              % (kind, SCIM_OPS)))
        subject = op["subject"]
        if kind == "create":
            if subject in self._users:
                raise EstateError(ESTATE_ERROR % ("subject %r already exists" % (subject,)))
            value = op["value"]
            if not isinstance(value, dict) or set(value) != {"name", "groups", "tenant"}:
                raise EstateError(ESTATE_ERROR % ("a new subject is a mapping of name, "
                                                  "groups and tenant, not %r" % (value,)))
            for group in value["groups"]:
                self.group(group)
            record = {"subject": subject, "name": _text(value["name"], "the name"),
                      "groups": tuple(value["groups"]),
                      "tenant": _text(value["tenant"], "the tenant"),
                      "active": True, "scim_version": 1}
            self._users[subject] = record
        else:
            record = self._users.get(subject)
            if record is None:
                raise EstateError(ESTATE_ERROR % ("no such subject %r" % (subject,)))
            if kind == "update":
                field = op["field"]
                if field not in ("name", "tenant", "active"):
                    raise EstateError(ESTATE_ERROR % ("%r is not an updatable field"
                                                      % (field,)))
                if field == "active":
                    if not isinstance(op["value"], bool):
                        raise EstateError(ESTATE_ERROR % ("active is a bool, not %r"
                                                          % (op["value"],)))
                    record["active"] = op["value"]
                elif field == "tenant":
                    record["tenant"] = _text(op["value"], "the tenant")
                else:
                    record["name"] = _text(op["value"], "the name")
            elif kind == "deactivate":
                record["active"] = False
            else:
                if op["field"] != "groups":
                    raise EstateError(ESTATE_ERROR % ("%r is not a group operation's field"
                                                      % (op["field"],)))
                group = op["value"]
                self.group(group)
                groups = list(record["groups"])
                if kind == "group-add":
                    if group in groups:
                        raise EstateError(ESTATE_ERROR % ("%r is already in %r"
                                                          % (subject, group)))
                    groups.append(group)
                    groups.sort()
                else:
                    if group not in groups:
                        raise EstateError(ESTATE_ERROR % ("%r is not in %r"
                                                          % (subject, group)))
                    groups.remove(group)
                record["groups"] = tuple(groups)
            record["scim_version"] = record["scim_version"] + 1
        self._write(0, subject, "scim", kind, "applied",
                    "version %d" % (record["scim_version"],))
        return dict(record)

    # -- the record ---------------------------------------------------------
    def _write(self, tick, actor, action, target, verdict, reason):
        self._log.append({"tick": tick, "actor": actor, "action": action,
                          "target": target, "verdict": verdict, "reason": reason})

    def log(self):
        """Every line this provider wrote, in order."""
        return tuple(self._log)

    def events(self):
        """The actions this provider performed, in order."""
        return tuple(line["action"] for line in self._log)

    def stats(self):
        """Counters recomputed from the log: what was asserted, verified and applied."""
        return {
            "assertions": len([line for line in self._log if line["action"] == "assertion"]),
            "verified": len([line for line in self._log if line["verdict"] == "verified"]),
            "scim": len([line for line in self._log if line["action"] == "scim"]),
            "denied": len([line for line in self._log if line["verdict"] == "refused"]),
            "users": len(self._users),
            "active": len([user for user in self._users.values() if user["active"]]),
        }

    @classmethod
    def build(cls, seed=7):
        """The customer's directory: five subjects at `northwind`, three at `contoso`."""
        stream = _stream(seed)
        groups = (
            {"name": "support", "roles": ("viewer",), "tenant": ESTATE_NAME},
            {"name": "finance", "roles": ("analyst",), "tenant": ESTATE_NAME},
            {"name": "engineering", "roles": ("analyst", "engineer"), "tenant": ESTATE_NAME},
            {"name": "auditors", "roles": ("admin",), "tenant": ESTATE_NAME},
            {"name": "contoso-support", "roles": ("viewer",), "tenant": OTHER_TENANT},
        )
        people = (("ada", "Ada Lovelace", ESTATE_NAME, ("engineering",)),
                  ("grace", "Grace Hopper", ESTATE_NAME, ("support",)),
                  ("alan", "Alan Turing", ESTATE_NAME, ("finance",)),
                  ("edsger", "Edsger Dijkstra", ESTATE_NAME, ("engineering", "auditors")),
                  ("barbara", "Barbara Liskov", ESTATE_NAME, ()),
                  ("linus", "Linus Torvalds", OTHER_TENANT, ("contoso-support",)),
                  ("margaret", "Margaret Hamilton", OTHER_TENANT, ("contoso-support",)),
                  ("katherine", "Katherine Johnson", OTHER_TENANT, ()))
        users = []
        for subject, name, tenant, memberships in people:
            next(stream)
            users.append({"subject": subject, "name": name, "groups": memberships,
                          "tenant": tenant, "active": True, "scim_version": 1})
        return cls(users, groups, "northwind-secret-%d" % (seed,))


class Estate:
    """The customer's record: rows, scanned documents, and the audit trail.

    `Estate(rows, documents)` takes both as data. `query` is the *unfiltered* fetch a
    careless caller uses — it returns whatever the shapes match, across tenants and
    classifications — which is exactly why every stage that touches rows takes a
    principal and why the row-visibility rule is the course's to write. `audit`
    appends one `AUDIT_KEYS` line for an act of the course, and `stats()` is
    recomputed from the log.
    """

    def __init__(self, rows, documents):
        self._rows = {}
        for row in rows:
            record = _need(dict(row), ROW_KEYS, "a row")
            if record["id"] in self._rows:
                raise EstateError(ESTATE_ERROR % ("row %r appears twice" % (record["id"],)))
            if record["classification"] not in CLASSIFICATIONS:
                raise EstateError(ESTATE_ERROR % ("row %r is %r, not one of %r"
                                                  % (record["id"], record["classification"],
                                                     CLASSIFICATIONS)))
            self._rows[record["id"]] = record
        self._documents = {}
        for document in documents:
            record = _need(dict(document), DOCUMENT_KEYS, "a document")
            self._documents[record["id"]] = record
        self._log = []

    def rows(self):
        """Every row, in id order."""
        return tuple(self._rows[key] for key in sorted(self._rows))

    def row(self, row_id):
        """One row by id; an unknown id is refused by name."""
        if row_id not in self._rows:
            raise EstateError(ESTATE_ERROR % ("no such row %r" % (row_id,)))
        return dict(self._rows[row_id])

    def documents(self):
        """Every document, in id order."""
        return tuple(self._documents[key] for key in sorted(self._documents))

    def document(self, document_id):
        """One document by id; an unknown id is refused by name."""
        if document_id not in self._documents:
            raise EstateError(ESTATE_ERROR % ("no such document %r" % (document_id,)))
        return dict(self._documents[document_id])

    def query(self, kind, **kwargs):
        """The unfiltered fetch: rows matching `kind`, in id order.

        `"tenant"` and `"classification"` take `value`, `"day"` takes `value`, and
        `"amount_at_least"` takes `value` in cents. Nothing is filtered for the
        caller: this is the store as it is.
        """
        if kind not in ("tenant", "classification", "day", "amount_at_least"):
            raise EstateError(ESTATE_ERROR % ("%r is not a query kind" % (kind,)))
        if set(kwargs) != {"value"}:
            raise EstateError(ESTATE_ERROR % ("a %s query takes a value, not %r"
                                              % (kind, sorted(kwargs))))
        value = kwargs["value"]
        if kind == "amount_at_least":
            _int(value, "the amount in cents")
            found = [row for row in self.rows() if row["amount_cents"] >= value]
        else:
            _text(value, "the value")
            found = [row for row in self.rows() if row[kind] == value]
        self._log.append({"tick": 0, "actor": "estate", "action": "query",
                          "target": kind, "verdict": "answered",
                          "reason": "%d rows" % (len(found),)})
        return tuple(found)

    def audit(self, actor, action, target, verdict, reason, tick):
        """Write one audit line for an act of the course and answer it."""
        for name, value in (("actor", actor), ("action", action), ("target", target),
                            ("verdict", verdict), ("reason", reason)):
            _text(value, "the audit line's %s" % (name,))
        line = {"tick": _int(tick, "the audit tick"), "actor": actor, "action": action,
                "target": target, "verdict": verdict, "reason": reason}
        self._log.append(line)
        return dict(line)

    def log(self):
        """Every line this estate wrote, in order."""
        return tuple(self._log)

    def stats(self):
        """Counters recomputed from the log."""
        queries = [line for line in self._log if line["action"] == "query"]
        return {
            "rows": len(self._rows),
            "documents": len(self._documents),
            "queries": len(queries),
            "rows_returned": sum(int(line["reason"].split()[0]) for line in queries),
            "audits": len([line for line in self._log if line["action"] != "query"]),
        }

    @classmethod
    def build(cls, seed=7):
        """The customer's record: rows across two tenants and six scanned invoices."""
        return cls(_build_rows(seed), _build_documents())


def _build_rows(seed):
    """Twenty-four rows: two tenants, four classifications, and the POs stage 3 needs."""
    stream = _stream(seed + 11)
    owners = ("ada", "grace", "alan", "edsger", "linus", "margaret")
    vendors = ("Baltic Steel", "Iberia Logistics", "Northwind Parts", "Oslo Fasteners",
               "Danube Tooling", "Contoso Supply")
    rows = []
    for index in range(24):
        draw = next(stream)
        tenant = ESTATE_NAME if index % 4 else OTHER_TENANT
        classification = CLASSIFICATIONS[draw % 4]
        amount = 90000 + (draw % 40000) * 3
        rows.append({
            "id": "row-%02d" % (index + 1,),
            "tenant": tenant,
            "owner": owners[draw % 6],
            "classification": classification,
            "po": "PO-%d" % (1001 + index,),
            "text": "%s invoice for %s" % (vendors[draw % 6], "PO-%d" % (1001 + index,)),
            "amount_cents": amount,
            "day": draw % 28 + 1,
        })
    # Six of the rows are the invoices stage 3 has to reconcile, byte for byte.
    for position, (po, vendor, cents, day) in enumerate(_INVOICE_TRUTH):
        row = rows[position]
        row["po"] = po
        row["text"] = "%s invoice for %s" % (vendor, po)
        row["amount_cents"] = cents
        row["day"] = day
        row["tenant"] = ESTATE_NAME
        row["classification"] = CLASSIFICATIONS[position % 2]
    # One row is deliberately duplicated by PO, for the reconciliation's hardest case.
    rows.append({"id": "row-25", "tenant": ESTATE_NAME, "owner": "alan",
                 "classification": "internal", "po": "PO-1003",
                 "text": "Northwind Parts invoice for PO-1003",
                 "amount_cents": _INVOICE_TRUTH[2][2], "day": _INVOICE_TRUTH[2][3]})
    return tuple(rows)


_INVOICE_TRUTH = (
    ("PO-1001", "Baltic Steel", 123456, 12),
    ("PO-1002", "Iberia Logistics", 98765, 13),
    ("PO-1003", "Northwind Parts", 123456, 14),
    ("PO-1004", "Oslo Fasteners", 45000, 15),
    ("PO-1005", "Danube Tooling", 765432, 16),
    ("PO-1006", "Baltic Steel", 23456, 17),
)


def _build_documents():
    """Six scanned invoices, each dirty in its own way — the OCR the customer has."""
    return (
        {"id": "doc-1", "source": "scanner-a", "pages": 2,
         "text": "INVOICE\nPO-1001\nVendor: Bal tic  Steel\nAmount: 1.234,56 EUR\n"
                 "Date: 12/03\nTerms: 30 days\n", "scanned": True},
        {"id": "doc-2", "source": "scanner-a", "pages": 1,
         "text": "INVOICE N0. 2\nPO-l002\nVendor: Iberia Logistics\n"
                 "Amount: 987.65 USD\nDate: l3/03\n", "scanned": True},
        {"id": "doc-3", "source": "scanner-b", "pages": 3,
         "text": "INVOICE\nPO-1003\nVendor: Northwind Parts\nAmount: 1234,56 EUR\n"
                 "Date: 14/03\n", "scanned": True},
        {"id": "doc-4", "source": "scanner-b", "pages": 1,
         "text": "INVOICE\nPO-1004\nVendor: Oslo Fasteners\nAmount:\nDate: 15/03\n",
         "scanned": True},
        {"id": "doc-5", "source": "scanner-c", "pages": 2,
         "text": "INVOICE\nPO-1005\nVendor: Danube Tooling\nAmount: 7.654,32 EUR\n"
                 "Date: 16/03\n", "scanned": True},
        {"id": "doc-6", "source": "scanner-c", "pages": 1,
         "text": "INVOICE\nPO-1006\nVendor: Baltic Steel Ltd\nAmount: 234.56 EUR\n"
                 "Date: 17/03\n", "scanned": True},
        {"id": "doc-7", "source": "scanner-d", "pages": 1,
         "text": "INVOICE\nPO-0977\nVendor: Aalborg Cement\nAmount: 1.234 EUR\n"
                 "Date: 05/04\n", "scanned": True},
        {"id": "doc-8", "source": "scanner-d", "pages": 4,
         "text": "INVOICE\nPO-1007\nVendor: Trondheim Verksted\nAmount: 45.000,50 SEK\n"
                 "Date: 18/03\n", "scanned": True},
    )
