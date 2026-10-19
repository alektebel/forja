"""sim.py — the deterministic network and the cluster driver (provided world).

Five nodes, integer ticks, ordered delivery, links cut and healed by a
schedule. This module owns the only two things a stage must never touch:
the clock and the fabric. A scenario is data (see `scenarios.py`); the
driver interprets it, tick by tick:

- at each tick the scenario's events happen first (cut, heal, crash,
  restart);
- every live node then gets `tick(state)` in id order; its replies are
  queued;
- the queue drains in FIFO order inside the tick: each delivery calls
  `recv(state, msg)` and queues its replies behind the pending ones;
- a message whose link is severed at the moment of delivery is DROPPED —
  never delayed, never reordered. What the fabric adds cannot be undone
  by luck: every run of a scenario is the same run.

Routing is the fabric's, not the node's: a REQUEST_VOTE, an APPEND or a
SNAPSHOT is one message the fabric sends to every live peer; a VOTE_REPLY
answers the candidate it names; an APPEND_REPLY or SNAPSHOT_REPLY answers
the leader it names, or — when the stage left that field out — the peer
whose APPEND the reply's author last accepted, which is what a real
follower does: it replies to who it believes leads.

The node protocol the driver calls:

    init(id, peers)         -> state      (a fresh follower)
    recv(state, msg)        -> (state, replies)
    tick(state)             -> (state, replies)
    client(state, command)  -> (state, messages, answer)

`command` is a string the application layer owns: `"k=v"` writes k,
`"get k"` reads it, `"members:a,b,c"` is a membership change. A client
call on a leader appends through the leader's own machinery and returns
the wire messages it broadcast; `answer` is None for a write (it completes
when the world sees it commit) and `("read", value)` for a read taken from
the node's committed state machine. On any other role the node answers
`("not_leader", hint)` and `messages` is empty.

A crash writes the node's state through the protocol's own `persist` (when
it has one) and then tears — `disk.crash()` loses the last record — so a
restarted node recovers whatever the stage's `recover` can read from the
bytes that survived. A protocol without `persist` restarts blank.

The one asymmetry between nodes is `wire.TIMEOUTS`: five fixed election
timeouts in ticks. A node compares its own row against its `elapsed` and
starts an election when the silence outlasts the timeout. No `random`,
no wall clock, anywhere.
"""

import wire
from disk import Disk

TIMEOUTS = wire.TIMEOUTS
HEARTBEAT = wire.HEARTBEAT

DEFAULT_PEERS = tuple(sorted(node for node, _ticks in TIMEOUTS))

MAX_DRAIN = 10000  # a livelocked protocol must hang the run, not the box


def timeout(node_id):
    """The node's election timeout in ticks — the world's only inequality."""
    for node, ticks in TIMEOUTS:
        if node == node_id:
            return ticks
    raise wire.ProtocolError("sim.timeout: %r has no row in the world's "
                             "TIMEOUTS table" % (node_id,))


class Clock:
    """Integer ticks, monotone; the driver's, never a node's."""

    def __init__(self):
        self._now = 0

    def tick(self):
        self._now += 1
        return self._now

    def now(self):
        return self._now


def _peers_of(ids):
    return tuple(sorted(ids))


class Cluster:
    """The driver: a node module and a schedule in, a recorded run out."""

    def __init__(self, node, ids=None, scenario=()):
        for part in ("init", "recv", "tick", "client"):
            if not callable(getattr(node, part, None)):
                raise wire.ProtocolError("sim.Cluster: the node module must "
                                         "carry %s()" % (part,))
        self.node = node
        self.ids = _peers_of(ids or DEFAULT_PEERS)
        if len(self.ids) < 3:
            raise wire.ProtocolError("sim.Cluster: consensus needs at least "
                                     "three nodes, got %r" % (self.ids,))
        for node_id in self.ids:
            timeout(node_id)  # every node must have a row in the table
        self.scenario = tuple(scenario)
        self.clock = Clock()
        self.states = {}
        self.disks = {}
        self._reply_to = {}
        self._cut = set()
        self._pending = []      # (sender, target, message)
        self._deliveries = []
        self.dropped = []
        self.leaders = []
        self.committed = []     # (tick, index, term, command) first commits
        self._committed_index = {}   # index -> first command committed there
        self._committed_seen = {}    # (index, term) -> command, dedup
        self.conflicts = []     # (tick, index, first, other): the same
        # slot committed with two different commands — the safety law in
        # one list, recorded once per index.
        self.history = []       # (kind, tick, proc, op, arg, value)
        self._opens = {}        # proc -> (tick, op, arg) waiting completion
        self.events = []
        self._max_tick = 0
        self._crashed = set()

    # -- boot and restart -------------------------------------------------

    def boot(self):
        for node_id in self.ids:
            self.states[node_id] = self.node.init(node_id, self.ids)

    def _fresh(self, node_id):
        self.states[node_id] = self.node.init(node_id, self.ids)

    def _save(self, node_id):
        """The fabric's storage model: every state transition is one
        record. A crash tears the LAST one off — the write that was in
        flight when the power died."""
        persist = getattr(self.node, "persist", None)
        if not callable(persist):
            return
        disk = self.disks.setdefault(node_id, Disk(node_id))
        disk.write(bytes(persist(self.states[node_id])))

    def _crash(self, node_id):
        state = self.states.get(node_id)
        if state is None:
            return
        self._save(node_id)
        disk = self.disks.get(node_id)
        if disk is not None:
            disk.crash()  # the last write is the one that never survived
        del self.states[node_id]
        self._crashed.add(node_id)

    def _restart(self, node_id):
        if node_id in self.states:
            return
        disk = self.disks.get(node_id)
        saved = disk.read() if disk is not None else b""
        recover = getattr(self.node, "recover", None)
        if saved and callable(recover):
            self.states[node_id] = recover(saved)
        else:
            self.states[node_id] = self.node.init(node_id, self.ids)
        self._crashed.discard(node_id)

    def _apply(self, event):
        kind = event[0]
        tick = event[1]
        if kind == "cut":
            self._cut.add(frozenset((event[2], event[3])))
            self.events.append((tick, "cut", event[2], event[3]))
        elif kind == "heal":
            self._cut = set()
            self.events.append((tick, "heal"))
        elif kind == "crash":
            self._crash(event[2])
            self.events.append((tick, "crash", event[2]))
        elif kind == "restart":
            self._restart(event[2])
            self.events.append((tick, "restart", event[2]))
        elif kind == "submit":
            self.submit(event[2], event[3])
            self.events.append((tick, "submit", event[2], event[3]))
        else:
            raise wire.ProtocolError("sim: scenario event %r is not cut, "
                                     "heal, crash, restart or submit"
                                     % (kind,))

    # -- the client surface -------------------------------------------------

    def submit(self, node_id, command):
        """One client command to one node. A write's invoke is recorded at
        submit and completes when the world sees the entry commit; a read
        completes with the value the node answered (a follower's
        "not_leader" is an error answer the checker ignores); the wire
        traffic the command caused drains before the call returns."""
        if node_id not in self.states:
            return ("refused", "no live node %s" % (node_id,))
        tick = self.clock.now()
        # one process, one call at a time: a client that retries has
        # given up on the call still open.
        for open_key in list(self._opens):
            when, proc, op = self._opens[open_key]
            if proc == node_id:
                del self._opens[open_key]
                self._record(("complete", tick, proc, op, "timeout"))
        state, messages, answer = self.node.client(self.states[node_id],
                                                   command)
        self.states[node_id] = state
        self._save(node_id)
        if command.startswith("get "):
            if answer and answer[0] == "read":
                self._record(("invoke", tick, node_id, command, None))
                self._record(("complete", tick, node_id, command,
                              answer[1]))
            elif answer and answer[0] == "not_leader":
                self._record(("invoke", tick, node_id, command, None))
                self._record(("complete", tick, node_id, command,
                              "not_leader"))
            else:
                raise wire.ProtocolError(
                    "sim.submit: a read must answer ('read', value) or "
                    "('not_leader', hint), got %r" % (answer,))
        elif command.startswith("members:") or "=" in command:
            self._record(("invoke", tick, node_id, command, None))
            if answer and answer[0] == "not_leader":
                self._record(("complete", tick, node_id, command,
                              "not_leader"))
            else:
                self._opens[(node_id, command)] = (tick, node_id, command)
        else:
            raise wire.ProtocolError("sim.submit: %r is neither a read "
                                     "(`get k`) nor a write (`k=v`) nor a "
                                     "membership change" % (command,))
        for message in messages:
            self._queue(node_id, message)
        self._drain(tick)
        return ("ok", command)

    def _record(self, event):
        self.history.append(event)

    # -- the fabric -----------------------------------------------------------

    def _queue(self, sender, message):
        kind = message[0]
        if kind in (wire.REQUEST_VOTE, wire.APPEND, wire.SNAPSHOT):
            for target in self.ids:
                if target != sender and target in self.states:
                    self._pending.append((sender, target, message))
        elif kind == wire.VOTE_REPLY:
            target = message[3]  # the candidate the answer addresses
            if target in self.states:
                self._pending.append((sender, target, message))
        elif kind in (wire.APPEND_REPLY, wire.SNAPSHOT_REPLY):
            at = 4 if kind == wire.SNAPSHOT_REPLY else 5
            leader = message[at] if len(message) > at else None
            if leader is None:
                leader = self._reply_to.get(sender)
            if leader in self.states and leader != sender:
                self._pending.append((sender, leader, message))
        else:
            raise wire.ProtocolError("sim: the fabric cannot route kind %r"
                                     % (kind,))

    def _deliver(self, tick):
        queued = self._pending
        self._pending = []
        used = 0
        while queued:
            sender, target, message = queued.pop(0)
            used += 1
            if used > MAX_DRAIN:
                raise wire.ProtocolError("sim: the run livelocked; the "
                                         "protocol never settles")
            if (sender not in self.states or target not in self.states
                    or frozenset((sender, target)) in self._cut):
                self.dropped.append((tick, sender, target, message))
                continue
            self._deliveries.append((tick, sender, target, message))
            if message[0] in (wire.APPEND, wire.SNAPSHOT):
                self._reply_to[target] = sender
            state, replies = self.node.recv(self.states[target], message)
            self.states[target] = state
            self._save(target)
            self._note_leader(tick, target, state)
            self._note_commits(tick, target, state)
            for reply in replies:
                self._queue(target, reply)
            queued.extend(self._pending)
            self._pending = []

    def _drain(self, tick):
        self._deliver(tick)

    def _note_leader(self, tick, node_id, state):
        if state["role"] != "leader":
            return
        for prior in self.leaders:
            if prior[1] == state["term"] and prior[2] == node_id:
                return
        self.leaders.append((tick, state["term"], node_id))

    def _note_commits(self, tick, node_id, state):
        """The first node to commit an (index, term) records it; the
        commit is a cluster event, not a per-node opinion."""
        start = wire.log_start(state["log"])
        upto = state["commit_index"] - start + 1
        for entry in state["log"][:max(upto, 0)]:
            index, term, command = entry
            seen = self._committed_index.get(index)
            if seen is not None and seen != command:
                if not any(c[1] == index for c in self.conflicts):
                    self.conflicts.append((tick, index, seen, command))
            elif seen is None:
                self._committed_index[index] = command
            key = (index, term)
            if key in self._committed_seen:
                continue
            self._committed_seen[key] = command
            self.committed.append((tick,) + entry)
            command = entry[2]
            for open_key, (when, proc, op) in list(self._opens.items()):
                if op == command:
                    self._record(("complete", tick, proc, op, "ok"))
                    del self._opens[open_key]

    # -- the loop ------------------------------------------------------------

    def run(self, ticks):
        """Drive the clock up to tick number `ticks` (absolute, monotone:
        call it again to extend a finished run) and answer the record."""
        if not self.states:
            self.boot()
        start = max(self._max_tick, self.clock.now()) + 1
        if start > ticks:
            self._max_tick = max(self._max_tick, ticks)
            return self.result()
        for tick in range(start, ticks + 1):
            self.clock.tick()
            for event in self.scenario:
                if event[1] == tick:
                    self._apply(event)
            for node_id in sorted(self.states):
                state, replies = self.node.tick(self.states[node_id])
                self.states[node_id] = state
                self._save(node_id)
                self._note_leader(tick, node_id, state)
                self._note_commits(tick, node_id, state)
                for reply in replies:
                    self._queue(node_id, reply)
            self._drain(tick)
        self._max_tick = max(self._max_tick, ticks)
        # A client that waits forever is a client that gave up: at the
        # horizon every still-open call completes as a timeout — it took
        # no effect anywhere, and `history` refuses to blame it.
        for open_key in list(self._opens):
            when, proc, op = self._opens.pop(open_key)
            self._record(("complete", self._max_tick, proc, op, "timeout"))
        return self.result()

    def result(self):
        return {"ticks": self._max_tick,
                "ids": self.ids,
                "leaders": tuple(self.leaders),
                "committed": tuple(self.committed),
                "conflicts": tuple(self.conflicts),
                "final_states": {node_id: self.states[node_id]
                                 for node_id in sorted(self.states)},
                "final_terms": {node_id: self.states[node_id]["term"]
                                for node_id in sorted(self.states)},
                "history": tuple(self.history),
                "deliveries": tuple(self._deliveries),
                "dropped": tuple(self.dropped),
                "events": tuple(self.events)}
