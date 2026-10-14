"""Durable Execution From Scratch — stage 7: The effect that happens exactly once.

An effect is the one thing in this course that leaves the run: a write into the
world, under a key. The world does not deduplicate — `work.Effects` counts, and
applying the same key twice reads `2` — so the only thing between "once" and
"twice" is the order of three events and one idempotency key: the intent is
**synced before** the effect runs, the effect is applied under the job's own key
(the same key on every attempt), and the `effect` line is written **after**. A
replay that finds an intent without an effect line cannot know which side of the
crash the effect was on, so it asks the world (`Effects.count(key)`) and either
records the line it can prove or re-applies under the same key.

    INTENT_TICK   the tick an `intent` line carries, before the attempt begins
    EffectError   what an intent, an effect or a settlement this stage refuses
    intent        write AND sync an `intent` line, before anything runs
    apply_effect  apply the effect under the job's key, and write `effect`
    settle        the replay's decision for an intent whose effect is unknown

DESIGN DECISION — why is the intent synced *before* the effect, and not after?
    Because the only moment at which the effect can be made safe is the moment
    before it runs. An `effect` line written afterwards records what happened; an
    `intent` line synced beforehand is what makes the difference between "the
    effect never ran" and "the effect may have run" *knowable to the process that
    comes after the crash*. Write the intent late, or believe one that was never
    synced, and the replay has no choice but to apply the effect again — which is
    the second application this whole stage exists to refuse.

DESIGN DECISION — why is an effect keyed by the job and not by the attempt?
    Because the attempt is the thing that dies. A key derived from the attempt
    (`fast-1`, `fast-2`) makes every retry a *new effect*: the world applies the
    same work twice and the key every later attempt looks for still reads zero.
    Nothing raises, and the run looks successful — which is why the key lives in
    the plan (`work.Job.key`), why this stage never composes one from a tick or
    an attempt number, and why its check applies the same job twice and asserts a
    single application under the plan's key.

DESIGN DECISION — why does `apply_effect` answer `"applied"`, `"already"` or
`"recorded"` instead of refusing the second call?
    Because a second call is the recovery path, not a mistake, and the caller has
    to know which of the three it is. `"already"` is the refusal the contract
    asks for: the key is applied and the log's `effect` line proves it, so
    nothing is applied and nothing is written — a second line for a proven key is
    the double count stage 9 audits. `"recorded"` is the crash between the effect
    and its line: write the line, do not touch the world. `"applied"` is a key
    the world has never seen.

DESIGN DECISION — why does `settle` answer `"applied"` or `"reapply"`, and why
does it act while it decides?
    Because those are the only two things a replay can conclude about an intent
    whose effect is unknown, and a decision nobody acts on is a decision nobody
    makes. If `Effects.count(key)` is at least one, the effect landed before the
    crash and the replay writes the line it can prove — `"applied"`, the count
    staying `1`. If it is zero, the effect never ran, so the replay applies it
    under the *same* key — `"reapply"`, the count becoming `1`. Either way the
    job ends with its key applied exactly once, which is the property a check can
    assert instead of promising.

DESIGN DECISION — why does `apply_effect` read the journal field by field
instead of looking for the key's text in it?
    Because an `intent job=fast key=effect:fast` line carries that text and is
    not an effect. A reader that searches the journal for the key decides the
    effect happened before it did, answers `"already"`, and writes no line: the
    world has the effect, the log never says so, and the next replay applies it
    again. So the journal is parsed (`stage_01.parse_line`) and the comparison is
    on the fields the line carries — its kind, its job and its key.

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
    tick or the line — a refusal that says "invalid" makes the caller guess which
    of three keys was the wrong one.
    """


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
    raise NotImplementedError("stage 7: implement intent()")


def apply_effect(disk, effects, job, *, tick):
    """Apply `job`'s effect under its own key, and write the `effect` line.

    Three things can be true when this is called, and all three are answers
    rather than accidents: `"applied"` (the world never had this key — apply it
    and write the line), `"already"` (the key is applied and the journal's
    `effect` line proves it — apply nothing, write nothing) and `"recorded"`
    (the world has the key but its line was lost with the process — write the
    line and do not apply again). The line is always written *after* the effect,
    and the key is always the job's own.
    """
    raise NotImplementedError("stage 7: implement apply_effect()")


def settle(disk, effects, lines, job, *, tick):
    """What a replay decides about an intent whose effect is unknown.

    `lines` is what a replay made of the journal. With an `effect` line already
    there the log proves the effect and the answer is `"applied"`; with an intent
    and no `effect` line the world is asked: `Effects.count(job.key)` at least
    one means the effect landed before the crash and the line it can prove is
    written (`"applied"`), zero means it never ran and it is applied under the
    *same* key (`"reapply"`). An intent the log never announced is refused by
    name — a replay that invents one invents the promise this stage is built on.
    """
    raise NotImplementedError("stage 7: implement settle()")
