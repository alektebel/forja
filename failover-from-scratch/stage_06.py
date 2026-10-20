"""Failover From Scratch — stage 6: Sessions: the pinned answer is a table, not a feeling.

TODO: implement each function; the docstring is the contract.

A pinned client does not shop for the freshest replica: its session is
home-pinned, and the ONLY honest answer about where to send it is a
table. Stage 5's health verdict, the regions' epochs and the epoch the
session has already SEEN decide the row; the table then answers one of
`("serve", region)`, `("redirect", region)`, `("refused", reason)`.
Hysteresis is the load-bearing row: a SUSPECT home still serves its own
pinned clients — a flap must not migrate everybody at once, because
every migration costs a fencing question, and a region that flaps would
spend the fleet's epoch counter for nothing. The fencing row is the
other half: redirecting into, or serving from, an epoch BELOW what the
session already saw would answer the client with a state it has outgrown
— the write its retry carries would vanish — so the session is refused,
not quietly demoted. And `ALL_DIE` lives in the last row: home down, no
promoted other, nothing to serve — `("refused", "no-home")`.

DESIGN DECISION — serve while `"up"` OR `"suspect"`, never only `"up"`?
Because `"suspect"` means "a majority still answers, but something is
lagging or unheard" — and a pinned client reading from a suspect home
gets the home's own coalesced answer, which is correct data. The only
verdict that moves a session is `"down"`, which stage 5 reserved for
WITNESSED death. Serving on suspect is what keeps a flap from becoming
a thundering migration; refusing a live-but-suspect home would promote
the other side on an artifact of the health signal.

DESIGN DECISION — why does fencing compare PLAIN ints and refuse
instead of serving the old state anyway?
Because `seen_epoch` is the session's own memory: the client already
holds the answer of a node at that epoch, and any region that cannot
show an epoch at least that high cannot show that answer. Serving a
lower epoch would delete the session's history — the retry would apply
against a state that lost it. The refusal names `fenced`: the table
refuses to lie about where the write is safe.

DESIGN DECISION — why is a promoted-but-down other region `no-home`,
not a redirect target?
Because promotion is a decision, not a pulse: the other region adopted
an epoch, then died, and a redirect would send the session to a region
with no live node to answer it. The fabric's fallback gate asks the
same question in the same order — eligible means promoted AND able to
answer (`up` or `suspect`) — so the table row and the world agree."""


import topology

import stage_01 as s1

import stage_05 as s5

FailError = s1.FailError

REASONS = ("fenced", "no-home")

def _check_verdict(where, value):
    """One health value must be one of stage 5's three verdicts; the
    refusal names the argument and the offender."""
    raise NotImplementedError("stage 6: implement _check_verdict()")

def _check_epoch(where, value):
    """An epoch is an int >= 0 — never a float, never a bool; the
    refusal names the argument and the offender."""
    raise NotImplementedError("stage 6: implement _check_epoch()")

def answer_region(home, home_health, home_epoch, other_health,
                  other_promoted, other_epoch, seen_epoch):
    """The session table for a client pinned to `home`. A home that is
    `"up"` or `"suspect"` SERVES — hysteresis: a flap never migrates
    everybody at once. A home that is `"down"` redirects only when the
    other region is `other_promoted` AND its health is `"up"` or
    `"suspect"`; anything else is `("refused", "no-home")`. Either the
    served or the redirected region must show an epoch at least
    `seen_epoch` — the session's own memory — or the answer is
    `("refused", "fenced")`. Malformed regions, verdicts, epochs or a
    non-bool `other_promoted` raise `FailError` naming the offender."""
    raise NotImplementedError("stage 6: implement answer_region()")
