"""Agent Metrics From Scratch — course manifest.

Ten graded stages between a fleet that writes down what happened and a dashboard
whose every number is a fold of those events over a window somebody chose. The
world is provided: `fleet.py` is J1's verbatim (the injected clock, the task and
pool fixtures, and the five worker plans this course records), and `telemetry.py`
is everything the fleet leaves behind — the twelve event fields and the five
kinds that carry them, the fleet's own reader and writer, the prices that are a
property of the pool, the window fixtures, the objectives, and `record()`, which
runs the fleet deterministically and counts what it did *as it goes*.

The thesis of the whole course is one sentence, and every stage's check asserts
it: A TRACE IS NOT A METRIC — A METRIC IS A FOLD OVER A WINDOW, THE WINDOW IS THE
DECISION, AND THE ONLY PROOF THE FOLD LOST NOTHING IS THE FLEET'S OWN COUNT. Every
stage is one half of that sentence: what an event is and which fields its kind
carries, where a window ends and why `[start, end)` makes a tumbling set a
partition, why a queue depth has a value at an instant and may not be summed over
time, why a percentile is an index and not an interpolation, which half of a
latency a retry moved, why a cost is summed before it is divided, why a rate that
does not name its denominator is a number nobody can defend, why a step past a
width leaves a hole, how a report is recomputed from the events and cross-checked
against the fleet's own count, and where two windows of the same run stop being
the same answer. The failures worth preventing are the ones that look like
success: a finish counted in two tumbling windows, an event exactly on the
boundary counted twice, a `p95` interpolated between two samples that never
happened, an unfinished task's latency reported as the sum of its attempts, a
per-event cost rounded and then summed, a rate whose denominator was the wrong
counter, and a report whose numbers came from the run's memory instead of its
lines.

Standard library only, offline, deterministic, **ints only** (ticks, tokens,
micros and basis points — no floats anywhere): no `time`, no `threading`, no
`asyncio`, no `os`, no sockets, no subprocesses, no unseeded randomness, no
module-level mutable state, and no `statistics`, `math`, `decimal` or `fractions`
either — a course about which fold a number came from cannot let a library decide
the two things it exists to decide by hand. `deploy-and-debug` (A7) does the same
work over floats and a live histogram; here every ratio is an exact reduced pair
and every scalar is basis points floored, so the check can assert the digit.

    python3 codecraft/cli.py run agent-metrics-from-scratch
"""

from codecraft.api import stage

TITLE = "Agent Metrics From Scratch"
DESCRIPTION = ("A trace as the input and a metric as the fold: the event and the "
               "fields its kind carries, a half-open window that makes a tumbling "
               "set a partition, queue depth as a gauge that is derived from two "
               "counters and may never be summed, percentiles as nearest-rank "
               "indices over exact integers, latency split into the wait, the "
               "service and the retry gap, tokens and micros summed before they "
               "are divided, failure and retry rates that name their own "
               "denominators, a step that may not leave a hole, a report recomputed "
               "from the events and cross-checked key by key against the fleet's own "
               "count, and a capstone whose budget is spent by the size of an "
               "overshoot and whose alert names the window that spent the last of "
               "it.")
LEVEL = "advanced"
ORDER = 24


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "agent-metrics-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J5_REPO=/path/to/learn-stuff-from-scratch")

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

    import fleet
    import stage_01 as s
    import telemetry as world

    # ---- the vocabulary every later stage speaks --------------------------

    assert s.EVENT_KEYS == world.EVENT_KEYS, (
        "this stage's event fields are %r, not the twelve the world writes"
        % (s.EVENT_KEYS,))
    assert s.KINDS == world.KINDS, (
        "this stage's kinds are %r, not the five the world records — and the "
        "order is a claim: a finish at tick t is a departure at tick t"
        % (s.KINDS,))
    assert s.ABSENT == world.ABSENT == "-", (
        "an absent field is spelled %r: it must be a spelling no value could be, "
        "or a measured value and an unmeasured one read the same" % (s.ABSENT,))
    assert isinstance(s.CARRIES, Mapping) and set(s.CARRIES) == set(s.KINDS), (
        "CARRIES covers %r, not the five kinds" % (sorted(s.CARRIES),))
    assert isinstance(s.REQUIRED, Mapping) and set(s.REQUIRED) == set(s.KINDS), (
        "REQUIRED covers %r, not the five kinds" % (sorted(s.REQUIRED),))
    for kind in s.KINDS:
        carried = s.CARRIES[kind]
        assert isinstance(carried, tuple) and "attempt" in carried, (
            "a %s event carries %r: every kind carries its attempt" % (kind, carried))
        assert all(key in s.EVENT_KEYS for key in carried), (
            "a %s event carries %r, and one of those is not an event field"
            % (kind, carried))
        assert s.REQUIRED[kind] == tuple(k for k in carried if k != "error"), (
            "a %s event requires %r: every field the kind carries is required "
            "of it except `error`, which a call that succeeded has none of"
            % (kind, s.REQUIRED[kind]))
    assert s.CARRIES["admitted"] == ("attempt",), (
        "an admitted event carries %r: it has not run yet" % (s.CARRIES["admitted"],))
    assert s.CARRIES["started"] == ("attempt", "wait"), (
        "a started event carries %r: it has waited and not yet finished"
        % (s.CARRIES["started"],))
    assert s.CARRIES["finished"] == ("attempt", "outcome", "service", "tokens_in",
                                     "tokens_out", "error"), (
        "a finished event carries %r: what it ended as, how long it took and what "
        "it spent" % (s.CARRIES["finished"],))
    assert issubclass(s.TelemetryError, ValueError), (
        "%r is not a ValueError: every refusal in this course is a verdict on a "
        "value, and every later stage derives its own from this one"
        % (s.TelemetryError,))
    assert issubclass(s.EventError, s.TelemetryError), (
        "%r is not a %s: one `except TelemetryError` must still catch a broken "
        "event" % (s.EventError, s.TelemetryError.__name__))

    # ---- carries: a closed vocabulary -------------------------------------

    for kind in s.KINDS:
        assert s.carries(kind) == s.CARRIES[kind], (
            "carries(%r) answers %r, not what CARRIES says" % (kind, s.carries(kind)))
    message = _refuses(s.EventError, "a kind that is a typo",
                       lambda: s.carries("finshed"))
    assert "finshed" in message and "finished" in message, (
        "the refusal of 'finshed' does not name it and suggest the real kind: %r"
        % (message,))
    message = _refuses(s.EventError, "a name no kind could be",
                       lambda: s.carries("frobnicate"))
    assert "frobnicate" in message and "did you mean" not in message, (
        "the refusal of 'frobnicate' suggests a name anyway: a suggestion that is "
        "not close is a lie, and the distance is two: %r" % (message,))
    message = _refuses(s.EventError, "a kind that is not a str",
                       lambda: s.carries(7))
    assert "str" in message and "7" in message, (
        "the refusal of a non-str kind does not name its shape and the offender: %r"
        % (message,))

    # ---- a run, and the reader the world's own lines demand ----------------

    run = world.record()
    lines = run["text"]
    events = tuple(s.parse_event(line) for line in lines)
    assert events == world.read(lines)["events"], (
        "the stage reads the world's own lines differently than the world does")
    assert all(list(event) == list(s.EVENT_KEYS) for event in events), (
        "a parsed event is not a record over exactly the twelve fields, in order")
    for line, event in zip(lines, events):
        assert s.write_event(event) == line, (
            "write_event is not the inverse of parse_event: %r came back as %r"
            % (line, s.write_event(event)))
        assert s.write_event(s.parse_event(line)) == line, (
            "a line the world wrote does not survive the round trip: %r" % (line,))
    assert "  " not in s.write_event(events[0]) and not s.write_event(
        events[0]).endswith(" "), (
        "a written line has a double or a trailing space, so it does not split "
        "into twelve fields: %r" % (s.write_event(events[0]),))
    whole = s.read_events(lines)
    assert whole == events, "read_events does not read a whole run the way one "
    assert isinstance(whole, tuple), (
        "read_events answers %r: a run is a sequence of events, not a list "
        "somebody may append to" % (type(whole).__name__,))
    assert s.read_events(lines[0]) == (events[0],), (
        "one line handed over as a str is not read as one event")
    assert s.read_events(()) == (), "an empty run has no events in it"

    # ---- the kind decides the fields, both ways ---------------------------

    base = {"tick": 3, "task": "render", "pool": "small", "tenant": "batch",
            "kind": "finished", "attempt": 1, "outcome": "ok", "wait": "-",
            "service": 4, "tokens_in": 120, "tokens_out": 40, "error": "-"}
    assert s.parse_event(base) == base, (
        "a well-formed finished event is not read as itself")
    assert s.parse_event(base)["tick"] == 3, "a parsed count is not an int"
    started = dict(base, kind="started", outcome="-", service="-", wait=2,
                   tokens_in="-", tokens_out="-")
    assert s.parse_event(started) == started, (
        "a well-formed started event is not read as itself")
    retried = dict(base, kind="retried", outcome="-", service="-", tokens_in="-",
                   tokens_out="-", error="-")
    assert s.parse_event(retried) == retried, (
        "a retried event with no error is refused: `error` is the one field a "
        "kind carries that may be empty — the reason a retry happened is not "
        "always known, and inventing one would be worse")
    dropped = dict(base, kind="dropped", outcome="-", service="-", tokens_in="-",
                   tokens_out="-", error="queue_full")
    assert s.parse_event(dropped) == dropped, (
        "a well-formed dropped event is not read as itself")
    admitted = dict(base, kind="admitted", outcome="-", service="-", wait="-",
                    tokens_in="-", tokens_out="-")
    assert s.parse_event(admitted) == admitted, (
        "a well-formed admitted event is not read as itself")

    message = _refuses(s.EventError, "a started event carrying an outcome",
                       lambda: s.parse_event(started | {"outcome": "ok"}))
    assert "outcome" in message and "started" in message, (
        "the refusal of a field a kind does not carry does not name the field and "
        "the kind: %r" % (message,))
    message = _refuses(s.EventError, "an admitted event carrying a wait",
                       lambda: s.parse_event(admitted | {"wait": 2}))
    assert "wait" in message, (
        "an admitted event is not refused for carrying a wait: %r" % (message,))
    message = _refuses(s.EventError, "a finished event with no outcome",
                       lambda: s.parse_event(base | {"outcome": "-"}))
    assert "outcome" in message and "finished" in message, (
        "the refusal of a field a kind requires does not name the field and the "
        "kind: %r" % (message,))
    message = _refuses(s.EventError, "a dropped event with no attempt",
                       lambda: s.parse_event(dropped | {"attempt": "-"}))
    assert "attempt" in message, (
        "a dropped event does not need its attempt: %r" % (message,))

    # ---- the numbers and the names ----------------------------------------

    message = _refuses(s.EventError, "a count handed over as a bool",
                       lambda: s.parse_event(base | {"service": True}))
    assert "bool" in message and "service" in message, (
        "`True` is one tick and one service: a bool in a count is refused by name, "
        "or the first int a caller reached for with a flag is summed into a "
        "latency: %r" % (message,))
    # the one float literal in this repository, and it is here to be refused:
    # every count in this course is an int, and a check that cannot name a float
    # cannot prove the stage refuses one.
    message = _refuses(s.EventError, "a count handed over as a float",
                       lambda: s.parse_event(base | {"tokens_in": 1.5}))
    assert "int" in message, (
        "a count that is not an int is not named as one: %r" % (message,))
    message = _refuses(s.EventError, "a negative count",
                       lambda: s.parse_event(base | {"service": -1}))
    assert "negative" in message and "service" in message, (
        "a negative service is not refused by name: %r" % (message,))
    message = _refuses(s.EventError, "an attempt counted from zero",
                       lambda: s.parse_event(base | {"attempt": 0}))
    assert "1" in message and "attempt" in message, (
        "an attempt is counted from 1: %r" % (message,))
    message = _refuses(s.EventError, "an empty task name",
                       lambda: s.parse_event(base | {"task": ""}))
    assert "task" in message, (
        "an empty name is not refused by name: %r" % (message,))
    message = _refuses(s.EventError, "a record whose task is `-`",
                       lambda: s.parse_event(base | {"task": "-"}))
    assert "task" in message, (
        "a task named `-` is accepted: `-` is the spelling of a field nobody "
        "measured, and a run whose task is `-` is a run whose fourth line was "
        "dropped: %r" % (message,))
    message = _refuses(s.EventError, "a record with no tick at all",
                       lambda: s.parse_event(base | {"tick": "-"}))
    assert "tick" in message, (
        "an event with no tick is accepted: every kind carries the instant it "
        "happened at, or no fold above this stage can put it in a window: %r"
        % (message,))
    message = _refuses(s.EventError, "a kind in the wrong case",
                       lambda: s.parse_event(base | {"kind": "Finished"}))
    assert "Finished" in message and "finished" in message, (
        "the refusal of 'Finished' does not name it and suggest the real kind: a "
        "kind is not folded, or a policy matches in the check and not in "
        "production: %r" % (message,))
    message = _refuses(s.EventError, "a name with a space in it",
                       lambda: s.parse_event(base | {"pool": "two words"}))
    assert "pool" in message or "space" in message, (
        "a name with a space is a line that no longer splits into twelve fields, "
        "and it is not refused: %r" % (message,))
    message = _refuses(s.EventError, "an outcome the fleet does not have",
                       lambda: s.parse_event(base | {"outcome": "faield"}))
    assert "faield" in message and "failed" in message, (
        "the refusal of a bad outcome does not name it and suggest the real one: %r"
        % (message,))
    message = _refuses(s.EventError, "an error with a space in it",
                       lambda: s.parse_event(dropped | {"error": "queue full"}))
    assert "queue full" in message or "space" in message, (
        "an error that is two words is not refused: it would be written into a "
        "line with no quoting and read back as two fields: %r" % (message,))

    # ---- the same rules through the mapping door --------------------------

    missing = {key: value for key, value in base.items() if key != "tokens_out"}
    message = _refuses(s.EventError, "a record with no tokens_out",
                       lambda: s.parse_event(missing))
    assert "tokens_out" in message, (
        "the refusal of a missing field does not name it: %r" % (message,))
    message = _refuses(s.EventError, "a record with a field nobody has",
                       lambda: s.parse_event(base | {"nope": 1}))
    assert "nope" in message, (
        "the refusal of an extra field does not name it: %r" % (message,))
    message = _refuses(s.EventError, "a record with a misspelled field",
                       lambda: s.parse_event(base | {"token_in": 1}))
    assert "token_in" in message and "tokens_in" in message, (
        "the refusal of a misspelled field does not suggest the real one: %r"
        % (message,))
    message = _refuses(s.EventError, "a record whose count is text",
                       lambda: s.parse_event(base | {"tick": "3"}))
    assert "int" in message and "tick" in message, (
        "a count handed over as text is a line's business: a mapping is a record, "
        "and a record's count is an int: %r" % (message,))
    message = _refuses(s.EventError, "a record whose kind nobody has",
                       lambda: s.parse_event(base | {"kind": "finishedd"}))
    assert "finishedd" in message and "finished" in message, (
        "the mapping door does not check the kind: %r" % (message,))
    message = _refuses(s.EventError, "an event that is not a mapping or a line",
                       lambda: s.parse_event(["tick", 3]))
    assert "mapping" in message and "line" in message, (
        "the refusal of a shape that is neither a line nor a mapping does not name "
        "both shapes it could have been: %r" % (message,))
    shuffled = {key: base[key] for key in reversed(list(base))}
    assert s.parse_event(shuffled) == base, (
        "a mapping whose keys are in the caller's own order is refused: an order "
        "is a line's business, and a record is a mapping like any other")
    assert list(s.parse_event(shuffled)) == list(s.EVENT_KEYS), (
        "a record parsed from a mapping keeps the caller's key order: a record is "
        "a record over the twelve fields in the format's order, whatever order "
        "the caller wrote it in — that is what makes two of them comparable")
    given = dict(base)
    record = s.parse_event(given)
    given["tick"] = 99
    assert record["tick"] == 3, (
        "a parsed record is the caller's mapping under another name: bending one "
        "bends the other, and a fold above this stage would read a count the "
        "caller changed after handing it over")
    message = _refuses(s.EventError, "a record written over a name",
                       lambda: s.write_event(base | {"task": 7}))
    assert "task" in message, (
        "write_event writes a record that parse_event refuses: %r" % (message,))
    assert s.write_event(shuffled) == s.write_event(base), (
        "the line a record is written as depends on the order its caller happened "
        "to write the mapping in: %r is not %r"
        % (s.write_event(shuffled), s.write_event(base)))

    # ---- lines: the format itself -----------------------------------------

    message = _refuses(s.EventError, "a line with a field missing",
                       lambda: s.parse_event(" ".join(lines[0].split(" ")[:-1])))
    assert "11" in message and "12" in message, (
        "the refusal of an eleven-field line does not say how many fields the "
        "format has: %r" % (message,))
    message = _refuses(s.EventError, "a line with an extra field",
                       lambda: s.parse_event(lines[0] + " extra=1"))
    assert "13" in message, (
        "the refusal of a thirteen-field line does not say how many fields it "
        "found: %r" % (message,))
    message = _refuses(s.EventError, "a field that is not key=value",
                       lambda: s.parse_event(lines[0].replace("tick=0", "tick0")))
    assert "key=value" in message, (
        "the refusal of a field with no `=` does not say what a field is: %r"
        % (message,))
    message = _refuses(s.EventError, "a line whose fields are in the wrong order",
                       lambda: s.parse_event(
                           " ".join([lines[0].split(" ")[1], lines[0].split(" ")[0]]
                                    + lines[0].split(" ")[2:])))
    assert "position" in message or "field 0" in message, (
        "the refusal of a reordered line does not name the position it read wrong: "
        "%r" % (message,))
    message = _refuses(s.EventError, "a line whose tick is not a number",
                       lambda: s.parse_event(lines[0].replace("tick=0", "tick=x")))
    assert "tick" in message and "x" in message, (
        "the refusal of a non-numeric count does not name the field and the text: "
        "%r" % (message,))
    message = _refuses(s.EventError, "a line with a negative tick",
                       lambda: s.parse_event(lines[0].replace("tick=0", "tick=-1")))
    assert "negative" in message or "-1" in message, (
        "a line with a negative tick is accepted: %r" % (message,))
    message = _refuses(s.EventError, "a read_events run whose second line is not "
                                     "an event",
                       lambda: s.read_events((lines[0], "not-an-event", lines[1])))
    assert "line 1" in message and "not-an-event" in message, (
        "the refusal of a bad line does not name its index and its text: a run "
        "whose second line was dropped is not a run with one line in it: %r"
        % (message,))
    # the same door again, over a line whose own refusal quotes only the *chunk*
    # it choked on: only a reader that quotes the whole line can be repaired from
    # its message, because the chunk is one field of twelve.
    broken = lines[0].replace("tick=0", "tick=x")
    message = _refuses(s.EventError, "a read_events run whose first line is not an "
                                     "event",
                       lambda: s.read_events((broken, lines[1])))
    assert "line 0" in message and broken in message, (
        "the refusal of a bad line does not quote the line itself, only the field "
        "it choked on: %r" % (message,))
    message = _refuses(s.EventError, "a run holding something that is not a str",
                       lambda: s.read_events((lines[0], 7)))
    assert "line 1" in message and "str" in message, (
        "the refusal of a non-str line does not name its index and its shape: %r"
        % (message,))
    message = _refuses(s.EventError, "a run handed over as an int",
                       lambda: s.read_events(12))
    assert "line" in message and "int" in message, (
        "the refusal of a shape that is not a sequence of lines does not say what "
        "it takes and what it was given: %r" % (message,))

    # ---- the world's other plans read too ---------------------------------

    for plan in ("sickly", "reliable", "crasher"):
        other = world.record(worker=plan)
        read = s.read_events(other["text"])
        assert read == world.read(other["text"])["events"], (
            "the %s run's lines do not read back the way the world read them"
            % (plan,))
        assert all(s.write_event(event) in other["text"] for event in read), (
            "a %s run's events do not write back as lines of that run" % (plan,))
    assert s.parse_event(world.line(events[0])) == events[0], (
        "the world's own writer and this stage's reader disagree about an event "
        "neither of them built by hand")
    assert isinstance(s.TelemetryError, type) and issubclass(
        fleet.QueueError, ValueError), (
        "the fleet's refusals are ValueErrors too — one course, one family")

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "agent-metrics-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J5_REPO=/path/to/learn-stuff-from-scratch")

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

    import stage_01
    import stage_02 as s
    import telemetry as world

    # ---- the refusal family ------------------------------------------------

    assert issubclass(s.WindowError, stage_01.TelemetryError), (
        "%r is not a %s: every later stage derives its refusal from this one, "
        "and one `except TelemetryError` must still catch a broken window"
        % (s.WindowError, stage_01.TelemetryError.__name__))
    assert issubclass(s.WindowError, ValueError), (
        "%r is not a ValueError: every refusal in this course is a verdict on a "
        "value a caller handed over" % (s.WindowError,))

    # ---- the fixtures ------------------------------------------------------

    bed = tuple(world.event(tick=tick) for tick in (0, 1, 2, 3, 4))
    jumble = tuple(world.event(tick=tick) for tick in (3, 1, 2, 5, 0))
    started = world.event(tick=0, task="render", pool="small", tenant="batch",
                          kind="started", attempt=1, wait=2)
    first = world.event(tick=1, task="render", pool="small", tenant="batch",
                        kind="finished", attempt=1, outcome="ok", service=3,
                        tokens_in=10, tokens_out=5)
    second = world.event(tick=2, task="render", pool="small", tenant="batch",
                         kind="finished", attempt=1, outcome="ok", service=5,
                         tokens_in=10, tokens_out=7)
    both = (started, first, second)

    # ---- window: both sides of the boundary --------------------------------

    inside = s.window(bed, 1, 3)
    assert isinstance(inside, tuple), (
        "window answers %r: a window is a sequence of events, not a list "
        "somebody may append to" % (type(inside).__name__,))
    assert tuple(event["tick"] for event in inside) == (1, 2), (
        "window [1, 3) is %r: an event at tick 1 is in and an event at tick 3 "
        "is out" % (tuple(event["tick"] for event in inside),))
    assert tuple(event["tick"] for event in s.window(bed, 0, 1)) == (0,), (
        "a one-tick window is a window like any other")
    assert tuple(event["tick"]
                 for event in s.window(bed, 0, 5)) == (0, 1, 2, 3, 4), (
        "the whole interval is not the whole run")
    assert s.window(bed, 5, 6) == (), (
        "a valid window with nothing in it answers () rather than refusing")
    assert tuple(event["tick"]
                 for event in s.window(jumble, 1, 4)) == (3, 1, 2), (
        "window reordered its events: a fold never sorts, because two events at "
        "one tick have an order of their own")
    assert tuple(event["tick"]
                 for event in s.window(jumble, 0, 6)) == (3, 1, 2, 5, 0), (
        "window [0, 6) over an out-of-order run is not that run in order")

    # ---- window: the interval that is not one ------------------------------

    message = _refuses(s.WindowError, "a window with no width",
                       lambda: s.window(bed, 2, 2))
    assert "no width" in message and "point has no fold" in message, (
        "a point is not refused for what it is: %r" % (message,))
    message = _refuses(s.WindowError, "a reversed window",
                       lambda: s.window(bed, 3, 1))
    assert "no width" in message, (
        "a window that ends before it starts is accepted: %r" % (message,))
    message = _refuses(s.WindowError, "a start that is not a tick",
                       lambda: s.window(bed, "x", 3))
    assert "start" in message and "int" in message and "x" in message, (
        "a start that is not an int is not refused by name: %r" % (message,))
    message = _refuses(s.WindowError, "an end that is not a tick",
                       lambda: s.window(bed, 0, "y"))
    assert "end" in message and "int" in message and "y" in message, (
        "an end that is not an int is not refused by name: %r" % (message,))
    message = _refuses(s.WindowError, "a start that is a bool",
                       lambda: s.window(bed, True, 3))
    assert "start" in message and "True" in message, (
        "`True` is one tick in Python and a flag in a caller's head: a bool "
        "bound is refused by name: %r" % (message,))
    message = _refuses(s.WindowError, "an end that is a bool",
                       lambda: s.window(bed, 0, False))
    assert "end" in message and "False" in message, (
        "a bool end is not refused by name: %r" % (message,))
    message = _refuses(s.WindowError, "a start below zero",
                       lambda: s.window(bed, -1, 3))
    assert "start" in message and "-1" in message, (
        "a negative start is not refused by name: %r" % (message,))
    message = _refuses(s.WindowError, "an end below zero",
                       lambda: s.window(bed, 0, -5))
    assert "end" in message and "-5" in message, (
        "a negative end is not refused by name: %r" % (message,))

    # ---- count: the events, and the carriers -------------------------------

    assert s.count(bed) == len(bed), (
        "count with no field answers %r, not the %d events it was given"
        % (s.count(bed), len(bed)))
    assert s.count(bed, "tick") == len(bed), (
        "every event carries its own tick")
    assert isinstance(s.count(bed), int) and not isinstance(s.count(bed), bool), (
        "count answers %r: a count is an int" % (s.count(bed),))
    assert s.count(both) == 3, "count with no field counts every event"
    assert s.count(both, "tokens_out") == 2, (
        "count(both, 'tokens_out') is %r: only a finish measured its tokens"
        % (s.count(both, "tokens_out"),))
    assert s.count(both, "wait") == 1, (
        "only the started event carries a wait")
    assert s.count(both, "error") == 0, (
        "count answers zero when nothing measured the field, because 'how many' "
        "has an honest answer of none")
    assert s.count((started,), "tokens_out") == 0, (
        "an event set where nothing carries the field still counts zero")

    # ---- total: the sum over the carriers ----------------------------------

    assert s.total(both, "tokens_out") == 12, (
        "total(both, 'tokens_out') is %r, not 5 + 7"
        % (s.total(both, "tokens_out"),))
    assert s.total(both, "tick") == 3, "total sums the ticks it is given"
    assert s.total((first,), "service") == 3, "total of one carrier is its value"
    assert isinstance(s.total(both, "tick"), int), (
        "a total is an int, not a number that has stopped being whole")
    message = _refuses(s.WindowError, "a total of a field nobody measured",
                       lambda: s.total((started,), "tokens_out"))
    assert "no event here carries" in message and "tokens_out" in message, (
        "a total of nothing is not refused for what it is: an unmeasured field "
        "is not a field whose value is zero: %r" % (message,))
    message = _refuses(s.WindowError, "a total of a misspelled field",
                       lambda: s.total(both, "token_out"))
    assert ("token_out" in message and "did you mean" in message
            and "tokens_out" in message), (
        "the refusal of a misspelled field does not name it and suggest the real "
        "one: %r" % (message,))
    message = _refuses(s.WindowError, "a total of a real field nobody measured",
                       lambda: s.total((started,), "service"))
    assert "service" in message and "did you mean" not in message, (
        "a real field that nobody measured earns no suggestion — only a "
        "misspelling does: %r" % (message,))
    floating = dict(first, service=1.5)
    message = _refuses(s.WindowError, "a field measured as a float",
                       lambda: s.total((floating,), "service"))
    assert "service" in message and "int" in message, (
        "a float in a total is a total that no longer adds up: %r" % (message,))
    flagged = dict(first, service=True)
    message = _refuses(s.WindowError, "a field measured as a bool",
                       lambda: s.total((flagged,), "service"))
    assert "service" in message, (
        "`True` is one tick in Python and a flag in a caller's head: a bool "
        "measurement is refused by name: %r" % (message,))

    # ---- mean: an exact reduced pair ---------------------------------------

    samples = tuple(world.event(tick=1, task="render", pool="small",
                                tenant="batch", kind="finished", attempt=1,
                                outcome="ok", service=value, tokens_in=0,
                                tokens_out=0)
                    for value in (1, 1, 1, 1, 2, 2))
    answer = s.mean(samples, "service")
    assert isinstance(answer, tuple) and len(answer) == 2, (
        "a mean is an exact pair, not %r" % (answer,))
    assert all(isinstance(part, int) and not isinstance(part, bool)
               for part in answer), (
        "a mean is a pair of ints: a float is a ratio that was rounded before "
        "anyone decided where: %r" % (answer,))
    assert answer == (4, 3), (
        "the mean of those services is %r: 8 over 6 is (4, 3), not (8, 6)"
        % (answer,))
    assert s.mean((first,), "service") == (3, 1), (
        "a mean of one sample is that sample over one")
    assert s.mean(both, "tokens_out") == (6, 1), (
        "the mean divides by the carriers, not the events: %r is not 12 over 3"
        % (s.mean(both, "tokens_out"),))
    message = _refuses(s.WindowError, "a mean of no samples",
                       lambda: s.mean((started,), "tokens_out"))
    assert "no event here carries" in message and "tokens_out" in message, (
        "a mean of no samples is not zero, and the refusal must name the field "
        "that had no samples: %r" % (message,))

    # ---- the partitions, and the run nobody bent ---------------------------

    snapshot = tuple(dict(event) for event in both)
    snapshot_jumble = tuple(dict(event) for event in jumble)
    left = s.window(jumble, 0, 2)
    right = s.window(jumble, 2, 6)
    assert s.count(left) + s.count(right) == s.count(jumble), (
        "the tumbling windows [0, 2) and [2, 6) are not a partition of "
        "[0, 6): an event on the boundary is in both or in neither")
    assert (s.total(left, "tick") + s.total(right, "tick")
            == s.total(jumble, "tick")), (
        "summing two tumbling windows does not agree with the whole interval")
    assert jumble == snapshot_jumble, (
        "a fold mutated the events it was given")

    run = world.record()
    events = run["events"]
    assert s.count(events, "tick") == len(events), (
        "the world's own run does not count the way this stage counts")
    assert s.window(events, 0, 1000) == events, (
        "the whole interval is not the whole run: a fold over a superset of the "
        "run must agree with the run")
    s.window(events, 0, 1000)
    s.count(events, "tokens_out")
    s.total(events, "tokens_out")
    s.mean(events, "tick")
    assert both == snapshot, (
        "a fold mutated the events it was given: a fold is a pure function of "
        "what it was handed")
    assert isinstance(events, tuple), (
        "the world's events stopped being a tuple")

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "agent-metrics-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J5_REPO=/path/to/learn-stuff-from-scratch")

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

    import stage_01
    import stage_03 as s
    import telemetry as world

    # ---- the refusal family ----------------------------------------------

    assert issubclass(s.GaugeError, stage_01.TelemetryError), (
        "%r is not the course's TelemetryError: one `except TelemetryError` must "
        "still catch a broken gauge" % (s.GaugeError,))
    assert issubclass(s.GaugeError, ValueError), (
        "%r is not a ValueError: every refusal in this course is a verdict on a "
        "value" % (s.GaugeError,))

    # ---- the world's own run, tick by tick --------------------------------

    run = world.record()
    events = run["events"]
    clock = run["clock"]
    series = s.depth_series(events, 0, clock + 1)
    assert isinstance(series, tuple), (
        "depth_series answers %r: a series is a tuple, not a list somebody may "
        "append to" % (type(series).__name__,))
    assert len(series) == clock + 1 == 48, (
        "the series has %d numbers for a run of %d ticks: one per tick, half-open"
        % (len(series), clock + 1))
    assert all(isinstance(value, int) and not isinstance(value, bool)
               for value in series), (
        "a depth is an int count and nothing else: %r" % (series,))
    assert series == (1, 2, 3, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
                      5, 5, 5, 5, 5, 5, 5, 4, 4, 4, 4, 4, 4, 3, 3, 3,
                      3, 3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 0), (
        "the gauge of the world's own run is %r: the depth is the tasks the "
        "fleet has admitted and not yet finished or dropped, carried forward "
        "tick by tick" % (series,))
    assert min(series) >= 0, (
        "a series a fold returned has a negative depth in it: %r" % (series,))

    for tick, want in ((0, 1), (2, 3), (3, 4), (4, 4), (5, 5), (22, 5),
                       (23, 4), (42, 2), (47, 0)):
        got = s.depth_at(events, tick)
        assert got == want, (
            "depth_at(events, %d) is %r, not %r: a tick's own events are in the "
            "depth at that tick" % (tick, got, want))
    assert s.depth_at(events, clock) == series[-1] == 0, (
        "the gauge when the run is over is %r: a fleet that has finished has an "
        "empty queue, and its own record says every admitted task left"
        % (s.depth_at(events, clock),))
    assert s.depth_series(events, 4, 8) == (4, 5, 5, 5), (
        "a window's series is %r: the depth at its first tick carries the ticks "
        "before it" % (s.depth_series(events, 4, 8),))
    assert s.depth_series(events, 3, 4) == (4,), (
        "a one-tick window is %r, not refused: a point has no *fold*, but a gauge "
        "has a value at every point" % (s.depth_series(events, 3, 4),))
    no_starts = tuple(event for event in events if event["kind"] != "started")
    assert s.depth_series(no_starts, 0, clock + 1) == series, (
        "removing every `started` event changed the gauge: a task that is running "
        "has not left the queue, so a start is neither an arrival nor a departure")
    no_retries = tuple(event for event in events if event["kind"] != "retried")
    message = _refuses(s.GaugeError, "the same run with its retries dropped",
                       lambda: s.depth_series(no_retries, 0, clock + 1))
    assert "render" in message and "twice" in message, (
        "a run whose `retried` events were dropped does not refuse naming the task "
        "that finished twice: %r — the retry is the arrival that keeps a failed "
        "attempt's task in the queue" % (message,))

    # ---- the peak: the first tick, and the absolute tick -------------------

    peak = s.peak_depth(events, 0, clock + 1)
    assert list(peak) == ["tick", "depth"], (
        "the peak is %r: a mapping over exactly `tick` and `depth`, in that "
        "order" % (peak,))
    assert peak == {"tick": 5, "depth": 5}, (
        "the peak of the default run is %r, not {tick: 5, depth: 5}: the maximum "
        "is attained first at tick 5" % (peak,))
    assert s.peak_depth(events, 23, 30) == {"tick": 23, "depth": 4}, (
        "a clipped window's peak is %r, not {tick: 23, depth: 4}"
        % (s.peak_depth(events, 23, 30),))
    assert s.peak_depth(events, 42, 48) == {"tick": 42, "depth": 2}, (
        "the peak is %r: the tick is the absolute tick, not the window's offset "
        "— and the *first* tick that attains the maximum wins"
        % (s.peak_depth(events, 42, 48),))

    # ---- the mean: a pair, reduced, over ticks ----------------------------

    for start, end, want in ((0, 1, (1, 1)), (0, 3, (2, 1)), (0, 4, (5, 2)),
                             (0, 6, (19, 6)), (3, 5, (4, 1)), (48, 52, (0, 1)),
                             (0, 48, (7, 2))):
        got = s.average_depth(events, start, end)
        assert isinstance(got, tuple) and len(got) == 2, (
            "the mean over [%d, %d) is %r: an exact reduced pair, never a "
            "scalar and never a mapping" % (start, end, got))
        assert got == want, (
            "the mean over [%d, %d) is %r, not %r" % (start, end, got, want))
        total = sum(s.depth_series(events, start, end))
        ticks = end - start
        assert got[0] * ticks == total * got[1], (
            "the mean over [%d, %d) is %r, which is not the interval's sum over "
            "its ticks: %d over %d (%r)" % (start, end, got, total, ticks,
                                            s.average_depth(events, start, end)))
    assert s.average_depth(events, 0, 48)[0] * 48 == sum(series) * 2, (
        "the reduced pair of the whole run does not stand for its sum: a gauge "
        "may be averaged over an interval and never summed over one")
    assert s.average_depth(events, 3, 5) != (8, 2), (
        "the mean came back unreduced: (8, 2) is (4, 1)")

    # ---- a run with no retries, and the drop that never entered -----------

    plain = world.record(worker="reliable")
    assert plain["summary"]["retries"] == 0, "the fixture was meant to have no retry"
    assert plain["summary"]["dropped"] == 1, "the fixture was meant to drop one"
    refused = [event for event in plain["events"] if event["kind"] == "dropped"]
    admitted = {event["task"] for event in plain["events"]
                if event["kind"] == "admitted"}
    assert refused and refused[0]["task"] not in admitted, (
        "the fixture's drop was meant to be a task the queue refused, not one "
        "that had been admitted")
    plain_series = s.depth_series(plain["events"], 0, plain["clock"] + 1)
    assert plain_series == (1, 2, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3,
                            3, 3, 3, 3, 3, 2, 2, 2, 1, 1, 1, 1, 0), (
        "the series of a run with no retries is %r" % (plain_series,))
    without_drop = tuple(event for event in plain["events"]
                        if event["kind"] != "dropped")
    assert s.depth_series(without_drop, 0, plain["clock"] + 1) == plain_series, (
        "removing the drop of a task that was never admitted changed the gauge: a "
        "task the queue refused was never in the queue to leave")
    assert s.peak_depth(plain["events"], 0, plain["clock"] + 1) == {
        "tick": 4, "depth": 4}, (
        "the peak of the reliable run is %r, not {tick: 4, depth: 4}"
        % (s.peak_depth(plain["events"], 0, plain["clock"] + 1),))
    assert s.depth_at(plain["events"], plain["clock"]) == 0, (
        "a run with no retries does not end with an empty queue: %r"
        % (s.depth_at(plain["events"], plain["clock"]),))

    # ---- the four kinds, one fixture each ---------------------------------

    left = (world.event(tick=0, task="render", kind="admitted", attempt=1),
            world.event(tick=1, task="render", kind="dropped", attempt=1,
                        error="out_of_time"))
    assert s.depth_series(left, 0, 3) == (1, 0, 0), (
        "a task dropped after it was admitted leaves the gauge: %r"
        % (s.depth_series(left, 0, 3),))
    assert s.depth_at(left, 1) == 0, "a dropped task is not still in flight"

    retried = (world.event(tick=0, task="render", kind="admitted", attempt=1),
               world.event(tick=1, task="render", kind="started", attempt=1,
                           wait=1),
               world.event(tick=3, task="render", kind="finished", attempt=1,
                           outcome="failed", error="failed"),
               world.event(tick=3, task="render", kind="retried", attempt=1,
                           error="failed"),
               world.event(tick=5, task="render", kind="finished", attempt=2,
                           outcome="ok"))
    assert s.depth_series(retried, 0, 7) == (1, 1, 1, 1, 1, 0, 0), (
        "a task that failed and was retried is still in the queue: %r"
        % (s.depth_series(retried, 0, 7),))
    assert s.depth_at(retried, 1) == 1, (
        "a started event moved the gauge: a task that is running has not left "
        "the queue")
    assert s.depth_at(retried, 3) == 1, (
        "a finished attempt that is retried left the gauge: the departure and the "
        "retry are the same tick, and the retry puts the task back")

    finish_first = (world.event(tick=2, task="render", kind="finished",
                                attempt=1, outcome="ok"),
                    world.event(tick=2, task="render", kind="admitted",
                                attempt=1))
    admit_first = (world.event(tick=2, task="render", kind="admitted",
                               attempt=1),
                   world.event(tick=2, task="render", kind="finished",
                               attempt=1, outcome="ok"))
    for name, same in (("finished first", finish_first),
                       ("admitted first", admit_first)):
        assert s.depth_series(same, 0, 3) == (0, 0, 0), (
            "a task admitted and finished at one tick (%s) does not net out to "
            "zero: %r" % (name, s.depth_series(same, 0, 3)))
    assert s.peak_depth(admit_first, 0, 3) == {"tick": 0, "depth": 0}, (
        "a same-tick admit and finish is not a peak of one")

    # ---- the negative depth, both sides of the window ---------------------

    broken = (world.event(tick=0, task="render", kind="admitted", attempt=1),
              world.event(tick=3, task="render", kind="finished", attempt=1,
                          outcome="failed", error="failed"),
              world.event(tick=5, task="render", kind="finished", attempt=2,
                          outcome="ok"))
    assert s.depth_at(broken, 2) == 1, (
        "the gauge before the fixture broke is %r, not 1"
        % (s.depth_at(broken, 2),))
    assert s.depth_at(broken, 3) == 0, (
        "the first finish is the departure the retry never put back: %r"
        % (s.depth_at(broken, 3),))
    assert s.depth_series(broken, 0, 5) == (1, 1, 1, 0, 0), (
        "a series that stops before the second finish is %r: the half-open end "
        "keeps the event at tick 5 out of the window, and the depth is answered "
        "there all the same" % (s.depth_series(broken, 0, 5),))
    for what, call in (
            ("a series whose window holds the lost retry",
             lambda: s.depth_series(broken, 0, 6)),
            ("the gauge at the tick a task finished twice",
             lambda: s.depth_at(broken, 5)),
            ("a peak over a fixture that goes negative",
             lambda: s.peak_depth(broken, 0, 6)),
            ("a mean over a fixture that goes negative",
             lambda: s.average_depth(broken, 0, 6)),
            ("a series that starts after the fixture broke",
             lambda: s.depth_series(broken, 2, 6))):
        message = _refuses(s.GaugeError, what, call)
        assert "render" in message, (
            "%s refused without naming the task that left twice: %r"
            % (what, message))
    message = _refuses(s.GaugeError, "a task finished twice",
                       lambda: s.depth_series(broken, 0, 6))
    assert "twice" in message and "5" in message, (
        "the refusal does not say that the task finished twice, and where: %r"
        % (message,))

    # ---- the ticks themselves --------------------------------------------

    message = _refuses(s.GaugeError, "a tick that is not an int",
                       lambda: s.depth_at(events, "3"))
    assert "tick" in message and "'3'" in message, (
        "the refusal of a tick that is text does not name it: %r" % (message,))
    message = _refuses(s.GaugeError, "a negative tick",
                       lambda: s.depth_at(events, -1))
    assert "tick" in message and "-1" in message, (
        "the refusal of a negative tick does not name it: %r" % (message,))
    _refuses(s.GaugeError, "a boolean tick",
             lambda: s.depth_at(events, True))
    message = _refuses(s.GaugeError, "a series with no width",
                       lambda: s.depth_series(events, 4, 4))
    assert "4" in message and "width" in message, (
        "the refusal of a zero-width series does not name the interval and the "
        "reason: %r" % (message,))
    _refuses(s.GaugeError, "a series whose end is before its start",
             lambda: s.depth_series(events, 5, 4))
    message = _refuses(s.GaugeError, "a series whose end is not a tick",
                       lambda: s.depth_series(events, 0, "9"))
    assert "'9'" in message, (
        "the refusal of a series whose end is text does not name it: %r"
        % (message,))
    _refuses(s.GaugeError, "a peak over no ticks",
             lambda: s.peak_depth(events, 0, 0))
    _refuses(s.GaugeError, "a mean over no ticks",
             lambda: s.average_depth(events, 3, 3))

    # ---- the fold does not bend the events it was handed ------------------

    given = list(events[:8])
    before = list(given)
    s.depth_series(given, 0, 4)
    assert given == before, (
        "the gauge reordered the events it was given: a fold reads the caller's "
        "events and gives them back the way they came")
    assert list(s.peak_depth(events, 0, 4)) == ["tick", "depth"], (
        "the peak's keys are in the caller's order, not the format's")
    assert isinstance(s.peak_depth(events, 0, 4)["tick"], int), (
        "the tick a peak names is not an int")

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "agent-metrics-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J5_REPO=/path/to/learn-stuff-from-scratch")

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

    import stage_01
    import stage_04 as s

    # ---- the vocabulary every later stage speaks --------------------------

    assert s.SUMMARY_KEYS == ("count", "min", "max", "p50", "p95", "p99"), (
        "this stage's summary keys are %r, not the six a window reports — and "
        "the order is a claim: a summary is read as one line" % (s.SUMMARY_KEYS,))
    assert isinstance(s.SUMMARY_KEYS, tuple), (
        "the summary keys are %r: a frozen vocabulary is a tuple, not a list "
        "somebody may append to" % (type(s.SUMMARY_KEYS).__name__,))
    assert issubclass(s.QuantileError, stage_01.TelemetryError), (
        "%r is not a %s: every refusal in this course derives from the course's "
        "one family, or a `except TelemetryError` stops catching it"
        % (s.QuantileError, stage_01.TelemetryError.__name__))
    assert issubclass(s.QuantileError, ValueError), (
        "%r is not a ValueError: every refusal in this course is a verdict on a "
        "value" % (s.QuantileError,))

    # ---- the rank is an index, and it is exact ----------------------------

    one = (7,)
    assert s.quantile(one, 50, 100) == 7, (
        "a one-sample window has no rank to get wrong: its only sample is every "
        "quantile of it")
    assert s.quantile(one, 1, 100) == 7, (
        "the smallest rank of a one-sample window is not the sample: the index "
        "is not clamped to zero")
    assert s.quantile(one, 100, 100) == 7, "the largest rank of a one-sample "
    eight = (40, 10, 30, 20, 80, 50, 70, 60)
    assert s.quantile(eight, 1, 100) == 10, (
        "p1 of eight samples is %r, not the minimum: ceil(8 * 1/100) - 1 is 0"
        % (s.quantile(eight, 1, 100),))
    assert s.quantile(eight, 50, 100) == 40, (
        "the median of eight samples is %r: ceil(8 * 50/100) - 1 is index 3"
        % (s.quantile(eight, 50, 100),))
    assert s.quantile(eight, 95, 100) == 80, (
        "p95 of eight samples is %r, not the maximum: the rank is ceil(7.6) - 1 "
        "= 7, so p95 *is* the maximum — this is the fact an interpolation gets "
        "wrong and the whole reason the rank is an integer"
        % (s.quantile(eight, 95, 100),))
    assert s.quantile(eight, 95, 100) == max(eight), (
        "p95 of eight samples is not the maximum")
    assert s.quantile(eight, 99, 100) == 80, (
        "p99 of eight samples is %r, not the maximum: with a rank of ceil(7.92) "
        "- 1 = 7 the nearest-rank rule makes the top quantiles land on the last "
        "sample" % (s.quantile(eight, 99, 100),))
    assert s.quantile(eight, 100, 100) == 80, (
        "p100 of eight samples is not its maximum")
    hundred = tuple(range(100))
    assert s.quantile(hundred, 50, 100) == 49, (
        "the median of a hundred samples is %r: ceil(50) - 1 is index 49"
        % (s.quantile(hundred, 50, 100),))
    assert s.quantile(hundred, 95, 100) == 94, (
        "p95 of a hundred samples is %r, not 95: the index is "
        "ceil(95) - 1 = 94" % (s.quantile(hundred, 95, 100),))
    assert s.quantile(hundred, 99, 100) == 98, (
        "p99 of a hundred samples is %r: at this size p99 is *not* the maximum, "
        "and a rule that always answers the last sample is caught here"
        % (s.quantile(hundred, 99, 100),))
    assert s.quantile(hundred, 100, 100) == 99, (
        "p100 of a hundred samples is not its maximum")

    # the input is the caller's, and it stays the caller's
    caller = [3, 1, 2]
    assert s.quantile(caller, 50, 100) == 2, (
        "the median of an unsorted caller's list is not read off the sorted copy")
    assert caller == [3, 1, 2], (
        "quantile sorted the caller's list in place: the answer of whatever "
        "reads it next is now different, and the bug shows up stages away")

    # ---- the fraction: a refusal names the operand ------------------------

    message = _refuses(s.QuantileError, "a quantile with no denominator",
                       lambda: s.quantile(eight, 50, 0))
    assert "denominator" in message and "above zero" in message, (
        "a denominator of zero is refused without naming it and the bound it "
        "breaks: %r" % (message,))
    message = _refuses(s.QuantileError, "a quantile with no numerator",
                       lambda: s.quantile(eight, 0, 100))
    assert "numerator" in message and "above zero" in message, (
        "a numerator of zero is refused without naming it: %r" % (message,))
    message = _refuses(s.QuantileError, "a quantile above one",
                       lambda: s.quantile(eight, 150, 100))
    assert "150" in message and "100" in message, (
        "a numerator above the denominator is refused without naming both "
        "operands: %r" % (message,))
    message = _refuses(s.QuantileError, "a numerator that is a float",
                       lambda: s.quantile(eight, 50.0, 100))
    assert "numerator" in message and "int" in message, (
        "a numerator that is not an int is not refused by name: %r" % (message,))
    message = _refuses(s.QuantileError, "a denominator that is a bool",
                       lambda: s.quantile(eight, 50, True))
    assert "denominator" in message and "int" in message, (
        "a denominator that is not an int is not refused by name: %r"
        % (message,))

    # ---- the samples: ints, copied, sorted, non-empty ---------------------

    message = _refuses(s.QuantileError, "a float sample",
                       lambda: s.quantile((1, 2, 1.5), 50, 100))
    assert "float" in message and "int" in message, (
        "a float sample is not refused by name: %r" % (message,))
    message = _refuses(s.QuantileError, "a bool sample",
                       lambda: s.quantile((1, True, 3), 50, 100))
    assert "bool" in message and "int" in message, (
        "`True` is one sample: a bool in a measurement is a caller who reached "
        "for a flag, and it is refused by name: %r" % (message,))
    message = _refuses(s.QuantileError, "a sample set that is not a sequence",
                       lambda: s.quantile(5, 50, 100))
    assert "sequence" in message and "int" in message, (
        "a sample set that is not a sequence does not say what it takes and what "
        "it was given: %r" % (message,))
    message = _refuses(s.QuantileError, "a quantile of no samples",
                       lambda: s.quantile((), 50, 100))
    assert "empty" in message or "no answer" in message, (
        "an empty window is answered instead of refused: a quantile of no "
        "samples is a question with no answer, not zero: %r" % (message,))

    # ---- the summary: one line, six numbers -------------------------------

    samples = (40, 10, 30, 20, 80, 50, 70, 60, 20)
    got = s.summary(samples)
    assert isinstance(got, Mapping), (
        "a summary is %r, not a mapping of six numbers"
        % (type(got).__name__,))
    assert list(got) == list(s.SUMMARY_KEYS) == ["count", "min", "max", "p50",
                                                 "p95", "p99"], (
        "the summary's keys are %r, not the six of SUMMARY_KEYS in their order"
        % (list(got),))
    assert got == {"count": 9, "min": 10, "max": 80, "p50": 40, "p95": 80,
                   "p99": 80}, (
        "the summary of %r is %r, and it is not the six numbers of that window "
        "(count counts samples, min and max come from the sorted copy, and p95 "
        "of nine is the maximum)" % (samples, got))
    assert got["min"] == 10 and got["max"] == 80, (
        "min and max are not read off the sorted copy")
    big = s.summary(hundred)
    assert big["count"] == 100 and big["min"] == 0 and big["max"] == 99, (
        "a hundred samples are not summarised: %r" % (big,))
    assert big["p50"] == 49 and big["p95"] == 94 and big["p99"] == 98, (
        "a hundred-sample summary has the wrong quantiles: %r — p99 of a "
        "hundred is 98, not the maximum" % (big,))
    caller = [40, 10, 30, 20]
    s.summary(caller)
    assert caller == [40, 10, 30, 20], (
        "summary sorted the caller's list in place")
    message = _refuses(s.QuantileError, "a summary of no samples",
                       lambda: s.summary(()))
    assert "no samples" in message or "empty" in message, (
        "an empty window is summarised instead of refused: %r" % (message,))

    # ---- above: strictly above, and the rate is floored -------------------

    got = s.above((10, 20, 30, 40), 20)
    assert list(got) == ["count", "total", "bp"], (
        "above's keys are %r, not count, total and bp in that order"
        % (list(got),))
    assert got == {"count": 2, "total": 4, "bp": 5000}, (
        "two of four above 20 is %r" % (got,))
    assert s.above((5, 5, 5), 5) == {"count": 0, "total": 3, "bp": 0}, (
        "a sample equal to the threshold is *not* above it: %r"
        % (s.above((5, 5, 5), 5),))
    assert s.above((5, 5, 5), 4) == {"count": 3, "total": 3, "bp": 10000}, (
        "every sample above the threshold is not 100 percent: %r"
        % (s.above((5, 5, 5), 4),))
    got = s.above((1, 2, 3), 1)
    assert got == {"count": 2, "total": 3, "bp": 6666}, (
        "two of three is %r: the rate is floored to basis points, so it is 6666 "
        "and never 6667" % (got,))
    message = _refuses(s.QuantileError, "an above rate with no samples",
                       lambda: s.above((), 5))
    assert "samples" in message, (
        "an above rate with no denominator is not refused naming what it "
        "needed: %r" % (message,))
    message = _refuses(s.QuantileError, "a threshold that is a float",
                       lambda: s.above((1, 2, 3), 1.5))
    assert "int" in message and "float" in message, (
        "a float threshold is not refused by name: %r" % (message,))
    message = _refuses(s.QuantileError, "a threshold that is a bool",
                       lambda: s.above((1, 2, 3), True))
    assert "bool" in message and "int" in message, (
        "a bool threshold is not refused by name: %r" % (message,))

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "agent-metrics-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J5_REPO=/path/to/learn-stuff-from-scratch")

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

    import fleet
    import stage_01 as one
    import stage_05 as s
    import telemetry as world

    # ---- the refusal family ----------------------------------------------

    assert issubclass(s.LatencyError, one.TelemetryError), (
        "%r is not a %s: one `except TelemetryError` must still catch a latency "
        "this stage refuses" % (s.LatencyError, one.TelemetryError.__name__))
    assert issubclass(s.LatencyError, ValueError), (
        "%r is not a ValueError: every refusal in this course is a verdict on a "
        "value" % (s.LatencyError,))

    # ---- a hand-built run: two tasks, one of them with a real retry gap ----

    def ev(**fields):
        return world.event(**fields)

    def admit(tick, task):
        return ev(tick=tick, task=task, pool="small", tenant="batch",
                  kind="admitted", attempt=1)

    def start(tick, task, attempt, wait):
        return ev(tick=tick, task=task, pool="small", tenant="batch",
                  kind="started", attempt=attempt, wait=wait)

    def finish(tick, task, attempt, service, outcome, error=world.ABSENT):
        return ev(tick=tick, task=task, pool="small", tenant="batch",
                  kind="finished", attempt=attempt, outcome=outcome,
                  service=service, tokens_in=10, tokens_out=5, error=error)

    def retry(tick, task, attempt, error):
        return ev(tick=tick, task=task, pool="small", tenant="batch",
                  kind="retried", attempt=attempt, error=error)

    # `render` finishes once; `index` fails its first attempt, is re-queued two
    # ticks later (the gap), and finishes its second attempt — so its span has
    # time that neither attempt's wait nor service covers.
    gap = (admit(0, "render"),
           admit(0, "index"),
           start(0, "render", 1, 0),
           start(0, "index", 1, 0),
           finish(2, "render", 1, 2, "ok"),
           finish(3, "index", 1, 3, "failed", "failed"),
           retry(5, "index", 1, "failed"),
           start(8, "index", 2, 3),
           finish(12, "index", 2, 4, "ok"))
    frozen = tuple(dict(event) for event in gap)

    assert isinstance(s.waits(gap), tuple), (
        "waits answers %r: a fold of the starts is a sequence, not a list "
        "somebody may append to" % (type(s.waits(gap)).__name__,))
    assert s.waits(gap) == (0, 0, 3), (
        "the waits of the fixture are %r, not (0, 0, 3) — every start, in tick "
        "order, including the retry's" % (s.waits(gap),))
    assert isinstance(s.services(gap), tuple), (
        "services answers %r, not a tuple" % (type(s.services(gap)).__name__,))
    assert s.services(gap) == (2, 3, 4), (
        "the services of the fixture are %r, not (2, 3, 4) — every finish, in "
        "tick order" % (s.services(gap),))
    assert s.attempt_latency(gap) == (2, 3, 7), (
        "the attempt latencies are %r, not (2, 3, 7): each finish adds the wait "
        "of the start of the *same* attempt" % (s.attempt_latency(gap),))
    assert len(s.attempt_latency(gap)) == 3, (
        "there are three finished attempts in the fixture, and %d attempt "
        "latencies" % (len(s.attempt_latency(gap)),))
    assert s.task_latency(gap) == (("index", 12), ("render", 2)), (
        "the spans are %r, not ((\"index\", 12), (\"render\", 2)) — sorted by "
        "id, admitted tick to last finish" % (s.task_latency(gap),))
    assert isinstance(s.task_latency(gap), tuple), (
        "task_latency answers %r: a sequence of pairs, not a list"
        % (type(s.task_latency(gap)).__name__,))

    pieces = s.split(gap)
    assert isinstance(pieces, dict), (
        "split answers %r: a mapping of four sums" % (type(pieces).__name__,))
    assert list(pieces) == ["wait", "service", "gap", "total"], (
        "split's keys are %r, not wait, service, gap, total in that order"
        % (list(pieces),))
    assert pieces == {"wait": 3, "service": 9, "gap": 2, "total": 14}, (
        "split is %r, not {'wait': 3, 'service': 9, 'gap': 2, 'total': 14}"
        % (pieces,))
    assert pieces["wait"] + pieces["service"] + pieces["gap"] == pieces["total"], (
        "wait + service + gap does not equal total: %r" % (pieces,))
    assert pieces["gap"] == 2, (
        "the fixture's retry gap is two ticks, and split reports %r"
        % (pieces["gap"],))
    assert sum(s.attempt_latency(gap)) < sum(t for _, t in s.task_latency(gap)), (
        "with a real retry gap the sum of the attempts is strictly less than the "
        "sum of the spans: %d is not < %d"
        % (sum(s.attempt_latency(gap)), sum(t for _, t in s.task_latency(gap))))
    assert tuple(dict(event) for event in gap) == frozen, (
        "the fold mutated the events it was handed: a fold reads, it never writes")

    # ---- a fixture that never retried: the two sums are equal -------------

    flat = (admit(0, "render"),
            start(0, "render", 1, 0),
            finish(2, "render", 1, 2, "ok"))
    assert s.waits(flat) == (0,), "the one start waits 0"
    assert s.services(flat) == (2,), "the one finish served 2"
    assert s.attempt_latency(flat) == (2,), "the one attempt costs 0 + 2"
    assert s.task_latency(flat) == (("render", 2),), "the one span is 2"
    assert s.split(flat) == {"wait": 0, "service": 2, "gap": 0, "total": 2}, (
        "a fixture with no retry has no gap: %r" % (s.split(flat),))
    assert sum(s.attempt_latency(flat)) == sum(
        t for _, t in s.task_latency(flat)), (
        "with nothing retried the sum of the attempts equals the sum of the spans")

    # ---- the empty run ----------------------------------------------------

    assert s.waits(()) == () and s.services(()) == (), (
        "an empty run has no waits and no services")
    assert s.attempt_latency(()) == () and s.task_latency(()) == (), (
        "an empty run has no attempts and no spans")
    assert s.split(()) == {"wait": 0, "service": 0, "gap": 0, "total": 0}, (
        "an empty run's identity is 0 == 0: %r" % (s.split(()),))

    # ---- a finish with no start refuses, naming both ----------------------

    orphan = (admit(0, "index"),
              start(0, "index", 1, 0),
              finish(3, "index", 1, 3, "failed", "failed"),
              retry(5, "index", 1, "failed"),
              finish(12, "index", 2, 4, "ok"))
    message = _refuses(s.LatencyError, "a finished attempt whose start is missing",
                       lambda: s.attempt_latency(orphan))
    assert "attempt 2" in message and "index" in message and "started" in message, (
        "the refusal of an unmatched attempt does not name the attempt, the task "
        "and what is missing: %r" % (message,))
    _refuses(s.LatencyError, "split over an unmatched attempt",
             lambda: s.split(orphan))

    # ---- a task that never finished refuses, naming it --------------------

    unfinished = (admit(0, "render"),
                  start(0, "render", 1, 0),
                  finish(2, "render", 1, 2, "ok"),
                  admit(4, "purge"),
                  start(4, "purge", 1, 0))
    message = _refuses(s.LatencyError, "a task that never finished",
                       lambda: s.task_latency(unfinished))
    assert "purge" in message and "never finished" in message, (
        "the refusal of an unfinished task does not name it as unfinished: %r"
        % (message,))
    _refuses(s.LatencyError, "split over a task that never finished",
             lambda: s.split(unfinished))
    assert "render" not in message, (
        "the refusal names the task that did finish instead of the one that did "
        "not: %r" % (message,))

    # ---- the world's own runs ---------------------------------------------

    for pool in ("small", "narrow"):
        for worker in ("reliable", "flaky", "mixed"):
            run = world.record(pool=pool, worker=worker)
            events = run["events"]
            starts = {}
            for event in events:
                if event["kind"] == "started":
                    starts[(event["task"], event["attempt"])] = event["wait"]
            want_waits = tuple(event["wait"] for event in events
                               if event["kind"] == "started")
            want_services = tuple(event["service"] for event in events
                                  if event["kind"] == "finished")
            want_attempts = tuple(
                starts[(event["task"], event["attempt"])] + event["service"]
                for event in events if event["kind"] == "finished")
            admitted = {}
            last = {}
            for event in events:
                if event["kind"] == "admitted" and event["task"] not in admitted:
                    admitted[event["task"]] = event["tick"]
                elif event["kind"] == "finished":
                    last[event["task"]] = event["tick"]
            want_spans = tuple((task, last[task] - admitted[task])
                               for task in sorted(admitted))
            attempts_sum = sum(t for _, t in want_spans)
            assert s.waits(events) == want_waits, (
                "the %s/%s run's waits are not the starts' waits" % (pool, worker))
            assert s.services(events) == want_services, (
                "the %s/%s run's services are not the finishes' services"
                % (pool, worker))
            assert s.attempt_latency(events) == want_attempts, (
                "the %s/%s run's attempt latencies do not match (task, attempt)"
                % (pool, worker))
            assert s.task_latency(events) == want_spans, (
                "the %s/%s run's spans are not admitted-to-last-finish, sorted"
                % (pool, worker))
            assert sum(s.attempt_latency(events)) <= attempts_sum, (
                "the sum of the attempts exceeds the sum of the spans")
            got = s.split(events)
            assert got == {"wait": sum(want_waits), "service": sum(want_services),
                           "gap": attempts_sum - sum(want_attempts),
                           "total": attempts_sum}, (
                "the %s/%s run's split does not agree with its own folds: %r"
                % (pool, worker, got))
            assert got["wait"] + got["service"] + got["gap"] == got["total"], (
                "the identity fails on the %s/%s run: %r" % (pool, worker, got))
            if run["summary"]["retries"] == 0:
                assert sum(s.attempt_latency(events)) == attempts_sum, (
                    "a run with no retries and a gap between its spans and its "
                    "attempts is a run that lost an event")

    # ---- the world's own writer, read back --------------------------------

    run = world.record()
    lines = run["text"]
    parsed = one.read_events(lines)
    assert s.waits(parsed) == s.waits(run["events"]), (
        "the stage reads the world's lines and its records differently")
    assert s.split(parsed) == s.split(run["events"]), (
        "the identity of a run depends on which door its events came through")
    assert isinstance(fleet.QueueError, type) and issubclass(
        fleet.QueueError, ValueError), (
        "the fleet's refusals are ValueErrors too — one course, one family")

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "agent-metrics-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J5_REPO=/path/to/learn-stuff-from-scratch")

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

    import fleet
    import stage_01 as one
    import stage_06 as s
    import telemetry as world

    # ---- the vocabulary and the refusal family ---------------------------

    assert s.TOKEN_KEYS == ("in", "out"), (
        "the two halves of a token count are %r, not the pair `in` then `out`"
        % (s.TOKEN_KEYS,))
    assert s.COST_KEYS == ("micros", "tasks", "numerator", "denominator", "bp"), (
        "a cost per task reports %r, not the five keys in their order"
        % (s.COST_KEYS,))
    assert issubclass(s.CostError, one.TelemetryError), (
        "CostError is not the course's own refusal family")
    assert issubclass(s.CostError, ValueError), (
        "a bad pool is a caller's mistake: CostError must be a ValueError")

    # ---- the fixtures ----------------------------------------------------
    # A price is the pool's, so the same tokens in two pools cost two numbers,
    # and a pool that only ever admitted is a zero that still has an answer.

    def finished(tick, task, pool, tokens_in, tokens_out, outcome="ok"):
        return world.event(tick=tick, task=task, pool=pool, tenant="acme",
                           kind="finished", attempt=1, outcome=outcome,
                           service=1, tokens_in=tokens_in,
                           tokens_out=tokens_out, error=world.ABSENT)

    def admitted(tick, task, pool):
        return world.event(tick=tick, task=task, pool=pool, tenant="acme",
                           kind="admitted", attempt=1)

    def retried(tick, task, pool):
        return world.event(tick=tick, task=task, pool=pool, tenant="acme",
                           kind="retried", attempt=1, error="failed")

    # A: two priced pools, and a third that never finished anything.
    #    small: 100*2 + 50*12 = 800; wide: 10*10 + 0*60 = 100; narrow: nothing.
    a = (finished(0, "render", "small", 100, 50),
         finished(1, "index", "wide", 10, 0),
         admitted(0, "notify", "narrow"))
    frozen = [dict(event) for event in a]

    # ---- tokens: the whole run's token count -----------------------------

    got = s.tokens(a)
    assert list(got) == ["in", "out"], (
        "tokens reports %r, not `in` then `out`" % (list(got),))
    assert got == {"in": 110, "out": 50}, (
        "tokens of a run that spent 110 in and 50 out answered %r" % (got,))
    assert s.tokens(()) == {"in": 0, "out": 0}, (
        "a run with no events spent no tokens, not %r" % (s.tokens(()),))

    bent = s.tokens(a)
    bent["in"] = 999
    assert s.tokens(a) == {"in": 110, "out": 50}, (
        "tokens handed back a mapping it kept, so bending it bent the run")

    # A failed attempt spent its tokens too: the fold counts finishes, not
    # successes, or the fleet's own count disagrees with it.
    flaky = (finished(0, "render", "small", 100, 50, outcome="failed"),
             finished(1, "render", "small", 100, 50))
    assert s.tokens(flaky) == {"in": 200, "out": 100}, (
        "tokens dropped the tokens of an attempt that failed, which were spent")

    # ---- by_pool: a price is a property of the pool ----------------------

    got = s.by_pool(a)
    assert list(got) == ["narrow", "small", "wide"], (
        "by_pool reports its pools as %r, not in sorted order" % (list(got),))
    assert got == {"narrow": 0, "small": 800, "wide": 100}, (
        "by_pool answered %r, not what each pool spent in its own price" % (got,))
    assert s.by_pool(()) == {}, (
        "by_pool of a run with no events answered %r" % (s.by_pool(()),))

    bent = s.by_pool(a)
    bent["small"] = 0
    assert s.by_pool(a) == {"narrow": 0, "small": 800, "wide": 100}, (
        "by_pool handed back a mapping it kept, so bending it bent the run")

    # A pool that never finished is a zero, not absent: the run named it.
    assert s.by_pool((admitted(0, "notify", "narrow"),)) == {"narrow": 0}, (
        "a pool with nothing finished is a zero, not missing from the answer")

    assert s.micros(a) == 900, (
        "the run cost 900 micros, not %r" % (s.micros(a),))
    assert s.micros(()) == 0, "an empty run cost nothing, not %r" % (s.micros(()),)

    # ---- cost_per_task: one sum over one count ---------------------------

    got = s.cost_per_task(a)
    assert list(got) == ["micros", "tasks", "numerator", "denominator", "bp"], (
        "cost_per_task reports %r, not the five keys in their order" % (list(got),))
    assert got == {"micros": 900, "tasks": 2, "numerator": 450,
                   "denominator": 1, "bp": 4500000}, (
        "900 micros over 2 finished tasks is 450/1 and 4500000 bp, not %r" % (got,))

    # B: a sum that does not divide evenly, and a floor that rounds down.
    #    800 + 800 + 400 = 2000 over 3 finishes is 6666666 bp, not 6666667.
    #    The admitted and retried events cost nothing and finish nothing.
    b = (finished(0, "render", "small", 100, 50),
         finished(1, "render", "small", 100, 50),
         finished(2, "audit", "small", 200, 0),
         admitted(0, "purge", "small"),
         retried(1, "digest", "small"))
    assert s.tokens(b) == {"in": 400, "out": 100}, (
        "a fold that counted the admitted or retried events' tokens answered %r"
        % (s.tokens(b),))
    assert s.micros(b) == 2000, (
        "the run cost 2000 micros, not %r — an event with no tokens costs none"
        % (s.micros(b),))
    got = s.cost_per_task(b)
    assert got == {"micros": 2000, "tasks": 3, "numerator": 2000,
                   "denominator": 3, "bp": 6666666}, (
        "2000 micros over 3 finishes is 2000/3 and 6666666 bp, not %r" % (got,))

    # A finish whose in tokens were zero finished all the same: the denominator
    # counts the events that finished, not the ones with a non-zero field.
    z = (finished(0, "notify", "small", 0, 7),
         finished(1, "purge", "small", 10, 0))
    assert s.micros(z) == 104, (
        "7 out tokens at 12 and 10 in tokens at 2 is 104 micros, not %r"
        % (s.micros(z),))
    got = s.cost_per_task(z)
    assert got["tasks"] == 2, (
        "a finish with no in tokens still finished, so it is still a task")
    assert got == {"micros": 104, "tasks": 2, "numerator": 52,
                   "denominator": 1, "bp": 520000}, (
        "104 micros over 2 finishes is 52/1 and 520000 bp, not %r" % (got,))

    # ---- a zero denominator is a question, and the answer is a refusal ---

    dead = (admitted(0, "purge", "small"), retried(1, "digest", "small"))
    assert s.micros(dead) == 0, "nothing finished, so nothing was spent"
    assert s.tokens(dead) == {"in": 0, "out": 0}, (
        "no event carried a token, so the fold answers zero, not a refusal")
    message = _refuses(s.CostError, "a cost per task with no finish",
                       lambda: s.cost_per_task(dead))
    assert "a cost per task needs tasks" in message, (
        "a zero denominator must be refused by naming it, got %r" % (message,))

    # ---- the pool is the price, and an unknown one is refused by name ----

    for what, call in (("by_pool", lambda: s.by_pool((finished(0, "render", "gpu-1", 1, 1),))),
                       ("micros", lambda: s.micros((finished(0, "render", "gpu-1", 1, 1),))),
                       ("cost_per_task",
                        lambda: s.cost_per_task((finished(0, "render", "gpu-1", 1, 1),)))):
        message = _refuses(s.CostError, "an unknown pool in %s" % (what,), call)
        assert "no price for pool 'gpu-1'" in message, (
            "%s must refuse a pool with no price by naming it, got %r"
            % (what, message))

    # tokens needs no price: a token is a property of the task.
    assert s.tokens((finished(0, "render", "gpu-1", 3, 4),)) == {"in": 3, "out": 4}, (
        "tokens needs no pool, so an unpriced pool is not its business")

    # A near miss earns the pool it probably meant; a far one earns nothing.
    message = _refuses(s.CostError, "a misspelled pool",
                       lambda: s.micros((finished(0, "render", "smal", 1, 1),)))
    assert "smal" in message and "small" in message, (
        "a pool within two edits of one we have must name it, got %r" % (message,))
    message = _refuses(s.CostError, "a pool three edits away",
                       lambda: s.micros((finished(0, "render", "gpu-1", 1, 1),)))
    assert "small" not in message, (
        "a pool too far from any we have earns no suggestion, got %r" % (message,))

    # ---- a fold never bends the events it was handed ---------------------

    assert [dict(event) for event in a] == frozen, (
        "folding the events bent them: a metric is a function of what it was given")

    # ---- the fleet's own count is the tie-breaker ------------------------

    run = world.record()
    events = run["events"]
    summary = run["summary"]
    assert events, "the default run must have events in it to fold"

    got = s.tokens(events)
    assert got == {"in": summary["tokens_in"], "out": summary["tokens_out"]}, (
        "this stage's tokens %r disagree with the fleet's own %r"
        % (got, {"in": summary["tokens_in"], "out": summary["tokens_out"]}))
    assert s.micros(events) == summary["micros"], (
        "this stage's micros %r disagree with the fleet's own %r"
        % (s.micros(events), summary["micros"]))
    assert s.by_pool(events) == {"small": summary["micros"]}, (
        "the default run is one pool, so by_pool is that pool's own total")
    got = s.cost_per_task(events)
    assert got["micros"] == summary["micros"], (
        "the numerator is the fleet's whole spend, %r" % (got["micros"],))
    assert got["tasks"] == summary["attempts"], (
        "the denominator is how many events finished (%r), not %r"
        % (summary["attempts"], got["tasks"]))

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "agent-metrics-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J5_REPO=/path/to/learn-stuff-from-scratch")

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

    def _fixture(world):
        """A run whose attempts and whose tasks disagree on purpose.

        `render` fails its first two attempts and succeeds on the third; `index`
        fails all three and is never retried again (the last attempt's outcome
        stands); `purge` and `audit` are dropped without ever running; `digest` is
        still in flight. So there are six finished attempts and five failures over
        two tasks that ever failed, five admissions, four retries, and two events
        that are neither an attempt nor a failure.
        """
        made = []

        def add(**fields):
            made.append(world.event(**fields))

        def attempt(task, number, *, outcome="ok", tick=0):
            add(tick=tick, task=task, pool="small", tenant="batch", kind="started",
                attempt=number, wait=0)
            add(tick=tick + 1, task=task, pool="small", tenant="batch",
                kind="finished", attempt=number, outcome=outcome, service=1,
                tokens_in=10, tokens_out=4,
                error=world.ABSENT if outcome == "ok" else outcome)
            if outcome != "ok" and number < 3:
                add(tick=tick + 1, task=task, pool="small", tenant="batch",
                    kind="retried", attempt=number, error=outcome)

        add(tick=0, task="render", pool="small", tenant="batch", kind="admitted",
            attempt=1)
        attempt("render", 1, outcome="failed", tick=0)
        attempt("render", 2, outcome="failed", tick=1)
        attempt("render", 3, outcome="ok", tick=2)
        add(tick=0, task="index", pool="small", tenant="batch", kind="admitted",
            attempt=1)
        attempt("index", 1, outcome="failed", tick=0)
        attempt("index", 2, outcome="failed", tick=1)
        attempt("index", 3, outcome="failed", tick=2)
        for task in ("purge", "audit"):
            add(tick=0, task=task, pool="small", tenant="batch", kind="admitted",
                attempt=1)
            add(tick=1, task=task, pool="small", tenant="batch", kind="dropped",
                attempt=1, error="queue_full")
        add(tick=0, task="digest", pool="small", tenant="batch", kind="admitted",
            attempt=1)
        add(tick=0, task="digest", pool="small", tenant="batch", kind="started",
            attempt=1, wait=0)
        return tuple(made)

    import stage_01
    import stage_07 as s
    import telemetry as world

    # ---- the family -------------------------------------------------------

    assert issubclass(s.RateError, stage_01.TelemetryError), (
        "%r is not a %s: one `except TelemetryError` must still catch a broken "
        "rate" % (s.RateError, stage_01.TelemetryError.__name__))
    assert issubclass(s.RateError, ValueError), (
        "%r is not a ValueError: a refusal is a verdict on a value, as "
        "everywhere in this course" % (s.RateError,))

    # ---- rate: the one place a ratio is built -----------------------------

    answer = s.rate(1, 3, what="a widget rate needs widgets")
    assert isinstance(answer, dict), (
        "rate answers %r: a ratio is a small mapping of its four parts"
        % (type(answer).__name__,))
    assert list(answer) == ["num", "den", "reduced", "bp"], (
        "rate answers %r: the keys are `num`, `den`, `reduced`, `bp`, in that "
        "order" % (list(answer),))
    assert answer["num"] == 1 and answer["den"] == 3, (
        "rate keeps the caller's counts: %r" % (answer,))
    assert isinstance(answer["reduced"], tuple) and answer["reduced"] == (1, 3), (
        "the reduced pair of 1/3 is the tuple (1, 3), not %r"
        % (answer["reduced"],))
    assert answer["bp"] == 3333, (
        "1 in 3 is 3333 basis points floored, not %r" % (answer["bp"],))

    assert s.rate(2, 4, what="x") == {"num": 2, "den": 4, "reduced": (1, 2),
                                      "bp": 5000}, (
        "2/4 is not reduced to 1/2 and scaled to 5000 bp: %r"
        % (s.rate(2, 4, what="x"),))
    whole = s.rate(5, 5, what="x")
    assert whole["reduced"] == (1, 1) and whole["bp"] == 10000, (
        "5/5 is the whole of it: %r" % (whole,))
    nothing = s.rate(0, 7, what="x")
    assert nothing["reduced"] == (0, 1) and nothing["bp"] == 0, (
        "a numerator of zero over a denominator is 0/1 and 0 bp, not %r"
        % (nothing,))
    assert s.rate(7, 3, what="x")["bp"] == 23333, (
        "7/3 floored is 23333 bp, not %r" % (s.rate(7, 3, what="x")["bp"],))
    assert s.rate(1, 1, what="x")["bp"] == 10000, (
        "a denominator of one is not refused and is the sample scaled by 10000")
    assert s.rate(1, 10000, what="x")["bp"] == 1, (
        "1/10000 is a single basis point, not %r"
        % (s.rate(1, 10000, what="x")["bp"],))
    assert s.rate(2, 3, what="x")["bp"] == 6666, (
        "2/3 is floored to 6666, not rounded up to 6667: %r"
        % (s.rate(2, 3, what="x")["bp"],))
    assert s.rate(9999, 10000, what="x")["bp"] == 9999, (
        "a hair under the whole is still under it: %r"
        % (s.rate(9999, 10000, what="x")["bp"],))
    assert s.rate(10001, 10000, what="x")["bp"] == 10001, (
        "more than the whole is more than 10000 bp, not clamped: %r"
        % (s.rate(10001, 10000, what="x")["bp"],))

    # ---- rate: a zero denominator, in the caller's own words --------------

    message = _refuses(s.RateError, "a ratio of nothing",
                       lambda: s.rate(1, 0, what="a widget rate needs widgets"))
    assert message == "a widget rate needs widgets", (
        "the refusal of a zero denominator does not quote the caller's `what`: "
        "%r" % (message,))
    message = _refuses(s.RateError, "a ratio of nothing at all",
                       lambda: s.rate(0, 0, what="other words entirely"))
    assert message == "other words entirely", (
        "the refusal is a fixed sentence instead of the `what` it was handed: "
        "%r" % (message,))
    message = _refuses(s.RateError, "a failure rate over no attempt",
                       lambda: s.failure_rate(()))
    assert "attempts" in message and "failure rate" in message, (
        "a failure rate with no attempts is refused without naming the attempts "
        "it needs: %r" % (message,))
    message = _refuses(s.RateError, "a retry rate over no admission",
                       lambda: s.retry_rate(()))
    assert "admissions" in message and "retry rate" in message, (
        "a retry rate with nothing admitted is refused without naming the "
        "admissions it needs: %r" % (message,))

    # ---- the counters, on the fixture that makes attempts differ ----------

    events = _fixture(world)
    before = tuple(dict(event) for event in events)
    assert s.attempts(events) == 6, (
        "the fixture has six finished attempts, and attempts answers %r"
        % (s.attempts(events),))
    assert s.failures(events) == 5, (
        "the fixture failed five attempts (render twice, index three times), "
        "and failures answers %r" % (s.failures(events),))
    assert s.retries(events) == 4, (
        "the fixture retried four times, and retries answers %r"
        % (s.retries(events),))
    assert s.admissions(events) == 5, (
        "the fixture admitted five tasks, and admissions answers %r"
        % (s.admissions(events),))
    failed_tasks = {event["task"] for event in events
                    if event["kind"] == "finished" and event["outcome"] != "ok"}
    assert failed_tasks == {"render", "index"}, (
        "the fixture built its failed attempts out of two tasks: %r"
        % (sorted(failed_tasks),))
    assert s.failures(events) != len(failed_tasks), (
        "two tasks ever failed and five attempts did: a failure counted per task "
        "(%r) is the count that hides the flaky one, per attempt it is %r"
        % (len(failed_tasks), s.failures(events)))
    finished_tasks = {event["task"] for event in events
                      if event["kind"] == "finished"}
    assert s.attempts(events) != len(finished_tasks), (
        "two tasks finished and six attempts did: an attempt is a `finished` "
        "event, not a task — attempts answers %r" % (s.attempts(events),))
    started = sum(1 for event in events if event["kind"] == "started")
    assert s.attempts(events) != started, (
        "a `started` event is an attempt still in flight: there are %d of them "
        "and attempts answers %r" % (started, s.attempts(events)))
    dropped = [event for event in events if event["kind"] == "dropped"]
    assert len(dropped) == 2 and all(event["outcome"] == world.ABSENT
                                     for event in dropped), (
        "the fixture dropped two tasks that never ran")
    without = tuple(event for event in events if event["kind"] != "dropped")
    assert s.failures(events) == s.failures(without), (
        "a dropped event is counted as a failure: dropping two tasks moved the "
        "count from %r to %r"
        % (s.failures(without), s.failures(events)))
    assert s.attempts(events) == s.attempts(without), (
        "a dropped event is counted as an attempt: dropping two tasks moved the "
        "count from %r to %r" % (s.attempts(without), s.attempts(events)))

    failure = s.failure_rate(events)
    assert list(failure) == ["num", "den", "reduced", "bp"], (
        "failure_rate answers %r: the same four keys as rate" % (list(failure),))
    assert failure == {"num": 5, "den": 6, "reduced": (5, 6), "bp": 8333}, (
        "five failures over six attempts is 5/6 and 8333 bp, not %r"
        % (failure,))
    retry = s.retry_rate(events)
    assert list(retry) == ["num", "den", "reduced", "bp"], (
        "retry_rate answers %r: the same four keys as rate" % (list(retry),))
    assert retry == {"num": 4, "den": 5, "reduced": (4, 5), "bp": 8000}, (
        "four retries over five admissions is 4/5 and 8000 bp, not %r"
        % (retry,))
    assert hasattr(s, "rate") and callable(s.rate), "rate is the one ratio door"
    assert tuple(dict(event) for event in events) == before, (
        "a fold bent the events it was given: a counter and a rate are pure "
        "functions of the events, not editors of them")

    # ---- the fleet's own count is the tie-breaker -------------------------

    for plan in ("mixed", "sickly", "flaky", "crasher", "reliable"):
        run = world.record(worker=plan)
        folded, tally = run["events"], run["summary"]
        assert s.attempts(folded) == tally["attempts"], (
            "the %s run: the fleet counted %d attempts, the stage says %d"
            % (plan, tally["attempts"], s.attempts(folded)))
        assert s.failures(folded) == tally["failures"], (
            "the %s run: the fleet counted %d failures, the stage says %d"
            % (plan, tally["failures"], s.failures(folded)))
        assert s.retries(folded) == tally["retries"], (
            "the %s run: the fleet counted %d retries, the stage says %d"
            % (plan, tally["retries"], s.retries(folded)))
        assert s.admissions(folded) == tally["admissions"], (
            "the %s run: the fleet admitted %d tasks, the stage says %d"
            % (plan, tally["admissions"], s.admissions(folded)))

    mixed = world.record(worker="mixed")
    assert s.failure_rate(mixed["events"]) == {"num": 5, "den": 10,
                                               "reduced": (1, 2), "bp": 5000}, (
        "the mixed run fails one attempt in two: %r"
        % (s.failure_rate(mixed["events"]),))
    assert s.retry_rate(mixed["events"])["reduced"] == (1, 1), (
        "the mixed run retries every task it admitted exactly once: %r"
        % (s.retry_rate(mixed["events"]),))
    clean = world.record(worker="reliable")
    assert s.failures(clean["events"]) == 0, (
        "a reliable fleet has no failures: %r" % (s.failures(clean["events"]),))
    assert s.failure_rate(clean["events"])["bp"] == 0, (
        "a failure rate of none over all of them is 0 bp, not a refusal: %r"
        % (s.failure_rate(clean["events"]),))

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "agent-metrics-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J5_REPO=/path/to/learn-stuff-from-scratch")

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

    def _flight(events, tick):
        """How many tasks are in flight at `tick`: the check's own count of them.

        A task is in flight from the tick it is admitted to the tick it leaves for
        good — a finish no retry follows, or a drop of a task that was in the queue
        to be dropped. Written the slow, obvious way on purpose: two readers of the
        same rule is the only way to check one of them.
        """
        again = {(event["task"], event["attempt"]) for event in events
                 if event["kind"] == "retried"}
        admitted = {event["task"] for event in events
                    if event["kind"] == "admitted"}
        live = set()
        for event in events:
            if event["tick"] > tick:
                continue
            if event["kind"] == "admitted":
                live.add(event["task"])
            elif event["kind"] == "finished" \
                    and (event["task"], event["attempt"]) not in again:
                live.discard(event["task"])
            elif event["kind"] == "dropped" and event["task"] in admitted:
                live.discard(event["task"])
        return len(live)

    from collections import Counter

    import stage_01
    import stage_08 as s

    import fleet
    import telemetry as world

    # ---- the shape this stage freezes -------------------------------------

    assert s.FOLD_KEYS == ("start", "end", "events", "count", "total",
                           "peak_depth"), (
        "FOLD_KEYS is %r: a fold is the window it folded, the events it found, "
        "how many of them there are, what they spent and how deep the queue got "
        "inside the window" % (s.FOLD_KEYS,))
    assert issubclass(s.PartitionError, stage_01.TelemetryError), (
        "%r is not a %s: one `except TelemetryError` must still catch a broken "
        "window set" % (s.PartitionError, stage_01.TelemetryError.__name__))
    assert issubclass(s.PartitionError, ValueError), (
        "%r is not a ValueError: every refusal in this course is a verdict on a "
        "value" % (s.PartitionError,))

    # ---- windows: the two sets a fixture can mean -------------------------

    minute = s.windows(0, 120, 20)
    assert isinstance(minute, tuple), (
        "windows answers %r: a window set is a sequence of specs, not a list "
        "somebody may append to" % (type(minute).__name__,))
    assert minute == s.windows(0, 120, 20, step=20), (
        "step=None is not the tumbling set: %r" % (minute,))
    assert minute == s.windows(**world.window("minute")), (
        "the minute fixture builds %r, not %r"
        % (s.windows(**world.window("minute")), minute))
    assert tuple(spec["start"] for spec in minute) == (0, 20, 40, 60, 80, 100), (
        "the tumbling windows start at %r: window i starts at start + i*step"
        % (tuple(spec["start"] for spec in minute),))
    assert tuple(spec["end"] for spec in minute) == (20, 40, 60, 80, 100, 120), (
        "the tumbling windows end at %r"
        % (tuple(spec["end"] for spec in minute),))
    for spec in minute:
        assert tuple(spec) == ("start", "end", "width", "step"), (
            "a spec is %r: the interval the window names and the two numbers the "
            "set was built with, in that order" % (list(spec),))
        assert (spec["width"], spec["step"]) == (20, 20), (
            "a minute window remembers %r: the width and the step it was built "
            "with" % ((spec["width"], spec["step"]),))

    rolling = s.windows(**world.window("rolling"))
    assert rolling == s.windows(0, 120, 40, step=20), (
        "the rolling fixture's step is not the caller's: %r" % (rolling,))
    assert tuple((spec["start"], spec["end"]) for spec in rolling) == (
        (0, 40), (20, 60), (40, 80), (60, 100), (80, 120), (100, 120)), (
        "the sliding set is %r: window i is [start + i*step, start + i*step + "
        "width), and the last one is cut at end"
        % (tuple((spec["start"], spec["end"]) for spec in rolling),))
    assert all(spec["width"] == 40 and spec["step"] == 20 for spec in rolling), (
        "a rolling window remembers %r, not the width and the step it was built "
        "with" % ([(spec["width"], spec["step"]) for spec in rolling],))

    assert s.windows(0, 50, 20) == (
        {"start": 0, "end": 20, "width": 20, "step": 20},
        {"start": 20, "end": 40, "width": 20, "step": 20},
        {"start": 40, "end": 50, "width": 20, "step": 20}), (
        "an interval that is not a whole number of widths gives %r: the last "
        "window is truncated at end, not dropped and not run past it"
        % (s.windows(0, 50, 20),))
    assert s.windows(5, 25, 20) == (
        {"start": 5, "end": 25, "width": 20, "step": 20},), (
        "a window set that starts at 5 gives %r: the first window begins at "
        "start, not at zero" % (s.windows(5, 25, 20),))
    assert s.windows(3, 100, 30, step=30) == (
        {"start": 3, "end": 33, "width": 30, "step": 30},
        {"start": 33, "end": 63, "width": 30, "step": 30},
        {"start": 63, "end": 93, "width": 30, "step": 30},
        {"start": 93, "end": 100, "width": 30, "step": 30}), (
        "a tumbling set aligned to 3 gives %r" % (s.windows(3, 100, 30, step=30),))
    assert s.windows(0, 10, 20) == (
        {"start": 0, "end": 10, "width": 20, "step": 20},), (
        "a width wider than the interval gives %r: one window, truncated at end "
        "— a width is not a promise the interval is that wide"
        % (s.windows(0, 10, 20),))

    message = _refuses(s.PartitionError, "a window set with no width",
                       lambda: s.windows(0, 0, 10))
    assert "point" in message and "0" in message, (
        "an interval with no width is not refused as a point: %r" % (message,))
    message = _refuses(s.PartitionError, "a reversed interval",
                       lambda: s.windows(10, 0, 5))
    assert "point" in message, (
        "a reversed interval is not refused as a point: %r" % (message,))
    message = _refuses(s.PartitionError, "a width of zero",
                       lambda: s.windows(0, 10, 0))
    assert "width" in message and "0" in message, (
        "a width of zero is not refused by name: %r" % (message,))
    message = _refuses(s.PartitionError, "a width of zero with a step",
                       lambda: s.windows(0, 10, 0, step=5))
    assert "width" in message, (
        "a width of zero is accepted because a step was given: %r" % (message,))
    message = _refuses(s.PartitionError, "a negative width",
                       lambda: s.windows(0, 10, -5))
    assert "width" in message and "-5" in message, (
        "a negative width is not refused by name: %r" % (message,))
    message = _refuses(s.PartitionError, "a step of zero",
                       lambda: s.windows(0, 10, 20, step=0))
    assert "step" in message and "0" in message, (
        "a step of zero is not refused by name: %r" % (message,))
    message = _refuses(s.PartitionError, "a negative step",
                       lambda: s.windows(0, 10, 20, step=-2))
    assert "step" in message and "-2" in message, (
        "a negative step is not refused by name: %r" % (message,))
    message = _refuses(s.PartitionError, "a step past the width",
                       lambda: s.windows(0, 10, 20, step=21))
    assert "hole" in message and "21" in message and "20" in message, (
        "a step past the width is not refused as the hole it leaves: %r"
        % (message,))
    message = _refuses(s.PartitionError, "a step handed over as a name",
                       lambda: s.windows(0, 10, 20, step="20"))
    assert "step" in message and "str" in message, (
        "a step that is not an int is not refused by name and by shape: %r"
        % (message,))
    message = _refuses(s.PartitionError, "a start that is not a tick",
                       lambda: s.windows("0", 10, 5))
    assert "start" in message and "str" in message, (
        "a start that is not an int is not refused by name: %r" % (message,))
    message = _refuses(s.PartitionError, "a negative start",
                       lambda: s.windows(-1, 10, 5))
    assert "start" in message and "-1" in message, (
        "a negative start is not refused by name: %r" % (message,))
    message = _refuses(s.PartitionError, "an end that is a float",
                       lambda: s.windows(0, 10.5, 5))
    assert "end" in message and "float" in message, (
        "an end that is not an int is not refused by name: %r" % (message,))
    message = _refuses(s.PartitionError, "a width that is a bool",
                       lambda: s.windows(0, 10, True, step=1))
    assert "width" in message and "bool" in message, (
        "a width that is a bool is accepted: %r" % (message,))

    # ---- fold: one window's numbers ---------------------------------------

    gauge = (
        world.event(tick=10, task="alpha", pool="small", tenant="batch",
                    kind="finished", attempt=1, outcome="failed", service=3,
                    tokens_in=10, tokens_out=4, error="failed"),
        world.event(tick=0, task="alpha", pool="small", tenant="batch",
                    kind="admitted", attempt=1),
        world.event(tick=6, task="beta", pool="small", tenant="batch",
                    kind="admitted", attempt=1),
        world.event(tick=20, task="epsilon", pool="small", tenant="batch",
                    kind="admitted", attempt=1),
        world.event(tick=8, task="gamma", pool="small", tenant="batch",
                    kind="admitted", attempt=1),
        world.event(tick=4, task="alpha", pool="small", tenant="batch",
                    kind="started", attempt=1, wait=4),
        world.event(tick=10, task="alpha", pool="small", tenant="batch",
                    kind="retried", attempt=1, error="failed"),
        world.event(tick=10, task="gamma", pool="small", tenant="batch",
                    kind="dropped", attempt=1, error="out_of_time"),
        world.event(tick=12, task="beta", pool="small", tenant="batch",
                    kind="finished", attempt=1, outcome="ok", service=6,
                    tokens_in=20, tokens_out=8),
        world.event(tick=14, task="delta", pool="small", tenant="batch",
                    kind="dropped", attempt=1, error="queue_full"),
        world.event(tick=6, task="beta", pool="small", tenant="batch",
                    kind="started", attempt=1, wait=0),
        world.event(tick=16, task="alpha", pool="small", tenant="batch",
                    kind="finished", attempt=2, outcome="ok", service=4,
                    tokens_in=10, tokens_out=4),
        world.event(tick=6, task="zeta", pool="small", tenant="batch",
                    kind="admitted", attempt=1),
        world.event(tick=12, task="theta", pool="small", tenant="batch",
                    kind="admitted", attempt=1),
        world.event(tick=12, task="theta", pool="small", tenant="batch",
                    kind="finished", attempt=1, outcome="ok", service=1,
                    tokens_in=5, tokens_out=2),
    )
    for event in gauge:
        assert stage_01.parse_event(event) == event, (
            "the check's own fixture is not an event this course would accept: %r"
            % (event,))
    same_tick = (
        world.event(tick=3, task="solo", pool="small", tenant="batch",
                    kind="admitted", attempt=1),
        world.event(tick=3, task="solo", pool="small", tenant="batch",
                    kind="finished", attempt=1, outcome="ok", service=2,
                    tokens_in=5, tokens_out=2),
    )
    assert s.fold(same_tick, {"start": 3, "end": 4})["peak_depth"] == {
        "tick": 3, "depth": 0}, (
        "a task admitted and finished at the same tick does not net out to zero: "
        "a tick's events are added up before the tick is looked at, so neither "
        "the order the two were written in nor which of them came last decides "
        "what the queue was: %r" % (s.fold(same_tick, {"start": 3, "end": 4}),))

    one = s.fold(gauge, {"start": 0, "end": 20})
    assert tuple(one) == s.FOLD_KEYS, (
        "a fold's keys are %r, not %r and in that order"
        % (tuple(one), s.FOLD_KEYS))
    assert one["start"] == 0 and one["end"] == 20, (
        "a fold of [0, 20) says it is %r to %r" % (one["start"], one["end"]))
    assert tuple(event["tick"] for event in one["events"]) == (10, 0, 6, 8, 4, 10,
                                                              10, 12, 14, 6, 16, 6,
                                                              12, 12), (
        "a fold's events are %r: the ones in the window, in the order they were "
        "given — a fold never sorts, and the fixture is deliberately unsorted"
        % (tuple(event["tick"] for event in one["events"]),))
    assert one["count"] == 14 and one["count"] == len(one["events"]), (
        "a fold of fourteen events counts %r" % (one["count"],))
    assert one["total"] == 14, (
        "the ticks the window spent are %r, not 3 + 6 + 4 + 1: an event whose kind "
        "carries no service spends none, and a total of a window is the sum of what "
        "its events measured" % (one["total"],))
    assert tuple(one["peak_depth"]) == ("tick", "depth"), (
        "a fold's peak_depth is %r, not stage 3's two keys" % (one["peak_depth"],))
    assert one["peak_depth"] == {"tick": 8, "depth": 4}, (
        "the deepest the queue got in [0, 20) is %r: four tasks were in flight "
        "from tick 8, and the first tick that attains the maximum is the one that "
        "is reported" % (one["peak_depth"],))

    middle = s.fold(gauge, {"start": 10, "end": 12})
    assert middle["total"] == 3 and middle["count"] == 3, (
        "the window [10, 12) holds %r events spending %r: the finish at exactly "
        "12 is out" % (middle["count"], middle["total"]))
    assert middle["peak_depth"] == {"tick": 10, "depth": 3}, (
        "the queue is three deep at ticks 10 and 11, and the peak is reported at "
        "%r: the tie goes to the first tick that attains it"
        % (middle["peak_depth"],))
    assert s.fold(gauge, {"start": 20, "end": 21}) == {
        "start": 20, "end": 21,
        "events": (gauge[3],), "count": 1, "total": 0,
        "peak_depth": {"tick": 20, "depth": 2}}, (
        "a window holding one event that spent nothing is %r: zero service in a "
        "window is a measurement, not a silence, and the queue a window opens on "
        "is the queue the run left it"
        % (s.fold(gauge, {"start": 20, "end": 21}),))
    empty = s.fold(gauge, {"start": 30, "end": 40})
    assert empty["count"] == 0 and empty["events"] == () and empty["total"] == 0, (
        "a window with no events in it is %r: a window past the end of a run has "
        "a fold, and it is nothing" % (empty,))

    # the boundary rule, both sides
    assert tuple(event["tick"] for event in s.fold(
        gauge, {"start": 0, "end": 10})["events"]) == (0, 6, 8, 4, 6, 6), (
        "the events of [0, 10) are %r: an event at exactly 10 is out, and one at "
        "exactly 0 is in" % (s.fold(gauge, {"start": 0, "end": 10})["events"],))
    assert [event["task"] for event in s.fold(
        gauge, {"start": 10, "end": 20})["events"]] == ["alpha", "alpha", "gamma",
                                                        "beta", "delta", "alpha",
                                                        "theta", "theta"], (
        "the events of [10, 20) are not the ones from tick 10 up to tick 20")

    # a fold is a read: the events it was handed are the events it was handed
    before = [dict(event) for event in gauge]
    assert tuple(event["tick"] for event in gauge) == (10, 0, 6, 20, 8, 4, 10, 10,
                                                       12, 14, 6, 16, 6, 12, 12)
    s.partition(gauge, s.windows(0, 20, 10))
    assert [dict(event) for event in gauge] == before, (
        "folding the events changed them: a fold is a read, not a rewrite")

    # every tick of a run's depth, against the check's own count of it
    run = world.record()
    events = run["events"]
    for source, last in ((gauge, 22), (events, 48)):
        for tick in range(0, last):
            got = s.fold(source, {"start": tick, "end": tick + 1})["peak_depth"]
            assert got == {"tick": tick, "depth": _flight(source, tick)}, (
                "the depth at tick %d is %r, not the %d tasks in flight: a finish "
                "a retry follows is not a departure, and a drop of a task nobody "
                "admitted is not one either"
                % (tick, got, _flight(source, tick)))
    assert s.fold(events, world.window("minute"))["peak_depth"] == {
        "tick": 5, "depth": 5}, (
        "the deepest the default run's queue gets is %r: five tasks in flight "
        "from tick 5" % (s.fold(events, world.window("minute"))["peak_depth"],))

    message = _refuses(s.PartitionError, "a spec that is not a mapping",
                       lambda: s.fold(gauge, 20))
    assert "mapping" in message and "int" in message, (
        "a spec that is not a window is not refused by shape: %r" % (message,))
    message = _refuses(s.PartitionError, "a spec with a misspelled start",
                       lambda: s.fold(gauge, {"strat": 0, "end": 10}))
    assert "start" in message and "strat" in message, (
        "a spec missing 'start' is not refused by name and by the key it probably "
        "meant: %r" % (message,))
    message = _refuses(s.PartitionError, "a spec with no end",
                       lambda: s.fold(gauge, {"start": 0}))
    assert "end" in message, (
        "a spec with no end is not refused by name: %r" % (message,))
    message = _refuses(s.PartitionError, "a spec that is a point",
                       lambda: s.fold(gauge, {"start": 5, "end": 5}))
    assert "point" in message, (
        "a spec with no width is not refused as a point: %r" % (message,))
    message = _refuses(s.PartitionError, "a spec with a negative start",
                       lambda: s.fold(gauge, {"start": -3, "end": 5}))
    assert "negative" in message and "-3" in message, (
        "a spec whose start is negative is not refused by name: %r" % (message,))
    message = _refuses(s.PartitionError, "a spec whose start is a name",
                       lambda: s.fold(gauge, {"start": "0", "end": 5}))
    assert "start" in message and "str" in message, (
        "a spec whose start is not an int is not refused by name: %r" % (message,))
    message = _refuses(s.PartitionError, "events that are not a sequence",
                       lambda: s.fold(12, {"start": 0, "end": 5}))
    assert "sequence" in message and "int" in message, (
        "events that are not a sequence are not refused by shape: %r" % (message,))
    message = _refuses(s.PartitionError, "a mapping of events",
                       lambda: s.fold({"tick": 0}, {"start": 0, "end": 5}))
    assert "sequence" in message, (
        "a mapping handed over as events is not refused by shape: %r" % (message,))
    message = _refuses(s.PartitionError, "an event that is not a mapping",
                       lambda: s.fold((gauge[1], 7), {"start": 0, "end": 5}))
    assert "event 1" in message and "int" in message, (
        "an event that is not a mapping is not refused by its index: %r"
        % (message,))
    message = _refuses(s.PartitionError, "an event with no tick",
                       lambda: s.fold(({"kind": "admitted", "task": "a"},),
                                      {"start": 0, "end": 5}))
    assert "event 0" in message and "tick" in message, (
        "an event with no tick is not refused by its index: %r" % (message,))
    message = _refuses(s.PartitionError, "a service that is not a count",
                       lambda: s.fold((world.event(tick=0, task="a", pool="small",
                                                   tenant="batch", kind="finished",
                                                   attempt=1, outcome="ok",
                                                   service="three", tokens_in=1,
                                                   tokens_out=1),),
                                      {"start": 0, "end": 5}))
    assert "service" in message and "three" in message, (
        "a service that is not a count is summed into the window anyway: %r"
        % (message,))
    message = _refuses(s.PartitionError, "a queue that would go negative",
                       lambda: s.fold((world.event(tick=2, task="ghost",
                                                   pool="small", tenant="batch",
                                                   kind="finished", attempt=1,
                                                   outcome="ok", service=1,
                                                   tokens_in=1, tokens_out=1),),
                                      {"start": 0, "end": 5}))
    assert "negative" in message and "2" in message, (
        "a finish nobody admitted is not refused as the broken fixture it is — a "
        "queue of minus one: %r" % (message,))

    # ---- partition and covers: the property the schema cannot state --------

    folds = s.partition(gauge, s.windows(0, 20, 10))
    assert isinstance(folds, tuple) and len(folds) == 2, (
        "partition answers %r: a sequence of folds, in the order the windows "
        "happen" % (folds,))
    assert tuple(fold["start"] for fold in folds) == (0, 10), (
        "the folds come back in the order %r, not the order their windows happen"
        % (tuple(fold["start"] for fold in folds),))
    gathered = tuple(event for fold in folds for event in fold["events"])
    inside = tuple(event for event in gauge if event["tick"] < 20)
    for fold in folds:
        expected = tuple(event for event in gauge
                         if fold["start"] <= event["tick"] < fold["end"])
        assert fold["events"] == expected, (
            "the fold of [%d, %d) holds %r: the window's events, in the order they "
            "were given — a fold never sorts, and the fixture is unsorted"
            % (fold["start"], fold["end"],
               tuple(event["tick"] for event in fold["events"])))
    assert Counter(tuple(sorted(event.items())) for event in gathered) == Counter(
            tuple(sorted(event.items())) for event in inside), (
        "the folds' events are not the interval's events once each: for a tumbling "
        "set every event of [start, end) is in exactly one fold — which is what "
        "makes two overlapping windows agree on their overlap")
    assert sum(fold["count"] for fold in folds) == len(gathered) == len(inside), (
        "the folds' counts do not add up to the events they hold between them")

    assert s.covers(gauge, s.windows(0, 20, 10)) is True, (
        "the tumbling set does not cover its own interval")
    assert s.covers(gauge, ({"start": 0, "end": 20},)) is True, (
        "one window does not cover its own interval")
    assert s.covers(gauge, s.windows(0, 20, 12, step=6)) is False, (
        "a sliding set is answered True: the events in the overlap are "
        "deliberately in two folds, and summing them would count them twice")
    assert s.covers(gauge, s.windows(0, 20, 20, step=10)) is False, (
        "a sliding set is answered True")
    assert s.covers(gauge, ({"start": 0, "end": 10},
                            {"start": 12, "end": 20})) is False, (
        "a set with a hole is answered True: the events between 10 and 12 are in "
        "no window at all")
    assert s.covers(gauge, ({"start": 0, "end": 10},
                            {"start": 10, "end": 20})) is True, (
        "a pair of windows that abut does not cover their interval")
    assert s.covers(gauge, ({"start": 20, "end": 22},)) is True, (
        "the window the last event is in does not cover its own interval")

    message = _refuses(s.PartitionError, "a window set with no windows",
                       lambda: s.partition(gauge, ()))
    assert "windows" in message, (
        "a window set with no windows in it is not refused by name: %r"
        % (message,))
    message = _refuses(s.PartitionError, "a window set out of order",
                       lambda: s.partition(gauge, ({"start": 10, "end": 20},
                                                   {"start": 0, "end": 10})))
    assert "order" in message and "1" in message, (
        "a window set whose second window starts before its first is not refused "
        "by name and index: %r" % (message,))
    message = _refuses(s.PartitionError, "a window set handed over as a name",
                       lambda: s.partition(gauge, "minute"))
    assert "sequence" in message and "str" in message, (
        "a window set that is not a sequence is not refused by shape: %r"
        % (message,))
    message = _refuses(s.PartitionError, "a window set handed over as one spec",
                       lambda: s.covers(gauge, {"start": 0, "end": 10}))
    assert "sequence" in message and "dict" in message, (
        "one spec is not a window set, and both shapes are not named: %r"
        % (message,))
    message = _refuses(s.PartitionError, "covers over an empty window set",
                       lambda: s.covers(gauge, ()))
    assert "windows" in message, (
        "covers over a window set with no windows in it is not refused: %r"
        % (message,))

    # ---- the world's own run, folded --------------------------------------

    minute = s.windows(**world.window("minute"))
    folds = s.partition(events, minute)
    assert tuple(fold["start"] for fold in folds) == (0, 20, 40, 60, 80, 100), (
        "the minute fixture's folds start at %r"
        % (tuple(fold["start"] for fold in folds),))
    gathered = tuple(event for fold in folds for event in fold["events"])
    assert gathered == events, (
        "the default run's events are not the minute folds' events, in order, "
        "once each: %d of the run's %d are in a fold"
        % (len(gathered), len(events)))
    assert sum(fold["total"] for fold in folds) == sum(
            event["service"] for event in events
            if event["service"] != world.ABSENT), (
        "the folds' totals do not add up to the run's service: a counter summed "
        "over a partition of a window is the whole window")
    assert sum(fold["count"] for fold in folds) == len(events), (
        "the folds do not hold every event of the run")
    assert s.covers(events, minute) is True, (
        "the minute fixture does not partition the default run")
    assert s.covers(events, s.windows(**world.window("rolling"))) is False, (
        "the rolling fixture is reported as a partition: its windows overlap on "
        "purpose, and a fold over them may not be summed")
    for fold in folds:
        assert tuple(fold) == s.FOLD_KEYS, (
            "a fold of the run is %r, not a fold over FOLD_KEYS" % (tuple(fold),))

    # the fleet's own family, and the stage's
    assert issubclass(fleet.QueueError, ValueError), (
        "the fleet's refusals are ValueErrors too — one course, one family")

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "agent-metrics-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J5_REPO=/path/to/learn-stuff-from-scratch")

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

    def _flight(events, tick):
        """How many tasks are in flight at `tick`: the check's own count of them.

        A task is in flight from the tick it is admitted to the tick it leaves for
        good — a finish no retry follows, or a drop of a task that was in the queue
        to be dropped. Written the slow, obvious way on purpose: two readers of the
        same rule is the only way to check one of them.
        """
        again = {(event["task"], event["attempt"]) for event in events
                 if event["kind"] == "retried"}
        admitted = {event["task"] for event in events
                    if event["kind"] == "admitted"}
        live = set()
        for event in events:
            if event["tick"] > tick:
                continue
            if event["kind"] == "admitted":
                live.add(event["task"])
            elif event["kind"] == "finished" \
                    and (event["task"], event["attempt"]) not in again:
                live.discard(event["task"])
            elif event["kind"] == "dropped" and event["task"] in admitted:
                live.discard(event["task"])
        return len(live)

    def _peak_flight(events, start, end):
        """The first tick of `[start, end)` where the check's own count is deepest.

        The tally is frozen the way stage 3 freezes it: the *first* tick that attains
        the maximum, over a series that carries what the ticks before the window left
        behind.
        """
        best_tick, best_depth = start, 0
        for tick in range(start, end):
            depth = _flight(events, tick)
            if depth > best_depth:
                best_tick, best_depth = tick, depth
        return (best_tick, best_depth)

    def _attempts(events):
        """`(wait + service, the tick it finished at)` for every finished attempt.

        Matched by `(task, attempt)` the way stage 5 matches them, but written here
        so that the two readers can disagree.
        """
        started = {(event["task"], event["attempt"]): event["wait"]
                   for event in events if event["kind"] == "started"}
        found = []
        for event in events:
            if event["kind"] == "finished":
                found.append((started[(event["task"], event["attempt"])]
                              + event["service"], event["tick"]))
        return tuple(found)

    def _latency_in(events, start, end):
        """The latencies of the attempts the check says finished in `[start, end)`."""
        return tuple(latency for latency, tick in _attempts(events)
                     if start <= tick < end)

    def _nearest(values, numerator, denominator):
        """The nearest-rank quantile by hand: `ceil(n * num / den) - 1`, clamped."""
        ordered = sorted(values)
        index = (len(ordered) * numerator + denominator - 1) // denominator - 1
        return ordered[max(0, index)]

    def _numbers(events, start, end, kind):
        """How many events of one kind the check itself finds in `[start, end)`."""
        return sum(1 for event in events
                   if event["kind"] == kind and start <= event["tick"] < end)

    def _spent(events, start, end, price):
        """The window's micros, priced by the check from the price it was handed."""
        total = 0
        for event in events:
            if event["kind"] == "finished" and start <= event["tick"] < end:
                total += (event["tokens_in"] * price["in"]
                          + event["tokens_out"] * price["out"])
        return total

    def _tokens(events, start, end):
        """What the window spent in tokens, counted by the check."""
        spent_in = 0
        spent_out = 0
        for event in events:
            if event["kind"] == "finished" and start <= event["tick"] < end:
                spent_in += event["tokens_in"]
                spent_out += event["tokens_out"]
        return spent_in, spent_out

    from collections.abc import Mapping, Sequence

    import stage_01
    import stage_04
    import stage_09 as s

    import telemetry as world

    # ---- the shape this stage freezes -------------------------------------

    assert s.METRIC_KEYS == ("events", "tasks", "attempts", "failures",
                             "retries", "dropped", "in_flight", "depth",
                             "peak_tick", "peak_depth", "p50", "p95", "p99",
                             "tokens_in", "tokens_out", "micros", "failure_bp",
                             "retry_bp"), (
        "METRIC_KEYS is %r: a report is the eighteen cells of the contract, in "
        "the contract's order — the counts, then the window's two ends and its "
        "peak, then the quantiles, the spend and the rates" % (s.METRIC_KEYS,))
    cells = s.METRIC_KEYS
    assert isinstance(cells, Sequence) and not isinstance(cells, str), (
        "METRIC_KEYS is %r: a row's cell names are a tuple, not something a "
        "caller may append to" % (type(cells).__name__,))
    assert len(set(cells)) == 18, (
        "METRIC_KEYS names %d cells: eighteen keys, no repeats"
        % (len(set(cells)),))
    assert issubclass(s.ReportError, stage_01.TelemetryError), (
        "%r is not a %s: one `except TelemetryError` must still catch a broken "
        "report" % (s.ReportError, stage_01.TelemetryError.__name__))
    assert issubclass(s.ReportError, ValueError), (
        "%r is not a ValueError: every refusal in this course is a verdict on a "
        "value" % (s.ReportError,))

    # ---- a ledger whose every cell can be argued by hand -------------------
    #
    # Two tasks: alpha is admitted at 0, started at 2 and done at 4 (ok, 10 in
    # and 4 out); beta is admitted and started at 5 and allowed to fail at 7,
    # which is what puts a retry — and a task that stays in flight — into the
    # ledger; gamma is dropped at 9 without ever being admitted, so a drop that
    # departs from nothing is in the fixtures too.

    ledger = (
        world.event(tick=0, task="alpha", pool="small", tenant="batch",
                    kind="admitted", attempt=1),
        world.event(tick=2, task="alpha", pool="small", tenant="batch",
                    kind="started", attempt=1, wait=2),
        world.event(tick=4, task="alpha", pool="small", tenant="batch",
                    kind="finished", attempt=1, outcome="ok", service=2,
                    tokens_in=10, tokens_out=4),
        world.event(tick=5, task="beta", pool="small", tenant="batch",
                    kind="admitted", attempt=1),
        world.event(tick=5, task="beta", pool="small", tenant="batch",
                    kind="started", attempt=1, wait=0),
        world.event(tick=7, task="beta", pool="small", tenant="batch",
                    kind="finished", attempt=1, outcome="failed", service=2,
                    tokens_in=5, tokens_out=2, error="failed"),
        world.event(tick=7, task="beta", pool="small", tenant="batch",
                    kind="retried", attempt=1, error="failed"),
        world.event(tick=9, task="gamma", pool="small", tenant="batch",
                    kind="dropped", attempt=1, error="out_of_time"),
    )
    kept = tuple(dict(event) for event in ledger)

    opening = s.metrics(ledger, start=0, end=5)
    assert opening == (
        {"events": 3, "tasks": 1, "attempts": 1, "failures": 0, "retries": 0,
         "dropped": 0, "in_flight": 0, "depth": 1, "peak_tick": 0,
         "peak_depth": 1, "p50": 4, "p95": 4, "p99": 4, "tokens_in": 10,
         "tokens_out": 4, "micros": 68, "failure_bp": 0, "retry_bp": 0}), (
        "the row for [0, 5) of the ledger is %r: three events, one task finished "
        "on one attempt with no failure, a queue of one at the window's first "
        "tick and none at its last, and one attempt of wait+service 4"
        % (opening,))

    closing = s.metrics(ledger, start=5, end=10)
    assert closing == (
        {"events": 5, "tasks": 1, "attempts": 1, "failures": 1, "retries": 1,
         "dropped": 1, "in_flight": 1, "depth": 1, "peak_tick": 5,
         "peak_depth": 1, "p50": 2, "p95": 2, "p99": 2, "tokens_in": 5,
         "tokens_out": 2, "micros": 34, "failure_bp": 10000, "retry_bp": 10000}), (
        "the row for [5, 10) of the ledger is %r: one failed attempt is a "
        "failure and, with one admission, a failure rate of every attempt — and "
        "the task it retried is still in flight at the window's last tick"
        % (closing,))

    assert tuple(opening) == s.METRIC_KEYS, (
        "a row is %r: the cells are written in `METRIC_KEYS` order"
        % (list(opening),))
    assert all(isinstance(value, int) and not isinstance(value, bool)
               for value in opening.values()), (
        "the row holds %r: every cell of a report is an int count"
        % (opening,))

    # ---- the boundary, both sides, once -----------------------------------

    assert s.metrics(ledger, start=5, end=6)["events"] == 2, (
        "a window that starts at 5 gives %r: an event at `tick == start` is in"
        % (s.metrics(ledger, start=5, end=6),))
    before = s.metrics(ledger, start=0, end=7)
    after = s.metrics(ledger, start=0, end=8)
    assert (before["events"], after["events"]) == (5, 7), (
        "the ledger holds %r events up to tick 7 and %r up to tick 8: the two "
        "events at `tick == 7` are the ones the boundary decides"
        % (before["events"], after["events"]))
    assert (before["attempts"], after["attempts"]) == (1, 2), (
        "the attempts before the boundary and after it are %r: an attempt "
        "finishing at `tick == end` is out of the window that ends there"
        % ((before["attempts"], after["attempts"]),))
    assert (before["retries"], after["retries"]) == (0, 1), (
        "the retries before and after the boundary are %r"
        % ((before["retries"], after["retries"]),))
    assert (before["failure_bp"], after["failure_bp"]) == (0, 5000), (
        "the failure rates before and after the boundary are %r: one failure in "
        "two attempts is 5000 basis points" % ((before["failure_bp"],
                                                after["failure_bp"]),))
    assert (before["tokens_in"], after["tokens_in"]) == (10, 15), (
        "the tokens the two windows spent are %r"
        % ((before["tokens_in"], after["tokens_in"]),))

    # ---- a window is a state somebody was already in ----------------------

    middle = s.metrics(ledger, start=4, end=7)
    assert (middle["depth"], middle["in_flight"]) == (0, 1), (
        "the window [4, 7) opens with %r and closes with %r in flight: alpha "
        "finished at 4, and beta was admitted at 5 and is still there at 6"
        % (middle["depth"], middle["in_flight"]))
    assert (middle["peak_tick"], middle["peak_depth"]) == (5, 1), (
        "the peak of [4, 7) is %r: the first tick inside the window that attains "
        "the deepest queue" % ((middle["peak_tick"], middle["peak_depth"]),))
    assert (middle["p50"], middle["p95"], middle["p99"]) == (4, 4, 4), (
        "the quantiles of [4, 7) are %r: alpha's attempt finished at 4 — inside "
        "the window — although it was started at 2, outside it, so an attempt "
        "whose start the window cut off is still the window's measurement"
        % ((middle["p50"], middle["p95"], middle["p99"]),))

    late = s.metrics(ledger, start=20, end=30)
    assert (late["events"], late["depth"], late["in_flight"]) == (0, 1, 1), (
        "the window [20, 30) holds %r events, and its depth is %r rather than "
        "zero: nothing fell in it, and beta was put in flight at 5 and never "
        "left it" % (late["events"], late["depth"]))
    assert (late["peak_tick"], late["peak_depth"]) == (20, 1), (
        "the peak of an empty window that a queue ran through is %r: stage 3's "
        "first tick that attains it" % ((late["peak_tick"], late["peak_depth"]),))
    assert all(late[key] == 0 for key in ("p50", "p95", "p99", "failure_bp",
                                          "retry_bp", "micros", "tokens_in")), (
        "the folds of a window that measured nothing are %r: the report answers "
        "zero where stages 4 and 7 refuse, and the refusal stays where it was"
        % (late,))
    assert _refuses(stage_04.QuantileError,
                    "a percentile of no samples",
                    lambda: stage_04.quantile((), 95, 100)), (
        "stage 4's refusal has moved: a quantile of nothing must still refuse, "
        "because the report answers zero and the fold does not")

    # ---- the default window is the whole run ------------------------------

    assert s.metrics(ledger) == s.metrics(ledger, start=0, end=10), (
        "the ledger's default window is %r, not the whole of it"
        % (s.metrics(ledger),))
    offset = (
        world.event(tick=3, task="solo", pool="small", tenant="batch",
                    kind="admitted", attempt=1),
        world.event(tick=3, task="solo", pool="small", tenant="batch",
                    kind="started", attempt=1, wait=0),
        world.event(tick=5, task="solo", pool="small", tenant="batch",
                    kind="finished", attempt=1, outcome="ok", service=2,
                    tokens_in=7, tokens_out=1),
    )
    assert s.metrics(offset) == s.metrics(offset, start=3, end=6), (
        "a run whose first event is at tick 3 defaults to %r, not to the window "
        "its first tick to its last tick plus one names"
        % (s.metrics(offset),))
    assert (s.metrics(offset)["events"], s.metrics(offset)["depth"]) == (3, 1), (
        "the offset run's whole window is %r: three events, and a queue of one "
        "at the tick the run began"
        % (s.metrics(offset),))
    assert s.metrics(()) == dict.fromkeys(s.METRIC_KEYS, 0), (
        "a run with no events answers %r: a dashboard over a fleet that did "
        "nothing is a row of zeros" % (s.metrics(()),))

    # ---- the world's own count is the tie-breaker -------------------------

    run = world.record()
    events = stage_01.read_events(run["text"])
    summary = run["summary"]
    frozen = tuple(dict(event) for event in events)
    row = s.metrics(events)

    assert tuple(row) == tuple(s.METRIC_KEYS), (
        "the run's row is %r: the eighteen cells, in order" % (list(row),))
    for key in world.SUMMARY_KEYS:
        if key in s.METRIC_KEYS:
            assert row[key] == summary[key], (
                "the row's %s is %r and the fleet counted %r: a fold that "
                "disagrees with the world that made it has lost an event"
                % (key, row[key], summary[key]))

    start, last = summary["first_tick"], summary["last_tick"]
    kinds = sum(_numbers(events, start, last + 1, kind)
                for kind in world.KINDS)
    assert row["events"] == len(events) == kinds, (
        "the row counts %r events, the run has %r, and its five kinds hold %r"
        % (row["events"], len(events), kinds))
    assert row["tasks"] == _numbers(events, start, last + 1, "admitted"), (
        "the row's tasks is %r and the run admitted %r"
        % (row["tasks"], _numbers(events, start, last + 1, "admitted")))
    assert row["attempts"] == _numbers(events, start, last + 1, "finished"), (
        "the row's attempts is %r and the run finished %r"
        % (row["attempts"], _numbers(events, start, last + 1, "finished")))
    assert row["retries"] == _numbers(events, start, last + 1, "retried"), (
        "the row's retries is %r and the run retried %r"
        % (row["retries"], _numbers(events, start, last + 1, "retried")))
    assert row["dropped"] == _numbers(events, start, last + 1, "dropped"), (
        "the row's dropped is %r and the run dropped %r"
        % (row["dropped"], _numbers(events, start, last + 1, "dropped")))
    assert row["failures"] == sum(
        1 for event in events
        if event["kind"] == "finished" and event["outcome"] != "ok"), (
        "the row's failures is %r: one failure per attempt that did not succeed, "
        "never one per task" % (row["failures"],))

    assert (row["depth"], row["in_flight"]) == (_flight(events, start),
                                                _flight(events, last)), (
        "the row's depth at the window's two ends is %r, and the run's own count "
        "of what is in flight says %r"
        % ((row["depth"], row["in_flight"]),
           (_flight(events, start), _flight(events, last))))
    assert (row["peak_tick"], row["peak_depth"]) == _peak_flight(events, start,
                                                                 last + 1), (
        "the row's peak is %r and the check's own count of the queue makes it %r"
        % ((row["peak_tick"], row["peak_depth"]),
           _peak_flight(events, start, last + 1)))

    latencies = _latency_in(events, start, last + 1)
    assert (row["p50"], row["p95"], row["p99"]) == (
        _nearest(latencies, 50, 100), _nearest(latencies, 95, 100),
        _nearest(latencies, 99, 100)), (
        "the row's quantiles are %r and the run's %d attempts make them %r"
        % ((row["p50"], row["p95"], row["p99"]), len(latencies),
           (_nearest(latencies, 50, 100), _nearest(latencies, 95, 100),
            _nearest(latencies, 99, 100))))
    assert len(latencies) == row["attempts"], (
        "the row holds %r quantiles over %r attempts that finished in the "
        "window" % (len(latencies), row["attempts"]))
    assert row["p95"] in latencies and row["p99"] in latencies, (
        "a quantile is one of the samples: %r is not one of %r"
        % ((row["p95"], row["p99"]), sorted(latencies)))

    assert (row["tokens_in"], row["tokens_out"]) == _tokens(events, start,
                                                            last + 1), (
        "the row's tokens are %r and the run's finished events spent %r"
        % ((row["tokens_in"], row["tokens_out"]),
           _tokens(events, start, last + 1)))
    assert row["micros"] == _spent(events, start, last + 1,
                                   world.PRICES["small"]), (
        "the row's micros is %r and the world's own price table makes the run "
        "spend %r"
        % (row["micros"],
           _spent(events, start, last + 1, world.PRICES["small"])))
    assert row["failure_bp"] == (row["failures"] * 10000 // row["attempts"]), (
        "the row's failure_bp is %r: failures over attempts, floored"
        % (row["failure_bp"],))
    assert row["retry_bp"] == (row["retries"] * 10000 // row["tasks"]), (
        "the row's retry_bp is %r: retries over admissions, floored"
        % (row["retry_bp"],))

    assert s.metrics(events) == s.metrics(events, start=start, end=last + 1), (
        "the run's default window is not its own first tick to its last tick "
        "plus one")

    # ---- a sub-window of a run is a window like any other -----------------

    part = s.metrics(events, start=20, end=40)
    inside = _latency_in(events, 20, 40)
    assert part["events"] == sum(1 for event in events
                                 if 20 <= event["tick"] < 40), (
        "the sub-window [20, 40) holds %r events" % (part["events"],))
    assert part["depth"] == _flight(events, 20) == 5, (
        "the sub-window opens with %r in flight: the queue at 20 is what the "
        "ticks before the window left behind, %r"
        % (part["depth"], _flight(events, 20)))
    assert (part["p50"], part["p95"]) == (_nearest(inside, 50, 100),
                                          _nearest(inside, 95, 100)), (
        "the sub-window's quantiles are %r over the attempts that finished in it "
        "(%r), not over the run's"
        % ((part["p50"], part["p95"]), inside))
    assert part["micros"] == _spent(events, 20, 40, world.PRICES["small"]), (
        "the sub-window's micros is %r and its own events make it %r"
        % (part["micros"], _spent(events, 20, 40, world.PRICES["small"])))
    assert (part["depth"], part["in_flight"], part["p95"]) != (
        row["depth"], row["in_flight"], row["p95"]), (
        "a sub-window folds to the whole run's row: the window is the decision")

    drained = s.metrics(events, start=last + 1, end=last + 2)
    assert (drained["events"], drained["depth"],
            drained["in_flight"]) == (0, 0, 0), (
        "the window one past the run's end is %r: nothing fell in it, and the "
        "run was drained by then" % (drained,))
    assert all(drained[key] == 0 for key in s.METRIC_KEYS
               if key != "peak_tick"), (
        "the zero row of a drained window is %r: every cell the window measured "
        "is zero" % (drained,))
    assert (drained["peak_tick"], drained["peak_depth"]) == (last + 1, 0), (
        "the peak of a drained window is %r: stage 3's first tick that attains "
        "it — the tick the window opened at, which is where a peak of zero is "
        "first attained inside it" % ((drained["peak_tick"],
                                       drained["peak_depth"]),))

    kept_events = tuple(dict(event) for event in events)
    assert kept_events == frozen and kept == tuple(dict(event) for event in ledger), (
        "the events have moved: a fold reads its input and never rewrites it")

    # ---- report: the row, once the fleet's count agrees -------------------

    tied = s.report(events, summary)
    assert tied == row, (
        "the report of a run whose fleet count agrees with it is %r, not the "
        "row %r" % (tied, row))
    assert tied is not summary and tied is not row, (
        "the report handed back the caller's own mapping: a row is a fresh "
        "mapping every time")
    assert s.report(events, {}) == row, (
        "a fleet's count that carries nothing compares nothing: %r"
        % (s.report(events, {}),))

    carrying = dict(summary, in_flight=row["in_flight"] + 99)
    assert s.report(events, carrying) == row, (
        "a summary carrying `in_flight` was compared: it is the window's own end "
        "state and never a key the fleet's count decides")

    lie = dict(summary, failures=summary["failures"] + 1)
    message = _refuses(s.ReportError, "a report the events do not support",
                       lambda: s.report(events, lie))
    assert "failures" in message, (
        "the refusal does not name the key the fleet and the events disagree "
        "about: %r" % (message,))
    assert "counted %d" % lie["failures"] in message, (
        "the refusal does not carry the fleet's own number: %r" % (message,))
    assert "say %d" % row["failures"] in message, (
        "the refusal does not carry the number the events produced: %r"
        % (message,))
    assert _refuses(s.ReportError, "a report over a sub-window",
                    lambda: s.report(events, summary, start=start + 1,
                                     end=last + 1)), (
        "a whole-run fleet count compared against a sub-window must refuse")
    message = _refuses(s.ReportError, "a fleet's count that is not a mapping",
                       lambda: s.report(events, ["failures", "attempts"]))
    assert "list" in message, (
        "a summary that is not a mapping is not refused by its shape: %r"
        % (message,))

    # ---- audit: the same walk, reporting instead of raising ---------------

    audited = s.audit(events, summary)
    assert tuple(audited) == ("missing", "extra", "count"), (
        "an audit is %r: the keys it could not explain, the cells the fleet "
        "never counted, and how many it compared" % (list(audited),))
    assert audited["missing"] == ("admissions", "died", "first_tick",
                                  "last_tick"), (
        "the keys of the fleet's count the row cannot explain are %r: the row "
        "has no cell for them" % (audited["missing"],))
    assert audited["extra"] == tuple(key for key in s.METRIC_KEYS
                                     if key not in world.SUMMARY_KEYS), (
        "the cells the fleet never counted are %r" % (audited["extra"],))
    assert audited["count"] == 8, (
        "an audit of the fleet's count compared %r keys: the eight both the "
        "fleet and the row can speak about" % (audited["count"],))

    reported = s.audit(events, lie)
    assert "failures" in reported["missing"], (
        "an audit reports the disagreement: %r" % (reported,))
    assert reported["count"] == audited["count"] == 8, (
        "a disagreement is still a key that was compared: %r"
        % (reported["count"],))
    assert reported["extra"] == audited["extra"], (
        "the extra cells changed with a disagreement: %r" % (reported,))

    partial = s.audit(events, {"tasks": summary["tasks"], "failures": 0})
    assert partial == (
        {"missing": ("failures",),
         "extra": tuple(key for key in s.METRIC_KEYS
                        if key not in ("tasks", "failures")),
         "count": 2}), (
        "an audit of a two-key count is %r: one key agreed, one did not, and the "
        "rest of the row was never counted by this fleet" % (partial,))
    with_state = dict(summary, in_flight=0)
    assert s.audit(events, with_state) == {
        "missing": ("admissions", "died", "first_tick", "last_tick", "in_flight"),
        "extra": tuple(key for key in s.METRIC_KEYS if key not in with_state),
        "count": 8}, (
        "an audit of a count carrying `in_flight` is %r: the state is never "
        "compared, and it is one of the keys the row does not explain"
        % (s.audit(events, with_state),))
    assert s.audit(events, {}) == {"missing": (), "extra": tuple(s.METRIC_KEYS),
                                   "count": 0}, (
        "an audit of an empty count is %r: nothing compared, and every cell of "
        "the row uncounted" % (s.audit(events, {}),))
    message = _refuses(s.ReportError, "an audit of a summary that is not a mapping",
                       lambda: s.audit(events, 12))
    assert "int" in message, (
        "an audit of a count that is not a mapping is not refused by its shape: "
        "%r" % (message,))

    untouched = dict(summary)
    s.report(events, untouched)
    s.audit(events, untouched)
    assert untouched == summary, (
        "a report rewrote the fleet's own count: %r" % (untouched,))
    assert lie == dict(summary, failures=summary["failures"] + 1), (
        "a refused report rewrote the fleet's own count: %r" % (lie,))

    # ---- the arguments a report refuses -----------------------------------

    message = _refuses(s.ReportError, "a window with no width",
                       lambda: s.metrics(events, start=5, end=5))
    assert "point" in message and "5" in message, (
        "a window with no width is not refused as a point: %r" % (message,))
    message = _refuses(s.ReportError, "a window that runs backwards",
                       lambda: s.metrics(events, start=9, end=5))
    assert "point" in message, (
        "a window that runs backwards is not refused: %r" % (message,))
    message = _refuses(s.ReportError, "a negative start",
                       lambda: s.metrics(events, start=-1))
    assert "start" in message and "-1" in message, (
        "a negative start is not refused by name: %r" % (message,))
    message = _refuses(s.ReportError, "a start handed over as a name",
                       lambda: s.metrics(events, start="0"))
    assert "start" in message and "str" in message, (
        "a start that is not an int is not refused by name and shape: %r"
        % (message,))
    message = _refuses(s.ReportError, "an end that is a float",
                       lambda: s.metrics(events, start=0, end=1.5))
    assert "end" in message and "float" in message, (
        "an end that is not an int is not refused by name and shape: %r"
        % (message,))
    message = _refuses(s.ReportError, "an end that is a bool",
                       lambda: s.metrics(events, start=0, end=True))
    assert "end" in message and "bool" in message, (
        "a bool bound is accepted as a tick: %r" % (message,))
    message = _refuses(s.ReportError, "a run handed over as a line",
                       lambda: s.metrics(run["text"][0]))
    assert "str" in message, (
        "a str handed over as a run is walked as characters: %r" % (message,))
    message = _refuses(s.ReportError, "a run that is not a sequence",
                       lambda: s.metrics(42))
    assert "int" in message, (
        "a run that is not a sequence is not refused by shape: %r" % (message,))
    message = _refuses(s.ReportError, "a run of things that are not records",
                       lambda: s.metrics([42]))
    assert "0" in message and "42" in message, (
        "an event that is not a record is not refused by its index: %r"
        % (message,))
    message = _refuses(s.ReportError, "an event with no tick",
                       lambda: s.metrics([{"task": "alpha", "kind": "admitted"}]))
    assert "0" in message and "tick" in message, (
        "an event with no tick is not refused by its index and its field: %r"
        % (message,))
    message = _refuses(s.ReportError, "an event whose tick is not one",
                       lambda: s.metrics([{"task": "alpha", "kind": "admitted",
                                           "tick": "-"}]))
    assert "tick" in message and "str" in message, (
        "an event whose tick is not an int is not refused by name: %r"
        % (message,))
    assert _refuses(s.ReportError, "an audit of a window with no width",
                    lambda: s.audit(events, summary, start=5, end=5)), (
        "an audit folds the window like a report, so it refuses a point too")

    assert kept_events == tuple(dict(event) for event in events), (
        "the run moved under the report: %r" % (events[:1],))
    assert isinstance(row, Mapping), (
        "a row is %r: a mapping a caller may read by cell name"
        % (type(row).__name__,))

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    COURSE = "agent-metrics-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("J5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J5_REPO=/path/to/learn-stuff-from-scratch")

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

    def _attempts(events):
        """`(wait + service, the tick it finished at)` for every finished attempt.

        Matched by `(task, attempt)` the way stage 5 matches them, but written here
        so that the two readers can disagree.
        """
        started = {(event["task"], event["attempt"]): event["wait"]
                   for event in events if event["kind"] == "started"}
        found = []
        for event in events:
            if event["kind"] == "finished":
                found.append((started[(event["task"], event["attempt"])]
                              + event["service"], event["tick"]))
        return tuple(found)

    def _latency_in(events, start, end):
        """The latencies of the attempts the check says finished in `[start, end)`."""
        return tuple(latency for latency, tick in _attempts(events)
                     if start <= tick < end)

    def _nearest(values, numerator, denominator):
        """The nearest-rank quantile by hand: `ceil(n * num / den) - 1`, clamped."""
        ordered = sorted(values)
        index = (len(ordered) * numerator + denominator - 1) // denominator - 1
        return ordered[max(0, index)]

    def _p95(events, spec):
        """A window's 95th percentile, as the report answers it: zero unmeasured."""
        values = _latency_in(events, spec["start"], spec["end"])
        return _nearest(values, 95, 100) if values else 0

    def _failure_bp(events, spec):
        """A window's failure rate in floored basis points, counted by the check."""
        chosen = [event for event in events
                  if spec["start"] <= event["tick"] < spec["end"]]
        attempts = sum(1 for event in chosen if event["kind"] == "finished")
        failures = sum(1 for event in chosen if event["kind"] == "finished"
                       and event["outcome"] != "ok")
        return 0 if attempts == 0 else failures * 10000 // attempts

    def _spent(events, start, end, price):
        """The window's micros, priced by the check from the price it was handed."""
        total = 0
        for event in events:
            if event["kind"] == "finished" and start <= event["tick"] < end:
                total += (event["tokens_in"] * price["in"]
                          + event["tokens_out"] * price["out"])
        return total

    def _flight(events, tick):
        """How many tasks are in flight at `tick`: the check's own count of them.

        A task is in flight from the tick it is admitted to the tick it leaves for
        good — a finish no retry follows, or a drop of a task that was in the queue
        to be dropped. Written the slow, obvious way on purpose: two readers of the
        same rule is the only way to check one of them.
        """
        again = {(event["task"], event["attempt"]) for event in events
                 if event["kind"] == "retried"}
        admitted = {event["task"] for event in events
                    if event["kind"] == "admitted"}
        live = set()
        for event in events:
            if event["tick"] > tick:
                continue
            if event["kind"] == "admitted":
                live.add(event["task"])
            elif event["kind"] == "finished" \
                    and (event["task"], event["attempt"]) not in again:
                live.discard(event["task"])
            elif event["kind"] == "dropped" and event["task"] in admitted:
                live.discard(event["task"])
        return len(live)

    def _peak_flight(events, start, end):
        """The first tick of `[start, end)` where the check's own count is deepest."""
        best_tick, best_depth = start, 0
        for tick in range(start, end):
            depth = _flight(events, tick)
            if depth > best_depth:
                best_tick, best_depth = tick, depth
        return (best_tick, best_depth)

    def _reduced(numerator, denominator):
        """A ratio as an exact reduced pair, reduced by the check's own gcd."""
        first, second = numerator, denominator
        while second:
            first, second = second, first % second
        return (numerator // first, denominator // first)

    from collections.abc import Mapping, Sequence

    import stage_01
    import stage_08
    import stage_09 as s9
    import stage_10 as s

    import telemetry as world

    # ---- the shape this stage freezes -------------------------------------

    assert s.SLO_KEYS == ("metric", "target", "window", "budget"), (
        "SLO_KEYS is %r: an objective is the metric the promise is about, the "
        "target the metric has to stay inside, the window fixture it is measured "
        "over and the budget the overshoots are spent from, in that order"
        % (s.SLO_KEYS,))
    assert isinstance(s.SLO_KEYS, Sequence) and not isinstance(s.SLO_KEYS, str), (
        "SLO_KEYS is %r: an objective's keys are a tuple, not something a caller "
        "may append to" % (type(s.SLO_KEYS).__name__,))
    assert len(set(s.SLO_KEYS)) == 4, (
        "SLO_KEYS names %d keys: four, no repeats" % (len(set(s.SLO_KEYS)),))
    assert issubclass(s.SloError, stage_01.TelemetryError), (
        "%r is not a %s: one `except TelemetryError` must still catch a broken "
        "objective" % (s.SloError, stage_01.TelemetryError.__name__))
    assert issubclass(s.SloError, ValueError), (
        "%r is not a ValueError: every refusal in this course is a verdict on a "
        "value" % (s.SloError,))

    # ---- a ledger and four windows whose every cell can be argued by hand --
    #
    # Four tasks, none of them retried twice: `a` is admitted, started and done
    # at tick 2 on one attempt, so its window's only measurement is a latency of
    # 2; `d` is started at 4 and finishes at 6, so its attempt *crosses* the
    # boundary at 5 and the window that holds its finish cut its start off; `b`
    # runs from 5 to 9; `e` starts at 9 and finishes at 10, exactly on the
    # boundary, so it is the window that *ends* there that must not hold it; `r`
    # fails at 12 and is retried, so it is still in flight after that; `q` is
    # admitted at 13 and never runs; and `s` finishes at 19, exactly at the third
    # window's target. The depth at each tick is the four counters of those tasks
    # read as one state machine.

    def record(**fields):
        return world.event(pool="small", tenant="batch", **fields)

    ledger = (
        record(tick=0, task="a", kind="admitted", attempt=1),
        record(tick=0, task="a", kind="started", attempt=1, wait=0),
        record(tick=2, task="a", kind="finished", attempt=1, outcome="ok",
               service=2, tokens_in=10, tokens_out=4),
        record(tick=4, task="d", kind="admitted", attempt=1),
        record(tick=4, task="d", kind="started", attempt=1, wait=0),
        record(tick=5, task="b", kind="admitted", attempt=1),
        record(tick=5, task="b", kind="started", attempt=1, wait=0),
        record(tick=6, task="d", kind="finished", attempt=1, outcome="ok",
               service=2, tokens_in=3, tokens_out=3),
        record(tick=9, task="b", kind="finished", attempt=1, outcome="ok",
               service=4, tokens_in=5, tokens_out=2),
        record(tick=9, task="e", kind="admitted", attempt=1),
        record(tick=9, task="e", kind="started", attempt=1, wait=0),
        record(tick=10, task="e", kind="finished", attempt=1, outcome="ok",
               service=1, tokens_in=1, tokens_out=1),
        record(tick=10, task="r", kind="admitted", attempt=1),
        record(tick=10, task="r", kind="started", attempt=1, wait=0),
        record(tick=12, task="r", kind="finished", attempt=1, outcome="failed",
               service=7, tokens_in=2, tokens_out=1, error="failed"),
        record(tick=12, task="r", kind="retried", attempt=1, error="failed"),
        record(tick=13, task="q", kind="admitted", attempt=1),
        record(tick=16, task="s", kind="admitted", attempt=1),
        record(tick=16, task="s", kind="started", attempt=1, wait=0),
        record(tick=19, task="s", kind="finished", attempt=1, outcome="ok",
               service=3, tokens_in=1, tokens_out=1),
    )
    kept_ledger = tuple(dict(event) for event in ledger)

    four = stage_08.windows(0, 20, 5)
    kept_four = tuple(dict(spec) for spec in four)
    assert tuple(spec["start"] for spec in four) == (0, 5, 10, 15), (
        "the window set under this check is %r: four tumbling windows of five "
        "ticks" % (four,))

    # ---- budget: what each window measured, and what it spent -------------

    slo = {"metric": "p95", "target": 3, "window": "minute", "budget": 4}
    spent = s.budget(ledger, slo, windows_=four)

    assert tuple(spent) == ("allowed", "spent", "folds", "breaches"), (
        "a budget answers %r: the objective's allowance, the sum of the "
        "overshoots, one fold per window and the windows that breached, in that "
        "order" % (list(spent),))
    assert isinstance(spent["folds"], tuple) and isinstance(spent["breaches"],
                                                            tuple), (
        "the folds and the breaches come back as %r and %r: a caller may not "
        "append a window to either"
        % (type(spent["folds"]).__name__, type(spent["breaches"]).__name__))
    assert spent["allowed"] == 4, (
        "the allowance is %r: the objective's budget, in the metric's own unit"
        % (spent["allowed"],))
    assert spent["spent"] == 5, (
        "the spend is %r: the windows that came in above 3 overshot it by 1 and "
        "by 4, and the size of an overshoot is what a budget in the metric's own "
        "unit measures — the number of bad windows is not" % (spent["spent"],))
    assert len(spent["folds"]) == 4, (
        "the budget folded %d windows: every window of the set is folded, "
        "whatever its metric came out at, so a caller can see the whole series"
        % (len(spent["folds"]),))
    for index, fold in enumerate(spent["folds"]):
        assert tuple(fold) == tuple(stage_08.FOLD_KEYS) + ("p95",), (
            "fold %d is %r: stage 8's six keys with the objective's metric "
            "appended, so a window and the promise it is judged against are one "
            "mapping" % (index, list(fold)))
    assert spent["folds"][0]["start"] == 0 and spent["folds"][0]["end"] == 5, (
        "the first fold is %r: the window the set handed over, at its own bounds"
        % (spent["folds"][0],))
    assert spent["folds"][0]["events"] == ledger[:5], (
        "the window [0, 5) holds %r: the events at tick 0 and 4 of the ledger, in "
        "the order they happened" % (spent["folds"][0]["events"],))
    assert (spent["folds"][0]["count"], spent["folds"][0]["total"]) == (5, 2), (
        "the first fold counts %r and totals %r: five events, and the two ticks "
        "of service that `a` spent finishing inside it"
        % (spent["folds"][0]["count"], spent["folds"][0]["total"]))
    assert spent["folds"][0]["peak_depth"] == {"tick": 0, "depth": 1}, (
        "the first window's peak is %r: `a` is admitted at the window's first "
        "tick, so that tick is the first to attain a depth of one"
        % (spent["folds"][0]["peak_depth"],))

    middle = spent["folds"][1]
    assert tuple(event["tick"] for event in middle["events"]) == (5, 5, 6, 9, 9, 9), (
        "the window [5, 10) holds the events at %r: the events at `tick == 5` are "
        "in and `e`'s finish at `tick == 10` — the window's own end — is out, "
        "which is the boundary stages 2 and 8 froze"
        % (tuple(event["tick"] for event in middle["events"]),))
    assert middle["peak_depth"] == {"tick": 5, "depth": 2}, (
        "the window [5, 10) peaks at %r: `b` is admitted at its first tick "
        "although `d` is still running, and `d` finishes at 6"
        % (middle["peak_depth"],))
    assert spent["folds"][2]["peak_depth"] == {"tick": 13, "depth": 2}, (
        "the window [10, 15) peaks at %r: `q` is admitted at 13 while `r`, whose "
        "finish a retry follows, is still in flight"
        % (spent["folds"][2]["peak_depth"],))
    assert spent["folds"][3]["peak_depth"] == {"tick": 16, "depth": 3}, (
        "the window [15, 20) peaks at %r: the window opened on a queue that was "
        "already there and `s` joins it at 16"
        % (spent["folds"][3]["peak_depth"],))

    assert [fold["p95"] for fold in spent["folds"]] == [2, 4, 7, 3], (
        "the windows measured %r: [0, 5) holds `a`'s attempt (wait 0 + service "
        "2), [5, 10) holds `d`'s — whose `started` event is at tick 4, *outside* "
        "the window — and `b`'s (0 + 4), so the 95th percentile of (2, 4) is 4, "
        "[10, 15) holds `r`'s (0 + 7) and [15, 20) holds `s`'s (0 + 3)"
        % ([fold["p95"] for fold in spent["folds"]],))
    assert spent["breaches"] == (four[1], four[2]), (
        "the windows that breached are %r: [5, 10) came in at 4 and [10, 15) at "
        "7 against a target of 3, and the windows that stayed inside are the "
        "specs the set handed over and not a count of them"
        % (spent["breaches"],))

    empty = s.budget(ledger, dict(slo, target=3, budget=100),
                     windows_=(stage_08.windows(0, 25, 5)[4],))
    assert empty["folds"] == ({"start": 20, "end": 25, "events": (), "count": 0,
                               "total": 0, "peak_depth": {"tick": 20, "depth": 2},
                               "p95": 0},), (
        "a window that nothing happened in folds to %r: a row of zeros for what "
        "it measured — the report answers zero where the folds below it refuse — "
        "and a queue of two for a state somebody was already in"
        % (empty["folds"],))
    assert (empty["spent"], empty["breaches"]) == (0, ()), (
        "a window inside the target spent %r and breached %r: zero is not a "
        "breach and a breach is a window, never a number"
        % (empty["spent"], empty["breaches"]))

    # ---- the metric's own unit, one family at a time ----------------------

    priced = s.budget(ledger, {"metric": "micros", "target": 68,
                               "window": "minute", "budget": 1000},
                      windows_=four)
    assert [fold["micros"] for fold in priced["folds"]] == [68, 76, 30, 14], (
        "the windows spent %r micros: `a`'s 10 in and 4 out at 2 and 12 apiece is "
        "68, `d`'s 3 and 3 plus `b`'s 5 and 2 is 76 — `e` was only started inside "
        "that window and a start spends nothing — `e`'s 1 in and 1 out at 10, the "
        "boundary it finished on, plus `r`'s 2 and 1 is 30, and `s`'s 1 and 1 is 14"
        % ([fold["micros"] for fold in priced["folds"]],))
    assert tuple(priced["folds"][0]) == tuple(stage_08.FOLD_KEYS) + ("micros",), (
        "a budget on micros folds %r: the metric the objective names, not the one "
        "the stage likes best" % (list(priced["folds"][0]),))
    assert priced["spent"] == 8 and priced["breaches"] == (four[1],), (
        "a target of 68 micros is spent by %r: [0, 5) came in exactly at the "
        "target and spent nothing, and [5, 10) overshot it by 8 micros"
        % (priced["spent"],))

    graded = s.budget(ledger, {"metric": "failure_bp", "target": 0,
                               "window": "minute", "budget": 1000},
                      windows_=four)
    assert [fold["failure_bp"] for fold in graded["folds"]] == [0, 0, 5000, 0], (
        "the windows failed %r basis points: one attempt in [0, 5) and two in "
        "[5, 10) all succeeded, `e`'s attempt at 10 and `r`'s failed one at 12 "
        "make [10, 15) one in two, and [15, 20) measured nothing — no attempt is "
        "not a rate" % ([fold["failure_bp"] for fold in graded["folds"]],))
    assert graded["spent"] == 5000, (
        "a target of zero basis points is spent by %r: a rate above zero is a "
        "breach whatever it is measured in" % (graded["spent"],))

    retried = s.budget(ledger, {"metric": "retry_bp", "target": 0,
                                "window": "minute", "budget": 1000},
                       windows_=four)
    assert [fold["retry_bp"] for fold in retried["folds"]] == [0, 0, 5000, 0], (
        "the windows retried %r basis points: one retry against the two "
        "admissions of [10, 15) is 5000, and a retry rate is retries over "
        "admissions and never over attempts"
        % ([fold["retry_bp"] for fold in retried["folds"]],))

    # ---- burn: the same spend, as a share of the allowance ----------------

    share = s.burn(ledger, slo, windows_=four)
    assert tuple(share) == ("burn", "allowed", "fraction"), (
        "a burn answers %r: the spend, the allowance and the share of it that is "
        "gone, in that order" % (list(share),))
    assert share["burn"] == spent["spent"] and share["allowed"] == spent["allowed"], (
        "the burn answers %r where the budget measured %r: one walk, one spend"
        % (share, {"spent": spent["spent"], "allowed": spent["allowed"]}))
    assert share["fraction"] == _reduced(share["burn"], share["allowed"]), (
        "the share of the budget that is gone is %r, and %r over %r reduces to %r"
        % (share["fraction"], share["burn"], share["allowed"],
           _reduced(share["burn"], share["allowed"])))

    reduced = s.burn(ledger, {"metric": "p95", "target": 0, "window": "minute",
                              "budget": 8}, windows_=(four[1],))
    assert reduced == {"burn": 4, "allowed": 8, "fraction": (1, 2)}, (
        "a burn of 4 out of 8 is %r: every ratio in this course is an exact *reduced* "
        "pair, so (4, 8) is not the answer" % (reduced,))

    clean = s.burn(ledger, {"metric": "p95", "target": 100, "window": "minute",
                            "budget": 12}, windows_=four)
    assert clean == {"burn": 0, "allowed": 12, "fraction": (0, 1)}, (
        "a budget nothing was spent out of is %r: a share of nothing is 0 over 1, "
        "not 0 over 0" % (clean,))

    message = _refuses(s.SloError, "a burn of a budget nobody set",
                       lambda: s.burn(ledger, dict(slo, budget=0), windows_=four))
    assert "p95" in message and "budget" in message and "zero" in message, (
        "a budget of zero is refused by %r: the refusal names the objective it "
        "belongs to and says why a share of nothing has no answer" % (message,))

    # ---- alert: the budget, not the first breach --------------------------

    page = s.alert(ledger, dict(slo, target=2), windows_=four)
    assert tuple(page) == ("fires", "reason", "metric", "window"), (
        "an alert answers %r: whether it fires, why, the metric the promise is "
        "about and the window fixture it was measured over, in that order"
        % (list(page),))
    assert page["fires"] is True, (
        "the alert did not fire at %r: a target of 2 over those windows spends "
        "2 + 5 + 1 of an allowance of 4" % (page,))
    assert isinstance(page["reason"], str), (
        "the reason is %r: a page an operator can read is a str"
        % (type(page["reason"]).__name__,))
    assert "10" in page["reason"], (
        "the reason is %r: it names the window that spent the *last* of the "
        "budget — [10, 15), the one whose overshoot carried the total past the "
        "allowance — and not the first window that breached, which opened at 5"
        % (page["reason"],))
    assert page["metric"] == "p95" and page["window"] == "minute", (
        "the alert answers %r and %r: the metric and the fixture the objective "
        "named" % (page["metric"], page["window"]))

    even = s.alert(ledger, dict(slo, budget=5), windows_=four)
    assert even["fires"] is False and isinstance(even["reason"], str), (
        "a budget that is exactly used up answered %r: the page arrives when the "
        "spend is *greater* than the allowance, and five out of five is used up "
        "rather than exceeded" % (even,))

    quiet = s.alert(ledger, {"metric": "p95", "target": 100, "window": "minute",
                             "budget": 1}, windows_=four)
    assert quiet["fires"] is False and isinstance(quiet["reason"], str), (
        "four windows inside the target answered %r: every window inside the "
        "target fires nothing, however many of them there are" % (quiet,))

    broke = s.alert(ledger, dict(slo, target=6, budget=0), windows_=four)
    assert broke["fires"] is True and "tick 10" in broke["reason"], (
        "a budget of zero is not refused by the alert: [10, 15) is the only "
        "window above a target of 6 and it spends the last of an allowance that "
        "never existed, and the page names it: %r" % (broke,))

    quiet_alert = s.alert(ledger, {"metric": "p95", "target": 3,
                                   "window": "minute", "budget": 100},
                          windows_=())
    assert quiet_alert["fires"] is False and isinstance(quiet_alert["reason"], str), (
        "an alert over no windows at all answered %r: nothing was spent, so "
        "nothing fires, and a reason is still a str" % (quiet_alert,))
    assert s.budget(ledger, slo, windows_=()) == {"allowed": 4, "spent": 0,
                                                  "folds": (), "breaches": ()}, (
        "a budget over no windows is %r: no window breached, so nothing was spent"
        % (s.budget(ledger, slo, windows_=()),))

    # ---- the window set: a name, the specs, and what is neither -----------

    named = s.budget(ledger, slo, windows_="minute")
    fixture = world.window("minute")
    built = stage_08.windows(fixture["start"], fixture["end"], fixture["width"],
                             step=fixture["step"])
    assert named == s.budget(ledger, slo, windows_=built), (
        "a fixture's name and its own windows are two spellings of one set: %r "
        "and %r" % (named, s.budget(ledger, slo, windows_=built)))
    assert named["allowed"] == 4 and len(named["folds"]) == len(built) == 6, (
        "a budget over the minute fixture is %r: the same objective and the "
        "fixture's own six windows" % (named,))

    message = _refuses(world.EventError, "a window fixture nobody has",
                       lambda: s.budget(ledger, slo, windows_="minut"))
    assert "minut" in message, (
        "a window fixture nobody has is not refused by the world: %r" % (message,))
    message = _refuses(s.SloError, "a window set handed over as raw bytes",
                       lambda: s.budget(ledger, slo, windows_=b"minute"))
    assert "bytes" in message, (
        "raw bytes handed over as a window set are not refused by their shape: "
        "%r" % (message,))

    # ---- the objective, and the window set, this stage refuses ------------

    message = _refuses(s.SloError, "an objective that is not a mapping",
                       lambda: s.budget(ledger, ["metric", "target", "window",
                                                 "budget"], windows_=four))
    assert "list" in message, (
        "an objective that is not a mapping is not refused by its shape: %r"
        % (message,))
    message = _refuses(s.SloError, "an objective with no budget",
                       lambda: s.budget(ledger, {key: slo[key] for key in slo
                                                 if key != "budget"},
                                        windows_=four))
    assert "budget" in message, (
        "an objective with no budget is not refused by the key it is missing: %r"
        % (message,))
    message = _refuses(s.SloError, "an objective carrying a key that is not one",
                       lambda: s.budget(ledger, dict(slo, ramp=1), windows_=four))
    assert "ramp" in message, (
        "an objective carrying a key that is not one of the four is not refused "
        "by that key: %r" % (message,))
    message = _refuses(s.SloError, "a misspelled key",
                       lambda: s.budget(ledger, {"metric": "p95", "target": 3,
                                                 "window": "minute",
                                                 "budgett": 4}, windows_=four))
    assert "did you mean" in message and "budget" in message, (
        "a key within reach of a real one earns the world's suggestion: %r"
        % (message,))
    message = _refuses(s.SloError, "a metric no target can be denominated in",
                       lambda: s.budget(ledger, dict(slo, metric="p90"),
                                        windows_=four))
    assert "p90" in message and "p95" in message and "did you mean" in message, (
        "a metric no target can be denominated in is not refused by name with "
        "the metrics that would have worked and the world's suggestion: %r"
        % (message,))
    message = _refuses(s.SloError, "a metric that is not a name at all",
                       lambda: s.budget(ledger, dict(slo, metric=7),
                                        windows_=four))
    assert "7" in message, (
        "a metric that is not a name is not refused by what it is: %r"
        % (message,))
    message = _refuses(s.SloError, "a target handed over as a name",
                       lambda: s.alert(ledger, dict(slo, target="3"),
                                       windows_=four))
    assert "target" in message and "str" in message, (
        "a target that is not an int is not refused by name and shape: %r"
        % (message,))
    message = _refuses(s.SloError, "a target that is a float",
                       lambda: s.budget(ledger, dict(slo, target=3.5),
                                        windows_=four))
    assert "target" in message and "float" in message, (
        "a float target is accepted: every number in this course is an int count "
        "— %r" % (message,))
    message = _refuses(s.SloError, "a target that is a bool",
                       lambda: s.budget(ledger, dict(slo, target=True),
                                        windows_=four))
    assert "target" in message and "bool" in message, (
        "a bool is accepted as a target, so `True` is a target of one: %r"
        % (message,))
    message = _refuses(s.SloError, "a budget that is negative",
                       lambda: s.burn(ledger, dict(slo, budget=-2), windows_=four))
    assert "budget" in message and "-2" in message, (
        "a negative budget is not refused by name: %r" % (message,))
    message = _refuses(s.SloError, "a window fixture with no name",
                       lambda: s.budget(ledger, dict(slo, window=""),
                                        windows_=four))
    assert "window" in message, (
        "a window fixture with an empty name is not refused by name: %r"
        % (message,))
    message = _refuses(s.SloError, "a window fixture named with a space in it",
                       lambda: s.budget(ledger, dict(slo, window="two words"),
                                        windows_=four))
    assert "window" in message, (
        "a window fixture whose name carries a space is not refused: %r"
        % (message,))
    message = _refuses(s.SloError, "a window fixture named by a number",
                       lambda: s.alert(ledger, dict(slo, window=7),
                                       windows_=four))
    assert "window" in message, (
        "a window fixture named by a number is not refused by name: %r"
        % (message,))
    message = _refuses(s.SloError, "a window set that is not a sequence",
                       lambda: s.budget(ledger, slo, windows_=7))
    assert "int" in message, (
        "a window set that is not a sequence is not refused by its shape: %r"
        % (message,))
    message = _refuses(s.SloError, "a window that is not a spec",
                       lambda: s.budget(ledger, slo, windows_=(7,)))
    assert "0" in message and "7" in message, (
        "a spec that is not a mapping is not refused by its index: %r"
        % (message,))
    message = _refuses(stage_01.TelemetryError, "a window with no width",
                       lambda: s.budget(ledger, slo,
                                        windows_=({"start": 5, "end": 5,
                                                   "width": 5, "step": 5},)))
    assert "point" in message and "5" in message, (
        "a window with no width is not refused as a point: %r" % (message,))
    message = _refuses(stage_01.TelemetryError, "a run handed over as a line",
                       lambda: s.budget("0 a small batch admitted 1", slo,
                                        windows_=four))
    assert "str" in message, (
        "a str handed over as a run is walked as characters: %r" % (message,))

    assert four == kept_four, (
        "the budget rewrote the windows it was handed: %r" % (four,))
    assert ledger == kept_ledger, (
        "the events have moved: a fold reads its input and never rewrites it")

    # ---- run: the whole pipeline, and the two properties it must have -----

    fixture_state = (dict(world.WINDOWS["minute"]), dict(world.WINDOWS["rolling"]),
                     dict(world.SLOS["latency_p95"]),
                     dict(world.SLOS["failure_rate"]))
    objective = world.slo("latency_p95")

    one = s.run()
    two = s.run()
    assert tuple(one) == ("events", "summary", "windows", "folds", "report",
                          "budget", "burn", "alert", "clock"), (
        "a run answers %r: the events, the fleet's own count, the fixture's "
        "windows, one fold per window, the report, the budget, the burn, the "
        "alert and the clock, in the contract's order" % (list(one),))
    assert isinstance(one["events"], tuple) and isinstance(one["windows"], tuple) \
        and isinstance(one["folds"], tuple), (
        "a run hands back %r for its events, %r for its windows and %r for its "
        "folds: tuples a caller may keep"
        % (type(one["events"]).__name__, type(one["windows"]).__name__,
           type(one["folds"]).__name__))
    assert one == two, (
        "two runs of the same fleet are %r and %r: a run is a pure function of "
        "the fleet and the fixtures, or a dashboard nobody may compare"
        % (one, two))
    assert one["events"] is not two["events"] \
        and one["folds"][0] is not two["folds"][0], (
        "two runs handed back the same objects: a run shares nothing with the "
        "run before it")

    minute = world.window("minute")
    expected_windows = stage_08.windows(minute["start"], minute["end"],
                                        minute["width"], step=minute["step"])
    assert tuple(one["windows"]) == expected_windows, (
        "the run's windows are %r, not the objective's own fixture's windows %r"
        % (one["windows"], expected_windows))
    assert len(one["folds"]) == len(one["windows"]) == 6, (
        "the run folded %d of its %d windows"
        % (len(one["folds"]), len(one["windows"])))
    for fold in one["folds"]:
        assert tuple(fold) == tuple(stage_08.FOLD_KEYS), (
            "a run's fold is %r: the six keys stage 8 defined, and not the "
            "objective's metric tacked on — the metric is what the budget's own "
            "folds carry" % (list(fold),))

    measured = [_p95(one["events"], spec) for spec in one["windows"]]
    for fold, graded_fold in zip(one["folds"], one["budget"]["folds"]):
        assert tuple(graded_fold) == tuple(stage_08.FOLD_KEYS) \
            + (objective["metric"],) \
            and all(fold[key] == graded_fold[key] for key in stage_08.FOLD_KEYS), (
            "the run's fold %r and the budget's fold %r are not the same fold "
            "with the metric included: %r"
            % (fold, graded_fold, (fold, graded_fold)))
    assert [fold["p95"] for fold in one["budget"]["folds"]] == measured, (
        "the run's windows measured %r and this check's own nearest rank over "
        "the attempts that finished in them says %r"
        % ([fold["p95"] for fold in one["budget"]["folds"]], measured))
    assert len(measured) == len(one["folds"]) and all(
        value in _latency_in(one["events"], spec["start"], spec["end"])
        for value, spec in zip(measured, one["windows"]) if value), (
        "a window's metric is a sample that happened: %r" % (measured,))

    for fold, spec in zip(one["folds"], one["windows"]):
        assert (fold["start"], fold["end"]) == (spec["start"], spec["end"]), (
            "a fold is %r for the window %r: the fold is over the spec the set "
            "handed over" % (fold, spec))
        assert (fold["peak_depth"]["tick"], fold["peak_depth"]["depth"]) \
            == _peak_flight(one["events"], spec["start"], spec["end"]), (
            "the window %r peaked at %r and this check's own count of what is in "
            "flight makes it %r"
            % (spec, fold["peak_depth"],
               _peak_flight(one["events"], spec["start"], spec["end"])))

    assert one["budget"]["allowed"] == objective["budget"] == 12, (
        "the run's allowance is %r: the fixture's own budget of 12 ticks"
        % (one["budget"]["allowed"],))
    assert one["budget"]["spent"] == sum(max(0, value - objective["target"])
                                         for value in measured), (
        "the run spent %r: the sum of the overshoots of the windows above %d, "
        "each one in the metric's own unit"
        % (one["budget"]["spent"], objective["target"]))
    assert one["budget"]["breaches"] == tuple(
        spec for spec, value in zip(one["windows"], measured)
        if value > objective["target"]), (
        "the run's breaches are %r: the windows the check's own reading puts "
        "above the target, in order" % (one["budget"]["breaches"],))

    running = 0
    crossing = None
    for spec, value in zip(one["windows"], measured):
        if value <= objective["target"]:
            continue
        running += value - objective["target"]
        if crossing is None and running > objective["budget"]:
            crossing = spec["start"]
    assert one["budget"]["spent"] > one["budget"]["allowed"], (
        "the default run's own fixture spends %r of %r: a check that cannot see "
        "a page cannot see the silence either"
        % (one["budget"]["spent"], one["budget"]["allowed"]))
    assert one["alert"]["fires"] is True and str(crossing) in one["alert"]["reason"], (
        "the run's alert is %r: it fires because the spend is above the budget, "
        "and the reason names the window whose overshoot crossed it, the one that "
        "opened at %r" % (one["alert"], crossing))
    assert one["alert"]["metric"] == objective["metric"] == "p95" \
        and one["alert"]["window"] == objective["window"] == "minute", (
        "the run's alert answers %r: the metric and the fixture the objective "
        "named" % (one["alert"],))

    assert one["burn"]["burn"] == one["budget"]["spent"] \
        and one["burn"]["allowed"] == one["budget"]["allowed"], (
        "the run's burn is %r where its budget measured %r: one walk, one spend"
        % (one["burn"], one["budget"]))
    assert one["burn"]["fraction"] == _reduced(one["burn"]["burn"],
                                               one["burn"]["allowed"]), (
        "the run's share of its budget is %r, and %r over %r reduces to %r"
        % (one["burn"]["fraction"], one["burn"]["burn"], one["burn"]["allowed"],
           _reduced(one["burn"]["burn"], one["burn"]["allowed"])))

    assert tuple(one["report"]) == tuple(s9.METRIC_KEYS), (
        "the run's report is %r: the eighteen cells of stage 9's row, not the "
        "fleet's own count handed back" % (list(one["report"]),))
    for key in world.SUMMARY_KEYS:
        if key in s9.METRIC_KEYS:
            assert one["report"][key] == one["summary"][key], (
                "the run's report holds %s = %r and the fleet counted %r: the "
                "report of the whole run is the proof that the fold lost nothing"
                % (key, one["report"][key], one["summary"][key]))

    assert one["clock"] == one["summary"]["last_tick"], (
        "the default run stopped at %r and its last event happened at %r"
        % (one["clock"], one["summary"]["last_tick"]))
    short = s.run(max_ticks=1)
    assert short["clock"] == 1 and short["summary"]["last_tick"] == 0, (
        "a run cut off after one tick answers clock %r with its last event at "
        "tick %r: the clock is the tick the fleet stopped at, not the tick of the "
        "last event it wrote" % (short["clock"], short["summary"]["last_tick"]))
    assert tuple(short["folds"][0]) == tuple(stage_08.FOLD_KEYS) \
        and tuple(short["budget"]["folds"][0]) \
        == tuple(stage_08.FOLD_KEYS) + ("p95",), (
        "a run that finished nothing still folds its windows: %r"
        % (short["folds"][:1],))

    # ---- the run honors every one of its arguments ------------------------

    rolling = s.run(windows_="rolling")
    rolling_fixture = world.window("rolling")
    assert tuple(rolling["windows"]) == stage_08.windows(
        rolling_fixture["start"], rolling_fixture["end"],
        rolling_fixture["width"], step=rolling_fixture["step"]), (
        "a run over the rolling fixture answers %r: the fixture the caller named, "
        "width and step and all" % (rolling["windows"],))
    assert rolling["windows"][0]["width"] == 40, (
        "the rolling fixture's windows are %r: a sliding set of width 40, which "
        "is not the objective's own tumbling one" % (rolling["windows"][:1],))
    assert one["windows"][0]["width"] == 20, (
        "the default run's windows are %r: the objective's own fixture"
        % (one["windows"][:1],))

    failing = s.run(slo="failure_rate")
    rate = world.slo("failure_rate")
    assert failing["alert"]["metric"] == rate["metric"] == "failure_bp", (
        "an objective on the failure rate answers %r: the metric the fixture "
        "names, not the one the stage likes best" % (failing["alert"]["metric"],))
    assert failing["alert"]["window"] == rate["window"] == "minute", (
        "an objective on the failure rate measures over %r"
        % (failing["alert"]["window"],))
    assert failing["budget"]["allowed"] == rate["budget"] == 200, (
        "the failure rate's budget is %r basis points: the fixture's own"
        % (failing["budget"]["allowed"],))
    for fold in failing["budget"]["folds"]:
        assert tuple(fold) == tuple(stage_08.FOLD_KEYS) + ("failure_bp",), (
            "a fold under the failure rate objective is %r" % (list(fold),))
    assert [fold["failure_bp"] for fold in failing["budget"]["folds"]] == [
        _failure_bp(failing["events"], spec) for spec in failing["windows"]], (
        "the failure rate's windows measured %r and this check's own count says "
        "%r" % ([fold["failure_bp"] for fold in failing["budget"]["folds"]],
                [_failure_bp(failing["events"], spec)
                 for spec in failing["windows"]]))

    money = s.budget(one["events"], {"metric": "micros", "target": 0,
                                     "window": "minute", "budget": 1000},
                     windows_=one["windows"])
    assert [fold["micros"] for fold in money["folds"]] == [
        _spent(one["events"], spec["start"], spec["end"], world.PRICES["small"])
        for spec in one["windows"]], (
        "the run's windows spent %r micros and the world's own price table makes "
        "them %r"
        % ([fold["micros"] for fold in money["folds"]],
           [_spent(one["events"], spec["start"], spec["end"],
                   world.PRICES["small"]) for spec in one["windows"]]))
    assert sum(fold["micros"] for fold in money["folds"]) \
        == one["summary"]["micros"] == money["spent"], (
        "the run's windows add up to %r micros and the fleet counted %r: a "
        "tumbling set partitions the run's spend exactly"
        % (sum(fold["micros"] for fold in money["folds"]), one["summary"]["micros"]))

    reliable = s.run(worker="reliable")
    assert reliable["summary"]["retries"] == 0 < one["summary"]["retries"], (
        "a reliable fleet and a flaky one answered the same run — %r against %r: "
        "the worker plan is an argument of the run and not a default"
        % (reliable["summary"], one["summary"]))

    single = s.run(tasks=("render",), worker="reliable", max_ticks=10)
    tokens = world.tokens("render")
    price = world.PRICES["small"]
    assert single["summary"]["tasks"] == 1, (
        "a run with one task in it admitted %r: the workload is an argument of "
        "the run" % (single["summary"]["tasks"],))
    assert single["summary"]["micros"] == (tokens["in"] * price["in"]
                                          + tokens["out"] * price["out"]), (
        "one call to `render` cost %r micros and the world's own prices make it "
        "%r" % (single["summary"]["micros"],
                tokens["in"] * price["in"] + tokens["out"] * price["out"]))
    wide = s.run(pool="wide", tasks=("render",), worker="reliable", max_ticks=10)
    wide_price = world.PRICES["wide"]
    assert wide["summary"]["micros"] == (tokens["in"] * wide_price["in"]
                                         + tokens["out"] * wide_price["out"]), (
        "one call to `render` on the wide pool cost %r and its own prices make it "
        "%r: a price is a property of the pool" % (wide["summary"]["micros"],
                tokens["in"] * wide_price["in"] + tokens["out"] * wide_price["out"]))

    message = _refuses(world.EventError, "an objective fixture nobody has",
                       lambda: s.run(slo="latency_p95x"))
    assert "latency_p95x" in message, (
        "a typo in an objective's name is not the world's refusal: %r"
        % (message,))
    message = _refuses(world.EventError, "a window fixture nobody has",
                       lambda: s.run(windows_="minuteX"))
    assert "minuteX" in message, (
        "a typo in a window fixture's name is not the world's refusal: %r"
        % (message,))

    assert (dict(world.WINDOWS["minute"]), dict(world.WINDOWS["rolling"]),
            dict(world.SLOS["latency_p95"]),
            dict(world.SLOS["failure_rate"])) == fixture_state, (
        "a run rewrote one of the world's own fixtures: %r"
        % ([dict(world.WINDOWS["minute"]), dict(world.SLOS["latency_p95"])],))
    assert isinstance(one, Mapping) and isinstance(one["budget"], Mapping), (
        "a run is %r: a mapping a caller may read by name"
        % (type(one).__name__,))

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The event, and the fact it records",
        tags=["events", "schema"],
        action="Write `TelemetryError`, `EventError`, `EVENT_KEYS`, `KINDS`, "
               "`ABSENT`, `CARRIES`, `REQUIRED`, `carries`, `parse_event`, "
               "`write_event` and `read_events` in stage_01.py.",
        predict="Which fields a `finished` event carries and which of them a "
                "`started` one must not, and why an event whose kind does not "
                "carry a field has to say so instead of leaving it out.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The window, and the fold",
        tags=["window", "fold"],
        action="Write `WindowError`, `window`, `count`, `total` and `mean` in "
               "stage_02.py.",
        predict="Whether an event at exactly the window's end is in it, and what "
                "a total should answer when no event in the window carries the "
                "field being asked about.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="Queue depth is a gauge, not a counter",
        tags=["gauge", "depth"],
        action="Write `GaugeError`, `depth_at`, `depth_series`, `peak_depth` and "
               "`average_depth` in stage_03.py.",
        predict="Which two kinds of event move a queue's depth and why `retried` "
                "is not one of them, and what a depth that would go negative "
                "means about the fixture rather than about the queue.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The percentile is an index",
        tags=["percentiles", "exactness"],
        action="Write `QuantileError`, `SUMMARY_KEYS`, `quantile`, `summary` and "
               "`above` in stage_04.py.",
        predict="What `p95` of eight samples is, and whether a percentile of a "
                "window with four samples may be a number no sample ever had.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="Latency, and where the time went",
        tags=["latency", "attempts"],
        action="Write `LatencyError`, `waits`, `services`, `attempt_latency`, "
               "`task_latency` and `split` in stage_05.py.",
        predict="Why a task that failed twice and then succeeded has a latency "
                "nobody can read off a single event, and which of the waits "
                "belongs to which attempt.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="Tokens, and the cost that was summed first",
        tags=["tokens", "cost"],
        action="Write `CostError`, `tokens`, `by_pool`, `micros` and "
               "`cost_per_task` in stage_06.py.",
        predict="Where a price comes from when nobody passed one, and whether a "
                "cost per task is a sum divided by a count or the mean of a "
                "column of per-task numbers.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="Failures and retries are rates",
        tags=["rates", "denominators"],
        action="Write `RateError`, `failures`, `attempts`, `retries`, "
               "`admissions`, `rate`, `failure_rate` and `retry_rate` in "
               "stage_07.py.",
        predict="What a failure rate's denominator is, and whether a task that "
                "failed once and then succeeded counts as one failure or one "
                "failed task.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The window is the decision",
        tags=["windows", "partitions"],
        action="Write `PartitionError`, `FOLD_KEYS`, `windows`, `fold`, "
               "`partition` and `covers` in stage_08.py.",
        predict="When a set of windows partitions a run rather than merely "
                "covering it, and what a step wider than the width leaves behind.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The report, and the fleet's own count",
        tags=["report", "cross-check"],
        action="Write `ReportError`, `METRIC_KEYS`, `metrics`, `report` and "
               "`audit` in stage_09.py.",
        predict="Which numbers a report may recompute from the events and which "
                "one it must not be handed, and what a disagreement with the "
                "fleet's own count is evidence of.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The capstone: two windows, one answer",
        tags=["capstone", "run"],
        action="Write `SloError`, `SLO_KEYS`, `budget`, `burn`, `alert` and `run` "
               "in stage_10.py.",
        predict="Whether one very bad window or three slightly bad ones spends "
                "more of a budget, and what two runs of the same fleet have to "
                "agree about before a dashboard may be believed.",
        check=check_10,
    ),
]
