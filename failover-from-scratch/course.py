"""Failover From Scratch — the promotion a dead region never gets.

Ten graded stages over a world provided as data (`kv.py`, `topology.py`,
`fabric.py`, `scenarios.py`), the way the rest of this repository teaches
a mechanism: the world is data and holds the pinned truth, a stage is a
file you write, a check is what happens to it, and the fabric's own
replayed PINS table is the judge — because a failover you cannot fail
on schedule has exactly one authority, and a node's behavior is graded
by equality with it, one tick at a time.

What the course is about, in one line: *failover is a decision, never an
accident — and a decision is a majority with death notices, not a
timeout with a feeling.*

    the clock: ordering the versions, not the values
    the quorum: serve inside three or refuse entirely
    the hints: held for a peer, never served as yours
    anti-entropy: the union over ranges, never a choice
    health: a signal that is not a heartbeat
    sessions: the pinned answer is a table, not a feeling
    promotion: a majority adopted, or no epoch at all
    the redirect: a write applied exactly once
    late writes: reconcile, name the lost, price the RPO
    the drill: RTO/RPO measured, the foil run, the audit refused

The house laws hold here (`.h8-dev/CONTRACT.md` §1): standard library
only, no `float` anywhere — epochs, ticks, counters and clock entries
are ints the whole way —, no `math`, no `random`, no clock, no thread,
no socket, no wall-time ordering of anything a region can disagree on,
and a stage's job is pure state in, state out: the fabric drives the
network, the clocks and the failures, never the student.

What the course does **not** do is trust a heartbeat: the world sends
death notices on a watch channel, cuts stay SILENT, and the foil in
`naive.py` — same machine, wrong in exactly three places — runs the
same schedules so stage 10 can prove the divergences it names. Where
the lessons meet the paper (A6's hinted handoff and Merkle
anti-entropy, Dynamo's quorum arithmetic, H6's epoch fencing) lives in
the course's README — the drills are the practice half of the bargain.

    python3 codecraft/cli.py run failover-from-scratch
"""

from codecraft.api import stage

TITLE = "Failover From Scratch"
DESCRIPTION = ("A multi-region failover the whole way: a version clock "
               "that orders siblings instead of values, a quorum that "
               "serves inside a majority or refuses entirely, hinted "
               "handoff parked for unreachable peers, Merkle-style "
               "anti-entropy over ranges, a health signal built from "
               "death notices instead of heartbeats, pinned-session "
               "routing with an epoch fence, a promotion a majority "
               "adopts or no epoch at all, a redirect that never "
               "applies a write twice, an RPO that names every lost "
               "rid, and a drill that measures RTO off the answer "
               "column and pins the foil's divergence — ints and "
               "notices the whole way, silence never death.")

LEVEL = "advanced"
ORDER = 39


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "failover-from-scratch"

    STAGE = 1

    STUB_MESSAGE = "stage 1: implement compare()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "fabric.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H8_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h8_check01_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import kv, stage_01 as s1\n"
                    "try:\n"
                    "    s1.compare(kv.version('x', (('e1', 1),)),\n"
                    "               kv.version('x', (('e2', 1),)))\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "fabric.py"))
                    and os.path.isfile(os.path.join(p, "stage_01.py"))),
                   None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h8_check01_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import fabric
        import kv
        import scenarios
        import stage_01 as s1
        import topology

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        # --- the world's pins, re-read (§4)
        must("KINDS", kv.KIND_VERSION == "v" and kv.KIND_HINT == "hint")
        must("VALID_NODES sorted fleet",
             kv.VALID_NODES == ("e1", "e2", "e3", "w1", "w2", "w3"))
        must("KvError is a ValueError", issubclass(kv.KvError, ValueError))
        must("REGIONS", topology.REGIONS == ("east", "west"))
        must("NODES", topology.NODES == (("e1", "east"), ("e2", "east"),
                                         ("e3", "east"), ("w1", "west"),
                                         ("w2", "west"), ("w3", "west")))
        must("PRIMARY/INITIAL_EPOCH",
             topology.PRIMARY == "east"
             and topology.INITIAL_EPOCH == 1)
        must("independent clocks", topology.TICK_RATE == 2)
        must("LAG_BOUND", topology.LAG_BOUND == 2)
        must("nodes_of sorted",
             topology.nodes_of("east") == ("e1", "e2", "e3"))
        must("peers_of excludes self",
             topology.peers_of("e1") == ("e2", "e3"))
        must("majority is an int",
             (topology.majority(3), topology.majority(2),
              topology.majority(1)) == (2, 2, 1))
        _refuses(ValueError, "region_of refuses an unknown node",
                 lambda: topology.region_of("z9"), names=("z9",))
        must("STATE_KEYS seven",
             fabric.STATE_KEYS == ("epoch", "promoted", "applied", "store",
                                   "hints", "applied_count", "notices"))
        must("KINDS five / WATCH_KINDS two",
             fabric.KINDS == ("sync", "relay", "hint", "propose", "adopt")
             and fabric.WATCH_KINDS == ("dead", "alive"))
        must("SCENARIOS seven",
             tuple((row[0], row[1], row[3]) for row in scenarios.SCENARIOS)
             == (("ONE_NODE", "single-node", 24),
                 ("REGION_DIE", "region-death", 24),
                 ("DUAL", "dual-write", 24),
                 ("FLAP", "flapping", 24),
                 ("LAG", "lag", 24),
                 ("FAKE_DEATH", "false-death", 24),
                 ("ALL_DIE", "total-loss", 24)))
        must("PINS columns are probe and naive",
             tuple(sorted(scenarios.PINS)) == tuple(sorted(
                 row[0] for row in scenarios.SCENARIOS))
             and all(frozenset(row) == frozenset(("probe", "naive"))
                     for row in scenarios.PINS.values()))
        must("ONE_NODE probe row",
             scenarios.PINS["ONE_NODE"]["probe"]
             == {"promotes": (),
                 "answers": ((2, "alpha", 1, ("applied",)),
                             (6, "alpha", 2, ("ok", ("1",)))),
                 "dups": (), "lost": (), "rto": None, "rpo": 0})
        fact("FLAP probe rto is the refused-to-served distance",
             scenarios.PINS["FLAP"]["probe"]["rto"] == 6)
        fact("LAG probe names the lost writes",
             scenarios.PINS["LAG"]["probe"]["lost"]
             == (("alpha", 1, "p"), ("alpha", 2, "p"))
             and scenarios.PINS["LAG"]["probe"]["rpo"] == 2)
        _refuses(KeyError, "scenario refuses an unknown name",
                 lambda: scenarios.scenario("NOT_A_THING"),
                 names=("NOT_A_THING",))

        # --- the stub probe: an untouched template answers exit 2
        stub = 0
        try:
            s1.compare(kv.version("x", (("e1", 1),)),
                       kv.version("x", (("e2", 1),)))
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_01: stage 1: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("FailError is a ValueError", issubclass(s1.FailError, ValueError))
        must("VERDICTS four-way",
             s1.VERDICTS == ("before", "after", "equal", "concurrent"))

        # --- A6 Figure 3, hand-built: e1 writes, e2 writes, e1 syncs,
        # e3 writes cold. v3 strictly dominates v1 and v2; v4 belongs
        # to nobody's history.
        v1 = kv.version("a", (("e1", 1),))
        v2 = kv.version("b", (("e2", 1),))
        v3 = kv.version("ab", (("e1", 1), ("e2", 1)))
        v4 = kv.version("c", (("e3", 1),))

        # --- compare: the four-way law, every direction a witness
        must("after: v3 carries everything v1 does",
             s1.compare(v3, v1) == "after")
        must("before: mirrored", s1.compare(v1, v3) == "before")
        must("concurrent: siblings", s1.compare(v1, v2) == "concurrent")
        must("concurrent is symmetric", s1.compare(v2, v1) == "concurrent")
        must("equal: a version with itself", s1.compare(v3, v3) == "equal")
        fact("equal: same clock, different value",
             s1.compare(kv.version("ab2", (("e1", 1), ("e2", 1))),
                        v3) == "equal")
        fact("equal is not after", s1.compare(v3, v3) != "after")
        fact("bumped clock is after, not equal",
             s1.compare(kv.version("a2", kv.bump(kv.clock_of(v1), "e1")),
                        v1) == "after")

        # --- coalesce: the survivor set
        must("Figure 3: four versions, exactly two siblings",
             s1.coalesce((v1, v2, v3, v4)) == (v3, v4))
        for perm in ((v4, v1, v3, v2), tuple(reversed((v1, v2, v3, v4))),
                     (v2, v4, v1, v3)):
            fact("coalesce ignores input order %r" % (perm,),
                 s1.coalesce(perm) == (v3, v4))
        must("coalesce(()) is ()", s1.coalesce(()) == ())
        must("exact duplicates are absorbed",
             s1.coalesce((v1, v2, v3, v4, v1, v3, v1)) == (v3, v4))
        fact("equal clocks with different values both survive",
             s1.coalesce((v3, kv.version("ab2", v3[2])))
             == (v3, kv.version("ab2", v3[2]))
             or s1.coalesce((v3, kv.version("ab2", v3[2])))
             == (kv.version("ab2", v3[2]), v3))
        fact("a single version survives alone", s1.coalesce((v2,)) == (v2,))
        fact("coalesce is idempotent",
             s1.coalesce(s1.coalesce((v1, v2, v3, v4))) == (v3, v4))

        # --- dominance_table: the check's evidence, sorted by the pair
        rows = s1.dominance_table((v1[2], v2[2], v3[2], v4[2]))
        must("table has one row per unordered pair", len(rows) == 6)
        must("rows sorted by the pair",
             rows == tuple(sorted(rows, key=lambda r: (r[0], r[1]))))
        must("first and last row (clocks sort e1 < e1+e2 < e2 < e3)",
             (rows[0], rows[-1])
             == ((v1[2], v3[2], "before"),
                 (v2[2], v4[2], "concurrent")))
        fact("a shuffled caller gets the same sorted table",
             s1.dominance_table((v4[2], v2[2], v1[2], v3[2])) == rows)
        fact("the table carries the domination verdict",
             (v1[2], v3[2], "before") in rows)
        fact("two clocks answer one row",
             s1.dominance_table((v1[2], v1[2]))
             == ((v1[2], v1[2], "equal"),))

        # --- the refusal split: data is kv's, arguments are the stage's
        bad_version = ("h", "k", v1, "e1")
        bad_clock = (("e2", 1), ("e1", 1))
        unknown = ("v", "x", (("zz", 1),))
        _refuses(kv.KvError, "compare refuses malformed data",
                 lambda: s1.compare(bad_version, v1), names=())
        _refuses(kv.KvError, "compare refuses an unsorted clock",
                 lambda: s1.compare(v1, kv.version("x", bad_clock)),
                 names=())
        _refuses(kv.KvError, "coalesce refuses a node outside the fleet",
                 lambda: s1.coalesce((unknown,)), names=("zz",))
        _refuses(kv.KvError, "the table refuses a malformed clock",
                 lambda: s1.dominance_table((bad_clock, v1[2])), names=())
        _refuses(s1.FailError, "the table refuses one clock",
                 lambda: s1.dominance_table((v1[2],)), names=("1",))
        _refuses(s1.FailError, "the table refuses no clocks",
                 lambda: s1.dominance_table(()), names=("0",))
        fact("determinism", s1.coalesce((v1, v2, v3, v4))
             == s1.coalesce((v1, v2, v3, v4)))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_01: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "failover-from-scratch"

    STAGE = 2

    STUB_MESSAGE = "stage 2: implement ackable()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "fabric.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H8_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h8_check02_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_02 as s2\n"
                    "try:\n"
                    "    s2.ackable('east', ('e1', 'e2'))\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "fabric.py"))
                    and os.path.isfile(os.path.join(p, "stage_02.py"))),
                   None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h8_check02_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import fabric
        import scenarios
        import stage_01 as s1
        import stage_02 as s2
        import topology

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        # --- the world's pins, re-read (§4)
        must("PRIMARY/INITIAL_EPOCH",
             topology.PRIMARY == "east" and topology.INITIAL_EPOCH == 1)
        must("TICK_RATE/LAG_BOUND",
             topology.TICK_RATE == 2 and topology.LAG_BOUND == 2)
        must("nodes_of east/west",
             topology.nodes_of("east") == ("e1", "e2", "e3")
             and topology.nodes_of("west") == ("w1", "w2", "w3"))
        must("majority of three is two", topology.majority(3) == 2)
        must("STATE_KEYS seven", len(fabric.STATE_KEYS) == 7)
        must("SCENARIOS seven", len(scenarios.SCENARIOS) == 7)
        fact("PINS keeps probe and naive",
             all(frozenset(row) == frozenset(("probe", "naive"))
                 for row in scenarios.PINS.values()))

        # --- the stub probe: an untouched template answers exit 2
        stub = 0
        try:
            s2.ackable("east", ("e1", "e2"))
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_02: stage 2: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("FailError is stage 1's class", s2.FailError is s1.FailError)

        # --- ackable: the majority law on ints
        must("two of three is a majority",
             s2.ackable("east", ("e1", "e2")) is True)
        must("all three is a majority",
             s2.ackable("east", ("e1", "e2", "e3")) is True)
        must("one of three is not",
             s2.ackable("east", ("e2",)) is False)
        _refuses(s2.FailError, "a bad region with no ids is still refused",
                 lambda: s2.ackable("north", ()), names=("north",))
        must("nobody is not", s2.ackable("east", ()) is False)
        fact("the order of acks is irrelevant",
             s2.ackable("west", ("w3", "w1")) is True)
        _refuses(s2.FailError, "a cross-region id is refused",
                 lambda: s2.ackable("east", ("e1", "w1")), names=("w1",))
        _refuses(s2.FailError, "a duplicate ack is refused",
                 lambda: s2.ackable("east", ("e1", "e1")), names=("e1",))
        _refuses(s2.FailError, "an unknown region is refused",
                 lambda: s2.ackable("north", ("e1",)), names=("north",))
        _refuses(s2.FailError, "an unknown id is refused",
                 lambda: s2.ackable("east", ("e9",)), names=("e9",))

        # --- readable/writable: the same gate over the live set
        must("readable is ackable",
             s2.readable("west", ("w1", "w2"))
             == s2.ackable("west", ("w1", "w2")))
        must("writable is ackable",
             s2.writable("west", ("w1", "w2"))
             == s2.ackable("west", ("w1", "w2")))
        fact("a one-node region cannot serve",
             s2.readable("east", ("e1",)) is False
             and s2.writable("east", ("e2",)) is False)
        fact("both gates answer with real bools",
             s2.readable("east", ("e1", "e3")) is True
             and s2.writable("east", ()) is False)
        _refuses(s2.FailError, "readable shares ackable's refusals",
                 lambda: s2.readable("east", ("e1", "e1")), names=("e1",))

        # --- r_w_law: A6's availability rule, ints only
        must("3,2,2 intersects", s2.r_w_law(3, 2, 2) is True)
        must("3,1,2 does not", s2.r_w_law(3, 1, 2) is False)
        must("the boundary r+w==n is refused by the law",
             s2.r_w_law(3, 1, 2) == s2.r_w_law(3, 2, 1) is False)
        fact("3,3,1 intersects", s2.r_w_law(3, 3, 1) is True)
        fact("1,1,1 intersects", s2.r_w_law(1, 1, 1) is True)
        _refuses(s2.FailError, "a float quorum is a caller's mistake",
                 lambda: s2.r_w_law(3, 1.5, 2), names=("r",))
        _refuses(s2.FailError, "an empty fleet is refused",
                 lambda: s2.r_w_law(0, 0, 1), names=("0",))

        # --- healthy_count: alive AND within LAG_BOUND of the best
        must("three alive at one pace are three",
             s2.healthy_count((("e1", 5, True), ("e2", 5, True),
                               ("e3", 5, True))) == 3)
        must("the dead never count",
             s2.healthy_count((("e1", 5, True), ("e2", 5, False),
                               ("e3", 5, True))) == 2)
        must("a lagger beyond LAG_BOUND does not count",
             s2.healthy_count((("e1", 10, True), ("e2", 7, True),
                               ("e3", 10, True))) == 2)
        must("lag exactly at LAG_BOUND still counts",
             s2.healthy_count((("e1", 10, True), ("e2", 8, True))) == 2)
        fact("the dead set the bar, not their number",
             s2.healthy_count((("e1", 10, False), ("e2", 4, True),
                               ("e3", 4, True))) == 2)
        must("an empty observation counts zero", s2.healthy_count(()) == 0)
        must("all dead counts zero",
             s2.healthy_count((("e1", 3, False), ("e2", 3, False))) == 0)
        fact("a healthy two of three is a quorum",
             s2.healthy_count((("e1", 10, True), ("e2", 9, True),
                               ("e3", 4, True))) >= topology.majority(3))
        _refuses(s2.FailError, "a malformed observation is refused",
                 lambda: s2.healthy_count((("e1", 5),)), names=("e1",))
        _refuses(s2.FailError, "a negative count is refused",
                 lambda: s2.healthy_count((("e2", -1, True),)),
                 names=("e2",))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_02: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "failover-from-scratch"

    STAGE = 3

    STUB_MESSAGE = "stage 3: implement park()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "fabric.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H8_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h8_check03_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import kv, stage_03 as s3\n"
                    "try:\n"
                    "    s3.park('e1', (), kv.hint('a', kv.version('x', "
                    "(('w1', 1),)), 'w2'))\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "fabric.py"))
                    and os.path.isfile(os.path.join(p, "stage_03.py"))),
                   None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h8_check03_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import fabric
        import kv
        import scenarios
        import stage_01 as s1
        import stage_02 as s2
        import stage_03 as s3
        import topology

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        # --- the world's pins, re-read (§4)
        must("KIND_HINT shape", kv.KIND_HINT == "hint")
        fact("kv.hint is the only hint constructor that answers",
             kv.hint("a", kv.version("x", (("e1", 1),)), "w2")[0]
             == kv.KIND_HINT)
        _refuses(kv.KvError, "kv.hint refuses an off-fleet owner",
                 lambda: kv.hint("a", kv.version("x", (("e1", 1),)), "z9"),
                 names=("z9",))
        fact("DUAL pins the merged sibling answer on both sides",
             scenarios.PINS["DUAL"]["probe"]["answers"][-1]
             == (15, "w1", 10, ("ok", ("3", "5"))))
        must("relay is a legal kind", "relay" in fabric.KINDS)
        must("STATE_KEYS seven", len(fabric.STATE_KEYS) == 7)
        must("LAG_BOUND/TICK_RATE",
             topology.LAG_BOUND == 2 and topology.TICK_RATE == 2)
        must("east/west rosters",
             topology.nodes_of("east") == ("e1", "e2", "e3")
             and topology.nodes_of("west") == ("w1", "w2", "w3"))

        # --- the stub probe: an untouched template answers exit 2
        stub = 0
        try:
            s3.park("e1", (), kv.hint("a", kv.version("x", (("w1", 1),)),
                                      "w2"))
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_03: stage 3: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("FailError is stage 1's class", s3.FailError is s1.FailError)

        v_w = kv.version("1", (("w1", 1),))
        h = kv.hint("a", v_w, "w2")
        h2 = kv.hint("b", kv.version("2", (("w2", 1),)), "w3")

        # --- park: cross-region only, exact duplicates absorbed
        must("a cross-region hint parks", s3.park("e1", (), h) == (h,))
        fact("a parked pile keeps pile order",
             s3.park("e1", (h,), h2) == (h, h2))
        must("the same hint twice is one hint",
             s3.park("e1", (h,), h) == (h,))
        _refuses(s3.FailError, "parking for a neighbor is refused",
                 lambda: s3.park("w1", (),
                                 kv.hint("a", v_w, "w3")),
                 names=("w1", "w3", "west"))
        _refuses(s3.FailError, "parking for oneself is refused",
                 lambda: s3.park("w1", (), kv.hint("a", v_w, "w1")),
                 names=("w1",))
        _refuses(s3.FailError, "a malformed parker is refused",
                 lambda: s3.park("z9", (), h), names=("z9",))
        _refuses(kv.KvError, "a version is not a hint",
                 lambda: s3.park("e1", (), v_w), names=())
        _refuses(kv.KvError, "a hint with a malformed version is refused",
                 lambda: s3.park("e1", (),
                                 ("hint", "a", ("v", 5, (("e1", 1),)),
                                  "w2")),
                 names=())
        _refuses(kv.KvError, "an off-fleet owner is refused",
                 lambda: s3.park("e1", (),
                                 ("hint", "a", v_w, "z9")), names=("z9",))

        # --- deliver: the relay is the fabric's own shape
        relayed, kept = s3.deliver("e1", (h, h2), ("w2",))
        must("the live owner's hint leaves the pile", kept == (h2,))
        must("the relay is fabric.message's shape with the sender at 2",
             relayed == (fabric.message("relay", "w2", "e1", "a", v_w),))
        fact("the relay routes to the owner",
             fabric.msg_target(relayed[0]) == "w2"
             and fabric.msg_kind(relayed[0]) == "relay")
        must("re-running the same live set relays the same payload",
             s3.deliver("e1", (h, h2), ("w2",)) == (relayed, (h2,)))
        fact("an empty live set keeps the whole pile in order",
             s3.deliver("e1", (h, h2), ()) == ((), (h, h2)))
        fact("both owners live drains the pile",
             s3.deliver("e1", (h, h2), ("w2", "w3"))[1] == ())
        _refuses(s3.FailError, "a malformed live id is refused",
                 lambda: s3.deliver("e1", (h,), ("z9",)), names=("z9",))
        _refuses(s3.FailError, "a malformed deliverer is refused",
                 lambda: s3.deliver("z9", (h,), ("w2",)), names=("z9",))
        _refuses(kv.KvError, "a malformed hint in the pile is refused",
                 lambda: s3.deliver("e1", (v_w,), ("w2",)), names=())

        # --- owned / served: a hint is never an owned version
        v1 = kv.version("3", (("e1", 1),))
        v2 = kv.version("5", (("w2", 1),))
        must("owned passes the node's own versions",
             s3.owned((v1, v2)) == (v1, v2))
        _refuses(kv.KvError, "a hint parked in a store is refused",
                 lambda: s3.owned((h,)), names=())
        must("served answers the owned set, sorted",
             s3.served((v2, v1), ()) == ("ok", ("3", "5")))
        must("a held hint never widens the answer",
             s3.served((v1, v2), (h, h2)) == s3.served((v1, v2), ()))
        fact("serving an empty set answers empty", s3.served((), (h,))
             == ("ok", ()))
        fact("a dominated owned version narrows, stage 1's law",
             s3.served((v1, kv.version("35", (("e1", 1), ("w2", 1)))), ())
             == ("ok", ("35",)))
        must("the temptation is real but inert: w2's hint of value 9",
             s3.served((v1,), (kv.hint("a", kv.version("9", (("w2", 2),)),
                                       "w2"),)) == ("ok", ("3",)))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_03: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import hashlib
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "failover-from-scratch"

    STAGE = 4

    STUB_MESSAGE = "stage 4: implement fingerprint()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "fabric.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H8_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _is_hex(text):
        """True iff `text` is a lowercase sha256 hex digest."""
        return (isinstance(text, str) and len(text) == 64
                and all(c in "0123456789abcdef" for c in text))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h8_check04_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_04 as s4\n"
                    "try:\n"
                    "    s4.fingerprint(())\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "fabric.py"))
                    and os.path.isfile(os.path.join(p, "stage_04.py"))),
                   None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h8_check04_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import kv
        import scenarios
        import stage_01 as s1
        import stage_02 as s2
        import stage_03 as s3
        import stage_04 as s4
        import topology

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        # --- the world's pins, re-read (§4)
        must("sha256 is a thing stdlib answers",
             hashlib.sha256(b"").hexdigest()
             == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495"
                "991b7852b855")
        must("KIND_VERSION shape", kv.KIND_VERSION == "v")
        must("east/west rosters",
             topology.nodes_of("east") == ("e1", "e2", "e3"))
        fact("DUAL pins the merged sibling answer",
             scenarios.PINS["DUAL"]["probe"]["answers"][-1]
             == (15, "w1", 10, ("ok", ("3", "5"))))

        # --- the stub probe: an untouched template answers exit 2
        stub = 0
        try:
            s4.fingerprint(())
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_04: stage 4: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("FailError is stage 1's class", s4.FailError is s1.FailError)

        va = kv.version("3", (("e1", 1),))
        vb = kv.version("5", (("w2", 1),))
        vc = kv.version("35", (("e1", 1), ("w2", 1)))

        # --- fingerprint: clocks only, sorted, hex
        fa = s4.fingerprint((va,))
        must("a fingerprint is a sha256 hex", _is_hex(fa))
        must("the same siblings in any order hash the same",
             s4.fingerprint((va, vb)) == s4.fingerprint((vb, va)))
        must("a value never enters the hash",
             s4.fingerprint((kv.version("999", (("e1", 1),)),)) == fa)
        must("the hash is over the SORTED clock reprs",
             fa == hashlib.sha256(repr(kv.clock_of(va))
                                  .encode("utf-8")).hexdigest())
        must("two siblings hash differently from one of them",
             s4.fingerprint((va, vb)) != fa)
        fact("the sibling set differs from its reconciled version — the "
             "tree sees the conflict",
             s4.fingerprint((va, vb)) != s4.fingerprint((vc,))
             and s4.fingerprint((va, vb, vc)) != s4.fingerprint((vc,)))
        must("the empty version set has a hash",
             s4.fingerprint(()) == hashlib.sha256(b"").hexdigest())
        _refuses(kv.KvError, "a clock is not a version",
                 lambda: s4.fingerprint((("v", 5, (("e1", 1),)),)),
                 names=())
        _refuses(kv.KvError, "an off-fleet clock is refused",
                 lambda: s4.fingerprint((kv.version("3", (("z9", 1),)),)),
                 names=("z9",))

        # --- ranges: the fixed partition, contiguous and covering
        must("empty keys answer four empty ranges",
             s4.ranges(()) == ((0, 0), (0, 0), (0, 0), (0, 0)))
        must("one key lands in the last slot",
             s4.ranges(("a",)) == ((0, 0), (0, 0), (0, 0), (0, 1)))
        must("three keys split 0|1|1|1",
             s4.ranges(("a", "b", "c")) == ((0, 0), (0, 1), (1, 2), (2, 3)))
        must("eight keys split 2|2|2|2",
             s4.ranges(tuple("abcdefgh"))
             == ((0, 2), (2, 4), (4, 6), (6, 8)))
        fact("key ORDER never moves a range",
             s4.ranges(("m", "a", "k")) == s4.ranges(("a", "k", "m")))
        for keys in ((), ("a",), ("a", "b"), tuple("abcdefgh")):
            parts = s4.ranges(keys)
            must("the ranges cover [0, n) for n=%d" % len(keys),
                 parts[0][0] == 0 and parts[-1][1] == len(keys)
                 and all(parts[i][1] == parts[i + 1][0]
                         for i in range(3)))
        _refuses(s4.FailError, "a non-string key is refused",
                 lambda: s4.ranges(("a", 5)), names=("5",))
        _refuses(s4.FailError, "an empty key is refused",
                 lambda: s4.ranges(("a", "")), names=())

        # --- tree_hashes: one fold per range, empties included
        store_a = {"a": (va,), "b": (vb,)}
        store_b = {"a": (vb,)}
        t_a = s4.tree_hashes(store_a)
        t_b = s4.tree_hashes(store_b)
        must("a tree is four (range, hex) pairs",
             len(t_a) == 4 and all(_is_hex(h) for _, h in t_a)
             and tuple(r for r, _ in t_a) == s4.ranges(sorted(store_a)))
        must("the empty fold is the empty hash",
             t_a[0] == ((0, 0), hashlib.sha256(b"").hexdigest()))
        must("a range's tree entry folds its keys' fingerprints",
             t_a[1] == ((0, 1), hashlib.sha256(
                 s4.fingerprint((va,)).encode("utf-8")).hexdigest())
             and t_a[3] == ((1, 2), hashlib.sha256(
                 s4.fingerprint((vb,)).encode("utf-8")).hexdigest()))
        fact("an empty store still answers four hashes",
             s4.tree_hashes({}) == tuple(((0, 0),
                                         hashlib.sha256(b"").hexdigest())
                                        for _ in range(4)))
        must("a tree never differs from itself", s4.diff(t_a, t_a) == ())
        must("two identical stores have an empty diff",
             s4.diff(t_a, s4.tree_hashes({"a": (va,), "b": (vb,)})) == ())
        must("the diff names every mismatching range",
             s4.diff(t_a, t_b) == ((0, 1), (1, 1), (1, 2)))
        must("diff is symmetric", s4.diff(t_b, t_a) == s4.diff(t_a, t_b))
        _refuses(s4.FailError, "a flat hash list is refused",
                 lambda: s4.diff((("x",),), t_b), names=())

        # --- repair: stage 1's law, pinned as an equality
        must("repair is the union's coalesce",
             s4.repair((va, vb), (vc,)) == s1.coalesce((va, vb, vc)))
        must("repair never picks a sibling away",
             s4.repair((va,), (vb,)) == (va, vb))
        must("repair drops a dominated version",
             s4.repair((va, vb), (vc,)) == (vc,))
        must("repair is idempotent", s4.repair((va,), (va,)) == (va,))
        must("empty repairs to the other side",
             s4.repair((), (va, vb)) == (va, vb))
        _refuses(kv.KvError, "a hint is not a version to repair",
                 lambda: s4.repair((va,), (kv.hint("a", va, "w2"),)),
                 names=())

        # --- the two-phase lesson, end to end
        merged = {"a": s4.repair(tuple(store_a["a"]), tuple(store_b["a"])),
                  "b": s4.repair((), tuple(store_a["b"]))}
        fact("after repairing every diffed range both trees agree",
             s4.diff(s4.tree_hashes(merged), s4.tree_hashes(merged)) == ()
             and s4.tree_hashes(merged)[3][1]
             == hashlib.sha256(s4.fingerprint((vb,))
                               .encode("utf-8")).hexdigest())

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_04: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "failover-from-scratch"

    STAGE = 5

    STUB_MESSAGE = "stage 5: implement health()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "fabric.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H8_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h8_check05_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_05 as s5\n"
                    "try:\n"
                    "    s5.health((('e1', 1, True),), ())\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "fabric.py"))
                    and os.path.isfile(os.path.join(p, "stage_05.py"))),
                   None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h8_check05_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import fabric
        import kv
        import scenarios
        import stage_01 as s1
        import stage_02 as s2
        import stage_05 as s5
        import topology

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        # --- the world's pins, re-read (§4)
        must("WATCH_KINDS are the two notices",
             fabric.WATCH_KINDS == ("dead", "alive"))
        must("majority(3) is 2", topology.majority(3) == 2)
        must("LAG_BOUND is 2", topology.LAG_BOUND == 2)
        fact("FAKE_DEATH: the naive foil promotes east — silence voting "
             "IS the heartbeat bug",
             scenarios.PINS["FAKE_DEATH"]["naive"]["promotes"]
             == ((3, "east", 2), (6, "west", 2))
             and scenarios.PINS["FAKE_DEATH"]["probe"]["promotes"] == ())
        fact("ONE_NODE pins a real death that IS a majority",
             scenarios.PINS["ONE_NODE"]["naive"]["promotes"]
             == ((3, "east", 2), (6, "west", 2)))

        # --- the stub probe: an untouched template answers exit 2
        stub = 0
        try:
            s5.health((("e1", 1, True),), ())
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_05: stage 5: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("FailError is stage 1's class", s5.FailError is s1.FailError)
        must("the verdicts are the contract's three",
             s5.VERDICTS == ("up", "suspect", "down"))

        up3 = (("e1", 4, True), ("e2", 4, True), ("e3", 4, True))
        must("a caught-up majority is up", s5.health(up3, ()) == "up")
        must("a dead minority still leaves the majority up",
             s5.health((("e1", 4, True), ("e2", 4, True),
                        ("e3", 0, False)), ()) == "up")
        must("silence never votes down",
             s5.health((), ()) == "suspect")
        must("one explicit death is a minority: suspect",
             s5.health((), (("dead", "e1"),)) == "suspect")
        must("a majority of explicit deaths is down",
             s5.health((), (("dead", "e1"), ("dead", "e2"))) == "down")

        # --- the lag law is stage 2's, through healthy_count
        must("the lag within LAG_BOUND still counts up",
             s5.health((("e1", 7, True), ("e2", 7, True),
                        ("e3", 4, True)), ()) == "up")
        must("a lagger is not alive-voted: suspect",
             s5.health((("e1", 7, True), ("e2", 0, False),
                        ("e3", 4, True)), ()) == "suspect")
        must("a retracted claim restores the region to up",
             s5.health(up3, (("dead", "e1"), ("alive", "e1"))) == "up")
        fact("lag-into-healthy_count: alive votes that fail the bound "
             "never read up",
             s5.health((("e1", 7, True), ("e2", 4, True),
                        ("e3", 4, True)), ()) == "suspect")

        # --- retraction: arrival order, no clock arithmetic
        must("alive retracts the same-tick claim",
             s5.health((), (("dead", "e1"), ("alive", "e1"),
                            ("dead", "e2"))) == "suspect")
        must("a retraction cannot resurrect a second claim",
             s5.health((), (("alive", "e1"), ("dead", "e1"),
                            ("dead", "e2"))) == "down")
        must("alive-then-dead re-makes the claim",
             s5.health((), (("dead", "e2"), ("alive", "e2"),
                            ("dead", "e1"), ("dead", "e2"))) == "down")

        # --- notices beat rows: a death seen is a death, alive=True or not
        must("an alive vote cannot outvote a witnessed death",
             s5.health((("e1", 4, True), ("e2", 4, True),
                        ("e3", 4, True)), (("dead", "e1"),)) == "up")
        must("two witnessed deaths down the region despite alive rows",
             s5.health(up3, (("dead", "e1"), ("dead", "e2"))) == "down")
        must("an observed alive=False row votes the same as a notice",
             s5.health((("e1", 4, True), ("e2", 0, False),
                        ("e3", 0, False)), ()) == "down")

        # --- refusals name the offender
        _refuses(s5.FailError, "a malformed notice is refused",
                 lambda: s5.health((), (("dead", "z9"),)), names=("z9",))
        _refuses(s5.FailError, "a watch kind that is not dead/alive",
                 lambda: s5.health((), (("gone", "e1"),)), names=())
        _refuses(s5.FailError, "a malformed observation is refused",
                 lambda: s5.health((("e1", 1.5, True),), ()), names=())
        _refuses(s5.FailError, "votes spanning two regions are refused",
                 lambda: s5.health((("e1", 4, True), ("w1", 4, True)), ()),
                 names=("e1", "w1", "east", "west"))
        _refuses(s5.FailError, "death claims spanning two regions",
                 lambda: s5.health((), (("dead", "e1"), ("dead", "w1"),
                                        ("dead", "w2"))),
                 names=("east", "west"))
        _refuses(s5.FailError, "primary_gone refuses a bad region",
                 lambda: s5.primary_gone((), "south"), names=("south",))
        _refuses(s5.FailError, "primary_gone refuses a malformed notice",
                 lambda: s5.primary_gone((("dead", 5),), "east"),
                 names=())

        # --- primary_gone: the promotion gate
        must("a majority of the old primary's region died",
             s5.primary_gone((("dead", "e1"), ("dead", "e2")), "east")
             is True)
        must("one death is not a majority",
             s5.primary_gone((("dead", "e1"),), "east") is False)
        must("retraction clears the claim",
             s5.primary_gone((("dead", "e1"), ("alive", "e1"),
                              ("dead", "e2")), "east") is False)
        must("the other region's deaths do not prove ours",
             s5.primary_gone((("dead", "w1"), ("dead", "w2")), "east")
             is False)
        must("west's own majority is gone",
             s5.primary_gone((("dead", "w1"), ("dead", "w2")), "west")
             is True)
        must("silence proves nothing",
             s5.primary_gone((), "east") is False)
        fact("a mixed pile counts only the region asked about",
             s5.primary_gone((("dead", "e1"), ("dead", "e2"),
                              ("dead", "w1")), "west") is False
             and s5.primary_gone((("dead", "w1"), ("alive", "w1"),
                                  ("dead", "w2"), ("dead", "w3")),
                                 "west") is True)
        fact("the folded shape (§0.2: notices are subject ids) reads the "
             "same verdicts as the received pairs",
             s5.health((), ("e1", "e2")) == "down"
             and s5.health((), ("e1",)) == "suspect"
             and s5.health((), ("e1", "e2", ("alive", "e2"))) == "suspect"
             and s5.primary_gone(("e1", "e2"), "east") is True
             and s5.primary_gone(("e1", "e2", ("alive", "e2")), "east")
             is False)

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_05: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "failover-from-scratch"

    STAGE = 6

    STUB_MESSAGE = "stage 6: implement answer_region()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "fabric.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H8_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h8_check06_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_06 as s6\n"
                    "try:\n"
                    "    s6.answer_region('east', 'up', 1, 'down', False, 0, 0)\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "fabric.py"))
                    and os.path.isfile(os.path.join(p, "stage_06.py"))),
                   None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h8_check06_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import kv
        import scenarios
        import stage_01 as s1
        import stage_05 as s5
        import stage_06 as s6
        import topology

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        answer = s6.answer_region

        # --- the world's pins, re-read (§4)
        must("REGIONS are exactly two", topology.REGIONS == ("east", "west"))
        must("INITIAL_EPOCH is 1", topology.INITIAL_EPOCH == 1)
        must("stage 5's verdicts are the table's alphabet",
             s5.VERDICTS == ("up", "suspect", "down"))
        must("the answer verbs are the fabric's",
             ("serve", "redirect", "refused")
             == ("serve", "redirect", "refused"))
        fact("FLAP pins the fabric's own unpromoted refusal rows",
             any(a[3] == ("refused", "unpromoted")
                 for a in scenarios.PINS["FLAP"]["probe"]["answers"])
             and any(a[3] == ("redirect", "west")
                     or a[3][0] == "redirect"
                     for a in scenarios.PINS["FLAP"]["probe"]["answers"]))

        # --- the stub probe: an untouched template answers exit 2
        stub = 0
        try:
            answer("east", "up", 1, "down", False, 0, 0)
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_06: stage 6: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("FailError is stage 1's class", s6.FailError is s1.FailError)

        # --- the hysteresis row: up OR suspect serves, untouched
        must("an up home serves",
             answer("east", "up", 1, "down", False, 0, 0) == ("serve", "east"))
        must("a SUSPECT home still serves its own pinned client",
             answer("east", "suspect", 1, "down", True, 9, 0)
             == ("serve", "east"))
        must("the mirror home serves west",
             answer("west", "suspect", 1, "up", True, 5, 0)
             == ("serve", "west"))
        fact("a served home never reads the other side's health",
             all(answer("east", hh, 3, oh, op, 1, 2) == ("serve", "east")
                 for hh in ("up", "suspect")
                 for oh in s5.VERDICTS for op in (True, False)))

        # --- the redirect row: down + promoted + up-or-suspect
        must("a down home with a promoted up other redirects",
             answer("east", "down", 1, "up", True, 2, 0)
             == ("redirect", "west"))
        must("a promoted suspect other still takes the session",
             answer("east", "down", 1, "suspect", True, 2, 0)
             == ("redirect", "west"))
        must("west pins redirect the other way",
             answer("west", "down", 1, "up", True, 2, 0)
             == ("redirect", "east"))

        # --- the no-home rows: unqualified target or no target at all
        must("a down other region takes nobody",
             answer("east", "down", 1, "down", True, 2, 0)
             == ("refused", "no-home"))
        must("an UNPROMOTED survivor is refused — failover is a decision",
             answer("east", "down", 1, "up", False, 2, 0)
             == ("refused", "no-home"))
        must("ALL_DIE: both regions down answers no-home",
             answer("east", "down", 1, "down", False, 1, 0)
             == ("refused", "no-home"))

        # --- the fencing law: BELOW, never equal
        must("a serve into an epoch below the session's memory is fenced",
             answer("east", "up", 1, "down", False, 0, 2)
             == ("refused", "fenced"))
        must("equal is NOT below: the session's epoch serves",
             answer("east", "up", 2, "down", False, 0, 2)
             == ("serve", "east"))
        must("a redirect below the session's memory is fenced",
             answer("east", "down", 1, "up", True, 2, 3)
             == ("refused", "fenced"))
        must("a redirect at the memory's epoch is legal",
             answer("east", "down", 1, "up", True, 3, 3)
             == ("redirect", "west"))
        must("fencing beats no-home: a fenced redirect is never a refusal "
             "to move", answer("east", "down", 1, "up", True, 0, 1)
             == ("refused", "fenced"))
        must("fencing asks the eligible region, not the home: a down home "
             "with a promoted stale other fences, never serves the dead",
             answer("east", "down", 9, "up", True, 1, 5)
             == ("refused", "fenced"))

        # --- refusals name the offender
        _refuses(s6.FailError, "an off-roster region is refused",
                 lambda: answer("south", "up", 1, "up", False, 0, 0),
                 names=("south", "east", "west"))
        _refuses(s6.FailError, "a health verdict outside stage 5 is refused",
                 lambda: answer("east", "healthy", 1, "up", False, 0, 0),
                 names=("healthy",))
        _refuses(s6.FailError, "a float epoch is refused",
                 lambda: answer("east", "up", 1.5, "up", False, 0, 0),
                 names=("1.5",))
        _refuses(s6.FailError, "a negative epoch is refused",
                 lambda: answer("east", "up", -1, "up", False, 0, 0),
                 names=())
        _refuses(s6.FailError, "a bool seen-epoch is refused",
                 lambda: answer("east", "up", 1, "up", False, 0, True),
                 names=())
        _refuses(s6.FailError, "a non-bool promotion is refused",
                 lambda: answer("east", "down", 1, "up", "yes", 0, 0),
                 names=())
        _refuses(s6.FailError, "the other health is validated even when "
                 "home serves", lambda: answer("east", "up", 1, "fine",
                                                False, 0, 0),
                 names=("fine",))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_06: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "failover-from-scratch"

    STAGE = 7

    STUB_MESSAGE = "stage 7: implement propose()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "fabric.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H8_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _state(node, **over):
        """A candidate's state, fabric-legal: STATE_KEYS plus id/peers."""
        region = "west" if node[0] == "w" else "east"
        roster = tuple(n for n, r in (("e1", "east"), ("e2", "east"),
                                      ("e3", "east"), ("w1", "west"),
                                      ("w2", "west"), ("w3", "west"))
                       if r == region)
        st = {"id": node, "peers": tuple(p for p in roster if p != node),
              "epoch": 1, "promoted": False, "applied": (), "store": {},
              "hints": (), "applied_count": 0, "notices": (),
              "ledger": {}, "votes": {}}
        st.update(over)
        return st

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h8_check07_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_07 as s7\n"
                    "st = {'id': 'w1', 'peers': ('w2', 'w3'), 'epoch': 1,\n"
                    "      'promoted': False, 'applied': (), 'store': {},\n"
                    "      'hints': (), 'applied_count': 0, 'notices': (),\n"
                    "      'ledger': {}, 'votes': {}}\n"
                    "try:\n"
                    "    s7.propose(st)\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "fabric.py"))
                    and os.path.isfile(os.path.join(p, "stage_07.py"))),
                   None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h8_check07_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import fabric
        import kv
        import scenarios
        import stage_01 as s1
        import stage_05 as s5
        import stage_07 as s7
        import topology

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        # --- the world's pins, re-read (§4)
        must("propose and adopt are legal kinds",
             "propose" in fabric.KINDS and "adopt" in fabric.KINDS)
        must("PRIMARY is east, INITIAL_EPOCH is 1",
             topology.PRIMARY == "east"
             and topology.INITIAL_EPOCH == 1)
        must("majority(3) is 2", topology.majority(3) == 2)
        fact("REGION_DIE: west promoted at 6 — notices landed at 5+1",
             (6, "west", 2) in scenarios.PINS["REGION_DIE"]["probe"]
             ["promotes"])
        fact("FAKE_DEATH: the probe NEVER promotes — no notice arrived",
             scenarios.PINS["FAKE_DEATH"]["probe"]["promotes"] == ())
        fact("ALL_DIE: w3 holds the east claims but its OWN region is "
             "below quorum — no promotion",
             scenarios.PINS["ALL_DIE"]["probe"]["promotes"] == ())

        # --- the stub probe: an untouched template answers exit 2
        stub = 0
        try:
            s7.propose(_state("w1"))
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_07: stage 7: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("FailError is stage 1's class", s7.FailError is s1.FailError)
        east_gone = ("e1", "e2")  # the folded shape the fabric carries
        _gone = _state("w1", notices=east_gone + ("w2", "w3"))
        must("a region below its own quorum declines the vote — no "
             "proposal AND no self-vote (it did not ask)",
             s7.propose(_gone) == ((), _gone))

        # --- propose: the five gates, one at a time
        msgs, st2 = s7.propose(_state("w1", notices=east_gone))
        must("the proposal reaches every live peer",
             tuple(fabric.msg_target(m) for m in msgs) == ("w2", "w3"))
        must("a proposal is a propose kind with the sender at field 2",
             all(fabric.msg_kind(m) == "propose" and m[2] == "w1"
                 for m in msgs))
        must("the proposal carries the candidate's epoch+1",
             all(m[3] == 2 for m in msgs))
        must("the candidate adopts nothing yet — it only ASKED",
             st2["epoch"] == 1 and not st2["promoted"])
        must("the candidate records its own vote",
             st2["votes"] == {2: frozenset({"w1"})})
        fact("the proposal is region-internal: no message crosses to east",
             all(fabric.msg_target(m)[0] == "w" for m in msgs))
        must("silence proposes nothing",
             s7.propose(_state("w1"))[0] == ())
        must("a minority death claim proposes nothing",
             s7.propose(_state("w1", notices=("e1",)))[0] == ())
        must("the primary's own region never proposes",
             s7.propose(_state("e1", notices=("w1", "w2")))[0] == ())
        must("an already-promoted node proposes nothing",
             s7.propose(_state("w1", notices=east_gone,
                               promoted=True))[0] == ())
        must("a failed round does not re-ask",
             s7.propose(_state("w1", notices=east_gone, epoch=2))[0] == ())
        must("a region below its own quorum proposes nothing",
             s7.propose(_state("w1", notices=east_gone + ("w2",
                                                          "w3")))[0] == ())
        must("a dead peer is not asked (its vote can never come)",
             tuple(fabric.msg_target(m) for m in
                   s7.propose(_state("w1",
                                     notices=east_gone + ("w2",)))[0])
             == ("w3",))

        # --- tally: distinct adopters, majority of the ROSTER
        promoted, st3 = s7.tally(st2, (("adopt", "w1", "w2", 2),
                                       ("adopt", "w1", "w3", 2)))
        must("two adopters plus the self-vote promote the region",
             promoted is True and st3["epoch"] == 2)
        promoted, _ = s7.tally(_state("w1", votes={2: frozenset({"w1"})}),
                               ())
        must("the self-vote alone is one adopter < majority(3): False",
             promoted is False)
        promoted, _ = s7.tally(_state("w1"),
                               (("adopt", "w1", "w1", 2),))
        must("a node cannot double-count itself", promoted is False)
        promoted, _ = s7.tally(_state("w1", notices=("w2", "w3")),
                               (("adopt", "w1", "w1", 2),))
        must("the majority is of the ROSTER, not the living",
             promoted is False)
        promoted, st3 = s7.tally(_state("w1"),
                                 (("adopt", "w1", "w2", 2),
                                  ("adopt", "w1", "w2", 2)))
        must("one node adopting twice is one voter — and {self, w2} "
             "reaches the majority",
             promoted is True
             and st3["votes"][2] == frozenset({"w2"}))

        # --- monotonicity: at or below the current epoch is a refusal
        promoted, st3 = s7.tally(_state("w1", epoch=3),
                                 (("adopt", "w1", "w2", 2),))
        must("an adopt BELOW the node's epoch is never counted",
             promoted is False and st3["epoch"] == 3)
        promoted, _ = s7.tally(_state("w1", epoch=2),
                               (("adopt", "w1", "w2", 2),))
        must("an adopt AT the node's epoch is a recorded refusal",
             promoted is False)
        promoted, st3 = s7.tally(_state("w1", votes={2: frozenset({"w1",
                                                                   "w2"}),
                                                     }, epoch=2),
                                 (("adopt", "w1", "w3", 3),))
        must("a lower round's votes do not leak into the higher epoch",
             promoted is True and st3["epoch"] == 3)
        promoted, st3 = s7.tally(_state("w1", epoch=2, promoted=True), ())
        must("promoted stays promoted — an epoch is a ratchet",
             promoted is True)
        promoted, st3 = s7.tally(_state("w1"),
                                 (("adopt", "w1", "w2", 2),
                                  ("adopt", "w1", "w3", 3)))
        must("arrival order: both rounds count, the last carries the "
             "promotion",
             promoted is True and st3["epoch"] == 3
             and st3["votes"][2] == frozenset({"w2"}))

        # --- the cross-region vote: the split-brain seed, refused
        _refuses(s7.FailError, "an adopt from the other region is refused",
                 lambda: s7.tally(_state("w1"),
                                  (("adopt", "w1", "e2", 2),)),
                 names=("e2", "east", "west"))
        for bad in (lambda: s7.tally(_state("w1"),
                                     (("adopt", "w2", "w2", 2),)),
                    lambda: s7.tally(_state("w1"),
                                     (("adopt", "w1", "z9", 2),)),
                    lambda: s7.tally(_state("w1"),
                                     (("adopt", "w1", "w2", 2.5),)),
                    lambda: s7.tally(_state("w1"),
                                     (("adopt", "w1", "w2", -1),)),
                    lambda: s7.tally(_state("w1"),
                                     (("sync", "w1", "w2", 2),)),
                    lambda: s7.tally(_state("w1"), (("adopt",),))):
            _refuses(s7.FailError, "a malformed reply is refused", bad,
                     names=())
        for bad_state in (lambda: s7.propose(_state("z9")),
                          lambda: s7.propose(_state("w1", epoch=1.5)),
                          lambda: s7.propose(_state("w1",
                                                    promoted="yes")),
                          lambda: s7.propose(_state("w1", notices=("z9",))),
                          lambda: s7.propose(_state("w1", store=[])),
                          lambda: s7.propose("not-a-state"),
                          lambda: s7.tally(_state("w1", votes={2: ("z9",)}),
                                          ())):
            _refuses(s7.FailError, "a malformed state is refused",
                     bad_state, names=())
        h = kv.hint("a", kv.version("x", (("w1", 1),)), "e1")
        _refuses(kv.KvError, "a hint parked in the store is refused "
                 "before it travels",
                 lambda: s7.propose(_state("w1", notices=east_gone,
                                           store={"a": (h,)})), names=())
        fact("the store travels with the proposal",
             s7.propose(_state("w1", notices=east_gone,
                               store={"a": (kv.version("7", (("w1", 1),)),
                                            )}))[0][0][4]
             == {"a": (kv.version("7", (("w1", 1),)),)})

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_07: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "failover-from-scratch"

    STAGE = 8

    STUB_MESSAGE = "stage 8: implement apply_once()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "fabric.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H8_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _st(node="w1", **over):
        """A node state with everything the gate reads."""
        base = {"id": node, "epoch": 1, "store": {}, "applied": (),
                "applied_count": 0, "ledger": {}, "hints": ()}
        base.update(over)
        return base

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h8_check08_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_08 as s8\n"
                    "st = {'id': 'w1', 'epoch': 1, 'store': {}, 'applied': (),\n"
                    "      'applied_count': 0, 'ledger': {}, 'hints': ()}\n"
                    "try:\n"
                    "    s8.apply_once(st, 'alpha', 1, ('set', 'a', '2', 1))\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "fabric.py"))
                    and os.path.isfile(os.path.join(p, "stage_08.py"))),
                   None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h8_check08_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import fabric
        import kv
        import scenarios
        import stage_01 as s1
        import stage_03 as s3
        import stage_08 as s8
        import topology

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        # --- the world's pins, re-read (§4)
        must("the fabric reads applied as the ledger's truth",
             "applied" in fabric.STATE_KEYS)
        fact("FLAP: the probe's dups column is EMPTY — the ledger's law",
             scenarios.PINS["FLAP"]["probe"]["dups"] == ())
        fact("FLAP: the foil re-applies r=3 — dups names every re-apply",
             len(scenarios.PINS["FLAP"]["naive"]["dups"]) > 0)
        fact("REGION_DIE: the r=2 retry at 7 answers the recorded ack",
             (7, "alpha", 2, ("applied",))
             in scenarios.PINS["REGION_DIE"]["probe"]["answers"])

        # --- the stub probe: an untouched template answers exit 2
        stub = 0
        try:
            s8.apply_once(_st(), "alpha", 1, ("set", "a", "2", 1))
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_08: stage 8: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("FailError is stage 1's class", s8.FailError is s1.FailError)
        must("the ops are set and get", s8.OPS == ("set", "get"))

        # --- first arrival: all four move together
        answer, after = s8.apply_once(_st(), "alpha", 1,
                                      ("set", "a", "2", 1))
        must("a first set answers applied", answer == ("applied",))
        must("store, applied, applied_count, ledger moved together",
             after["store"] == {"a": (kv.version("2", (("w1", 1),)),)}
             and after["applied"] == (("alpha", 1, "a"),)
             and after["applied_count"] == 1
             and after["ledger"] == {("alpha", 1): (("applied",), "2")})

        # --- replay: the RECORDED answer, NOTHING moves
        again, after2 = s8.apply_once(after, "alpha", 1,
                                      ("set", "a", "9", 1))
        must("a retry returns the recorded answer",
             again == ("applied",))
        must("a retry moves NOTHING", after2 is after)
        must("seen exposes the recorded entry",
             s8.seen(after2, "alpha", 1) == (("applied",), "2"))
        must("seen is None for a request never received",
             s8.seen(after2, "alpha", 2) is None)
        fact("the retry survives a promotion: the ledger is checked "
             "BEFORE the fence — REGION_DIE's r=2 at epoch 2",
             s8.apply_once(dict(after, epoch=2, id="w2"), "alpha", 1,
                           ("set", "a", "2", 1))
             == (("applied",), dict(after, epoch=2, id="w2")))

        # --- reads are free: a get never enters the ledger
        got, after3 = s8.apply_once(after2, "alpha", 2,
                                    ("get", "a", None, 1))
        must("a get answers served", got == ("ok", ("2",)))
        must("a get touches nothing", after3 is after2)
        must("a get with a rid the ledger holds for a set still reads",
             s8.apply_once(after2, "alpha", 1, ("get", "a", None, 1))[0]
             == ("ok", ("2",)))
        must("a get of an absent key is an empty ok",
             s8.apply_once(_st(), "beta", 7, ("get", "z", None, 1))[0]
             == ("ok", ()))

        # --- the fence: below the epoch is refused, equal is not
        fenced, untouched = s8.apply_once(_st(epoch=2), "gamma", 1,
                                          ("set", "a", "x", 1))
        must("an unseen op below the epoch is refused fenced",
             fenced == ("refused", "fenced"))
        must("a refused op touches NO state", untouched["store"] == {}
             and untouched["applied"] == ())
        must("equal epoch is NOT fenced",
             s8.apply_once(_st(epoch=2), "gamma", 1,
                           ("set", "a", "x", 2))[0] == ("applied",))
        must("a get below the epoch is fenced too — ops are ops",
             s8.apply_once(_st(epoch=2), "gamma", 1,
                           ("get", "a", None, 1))[0]
             == ("refused", "fenced"))

        # --- the sibling law: a write ends the conflict, a read never
        # narrows it
        dual = {"a": (kv.version("3", (("e1", 2),)),
                      kv.version("5", (("w1", 2),)))}
        must("a read over a sibling set answers BOTH",
             s8.apply_once(_st(store=dual), "c", 1,
                           ("get", "a", None, 1))[0] == ("ok", ("3", "5")))
        answer, merged = s8.apply_once(_st(store=dual), "c", 9,
                                       ("set", "a", "7", 1))
        winner = merged["store"]["a"]
        must("a write after the conflict is ONE dominating version",
             len(winner) == 1
             and kv.dominates(kv.clock_of(winner[0]),
                              kv.clock_of(dual["a"][0]))
             and kv.dominates(kv.clock_of(winner[0]),
                              kv.clock_of(dual["a"][1])))
        must("the bump carries the writing node",
             ("w1", 3) in kv.clock_of(winner[0]))
        fact("a replica still holding a sibling cannot resurrect it "
             "over the write (A6's increment law)",
             s8.apply_once(dict(merged, store={"a": (
                 kv.version("3", (("e1", 2),)), winner[0])}),
                 "c", 1, ("get", "a", None, 1))[0] == ("ok", ("7",)))

        # --- distinct (client, rid) keys: the ledger is per pair
        must("the same rid from another client is a distinct request",
             s8.apply_once(merged, "d", 9, ("set", "a", "8", 1))[1]
             ["applied_count"] == 2)

        # --- refusals name the offender
        _refuses(s8.FailError, "a negative rid is refused, naming it",
                 lambda: s8.apply_once(_st(), "alpha", -3,
                                       ("set", "a", "2", 1)),
                 names=("-3",))
        _refuses(s8.FailError, "a float rid is refused",
                 lambda: s8.apply_once(_st(), "alpha", 1.5,
                                       ("set", "a", "2", 1)), names=())
        _refuses(s8.FailError, "an empty client is refused",
                 lambda: s8.apply_once(_st(), "", 1,
                                       ("set", "a", "2", 1)), names=())
        for bad in (lambda: s8.apply_once(_st(), "alpha", 1,
                                          ("put", "a", "2", 1)),
                    lambda: s8.apply_once(_st(), "alpha", 1,
                                          ("set", "", "2", 1)),
                    lambda: s8.apply_once(_st(), "alpha", 1,
                                          ("set", "a", 5, 1)),
                    lambda: s8.apply_once(_st(), "alpha", 1,
                                          ("get", "a", "x", 1)),
                    lambda: s8.apply_once(_st(), "alpha", 1,
                                          ("set", "a", "2", -1)),
                    lambda: s8.apply_once(_st(), "alpha", 1,
                                          ("set", "a", "2", True)),
                    lambda: s8.apply_once(
                        _st(ledger={("c", 1): (("applied",), 5)}), "c", 1,
                        ("get", "a", None, 1)),
                    lambda: s8.apply_once(
                        _st(applied=(("c", "x", "a"),)), "c", 1,
                        ("get", "a", None, 1)),
                    lambda: s8.apply_once("nope", "c", 1,
                                          ("get", "a", None, 1)),
                    lambda: s8.apply_once(_st(id="z9"), "c", 1,
                                          ("get", "a", None, 1)),
                    lambda: s8.seen(_st(), "alpha", True),
                    lambda: s8.seen("nope", "alpha", 1)):
            _refuses(s8.FailError, "a malformed input is refused", bad,
                     names=())
        _refuses(kv.KvError, "a malformed version in the store is refused "
                 "by the world's grammar",
                 lambda: s8.apply_once(_st(store={"a": [1]}), "c", 1,
                                       ("set", "a", "2", 1)), names=())
        h = kv.hint("a", kv.version("1", (("e1", 1),)), "w1")
        _refuses(s8.FailError, "a version parked in hints is refused",
                 lambda: s8.apply_once(_st(hints=(
                     kv.version("a", (("w1", 1),)),)), "c", 1,
                     ("get", "x", None, 1)), names=("malformed",))
        must("a legal hint travels through the gate untouched",
             s8.apply_once(_st(hints=(h,)), "c", 1,
                           ("get", "x", None, 1))[0] == ("ok", ()))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_08: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "failover-from-scratch"

    STAGE = 9

    STUB_MESSAGE = "stage 9: implement merged()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "fabric.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H8_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h8_check09_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_09 as s9\n"
                    "try:\n"
                    "    s9.merged({}, {})\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "fabric.py"))
                    and os.path.isfile(os.path.join(p, "stage_09.py"))),
                   None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h8_check09_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import fabric
        import kv
        import scenarios
        import stage_01 as s1
        import stage_03 as s3
        import stage_09 as s9
        import topology

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label, )
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        # --- the world's pins, re-read (§4)
        fact("DUAL pins the sibling answer both regions must reach",
             scenarios.PINS["DUAL"]["probe"]["answers"][-1]
             == (15, "w1", 10, ("ok", ("3", "5"))))
        fact("LAG pins the named lost writes and rpo = 2",
             scenarios.PINS["LAG"]["probe"]["lost"]
             == (("alpha", 1, "p"), ("alpha", 2, "p"))
             and scenarios.PINS["LAG"]["probe"]["rpo"] == 2)
        fact("FLAP pins rto = 6 (refused 7, served 13)",
             scenarios.PINS["FLAP"]["probe"]["rto"] == 6)
        fact("REGION_DIE was never refused: rto None; ALL_DIE never "
             "recovered: rto None",
             scenarios.PINS["REGION_DIE"]["probe"]["rto"] is None
             and scenarios.PINS["ALL_DIE"]["probe"]["rto"] is None)

        # --- the stub probe: an untouched template answers exit 2
        stub = 0
        try:
            s9.merged({}, {})
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_09: stage 9: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("FailError is stage 1's class", s9.FailError is s1.FailError)

        va = kv.version("3", (("e1", 2),))
        vb = kv.version("5", (("w1", 2),))

        # --- merged: the union, never a choice
        m = s9.merged({"a": (va,), "b": (kv.version("x", (("e1", 1),)),)},
                      {"a": (vb,), "c": (kv.version("5", (("w1", 2),)),)})
        must("every key of both sides survives the merge",
             set(m) == {"a", "b", "c"})
        must("keys are ordered — the same pair merges byte-equal "
             "everywhere",
             list(m) == ["a", "b", "c"])
        must("a conflicted key answers EVERY sibling (DUAL's law)",
             s3.served(m["a"], ()) == ("ok", ("3", "5")))
        must("merging a store with itself is idempotent",
             s9.merged(m, m) == m)
        fact("merged keeps BOTH siblings and chooses nothing: neither "
             "clock dominates the other (stage 8's bump is what ends a "
             "conflict)",
             len(m["a"]) == 2
             and not kv.dominates(kv.clock_of(m["a"][0]),
                                  kv.clock_of(m["a"][1]))
             and not kv.dominates(kv.clock_of(m["a"][1]),
                                  kv.clock_of(m["a"][0])))

        # --- lost: name the broken promises, never count-and-forget
        acked = (("alpha", 1, "p"), ("alpha", 2, "q"), ("beta", 3, "a"))
        must("a key no live store carries is NAMED, with its rid",
             s9.lost(acked, ({"a": (va,)},))
             == (("alpha", 1, "p"), ("alpha", 2, "q")))
        must("a key every ack can point at is kept",
             s9.lost(acked, ({"p": (), "q": (), "a": (va,)},)) == ())
        must("the promise is about the KEY: a different version still "
             "keeps it (DUAL's r=1 was overwritten, not lost)",
             s9.lost(acked, ({"p": (vb,), "q": (va,), "a": ()},)) == ())
        must("an empty fleet names EVERYTHING",
             s9.lost(acked, ()) == acked)
        must("a retried acked row is named ONCE — writes, not arrivals",
             s9.lost((("c", 1, "k"), ("c", 1, "k"), ("c", 2, "k")), ())
             == (("c", 1, "k"), ("c", 2, "k")))
        must("the answer follows arrival order",
             s9.lost((("c", 9, "z"), ("c", 1, "y")), ())
             == (("c", 9, "z"), ("c", 1, "y")))

        # --- rpo: the count, and the fabric's agreement
        must("rpo is the length", s9.rpo(acked) == 3 and s9.rpo(()) == 0)
        fact("LAG: this function on the acked rows names exactly the "
             "fabric's lost column, and rpo agrees",
             s9.lost(scenarios.PINS["LAG"]["probe"]["lost"],
                     ({"a": (kv.version("7", (("w1", 1),)),)},))
             == scenarios.PINS["LAG"]["probe"]["lost"]
             and s9.rpo(scenarios.PINS["LAG"]["probe"]["lost"])
             == scenarios.PINS["LAG"]["probe"]["rpo"])
        must("ALL_DIE names its one lost write",
             s9.rpo(scenarios.PINS["ALL_DIE"]["probe"]["lost"]) == 1)

        # --- rto: the outage's duration, or None
        must("FLAP's number: 13 - 7 = 6", s9.rto(7, 13) == 6)
        must("a never-refused run has no outage", s9.rto(None, 13) is None)
        must("a never-served run has no recovery",
             s9.rto(7, None) is None)
        must("instant recovery is zero ticks", s9.rto(7, 7) == 0)
        flap_answers = scenarios.PINS["FLAP"]["probe"]["answers"]
        first_refused = min(t for t, _c, _r, a in flap_answers
                            if a[0] == "refused")
        first_served = min(t for t, _c, _r, a in flap_answers
                           if a[0] in ("ok", "applied")
                           and t >= first_refused)
        fact("the report's rto MEASURES the answer column, and the "
             "fabric's column agrees",
             s9.rto(first_refused, first_served) == 6
             == scenarios.PINS["FLAP"]["probe"]["rto"])

        # --- refusals name the offender
        _refuses(s9.FailError, "merged refuses a non-dict, naming it",
                 lambda: s9.merged("nope", {}), names=("store_a",))
        _refuses(s9.FailError, "merged refuses a non-tuple value",
                 lambda: s9.merged({}, {"a": 5}), names=("store_b",))
        _refuses(s9.FailError, "merged refuses an empty key",
                 lambda: s9.merged({"": (va,)}, {}), names=())
        _refuses(s9.FailError, "lost refuses a malformed row",
                 lambda: s9.lost((("c", 1),), ()), names=())
        _refuses(s9.FailError, "lost refuses a negative rid",
                 lambda: s9.lost((("c", -1, "k"),), ()), names=())
        _refuses(s9.FailError, "lost refuses a float rid",
                 lambda: s9.lost((("c", 1.5, "k"),), ()), names=())
        _refuses(s9.FailError, "lost refuses a bool rid",
                 lambda: s9.lost((("c", True, "k"),), ()), names=())
        _refuses(s9.FailError, "lost refuses stores that are not a tuple",
                 lambda: s9.lost(acked, {"a": ()}), names=())
        _refuses(s9.FailError, "rpo refuses anything but acked rows",
                 lambda: s9.rpo("nope"), names=())
        _refuses(s9.FailError, "rto refuses a float tick",
                 lambda: s9.rto(7.5, 13), names=())
        _refuses(s9.FailError, "rto refuses a bool tick",
                 lambda: s9.rto(True, 7), names=())
        _refuses(s9.FailError, "rto refuses a negative tick",
                 lambda: s9.rto(-1, 7), names=())
        _refuses(s9.FailError,
                 "rto refuses recovery BEFORE the outage, naming both",
                 lambda: s9.rto(13, 7), names=("13", "7"))
        _refuses(kv.KvError, "a junk version inside a store is the "
                 "world's grammar",
                 lambda: s9.merged({"a": (va, "junk")}, {}), names=())

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_09: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "failover-from-scratch"

    STAGE = 10

    STUB_MESSAGE = "stage 10: implement init()"

    DRILL_NAMES = ("ONE_NODE", "REGION_DIE", "DUAL", "FLAP", "LAG",
                   "FAKE_DEATH", "ALL_DIE")

    def _repo(start=None):
        for candidate_start in (os.environ.get("H8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "fabric.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H8_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h8_check10_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_10 as s10\n"
                    "try:\n"
                    "    s10.init('e1', ('e2', 'e3'))\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "fabric.py"))
                    and os.path.isfile(os.path.join(p, "stage_10.py"))),
                   None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h8_check10_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import fabric
        import kv
        import naive
        import scenarios
        import stage_10 as s10
        import topology

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label, )
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        # --- the world's pins, re-read (§4)
        fact("the drill table is the scenario table, seven names",
             sorted(s10.DRILLS) == sorted(
                 name for name, _k, _s, _t in scenarios.SCENARIOS)
             and len(s10.DRILLS) == 7)
        fact("FLAP pins rto 6 and LAG pins rpo 2 in the probe column",
             scenarios.PINS["FLAP"]["probe"]["rto"] == 6
             and scenarios.PINS["LAG"]["probe"]["rpo"] == 2
             and scenarios.PINS["ALL_DIE"]["probe"]["rto"] is None)

        # --- the node: a state the fabric can drive
        st = s10.init("w1", ("w2", "w3"))
        fact("init carries every STATE_KEYS field at the initial epoch",
             all(key in st for key in fabric.STATE_KEYS)
             and st["epoch"] == topology.INITIAL_EPOCH
             and st["promoted"] is False and st["store"] == {}
             and st["applied"] == () and st["applied_count"] == 0
             and st["notices"] == ())
        _refuses(s10.FailError, "init refuses a node id off the fleet",
                 lambda: s10.init("zz", ()), names=("zz",))

        # watch fold, absorb, and the redirect gate — hand-built states
        gone = s10.recv(st, ("dead", "w2"))[0]
        gone = s10.recv(gone, ("dead", "w3"))[0]
        back = s10.recv(gone, ("alive", "w2"))[0]
        fact("the watch channel folds plain ids: dead claims, alive retracts",
             gone["notices"] == ("w2", "w3")
             and back["notices"] == ("w3",))
        v1 = kv.version("1", (("w1", 1),))
        v0 = kv.version("0", (("w1", 1),))
        st = s10.recv(st, ("sync", "w1", "w2", "a", v1, "c", 1))[0]
        st = s10.recv(st, ("sync", "w1", "w2", "a", v0, "c", 2))[0]
        fact("a sync is absorbed — siblings kept, the sender's row recorded",
             set(st["store"]["a"]) == {v1, v0}
             and st["applied"] == (("c", 1, "a"), ("c", 2, "a"))
             and st["applied_count"] == 2)
        _refuses(s10.FailError, "recv refuses a kind the protocol does not speak",
                 lambda: s10.recv(st, ("noise", "w1")), names=("noise",))
        _state, _msgs, verdict = s10.client(gone, "get a c=me r=7")
        fact("below quorum a call redirects home, not absorbed",
             verdict == ("redirect", "east") and _msgs == ()
             and _state["applied_count"] == 0)

        # --- the drill: shape, and every probe column matched
        rows = [s10.drill(name) for name in DRILL_NAMES]
        by_name = {}
        shape_ok = True
        for row in rows:
            tag, result, pins, rto, rpo = row
            shape_ok = (shape_ok and tag == "scenario"
                        and isinstance(result, dict)
                        and all(c in result for c in
                                ("promotes", "answers", "dups", "lost")))
        fact("drill returns ('scenario', result, pins, rto, rpo) for all seven",
             shape_ok and all(row[2] is scenarios.PINS[name]
                              for row, name in zip(rows, DRILL_NAMES)))
        matched = True
        for row, name in zip(rows, DRILL_NAMES):
            _tag, result, _pins, rto, rpo = row
            probe = scenarios.PINS[name]["probe"]
            for column in ("promotes", "answers", "dups", "lost"):
                if result[column] != probe[column]:
                    matched = False
                    print("     %s %s: %r != %r" % (name, column,
                                                    result[column],
                                                    probe[column]))
            if rto != probe["rto"] or rpo != probe["rpo"]:
                matched = False
                print("     %s rto/rpo: %r/%r != %r/%r"
                      % (name, rto, rpo, probe["rto"], probe["rpo"]))
        fact("every drill's run matches the probe column, measured rto/rpo included",
             matched)
        flap = dict(zip(DRILL_NAMES, rows))["FLAP"]
        lag = dict(zip(DRILL_NAMES, rows))["LAG"]
        fact("the measured report: FLAP rto 6, LAG rpo 2 naming every lost rid",
             flap[3] == 6 and lag[3] is None and lag[4] == 2
             and lag[1]["lost"] == (("alpha", 1, "p"), ("alpha", 2, "p")))
        fake_run = s10._measure({"answers": ((2, "a", 1, ("refused", "x")),
                                             (5, "a", 1, ("applied",))),
                                 "lost": (("a", 1, "k"), ("a", 2, "k"))})
        none_run = s10._measure({"answers": ((2, "a", 1, ("applied",)),
                                              (6, "a", 2, ("refused", "x")),
                                              (8, "b", 3, ("redirect", "e"))),
                                 "lost": ()})
        fact("rto/rpo are computed from the answer column, not the pins",
             fake_run == (3, 2) and none_run == (None, 0))
        _refuses(KeyError, "an unknown drill name is refused by the table",
                 lambda: s10.drill("NOT_A_SCENARIO"), names=("NOT_A_SCENARIO",))

        # --- the audit: pass on the real seven...
        fact("audit passes the honest seven",
             s10.audit(tuple(rows)) == ("pass", ()))

        # --- ...and refuses everything else
        tag, result, pins, rto, rpo = flap
        tampered = (tag, dict(result, dups=(("alpha", 3, "w1"),)),
                    pins, rto, rpo)
        verdict, reasons = s10.audit(tuple(
            tampered if row[1] is result else row for row in rows))
        fact("audit refuses a run whose FLAP dups is not empty, naming it",
             verdict == "fail" and any("FLAP" in r and "dups" in r
                                       for r in reasons))
        wrong = (tag, result, pins, 99, rpo)
        verdict, reasons = s10.audit(tuple(
            wrong if row[1] is result else row for row in rows))
        fact("audit refuses a report whose rto does not come from the run",
             verdict == "fail" and any("FLAP" in r and "rto" in r
                                       for r in reasons))
        verdict, reasons = s10.audit(tuple(
            row for row in rows if row[1] is not lag[1]))
        fact("audit refuses an incomplete drill set, naming the missing schedule",
             verdict == "fail" and any("LAG" in r for r in reasons))
        verdict, reasons = s10.audit(tuple(
            (row[0], row[1], row[2], row[3], row[4] + 1)
            if row[1] is lag[1] else row for row in rows))
        fact("audit refuses a report whose rpo is not the run's lost count",
             verdict == "fail" and any("LAG" in r and "rpo" in r
                                       for r in reasons))
        _refuses(s10.FailError, "audit refuses a row that is not a drill",
                 lambda: s10.audit(("not", "a", "drill", "row")),
                 names=("scenario",))
        _refuses(s10.FailError, "audit refuses pins from outside the world's table",
                 lambda: s10.audit((("scenario", flap[1], {"probe": {},
                                                           "naive": {}},
                                     flap[3], flap[4]),)),
                 names=("PINS",))

        # --- the foil: its divergence is a RUN, and the audit drives it
        foil_fake = fabric.Fabric(naive,
                                  scenario=scenarios.scenario("FAKE_DEATH")[1])
        foil_fake.run(24)
        foil_flap = fabric.Fabric(naive,
                                  scenario=scenarios.scenario("FLAP")[1])
        foil_flap.run(24)
        foil_dual = fabric.Fabric(naive,
                                  scenario=scenarios.scenario("DUAL")[1])
        foil_dual.run(24)
        fake_col = foil_fake.result()["promotes"]
        flap_col = foil_flap.result()["dups"]
        dual_col = foil_dual.result()["answers"]
        fact("the foil's FAKE_DEATH run really promotes on silence",
             fake_col == ((3, "east", 2), (6, "west", 2)) and bool(fake_col))
        fact("the foil's FLAP run really re-applies the retried rid",
             flap_col == (("alpha", 3, "w1"), ("alpha", 3, "w1")))
        fact("the foil's DUAL run really narrows the sibling pair",
             (14, "e1", 9, ("ok", ("3",))) in tuple(dual_col)
             and (15, "w1", 10, ("ok", ("5",))) in tuple(dual_col)
             and scenarios.PINS["DUAL"]["probe"]["answers"][-1][3]
             == ("ok", ("3", "5")))
        fact("the audit's own foil drive equals these direct runs",
             s10._foil("FAKE_DEATH")["promotes"] == fake_col
             and s10._divergence("DUAL", {"answers": dual_col}) is not None
             and s10._divergence("DUAL", {"answers": tuple(
                 scenarios.PINS["DUAL"]["probe"]["answers"])}) is None)
        saved = s10._foil
        try:
            s10._foil = lambda name: scenarios.PINS[name]["probe"]
            verdict, reasons = s10.audit(tuple(rows))
            fact("audit refuses a foil drive that behaved correctly, naming it",
                 verdict == "fail" and any("FAKE_DEATH" in r for r in reasons))
        finally:
            s10._foil = saved

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_10: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The clock: ordering the versions, not the values",
        tags=['vector-clock', 'siblings', 'dominance'],
        action="Write `compare`, `coalesce` and `dominance_table` in stage_01.py.",
        predict="Why concurrent siblings never collapse, and what a local stamp silently narrows.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="Quorum: serve inside three or refuse entirely",
        tags=['quorum', 'r-w-n', 'lag'],
        action="Write `ackable`, `readable`, `writable`, `r_w_law` and `healthy_count` in stage_02.py.",
        predict="Why a two-of-three ack is a promise and one of three is silence, and why presence is not servability.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="Hints: held for a peer, never served as yours",
        tags=['hinted-handoff', 'park', 'deliver'],
        action="Write `park`, `deliver`, `owned` and `served` in stage_03.py.",
        predict="Why a parked write must not widen a read, and what makes re-delivery cost nothing.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="Anti-entropy: the union over ranges, never a choice",
        tags=['merkle', 'ranges', 'repair'],
        action="Write `fingerprint`, `ranges`, `tree_hashes`, `diff` and `repair` in stage_04.py.",
        predict="Why siblings hash apart, why an empty range still has a hash, and why repair picks nothing.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="Health: a signal that is not a heartbeat",
        tags=['failure-detector', 'notices', 'retraction'],
        action="Write `health` and `primary_gone` in stage_05.py.",
        predict="Why silence cannot vote, and what one `alive` notice retracts.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="Sessions: the pinned answer is a table, not a feeling",
        tags=['pinned-sessions', 'redirect', 'fencing'],
        action="Write `answer_region` in stage_06.py.",
        predict="Why a suspect region still serves its own clients, and why an old epoch is refused forever after.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="Promotion: a majority adopted, or no epoch at all",
        tags=['promotion', 'epoch', 'quorum-vote'],
        action="Write `propose` and `tally` in stage_07.py.",
        predict="Why a lonely node promotes nothing, and why a proposal never crosses the cut.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The redirect that does not apply a write twice",
        tags=['exactly-once', 'ledger', 'replay'],
        action="Write `apply_once` and `seen` in stage_08.py.",
        predict="Why a retry returns the recorded answer and moves nothing, and why reads never touch the ledger.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="Late writes: reconcile, name the lost, price the RPO",
        tags=['rpo', 'lost-writes', 'merge'],
        action="Write `merged`, `lost`, `rpo` and `rto` in stage_09.py.",
        predict="Why an acked write nobody holds is a debt, and why the RPO is a length and the RTO a difference.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The drill: RTO/RPO measured, the foil run, the audit refused",
        tags=['drill', 'rto', 'foil-audit'],
        action="Write the node protocol plus `drill` and `audit` in stage_10.py.",
        predict="Why a node that passes every stage still fails the region, and why the foil's divergence must be run, never asserted.",
        check=check_10,
    ),
]
