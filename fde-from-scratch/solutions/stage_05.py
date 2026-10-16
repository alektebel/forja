"""FDE From Scratch — stage 5: The legacy system as tools, and the credentials that stay behind.

Stage 4 answered questions out of a store that had already been filtered. This one
goes the other way: the agent has to act on the customer's system of record — the
order table, the scanned invoices — through a small closed catalogue of tool calls.
The thing that makes the design work is where the credential is *not*. A tool is a
name, a verb, a table, a closed set of argument names and a number of calls per tick.
The credential that lets a call reach the table stays inside a vault, which hands out
a *lease* — a name, a deadline and a flag — and never the secret. Nothing but the
vault's own accessor ever reads the secret, so there is no line to redact: the secret
is not on any path a call can take, and the check proves it by looking for the
literal in every line the estate and the vault kept.

The order of a call is the rest of the stage. Authorization comes first and it is the
principal's *rights* against the tool's own verb — never the verb alone, and never the
caller's name: an admin may call every tool, a viewer may call a read tool, and a
viewer reaching for a write tool is refused `read-only`, which is a different fact
from `no-right`. Then the lease is spent: the vault is asked for the name, the lease
comes back without the secret, and it is redeemed before the call reaches anything.
Then the rate limit is counted before the work, and the count is given back when the
call is refused — the counter measures calls that reached the table, and a refusal is
exactly the call that did not. Every call, allowed or refused, writes one audit line
through the estate: the refusal is the line the customer's auditor reads, so a refusal
that left no line would be the bug rather than the efficiency.

    TOOL_KEYS           one tool: name, verb, table, its argument names, its per-tick limit
    VERBS               the two verbs a tool may carry, in order
    TOOLS               the catalogue over this estate's own tables
    LEASE_KEYS          one lease: name, expires_at, redeemed — and never the secret
    REASONS             the closed vocabulary a refused call answers with
    MCPError            this stage's refusal, a kind of estate.EstateError
    Vault(leases)       the vault, built over a mapping of names to secrets
    Vault.lease(name, ttl, tick) -> LEASE_KEYS, minted and not yet redeemed
    Vault.redeem(lease, tick) -> LEASE_KEYS, marked redeemed once and only once
    Vault.secret_of(name) -> the secret: the vault's own accessor and the only read
    Vault.log()         what the vault was asked, as (action, name, tick, verdict) lines
    describe(tools)     -> the catalogue as TOOL_KEYS records, validated
    authorized(principal, tool) -> bool: the principal's rights against the tool's verb
    tick_calls(calls)   -> how many calls the per-tick structure holds
    call(estate, principal, tools, vault, calls, name, args, tick)
                        -> (result, reason): the rows for a read, the affected count for
                           a write, and None for every refusal

DESIGN DECISION — why does a lease carry a name and a deadline instead of the secret?

Because a secret that travels is a secret that leaks. The caller passes a *name*
around — the tool's own name — and the vault answers a lease that says which name it
covers, when it stops being usable and whether it has been spent. The secret is read
in exactly one place, the vault's own `secret_of`, and this stage never calls it: the
whole point is that no argument, no answer and no log line of a tool call could carry
the secret even by accident, so there is nothing to redact after the fact.

DESIGN DECISION — why is a call's order authorization, then lease, then counter, then
work?

Because each step asks a different question and the order decides what a refusal
means. Authorization asks whether this caller may touch this tool at all, so it comes
first: a caller with no right never gets near the credential. The lease asks whether
the vault will let this name be used *now*, so it comes next: it is the point of trust
between the course and the customer's secret store. The counter then measures the work
at the table, and that is why it is the step that is given back when the call is
refused: a call the arguments knock back never reached the table, and a budget spent on
a call that did not happen would refuse the next call that could. The lease is not
given back — a lease is minted per call, spent once, and the vault's own log records
it.

DESIGN DECISION — why is `bad-arguments` a returned reason while a broken shape raises?

Because one is a decision about this call and the other is not a call at all. The
arguments arrive as a mapping or they are not arguments: a tool name that is not a
name, an arguments value that is not a mapping, a catalogue record that is not a
`TOOL_KEYS` record — none of those can be judged as a tool call, so they raise
`MCPError` naming the offender. But an argument the tool does not declare, a declared
argument the call leaves out, a value of a type the argument cannot take: those are
things a caller really does, and the closed vocabulary has a word for them — so they
come back as `bad-arguments`, named on the audit line. The same split covers a tool
name that is not in the catalogue (`unknown-tool` is a verdict about the customer's
system) and a tool record that is not a record at all (which raises).

DESIGN DECISION — why is the per-tick budget keyed by the tool rather than by the
caller?

Because the limit belongs to the legacy endpoint and not to the session. A rate limit
is what the customer's system of record can take on one table in one tick, so two
tools must not share one budget — an agent that spent its whole allowance on reads
must still be able to write — and two callers must not share one either: the second
caller's first call is not the first call the table sees. So the structure the caller
owns maps a tool name to the tick it was last counted in and the calls made there, the
pair is replaced the moment the tick moves on, and `tick_calls` answers how many calls
the structure holds.

DESIGN DECISION — why does the audit line name the tool and the offending argument
instead of the values the call carried?

Because the audit is written for the customer's auditor and the values are the
customer's data. Every call is one line — allowed or refused — and what the line needs
to say is which tool was called, on whose behalf, whether it was allowed, and, when it
was refused, *which* argument or which tool refused it. The values are not evidence:
they are the payload. Names instead of values is also why a secret cannot appear on
the line: the line has no place to put it.

DESIGN DECISION — why is a lease's deadline decided before whether it was redeemed?

Because the tick decides whether the credential exists at all. A lease is a credential
with a deadline, so a lease past `expires_at` is not a credential that was spent — it
is nothing, whatever else is true of it, and the tick at `expires_at` itself is
already past it (`tick < expires_at` is the whole test). A lease that is both expired
and spent therefore answers `lease-expired`, the redemption is never attempted, and
the vault refuses to redeem a lease past its deadline for exactly the same reason.
"""

import estate
import stage_01

TOOL_KEYS = ("name", "verb", "table", "arguments", "limits")

VERBS = ("read", "write")

TOOLS = (
    {"name": "orders.read", "verb": "read", "table": "orders",
     "arguments": ("po",), "limits": 4},
    {"name": "orders.write", "verb": "write", "table": "orders",
     "arguments": ("po", "amount_cents"), "limits": 2},
    {"name": "invoices.read", "verb": "read", "table": "invoices",
     "arguments": ("source",), "limits": 3},
)

LEASE_KEYS = ("name", "expires_at", "redeemed")

REASONS = ("no-right", "no-lease", "lease-expired", "lease-redeemed", "rate-limited",
           "bad-arguments", "unknown-tool", "read-only")

_VERB_RIGHTS = {"read": "rows:read", "write": "rows:write"}

_LEASE_TTL = 4

_TABLES = ("orders", "invoices")

_ARGUMENTS = ("po", "source", "amount_cents")

_AMOUNT_ARGUMENTS = ("amount_cents",)


class MCPError(estate.EstateError):
    """A shape this stage cannot accept, or a call it will not make."""


def _mapping(value, what):
    """`value` as a mapping, or the mistake naming what arrived."""
    if not isinstance(value, dict):
        raise MCPError("the %s is a %s, not a mapping" % (what, type(value).__name__))
    return value


def _principal(principal):
    """A principal this stage can read, or the mistake naming what arrived."""
    if not isinstance(principal, dict):
        raise MCPError("the principal is a %s, not a mapping: %r"
                       % (type(principal).__name__, principal))
    return principal


def _name(value, what):
    """`value` as a non-empty name, or the mistake naming what arrived."""
    if not isinstance(value, str) or not value:
        raise MCPError("%s is %r, not a name" % (what, value))
    return value


def _whole(value, what):
    """`value` as a whole number; a `bool` is not one here, exactly as in the world."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise MCPError("%s is %r, not a whole number" % (what, value))
    return value


def _positive(value, what):
    """`value` as a whole number above zero, or the mistake naming both sides."""
    value = _whole(value, what)
    if value <= 0:
        raise MCPError("%s is a positive number, and %d is not" % (what, value))
    return value


def _names(value, what):
    """`value` as a tuple of names: a bare string is one name, and one name is not a tuple."""
    if isinstance(value, str):
        raise MCPError("%s is a tuple of names, not the string %r" % (what, value))
    if not isinstance(value, (tuple, list)):
        raise MCPError("%s is a tuple of names, not %r" % (what, value))
    for name in value:
        _name(name, "an argument name")
    return tuple(value)


def _tool(tool):
    """One `TOOL_KEYS` record, or the mistake naming what arrived."""
    if not isinstance(tool, dict):
        raise MCPError("a tool is a %s, and a tool is a mapping: %r"
                       % (type(tool).__name__, tool))
    keys = tuple(tool)
    if keys != TOOL_KEYS:
        raise MCPError("a tool carries %r, not %r" % (keys, TOOL_KEYS))
    name = _name(tool["name"], "the tool's name")
    if tool["verb"] not in VERBS:
        raise MCPError("the tool %r carries the verb %r, and a verb is one of %r"
                       % (name, tool["verb"], VERBS))
    if tool["table"] not in _TABLES:
        raise MCPError("the tool %r is over the table %r, and this estate's tables are "
                       "%r" % (name, tool["table"], _TABLES))
    arguments = _names(tool["arguments"], "the arguments of the tool %r" % (name,))
    for argument in arguments:
        if argument not in _ARGUMENTS:
            raise MCPError("the tool %r declares the argument %r, and this estate's "
                           "arguments are %r" % (name, argument, _ARGUMENTS))
    limits = _positive(tool["limits"], "the per-tick limit of the tool %r" % (name,))
    return {"name": name, "verb": tool["verb"], "table": tool["table"],
            "arguments": arguments, "limits": limits}


def _lease_record(lease):
    """One `LEASE_KEYS` record, or the mistake naming what arrived."""
    if not isinstance(lease, dict):
        raise MCPError("a lease is a %s, and a lease is a mapping: %r"
                       % (type(lease).__name__, lease))
    keys = tuple(lease)
    if keys != LEASE_KEYS:
        raise MCPError("a lease carries %r, not %r" % (keys, LEASE_KEYS))
    name = _name(lease["name"], "the lease's name")
    expires_at = _whole(lease["expires_at"], "the lease's expiry")
    if not isinstance(lease["redeemed"], bool):
        raise MCPError("the lease %r carries redeemed %r, and redeemed is a bool"
                       % (name, lease["redeemed"]))
    return {"name": name, "expires_at": expires_at, "redeemed": lease["redeemed"]}


def _subject_of(principal):
    """The subject a call is made for, from a principal this stage can read."""
    return _name(_principal(principal).get("subject"), "the principal's subject")


def _store(estate, *asks):
    """The customer's record, or the mistake: it must answer what this stage asks."""
    for name in asks:
        if not callable(getattr(estate, name, None)):
            raise MCPError("the estate is a %s, and this stage asks an estate for %s()"
                           % (type(estate).__name__, name))
    return estate


def _keyring(vault, *asks):
    """The vault, or the mistake: it must answer what this stage asks a vault for."""
    for name in asks:
        if not callable(getattr(vault, name, None)):
            raise MCPError("the vault is a %s, and this stage asks a vault for %s()"
                           % (type(vault).__name__, name))
    return vault


class Vault:
    """The customer's credentials: names, secrets behind them, and leases over them.

    The vault is built over a mapping of names to secrets and holds both copies
    privately. `secret_of` is the only way a secret is ever read, and this stage
    calls it nowhere: a caller is handed a lease — the name, the deadline, the flag —
    and the secret stays where it was. Every line the vault keeps is what it was
    asked and what it answered, which is why the check can assert that the literal
    secret appears in none of them.
    """

    def __init__(self, leases):
        """A vault holding the names and secrets of `leases`, and no log yet."""
        leases = _mapping(leases, "vault's leases")
        self._leases = {}
        for name in leases:
            self._leases[_name(name, "a lease name")] = _name(
                leases[name], "the secret held under %r" % (name,))
        self._spent = {}
        self._log = []

    def _kept(self, action, name, tick, verdict):
        """One line of what the vault was asked and what it answered.

        A line is `(action, name, tick, verdict)` and has no field a secret could be
        written into: the vault records that a name was leased or redeemed, never
        what was behind it.
        """
        self._log.append((action, name, tick, verdict))
        return verdict

    def secret_of(self, name):
        """The secret held under `name`: the vault's own accessor, and the only read.

        A name the vault does not hold is refused by name, and what is answered is
        the secret itself — never a lease, never a hash of it and never a part of it.
        Only code that has already decided it needs the secret calls this; a tool call
        needs a lease, so the secret never reaches the audit line or the arguments.
        """
        name = _name(name, "the lease name")
        if name not in self._leases:
            raise MCPError("the vault holds no secret under the name %r, and holds %r"
                           % (name, tuple(sorted(self._leases))))
        return self._leases[name]

    def lease(self, name, ttl, tick):
        """Mint a lease over `name`: `LEASE_KEYS`, unredeemed, expiring after `ttl`.

        The lease's `expires_at` is `tick + ttl`, so a lease is usable in the tick it
        was minted in and stops being usable at its deadline. A name the vault does
        not hold has no lease to mint and is refused by name; a lifetime that is not a
        positive number of ticks cannot be a deadline and is refused by both sides.
        A fresh lease is minted per call: one lease is spent once.
        """
        name = _name(name, "the lease name")
        ttl = _positive(ttl, "the lease's lifetime")
        tick = _whole(tick, "the tick")
        if name not in self._leases:
            self._kept("lease", name, tick, "unknown")
            raise MCPError("the vault holds no lease for the name %r, and holds %r"
                           % (name, tuple(sorted(self._leases))))
        self._kept("lease", name, tick, "leased")
        self._spent[name] = False
        return {"name": name, "expires_at": tick + ttl, "redeemed": False}

    def redeem(self, lease, tick):
        """Spend `lease` at `tick`: the same lease, marked redeemed.

        A lease past its deadline and a lease that has already been spent are both
        refused by name — `tick >= expires_at` is expired, and the vault refuses an
        expired lease before it looks at the flag, because a credential past its
        deadline is not a credential. The vault also keeps its own record of the
        name's lease: one that has been redeemed is not redeemed a second time, and
        only a fresh mint clears that record. A lease that is not a `LEASE_KEYS`
        record is refused naming what arrived.
        """
        lease = _lease_record(lease)
        tick = _whole(tick, "the tick")
        name = lease["name"]
        if tick >= lease["expires_at"]:
            self._kept("redeem", name, tick, "expired")
            raise MCPError("the lease for %r expired at %d and the tick is %d, so it is "
                           "not redeemed" % (name, lease["expires_at"], tick))
        if lease["redeemed"] or self._spent.get(name, False):
            self._kept("redeem", name, tick, "spent")
            raise MCPError("the lease for %r was redeemed already, so it is not "
                           "redeemed again" % (name,))
        self._spent[name] = True
        self._kept("redeem", name, tick, "redeemed")
        return {"name": name, "expires_at": lease["expires_at"], "redeemed": True}

    def log(self):
        """Every line the vault kept, as `(action, name, tick, verdict)` tuples.

        `action` is `"lease"` or `"redeem"`, `verdict` is what came of it (`"leased"`,
        `"redeemed"`, `"expired"`, `"spent"`, `"unknown"`), and no line carries a
        secret — there is no field for one.
        """
        return tuple(self._log)


def describe(tools):
    """The catalogue as `TOOL_KEYS` records, validated, in catalogue order.

    A tool is a record with exactly the keys of `TOOL_KEYS` in that order, a name, a
    verb out of `VERBS`, a table this estate has, argument names this estate's tables
    have, and a positive per-tick limit. Anything else is not a tool this stage can
    describe and is refused naming what arrived.
    """
    if isinstance(tools, str) or not isinstance(tools, (tuple, list)):
        raise MCPError("the catalogue is a tuple of tools, not %r" % (tools,))
    return tuple(_tool(tool) for tool in tools)


def authorized(principal, tool):
    """Whether this principal's rights allow this tool: the verb's own right, or nothing.

    A read tool takes `rows:read` and a write tool takes `rows:write`, read from the
    principal's roles through stage 1 rather than from the tool's verb alone — a verb
    is not a permission. The answer is a `bool`; the *reason* a call was refused is
    `call`'s to answer, because `read-only` and `no-right` are two different facts.
    """
    tool = _tool(tool)
    return _VERB_RIGHTS[tool["verb"]] in stage_01.rights(_principal(principal))


def _pair(entry, name):
    """One `(tick, count)` pair of the per-tick structure, or the mistake naming it."""
    if isinstance(entry, str) or not isinstance(entry, tuple) or len(entry) != 2:
        raise MCPError("the call counter's entry for %r is %r, and an entry is a "
                       "(tick, count) pair" % (name, entry))
    _whole(entry[0], "the tick of the entry for %r" % (name,))
    _whole(entry[1], "the count of the entry for %r" % (name,))
    return entry


def _count(calls, name, tick):
    """One more call to `name` in `tick`'s budget, and the structure pruned to `tick`.

    The structure is per tick: an entry carrying another tick is a budget that has
    already expired and is dropped here, so the tick the call happens in is the only
    tick the structure ever holds. The answer is the count *including* this call.
    """
    for key in list(calls):
        if _pair(calls[key], _name(key, "the call counter's key"))[0] != tick:
            del calls[key]
    held = calls.get(name)
    count = (_pair(held, name)[1] if held is not None else 0) + 1
    calls[name] = (tick, count)
    return count


def _uncount(calls, name, tick):
    """The refused call's count given back: the structure holds the calls that happened."""
    held = calls.get(name)
    count = (_pair(held, name)[1] if held is not None else 1) - 1
    calls[name] = (tick, count)
    return count


def tick_calls(calls):
    """How many calls the per-tick structure holds.

    The structure maps a tool name to the tick it was last counted in and the calls
    made there, so this is the sum of the counts it holds. A structure whose entries
    are not pairs of whole numbers is refused naming the entry.
    """
    calls = _mapping(calls, "the call counter")
    total = 0
    for key in calls:
        _pair(calls[key], _name(key, "the call counter's key"))
        total += calls[key][1]
    return total


def _takes(argument, value):
    """`value` as what `argument` takes, or `None`: an amount is a positive count."""
    if argument in _AMOUNT_ARGUMENTS:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return None
        return value
    if not isinstance(value, str) or not value:
        return None
    return value


def _offender(tool, args):
    """The first argument this call cannot make, or `None` when the call fits the tool.

    Three questions are really the same question — which argument refused this call —
    so the first answer decides: an argument name the tool does not declare, a declared
    argument the call leaves out, and a value the argument cannot take.
    """
    for key in args:
        if key not in tool["arguments"]:
            return key
    for argument in tool["arguments"]:
        if argument not in args:
            return argument
    for argument in tool["arguments"]:
        if _takes(argument, args[argument]) is None:
            return argument
    return None


def _work(store, tool, args):
    """The work one allowed call does at the table: the records, or the affected count.

    A read answers the records the tool's own argument selects out of the table it is
    over; a write answers how many records it affects. Nothing is written: the estate
    is the customer's and this course only reads it, which is what the check proves by
    diffing the world before and after the whole workload.
    """
    if tool["table"] == "orders":
        found = tuple(row for row in store.rows() if row["po"] == args["po"])
    else:
        found = tuple(document for document in store.documents()
                      if document["source"] == args["source"])
    if tool["verb"] == "write":
        return len(found)
    return found


def _done(tool, result):
    """What the audit line says an allowed call did, with none of the values it carried."""
    if tool["verb"] == "write":
        return "rows affected: %d" % (result,)
    return "rows: %d" % (len(result),)


def _audit(store, actor, action, target, verdict, reason, tick):
    """One audit line for one call, written through the estate's own audit.

    The line names the tool and, when a refusal is about an argument, the argument:
    `target` is the table an allowed call touched and the offender when there is one.
    """
    return store.audit(actor, action, target, verdict, reason, tick)


def _spend(vault, tool, tick):
    """Redeem a lease over the tool's name, or the reason it cannot be spent.

    The vault is asked for a lease over the tool's own name; a vault that will not
    mint one holds no credential for this tool, and the answer is `no-lease`. The
    lease that comes back is data like anything else: one handed over for another name
    is not this call's credential and raises, one already past `expires_at` is
    `lease-expired`, one already redeemed is `lease-redeemed`, and only a live
    unredeemed lease over the right name is redeemed at this tick — before the count,
    so a refused call has already spent the credential it was authorized to spend.
    """
    try:
        lease = vault.lease(tool["name"], _LEASE_TTL, tick)
    except MCPError:
        return "no-lease"
    lease = _lease_record(lease)
    if lease["name"] != tool["name"]:
        raise MCPError("the vault handed over the lease for %r, and this call is for %r"
                       % (lease["name"], tool["name"]))
    if tick >= lease["expires_at"]:
        return "lease-expired"
    if lease["redeemed"]:
        return "lease-redeemed"
    vault.redeem(lease, tick)
    return None


def call(estate, principal, tools, vault, calls, name, args, tick):
    """One tool call: authorize, spend a lease, count, work, audit — in that order.

    The answer is `(result, reason)`: for an allowed call the rows a read fetched or
    the number of rows a write affects, with `reason` `None`; for a refused call
    `None` and one of `REASONS`. Authorization is against the tool's own verb, the
    lease is minted and redeemed from the vault (the secret is never touched), the
    per-tick budget for *this* tool is counted before the work and given back when the
    call is refused, and every call — allowed or refused — writes exactly one
    `AUDIT_KEYS` line through the estate, naming the tool or the offending argument
    and never a value. Nothing is ever written to the estate's rows.
    """
    subject = _subject_of(principal)
    name = _name(name, "the tool name")
    tick = _whole(tick, "the tick")
    args = _mapping(args, "call's arguments")
    calls = _mapping(calls, "call counter")
    store = _store(estate, "rows", "documents", "audit")
    keyring = _keyring(vault, "lease", "redeem")

    tool = None
    for record in describe(tools):
        if record["name"] == name:
            tool = record
    if tool is None:
        _audit(store, subject, name, name, "refused", "unknown-tool", tick)
        return (None, "unknown-tool")

    if not authorized(principal, tool):
        held = stage_01.rights(principal)
        reason = ("read-only" if tool["verb"] == "write" and "rows:read" in held
                  else "no-right")
        _audit(store, subject, name, tool["table"], "refused", reason, tick)
        return (None, reason)

    reason = _spend(keyring, tool, tick)
    if reason is not None:
        _audit(store, subject, name, tool["table"], "refused", reason, tick)
        return (None, reason)

    counted = _count(calls, tool["name"], tick)
    if counted > tool["limits"]:
        _uncount(calls, tool["name"], tick)
        _audit(store, subject, name, tool["table"], "refused", "rate-limited", tick)
        return (None, "rate-limited")

    offender = _offender(tool, args)
    if offender is not None:
        _uncount(calls, tool["name"], tick)
        _audit(store, subject, name, offender, "refused", "bad-arguments", tick)
        return (None, "bad-arguments")

    result = _work(store, tool, args)
    _audit(store, subject, name, tool["table"], "allowed", _done(tool, result), tick)
    return (result, None)
