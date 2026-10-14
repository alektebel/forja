"""work.py — the jobs, and the effects they must land exactly once, PROVIDED.

The journal is the run's own account of itself; `Effects` is the *world* the run
acts on. The two are deliberately separate, because the interesting failure is a
log that says one thing and a world that did another — and the only way to see it
is to ask the world.

An effect is applied **under a key**, and applying the same key twice is visible:
`count(key)` becomes `2`, and `log()` keeps both records. There is no dedup here
on purpose. A course about exactly-once cannot catch "applied twice" if the
thing it applies to refuses to record the second time.

    effects = Effects()
    effects.apply("job-1", "wrote 12 bytes", tick=4)
    effects.count("job-1")        # 1
    effects.apply("job-1", "wrote 12 bytes", tick=9)
    effects.count("job-1")        # 2   <- the accident, made visible

A `Job` is immutable and carries its own idempotency key, so an effect's identity
is a property of the *plan* and not of the attempt that applied it: a retry that
takes a fresh key is the bug this course is about, and it has to be visible in
the data rather than hidden in a helper.

    Job       one unit of work: who runs it, what it costs, what it writes
    JOBS      the six the course uses, small enough to hand-compute
    job       one job by id, with a field or two overridden
    worker_for  the scripted `fleet.Worker` a job's label names
    Effects   the world: keyed applications, counted, never deduplicated
    WorkError a job, a label or an effect this module refuses
"""

import types
from dataclasses import dataclass

import fleet

#: What a job costs when it does not say.
DEFAULT_TICKS = 2

#: The fields a job carries, in the order a reader meets them. A field outside
#: this tuple is a typo, and a typo is refused by name.
JOB_KEYS = ("id", "label", "ticks", "key", "value")


class WorkError(ValueError):
    """A job, a label or an effect this module refuses.

    Refusals name the field, the id or the key: a job whose typo quietly became
    a default is a job whose journal describes work nobody asked for.
    """


def _require_text(value, what):
    """A string that says something: an id, a label, a key or a value."""
    if not isinstance(value, str) or not value.strip():
        raise WorkError("%s must be a non-empty str, got %r" % (what, value))
    return value


def _require_ticks(value):
    """A job's cost: a real int, not negative, and not the flag `True`."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WorkError(
            "a job's ticks must be a non-negative int, got %r" % (value,))
    return value


@dataclass(frozen=True)
class Job:
    """One unit of work.

    `label` names the `fleet` script that runs it (see `worker_for`), `ticks` is
    what one attempt costs on the injected clock, and `key` is the idempotency
    key its effect is applied under — the same key on every attempt, which is
    what makes "exactly once" a property the world can witness.
    """

    id: str
    label: str
    ticks: int
    key: str
    value: str


#: The six jobs, written the way a plan file would carry them. Small numbers,
#: short values, and one of each interesting shape: a fast one, a slow one, one
#: whose worker fails twice and then succeeds, one whose worker dies holding the
#: lease, one whose effect writes a long value, and one no worker can finish.
JOBS = types.MappingProxyType({
    "fast": {"id": "fast", "label": "instant", "ticks": 1,
             "key": "effect:fast", "value": "fast done"},
    "slow": {"id": "slow", "label": "sluggish", "ticks": 3,
             "key": "effect:slow", "value": "slow done"},
    "flaky": {"id": "flaky", "label": "flaky", "ticks": 2,
              "key": "effect:flaky", "value": "flaky done"},
    "fragile": {"id": "fragile", "label": "dying", "ticks": 4,
                "key": "effect:fragile", "value": "fragile done"},
    "bulk": {"id": "bulk", "label": "reliable", "ticks": 2,
             "key": "effect:bulk", "value": "x" * 64},
    "hopeless": {"id": "hopeless", "label": "hopeless", "ticks": 1,
                 "key": "effect:hopeless", "value": "never"},
})

#: The worker labels this module can resolve, and the `fleet` script each one
#: builds. `hopeless` is `fleet.always("failed")`: it answers, and the answer is
#: a failure, which is a different thing from a worker that dies.
LABELS = ("instant", "reliable", "sluggish", "flaky", "dying", "crasher",
          "hopeless")


def job(job_id, **overrides):
    """One job by id, with fields overridden — `job("fast")` is the fixture,
    `job("fast", ticks=9)` is the same job costing nine.

    An unknown id, an unknown field and a value the field refuses are all
    refused here, naming the offender: a fixture that silently loses an override
    is the same failure as a typo'd key in a plan.
    """
    if job_id not in JOBS:
        raise WorkError(
            "there is no job %r; the jobs are %s" % (job_id, ", ".join(sorted(JOBS))))
    body = dict(JOBS[job_id])
    for field, value in overrides.items():
        if field not in JOB_KEYS:
            raise WorkError(
                "a job has no field %r; it has %s"
                % (field, ", ".join(JOB_KEYS)))
        body[field] = value
    body["id"] = _require_text(body["id"], "a job's id")
    body["label"] = _require_text(body["label"], "a job's label")
    body["key"] = _require_text(body["key"], "a job's key")
    body["value"] = _require_text(body["value"], "a job's value")
    body["ticks"] = _require_ticks(body["ticks"])
    return Job(**body)


def worker_for(label):
    """The scripted worker a job's `label` names.

    The scripts are `fleet`'s, so a job behaves exactly like a J1 task: `dying`
    answers `died` on its second attempt (the one a lease has to survive),
    `flaky` fails twice and then succeeds, and `hopeless` answers `failed` for
    ever. A label that is not one of these is refused by name.
    """
    if label not in LABELS:
        raise WorkError(
            "there is no worker %r; there are %s" % (label, ", ".join(LABELS)))
    if label == "hopeless":
        return fleet.always("failed")
    if label == "instant":
        return fleet.instant()
    if label == "reliable":
        return fleet.reliable()
    if label == "sluggish":
        return fleet.sluggish()
    if label == "flaky":
        return fleet.flaky()
    if label == "dying":
        return fleet.dying()
    return fleet.crasher()


class Effects:
    """The world outside the run: keyed applications, and no deduplication.

    Every application is recorded as `{"tick", "key", "value"}`; the log is
    append-only and keeps order, so "this key was applied twice" is a fact a
    check reads off `count` and a reader reads off `log`.
    """

    def __init__(self):
        self._log = []

    def apply(self, key, value, *, tick):
        """Apply an effect under `key`, and record it.

        The key is what makes the application *identifiable* across a crash, so
        it is refused when it is blank; the value is what the effect wrote, and
        applying the same key with a different value is allowed and visible.
        """
        _require_text(key, "an effect's key")
        _require_text(value, "an effect's value")
        if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
            raise WorkError(
                "an effect's tick must be a non-negative int, got %r" % (tick,))
        entry = {"tick": tick, "key": key, "value": value}
        self._log.append(entry)
        return dict(entry)

    def count(self, key):
        """How many times `key` has been applied (0 when never)."""
        return sum(1 for entry in self._log if entry["key"] == key)

    def applied(self):
        """Every key applied, in application order, repeats included."""
        return tuple(entry["key"] for entry in self._log)

    def value(self, key):
        """The last value written under `key`, or `None` when never applied."""
        for entry in reversed(self._log):
            if entry["key"] == key:
                return entry["value"]
        return None

    def log(self):
        """Every application, as frozen copies, in order."""
        return tuple(dict(entry) for entry in self._log)

    def keys(self):
        """The distinct keys applied, sorted — the set exactly-once is a claim
        about."""
        return tuple(sorted({entry["key"] for entry in self._log}))

    def __repr__(self):
        return "<Effects %d application(s), %d key(s)>" % (
            len(self._log), len(self.keys()))
