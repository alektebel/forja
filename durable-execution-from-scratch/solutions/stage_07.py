"""stage_07.py — the effect that happens exactly once.

Durable Execution From Scratch — stage 7: The effect that happens exactly once

An effect is the one thing in this course that leaves the run: a write into the
world, under a key. The world does not deduplicate (`work.Effects` counts), so
the only thing standing between "once" and "twice" is the order of three events
and one idempotency key: the intent is **synced before** the effect runs, the
effect is applied under the job's own key — the same key on every attempt — and
the `effect` line is written **after**. A replay that finds an intent without an
effect line cannot know which side of the crash the effect was on, so it asks
the world (`Effects.count(key)`) and either records the line it can prove or
re-applies under the same key.

    EffectError   what an intent, an effect or a settlement this stage refuses
    intent        write AND sync an `intent` line, before anything runs
    apply_effect  apply the effect under the job's key, and write `effect`
    settle        the replay's decision for an intent whose effect is unknown

DESIGN DECISION — why does `intent` carry no tick, and write the line at tick 0?
    Because an intent is not an event on the clock; it is a promise made before
    the attempt. Every line has to carry a tick, and the honest one for a promise
    is `0`: the job has not cost anything yet, and giving the intent a real tick
    would let a reader believe it is a fact about when something happened. The
    `effect` line, written by a function that *was* handed a tick, carries the
    real one — `apply_effect` and `settle` both take `*, tick` for exactly that
    reason — so the two lines a job's effect leaves behind are readable as
    "promised at no tick, landed at tick 6" and never as two events that were
    confused with each other.

DESIGN DECISION — why is the key the job's and not the attempt's?
    Because the attempt is the thing that dies. A key derived from the attempt
    (`fast-1`, `fast-2`) is a *new effect* every time the job is retried, so the
    world applies the same work twice and `Effects.count("effect:fast")` — the
    job's own key, the one every later attempt will look for — still reads `0`.
    Nothing raises, the effect simply happened twice, which is why this stage
    keys everything by `job.key` and why its check applies the same job twice and
    asserts the world holds *one* application, under the key the plan named.

DESIGN DECISION — why does `apply_effect` report `"applied"`, `"already"` and
`"recorded"` instead of raising on the second call?
    Because the second call is not a mistake: it is the crash-recovery path, and
    a caller that has to distinguish "I applied it" from "the world already had
    it" from "the world had it but its line was lost" needs the answer as data.
    `"already"` is the refusal the contract asks for — the key is applied and the
    log proves it (an `effect` line is there), so nothing is applied and nothing
    is written: a second line for the same key is exactly the double-count stage
    9 audits. `"recorded"` is the crash between the effect and its line: the line
    is written and the effect is **not** applied again. `"applied"` is a fresh
    key: apply, then write.

DESIGN DECISION — why does `settle` answer `"applied"` or `"reapply"`, and why
does it write as it decides?
    Because these are the only two things a replay can conclude, and because a
    decision that is not acted on is a decision nobody makes. `settle` takes the
    *lines* a replay produced, so it can see that the job announced an intent and
    that no `effect` line proves it; then it asks the world. If the world has the
    key (`count(key) >= 1`) the effect landed before the crash and the replay
    records the line it can prove — `"applied"`, and the count stays `1`. If the
    world does not have it, the effect never ran and the replay applies it under
    the *same* key — `"reapply"`, and the count becomes `1`. Either way the job
    ends finished with its key applied exactly once, which is the property, and
    it is the check's last assertion.

TODO: implement `EffectError`, `intent`, `apply_effect` and `settle`.
"""

from collections.abc import Mapping

import stage_01
import work
from disk import DEFAULT_JOURNAL

#: The tick an `intent` line carries. Every line carries a tick, and an intent
#: is a promise made before the attempt rather than an event on the clock, so
#: the promise is written at the tick that reads as "nothing has happened yet";
#: the `effect` line carries the tick its caller was handed.
INTENT_TICK = 0


class EffectError(stage_01.DurableError):
    """An intent, an effect or a settlement this stage refuses.

    It derives from the course's base, so one `except DurableError` still
    catches a broken course, and it names the offender: the job, the key, the
    tick or the line — a refusal that says "invalid" is a refusal that makes the
    caller guess which of three keys was the wrong one.
    """


def _require_text(value, what):
    """A job id or a key: a non-empty str, refused by name and by value."""
    if not isinstance(value, str) or not value.strip():
        raise EffectError("%s must be a non-empty str, got %r" % (what, value))
    for char in value:
        if char.isspace():
            raise EffectError(
                "%s must not contain whitespace, got %r: a key is what a later "
                "replay looks a line up by" % (what, value))
    return value


def _require_tick(value, what):
    """A tick: a real int, not negative, and not the flag `True`."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EffectError(
            "%s must be a non-negative int, got %r" % (what, value))
    return value


def _require_job(job):
    """The job an effect belongs to: a `work.Job`, refused by name.

    A job carries its own idempotency key, so a caller that hands this stage a
    job id, a mapping or `None` has handed it something that cannot say which key
    its effect belongs under — the one fact this stage exists to keep.
    """
    if not isinstance(job, work.Job):
        raise EffectError(
            "an effect belongs to a work.Job, got %r" % (job,))
    return job


def _records(disk):
    """The journal's lines, parsed, in order.

    The disk's own path is the journal (`disk.DEFAULT_JOURNAL`), and what is
    read is what the program can see: an intent is believed to be there only when
    it is *synced*, which is the caller's business, and this reader's job is to
    report the lines as they are. A line that is not a line is stage 1's
    `JournalError` naming it, because a reader that skips what it cannot parse is
    a reader that decides on a log it cannot read.
    """
    text = disk.read(DEFAULT_JOURNAL)
    tokens = text.split("\n")
    if tokens and tokens[-1] == "":
        tokens = tokens[:-1]
    return tuple(stage_01.parse_line(token) for token in tokens)


def _effect_line(lines, job):
    """The `effect` line for `job`'s key in `lines`, or `None`.

    Compared field by field on what the line *carries* — the kind, the job and
    the key — never by looking for the key's text inside the journal: an
    `intent job=fast key=effect:fast` line carries that text and is not an
    effect, and a reader that cannot tell them apart has decided the effect
    happened before it did.
    """
    for entry in lines:
        if (entry.get("kind") == "effect" and entry.get("job") == job.id
                and entry.get("key") == job.key):
            return entry
    return None


def _intent_line(lines, job):
    """The `intent` line for `job`'s key in `lines`, or `None`."""
    for entry in lines:
        if (entry.get("kind") == "intent" and entry.get("job") == job.id
                and entry.get("key") == job.key):
            return entry
    return None


def _effect_text(tick, job):
    """The text of the `effect` line a job's effect leaves behind."""
    return stage_01.line(tick, "effect", job=job.id, key=job.key)


def _write_effect(disk, tick, job):
    """Write the `effect` line — after the effect, never before it."""
    text = _effect_text(tick, job)
    stage_01.write_line(disk, {"tick": tick, "kind": "effect", "job": job.id,
                               "key": job.key})
    return text


def intent(disk, job_id, key):
    """Write an `intent` line and sync it, before any effect runs.

    The intent is the one line that must be a fact before the world is touched:
    a replay that finds it knows an effect *may* have landed, and a replay that
    does not find it would apply the effect a second time. So the line is written
    and synced, and then checked — `disk.synced` must carry it — because a caller
    whose disk cannot make it durable has not announced an intent at all and gets
    an `EffectError` naming the job and the key instead of permission to run the
    effect. The return value is the journal's length once the line is durable.
    """
    job_id = _require_text(job_id, "an intent's job id")
    key = _require_text(key, "an intent's key")
    entry = {"tick": INTENT_TICK, "kind": "intent", "job": job_id, "key": key}
    written = stage_01.line(INTENT_TICK, "intent", job=job_id, key=key) + "\n"
    length = stage_01.write_line(disk, entry)
    disk.sync()
    durable = disk.synced(DEFAULT_JOURNAL)
    if not durable.endswith(written):
        raise EffectError(
            "the intent for job %r under key %r is not durable: the journal "
            "holds %r after the sync, not a line ending in %r — an intent that "
            "can be lost is not an intent" % (job_id, key, durable, written))
    return length


def apply_effect(disk, effects, job, *, tick):
    """Apply `job`'s effect under its own key, and write the `effect` line.

    Three things can be true when this is called, and all three are answers
    rather than accidents:

      * `"applied"`  — the world never had this key: the effect is applied now
        (`effects.apply(job.key, job.value, tick=tick)`) and the line is written.
      * `"already"`  — the key is applied *and* the journal's `effect` line
        proves it: nothing is applied and nothing is written, because a second
        line for a key the log already proves is the double count this stage
        exists to prevent.
      * `"recorded"` — the world has the key but the line was lost with the
        process (a crash between the effect and its append): the line is written
        and the effect is not applied again.

    The line is always written *after* the effect, and the key is always the
    job's own, so the same job retried any number of times leaves the world with
    exactly one application under the key the plan named.
    """
    _require_job(job)
    _require_tick(tick, "an effect's tick")
    lines = _records(disk)
    if _effect_line(lines, job) is not None:
        return {"job": job.id, "key": job.key, "value": job.value, "tick": tick,
                "decision": "already", "line": _effect_text(tick, job)}
    if effects.count(job.key) >= 1:
        return {"job": job.id, "key": job.key, "value": job.value, "tick": tick,
                "decision": "recorded", "line": _write_effect(disk, tick, job)}
    effects.apply(job.key, job.value, tick=tick)
    return {"job": job.id, "key": job.key, "value": job.value, "tick": tick,
            "decision": "applied", "line": _write_effect(disk, tick, job)}


def settle(disk, effects, lines, job, *, tick):
    """What a replay decides about an intent whose effect is unknown.

    `lines` is what a replay made of the journal (stage 3's records). `settle`
    looks for the job's `intent` and for an `effect` line for the job's key:

      * no intent and no effect line — there is nothing to settle, and the job is
        refused by name, because a replay that invents an intent is a replay that
        invents the promise the whole stage is built on;
      * the `effect` line is already there — the log proves the effect: nothing
        is written and `"applied"` is answered;
      * an intent and no `effect` — the world is asked. `Effects.count(job.key)`
        at least one means the effect landed before the crash, so the line it can
        prove is written and `"applied"` is answered; zero means it did not, so
        the effect is applied under the *same* key, the line is written, and
        `"reapply"` is answered.

    Every branch that acts leaves the journal with an `effect` line for the key
    and the world with exactly one application of it.
    """
    _require_job(job)
    _require_tick(tick, "a settlement's tick")
    if not isinstance(lines, (tuple, list)):
        raise EffectError(
            "a settlement replays a sequence of lines, got %r" % (lines,))
    for index, entry in enumerate(lines):
        if not isinstance(entry, Mapping):
            raise EffectError(
                "a settlement replays parsed lines, and line %d is %r"
                % (index, entry))
    proven = _effect_line(lines, job)
    if proven is None and _intent_line(lines, job) is None:
        raise EffectError(
            "there is no intent for job %r under key %r to settle: an effect "
            "without an intent is a run that applied something it never "
            "announced" % (job.id, job.key))
    if proven is not None:
        return "applied"
    if effects.count(job.key) >= 1:
        _write_effect(disk, tick, job)
        return "applied"
    effects.apply(job.key, job.value, tick=tick)
    _write_effect(disk, tick, job)
    return "reapply"
