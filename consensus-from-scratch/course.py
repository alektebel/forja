"""Consensus From Scratch — a replicated log judged by simulation.

Ten graded stages over a world provided as code (`wire.py`, `disk.py`,
`sim.py`, `history.py`, `naive.py`, `scenarios.py`), the way the rest of
this repository teaches a mechanism: the world holds the ground truth, a
stage is a file you write, a check is what happens to it, and the judges
are the fabric and the linearizability checker — because an agreement
protocol you can be exactly wrong about has exactly one authority: the
history.

What the course is about, in one line: *a leader is a number a majority
agreed on, a commit is a law about terms, and everything else is
bookkeeping you cannot fake.*

    the vote: terms, and one vote per term
    the election: a leader is a number a majority agreed on
    the heartbeats: leadership is exercised, not claimed
    replication: the entries match term by term
    the commit rule: a majority, and the current term
    the stale leader: refuse, downgrade, never ignore
    the disk that lied: persist and recover
    the snapshot: commit without losing a committed entry
    the membership change: one at a time
    the proof: one history, two verdicts

The house laws hold here (`.h6-dev/CONTRACT.md` §1): standard library
only, no `float` literal — a majority is `n // 2 + 1`, the whole way —,
no `random` (the one asymmetry between nodes is `wire.TIMEOUTS`, five
fixed election timeouts), no clock, no thread, no socket: the fabric
ticks integer clocks and drops links per schedule. And no `naive` in a
stage 1–9: the foil is driven through `sim.Cluster` by the proof stage
and nowhere else.

What the course does **not** do is trust an implementation's word: the
acceptance is the scenario matrix — seven schedules, the leaders and
first-commits each one pins, `conflicts` empty on every run, every
history linearizable — while the same fabric, same schedules, same
client records demonstrably split the foil's brain.

    python3 codecraft/cli.py run consensus-from-scratch
"""

from codecraft.api import stage

TITLE = "Consensus From Scratch"
DESCRIPTION = ("A replicated log over a deterministic fabric, judged by "
               "simulation and the history: ten stages that answer a vote "
               "under the three refusals, count a leader from distinct "
               "granter majorities, exercise leadership in empty APPENDs, "
               "replicate entries that match term by term, commit only "
               "through the current term, refuse and downgrade stale "
               "leaders, recover from a torn disk, snapshot below the "
               "commit line, change membership through a joint config, and "
               "prove the whole node linearizable on every scenario while "
               "the provided foil double-commits one slot under the same "
               "schedule.")

LEVEL = "advanced"
ORDER = 37


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "consensus-from-scratch"

    STAGE = 1

    STUB_MESSAGE = "stage 1: implement grant_vote()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H6_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H6_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        for name in sorted(os.listdir(overlay)):
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
                raise AssertionError("%s: refusal %r does not name %s"
                                     % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _run_py(course, snippet):
        code = ("import sys; sys.path.insert(0, %r)\n" % (course,)) + snippet
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=120)
        return proc.returncode, proc.stdout + proc.stderr

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h6_check01_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_01 as s1\n"
                    "try:\n"
                    "    s1.grant_vote(None, None)\n"
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
                    if os.path.isfile(os.path.join(p, "wire.py"))
                    and os.path.isfile(os.path.join(p, "stage_01.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h6_check01_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import wire
        import stage_01 as s1

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

        # --- the world's pins, re-read
        must("majority table", [wire.majority(n) for n in range(1, 7)]
             == [1, 2, 2, 3, 3, 4])
        must("TIMEOUTS", wire.TIMEOUTS == (("a1", 11), ("a2", 7), ("a3", 9),
                                           ("a4", 5), ("a5", 13)))
        must("HEARTBEAT", wire.HEARTBEAT == 5)
        must("state key shapes", (len(wire.FOLLOWER_KEYS),
                                  len(wire.CANDIDATE_KEYS),
                                  len(wire.LEADER_KEYS)) == (9, 10, 12))

        stub = 0
        try:
            s1.grant_vote(wire.follower("a2"), wire.request_vote(1, "a3",
                                                                 0, -1))
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_01: stage 1: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)
        must("grant_vote exists", callable(getattr(s1, "grant_vote", None)))

        # --- a lower term is refused; the reply answers at the voter's
        voter = wire.follower("a2", term=4, config=("a1", "a2", "a3"))
        stale = wire.request_vote(3, "a1", 0, -1)
        reply, state2 = s1.grant_vote(voter, stale)
        fact("lower-term request refused", reply == (wire.VOTE_REPLY, 4,
                                                     "a2", "a1", False))
        fact("refusal keeps the voter's term", state2["term"] == 4)
        fact("refusal keeps voted_for", state2["voted_for"] is None)

        # --- one vote per term: the latch
        ask = wire.request_vote(4, "a1", 0, -1)
        reply, voted = s1.grant_vote(voter, ask)
        fact("own-term request with empty log granted",
             reply == (wire.VOTE_REPLY, 4, "a2", "a1", True))
        fact("grant latches voted_for", voted["voted_for"] == "a1")
        rival = wire.request_vote(4, "a3", 0, -1)
        reply, again = s1.grant_vote(voted, rival)
        fact("second candidate same term refused",
             reply[4] is False and again["voted_for"] == "a1")
        reply, same = s1.grant_vote(voted, ask)
        fact("re-ask from the SAME candidate re-grants",
             reply[4] is True and same["voted_for"] == "a1")

        # --- the up-to-date law: term before index, own term included
        long_log = wire.follower("a2", term=4, config=("a1", "a2", "a3"),
                                 log=((0, 3, "x=1"),), commit_index=0)
        short = wire.request_vote(4, "a1", 3, -1)  # last term 3 < voter 3?
        # voter last is (0, 3); candidate claims (-1, 3): same term, lower
        # index -> refused.
        reply, _ = s1.grant_vote(long_log, short)
        fact("shorter log refused at equal last term", reply[4] is False)
        ahead = wire.request_vote(4, "a1", 5, 0)  # last term 5 > voter's 3
        reply, _ = s1.grant_vote(long_log, ahead)
        fact("higher last term wins over length", reply[4] is True)
        deeper = wire.request_vote(4, "a1", 3, 7)  # same term, deeper index
        reply, _ = s1.grant_vote(long_log, deeper)
        fact("same last term, longer log granted", reply[4] is True)
        snap = wire.follower("a2", term=4, config=("a1", "a2", "a3"),
                             log=(), commit_index=-1, snapshot_at=(9, 6))
        reply, _ = s1.grant_vote(snap, wire.request_vote(4, "a1", 5, 99))
        fact("shallower-boundary candidate refused", reply[4] is False)
        reply, _ = s1.grant_vote(snap, wire.request_vote(4, "a1", 6, 9))
        fact("boundary pair granted at equality", reply[4] is True)

        # --- higher term adopted BEFORE the vote is considered
        latch = wire.follower("a2", term=4, voted_for="a1",
                              config=("a1", "a2", "a3"), elapsed=3)
        higher = wire.request_vote(6, "a3", 0, -1)
        reply, upgraded = s1.grant_vote(latch, higher)
        fact("higher term adopted", upgraded["term"] == 6)
        fact("latch cleared on adoption", upgraded["voted_for"] == "a3")
        fact("reply answers at the NEW term", reply == (wire.VOTE_REPLY, 6,
                                                        "a2", "a3", True))
        fact("timer reset on adoption", upgraded["elapsed"] == 0)

        # --- the reply carries the VOTER in field 2
        reply, _ = s1.grant_vote(voter, ask)
        fact("voter id in field 2", reply[2] == "a2" and reply[3] == "a1")

        fresh = wire.follower("a2", term=4, config=("a1", "a2", "a3"))
        s1.grant_vote(fresh, ask)
        fact("grant leaves the caller's state untouched",
             fresh == wire.follower("a2", term=4, config=("a1", "a2",
                                                          "a3")))
        r1 = s1.grant_vote(latch, higher)
        r2 = s1.grant_vote(latch, higher)
        fact("deterministic", r1 == r2)

        # --- malformed input refused by name; a refused vote is not one
        _refuses(wire.ProtocolError, "hand-built request refused",
                 lambda: s1.grant_vote(voter, ("request_vote", 1, "x")),
                 names=("stage_01",))
        _refuses(wire.ProtocolError, "wrong-kind request refused",
                 lambda: s1.grant_vote(
                     voter, wire.vote_reply(1, "a1", "a2", True)),
                 names=("stage_01",))
        broken = dict(wire.follower("a2"))
        del broken["config"]
        _refuses(wire.ProtocolError, "state missing config refused",
                 lambda: s1.grant_vote(broken, ask), names=("config",))
        fact("a refusal is granted=False, not an error",
             s1.grant_vote(voter, stale)[0][4] is False)

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_01: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
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

    COURSE = "consensus-from-scratch"

    STAGE = 2

    STUB_MESSAGE = "stage 2: implement start_election()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H6_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H6_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        for name in sorted(os.listdir(overlay)):
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
                raise AssertionError("%s: refusal %r does not name %s"
                                     % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h6_check02_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_02 as s2\n"
                    "for call in (lambda: s2.start_election(None),\n"
                    "             lambda: s2.tally(None, ())):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "print('not implemented yet')\n"
                    "raise SystemExit(42)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "wire.py"))
                    and os.path.isfile(os.path.join(p, "stage_02.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h6_check02_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import wire
        import stage_02 as s2

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

        # --- the world's pins, re-read
        must("majority table", [wire.majority(n) for n in range(1, 7)]
             == [1, 2, 2, 3, 3, 4])
        must("HEARTBEAT", wire.HEARTBEAT == 5)

        stub = 0
        for call in (lambda: s2.start_election(wire.follower("a1")),
                     lambda: s2.tally(wire.candidate("a1", 1), ())):
            try:
                call()
            except NotImplementedError as error:
                must("stub message", STUB_MESSAGE in str(error))
                stub += 1
        if stub:
            print("check_02: stage 2: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)
        must("start_election exists",
             callable(getattr(s2, "start_election", None)))
        must("tally exists", callable(getattr(s2, "tally", None)))

        cfg3 = ("a1", "a2", "a3")
        cfg5 = ("a1", "a2", "a3", "a4", "a5")

        # --- start_election: term, self-vote, timer
        node = wire.follower("a1", term=3, config=cfg3, elapsed=4)
        requests, cand = s2.start_election(node)
        fact("term advances", cand["term"] == 4)
        fact("self-vote latched", cand["voted_for"] == "a1")
        fact("fresh candidacy has no grants yet", cand["votes"] == ())
        fact("timer reset", cand["elapsed"] == 0)
        fact("role candidate", cand["role"] == "candidate")
        expect = wire.request_vote(4, "a1", 0, -1)
        fact("one request per peer, none to self",
             requests == (expect, expect))
        fact("requests carry term and candidate id",
             all(r[1] == 4 and r[2] == "a1" for r in requests))

        # --- a re-election raises the term again
        retry, cand2 = s2.start_election(cand)
        fact("re-election raises the term", cand2["term"] == 5)
        fact("re-election re-casts the self-vote",
             cand2["voted_for"] == "a1")

        # --- the claim is wire.last_entry, snapshot boundary included
        snap = wire.follower("a1", term=2, config=cfg3, log=(),
                             commit_index=-1, snapshot_at=(9, 6))
        requests, _ = s2.start_election(snap)
        fact("boundary pair travels in the request",
             requests[0] == wire.request_vote(3, "a1", 6, 9))
        tail = wire.follower("a1", term=2, config=cfg3,
                             log=((7, 5, "x=1"),), commit_index=7)
        requests, _ = s2.start_election(tail)
        fact("live tail end travels in the request",
             requests[0] == wire.request_vote(3, "a1", 5, 7))

        # --- tally: leader is a number a majority agreed on
        cand = wire.candidate("a1", 4, voted_for="a1", config=cfg5)
        role, state2 = s2.tally(
            cand, (wire.vote_reply(4, "a2", "a1", True),
                   wire.vote_reply(4, "a3", "a1", True)))
        fact("majority of distinct grants elects", role == "leader"
             and state2["role"] == "leader" and state2["id"] == "a1"
             and state2["term"] == 4)
        role, short = s2.tally(cand, (wire.vote_reply(4, "a2", "a1", True),))
        fact("one grant is short of a quorum of five",
             role == "candidate" and short["term"] == 4)
        fact("votes kept as a sorted tuple of distinct ids",
             short["votes"] == ("a1", "a2"))
        role, dup = s2.tally(cand, (wire.vote_reply(4, "a2", "a1", True),
                                    wire.vote_reply(4, "a2", "a1", True)))
        fact("the same voter twice is one grant",
             role == "candidate" and dup["votes"] == ("a1", "a2"))
        acc1, mid = s2.tally(cand, (wire.vote_reply(4, "a2", "a1", True),))
        role, done = s2.tally(mid, (wire.vote_reply(4, "a3", "a1", True),))
        fact("grants accumulate across batches to a quorum",
             role == "leader" and done["role"] == "leader")

        # --- replies that are not votes for this candidacy
        role, kept = s2.tally(cand, (wire.vote_reply(4, "a9", "a1", True),))
        fact("a grant from outside the config is ignored",
             role == "candidate" and "a9" not in kept["votes"])
        role, kept = s2.tally(
            cand, (wire.vote_reply(4, "a2", "a5", True),))
        fact("a grant addressed to another candidate is ignored",
             role == "candidate" and "a2" not in kept["votes"])
        role, kept = s2.tally(
            cand, (wire.vote_reply(3, "a2", "a1", True),))
        fact("a stale-term grant is ignored",
             role == "candidate" and "a2" not in kept["votes"])
        role, kept = s2.tally(
            cand, (wire.vote_reply(4, "a2", "a1", False),))
        fact("an equal-term denial keeps the candidacy",
             role == "candidate" and "a2" not in kept["votes"])

        # --- the term law BEFORE a majority can be counted
        role, demoted = s2.tally(
            cand, (wire.vote_reply(4, "a2", "a1", True),
                   wire.vote_reply(4, "a3", "a1", True),
                   wire.vote_reply(7, "a4", "a1", False)))
        fact("a higher term in the batch voids the election",
             role == "follower" and demoted["role"] == "follower")
        fact("the voided candidacy adopts the term and clears the latch",
             demoted["term"] == 7 and demoted["voted_for"] is None)

        # --- malformed inputs refused by name; purity and determinism
        _refuses(wire.ProtocolError, "start_election refuses a leader",
                 lambda: s2.start_election(
                     wire.leader("a1", 4, config=cfg3)),
                 names=("stage_02",))
        _refuses(wire.ProtocolError, "tally refuses a non-candidate",
                 lambda: s2.tally(wire.follower("a1", config=cfg3), ()),
                 names=("stage_02",))
        _refuses(wire.ProtocolError, "hand-built reply refused",
                 lambda: s2.tally(cand, (("vote_reply", 4, "a2"),)),
                 names=("stage_02",))
        _refuses(wire.ProtocolError, "wrong-kind reply refused",
                 lambda: s2.tally(cand, (wire.request_vote(4, "a2", 0, -1),)),
                 names=("stage_02",))
        fresh = wire.candidate("a1", 4, voted_for="a1", config=cfg5)
        expected = dict(fresh)
        s2.tally(fresh, (wire.vote_reply(4, "a2", "a1", True),))
        fact("tally leaves the caller's candidate untouched",
             fresh == expected)
        start = wire.follower("a1", term=3, config=cfg3, elapsed=4)
        wanted = dict(start)
        s2.start_election(start)
        fact("start_election leaves the caller's state untouched",
             start == wanted)
        fact("deterministic",
             s2.tally(cand, (wire.vote_reply(4, "a2", "a1", True),))
             == s2.tally(cand, (wire.vote_reply(4, "a2", "a1", True),)))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_02: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
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

    COURSE = "consensus-from-scratch"

    STAGE = 3

    STUB_MESSAGE = "stage 3: implement become_leader()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H6_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H6_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        for name in sorted(os.listdir(overlay)):
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
                raise AssertionError("%s: refusal %r does not name %s"
                                     % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h6_check03_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_03 as s3\n"
                    "for call in (lambda: s3.become_leader(None),\n"
                    "             lambda: s3.heartbeat(None),\n"
                    "             lambda: s3.observe_append(None, None),\n"
                    "             lambda: s3.observe_reply(None, None)):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "print('not implemented yet')\n"
                    "raise SystemExit(42)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "wire.py"))
                    and os.path.isfile(os.path.join(p, "stage_03.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h6_check03_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import wire
        import stage_03 as s3

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

        # --- the world's pins, re-read
        must("majority table", [wire.majority(n) for n in range(1, 7)]
             == [1, 2, 2, 3, 3, 4])
        must("HEARTBEAT", wire.HEARTBEAT == 5)

        stub = 0
        cfg3 = ("a1", "a2", "a3")
        for call in (
                lambda: s3.become_leader(wire.candidate("a1", 1,
                                                        config=cfg3)),
                lambda: s3.heartbeat(wire.leader("a1", 1, config=cfg3)),
                lambda: s3.observe_append(
                    wire.follower("a2", config=cfg3),
                    wire.append(1, "a1", 0, -1, (), -1)),
                lambda: s3.observe_reply(
                    wire.leader("a1", 1, config=cfg3),
                    wire.append_reply(1, "a2", -1, 0, leader="a1"))):
            try:
                call()
            except NotImplementedError as error:
                must("stub message", STUB_MESSAGE in str(error))
                stub += 1
        if stub:
            print("check_03: stage 3: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)
        for name in ("become_leader", "heartbeat", "observe_append",
                     "observe_reply"):
            must("%s exists" % name, callable(getattr(s3, name, None)))

        # --- become_leader: authority bookkeeping
        cand = wire.candidate("a1", 4, voted_for="a1", config=cfg3,
                              log=((0, 3, "x=1"), (1, 3, "y=2")),
                              commit_index=1)
        lead = s3.become_leader(cand)
        fact("role becomes leader", lead["role"] == "leader"
             and lead["term"] == 4)
        fact("matched starts empty of self and -1 per peer",
             "a1" not in lead["matched"]
             and lead["matched"] == {"a2": -1, "a3": -1})
        fact("next_index one past the last entry",
             lead["next_index"] == {"a2": 2, "a3": 2})
        fact("commit unchanged", lead["commit_index"] == 1)
        fact("timer starts fresh", lead["elapsed"] == 0)
        fact("log carried unchanged",
             lead["log"] == ((0, 3, "x=1"), (1, 3, "y=2")))

        # --- snapshot-relative tail
        snap_cand = wire.candidate("a1", 4, voted_for="a1", config=cfg3,
                                   log=((10, 7, "z=3"),), commit_index=10,
                                   snapshot_at=(9, 6))
        snap_lead = s3.become_leader(snap_cand)
        fact("boundary leader starts next_index past the tail",
             snap_lead["next_index"] == {"a2": 11, "a3": 11})
        # --- heartbeat: one empty APPEND per peer, prev at next_index-1
        beat = s3.heartbeat(lead)
        fact("one append per peer, none to self",
             len(beat) == 2 and all(m[0] == wire.APPEND and m[2] == "a1"
                                    for m in beat))
        fact("empty payload is a heartbeat",
             all(m[5] == () for m in beat))
        fact("prev at next_index - 1 with the tail's term",
             all(m[4] == 1 and m[3] == 3 for m in beat))
        fact("leader_commit rides along",
             all(m[6] == 1 for m in beat))
        walked = wire.leader("a1", 4, config=cfg3,
                             log=((0, 3, "x=1"), (1, 4, "y=2")),
                             commit_index=1,
                             matched={"a2": 0, "a3": -1},
                             next_index={"a2": 2, "a3": 1})
        beat = s3.heartbeat(walked)
        fact("each peer gets its own prev-anchor",
             sorted(m[4] for m in beat) == [0, 1])
        fact("the anchors carry the right terms",
             [m[3] for m in beat if m[4] == 0] == [3]
             and [m[3] for m in beat if m[4] == 1] == [4])
        boundary_lead = wire.leader("a1", 7, config=cfg3,
                                    log=((10, 7, "z=3"),), commit_index=10,
                                    snapshot_at=(9, 6),
                                    matched={"a2": 9, "a3": -1},
                                    next_index={"a2": 11, "a3": 10})
        beat = s3.heartbeat(boundary_lead)
        a3msg = [m for m in beat if m[4] == 9][0]
        fact("prev at the snapshot boundary takes the boundary term",
             a3msg[3] == 6)
        a2msg = [m for m in beat if m[4] == 10][0]
        fact("prev inside the tail takes the entry's term",
             a2msg[3] == 7)


        # --- observe_append: accept law
        fol = wire.follower("a2", term=4, config=cfg3, elapsed=5)
        msg = wire.append(4, "a1", 0, -1, (), -1)
        reply, fol2 = s3.observe_append(fol, msg)
        fact("accepted heartbeat resets the timer", fol2["elapsed"] == 0)
        fact("leader adopted as voted_for when unset",
             fol2["voted_for"] == "a1")
        fact("agree reply carries matched at the log's end",
             reply == wire.append_reply(4, "a2", -1, 0, leader="a1"))

        # --- the term law before everything else
        hot = wire.follower("a2", term=4, voted_for="a1", config=cfg3,
                            elapsed=2)
        reply, fol2 = s3.observe_append(hot, wire.append(6, "a3", 0, -1, (),
                                                         -1))
        fact("higher term adopted", fol2["term"] == 6)
        fact("higher-term adoption clears the vote then re-latches to "
             "the sender", fol2["voted_for"] == "a3")
        fact("reply answers at the new term", reply[1] == 6)

        rival = wire.candidate("a2", 4, voted_for="a2", config=cfg3,
                               elapsed=3)
        reply, fol2 = s3.observe_append(
            rival, wire.append(4, "a1", 0, -1, (), -1))
        fact("a candidate standing down to a real leader",
             fol2["role"] == "follower" and fol2["elapsed"] == 0)

        # --- refusals: stale sender, foreign same-term leader
        stale = wire.follower("a2", term=4, config=cfg3, elapsed=3)
        reply, out = s3.observe_append(stale,
                                       wire.append(3, "a1", 0, -1, (), -1))
        fact("stale-term append refused",
             reply == wire.append_reply(4, "a2", -1, 0, leader="a1"))
        fact("refusal keeps the timer", out["elapsed"] == 3)
        fact("refusal keeps the term", out["term"] == 4)
        foreign = wire.leader("a5", 4, config=cfg3, log=((0, 3, "q=9"),),
                              commit_index=0)
        reply, out = s3.observe_append(
            foreign, wire.append(4, "a1", 0, 0, (), 0))
        fact("same-term foreign leader refused, never demotes",
             out["role"] == "leader" and out["term"] == 4)
        fact("the refusal is an append_reply deny",
             reply == wire.append_reply(4, "a5", 0, 1, leader="a1"))
        demoted_lead = wire.leader("a5", 4, config=cfg3,
                                   log=((0, 3, "q=9"),), commit_index=0)
        reply, out = s3.observe_append(
            demoted_lead, wire.append(6, "a1", 3, 0, (), 0))
        fact("a higher term ends the receiver's leadership itself",
             out["role"] == "follower" and out["term"] == 6
             and out["voted_for"] == "a1"
             and reply == wire.append_reply(6, "a5", 0, 1, leader="a1"))

        # --- prev window: out-of-window anchors deny, timer still reset
        ahead = wire.follower("a2", term=4, config=cfg3,
                              log=((0, 3, "x=1"),), commit_index=0)
        reply, out = s3.observe_append(ahead,
                                       wire.append(4, "a1", 0, 5, (), 0))
        fact("prev past the tail denied",
             reply[3] == 0 and reply[4] == 1)
        fact("the deny still proves life (timer reset)",
             out["elapsed"] == 0)
        far = wire.follower("a2", term=4, config=cfg3,
                            log=((10, 7, "z=3"),), commit_index=10,
                            snapshot_at=(9, 6))
        reply, out = s3.observe_append(far, wire.append(4, "a1", 7, 1, (),
                                                        10))
        fact("prev below the window denied at the boundary end",
             reply[3] == 10 and reply[4] == 11)

        # --- prev-term mismatch: stage 3 DENIES, does not truncate
        mixed = wire.follower("a2", term=4, config=cfg3,
                              log=((0, 3, "x=1"), (1, 4, "bad=1")),
                              commit_index=0)
        reply, out = s3.observe_append(mixed, wire.append(4, "a1", 9, 1, (),
                                                          0))
        fact("pair mismatch denied without truncating",
             reply[3] == 1 and reply[4] == 2
             and out["log"] == ((0, 3, "x=1"), (1, 4, "bad=1")))

        # --- commit line: advances with a real leader, clamps to the tail
        committed = wire.follower("a2", term=4, config=cfg3,
                                  log=((0, 3, "x=1"), (1, 3, "y=2")),
                                  commit_index=0)
        reply, out = s3.observe_append(committed,
                                       wire.append(4, "a1", 3, 1, (), 1))
        fact("leader_commit advances the follower", out["commit_index"] == 1)
        reply, out = s3.observe_append(committed,
                                       wire.append(4, "a1", 3, 1, (), 99))
        fact("leader_commit past the tail clamps",
             out["commit_index"] == 1)

        # --- observe_reply: the leader reads what came back
        lead = s3.become_leader(wire.candidate("a1", 4, voted_for="a1",
                                               config=cfg3))
        got = s3.observe_reply(lead, wire.append_reply(4, "a2", 1, 2,
                                                      leader="a1"))
        fact("matched recorded", got["matched"]["a2"] == 1)
        fact("conflict walks next_index", got["next_index"]["a2"] == 2)
        fact("the other peer untouched", got["matched"]["a3"] == -1)
        demoted = s3.observe_reply(lead, wire.append_reply(7, "a3", -1, 0,
                                                           leader="a1"))
        fact("higher term steps the leader down",
             demoted["role"] == "follower" and demoted["term"] == 7
             and demoted["elapsed"] == 0)
        ignored = s3.observe_reply(lead, wire.append_reply(2, "a2", 5, 6,
                                                           leader="a1"))
        fact("stale-term reply ignored", ignored == dict(lead))
        stranger = s3.observe_reply(lead, wire.append_reply(4, "a9", 1, 2,
                                                            leader="a1"))
        fact("reply from outside the config ignored",
             stranger == dict(lead))

        # --- malformed inputs refused by name
        _refuses(wire.ProtocolError, "hand-built append refused",
                 lambda: s3.observe_append(fol, ("append", 1, "a1")),
                 names=("stage_03",))
        _refuses(wire.ProtocolError, "wrong-kind refused",
                 lambda: s3.observe_append(
                     fol, wire.vote_reply(1, "a1", "a2", True)),
                 names=("stage_03",))
        _refuses(wire.ProtocolError, "entries belong to stage 4",
                 lambda: s3.observe_append(
                     fol, wire.append(4, "a1", 0, -1, ((0, 4, "x=1"),),
                                      -1)),
                 names=("stage_03", "stage 4"))
        _refuses(wire.ProtocolError, "become_leader refuses a follower",
                 lambda: s3.become_leader(wire.follower("a1", config=cfg3)),
                 names=("stage_03",))
        _refuses(wire.ProtocolError, "heartbeat refuses a follower",
                 lambda: s3.heartbeat(
                     wire.follower("a1", config=cfg3)),
                 names=("stage_03",))
        _refuses(wire.ProtocolError, "observe_reply refuses a follower",
                 lambda: s3.observe_reply(
                     wire.follower("a1", config=cfg3),
                     wire.append_reply(1, "a2", -1, 0, leader="a1")),
                 names=("stage_03",))
        _refuses(wire.ProtocolError, "hand-built reply refused",
                 lambda: s3.observe_reply(lead, ("append_reply", 4, "a2")),
                 names=("stage_03",))

        # --- purity and determinism
        hold = wire.follower("a2", term=4, config=cfg3, elapsed=5)
        wanted = dict(hold)
        s3.observe_append(hold, msg)
        fact("observe_append leaves the caller's state untouched",
             hold == wanted)
        hold = s3.become_leader(wire.candidate("a1", 4, voted_for="a1",
                                               config=cfg3))
        wanted = dict(hold)
        s3.observe_reply(hold, wire.append_reply(4, "a2", 0, 1,
                                                 leader="a1"))
        fact("observe_reply leaves the caller's leader untouched",
             hold == wanted)
        wanted = dict(lead)
        s3.heartbeat(lead)
        fact("heartbeat leaves the leader untouched", lead == wanted)
        fact("deterministic",
             s3.observe_reply(lead, wire.append_reply(4, "a2", 1, 2,
                                                      leader="a1"))
             == s3.observe_reply(lead, wire.append_reply(4, "a2", 1, 2,
                                                         leader="a1")))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_03: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "consensus-from-scratch"

    STAGE = 4

    STUB_MESSAGE = "stage 4: implement client_submit()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H6_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H6_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        for name in sorted(os.listdir(overlay)):
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
                raise AssertionError("%s: refusal %r does not name %s"
                                     % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h6_check04_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_04 as s4\n"
                    "for call in (lambda: s4.client_submit(None, None),\n"
                    "             lambda: s4.broadcast_append(None),\n"
                    "             lambda: s4.handle_append(None, None)):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "print('not implemented yet')\n"
                    "raise SystemExit(42)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "wire.py"))
                    and os.path.isfile(os.path.join(p, "stage_04.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h6_check04_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import wire
        import stage_04 as s4

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

        # --- the world's pins, re-read
        must("majority table", [wire.majority(n) for n in range(1, 7)]
             == [1, 2, 2, 3, 3, 4])
        must("TIMEOUTS", wire.TIMEOUTS == (("a1", 11), ("a2", 7), ("a3", 9),
                                           ("a4", 5), ("a5", 13)))

        stub = 0
        cfg3 = ("a1", "a2", "a3")
        for call in (
                lambda: s4.client_submit(wire.leader("a1", 1, config=cfg3),
                                         "x=1"),
                lambda: s4.broadcast_append(
                    wire.leader("a1", 1, config=cfg3)),
                lambda: s4.handle_append(
                    wire.follower("a2", config=cfg3),
                    wire.append(1, "a1", 0, -1, (), -1))):
            try:
                call()
            except NotImplementedError as error:
                must("stub message", STUB_MESSAGE in str(error))
                stub += 1
        if stub:
            print("check_04: stage 4: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)
        for name in ("client_submit", "broadcast_append", "handle_append"):
            must("%s exists" % name, callable(getattr(s4, name, None)))

        # --- client_submit: the order is the index
        lead = wire.leader("a1", 5, config=cfg3, log=((0, 3, "x=1"),),
                           commit_index=0, matched={"a2": 0, "a3": -1},
                           next_index={"a2": 1, "a3": 1})
        lead2, msgs = s4.client_submit(lead, "y=2")
        fact("entry appended at last_index+1 with the leader's term",
             lead2["log"] == ((0, 3, "x=1"), (1, 5, "y=2")))
        fact("the append precedes the broadcast: msgs carry the tail",
             len(msgs) == 2 and all(m[5] and m[5][-1] == (1, 5, "y=2")
                                    for m in msgs))
        fact("each peer's slice respects next_index",
             sorted(len(m[5]) for m in msgs) == [1, 1])
        fact("commit rides at the leader's line",
             all(m[6] == 0 for m in msgs))
        fact("the caller's leader untouched",
             lead["log"] == ((0, 3, "x=1"),))
        walked = wire.leader("a1", 5, config=cfg3,
                             log=((0, 3, "x=1"), (1, 5, "y=2")),
                             commit_index=0, matched={"a2": 0, "a3": -1},
                             next_index={"a2": 1, "a3": 2})
        _new, msgs = s4.client_submit(walked, "z=3")
        fact("a walked-back peer re-receives from its own next_index",
             len([m for m in msgs if m[4] == 0][0][5]) == 2)
        fact("the peer already caught up gets only the new entry",
             len([m for m in msgs if m[4] == 1][0][5]) == 1)

        # --- snapshot-relative numbering
        snap_lead = wire.leader("a1", 8, config=cfg3,
                                log=((10, 7, "z=3"),), commit_index=10,
                                snapshot_at=(9, 6),
                                matched={"a2": 10, "a3": 10},
                                next_index={"a2": 11, "a3": 11})
        snap_lead2, msgs = s4.client_submit(snap_lead, "w=4")
        fact("boundary leader numbers from the tail, not len()",
             snap_lead2["log"][-1] == (11, 8, "w=4"))
        fact("the broadcast anchors inside the tail",
             msgs[0][4] == 10 and msgs[0][3] == 7)
        fact("the boundary slice is the new entry only",
             all(m[5] == ((11, 8, "w=4"),) for m in msgs))
        lagging = wire.leader("a1", 8, config=cfg3,
                              log=((10, 7, "z=3"), (11, 8, "w=4")),
                              commit_index=10, snapshot_at=(9, 6),
                              matched={"a2": 10, "a3": 6},
                              next_index={"a2": 12, "a3": 10})
        msgs = s4.broadcast_append(lagging)
        by_anchor = {m[4]: m for m in msgs}
        fact("a peer at the boundary anchors on the snapshot's term",
             by_anchor[9][3] == 6)
        fact("its slice is the whole tail",
             by_anchor[9][5] == ((10, 7, "z=3"), (11, 8, "w=4")))

        # --- reads and membership refuse
        _refuses(wire.ProtocolError, "get is not replicated",
                 lambda: s4.client_submit(lead, "get x"),
                 names=("stage_04",))
        _refuses(wire.ProtocolError, "unknown member refused",
                 lambda: s4.client_submit(lead, "members:a1,a9"),
                 names=("stage_04", "a9"))
        ok_lead, _m = s4.client_submit(lead, "members:a1,a2,a3")
        fact("known members accepted as an entry",
             ok_lead["log"][-1][2] == "members:a1,a2,a3")
        _refuses(wire.ProtocolError, "client_submit refuses a follower",
                 lambda: s4.client_submit(wire.follower("a2", config=cfg3),
                                          "x=1"),
                 names=("stage_04",))

        # --- handle_append: install
        fol = wire.follower("a2", term=5, config=cfg3, elapsed=4)
        tail = ((0, 3, "x=1"), (1, 5, "y=2"))
        reply, fol2 = s4.handle_append(
            fol, wire.append(5, "a1", 0, -1, tail, 0))
        fact("the tail is installed", fol2["log"] == tail)
        fact("commit advances with the leader's line",
             fol2["commit_index"] == 0)
        fact("the reply agrees at the new end",
             reply == wire.append_reply(5, "a2", 1, 2, leader="a1"))
        fact("replication proves life: timer reset", fol2["elapsed"] == 0)
        fact("the leader is adopted into voted_for",
             fol2["voted_for"] == "a1")

        # --- overwriting the old leader's leftovers
        ghost = wire.follower("a2", term=5, config=cfg3,
                              log=((0, 3, "x=1"), (1, 2, "bad=1"),
                                   (2, 2, "bad2=2")), commit_index=0)
        reply, out = s4.handle_append(
            ghost, wire.append(5, "a1", 3, 0, ((1, 5, "y=2"),), 1))
        fact("a different term at the same index is overwritten",
             out["log"] == ((0, 3, "x=1"), (1, 5, "y=2")))
        fact("the reply reports the new end", reply[3] == 1)

        # --- prev mismatch truncates BY TERM, commit follows below cut
        diverged = wire.follower("a2", term=5, config=cfg3,
                                 log=((0, 3, "x=1"), (1, 4, "old=1"),
                                      (2, 4, "old2=2"), (3, 7, "ghost=9")),
                                 commit_index=1)
        reply, out = s4.handle_append(
            diverged, wire.append(5, "a1", 4, 3, ((4, 5, "new=1"),), 1))
        fact("the suffix from the first prev_term entry is dropped",
             out["log"] == ((0, 3, "x=1"),))
        fact("matched sits at the last kept index", reply[3] == 0)
        fact("conflict is one past it", reply[4] == 1)
        fact("the commit line is pulled back below the cut",
             out["commit_index"] == 0)
        # the leader walks next_index back to conflict and retries:
        reply, out2 = s4.handle_append(
            out, wire.append(5, "a1", 3, 0, ((1, 4, "old=1"),
                                             (2, 4, "old2=2"),
                                             (3, 5, "new=1")), 3))
        fact("one retry per conflicting term converges",
             out2["log"] == ((0, 3, "x=1"), (1, 4, "old=1"),
                             (2, 4, "old2=2"), (3, 5, "new=1")))
        fact("the retry raises the commit line",
             out2["commit_index"] == 3)

        # --- leader_commit past the tail clamps, never trusted blindly
        shallow = wire.follower("a2", term=5, config=cfg3,
                                log=((0, 3, "x=1"),), commit_index=0)
        reply, out = s4.handle_append(
            shallow, wire.append(5, "a1", 3, 0, ((1, 5, "y=2"),), 42))
        fact("leader_commit past the tail clamps to the last entry",
             out["commit_index"] == 1)

        # --- retransmits are free: the same tail twice is idempotent
        twice = wire.follower("a2", term=5, config=cfg3, log=tail,
                              commit_index=1)
        reply, out = s4.handle_append(twice,
                                      wire.append(5, "a1", 0, -1, tail, 1))
        fact("duplicate install leaves the log identical",
             out["log"] == tail and out["commit_index"] == 1)

        # --- a boundary-anchored install is stage 8's SNAPSHOT traffic:
        # the APPEND path refuses it at the trimmed node's boundary end
        trimmed = wire.follower("a2", term=5, config=cfg3, log=(),
                                commit_index=-1, snapshot_at=(9, 6))
        reply, out = s4.handle_append(
            trimmed, wire.append(5, "a1", 6, 9, ((10, 5, "n=1"),), 10))
        fact("anchor below the window is refused, not guessed",
             reply == wire.append_reply(5, "a2", 9, 10, leader="a1")
             and out["log"] == ())

        # --- term law first
        hot = wire.follower("a2", term=4, voted_for="a1", config=cfg3,
                            elapsed=2)
        reply, out = s4.handle_append(
            hot, wire.append(6, "a3", 0, -1, ((0, 6, "t=1"),), -1))
        fact("higher term adopted before anything else",
             out["term"] == 6 and out["role"] == "follower")
        fact("the latch cleared then re-set for the sender",
             out["voted_for"] == "a3")

        stale = wire.follower("a2", term=5, config=cfg3, elapsed=3)
        reply, out = s4.handle_append(stale, wire.append(3, "a1", 0, -1, (),
                                                         -1))
        fact("stale sender refused at our term",
             reply == wire.append_reply(5, "a2", -1, 0, leader="a1"))
        fact("a refusal does NOT reset the timer", out["elapsed"] == 3)
        fact("a refusal installs nothing", out["log"] == ())

        rival = wire.leader("a5", term=5, config=cfg3,
                            log=((0, 3, "q=9"),), commit_index=0)
        reply, out = s4.handle_append(rival, wire.append(5, "a1", 3, 0,
                                                         ((1, 5, "n=1"),),
                                                         0))
        fact("a same-term rival is refused, never obeyed",
             out["role"] == "leader" and out["log"] == ((0, 3, "q=9"),))

        cand = wire.candidate("a2", term=5, voted_for="a2", config=cfg3,
                              votes=("a2",), elapsed=1)
        reply, out = s4.handle_append(cand,
                                      wire.append(5, "a1", 0, -1, tail, 1))
        fact("a candidate stands down and installs",
             out["role"] == "follower" and out["log"] == tail)

        # --- malformed input refused; purity; determinism
        _refuses(wire.ProtocolError, "hand-built append refused",
                 lambda: s4.handle_append(fol, ("append", 5, "a1")),
                 names=("stage_04",))
        _refuses(wire.ProtocolError, "wrong kind refused",
                 lambda: s4.handle_append(
                     fol, wire.vote_reply(5, "a1", "a2", True)),
                 names=("stage_04",))
        hold = wire.follower("a2", term=5, config=cfg3, elapsed=4)
        wanted = dict(hold)
        s4.handle_append(hold, wire.append(5, "a1", 0, -1, tail, 0))
        fact("handle_append leaves the caller's state untouched",
             hold == wanted)
        wanted = dict(lead)
        s4.client_submit(lead, "y=2")
        fact("client_submit leaves the caller's leader untouched",
             lead == wanted)
        fact("deterministic",
             s4.handle_append(hold, wire.append(5, "a1", 0, -1, tail, 0))
             == s4.handle_append(hold, wire.append(5, "a1", 0, -1, tail, 0)))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_04: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
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

    COURSE = "consensus-from-scratch"

    STAGE = 5

    STUB_MESSAGE = "stage 5: implement advance_commit()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H6_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H6_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        for name in sorted(os.listdir(overlay)):
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
                raise AssertionError("%s: refusal %r does not name %s"
                                     % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h6_check05_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_05 as s5\n"
                    "try:\n"
                    "    s5.advance_commit(None)\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "print('not implemented yet')\n"
                    "raise SystemExit(42)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "wire.py"))
                    and os.path.isfile(os.path.join(p, "stage_05.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h6_check05_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import wire
        import stage_05 as s5

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

        must("majority table", [wire.majority(n) for n in range(1, 7)]
             == [1, 2, 2, 3, 3, 4])

        stub = 0
        try:
            s5.advance_commit(wire.leader("a1", 1, config=("a1",)))
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_05: stage 5: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)
        must("advance_commit exists", callable(getattr(s5, "advance_commit",
                                                       None)))

        cfg3 = ("a1", "a2", "a3")

        # --- majority of the config, own term, leader's copy counted
        lead = wire.leader("a1", 5, config=cfg3,
                           log=((0, 5, "x=1"), (1, 5, "y=2"), (2, 5, "z=3")),
                           commit_index=-1,
                           matched={"a2": 1, "a3": -1},
                           next_index={"a2": 2, "a3": 3})
        out = s5.advance_commit(lead)
        fact("self plus one follower is a 3-node majority",
             out["commit_index"] == 1)
        fact("an index short of a majority is not committed",
             out["commit_index"] < 2)
        fact("the rest of the leader survives the pass",
             out["log"] == lead["log"] and out["matched"] == lead["matched"]
             and out["term"] == 5 and out["id"] == "a1")

        # --- the classic figure: counting an OLD term is forbidden
        fresh = wire.leader("a2", 3, config=cfg3,
                            log=((0, 2, "x=1"), (1, 2, "y=2"),
                                 (2, 2, "ghost=9")),
                            commit_index=-1,
                            matched={"a1": 2, "a3": 2},
                            next_index={"a1": 3, "a3": 3})
        out = s5.advance_commit(fresh)
        fact("a term-3 leader will not commit a term-2 entry by counting",
             out["commit_index"] == -1)
        grown = wire.leader("a2", 3, config=cfg3,
                            log=((0, 2, "x=1"), (1, 2, "y=2"),
                                 (2, 2, "ghost=9"), (3, 3, "new=1")),
                            commit_index=-1,
                            matched={"a1": 3, "a3": 3},
                            next_index={"a1": 4, "a3": 4})
        out = s5.advance_commit(grown)
        fact("a current-term entry carries the old ones in",
             out["commit_index"] == 3)
        only_old = wire.leader("a2", 3, config=cfg3,
                               log=((3, 3, "new=1"),), commit_index=2,
                               snapshot_at=(2, 2),
                               matched={"a1": 3, "a3": -1},
                               next_index={"a1": 4, "a3": 1})
        out = s5.advance_commit(only_old)
        fact("a current-term tail commits even with the prefix trimmed",
             out["commit_index"] == 3)
        cfg5 = ("a1", "a2", "a3", "a4", "a5")
        thin = wire.leader("a1", 5, config=cfg5,
                           log=((0, 5, "x=1"), (1, 5, "y=2")),
                           commit_index=-1, matched={"a2": 1},
                           next_index={"a2": 2})
        fact("two of five is not a majority",
             s5.advance_commit(thin)["commit_index"] == -1)
        broad = wire.leader("a1", 5, config=cfg5,
                            log=((0, 5, "x=1"), (1, 5, "y=2"),
                                 (2, 5, "z=3")),
                            commit_index=-1,
                            matched={"a2": 2, "a3": 0},
                            next_index={"a2": 3, "a3": 1})
        fact("three of five commit up to the shallowest answer",
             s5.advance_commit(broad)["commit_index"] == 0)
        # --- monotone: commit never rolls back
        ahead = wire.leader("a1", 5, config=cfg3,
                            log=((0, 5, "x=1"),), commit_index=0,
                            matched={"a2": -1, "a3": -1},
                            next_index={"a2": 1, "a3": 1})
        out = s5.advance_commit(ahead)
        fact("a lost majority does not undo a commit",
             out["commit_index"] == 0)

        # --- single-node config: the leader's own copy commits
        solo = wire.leader("a1", 9, config=("a1",),
                           log=((0, 9, "x=1"),), commit_index=-1,
                           matched={}, next_index={})
        out = s5.advance_commit(solo)
        fact("one node is a majority of one", out["commit_index"] == 0)

        # --- only the config votes
        cfg2 = ("a1", "a2")
        outsider = wire.leader("a1", 5, config=cfg2,
                               log=((0, 5, "x=1"),), commit_index=-1,
                               matched={"a2": -1, "a3": 0},
                               next_index={"a2": 1, "a3": 1})
        out = s5.advance_commit(outsider)
        fact("a peer outside the config does not vote",
             out["commit_index"] == -1)
        silent = wire.leader("a1", 5, config=cfg2,
                             log=((0, 5, "x=1"),), commit_index=-1,
                             matched={"a2": 0}, next_index={"a2": 1})
        out = s5.advance_commit(silent)
        fact("the leader plus one config peer commits",
             out["commit_index"] == 0)

        # --- snapshot-relative scan
        trimmed = wire.leader("a1", 8, config=cfg3,
                              log=((10, 7, "z=3"), (11, 8, "w=4")),
                              commit_index=9, snapshot_at=(9, 6),
                              matched={"a2": 11, "a3": 11},
                              next_index={"a2": 12, "a3": 12})
        out = s5.advance_commit(trimmed)
        fact("a boundary leader counts its tail, not len()",
             out["commit_index"] == 11)

        # --- the role guard and purity
        _refuses(wire.ProtocolError, "advance_commit refuses a follower",
                 lambda: s5.advance_commit(wire.follower("a2", config=cfg3)),
                 names=("stage_05",))
        hold = wire.leader("a1", 5, config=cfg3, log=((0, 5, "x=1"),),
                           commit_index=-1, matched={"a2": 0, "a3": 0},
                           next_index={"a2": 1, "a3": 1}, elapsed=3)
        wanted = dict(hold)
        s5.advance_commit(hold)
        fact("the caller's leader is untouched", hold == wanted)
        fact("deterministic", s5.advance_commit(hold) == s5.advance_commit(hold))
        kept = wire.leader("a1", 5, config=cfg3, log=(), commit_index=-1,
                           matched={}, next_index={}, elapsed=4,
                           old_config=("a1", "a2", "a3"))
        out = s5.advance_commit(kept)
        fact("the rebuild preserves elapsed and old_config",
             out["elapsed"] == 4 and out["old_config"] == ("a1", "a2", "a3")
             and out["snapshot_at"] is None)

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_05: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
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

    COURSE = "consensus-from-scratch"

    STAGE = 6

    STUB_MESSAGE = "stage 6: implement check_request()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H6_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H6_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        for name in sorted(os.listdir(overlay)):
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
                raise AssertionError("%s: refusal %r does not name %s"
                                     % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h6_check06_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_06 as s6\n"
                    "for call in (lambda: s6.check_request(None, None),\n"
                    "             lambda: s6.same_term_stale(None, None)):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "print('not implemented yet')\n"
                    "raise SystemExit(42)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "wire.py"))
                    and os.path.isfile(os.path.join(p, "stage_06.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h6_check06_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import wire
        import stage_06 as s6

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

        stub = 0
        cfg3 = ("a1", "a2", "a3")
        for call in (lambda: s6.check_request(
                         wire.follower("a2", config=cfg3),
                         wire.append(1, "a1", 0, -1, (), -1)),
                     lambda: s6.same_term_stale(
                         wire.leader("a1", 1, config=cfg3),
                         wire.append_reply(1, "a2", -1, 0))):
            try:
                call()
            except NotImplementedError as error:
                must("stub message", STUB_MESSAGE.split("()")[0] in str(error))
                stub += 1
        if stub:
            print("check_06: stage 6: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)
        for name in ("check_request", "same_term_stale"):
            must("%s exists" % name, callable(getattr(s6, name, None)))

        cfg3 = ("a1", "a2", "a3")

        # --- the door: higher term adopts, from any kind
        fol = wire.follower("a2", term=4, voted_for="a1", config=cfg3,
                            log=((0, 3, "x=1"),), commit_index=0,
                            elapsed=6)
        for msg in (wire.request_vote(7, "a3", 3, 0),
                    wire.vote_reply(7, "a1", "a2", True),
                    wire.append(7, "a1", 3, 0, (), 0),
                    wire.append_reply(7, "a1", 0, 1),
                    wire.snapshot(7, "a1", 3, 0, ()),
                    wire.snapshot_reply(7, "a1", 0)):
            accept, out = s6.check_request(fol, msg)
            fact("higher term accepted at the door", accept)
            fact("the term is adopted before the kind is handled",
                 out["term"] == 7 and out["role"] == "follower")
            fact("the election latch and the heartbeat clock reset",
                 out["voted_for"] is None and out["elapsed"] == 0)
            fact("the durable parts ride through the step down",
                 out["log"] == fol["log"]
                 and out["commit_index"] == 0
                 and out["config"] == cfg3)
        accept, out = s6.check_request(fol, wire.request_vote(4, "a3",
                                                              3, 0))
        fact("equal term passes through", accept and out["term"] == 4)
        fact("equal term changes nothing", out == fol)
        accept, out = s6.check_request(fol, wire.append(3, "a1", 0, -1,
                                                        (), -1))
        fact("lower term is refused, not ignored", not accept)
        fact("a refusal leaves the state untouched", out == fol)
        fact("the caller's follower is never mutated",
             fol["term"] == 4 and fol["elapsed"] == 6)

        # --- a leader downgrades through the same door
        lead = wire.leader("a1", 5, config=cfg3, log=((0, 5, "x=1"),),
                           commit_index=0, matched={"a2": 0, "a3": -1},
                           next_index={"a2": 1, "a3": 1})
        accept, out = s6.check_request(lead, wire.append_reply(9, "a2", 0, 1))
        fact("a higher-term reply deposes the leader",
             accept and out["role"] == "follower" and out["term"] == 9)
        fact("the downgrade keeps the leader's log and commit line",
             out["log"] == lead["log"] and out["commit_index"] == 0)

        # --- a candidate steps down at the door too
        cand = wire.candidate("a2", term=5, voted_for="a2", config=cfg3,
                              votes=("a2",), elapsed=3)
        accept, out = s6.check_request(cand, wire.request_vote(6, "a5",
                                                               5, 2))
        fact("a candidate hearing a newer term becomes follower",
             accept and out["role"] == "follower"
             and out["voted_for"] is None and out["elapsed"] == 0)

        # --- malformed input at the door
        _refuses(wire.ProtocolError, "hand-built tuple refused",
                 lambda: s6.check_request(fol, ("append", 5)),
                 names=("stage_06",))
        _refuses(wire.ProtocolError, "unknown kind refused",
                 lambda: s6.check_request(fol, ("heartbeat", 5, "a1")),
                 names=("stage_06",))
        _refuses(wire.ProtocolError, "bool term refused",
                 lambda: s6.check_request(fol, ("append", True)),
                 names=("stage_06",))
        _refuses(wire.ProtocolError, "negative term refused",
                 lambda: s6.check_request(
                     fol, ("append", -1, "a1", 0, -1, (), -1)),
                 names=("stage_06",))

        # --- same_term_stale: strict evidence
        seen = wire.leader("a1", 5, config=cfg3,
                           log=((0, 5, "x=1"), (1, 5, "y=2")),
                           commit_index=1, matched={"a2": 1, "a3": -1},
                           next_index={"a2": 2, "a3": 1})
        fact("a denial at a higher term is supersession",
             s6.same_term_stale(seen, wire.append_reply(6, "a2", 1, 2)))
        fact("a denial at a lower term is not about us",
             not s6.same_term_stale(seen, wire.append_reply(4, "a2", 1, 2)))
        fact("regressed below the commit line it once acknowledged: stale",
             s6.same_term_stale(seen, wire.append_reply(5, "a2", 0, 1)))
        fact("a lagging peer that never acknowledged the line proves "
             "nothing",
             not s6.same_term_stale(seen, wire.append_reply(5, "a3", -1, 0)))
        fact("advancing is never evidence",
             not s6.same_term_stale(seen, wire.append_reply(5, "a2", 1, 2)))
        fact("holding the line is never evidence",
             not s6.same_term_stale(seen, wire.snapshot_reply(5, "a2", 1)))
        past = wire.leader("a1", 5, config=cfg3,
                           log=((0, 5, "x=1"), (1, 5, "y=2"),
                                (2, 5, "z=3"), (3, 5, "w=4"),
                                (4, 5, "v=5"), (5, 5, "u=6")),
                           commit_index=5, matched={"a2": 2, "a3": 5},
                           next_index={"a2": 3, "a3": 6})
        fact("regression below an UNCOMMITTED line is mere lagging",
             not s6.same_term_stale(past, wire.append_reply(5, "a2", 1, 2)))
        fact("but a higher-term denial from the same peer deposes",
             s6.same_term_stale(past, wire.append_reply(6, "a2", 1, 2)))
        fresh = wire.leader("a1", 5, config=cfg3,
                            log=((0, 5, "x=1"),), commit_index=-1,
                            matched={"a2": -1, "a3": -1},
                            next_index={"a2": 1, "a3": 1})
        fact("nothing regressed on a fresh leader",
             not s6.same_term_stale(fresh, wire.append_reply(5, "a2", -1, 0)))

        # --- the chain: evidence + the door ends in follower
        evidence = wire.append_reply(6, "a2", 0, 1)
        fact("a leader following the law steps down on supersession",
             s6.same_term_stale(seen, evidence)
             and s6.check_request(seen, evidence)[1]["role"] == "follower")

        # --- guards and purity
        _refuses(wire.ProtocolError, "same_term_stale refuses a follower",
                 lambda: s6.same_term_stale(fol, wire.append_reply(5, "a2",
                                                                  0, 1)),
                 names=("stage_06",))
        _refuses(wire.ProtocolError, "same_term_stale refuses a request",
                 lambda: s6.same_term_stale(seen, wire.append(5, "a1", 5, 0,
                                                              (), 0)),
                 names=("stage_06",))
        hold = dict(seen)
        s6.same_term_stale(seen, wire.append_reply(6, "a2", 1, 2))
        s6.check_request(seen, wire.append_reply(6, "a2", 1, 2))
        fact("the door and the judge never mutate the caller",
             seen == hold)
        fact("deterministic",
             s6.check_request(seen, wire.append(6, "a1", 0, -1, (), -1))
             == s6.check_request(seen, wire.append(6, "a1", 0, -1, (), -1)))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_06: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
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

    COURSE = "consensus-from-scratch"

    STAGE = 7

    STUB_MESSAGE = "stage 7: implement persist()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H6_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H6_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        for name in sorted(os.listdir(overlay)):
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
                raise AssertionError("%s: refusal %r does not name %s"
                                     % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h6_check07_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_07 as s7\n"
                    "for call in (lambda: s7.persist(None),\n"
                    "             lambda: s7.recover(None),\n"
                    "             lambda: s7.heal_from_leader(None, None)):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "print('not implemented yet')\n"
                    "raise SystemExit(42)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "wire.py"))
                    and os.path.isfile(os.path.join(p, "stage_07.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h6_check07_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import wire
        import disk
        import stage_07 as s7

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

        stub = 0
        cfg3 = ("a1", "a2", "a3")
        for call in (lambda: s7.persist(wire.follower("a2", config=cfg3)),
                     lambda: s7.recover(b"v1\na2\n5\n-\n-1\na1,a2,a3\n-\n"
                                        b"0;3;x=1"),
                     lambda: s7.heal_from_leader(
                         wire.follower("a2", config=cfg3),
                         wire.append(1, "a1", 0, -1, (), -1))):
            try:
                call()
            except NotImplementedError as error:
                must("stub message", "implement" in str(error))
                stub += 1
        if stub:
            print("check_07: stage 7: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)
        for name in ("persist", "recover", "heal_from_leader"):
            must("%s exists" % name, callable(getattr(s7, name, None)))

        # --- the image, line by line
        fol = wire.follower("a2", term=5, voted_for="a1", config=cfg3,
                            log=((0, 3, "x=1"), (1, 5, "y=2")),
                            commit_index=0, elapsed=4)
        saved = s7.persist(fol)
        fact("the image is bytes", isinstance(saved, bytes))
        lines = saved.decode("utf-8").split("\n")
        fact("version first", lines[0] == "v1")
        fact("every durable field has its own line",
             lines[1:7] == ["a2", "5", "a1", "0", "a1,a2,a3", "-"])
        fact("entries are index;term;command",
             lines[7:] == ["0;3;x=1", "1;5;y=2"])
        fact("volatile truth is not on the disk: no elapsed, no role",
             "4" not in lines[1:7] and "follower" not in saved.decode())
        fact("deterministic: the same state, the same bytes",
             s7.persist(fol) == saved)

        # --- round trip through the builders
        back = s7.recover(saved)
        fact("the round trip restores the durable truth",
             (back["id"], back["term"], back["voted_for"], back["log"],
              back["commit_index"], back["config"], back["snapshot_at"])
             == (fol["id"], fol["term"], fol["voted_for"], fol["log"],
                 fol["commit_index"], fol["config"], fol["snapshot_at"]))
        fact("a restart comes up FOLLOWER: role is volatile",
             back["role"] == "follower")
        fact("a restart comes up with a fresh clock", back["elapsed"] == 0)
        lead = wire.leader("a1", 5, config=cfg3, log=((0, 5, "x=1"),),
                           commit_index=0, matched={"a2": 0, "a3": -1},
                           next_index={"a2": 1, "a3": 1}, elapsed=2)
        back = s7.recover(s7.persist(lead))
        fact("a crashed leader recovers as a follower",
             back["role"] == "follower" and back["id"] == "a1"
             and back["log"] == lead["log"])
        fact("and the image re-persists byte-identical",
             s7.persist(back) == s7.persist(lead))
        snapped = wire.follower("a2", term=8, config=cfg3,
                                log=((10, 7, "z=3"),), commit_index=10,
                                snapshot_at=(9, 6))
        back = s7.recover(s7.persist(snapped))
        fact("the snapshot boundary survives",
             back["snapshot_at"] == (9, 6) and back["log"] == snapped["log"])
        blank = wire.follower("a2", config=cfg3)
        fact("an empty node round trips", s7.recover(s7.persist(blank))
             == wire.follower("a2", config=cfg3))

        # --- malformed images: the line is named, never half-read
        for bad, why in ((b"", "empty"), (b"v2\na2\n1\n-\n-1\na1\n-",
                                           "version"),
                         ("v1".encode("utf-16"), "utf-8"),
                         (b"", "empty again")):
            _refuses(wire.ProtocolError, "recover of %s image" % why,
                     lambda b=bad: s7.recover(b), names=("stage_07",))
        _refuses(wire.ProtocolError, "recover of a str image",
                 lambda: s7.recover("v1"), names=("stage_07",))
        _refuses(wire.ProtocolError, "recover of a short head",
                 lambda: s7.recover(b"v1\na2\n5\n-\n-1\na1,a2,a3"),
                 names=("stage_07", "line 6"))
        _refuses(wire.ProtocolError, "recover of a non-int term",
                 lambda: s7.recover(b"v1\na2\nx\n-\n-1\na1,a2,a3\n-"),
                 names=("stage_07", "line 2"))
        _refuses(wire.ProtocolError, "recover of a torn entry",
                 lambda: s7.recover(b"v1\na2\n5\n-\n-1\na1,a2,a3\n-\n"
                                    b"0;3"),
                 names=("stage_07", "line 7"))
        _refuses(wire.ProtocolError, "recover of a config hole",
                 lambda: s7.recover(b"v1\na2\n5\n-\n-1\na1,,a3\n-"),
                 names=("stage_07", "line 5"))
        _refuses(wire.ProtocolError, "recover of a window liar",
                 lambda: s7.recover(b"v1\na2\n5\n-\n7\na1,a2,a3\n-\n"
                                    b"0;3;x=1"),
                 names=("stage_07",))
        _refuses(wire.ProtocolError, "recover of a gappy log",
                 lambda: s7.recover(b"v1\na2\n5\n-\n-1\na1,a2,a3\n-\n"
                                    b"0;3;x=1\n2;5;z=3"),
                 names=("stage_07",))
        _refuses(wire.ProtocolError, "persist of a corpse",
                 lambda: s7.persist({"id": "a2", "term": 5,
                                     "voted_for": None, "log": (),
                                     "commit_index": 9, "config": cfg3,
                                     "snapshot_at": None}),
                 names=("stage_07",))

        # --- the real tear: disk.Disk.crash() loses the LAST record
        d = disk.Disk("a2")
        early = wire.follower("a2", term=5, config=cfg3,
                              log=((0, 3, "x=1"), (1, 5, "y=2")),
                              commit_index=1)
        late = wire.follower("a2", term=5, config=cfg3,
                             log=((0, 3, "x=1"), (1, 5, "y=2"),
                                  (2, 5, "z=3")),
                             commit_index=1)
        d.write(s7.persist(early))
        d.write(s7.persist(late))
        torn = d.crash()
        fact("the tear takes exactly the last record",
             torn == s7.persist(early) and d.read() == s7.persist(early))
        back = s7.recover(torn)
        fact("the committed prefix survives the tear",
             back["log"] == ((0, 3, "x=1"), (1, 5, "y=2"))
             and back["commit_index"] == 1)

        # --- heal: the leader resends the lost tail
        msg = wire.append(5, "a1", 5, 1, ((2, 5, "z=3"),), 1)
        reply, healed = s7.heal_from_leader(back, msg)
        fact("the healed node holds the whole log again",
             healed["log"] == late["log"])
        fact("the answer sits at the new boundary",
             reply == wire.append_reply(5, "a2", 2, 3, leader="a1"))
        fact("the commit line survived the restart: nothing re-undone",
             healed["commit_index"] == 1)

        # --- heal keeps a prefix the leader must WALK BACK over
        stale_log = wire.follower("a2", term=5, config=cfg3,
                                  log=((0, 3, "x=1"), (1, 4, "ghost=9")),
                                  commit_index=0)
        reply, healed = s7.heal_from_leader(
            stale_log, wire.append(5, "a1", 3, 0, ((1, 5, "y=2"),), 0))
        fact("a torn node with a divergent tail truncates, not appends",
             healed["log"] == ((0, 3, "x=1"), (1, 5, "y=2")))

        # --- heal on a higher term: the term law still runs first
        reply, healed = s7.heal_from_leader(
            back, wire.append(7, "a1", 5, 1, ((2, 7, "z=3"),), 1))
        fact("heal adopts the newer term before reconciling",
             healed["term"] == 7)
        locked = wire.follower("a2", term=5, voted_for="a4", config=cfg3,
                               log=((0, 3, "x=1"), (1, 5, "y=2")),
                               commit_index=1)
        reply, healed = s7.heal_from_leader(
            locked, wire.append(7, "a1", 5, 1, ((2, 7, "z=3"),), 1))
        fact("the term law clears the old latch before re-locking",
             healed["term"] == 7 and healed["voted_for"] == "a1")

        # --- purity and determinism
        hold = dict(back)
        wanted_msg = wire.append(5, "a1", 5, 1, ((2, 5, "z=3"),), 1)
        s7.heal_from_leader(back, wanted_msg)
        s7.persist(back)
        fact("the disk functions never mutate the caller", back == hold)
        fact("persist is pure over recover's output",
             s7.persist(s7.recover(saved)) == saved)
        fact("heal is deterministic",
             s7.heal_from_leader(back, wanted_msg)
             == s7.heal_from_leader(back, wanted_msg))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_07: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
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

    COURSE = "consensus-from-scratch"

    STAGE = 8

    STUB_MESSAGE = "stage 8: implement build_snapshot()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H6_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H6_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        for name in sorted(os.listdir(overlay)):
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
                raise AssertionError("%s: refusal %r does not name %s"
                                     % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h6_check08_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_08 as s8\n"
                    "for call in (lambda: s8.build_snapshot(None, 0),\n"
                    "             lambda: s8.install_snapshot(None, None)):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "print('not implemented yet')\n"
                    "raise SystemExit(42)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "wire.py"))
                    and os.path.isfile(os.path.join(p, "stage_08.py"))),
                   None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h6_check08_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import wire
        import stage_04
        import stage_08 as s8

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

        stub = 0
        cfg3 = ("a1", "a2", "a3")
        for call in (lambda: s8.build_snapshot(
                         wire.leader("a1", 5, config=cfg3,
                                     log=((0, 1, "x=1"), (1, 1, "y=2")),
                                     commit_index=0), 0),
                     lambda: s8.install_snapshot(
                         wire.follower("a2", config=cfg3),
                         wire.snapshot(1, "a1", 1, 0,
                                       ((0, 1, "x=1"),)))):
            try:
                call()
            except NotImplementedError as error:
                must("stub message", "implement" in str(error))
                stub += 1
        if stub:
            print("check_08: stage 8: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        # --- build_snapshot: the committed prefix becomes a message -------
        leader = wire.leader("a1", 5, config=cfg3,
                             log=((0, 3, "x=1"), (1, 5, "y=2"),
                                  (2, 5, "z=3")),
                             commit_index=1, matched={"a2": 1, "a3": 1},
                             next_index={"a2": 2, "a3": 2}, elapsed=2)
        hold = dict(leader)
        msg, leader2 = s8.build_snapshot(leader, 1)
        fact("the snapshot is the boundary pair plus the compacted entries",
             msg == wire.snapshot(5, "a1", 5, 1,
                                  ((0, 3, "x=1"), (1, 5, "y=2"))))
        fact("the leader's log becomes the tail",
             leader2["log"] == ((2, 5, "z=3"),))
        fact("the boundary rides in snapshot_at",
             leader2["snapshot_at"] == (1, 5))
        fact("commit_index rides with the boundary",
             leader2["commit_index"] == 1)
        fact("the peer tables survive compaction",
             leader2["matched"] == {"a2": 1, "a3": 1}
             and leader2["next_index"] == {"a2": 2, "a3": 2})
        fact("the timer is not reset by a local decision",
             leader2["elapsed"] == 2)
        fact("term, config and role survive",
             leader2["term"] == 5 and leader2["config"] == cfg3
             and leader2["role"] == "leader"
             and leader2["old_config"] is None)
        fact("build_snapshot never mutates the caller", leader == hold)
        _refuses(wire.ProtocolError, "compacting past the commit line",
                 lambda: s8.build_snapshot(leader, 2),
                 names=("stage_08", "2", "1"))
        _refuses(wire.ProtocolError, "compacting an index outside the tail",
                 lambda: s8.build_snapshot(leader, 9), names=("stage_08",))
        _refuses(wire.ProtocolError, "compacting below the boundary",
                 lambda: s8.build_snapshot(
                     wire.leader("a1", 5, config=cfg3,
                                 log=((5, 5, "a=1"), (6, 5, "b=2")),
                                 commit_index=6, snapshot_at=(5, 5)), 5),
                 names=("stage_08",))
        _refuses(wire.ProtocolError, "compacting below the tail's start",
                 lambda: s8.build_snapshot(
                     wire.leader("a1", 5, config=cfg3,
                                 log=((6, 5, "b=2"), (7, 5, "c=3")),
                                 commit_index=7, snapshot_at=(5, 5)), 5),
                 names=("stage_08", "outside"))
        _refuses(wire.ProtocolError, "a bool index is not an index",
                 lambda: s8.build_snapshot(leader, True),
                 names=("stage_08",))
        _refuses(wire.ProtocolError, "only a leader compacts",
                 lambda: s8.build_snapshot(
                     wire.follower("a2", term=5, config=cfg3), 0),
                 names=("stage_08",))
        fact("building is deterministic",
             s8.build_snapshot(leader, 1) == (msg, leader2))

        # --- install_snapshot: the receiver's side ------------------------
        behind = wire.follower("a2", term=5, config=cfg3,
                               log=((0, 3, "x=1"),), commit_index=0,
                               elapsed=4)
        hold2 = dict(behind)
        reply, installed = s8.install_snapshot(behind, msg)
        fact("the install is acknowledged at the boundary",
             reply == wire.snapshot_reply(5, "a2", 1, leader="a1"))
        fact("the payload replaces the log",
             installed["log"] == ((0, 3, "x=1"), (1, 5, "y=2")))
        fact("the commit line lands at the boundary",
             installed["commit_index"] == 1)
        fact("the boundary is adopted", installed["snapshot_at"] == (1, 5))
        fact("a snapshot is proof of life: the timer resets",
             installed["elapsed"] == 0)
        fact("the sender is the leader the node remembers",
             installed["voted_for"] == "a1")
        fact("install_snapshot never mutates the caller", behind == hold2)

        # the round trip resumes over the real stage 4
        r, resumed = stage_04.handle_append(
            installed, wire.append(5, "a1", 5, 1, ((2, 5, "z=3"),), 1))
        fact("after an install the next APPEND anchors on the boundary",
             resumed["log"] == ((0, 3, "x=1"), (1, 5, "y=2"),
                                 (2, 5, "z=3"))
             and r == wire.append_reply(5, "a2", 2, 3, leader="a1"))

        # an exact repeat is refused — and a refusal keeps the clock
        waiting = wire.follower("a2", term=5, config=cfg3,
                                log=((0, 3, "x=1"), (1, 5, "y=2")),
                                commit_index=1, snapshot_at=(1, 5),
                                voted_for="a1", elapsed=3)
        reply, same = s8.install_snapshot(waiting, msg)
        fact("a snapshot that does not beat what we hold is refused",
             reply == wire.snapshot_reply(5, "a2", 1, leader="a1")
             and same["snapshot_at"] == (1, 5)
             and same["log"] == waiting["log"])
        fact("a refusal does not reset the election clock",
             same["elapsed"] == 3)

        # stale sender: refuse, keep term, keep the vote
        ahead = wire.follower("a2", term=9, voted_for="a3", config=cfg3,
                              elapsed=3)
        reply, kept = s8.install_snapshot(ahead, msg)
        fact("a snapshot from an old term cannot demote us",
             kept["term"] == 9 and kept["role"] == "follower")
        fact("a refused snapshot answers at our own end",
             reply == wire.snapshot_reply(9, "a2", -1, leader="a1"))
        fact("the follower's voter survives a refused install",
             kept["voted_for"] == "a3" and kept["elapsed"] == 3)

        # a rival leader in our term: refuse, keep our own log and line
        rival = wire.leader("a5", 5, config=cfg3, log=((0, 3, "q=9"),),
                            commit_index=0, matched={"a2": 0, "a3": 0},
                            next_index={"a2": 1, "a3": 1})
        reply, keeper = s8.install_snapshot(rival, msg)
        fact("a rival's snapshot does not dethrone us in our own term",
             reply[0] == wire.SNAPSHOT_REPLY and keeper["role"] == "leader"
             and keeper["id"] == "a5")
        fact("a refused install leaves the rival's own log and line alone",
             keeper["log"] == ((0, 3, "q=9"),)
             and keeper["commit_index"] == 0
             and keeper["matched"] == {"a2": 0, "a3": 0})

        # higher term: the term law runs before any boundary compare
        small = wire.follower("a2", term=4, voted_for="a5", config=cfg3)
        reply, grown = s8.install_snapshot(
            small, wire.snapshot(9, "a1", 3, 1,
                                 ((0, 3, "x=1"), (1, 3, "y=2"))))
        fact("a higher term is adopted first, voted_for and all",
             grown["term"] == 9 and grown["voted_for"] == "a1"
             and grown["log"] == ((0, 3, "x=1"), (1, 3, "y=2")))

        # a candidate stands down before installing
        running = wire.candidate("a2", term=5, voted_for="a2", config=cfg3,
                                 votes=("a2",), elapsed=1)
        reply, stood = s8.install_snapshot(running, msg)
        fact("a candidate stands down for a snapshot's leader",
             stood["role"] == "follower" and stood["log"] == msg[5])

        # the tail may not be rewritten by a payload
        ghost = wire.follower("a2", term=5, config=cfg3,
                              log=((0, 3, "x=1"), (1, 4, "ghost=9")),
                              commit_index=0)
        reply, faithful = s8.install_snapshot(ghost, msg)
        fact("a snapshot that contradicts the remembered tail is refused",
             faithful["log"] == ((0, 3, "x=1"), (1, 4, "ghost=9"))
             and reply == wire.snapshot_reply(5, "a2", 1, leader="a1"))

        # entries below the payload are folded; overlapping ones must match
        overlap = wire.snapshot(5, "a1", 5, 4,
                                ((2, 4, "c=2"), (3, 4, "d=3"),
                                 (4, 5, "e=4")))
        holder = wire.follower("a2", term=5, config=cfg3,
                               log=((0, 3, "x=1"), (1, 3, "b=1"),
                                    (2, 4, "c=2"), (3, 4, "d=3")),
                               commit_index=3, elapsed=2)
        reply, filled = s8.install_snapshot(holder, overlap)
        fact("a payload above our boundary installs over a folded prefix",
             filled["log"] == overlap[5] and filled["commit_index"] == 4
             and filled["snapshot_at"] == (4, 5)
             and reply == wire.snapshot_reply(5, "a2", 4, leader="a1"))
        liar = wire.follower("a2", term=5, config=cfg3,
                             log=((0, 3, "x=1"), (1, 3, "b=1"),
                                  (2, 4, "c=2"), (3, 4, "OTHER=9")),
                             commit_index=3)
        reply, honest = s8.install_snapshot(liar, overlap)
        fact("an overlapping tail entry the payload rewrites refuses it",
             honest["log"] == liar["log"]
             and reply == wire.snapshot_reply(5, "a2", 3, leader="a1"))

        # a boundary at our own end is not ahead: refuse even when the
        # commit line would allow the install
        level = wire.follower("a2", term=5, config=cfg3,
                              log=((0, 3, "x=1"), (1, 5, "y=2"),
                                   (2, 5, "z=3")), commit_index=1)
        reply, levelled = s8.install_snapshot(level, msg)
        fact("install refuses a snapshot that ends where we end",
             levelled["log"] == ((0, 3, "x=1"), (1, 5, "y=2"),
                                 (2, 5, "z=3"))
             and reply == wire.snapshot_reply(5, "a2", 2, leader="a1"))

        # a snapshot below our commit line is a safety lie
        deep = wire.follower("a2", term=5, config=cfg3,
                             log=((0, 3, "x=1"), (1, 4, "g=1"),
                                  (2, 4, "g2=2")), commit_index=2)
        reply, deeper = s8.install_snapshot(deep, msg)
        fact("install refuses to move the commit line backward",
             deeper["commit_index"] == 2
             and deeper["log"] == deep["log"]
             and reply == wire.snapshot_reply(5, "a2", 2, leader="a1"))
        # ...even when the tail's term hides it from the up-to-date law
        held = wire.follower("a2", term=5, config=cfg3, snapshot_at=(5, 5),
                             log=((6, 5, "f=6"), (7, 4, "g=7")),
                             commit_index=7)
        reply, shallow = s8.install_snapshot(
            held, wire.snapshot(5, "a1", 5, 6, ((6, 5, "f=6"),)))
        fact("a boundary that trails our commit line is refused outright",
             shallow["commit_index"] == 7 and shallow["log"] == held["log"]
             and reply == wire.snapshot_reply(5, "a2", 7, leader="a1"))

        # the door: grammar first, before any state law
        _refuses(wire.ProtocolError, "only SNAPSHOT is installable",
                 lambda: s8.install_snapshot(
                     behind, wire.append(5, "a1", 3, 1, (), 1)),
                 names=("stage_08",))
        _refuses(wire.ProtocolError, "a short snapshot is not the grammar",
                 lambda: s8.install_snapshot(behind,
                                             (wire.SNAPSHOT, 5, "a1", 3)),
                 names=("stage_08",))
        _refuses(wire.ProtocolError, "a boundary pair must match the payload",
                 lambda: s8.install_snapshot(
                     behind, (wire.SNAPSHOT, 5, "a1", 5, 3,
                              ((0, 3, "x=1"), (1, 5, "y=2")))),
                 names=("stage_08",))
        _refuses(wire.ProtocolError, "a gapped payload is not a log",
                 lambda: s8.install_snapshot(
                     behind, (wire.SNAPSHOT, 5, "a1", 5, 2,
                              ((0, 3, "x=1"), (2, 5, "z=3")))),
                 names=("stage_08",))
        _refuses(wire.ProtocolError, "an empty payload proves nothing",
                 lambda: s8.install_snapshot(
                     behind, (wire.SNAPSHOT, 5, "a1", 0, -1, ())),
                 names=("stage_08",))

        fact("install is deterministic",
             s8.install_snapshot(behind, msg)[1]
             == s8.install_snapshot(behind, msg)[1])

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_08: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
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

    COURSE = "consensus-from-scratch"

    STAGE = 9

    STUB_MESSAGE = "stage 9: implement begin_change()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H6_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H6_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        for name in sorted(os.listdir(overlay)):
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
                raise AssertionError("%s: refusal %r does not name %s"
                                     % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h6_check09_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_09 as s9\n"
                    "for call in (lambda: s9.begin_change(None, None),\n"
                    "             lambda: s9.quorum(None),\n"
                    "             lambda: s9.finish_change(None)):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "print('not implemented yet')\n"
                    "raise SystemExit(42)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "wire.py"))
                    and os.path.isfile(os.path.join(p, "stage_09.py"))),
                   None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h6_check09_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import wire
        import stage_04
        import stage_09 as s9

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

        OLD = ("a1", "a2", "a3")
        NEW = ("a4", "a5")
        UNION = ("a1", "a2", "a3", "a4", "a5")

        def plain():
            return wire.leader("a1", 5, config=OLD,
                               log=((0, 3, "x=1"), (1, 4, "y=2")),
                               commit_index=1, matched={"a2": 1, "a3": 1},
                               next_index={"a2": 2, "a3": 2}, elapsed=2)

        # --- stub probe: valid builders, so a solution runs past them -----
        stub = 0
        joint_fix = wire.leader("a1", 5, config=UNION, old_config=OLD,
                                log=((0, 3, "x=1"), (1, 4, "y=2"),
                                     (2, 5, "members:a4,a5")),
                                commit_index=2,
                                matched={"a2": 2, "a3": 2, "a4": 2,
                                         "a5": 2},
                                next_index={"a2": 3, "a3": 3, "a4": 3,
                                            "a5": 3})
        for call in (lambda: s9.begin_change(plain(), NEW),
                     lambda: s9.quorum(plain()),
                     lambda: s9.finish_change(joint_fix)):
            try:
                call()
            except NotImplementedError as error:
                must("stub message", "implement" in str(error))
                stub += 1
        if stub:
            print("check_09: stage 9: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        # --- begin_change: the window opens with an entry -----------------
        leader = plain()
        hold = dict(leader)
        leader2, entry = s9.begin_change(leader, ("a5", "a4"))
        fact("the change rides as a sorted members entry at the tail",
             entry == (2, 5, "members:a4,a5"))
        fact("the appended log ends in the joint entry",
             leader2["log"] == ((0, 3, "x=1"), (1, 4, "y=2"), entry))
        fact("the live config is the sorted union",
             leader2["config"] == UNION)
        fact("old_config keeps the old set verbatim",
             leader2["old_config"] == OLD)
        fact("commit_index is not moved by an append",
             leader2["commit_index"] == 1)
        fact("new voters are seeded at the entry's successor",
             leader2["matched"] == {"a2": 1, "a3": 1, "a4": -1, "a5": -1}
             and leader2["next_index"] == {"a2": 2, "a3": 2, "a4": 3,
                                           "a5": 3})
        fact("term, role and timer ride along",
             leader2["term"] == 5 and leader2["role"] == "leader"
             and leader2["elapsed"] == 2)
        fact("begin_change never mutates the caller",
             leader == hold and leader["matched"] == hold["matched"]
             and leader["next_index"] == hold["next_index"])
        fact("begin_change is deterministic",
             s9.begin_change(plain(), ("a5", "a4")) == (leader2, entry))
        trimmed = wire.leader("a1", 6, config=OLD, snapshot_at=(6, 4),
                              log=((7, 4, "b=2"),), commit_index=7)
        _, cut_entry = s9.begin_change(trimmed, NEW)
        fact("a trimmed log still numbers the entry from its start",
             cut_entry == (8, 6, "members:a4,a5"))
        _refuses(wire.ProtocolError, "an empty new config has no majority",
                 lambda: s9.begin_change(plain(), ()), names=("stage_09",))
        _refuses(wire.ProtocolError, "an unknown member has no timeout row",
                 lambda: s9.begin_change(plain(), ("a4", "zz")),
                 names=("stage_09", "zz"))
        _refuses(wire.ProtocolError, "a repeated member weights one voter",
                 lambda: s9.begin_change(plain(), ("a4", "a4")),
                 names=("stage_09", "a4"))
        _refuses(wire.ProtocolError, "a new config is a tuple of ids",
                 lambda: s9.begin_change(plain(), ["a4"]),
                 names=("stage_09",))
        _refuses(wire.ProtocolError, "one window at a time",
                 lambda: s9.begin_change(joint_fix, ("a1",)),
                 names=("stage_09",))
        _refuses(wire.ProtocolError, "only a leader opens the window",
                 lambda: s9.begin_change(wire.follower("a2", term=5,
                                                      config=OLD), NEW),
                 names=("stage_09",))

        # --- quorum: the sum of both majorities while joint ---------------
        fact("a joint proposal needs both majorities answered",
             s9.quorum(leader2) == wire.majority(3) + wire.majority(2) == 4)
        fact("a plain leader answers its config's majority",
             s9.quorum(plain()) == wire.majority(3))
        fact("a five-node leader answers three",
             s9.quorum(wire.leader("a1", 2)) == 3)
        fact("a candidate has no window: single-config law",
             s9.quorum(wire.candidate("a2", 6, voted_for="a2", config=OLD,
                                      votes=("a2",))) == 2)
        fact("a follower has no window either",
             s9.quorum(wire.follower("a2", config=UNION)) == 3)

        # --- finish_change: the window closes under the new majority ------
        _refuses(wire.ProtocolError, "finishing without opening skips it",
                 lambda: s9.finish_change(plain()), names=("stage_09",))
        _refuses(wire.ProtocolError, "only a leader closes the window",
                 lambda: s9.finish_change(wire.follower("a2", config=OLD)),
                 names=("stage_09",))

        uncommitted = wire.leader("a1", 5, config=UNION, old_config=OLD,
                                  log=((0, 3, "x=1"), (1, 4, "y=2"),
                                       (2, 5, "members:a4,a5")),
                                  commit_index=1,
                                  matched={"a2": 2, "a3": 2, "a4": 2,
                                           "a5": 2},
                                  next_index={"a2": 3, "a3": 3, "a4": 3,
                                              "a5": 3})
        still_open = s9.finish_change(uncommitted)
        fact("an uncommitted joint entry keeps the window open",
             still_open["old_config"] == OLD
             and still_open["config"] == UNION
             and still_open["commit_index"] == 1)

        thin = wire.leader("a1", 5, config=UNION, old_config=OLD,
                           log=((0, 3, "x=1"), (1, 4, "y=2"),
                                (2, 5, "members:a4,a5")),
                           commit_index=2,
                           matched={"a2": 2, "a3": 2, "a4": 2, "a5": 1},
                           next_index={"a2": 3, "a3": 3, "a4": 3,
                                       "a5": 3})
        not_yet = s9.finish_change(thin)
        fact("a committed entry the new majority lacks stays joint",
             not_yet["old_config"] == OLD and not_yet["config"] == UNION)

        out = s9.finish_change(joint_fix)
        fact("a leader the new config excludes steps down",
             out["role"] == "follower" and out["id"] == "a1")
        fact("the follower keeps term, log and commit line",
             out["term"] == 5 and out["commit_index"] == 2
             and out["log"] == joint_fix["log"])
        fact("the stepped-down node serves the new config",
             out["config"] == NEW and out["voted_for"] is None)
        fact("step-down rebuilds a pure follower",
             tuple(sorted(out)) == tuple(sorted(wire.FOLLOWER_KEYS)))

        last_wins = wire.leader("a1", 5, config=UNION,
                                old_config=("a2", "a3", "a4", "a5"),
                                log=((0, 3, "members:a5",),
                                     (1, 4, "x=1"),
                                     (2, 5, "members:a1,a2,a3")),
                                commit_index=2,
                                matched={"a2": 2, "a3": 2, "a5": 0},
                                next_index={"a2": 3, "a3": 3, "a5": 1})
        closed = s9.finish_change(last_wins)
        fact("the close swaps config to the LATEST members entry",
             closed["role"] == "leader"
             and closed["config"] == ("a1", "a2", "a3")
             and closed["old_config"] is None)
        fact("the peer maps are pruned to the surviving voters",
             closed["matched"] == {"a2": 2, "a3": 2}
             and closed["next_index"] == {"a2": 3, "a3": 3})
        hold_joint = dict(joint_fix)
        s9.finish_change(joint_fix)
        fact("finish_change never mutates the caller", joint_fix == hold_joint)
        fact("finish is deterministic",
             s9.finish_change(joint_fix) == s9.finish_change(joint_fix))

        # --- the joint leader replicates over the union (real stage 4) ----
        messages = stage_04.broadcast_append(leader2)
        fact("the joint leader appends to every union peer",
             len(messages) == 4
             and all(m[0] == wire.APPEND for m in messages))
        fact("a tracked peer's append carries the joint entry",
             entry in messages[0][5])
        probe = wire.follower("a5", term=5, config=UNION,
                              log=((0, 3, "x=1"), (1, 4, "y=2")),
                              commit_index=1)
        r1, probed = stage_04.handle_append(probe, messages[3])
        fact("a new voter refuses the tail probe: it lacks the anchor",
             r1 == wire.append_reply(5, "a5", 1, 2, leader="a1")
             and probed["log"] == probe["log"])
        backed_off = wire.leader("a1", 5, config=UNION, old_config=OLD,
                                 log=leader2["log"], commit_index=1,
                                 matched=dict(leader2["matched"], a5=1),
                                 next_index=dict(leader2["next_index"],
                                                 a5=2))
        retry = stage_04.broadcast_append(backed_off)[3]
        fact("the retry anchors one slot back and sends the entry",
             retry[4] == 1 and retry[5] == (entry,))
        r2, joined = stage_04.handle_append(probed, retry)
        fact("after backing off the new voter holds the joint entry",
             joined["log"] == leader2["log"]
             and r2 == wire.append_reply(5, "a5", 2, 3, leader="a1"))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_09: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
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

    COURSE = "consensus-from-scratch"

    STAGE = 10

    STUB_MESSAGE = "stage 10: implement init()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H6_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "wire.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H6_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        for name in sorted(os.listdir(overlay)):
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
                raise AssertionError("%s: refusal %r does not name %s"
                                     % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h6_check10_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_10 as s10\n"
                    "for call in (lambda: s10.init('a1', ('a1', 'a2', 'a3')),\n"
                    "             lambda: s10.recv(None, None),\n"
                    "             lambda: s10.tick(None),\n"
                    "             lambda: s10.client(None, 'x=1'),\n"
                    "             lambda: s10.prove('ELECT_ONE'),\n"
                    "             lambda: s10.audit(())):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "print('not implemented yet')\n"
                    "raise SystemExit(42)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "wire.py"))
                    and os.path.isfile(os.path.join(p, "stage_10.py"))),
                   None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h6_check10_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import wire

        import scenarios
        import stage_10 as s10

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

        FIVE = ("a1", "a2", "a3", "a4", "a5")
        THREE = ("a1", "a2", "a3")

        # --- stub probe: real builders, so a solution runs past them ------
        stub = 0
        for call in (lambda: s10.init("a1", FIVE),
                     lambda: s10.recv(wire.follower("a1"),
                                      wire.vote_reply(1, "a2", "a1", True)),
                     lambda: s10.tick(wire.follower("a1")),
                     lambda: s10.client(wire.follower("a1"), "get x"),
                     lambda: s10.prove("ELECT_ONE"),
                     lambda: s10.audit(())):
            try:
                call()
            except NotImplementedError as error:
                must("stub message", "implement" in str(error))
                stub += 1
        if stub:
            print("check_10: stage 10: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        # --- init: the fresh node is a pure follower ----------------------
        fresh = s10.init("a3", FIVE)
        fact("init builds a follower", fresh["role"] == "follower")
        fact("init starts at term 0 with no vote cast",
             fresh["term"] == 0 and fresh["voted_for"] is None)
        fact("init starts with an empty log below an empty commit line",
             fresh["log"] == () and fresh["commit_index"] == -1)
        fact("init serves the config it was handed",
             fresh["config"] == FIVE)
        fact("init builds exactly the follower shape",
             tuple(sorted(fresh)) == tuple(sorted(wire.FOLLOWER_KEYS)))
        fact("init is deterministic",
             s10.init("a3", FIVE) == fresh)

        # --- client: refusals, committed reads, accepted writes -----------
        hold = dict(fresh)
        state, messages, answer = s10.client(fresh, "x=1")
        fact("a follower's write is refused with a hint",
             answer[0] == "not_leader" and isinstance(answer[1], str))
        fact("a refused write sends nothing and keeps the state",
             messages == () and state == hold)
        cand = wire.candidate("a1", 4, votes=("a1",), config=FIVE,
                              log=((0, 3, "x=1"),), commit_index=0)
        state, messages, answer = s10.client(cand, "x=1")
        fact("a candidate cannot serve the client either",
             answer[0] == "not_leader" and messages == ()
             and state == cand)
        state, messages, answer = s10.client(fresh, "get x")
        fact("a follower answers reads as a refusal, not a value",
             answer[0] == "not_leader")

        def leading(term=5, log=((0, 4, "x=1"), (1, 5, "y=2")), commit=0,
                    config=THREE, matched=None, next_index=None,
                    elapsed=1, snapshot_at=None):
            return wire.leader("a1", term, log=log, commit_index=commit,
                               config=config,
                               matched=matched if matched is not None
                               else {"a2": 0, "a3": -1},
                               next_index=next_index if next_index is not None
                               else {"a2": 1, "a3": 2},
                               elapsed=elapsed, snapshot_at=snapshot_at)

        leader = leading()
        hold = dict(leader)
        state, messages, answer = s10.client(leading(commit=-1), "get x")
        fact("a leader reads only COMMITTED state: nothing is committed",
             answer == ("read", ""))
        state, messages, answer = s10.client(leading(commit=1), "get x")
        fact("the committed slot answers its value", answer == ("read", "1"))
        state, messages, answer = s10.client(leading(commit=1), "get z")
        fact("an unknown key reads as the empty value",
             answer == ("read", ""))
        leader = leading()
        state, messages, answer = s10.client(leader, "z=9")
        fact("an accepted write answers (None,)", answer == (None,))
        fact("the write lands at the log's tail",
             state["log"] == ((0, 4, "x=1"), (1, 5, "y=2"), (2, 5, "z=9")))
        fact("the write fires one APPEND per peer",
             len(messages) == 2 and all(m[0] == wire.APPEND
                                        for m in messages))
        fact("each append carries the peer's own tail",
             messages[0][5] == ((1, 5, "y=2"), (2, 5, "z=9"))
             and messages[1][5] == ((2, 5, "z=9"),))
        fact("client never mutates the caller", leader == hold)

        behind = wire.leader("a1", 5, log=((2, 5, "w=7"),), commit_index=2,
                             config=THREE, matched={"a2": 1, "a3": 2},
                             next_index={"a2": 1, "a3": 3}, elapsed=1,
                             snapshot_at=(1, 5))
        state, messages, answer = s10.client(behind, "z=9")
        fact("a peer behind the boundary gets a SNAPSHOT, not an APPEND",
             len(messages) == 2
             and messages[0] == wire.snapshot(5, "a1", 5, 2,
                                              ((2, 5, "w=7"),))
             and messages[1][0] == wire.APPEND and messages[1][5]
             == ((3, 5, "z=9"),))
        fact("routing the snapshot does not trim the sender itself",
             state["snapshot_at"] == (1, 5)
             and wire.log_start(state["log"]) == 2)

        # --- recv REQUEST_VOTE: leaders and candidates keep their term ----
        rival = wire.request_vote(5, "a2", 9, 99)
        leader = leading()
        hold = dict(leader)
        state, replies = s10.recv(leader, rival)
        fact("a leader denies a same-term request and keeps leading",
             state["role"] == "leader" and state["term"] == 5
             and replies == (wire.vote_reply(5, "a1", "a2", False),))
        fact("the denial is silent about the log and maps", state == hold)
        state, replies = s10.recv(leader, wire.request_vote(3, "a2", 0, -1))
        fact("a leader denies a LOWER-term request too",
             state["role"] == "leader" and replies[0][4] is False)
        running = wire.candidate("a1", 4, voted_for="a1", votes=("a1",),
                                 config=FIVE, log=((0, 3, "x=1"),),
                                 commit_index=0)
        state, replies = s10.recv(running, wire.request_vote(4, "a2", 9, 99))
        fact("a candidate denies a same-term rival and keeps its election",
             state["role"] == "candidate" and state["votes"] == ("a1",)
             and state["voted_for"] == "a1"
             and replies == (wire.vote_reply(4, "a1", "a2", False),))
        state, replies = s10.recv(running, wire.request_vote(6, "a2", 3, 0))
        fact("a higher term ends the candidacy: follower, adopted term",
             state["role"] == "follower" and state["term"] == 6
             and "votes" not in state)
        fact("the stepped-down candidate votes for the fresher rival",
             replies == (wire.vote_reply(6, "a1", "a2", True),)
             and state["voted_for"] == "a2")
        voter = wire.follower("a3", term=2, log=((0, 1, "x=1"),),
                              commit_index=0, config=FIVE, elapsed=4)
        state, replies = s10.recv(voter, wire.request_vote(4, "a2", 1, 0))
        fact("a follower adopts a higher term and grants by currency",
             replies == (wire.vote_reply(4, "a3", "a2", True),)
             and state["term"] == 4 and state["voted_for"] == "a2")

        # --- recv VOTE_REPLY: the majority crowns and fires ----------------
        candidate = wire.candidate("a1", 4, votes=("a1",), config=THREE,
                                   log=((0, 3, "x=1"),), commit_index=0)
        state, replies = s10.recv(candidate,
                                  wire.vote_reply(4, "a2", "a1", True))
        fact("the majority vote crowns the leader (self plus two)",
             state["role"] == "leader" and state["term"] == 4)
        fact("the new leader seeds stage 3's maps",
             state["matched"] == {"a2": -1, "a3": -1}
             and state["next_index"] == {"a2": 1, "a3": 1})
        fact("the crown fires one APPEND per peer",
             len(replies) == 2 and all(m[0] == wire.APPEND
                                       for m in replies))
        denied = wire.candidate("a1", 4, votes=("a1",), config=THREE,
                                log=((0, 3, "x=1"),), commit_index=0)
        state, replies = s10.recv(denied, wire.vote_reply(4, "a2", "a1",
                                                          False))
        fact("a denial keeps the candidacy and the votes",
             state["role"] == "candidate" and state["votes"] == ("a1",)
             and replies == ())
        state, replies = s10.recv(denied, wire.vote_reply(5, "a2", "a1",
                                                          True))
        fact("a reply at a higher term ends the election",
             state["role"] == "follower" and state["term"] == 5
             and replies == ())
        state, replies = s10.recv(voter, wire.vote_reply(4, "a2", "a1",
                                                         True))
        fact("a vote reply to a follower changes nothing",
             state == voter and replies == ())

        # --- recv APPEND: reconcile and apply committed membership ---------
        behind = wire.follower("a2", term=4, log=((0, 3, "x=1"),),
                               commit_index=0, config=THREE, elapsed=6)
        hold = dict(behind)
        msg = wire.append(5, "a1", 3, 0,
                          ((1, 4, "y=2"), (2, 5, "members:a2,a3")), 2)
        state, replies = s10.recv(behind, msg)
        fact("the append lands, the commit line follows the leader",
             state["log"] == ((0, 3, "x=1"), (1, 4, "y=2"),
                              (2, 5, "members:a2,a3"))
             and state["commit_index"] == 2)
        fact("a COMMITTED members command rewrites the receiver's config",
             state["config"] == ("a2", "a3"))
        fact("the receiver answers at its own tail",
             replies == (wire.append_reply(5, "a2", 2, 3, leader="a1"),))
        fact("the append path never mutates the caller", behind == hold)
        uncommitted = wire.append(5, "a1", 3, 0, ((1, 4, "y=2"),
                                                  (2, 5, "members:a2,a3")),
                                  1)
        state, replies = s10.recv(behind, uncommitted)
        fact("an UNCOMMITTED members entry does not touch the config",
             state["config"] == THREE and state["commit_index"] == 1)

        # --- recv APPEND_REPLY: ledger, standdown, advance ------------------
        leader = leading()
        hold = dict(leader)
        state, replies = s10.recv(
            leader, wire.append_reply(5, "a3", 1, 2, leader="a1"))
        fact("an honest reply updates the ledger and the commit line",
             state["matched"] == {"a2": 0, "a3": 1}
             and state["next_index"] == {"a2": 1, "a3": 2}
             and state["commit_index"] == 1 and replies == ())
        state, replies = s10.recv(leader, wire.append_reply(7, "a3", 1, 2,
                                                            leader="a1"))
        fact("a higher-term reply steps the leader down",
             state["role"] == "follower" and state["term"] == 7
             and "matched" not in state and replies == ())
        truncated = wire.leader("a1", 5, log=((0, 5, "x=1"), (1, 5, "y=2")),
                                commit_index=1, config=THREE,
                                matched={"a2": 1, "a3": 1},
                                next_index={"a2": 2, "a3": 2}, elapsed=2)
        state, replies = s10.recv(truncated, wire.append_reply(5, "a2", 0,
                                                               1,
                                                               leader="a5"))
        fact("a same-term reply proving truncation stands the leader down",
             state["role"] == "follower" and state["term"] == 5
             and state["commit_index"] == 1 and replies == ())
        fact("the standdown keeps the log the rival has not touched",
             state["log"] == truncated["log"])
        state, replies = s10.recv(voter, wire.append_reply(4, "a2", 1, 2,
                                                           leader="a1"))
        fact("append replies to a follower are silence",
             state == voter and replies == ())

        # --- recv SNAPSHOT both ways ---------------------------------------
        lost = wire.follower("a2", term=4, log=((0, 3, "x=1"),),
                             commit_index=0, config=THREE, elapsed=2)
        msg = wire.snapshot(5, "a1", 4, 1,
                             ((0, 3, "x=1"), (1, 4, "y=2")))
        state, replies = s10.recv(lost, msg)
        fact("a snapshot installs through stage 8 and is acknowledged",
             replies == (wire.snapshot_reply(5, "a2", 1, leader="a1"),)
             and state["snapshot_at"] == (1, 4)
             and state["commit_index"] == 1)
        ahead_leader = wire.leader("a1", 5, log=((2, 5, "z=3"),),
                                   commit_index=1, config=THREE,
                                   snapshot_at=(1, 5),
                                   matched={"a2": -1, "a3": -1},
                                   next_index={"a2": 2, "a3": 2})
        state, replies = s10.recv(ahead_leader,
                                  wire.snapshot_reply(5, "a2", 1,
                                                      leader="a1"))
        fact("a snapshot reply reconciles the leader's maps",
             state["matched"]["a2"] == 1 and state["next_index"]["a2"] == 2)
        state, replies = s10.recv(ahead_leader,
                                  wire.snapshot_reply(3, "a2", 1,
                                                      leader="a1"))
        fact("a snapshot reply at an old term is silence",
             state == ahead_leader and replies == ())
        state, replies = s10.recv(voter, wire.snapshot_reply(4, "a2", 1,
                                                             leader="a1"))
        fact("a snapshot reply to a follower is silence",
             state == voter and replies == ())

        # --- tick: heartbeat, one request, quiet aging ----------------------
        leader = leading(elapsed=4)
        state, replies = s10.tick(leader)
        fact("the heartbeat beat resets the timer",
             state["elapsed"] == 0 and state["role"] == "leader")
        fact("the heartbeat appends to every peer",
             len(replies) == 2 and all(m[0] == wire.APPEND
                                       for m in replies))
        state, replies = s10.tick(leading(elapsed=1))
        fact("below HEARTBEAT the leader keeps quiet",
             state["elapsed"] == 2 and replies == ())
        waiting = wire.follower("a1", term=2, config=THREE, elapsed=10,
                                log=((0, 1, "x=1"),), commit_index=0)
        state, replies = s10.tick(waiting)
        fact("silence past the node's timeout opens an election",
             state["role"] == "candidate" and state["term"] == 3
             and state["votes"] == () and state["voted_for"] == "a1")
        fact("the node sends EXACTLY ONE request: the fabric fans it",
             len(replies) == 1 and replies[0] == wire.request_vote(
                 3, "a1", 1, 0))
        quiet = wire.follower("a1", term=2, config=THREE, elapsed=5)
        state, replies = s10.tick(quiet)
        fact("a follower below its timeout only ages",
             state["elapsed"] == 6 and replies == ())
        fact("tick never mutates the caller",
             waiting["elapsed"] == 10 and leader["elapsed"] == 4)

        # --- durability rides on stage 7 ------------------------------------
        fact("the node persists and recovers for the fabric",
             callable(getattr(s10, "persist", None))
             and callable(getattr(s10, "recover", None)))
        image = s10.persist(leading())
        back = s10.recover(image)
        fact("a persisted leader image recovers its durable truth",
             back["role"] == "follower" and back["term"] == 5
             and back["log"] == leading()["log"]
             and back["commit_index"] == 0 and back["config"] == THREE)
        _refuses(wire.ProtocolError, "a torn image is refused, not guessed",
                 lambda: s10.recover(b"nonsense"), names=("stage_07",))

        # --- the source keeps its promises ----------------------------------
        with open(os.path.join(course, "stage_10.py")) as handle:
            text = handle.read()
        fact("the foil is imported only inside audit",
             "\nimport naive" not in text
             and "import naive" in text.split("def audit", 1)[-1])
        fact("audit drives the foil through the fabric, not through PINS",
             "sim.Cluster(naive" in text.split("def audit", 1)[-1])
        fact("the stage never reaches for the clock or the dice",
             "\nimport os" not in text and "\nimport random" not in text
             and "\nimport time" not in text)

        # --- prove: the probe column, scenario by scenario -------------------
        for name in ("ELECT_ONE", "HEAL", "ASYMMETRIC", "MINORITY",
                     "LAGGARD", "TORN", "JOINT"):
            proof = s10.prove(name)
            must("prove shape", len(proof) == 4 and proof[0] == name)
            _name, result, pins, linear = proof
            fact("%s: leaders match the probe pin" % name,
                 result["leaders"] == pins["leaders"])
            fact("%s: commits match the probe pin" % name,
                 result["committed"] == pins["committed"])
            fact("%s: conflicts match the probe pin" % name,
                 result["conflicts"] == pins["conflicts"])
            fact("%s: the history linearizes" % name, linear[0] is True)
        proof = s10.prove("JOINT")
        fact("the membership scenario pins the mid-change election",
             proof[1]["leaders"] == ((5, 1, "a4"), (35, 3, "a2"),
                                     (40, 4, "a4")))
        fact("the members command commits as a log entry",
             (22, 1, 1, "members:a1,a2,a3") in proof[1]["committed"])
        proof = s10.prove("TORN")
        fact("TORN survives the tear: the crashed writes recover",
             proof[1]["committed"] == ((11, 0, 1, "x=1"),
                                       (14, 1, 1, "y=2"),
                                       (26, 2, 1, "z=3")))

        # --- audit: the verdict, and its refusal of a clean foil -------------
        proofs = [s10.prove(n) for n in ("ELECT_ONE", "HEAL", "ASYMMETRIC",
                                         "MINORITY", "LAGGARD", "TORN",
                                         "JOINT")]
        verdict, reasons = s10.audit(proofs)
        fact("audit passes the seven clean proofs", verdict == "pass")
        fact("a pass carries no reasons", reasons == ())
        _kind, events, ticks, pins = scenarios.scenario("ASYMMETRIC")
        import naive
        import sim
        foil_result = sim.Cluster(naive, scenario=events).run(ticks)
        tainted = ("ASYMMETRIC", foil_result, pins["probe"],
                   (True, ()))
        verdict, reasons = s10.audit((tainted,))
        fact("audit refuses the foil's own run presented as proof",
             verdict == "fail" and any("leaders" in r for r in reasons))
        missing = ("NOPE", foil_result, {}, (True, ()))
        verdict, reasons = s10.audit((missing,) + tuple(proofs))
        fact("audit refuses a name the pins table does not know",
             verdict == "fail" and any("NOPE" in r for r in reasons))
        broken = list(proofs)
        name, result, pin, linear = broken[4]
        broken[4] = (name, dict(result, leaders=()), pin, (False, ("stale",)))
        verdict, reasons = s10.audit(tuple(broken))
        fact("audit reports the broken history instead of passing it",
             verdict == "fail" and any("linear" in r for r in reasons))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_10: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
            shutil.rmtree(root, ignore_errors=True)

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title='The vote: terms, and one vote per term',
        tags=['raft', 'election', 'voted-for'],
        action="Write `grant_vote` in stage_01.py.",
        predict="Why the higher term is adopted before the vote is cast, and what a node that votes twice in one term costs the cluster.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title='The election: a leader is a number a majority agreed on',
        tags=['election', 'quorum', 'distinct-voters'],
        action="Write `start_election` and `tally` in stage_02.py.",
        predict="Why two majorities always overlap, and why a reply that names the voter is what makes the count honest.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title='The heartbeats: leadership is exercised, not claimed',
        tags=['heartbeat', 'append', 'step-down'],
        action="Write `become_leader`, `heartbeat`, `observe_append` and `observe_reply` in stage_03.py.",
        predict="Why an empty APPEND is the whole of a heartbeat, and what a follower's silence proves about a leader.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title='Replication: the entries match term by term',
        tags=['replication', 'prev-check', 'truncation'],
        action="Write `client_submit`, `broadcast_append` and `handle_append` in stage_04.py.",
        predict="Why the prev check compares term and index together, and how truncating by term converges two logs without scanning them.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title='The commit rule: a majority, and the current term',
        tags=['commit', 'majority', 'current-term'],
        action="Write `advance_commit` in stage_05.py.",
        predict="Why a leader may not commit an old-term entry by counting it, and what the majority of the WRONG epoch commits twice.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title='The stale leader: refuse, downgrade, never ignore',
        tags=['stale-leader', 'term-law', 'step-down'],
        action="Write `check_request` and `same_term_stale` in stage_06.py.",
        predict="Why a refusal must answer with the node's own term, and what silence does to a leader that believes it still leads.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title='The disk that lied: persist and recover',
        tags=['durability', 'torn-write', 'recovery'],
        action="Write `persist`, `recover` and `heal_from_leader` in stage_07.py.",
        predict="Why term and voted_for are the load-bearing fields of the image, and why the tear can lose an uncommitted entry and never a committed one.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title='The snapshot: commit without losing a committed entry',
        tags=['snapshot', 'boundary', 'compaction'],
        action="Write `build_snapshot` and `install_snapshot` in stage_08.py.",
        predict="Why compaction may only cut below the commit line, and what the boundary pair means for elections and up-to-date laws.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title='The membership change: one at a time',
        tags=['joint-consensus', 'membership', 'two-majorities'],
        action="Write `begin_change`, `quorum` and `finish_change` in stage_09.py.",
        predict="Why a membership change must be a log entry, and why the joint window needs a majority of EACH config.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title='The proof: one history, two verdicts',
        tags=['proof', 'linearizability', 'foil'],
        action="Write the composed node (`init`, `recv`, `tick`, `client`), `prove` and `audit` in stage_10.py.",
        predict="Why reads answer from committed state and never from the log, and why the audit runs the foil through the fabric instead of trusting the pin table.",
        check=check_10,
    ),
]
