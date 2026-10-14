"""stage_08.py — the resume, and the log that is not this run's.

Durable Execution From Scratch — stage 8: The resume, and the log that is not this run's

A run is not the process that started it; it is the log on disk. This stage adds
the two things a log needs before a second process may pick up a first one's
work: a **checkpoint** — what the run had already folded, written whole and
synced before it is believed — and a `repair`, the one function in the course
that edits a log, for the half-written tail a kill leaves behind. And it adds the
refusal that makes a resume safe at all: a resume is allowed only over a
checkpoint that is *this* run's and *this* plan's, because a resume over somebody
else's log is a second run wearing the first one's name (contract §0).

    DEFAULT_CHECKPOINT  the checkpoint's path: the world's journal, plus a suffix
    ResumeError         what a resume refuses, and what a broken checkpoint raises
    checkpoint          write this run's states whole, synced, and return the length
    read_checkpoint     the checkpoint on disk, or None when there is none
    repair              drop a torn tail from a log, and return what was kept and lost
    resume              the checkpoint's states, the lines after it, and whose they are

DESIGN DECISION — why is the checkpoint a file of its own, and not a rewrite of the journal?
    Because the journal is evidence and a checkpoint is a summary, and a summary
    that eats its source cannot be checked against it. A resume replays the lines
    after the checkpoint, so the lines the checkpoint folded have to still be
    there: `repair` has to know what a torn tail was appended to, stage 9 counts
    the run's lines and compares them with the world, and stage 6 recovers a dead
    lease from the `claim` line the owner wrote — none of which survives a
    checkpoint that overwrites the journal. So the checkpoint is written *beside*
    the journal with `disk.replace` (a whole-file rewrite, never an append, so a
    crash leaves the old checkpoint or the new one and never a mixture), and the
    journal stays the append-only tail that follows it.

DESIGN DECISION — why is the checkpoint's path the journal's path plus a suffix?
    Because the two are one thing. The world owns the journal's path
    (`disk.DEFAULT_JOURNAL`) and a path a stage invented would be a path the next
    process cannot find; deriving the checkpoint's from the journal's means a
    journal that moves takes its checkpoint with it. A checkpoint without its
    journal is a summary of nothing — its states are only worth as much as the
    lines they were folded from.

DESIGN DECISION — why does `resume` replay only the lines after the checkpoint's tick?
    Because the checkpoint's states already fold every line at or before `now`,
    and this course's clock is what makes "after" a fact instead of a guess: ticks
    never go backwards, a line carries the tick it was written at, and a
    checkpoint is written at the end of a tick. Re-folding what was already folded
    is not harmless: an `intent` folded there would be reconciled a second time,
    and "the effect happened exactly once" is the one property this course will
    not let a resume soften.

DESIGN DECISION — why does a resume only believe what `disk.synced` holds, and write a checkpoint only when there is none?
    The first is contract §3.3's rule: a process that came after a crash may only
    believe what a crash would keep, so a line written and not synced did not
    happen — and neither did a checkpoint written and not synced. The second is
    the difference between resuming and starting: a run that finds no checkpoint
    is starting, and writes one (`resumed` is False, because *this* run wrote its
    own checkpoint); a run that finds one reuses it and writes nothing, because a
    resume that rewrote the checkpoint on every call would turn a read into a
    write and a summary into a second source of truth.

DESIGN DECISION — why does `resume` reconcile the replayed intents and apply nothing?
    Because a replay's job is to make the *log* true, not to do work. An effect
    that landed before the crash has an application in the world and no `effect`
    line in the log, so the run that comes after would apply it a second time;
    writing the line it can prove is what stops that. An intent the world never
    saw is left alone: the run re-applies it under the same key when it runs the
    job, which is a run's business and not a resume's. `effects` is a parameter
    for exactly this — the world is the only witness to what landed.

DESIGN DECISION — why is `repair` a text operation that keeps every complete line?
    Because a repair must not decide what a line means: it drops the fragment
    after the last terminator and nothing else, so a half-written line costs
    exactly itself. A repair that parsed the log would refuse to fix a log it
    cannot parse, and a repair that dropped the last *complete* line to be safe
    would throw away a decision the run really made — the mistake this stage
    names. It writes only when something was dropped, and it writes the kept
    prefix whole with `replace` and syncs it, because a repair a crash undoes is
    not a repair.
"""

from collections.abc import Mapping

import stage_01 as s1
from disk import DEFAULT_JOURNAL
from stage_01 import DurableError

#: The checkpoint's path: the world's journal path plus a suffix, because a
#: checkpoint and the journal it summarizes are one thing, and a reader that
#: finds one has to be able to find the other.
DEFAULT_CHECKPOINT = DEFAULT_JOURNAL + ".checkpoint"

#: The six statuses a state table may say (contract §3.2). A status outside them
#: is a state nobody can read back, so it is refused by name — with the real name
#: suggested when a typo is one or two edits from it.
_STATES = ("pending", "running", "expired", "done", "failed", "skipped")

#: What a `result` line's status means for a job's state. `ok` finished it and
#: `failed` spent it; `died` is not an attempt that ended — the worker is gone, so
#: the slot it held comes back (contract §2.1, stage 5).
_RESULT_STATES = {"ok": "done", "failed": "failed", "died": "expired"}

#: The statuses whose state record may carry the worker's own detail (contract
#: §3.2): a `done` or a `failed` state is the one a reader wants the text of.
_DETAILED = ("done", "failed")

#: Stage 5's `MAX_MISSES`: a lease is dead `MAX_MISSES` ticks after its deadline.
#: That grace is what a resume gives an owner that stopped answering, and it is
#: the reason a lease that expired *now* is still running.
_GRACE = 2

#: The checkpoint's own line: a tick, this marker — a kind the journal's nine do
#: not have, so a reader that knows only the journal refuses a checkpoint instead
#: of folding it — and the three fields a checkpoint carries.
_MARKER = "checkpoint"
_FIELDS = ("run", "plan", "states")

#: The characters the states table's encoding spends on structure, and the reason
#: a job id or a detail that contains one is refused: a separator a value could
#: contain is not a separator.
_SEPARATORS = (",", "=", ":")

#: How far a typo may be from a real name and still earn a suggestion.
_NEAR = 2


class ResumeError(DurableError):
    """A checkpoint, a log or a resume this stage refuses.

    The refusal always names the offender — the run, the plan, the line, the
    field, the state — and, when the offender is a typo of a real name, the real
    name too: `run`/`plan`/`states` and the six statuses are exactly where a typo
    silently becomes a default.
    """


def _edits(one, other):
    """The Levenshtein distance between two strings, as an int."""
    previous = list(range(len(other) + 1))
    for i, left in enumerate(one, 1):
        current = [i]
        for j, right in enumerate(other, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def _near(name, known):
    """The known name within `_NEAR` edits of `name`, or `None`."""
    if not isinstance(name, str) or name in known:
        return None
    best = None
    for candidate in known:
        if abs(len(candidate) - len(name)) > _NEAR:
            continue
        distance = _edits(name, candidate)
        if distance <= _NEAR and (best is None or distance < best[1]
                                  or (distance == best[1] and candidate < best[0])):
            best = (candidate, distance)
    return None if best is None else best[0]


def _maybe(name, known):
    """`; did you mean 'x'?` for a typo, and nothing when there is no candidate."""
    guessed = _near(name, known)
    return "" if guessed is None else "; did you mean %r?" % (guessed,)


def _tick(value, what):
    """A tick a checkpoint or a resume may carry: a real int, not negative, and
    not the flag `True`."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResumeError(
            "%s must be a non-negative int, got %r" % (what, value))
    return value


def _text(value, what):
    """A field's value: a non-empty str with no whitespace in it.

    Whitespace separates a checkpoint's fields, so a value that contained it
    could not be read back — and a checkpoint that cannot be read back is a
    resume that guesses.
    """
    if not isinstance(value, str) or not value.strip():
        raise ResumeError("%s must be a non-empty str, got %r" % (what, value))
    for char in value:
        if char.isspace():
            raise ResumeError(
                "%s must not contain whitespace, got %r: whitespace separates a "
                "checkpoint's fields" % (what, value))
    return value


def _token(value, what):
    """A value the states table's encoding can spell: a field's value, and none
    of the three characters the encoding spends on structure."""
    value = _text(value, what)
    for char in _SEPARATORS:
        if char in value:
            raise ResumeError(
                "%s must not contain %r, got %r: the separator is structure, and "
                "a value that contained it could not be read back"
                % (what, char, value))
    return value


def _status(value, what):
    """A state table's status: one of the six, or a refusal naming it."""
    if value not in _STATES:
        raise ResumeError(
            "a state's status must be one of %s, got %r%s"
            % (", ".join(_STATES), value, _maybe(value, _STATES)))
    return value


def _state(value, job):
    """A state record, as the pair `(status, text or None)` it spells.

    A state is a status (`"done"`) or a record carrying `status` and, when the
    deciding result line carried one, the worker's own `text`. A record with no
    `text` is the status string it says — the log has one way to say "done with
    no detail" — and a record with a field outside the two is refused by name,
    because a state nobody can read back is a state the next process invents.
    """
    what = "the state of the job %r" % (job,)
    if isinstance(value, Mapping):
        for name in value:
            if name not in ("status", "text"):
                raise ResumeError(
                    "%s carries %r; a state record carries 'status' and "
                    "'text'%s" % (what, name, _maybe(name, ("status", "text"))))
        if "status" not in value:
            raise ResumeError("%s has no 'status'; a state record carries one" % (what,))
        status = _status(value["status"], what)
        if "text" not in value:
            return status, None
        return status, _token(value["text"], "%s's text" % (what,))
    if isinstance(value, str):
        return _status(value, what), None
    raise ResumeError(
        "%s is %r: a state is one of %s, or a record carrying 'status' and 'text'"
        % (what, value, ", ".join(_STATES)))


def _encode(states):
    """The states table as the one whitespace-free token a checkpoint carries.

    One entry per job, id-sorted, each `<job>=<status>` or `<job>=<status>:<text>`,
    separated by commas: deterministic, hand-readable, and injective, because a
    job id, a status and a detail may not contain the three characters that spell
    the structure.
    """
    if not isinstance(states, Mapping):
        raise ResumeError("a checkpoint's states must be a mapping, got %r" % (states,))
    records = {}
    for job in states:
        records[_token(job, "a state's job id")] = _state(states[job], job)
    parts = []
    for job in sorted(records):
        status, text = records[job]
        parts.append("%s=%s" % (job, status if text is None else "%s:%s" % (status, text)))
    return ",".join(parts)


def _decode(token):
    """The states table a checkpoint's token spells, refused by name when it does
    not spell one."""
    table = {}
    if not token:
        return table
    for item in token.split(","):
        if "=" not in item:
            raise ResumeError(
                "a checkpoint's state %r is not job=status; a state entry is "
                "`<job>=<status>` with the detail, when there is one, after ':'"
                % (item,))
        job, _, rest = item.partition("=")
        job = _token(job, "a checkpoint's job id")
        if job in table:
            raise ResumeError("a checkpoint names the job %r twice" % (job,))
        status, colon, text = rest.partition(":")
        what = "a checkpoint's state for the job %r" % (job,)
        status = _status(status, what)
        table[job] = status if not colon else {"status": status,
                                               "text": _token(text, "%s's text" % (what,))}
    return table


def _line(run_id, plan_hash, states, now):
    """The checkpoint's text: one line, terminated, carrying the four facts a
    resume is allowed to act on."""
    return "%d %s run=%s plan=%s states=%s\n" % (
        now, _MARKER, run_id, plan_hash, _encode(states))


def checkpoint(disk, run_id, plan_hash, *, states, now):
    """Write this run's checkpoint whole, sync it, and return its length.

    A checkpoint is a *whole-file rewrite* (`disk.replace`) of
    `DEFAULT_CHECKPOINT`, never an append: after it the file reads the new
    checkpoint, and after a crash without the sync it reads the old one — never a
    mixture, because a half-written checkpoint is the failure this stage exists to
    refuse. It carries the run, the plan, the tick it was taken at and the states
    the run had folded by then; a blank run or plan, a tick that is not a
    non-negative int, a states table that is not a mapping and a state that is not
    one of the six are all refused here, naming the offender and writing nothing.
    """
    now = _tick(now, "a checkpoint's tick")
    run_id = _text(run_id, "a checkpoint's run id")
    plan_hash = _text(plan_hash, "a checkpoint's plan hash")
    text = _line(run_id, plan_hash, states, now)
    length = disk.replace(DEFAULT_CHECKPOINT, text)
    disk.sync()
    return length


def _parse_checkpoint(text):
    """The checkpoint a line spells, or a refusal naming the line and the field."""
    tokens = text.split()
    if len(tokens) < 2 or tokens[1] != _MARKER:
        raise ResumeError(
            "there is no checkpoint in %r: a checkpoint is "
            "`<tick> checkpoint run=<run> plan=<plan> states=<states>`" % (text,))
    if not tokens[0].isdigit():
        raise ResumeError(
            "a checkpoint's tick must be a non-negative int, got %r in %r"
            % (tokens[0], text))
    entry = {"now": int(tokens[0])}
    for token in tokens[2:]:
        if "=" not in token:
            raise ResumeError(
                "a checkpoint's field must be name=value, got %r in %r"
                % (token, text))
        name, value = token.split("=", 1)
        if name not in _FIELDS:
            raise ResumeError(
                "a checkpoint has no field %r in %r%s"
                % (name, text, _maybe(name, _FIELDS)))
        if name in entry:
            raise ResumeError("a checkpoint has %r twice, in %r" % (name, text))
        entry[name] = value
    for name in _FIELDS:
        if name not in entry:
            raise ResumeError(
                "a checkpoint needs %r, in %r; it carries %s"
                % (name, text, ", ".join(_FIELDS)))
    return {"run": _text(entry["run"], "a checkpoint's run id"),
            "plan": _text(entry["plan"], "a checkpoint's plan hash"),
            "now": entry["now"],
            "states": _decode(entry["states"])}


def read_checkpoint(disk):
    """The checkpoint on disk, or `None` when there is none.

    What is read is `disk.synced` and not `disk.read`: a checkpoint a crash would
    take away is not a checkpoint, and a process that came after a crash may only
    believe what a crash would keep (contract §3.3). An empty file is no
    checkpoint; a file that is not a checkpoint is refused, naming it, because
    somebody wrote it by hand and guessing is worse than refusing.
    """
    text = disk.synced(DEFAULT_CHECKPOINT)
    if not text.strip():
        return None
    parts = [one for one in text.split("\n") if one.strip()]
    if len(parts) != 1:
        raise ResumeError(
            "the checkpoint at %r holds %d lines, and a checkpoint is one line: "
            "a file that is not a checkpoint is not a resume's business"
            % (DEFAULT_CHECKPOINT, len(parts)))
    return _parse_checkpoint(parts[0])


def repair(disk, *, path=DEFAULT_JOURNAL):
    """Drop a torn tail from the log at `path`, and return what was kept and lost.

    `kept` is the complete lines the log still holds, in order and without their
    terminators; `dropped` is the fragment that never got one, and it is `""` when
    there was nothing torn. The one function in the course that edits a log, and
    it edits the least it can: every complete line is kept, however torn the tail
    after it is — a repair that dropped a whole line to fix a half one would
    throw away a decision the run really made. The kept prefix is written whole
    (`disk.replace`) and synced, and only when something was dropped: a repair
    with nothing to drop has no business writing.
    """
    text = disk.synced(path)
    cut = text.rfind("\n") + 1
    kept_text, dropped = text[:cut], text[cut:]
    if dropped:
        disk.replace(path, kept_text)
        disk.sync()
    return (tuple(kept_text.split("\n"))[:-1] if kept_text else ()), dropped


def _tail(disk, cp):
    """The lines a resume is allowed to replay: the journal's, and only the ones
    after the checkpoint's tick.

    Read from `disk.synced` for the same reason a checkpoint is: a line a crash
    would take away did not happen. A journal that ends in a fragment refuses
    (stage 6's rule — a recovery that guesses is the failure mode) and names the
    fragment, so the caller can `repair` it; a checkpoint's own `states` are the
    table the resume starts from, so what is folded again is only what came after.
    """
    text = disk.synced(DEFAULT_JOURNAL)
    if text and not text.endswith("\n"):
        raise ResumeError(
            "the journal ends in the half-written line %r: a resume cannot guess "
            "what it meant, and repair() drops it" % (text[text.rfind("\n") + 1:],))
    lines = []
    for one in text.split("\n"):
        if not one:
            continue
        entry = s1.parse_line(one)
        if cp is not None and entry["tick"] <= cp["now"]:
            continue
        lines.append(entry)
    return lines


def _claim(cp, run_id, plan_hash):
    """Refuse a checkpoint that is not this run's or this plan's, by name."""
    if cp["run"] != run_id:
        raise ResumeError(
            "the checkpoint belongs to the run %r and this resume is the run %r: "
            "a resume over somebody else's log is a second run wearing the first "
            "one's name" % (cp["run"], run_id))
    if cp["plan"] != plan_hash:
        raise ResumeError(
            "the checkpoint was taken against the plan %r and this resume is the "
            "plan %r: a log is only reusable by the run that would have written it"
            % (cp["plan"], plan_hash))


def _own(lines, run_id, plan_hash):
    """Refuse a log that names another run or another plan, by name.

    With no checkpoint on disk there is nothing else that says whose log this is,
    and the log's own `start` line does say (stage 1: the run in `key`, the plan
    in `text`). Folding another run's lines into this run's checkpoint is the same
    mistake the checkpoint's refusal exists for, one step earlier.
    """
    for entry in lines:
        if entry["kind"] != "start":
            continue
        if entry["key"] != run_id:
            raise ResumeError(
                "the log's start names the run %r and this resume is the run %r: a "
                "resume over somebody else's log is a second run wearing the first "
                "one's name" % (entry["key"], run_id))
        if entry["text"] != plan_hash:
            raise ResumeError(
                "the log's start names the plan %r and this resume is the plan %r"
                % (entry["text"], plan_hash))


def _inherited(states):
    """A checkpoint's table as a resume may believe it: its `running` jobs are
    expired.

    A checkpoint does not carry a deadline, so a lease it remembers cannot be
    honoured here — and a lease a checkpoint remembers belongs to the process that
    wrote it, which is not this one (a resume is what a process does after the one
    that wrote the checkpoint is gone). A job held by nobody has to come back, and
    the alternative is a run waiting for ever for an owner that no longer exists.
    """
    table = {}
    for job in states:
        state = states[job]
        status = state["status"] if isinstance(state, Mapping) else state
        table[job] = "expired" if status == "running" else state
    return table


def _fold(table, lines, *, now):
    """The states a table and a run of lines add up to, id-sorted.

    One pass over the lines in order — the newest decision wins — and then the
    recovery rule over the leases that are still standing (stage 6's, which is
    stage 5's): a job whose newest claim or beat was never answered by a result is
    `running` while its lease is alive and `expired` once its deadline is
    `_GRACE` ticks behind `now`.
    """
    record = dict(table)
    lease = {}
    for entry in lines:
        job = entry.get("job")
        if job is None:                      # a `start` or a `done`: no job
            continue
        kind = entry["kind"]
        if kind in ("claim", "beat"):
            lease[job] = {"owner": entry["owner"], "deadline": entry["ticks"]}
            record[job] = "running"
        elif kind == "result":
            status = _RESULT_STATES[entry["status"]]
            text = entry.get("text")
            record[job] = ({"status": status, "text": text}
                           if text and status in _DETAILED else status)
            lease.pop(job, None)
        elif kind == "expire":
            if lease.get(job, {}).get("owner") == entry["owner"]:
                record[job] = "expired"
                lease.pop(job, None)
        elif kind == "retry":
            record[job] = "pending"
            lease.pop(job, None)
        else:                                # an `intent` or an `effect`
            record.setdefault(job, "pending")
    for job in lease:
        if now >= lease[job]["deadline"] + _GRACE:
            record[job] = "expired"
        else:
            record[job] = "running"
    return {job: record[job] for job in sorted(record)}


def _record(disk, effects, lines, now):
    """Write the `effect` line for every replayed intent whose application the
    world can prove, and nothing for the ones it cannot.

    A replay's job is to make the log true: an effect that landed before the crash
    but left no line would be applied again by the run that comes after. Nothing
    is applied here — an intent the world never saw is the run's to re-apply under
    the same key — and nothing is written for a key the replay already recorded.
    The lines are written with stage 1's `write_line` and synced once, because a
    fact written per line and synced per line is the pathological answer stage 2
    names.
    """
    landed = {entry["key"] for entry in lines if entry["kind"] == "effect"}
    proven = []
    for entry in lines:
        if entry["kind"] != "intent":
            continue
        key = entry["key"]
        if key in landed:
            continue
        landed.add(key)
        if effects.count(key) >= 1:
            proven.append((entry["job"], key))
    if not proven:
        return ()
    for job, key in proven:
        s1.write_line(disk, {"tick": now, "kind": "effect", "job": job, "key": key})
    disk.sync()
    return tuple(proven)


def resume(disk, effects, *, now, run_id, plan_hash):
    """Pick this run up from its checkpoint, or start it.

    Returns `{"states", "resumed", "reused", "replayed", "checkpoint"}`.

    * `states` is the table a process that just woke up must believe: the
      checkpoint's own states (its `running` jobs expired, because a lease a
      checkpoint remembers is not this process's), then the lines after the
      checkpoint folded in order, then stage 6's recovery for the leases still
      standing (`_GRACE` ticks past their deadline).
    * `resumed` is False when there was no checkpoint and this call wrote one —
      this run wrote its own checkpoint, so nothing was resumed — and True when a
      checkpoint was found and reused.
    * `reused` counts the *jobs* the checkpoint already had and `replayed` the
      jobs the replayed lines name: both counts of jobs, both hand-computable.
    * `checkpoint` is the checkpoint in force when the call returned: the one read,
      or the one this call wrote.

    A checkpoint that names another run or another plan refuses by name, a journal
    that names another run refuses by name, and a torn tail refuses naming the
    fragment; the replayed intents the world can prove get their `effect` line.
    """
    now = _tick(now, "a resume's tick")
    run_id = _text(run_id, "a resume's run id")
    plan_hash = _text(plan_hash, "a resume's plan hash")
    if not callable(getattr(effects, "count", None)):
        raise ResumeError(
            "a resume needs the world's effects to check a replayed intent "
            "against, and %r has no count()" % (effects,))
    cp = read_checkpoint(disk)
    lines = _tail(disk, cp)
    if cp is None:
        _own(lines, run_id, plan_hash)
        states = _fold({}, lines, now=now)
        checkpoint(disk, run_id, plan_hash, states=states, now=now)
        cp = read_checkpoint(disk)
        resumed, reused = False, 0
    else:
        _claim(cp, run_id, plan_hash)
        states = _fold(_inherited(cp["states"]), lines, now=now)
        resumed, reused = True, len(cp["states"])
    _record(disk, effects, lines, now)
    return {"states": states, "resumed": resumed, "reused": reused,
            "replayed": len({one["job"] for one in lines if "job" in one}),
            "checkpoint": cp}
