"""wire.py — the message grammar and the state builders (provided world).

Consensus has one alphabet: the messages a node sends and the states a node
carries. This module freezes both so every stage, every scenario and every
judge speak the same bytes. It is data and constructors only — no logic a
stage could be graded on.

Messages are plain tuples whose first element is the kind. The kinds:

    REQUEST_VOTE   ("request_vote", term, cand, last_term, last_index)
    VOTE_REPLY     ("vote_reply", term, cand, granted)
    APPEND         ("append", term, sender, prev_term, prev_index,
                    entries, leader_commit)
    APPEND_REPLY   ("append_reply", term, node, matched, conflict)
    SNAPSHOT       ("snapshot", term, sender, last_included_term,
                    last_included_index, entries)
    SNAPSHOT_REPLY ("snapshot_reply", term, node, matched)

`entries` is a tuple of `(index, term, command)` triples; `command` is a
string, opaque to the wire and meaningful only to the state machine. Every
constructor refuses a malformed message with `ProtocolError` naming the
field — a stage can never build an impossible message by accident.

States are plain dicts with EXACTLY the keys the role's builder lists; the
builders are the only way to make one (a stage that needs a state calls
them, so a typo in a key is the world's error, not a student's).

The quorum arithmetic lives here once: `majority(n) == n // 2 + 1`, ints
throughout. `TIMEOUTS` is the one source of asymmetry between nodes — five
fixed election timeouts in ticks; there is no randomness anywhere in the
course.
"""

PROTOCOL_VERSION = 1

REQUEST_VOTE = "request_vote"
VOTE_REPLY = "vote_reply"
APPEND = "append"
APPEND_REPLY = "append_reply"
SNAPSHOT = "snapshot"
SNAPSHOT_REPLY = "snapshot_reply"

KINDS = (REQUEST_VOTE, VOTE_REPLY, APPEND, APPEND_REPLY,
         SNAPSHOT, SNAPSHOT_REPLY)

ROLES = ("follower", "candidate", "leader")

# The one asymmetry between the five nodes: election timeouts in ticks.
TIMEOUTS = (("a1", 11), ("a2", 7), ("a3", 9), ("a4", 5), ("a5", 13))

HEARTBEAT = 5  # ticks a leader waits between heartbeats

class ProtocolError(ValueError):
    """The course-wide refusal: the message or state is not the grammar."""


def _check_int(what, field, value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProtocolError("wire.%s: %s must be a non-negative int, got %r"
                            % (what, field, value))
    return value


def _check_slot(what, field, value):
    """An index slot: -1 means "nothing yet" (empty log, no match)."""
    if isinstance(value, bool) or not isinstance(value, int) or value < -1:
        raise ProtocolError("wire.%s: %s must be an int >= -1, got %r"
                            % (what, field, value))
    return value


def _check_id(what, field, value):
    if not isinstance(value, str) or not value:
        raise ProtocolError("wire.%s: %s must be a node id string, got %r"
                            % (what, field, value))
    return value


def _check_entries(what, entries):
    if not isinstance(entries, tuple):
        raise ProtocolError("wire.%s: entries must be a tuple, got %r"
                            % (what, type(entries).__name__))
    for entry in entries:
        if (not isinstance(entry, tuple) or len(entry) != 3
                or isinstance(entry[0], bool) or not isinstance(entry[0], int)
                or entry[0] < 0
                or isinstance(entry[1], bool) or not isinstance(entry[1], int)
                or entry[1] < 0
                or not isinstance(entry[2], str)):
            raise ProtocolError("wire.%s: an entry must be an "
                                "(index, term, command-string) triple, "
                                "got %r" % (what, entry))
    return entries


def request_vote(term, cand, last_term, last_index):
    """A candidate asks a peer for its vote."""
    return (REQUEST_VOTE, _check_int("request_vote", "term", term),
            _check_id("request_vote", "cand", cand),
            _check_int("request_vote", "last_term", last_term),
            _check_slot("request_vote", "last_index", last_index))


def vote_reply(term, node, cand, granted):
    """The peer's answer: `node` is the voter, `cand` the candidate the
    answer addresses, `granted` a bool."""
    if not isinstance(granted, bool):
        raise ProtocolError("wire.vote_reply: granted must be a bool, got %r"
                            % (granted,))
    return (VOTE_REPLY, _check_int("vote_reply", "term", term),
            _check_id("vote_reply", "node", node),
            _check_id("vote_reply", "cand", cand), bool(granted))


def append(term, sender, prev_term, prev_index, entries, leader_commit):
    """The leader's replication: the entry tail after prev, and its commit."""
    _check_entries("append", entries)
    return (APPEND, _check_int("append", "term", term),
            _check_id("append", "sender", sender),
            _check_int("append", "prev_term", prev_term),
            _check_slot("append", "prev_index", prev_index),
            entries, _check_slot("append", "leader_commit", leader_commit))


def append_reply(term, node, matched, conflict, leader=None):
    """The follower's answer: how far its log now matches, and where the
    leader should retry when it does not. `leader` names the peer the
    answer must reach — the fabric routes by it, so a reply is never
    guessed at."""
    message = (APPEND_REPLY, _check_int("append_reply", "term", term),
               _check_id("append_reply", "node", node),
               _check_slot("append_reply", "matched", matched),
               _check_slot("append_reply", "conflict", conflict))
    if leader is not None:
        _check_id("append_reply", "leader", leader)
        return message + (leader,)
    return message


def snapshot(term, sender, last_included_term, last_included_index, entries):
    """The compressed log a leader installs into a follower too far behind."""
    _check_entries("snapshot", entries)
    return (SNAPSHOT, _check_int("snapshot", "term", term),
            _check_id("snapshot", "sender", sender),
            _check_int("snapshot", "last_included_term", last_included_term),
            _check_int("snapshot", "last_included_index",
                       last_included_index), entries)


def snapshot_reply(term, node, matched, leader=None):
    message = (SNAPSHOT_REPLY, _check_int("snapshot_reply", "term", term),
               _check_id("snapshot_reply", "node", node),
               _check_slot("snapshot_reply", "matched", matched))
    if leader is not None:
        _check_id("snapshot_reply", "leader", leader)
        return message + (leader,)
    return message


def kind(message):
    """The kind of a message, refusing anything the grammar does not know."""
    if not isinstance(message, tuple) or not message or message[0] not in KINDS:
        raise ProtocolError("wire.kind: %r is not a wire message" % (message,))
    return message[0]


def majority(config_len):
    """The only quorum arithmetic in the course: n // 2 + 1, ints."""
    if isinstance(config_len, bool) or not isinstance(config_len, int) \
            or config_len <= 0:
        raise ProtocolError("wire.majority: config_len must be a positive "
                            "int, got %r" % (config_len,))
    return config_len // 2 + 1


def _log_of(what, log):
    if not isinstance(log, tuple):
        raise ProtocolError("wire.%s: log must be a tuple, got %r"
                            % (what, type(log).__name__))
    _check_entries(what, log)
    previous = None
    for index, term, _command in log:
        if previous is None:
            if index < 0:
                raise ProtocolError("wire.%s: a log cannot start below 0, "
                                    "got %d" % (what, index))
        elif index != previous + 1:
            raise ProtocolError("wire.%s: a log must be dense, got index "
                                "%d after %d" % (what, index, previous))
        previous = index
    return log


def log_start(log):
    """The index of the log's first entry — 0 unless a snapshot ate the
    prefix."""
    return log[0][0] if log else 0


def _check_config(role, config):
    if not isinstance(config, tuple) or not config:
        raise ProtocolError("wire.%s: config must be a non-empty tuple of "
                            "node ids, got %r" % (role, config))
    for p in config:
        _check_id(role, "config member", p)
    if len(set(config)) != len(config):
        raise ProtocolError("wire.%s: config has a duplicate member: %r"
                            % (role, config))
    return config


def _check_snapshot_at(role, snapshot_at):
    if snapshot_at is None:
        return None
    if (not isinstance(snapshot_at, tuple) or len(snapshot_at) != 2
            or any(isinstance(x, bool) or not isinstance(x, int)
                   for x in snapshot_at)):
        raise ProtocolError("wire.%s: snapshot_at must be None or an "
                            "(index, term) pair, got %r"
                            % (role, snapshot_at))
    return snapshot_at


def _common(state, role, id, term, voted_for, log, commit_index, config,
           elapsed, snapshot_at=None):
    _check_id(role, "id", id)
    state["id"] = id
    state["role"] = role
    state["term"] = _check_int(role, "term", term)
    if voted_for is not None:
        _check_id(role, "voted_for", voted_for)
    state["voted_for"] = voted_for
    state["log"] = _log_of(role, log)
    state["snapshot_at"] = _check_snapshot_at(role, snapshot_at)
    if isinstance(commit_index, bool) or not isinstance(commit_index, int) \
            or commit_index < -1:
        raise ProtocolError("wire.%s: commit_index must be an int >= -1 "
                            "(-1 is nothing committed), got %r"
                            % (role, commit_index))
    state["commit_index"] = commit_index
    start = log_start(state["log"])
    if commit_index < start - 1:
        raise ProtocolError("wire.%s: commit_index %d is below the log's "
                            "start %d — entries the log no longer carries "
                            "are committed by definition"
                            % (role, commit_index, start))
    last_index = state["log"][-1][0] if state["log"] else start - 1
    if commit_index > last_index:
        raise ProtocolError("wire.%s: commit_index %d is past the log's "
                            "last entry %d" % (role, commit_index,
                                               last_index))
    state["config"] = _check_config(role, config)
    state["elapsed"] = _check_int(role, "elapsed", elapsed)
    return state


FOLLOWER_KEYS = ("id", "role", "term", "voted_for", "log", "commit_index",
                 "config", "elapsed", "snapshot_at")
CANDIDATE_KEYS = FOLLOWER_KEYS + ("votes",)
LEADER_KEYS = FOLLOWER_KEYS + ("matched", "next_index", "old_config")


def follower(id, term=0, voted_for=None, log=(), commit_index=-1,
             config=("a1", "a2", "a3", "a4", "a5"), elapsed=0,
             snapshot_at=None):
    """A node that follows: no vote issued for the current term yet."""
    return _common({}, "follower", id, term, voted_for, log, commit_index,
                   config, elapsed, snapshot_at)


def candidate(id, term, voted_for=None, log=(), commit_index=-1,
              config=("a1", "a2", "a3", "a4", "a5"), elapsed=0, votes=(),
              snapshot_at=None):
    """A node running for leader: `voted_for` is its own id once it has
    cast its own vote; `votes` is the tuple of ids that granted this
    term's request."""
    state = _common({}, "candidate", id, term, voted_for, log, commit_index,
                    config, elapsed, snapshot_at)
    if not isinstance(votes, tuple) or any(not isinstance(v, str)
                                           for v in votes):
        raise ProtocolError("wire.candidate: votes must be a tuple of node "
                            "ids, got %r" % (votes,))
    state["votes"] = votes
    return state


def leader(id, term, log=(), commit_index=-1, config=("a1", "a2", "a3",
           "a4", "a5"), matched=None, next_index=None, snapshot_at=None,
           old_config=None, elapsed=0):
    """A node leading: `matched[node]` is the highest index that node's log
    agrees with, `next_index[node]` where the leader will send next."""
    state = _common({}, "leader", id, term, None, log, commit_index,
                    config, elapsed, snapshot_at)
    if matched is None:
        matched = {}
    if next_index is None:
        next_index = {}
    if not isinstance(matched, dict) or not isinstance(next_index, dict):
        raise ProtocolError("wire.leader: matched and next_index must be "
                            "dicts keyed by node id")
    for key, value in matched.items():
        _check_id("leader", "matched key", key)
        if isinstance(value, bool) or not isinstance(value, int) \
                or value < -1:
            raise ProtocolError("wire.leader: matched[%s] must be an int "
                                ">= -1, got %r" % (key, value))
    for key, value in next_index.items():
        _check_id("leader", "next_index key", key)
        if isinstance(value, bool) or not isinstance(value, int) \
                or value < 0:
            raise ProtocolError("wire.leader: next_index[%s] must be a "
                                "non-negative int, got %r" % (key, value))
    state["matched"] = dict(matched)
    state["next_index"] = dict(next_index)
    if old_config is not None:
        _check_config("leader", old_config)
    state["old_config"] = old_config
    return state


def last_of(log):
    """The (index, term) of a raw log tuple's last entry — (-1, 0) empty."""
    _log_of("last_of", log)
    if not log:
        return (-1, 0)
    index, term, _command = log[-1]
    return (index, term)


def last_entry(state):
    """The (index, term) a node's log truly ends at: its last entry, or
    the snapshot boundary when the tail is empty — a snapshotted node is
    not an empty one."""
    log = state["log"]
    if log:
        return (log[-1][0], log[-1][1])
    if state.get("snapshot_at") is not None:
        return state["snapshot_at"]
    return (-1, 0)


def at_least_as_up_to_date(candidate_last, voter_last):
    """Raft's election restriction, exposed once: compare last term, then
    last index, on (index, term) pairs from `last_entry`. True when a
    voter may grant the candidate its vote."""
    c_index, c_term = candidate_last
    v_index, v_term = voter_last
    if c_term != v_term:
        return c_term > v_term
    return c_index >= v_index
