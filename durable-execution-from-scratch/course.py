"""Durable Execution From Scratch — course manifest.

Ten graded stages between a run that is the process that started it and a run
that is the log on disk. The world is provided: `fleet.py` is J1's, verbatim (the
injected clock, the immutable task and pool specs, the scripted workers), `disk.py`
is the disk with one rule — a write is not durable until it is synced, and
`crash()` discards exactly what was not — and `work.py` is the jobs and the
`Effects` side channel where applying a key twice is *visible*.

The thesis of the whole course is one sentence, and every stage's check asserts
it: A RUN IS NOT THE PROCESS THAT STARTED IT; IT IS THE LOG ON DISK. Every stage
is one decision about that log — what a line is and what a broken one must
refuse, why a write that was not synced did not happen, how a replay turns lines
into state, what a lease is when the owner is dead, when a heartbeat is a steal,
what a crash costs and what the process after it may believe, how an effect
happens exactly once when it may have landed before the crash, whether a resume
is allowed to touch this log at all, and which of the run's numbers the log is
the only source of. The failures worth preventing are the ones that look like
success: a program that believes a write it never synced, a lease held by a
process that no longer exists, a replayed intent that applies the effect a second
time, a resume over somebody else's log, and a report whose numbers came from the
run's memory instead of its disk.

Standard library only, offline, deterministic, **every number an int** (ticks,
bytes, counts): no `time`, no `threading`, no `asyncio`, no subprocesses, no
unseeded randomness, no module-level mutable state. Nothing here reads the real
filesystem or a real clock — the disk is an object, the clock is injected, and a
kill is a `crash()` the caller performs, so a crash is reproducible and a check
can assert the lost bytes instead of trusting them.

    python3 codecraft/cli.py run durable-execution-from-scratch
"""

from codecraft.api import stage

TITLE = "Durable Execution From Scratch"
DESCRIPTION = ("A run that survives its own process: a journal of lines that refuses "
               "a field its kind does not carry, a sync barrier that makes a write "
               "durable and a crash that discards exactly what was not, a replay "
               "that turns lines into state and names a torn tail, a lease with an "
               "owner and a deadline read from the log rather than kept in memory, "
               "heartbeats that renew and never steal, recovery after a crash that "
               "believes only what was synced, effects that happen exactly once "
               "because the intent is synced before them, a resume that refuses a "
               "log that is not its run's, a report whose every number is "
               "recomputed from the lines, and two workers where one is killed "
               "holding the lease.")
LEVEL = "advanced"
ORDER = 22

# --- the checks. Each one is self-contained: its fixtures are nested
# inside it because `course.py` is one namespace for ten stages.

import json
import os
import shutil
import sys
import tempfile


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate,
                                              "durable-execution-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    from collections.abc import Mapping

    import disk as world
    import stage_01 as s

    # ---- the vocabulary every later stage speaks --------------------------

    assert s.LINE_KEYS == ("tick", "kind", "job", "owner", "status", "ticks",
                           "key", "text"), (
        "this stage's fields are %r, not the eight the course defined"
        % (s.LINE_KEYS,))
    assert issubclass(s.DurableError, ValueError), (
        "%r is not a ValueError: the course's refusal is a named error a caller "
        "can catch, and every later stage derives its own from it"
        % (s.DurableError,))
    assert issubclass(s.JournalError, s.DurableError), (
        "%r is not a %s: one `except DurableError` must still catch a broken "
        "line" % (s.JournalError, s.DurableError.__name__))

    # ---- the nine kinds, hand-computed ------------------------------------

    # one whole line's text, by hand: the tick, the kind, then every field the
    # kind carries in LINE_KEYS order, space-separated, no trailing space
    claim = {"tick": 3, "kind": "claim", "job": "fast", "owner": "w1",
             "ticks": 5}
    assert s.line(3, "claim", job="fast", owner="w1", ticks=5) == (
        "3 claim job=fast owner=w1 ticks=5"), (
        "a claim line is not the text its own fields spell: %r"
        % (s.line(3, "claim", job="fast", owner="w1", ticks=5),))

    cases = (
        ({"tick": 0, "kind": "start", "key": "run-1", "text": "plan:h1"},
         "0 start key=run-1 text=plan:h1"),
        ({"tick": 3, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 5},
         "3 claim job=fast owner=w1 ticks=5"),
        ({"tick": 4, "kind": "beat", "job": "fast", "owner": "w1", "ticks": 9},
         "4 beat job=fast owner=w1 ticks=9"),
        ({"tick": 5, "kind": "intent", "job": "fast", "key": "effect:fast"},
         "5 intent job=fast key=effect:fast"),
        ({"tick": 6, "kind": "result", "job": "fast", "owner": "w1",
          "status": "ok", "ticks": 1, "text": "done"},
         "6 result job=fast owner=w1 status=ok ticks=1 text=done"),
        ({"tick": 6, "kind": "effect", "job": "fast", "key": "effect:fast"},
         "6 effect job=fast key=effect:fast"),
        ({"tick": 9, "kind": "expire", "job": "slow", "owner": "w2"},
         "9 expire job=slow owner=w2"),
        ({"tick": 9, "kind": "retry", "job": "slow", "ticks": 2},
         "9 retry job=slow ticks=2"),
        ({"tick": 9, "kind": "done"}, "9 done"),
    )
    assert len(cases) == 9, "the nine kinds, one case each"
    seen = set()
    for want, text in cases:
        kind = want["kind"]
        seen.add(kind)
        fields = {name: value for name, value in want.items()
                  if name not in ("tick", "kind")}
        got_text = s.line(want["tick"], kind, **fields)
        assert got_text == text, (
            "the %r line is %r, not the text its fields spell (%r)"
            % (kind, got_text, text))
        # the round trip: parse_line(line(fields)) is exactly the fields — the
        # tick and the kind, and nothing the kind does not carry
        got = s.parse_line(got_text)
        assert isinstance(got, Mapping), (
            "parse_line(%r) gave %r, which is not a mapping" % (text, got))
        assert got == want, (
            "parse_line(%r) gave %r, not the fields the line spells: %r"
            % (text, got, want))
        for name, value in want.items():
            assert type(got[name]) is type(value) or name in ("kind",), (
                "parse_line(%r) parsed %r as %r, not as the %s it was written "
                "as" % (text, name, type(got[name]).__name__, type(value).__name__))
    assert seen == set(cases[i][1].split()[1] for i in range(9)), (
        "the round trip does not cover the nine kinds: %r" % (sorted(seen),))

    # a `result` may carry no detail: that is a result, not a broken line
    bare = s.line(6, "result", job="fast", owner="w1", status="ok", ticks=1)
    assert bare == "6 result job=fast owner=w1 status=ok ticks=1", (
        "a result without a detail is %r, not the line its four fields spell"
        % (bare,))
    assert s.parse_line(bare) == {"tick": 6, "kind": "result", "job": "fast",
                                  "owner": "w1", "status": "ok", "ticks": 1}, (
        "a result without a detail parsed to %r" % (s.parse_line(bare),))
    # and a done line is just a tick and a kind: nothing else
    assert s.line(0, "done") == "0 done", (
        "a done line is %r, not '0 done' — the run has nothing left, and a job "
        "is something it does not have" % (s.line(0, "done"),))

    # ---- line(): a field the kind does not carry is refused by name -------

    message = _refuses(s.JournalError, "a status on a claim line",
                       lambda: s.line(0, "claim", job="fast", owner="w1",
                                      status="ok", ticks=1))
    assert "'status'" in message and "'claim'" in message, (
        "the refusal of a status on a claim does not name the field and the "
        "kind: %r" % (message,))
    assert "job" in message and "owner" in message and "ticks" in message, (
        "the refusal of a field a claim does not carry does not say what a "
        "claim does carry: %r" % (message,))
    message = _refuses(s.JournalError, "a job on a done line",
                       lambda: s.line(0, "done", job="fast"))
    assert "'job'" in message and "'done'" in message, (
        "the refusal of a done line that names a job does not name both: %r"
        % (message,))
    message = _refuses(s.JournalError, "a key on an expire line",
                       lambda: s.line(9, "expire", job="slow", owner="w2",
                                      key="effect:slow"))
    assert "'key'" in message and "'expire'" in message, (
        "the refusal of a key on an expire does not name both: %r" % (message,))
    message = _refuses(s.JournalError, "a text on an intent line",
                       lambda: s.line(5, "intent", job="fast", key="effect:fast",
                                      text="before"))
    assert "'text'" in message and "'intent'" in message, (
        "the refusal of a text on an intent does not name both: %r" % (message,))
    message = _refuses(s.JournalError, "a ticks on a done line",
                       lambda: s.line(0, "done", ticks=4))
    assert "'ticks'" in message and "'done'" in message, (
        "the refusal of a ticks on a done line does not name both: %r"
        % (message,))

    # ---- line(): a kind that is not one of the nine -----------------------

    message = _refuses(s.JournalError, "a kind outside the nine",
                       lambda: s.line(0, "clai", job="fast", owner="w1"))
    assert "'clai'" in message and "did you mean 'claim'" in message, (
        "the refusal of the kind 'clai' does not name it and suggest the real "
        "kind it is one edit from: %r" % (message,))
    assert "done" in message, (
        "the refusal of a bad kind does not list the nine: %r" % (message,))
    message = _refuses(s.JournalError, "a kind that resembles nothing",
                       lambda: s.line(0, "journal"))
    assert "'journal'" in message, (
        "the refusal of a kind that resembles nothing does not name it: %r"
        % (message,))

    # ---- line(): a field the kind needs, missing --------------------------

    message = _refuses(s.JournalError, "a claim with no job",
                       lambda: s.line(0, "claim", owner="w1", ticks=1))
    assert "'job'" in message and "'claim'" in message, (
        "the refusal of a claim with no job does not name the field and the "
        "kind: %r" % (message,))
    message = _refuses(s.JournalError, "a claim with no owner",
                       lambda: s.line(0, "claim", job="fast", ticks=1))
    assert "'owner'" in message, (
        "the refusal of a claim with no owner does not name the owner: %r"
        % (message,))
    message = _refuses(s.JournalError, "an intent with no key",
                       lambda: s.line(0, "intent", job="fast"))
    assert "'key'" in message and "'intent'" in message, (
        "the refusal of an intent with no key does not name both: %r"
        % (message,))
    message = _refuses(s.JournalError, "a start with no run id",
                       lambda: s.line(0, "start", text="plan:h1"))
    assert "'key'" in message, (
        "the refusal of a start with no run id does not name the field that "
        "carries it: %r" % (message,))
    message = _refuses(s.JournalError, "a start with no plan hash",
                       lambda: s.line(0, "start", key="run-1"))
    assert "'text'" in message, (
        "the refusal of a start with no plan hash does not name the field: %r"
        % (message,))
    message = _refuses(s.JournalError, "a result with no status",
                       lambda: s.line(0, "result", job="fast", owner="w1",
                                      ticks=1))
    assert "'status'" in message, (
        "the refusal of a result with no status does not name the status: %r"
        % (message,))
    message = _refuses(s.JournalError, "a retry with no job",
                       lambda: s.line(0, "retry", ticks=2))
    assert "'job'" in message, (
        "the refusal of a retry with no job does not name the job: %r"
        % (message,))

    # ---- line(): a status its kind cannot say -----------------------------

    message = _refuses(s.JournalError, "a result whose status is a state",
                       lambda: s.line(0, "result", job="fast", owner="w1",
                                      status="done", ticks=1))
    assert "'done'" in message, (
        "the refusal of a status the outcomes do not have does not name it: %r"
        % (message,))
    for status in ("ok", "failed", "died"):
        assert " " + status in " " + message, (
            "the refusal of a bad status does not list the outcomes a result "
            "may say (missing %r): %r" % (status, message))

    # ---- line(): a number that is not a non-negative int ------------------

    for bad in (True, False, 1.5, "5", -1, None):
        message = _refuses(s.JournalError, "a ticks of %r" % (bad,),
                           lambda bad=bad: s.line(0, "claim", job="fast",
                                                  owner="w1", ticks=bad))
        assert "'ticks'" in message or "ticks" in message, (
            "the refusal of a ticks of %r does not name the field: %r"
            % (bad, message))
        assert repr(bad) in message, (
            "the refusal of a ticks of %r does not name the value it refused: "
            "%r" % (bad, message))
    message = _refuses(s.JournalError, "a tick of True",
                       lambda: s.line(True, "done"))
    assert "True" in message and "tick" in message, (
        "the refusal of a tick of True does not name the tick and the value: %r"
        % (message,))
    message = _refuses(s.JournalError, "a tick of -1",
                       lambda: s.line(-1, "done"))
    assert "-1" in message, (
        "the refusal of a tick of -1 does not name the value: %r" % (message,))

    # ---- line(): a blank owner, key or text -------------------------------

    message = _refuses(s.JournalError, "a blank owner",
                       lambda: s.line(0, "claim", job="fast", owner="  ",
                                      ticks=1))
    assert "'owner'" in message or "owner" in message, (
        "the refusal of a blank owner does not name the field: %r" % (message,))
    message = _refuses(s.JournalError, "an empty key",
                       lambda: s.line(0, "intent", job="fast", key=""))
    assert "key" in message, (
        "the refusal of an empty key does not name the field: %r" % (message,))
    message = _refuses(s.JournalError, "a blank text",
                       lambda: s.line(0, "start", key="run-1", text=" "))
    assert "text" in message, (
        "the refusal of a blank text does not name the field: %r" % (message,))
    # a value that carries the separator could not be read back
    message = _refuses(s.JournalError, "a job with a space in it",
                       lambda: s.line(0, "claim", job="fa st", owner="w1",
                                      ticks=1))
    assert "job" in message, (
        "the refusal of a job carrying whitespace does not name the field: %r"
        % (message,))

    # ---- parse_line(): a line that is not a line --------------------------

    message = _refuses(s.JournalError, "a line that is not a str",
                       lambda: s.parse_line(7))
    assert "7" in message, (
        "the refusal of the line 7 does not name it: %r" % (message,))
    message = _refuses(s.JournalError, "an empty line",
                       lambda: s.parse_line("   "))
    assert "empty" in message, (
        "the refusal of a blank line does not say it is empty: %r" % (message,))
    message = _refuses(s.JournalError, "a line with no kind",
                       lambda: s.parse_line("3"))
    assert "3" in message and "kind" in message, (
        "the refusal of a line with no kind does not name the line and the "
        "kind: %r" % (message,))
    message = _refuses(s.JournalError, "a line with an unknown kind",
                       lambda: s.parse_line("0 cla"))
    assert "'cla'" in message and "did you mean 'claim'" in message, (
        "the refusal of the kind 'cla' does not name it and suggest its near "
        "real one: %r" % (message,))
    message = _refuses(s.JournalError, "a negative tick",
                       lambda: s.parse_line("-1 done"))
    assert "-1" in message, (
        "the refusal of the tick -1 does not name it: %r" % (message,))
    message = _refuses(s.JournalError, "a tick that is not a number",
                       lambda: s.parse_line("now done"))
    assert "now" in message, (
        "the refusal of the tick 'now' does not name it: %r" % (message,))
    message = _refuses(s.JournalError, "a field with no value",
                       lambda: s.parse_line("0 done what"))
    assert "what" in message, (
        "the refusal of the field 'what' does not name it: %r" % (message,))

    # ---- parse_line(): a field the kind does not carry, and a missing one --

    message = _refuses(s.JournalError, "a status on a parsed claim",
                       lambda: s.parse_line("0 claim job=fast owner=w1 "
                                            "ticks=1 status=ok"))
    assert "status" in message and "claim" in message, (
        "the refusal of a status on a claim does not name the field and the "
        "kind: %r" % (message,))
    message = _refuses(s.JournalError, "a field the line has no vocabulary for",
                       lambda: s.parse_line("0 claim job=fast owner=w1 "
                                            "statuz=1"))
    assert "statuz" in message and "did you mean 'status'" in message, (
        "the refusal of the field 'statuz' does not name it and suggest the "
        "real field it is one edit from: %r" % (message,))
    message = _refuses(s.JournalError, "a claim whose owner is missing",
                       lambda: s.parse_line("0 claim job=fast ticks=1"))
    assert "owner" in message and "claim" in message, (
        "the refusal of a claim with no owner does not name the field and the "
        "kind: %r" % (message,))
    message = _refuses(s.JournalError, "a done line that names a job",
                       lambda: s.parse_line("0 done job=fast"))
    assert "job" in message and "done" in message, (
        "the refusal of a done line that names a job does not name both: %r"
        % (message,))
    message = _refuses(s.JournalError, "a field repeated on one line",
                       lambda: s.parse_line("0 claim job=fast owner=w1 "
                                            "owner=w2 ticks=1"))
    assert "owner" in message and "twice" in message, (
        "the refusal of a repeated field does not name it and say it repeats: "
        "%r" % (message,))
    message = _refuses(s.JournalError, "a parsed ticks that is not a number",
                       lambda: s.parse_line("0 claim job=fast owner=w1 ticks=x"))
    assert "ticks" in message and "x" in message, (
        "the refusal of the ticks 'x' does not name the field and the value: %r"
        % (message,))
    message = _refuses(s.JournalError, "a parsed ticks that is negative",
                       lambda: s.parse_line("0 claim job=fast owner=w1 ticks=-2"))
    assert "-2" in message, (
        "the refusal of the ticks '-2' does not name it: %r" % (message,))
    message = _refuses(s.JournalError, "a parsed blank value",
                       lambda: s.parse_line("0 intent job=fast key="))
    assert "key" in message, (
        "the refusal of a blank key does not name the field: %r" % (message,))
    message = _refuses(s.JournalError, "a parsed status the outcomes lack",
                       lambda: s.parse_line("0 result job=fast owner=w1 "
                                            "status=expired ticks=1"))
    assert "expired" in message, (
        "the refusal of the status 'expired' does not name it: %r" % (message,))
    message = _refuses(s.JournalError, "a line whose tick is not a field",
                       lambda: s.parse_line("0 claim tick=1"))
    assert "tick" in message, (
        "the refusal of 'tick' as a field does not name it: %r" % (message,))

    # ---- parse_line() refuses with the line it was given ------------------

    message = _refuses(s.JournalError, "a result with a bad status",
                       lambda: s.parse_line("0 result job=fast owner=w1 "
                                            "status=okay ticks=1"))
    assert "0 result job=fast owner=w1 status=okay ticks=1" in message, (
        "the refusal of a bad status does not carry the line it refused: %r"
        % (message,))

    # ---- write_line(): the append, the length, and no sync ----------------

    journal = world.Disk()
    length = s.write_line(journal, claim)
    assert world.DEFAULT_JOURNAL == "/var/log/durable/journal", (
        "the world's journal path moved: %r" % (world.DEFAULT_JOURNAL,))
    expected = "3 claim job=fast owner=w1 ticks=5\n"
    assert length == len(expected), (
        "write_line returned %r, not the new length of the journal (%r): a "
        "line is appended, and its length is what the disk reports"
        % (length, len(expected)))
    assert journal.read(world.DEFAULT_JOURNAL) == expected, (
        "the journal reads %r, not the line write_line was handed (%r)"
        % (journal.read(world.DEFAULT_JOURNAL), expected))
    # the append is NOT synced: a line is a prediction until a sync makes it a
    # fact, and stage 2 owns the sync
    assert journal.synced(world.DEFAULT_JOURNAL) == "", (
        "write_line synced the journal (%r): stage 2 owns the sync, and a line "
        "that claims to be durable without one is the failure this course is "
        "about" % (journal.synced(world.DEFAULT_JOURNAL),))
    assert not journal.durable(world.DEFAULT_JOURNAL, expected), (
        "the line write_line appended is already durable: a write is not "
        "durable until a sync")
    # a second line appends: the journal is append-only
    second = s.write_line(journal, {"tick": 4, "kind": "beat", "job": "fast",
                                    "owner": "w1", "ticks": 9})
    assert second == len(expected) + len("4 beat job=fast owner=w1 ticks=9\n"), (
        "the second write_line returned %r, not the journal's new length" % (second,))
    assert journal.read(world.DEFAULT_JOURNAL) == (
        expected + "4 beat job=fast owner=w1 ticks=9\n"), (
        "the journal reads %r: a second line appends, it does not replace"
        % (journal.read(world.DEFAULT_JOURNAL),))
    # and a crash loses exactly the two unsynced lines, at the world's path
    lost = journal.crash()
    assert lost == ((world.DEFAULT_JOURNAL, expected
                     + "4 beat job=fast owner=w1 ticks=9\n"),), (
        "a crash lost %r, not the whole unsynced journal: write_line appended "
        "through disk.write and never synced" % (lost,))
    assert journal.read(world.DEFAULT_JOURNAL) == "", (
        "the journal still reads %r after a crash that lost everything"
        % (journal.read(world.DEFAULT_JOURNAL),))

    # the append really goes through the disk the caller handed, at the world's
    # path and not a path of this stage's own
    other = world.Disk()
    s.write_line(other, {"tick": 9, "kind": "done"})
    assert other.files() == (world.DEFAULT_JOURNAL,), (
        "write_line wrote to %r, not the world's journal %r"
        % (other.files(), world.DEFAULT_JOURNAL))
    assert other.read(world.DEFAULT_JOURNAL) == "9 done\n", (
        "the done line landed as %r" % (other.read(world.DEFAULT_JOURNAL),))

    # ---- write_line(): a broken entry is refused by name ------------------

    message = _refuses(s.JournalError, "an entry that is not a mapping",
                       lambda: s.write_line(world.Disk(), 7))
    assert "7" in message, (
        "the refusal of the entry 7 does not name it: %r" % (message,))
    message = _refuses(s.JournalError, "an entry with no tick",
                       lambda: s.write_line(world.Disk(), {"kind": "done"}))
    assert "tick" in message, (
        "the refusal of an entry with no tick does not name it: %r" % (message,))
    message = _refuses(s.JournalError, "an entry with no kind",
                       lambda: s.write_line(world.Disk(), {"tick": 0}))
    assert "kind" in message, (
        "the refusal of an entry with no kind does not name it: %r" % (message,))
    message = _refuses(s.JournalError, "an entry with a foreign field",
                       lambda: s.write_line(world.Disk(), {"tick": 0,
                                                           "kind": "done",
                                                           "tickz": 1}))
    assert "tickz" in message and "did you mean 'tick'" in message, (
        "the refusal of the entry field 'tickz' does not name it and suggest "
        "its near real field: %r" % (message,))
    message = _refuses(s.JournalError, "an entry whose value a kind refuses",
                       lambda: s.write_line(world.Disk(), {"tick": 0,
                                                           "kind": "claim",
                                                           "job": "fast",
                                                           "ticks": 1}))
    assert "owner" in message, (
        "the refusal of an entry that omits a required field does not name it: "
        "%r" % (message,))
    # and a refused entry writes nothing at all
    blank = world.Disk()
    _refuses(s.JournalError, "a claim entry with no owner",
             lambda: s.write_line(blank, {"tick": 0, "kind": "claim",
                                          "job": "fast", "ticks": 1}))
    assert blank.read(world.DEFAULT_JOURNAL) == "", (
        "a refused entry still wrote %r to the journal"
        % (blank.read(world.DEFAULT_JOURNAL),))

    print("check_01: the line — nine kinds, each carrying exactly the fields it "
          "needs and refused by name when one is missing, unknown or the wrong "
          "shape; the whole text of a claim line is hand-computed and every "
          "kind round-trips through line then parse_line; a field a kind does "
          "not carry, a blank owner/key/text, a bool or float ticks and a "
          "status a result cannot say are all refused; and write_line appends "
          "one line through disk.write at the world's journal, returning the "
          "new length and syncing nothing")

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate,
                                              "durable-execution-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet. The
        refusals are caught as stage 1's own class, so a stage that refuses with a
        bare `ValueError` is caught here too.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import disk as world
    import stage_01 as stage1
    import stage_02 as s

    journal = world.DEFAULT_JOURNAL
    assert journal == "/var/log/durable/journal", (
        "the world's journal path moved: %r" % (journal,))
    # a second path, so `lost` can be pinned on its path-by-path, sorted report
    other = "/var/log/durable/other"
    assert journal < other

    # ---- the lines this check writes, hand-counted ------------------------
    start = "0 start key=run-1 text=plan:h1"
    claim = "3 claim job=fast owner=w1 ticks=5"
    beat = "4 beat job=fast owner=w1 ticks=9"
    assert (len(start), len(claim), len(beat)) == (30, 33, 32), (
        "this check mis-counts its own lines: %r"
        % ((len(start), len(claim), len(beat)),))
    start_entry = {"tick": 0, "kind": "start", "key": "run-1", "text": "plan:h1"}
    claim_entry = {"tick": 3, "kind": "claim", "job": "fast", "owner": "w1",
                   "ticks": 5}
    beat_entry = {"tick": 4, "kind": "beat", "job": "fast", "owner": "w1",
                  "ticks": 9}

    # ---- append: a line the program can read, and no sync at all ----------
    disk = world.Disk()
    length = s.append(disk, claim_entry)
    assert length == 34, (
        "append returned %r, not the journal's new length (34: the claim line's "
        "33 characters and the terminator write_line appends)" % (length,))
    assert disk.read(journal) == claim + "\n", (
        "the journal reads %r, not the line append was handed"
        % (disk.read(journal),))
    assert disk.synced(journal) == "", (
        "append synced the journal (%r): a line that was not synced is a "
        "prediction, and a program that believes one is the failure this course "
        "is about" % (disk.synced(journal),))
    assert disk.durable(journal, claim + "\n") is False, (
        "the appended line is already durable: nothing is durable until a sync")
    assert disk.volatile() == (journal,), (
        "the disk does not report the journal as volatile (%r): append wrote "
        "and did not sync" % (disk.volatile(),))
    assert s.survives(disk, claim) is False, (
        "survives said an appended line is durable: a write is not durable until "
        "a sync")
    assert s.survives(disk, claim + "\n") is False, (
        "survives said an appended line is durable when it carries the journal's "
        "terminator")
    assert s.lost(disk) == ((journal, claim + "\n"),), (
        "lost reported %r, not the whole line a crash would discard"
        % (s.lost(disk),))

    # a second append appends: the journal is append-only and the unsynced tail
    # grows by exactly the second line
    second = s.append(disk, beat_entry)
    assert second == 67, (
        "the second append returned %r, not the journal's new length (67: the "
        "claim's 34 and the beat's 33)" % (second,))
    assert disk.read(journal) == claim + "\n" + beat + "\n", (
        "the journal reads %r: a second line appends, it does not replace"
        % (disk.read(journal),))
    assert disk.synced(journal) == ""
    assert s.lost(disk) == ((journal, claim + "\n" + beat + "\n"),), (
        "lost reported %r, not the whole unsynced tail" % (s.lost(disk),))
    # a crash at this moment costs exactly the unsynced tail, and nothing else
    assert disk.crash() == ((journal, claim + "\n" + beat + "\n"),), (
        "the crash cost %r, not the two unsynced lines"
        % (disk.crash(),))
    assert disk.read(journal) == "" and disk.synced(journal) == ""

    # ---- commit: the same line, and the sync that makes it a fact ---------
    disk = world.Disk()
    length = s.commit(disk, claim_entry)
    assert length == 34, (
        "commit returned %r, not the journal's new length (34)" % (length,))
    assert disk.read(journal) == claim + "\n", (
        "commit's journal reads %r, not the line it was handed"
        % (disk.read(journal),))
    assert disk.synced(journal) == claim + "\n", (
        "commit's journal is not durable (%r): commit exists to sync the line it "
        "wrote" % (disk.synced(journal),))
    assert disk.durable(journal, claim + "\n") is True
    assert s.survives(disk, claim) is True, (
        "survives said a committed line is not durable")
    assert s.survives(disk, claim + "\n") is True, (
        "survives refused the same line spelled with the terminator the journal "
        "adds")
    assert s.lost(disk) == (), (
        "a crash after a commit costs %r, not nothing" % (s.lost(disk),))
    # and the crash costs nothing: the line this process believed is the line
    # the next process finds
    assert disk.crash() == (), (
        "the crash after a commit cost %r" % (disk.crash(),))
    assert disk.read(journal) == claim + "\n"
    assert disk.synced(journal) == claim + "\n"

    # ---- the sync is a barrier, not a per-line stamp ----------------------
    disk = world.Disk()
    s.append(disk, start_entry)
    assert disk.synced(journal) == ""
    length = s.commit(disk, claim_entry)
    assert length == 65, (
        "commit returned %r, not the journal's new length (65: the start line's "
        "31 characters and the claim's 34)" % (length,))
    assert disk.synced(journal) == start + "\n" + claim + "\n", (
        "commit flushed %r: it synced its own line and left the line written "
        "before it a prediction" % (disk.synced(journal),))
    assert s.survives(disk, start) is True and s.survives(disk, claim) is True
    assert s.lost(disk) == (), (
        "a crash after a commit costs %r, not nothing" % (s.lost(disk),))

    # ---- lost: what a crash would cost, asked without crashing ------------
    disk = world.Disk()
    s.commit(disk, start_entry)
    s.commit(disk, claim_entry)
    s.append(disk, beat_entry)
    kept = start + "\n" + claim + "\n"
    tail = beat + "\n"
    assert s.lost(disk) == ((journal, tail),), (
        "lost reported %r, not exactly the unsynced tail behind the two "
        "committed lines" % (s.lost(disk),))
    # `lost` is a reading: it answers, and changes nothing
    assert disk.read(journal) == kept + tail, (
        "lost crashed the disk it was asked about (%r): it is a question, not a "
        "kill" % (disk.read(journal),))
    assert disk.synced(journal) == kept, (
        "lost synced the journal (%r): it reports what a crash would cost, it "
        "does not change the cost" % (disk.synced(journal),))
    assert s.lost(disk) == disk.crash(), (
        "lost and a crash disagree about what a crash would cost")
    assert disk.read(journal) == kept and disk.synced(journal) == kept
    assert s.survives(disk, claim) is True and s.survives(disk, beat) is False
    # the crash that just happened is over: nothing is volatile, nothing to lose
    assert s.lost(disk) == ()
    assert s.lost(disk) == disk.crash()

    # path by path, in the order a crash reports them
    disk = world.Disk()
    disk.write(other, "side")
    disk.write(journal, claim + "\n")
    assert s.lost(disk) == ((journal, claim + "\n"), (other, "side")), (
        "lost reported %r, not the volatile paths sorted by path"
        % (s.lost(disk),))
    assert s.lost(disk) == disk.crash()

    # a staged rewrite was never durable, so all of it is lost
    disk = world.Disk()
    disk.write(journal, start + "\n")
    disk.sync()
    disk.replace(journal, claim + "\n")
    assert s.lost(disk) == ((journal, claim + "\n"),), (
        "lost reported %r for a staged rewrite" % (s.lost(disk),))
    assert s.lost(disk) == disk.crash()

    # a path with nothing to lose is not part of the cost
    blank = world.Disk()
    blank.write(journal, "")
    assert s.lost(blank) == (), (
        "lost reported %r for a write that carries no text" % (s.lost(blank),))
    assert s.lost(blank) == blank.crash()
    assert s.lost(world.Disk()) == (), (
        "a fresh disk has %r to lose" % (s.lost(world.Disk()),))

    # ---- survives: a whole line, not a match inside one -------------------
    disk = world.Disk()
    s.commit(disk, start_entry)
    s.commit(disk, claim_entry)
    assert s.survives(disk, claim) is True, (
        "survives said a committed line is not durable")
    for guess in ("3 claim", "3", "claim", "3 claim job=fast",
                  "3 claim job=fast owner=w1", "3 claim job=fast owner=w1 ticks=5 ",
                  "0 start", start[:-1], claim + "x", "x" + claim, beat):
        assert s.survives(disk, guess) is False, (
            "survives said %r is durable: only a whole line of the synced "
            "journal is" % (guess,))
    assert s.survives(disk, start) is True, (
        "survives answered about a line the journal does carry")

    # the question is about the synced journal, not about what the program sees
    disk = world.Disk()
    s.append(disk, claim_entry)
    assert s.survives(disk, claim) is False, (
        "survives answered about what the program can see instead of what a "
        "crash would keep")

    # the trailing line that never got a terminator is not a line yet: a crash
    # in the middle of an append leaves it, and it is stage 3's `torn`
    disk = world.Disk()
    s.commit(disk, {"tick": 0, "kind": "done"})
    assert s.survives(disk, "0 done") is True
    disk.write(journal, "1 be")
    disk.sync()
    assert disk.synced(journal) == "0 done\n1 be"
    assert s.lost(disk) == ()
    assert s.survives(disk, "1 be") is False, (
        "survives said the half-written tail is durable: a line that never got "
        "its terminator is not a line yet")
    assert s.survives(disk, "1 be\n") is False
    assert s.survives(disk, "0 done") is True, (
        "survives stopped seeing the finished line in front of the tail")

    # ---- refusals: stage 1's own vocabulary, naming the offender ----------
    assert issubclass(stage1.JournalError, stage1.DurableError), (
        "stage 1's refusal is not the course's family any more")

    message = _refuses(stage1.JournalError, "an entry that is not a mapping",
                       lambda: s.append(world.Disk(), 7))
    assert "7" in message, (
        "the refusal of the entry 7 does not name it: %r" % (message,))
    message = _refuses(stage1.JournalError, "a claim entry with no owner",
                       lambda: s.append(world.Disk(),
                                        {"tick": 0, "kind": "claim",
                                         "job": "fast", "ticks": 1}))
    assert "owner" in message, (
        "the refusal of a claim with no owner does not name the field: %r"
        % (message,))
    message = _refuses(stage1.JournalError, "an entry with a foreign field",
                       lambda: s.append(world.Disk(), {"tick": 0,
                                                       "kind": "done",
                                                       "tickz": 1}))
    assert "tickz" in message and "did you mean 'tick'" in message, (
        "the refusal of the entry field 'tickz' does not name it and suggest its "
        "near real field: %r" % (message,))
    message = _refuses(stage1.JournalError, "a start with no plan hash",
                       lambda: s.commit(world.Disk(), {"tick": 0,
                                                       "kind": "start",
                                                       "key": "run-1"}))
    assert "text" in message, (
        "the refusal of a start with no plan hash does not name the field: %r"
        % (message,))

    # a refused commit makes nothing durable — not even what was pending before
    disk = world.Disk()
    s.append(disk, claim_entry)
    _refuses(stage1.JournalError, "a commit of a broken entry",
             lambda: s.commit(disk, {"tick": 0, "kind": "claim", "job": "fast",
                                     "ticks": 1}))
    assert disk.read(journal) == claim + "\n", (
        "a refused commit wrote %r to the journal" % (disk.read(journal),))
    assert disk.synced(journal) == "", (
        "a refused commit synced %r: a call that failed must not decide what is "
        "durable" % (disk.synced(journal),))
    assert s.lost(disk) == ((journal, claim + "\n"),), (
        "the line appended before the refused commit is no longer volatile: the "
        "refusal made a prediction durable")

    # the world's disk, or a refusal naming what was handed instead
    for wrong in (None, 7, "the journal"):
        for name, call in (("append", lambda w=wrong: s.append(w, claim_entry)),
                           ("commit", lambda w=wrong: s.commit(w, claim_entry)),
                           ("lost", lambda w=wrong: s.lost(w)),
                           ("survives", lambda w=wrong: s.survives(w, claim))):
            message = _refuses(stage1.JournalError,
                               "%s handed %r" % (name, wrong), call)
            assert repr(wrong) in message, (
                "the refusal of %r does not name it: %r" % (wrong, message))

    # and a text `survives` cannot look for is refused naming it
    disk = world.Disk()
    for bad in (None, 7, claim_entry):
        message = _refuses(stage1.JournalError,
                           "a text that is not a str (%r)" % (bad,),
                           lambda bad=bad: s.survives(disk, bad))
        assert repr(bad) in message, (
            "the refusal of the text %r does not name it: %r" % (bad, message))
    for blank_text in ("", " ", "   \n "):
        message = _refuses(stage1.JournalError,
                           "the blank text %r" % (blank_text,),
                           lambda blank_text=blank_text: s.survives(
                               disk, blank_text))
        assert repr(blank_text) in message, (
            "the refusal of the blank text %r does not name it: %r"
            % (blank_text, message))

    print("check_02: the line append writes is not durable — synced empty, "
          "durable False, survives False, and a crash that costs the whole "
          "unsynced tail — while commit makes the same line, hand-counted at 34 "
          "characters, a fact a crash cannot touch; the sync is a barrier over "
          "everything written before it; lost equals crash() without crashing, "
          "path by path, for a tail, a rewrite, two paths and a write that "
          "carries no text; survives answers for whole lines only, so a prefix "
          "of one is not durable and a tail that never got a terminator is not "
          "a line yet; and every refusal is stage 1's own and names its "
          "offender")

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    SIX = ("pending", "running", "expired", "done", "failed", "skipped")

    def _repo(start=None):
        for candidate_start in (os.environ.get("J3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate,
                                              "durable-execution-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _journal(disk, entries, write, path):
        """Write a hand-built journal through stage 1's `write_line`.

        Every entry is a mapping of `tick`, `kind` and the fields its kind carries;
        the writer owns the terminator the reader is about to ask about, and it
        appends at the world's own journal (`path` here is where the fixture is
        read back from).
        """
        for entry in entries:
            write(disk, dict(entry))
        return disk.read(path)

    import disk as world
    import stage_01 as s1
    import stage_03 as s

    # ---- the refusal family every later stage catches ---------------------

    assert issubclass(s.ReplayError, s1.DurableError), (
        "%r is not a %s: a caller that catches the course's one refusal family "
        "must still catch a log it cannot believe"
        % (s.ReplayError, s1.DurableError.__name__))

    # ---- one journal, written line by line, that a reader must fold -------
    #
    # 22 lines, hand-written: a `start`, seven jobs, and the decisions that
    # make the table below. `slow` is claimed and never answered; `fast` is
    # claimed, beaten, finished with a detail and then expired by an owner that
    # had already answered; `bulk` dies; `hopeless` fails for good; `flaky`
    # fails, is retried, is claimed by a second owner, and the *first* owner's
    # expire arrives after the new claim; `fragile` is claimed and expired, and
    # an `intent` after it decides nothing; `ghost` is named by an `intent` and
    # nothing else; and the run writes `done`, which names no job at all.

    src = (
        {"tick": 0, "kind": "start", "key": "run-1", "text": "plan:abc"},
        {"tick": 1, "kind": "claim", "job": "slow", "owner": "w1", "ticks": 6},
        {"tick": 2, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 4},
        {"tick": 3, "kind": "beat", "job": "fast", "owner": "w1", "ticks": 7},
        {"tick": 4, "kind": "result", "job": "fast", "owner": "w1",
         "status": "ok", "ticks": 1, "text": "wrote:f1"},
        {"tick": 5, "kind": "intent", "job": "fast", "key": "fast-key"},
        {"tick": 6, "kind": "effect", "job": "fast", "key": "fast-key"},
        {"tick": 7, "kind": "expire", "job": "fast", "owner": "w1"},
        {"tick": 8, "kind": "claim", "job": "bulk", "owner": "w1", "ticks": 2},
        {"tick": 9, "kind": "result", "job": "bulk", "owner": "w1",
         "status": "died", "ticks": 2},
        {"tick": 10, "kind": "claim", "job": "hopeless", "owner": "w1",
         "ticks": 2},
        {"tick": 11, "kind": "result", "job": "hopeless", "owner": "w1",
         "status": "failed", "ticks": 2, "text": "gave-up"},
        {"tick": 12, "kind": "claim", "job": "flaky", "owner": "w1", "ticks": 3},
        {"tick": 13, "kind": "result", "job": "flaky", "owner": "w1",
         "status": "failed", "ticks": 3, "text": "boom"},
        {"tick": 14, "kind": "retry", "job": "flaky", "ticks": 2},
        {"tick": 15, "kind": "claim", "job": "flaky", "owner": "w2", "ticks": 9},
        {"tick": 16, "kind": "expire", "job": "flaky", "owner": "w1"},
        {"tick": 17, "kind": "claim", "job": "fragile", "owner": "w2",
         "ticks": 5},
        {"tick": 18, "kind": "expire", "job": "fragile", "owner": "w2"},
        {"tick": 19, "kind": "intent", "job": "fragile", "key": "fragile-key"},
        {"tick": 20, "kind": "intent", "job": "ghost", "key": "ghost-key"},
        {"tick": 21, "kind": "done"},
    )

    disk = world.Disk()
    text = _journal(disk, src, s1.write_line, world.DEFAULT_JOURNAL)

    assert disk.synced(world.DEFAULT_JOURNAL) == "", (
        "the fixture synced the journal it built; a replay must be asked about "
        "a write that is still only a prediction, which is the interesting one")
    assert text.endswith("\n"), (
        "stage 1's write_line did not terminate its last line: %r" % (text,))

    lines = s.replay(disk)
    assert isinstance(lines, tuple), (
        "a replay yields the lines as a tuple, got %r" % (type(lines).__name__,))
    assert lines == tuple(src), (
        "the replayed lines are not the lines the journal holds:\n  got  %r\n"
        "  want %r" % (lines, tuple(src)))
    assert len(lines) == 22, (
        "the journal holds 22 lines, the replay returned %d" % (len(lines),))
    assert lines[0] == {"tick": 0, "kind": "start", "key": "run-1",
                        "text": "plan:abc"}, (
        "the first line of the replay is not the `start` the log begins with: "
        "%r" % (lines[0],))
    assert lines[9] == {"tick": 9, "kind": "result", "job": "bulk",
                        "owner": "w1", "status": "died", "ticks": 2}, (
        "the tenth line of the replay is not the result the log holds: %r"
        % (lines[9],))
    assert lines[-1] == {"tick": 21, "kind": "done"}, (
        "the last line of the replay is not the run's `done`: %r" % (lines[-1],))
    assert s.replay(disk) == lines and s.replay(disk) is not lines, (
        "two replays of the same lines must yield equal lines")
    assert disk.synced(world.DEFAULT_JOURNAL) == "", (
        "the replay synced the journal it read; reading is not a write")

    # the path is the caller's, and the world's default is only the default
    other = "/tmp/journal-of-another-run"
    copy = world.Disk()
    copy.write(other, text)
    assert s.replay(copy, other) == tuple(src), (
        "a replay of a journal at another path did not read that path")
    assert s.replay(copy) == (), (
        "a replay with no path must read the world's DEFAULT_JOURNAL, not the "
        "path the caller meant")

    # ---- the state table, hand-computed from the same lines ---------------

    expected = {
        "bulk": "failed",
        "fast": {"status": "done", "text": "wrote:f1"},
        "flaky": "running",
        "fragile": "expired",
        "ghost": "pending",
        "hopeless": {"status": "failed", "text": "gave-up"},
        "slow": "running",
    }
    states = s.state_of(lines)
    assert states == expected, (
        "the state table is not the one these 22 lines spell:\n  got  %r\n"
        "  want %r" % (states, expected))
    assert s.state_of(tuple(src)) == expected, (
        "the same lines folded from their field bags disagree: %r"
        % (s.state_of(tuple(src)),))
    assert tuple(states) == tuple(sorted(expected)), (
        "the table is not sorted by job id: %r" % (tuple(states),))
    assert len(states) == 7, (
        "the log names seven jobs, the table has %d" % (len(states),))
    assert "run-1" not in states, (
        "the table invented a job from the `start` line's key: %r"
        % (tuple(states),))
    for value in states.values():
        status = value if isinstance(value, str) else value["status"]
        assert status in SIX, (
            "the table says %r, which is not one of the six statuses %s"
            % (status, ", ".join(SIX)))

    # fresh: the same lines fold to an equal table, never to the same object
    again = s.state_of(lines)
    assert again == expected and again is not states, (
        "a state table must be a fresh mapping: two folds returned the same "
        "object, so one caller's edit is another's state")
    states["slow"] = "expired"
    assert s.state_of(lines) == expected, (
        "a fold handed back a table it had kept: an edit to it changed the next "
        "fold")

    # ---- the newest claim decides, and not the last line ------------------

    assert lines[-1]["kind"] == "done" and "job" not in lines[-1], (
        "the fixture's last line was meant to name no job at all: %r"
        % (lines[-1],))
    assert lines[-2] == {"tick": 20, "kind": "intent", "job": "ghost",
                         "key": "ghost-key"}, (
        "the last line that names a job was meant to be an `intent`: %r"
        % (lines[-2],))
    assert expected["ghost"] == "pending", (
        "`ghost` is named by an `intent` that decides nothing, so it is "
        "`pending`, not %r" % (expected["ghost"],))
    assert expected["flaky"] == "running", (
        "`flaky` is claimed by w1, fails, is retried and claimed by w2, so the "
        "newest claim decides: `running`, not %r" % (expected["flaky"],))
    assert expected["fragile"] == "expired", (
        "`fragile`'s expire is its newest decision, so `expired`, not %r"
        % (expected["fragile"],))
    assert expected["fast"] == {"status": "done", "text": "wrote:f1"}, (
        "`fast` finished and its own owner's later `expire` cannot overwrite "
        "that: %r" % (expected["fast"],))

    # ---- one decision at a time ------------------------------------------

    def claim(job, owner, tick, ticks=5):
        return {"tick": tick, "kind": "claim", "job": job, "owner": owner,
                "ticks": ticks}

    def result(job, owner, status, tick, **rest):
        entry = {"tick": tick, "kind": "result", "job": job, "owner": owner,
                 "status": status, "ticks": 1}
        entry.update(rest)
        return entry

    assert s.state_of(()) == {}, (
        "an empty journal has no jobs, the table says %r" % (s.state_of(()),))
    assert s.state_of(()) is not s.state_of(()), (
        "two folds of an empty journal returned the same object")
    assert s.state_of((claim("fast", "w1", 0),)) == {"fast": "running"}, (
        "one claim leaves one running job: %r"
        % (s.state_of((claim("fast", "w1", 0),)),))
    assert s.state_of(({"tick": 0, "kind": "start", "key": "run-1",
                        "text": "plan:abc"},
                       {"tick": 1, "kind": "done"})) == {}, (
        "a `start` and a `done` name no job, and the table must invent none: %r"
        % (s.state_of(({"tick": 0, "kind": "start", "key": "run-1",
                        "text": "plan:abc"},
                       {"tick": 1, "kind": "done"})),))
    assert s.state_of(({"tick": 0, "kind": "intent", "job": "ghost",
                        "key": "ghost-key"},)) == {"ghost": "pending"}, (
        "a job an `intent` names and nothing else decides is `pending`, not %r"
        % (s.state_of(({"tick": 0, "kind": "intent", "job": "ghost",
                        "key": "ghost-key"},)),))

    # `died` is a failed attempt, and a result with no detail has no record
    assert s.state_of((claim("bulk", "w1", 0),
                       result("bulk", "w1", "died", 1))) == {"bulk": "failed"}, (
        "an attempt that died is a failed job: %r"
        % (s.state_of((claim("bulk", "w1", 0),
                       result("bulk", "w1", "died", 1))),))
    assert s.state_of((claim("fast", "w1", 0),
                       result("fast", "w1", "ok", 1))) == {"fast": "done"}, (
        "a result that carried no detail is the plain status, not a record: %r"
        % (s.state_of((claim("fast", "w1", 0),
                       result("fast", "w1", "ok", 1))),))
    assert s.state_of((claim("fast", "w1", 0),
                       result("fast", "w1", "ok", 1, text="wrote:f1"))) == {
        "fast": {"status": "done", "text": "wrote:f1"}}, (
        "a result that carried a detail is a record: %r"
        % (s.state_of((claim("fast", "w1", 0),
                       result("fast", "w1", "ok", 1, text="wrote:f1"))),))

    # a retry re-issues the job and drops the outcome before it
    assert s.state_of((claim("flaky", "w1", 0),
                       result("flaky", "w1", "failed", 1, text="boom"),
                       {"tick": 2, "kind": "retry", "job": "flaky",
                        "ticks": 2})) == {"flaky": "pending"}, (
        "a retried job is pending again, with no outcome to report: %r"
        % (s.state_of((claim("flaky", "w1", 0),
                       result("flaky", "w1", "failed", 1, text="boom"),
                       {"tick": 2, "kind": "retry", "job": "flaky",
                        "ticks": 2})),))

    # a beat cannot revive an expired lease, and an expire belongs to its owner
    assert s.state_of((claim("slow", "w1", 0),
                       {"tick": 1, "kind": "expire", "job": "slow",
                        "owner": "w1"},
                       {"tick": 2, "kind": "beat", "job": "slow",
                        "owner": "w1", "ticks": 9})) == {"slow": "expired"}, (
        "a beat renames a deadline; it does not revive an expired lease: %r"
        % (s.state_of((claim("slow", "w1", 0),
                       {"tick": 1, "kind": "expire", "job": "slow",
                        "owner": "w1"},
                       {"tick": 2, "kind": "beat", "job": "slow",
                        "owner": "w1", "ticks": 9})),))
    assert s.state_of((claim("slow", "w1", 0),
                       {"tick": 1, "kind": "expire", "job": "slow",
                        "owner": "w2"})) == {"slow": "running"}, (
        "an expire for an owner that does not hold the job decides nothing: %r"
        % (s.state_of((claim("slow", "w1", 0),
                       {"tick": 1, "kind": "expire", "job": "slow",
                        "owner": "w2"})),))
    assert s.state_of(({"tick": 0, "kind": "expire", "job": "ghost",
                        "owner": "w1"},)) == {"ghost": "pending"}, (
        "an expire can only end a running lease, so a job nobody holds stays "
        "pending: %r"
        % (s.state_of(({"tick": 0, "kind": "expire", "job": "ghost",
                        "owner": "w1"},)),))

    # ---- a line that does not parse is refused by index and text ----------

    bad = world.Disk()
    bad.write(world.DEFAULT_JOURNAL, "0 clai job=fast\n")
    message = _refuses(s.ReplayError, "a journal whose line names no kind",
                       lambda: s.replay(bad))
    assert "line 0" in message and "0 clai job=fast" in message, (
        "the refusal of a line with no kind does not name its index and its "
        "text: %r" % (message,))

    bad = world.Disk()
    bad.write(world.DEFAULT_JOURNAL,
              s1.line(0, "start", key="run-1", text="plan:abc") + "\n"
              + "1 claim job=fast\n")
    message = _refuses(s.ReplayError, "a journal whose second line has no owner",
                       lambda: s.replay(bad))
    assert "line 1" in message and "owner" in message, (
        "the refusal of a claim with no owner does not name the line's index "
        "and the field that broke: %r" % (message,))

    bad = world.Disk()
    bad.write(world.DEFAULT_JOURNAL, "0 done\n\n")
    message = _refuses(s.ReplayError, "a journal with a blank line in it",
                       lambda: s.replay(bad))
    assert "line 1" in message, (
        "a blank line in the middle is a line that does not parse, and the "
        "refusal must name it: %r" % (message,))

    # ---- a torn tail is refused, and nothing is repaired -----------------

    torn_text = s1.line(0, "start", key="run-1", text="plan:abc")
    tail = world.Disk()
    tail.write(world.DEFAULT_JOURNAL, torn_text)
    message = _refuses(s.ReplayError,
                       "a journal whose line was never terminated",
                       lambda: s.replay(tail))
    assert "line 0" in message and torn_text in message, (
        "the refusal of a torn tail does not name its index and its text: %r"
        % (message,))
    assert s.torn(tail.read(world.DEFAULT_JOURNAL)) == 0, (
        "`torn` and `replay` disagree about the same unfinished tail")
    assert tail.read(world.DEFAULT_JOURNAL) == torn_text, (
        "the refusal repaired the log it read: %r"
        % (tail.read(world.DEFAULT_JOURNAL),))
    assert tail.synced(world.DEFAULT_JOURNAL) == "", (
        "the refusal synced the torn tail it refused")

    half = world.Disk()
    half.write(world.DEFAULT_JOURNAL, "0 done\n1 cla")
    message = _refuses(s.ReplayError, "a journal whose last append was cut short",
                       lambda: s.replay(half))
    assert "line 1" in message and "1 cla" in message and "torn" in message, (
        "the refusal of a half-written tail does not name its index, its text "
        "and what it is: %r" % (message,))
    assert s.torn(half.read(world.DEFAULT_JOURNAL)) == 1, (
        "`torn` found no tail in a journal that ends without a terminator")

    empty = world.Disk()
    assert s.replay(empty) == (), (
        "a journal that was never written holds no lines: %r" % (s.replay(empty),))

    # ---- the refusals of a reader that was handed the wrong thing --------

    message = _refuses(s.ReplayError, "a replay with no disk",
                       lambda: s.replay(None))
    assert "None" in message, (
        "the refusal of a missing disk does not name it: %r" % (message,))
    message = _refuses(s.ReplayError, "a replay with an empty path",
                       lambda: s.replay(world.Disk(), ""))
    assert "''" in message, (
        "the refusal of an empty path does not name it: %r" % (message,))
    message = _refuses(s.ReplayError, "a replay with a path that is not a str",
                       lambda: s.replay(world.Disk(), 5))
    assert "5" in message, (
        "the refusal of a path that is not a str does not name it: %r"
        % (message,))
    message = _refuses(s.ReplayError, "a replay with a relative path",
                       lambda: s.replay(world.Disk(), "var/log/durable/journal"))
    assert "var/log/durable/journal" in message, (
        "the refusal of a relative path does not name it: %r" % (message,))

    message = _refuses(s.ReplayError, "a table folded from a journal's text",
                       lambda: s.state_of("0 done\n"))
    assert "0 done" in message, (
        "the refusal of a str where a journal's lines belong does not name it: "
        "%r" % (message,))
    message = _refuses(s.ReplayError, "a table folded from a line that is text",
                       lambda: s.state_of(("0 done\n",)))
    assert "line 0" in message, (
        "the refusal of a raw line does not name its index: %r" % (message,))
    message = _refuses(s.ReplayError, "a table folded from a kind of the nine",
                       lambda: s.state_of(({"tick": 0, "kind": "clai",
                                            "job": "fast"},)))
    assert "clai" in message, (
        "the refusal of a kind that is not one of the nine does not name it: %r"
        % (message,))
    message = _refuses(s.ReplayError, "a claim with no owner",
                       lambda: s.state_of(({"tick": 0, "kind": "claim",
                                            "job": "fast"},)))
    assert "owner" in message and "claim" in message, (
        "the refusal of a claim with no owner does not name the kind and the "
        "field: %r" % (message,))
    message = _refuses(s.ReplayError, "a claim with no job",
                       lambda: s.state_of(({"tick": 0, "kind": "claim",
                                            "owner": "w1"},)))
    assert "job" in message and "claim" in message, (
        "the refusal of a claim that names no job does not name the kind and "
        "the missing field: %r" % (message,))
    message = _refuses(s.ReplayError, "a result with no status",
                       lambda: s.state_of(({"tick": 0, "kind": "result",
                                            "job": "fast", "owner": "w1"},)))
    assert "status" in message, (
        "the refusal of a result with no status does not name it: %r"
        % (message,))

    # ---- `torn` is a question, and it changes nothing ---------------------

    assert s.torn("") is None, (
        "a journal that was never written has no tail: %r" % (s.torn(""),))
    assert s.torn("0 done\n") is None, (
        "a journal that ended with its terminator has no tail: %r"
        % (s.torn("0 done\n"),))
    assert s.torn(("0 done", "")) is None, (
        "a blank tail is not torn, it is what a finished journal looks like")
    assert s.torn([]) is None, (
        "no lines at all is no tail: %r" % (s.torn([]),))
    assert s.torn("0 done") == 0, (
        "a single line with no terminator is the whole tail: %r"
        % (s.torn("0 done"),))
    assert s.torn("0 done\n1 claim job=fast owner=w1") == 1, (
        "the second of two lines was never terminated, so the tail is at 1: %r"
        % (s.torn("0 done\n1 claim job=fast owner=w1"),))
    assert s.torn(("0 done", "1 claim job=fast owner=w1")) == 1, (
        "the pieces of a journal answer the same question as its text: %r"
        % (s.torn(("0 done", "1 claim job=fast owner=w1")),))
    assert s.torn(["0 done", "1 claim job=fast owner=w1"]) == 1, (
        "a list of a journal's pieces is a journal's pieces: %r"
        % (s.torn(["0 done", "1 claim job=fast owner=w1"]),))
    assert s.torn("0 done\n1 claim job=fast owner=w1\n") is None, (
        "the same two lines, terminated, have no tail: %r"
        % (s.torn("0 done\n1 claim job=fast owner=w1\n"),))

    kept = tail.read(world.DEFAULT_JOURNAL)
    assert s.torn(kept) == 0, "`torn` did not find the tail it was asked about"
    assert tail.read(world.DEFAULT_JOURNAL) == kept, (
        "`torn` changed the log it read: %r"
        % (tail.read(world.DEFAULT_JOURNAL),))
    assert tail.synced(world.DEFAULT_JOURNAL) == "", (
        "`torn` synced what it read")

    message = _refuses(s.ReplayError, "a journal's lines given as a number",
                       lambda: s.torn(5))
    assert "5" in message, (
        "the refusal of a journal's lines given as a number does not name it: "
        "%r" % (message,))
    message = _refuses(s.ReplayError, "a journal whose second piece is not text",
                       lambda: s.torn(("0 done", 5)))
    assert "1" in message and "5" in message, (
        "the refusal of a piece that is not text does not name its index and "
        "its value: %r" % (message,))
    message = _refuses(s.ReplayError, "a mapping handed where lines belong",
                       lambda: s.torn({"0 done": True}))
    assert "0 done" in message, (
        "the refusal of a mapping where a journal's lines belong does not name "
        "it: %r" % (message,))

    print("check_03: the reader — a journal of 22 hand-written lines replays to "
          "exactly the field bags stage 1 wrote, a torn tail is refused by index "
          "and text (parseable or not) while nothing is repaired, `torn` answers "
          "where the unfinished tail sits of a text or of its pieces and calls a "
          "blank tail finished, and the state table folds seven jobs out of the "
          "same lines — the newest claim decides, a done job is not expired by a "
          "later expire, a retried job is pending and a beat revives nothing")

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate,
                                              "durable-execution-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import disk as world
    import stage_01 as one
    import stage_04 as s

    # ---- the refusal family -----------------------------------------------

    assert issubclass(s.LeaseError, one.DurableError), (
        "%r is not a %s: one `except DurableError` must still catch a lease that "
        "is refused" % (s.LeaseError, one.DurableError.__name__))
    assert issubclass(s.LeaseError, ValueError), (
        "%r is not a ValueError: the course's refusal is a named error a caller "
        "can catch" % (s.LeaseError,))

    # ---- claim: one whole line, and the lease it spells, hand-computed -----

    journal = world.Disk()
    lease = s.claim(journal, "fast", "w1", now=3, ticks=5)
    assert journal.files() == (world.DEFAULT_JOURNAL,), (
        "claim wrote to %r, not the world's journal %r"
        % (journal.files(), world.DEFAULT_JOURNAL))
    expected = "3 claim job=fast owner=w1 ticks=5\n"
    assert journal.read(world.DEFAULT_JOURNAL) == expected, (
        "the journal reads %r, not the claim line the lease was taken with (%r)"
        % (journal.read(world.DEFAULT_JOURNAL), expected))
    assert lease == {"job": "fast", "owner": "w1", "deadline": 8,
                     "claimed_at": 3}, (
        "the lease of a claim at 3 for 5 ticks is %r, not "
        "{'job': 'fast', 'owner': 'w1', 'deadline': 8, 'claimed_at': 3}"
        % (lease,))
    assert sorted(lease) == ["claimed_at", "deadline", "job", "owner"], (
        "a lease carries %r, not the four fields a reader of the log needs: "
        "job, owner, deadline and claimed_at" % (sorted(lease),))
    assert lease["deadline"] == 3 + 5 == 8, (
        "the deadline of a claim at 3 with 5 ticks is %r, not 3 + 5"
        % (lease["deadline"],))
    # a claim is written, not synced: whether it is durable is the caller's
    # decision, and a lease that dies with the process is stage 10's material
    assert journal.synced(world.DEFAULT_JOURNAL) == "", (
        "claim synced the journal (%r): a claim is a line like any other, and "
        "stage 2 owns the sync" % (journal.synced(world.DEFAULT_JOURNAL),))
    assert not journal.durable(world.DEFAULT_JOURNAL, expected), (
        "the claim line is already durable: a write is not durable until a sync")

    # a second job claims alongside, and the journal is append-only
    second = s.claim(journal, "slow", "w2", now=3, ticks=4)
    assert second == {"job": "slow", "owner": "w2", "deadline": 7,
                      "claimed_at": 3}, (
        "a claim at 3 for 4 ticks gave %r, not a deadline of 7" % (second,))
    assert journal.read(world.DEFAULT_JOURNAL) == (
        expected + "3 claim job=slow owner=w2 ticks=4\n"), (
        "the journal reads %r: a second claim appends, it does not replace"
        % (journal.read(world.DEFAULT_JOURNAL),))

    # the lease the caller got is the lease the next process reads off the log
    lines = [one.parse_line(raw)
             for raw in journal.read(world.DEFAULT_JOURNAL).split("\n") if raw]
    assert lines == [
        {"tick": 3, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 5},
        {"tick": 3, "kind": "claim", "job": "slow", "owner": "w2", "ticks": 4},
    ], ("the journal parsed to %r, not the two claims that were written"
        % (lines,))
    assert s.lease_of(lines, "fast") == lease, (
        "the lease off the log is %r, not the lease claim handed back (%r): a "
        "lease is data, and the next process reads it out of the journal"
        % (s.lease_of(lines, "fast"), lease))
    assert s.lease_of(lines, "slow") == second, (
        "slow's lease off the log is %r, not %r"
        % (s.lease_of(lines, "slow"), second))

    # ---- claim refuses a live lease, and the boundary is the deadline ------

    held = world.Disk()
    first = s.claim(held, "fast", "w1", now=3, ticks=5)
    assert first["deadline"] == 8, (
        "the lease is %r, not one with a deadline of 8" % (first,))
    before = held.read(world.DEFAULT_JOURNAL)
    # one tick before the deadline the job is still w1's — and the claim that
    # decided that was never synced, so claim read the journal it can *see*
    message = _refuses(s.LeaseError, "a claim one tick before the deadline",
                       lambda: s.claim(held, "fast", "w2", now=7, ticks=5))
    assert "'w1'" in message and "'fast'" in message, (
        "the refusal of a claim over a live lease does not name the job and the "
        "owner holding it: %r" % (message,))
    assert "8" in message, (
        "the refusal does not say until when the lease is held: %r" % (message,))
    assert held.read(world.DEFAULT_JOURNAL) == before, (
        "a refused claim still wrote %r"
        % (held.read(world.DEFAULT_JOURNAL)[len(before):],))
    # the owner that holds it may not claim it twice either: a live lease is a
    # live lease, and a second claim is a second line saying something else
    message = _refuses(s.LeaseError, "the holder claiming its own live lease",
                       lambda: s.claim(held, "fast", "w1", now=4, ticks=5))
    assert "'w1'" in message and "'fast'" in message, (
        "the refusal of a second claim by the holder does not name both: %r"
        % (message,))
    # at exactly the deadline the lease is over: deadline <= now, inclusive
    taken = s.claim(held, "fast", "w2", now=8, ticks=5)
    assert taken == {"job": "fast", "owner": "w2", "deadline": 13,
                     "claimed_at": 8}, (
        "a claim at exactly the deadline (8) is %r, not a lease with a deadline "
        "of 8 + 5" % (taken,))
    assert taken["deadline"] == 13, (
        "the lease taken at 8 for 5 ticks has deadline %r, not 13"
        % (taken["deadline"],))
    assert held.read(world.DEFAULT_JOURNAL) == (
        before + "8 claim job=fast owner=w2 ticks=5\n"), (
        "the journal reads %r: a claim at the deadline is allowed and appends"
        % (held.read(world.DEFAULT_JOURNAL),))
    # and now w2's lease (until 13) is the one a claim at 12 must respect
    message = _refuses(s.LeaseError, "a claim one tick before the second deadline",
                       lambda: s.claim(held, "fast", "w1", now=12, ticks=1))
    assert "'w2'" in message and "13" in message, (
        "the refusal does not name the new owner and the new deadline: %r"
        % (message,))

    # ---- lease_of: the newest claim, and the plan is not the log's business --

    two = [
        {"tick": 3, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 5},
        {"tick": 6, "kind": "result", "job": "fast", "owner": "w1",
         "status": "died", "ticks": 3},
        {"tick": 9, "kind": "claim", "job": "fast", "owner": "w2", "ticks": 4},
        {"tick": 9, "kind": "claim", "job": "slow", "owner": "w3", "ticks": 2},
    ]
    newest = s.lease_of(two, "fast")
    assert newest == {"job": "fast", "owner": "w2", "deadline": 13,
                      "claimed_at": 9}, (
        "the newest claim for fast is w2's at 9 for 4 ticks, so the lease is "
        "{'job': 'fast', 'owner': 'w2', 'deadline': 13, 'claimed_at': 9}, not %r"
        % (newest,))
    assert newest["deadline"] == 9 + 4 == 13, (
        "the deadline of the newest claim is %r, not 9 + 4"
        % (newest["deadline"],))
    assert s.lease_of(two, "slow") == {"job": "slow", "owner": "w3",
                                      "deadline": 11, "claimed_at": 9}, (
        "slow's lease is %r, not a deadline of 9 + 2"
        % (s.lease_of(two, "slow"),))
    assert s.lease_of(two, "bulk") is None, (
        "lease_of invented a lease for a job the log never claimed: %r"
        % (s.lease_of(two, "bulk"),))
    assert s.lease_of([], "fast") is None, (
        "lease_of of an empty log is %r, not None" % (s.lease_of([], "fast"),))
    # a lease is a reading, not a handle: editing what came back changes nothing
    newest["owner"] = "w9"
    newest["deadline"] = 99
    assert s.lease_of(two, "fast") == {"job": "fast", "owner": "w2",
                                      "deadline": 13, "claimed_at": 9}, (
        "editing the lease lease_of returned changed what the log says: %r"
        % (s.lease_of(two, "fast"),))
    assert two[2] == {"tick": 9, "kind": "claim", "job": "fast", "owner": "w2",
                      "ticks": 4}, (
        "lease_of rewrote the line it read: %r" % (two[2],))

    message = _refuses(s.LeaseError, "a line that is not a mapping",
                       lambda: s.lease_of([7], "fast"))
    assert "7" in message, (
        "the refusal of the line 7 does not name it: %r" % (message,))
    message = _refuses(s.LeaseError, "a line with no kind",
                       lambda: s.lease_of([{"tick": 3, "job": "fast",
                                            "owner": "w1", "ticks": 5}],
                                          "fast"))
    assert "kind" in message, (
        "the refusal of a line with no kind does not name the field: %r"
        % (message,))
    message = _refuses(s.LeaseError, "a job id that is not a str",
                       lambda: s.lease_of(two, 7))
    assert "7" in message, (
        "the refusal of the job id 7 does not name it: %r" % (message,))
    message = _refuses(s.LeaseError, "a blank job id",
                       lambda: s.lease_of(two, "   "))
    assert "job" in message, (
        "the refusal of a blank job id does not name the field: %r" % (message,))
    message = _refuses(s.LeaseError, "a claim line with no owner",
                       lambda: s.lease_of([{"tick": 3, "kind": "claim",
                                            "job": "fast", "ticks": 5}],
                                          "fast"))
    assert "owner" in message, (
        "the refusal of a claim with no owner does not name the owner: %r"
        % (message,))
    message = _refuses(s.LeaseError, "a claim line with no length",
                       lambda: s.lease_of([{"tick": 3, "kind": "claim",
                                            "job": "fast", "owner": "w1"}],
                                          "fast"))
    assert "ticks" in message, (
        "the refusal of a claim with no length does not name the field that "
        "carries it: %r" % (message,))
    message = _refuses(s.LeaseError, "a claim line of zero length",
                       lambda: s.lease_of([{"tick": 3, "kind": "claim",
                                            "job": "fast", "owner": "w1",
                                            "ticks": 0}], "fast"))
    assert "ticks" in message and "0" in message, (
        "the refusal of a lease of no length does not name the field and the "
        "value: %r" % (message,))

    # ---- expired: the boundary, both sides of it ---------------------------

    at_three = {"job": "fast", "owner": "w1", "deadline": 8, "claimed_at": 3}
    assert s.expired(at_three, 7) is False, (
        "a lease with deadline 8 is not expired at 7, and expired() said %r"
        % (s.expired(at_three, 7),))
    assert s.expired(at_three, 8) is True, (
        "a lease with deadline 8 is expired at exactly 8 (`deadline <= now`), "
        "and expired() said %r" % (s.expired(at_three, 8),))
    assert s.expired(at_three, 9) is True, (
        "a lease with deadline 8 is over at 9, and expired() said %r"
        % (s.expired(at_three, 9),))
    assert s.expired(at_three, 0) is False, (
        "a lease with deadline 8 is not expired at 0, and expired() said %r"
        % (s.expired(at_three, 0),))
    assert s.expired({"job": "fast", "owner": "w1", "deadline": 0,
                      "claimed_at": 0}, 0) is True, (
        "a lease that runs out at the tick it was taken is expired at 0")
    assert type(s.expired(at_three, 8)) is bool, (
        "expired() answered %r, not a bool" % (s.expired(at_three, 8),))

    message = _refuses(s.LeaseError, "a lease that is not a mapping",
                       lambda: s.expired(7, 8))
    assert "7" in message and "lease" in message, (
        "the refusal of the lease 7 does not name it: %r" % (message,))
    message = _refuses(s.LeaseError, "a lease with no deadline",
                       lambda: s.expired({"job": "fast", "owner": "w1",
                                          "claimed_at": 3}, 8))
    assert "deadline" in message, (
        "the refusal of a lease with no deadline does not name it: %r"
        % (message,))
    message = _refuses(s.LeaseError, "a lease with a field a lease does not have",
                       lambda: s.expired(dict(at_three, dead_line=1), 8))
    assert "dead_line" in message and "did you mean 'deadline'" in message, (
        "the refusal of the lease field 'dead_line' does not name it and suggest "
        "its near real field: %r" % (message,))
    message = _refuses(s.LeaseError, "a deadline that is not an int",
                       lambda: s.expired(dict(at_three, deadline="8"), 8))
    assert "deadline" in message and "'8'" in message, (
        "the refusal of the deadline '8' does not name the field and the value: "
        "%r" % (message,))
    message = _refuses(s.LeaseError, "a deadline of True",
                       lambda: s.expired(dict(at_three, deadline=True), 8))
    assert "deadline" in message and "True" in message, (
        "the refusal of the deadline True does not name the field and the "
        "value: %r" % (message,))
    message = _refuses(s.LeaseError, "a negative claimed_at",
                       lambda: s.expired(dict(at_three, claimed_at=-1), 8))
    assert "claimed_at" in message and "-1" in message, (
        "the refusal of the claimed_at -1 does not name the field and the "
        "value: %r" % (message,))
    message = _refuses(s.LeaseError, "a lease with a blank owner",
                       lambda: s.expired(dict(at_three, owner=" "), 8))
    assert "owner" in message, (
        "the refusal of a blank owner does not name the field: %r" % (message,))
    message = _refuses(s.LeaseError, "a lease whose owner is the empty string",
                       lambda: s.expired(dict(at_three, owner=""), 8))
    assert "owner" in message, (
        "the refusal of an empty owner does not name the field: %r"
        % (message,))
    message = _refuses(s.LeaseError, "a now of True",
                       lambda: s.expired(at_three, True))
    assert "now" in message and "True" in message, (
        "the refusal of the now True does not name the tick and the value: %r"
        % (message,))
    message = _refuses(s.LeaseError, "a now of -1",
                       lambda: s.expired(at_three, -1))
    assert "now" in message and "-1" in message, (
        "the refusal of the now -1 does not name the tick and the value: %r"
        % (message,))

    # ---- renew: the same owner, a later deadline ---------------------------

    held_lease = {"job": "fast", "owner": "w1", "deadline": 8, "claimed_at": 3}
    later = s.renew(held_lease, "w1", now=6, ticks=4)
    assert later == {"job": "fast", "owner": "w1", "deadline": 10,
                     "claimed_at": 3}, (
        "a heartbeat at 6 for 4 ticks on a lease with deadline 8 is %r, not "
        "{'job': 'fast', 'owner': 'w1', 'deadline': 10, 'claimed_at': 3}"
        % (later,))
    assert later["deadline"] == 6 + 4 == 10, (
        "the renewed deadline is %r, not now + ticks; the old deadline (8) plus "
        "ticks would be 12, and neither is a heartbeat" % (later["deadline"],))
    assert later["claimed_at"] == 3, (
        "the heartbeat moved claimed_at to %r: a heartbeat extends a lease, it "
        "does not start one, and a reader that saw it move would think a second "
        "worker had taken the job" % (later["claimed_at"],))
    assert held_lease == {"job": "fast", "owner": "w1", "deadline": 8,
                          "claimed_at": 3}, (
        "renew rewrote the lease it was handed: %r" % (held_lease,))
    later["deadline"] = 99
    later["owner"] = "w9"
    assert s.renew(held_lease, "w1", now=6, ticks=4) == {
        "job": "fast", "owner": "w1", "deadline": 10, "claimed_at": 3}, (
        "editing the lease renew returned changed the next renewal: %r"
        % (s.renew(held_lease, "w1", now=6, ticks=4),))

    # a heartbeat from somebody else is a steal, and the refusal names both
    message = _refuses(s.LeaseError, "a heartbeat from a second owner",
                       lambda: s.renew(held_lease, "w2", now=6, ticks=4))
    assert "'w2'" in message and "'w1'" in message, (
        "the refusal of a steal does not name the owner that tried and the owner "
        "that holds: %r" % (message,))
    assert "'fast'" in message, (
        "the refusal of a steal does not name the job: %r" % (message,))
    assert held_lease["deadline"] == 8, (
        "a refused heartbeat still moved the lease: %r" % (held_lease,))

    for bad in (0, -1, True, False, 2.5, "4", None):
        message = _refuses(s.LeaseError, "a heartbeat for %r ticks" % (bad,),
                           lambda bad=bad: s.renew(held_lease, "w1", now=6,
                                                   ticks=bad))
        assert "ticks" in message, (
            "the refusal of a heartbeat for %r ticks does not name the field: %r"
            % (bad, message))
        assert repr(bad) in message, (
            "the refusal of a heartbeat for %r ticks does not name the value: %r"
            % (bad, message))
    message = _refuses(s.LeaseError, "a heartbeat at a now of True",
                       lambda: s.renew(held_lease, "w1", now=True, ticks=4))
    assert "now" in message and "True" in message, (
        "the refusal of a heartbeat at True does not name the tick and the "
        "value: %r" % (message,))
    message = _refuses(s.LeaseError, "a heartbeat by a nameless owner",
                       lambda: s.renew(held_lease, "  ", now=6, ticks=4))
    assert "owner" in message, (
        "the refusal of a nameless owner does not name the field: %r"
        % (message,))
    message = _refuses(s.LeaseError, "a heartbeat on a lease with no claimed_at",
                       lambda: s.renew({"job": "fast", "owner": "w1",
                                        "deadline": 8}, "w1", now=6, ticks=4))
    assert "claimed_at" in message, (
        "the refusal of a lease with no claimed_at does not name it: %r"
        % (message,))

    # ---- claim: a job the plan has not, and a length that is not a length --

    blank = world.Disk()
    message = _refuses(s.LeaseError, "a job the plan does not have",
                       lambda: s.claim(blank, "fst", "w1", now=0, ticks=1))
    assert "'fst'" in message and "did you mean 'fast'" in message, (
        "the refusal of the job 'fst' does not name it and suggest its near real "
        "job: %r" % (message,))
    assert "slow" in message and "bulk" in message, (
        "the refusal of a job the plan has not does not list the plan's jobs: %r"
        % (message,))
    message = _refuses(s.LeaseError, "a job id that is not a str",
                       lambda: s.claim(blank, 7, "w1", now=0, ticks=1))
    assert "7" in message and "job" in message, (
        "the refusal of the job id 7 does not name it: %r" % (message,))
    message = _refuses(s.LeaseError, "a blank owner",
                       lambda: s.claim(blank, "fast", "  ", now=0, ticks=1))
    assert "owner" in message, (
        "the refusal of a blank owner does not name the field: %r" % (message,))
    message = _refuses(s.LeaseError, "an owner that is the empty string",
                       lambda: s.claim(blank, "fast", "", now=0, ticks=1))
    assert "owner" in message, (
        "the refusal of the empty owner does not name the field: %r"
        % (message,))
    message = _refuses(s.LeaseError, "an owner carrying the field separator",
                       lambda: s.claim(blank, "fast", "w 1", now=0, ticks=1))
    assert "owner" in message and "'w 1'" in message, (
        "the refusal of the owner 'w 1' does not name the field and the value: "
        "%r" % (message,))
    message = _refuses(s.LeaseError, "an owner that is not a str",
                       lambda: s.claim(blank, "fast", 7, now=0, ticks=1))
    assert "owner" in message and "7" in message, (
        "the refusal of the owner 7 does not name it: %r" % (message,))
    for bad in (0, -3, True, False, 2.5, "5", None):
        message = _refuses(s.LeaseError, "a claim for %r ticks" % (bad,),
                           lambda bad=bad: s.claim(blank, "fast", "w1", now=0,
                                                   ticks=bad))
        assert "ticks" in message, (
            "the refusal of a claim of %r ticks does not name the field: %r"
            % (bad, message))
        assert repr(bad) in message, (
            "the refusal of a claim of %r ticks does not name the value: %r"
            % (bad, message))
    for bad in (True, -1, 1.5, "3", None):
        message = _refuses(s.LeaseError, "a claim at now = %r" % (bad,),
                           lambda bad=bad: s.claim(blank, "fast", "w1", now=bad,
                                                   ticks=1))
        assert "now" in message, (
            "the refusal of a claim at now = %r does not name the tick: %r"
            % (bad, message))
        assert repr(bad) in message, (
            "the refusal of a claim at now = %r does not name the value: %r"
            % (bad, message))
    assert blank.read(world.DEFAULT_JOURNAL) == "", (
        "a refused claim wrote %r to the journal"
        % (blank.read(world.DEFAULT_JOURNAL),))

    # ---- claim reads the log it was handed, and refuses one it cannot read --

    broken = world.Disk()
    broken.write(world.DEFAULT_JOURNAL, "3 claim job=fast\n")   # no owner
    message = _refuses(s.LeaseError, "a claim over a journal line it cannot read",
                       lambda: s.claim(broken, "fast", "w1", now=4, ticks=2))
    assert "3 claim job=fast" in message, (
        "the refusal does not carry the line it could not read: %r" % (message,))
    assert broken.read(world.DEFAULT_JOURNAL) == "3 claim job=fast\n", (
        "a claim over a journal it cannot read still wrote %r"
        % (broken.read(world.DEFAULT_JOURNAL)[len("3 claim job=fast\n"):],))

    print("check_04: the lease — a claim writes one hand-computed line and not "
          "syncs it, reads the journal it can see back through stage 1's parser, "
          "and refuses a job the plan has not, a nameless owner and a length "
          "that is not a positive int; a live lease is refused one tick before "
          "its deadline and taken at exactly it, `deadline <= now`; lease_of "
          "returns the newest claim as a fresh four-field lease with a computed "
          "deadline (or None), refusing a line it cannot read; and renew moves "
          "the deadline to `now + ticks` while keeping `claimed_at`, refusing a "
          "heartbeat from anybody but the lease's owner")

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate,
                                              "durable-execution-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    from collections.abc import Mapping

    import disk as world
    import stage_01 as one
    import stage_05 as s

    def _log(entries):
        """A journal holding `entries`, and the lines a replay makes of them."""
        journal = world.Disk()
        for entry in entries:
            one.write_line(journal, entry)
        raw = journal.read(world.DEFAULT_JOURNAL)
        return journal, tuple(one.parse_line(item) for item in raw.splitlines())

    # ---- the policy's one constant, and the family of its refusals ---------

    assert s.MAX_MISSES == 2, (
        "MAX_MISSES is %r, not the 2 ticks of grace the stage is about"
        % (s.MAX_MISSES,))
    assert issubclass(s.JournalError, one.DurableError), (
        "%r is not a %s: one `except DurableError` must still catch a heartbeat "
        "refused for a lease that is already expired"
        % (s.JournalError, one.DurableError.__name__))
    for name in ("heartbeat", "dead", "recover", "reclaimable"):
        assert callable(getattr(s, name, None)), (
            "this stage's surface has no %r: the four decisions are the stage"
            % (name,))

    # ---- heartbeat: the beat, and the lease it renews, hand-computed -------

    # a claim at tick 3 that granted 5 ticks has a deadline of 8; a beat at
    # tick 6 that grants 4 ticks is a deadline of 10, and it is the same lease:
    # the same job, the same owner, the same claimed_at
    live = {"job": "fast", "owner": "w1", "deadline": 8, "claimed_at": 3}
    journal = world.Disk()
    renewed = s.heartbeat(journal, live, now=6, ticks=4)
    assert isinstance(renewed, Mapping), (
        "heartbeat returned %r, which is not a lease mapping" % (renewed,))
    assert renewed == {"job": "fast", "owner": "w1", "deadline": 10,
                       "claimed_at": 3}, (
        "a beat at tick 6 granting 4 ticks is the same lease with a deadline of "
        "10 (6 + 4) and its original claimed_at, not %r" % (renewed,))
    assert renewed is not live, (
        "heartbeat returned the lease it was handed: a lease comes off the log "
        "as data, and the caller's copy is not this stage's to keep")
    assert live == {"job": "fast", "owner": "w1", "deadline": 8,
                    "claimed_at": 3}, (
        "heartbeat rewrote the lease it was handed: %r" % (live,))

    beat = "6 beat job=fast owner=w1 ticks=4\n"
    assert world.DEFAULT_JOURNAL == "/var/log/durable/journal", (
        "the world's journal path moved: %r" % (world.DEFAULT_JOURNAL,))
    assert journal.files() == (world.DEFAULT_JOURNAL,), (
        "a heartbeat wrote %r, not the world's journal alone"
        % (journal.files(),))
    assert journal.read(world.DEFAULT_JOURNAL) == beat, (
        "the journal reads %r, not the beat the heartbeat wrote (%r)"
        % (journal.read(world.DEFAULT_JOURNAL), beat))
    # the beat is a line like any other: a prediction until a sync makes it a
    # fact, and stage 2 owns the sync
    assert journal.synced(world.DEFAULT_JOURNAL) == "", (
        "heartbeat synced the beat (%r): a beat is a line, and stage 1's "
        "write_line never syncs" % (journal.synced(world.DEFAULT_JOURNAL),))
    assert not journal.durable(world.DEFAULT_JOURNAL, beat), (
        "the beat a heartbeat wrote is already durable: a write is not durable "
        "until a sync")

    # a second beat appends, and starts from the lease the first one returned:
    # 7 + 6 = 13
    later = s.heartbeat(journal, renewed, now=7, ticks=6)
    assert later == {"job": "fast", "owner": "w1", "deadline": 13,
                     "claimed_at": 3}, (
        "a beat at tick 7 granting 6 ticks is a deadline of 13, not %r"
        % (later,))
    assert journal.read(world.DEFAULT_JOURNAL) == beat + (
        "7 beat job=fast owner=w1 ticks=6\n"), (
        "a second beat appends to the journal, which reads %r"
        % (journal.read(world.DEFAULT_JOURNAL),))
    # the stage writes lines and never syncs: a crash loses exactly the beats
    lost = journal.crash()
    assert lost == ((world.DEFAULT_JOURNAL, beat
                     + "7 beat job=fast owner=w1 ticks=6\n"),), (
        "a crash lost %r, not both unsynced beats: heartbeat appended through "
        "disk.write and synced nothing" % (lost,))

    # a beat one tick before the deadline is fine (7 + 1 = 8), and a beat *at*
    # the deadline is already too late: `deadline <= now` is stage 4's boundary
    edge = world.Disk()
    held = s.heartbeat(edge, live, now=7, ticks=1)
    assert held["deadline"] == 8, (
        "a beat at tick 7 granting 1 tick has a deadline of 8, not %r"
        % (held["deadline"],))
    assert edge.read(world.DEFAULT_JOURNAL) == "7 beat job=fast owner=w1 ticks=1\n", (
        "the beat at the deadline's edge landed as %r"
        % (edge.read(world.DEFAULT_JOURNAL),))
    blank = world.Disk()
    message = _refuses(s.JournalError, "a beat exactly at the deadline",
                       lambda: s.heartbeat(blank, live, now=8, ticks=2))
    assert "expired at tick 8" in message and "a beat at tick 8" in message, (
        "the refusal of a beat at the deadline does not name both ticks (the "
        "deadline it passed and the tick it was attempted at): %r" % (message,))
    message = _refuses(s.JournalError, "a beat after the deadline",
                       lambda: s.heartbeat(blank, live, now=12, ticks=2))
    assert "expired at tick 8" in message and "a beat at tick 12" in message, (
        "the refusal of a beat four ticks past the deadline does not name both "
        "ticks: %r" % (message,))
    assert blank.read(world.DEFAULT_JOURNAL) == "" and blank.files() == (), (
        "a refused heartbeat still wrote %r to the journal"
        % (blank.read(world.DEFAULT_JOURNAL),))

    # ---- heartbeat: the lease's shape, the ticks, and the tick ------------

    for what, lease, wanted in (
            ("a lease that is not a mapping", 7, ["must be a mapping"]),
            ("a lease with no deadline",
             {"job": "fast", "owner": "w1", "claimed_at": 3}, ["'deadline'"]),
            ("a lease with no owner",
             {"job": "fast", "deadline": 8, "claimed_at": 3}, ["'owner'"]),
            ("a lease with no job",
             {"owner": "w1", "deadline": 8, "claimed_at": 3}, ["'job'"]),
            ("a lease with no claimed_at",
             {"job": "fast", "owner": "w1", "deadline": 8}, ["'claimed_at'"]),
            ("a lease whose owner is blank",
             {"job": "fast", "owner": "   ", "deadline": 8, "claimed_at": 3},
             ["a lease's owner"]),
            ("a lease whose job is blank",
             {"job": "  ", "owner": "w1", "deadline": 8, "claimed_at": 3},
             ["a lease's job"]),
            ("a lease whose deadline is a bool",
             {"job": "fast", "owner": "w1", "deadline": True,
              "claimed_at": 3}, ["deadline"]),
            ("a lease whose claimed_at is a float",
             {"job": "fast", "owner": "w1", "deadline": 8,
              "claimed_at": 1.5}, ["claimed_at"]),
    ):
        message = _refuses(
            s.JournalError, what,
            lambda lease=lease: s.heartbeat(world.Disk(), lease, now=4, ticks=2))
        for piece in wanted:
            assert piece in message, (
                "the refusal of %s does not name %r: %r" % (what, piece, message))

    for bad in (0, -1, True, False, 1.5, "4", None):
        message = _refuses(
            s.JournalError, "a heartbeat whose ticks is %r" % (bad,),
            lambda bad=bad: s.heartbeat(world.Disk(), live, now=4, ticks=bad))
        assert "a heartbeat's ticks" in message, (
            "the refusal of a ticks of %r is not this stage's: a beat that "
            "grants no time is a lease that expires where it stands: %r"
            % (bad, message))
        assert repr(bad) in message, (
            "the refusal of a ticks of %r does not name the value: %r"
            % (bad, message))

    for bad in (True, -1, 1.5, "6", None):
        message = _refuses(
            s.JournalError, "a heartbeat at %r" % (bad,),
            lambda bad=bad: s.heartbeat(world.Disk(), live, now=bad, ticks=2))
        assert "a heartbeat is written at" in message, (
            "the refusal of the tick %r is not this stage's: a heartbeat is "
            "written at a tick, and that tick is what the journal records: %r"
            % (bad, message))
        assert repr(bad) in message, (
            "the refusal of the tick %r does not name the value: %r"
            % (bad, message))

    # ---- dead: the exact tick the grace flips, hand-computed --------------

    # the lease of a claim at tick 3 granting 5 ticks: deadline 8. At 8 and 9 the
    # owner has missed 0 and 1 beats; at 10 it has missed MAX_MISSES = 2, which
    # is where a slow owner becomes a dead one
    judged = {"job": "fast", "owner": "w1", "deadline": 8, "claimed_at": 3}
    for now, want in ((8, False), (9, False), (10, True), (11, True)):
        got = s.dead(judged, now=now, misses=now - judged["deadline"])
        assert got is want, (
            "a lease whose deadline was 8, read at tick %d with %d missed beats, "
            "is dead=%r, not %r: the grace is MAX_MISSES (%d) ticks after the "
            "deadline, so it flips at 10"
            % (now, now - judged["deadline"], got, want, s.MAX_MISSES))
    # each half of the policy on its own
    assert s.dead(judged, now=8, misses=2) is True, (
        "a lease expired at the deadline with MAX_MISSES beats missed is dead")
    assert s.dead(judged, now=8, misses=1) is False, (
        "one missed beat is a slow owner, not a dead one")
    assert s.dead(judged, now=7, misses=2) is False, (
        "a lease inside its deadline is alive however many beats were counted: "
        "the deadline is what the owner promised, and the grace starts after it")
    assert s.dead(judged, now=100, misses=0) is False, (
        "an expired lease whose owner just wrote a beat is alive: the count is "
        "the observation and the deadline is the promise")
    assert judged == {"job": "fast", "owner": "w1", "deadline": 8,
                      "claimed_at": 3}, (
        "dead rewrote the lease it was judging: %r" % (judged,))

    message = _refuses(s.JournalError, "judging a lease that is not a mapping",
                       lambda: s.dead(7, now=9, misses=2))
    assert "must be a mapping" in message, (
        "the refusal of the lease 7 does not say what a lease is: %r" % (message,))
    message = _refuses(s.JournalError, "judging a lease with no deadline",
                       lambda: s.dead({"job": "fast", "owner": "w1",
                                       "claimed_at": 3}, now=9, misses=2))
    assert "'deadline'" in message, (
        "the refusal of a lease with no deadline does not name the field: %r"
        % (message,))
    for bad in (True, -1, 1.5, "9", None):
        message = _refuses(
            s.JournalError, "judging a lease at %r" % (bad,),
            lambda bad=bad: s.dead(judged, now=bad, misses=2))
        assert "the tick a lease is judged at" in message, (
            "the refusal of the tick %r does not name it: %r" % (bad, message))
    for bad in (True, -1, 1.5, "2", None):
        message = _refuses(
            s.JournalError, "judging a lease with %r missed beats" % (bad,),
            lambda bad=bad: s.dead(judged, now=9, misses=bad))
        assert "the beats an owner missed" in message, (
            "the refusal of the count %r does not name it: %r" % (bad, message))

    # ---- recover: a live lease stays running ------------------------------

    journal, lines = _log([
        {"tick": 0, "kind": "start", "key": "run-1", "text": "plan:h1"},
        {"tick": 3, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 5},
    ])
    before = (journal.read(world.DEFAULT_JOURNAL),
              journal.synced(world.DEFAULT_JOURNAL), journal.files())
    # hand-computed: the claim at tick 3 granted 5 ticks, so the deadline is 8
    assert s.recover(lines, now=5) == {"fast": "running"}, (
        "a claim at 3 granting 5 ticks is a lease with a deadline of 8, so at "
        "tick 5 the job is running, not %r" % (s.recover(lines, now=5),))
    assert s.reclaimable(lines, now=5) == (), (
        "a job whose owner is inside its deadline is not reclaimable: %r"
        % (s.reclaimable(lines, now=5),))
    # the same lines, read tick by tick through the grace: expired at 8, still
    # alive at 9, and dead at 8 + MAX_MISSES = 10
    assert s.recover(lines, now=8) == {"fast": "running"}, (
        "at the deadline the lease is expired but not yet dead, and the grace "
        "of MAX_MISSES ticks has not been spent: %r" % (s.recover(lines, now=8),))
    assert s.reclaimable(lines, now=8) == (), (
        "a lease one tick into its grace is not reclaimable yet: %r"
        % (s.reclaimable(lines, now=8),))
    assert s.recover(lines, now=9) == {"fast": "running"}, (
        "at 9 the owner has missed one beat, and one missed beat is a slow "
        "worker: %r" % (s.recover(lines, now=9),))
    assert s.recover(lines, now=10) == {"fast": "expired"}, (
        "a lease with deadline 8 whose owner has been silent for 2 = MAX_MISSES "
        "ticks is dead, and the job is expired, not %r"
        % (s.recover(lines, now=10),))
    assert s.reclaimable(lines, now=10) == ("fast",), (
        "the slot a dead owner held is reclaimable: %r"
        % (s.reclaimable(lines, now=10),))
    assert s.recover(lines, now=99) == {"fast": "expired"}, (
        "a lease never beaten only gets deader: %r" % (s.recover(lines, now=99),))
    # recovery is a reading: the journal it was handed is untouched
    journal_now = (journal.read(world.DEFAULT_JOURNAL),
                   journal.synced(world.DEFAULT_JOURNAL), journal.files())
    assert journal_now == before, (
        "recover wrote to the journal: %r, was %r" % (journal_now, before))

    # ---- recover: a beat renames a deadline, for its own lease only --------

    journal, lines = _log([
        {"tick": 3, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 5},
        {"tick": 4, "kind": "beat", "job": "fast", "owner": "w1", "ticks": 9},
    ])
    # hand-computed: the beat at 4 granted 9, so the deadline is 13 — running at
    # 12 and at 14 (one missed beat), expired at 15 (two)
    assert s.recover(lines, now=12) == {"fast": "running"}, (
        "the beat moved the deadline to 4 + 9 = 13, so at 12 the job runs: %r"
        % (s.recover(lines, now=12),))
    assert s.recover(lines, now=14) == {"fast": "running"}, (
        "one missed beat after a deadline of 13 is not death yet: %r"
        % (s.recover(lines, now=14),))
    assert s.recover(lines, now=15) == {"fast": "expired"}, (
        "13 + MAX_MISSES = 15 is where a lease whose last beat was at 4 dies: %r"
        % (s.recover(lines, now=15),))
    assert s.reclaimable(lines, now=15) == ("fast",), (
        "reclaimable at 15 is %r" % (s.reclaimable(lines, now=15),))

    # a beat for a job no claim ever took names the job and nothing more: a beat
    # is evidence about a lease, and there is no lease here to be evidence about
    journal, lines = _log([
        {"tick": 4, "kind": "beat", "job": "bulk", "owner": "w3", "ticks": 5},
    ])
    assert s.recover(lines, now=4) == {"bulk": "pending"}, (
        "a beat for a job that was never claimed leaves the job claimed by "
        "nobody, not %r" % (s.recover(lines, now=4),))
    assert s.reclaimable(lines, now=4) == (), (
        "a job no owner ever held is not a dead owner's slot: %r"
        % (s.reclaimable(lines, now=4),))

    journal, lines = _log([
        {"tick": 3, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 2},
        {"tick": 4, "kind": "beat", "job": "fast", "owner": "w9", "ticks": 50},
    ])
    assert s.recover(lines, now=6) == {"fast": "running"}, (
        "w1's lease has deadline 3 + 2 = 5, one tick into its grace at 6: %r"
        % (s.recover(lines, now=6),))
    assert s.recover(lines, now=7) == {"fast": "expired"}, (
        "a beat by w9 is not a heartbeat for w1's lease: its deadline is still "
        "5, and at 7 w1 has missed 2 = MAX_MISSES beats, so the job is %r"
        % (s.recover(lines, now=7),))
    assert s.reclaimable(lines, now=7) == ("fast",), (
        "the slot w1 died holding is reclaimable: %r"
        % (s.reclaimable(lines, now=7),))

    # ---- recover: the newest claim is what a recovery believes -------------

    journal, lines = _log([
        {"tick": 1, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 1},
        {"tick": 5, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 10},
    ])
    assert s.recover(lines, now=14) == {"fast": "running"}, (
        "the newest claim, at 5 granting 10, has a deadline of 15 — not the "
        "first claim's 2 — so the job runs at 14: %r"
        % (s.recover(lines, now=14),))
    assert s.recover(lines, now=17) == {"fast": "expired"}, (
        "15 + MAX_MISSES = 17 is where the newest claim's lease dies: %r"
        % (s.recover(lines, now=17),))

    # a claim after a result: the newest claim is the one that counts, so a job
    # whose newest owner never answered is expired even though somebody finished
    # an attempt of it
    journal, lines = _log([
        {"tick": 3, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 3},
        {"tick": 6, "kind": "result", "job": "fast", "owner": "w1",
         "status": "ok", "ticks": 1, "text": "done"},
        {"tick": 7, "kind": "claim", "job": "fast", "owner": "w2", "ticks": 3},
    ])
    assert s.recover(lines, now=9) == {"fast": "running"}, (
        "w2 claimed at 7 granting 3, so the deadline is 10 and the job runs at "
        "9: %r" % (s.recover(lines, now=9),))
    assert s.recover(lines, now=20) == {"fast": "expired"}, (
        "w2's lease, deadline 10, is dead at 20 and w2 never answered: the job "
        "is expired, not %r" % (s.recover(lines, now=20),))
    assert s.reclaimable(lines, now=20) == ("fast",), (
        "reclaimable at 20 is %r" % (s.reclaimable(lines, now=20),))

    # ---- recover: a finished job keeps what the log says -------------------

    journal, lines = _log([
        {"tick": 3, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 1},
        {"tick": 4, "kind": "result", "job": "fast", "owner": "w1",
         "status": "ok", "ticks": 1, "text": "done"},
    ])
    assert s.recover(lines, now=99) == {"fast": {"status": "done",
                                                 "text": "done"}}, (
        "a done result is the log's last word on the job, long after its lease "
        "would have died: %r" % (s.recover(lines, now=99),))
    assert s.reclaimable(lines, now=99) == (), (
        "a finished job is not reclaimable: %r" % (s.reclaimable(lines, now=99),))
    # a result with no detail is a bare status, exactly as contract §3.2 reads
    journal, lines = _log([
        {"tick": 3, "kind": "claim", "job": "slow", "owner": "w2", "ticks": 1},
        {"tick": 4, "kind": "result", "job": "slow", "owner": "w2",
         "status": "failed", "ticks": 1},
    ])
    assert s.recover(lines, now=4) == {"slow": "failed"}, (
        "a result with no text is a failed job with no detail, not %r"
        % (s.recover(lines, now=4),))
    # and an expire line does not overwrite a result
    journal, lines = _log([
        {"tick": 3, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 1},
        {"tick": 4, "kind": "result", "job": "fast", "owner": "w1",
         "status": "ok", "ticks": 1},
        {"tick": 9, "kind": "expire", "job": "fast", "owner": "w1"},
    ])
    assert s.recover(lines, now=9) == {"fast": "done"}, (
        "an expire line does not overwrite a result: the job finished, and %r "
        "is a job re-issued after it was done" % (s.recover(lines, now=9),))
    # and the same holds of a done job that carries the worker's own detail
    journal, lines = _log([
        {"tick": 3, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 1},
        {"tick": 4, "kind": "result", "job": "fast", "owner": "w1",
         "status": "ok", "ticks": 1, "text": "done"},
        {"tick": 9, "kind": "expire", "job": "fast", "owner": "w1"},
    ])
    assert s.recover(lines, now=9) == {"fast": {"status": "done",
                                                "text": "done"}}, (
        "an expire line does not overwrite a done job that carries a detail, "
        "either: %r" % (s.recover(lines, now=9),))

    # ---- recover: expire, retry, and the jobs the log only names ----------

    journal, lines = _log([
        {"tick": 3, "kind": "claim", "job": "slow", "owner": "w2", "ticks": 2},
        {"tick": 9, "kind": "expire", "job": "slow", "owner": "w2"},
    ])
    assert s.recover(lines, now=20) == {"slow": "expired"}, (
        "the log says the lease ran out: %r" % (s.recover(lines, now=20),))
    assert s.reclaimable(lines, now=20) == ("slow",), (
        "reclaimable at 20 is %r" % (s.reclaimable(lines, now=20),))

    journal, lines = _log([
        {"tick": 3, "kind": "claim", "job": "slow", "owner": "w2", "ticks": 1},
        {"tick": 9, "kind": "retry", "job": "slow", "ticks": 2},
    ])
    assert s.recover(lines, now=99) == {"slow": "pending"}, (
        "a re-issued job is waiting for a claim, and the lease its dead owner "
        "held is gone with the line that re-issued it: %r"
        % (s.recover(lines, now=99),))
    assert s.reclaimable(lines, now=99) == (), (
        "a job recovery re-issued is not a dead owner's slot to reclaim: %r"
        % (s.reclaimable(lines, now=99),))

    journal, lines = _log([
        {"tick": 3, "kind": "claim", "job": "slow", "owner": "w2", "ticks": 1},
        {"tick": 9, "kind": "expire", "job": "slow", "owner": "w2"},
        {"tick": 9, "kind": "retry", "job": "slow", "ticks": 2},
    ])
    assert s.recover(lines, now=99) == {"slow": "pending"}, (
        "a re-issued job is waiting for a claim, and its old lease is gone: %r"
        % (s.recover(lines, now=99),))
    assert s.reclaimable(lines, now=99) == (), (
        "a job recovery already re-issued is not re-issued a second time: %r"
        % (s.reclaimable(lines, now=99),))

    journal, lines = _log([
        {"tick": 5, "kind": "intent", "job": "bulk", "key": "effect:bulk"},
    ])
    assert s.recover(lines, now=5) == {"bulk": "pending"}, (
        "a line that names a job without claiming it names it as claimed by "
        "nobody: %r" % (s.recover(lines, now=5),))
    assert s.reclaimable(lines, now=5) == (), (
        "a job no owner ever held is not a dead owner's slot: %r"
        % (s.reclaimable(lines, now=5),))

    journal, lines = _log([
        {"tick": 0, "kind": "start", "key": "run-1", "text": "plan:h1"},
        {"tick": 9, "kind": "done"},
    ])
    assert s.recover(lines, now=9) == {}, (
        "a run that began and has nothing left names no job, and a recovery "
        "invents no state for a job the log never mentioned: %r"
        % (s.recover(lines, now=9),))

    # a claim that granted no ticks has a deadline where it stands
    assert s.recover(({"tick": 4, "kind": "claim", "job": "fast",
                       "owner": "w1"},), now=4) == {"fast": "running"}, (
        "a claim with no ticks granted none, so its deadline is 4 and the job "
        "runs at 4: %r"
        % (s.recover(({"tick": 4, "kind": "claim", "job": "fast",
                       "owner": "w1"},), now=4),))
    assert s.recover(({"tick": 4, "kind": "claim", "job": "fast",
                       "owner": "w1"},), now=6) == {"fast": "expired"}, (
        "a claim with a deadline of 4 is dead at 4 + MAX_MISSES = 6")
    assert s.reclaimable(({"tick": 4, "kind": "claim", "job": "fast",
                           "owner": "w1"},), now=6) == ("fast",), (
        "reclaimable at 6 is %r"
        % (s.reclaimable(({"tick": 4, "kind": "claim", "job": "fast",
                           "owner": "w1"},), now=6),))

    # ---- recover: sorted, fresh, and nothing the log never named ----------

    journal, lines = _log([
        {"tick": 1, "kind": "claim", "job": "slow", "owner": "w1", "ticks": 1},
        {"tick": 2, "kind": "claim", "job": "bulk", "owner": "w2", "ticks": 1},
    ])
    states = s.recover(lines, now=99)
    assert tuple(states) == ("bulk", "slow"), (
        "the recovered table is id-sorted, not in the order the log named the "
        "jobs (slow, bulk): %r" % (tuple(states),))
    assert states == {"bulk": "expired", "slow": "expired"}, (
        "both leases are dead at 99, so both jobs are expired: %r" % (states,))
    assert s.reclaimable(lines, now=99) == ("bulk", "slow"), (
        "reclaimable is sorted: %r" % (s.reclaimable(lines, now=99),))

    # ---- recover: a record stage 1 would refuse is refused by name --------

    for what, lines, wanted in (
            ("a line that is not a mapping", (7,), ["at index 0", "7"]),
            ("a line with no kind", ({"tick": 0},), ["at index 0", "kind"]),
            ("a kind outside the nine",
             ({"tick": 0, "kind": "clai", "job": "fast"},),
             ["'clai'", "at index 0"]),
            ("a claim with no owner",
             ({"tick": 0, "kind": "claim", "job": "fast", "ticks": 1},),
             ["owner", "claim"]),
            ("a field a line has no vocabulary for",
             ({"tick": 0, "kind": "done", "tickz": 1},), ["tickz"]),
    ):
        message = _refuses(s.JournalError, what,
                           lambda lines=lines: s.recover(lines, now=0))
        for piece in wanted:
            assert piece in message, (
                "the refusal of %s does not name %r: %r" % (what, piece, message))
    message = _refuses(s.JournalError, "a recovery handed a journal's text",
                       lambda: s.recover("0 done\n", now=0))
    assert repr("0 done\n") in message, (
        "the refusal of a journal's text does not name the text: a str is not a "
        "list of line records: %r" % (message,))
    for bad in (True, -1, 1.5, "9", None):
        message = _refuses(
            s.JournalError, "recovery at %r" % (bad,),
            lambda bad=bad: s.recover(lines, now=bad))
        assert "the tick a recovery reads the log at" in message, (
            "the refusal of the tick %r does not name it: %r" % (bad, message))
    message = _refuses(s.JournalError, "reclaimable at a bad tick",
                       lambda: s.reclaimable(lines, now=-1))
    assert "the tick a recovery reads the log at" in message, (
        "reclaimable read the log at a tick that is not a tick: %r" % (message,))

    print("check_05: the heartbeat — a beat writes one line at the world's "
          "journal, renames the deadline to now + ticks and syncs nothing; a "
          "beat at an expired lease is refused naming both ticks; the grace "
          "flips from running to dead at exactly deadline + MAX_MISSES; and a "
          "recovery reads the state a process that just woke up must believe — "
          "live leases running, dead ones expired, finished jobs as the log "
          "says — writing nothing")

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate,
                                              "durable-execution-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _journal(*lines):
        """A disk holding these lines durably, at the world's journal path."""
        import disk as world

        store = world.Disk()
        for text in lines:
            store.write(world.DEFAULT_JOURNAL, text)
        store.sync()
        return store

    from collections.abc import Mapping

    import disk as world
    import stage_01 as first
    import stage_06 as s

    # ---- the surface, and the shrinking vocabulary ------------------------

    assert s.MAX_MISSES == 2, (
        "the grace a lease past its deadline gets is %r, not the two ticks "
        "stage 5 hands the recovery" % (s.MAX_MISSES,))
    assert issubclass(s.RecoveryError, first.DurableError), (
        "%r is not a %s: one `except DurableError` must still catch a journal "
        "a recovery refuses" % (s.RecoveryError, first.DurableError.__name__))
    J = world.DEFAULT_JOURNAL
    assert J == "/var/log/durable/journal", (
        "the world's journal path moved: %r" % (J,))

    # ---- the kill: only what survived it is believed ----------------------

    # hand-computed, line by line. The crashed process believed SIX lines; the
    # disk had synced FIVE. `fast`'s lease was re-deadlined by its own beat to
    # 4 + 9 = 13, so at now=12 it is 12 >= 13 + 2? No — running. `slow`'s lease
    # died at 5 + 3 = 8 and `bulk`'s at 5 + 2 = 7, so both are expired at 12,
    # and the `result` that would have finished `slow` was written and NEVER
    # synced: it did not happen.
    keeper = ("0 start key=run-1 text=plan:h1\n"
              "3 claim job=fast owner=w1 ticks=5\n"
              "4 beat job=fast owner=w1 ticks=9\n"
              "5 claim job=slow owner=w2 ticks=3\n"
              "5 claim job=bulk owner=w3 ticks=2\n")
    ghost = "9 result job=slow owner=w2 status=ok ticks=1 text=done\n"
    journal = world.Disk()
    journal.write(J, keeper)
    journal.sync()
    journal.write(J, ghost)
    assert journal.read(J) == keeper + ghost and journal.synced(J) == keeper, (
        "the fixture is wrong: the volatile buffer must hold %r and the disk %r"
        % (ghost, keeper))
    believed = tuple(first.parse_line(text)
                     for text in (keeper + ghost).rstrip("\n").split("\n"))
    assert len(believed) == 6, "the crashed process believed six lines"

    lost, survivors, states = s.crash(journal, believed, now=12)
    assert isinstance(lost, tuple) and isinstance(survivors, tuple), (
        "crash returned %r, not the `(lost, lines, states)` triple"
        % (lost, survivors, states))
    assert lost == ((J, ghost),), (
        "the kill lost %r, not exactly the line that was written and never "
        "synced (%r)" % (lost, ghost))
    assert survivors == (
        {"tick": 0, "kind": "start", "key": "run-1", "text": "plan:h1"},
        {"tick": 3, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 5},
        {"tick": 4, "kind": "beat", "job": "fast", "owner": "w1", "ticks": 9},
        {"tick": 5, "kind": "claim", "job": "slow", "owner": "w2", "ticks": 3},
        {"tick": 5, "kind": "claim", "job": "bulk", "owner": "w3", "ticks": 2},
        {"tick": 12, "kind": "expire", "job": "bulk", "owner": "w3"},
        {"tick": 12, "kind": "expire", "job": "slow", "owner": "w2"},
    ), (
        "the log after the kill is %r, not the five lines that survived plus "
        "one `expire` per dead owner at tick 12, in job-id order" % (survivors,))
    assert states == {"bulk": "expired", "fast": "running", "slow": "expired"}, (
        "the states after the kill are %r, not the hand-computed table" % (states,))
    assert not [entry for entry in survivors if entry["kind"] == "result"], (
        "the unsynced `result` survived the kill: a write that was not synced "
        "did not happen, so `slow` is expired — a job no disk agreed to finish")
    assert journal.synced(J) == (
        keeper + "12 expire job=bulk owner=w3\n"
        "12 expire job=slow owner=w2\n"), (
        "the journal reads %r durably after the kill, not the surviving lines "
        "plus the two `expire` lines the dead owners are owed"
        % (journal.synced(J),))
    assert journal.read(J) == journal.synced(J) and journal.volatile() == (), (
        "the recovery's own decision is still volatile: an expire line a second "
        "crash could lose is not a decision")

    # the kill is not repeatable business: the log now says what the recovery
    # decided, so the same call finds nothing to lose and nothing to add
    again_lost, again_lines, again_states = s.crash(journal, survivors, now=12)
    assert (again_lost, again_lines, again_states) == ((), survivors, states), (
        "a second kill over the log the first one wrote lost %r and changed the "
        "log to %r: a recovery that re-decides what the log already says writes "
        "an expire line per call" % (again_lost, again_lines))

    # ---- recovered: the same states, from the disk alone ------------------

    assert s.recovered(journal, now=12) == states, (
        "recovered() read %r from the disk the kill left, not the states the "
        "kill returned (%r)" % (s.recovered(journal, now=12), states))
    alone = _journal(keeper)
    assert s.recovered(alone, now=12) == states, (
        "the disk alone yields %r, not the states the process that crashed "
        "would have come back to (%r)" % (s.recovered(alone, now=12), states))
    assert alone.read(J) == keeper and alone.volatile() == (), (
        "recovered() wrote to the journal (%r): a recovery that reads is not a "
        "recovery that acts" % (alone.read(J),))
    assert sorted(states) == ["bulk", "fast", "slow"], (
        "the table holds %r: a recovery reports exactly the ids the log names"
        % (sorted(states),))
    assert not set(states) & {"flaky", "fragile", "hopeless"}, (
        "the table invents a plan job the log never named: %r" % (sorted(states),))
    assert s.recovered(world.Disk(), now=0) == {}, (
        "a journal that was never written yields %r, not the empty table"
        % (s.recovered(world.Disk(), now=0),))

    # the volatile buffer is not the log: a `result` the disk would lose cannot
    # finish a job, and a crash proves the line was never there
    volatile = world.Disk()
    volatile.write(J, "3 claim job=fast owner=w1 ticks=9\n")
    volatile.sync()
    volatile.write(J, "9 result job=fast owner=w1 status=ok ticks=1 text=done\n")
    assert s.recovered(volatile, now=6) == {"fast": "running"}, (
        "recovered() read the volatile buffer: `fast`'s claim re-deadlines it to "
        "3 + 9 = 12, so at now=6 it is running unless a result the disk would "
        "lose is believed (%r)" % (s.recovered(volatile, now=6),))
    assert s.crash(volatile, (), now=6)[0] == (
        (J, "9 result job=fast owner=w1 status=ok ticks=1 text=done\n"),), (
        "the kill did not report the volatile `result` it discarded")

    # ---- stage 5's policy: the grace boundary, hand-computed -------------

    # a claim at 3 for five ticks has deadline 8: at now=8 and now=9 the owner
    # has not yet missed two ticks and may still beat, at now=10 it has
    edge = _journal("3 claim job=fast owner=w1 ticks=5\n")
    assert s.recovered(edge, now=8) == {"fast": "running"}, (
        "a lease whose deadline is exactly now was declared dead: the deadline "
        "is not the death, the grace is")
    assert s.recovered(edge, now=9) == {"fast": "running"}, (
        "one tick of grace is not MAX_MISSES: 9 < 8 + 2 leaves the owner time")
    assert s.recovered(edge, now=10) == {"fast": "expired"}, (
        "at 10 = 8 + 2 the owner has missed both beats and the job is expired")

    # ---- the lease is read out of the log --------------------------------

    # a beat from somebody who is not the lease's owner is a steal, not a
    # renewal: `fast`'s deadline stays 3 + 5 = 8, so at 12 it is expired
    thief = _journal("3 claim job=fast owner=w1 ticks=5\n"
                     "6 beat job=fast owner=w2 ticks=20\n")
    assert s.recovered(thief, now=12) == {"fast": "expired"}, (
        "a beat from `w2` renewed `w1`'s lease (%r): a heartbeat from somebody "
        "else is the steal this course refuses" % (s.recovered(thief, now=12),))
    owner = _journal("3 claim job=fast owner=w1 ticks=5\n"
                     "6 beat job=fast owner=w1 ticks=20\n")
    assert s.recovered(owner, now=12) == {"fast": "running"}, (
        "the owner's own beat left the deadline at 8 (%r): a beat moves it to "
        "6 + 20 = 26" % (s.recovered(owner, now=12),))

    # the NEWEST claim decides: a retry re-issues a failed attempt, and the
    # re-claim at 10 for nine ticks dies at 19 + 2 = 21, so 20 is running
    reissued = _journal("3 claim job=fast owner=w1 ticks=5\n"
                        "9 result job=fast owner=w1 status=failed ticks=1 text=boom\n"
                        "9 retry job=fast ticks=2\n"
                        "10 claim job=fast owner=w2 ticks=9\n")
    assert s.recovered(reissued, now=20) == {"fast": "running"}, (
        "the re-issued job reads %r: the newest claim (deadline 19) decides, not "
        "the first one (deadline 8)" % (s.recovered(reissued, now=20),))
    tail = _journal("3 claim job=fast owner=w1 ticks=5\n"
                    "9 result job=fast owner=w1 status=failed ticks=1 text=boom\n"
                    "9 retry job=fast ticks=2\n")
    assert s.recovered(tail, now=20) == {"fast": "pending"}, (
        "a job the log re-issued and nobody holds reads %r, not pending: a "
        "`retry` clears the lease and the finished attempt" % (s.recovered(tail, now=20),))
    assert s.crash(tail, (), now=20)[1] == tuple(
        first.parse_line(text) for text in
        ("3 claim job=fast owner=w1 ticks=5",
         "9 result job=fast owner=w1 status=failed ticks=1 text=boom",
         "9 retry job=fast ticks=2")), (
        "the recovery wrote an expire line for a job nothing holds")

    # ---- what finishes a job, and what does not overwrite it -------------

    # an `expire` line a previous recovery wrote is believed while nothing has
    # finished the job — even before the grace is spent
    marked = _journal("3 claim job=fast owner=w1 ticks=5\n"
                      "9 expire job=fast owner=w1\n")
    assert s.recovered(marked, now=9) == {"fast": "expired"}, (
        "the `expire` line a previous recovery wrote reads %r at now=9: the log "
        "already decided, and 8 + 2 is not the only way to be expired"
        % (s.recovered(marked, now=9),))
    assert s.crash(marked, (), now=9)[1] == tuple(
        first.parse_line(text) for text in
        ("3 claim job=fast owner=w1 ticks=5", "9 expire job=fast owner=w1")), (
        "the recovery wrote a second `expire` line for a job the log already "
        "expired")

    # an expire is NOT believed once the owner wrote a result — that is the
    # mistake catalogue's "an expire line believed for a job whose owner wrote a
    # result" — and a later expire does not overwrite a finished job either
    late = _journal("3 claim job=slow owner=w2 ticks=3\n"
                    "9 expire job=slow owner=w2\n"
                    "11 result job=slow owner=w2 status=ok ticks=1 text=late\n")
    assert s.recovered(late, now=30) == {"slow": {"status": "done", "text": "late"}}, (
        "a job whose owner answered after an `expire` reads %r: the result is "
        "newer than the expire and the worker's own detail travels with it"
        % (s.recovered(late, now=30),))
    after = _journal("3 claim job=slow owner=w2 ticks=3\n"
                     "9 result job=slow owner=w2 status=ok ticks=1\n"
                     "20 expire job=slow owner=w2\n")
    assert s.recovered(after, now=30) == {"slow": "done"}, (
        "a later `expire` overwrote a `done` (%r): a state the log never "
        "decided, and `done` carries no detail when the result wrote none"
        % (s.recovered(after, now=30),))
    # a re-claim is a new attempt: it clears the failed attempt before it (so the
    # job is not "finished") and the expire before it (so it is running) — the
    # lease of the newest claim is the only one the recovery reads
    retaken = _journal("3 claim job=fast owner=w1 ticks=5\n"
                       "9 result job=fast owner=w1 status=failed ticks=1 text=boom\n"
                       "20 claim job=fast owner=w2 ticks=5\n")
    assert s.recovered(retaken, now=30) == {"fast": "expired"}, (
        "a job re-claimed at 20 for five ticks reads %r at 30, not expired: the "
        "new lease died at 20 + 5 + 2 = 27, and the failed attempt before it was "
        "cleared by the re-claim" % (s.recovered(retaken, now=30),))
    revived = _journal("3 claim job=fast owner=w1 ticks=5\n"
                       "9 expire job=fast owner=w1\n"
                       "20 claim job=fast owner=w2 ticks=5\n")
    assert s.recovered(revived, now=22) == {"fast": "running"}, (
        "a re-claim over an `expire` reads %r at 22: the new lease (deadline 25) "
        "overrides the expire the old one earned" % (s.recovered(revived, now=22),))
    again = _journal("3 claim job=fast owner=w1 ticks=5\n"
                     "9 expire job=fast owner=w1\n"
                     "12 retry job=fast ticks=2\n")
    assert s.recovered(again, now=30) == {"fast": "pending"}, (
        "a job re-issued after an `expire` reads %r: a `retry` clears the lease "
        "and the expire with it, and nobody holds it" % (s.recovered(again, now=30),))
    stale = _journal("3 claim job=fast owner=w1 ticks=5\n"
                     "9 expire job=fast owner=w1\n"
                     "20 claim job=fast owner=w2 ticks=5\n"
                     "21 expire job=fast owner=w1\n")
    assert s.recovered(stale, now=22) == {"fast": "running"}, (
        "an expire naming an owner that no longer holds the lease reads %r at "
        "22: the standing lease is `w2`'s (deadline 25), and a stale expire "
        "for `w1` decides nothing" % (s.recovered(stale, now=22),))

    assert s.recovered(_journal("9 result job=slow owner=w2 status=failed ticks=1"
                                " text=boom\n"), now=30) == {
        "slow": {"status": "failed", "text": "boom"}}, (
        "a failed attempt is not `failed` with its own detail")
    assert s.recovered(_journal("9 result job=slow owner=w2 status=died ticks=1\n"),
                       now=30) == {"slow": "failed"}, (
        "a worker that died is not a failed attempt, and a result with no detail "
        "is a bare status")

    # a job the log names without ever claiming it is pending, not running
    named = _journal("5 intent job=bulk key=effect:bulk\n"
                     "9 effect job=bulk key=effect:bulk\n")
    assert s.recovered(named, now=30) == {"bulk": "pending"}, (
        "a job the log names and never claims reads %r, not pending: nobody "
        "holds a lease it never took" % (s.recovered(named, now=30),))

    # ---- a journal a recovery refuses ------------------------------------

    torn = _journal("0 start key=run-1 text=plan:h1\n"
                    "3 claim job=fast owner=w1 ticks=5\n"
                    "6 res")
    message = _refuses(s.RecoveryError, "a torn tail in recovered()",
                       lambda: s.recovered(torn, now=9))
    assert "torn" in message and "line 2" in message and "6 res" in message, (
        "the refusal of the torn tail does not name the index and the text: %r"
        % (message,))
    message = _refuses(s.RecoveryError, "a torn tail in crash()",
                       lambda: s.crash(torn, (), now=9))
    assert "torn" in message and "line 2" in message and "6 res" in message, (
        "the kill's refusal of the torn tail does not name the index and the "
        "text: %r" % (message,))
    assert torn.read(J) == ("0 start key=run-1 text=plan:h1\n"
                            "3 claim job=fast owner=w1 ticks=5\n6 res"), (
        "a refused recovery wrote to the journal it refused: %r"
        % (torn.read(J),))

    broken = _journal("0 start key=run-1 text=plan:h1\n", "0 bogus job=fast\n")
    message = _refuses(s.RecoveryError, "a line a recovery cannot parse",
                       lambda: s.recovered(broken, now=1))
    assert "line 1" in message and "0 bogus job=fast" in message, (
        "the refusal of an unparseable line does not name its index and its "
        "text: %r" % (message,))

    # ---- the tick, and the kill that must not happen before it ----------

    for bad in (True, False, -1, 2.5, "9", None):
        message = _refuses(s.RecoveryError, "recovered() at now=%r" % (bad,),
                           lambda bad=bad: s.recovered(alone, now=bad))
        assert "now" in message and repr(bad) in message, (
            "the refusal of now=%r does not name it: %r" % (bad, message))
        message = _refuses(s.RecoveryError, "crash() at now=%r" % (bad,),
                           lambda bad=bad: s.crash(world.Disk(), (), now=bad))
        assert "now" in message and repr(bad) in message, (
            "the kill's refusal of now=%r does not name it: %r" % (bad, message))
    untouched = world.Disk()
    untouched.write(J, "0 start key=run-1 text=plan:h1\n")
    _refuses(s.RecoveryError, "a kill at a tick that is not a tick",
             lambda: s.crash(untouched, (), now=True))
    assert untouched.read(J) == "0 start key=run-1 text=plan:h1\n", (
        "a refused kill discarded the volatile buffer anyway: the tick is "
        "checked before the disk is killed")

    # ---- the path, and the world's default -------------------------------

    other = world.Disk()
    other.write("/var/log/durable/other", "3 claim job=fast owner=w1 ticks=5\n")
    other.sync()
    assert s.recovered(other, now=9, path="/var/log/durable/other") == {
        "fast": "running"}, (
        "recovered() ignored its `path`: the journal it was pointed at holds a "
        "claim that should read running")
    assert s.recovered(other, now=9) == {}, (
        "recovered() fell back to a path of its own instead of the world's "
        "journal %r" % (J,))

    print("check_06: crash — the kill discards exactly the unsynced line, the "
          "survivors are re-read from disk.synced so the lines the caller "
          "believed decide nothing, the dead owners get one synced `expire` line "
          "each in job-id order, and the returned triple is hand-computed; "
          "recovered yields the same states from the disk alone and writes "
          "nothing; the grace boundary flips at deadline + MAX_MISSES; a steal "
          "is not a renewal, the newest claim decides, a `retry` leaves a job "
          "pending, an `expire` is believed only until a result finishes the "
          "job, a job the log never names is never in the table; and a torn tail "
          "is refused by index and text")

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    class _NoSync:
        """A disk that takes a write and cannot make it durable.

        `disk.Disk.sync` always succeeds, so the only way to reach `intent`'s refusal
        is a disk whose sync is a no-op: the line is readable (`read` shows it) and
        not durable (`synced` does not), which is exactly the state `intent` exists to
        refuse to believe.
        """

        def __init__(self, inner):
            self.inner = inner

        def write(self, path, text):
            return self.inner.write(path, text)

        def read(self, path):
            return self.inner.read(path)

        def synced(self, path):
            return self.inner.synced(path)

        def sync(self):
            return 0

    class _Watching:
        """An `Effects` stand-in that looks at the journal while the effect runs.

        Order is the one thing a check cannot see from the outside, and it is the
        whole stage: the `effect` line belongs *after* the effect, never before it.
        So this stand-in reads the disk from inside `apply` and refuses to be applied
        to while the journal already says an effect happened — a log that decides
        before the world does is a log the world can contradict.
        """

        def __init__(self, disk, path):
            self.disk = disk
            self.path = path
            self.applied_keys = ()

        def count(self, key):
            return sum(1 for applied in self.applied_keys if applied == key)

        def apply(self, key, value, *, tick):
            for raw in self.disk.read(self.path).split("\n"):
                tokens = raw.split()
                assert len(tokens) < 2 or tokens[1] != "effect", (
                    "the journal already carries an effect line while the effect for "
                    "%r is being applied: the line is written after the effect, "
                    "never before it" % (key,))
            self.applied_keys = self.applied_keys + (key,)
            return {"tick": tick, "key": key, "value": value}

    def _repo(start=None):
        for candidate_start in (os.environ.get("J3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate,
                                              "durable-execution-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import disk as world
    import stage_01 as one
    import stage_07 as s
    import work

    # ---- the vocabulary this stage adds -----------------------------------

    assert s.INTENT_TICK == 0, (
        "an intent line is written at tick 0 (a promise is not an event on the "
        "clock), got %r" % (s.INTENT_TICK,))
    assert issubclass(s.EffectError, one.DurableError), (
        "%r is not a %s: one `except DurableError` must still catch a broken "
        "effect" % (s.EffectError, one.DurableError.__name__))
    assert issubclass(s.EffectError, ValueError), (
        "%r is not a ValueError: the course's refusals are named errors a "
        "caller can catch" % (s.EffectError,))

    job = work.job("fast")
    assert (job.id, job.key, job.value) == ("fast", "effect:fast", "fast done"), (
        "the fixture moved: %r" % (job,))

    # ---- intent(): the line, synced, before anything runs -----------------

    disk = world.Disk()
    intent_text = "0 intent job=fast key=effect:fast\n"
    length = s.intent(disk, "fast", "effect:fast")
    assert length == len(intent_text), (
        "intent returned %r, not the journal's new length (%r)"
        % (length, len(intent_text)))
    # a second intent for the same job is a second line: the log is append-only
    # and nothing deduplicates a promise — the retry announces its intent too
    second_intent = s.intent(disk, "fast", "effect:fast")
    assert second_intent == 2 * len(intent_text), (
        "a second intent appended to a journal of %r bytes returned %r, not %r"
        % (len(intent_text), second_intent, 2 * len(intent_text)))
    assert disk.synced(world.DEFAULT_JOURNAL) == 2 * intent_text, (
        "the intents are not durable: disk.synced holds %r, and an intent that a "
        "crash can lose is not an intent"
        % (disk.synced(world.DEFAULT_JOURNAL),))
    assert disk.read(world.DEFAULT_JOURNAL) == 2 * intent_text, (
        "the journal reads %r, not the two intent lines that were written"
        % (disk.read(world.DEFAULT_JOURNAL),))
    assert one.parse_line(intent_text.strip()) == {
        "tick": 0, "kind": "intent", "job": "fast", "key": "effect:fast"}, (
        "the intent line is not the line its fields spell: %r"
        % (intent_text.strip(),))
    assert disk.files() == (world.DEFAULT_JOURNAL,), (
        "intent wrote to %r, not the world's journal %r"
        % (disk.files(), world.DEFAULT_JOURNAL))

    message = _refuses(s.EffectError, "an intent with a blank job id",
                       lambda: s.intent(world.Disk(), "  ", "effect:fast"))
    assert "job" in message, (
        "the refusal of a blank job id does not name the field: %r" % (message,))
    message = _refuses(s.EffectError, "an intent with an empty key",
                       lambda: s.intent(world.Disk(), "fast", ""))
    assert "key" in message, (
        "the refusal of an empty key does not name the field: %r" % (message,))
    message = _refuses(s.EffectError, "an intent with a job id that is not a str",
                       lambda: s.intent(world.Disk(), 7, "effect:fast"))
    assert "7" in message, (
        "the refusal does not name the job id it refused: %r" % (message,))
    message = _refuses(s.EffectError, "a key carrying whitespace",
                       lambda: s.intent(world.Disk(), "fast", "effect fast"))
    assert "effect fast" in message, (
        "the refusal of a key carrying the field separator does not name it: %r"
        % (message,))
    # a caller that cannot sync has not announced an intent, and must not be
    # told the effect may run
    message = _refuses(s.EffectError, "an intent on a disk that cannot sync",
                       lambda: s.intent(_NoSync(world.Disk()), "fast",
                                        "effect:fast"))
    assert "fast" in message and "effect:fast" in message, (
        "the refusal of an intent that could not be made durable does not name "
        "the job and the key: %r" % (message,))

    # ---- apply_effect(): applied, keyed, and the line comes after ---------

    disk = world.Disk()
    effects = work.Effects()
    s.intent(disk, "fast", "effect:fast")
    got = s.apply_effect(disk, effects, job, tick=6)
    assert got == {"job": "fast", "key": "effect:fast", "value": "fast done",
                   "tick": 6, "decision": "applied",
                   "line": "6 effect job=fast key=effect:fast"}, (
        "the applied effect is %r, not the effect, its key and its line" % (got,))
    assert effects.count("effect:fast") == 1, (
        "the world applied the job's key %d time(s), not once"
        % (effects.count("effect:fast"),))
    assert effects.value("effect:fast") == "fast done", (
        "the effect wrote %r, not the job's own value"
        % (effects.value("effect:fast"),))
    assert effects.log() == ({"tick": 6, "key": "effect:fast",
                              "value": "fast done"},), (
        "the world's log is %r, not one application at the tick it was given"
        % (effects.log(),))
    assert disk.read(world.DEFAULT_JOURNAL) == (
        intent_text + "6 effect job=fast key=effect:fast\n"), (
        "the journal reads %r: the intent comes first and the effect line after "
        "it" % (disk.read(world.DEFAULT_JOURNAL),))
    # the effect line is written, and NOT synced: the intent is the line that
    # must be durable, and the world — not the log — is the proof of the effect
    assert disk.synced(world.DEFAULT_JOURNAL) == intent_text, (
        "the effect line was synced (%r): the intent is the line that must be a "
        "fact before the effect runs, and a crash that loses the effect line "
        "costs nothing a replay cannot ask the effect's key about"
        % (disk.synced(world.DEFAULT_JOURNAL),))
    # ...and that crash really does cost the line and nothing else
    lost = disk.crash()
    assert lost == ((world.DEFAULT_JOURNAL,
                     "6 effect job=fast key=effect:fast\n"),), (
        "the crash lost %r, not the unsynced effect line alone" % (lost,))
    assert effects.count("effect:fast") == 1, (
        "the effect was applied %d time(s) after a crash that lost only its "
        "line" % (effects.count("effect:fast"),))

    # ---- a second call: already applied, and nothing written -------------

    disk = world.Disk()
    effects = work.Effects()
    s.intent(disk, "fast", "effect:fast")
    s.apply_effect(disk, effects, job, tick=6)
    again = s.apply_effect(disk, effects, job, tick=9)
    assert again["decision"] == "already", (
        "a second call for a key the log already proves answered %r, not "
        "'already': it must not apply the effect twice"
        % (again["decision"],))
    assert effects.count("effect:fast") == 1, (
        "the second call applied the effect again: count is %d"
        % (effects.count("effect:fast"),))
    assert disk.read(world.DEFAULT_JOURNAL) == (
        intent_text + "6 effect job=fast key=effect:fast\n"), (
        "the second call wrote %r: a key the log already proves gets no second "
        "line" % (disk.read(world.DEFAULT_JOURNAL),))
    assert disk.read(world.DEFAULT_JOURNAL).count("effect job=") == 1, (
        "the journal holds %d effect lines for one job"
        % (disk.read(world.DEFAULT_JOURNAL).count("effect job="),))

    # ---- a disk that has no journal at all -------------------------------

    disk = world.Disk()
    effects = work.Effects()
    fresh = s.apply_effect(disk, effects, job, tick=1)
    assert fresh["decision"] == "applied", (
        "a key the world has never seen on a disk with no journal at all was "
        "%r, not applied" % (fresh["decision"],))
    assert disk.read(world.DEFAULT_JOURNAL) == (
        "1 effect job=fast key=effect:fast\n"), (
        "the journal of a disk that had none reads %r, not the one effect line"
        % (disk.read(world.DEFAULT_JOURNAL),))
    assert effects.count("effect:fast") == 1, (
        "the effect on an empty disk was applied %d time(s)"
        % (effects.count("effect:fast"),))

    # ---- the crash between the effect and its line: recorded -------------

    disk = world.Disk()
    effects = work.Effects()
    s.intent(disk, "slow", "effect:slow")
    effects.apply("effect:slow", "slow done", tick=5)   # the world has it...
    recorded = s.apply_effect(disk, effects, work.job("slow"), tick=7)
    assert recorded == {"job": "slow", "key": "effect:slow",
                        "value": "slow done", "tick": 7,
                        "decision": "recorded",
                        "line": "7 effect job=slow key=effect:slow"}, (
        "an effect the world already holds, whose line was lost, is %r, not "
        "'recorded'" % (recorded,))
    assert effects.count("effect:slow") == 1, (
        "the world applied the key a second time (%d applications): a crash "
        "between the effect and its line must not apply it again"
        % (effects.count("effect:slow"),))
    assert disk.read(world.DEFAULT_JOURNAL) == (
        "0 intent job=slow key=effect:slow\n7 effect job=slow key=effect:slow\n"), (
        "the journal reads %r, not the intent and the recorded effect line"
        % (disk.read(world.DEFAULT_JOURNAL),))

    # ---- the line is written after the effect, not before ----------------

    disk = world.Disk()
    s.intent(disk, "bulk", "effect:bulk")
    watching = _Watching(disk, world.DEFAULT_JOURNAL)
    watched = s.apply_effect(disk, watching, work.job("bulk"), tick=5)
    assert watched["decision"] == "applied", (
        "the effect was %r, not applied, on a disk whose journal holds only its "
        "intent" % (watched["decision"],))
    assert watching.applied_keys == ("effect:bulk",), (
        "the world was applied to under %r, not under the job's own key"
        % (watching.applied_keys,))
    assert disk.read(world.DEFAULT_JOURNAL) == (
        "0 intent job=bulk key=effect:bulk\n5 effect job=bulk key=effect:bulk\n"), (
        "the journal reads %r: the effect line is written after the effect"
        % (disk.read(world.DEFAULT_JOURNAL),))
    # the journal is read field by field, not searched for the key's text: the
    # intent line carries `key=effect:fast` too
    disk = world.Disk()
    effects = work.Effects()
    s.intent(disk, "fast", "effect:fast")
    alone = s.apply_effect(disk, effects, job, tick=6)
    assert alone["decision"] == "applied", (
        "an intent line carrying the key's text was mistaken for the effect "
        "line: the answer was %r, and the effect was applied %d time(s)"
        % (alone["decision"], effects.count("effect:fast")))

    # ---- settle(): the replay's decision ---------------------------------

    # (a) the crash was between the intent and the effect: nothing landed
    disk = world.Disk()
    effects = work.Effects()
    s.intent(disk, "bulk", "effect:bulk")
    announced = (one.parse_line("0 intent job=bulk key=effect:bulk"),)
    answer = s.settle(disk, effects, announced, work.job("bulk"), tick=8)
    assert answer == "reapply", (
        "a replay of an intent whose effect never landed answered %r, not "
        "'reapply'" % (answer,))
    assert effects.count("effect:bulk") == 1, (
        "the job whose crash was between the intent and the effect ends with its "
        "key applied %d time(s), not once" % (effects.count("effect:bulk"),))
    assert effects.value("effect:bulk") == "x" * 64, (
        "the re-applied effect wrote %r, not the job's own value"
        % (effects.value("effect:bulk"),))
    assert disk.read(world.DEFAULT_JOURNAL) == (
        "0 intent job=bulk key=effect:bulk\n8 effect job=bulk key=effect:bulk\n"), (
        "the settled journal reads %r, not the intent and the effect line it "
        "could not prove before" % (disk.read(world.DEFAULT_JOURNAL),))

    # (b) the effect landed before the crash and only its line was lost
    disk = world.Disk()
    effects = work.Effects()
    s.intent(disk, "slow", "effect:slow")
    effects.apply("effect:slow", "slow done", tick=5)
    answer = s.settle(disk, effects, (
        one.parse_line("0 intent job=slow key=effect:slow"),),
        work.job("slow"), tick=9)
    assert answer == "applied", (
        "a replay of an intent whose effect the world already holds answered "
        "%r, not 'applied'" % (answer,))
    assert effects.count("effect:slow") == 1, (
        "the replay applied an effect the world already had: count is %d"
        % (effects.count("effect:slow"),))
    assert disk.read(world.DEFAULT_JOURNAL) == (
        "0 intent job=slow key=effect:slow\n9 effect job=slow key=effect:slow\n"), (
        "the journal reads %r, not the effect line the replay could prove"
        % (disk.read(world.DEFAULT_JOURNAL),))

    # (c) a log that already proves the effect is left exactly as it is
    proven = (one.parse_line("0 intent job=fast key=effect:fast"),
              one.parse_line("6 effect job=fast key=effect:fast"))
    disk = world.Disk()
    effects = work.Effects()
    effects.apply("effect:fast", "fast done", tick=6)
    answer = s.settle(disk, effects, proven, job, tick=9)
    assert answer == "applied", (
        "a replay whose log already proves the effect answered %r" % (answer,))
    assert disk.read(world.DEFAULT_JOURNAL) == "", (
        "a settled log that already proved its effect was written to (%r)"
        % (disk.read(world.DEFAULT_JOURNAL),))
    assert effects.count("effect:fast") == 1, (
        "the replay applied the effect again: count is %d"
        % (effects.count("effect:fast"),))

    # (d) a job the log never announced an intent for
    message = _refuses(s.EffectError, "a settlement with no intent in the log",
                       lambda: s.settle(world.Disk(), work.Effects(), (), 
                                        work.job("slow"), tick=9))
    assert "slow" in message and "effect:slow" in message, (
        "the refusal of a settlement with no intent does not name the job and "
        "the key: %r" % (message,))
    message = _refuses(s.EffectError, "a settlement over lines that are not a "
                       "sequence",
                       lambda: s.settle(world.Disk(), work.Effects(), 7, job,
                                        tick=9))
    assert "7" in message, (
        "the refusal of a lines that is not a sequence does not name it: %r"
        % (message,))
    message = _refuses(s.EffectError, "a settlement whose line is not a record",
                       lambda: s.settle(world.Disk(), work.Effects(),
                                        ("0 intent job=fast key=effect:fast",),
                                        job, tick=9))
    assert "0 intent job=fast key=effect:fast" in message, (
        "the refusal of a line that is not a record does not name it: %r"
        % (message,))

    # ---- the arguments, refused by name ----------------------------------

    message = _refuses(s.EffectError, "an effect for a job id instead of a job",
                       lambda: s.apply_effect(world.Disk(), work.Effects(),
                                              "fast", tick=6))
    assert "fast" in message, (
        "the refusal of a job that is not a job does not name it: %r"
        % (message,))
    message = _refuses(s.EffectError,
                       "a settlement for a job id instead of a job",
                       lambda: s.settle(world.Disk(), work.Effects(), (), "fast",
                                        tick=6))
    assert "fast" in message, (
        "the refusal of a job that is not a job does not name it: %r"
        % (message,))
    for bad in (True, -1, "6", 1.5, None):
        message = _refuses(s.EffectError, "an effect at tick %r" % (bad,),
                           lambda bad=bad: s.apply_effect(
                               world.Disk(), work.Effects(), job, tick=bad))
        assert repr(bad) in message, (
            "the refusal of the tick %r does not name it: %r" % (bad, message))
    message = _refuses(s.EffectError, "a settlement at tick True",
                       lambda: s.settle(world.Disk(), work.Effects(), (), job,
                                        tick=True))
    assert "True" in message, (
        "the refusal of the tick True does not name it: %r" % (message,))

    # ---- a journal that is not a journal is stage 1's refusal ------------

    disk = world.Disk()
    disk.write(world.DEFAULT_JOURNAL,
               "0 intent job=fast key=effect:fast\nnonsense\n")
    message = _refuses(one.JournalError,
                       "an effect over a journal holding a line that is not a "
                       "line",
                       lambda: s.apply_effect(disk, work.Effects(), job, tick=6))
    assert "nonsense" in message, (
        "the refusal of a broken journal line does not name the line: %r"
        % (message,))
    disk = world.Disk()
    disk.write(world.DEFAULT_JOURNAL,
               "0 intent job=fast key=effect:fast\n\n")
    message = _refuses(one.JournalError,
                       "an effect over a journal with a blank line in it",
                       lambda: s.apply_effect(disk, work.Effects(), job, tick=6))
    assert "empty" in message, (
        "a blank line in the middle of the journal was skipped instead of "
        "refused: %r" % (message,))

    # ---- the key is the job's, not the attempt's -------------------------

    # the accident the whole stage exists to catch, made visible in the data:
    # the same job applied twice under a key derived from the attempt leaves the
    # world with two applications and the plan's own key applied none
    disk = world.Disk()
    effects = work.Effects()
    s.intent(disk, "fast", "fast-1")
    first = s.apply_effect(disk, effects, work.job("fast", key="fast-1"), tick=4)
    s.intent(disk, "fast", "fast-2")
    second = s.apply_effect(disk, effects, work.job("fast", key="fast-2"), tick=6)
    assert (first["decision"], second["decision"]) == ("applied", "applied"), (
        "the two per-attempt keys were %r and %r: each attempt is a new key, so "
        "each is applied afresh and nothing refuses"
        % (first["decision"], second["decision"]))
    assert effects.applied() == ("fast-1", "fast-2"), (
        "the world's applications are %r: a per-attempt key applies the same "
        "work twice" % (effects.applied(),))
    assert effects.count("effect:fast") == 0, (
        "the key the plan named was applied %d time(s): with a per-attempt key "
        "the job's own key is never applied at all, which is how exactly-once "
        "breaks without anything raising" % (effects.count("effect:fast"),))
    assert effects.count("fast-1") == 1 and effects.count("fast-2") == 1, (
        "the two applications are %r and %r"
        % (effects.count("fast-1"), effects.count("fast-2")))
    # ...and under the job's own key the same two attempts leave one application
    disk = world.Disk()
    effects = work.Effects()
    s.intent(disk, "fast", "effect:fast")
    s.apply_effect(disk, effects, job, tick=4)
    s.intent(disk, "fast", "effect:fast")
    third = s.apply_effect(disk, effects, job, tick=6)
    assert third["decision"] == "already", (
        "the second attempt under the plan's key answered %r, not 'already'"
        % (third["decision"],))
    assert effects.applied() == ("effect:fast",), (
        "the world's applications are %r, not the job's one key applied once"
        % (effects.applied(),))

    print("check_07: the intent — one line, hand-computed, written at tick 0 and "
          "synced before anything runs, refused by name when its job id or key "
          "is blank and when the disk cannot make it durable; the effect — "
          "applied under the job's own key, with its line written after it and "
          "never before, unsynced because the world is the proof, answering "
          "'applied', 'already' (no second line, no second application) or "
          "'recorded' (the line written, the world untouched), and reading the "
          "journal field by field instead of searching it for the key; the "
          "settlement — 'applied' when the world already holds the key and "
          "'reapply' when it does not, either way leaving the key applied exactly "
          "once, and refusing a log with no intent, a lines that is not a "
          "sequence and a record that is not a mapping; and the per-attempt key "
          "shown for what it is — two applications under two keys, and the plan's "
          "own key applied zero times")

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate,
                                              "durable-execution-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import disk as world
    import stage_01 as s1
    import stage_08 as s
    import work

    J = world.DEFAULT_JOURNAL

    class Counting(world.Disk):
        """A disk that remembers how many whole-file rewrites and syncs it was
        handed: "a repair with nothing to drop wrote nothing" and "a resume that
        found a checkpoint wrote nothing" are facts about the disk, not about the
        return value."""

        def __init__(self):
            super().__init__()
            self.writes = 0
            self.syncs = 0

        def replace(self, path, text):
            self.writes += 1
            return super().replace(path, text)

        def sync(self):
            self.syncs += 1
            return super().sync()

    def written(path, text):
        """A disk holding `text` durably at `path`."""
        disk = Counting()
        disk.write(path, text)
        disk.sync()
        disk.writes = 0
        disk.syncs = 0
        return disk

    # ---- the vocabulary every later stage speaks --------------------------

    assert world.DEFAULT_JOURNAL == "/var/log/durable/journal", (
        "the world's journal path moved: %r" % (world.DEFAULT_JOURNAL,))
    assert issubclass(s.ResumeError, s1.DurableError), (
        "%r is not a %s: one `except DurableError` must still catch a refused "
        "resume" % (s.ResumeError, s1.DurableError.__name__))
    assert isinstance(s.DEFAULT_CHECKPOINT, str) and s.DEFAULT_CHECKPOINT.startswith(
        world.DEFAULT_JOURNAL) and s.DEFAULT_CHECKPOINT != world.DEFAULT_JOURNAL, (
        "the checkpoint's path is %r: it belongs to the world's journal, beside it "
        "and not on top of it" % (s.DEFAULT_CHECKPOINT,))

    # ---- checkpoint(): a whole file, synced, hand-computed ----------------

    disk = Counting()
    states = {"slow": "running", "fast": {"status": "done", "text": "fine"},
              "fragile": "failed"}
    head = ("7 checkpoint run=run-1 plan=plan-abc "
            "states=fast=done:fine,fragile=failed,slow=running\n")
    length = s.checkpoint(disk, "run-1", "plan-abc", states=states, now=7)
    assert length == len(head), (
        "checkpoint returned %r, not the length of the checkpoint it wrote (%r): a "
        "checkpoint is a whole file, and its length is what the disk reports"
        % (length, len(head)))
    assert disk.files() == (s.DEFAULT_CHECKPOINT,), (
        "the checkpoint was written to %r, not beside the journal at %r"
        % (disk.files(), s.DEFAULT_CHECKPOINT))
    assert disk.synced(s.DEFAULT_CHECKPOINT) == head, (
        "the checkpoint reads %r, not the line its fields spell (%r)"
        % (disk.synced(s.DEFAULT_CHECKPOINT), head))
    assert disk.read(s.DEFAULT_CHECKPOINT) == head, (
        "the checkpoint's text is %r" % (disk.read(s.DEFAULT_CHECKPOINT),))
    assert disk.synced(J) == "" and disk.files() == (s.DEFAULT_CHECKPOINT,), (
        "the journal reads %r: a checkpoint is written beside the journal, not "
        "over it" % (disk.synced(J),))
    assert (disk.writes, disk.syncs) == (1, 1), (
        "checkpoint did %d whole-file rewrite(s) and %d sync(s): one of each makes "
        "a checkpoint" % (disk.writes, disk.syncs))
    assert s.read_checkpoint(disk) == {
        "run": "run-1", "plan": "plan-abc", "now": 7,
        "states": {"fast": {"status": "done", "text": "fine"},
                   "fragile": "failed", "slow": "running"}}, (
        "read_checkpoint returned %r, not the four facts the checkpoint carries"
        % (s.read_checkpoint(disk),))

    # a second checkpoint replaces the first: a checkpoint is a rewrite, not an
    # append, so a crash can leave the old one or the new one and never both
    head2 = "8 checkpoint run=run-1 plan=plan-abc states=fast=done:fine\n"
    s.checkpoint(disk, "run-1", "plan-abc",
                 states={"fast": {"status": "done", "text": "fine"}}, now=8)
    assert disk.synced(s.DEFAULT_CHECKPOINT) == head2, (
        "after a second checkpoint the file reads %r, not %r: a checkpoint is a "
        "whole-file rewrite" % (disk.synced(s.DEFAULT_CHECKPOINT), head2))

    # a record with no detail is the status it says, and the six statuses the
    # contract names are all readable
    disk = Counting()
    s.checkpoint(disk, "run-1", "plan-abc",
                 states={"done_job": {"status": "done"}, "skipped": "skipped"},
                 now=1)
    assert disk.synced(s.DEFAULT_CHECKPOINT) == (
        "1 checkpoint run=run-1 plan=plan-abc states=done_job=done,skipped=skipped\n"), (
        "a record with no detail is written as %r"
        % (disk.synced(s.DEFAULT_CHECKPOINT),))
    assert s.read_checkpoint(disk)["states"] == {"done_job": "done",
                                                 "skipped": "skipped"}, (
        "a checkpoint's states read back as %r" % (s.read_checkpoint(disk),))

    # an empty table is a checkpoint too
    disk = Counting()
    s.checkpoint(disk, "run-1", "plan-abc", states={}, now=0)
    assert disk.synced(s.DEFAULT_CHECKPOINT) == (
        "0 checkpoint run=run-1 plan=plan-abc states=\n"), (
        "an empty states table is written as %r"
        % (disk.synced(s.DEFAULT_CHECKPOINT),))
    assert s.read_checkpoint(disk) == {"run": "run-1", "plan": "plan-abc",
                                       "now": 0, "states": {}}, (
        "an empty table reads back as %r" % (s.read_checkpoint(disk),))

    # nothing on disk, and nothing durable, are the same answer: None
    assert s.read_checkpoint(Counting()) is None, (
        "read_checkpoint of a disk with no checkpoint is not None")
    unsynced = Counting()
    unsynced.replace(s.DEFAULT_CHECKPOINT, head)     # a rewrite nobody synced
    assert unsynced.read(s.DEFAULT_CHECKPOINT) == head, (
        "the unsynced checkpoint is not even visible")
    assert s.read_checkpoint(unsynced) is None, (
        "read_checkpoint believes a checkpoint a crash would take away: %r"
        % (s.read_checkpoint(unsynced),))
    unsynced.sync()
    assert s.read_checkpoint(unsynced)["run"] == "run-1", (
        "the synced checkpoint is not readable")

    # ---- checkpoint(): a refused checkpoint writes nothing ----------------

    blank = Counting()
    message = _refuses(s.ResumeError, "a state that is not one of the six",
                       lambda: s.checkpoint(blank, "run-1", "plan-abc",
                                            states={"fast": "donee"}, now=0))
    assert "donee" in message and "did you mean 'done'" in message, (
        "the refusal of the state 'donee' does not name it and suggest its near "
        "status: %r" % (message,))
    message = _refuses(s.ResumeError, "a state record with a foreign field",
                       lambda: s.checkpoint(blank, "run-1", "plan-abc",
                                            states={"fast": {"status": "done",
                                                             "detail": "x"}},
                                            now=0))
    assert "detail" in message, (
        "the refusal of the state field 'detail' does not name it: %r" % (message,))
    message = _refuses(s.ResumeError, "a state record with no status",
                       lambda: s.checkpoint(blank, "run-1", "plan-abc",
                                            states={"fast": {"text": "x"}}, now=0))
    assert "status" in message, (
        "the refusal of a record with no status does not name it: %r" % (message,))
    message = _refuses(s.ResumeError, "a state detail with whitespace in it",
                       lambda: s.checkpoint(blank, "run-1", "plan-abc",
                                            states={"fast": {"status": "done",
                                                             "text": "a b"}},
                                            now=0))
    assert "a b" in message, (
        "the refusal of the detail 'a b' does not name it: %r" % (message,))
    message = _refuses(s.ResumeError, "a job id carrying the encoding's separator",
                       lambda: s.checkpoint(blank, "run-1", "plan-abc",
                                            states={"fa,st": "done"}, now=0))
    assert "fa,st" in message and "','" in message, (
        "the refusal of the job id 'fa,st' does not name it and the separator it "
        "carries: %r" % (message,))
    message = _refuses(s.ResumeError, "a job id carrying the detail's separator",
                       lambda: s.checkpoint(blank, "run-1", "plan-abc",
                                            states={"fa:st": "done"}, now=0))
    assert "fa:st" in message and "':'" in message, (
        "the refusal of the job id 'fa:st' does not name it and the separator it "
        "carries: %r" % (message,))
    message = _refuses(s.ResumeError, "a states table that is not a mapping",
                       lambda: s.checkpoint(blank, "run-1", "plan-abc",
                                            states=7, now=0))
    assert "7" in message, (
        "the refusal of the states table 7 does not name it: %r" % (message,))
    message = _refuses(s.ResumeError, "a blank run id",
                       lambda: s.checkpoint(blank, "", "plan-abc", states={}, now=0))
    assert "run id" in message, (
        "the refusal of a blank run id does not name the field: %r" % (message,))
    message = _refuses(s.ResumeError, "a plan hash carrying whitespace",
                       lambda: s.checkpoint(blank, "run-1", "plan abc", states={},
                                            now=0))
    assert "plan abc" in message, (
        "the refusal of the plan 'plan abc' does not name it: %r" % (message,))
    message = _refuses(s.ResumeError, "a `bool` tick",
                       lambda: s.checkpoint(blank, "run-1", "plan-abc", states={},
                                            now=True))
    assert "True" in message, (
        "the refusal of the tick True does not name it: %r" % (message,))
    message = _refuses(s.ResumeError, "a negative tick",
                       lambda: s.checkpoint(blank, "run-1", "plan-abc", states={},
                                            now=-1))
    assert "-1" in message, (
        "the refusal of the tick -1 does not name it: %r" % (message,))
    message = _refuses(s.ResumeError, "a tick that is not an int",
                       lambda: s.checkpoint(blank, "run-1", "plan-abc", states={},
                                            now="7"))
    assert "'7'" in message, (
        "the refusal of the tick '7' does not name it: %r" % (message,))
    assert (blank.files(), blank.volatile()) == ((), ()), (
        "a refused checkpoint still wrote %r / %r"
        % (blank.files(), blank.volatile()))

    # ---- read_checkpoint(): a file that is not a checkpoint ---------------

    disk = written(s.DEFAULT_CHECKPOINT, "0 start key=run-1 text=plan-abc\n")
    message = _refuses(s.ResumeError, "a journal line where a checkpoint belongs",
                       lambda: s.read_checkpoint(disk))
    assert "no checkpoint" in message and "0 start key=run-1" in message, (
        "the refusal of a file that is not a checkpoint does not name it: %r"
        % (message,))
    disk = written(s.DEFAULT_CHECKPOINT,
                   "7 checkpoint run=run-1 plan=plan-abc states=fast=nope\n")
    message = _refuses(s.ResumeError, "a checkpoint saying a status nobody has",
                       lambda: s.read_checkpoint(disk))
    assert "nope" in message, (
        "the refusal of the state 'nope' does not name it: %r" % (message,))
    disk = written(s.DEFAULT_CHECKPOINT, "7 checkpoint run=run-1 plan=plan-abc\n")
    message = _refuses(s.ResumeError, "a checkpoint with no states",
                       lambda: s.read_checkpoint(disk))
    assert "states" in message, (
        "the refusal of a checkpoint with no states does not name the field: %r"
        % (message,))
    disk = written(s.DEFAULT_CHECKPOINT,
                   "7 checkpoint run=run-1 plan=plan-abc fast=done states=\n")
    message = _refuses(s.ResumeError, "a checkpoint with a field it does not have",
                       lambda: s.read_checkpoint(disk))
    assert "fast" in message, (
        "the refusal of the checkpoint field 'fast' does not name it: %r"
        % (message,))
    disk = written(s.DEFAULT_CHECKPOINT,
                   "7 checkpoint run=run-1 run=run-1 plan=plan-abc states=\n")
    message = _refuses(s.ResumeError, "a checkpoint naming a field twice",
                       lambda: s.read_checkpoint(disk))
    assert "twice" in message and "run" in message, (
        "the refusal of a doubled 'run' does not name it: %r" % (message,))
    disk = written(s.DEFAULT_CHECKPOINT, "seven checkpoint run=r plan=p states=\n")
    message = _refuses(s.ResumeError, "a checkpoint whose tick is not a number",
                       lambda: s.read_checkpoint(disk))
    assert "seven" in message, (
        "the refusal of the tick 'seven' does not name it: %r" % (message,))
    disk = written(s.DEFAULT_CHECKPOINT, "-1 checkpoint run=r plan=p states=\n")
    message = _refuses(s.ResumeError, "a checkpoint with a negative tick",
                       lambda: s.read_checkpoint(disk))
    assert "-1" in message, (
        "the refusal of the tick -1 does not name it: %r" % (message,))
    disk = written(s.DEFAULT_CHECKPOINT,
                   "7 checkpoint run= plan=p states=\n")
    message = _refuses(s.ResumeError, "a checkpoint with a blank run",
                       lambda: s.read_checkpoint(disk))
    assert "run id" in message, (
        "the refusal of a blank run does not name the field: %r" % (message,))
    disk = written(s.DEFAULT_CHECKPOINT,
                   "7 checkpoint run=r plan=p states=fast=done,fast=failed\n")
    message = _refuses(s.ResumeError, "a checkpoint naming a job twice",
                       lambda: s.read_checkpoint(disk))
    assert "fast" in message and "twice" in message, (
        "the refusal of a doubled job does not name it: %r" % (message,))
    disk = written(s.DEFAULT_CHECKPOINT,
                   "7 checkpoint run=r plan=p states=\n"
                   "8 checkpoint run=r plan=p states=\n")
    message = _refuses(s.ResumeError, "a file holding two checkpoints",
                       lambda: s.read_checkpoint(disk))
    assert "2" in message and "line" in message, (
        "the refusal of a two-line checkpoint does not say how many lines it "
        "read: %r" % (message,))

    # ---- repair(): the fragment and only the fragment ---------------------

    first = "0 start key=run-1 text=plan-abc"
    second = "1 claim job=fast owner=w1 ticks=5"
    whole = first + "\n" + second + "\n"
    fragment = "2 cla"
    disk = written(J, whole + fragment)
    kept, dropped = s.repair(disk)
    assert (kept, dropped) == ((first, second), fragment), (
        "repair returned %r, not the two complete lines and the fragment: a "
        "repair drops a half-written line and never a whole one"
        % ((kept, dropped),))
    assert disk.synced(J) == whole and disk.read(J) == whole, (
        "after repair the journal reads %r, not the complete prefix %r"
        % (disk.synced(J), whole))
    assert (disk.writes, disk.syncs) == (1, 1), (
        "repair did %d rewrite(s) and %d sync(s): a repair that is not durable is "
        "not a repair" % (disk.writes, disk.syncs))

    # nothing torn: the log is left byte for byte alone
    disk = Counting()
    disk.write(J, whole)
    disk.sync()
    disk.writes = disk.syncs = 0
    assert s.repair(disk) == ((first, second), ""), (
        "repair of a log with nothing torn returned %r" % (s.repair(disk),))
    assert (disk.writes, disk.syncs) == (0, 0), (
        "repair rewrote a log it had nothing to drop from (%d rewrite(s), %d "
        "sync(s))" % (disk.writes, disk.syncs))

    # a log that is all fragment becomes empty
    disk = written(J, fragment)
    assert s.repair(disk) == ((), fragment), (
        "repair of a one-fragment log returned %r" % (s.repair(disk),))
    assert disk.synced(J) == "", (
        "after dropping the only fragment the journal reads %r" % (disk.synced(J),))

    # an empty log has nothing to drop and nothing to write
    disk = Counting()
    assert s.repair(disk) == ((), ""), (
        "repair of an empty log returned %r" % (s.repair(disk),))
    assert (disk.writes, disk.syncs) == (0, 0), (
        "repair wrote to an empty log (%d, %d)" % (disk.writes, disk.syncs))

    # the durable text decides, not the volatile write after it
    disk = Counting()
    disk.write(J, whole + fragment)
    disk.sync()
    disk.write(J, " and more")            # a write nobody synced
    disk.writes = disk.syncs = 0
    kept, dropped = s.repair(disk)
    assert (kept, dropped) == ((first, second), fragment), (
        "repair returned %r: the fragment is in what a crash would keep, not in "
        "what the program happens to see" % ((kept, dropped),))
    assert disk.synced(J) == whole, (
        "the repaired log reads %r" % (disk.synced(J),))

    # the path is the caller's, and the checkpoint beside the journal is not
    other = "/var/log/durable/other"
    disk = written(other, fragment)
    assert s.repair(disk, path=other) == ((), fragment), (
        "repair of the log at %r returned %r" % (other, s.repair(disk, path=other)))
    assert disk.synced(other) == "", (
        "the log at %r reads %r" % (other, disk.synced(other)))
    disk = Counting()
    s.checkpoint(disk, "run-1", "plan-abc", states={"fast": "done"}, now=3)
    disk.write(J, whole + fragment)
    disk.sync()
    disk.writes = disk.syncs = 0
    s.repair(disk)
    assert disk.synced(s.DEFAULT_CHECKPOINT) == (
        "3 checkpoint run=run-1 plan=plan-abc states=fast=done\n"), (
        "repair touched the checkpoint beside the journal: %r"
        % (disk.synced(s.DEFAULT_CHECKPOINT),))

    # ---- resume(): the fold, hand-computed -------------------------------

    early = ("0 start key=run-1 text=plan-abc\n"
             "1 claim job=old owner=w0 ticks=9\n")
    tail = ("5 claim job=a owner=w1 ticks=20\n"
            "5 claim job=d owner=w2 ticks=20\n"
            "6 result job=a owner=w1 status=ok ticks=2 text=fine\n"
            "6 result job=b owner=w1 status=failed ticks=1\n"
            "7 result job=c owner=w1 status=died ticks=1 text=gone\n"
            "7 expire job=d owner=w2\n"
            "8 expire job=a owner=w9\n"
            "8 claim job=e owner=w3 ticks=9\n"
            "9 claim job=g owner=w4 ticks=7\n"
            "9 claim job=h owner=w5 ticks=20\n"
            "9 intent job=f key=effect:f\n"
            "9 claim job=i owner=w6 ticks=20\n"
            "9 retry job=i ticks=2\n"
            "5 claim job=j owner=w7 ticks=5\n"
            "9 beat job=j owner=w7 ticks=20\n"
            "9 done\n")
    disk = Counting()
    disk.write(J, early)
    disk.sync()
    s.checkpoint(disk, "run-1", "plan-abc", states={"old": "running"}, now=4)
    head = disk.synced(s.DEFAULT_CHECKPOINT)
    disk.write(J, tail)
    disk.sync()
    disk.writes = disk.syncs = 0
    out = s.resume(disk, work.Effects(), now=11, run_id="run-1",
                   plan_hash="plan-abc")
    expected = {"a": {"status": "done", "text": "fine"},
                "b": "failed",
                "c": "expired",
                "d": "expired",
                "e": "expired",
                "f": "pending",
                "g": "expired",
                "h": "running",
                "i": "pending",
                "j": "running",
                "old": "expired"}
    assert out["states"] == expected, (
        "the resume's states are %r, not the table its lines fold: a claim is "
        "running, a result is done/failed/expired, an expire counts only for the "
        "owner that still holds the lease, a retry is pending, a beat renews the "
        "lease it names, and a lease is dead %d ticks past its deadline"
        % (out["states"], 2))
    assert tuple(out["states"]) == ("a", "b", "c", "d", "e", "f", "g", "h", "i",
                                    "j", "old"), (
        "the states read back as %r: a state table is id-sorted"
        % (tuple(out["states"]),))
    assert out["resumed"] is True, "a checkpoint was found and not resumed"
    assert out["reused"] == 1, (
        "the resume reused %r jobs, not the one its checkpoint held"
        % (out["reused"],))
    assert out["replayed"] == 10, (
        "the resume replayed %r jobs, not the ten the lines after the checkpoint "
        "name (the older ones were folded by the checkpoint and must not be "
        "replayed)" % (out["replayed"],))
    assert out["checkpoint"] == {"run": "run-1", "plan": "plan-abc", "now": 4,
                                 "states": {"old": "running"}}, (
        "the checkpoint in force is %r, not the one the resume read"
        % (out["checkpoint"],))
    assert (disk.writes, disk.syncs) == (0, 0), (
        "a resume that found a checkpoint wrote to the disk (%d, %d): a resume "
        "writes a checkpoint only when there is none" % (disk.writes, disk.syncs))
    assert disk.synced(s.DEFAULT_CHECKPOINT) == head, (
        "a resume rewrote the checkpoint it found: %r"
        % (disk.synced(s.DEFAULT_CHECKPOINT),))

    # the grace boundary, to the tick: `e` was claimed at 5 for 9 (deadline 9)
    # and `g` at 9 for 7 (deadline 7); at now=10 the first is alive and the
    # second is dead
    out10 = s.resume(disk, work.Effects(), now=10, run_id="run-1",
                     plan_hash="plan-abc")
    assert out10["states"] == dict(expected, e="running"), (
        "at now=10 the states are %r: a lease is dead %d ticks past its deadline "
        "and not before" % (out10["states"], 2))
    assert (disk.writes, disk.syncs) == (0, 0), (
        "the second resume wrote to the disk")

    # ---- resume(): the lines the checkpoint already folded are not replayed -

    disk = Counting()
    s.checkpoint(disk, "run-1", "plan-abc", states={"early": "done"}, now=4)
    disk.write(J, ("3 claim job=ghost owner=w1 ticks=20\n"
                   "4 retry job=folded ticks=2\n"
                   "5 claim job=late owner=w1 ticks=20\n"))
    disk.sync()
    out = s.resume(disk, work.Effects(), now=5, run_id="run-1",
                   plan_hash="plan-abc")
    assert out["reused"] == 1, "the checkpoint held one job: %r" % (out["reused"],)
    assert out["replayed"] == 1, (
        "the resume replayed %r jobs, not the one named after tick 4: a line at "
        "the checkpoint's own tick was already folded" % (out["replayed"],))
    assert out["states"] == {"early": "done", "late": "running"}, (
        "the states are %r: a job neither the checkpoint nor the tail names is not "
        "in the table" % (out["states"],))

    # ---- resume(): a fresh run writes its own checkpoint ------------------

    disk = Counting()
    journal = ("0 start key=run-1 text=plan-abc\n"
               "1 claim job=fast owner=w1 ticks=9\n"
               "2 retry job=slow ticks=2\n")
    disk.write(J, journal)
    disk.sync()
    disk.writes = disk.syncs = 0
    out = s.resume(disk, work.Effects(), now=3, run_id="run-1",
                   plan_hash="plan-abc")
    assert out["resumed"] is False, (
        "a run with no checkpoint to resume reported resumed=%r: this run wrote "
        "its own checkpoint" % (out["resumed"],))
    assert out["reused"] == 0 and out["replayed"] == 2, (
        "a fresh resume reported reused=%r, replayed=%r, not 0 and the two jobs "
        "its log names" % (out["reused"], out["replayed"]))
    assert out["states"] == {"fast": "running", "slow": "pending"}, (
        "the fresh table is %r" % (out["states"],))
    assert out["checkpoint"] == {"run": "run-1", "plan": "plan-abc", "now": 3,
                                 "states": {"fast": "running", "slow": "pending"}}, (
        "the checkpoint this run wrote is %r" % (out["checkpoint"],))
    assert disk.synced(s.DEFAULT_CHECKPOINT) == (
        "3 checkpoint run=run-1 plan=plan-abc states=fast=running,slow=pending\n"), (
        "the checkpoint on disk reads %r" % (disk.synced(s.DEFAULT_CHECKPOINT),))
    assert (disk.writes, disk.syncs) == (1, 1), (
        "a fresh resume did %d rewrite(s) and %d sync(s): it writes one checkpoint"
        % (disk.writes, disk.syncs))
    assert disk.synced(J) == journal, (
        "the fresh resume rewrote the journal (%r): a checkpoint is written beside "
        "the log, and the log is not eaten" % (disk.synced(J),))
    assert s.read_checkpoint(disk) == out["checkpoint"], (
        "the checkpoint the resume handed back is not the one on disk")
    again = s.resume(disk, work.Effects(), now=3, run_id="run-1",
                     plan_hash="plan-abc")
    assert again == {"states": {"fast": "expired", "slow": "pending"},
                     "resumed": True, "reused": 2, "replayed": 0,
                     "checkpoint": out["checkpoint"]}, (
        "the second resume returned %r: the checkpoint it found holds both jobs, "
        "its `running` lease is not this process's, and no line is after its tick"
        % (again,))
    assert (disk.writes, disk.syncs) == (1, 1), (
        "the second resume wrote to the disk (%d, %d)" % (disk.writes, disk.syncs))

    # ---- resume(): the log that is not this run's -------------------------

    disk = written(J, "0 start key=run-2 text=plan-abc\n")
    message = _refuses(s.ResumeError, "a fresh resume over another run's log",
                       lambda: s.resume(disk, work.Effects(), now=1,
                                        run_id="run-1", plan_hash="plan-abc"))
    assert "run-2" in message and "run-1" in message, (
        "the refusal of another run's log does not name both runs: %r" % (message,))
    assert disk.files() == (J,), (
        "a refused resume wrote a checkpoint anyway: %r" % (disk.files(),))
    disk = written(J, "0 start key=run-1 text=plan-xyz\n")
    message = _refuses(s.ResumeError, "a fresh resume over another plan's log",
                       lambda: s.resume(disk, work.Effects(), now=1,
                                        run_id="run-1", plan_hash="plan-abc"))
    assert "plan-xyz" in message and "plan-abc" in message, (
        "the refusal of another plan's log does not name both plans: %r" % (message,))
    disk = Counting()
    s.checkpoint(disk, "run-2", "plan-abc", states={}, now=0)
    message = _refuses(s.ResumeError, "a resume of another run's checkpoint",
                       lambda: s.resume(disk, work.Effects(), now=1,
                                        run_id="run-1", plan_hash="plan-abc"))
    assert "run-2" in message and "run-1" in message, (
        "the refusal of another run's checkpoint does not name both runs: %r"
        % (message,))
    disk = Counting()
    s.checkpoint(disk, "run-1", "plan-xyz", states={}, now=0)
    message = _refuses(s.ResumeError, "a resume of another plan's checkpoint",
                       lambda: s.resume(disk, work.Effects(), now=1,
                                        run_id="run-1", plan_hash="plan-abc"))
    assert "plan-xyz" in message and "plan-abc" in message, (
        "the refusal of another plan's checkpoint does not name both plans: %r"
        % (message,))

    # ---- resume(): a checkpoint's running job is not this process's lease --

    disk = Counting()
    s.checkpoint(disk, "run-1", "plan-abc",
                 states={"slow": "running", "fast": "done"}, now=4)
    out = s.resume(disk, work.Effects(), now=5, run_id="run-1",
                   plan_hash="plan-abc")
    assert out["states"] == {"fast": "done", "slow": "expired"}, (
        "the states are %r: a lease a checkpoint remembers is not this process's, "
        "and a job held by nobody has to come back" % (out["states"],))

    # ---- resume(): the effects the replay can prove -----------------------

    effects = work.Effects()
    effects.apply("effect:ghost", "ghost done", tick=1)   # folded by the checkpoint
    effects.apply("effect:late", "late done", tick=2)     # the tail's, unrecorded
    effects.apply("effect:settled", "settled done", tick=3)  # the tail's, recorded
    disk = Counting()
    early = ("0 intent job=ghost key=effect:ghost\n"
             "1 effect job=ghost key=effect:ghost\n")
    disk.write(J, early)
    disk.sync()
    s.checkpoint(disk, "run-1", "plan-abc", states={"ghost": "done"}, now=1)
    head = disk.synced(s.DEFAULT_CHECKPOINT)
    appended = ("2 intent job=late key=effect:late\n"
                "2 intent job=open key=effect:open\n"
                "2 intent job=settled key=effect:settled\n"
                "2 result job=settled owner=w1 status=ok ticks=1\n"
                "3 effect job=settled key=effect:settled\n")
    disk.write(J, appended)
    disk.sync()
    disk.writes = disk.syncs = 0
    out = s.resume(disk, effects, now=3, run_id="run-1", plan_hash="plan-abc")
    line = "3 effect job=late key=effect:late\n"
    assert disk.synced(J) == early + appended + line, (
        "after the resume the journal reads %r, not the lines plus the one `effect` "
        "line the replay could prove (%r): an intent the checkpoint already folded "
        "is not reconciled again, an intent the world never saw is left to the run, "
        "and an intent that already has its line gets no second one"
        % (disk.synced(J), line))
    assert (effects.count("effect:late"), effects.count("effect:ghost"),
            effects.count("effect:settled"), effects.count("effect:open")) == (
                1, 1, 1, 0), (
        "the world applied %r: a replay records what landed and applies nothing"
        % (effects.log(),))
    assert disk.synced(s.DEFAULT_CHECKPOINT) == head, (
        "the resume rewrote the checkpoint it found")
    assert out["replayed"] == 3 and out["reused"] == 1, (
        "the resume counted reused=%r, replayed=%r, not 1 and 3"
        % (out["reused"], out["replayed"]))
    assert out["states"] == {"ghost": "done", "late": "pending", "open": "pending",
                             "settled": "done"}, (
        "the states after the reconciliation are %r" % (out["states"],))

    # ---- resume(): a torn tail, and the repair that lets it resume --------

    disk = Counting()
    disk.write(J, "0 start key=run-1 text=plan-abc\n1 cla")
    disk.sync()
    message = _refuses(s.ResumeError, "a resume over a torn tail",
                       lambda: s.resume(disk, work.Effects(), now=1,
                                        run_id="run-1", plan_hash="plan-abc"))
    assert "1 cla" in message and "repair" in message, (
        "the refusal of a torn tail does not name the fragment and point at "
        "repair(): %r" % (message,))
    assert s.repair(disk) == (("0 start key=run-1 text=plan-abc",), "1 cla"), (
        "the repair before the resume returned %r" % (s.repair(disk),))
    out = s.resume(disk, work.Effects(), now=1, run_id="run-1",
                   plan_hash="plan-abc")
    assert out == {"states": {}, "resumed": False, "reused": 0, "replayed": 0,
                   "checkpoint": {"run": "run-1", "plan": "plan-abc", "now": 1,
                                  "states": {}}}, (
        "the resume after the repair returned %r" % (out,))

    # ---- resume(): a line that was not synced did not happen --------------

    disk = Counting()
    disk.write(J, "0 start key=run-1 text=plan-abc\n")
    disk.sync()
    disk.write(J, "1 retry job=slow ticks=2\n")          # a write nobody synced
    out = s.resume(disk, work.Effects(), now=2, run_id="run-1",
                   plan_hash="plan-abc")
    assert out["states"] == {} and out["replayed"] == 0, (
        "the resume replayed a line a crash would take away: %r" % (out,))
    assert disk.read(J) == ("0 start key=run-1 text=plan-abc\n"
                            "1 retry job=slow ticks=2\n"), (
        "the unsynced line is not even there: %r" % (disk.read(J),))

    # ---- resume(): its own refusals ---------------------------------------

    disk = Counting()
    message = _refuses(s.ResumeError, "a resume of no run",
                       lambda: s.resume(disk, work.Effects(), now=1, run_id="",
                                        plan_hash="plan-abc"))
    assert "a resume's run id" in message, (
        "the refusal of a blank run id does not name the field it is the resume's: "
        "%r" % (message,))
    message = _refuses(s.ResumeError, "a resume at a `bool` tick",
                       lambda: s.resume(disk, work.Effects(), now=True,
                                        run_id="run-1", plan_hash="plan-abc"))
    assert "a resume's tick" in message and "True" in message, (
        "the refusal of the tick True does not name it as the resume's: %r"
        % (message,))
    message = _refuses(s.ResumeError, "a resume at a tick that is not an int",
                       lambda: s.resume(disk, work.Effects(), now="3",
                                        run_id="run-1", plan_hash="plan-abc"))
    assert "a resume's tick" in message and "'3'" in message, (
        "the refusal of the tick '3' does not name it as the resume's: %r"
        % (message,))
    message = _refuses(s.ResumeError, "a resume without the world",
                       lambda: s.resume(disk, object(), now=1, run_id="run-1",
                                        plan_hash="plan-abc"))
    assert "count" in message, (
        "the refusal of a world with no count() does not say what is missing: %r"
        % (message,))

    print("check_08: the checkpoint — a whole-file rewrite beside the journal, "
          "synced before it is believed, whose exact text is hand-computed and "
          "whose run, plan and states are refused by name — read back through "
          "`disk.synced` only; the resume — the states a checkpoint already folds "
          "are not replayed, the counts are counts of jobs, a checkpoint that is "
          "not this run's or this plan's and a log that names another run are both "
          "refused by name, the dead leases are recovered at the grace boundary, "
          "the replayed intents the world proves get their one `effect` line, a "
          "fresh run writes its own checkpoint and a resumed one writes nothing, "
          "and a torn tail is refused until repair() drops it")

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate,
                                              "durable-execution-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    from collections.abc import Mapping

    import disk as world
    import stage_01 as s1
    import stage_09 as s
    import work

    journal = world.DEFAULT_JOURNAL

    # ---- the surface: eleven numbers, in the order a report writes them ---

    assert s.REPORT_KEYS == ("run", "jobs", "claimed", "beats", "intents",
                             "results", "effects", "expires", "retries",
                             "ticks", "synced"), (
        "this stage's report keys are %r, not the eleven the course defined"
        % (s.REPORT_KEYS,))

    # ---- one hand-built log: seventeen lines, every counter counted by hand -
    #
    #   line  tick  kind    what it decides
    #     1     1   start   key=run-1 text=plan-abc — the run begins
    #     2     2   claim   job=fast owner=w1 ticks=4 — w1 takes fast
    #     3     3   beat    job=fast owner=w1 ticks=5 — w1 is alive
    #     4     4   intent  job=fast key=effect:fast — fast's effect announced
    #     5     4   effect  job=fast key=effect:fast — and it landed
    #     6     5   result  job=fast owner=w1 status=ok — fast finished ok
    #     7     6   claim   job=slow owner=w2 ticks=3 — w2 takes slow
    #     8     7   intent  job=slow key=effect:slow — slow's effect announced
    #     9     8   beat    job=slow owner=w2 ticks=4 — w2 is alive
    #    10     9   result  job=slow owner=w2 status=died — w2 died
    #    11     9   expire  job=slow owner=w2 — the lease ran out
    #    12    10   retry   job=slow ticks=3 — slow is re-issued
    #    13    11   claim   job=slow owner=w3 ticks=3 — w3 takes slow
    #    14    12   intent  job=slow key=effect:slow — announced again
    #    15    12   effect  job=slow key=effect:slow — and it landed
    #    16    13   result  job=slow owner=w3 status=ok — slow finished ok
    #    17    14   done    — nothing left
    #
    # claimed 3 (lines 2, 7, 13)   beats 2 (3, 9)     intents 3 (4, 8, 14)
    # results 3 (6, 10, 16)        effects 2 (5, 15)  expires 1 (11)
    # retries 1 (12)               jobs 2 (fast, slow)  ticks 14 (the done line)

    log = (
        "1 start key=run-1 text=plan-abc\n"
        "2 claim job=fast owner=w1 ticks=4\n"
        "3 beat job=fast owner=w1 ticks=5\n"
        "4 intent job=fast key=effect:fast\n"
        "4 effect job=fast key=effect:fast\n"
        "5 result job=fast owner=w1 status=ok ticks=1 text=fast-done\n"
        "6 claim job=slow owner=w2 ticks=3\n"
        "7 intent job=slow key=effect:slow\n"
        "8 beat job=slow owner=w2 ticks=4\n"
        "9 result job=slow owner=w2 status=died ticks=2\n"
        "9 expire job=slow owner=w2\n"
        "10 retry job=slow ticks=3\n"
        "11 claim job=slow owner=w3 ticks=3\n"
        "12 intent job=slow key=effect:slow\n"
        "12 effect job=slow key=effect:slow\n"
        "13 result job=slow owner=w3 status=ok ticks=2 text=slow-done\n"
        "14 done\n"
    )
    entries = (
        {"tick": 1, "kind": "start", "key": "run-1", "text": "plan-abc"},
        {"tick": 2, "kind": "claim", "job": "fast", "owner": "w1", "ticks": 4},
        {"tick": 3, "kind": "beat", "job": "fast", "owner": "w1", "ticks": 5},
        {"tick": 4, "kind": "intent", "job": "fast", "key": "effect:fast"},
        {"tick": 4, "kind": "effect", "job": "fast", "key": "effect:fast"},
        {"tick": 5, "kind": "result", "job": "fast", "owner": "w1",
         "status": "ok", "ticks": 1, "text": "fast-done"},
        {"tick": 6, "kind": "claim", "job": "slow", "owner": "w2", "ticks": 3},
        {"tick": 7, "kind": "intent", "job": "slow", "key": "effect:slow"},
        {"tick": 8, "kind": "beat", "job": "slow", "owner": "w2", "ticks": 4},
        {"tick": 9, "kind": "result", "job": "slow", "owner": "w2",
         "status": "died", "ticks": 2},
        {"tick": 9, "kind": "expire", "job": "slow", "owner": "w2"},
        {"tick": 10, "kind": "retry", "job": "slow", "ticks": 3},
        {"tick": 11, "kind": "claim", "job": "slow", "owner": "w3", "ticks": 3},
        {"tick": 12, "kind": "intent", "job": "slow", "key": "effect:slow"},
        {"tick": 12, "kind": "effect", "job": "slow", "key": "effect:slow"},
        {"tick": 13, "kind": "result", "job": "slow", "owner": "w3",
         "status": "ok", "ticks": 2, "text": "slow-done"},
        {"tick": 14, "kind": "done"},
    )
    assert len(entries) == 17 and log.count("\n") == 17, (
        "the check's own log is not seventeen lines: %d entries, %d lines"
        % (len(entries), log.count("\n")))

    # the disk: the seventeen lines written through stage 1, plus a checkpoint's
    # bytes at another path — both a fact, both counted by `synced`
    checkpoint = (
        "checkpoint run-1 plan-abc states=fast,slow now=14\n")
    disk = world.Disk()
    for entry in entries:
        s1.write_line(disk, entry)
    assert disk.read(journal) == log, (
        "the hand-written log is not the bytes its entries spell: %r"
        % (disk.read(journal),))
    disk.write("/var/log/durable/checkpoint", checkpoint)
    disk.sync()
    assert disk.synced(journal) == log and disk.synced(
        "/var/log/durable/checkpoint") == checkpoint, (
        "the check's own fixture is not durable: %r"
        % (disk.synced(journal),))
    table = tuple(s1.parse_line(one) for one in log.splitlines())
    assert table == entries, (
        "the hand-written entries are not what the log spells: %r" % (table,))

    # the world the log describes: each key applied exactly once, when the log
    # says the effect landed
    effects = work.Effects()
    effects.apply("effect:fast", "fast done", tick=4)
    effects.apply("effect:slow", "slow done", tick=12)

    # ---- the report: every counter recomputed, by hand --------------------

    states = {"fast": {"status": "done", "text": "fast-done"}, "slow": "done"}
    built = s.report(disk, table, states=states, ticks=14, effects=effects)
    assert isinstance(built, Mapping), (
        "a report is a mapping, got %r" % (built,))
    assert tuple(built) == ("run", "jobs", "claimed", "beats", "intents",
                            "results", "effects", "expires", "retries", "ticks",
                            "synced"), (
        "the report carries %r, not the eleven keys in REPORT_KEYS order"
        % (tuple(built),))
    assert built["run"] == "run-1", (
        "the run's id is the `start` line's key, 'run-1', not %r"
        % (built["run"],))
    assert built["jobs"] == 2, (
        "the log names two ids, fast and slow — a repeated id is one job — not "
        "%r" % (built["jobs"],))
    assert built["claimed"] == 3, (
        "the log has three claim lines (2, 7, 13), not %r" % (built["claimed"],))
    assert built["beats"] == 2, (
        "the log has two beat lines (3, 9), not %r" % (built["beats"],))
    assert built["intents"] == 3, (
        "the log has three intent lines (4, 8, 14), not %r" % (built["intents"],))
    assert built["results"] == 3, (
        "the log has three result lines (6, 10, 16) — attempts, not jobs — not "
        "%r" % (built["results"],))
    assert built["effects"] == 2, (
        "the log has two effect lines (5, 15), not %r" % (built["effects"],))
    assert built["expires"] == 1, (
        "the log has one expire line (11), not %r" % (built["expires"],))
    assert built["retries"] == 1, (
        "the log has one retry line (12), not %r" % (built["retries"],))
    assert built["ticks"] == 14, (
        "the highest tick the log names is the done line's 14, not %r"
        % (built["ticks"],))
    assert len(log) == 602 and len(checkpoint) == 50, (
        "the check's own fixture changed size: %d journal bytes, %d checkpoint "
        "bytes" % (len(log), len(checkpoint)))
    assert built["synced"] == 652, (
        "the disk holds %d durable bytes — the 602-byte journal plus the "
        "50-byte checkpoint, and nothing volatile — not %r"
        % (len(log) + len(checkpoint), built["synced"]))

    # a report whose caller's table holds the record form of a state, and the
    # bare form, both accepted: a status is a status however it is spelled
    running = s.report(disk, table[:2], states={"fast": "running"}, ticks=2,
                       effects=work.Effects())
    assert running["jobs"] == 1 and running["claimed"] == 1, (
        "a report over the log's first two lines is one job and one claim, not "
        "%r" % (running,))
    assert running["beats"] == 0 and running["ticks"] == 2, (
        "a report over the log's first two lines has no beats and stops at tick "
        "2, not %r" % (running,))
    assert running["synced"] == 652, (
        "synced is a fact about the disk, not about the lines it was handed: "
        "%r" % (running["synced"],))

    # ---- the caller's totals, refused by name ------------------------------

    message = _refuses(
        s1.DurableError, "a report whose tick is past the log's last line",
        lambda: s.report(disk, table, states=states, ticks=15, effects=effects))
    assert "ticks" in message and "15" in message and "14" in message, (
        "the refusal of a contradicted tick names neither the key nor both "
        "numbers: %r" % (message,))

    message = _refuses(
        s1.DurableError, "a report whose tick is before the log's last line",
        lambda: s.report(disk, table, states=states, ticks=13, effects=effects))
    assert "ticks" in message and "13" in message and "14" in message, (
        "the refusal of a run that stopped before its own last line does not "
        "name the key and both numbers: %r" % (message,))

    message = _refuses(
        s1.DurableError, "a state table that forgot a job the log names",
        lambda: s.report(disk, table, states={"fast": "done"}, ticks=14,
                         effects=effects))
    assert "slow" in message, (
        "the refusal of a table that forgot the job 'slow' does not name it: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "a table that calls a job finished the log never "
        "answered",
        lambda: s.report(disk, table[:2], states={"fast": {"status": "done"}},
                         ticks=2, effects=work.Effects()))
    assert "fast" in message and "done" in message, (
        "the refusal of a job the log never finished does not name the job and "
        "the status: %r" % (message,))

    message = _refuses(
        s1.DurableError, "a table that calls a job failed the log never "
        "answered",
        lambda: s.report(disk, table[:2], states={"fast": {"status": "failed"}},
                         ticks=2, effects=work.Effects()))
    assert "fast" in message and "failed" in message, (
        "the refusal of a job the log never failed does not name the job and "
        "the status: %r" % (message,))

    message = _refuses(
        s1.DurableError, "a log with no start line",
        lambda: s.report(disk, table[1:], states={"fast": "running"}, ticks=14,
                         effects=effects))
    assert "start" in message, (
        "the refusal of a log no `start` line begins does not name it: %r"
        % (message,))

    announced = (s1.parse_line("1 start key=run-3 text=plan-abc"),
                 s1.parse_line("2 intent job=fast key=effect:fast"),
                 s1.parse_line("2 effect job=fast key=effect:fast"))
    one = work.Effects()
    one.apply("effect:fast", "fast done", tick=2)
    landed = s.report(disk, announced, states={"fast": "pending"}, ticks=2,
                      effects=one)
    assert landed["effects"] == 1 and landed["intents"] == 1, (
        "an effect line the world confirms is still one effect line: %r"
        % (landed,))

    message = _refuses(
        s1.DurableError, "an effect line the world never applied",
        lambda: s.report(disk, announced, states={"fast": "pending"}, ticks=2,
                         effects=work.Effects()))
    assert "effect:fast" in message and "0" in message, (
        "the refusal of an effect the world never applied does not name the key "
        "and the world's count: %r" % (message,))

    # an effect is not a result: a job whose effect landed and whose attempt is
    # still open is not a finished job
    message = _refuses(
        s1.DurableError, "a table that calls a job done on the strength of an "
        "effect",
        lambda: s.report(disk, announced, states={"fast": "done"}, ticks=2,
                         effects=one))
    assert "fast" in message and "done" in message, (
        "the refusal of a job finished by an effect instead of a result does "
        "not name the job and the status: %r" % (message,))

    twice = work.Effects()
    twice.apply("effect:fast", "fast done", tick=2)
    twice.apply("effect:fast", "fast done again", tick=3)
    message = _refuses(
        s1.DurableError, "a key the world applied twice and the log once",
        lambda: s.report(disk, announced, states={"fast": "pending"}, ticks=2,
                         effects=twice))
    assert "effect:fast" in message and "2" in message and "1" in message, (
        "the refusal of an effect that happened twice does not name the key and "
        "both numbers: %r" % (message,))

    # a walk over things that are not parsed lines: each refused by name
    broken = (
        ("a line that is not a mapping",
         ("1 start key=run-1 text=plan-abc",), "parsed lines"),
        ("a line with no kind",
         ({"tick": 1, "key": "run-1", "text": "plan-abc"},), "kind"),
        ("a line whose tick is a bool",
         ({"tick": True, "kind": "start", "key": "run-1", "text": "plan-abc"},),
         "non-negative int"),
        ("a line whose tick is negative",
         ({"tick": -1, "kind": "start", "key": "run-1", "text": "plan-abc"},),
         "non-negative int"),
        ("a line whose tick is not an int",
         ({"tick": "1", "kind": "start", "key": "run-1", "text": "plan-abc"},),
         "non-negative int"),
        ("a start line with no key",
         ({"tick": 1, "kind": "start", "text": "plan-abc"},), "key"),
    )
    for what, one_line, wanted in broken:
        message = _refuses(
            s1.DurableError, what,
            lambda table=one_line: s.report(disk, table, states={}, ticks=1,
                                            effects=work.Effects()))
        assert wanted in message, (
            "the refusal of %s does not name the offender: %r" % (what, message))

    # ---- audit: the same walk, told the other way -------------------------

    clean = s.audit(disk, table)
    assert isinstance(clean, Mapping), (
        "an audit is a mapping, got %r" % (clean,))
    assert set(clean) == set(("missing", "extra", "count")), (
        "an audit reports %r, not missing, extra and count" % (sorted(clean),))
    assert isinstance(clean["missing"], tuple) and isinstance(
        clean["extra"], tuple), (
        "an audit's findings are tuples, got %r and %r"
        % (clean["missing"], clean["extra"]))
    assert clean["missing"] == () and clean["extra"] == (), (
        "a table that holds exactly the log reports nothing: %r" % (clean,))
    assert clean["count"] == 17, (
        "the log holds seventeen lines, not %r" % (clean["count"],))

    short = s.audit(disk, table[:1])
    assert short["missing"] == table[1:], (
        "a table that is the log's first line is missing the other sixteen: %r"
        % (short["missing"],))
    assert short["extra"] == (), (
        "a table that is a prefix of the log has nothing extra: %r"
        % (short["extra"],))
    assert short["count"] == 17, (
        "count is the number of lines the log holds (17), not the table's %r"
        % (short["count"],))

    invented = s1.parse_line("20 done")
    more = s.audit(disk, table + (invented,))
    assert more["missing"] == () and more["extra"] == (invented,), (
        "a table with one invented line has it extra and nothing missing: %r"
        % (more,))
    assert more["count"] == 17, (
        "an invented line does not make the log hold more lines: %r"
        % (more["count"],))

    # the same tick and kind, a different owner: not the same line
    swapped = list(table)
    swapped[1] = s1.parse_line("2 claim job=fast owner=w9 ticks=4")
    wrong = s.audit(disk, tuple(swapped))
    assert wrong["missing"] == (table[1],) and wrong["extra"] == (
        swapped[1],), (
        "a claim by another owner is missing from the table and extra in it: %r"
        % (wrong,))
    assert wrong["count"] == 17, (
        "a swapped line is still seventeen log lines: %r" % (wrong["count"],))

    # a byte a crash would take back is not a line the log holds
    live = world.Disk()
    s1.write_line(live, entries[0])
    live.sync()
    s1.write_line(live, entries[1])
    assert live.synced(journal) == log.splitlines(True)[0], (
        "the check's own fixture is not half-durable: %r" % (live.synced(journal),))
    pending = s.audit(live, (table[0], table[1]))
    assert pending["missing"] == () and pending["extra"] == (table[1],), (
        "a line written and not synced is not a line the log holds: %r"
        % (pending,))
    assert pending["count"] == 1, (
        "the disk would keep one line of the two, not %r" % (pending["count"],))

    # a tail that never got its terminator is not a line the log holds either
    torn = world.Disk()
    torn.write(journal, log.splitlines(True)[0])
    torn.write(journal, "2 claim job=slow owner=w2 ticks=3")
    torn.sync()
    assert not torn.synced(journal).endswith("\n"), (
        "the check's own torn fixture is not torn: %r" % (torn.synced(journal),))
    half = s.audit(torn, (table[0],))
    assert half["missing"] == () and half["extra"] == (), (
        "a fragment with no terminator is not a line, so it is neither missing "
        "nor extra: %r" % (half,))
    assert half["count"] == 1, (
        "a log with one whole line holds one line, not %r" % (half["count"],))

    empty = s.audit(world.Disk(), ())
    assert empty == {"missing": (), "extra": (), "count": 0}, (
        "an empty disk audits clean and empty, got %r" % (empty,))

    message = _refuses(s1.DurableError, "an audit over things that are not "
                       "parsed lines",
                       lambda: s.audit(disk, ("1 start key=run-1 text=plan-abc",)))
    assert "parsed lines" in message, (
        "the refusal of a table that is not parsed lines does not name the "
        "offender: %r" % (message,))

    # ---- and the volatile byte the report must not count -------------------

    s1.write_line(disk, {"tick": 15, "kind": "done"})
    again = s.report(disk, table, states=states, ticks=14, effects=effects)
    assert again["synced"] == 652, (
        "a line written and not synced is not a byte the report counts: %r"
        % (again["synced"],))
    assert again["claimed"] == 3 and again["ticks"] == 14, (
        "a volatile line does not change the numbers the lines supply: %r"
        % (again,))

    print("check_09: the report — a hand-built log of seventeen lines whose "
          "every counter is recounted from its lines, a state table and a world "
          "of effects the log has to agree with, and a tick the log has to "
          "justify, all refused by name when they disagree; `synced` counting "
          "the disk's durable bytes and not its volatile ones; and the audit "
          "reporting what a table is missing and what it has extra against the "
          "lines the disk would keep")

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J3_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate,
                                              "durable-execution-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J3_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    _LOG = (
        "0 start key=run-1 text=<plan>\n"
        "0 claim job=fast owner=w1 ticks=4\n"
        "0 claim job=slow owner=w2 ticks=4\n"
        "1 beat job=fast owner=w1 ticks=4\n"
        "1 beat job=slow owner=w2 ticks=4\n"
        "0 intent job=fast key=effect:fast\n"
        "1 effect job=fast key=effect:fast\n"
        "1 result job=fast owner=w1 status=ok ticks=0\n"
        "2 beat job=slow owner=w2 ticks=4\n"
        "3 beat job=slow owner=w2 ticks=4\n"
        "4 beat job=slow owner=w2 ticks=4\n"
        "5 beat job=slow owner=w2 ticks=4\n"
        "6 beat job=slow owner=w2 ticks=4\n"
        "7 beat job=slow owner=w2 ticks=4\n"
        "8 beat job=slow owner=w2 ticks=4\n"
        "9 beat job=slow owner=w2 ticks=4\n"
        "0 intent job=slow key=effect:slow\n"
        "9 effect job=slow key=effect:slow\n"
        "9 result job=slow owner=w2 status=ok ticks=9\n"
        "9 done\n"
    )

    _LOST_AT_TICK_3 = "2 beat job=slow owner=w2 ticks=4\n"

    _CRASHED_AT_TICK_3 = (
        "0 start key=run-1 text=<plan>\n"
        "0 claim job=fast owner=w1 ticks=4\n"
        "0 claim job=slow owner=w2 ticks=4\n"
        "1 beat job=fast owner=w1 ticks=4\n"
        "1 beat job=slow owner=w2 ticks=4\n"
        "0 intent job=fast key=effect:fast\n"
        "1 effect job=fast key=effect:fast\n"
        "1 result job=fast owner=w1 status=ok ticks=0\n"
    )

    _RESUMED_TAIL = (
        "7 expire job=slow owner=w2\n"
        "7 retry job=slow ticks=4\n"
        "7 claim job=slow owner=w3 ticks=4\n"
        "8 beat job=slow owner=w3 ticks=4\n"
        "9 beat job=slow owner=w3 ticks=4\n"
        "10 beat job=slow owner=w3 ticks=4\n"
        "11 beat job=slow owner=w3 ticks=4\n"
        "12 beat job=slow owner=w3 ticks=4\n"
        "13 beat job=slow owner=w3 ticks=4\n"
        "14 beat job=slow owner=w3 ticks=4\n"
        "15 beat job=slow owner=w3 ticks=4\n"
        "16 beat job=slow owner=w3 ticks=4\n"
        "0 intent job=slow key=effect:slow\n"
        "16 effect job=slow key=effect:slow\n"
        "16 result job=slow owner=w3 status=ok ticks=9\n"
        "16 done\n"
    )

    _LOST_AT_TICK_2 = (
        "0 claim job=bulk owner=w1 ticks=4\n"
        "0 claim job=slow owner=w2 ticks=4\n"
        "1 beat job=bulk owner=w1 ticks=4\n"
        "1 beat job=slow owner=w2 ticks=4\n"
    )

    def _journal(disk, journal):
        """The journal's text, as `read` shows it and as a crash would keep it."""
        return disk.read(journal)

    def _orphan(world, s1):
        """A disk holding one claim line and no `start`: a log no run begins."""
        disk = world.Disk()
        s1.write_line(disk, {"tick": 0, "kind": "claim", "job": "fast",
                             "owner": "w1", "ticks": 4})
        disk.sync()
        return disk

    from collections.abc import Mapping

    import disk as world
    import fleet
    import stage_01 as s1
    import stage_03 as s3
    import stage_05 as s5
    import stage_06 as s6
    import stage_08 as s8
    import stage_09 as s9
    import stage_10 as s
    import work

    journal = world.DEFAULT_JOURNAL

    def status_of(state):
        return state if isinstance(state, str) else state["status"]

    def statuses(result):
        return {job: status_of(state) for job, state in result["states"].items()}

    def once(world_of_effects, plan, *, result):
        """Each key at most once, and exactly once for a job the states call
        `done` — the property §4.10 states as "each key applied exactly once"."""
        for job in sorted(plan):
            seen = world_of_effects.count(plan[job].key)
            wanted = status_of(result["states"][job]) == "done"
            if seen > 1 or (wanted and seen != 1):
                return False, (job, seen, wanted)
        return True, ()

    # ---- the surface: the two constants the course froze ------------------

    assert s.DEFAULT_LIMIT == 2, (
        "the cap is two workers in the air at once, not %r" % (s.DEFAULT_LIMIT,))
    assert s.LEASE_TICKS == 4, (
        "a synthetic owner's claim is granted four ticks, not %r"
        % (s.LEASE_TICKS,))

    # ---- one whole run, written out here line by line ---------------------

    plan = {"fast": work.job("fast"), "slow": work.job("slow")}
    disk = world.Disk()
    effects = work.Effects()
    clock = fleet.Clock()
    whole = s.run(plan, disk=disk, effects=effects, clock=clock)

    assert isinstance(whole, Mapping), (
        "a run returns a mapping, got %r" % (whole,))
    assert set(whole) == set(("states", "events", "report", "clock", "lost")), (
        "§3.5's mapping carries states, events, report, clock and lost, got %r"
        % (sorted(whole),))
    assert whole["clock"] == 9, (
        "the run stopped at the `done` line's tick, 9, not %r" % (whole["clock"],))
    assert whole["lost"] == (), (
        "a run that was never killed lost nothing, got %r" % (whole["lost"],))
    assert whole["states"] == {"fast": "done", "slow": "done"}, (
        "the two jobs the log finished are done, got %r" % (whole["states"],))

    start = whole["events"][0]
    assert start["kind"] == "start" and start["key"] == "run-1", (
        "the journal's first line begins the run `run-1`, got %r" % (start,))
    expected = _LOG.replace("<plan>", start["text"])
    assert len(expected) == 668, (
        "the check's own log changed size: %d bytes" % (len(expected),))
    assert _journal(disk, journal) == expected, (
        "the journal is not the twenty lines this check hand-wrote:\n%r"
        % (_journal(disk, journal),))
    assert disk.synced(journal) == expected, (
        "the run returned before its own last line was durable: %r"
        % (disk.synced(journal)[-80:],))

    records = tuple(s1.parse_line(line) for line in expected.splitlines())
    assert tuple(whole["events"]) == records, (
        "`events` is the journal's records and nothing else: %r"
        % (whole["events"],))

    built = whole["report"]
    assert tuple(built) == s9.REPORT_KEYS, (
        "a report carries REPORT_KEYS in order, got %r" % (tuple(built),))
    assert built == {"run": "run-1", "jobs": 2, "claimed": 2, "beats": 10,
                     "intents": 2, "results": 2, "effects": 2, "expires": 0,
                     "retries": 0, "ticks": 9, "synced": 668}, (
        "the report's eleven numbers are not the log's own — two claims, ten "
        "beats, two intents, two effects, two results, two jobs, nine ticks and "
        "668 durable bytes, got %r" % (built,))
    assert built == s9.report(disk, records, states=whole["states"],
                              ticks=9, effects=effects), (
        "the run's report is not what stage 9 recomputes from its own lines: %r"
        % (built,))
    assert whole["clock"] == built["ticks"] == max(
        one["tick"] for one in records), (
        "the tick a run stopped at is its log's highest tick, got %r, %r and %r"
        % (whole["clock"], built["ticks"],
           max(one["tick"] for one in records)))

    assert sorted(effects.applied()) == ["effect:fast", "effect:slow"], (
        "each job's effect landed once, under its own key: %r"
        % (effects.applied(),))
    assert effects.count("effect:fast") == 1 and effects.count("effect:slow") == 1, (
        "exactly once is the number, got %r" % (effects.applied(),))

    # two runs of one fixture are equal, value for value — and so are two runs
    # of one *plan*: the `start` line's hash is the plan's, not the process's
    twin = s.run({"fast": work.job("fast"), "slow": work.job("slow")},
                 disk=world.Disk(), effects=work.Effects())
    assert twin == whole, (
        "two runs of one fixture differ: %r" % (twin,))
    other = s.run({"fast": work.job("fast"), "slow": work.job("slow", ticks=2)},
                  disk=world.Disk(), effects=work.Effects())
    assert other["events"][0]["text"] != start["text"], (
        "another plan hashes to the same `start` text, %r" % (start["text"],))
    assert other["report"]["results"] == 2 and other["clock"] != 9, (
        "a slow job costing two ticks an attempt is not the fixture's own: %r"
        % (other,))
    shuffled = s.run({"slow": work.job("slow"), "fast": work.job("fast")},
                     disk=world.Disk(), effects=work.Effects())
    assert shuffled == whole, (
        "the plan's hash and the plan's order are the plan's, not the mapping's "
        "insertion order: %r" % (shuffled,))

    # ---- the kill after a sync: the lease that has to be honoured ---------

    cut_disk = world.Disk()
    cut_world = work.Effects()
    cut_clock = fleet.Clock()
    killed = s.run(plan, disk=cut_disk, effects=cut_world, clock=cut_clock,
                   workers=({"owner": "w1", "ticks": 4, "dies_at": None},
                            {"owner": "w2", "ticks": 4, "dies_at": 3}),
                   checkpoint_every=1)

    assert killed["clock"] == 3, (
        "the killed owner's tick is where the run stops, 3, not %r"
        % (killed["clock"],))
    assert killed["lost"] == ((journal, _LOST_AT_TICK_3),), (
        "the kill costs exactly the unsynced beat at tick 2, got %r"
        % (killed["lost"],))
    assert killed["states"] == {"fast": "done", "slow": "running"}, (
        "a killed owner's job is not `done` while its lease is held by a "
        "process that is gone: %r" % (killed["states"],))
    crashed = _journal(cut_disk, journal)
    assert crashed == _CRASHED_AT_TICK_3.replace("<plan>", start["text"]), (
        "the durable log at the kill is not the eight lines this check "
        "hand-wrote:\n%r" % (crashed,))
    assert cut_disk.read(journal) == crashed == cut_disk.synced(journal), (
        "after a crash the journal reads exactly what it would keep: %r"
        % (cut_disk.read(journal),))
    assert s8.read_checkpoint(cut_disk) is not None, (
        "a checkpoint every finished job leaves a checkpoint, and the kill's "
        "claims are durable because of its barrier")

    lines = s3.replay(cut_disk)
    deadline = 5          # claimed at 0 for four ticks, beaten at 1 for four more
    assert s6.recovered(cut_disk, now=deadline + 1) == {"fast": "done",
                                                        "slow": "running"}, (
        "a lapsed lease is honoured one tick before its grace is spent: %r"
        % (s6.recovered(cut_disk, now=deadline + 1),))
    assert s6.recovered(cut_disk, now=deadline + s5.MAX_MISSES) == {
        "fast": "done", "slow": "expired"}, (
        "at `deadline + MAX_MISSES` the lease is expired: %r"
        % (s6.recovered(cut_disk, now=deadline + s5.MAX_MISSES),))
    assert s5.reclaimable(lines, now=deadline + 1) == (), (
        "a lease inside its grace is not reclaimable: %r"
        % (s5.reclaimable(lines, now=deadline + 1),))
    assert s5.reclaimable(lines, now=deadline + s5.MAX_MISSES) == ("slow",), (
        "at `deadline + MAX_MISSES` the id is reclaimable, got %r"
        % (s5.reclaimable(lines, now=deadline + s5.MAX_MISSES),))

    # the resume: the same function, the same disk, a fresh process's clock
    resumed = s.run(plan, disk=cut_disk, effects=cut_world, clock=cut_clock)
    assert statuses(resumed) == statuses(whole), (
        "an interrupted run ends with the uninterrupted run's states: %r vs %r"
        % (statuses(resumed), statuses(whole)))
    assert once(cut_world, plan, result=resumed)[0], (
        "every key applied exactly once after the resume: %r"
        % (cut_world.log(),))
    assert list(resumed["events"])[:len(killed["events"])] == list(
        killed["events"]), (
        "the crash's survivors are the resumed log's own prefix")
    assert _journal(cut_disk, journal) == crashed + _RESUMED_TAIL, (
        "the resumed log's tail is not the beats, the expiry and the finish "
        "this check hand-wrote:\n%r" % (_journal(cut_disk, journal)[len(crashed):],))
    assert resumed["clock"] == 16, (
        "the resume stops at 16: seven ticks to the lease's death, nine for the "
        "slow job — not %r" % (resumed["clock"],))
    assert killed["report"]["ticks"] == 1, (
        "the report of the killed run stops where its *survivors* stop, at tick "
        "1, and not where the process stopped, at %r" % (killed["report"]["ticks"],))

    # ---- a kill at the tick the claim is made, and one before any sync -----

    first_disk = world.Disk()
    first = s.run(plan, disk=first_disk, effects=work.Effects(),
                  workers=({"owner": "w1", "ticks": 4, "dies_at": 0},
                           {"owner": "w2", "ticks": 4, "dies_at": None}))
    assert first["clock"] == 0, (
        "an owner killed at the tick it claims stops the run *there*, at 0, not "
        "at %r — the tick has to be checked before it is advanced" % (first["clock"],))
    assert first["lost"] == ((journal,
                              "0 claim job=fast owner=w1 ticks=4\n"
                              "0 claim job=slow owner=w2 ticks=4\n"),), (
        "the kill at tick 0 costs the two claims it was taken by: %r"
        % (first["lost"],))
    assert first["states"] == {}, (
        "nothing but the `start` was synced, so the table names no job: %r"
        % (first["states"],))

    # ---- the kill before a sync: the claim that died with the process -----

    loose_disk = world.Disk()
    loose_world = work.Effects()
    loose = s.run({"bulk": work.job("bulk", ticks=5), "slow": work.job("slow")},
                  disk=loose_disk, effects=loose_world,
                  workers=({"owner": "w1", "ticks": 4, "dies_at": None},
                           {"owner": "w2", "ticks": 4, "dies_at": 2}))
    assert loose["clock"] == 2, (
        "the second worker is killed at its own tick, 2, not %r"
        % (loose["clock"],))
    assert loose["lost"] == ((journal, _LOST_AT_TICK_2),), (
        "a kill before any sync costs both claims and the beats of tick 1: %r"
        % (loose["lost"],))
    assert loose["report"]["synced"] == 37, (
        "the `start` line is the only durable byte left, 37 of them, not %r"
        % (loose["report"]["synced"],))
    assert _journal(loose_disk, journal) == "0 start key=run-1 text=%s\n" % (
        loose["events"][0]["text"],), (
        "the journal at the kill is the `start` line and nothing else: %r"
        % (_journal(loose_disk, journal),))
    assert loose["states"] == {}, (
        "the log names no job, so the table invents none: %r"
        % (loose["states"],))
    assert {job: status_of(loose["states"].get(job, "pending"))
            for job in ("bulk", "slow")} == {"bulk": "pending",
                                            "slow": "pending"}, (
        "a claim that died with the process leaves the job `pending`, not "
        "`running` and not `expired`: %r" % (loose["states"],))
    assert s6.recovered(loose_disk, now=99) == {} and s5.reclaimable(
        s3.replay(loose_disk), now=99) == (), (
        "there is no lease to honour and no id to reclaim: the claim never "
        "became a fact")
    assert s8.read_checkpoint(loose_disk) is None, (
        "`checkpoint_every=None` writes no checkpoint at all")

    loose_twin = world.Disk()
    loose_whole = s.run({"bulk": work.job("bulk", ticks=5),
                         "slow": work.job("slow")},
                        disk=loose_twin, effects=work.Effects())
    back = s.run({"bulk": work.job("bulk", ticks=5), "slow": work.job("slow")},
                 disk=loose_disk, effects=loose_world)
    assert statuses(back) == statuses(loose_whole), (
        "the resume finishes the plan the crash interrupted: %r vs %r"
        % (statuses(back), statuses(loose_whole)))
    assert once(loose_world, {"bulk": work.job("bulk", ticks=5),
                              "slow": work.job("slow")}, result=back)[0], (
        "every key applied exactly once when the claim died instead of the "
        "world: %r" % (loose_world.log(),))
    assert "expire " not in _journal(loose_disk, journal) and (
        "retry " not in _journal(loose_disk, journal)), (
        "a job nobody held durably is not expired and not re-issued — it is "
        "claimed: %r" % (_journal(loose_disk, journal)[37:],))
    assert "0 claim job=bulk owner=w1 ticks=4\n" in _journal(loose_disk, journal), (
        "the second process claims afresh under the log's first owner — the log "
        "never read `w1` as a claimant, so the label is nobody's: %r"
        % (_journal(loose_disk, journal)[37:],))
    assert _journal(loose_disk, journal).count("claim ") == 2, (
        "two claims in the resumed log, the two the resume wrote: %r"
        % (_journal(loose_disk, journal)[37:],))

    # ---- the effect that landed before the line that proves it ------------

    held_disk = world.Disk()
    held_world = work.Effects()
    held = s.run(plan, disk=held_disk, effects=held_world,
                 workers=({"owner": "w1", "ticks": 4, "dies_at": None},
                          {"owner": "w2", "ticks": 4, "dies_at": 5}))
    assert held["clock"] == 5, (
        "the kill lands at tick 5, not %r" % (held["clock"],))
    assert held["states"] == {"fast": "running", "slow": "running"}, (
        "neither job is done while the process that held both leases is gone: "
        "%r" % (held["states"],))
    assert held_world.count("effect:fast") == 1, (
        "`fast`'s effect landed before the kill: %r" % (held_world.applied(),))
    assert "effect job=fast" not in _journal(held_disk, journal), (
        "and the line that proves it was not synced: %r"
        % (_journal(held_disk, journal),))
    assert "intent job=fast key=effect:fast" in _journal(held_disk, journal), (
        "the intent, synced before the effect, is exactly what survived: %r"
        % (_journal(held_disk, journal),))

    carried = s.run(plan, disk=held_disk, effects=held_world)
    assert carried["states"] == whole["states"], (
        "the resume over the effect that landed before its line ends with the "
        "uninterrupted run's states: %r" % (carried["states"],))
    assert held_world.count("effect:fast") == 1, (
        "stage 7's `settle` records the line the world can prove instead of "
        "applying the effect again — the count is 1, not 2: %r"
        % (held_world.applied(),))
    assert held_world.count("effect:slow") == 1, (
        "and the other job's effect landed once too: %r" % (held_world.applied(),))
    assert _journal(held_disk, journal).count("intent job=fast key=effect:fast") == 2, (
        "the second attempt announces its intent again, and only its line is "
        "added: %r" % (_journal(held_disk, journal),))
    assert once(held_world, plan, result=carried)[0], (
        "exactly once, over a resume that found the world ahead of the log: %r"
        % (held_world.log(),))

    # ---- the cap, before the claims, and an owner's own lease length ------

    three_plan = {"slow": work.job("slow"), "fast": work.job("fast"),
                  "bulk": work.job("bulk")}
    three_disk = world.Disk()
    three_world = work.Effects()
    three = s.run(three_plan, disk=three_disk, effects=three_world)
    assert statuses(three) == {job: "done" for job in three_plan}, (
        "three jobs, and the cap of two still finishes them all: %r"
        % (statuses(three),))
    assert once(three_world, three_plan, result=three)[0], (
        "each of the three keys applied exactly once: %r" % (three_world.log(),))
    order = [one["job"] for one in three["events"] if one["kind"] == "claim"]
    assert order == ["bulk", "fast", "slow"], (
        "the plan is worked in id order, whoever wrote the mapping: %r"
        % (order,))
    held = []
    for one in three["events"]:
        if one["kind"] == "claim":
            held.append(one["job"])
        elif one["kind"] == "result":
            break
    assert held == ["bulk", "fast"], (
        "exactly two claims stand in the air before the first `result` — the cap "
        "of two, applied *before* the claims: %r" % (held,))

    speed_disk = world.Disk()
    s.run({"slow": work.job("slow")}, disk=speed_disk, effects=work.Effects(),
          limit=1, workers=({"owner": "speed", "ticks": 6, "dies_at": None},))
    speed = _journal(speed_disk, journal)
    assert "0 claim job=slow owner=speed ticks=6\n" in speed, (
        "a claim is granted the owner's own lease length, six ticks, not the "
        "synthetic four: %r" % (speed,))
    assert speed.count("beat job=slow owner=speed ticks=6\n") == 9, (
        "every beat renames the deadline for the same six ticks: %r"
        % (speed.count("beat job=slow owner=speed ticks=6\n"),))
    assert "9 result job=slow owner=speed status=ok ticks=9\n" in speed, (
        "`sluggish` costs nine ticks whatever its lease is: %r" % (speed,))

    idle = s.run(three_plan, disk=three_disk, effects=three_world)
    assert idle["clock"] == three["clock"], (
        "a fresh clock handed to a resume is advanced to where the log left off, "
        "%r and not %r" % (idle["clock"], three["clock"]))
    assert idle["report"]["claimed"] == three["report"]["claimed"] == 3, (
        "a resume over a finished log claims nothing and re-issues nothing: %r"
        % (idle["report"],))
    assert idle["report"]["ticks"] == three["report"]["ticks"] == 10, (
        "the run's last line is the `done` at tick 10, and the resume stops "
        "there too: %r" % (idle["report"],))

    # ---- the refusals, each naming its offender ---------------------------

    message = _refuses(
        s1.DurableError, "a plan that is not a mapping",
        lambda: s.run(["fast"], disk=world.Disk(), effects=work.Effects()))
    assert "plan" in message, (
        "the refusal of a plan that is not a mapping does not name it: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "a plan whose key is not its job's id",
        lambda: s.run({"slow": work.job("fast")}, disk=world.Disk(),
                      effects=work.Effects()))
    assert "slow" in message and "fast" in message, (
        "the refusal of a key that is not its job's id names neither the key "
        "nor the id: %r" % (message,))

    message = _refuses(
        s1.DurableError, "a plan whose job is not a work.Job",
        lambda: s.run({"fast": {"id": "fast"}}, disk=world.Disk(),
                      effects=work.Effects()))
    assert "work.Job" in message, (
        "the refusal of a job that is not a work.Job does not name the type: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "an empty plan",
        lambda: s.run({}, disk=world.Disk(), effects=work.Effects()))
    assert "plan" in message and "one job" in message, (
        "the refusal of an empty plan does not say what a plan needs: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "a disk that is not the world's",
        lambda: s.run(plan, disk={}, effects=work.Effects()))
    assert "Disk" in message, (
        "the refusal of a disk that is not a Disk does not name it: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "a world that is not a work.Effects",
        lambda: s.run(plan, disk=world.Disk(), effects={}))
    assert "Effects" in message, (
        "the refusal of an effects that is not the world does not name it: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "a clock that is not a fleet.Clock",
        lambda: s.run(plan, disk=world.Disk(), effects=work.Effects(),
                      clock="later"))
    assert "fleet.Clock" in message, (
        "the refusal of a clock that is not a fleet.Clock does not name it: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "a worker whose dies_at is not a tick",
        lambda: s.run(plan, disk=world.Disk(), effects=work.Effects(),
                      workers=({"owner": "w1", "ticks": 4, "dies_at": True},)))
    assert "non-negative int" in message, (
        "the refusal of a `dies_at` that is a bool does not name what a tick "
        "is: %r" % (message,))

    message = _refuses(
        s1.DurableError, "a run id that cannot be written into a line",
        lambda: s.run(plan, disk=world.Disk(), effects=work.Effects(),
                      run_id="run 1"))
    assert "run id" in message, (
        "the refusal of a run id with a space in it does not name the id: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "a limit of zero",
        lambda: s.run(plan, disk=world.Disk(), effects=work.Effects(), limit=0))
    assert "positive" in message, (
        "the refusal of a limit of zero does not say what a limit is: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "a checkpoint_every of zero",
        lambda: s.run(plan, disk=world.Disk(), effects=work.Effects(),
                      checkpoint_every=0))
    assert "positive" in message, (
        "the refusal of a checkpoint_every of zero does not say so: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "a workers that is a string",
        lambda: s.run(plan, disk=world.Disk(), effects=work.Effects(),
                      workers="w1"))
    assert "workers" in message, (
        "the refusal of a workers that is not a tuple does not name it: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "a worker with no dies_at",
        lambda: s.run(plan, disk=world.Disk(), effects=work.Effects(),
                      workers=({"owner": "w1", "ticks": 4},)))
    assert "dies_at" in message, (
        "the refusal of a worker with no dies_at does not name the field: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "a worker whose ticks is zero",
        lambda: s.run(plan, disk=world.Disk(), effects=work.Effects(),
                      workers=({"owner": "w1", "ticks": 0, "dies_at": None},)))
    assert "positive" in message, (
        "the refusal of a lease of zero ticks does not say so: %r" % (message,))

    # a resume is allowed only over this run's log, and this run's checkpoint
    once_disk = world.Disk()
    once_world = work.Effects()
    s.run(plan, disk=once_disk, effects=once_world)

    message = _refuses(
        s1.DurableError, "a log no `start` line begins",
        lambda: s.run(plan, disk=_orphan(world, s1), effects=work.Effects()))
    assert "start" in message, (
        "the refusal of a log no run begins does not name the `start` line: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "a resume under another run's id",
        lambda: s.run(plan, disk=once_disk, effects=work.Effects(),
                      run_id="run-2"))
    assert "run-1" in message and "run-2" in message, (
        "the refusal of another run's log names neither run: %r" % (message,))

    message = _refuses(
        s1.DurableError, "a resume over another plan",
        lambda: s.run({"fast": work.job("fast"),
                       "slow": work.job("slow", ticks=2)},
                      disk=once_disk, effects=once_world))
    assert "plan" in message, (
        "the refusal of another plan's log does not name the plan: %r"
        % (message,))

    checkpointed = world.Disk()
    s.run(plan, disk=checkpointed, effects=work.Effects(), checkpoint_every=1)
    kept = s8.read_checkpoint(checkpointed)
    assert kept is not None and kept["run"] == "run-1" and kept["states"] == {
        "fast": "done", "slow": "done"}, (
        "a checkpoint every finished job leaves the run's own states: %r"
        % (kept,))

    message = _refuses(
        s1.DurableError, "a resume over somebody else's checkpoint",
        lambda: s.run(plan, disk=checkpointed, effects=work.Effects(),
                      run_id="run-2"))
    assert "run-2" in message and "run-1" in message, (
        "the refusal of another run's checkpoint names neither run: %r"
        % (message,))

    message = _refuses(
        s1.DurableError, "a resume over a checkpoint of another plan",
        lambda: s.run({"fast": work.job("fast"),
                       "slow": work.job("slow", ticks=2)},
                      disk=checkpointed, effects=work.Effects()))
    assert "plan" in message, (
        "the refusal of another plan's checkpoint does not name the plan: %r"
        % (message,))

    print("check_10: the capstone — one hand-written run of two workers in the "
          "air, its report recounted from its own lines; a kill after a "
          "checkpoint's barrier that leaves a lease the resume must wait out to "
          "`deadline + MAX_MISSES` and a kill before any sync that leaves "
          "nothing but the `start`; states and effects equal to the "
          "uninterrupted run either way, every key applied exactly once, and "
          "every refusal naming its offender")

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The line, and the journal that holds it",
        tags=["journal", "validation"],
        action="Write `LINE_KEYS`, `DurableError`, `JournalError`, `line`, "
               "`parse_line` and `write_line` in stage_01.py.",
        predict="What a line of a journal has to carry so that a reader who was "
                "not there can tell what happened — and why a field a kind does "
                "not carry must be refused rather than dropped.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The write that was not synced did not happen",
        tags=["sync", "durability"],
        action="Write `append`, `commit`, `lost` and `survives` in stage_02.py.",
        predict="What a crash costs when you write without syncing, and why the "
                "program that believed its own unsynced write is the failure — "
                "not the crash.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="Replay, and the tail that was never finished",
        tags=["replay", "state"],
        action="Write `replay`, `state_of` and `torn` in stage_03.py.",
        predict="Which line decides a job's state after a replay — the last one, "
                "or the newest claim that was never answered — and what a crash "
                "in the middle of an append leaves behind.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The lease, and the owner that stops answering",
        tags=["lease", "expiry"],
        action="Write `LeaseError`, `claim`, `lease_of`, `expired` and `renew` in "
               "stage_04.py.",
        predict="Whether a lease that expires exactly now is still held, and what "
                "a second owner is allowed to do to a job somebody else holds.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The heartbeat, and the worker that dies holding the slot",
        tags=["heartbeat", "recovery"],
        action="Write `MAX_MISSES`, `heartbeat`, `dead`, `recover` and "
               "`reclaimable` in stage_05.py.",
        predict="How long a job waits for an owner that stopped answering, and "
                "what a heartbeat from somebody who is not the owner means.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="Crash, and the process that comes after it",
        tags=["crash", "recovery"],
        action="Write `RecoveryError`, `crash` and `recovered` in stage_06.py.",
        predict="What the process that wakes up after a crash is allowed to "
                "believe — everything the disk holds, or only what it had "
                "synced.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The effect that happens exactly once",
        tags=["idempotency", "effects"],
        action="Write `EffectError`, `intent`, `apply_effect` and `settle` in "
               "stage_07.py.",
        predict="What has to be on disk *before* an effect runs, and what a "
                "replay does with an intent whose effect may or may not have "
                "landed.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The resume, and the log that is not this run's",
        tags=["resume", "checkpoint"],
        action="Write `ResumeError`, `checkpoint`, `read_checkpoint`, `repair` "
               "and `resume` in stage_08.py.",
        predict="What a resume may replay, what it must refuse, and what a torn "
                "tail costs when the only alternative is guessing what a "
                "half-written line meant.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The report, and the number that has to come from the log",
        tags=["report", "audit"],
        action="Write `REPORT_KEYS`, `report` and `audit` in stage_09.py.",
        predict="Which of a run's numbers its memory can supply and which only "
                "the lines can, and what a total the log contradicts has to do.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="Two workers, one killed holding the lease",
        tags=["durability", "capstone"],
        action="Write `DEFAULT_LIMIT` and `run` in stage_10.py.",
        predict="What the resumed run has to do with the job the killed worker "
                "was holding, and how an effect whose intent was synced but "
                "whose outcome is unknown can still happen exactly once.",
        check=check_10,
    ),
]
