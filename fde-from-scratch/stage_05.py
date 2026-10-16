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
the secret even by accident, so there is nothing to redact after the fact. A lease is
therefore a capability rather than a password: it is worth nothing outside the vault
that minted it, and a caller that logs every line it touches still logs nothing it
should not.

DESIGN DECISION — why is a call's order authorization, then lease, then counter, then
work?

Because each step asks a different question and the order decides what a refusal
means. Authorization asks whether this caller may touch this tool at all, so it comes
first: a caller with no right never gets near the credential. The lease asks whether
the vault will let this name be used *now*, so it comes next: it is the point of trust
between the course and the customer's secret store. The counter then measures the work
at the table, and that is why it is the step that is given back when the call is
refused: a call the arguments knock back never reached the table, and a budget spent
on a call that did not happen would refuse the next call that could. The lease is not
given back — a lease is minted per call, spent once, and the vault's own log records
it — which is the price of asking the vault first.

DESIGN DECISION — why is `bad-arguments` a returned reason while a broken shape raises?

Because one is a decision about this call and the other is not a call at all. The
arguments arrive as a mapping or they are not arguments: a tool name that is not a
name, an arguments value that is not a mapping, a catalogue record that is not a
`TOOL_KEYS` record, a lease that is not a lease — none of those can be judged as a
tool call, so they raise `MCPError` naming the offender and both numbers where there
are two. But an argument the tool does not declare, a declared argument the call
leaves out, a value of a type the argument cannot take: those are things a caller
really does, on purpose or by accident, and the closed vocabulary has a word for them
— so they come back as `bad-arguments`, named on the audit line, and the caller can
decide what to do. The same split covers a tool name that is not in the catalogue
(`unknown-tool` is a verdict about the customer's system) and a tool record that is
not a record at all (which raises).

DESIGN DECISION — why is the per-tick budget keyed by the tool rather than by the
caller?

Because the limit belongs to the legacy endpoint and not to the session. A rate limit
is what the customer's system of record can take on one table in one tick, so two
tools must not share one budget — an agent that spent its whole allowance on reads
must still be able to write — and two callers must not share one either: the second
caller's first call is not the first call the table sees. So the structure the caller
owns maps a tool name to the tick it was last counted in and the calls made there, the
pair is replaced the moment the tick moves on, and `tick_calls` answers how many calls
the structure holds. A budget keyed by the caller would refuse the wrong call and
happily overrun the table.

DESIGN DECISION — why does the audit line name the tool and the offending argument
instead of the values the call carried?

Because the audit is written for the customer's auditor and the values are the
customer's data. Every call is one line — allowed or refused — and what the line
needs to say is which tool was called, on whose behalf, whether it was allowed, and,
when it was refused, *which* argument or which tool refused it. The values are not
evidence: they are the payload, and one of them is a purchase order amount on a route
where the credential lives. Names instead of values is also why a secret cannot appear
on the line: the line has no place to put it, and the check asserts the literal is in
no line the estate or the vault kept.

DESIGN DECISION — why is a lease's deadline decided before whether it was redeemed?

Because the tick decides whether the credential exists at all. A lease is a credential
with a deadline, so a lease past `expires_at` is not a credential that was spent — it
is nothing, whatever else is true of it, and the tick at `expires_at` itself is
already past it (`tick < expires_at` is the whole test). A lease that is both expired
and spent therefore answers `lease-expired`, the redemption is never attempted, and
the vault refuses to redeem a lease past its deadline for exactly the same reason.
Both sides of that boundary are checked, because a comparison read the other way is
the difference between a credential and a permanent one.

TODO: implement `MCPError`, `Vault`, `describe`, `authorized`, `tick_calls` and `call`
in this file: the vault that mints and redeems leases over names and secrets, the
validated catalogue of tools, the rights check against a tool's own verb, the per-tick
structure keyed by tool name, and the call that authorizes, spends, counts, refunds,
works and audits — in that order.
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


class MCPError(estate.EstateError):
    """A shape this stage cannot accept, or a call it will not make."""


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
        self._leases = dict(leases)
        self._log = []

    def secret_of(self, name):
        """The secret held under `name`: the vault's own accessor, and the only read.

        A name the vault does not hold is refused by name, and what is answered is
        the secret itself — never a lease, never a hash of it and never a part of it.
        Only code that has already decided it needs the secret calls this; a tool call
        needs a lease, so the secret never reaches the audit line or the arguments.
        """
        raise NotImplementedError("stage 5: implement Vault.secret_of()")

    def lease(self, name, ttl, tick):
        """Mint a lease over `name`: `LEASE_KEYS`, unredeemed, expiring after `ttl`.

        The lease's `expires_at` is `tick + ttl`, so a lease is usable in the tick it
        was minted in and stops being usable at its deadline. A name the vault does
        not hold has no lease to mint and is refused by name; a lifetime that is not a
        positive number of ticks cannot be a deadline and is refused by both sides.
        A fresh lease is minted per call: one lease is spent once.
        """
        raise NotImplementedError("stage 5: implement Vault.lease()")

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
        raise NotImplementedError("stage 5: implement Vault.redeem()")

    def log(self):
        """Every line the vault kept, as `(action, name, tick, verdict)` tuples.

        `action` is `"lease"` or `"redeem"`, `verdict` is what came of it (`"leased"`,
        `"redeemed"`, `"expired"`, `"spent"`, `"unknown"`), and no line carries a
        secret — there is no field for one.
        """
        raise NotImplementedError("stage 5: implement Vault.log()")


def describe(tools):
    """The catalogue as `TOOL_KEYS` records, validated, in catalogue order.

    A tool is a record with exactly the keys of `TOOL_KEYS` in that order, a name, a
    verb out of `VERBS`, a table this estate has, argument names this estate's tables
    have, and a positive per-tick limit. Anything else is not a tool this stage can
    describe and is refused naming what arrived.
    """
    raise NotImplementedError("stage 5: implement describe()")


def authorized(principal, tool):
    """Whether this principal's rights allow this tool: the verb's own right, or nothing.

    A read tool takes `rows:read` and a write tool takes `rows:write`, read from the
    principal's roles through stage 1 rather than from the tool's verb alone — a verb
    is not a permission. The answer is a `bool`; the *reason* a call was refused is
    `call`'s to answer, because `read-only` and `no-right` are two different facts.
    """
    raise NotImplementedError("stage 5: implement authorized()")


def tick_calls(calls):
    """How many calls the per-tick structure holds.

    The structure maps a tool name to the tick it was last counted in and the calls
    made there, so this is the sum of the counts it holds. A structure whose entries
    are not pairs of whole numbers is refused naming the entry.
    """
    raise NotImplementedError("stage 5: implement tick_calls()")


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
    raise NotImplementedError("stage 5: implement call()")
