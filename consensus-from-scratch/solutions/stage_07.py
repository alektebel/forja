"""Consensus From Scratch — stage 7: The disk that lied: persist and
recover.

`persist` turns a node's whole durable truth — term, voted_for, commit
window, config, snapshot boundary, log — into bytes; `recover` reads them
back. The fabric write-throughs every state transition to the node's disk
and, when a `("crash", tick, node)` event fires, TEARS the last record:
whatever was in the middle of landing is gone. A restarted node comes up
from `recover` of the surviving bytes — or blank, if the protocol never
learned to persist — and `heal_from_leader` is what makes a torn node
rejoin without losing a committed entry.

DESIGN DECISION — why persist `term` and `voted_for` at all, when the log
survives?
Because losing the term loses the one-vote-per-term law across a restart:
a node that comes back at term 0 will happily grant two votes in the term
it already voted in, and the election that depends on the overlap of two
majorities stops being safe. The two fields plus the log are the minimum
durable set; the commit window and config ride along because `wire`'s
builders refuse a state without them, and a recover that cannot rebuild
a legal state is a recover that restarts a corpse.

DESIGN DECISION — why is the encoding a versioned, newline-delimited text
image rather than pickle or a struct?
Because the check must read the bytes to prove what survived the tear,
and pickle is opaque and struct needs a width table. `v1` in the first
line means a future stage can refuse an old image with a naming error
instead of misreading it; every field is one line, the log's entries are
`index;term;command` lines, and `-` marks an absent optional (no vote, no
snapshot boundary). `recover` of anything malformed raises
`wire.ProtocolError` naming the line — a torn head is a blank node, not a
half-understood one.

DESIGN DECISION — why does `heal_from_leader` reuse stage 4's prev check
instead of "just re-sync from 0"?
Because the leader's `next_index` walk IS the resync, and a node that
throws its log away on restart would answer `matched = -1` and force the
leader to resend a replicated history it already holds. The torn record
means the last entry may be missing — but everything before it is real,
so the healed follower keeps its prefix, accepts the leader's tail from
the first agreeing (index, term), and the committed entries the leader
holds at or below its `leader_commit` are, by the safety theorem, in that
prefix: the tear can lose an UNCOMMITTED entry (correct) and never a
committed one (the check pins both directions).
"""

import wire

import stage_04


def _line(lines, position):
    if position >= len(lines):
        raise wire.ProtocolError("stage_07.recover: line %d: missing"
                                 % (position,))
    return lines[position]


def _int_at(lines, position, what, allow_negative=False):
    text = _line(lines, position)
    try:
        value = int(text)
    except ValueError:
        raise wire.ProtocolError("stage_07.recover: line %d: %s is not an "
                                 "int: %r" % (position, what, text))
    if value < 0 and not (allow_negative and value == -1):
        raise wire.ProtocolError("stage_07.recover: line %d: %s is "
                                 "negative: %r" % (position, what, text))
    return value


def persist(state):
    """The node's durable truth as bytes: a `v1` image the check can read
    line by line. Deterministic: the same state, the same bytes."""
    # Rebuild through the follower builder first: whatever cannot be
    # rebuilt as a legal durable state must never reach a disk.
    try:
        durable = wire.follower(state["id"], term=state["term"],
                                voted_for=state["voted_for"],
                                log=state["log"],
                                commit_index=state["commit_index"],
                                config=state["config"],
                                snapshot_at=state["snapshot_at"])
    except wire.ProtocolError as problem:
        raise wire.ProtocolError("stage_07.persist: this state is not "
                                 "durable truth: %s" % (problem,))
    snap = durable["snapshot_at"]
    parts = ["v1", durable["id"], str(durable["term"]),
             durable["voted_for"] if durable["voted_for"] else "-",
             str(durable["commit_index"]),
             ",".join(durable["config"]),
             "-" if snap is None else "%d:%d" % (snap[0], snap[1])]
    for index, term, command in durable["log"]:
        parts.append("%d;%d;%s" % (index, term, command))
    return "\n".join(parts).encode("utf-8")


def recover(saved):
    """Bytes back to a state, via `wire`'s builders; malformed input
    raises ProtocolError naming the offender."""
    if not isinstance(saved, bytes):
        raise wire.ProtocolError("stage_07.recover: an image must be bytes, "
                                 "got %r" % (type(saved).__name__,))
    try:
        text = saved.decode("utf-8")
    except UnicodeDecodeError:
        raise wire.ProtocolError("stage_07.recover: line 0: not a utf-8 "
                                 "image")
    lines = text.split("\n")
    if _line(lines, 0) != "v1":
        raise wire.ProtocolError("stage_07.recover: line 0: not a v1 image: "
                                 "%r" % (_line(lines, 0),))
    node_id = _line(lines, 1)
    if not node_id:
        raise wire.ProtocolError("stage_07.recover: line 1: empty node id")
    term = _int_at(lines, 2, "term")
    voted_raw = _line(lines, 3)
    voted_for = None if voted_raw == "-" else voted_raw
    if voted_for is not None and not voted_for:
        raise wire.ProtocolError("stage_07.recover: line 3: an empty vote "
                                 "is neither '-' nor a node id")
    commit_index = _int_at(lines, 4, "commit index", allow_negative=True)
    config_line = _line(lines, 5)
    config = tuple(config_line.split(","))
    if not config_line or "" in config:
        raise wire.ProtocolError("stage_07.recover: line 5: empty config "
                                 "member: %r" % (config_line,))
    snap_raw = _line(lines, 6)
    if snap_raw == "-":
        snapshot_at = None
    else:
        pair = snap_raw.split(":")
        if len(pair) != 2:
            raise wire.ProtocolError("stage_07.recover: line 6: a snapshot "
                                     "boundary wants index:term: %r"
                                     % (snap_raw,))
        snapshot_at = (_int_at(pair, 0, "boundary index"),
                       _int_at(pair, 1, "boundary term"))
    log = []
    for position in range(7, len(lines)):
        part = _line(lines, position)
        fields = part.split(";", 2)
        if len(fields) != 3:
            raise wire.ProtocolError("stage_07.recover: line %d: an entry "
                                     "wants index;term;command: %r"
                                     % (position, part))
        log.append((_int_at(fields, 0, "entry index"),
                    _int_at(fields, 1, "entry term"),
                    fields[2]))
    try:
        return wire.follower(node_id, term=term, voted_for=voted_for,
                             log=tuple(log), commit_index=commit_index,
                             config=config, snapshot_at=snapshot_at)
    except wire.ProtocolError as problem:
        raise wire.ProtocolError("stage_07.recover: the image does not "
                                 "build a legal state: %s" % (problem,))


def heal_from_leader(state, msg):
    """A restarted node answering the leader's APPEND: keep the surviving
    prefix, accept the tail, answer at the boundary: (reply, state2)."""
    # The restart costs a node its role, its timers and — through the
    # tear — at most the last entry. Everything the disk kept is real;
    # stage 4's prev check IS the resync: it keeps this node's prefix,
    # installs the leader's tail past the agreeing pair, and answers
    # with the boundary so the leader's next_index walk stops here.
    return stage_04.handle_append(state, msg)
