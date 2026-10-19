"""Consensus From Scratch — stage 10: The proof: one history, two verdicts.

Everything before this stage was a law stated; this stage is the law
tested. The full node protocol — `init`, `recv`, `tick`, `client`,
`persist`, `recover` — composed from stages 1–9, driven by `sim.Cluster`
through every scenario in `scenarios.py`, judged by `history.linearizable`
against the history the fabric itself recorded, and pinned against the
`PINS` table: the leaders, the first commits, the conflicts, the
verdicts — for a correct node, and for the foil.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why does `client` answer reads from the COMMITTED state
and never append a `get` to the log?
Because a read has no order to agree on: its value is whatever the state
machine holds at the instant the leader answers, and the fabric records
that value in the history. A `get` that became an entry would let a
majority commit a command that changes nothing and consume a slot — and a
leader that reads uncommitted entries would answer a value that a newer
term can still overwrite: the stale read the foil answers under LAGGARD.
`("read", value)` / `("not_leader", hint)` / `(None,)` for an accepted
write — those three answers are the whole client contract, and `sim`
refuses anything else.

DESIGN DECISION — why is a non-leader's `client` a refusal with a hint
rather than a forward?
Because the fabric has no directory and the protocol has no obligation to
invent one: `("not_leader", hint)` records an invocation that took no
effect anywhere, and `history` drops refused calls on exactly that law.
Forwarding through the cluster would add a routing protocol the course
never asked for; the hint is where the client (in stage 10's checks, the
scenario's submit list) retries — and a retry closes the older open call
as a timeout, which the fabric also records honestly.

DESIGN DECISION — why does `prove(name)` return the run plus the pins
side by side instead of a bool?
Because a verdict without evidence is this course's foil: the check wants
to see WHICH leader was elected at WHICH tick and WHICH command landed at
slot 0, the same way `verify_provided` shows them. `("scenario", "result",
"pins", "linear")` — the stage compares its own run against the probe
column and asks the linearizer; the bool is `linear` AND equality, but
the tuple is the proof.

DESIGN DECISION — why must `audit` RUN the foil through the fabric rather
than read `PINS` and trust it?
Because `PINS` is the world's claim and the audit is the stage's proof:
a stage that reports the foil behaving correctly has either edited the
world (digest check catches that) or is not driving it at all. The audit
instantiates `sim.Cluster(naive, scenario=...)` on ASYMMETRIC and demands
a non-empty `conflicts` — the double-committed slot — and refuses its own
verdict if the foil comes back clean. The stage imports the foil ONLY
through `sim.Cluster`'s node-module parameter; `naive` never enters the
stage's own logic (the audit's banned-import check enforces the
separation).
"""

def init(node_id, peers):
    """A fresh follower at term 0, empty log, the five-name config."""
    raise NotImplementedError("stage 10: implement init()")


def recv(state, message):
    """One message in, replies out: the composed term law (stage 6), the
    vote (1), the append and its reply (3, 4, 5), the snapshot (8), the
    membership command applying at commit (9): (state2, replies)."""
    raise NotImplementedError("stage 10: implement recv()")


def tick(state):
    """One clock tick: heartbeat when leading, election when the silence
    outlasts `sim.timeout(s["id"])`, otherwise age the timer: (state2,
    replies)."""
    raise NotImplementedError("stage 10: implement tick()")


def client(state, command):
    """The application's call: (state2, messages, answer) — leader
    appends writes and answers reads from committed state; everyone else
    refuses."""
    raise NotImplementedError("stage 10: implement client()")


def prove(name):
    """Run scenario `name` through `sim.Cluster`, compare against the
    probe pins, linearize the history: ("scenario", "result", "pins",
    "linear")."""
    raise NotImplementedError("stage 10: implement prove()")


def audit(proofs):
    """The verdict over every scenario PLUS the foil's ASYMMETRIC run
    through the fabric: ("verdict", "reasons") — "pass" only when all
    histories linearize, all pins match, and the naive foil demonstrably
    double-commits."""
    raise NotImplementedError("stage 10: implement audit()")
