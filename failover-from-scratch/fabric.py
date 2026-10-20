"""fabric.py — the deterministic two-region driver (provided world).

H6's `sim.Cluster` shape with the two things a failover course cannot be
faked without: two INDEPENDENT clocks (west ticks once per TICK_RATE
global ticks, so stamps never line up across the link) and a WATCH
CHANNEL that carries death truth: a `kill` event delivers ("dead",
victim) to every live same-region peer on the tick, and to the other
region ONLY across the link — so a cut is silence and never a notice.
The health signal a student writes can be built from what arrives;
counting missing heartbeats is the foil's mistake, and the world makes
it observable by simply never sending one.

Client calls model a pinned session with an endpoint list: a scheduled
("client", t, home, command) lands on the home region's ENTRY node —
the first live id, sorted. Only when home has no live node at all does
the request try the other region's entry. A ("redirect", other) answer
makes the fabric re-inject the SAME command (same rid) at other's entry
one tick later, exactly one hop; a second redirect is a refused "loop",
and a node that redirects when the client already fell back to it is
misbehaving. That is how the same (client, rid) legitimately arrives
twice; the student's ledger is what makes the second arrival cost
nothing.

Messages the student sends are built with `message(...)` so every shape
is pinned: field 0 the kind, field 1 the target; the fabric routes on
the target and nothing else. `sync` never crosses the link (a stage
caught trying is dropped and counted); `relay`, `hint`, `propose`,
`adopt` cross and queue. A dead node never receives: its message is
counted in `dropped`. And a node dies with its own outbound traffic:
relays queued but undelivered when it is killed are gone — that is the
traffic stage 9's `lost` column prices in.

The record is a pure function of the schedule: `result()` reads states
and answers — `promotes` (first tick a node in a region announces epoch
>= 1), `answers`, `dups` (same (client, rid) applied twice by one
node), `lost` (acked writes no live node at the horizon has applied),
`final_states`, `dropped`, `delivered`.
"""

import kv
import topology
from topology import REGIONS, NODES, nodes_of, region_of


class FabricError(ValueError):
    """The driver's refusal: a message, state, or scenario the world cannot run."""

KINDS = ("sync", "relay", "hint", "propose", "adopt")
WATCH_KINDS = ("dead", "alive")

STATE_KEYS = ("epoch", "promoted", "applied", "store", "hints",
              "applied_count", "notices")

# `notices` is the tuple of subject ids THIS node currently believes dead
# ("alive" notices retract). The fabric writes nothing into a state; it
# only validates the shape of the set the student's node maintains. A
# watch notice the link could not carry QUEUES and lands one tick after
# the heal; a notice whose recipient has died meanwhile is dropped — the
# state of the dead is settled by the propose/adopt quorum, not memory.


def message(kind, target, *payload):
    """`("kind", "target", ...)` — the only legal student message shape."""
    if kind not in KINDS:
        raise FabricError("fabric: kind %r is not a message kind %s (watch "
                          "kinds %s are the fabric's to send, never yours)"
                          % (kind, ", ".join(KINDS), ", ".join(WATCH_KINDS)))
    if not isinstance(target, str) or target not in dict(NODES):
        raise FabricError("fabric: a message must target a fleet node, got %r"
                          % (target,))
    return (kind, target) + tuple(payload)


def msg_kind(m):
    if not isinstance(m, tuple) or not m:
        raise FabricError("fabric: a message must be a non-empty tuple, got %r"
                          % (m,))
    return m[0]


def msg_target(m):
    if not isinstance(m, tuple) or len(m) < 2:
        raise FabricError("fabric: a message must carry a target at field 1, "
                          "got %r" % (m,))
    return m[1]


def parse_command(text):
    """`"set k=v c=a r=7"` -> ("set", key, val, client, rid);
    `"get k c=a r=8"` -> ("get", key, None, client, rid). The rid is the
    client's: a retry re-sends it and the fabric never rewrites it.
    Both shapes are 5-tuples so callers index identically."""
    if not isinstance(text, str):
        raise FabricError("fabric: a command must be a string, got %r" % (text,))
    parts = text.split()
    if not parts or parts[0] not in ("set", "get"):
        raise FabricError("fabric: a command must start with set/get, got %r"
                          % (text,))
    op = parts[0]
    fields = {}
    payload = None
    for p in parts[1:]:
        name, sep, value = p.partition("=")
        if sep and name in ("c", "r"):
            if name in fields:
                raise FabricError("fabric: command %r repeats %s=" % (text, name))
            fields[name] = value
        elif sep and op == "set" and payload is None:
            payload = (name, value)
        elif not sep and op == "get" and payload is None:
            payload = (p, None)
        else:
            raise FabricError("fabric: malformed command %r (token %r)"
                              % (text, p))
    if payload is None or "c" not in fields or "r" not in fields:
        raise FabricError("fabric: command %r needs a key=payload token, c= "
                          "and r=" % (text,))
    key, value = payload
    try:
        rid = int(fields["r"])
    except ValueError:
        raise FabricError("fabric: rid %r is not an int" % (fields["r"],))
    if rid < 0:
        raise FabricError("fabric: rid %d is below 0" % (rid,))
    return (op, key, value, fields["c"], rid)


def _validate_state(state, node_id, where):
    if not isinstance(state, dict):
        raise FabricError("fabric: %s state of %s must be a dict, got %r"
                          % (where, node_id, type(state).__name__))
    for key in STATE_KEYS:
        if key not in state:
            raise FabricError("fabric: %s state of %s is missing %r "
                              "(required keys: %s)"
                              % (where, node_id, key, ", ".join(STATE_KEYS)))
    if not isinstance(state["epoch"], int) or isinstance(state["epoch"], bool) \
            or state["epoch"] < 0:
        raise FabricError("fabric: %s: %s has epoch %r, not an int >= 0"
                          % (where, node_id, state["epoch"]))
    if not isinstance(state["promoted"], bool):
        raise FabricError("fabric: %s: %s has promoted %r, not a bool"
                          % (where, node_id, state["promoted"]))
    if not isinstance(state["applied_count"], int) or \
            isinstance(state["applied_count"], bool) or \
            state["applied_count"] < 0:
        raise FabricError("fabric: %s: %s has applied_count %r, not an int "
                          ">= 0" % (where, node_id, state["applied_count"]))
    if not isinstance(state["applied"], tuple):
        raise FabricError("fabric: %s: %s has applied %r, not a tuple of "
                          "(client, rid, key)" % (where, node_id,
                                                  state["applied"]))
    for entry in state["applied"]:
        if (not isinstance(entry, tuple) or len(entry) != 3
                or not isinstance(entry[0], str)
                or not isinstance(entry[1], int) or isinstance(entry[1], bool)
                or not isinstance(entry[2], str)):
            raise FabricError("fabric: %s: %s applied entry %r is not "
                              "(client, rid, key)" % (where, node_id, entry))
    if not isinstance(state["store"], dict):
        raise FabricError("fabric: %s: %s has store %r, not a dict"
                          % (where, node_id, state["store"]))
    for versions in state["store"].values():
        if not isinstance(versions, tuple):
            raise FabricError("fabric: %s: %s store values must be tuples of "
                              "versions, got %r" % (where, node_id, versions))
        for v in versions:
            kv._check_version(v)
    if not isinstance(state["hints"], tuple):
        raise FabricError("fabric: %s: %s has hints %r, not a tuple"
                          % (where, node_id, state["hints"]))
    for h in state["hints"]:
        if not (isinstance(h, tuple) and len(h) == 4 and h[0] == kv.KIND_HINT):
            raise FabricError("fabric: %s: %s hint %r is not a kv.hint"
                              % (where, node_id, h))
    if not isinstance(state["notices"], tuple):
        raise FabricError("fabric: %s: %s has notices %r, not a tuple of "
                          "subject ids" % (where, node_id, state["notices"]))
    for n in state["notices"]:
        if not isinstance(n, str) or n not in dict(NODES):
            raise FabricError("fabric: %s: %s notice %r is not a fleet id"
                              % (where, node_id, n))


def _validate_messages(msgs, node_id, where):
    if not isinstance(msgs, tuple):
        raise FabricError("fabric: %s: %s returned messages %r, not a tuple"
                          % (where, node_id, msgs))
    for m in msgs:
        kind = msg_kind(m)
        if kind in WATCH_KINDS:
            raise FabricError("fabric: %s: %s sent watch kind %r — the "
                              "watch channel is the world's"
                              % (where, node_id, kind))
        if kind not in KINDS:
            raise FabricError("fabric: %s: %s sent unknown kind %r"
                              % (where, node_id, kind))
        if msg_target(m) == node_id:
            raise FabricError("fabric: %s: %s messaged itself"
                              % (where, node_id))


class Fabric:
    """The whole simulation: two clocks, one link, one record.

    `run(ticks)` drives to an ABSOLUTE horizon (re-running below the
    current tick is a no-op); per tick: scenario events -> due
    deliveries (watch notices, cross-region traffic, redirect
    re-injections) -> node ticks (east every tick, west every
    TICK_RATE) -> promote bookkeeping.
    """

    def __init__(self, node, ids=None, scenario=()):
        for fn in ("init", "recv", "tick", "client"):
            if not hasattr(node, fn):
                raise FabricError("fabric: the node module is missing %s" % fn)
        if ids is None:
            ids = tuple(n for n, _ in NODES)
        ids = tuple(ids)
        if len(ids) < 4:
            raise FabricError("fabric: a failover needs at least four nodes, "
                              "got %d" % len(ids))
        for i in ids:
            region_of(i)  # refuses ids outside the fleet
        self.node = node
        self.ids = ids
        self.down = set()
        self.link_up = True
        self.tick_now = 0
        self._events = tuple(scenario)
        self._cross = []      # (due-or-None, sender, msg) waiting on the link
        self._watch = []      # (due-or-None, target, notice) waiting on the link
        self._inject = []     # (tick, region, command) redirect re-injections
        self.states = {}
        self.answers = []
        self.acked = []       # (client, rid, key) whose set was acked
        self.delivered = []   # (tick, sender, kind)
        self.dropped = []     # (tick, sender, kind, target)
        self.promotes = []
        self._promoted_seen = set()
        for i in ids:
            state = node.init(i, topology.peers_of(i))
            _validate_state(state, i, "init")
            self.states[i] = state

    # ---- driving -------------------------------------------------------

    def run(self, ticks):
        if ticks < self.tick_now:
            return self.tick_now
        while self.tick_now <= ticks:
            t = self.tick_now
            # Order within a tick: world events first (kills/revives/cut/heal
            # queue their traffic), then every due delivery lands, then the
            # nodes tick, and ONLY THEN the scheduled clients speak — so a
            # revive and its catch-up notices are visible to a same-tick
            # request, and a same-tick death is felt before it is served.
            self._events_at(t)
            self._deliver_due()
            self._tick_nodes(t)
            self._clients_at(t)
            self._record_promotes(t)
            self.tick_now += 1
        return self.tick_now

    def _events_at(self, t):
        # scenario events are kind-first: ("kill", t, id), ("revive", t,
        # id), ("cut", t), ("heal", t); clients are deferred below.
        for ev in self._events:
            if ev[1] != t:
                continue
            kind = ev[0]
            if kind == "kill":
                self._kill(t, ev[2])
            elif kind == "revive":
                self._revive(t, ev[2])
            elif kind == "cut":
                self.link_up = False
            elif kind == "heal":
                self.link_up = True
            elif kind == "client":
                pass  # deferred to _clients_at, after this tick's traffic
            else:
                raise FabricError("fabric: unknown scenario event %r" % (ev,))

    def _clients_at(self, t):
        for ev in self._events:
            if ev[1] != t or ev[0] != "client":
                continue
            self._client(t, ev[2], ev[3])

    def _kill(self, t, node_id):
        if node_id not in self.ids:
            raise FabricError("fabric: kill of %r at %d: not a fleet id"
                              % (node_id, t))
        if node_id in self.down:
            raise FabricError("fabric: kill of %r at %d: already down"
                              % (node_id, t))
        self.down.add(node_id)
        # a node dies with its own outbound traffic: relays queued but
        # undelivered at the kill tick are gone (counted as dropped).
        kept = []
        for due, sender, m in self._cross:
            if sender == node_id:
                self.dropped.append((t, sender, msg_kind(m), msg_target(m)))
            else:
                kept.append((due, sender, m))
        self._cross = kept
        self._watch_notice(t, node_id, "dead")

    def _revive(self, t, node_id):
        if node_id not in self.ids:
            raise FabricError("fabric: revive of %r at %d: not a fleet id"
                              % (node_id, t))
        if node_id not in self.down:
            raise FabricError("fabric: revive of %r at %d: it was not down"
                              % (node_id, t))
        self.down.discard(node_id)
        # Catch-up: death is a fact about the region, not a transient
        # event. A revived node that missed notices while down receives
        # ("dead", x) for every x still down — same-region lands now,
        # cross-region obeys the link like any other notice.
        for x in self.ids:
            if x == node_id or x not in self.down:
                continue
            if region_of(x) == region_of(node_id):
                self._watch.append((t, node_id, ("dead", x)))
            elif self.link_up:
                self._watch.append((t + 1, node_id, ("dead", x)))
            else:
                self._watch.append((None, node_id, ("dead", x)))
        self._watch_notice(t, node_id, "alive")

    def _watch_notice(self, t, subject, notice_kind):
        for target in self.ids:
            if target == subject or target in self.down:
                continue
            notice = (notice_kind, subject)
            if region_of(target) == region_of(subject):
                self._watch.append((t, target, notice))
            elif self.link_up:
                self._watch.append((t + 1, target, notice))
            else:
                self._watch.append((None, target, notice))

    def _deliver_due(self):
        t = self.tick_now
        still = []
        for due, target, notice in self._watch:
            if due is None:
                if not self.link_up:
                    still.append((due, target, notice))
                    continue
                still.append((t + 1, target, notice))
                continue
            if t < due:
                still.append((due, target, notice))
                continue
            if target in self.down:
                self.dropped.append((t, notice[1], "watch-" + notice[0],
                                     target))
                continue
            self._watch_deliver(t, target, notice)
        self._watch = still
        still_cross = []
        for due, sender, m in self._cross:
            target = msg_target(m)
            if sender in self.down:
                # died after the queue tick was set, before delivery
                self.dropped.append((t, sender, msg_kind(m), target))
                continue
            if target in self.down:
                self.dropped.append((t, sender, msg_kind(m), target))
                continue
            if due is None:
                if not self.link_up:
                    still_cross.append((due, sender, m))
                    continue
                still_cross.append((t + 1, sender, m))
                continue
            if t < due:
                still_cross.append((due, sender, m))
                continue
            if not self.link_up:
                # the link cut again before delivery could land
                still_cross.append((None, sender, m))
                continue
            self._deliver(t, sender, m)
        self._cross = still_cross
        due_now = [item for item in self._inject if item[0] == t]
        if due_now:
            self._inject = [item for item in self._inject if item[0] != t]
            for _it, region, cmd in sorted(due_now):
                self._client(t, region, cmd, redirect_hop=True)

    def _watch_deliver(self, t, target, notice):
        state = self.states[target]
        state, replies = self.node.recv(state, notice)
        _validate_state(state, target, "recv-watch")
        self.states[target] = state
        self.delivered.append((t, notice[1], "watch-" + notice[0]))
        self._route(t, target, replies)

    def _tick_nodes(self, t):
        for i in sorted(self.ids):
            if i in self.down:
                continue
            if region_of(i) == "west" and t % topology.TICK_RATE != 0:
                continue
            state, replies = self.node.tick(self.states[i])
            _validate_state(state, i, "tick")
            self.states[i] = state
            self._route(t, i, replies)

    # ---- routing -------------------------------------------------------

    def _route(self, t, sender, msgs):
        _validate_messages(msgs, sender, "route")
        for m in msgs:
            self._send(t, sender, m)

    def _send(self, t, sender, m):
        target = msg_target(m)
        if target not in self.ids:
            raise FabricError("fabric: %s sent to %r, not a fleet id"
                              % (sender, target))
        if len(m) < 3 or m[2] != sender:
            raise FabricError("fabric: %s sent %r without naming itself at "
                              "field 2 — the wire carries its sender"
                              % (sender, m))
        if target in self.down:
            self.dropped.append((t, sender, msg_kind(m), target))
            return
        if region_of(target) != region_of(sender):
            if msg_kind(m) == "sync":
                self.dropped.append((t, sender, "sync", target))
                return
            if not self.link_up:
                self._cross.append((None, sender, m))
                return
            self._cross.append((t + 1, sender, m))
            return
        self._recv(t, sender, m)

    def _deliver(self, t, sender, m):
        # a queued cross message whose time has come: the link is up and
        # both ends are live (checked by the caller) — delivery never
        # re-queues, so a healed cut cannot livelock the queue.
        self._recv(t, sender, m)

    def _recv(self, t, sender, m):
        target = msg_target(m)
        state = self.states[target]
        state, replies = self.node.recv(state, m)
        _validate_state(state, target, "recv")
        self.states[target] = state
        self.delivered.append((t, sender, msg_kind(m)))
        self._route(t, target, replies)

    # ---- clients -------------------------------------------------------

    def _client(self, t, home, command, redirect_hop=False):
        parsed = parse_command(command)
        op, key, _value, client, rid = parsed
        if home not in REGIONS:
            raise FabricError("fabric: client home %r is not a region" % (home,))
        # endpoint list = home region's entry while home has ANY live node;
        # only a fully dead home may fall back — and ONLY to a region the
        # fleet has actually promoted. Failover is a decision, never an
        # accident: while the survivor has not adopted a new epoch, the
        # dead home's clients are refused, not absorbed.
        target = self._entry(home)
        fell_back = False
        if target is None:
            other = "west" if home == "east" else "east"
            if not self._region_promoted(other):
                self.answers.append((t, client, rid,
                                     ("refused", "unpromoted")))
                return
            target = self._entry(other)
            fell_back = target is not None
        if target is None:
            self.answers.append((t, client, rid, ("refused", "no-live")))
            return
        state, msgs, answer = self.node.client(self.states[target], command)
        _validate_state(state, target, "client")
        self.states[target] = state
        self._route(t, target, msgs)
        if (not isinstance(answer, tuple) or not answer
                or answer[0] not in ("ok", "applied", "redirect", "refused")):
            raise FabricError("fabric: %s answered %r, not a legal verdict"
                              % (target, answer))
        if answer[0] == "redirect" and (len(answer) != 2
                                        or answer[1] not in REGIONS):
            raise FabricError("fabric: %s redirected to %r, not a region"
                              % (target, answer))
        if answer[0] == "redirect" and fell_back:
            # the client is ALREADY at the other side's entry and that entry
            # declines: there is nowhere left to send it, so the retry lands
            # as a refusal, not a hop.
            answer = ("refused", "no-live")
        self.answers.append((t, client, rid, answer))
        if op == "set" and answer[0] in ("ok", "applied"):
            entry = (client, rid, key)
            if entry not in self.acked:   # a replay re-answers, never re-acks
                self.acked.append(entry)
        if answer[0] == "redirect":
            region = answer[1]
            if redirect_hop:
                self.answers.append((t, client, rid, ("refused", "loop")))
                return
            self._inject.append((t + 1, region, command))

    def _region_promoted(self, region):
        # a region counts as promoted when any LIVE node of it has adopted
        # an epoch above the initial one — the decision the fallback gate
        # checks ("failover is a decision, never an accident").
        for n in nodes_of(region):
            if n in self.ids and n not in self.down:
                st = self.states[n]
                if st["promoted"] and st["epoch"] > topology.INITIAL_EPOCH:
                    return True
        return False

    def _entry(self, region):
        for n in nodes_of(region):
            if n in self.ids and n not in self.down:
                return n
        return None

    # ---- record --------------------------------------------------------

    def _record_promotes(self, t):
        for i in sorted(self.ids):
            state = self.states[i]
            if state["promoted"] and state["epoch"] >= 1:
                mark = (region_of(i), state["epoch"])
                if mark not in self._promoted_seen:
                    self._promoted_seen.add(mark)
                    self.promotes.append((t, region_of(i), state["epoch"]))

    def result(self):
        return {
            "ticks": self.tick_now,
            "ids": self.ids,
            "promotes": tuple(self.promotes),
            "answers": tuple(self.answers),
            "dups": self._dups(),
            "lost": self._lost(),
            "final_states": dict((i, self.states[i]) for i in sorted(self.ids)),
            "dropped": tuple(self.dropped),
            "delivered": tuple(self.delivered),
        }

    def _dups(self):
        dups = []
        for i in sorted(self.ids):
            seen = set()
            for client, rid, _key in self.states[i]["applied"]:
                if (client, rid) in seen:
                    dups.append((client, rid, i))
                else:
                    seen.add((client, rid))
        return tuple(dups)

    def _lost(self):
        alive_applied = set()
        for i in sorted(self.ids):
            if i in self.down:
                continue
            for client, rid, _key in self.states[i]["applied"]:
                alive_applied.add((client, rid))
        return tuple((c, r, k) for (c, r, k) in self.acked
                     if (c, r) not in alive_applied)
