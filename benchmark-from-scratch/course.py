"""Benchmark From Scratch (Mus) — course manifest.

Ten graded stages that build the MEASUREMENT machinery of a benchmark, with the
game provided. The rules are `mus.py` (a Fournier mus table: dealing, the mus
exchange, the four lances with their three bet scales, the 40-point vaca, two
reference policies and a seeded match) — and the exercise is everything that
turns a game into a number: the turn gate that counts what landed, the match loop
with its as-dealt snapshots and its rails, one ground-truth record per decision
taken BEFORE the action, the link between a bet and the answer it got, the
reference distribution a bet is measured against, the risk scorecard where a
bluff is a weak hand and not a lost bet, the low-variance outcome that survives
the vaca reset, the calibration and discrimination probes with their degenerate
cases, the gate that decides what may be published, and the mirrored pair that
cancels the seat advantage.

The lesson of every stage is a mistake the user's own benchmark made and fixed:
a Chica strength read upside down, lances measured on incomparable scales,
per-hand piedras reported without their mirror, a deal stream that depended on
the play, bluffs conflated with lost bets, and an API outage entering the
leaderboard as a result. Each stage's check plants that mistake and names it.

No network, no wall clock, no global state: every match is seeded, every policy
is deterministic, and the numbers are the ones two runs of the same seed produce.

    python3 codecraft/cli.py run benchmark-from-scratch
"""

from codecraft.api import stage

TITLE = "Benchmark From Scratch (Mus)"
DESCRIPTION = ("The measurement machinery of a benchmark on top of a provided "
               "game: gate actions so a refusal is data and not a turn, run a "
               "match with as-dealt snapshots, an engine-supplied fallback and "
               "rails that stop a run that became about the harness, record one "
               "ground-truth decision per turn from the position the seat faced, "
               "link an aggression to the answer it got, tercile the strength of "
               "the hands that actually faced a bet, score aggression, bluffs and "
               "fold equity, reduce a match to piedras that survive the vaca "
               "reset, probe a declared probability with Brier, log-loss, AUC and "
               "a calibration table, gate what may be published, and pair every "
               "match with its mirror so the seat advantage cancels.")
LEVEL = "intermediate"
ORDER = 14

# --- the checks. Each one is self-contained: its fixtures are nested
# inside it because `course.py` is one namespace for ten stages.

import os
import shutil
import sys
import tempfile
import json
import math


def check_1():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _snapshot(table):
        """Everything about the position that a refusal must not have touched."""
        return (table.phase, table.mano, table.current_seat, table.hand_index,
                table.turns, table.points_a, table.points_b, table.vacas_a,
                table.vacas_b, table.hand_winner, tuple(sorted(table.mus_want)),
                tuple(tuple(cards) for _, cards in sorted(table.hands.items())),
                len(table.draw_pile), len(table.discard_pile))

    import stage_01 as s
    from mus import IllegalAction, Table

    # --- the counters -------------------------------------------------------
    assert tuple(s.STATS_KEYS) == ("turns", "rejections", "fallbacks",
                                   "llm_turns", "calls"), (
        "the match's counters are the five a benchmark reports: turns, "
        "rejections, fallbacks, llm_turns, calls (got %r)" % (s.STATS_KEYS,))
    stats = s.new_stats()
    assert dict(stats) == {key: 0 for key in s.STATS_KEYS}, (
        "a fresh match starts every counter at zero, got %r" % (stats,))
    probe = s.new_stats()
    probe["turns"] = 7
    assert s.new_stats()["turns"] == 0, (
        "new_stats hands out a FRESH dict: a second call after mutating the first "
        "must not inherit its counts, got %r" % (s.new_stats(),))

    # --- an accepted action is a turn ---------------------------------------
    table = Table(seed=5)
    table.deal()
    first = table.current_seat
    outcome = s.gate(table, first, {"action": "mus"}, stats=stats)
    assert outcome["ok"] is True and outcome["reason"] is None, (
        "a legal action is accepted and has nothing to explain: %r" % (outcome,))
    assert outcome["turn"] == 1 == stats["turns"], (
        "an accepted action is turn 1 and the stats say so: %r" % (outcome,))
    assert table.turns == stats["turns"], (
        "the match's turn count and the table's own count are the same number: "
        "the gate counts what the table accepted, %r vs %r"
        % (stats["turns"], table.turns))

    # --- a refusal is data --------------------------------------------------
    here = table.current_seat
    before = _snapshot(table)
    refused = s.gate(table, here, {"action": "reenvido"}, stats=stats)
    assert refused["ok"] is False, (
        "an action that is not legal in this phase is refused, not accepted: %r"
        % (refused,))
    assert isinstance(refused["reason"], str) and "reenvido" in refused["reason"], (
        "the refusal carries the ENGINE's words, which name the action that was "
        "refused — the seat has to be told what it did wrong: %r"
        % (refused["reason"],))
    assert _snapshot(table) == before, (
        "a refused action changed the position: the table's refusal is atomic, and "
        "the gate must not leave anything applied behind it")
    assert stats["rejections"] == 1 and stats["turns"] == 1, (
        "a refusal is a refusal and not a turn: a model that answers with nonsense "
        "four times did not take four turns, got %r" % (stats,))
    assert refused["turn"] == 1, (
        "the refusal reports the last turn that HAPPENED, not the one it would "
        "have been: %r" % (refused,))

    # --- out of turn is the engine's refusal too ----------------------------
    other = (table.current_seat + 1) % 4
    before = _snapshot(table)
    out_of_turn = s.gate(table, other, {"action": "mus"}, stats=stats)
    assert out_of_turn["ok"] is False, (
        "seat %d answered while seat %d was to move, and the table refused it: %r"
        % (other, table.current_seat, out_of_turn))
    assert str(table.current_seat) in str(out_of_turn["reason"]), (
        "the refusal relays the engine's own diagnosis, which names the seat that "
        "IS to move — a gate that re-derives the turn rule has a second rulebook: "
        "%r" % (out_of_turn["reason"],))
    assert _snapshot(table) == before and stats["rejections"] == 2, (
        "an out-of-turn answer changes nothing and is counted as a refusal: %r"
        % (stats,))
    assert out_of_turn["turn"] == 1, (
        "two refusals have happened and only one turn: a refusal reports the last "
        "turn that HAPPENED (1), not how many refusals it took to get there (2) "
        "and not the turn it would have been: %r" % (out_of_turn,))

    # --- a bug is not a refusal ---------------------------------------------
    class Boom:
        """A table whose apply() is broken: our bug, not the seat's."""

        current_seat = 0
        turns = 0

        def legal_actions(self, seat):
            return ["mus"]

        def apply(self, seat, action):
            raise RuntimeError("the harness has a bug")

    broken = s.new_stats()
    try:
        s.gate(Boom(), 0, {"action": "mus"}, stats=broken)
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "an exception that is not `IllegalAction` is OUR bug and must "
            "propagate: filing it as the model misbehaving puts a harness bug "
            "behind a behaviour metric")
    assert dict(broken) == {key: 0 for key in s.STATS_KEYS}, (
        "and a propagating bug is not counted as anything: %r" % (broken,))

    # --- the counters are the caller's --------------------------------------
    try:
        s.gate(table, table.current_seat, {"action": "mus"}, stats=[])
    except TypeError:
        pass
    else:
        raise AssertionError(
            "stats is the match's own dict; anything else is a bug in the caller "
            "and must not be silently tolerated")
    assert stats["turns"] == 1 and stats["rejections"] == 2, (
        "the stats dict is MUTATED in place, not replaced: the caller's counters "
        "keep the match's history, got %r" % (stats,))

    # --- the gate counts the same turns the table does ----------------------
    seat = table.current_seat
    s.gate(table, seat, {"action": "mus"}, stats=stats)
    assert stats["turns"] == 2 == table.turns, (
        "after two accepted actions the two counts still agree: %r vs %r"
        % (stats["turns"], table.turns))
    assert stats["turns"] + stats["rejections"] == 4, (
        "two turns and two refusals, counted separately: %r" % (stats,))

def check_2():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    ROW_KEYS = ("matchup", "seed", "teams", "names", "llm", "status", "hands",
                "turns", "llm_turns", "fallbacks", "rejections", "vacas_a",
                "vacas_b", "hand_wins_a", "hand_wins_b", "hand_gain_a",
                "hand_gain_b", "deals", "note")

    import stage_01
    import stage_02 as s
    import stage_03
    from mus import Table, heuristic_policy, random_policy

    def scripted(actions, then=True):
        """A seat that plays a fixed list, then hands the engine its own default."""
        remaining = list(actions)

        def policy(table, seat, legal):
            if remaining:
                return remaining.pop(0)
            return table.default_action(seat) if then else {"action": "no"}
        return policy

    def churn(table, seat, legal):
        """A seat that asks for mus whenever it may — so cards really change."""
        if "mus" in legal:
            return {"action": "mus"}
        return table.default_action(seat)

    names = ["red", "blue", "red2", "blue2"]

    # --- a clean match ------------------------------------------------------
    calls = []
    log_lines = []
    log = stage_03.DecisionLog(lambda text: log_lines.append(json.loads(text)))
    row = s.run_match(Table(seed=23),
                      [churn, random_policy(3), random_policy(3),
                       random_policy(3)],
                      names=names, hands=3, on_hand=calls.append, log=log)
    assert set(row) == set(ROW_KEYS), (
        "the row is the frozen match shape (plus `note` for a stopped match): "
        "extra %r, missing %r"
        % (sorted(set(row) - set(ROW_KEYS)), sorted(set(ROW_KEYS) - set(row))))
    assert row["status"] == "done" and row["note"] is None, (
        "two hands of random-but-legal play finish: %r" % (row,))
    assert row["hands"] == 3 == len(calls), (
        "the match played three hands and reported each one: %r / %r"
        % (row["hands"], len(calls)))
    assert row["matchup"] == "red-vs-blue" and row["seed"] == 23 \
        and row["teams"] == ["red", "blue"] and row["names"] == names, (
        "the row says which matchup, which seed and who sat where: %r" % (row,))
    assert row["turns"] > 0 and row["rejections"] == 0 \
        and row["fallbacks"] == 0 and row["llm_turns"] == 0, (
        "legal policies take real turns, refuse nothing, fall back never, and no "
        "seat was marked as a model: %r" % (row,))
    assert len(log_lines) == row["turns"], (
        "one record per TURN: %d records for %d turns — a retry written as its "
        "own line is a decision that never happened"
        % (len(log_lines), row["turns"]))
    assert [line["turn"] for line in log_lines] == list(range(1, row["turns"] + 1)), (
        "the records number the turns 1, 2, 3... with no gaps: %r"
        % ([line["turn"] for line in log_lines][:8],))
    assert row["hand_gain_a"] == sum(call["hand_gain_a"] for call in calls) \
        and row["hand_gain_b"] == sum(call["hand_gain_b"] for call in calls), (
        "the row's piedras are the hand records' own SUMS — this match's hands "
        "paid 87/6 piedras and the last one paid 44/0, so a row holding the last "
        "hand's numbers is a different, smaller match: %r vs %r"
        % ((row["hand_gain_a"], row["hand_gain_b"]),
           ([c["hand_gain_a"] for c in calls], [c["hand_gain_b"] for c in calls])))
    assert row["vacas_a"] == calls[-1]["vacas_a"] == 2 \
        and row["vacas_b"] == calls[-1]["vacas_b"] == 0, (
        "the vacas are a RUNNING total: this match's hands report 0-0, 1-0 and "
        "2-0, so the match ends at 2-0 — a row that sums the records reports 3 "
        "vacas and hands the team a vaca every time one is counted, and the "
        "first record alone reports a match that never scored: %r vs %r"
        % ((row["vacas_a"], row["vacas_b"]),
           (calls[-1]["vacas_a"], calls[-1]["vacas_b"])))
    assert row["hand_wins_a"] + row["hand_wins_b"] <= row["hands"], (
        "a tied hand is a win for neither side, so the wins cannot exceed the "
        "hands: %r" % (row,))
    assert all(call["kind"] == "hand" and len(call["dealt"]) == 4
               and all(len(hand) == 4 for hand in call["dealt"]) for call in calls), (
        "each hand record is a hand, with the four hands as dealt: %r" % (calls,))
    assert [call["dealt"] for call in calls] == row["deals"], (
        "the hand record's dealt snapshot and the match's are the same cards: "
        "both are taken when the hand starts, and a hand record whose 16 cards "
        "are read at the end of the hand is a snapshot of the mus exchange — "
        "%r vs %r" % ([call["dealt"] for call in calls], row["deals"]))
    assert len(row["deals"]) == 3 and all(
        len(deal) == 4 and all(len(hand) == 4 for hand in deal)
        for deal in row["deals"]), (
        "the row carries one as-dealt snapshot per hand played: %r"
        % (row["deals"],))

    # --- the deal is as dealt, not as the hand left it ----------------------
    fresh = Table(seed=23)
    fresh.deal()
    assert row["deals"][0] == [[str(card) for card in fresh.hands[seat]]
                               for seat in range(4)], (
        "the first hand's record matches the cards a FRESH table with the same "
        "seed was dealt: a snapshot taken after the hand records the exchange, "
        "and then two runs of one seed look like two different deals — recorded "
        "%r, dealt %r" % (row["deals"][0],
                          [[str(c) for c in fresh.hands[s]] for s in range(4)]))
    other = s.run_match(Table(seed=23), heuristic_policy(5), names=names, hands=3)
    assert other["deals"] == row["deals"], (
        "the same seed deals the same cards no matter who is playing: the deal "
        "is forked from the seed BEFORE any decision — random play saw %r, the "
        "heuristic saw %r" % (row["deals"], other["deals"]))
    assert s.run_match(Table(seed=24), random_policy(3), names=names,
                       hands=3)["deals"] != row["deals"], (
        "and a different seed deals different cards: the as-dealt snapshot is a "
        "fact about the seed, which is why the mirrored pair can compare on it")

    # --- a refused attempt is not a turn ------------------------------------
    log_lines = []
    row = s.run_match(Table(seed=17),
                      scripted([{"action": "nonsense"}, {"action": "no"}]),
                      names=names, hands=1, turn_limit=1,
                      log=stage_03.DecisionLog(
                          lambda text: log_lines.append(json.loads(text))))
    assert row["status"] == "degraded" and "turn_limit" in row["note"], (
        "the rail with `turn_limit=1` stops the match after one accepted action "
        "with a note that says which rail fired: %r" % (row,))
    assert row["turns"] == 1 and row["rejections"] == 1, (
        "one refusal then one legal action is ONE turn and one refusal — a retry "
        "charged as a turn would make a seat that stumbles look busier and, in "
        "any per-turn rate, better behaved: %r" % (row,))
    assert len(log_lines) == 1 and log_lines[0]["ok"] is True, (
        "and the log holds one line: the refused attempt is counted, not "
        "recorded as a decision the seat made: %r" % (log_lines,))

    # --- the fallback comes from the engine --------------------------------
    log_lines = []
    stumbled = scripted([{"action": "nonsense"}] * 3)   # three attempts, retries=2
    row = s.run_match(Table(seed=17),
                      [stumbled, random_policy(11), random_policy(12),
                       random_policy(13)],
                      names=names, llm=[True, False, False, False], hands=1,
                      retries=2,
                      log=stage_03.DecisionLog(
                          lambda text: log_lines.append(json.loads(text))))
    assert row["status"] == "done" and row["fallbacks"] == 1, (
        "a seat that cannot produce a legal action gets the engine's own default "
        "and the match goes on — a fallback built from a legal NAME is refused "
        "the moment a payload is required, which files the harness's mistake "
        "against the seat: %r" % (row,))
    assert row["rejections"] == 3, (
        "three attempts, three refusals, one fallback: the refusals are the "
        "seat's and the fallback is ours, and they are counted in their own "
        "buckets: %r" % (row,))
    fallback_lines = [line for line in log_lines if line["fallback"]]
    assert len(fallback_lines) == 1 and fallback_lines[0]["model"] == "red", (
        "and the forced action is flagged in its own record: %r" % (log_lines,))

    # --- and a fallback is not the model's turn -----------------------------
    row = s.run_match(Table(seed=17), scripted([{"action": "nonsense"}] * 3),
                      names=names, llm=[True, False, False, False], hands=1,
                      retries=2, turn_limit=1)
    assert row["turns"] == 1 and row["fallbacks"] == 1, (
        "one turn landed, and it was the harness's default: %r" % (row,))
    assert row["llm_turns"] == 0, (
        "so the model took no turn at all — counting the fallback would let the "
        "harness's own defaults pad the denominator the fallback rate is judged "
        "against, which is exactly how a degraded model looks healthy: %r"
        % (row,))

    # --- llm_turns counts the model's own seats -----------------------------
    row = s.run_match(Table(seed=19), random_policy(4), names=names,
                      llm=[True, False, False, False], hands=2)
    assert 0 < row["llm_turns"] < row["turns"], (
        "one of four seats is a model, so the model's turns are a share of the "
        "match's turns — counting every seat's turns makes `llm_turns` the match "
        "length, and the fallback rate divides by it: %r" % (row,))

    # --- a tie is a win for neither side ------------------------------------
    row = s.run_match(Table(seed=11),
                      [heuristic_policy(1), random_policy(2),
                       heuristic_policy(3), random_policy(4)],
                      names=names, hands=3)
    assert row["status"] == "done" and row["hands"] == 3, (
        "this seed deals a hand nobody takes: %r" % (row,))
    assert row["hand_wins_a"] + row["hand_wins_b"] < row["hands"], (
        "a hand with no winner is a win for neither team: crediting a tie to one "
        "side hands that side a free win in every match that has one, and the "
        "wins stop summing to the hands (%d + %d vs %d): %r"
        % (row["hand_wins_a"], row["hand_wins_b"], row["hands"], row))

    # --- the watchdog fires -------------------------------------------------
    row = s.run_match(Table(seed=17), random_policy(6), names=names, hands=1,
                      turn_limit=3)
    assert row["status"] == "degraded" and "turn_limit" in row["note"], (
        "a hand that takes more than `turn_limit` accepted actions stops the "
        "match: the mus round alone is four actions, so this rail always fires at "
        "three — a watchdog that never fires turns a policy bug into a hang: %r"
        % (row,))
    assert row["hands"] == 0 and len(row["deals"]) == 1, (
        "no hand finished, and the hand that started still has its deal recorded "
        "— the deal happened, the hand did not: %r" % (row,))

    row = s.run_match(Table(seed=17),
                      scripted([{"action": "nonsense"}, {"action": "no"}]),
                      names=names, hands=1, turn_limit=2)
    assert row["turns"] == 2 and row["rejections"] == 1, (
        "the rail counts TURNS, not attempts: with `turn_limit=2`, a first turn "
        "that stumbled once and a second that did not are two turns and the rail "
        "fires after them — counting calls would stop this match after one turn "
        "stayed on the board: %r" % (row,))

    # --- the fallback rail fires, after its warmup --------------------------
    row = s.run_match(Table(seed=17), scripted([{"action": "nonsense"}] * 200),
                      names=names, hands=3, retries=0)
    assert row["status"] == "degraded" and "fallbacks" in row["note"], (
        "a match that is mostly the harness's defaults is not about the seats and "
        "stops: %r" % (row,))
    assert row["fallbacks"] == s.FALLBACK_WARMUP + 1, (
        "the rail sits one past the warmup: %d fallbacks are tolerated, the next "
        "one stops the match — a rail without the warmup abandons a match over "
        "one bad answer: %r" % (s.FALLBACK_WARMUP, row))
    assert row["turns"] == s.FALLBACK_WARMUP + 1, (
        "each turn was one call plus the engine's default: %r" % (row,))

    # --- a bug is not a result ----------------------------------------------
    def raiser(table, seat, legal):
        raise RuntimeError("the seat blew up")

    row = s.run_match(Table(seed=17), [raiser, random_policy(7),
                                       random_policy(8), random_policy(9)],
                      names=names, hands=1)
    assert row["status"] == "error", (
        "a failure that is not the engine refusing is OUR bug: reporting it as a "
        "finished match puts a harness bug into the results as a data point: %r"
        % (row,))
    assert "RuntimeError" in row["note"] and "blew up" in row["note"], (
        "the row keeps the exception's own words, so the bug is visible: %r"
        % (row["note"],))
    assert row["hands"] == 0 and row["turns"] == 0, (
        "and it carries what the match actually managed: %r" % (row,))

    row = s.run_match(Table(seed=17), scripted(["not a dict"]), names=names,
                      hands=1)
    assert row["status"] == "done" and row["rejections"] == 1, (
        "a seat that answers with something the engine cannot look at is refused "
        "like any other illegal action: the refusal is counted, the seat is asked "
        "again, and the match goes on — the engine validates the payload, so the "
        "harness never has to: %r" % (row,))

def check_3():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    RECORD_KEYS = ("phase", "lance", "mano", "seat", "team", "legal", "strength",
                   "would_win", "points_a", "points_b", "vacas_a", "vacas_b",
                   "hand_gain_a", "hand_gain_b", "facing_bet", "stake", "previous",
                   "holder_team", "turn", "hand", "model", "action", "confidence",
                   "rejections", "fallback", "ok", "reason")

    def _advance(table, s, stats, *, want, limit=60):
        """Play engine defaults (preferring a quiet "no" in the mus round) until the
        seat to move has `want` among its legal actions."""
        for _ in range(limit):
            seat = table.current_seat
            legal = table.legal_actions(seat)
            if want in legal:
                return seat
            if "no" in legal:
                action = {"action": "no"}
            else:
                action = table.default_action(seat)
            assert action is not None, "the engine has a default for every phase"
            outcome = s.gate(table, seat, action, stats=stats)
            assert outcome["ok"], "the engine's own default is legal: %r" % (outcome,)
        raise AssertionError("never reached an action list containing %r" % (want,))

    import stage_01
    import stage_03 as s
    from mus import Card, Table, team_of

    # --- the snapshot, in the mus round -------------------------------------
    table = Table(seed=11)
    table.deal()
    seat = table.current_seat
    snap = s.truth_snapshot(table, seat)
    assert set(snap) == set(s.SNAPSHOT_KEYS), (
        "the snapshot is exactly the frozen set of facts a seat can see, got %r"
        % (sorted(snap),))
    assert snap["phase"] == table.phase.name and snap["seat"] == seat, (
        "the snapshot names the phase and the seat, got %r" % (snap,))
    assert snap["team"] == team_of(seat) and snap["mano"] == table.mano, (
        "the snapshot is from the seat's own view: its team and who is mano, %r"
        % (snap,))
    assert snap["legal"] == list(table.legal_actions(seat)), (
        "the legal names in the snapshot are the ENGINE's list, not a copy of the "
        "rules: %r vs %r" % (snap["legal"], table.legal_actions(seat)))
    assert snap["lance"] is None and snap["strength"] is None \
        and snap["would_win"] is None, (
        "outside the lances there is no lance, no strength comparison and no "
        "lance winner to report — None, never a zero: %r" % (snap,))
    assert snap["facing_bet"] is False and snap["stake"] == 0 \
        and snap["previous"] == 0 and snap["holder_team"] is None, (
        "nobody has bet yet: nothing on the table, nothing owed, no holder, %r"
        % (snap,))

    # --- the snapshot is the INPUT to the action ---------------------------
    stats = stage_01.new_stats()
    seat = _advance(table, stage_01, stats, want="envido")
    pre = s.truth_snapshot(table, seat)
    assert pre["facing_bet"] is False and pre["stake"] == 0, (
        "a seat about to open a lance is not facing a bet: %r" % (pre,))
    assert pre["lance"] is not None, (
        "the envite is opened inside a lance, and the snapshot names it: %r"
        % (pre,))
    outcome = stage_01.gate(table, seat, {"action": "envido"}, stats=stats)
    assert outcome["ok"], "envido is legal for this seat: %r" % (outcome,)
    envite = table.envite
    assert any(envite["facing"].values()), (
        "after a bet somebody is being asked to answer it: %r" % (envite,))
    facing = next(s_ for s_ in range(4) if envite["facing"][s_])
    post = s.truth_snapshot(table, facing)
    assert post["stake"] > 0 and post["stake"] != pre["stake"], (
        "the bet landed: the table now holds %r where it held %r"
        % (post["stake"], pre["stake"]))
    assert post["holder_team"] == pre["team"], (
        "and the holder of the bet is the seat that made it: %r" % (post,))
    assert post["facing_bet"] is True, (
        "the opposing seats are now facing a bet: %r" % (post,))

    line = s.decision_line(table, seat, {"action": "envido", "confidence": 0.5},
                           stats=stats, snapshot=pre, model="seat-a")
    assert line["stake"] == pre["stake"] == 0 and line["facing_bet"] is False, (
        "the record describes the position the seat DECIDED in: it faced nothing "
        "and staked nothing, even though the table has moved on — got stake %r "
        "and facing %r" % (line["stake"], line["facing_bet"]))
    assert line["action"] == {"action": "envido"} and line["confidence"] == 0.5, (
        "the record carries the action as the ENGINE saw it — the wire dict, read "
        "one level down by every later stage — and the confidence the seat "
        "declared as its own field: %r" % (line,))
    assert line["turn"] == stats["turns"] and line["ok"] is True \
        and line["reason"] is None, (
        "one record per turn, and an accepted action has nothing to explain: %r"
        % (line,))
    assert line["fallback"] is False and line["rejections"] == 0, (
        "the seat's own move, taken without a refusal: %r" % (line,))
    assert line["hand"] == table.hand_index and line["model"] == "seat-a", (
        "the record says WHICH hand and WHICH model, so a match is comparable: %r"
        % (line,))
    assert set(line) == set(RECORD_KEYS), (
        "the record is exactly the frozen keys — the seat's payload is not copied "
        "in, and nothing is invented: extra %r, missing %r"
        % (sorted(set(line) - set(RECORD_KEYS)),
           sorted(set(RECORD_KEYS) - set(line))))
    assert set(pre) == set(s.SNAPSHOT_KEYS), (
        "building the record leaves the caller's snapshot alone: the snapshot is "
        "the evidence of what the seat faced, and the log entry is a copy of it, "
        "not the same dict: %r" % (sorted(set(pre) - set(s.SNAPSHOT_KEYS)),))

    # --- a refusal is recorded as a refusal ---------------------------------
    seat = table.current_seat
    bad = s.decision_line(table, seat, {"action": "nonsense"}, stats=stats,
                          snapshot=s.truth_snapshot(table, seat),
                          model="seat-b", ok=False,
                          reason="illegal action 'nonsense'")
    assert bad["ok"] is False and bad["reason"] == "illegal action 'nonsense'", (
        "a refused action keeps its own record, with the engine's words: %r"
        % (bad,))

    # --- a fallback is flagged, and an unknown payload is dropped -----------
    flagged = s.decision_line(table, seat,
                              {"action": "no", "fallback": True},
                              stats=stats,
                              snapshot=s.truth_snapshot(table, seat),
                              model="seat-c")
    assert flagged["fallback"] is True, (
        "an action the harness forced on a seat that could not answer is marked "
        "as such, or it is counted as the seat's own choice: %r" % (flagged,))
    assert flagged["action"] == {"action": "no"}, (
        "and the two fields the harness owns stay out of the action: the wire "
        "dict the engine sees is the seat's own, with no `fallback` flag riding "
        "in it and no `confidence` either — the record has keys for both: %r"
        % (flagged["action"],))

    extra = s.decision_line(table, seat, {"action": "no", "thought": "hmm"},
                            stats=stats,
                            snapshot=s.truth_snapshot(table, seat),
                            model="seat-f")
    assert set(extra) == set(RECORD_KEYS), (
        "the record has exactly the frozen keys: whatever else a seat puts in its "
        "decision dict stays inside the action and does not become a field of the "
        "line every later stage reads — extra %r"
        % (sorted(set(extra) - set(RECORD_KEYS)),))
    assert extra["action"] == {"action": "no", "thought": "hmm"}, (
        "it stays where a seat's own data belongs: %r" % (extra["action"],))

    payload = s.decision_line(table, seat,
                              {"action": "discard", "cards": ["rey de oros"]},
                              stats=stats,
                              snapshot=s.truth_snapshot(table, seat),
                              model="seat-e")
    assert payload["action"] == {"action": "discard", "cards": ["rey de oros"]}, (
        "the action's payload is part of the decision and survives into the "
        "record: a discard is only readable as WHICH cards were thrown: %r"
        % (payload["action"],))

    # --- what a confidence may be ------------------------------------------
    snapshot = s.truth_snapshot(table, seat)
    for value in (True, False, "0.5", -0.1, 1.5, [0.5], float("nan")):
        try:
            s.decision_line(table, seat, {"action": "no", "confidence": value},
                            stats=stats, snapshot=snapshot, model="seat-d")
        except ValueError:
            pass
        else:
            raise AssertionError(
                "a confidence of %r is not a probability: a bool is 1 or 0 in "
                "Python (a yes/no answer would be scored as a perfectly "
                "calibrated one) and anything outside [0, 1] is a units bug, not "
                "a number to clamp" % (value,))
    for value, expected in ((None, None), (0.0, 0.0), (1.0, 1.0), (0, 0.0), (1, 1.0)):
        ok_line = s.decision_line(table, seat,
                                  {"action": "no", "confidence": value},
                                  stats=stats, snapshot=snapshot, model="seat-d")
        assert ok_line["confidence"] == expected, (
            "a confidence is a probability or None, and the bounds are "
            "inclusive: %r became %r" % (value, ok_line["confidence"]))

    # --- the record must be a record ---------------------------------------
    try:
        s.decision_line(table, seat, "no", stats=stats, snapshot=snapshot,
                        model="seat-d")
    except TypeError:
        pass
    else:
        raise AssertionError("a decision that is not a dict is a bug in the "
                             "caller, not a record")
    for bad_action in ({}, {"action": ""}, {"action": 7}):
        try:
            s.decision_line(table, seat, bad_action, stats=stats,
                            snapshot=snapshot, model="seat-d")
        except ValueError:
            pass
        else:
            raise AssertionError(
                "a decision must NAME its action — %r has no name to record"
                % (bad_action,))
    try:
        s.decision_line(table, seat, {"action": "no"}, stats=stats,
                        snapshot={"phase": "MUS_REQUEST"}, model="seat-d")
    except ValueError:
        pass
    else:
        raise AssertionError(
            "the snapshot passed in must be the whole frozen set of facts — a "
            "partial one records a decision nobody made")

    # --- the log ------------------------------------------------------------
    sink = []
    log = s.DecisionLog(sink.append)
    text = log.record(line)
    assert len(sink) == 1 and sink[0] == text, (
        "one record is handed to the sink exactly once, and the text returned is "
        "the text written: %r" % (sink,))
    assert text.endswith("\n") and text.count("\n") == 1, (
        "a JSONL line is one line: %r" % (text,))
    assert json.loads(text) == line, (
        "the record survives the round trip through JSON: %r vs %r"
        % (json.loads(text), line))
    pairs = json.loads(text, object_pairs_hook=lambda pairs: pairs)
    assert [k for k, _ in pairs] == sorted(k for k, _ in pairs), (
        "the keys are written sorted: two runs of the same seed must produce the "
        "same bytes, and dict insertion order is not a guarantee — got %r"
        % ([k for k, _ in pairs],))
    assert log.lines == 1, "the log counts the records it wrote: %r" % (log.lines,)
    second = log.record(dict(line, turn=line["turn"] + 1))
    assert log.lines == 2 and len(sink) == 2 and second != text, (
        "each record is its own line, with no state carried in the text: %r"
        % (sink,))
    assert {k for k, _ in json.loads(second, object_pairs_hook=lambda p: p)} \
        == set(RECORD_KEYS), "every record carries the whole frozen key set"
    try:
        log.record({"card": Card("rey", "oros")})
    except TypeError:
        pass
    else:
        raise AssertionError(
            "a value that is not JSON-serialisable is a bug in the record — a "
            "`default=str` fallback writes an object's repr into a field the "
            "analysis will read as a name, and no check downstream can see it")
    assert log.lines == 2 and len(sink) == 2, (
        "a record that could not be written is not counted, and nothing was "
        "handed to the sink: %r / %r" % (log.lines, sink))
    try:
        s.DecisionLog(None)
    except TypeError:
        pass
    else:
        raise AssertionError("the sink must be callable: it is handed each line")

def check_4():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def dec(hand, lance, seat, team, action, *, turn=0, model=None, stake=0,
            previous=0):
        """One frozen decision line (contract §2), built by hand.

        `turn` is the log-order handle this check uses to name who is who; the two
        snapshot numbers (`stake`, `previous`) are the ones the seat faced when it
        was asked to decide, which is what its answer is measured against.
        """
        return {"turn": turn, "hand": hand, "seat": seat, "team": team,
                "model": model or ("m%d" % seat), "phase": "ENVITE", "lance": lance,
                "action": {"action": action}, "legal": ["quiero", "no-quiero"],
                "confidence": None, "rejections": 0, "fallback": False,
                "strength": None, "would_win": None,
                "points_a": 0, "points_b": 0, "vacas_a": 0, "vacas_b": 0,
                "hand_gain_a": 0, "hand_gain_b": 0,
                "facing_bet": False, "stake": stake, "previous": previous,
                "holder_team": None, "ok": True, "reason": None}

    def pairs_of(links):
        """The (aggressor_turn, responder_turn) pairs, in the order they came back."""
        return [(link["aggressor_turn"], link["responder_turn"]) for link in links]

    import stage_04 as s

    # --- the two tuples the rest of the course reads ------------------------
    assert tuple(s.AGGRESSIVE) == ("envido", "y-yo", "reenvido", "ordago"), (
        "the four actions that put a stake on the table are the aggression: an "
        "envite, a y-yo, a reenvido and an ordago, got %r" % (s.AGGRESSIVE,))
    assert tuple(s.RESPONSES) == ("quiero", "no-quiero", "envido", "y-yo",
                                  "reenvido", "ordago"), (
        "an answer is a fold, a call, or another raise — a rival answers an "
        "envite by raising back too, so the four aggressions are answers, got "
        "%r" % (s.RESPONSES,))

    # --- an aggression nobody answered yields no link ------------------------
    lonely = [dec(1, "Grande", 0, 0, "envido", turn=1)]
    got = s.link_responses(lonely)
    assert got == [], (
        "an aggression nobody answered yields NO link at all — not a link to "
        "itself and not a link with a kind of None: the envite at turn 1 has no "
        "rival response after it in hand 1's Grande, so there is nothing to "
        "link, got %r" % (got,))

    # --- a response lives in ONE lance --------------------------------------
    across_lance = [
        dec(1, "Grande", 0, 0, "envido", turn=1),
        dec(1, "Chica", 1, 1, "no-quiero", turn=2, stake=2, previous=1),
    ]
    got = s.link_responses(across_lance)
    assert got == [], (
        "a line in another lance of the same hand is not an answer: the Chica "
        "fold at turn 2 answers hand 1's Chica, not an envite made in Grande, "
        "so the envite at turn 1 is unanswered, got %r" % (got,))

    # --- a response lives in ONE hand ---------------------------------------
    across_hand = [
        dec(1, "Grande", 0, 0, "envido", turn=1),
        dec(2, "Grande", 1, 1, "no-quiero", turn=2, stake=2, previous=1),
    ]
    got = s.link_responses(across_hand)
    assert got == [], (
        "hand 2's fold is the answer to hand 2's bet and not to hand 1's: a "
        "response lives in one hand, so the hand-1 envite at turn 1 is "
        "unanswered, got %r" % (got,))

    # --- only an aggression leads a link ------------------------------------
    passive = [
        dec(1, "Grande", 0, 0, "paso", turn=1),
        dec(1, "Grande", 1, 1, "quiero", turn=2, stake=2, previous=1),
        dec(1, "Grande", 0, 0, "no-quiero", turn=3, stake=2, previous=1),
    ]
    got = s.link_responses(passive)
    assert got == [], (
        "only a decision whose action is in AGGRESSIVE leads a link: a paso, a "
        "quiero and a no-quiero are things the table said back, not bets asking "
        "for an answer, so none of them gets a link of its own, got %r" % (got,))

    # --- the link reads (aggressor, responder) ------------------------------
    direction = [
        dec(1, "Grande", 0, 0, "envido", turn=1),
        dec(1, "Grande", 1, 1, "no-quiero", turn=2, stake=2, previous=1),
    ]
    links = s.link_responses(direction)
    assert pairs_of(links) == [(1, 2)], (
        "each link reads (aggressor_turn, responder_turn): the turn of the line "
        "that bet comes first, the turn of the rival line that answered second, "
        "got %r" % (links,))

    # --- a partner is skipped, not a stop -----------------------------------
    partner_paso = [
        dec(1, "Grande", 0, 0, "envido", turn=1),
        dec(1, "Grande", 2, 0, "paso", turn=2),
        dec(1, "Grande", 1, 1, "no-quiero", turn=3, stake=3, previous=2),
    ]
    links = s.link_responses(partner_paso)
    assert pairs_of(links) == [(1, 3)], (
        "the partner's paso at turn 2 is SKIPPED — never the answer and never "
        "the end of the scan — so the rival's fold at turn 3 is still the "
        "answer to the envite at turn 1, got %r" % (links,))

    # --- the aggressor's own team is never the answer ------------------------
    partner_quiero = [
        dec(1, "Grande", 0, 0, "envido", turn=1),
        dec(1, "Grande", 2, 0, "quiero", turn=2, stake=5, previous=5),
        dec(1, "Grande", 1, 1, "no-quiero", turn=3, stake=3, previous=2),
    ]
    links = s.link_responses(partner_quiero)
    assert [(l["aggressor_turn"], l["responder_turn"], l["kind"])
            for l in links] == [(1, 3, "fold")], (
        "the partner's quiero at turn 2 is the aggressor's OWN team answering "
        "itself: it is skipped, never the answer, so the link for the envite at "
        "turn 1 points at the rival's fold at turn 3, got %r" % (links,))

    # --- ... and each aggression of a lance keeps that one rival answer ------
    partner_y_yo = [
        dec(1, "Grande", 0, 0, "envido", turn=1),
        dec(1, "Grande", 2, 0, "y-yo", turn=2),
        dec(1, "Grande", 1, 1, "no-quiero", turn=3, stake=4, previous=2),
    ]
    links = s.link_responses(partner_y_yo)
    assert [(l["aggressor_turn"], l["responder_turn"], l["kind"])
            for l in links] == [(1, 3, "fold"), (2, 3, "fold")], (
        "the rival fold at turn 3 is the answer to BOTH aggressions of that "
        "hand and lance — one link each, turn 1's envite and turn 2's y-yo, "
        "whose own team is skipped as the ANSWER but whose own raise still gets "
        "its own link — and no-quiero is a fold for both, got %r" % (links,))

    # --- a rival line that is not a response does not end the scan ----------
    interrupted = [
        dec(1, "Chica", 0, 0, "envido", turn=1),
        dec(1, "Chica", 1, 1, "paso", turn=2),
        dec(1, "Chica", 1, 1, "no-quiero", turn=3, stake=3, previous=1),
    ]
    links = s.link_responses(interrupted)
    assert [(l["aggressor_turn"], l["responder_turn"]) for l in links] \
        == [(1, 3)], (
        "a rival line that is not an answer (the paso at turn 2) is skipped: "
        "the first rival RESPONSE is the fold at turn 3, and ending the scan at "
        "the paso reports an envite that WAS answered as unanswered, got %r"
        % (links,))

    # --- the FIRST answer is the one that counts ----------------------------
    twice = [
        dec(1, "Grande", 0, 0, "envido", turn=1),
        dec(1, "Grande", 1, 1, "quiero", turn=2, stake=2, previous=1),
        dec(1, "Grande", 3, 1, "no-quiero", turn=3, stake=6, previous=5),
    ]
    links = s.link_responses(twice)
    assert [(l["aggressor_turn"], l["responder_turn"], l["kind"])
            for l in links] == [(1, 2, "call")], (
        "the answer to the stake that was on the table is the FIRST rival "
        "response: the call at turn 2. The later fold at turn 3 answers a "
        "different stake, and keeping the last match turns a called envite into "
        "a folded one, got %r" % (links,))

    # --- the responder's snapshot, floored at 1 -----------------------------
    floored = [
        dec(2, "Grande", 1, 1, "envido", turn=1),
        dec(2, "Grande", 0, 0, "no-quiero", turn=2, stake=0, previous=0),
    ]
    links = s.link_responses(floored)
    assert len(links) == 1 and links[0]["fold_gain"] == 1, (
        "a fold with nothing on the table (previous 0) still collects the deje, "
        "and the deje is never less than 1: fold_gain 0 says folding won "
        "nothing, got %r" % (links,))
    assert links[0]["stake"] == 1, (
        "the responder's snapshot stake floors at 1 too: a call that risks "
        "'nothing' still risks the minimum, got %r" % (links,))

    # --- ... and both numbers come off the RESPONDER's line ------------------
    stakes = [
        dec(1, "Grande", 0, 0, "envido", turn=1, stake=9, previous=8),
        dec(1, "Grande", 1, 1, "quiero", turn=2, stake=3, previous=4),
    ]
    links = s.link_responses(stakes)
    assert (links[0]["stake"], links[0]["fold_gain"]) == (3, 4), (
        "the stakes are the RESPONDER's snapshot, not the aggressor's: the seat "
        "at turn 2 faced a stake of 3 with 4 already on the table, while the "
        "bettor's own line says 9 and 8 — a call risks what the caller saw, and "
        "a fold collects the deje the folder saw, got %r" % (links,))

    # --- no lance, no link --------------------------------------------------
    no_lance = [
        dec(1, None, 0, 0, "envido", turn=1),
        dec(1, None, 1, 1, "no-quiero", turn=2, stake=2, previous=1),
        dec(1, "Grande", 0, 0, "envido", turn=3),
        dec(1, "Grande", 1, 1, "no-quiero", turn=4, stake=2, previous=1),
    ]
    links = s.link_responses(no_lance)
    assert pairs_of(links) == [(3, 4)], (
        "a decision with lance None belongs to no lance at all, so it is "
        "neither an aggression nor an answer: the turn-1 envite gets no link, "
        "and turn 2's no-quiero cannot answer the Grande envite at turn 3 (only "
        "turn 4 can), got %r" % (links,))

    # --- the whole log: 3 hands, 2 lances, a partner in between, a fold, a
    # call, a raise, and an aggression nobody answered ------------------------
    log = [
        dec(1, "Grande", 0, 0, "envido", turn=1, model="aggr-a"),
        dec(1, "Grande", 2, 0, "y-yo", turn=2, model="partner-p"),
        dec(1, "Grande", 2, 0, "paso", turn=3, model="partner-p"),
        dec(1, "Grande", 1, 1, "paso", turn=4, model="rival-x"),
        dec(1, "Grande", 1, 1, "no-quiero", turn=5, model="rival-x", stake=2,
            previous=0),
        dec(1, "Chica", 1, 1, "reenvido", turn=6, model="rival-x"),
        dec(1, "Chica", 3, 1, "ordago", turn=7, model="rival-y"),
        dec(1, "Chica", 0, 0, "quiero", turn=8, model="aggr-a", stake=3,
            previous=4),
        dec(1, "Chica", 3, 1, "reenvido", turn=9, model="rival-y"),
        dec(2, "Chica", 2, 0, "envido", turn=10, model="partner-p"),
        dec(2, "Chica", 1, 1, "paso", turn=11, model="rival-x"),
        dec(2, "Grande", 1, 1, "y-yo", turn=12, model="rival-x"),
        dec(3, "Chica", 3, 1, "envido", turn=13, model="rival-y"),
        dec(3, "Grande", 0, 0, "quiero", turn=14, model="aggr-a", stake=5,
            previous=3),
        dec(3, "Chica", 0, 0, "no-quiero", turn=15, model="aggr-a", stake=6,
            previous=9),
        dec(3, "Grande", 0, 0, "envido", turn=16, model="aggr-a"),
        dec(3, "Grande", 3, 1, "ordago", turn=17, model="rival-y", stake=8,
            previous=2),
    ]
    frozen = [dict(line) for line in log]
    links = s.link_responses(log)
    by_turn = {link["aggressor_turn"]: link for link in links}
    assert 9 not in by_turn and 10 not in by_turn, (
        "an aggression nobody answered gets NO link at all: the reenvido at "
        "turn 9 (hand 1 Chica) and the envido at turn 10 (hand 2 Chica) have no "
        "rival response left in their own hand and lance — turn 12 is hand 2's "
        "Grande and turn 13 belongs to hand 3 — so an aggression can never be "
        "answered by its own line or by another hand's, got %r"
        % (sorted(by_turn),))
    assert pairs_of(links) == [(1, 5), (2, 5), (6, 8), (7, 8), (13, 15),
                               (16, 17)], (
        "the links are exactly (aggressor_turn, responder_turn) in play order — "
        "(1, 5), (2, 5), (6, 8), (7, 8), (13, 15), (16, 17): the turn of the "
        "bet comes first and the turn of the rival that answered second, and "
        "every aggression that WAS answered has its own pair, got %r"
        % (pairs_of(links),))
    a1 = by_turn[1]
    assert (a1["hand"], a1["lance"], a1["team"]) == (1, "Grande", 0), (
        "the link carries the aggression's own coordinates: hand 1, lance "
        "Grande, and the TEAM that bet (0) — not the responder's team, got %r"
        % (a1,))
    assert a1["model"] == "aggr-a" and a1["responder"] == "rival-x", (
        "the link names two models — the one that bet and the one that "
        "answered: aggr-a and rival-x, got %r" % (a1,))
    assert a1["kind"] == "fold" and a1["responder_turn"] == 5, (
        "no-quiero is a fold, and the answer is the first rival line that "
        "RESPONDED: turn 5 — not the partner's y-yo at turn 2 and not the "
        "rival's paso at turn 4, got %r" % (a1,))
    assert (a1["stake"], a1["fold_gain"]) == (2, 1), (
        "the stakes come off the responder's snapshot: turn 5 faced a stake of "
        "2 with previous 0 on the table, so a call risks 2 and the fold "
        "collects the floored deje 1, got %r" % (a1,))
    a2p = by_turn[2]
    assert (a2p["model"], a2p["responder"], a2p["kind"], a2p["responder_turn"]) \
        == ("partner-p", "rival-x", "fold", 5), (
        "the partner's y-yo is an aggression of its own and keeps its OWN first "
        "rival answer: partner-p's raise at turn 2 is folded by rival-x at turn "
        "5 exactly like the envite at turn 1 — one rival fold, two links — and "
        "consuming the response for the first aggression loses a real one, got "
        "%r" % (a2p,))
    a2 = by_turn[6]
    assert (a2["kind"], a2["responder_turn"], a2["team"]) == ("call", 8, 1), (
        "quiero is a CALL of the stake that was on the table: hand 1's Chica, "
        "turn 8, and the link stays in the aggression's team (1), got %r"
        % (a2,))
    assert (a2["stake"], a2["fold_gain"]) == (3, 4), (
        "the stakes are the responder's snapshot: turn 8 faced a stake of 3 "
        "with previous 4 on the table, got %r" % (a2,))
    a5 = by_turn[16]
    assert a5["kind"] == "raise", (
        "an ordago back is a RAISE, not a call: the rival at turn 17 pushed the "
        "stake higher instead of accepting it, and lumping the two reads every "
        "re-raise as a resigned yes, got %r" % (a5["kind"],))
    assert (a5["stake"], a5["fold_gain"]) == (8, 2), (
        "a raise still carries the responder's snapshot: stake 8, previous 2, "
        "got %r" % (a5,))
    assert log == frozen, (
        "the decision log is the wire shape stage 3 recorded: linking is a "
        "READING of it, so the input comes back unchanged and the links are "
        "what is new, got %r" % (log,))

    # --- nothing to link ----------------------------------------------------
    assert s.link_responses([]) == [], (
        "an empty log links nothing: a reader is called on whatever the run "
        "produced, including nothing, got %r" % (s.link_responses([]),))

def check_5():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    BETTING = ("envido", "y-yo", "reenvido", "ordago")

    RESPONSES = ["quiero", "no-quiero", "paso"]

    def dec(**over):
        """One decision in the frozen shape (`f1-contract.md` §2). Every field is
        filled: a stage reads some of them positionally."""
        decision = {
            "turn": 0, "hand": 1, "seat": 0, "team": 0, "model": "m0",
            "phase": "ENVITE", "lance": "Grande", "action": {"action": "paso"},
            "legal": ["paso"], "confidence": None, "rejections": 0,
            "fallback": False, "strength": None, "would_win": None,
            "points_a": 0, "points_b": 0, "vacas_a": 0, "vacas_b": 0,
            "hand_gain_a": 0, "hand_gain_b": 0, "facing_bet": False, "stake": 0,
            "previous": 0, "holder_team": None, "ok": True, "reason": None,
        }
        decision.update(over)
        return decision

    def _log():
        """The fixture log, built by hand.

          Grande   eight measured hands that faced a bet, arriving out of order,
                   strengths 0.1..0.8 -> cut (0.3, 0.6); plus one bet-capable hand
                   nobody measured, which must not shift the cut;
                   plus four Grande hands that could NOT bet with tempting
                   strengths 0.85..1.0, which must not move the cut either
          Chica    five measured hands that faced a bet (0.90..0.98) plus one
                   unmeasured bet-capable hand -> no cut
          Pares    six hands that could NOT bet, strengths 0.01..0.06 -> no entry
          Puntos   one bet-capable hand, never measured -> an entry with no cut
          plus a bet-capable decision with no lance named, and a seat answering a
          bet rather than making one: neither is a bet on a lance.
        """
        betting = ["envido", "y-yo", "paso"]
        recs = []
        for strength in (0.5, 0.1, 0.8, 0.3, 0.6, 0.2, 0.7, 0.4):
            recs.append(dec(lance="Grande", strength=strength, legal=list(betting)))
        recs.append(dec(lance="Grande", strength=None, legal=list(betting)))
        for strength in (0.85, 0.90, 0.95, 1.0):
            recs.append(dec(lance="Grande", strength=strength,
                            legal=["paso", "quiero"]))
        for strength in (0.98, 0.90, 0.96, 0.92, 0.94):
            recs.append(dec(lance="Chica", strength=strength, legal=list(betting)))
        recs.append(dec(lance="Chica", strength=None, legal=list(betting)))
        for strength in (0.01, 0.02, 0.03, 0.04, 0.05, 0.06):
            recs.append(dec(lance="Pares", strength=strength, legal=["paso"]))
        recs.append(dec(lance=None, strength=0.42, legal=list(betting)))
        recs.append(dec(lance="Grande", strength=0.45, legal=list(RESPONSES)))
        recs.append(dec(lance="Puntos", strength=None, legal=list(betting)))
        return recs

    import stage_04
    import stage_05 as s

    # --- the floor and the verbs ------------------------------------------
    assert s.MIN_REFERENCE == 6, (
        "six hands is the smallest reference that splits into three non-empty "
        "thirds: at five, one third of the distribution is a single hand and "
        "every hand compared against that third is compared against that one "
        "hand (MIN_REFERENCE)")

    assert tuple(stage_04.AGGRESSIVE) == BETTING, (
        "the betting verbs are the engine's four aggressive actions, envido, "
        "y-yo, reenvido and ordago, and stage 5 reads them from stage 4: a "
        "second copy of the list is a threshold that drifts the day stage 4 "
        "learns a new verb (%r)" % (stage_04.AGGRESSIVE,))

    # --- who faced a bet ---------------------------------------------------
    assert s.can_bet(dec(lance="Grande", legal=["paso", "envido"])) is True, (
        "a seat whose legal actions include an aggressive verb holds a live "
        "betting option: the engine's `legal` list is the only thing that "
        "answers that question, and it says yes (can_bet)")
    assert s.can_bet(dec(lance="Grande", legal=["paso"])) is False, (
        "a seat that may only pass never chose under pressure: it belongs in "
        "the reference no more than a hand dealt to a seat that had no turn "
        "(can_bet)")
    assert s.can_bet(dec(lance="Grande", legal=[])) is False, (
        "an empty legal list is not a turn at all, so it cannot be a betting "
        "option (can_bet)")
    assert s.can_bet(dec(lance=None, legal=["envido"])) is False, (
        "an envite with no lance named is not a bet on a lance: there is no "
        "distribution to compare the hand against, and counting it lands a "
        "strength in a pool keyed by None (can_bet)")
    assert s.can_bet(dec(lance="Grande", legal=["quiero", "no-quiero"])) is False, (
        "answering an envite is not making one: 'quiero' and 'no-quiero' are "
        "responses, and only the aggressive verbs put a new stake on the "
        "table (AGGRESSIVE)")

    # --- the reference itself ----------------------------------------------
    log = _log()
    cuts = s.strength_terciles(log)

    assert cuts.get("Grande") == (0.3, 0.6), (
        "eight measured hands 0.1..0.8 cut at vals[n // 3] and vals[2 * n // 3] "
        "gives (0.3, 0.6): the bottom cut is the hand a third of the way in, "
        "the top cut is the hand two thirds of the way in, and both are hands "
        "the reference itself contains (%r)" % (cuts.get("Grande"),))

    assert cuts.get("Chica", "absent") is None, (
        "five measured hands do not make a tercile: one third of five hands is "
        "a single hand, so the lance has no cut until MIN_REFERENCE of them "
        "have faced a bet, and a fabricated cut would call the second-best of "
        "five a 'weak' hand (%r)" % (cuts.get("Chica", "absent"),))

    assert "Pares" not in cuts, (
        "the reference is the hands that FACED a bet: a seat whose legal "
        "actions were only pass and answer never met an envite, and pooling "
        "its hand lets the threshold drift with who happened to be dealt the "
        "option rather than with the hands (strength_terciles)")

    assert cuts.get("Puntos", "absent") is None, (
        "a lance enters the reference as soon as one of its decisions was "
        "bet-capable, and a pool with nothing measured in it has a cut of None: "
        "'no cut yet' and 'no lance' are different facts, and a report that "
        "cannot tell them shows a lance of four hands as a lance that never "
        "faced a bet (strength_terciles)")

    assert set(cuts) == {"Grande", "Chica", "Puntos"}, (
        "the reference holds exactly one entry per lance that faced a bet, "
        "keyed by the lance name -- a key of None is a bet on no lance and a "
        "key of 'Pares' is a bet nobody offered (%r)" % (sorted(cuts, key=str),))

    assert s.strength_terciles([dict(d, model="other") for d in log]) == cuts, (
        "the threshold is a property of the hands, not of who held them: "
        "renaming the model must not move a cut, or every model is measured "
        "against a distribution of its own and the comparison the scorecard "
        "rests on is not there (strength_terciles)")

    assert s.strength_terciles([dict(d) for d in log]) == cuts, (
        "the same log cuts the same way twice: a reference that moves between "
        "calls makes two scorecards of the same run incomparable "
        "(strength_terciles)")

    # --- the two boundaries, and the hands that sit on them ----------------
    assert s.strength_band(dec(lance="Grande", strength=0.3), cuts) == "weak", (
        "0.3 IS the bottom cut -- one of the eight hands the cut was read from "
        "-- and the hand exactly on it is weak: the bottom third is inclusive "
        "at its top (`s <= lo`), and calling that hand medium files an "
        "observed weak hand one band too high (strength_band)")
    assert s.strength_band(dec(lance="Grande", strength=0.6), cuts) == "medium", (
        "0.6 IS the top cut and the hand exactly on it is still medium: the "
        "top third begins strictly above it (`s > hi`), because moving 0.6 up "
        "to strong leaves medium holding one hand fewer than the third it "
        "names (strength_band)")
    assert s.strength_band(dec(lance="Grande", strength=0.29), cuts) == "weak", (
        "a hand just under the bottom cut is in the bottom third, so `<= lo` "
        "and `< lo` differ only on the cut value itself (strength_band)")
    assert s.strength_band(dec(lance="Grande", strength=0.31), cuts) == "medium", (
        "a hand just over the bottom cut is medium: the bottom third ends at "
        "0.3, not at everything below it (strength_band)")
    assert s.strength_band(dec(lance="Grande", strength=0.61), cuts) == "strong", (
        "a hand just over the top cut is strong: strengths are percentiles in "
        "[0, 1] and the three bands tile the range (strength_band)")

    bands = [s.strength_band(d, cuts) for d in log
             if d["lance"] == "Grande" and d["strength"] is not None
             and s.can_bet(d)]
    assert len(bands) == 8 and bands.count("weak") == 3 \
        and bands.count("medium") == 3 and bands.count("strong") == 2, (
        "the eight hands that faced a bet divide 3 weak / 3 medium / 2 strong: "
        "the eighth hand is the remainder the top third keeps, and any "
        "off-by-one at either cut moves exactly one of these hands into the "
        "neighbouring band (%r)" % (bands,))

    # --- nothing to measure ------------------------------------------------
    assert s.strength_band(dec(lance="Grande", strength=None), cuts) is None, (
        "a decision with no measured strength has no band: None is the absence "
        "of a measurement, and letting it fall to the bottom of the scale "
        "records an unmeasured hand as a weak one (strength_band)")
    assert s.strength_band(dec(lance="Chica", strength=0.93), cuts) is None, (
        "Chica's reference is five hands, so it has no cut and none of its "
        "hands has a band: 0.93 means nothing against a distribution that was "
        "never measured (strength_band)")
    assert s.strength_band(dec(lance="Puntos", strength=0.5), cuts) is None, (
        "a lance whose pool is empty has no cut, and a band without a "
        "reference is a claim about a distribution nobody observed "
        "(strength_band)")
    assert s.strength_band(dec(lance="Pares", strength=0.01), cuts) is None, (
        "a lance that never faced a bet is not in the reference at all, and "
        "the lookup has to miss instead of inventing a scale for it "
        "(strength_band)")
    assert s.strength_band(dec(lance=None, strength=0.5), cuts) is None, (
        "a decision with no lance has no distribution to be placed in, "
        "whatever its strength says (strength_band)")
    assert s.strength_band(dec(lance="Grande", strength=0.5), {}) is None, (
        "no cuts is no bands: an empty reference returns None rather than "
        "raising or guessing (strength_band)")
    assert s.strength_terciles([]) == {}, (
        "a log with no decisions has no reference, not an exception: the "
        "function is called on whatever the run produced, including nothing "
        "(strength_terciles)")

def check_6():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    BET_LEGAL = ("paso", "envido", "ordago")

    NO_BET_LEGAL = ("quiero", "no-quiero")

    NOTHING_LEGAL = ()

    SCORE_KEYS = frozenset((
        "decisions", "aggressive", "bet_chances", "aggression_rate", "bluffs",
        "value_bets", "bluff_rate", "weak_hand_bet_rate", "value_bet_rate",
        "avg_strength_when_betting", "bluff_folded", "bluff_called", "bluff_success",
        "value_folded", "value_called", "value_bet_fold_rate", "stake_won_folds",
        "stake_lost_called_bluffs", "fold_equity", "faced_winning", "fold_error",
        "fold_error_rate", "faced_losing", "payoff", "payoff_rate",
    ))

    RATE_KEYS = ("aggression_rate", "bluff_rate", "weak_hand_bet_rate",
                 "value_bet_rate", "avg_strength_when_betting", "bluff_success",
                 "value_bet_fold_rate", "fold_error_rate", "payoff_rate")

    def dec(hand, seat, team, action, *, turn=0, model=None, lance="Grande",
            strength=0.5, legal=BET_LEGAL, would_win=None, facing_bet=False,
            stake=0, previous=0, holder_team=None):
        """One frozen decision record (contract §2), by hand.

        `action` goes in as the wire dict `{"action": name}` — the shape
        `Table.apply` accepts and that stages 4 and 6 both have to read one level
        down.
        """
        return {
            "turn": turn, "hand": hand, "seat": seat, "team": team,
            "model": "m%d" % team if model is None else model,
            "phase": "ENVITE", "lance": lance, "action": {"action": action},
            "legal": list(legal), "confidence": None, "rejections": 0,
            "fallback": False, "strength": strength, "would_win": would_win,
            "points_a": 0, "points_b": 0, "vacas_a": 0, "vacas_b": 0,
            "hand_gain_a": 0, "hand_gain_b": 0, "facing_bet": facing_bet,
            "stake": stake, "previous": previous, "holder_team": holder_team,
            "ok": True, "reason": None,
        }

    def _reference(lance="Grande", count=30, hand0=900, turn0=9000):
        """The bet-capable pool that gives one lance a real cut.

        Thirty decisions at 30/31/.../59 strength, all holding a betting option and
        none of them betting: the tierce cut of this lance lands in that spread, so
        a fixture hand at 0.2 is weak and one at 0.9 is strong BY CONSTRUCTION, and
        the check is pinning the scorecard, not re-deriving the cut.
        """
        return [dec(hand0 + i, 3, 1, "paso", turn=turn0 + i, model="campos",
                    lance=lance, strength=0.30 + 0.01 * i, legal=BET_LEGAL)
                for i in range(count)]

    def _shape(card, who):
        missing = SCORE_KEYS - set(card)
        assert not missing, (
            "the scorecard for %s is missing metrics the contract names (%s): a "
            "risk table read by a report must carry all of them, a rate included"
            % (who, ", ".join(sorted(missing))))

    def _rate_is_none(card, who, key):
        assert card[key] is None, (
            "%s.%s is %r: with no denominator the rate is not 0.0 — 0.0 reads as "
            "'never did it', which is what a perfect player reports, so the seat that "
            "was never asked the question would top the table" % (who, key, card[key]))

    import stage_06 as s

    reference = _reference()

    # --- the bluff is a WEAK-HAND bet, not a losing one --------------------
    # Eight bets from 0.9 strength hands, every one of which LOSES its lance.
    # They are value bets, all eight of them.
    losing = [dec(hand, 0, 0, "envido", turn=10 + hand, model="duro",
                  strength=0.9, would_win=False)
              for hand in range(1, 9)]
    # six weak hands that could bet and passed (they only shape the counts)
    quiet_weak = [dec(8 + hand, 0, 0, "paso", turn=20 + hand, model="mate",
                      strength=0.2)
                  for hand in range(6)]
    card = s.scorecard(reference + losing + quiet_weak)["duro"]
    _shape(card, "duro")
    assert card["bluff_rate"] == 0.0, (
        "a bet from a STRONG hand that lost the lance is not a bluff: with two "
        "hands a team wins any lance about half the time, so 'bet and then lost' "
        "measures the base rate of the game and not the player — eight losing "
        "0.9-strength bets read bluff_rate %r" % (card["bluff_rate"],))
    assert card["bluffs"] == 0 and card["value_bets"] == 8, (
        "the eight losing bets are value bets — a strong hand pushing — so a "
        "table reporting bluffs %r and value_bets %r has classified them by "
        "their outcome and not by the hand they were made from"
        % (card["bluffs"], card["value_bets"]))
    assert card["aggressive"] == 8 and card["bluff_rate"] == 0.0, (
        "bluff_rate is 0.0 over a non-empty denominator (8 bets), which is a "
        "measurement, not an absence: reading %r of %r bets means the bluffs "
        "were counted from something other than the weak hands"
        % (card["bluff_rate"], card["aggressive"]))
    assert card["aggression_rate"] == 1.0, (
        "every one of those eight decisions held a betting option and bet, so "
        "aggression_rate is a certain 1.0 — reading %r means the chances were "
        "counted from something other than the betting options stage 5 "
        "identifies" % (card["aggression_rate"],))
    assert card["avg_strength_when_betting"] == 0.9, (
        "the average strength of the hands it bet from is the bets' own 0.9 — "
        "reading %r is the average of every decision it made, weak passes "
        "included, which measures the hands it was DEALT and not the hands it "
        "chose to bet" % (card["avg_strength_when_betting"],))

    # --- a called bluff that WINS is not a loss ---------------------------
    won_call = [
        dec(1, 0, 0, "envido", turn=30, model="gana", strength=0.2,
            would_win=True),
        dec(1, 1, 1, "quiero", turn=31, model="rival", strength=None,
            legal=NO_BET_LEGAL, facing_bet=True, stake=4, previous=2,
            holder_team=0, would_win=False),
    ]
    card = s.scorecard(reference + won_call)["gana"]
    assert card["bluffs"] == 1 and card["bluff_called"] == 1, (
        "the weak bet was called by the opposition, so one bluff was answered by "
        "a call — a table reading bluffs %r and bluff_called %r has lost the "
        "answer to the bet" % (card["bluffs"], card["bluff_called"]))
    assert card["stake_lost_called_bluffs"] == 0, (
        "a called bluff is only PAID when the lance is LOST: this bluff wins the "
        "lance, so the call hands the bettor the pot — charging the responder's 4 "
        "to stake_lost_called_bluffs (it reads %r) reports a profitable bluff as "
        "a loss" % (card["stake_lost_called_bluffs"],))
    assert card["fold_equity"] == 0, (
        "fold_equity nets the folds won against the calls paid; a bluff that won "
        "and was called nets 0, and %r means the call was booked as a payment"
        % (card["fold_equity"],))

    # --- the PARTNER's answer is not the answer ---------------------------
    # The partner raises the aggressor's own bet first; the opposition then
    # folds. The link stage 4 makes is the FOLD.
    partner_first = [
        dec(2, 0, 0, "envido", turn=40, model="solo", strength=0.2,
            would_win=True),
        dec(2, 2, 0, "reenvido", turn=41, model="socio", strength=0.2,
            legal=BET_LEGAL, facing_bet=True, stake=2, previous=1,
            holder_team=0),
        dec(2, 1, 1, "no-quiero", turn=42, model="rival2", strength=None,
            legal=NO_BET_LEGAL, facing_bet=True, stake=3, previous=2,
            holder_team=0),
    ]
    card = s.scorecard(reference + partner_first)["solo"]
    assert card["bluff_folded"] == 1 and card["bluff_called"] == 0, (
        "the aggressor's own team answering itself is not the answer: the "
        "partner's reenvido was the first later action in the lance, but the "
        "opposition's no-quiero is the response — bluff_folded %r, bluff_called "
        "%r" % (card["bluff_folded"], card["bluff_called"]))
    assert card["stake_won_folds"] == 2, (
        "the fold collects the deje the responder had on the table, its "
        "`previous` of 2 — a fold worth %r was read from the aggressor's own "
        "snapshot instead of the responder's"
        % (card["stake_won_folds"],))

    # --- fold error and payoff need a bet from the OTHER team -------------
    responses = [
        # folds a lance it would have won, facing an opponent -> an error
        dec(3, 0, 0, "no-quiero", turn=50, model="yugo", lance=None,
            strength=None, legal=NO_BET_LEGAL, would_win=True, facing_bet=True,
            holder_team=1),
        # calls a lance it loses, facing an opponent -> pays off
        dec(4, 0, 0, "quiero", turn=51, model="yugo", lance=None, strength=None,
            legal=NO_BET_LEGAL, would_win=False, facing_bet=True, holder_team=1),
        # folds a lance it loses: the fold was right, no payoff
        dec(5, 0, 0, "no-quiero", turn=52, model="yugo", lance=None,
            strength=None, legal=NO_BET_LEGAL, would_win=False,
            facing_bet=True, holder_team=1),
        # the PARTNER holds the bet: the team's points are the team's points,
        # so neither a fold error nor a payoff
        dec(6, 0, 0, "quiero", turn=53, model="yugo", lance=None, strength=None,
            legal=NO_BET_LEGAL, would_win=False, facing_bet=True, holder_team=0),
        dec(7, 0, 0, "no-quiero", turn=54, model="yugo", lance=None,
            strength=None, legal=NO_BET_LEGAL, would_win=True, facing_bet=True,
            holder_team=0),
    ]
    cards = s.scorecard(reference + responses)
    card = cards["yugo"]
    assert (card["faced_winning"], card["fold_error"]) == (1, 1), (
        "folding to the PARTNER's bet is not a fold error: only an opponent's "
        "bet is one this seat can fold to — facing %r winning bets and folding "
        "%r of them means the holder's team was never consulted"
        % (card["faced_winning"], card["fold_error"]))
    assert card["fold_error_rate"] == 1.0, (
        "the one lance it was winning against an opponent, it folded: a "
        "fold_error_rate of %r is read over a different set of decisions than the "
        "winning lances it actually faced" % (card["fold_error_rate"],))
    assert (card["faced_losing"], card["payoff"]) == (2, 1), (
        "one of the two lances lost against an opponent was called and one was "
        "folded: a fold to a lost lance is not a payoff, and the partner's bet is "
        "neither — %r losing lances and %r payoffs means a fold, or the partner's "
        "bet, was paid off"
        % (card["faced_losing"], card["payoff"]))
    assert card["payoff_rate"] == 0.5, (
        "one payoff out of the two losing lances it faced; reading %r counts the "
        "fold to a lost lance as a payoff" % (card["payoff_rate"],))
    # key="seat" is the same aggregation one column over
    by_seat = s.scorecard(responses, key="seat")
    assert set(by_seat) == {"0"}, (
        "key='seat' buckets by str(decision['seat']), and every one of these is "
        "seat 0: keys %r" % (sorted(by_seat),))
    assert by_seat["0"]["faced_winning"] == 1, (
        "the seat view is the same aggregation: seat 0 faced one winning lance, "
        "while the seat table reports %r" % (by_seat["0"]["faced_winning"],))

    # --- weak_hand_bet_rate divides by the WEAK opportunities --------------
    # Four weak-hand bets, two weak hands that passed, two strong hands that
    # passed, and one decision with no betting option at all.
    mix = [dec(10 + i, 0, 0, "envido", turn=100 + i, model="mezcla",
               strength=0.2) for i in range(4)]
    mix += [dec(14 + i, 0, 0, "paso", turn=110 + i, model="mezcla",
                strength=0.2) for i in range(2)]
    mix += [dec(16 + i, 0, 0, "paso", turn=120 + i, model="mezcla",
                strength=0.9) for i in range(2)]
    mix += [dec(18, 0, 0, "paso", turn=130, model="mezcla", strength=0.5,
                legal=NO_BET_LEGAL)]
    card = s.scorecard(reference + mix)["mezcla"]
    assert card["bluffs"] == 4 and card["bet_chances"] == 8, (
        "four bets from weak hands out of eight betting chances — the ninth "
        "decision held no aggressive verb, so it is not a chance: %r bluffs over "
        "%r chances counts a decision that never had the option"
        % (card["bluffs"], card["bet_chances"]))
    assert card["bluff_rate"] == 1.0, (
        "every one of its four bets came from a weak hand, so bluff_rate (bluffs "
        "over BETS) is a certain 1.0; %r is bluffs over the betting chances, "
        "which folds the hands it did not bet into the question"
        % (card["bluff_rate"],))
    assert abs(card["weak_hand_bet_rate"] - 4.0 / 6.0) < 1e-9, (
        "weak_hand_bet_rate answers 'of the weak hands I could bet with, how "
        "often did I push?', 4 of 6 — %r is the ratio over the bets the seat made "
        "(4) or over every chance (8), both of which answer a different question"
        % (card["weak_hand_bet_rate"],))
    assert card["aggression_rate"] == 0.5, (
        "four bets out of eight chances; %r means the chances were counted from "
        "something other than the betting options"
        % (card["aggression_rate"],))
    assert card["avg_strength_when_betting"] == 0.2, (
        "the four bets all came from 0.2-strength hands, so the average of the "
        "hands it BET from is 0.2 — %r is dominated by the strong hands it passed "
        "on, which measures the deal and not the choice"
        % (card["avg_strength_when_betting"],))

    # --- no denominator is None, never 0.0 --------------------------------
    quiet = [
        dec(8, 3, 1, "paso", turn=60, model="prudente", lance=None,
            strength=None, legal=NOTHING_LEGAL),
        dec(9, 3, 1, "paso", turn=61, model="prudente", lance=None,
            strength=None, legal=NOTHING_LEGAL),
    ]
    card = s.scorecard(reference + quiet)["prudente"]
    _shape(card, "prudente")
    assert card["decisions"] == 2 and card["aggressive"] == 0, (
        "two decisions, no bets: %r decisions and %r bets"
        % (card["decisions"], card["aggressive"]))
    for key in RATE_KEYS:
        _rate_is_none(card, "prudente", key)
    assert card["fold_equity"] == 0 and card["bluffs"] == 0, (
        "the counters of a seat that was never in a spot are real zeros, the "
        "rates are None: %r" % (card,))

    # --- a bet with no cut is neither weak nor strong ----------------------
    uncut = [dec(20, 0, 0, "envido", turn=140, model="novato", lance="Chico",
                 strength=0.9, would_win=False)]
    card = s.scorecard(reference + uncut)["novato"]
    assert card["aggressive"] == 1, (
        "a bet is a bet even in a lance too thin to band; counting %r of them "
        "means the band was used as the test for what a bet is"
        % (card["aggressive"],))
    assert card["bluffs"] == 0 and card["value_bets"] == 0, (
        "one hand is not a tercile: with no cut the band is None, and a bet with "
        "no band is neither a bluff nor a value bet — %r bluffs and %r value bets "
        "means a missing cut was read as a weak (or strong) hand"
        % (card["bluffs"], card["value_bets"]))
    assert card["bluff_rate"] == 0.0 and card["value_bet_rate"] == 0.0, (
        "the bet counted in the denominator of both rates and in neither "
        "numerator: %r and %r"
        % (card["bluff_rate"], card["value_bet_rate"]))

    # --- each aggressor gets its OWN answer, in the same hand and lance ----
    # The envite is answered by the fold at turn 201; the reenvido that follows
    # is itself answered by the quiero at turn 203. One (hand, lance) holds two
    # aggressors and two different answers.
    twins = [
        dec(21, 0, 0, "envido", turn=200, model="ataca", strength=0.2,
            would_win=True),
        dec(21, 1, 1, "no-quiero", turn=201, model="rival3", strength=None,
            legal=NO_BET_LEGAL, facing_bet=True, holder_team=0, stake=2,
            previous=1),
        dec(21, 3, 1, "reenvido", turn=202, model="responde", strength=0.9,
            legal=BET_LEGAL, facing_bet=True, holder_team=0, stake=4,
            previous=3),
        dec(21, 2, 0, "quiero", turn=203, model="socio3", strength=None,
            legal=NO_BET_LEGAL, facing_bet=True, holder_team=1),
    ]
    cards = s.scorecard(reference + twins)
    assert cards["ataca"]["bluff_folded"] == 1, (
        "the first opposing action in the lance answers THIS aggression: the "
        "no-quiero at turn 201 folds to the envido, so a table reporting %r folds "
        "has keyed the links by (hand, lance) and handed this aggressor the last "
        "answer written in the pair"
        % (cards["ataca"]["bluff_folded"],))
    assert cards["ataca"]["bluff_called"] == 0, (
        "the quiero at turn 203 answers the reenvido, not the envido, so 'ataca' "
        "was never called: reading %r means one answer was shared by two "
        "aggressors" % (cards["ataca"]["bluff_called"],))
    assert cards["responde"]["value_called"] == 1, (
        "the reenvido's answer is the quiero that follows it, not the fold that "
        "came before it: %r means the answer was taken from the wrong side of the "
        "bet" % (cards["responde"]["value_called"],))
    assert cards["responde"]["value_folded"] == 0, (
        "and it has no fold of its own to collect; %r folds means the fold before "
        "its bet was credited to it"
        % (cards["responde"]["value_folded"],))

    # --- fold equity nets the folds won against the calls PAID -------------
    odds = [
        dec(22, 0, 0, "envido", turn=210, model="apuesta", strength=0.2,
            would_win=False),
        dec(22, 1, 1, "no-quiero", turn=211, model="cede", strength=None,
            legal=NO_BET_LEGAL, facing_bet=True, stake=1, previous=3,
            holder_team=0),
        dec(23, 0, 0, "envido", turn=212, model="apuesta", strength=0.2,
            would_win=False),
        dec(23, 1, 1, "reenvido", turn=213, model="sube", strength=0.9,
            legal=BET_LEGAL, facing_bet=True, stake=6, previous=1,
            holder_team=0),
    ]
    card = s.scorecard(reference + odds)["apuesta"]
    assert card["bluffs"] == 2, (
        "two weak-hand bets, and %r bluffs means the bands were read from "
        "something other than the hands" % (card["bluffs"],))
    assert card["bluff_folded"] == 1 and card["stake_won_folds"] == 3, (
        "one weak bet was folded to, and the folder had 3 on the table to "
        "collect — %r folds and %r collected means the fold or the deje went "
        "missing" % (card["bluff_folded"], card["stake_won_folds"]))
    assert card["bluff_called"] == 1, (
        "a RAISE is the opposition declining to fold, exactly like a call: the "
        "reenvido answered the second bluff, so %r calls has dropped the loudest "
        "answers out of every success rate" % (card["bluff_called"],))
    assert card["stake_lost_called_bluffs"] == 6, (
        "the called bluff LOST its lance and the caller had 6 at risk, so 6 is "
        "what it paid — %r is read from the bettor's own snapshot, the wrong side "
        "of the table" % (card["stake_lost_called_bluffs"],))
    assert card["fold_equity"] == -3, (
        "fold_equity is what the weak bets WON by folds minus what they PAID when "
        "called and lost, 3 - 6 = -3: %r hides the bluffs that were called off"
        % (card["fold_equity"],))
    assert card["bluff_success"] == 0.5, (
        "of the two bluffs the opposition answered, one folded; the denominator "
        "is folds PLUS calls (and raises), so %r has narrowed the answer set"
        % (card["bluff_success"],))

    # --- the counters are ints, the rates floats or None -------------------
    card = s.scorecard(reference + losing)["duro"]
    for key, value in card.items():
        if key in RATE_KEYS:
            assert value is None or isinstance(value, float), (
                "%s is %r: a rate is a float or None, and a bool would sail "
                "through every comparison as 0 or 1" % (key, value))
        else:
            assert isinstance(value, int) and not isinstance(value, bool), (
                "%s is %r: every counter is an int" % (key, value))

def check_7():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    import stage_07 as s

    def dec(**over):
        """One record of the log, filled by hand.

        The hand records carry the point counters (`points_a`/`points_b`) exactly
        as the reference log does: the counters are what a column summed from them
        would read, and the vaca that fires mid-match zeroes them.
        """
        rec = {"kind": "hand", "hand": 1, "hand_gain_a": 0, "hand_gain_b": 0,
               "hand_winner": None, "points_a": 0, "points_b": 0,
               "vacas_a": 0, "vacas_b": 0,
               "dealt": [["rey de oros"], ["as de espadas"]]}
        rec.update(over)
        return rec

    # --- match A: six hands, and a vaca at hand 4 --------------------------
    # The vaca is a threshold: A's counter stood at 2 after hand 3, hand 4
    # awarded 40 more, the vaca was banked in vacas_a and BOTH counters went
    # back to zero. So the six hands left a counter reading 2 and awarded 42
    # piedras. Hand 6 is the tie: 0-0, so no winner.
    match_a = [
        dec(hand=1, hand_gain_a=0, hand_gain_b=1, hand_winner=1,
            points_a=0, points_b=1),
        dec(hand=2, hand_gain_a=0, hand_gain_b=1, hand_winner=1,
            points_a=0, points_b=2),
        dec(hand=3, hand_gain_a=2, hand_gain_b=1, hand_winner=0,
            points_a=2, points_b=3),
        dec(hand=4, hand_gain_a=40, hand_gain_b=3, hand_winner=0,
            points_a=0, points_b=0, vacas_a=1, vacas_b=0),
        dec(hand=5, hand_gain_a=0, hand_gain_b=1, hand_winner=1,
            points_a=0, points_b=1, vacas_a=1, vacas_b=0),
        dec(hand=6, hand_gain_a=0, hand_gain_b=0, hand_winner=None,
            points_a=0, points_b=1, vacas_a=1, vacas_b=0),
    ]
    # the per-decision rows share the log: this one is not a hand, however much
    # its own hand_gain_a looks like one.
    decision_row = dec(kind="decision", turn=9, hand=6, seat=2, team=1,
                       phase="DECLARE", lance=None, action={"action": "paso"},
                       hand_gain_a=999, hand_gain_b=999, hand_winner=0,
                       points_a=999, points_b=999)
    match_a_with_decoy = match_a + [decision_row]

    # --- match B: the other orientation, two hands, indexes from 1 again ----
    match_b = [
        dec(hand=1, hand_gain_a=4, hand_gain_b=1, hand_winner=0,
            points_a=4, points_b=1, vacas_a=1, vacas_b=0),
        dec(hand=2, hand_gain_a=2, hand_gain_b=1, hand_winner=0,
            points_a=6, points_b=2, vacas_a=1, vacas_b=0),
    ]
    pair = match_a + match_b

    out_a = s.outcome(match_a)
    counters_a = sum(r["points_a"] for r in match_a)

    # --- what the hands awarded, not what the counters read ----------------
    assert out_a["hands"] == 6, (
        "a match is the hands it played: six hand records are in the fixture and "
        "the outcome is over those six hands, got %r" % (out_a["hands"],))
    assert out_a["piedras_a"] == 42, (
        "the piedras are what the hands AWARDED: these six hands gave team A 42, "
        "and `points_a` sums to 2 because the vaca that fired at hand 4 banked "
        "forty points and zeroed both counters — a column summed from the counters "
        "reports the play still sitting on the counter, not the match, got %r"
        % (out_a["piedras_a"],))
    assert out_a["piedras_a"] - counters_a == 40, (
        "the piedras exceed the counter by exactly the vaca: forty points were "
        "banked and wiped from `points_a` while `hand_gain_a` went on counting "
        "them, so every vaca in a match is forty piedras a counter-summed outcome "
        "never sees, got %r against a counter of %r"
        % (out_a["piedras_a"] - counters_a, counters_a))
    assert out_a["piedras_b"] == 7, (
        "the vaca zeroes BOTH counters, so the loser's counter is no witness "
        "either: team B was awarded 7 piedras across these six hands while its "
        "counter sums to 9 — the counter is a running total, printed once per "
        "hand, got %r" % (out_a["piedras_b"],))
    assert out_a["piedras_per_hand_a"] == 7.0, (
        "the per-hand rate is the piedras over the hands played: 42 piedras across "
        "six hands is 7.0 a hand, and that is the number comparable between a "
        "six-hand match and a forty-hand one, got %r"
        % (out_a["piedras_per_hand_a"],))
    assert out_a["piedras_per_hand_b"] == 1.167, (
        "seven piedras over six hands is 1.1666... and the report spells it 1.167: "
        "the per-hand numbers are rounded to three decimals so two matches can be "
        "printed side by side, and an unrounded float is the same value under a "
        "different name, got %r" % (out_a["piedras_per_hand_b"],))
    assert out_a["piedras_diff_per_hand"] == 5.833, (
        "the difference is PER HAND and rounded to three decimals: 42 - 7 = 35 "
        "piedras over six hands is 5.833 a hand, while 35 is a match total whose "
        "size depends on how long the match ran, got %r"
        % (out_a["piedras_diff_per_hand"],))

    # --- a tie is a win for neither side -----------------------------------
    assert out_a["hand_wins_a"] == 2, (
        "a tie is a win for NEITHER side: hand 6 is the one hand where both teams "
        "took the same piedras (0-0), so team A won hands 3 and 4 and nothing else "
        "— counting the tie for A hands a team a win it did not earn, got %r"
        % (out_a["hand_wins_a"],))
    assert out_a["hand_wins_b"] == 3, (
        "and the tie is not a B win either: team B took hands 1, 2 and 5, and hand "
        "6 has no winner, got %r" % (out_a["hand_wins_b"],))
    assert out_a["hand_wins_a"] + out_a["hand_wins_b"] == 5, (
        "five of the six hands were decided: 2 + 3 = 5, and the hand whose "
        "hand_winner is None belongs to neither count, got %r"
        % (out_a["hand_wins_a"] + out_a["hand_wins_b"],))

    # --- the vacas are a running total, not a per-hand delta ---------------
    assert out_a["vacas_a"] == 1, (
        "the vaca counters are a RUNNING TOTAL, so only the LAST record holds "
        "where they ended: this match banked one vaca for A at hand 4 and the six "
        "records read 0, 0, 0, 1, 1, 1 — adding the snapshots up counts the same "
        "vaca once per hand that followed it, got %r" % (out_a["vacas_a"],))
    assert out_a["vacas_b"] == 0, (
        "team B never reached forty in this match, so its running total is 0 in "
        "every record; the A counter read into the B column reports a vaca the "
        "other team never banked, got %r" % (out_a["vacas_b"],))

    # --- the report's own shape -------------------------------------------
    fields = ["hands", "piedras_a", "piedras_b", "piedras_per_hand_a",
              "piedras_per_hand_b", "piedras_diff_per_hand", "vacas_a", "vacas_b",
              "hand_wins_a", "hand_wins_b"]
    assert sorted(out_a) == sorted(fields), (
        "the outcome is a fixed report of ten fields — each one is rendered by "
        "name, so a missing or renamed key is a dashboard printing nothing — and "
        "the fields are %r, got %r" % (fields, sorted(out_a)))

    # --- the decision rows in the log are not hands ------------------------
    out_with_decoy = s.outcome(match_a_with_decoy)
    assert out_with_decoy["hands"] == 6, (
        "only records whose `kind` is 'hand' are hands: the log also holds the "
        "per-decision rows, and this fixture's decision row carries a hand_gain_a "
        "of 999 — counting it as a hand adds a decision to the match and divides "
        "the per-hand rate by a row that never was a hand, got %r"
        % (out_with_decoy["hands"],))
    assert out_with_decoy == out_a, (
        "a decision row changes nothing about the outcome of a match: the same six "
        "hands, the same piedras, the same per-hand rate, got %r" % (out_with_decoy,))

    # --- the list is a PAIR: two matches, and both count their hands from 1 --
    out_pair = s.outcome(pair)
    assert out_pair["hands"] == 8, (
        "the list holds two matches — six hands in the first, two in the second, "
        "and both matches number their hands from 1 — so the outcome covers the 8 "
        "hands that were played: a count taken from the last record's `hand` says "
        "2 and one taken from the longest match says 6, and neither is the hands in "
        "the list, got %r" % (out_pair["hands"],))
    assert out_pair["piedras_a"] == 48, (
        "the piedras sum over every hand in the list: 42 from the first match plus "
        "6 from the second is 48, and the second match's hand indexes restarting at "
        "1 does not restart the sum, got %r" % (out_pair["piedras_a"],))
    assert out_pair["piedras_per_hand_a"] == 6.0, (
        "the per-hand rate divides by the 8 hands IN THE LIST — no single match is "
        "the denominator: 48 piedras over 8 hands is 6.0, while dividing by one "
        "match's hands reads 48/6 = 8.0 or 48/2 = 24.0, the rate of whichever match "
        "happened to be longer, got %r" % (out_pair["piedras_per_hand_a"],))
    assert out_pair["piedras_per_hand_b"] == 1.125, (
        "9 piedras over the same 8 hands is 1.125 a hand: the B column divides by "
        "the hands in the list too, got %r" % (out_pair["piedras_per_hand_b"],))
    assert out_pair["piedras_diff_per_hand"] == 4.875, (
        "the difference is (48 - 9) over the 8 hands of the pair, 4.875 a hand, so "
        "that one match's result cannot be divided into the other's, got %r"
        % (out_pair["piedras_diff_per_hand"],))
    assert out_pair["vacas_a"] == 1 and out_pair["vacas_b"] == 0, (
        "the pair's vacas are the running totals at the end of the LAST record, "
        "and the second match's records continue that running total instead of "
        "restarting it, got %r and %r"
        % (out_pair["vacas_a"], out_pair["vacas_b"]))
    assert out_pair["hand_wins_a"] == 4 and out_pair["hand_wins_b"] == 3, (
        "the wins count over every hand in the list: A took four of the eight — "
        "hands 3 and 4 of the first match and both hands of the second — and B took "
        "three, with one tie belonging to neither, got %r and %r"
        % (out_pair["hand_wins_a"], out_pair["hand_wins_b"]))

    # --- no hand records is not a match that scored nothing ----------------
    assert s.outcome([]) == {}, (
        "a match with no hand records has no outcome, and this stage pins `{}` for "
        "it: a dict of zeros cannot be told apart from a match where both teams "
        "really scored nothing, and a caller that prints it reports 0.000 piedras "
        "per hand for a match that never ran, got %r" % (s.outcome([]),))
    assert s.outcome([decision_row]) == {}, (
        "and a log whose only rows are decisions is the same nothing, whatever "
        "those rows carry, got %r" % (s.outcome([decision_row]),))

def check_8():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    import stage_08 as s

    # ---------------------------------------------------------------- surface ---
    assert s.EPS == 1e-6, (
        "the clip bound is 1e-6 and the reported ceiling of the log-loss is "
        "-ln(EPS) = 13.815510557964274 nats: any other bound reports a different "
        "price for the most confident possible miss, and a reader who checks that "
        "number against the table needs it to be this one, got %r" % (s.EPS,))

    # ------------------------------------------------- Brier: quadratic scale ---
    coinflip = [(0.5, h % 2 == 0) for h in range(10)]
    assert s.brier(coinflip) == 0.25, (
        "a coin-flip read against a half-and-half outcome scores 0.25: the Brier "
        "scale is quadratic, so (0.5 - 1)**2 and (0.5 - 0)**2 are a quarter each, "
        "while the 0.5 a mean ABSOLUTE error gives is the outcome's own spread — an "
        "absolute-error score cannot tell a coin from a model that learned nothing, "
        "got %r" % (s.brier(coinflip),))
    assert abs(s.brier([(0.9, True), (0.1, False)]) - 0.01) < 1e-12, (
        "a 0.9 on a hand that was won and a 0.1 on a hand that was lost costs "
        "(0.1)**2 + (0.1)**2 over two pairs = 0.01: the error is squared, so the "
        "same two absolute misses (0.1 and 0.1) would average to 0.1, got %r"
        % (s.brier([(0.9, True), (0.1, False)]),))
    assert s.brier([(1.0, True)]) == 0.0 and s.brier([(0.0, True)]) == 1.0, (
        "a certain prediction that came true costs 0.0 and a certain prediction "
        "that was wrong costs 1.0: the whole scale of the score, got %r / %r"
        % (s.brier([(1.0, True)]), s.brier([(0.0, True)])))
    assert s.brier([(0.5, True), (0.5, False)]) == s.brier([(0.5, 1), (0.5, 0)]), (
        "an outcome written `True`/`False` and one written `1`/`0` are the same "
        "outcome and must score the same, got %r vs %r"
        % (s.brier([(0.5, True), (0.5, False)]), s.brier([(0.5, 1), (0.5, 0)])))

    # --------------------------------------- log-loss: the probability of what
    #                                            happened, clipped so it is finite ---
    assert abs(s.logloss([(0.5, True), (0.5, False)]) - math.log(2)) < 1e-12, (
        "a 0.5 costs ln 2 = 0.6931 nats whichever way the hand went: the log-loss "
        "of 0.5 is symmetric in the outcome, which is what makes it a proper "
        "score, got %r" % (s.logloss([(0.5, True), (0.5, False)]),))
    assert abs(s.logloss([(0.9, True)]) + math.log(0.9)) < 1e-12, (
        "the loss is taken on the probability of what HAPPENED: a confident 0.9 "
        "that came true costs -ln(0.9) = 0.1054, got %r"
        % (s.logloss([(0.9, True)]),))
    assert abs(s.logloss([(0.9, False)]) + math.log(0.1)) < 1e-12, (
        "the same 0.9 on a hand that was LOST costs -ln(0.1) = 2.3026: logging the "
        "same side for both outcomes scores a confident miss as cheaply as a "
        "confident hit and hides the miss, got %r" % (s.logloss([(0.9, False)]),))

    clip = -math.log(1e-6)
    near = -math.log(1.0 - 1e-6)
    worst = s.logloss([(1.0, False)])
    assert worst is not None and math.isfinite(worst) and abs(worst - clip) < 1e-9, (
        "a read of 1.0 on a hand that was lost is the most confident possible "
        "miss, and it is worth -ln(1e-6) = 13.8155 nats, not an infinity: without "
        "the clip it is -ln(0), which is not a number a table can print and erases "
        "every other pair in the same mean, got %r" % (worst,))
    worst_true = s.logloss([(0.0, True)])
    assert (worst_true is not None and math.isfinite(worst_true)
            and abs(worst_true - clip) < 1e-9), (
        "a read of 0.0 on a hand that was WON is the same certain miss on the other "
        "side of the interval and costs the same 13.8155 nats, got %r"
        % (worst_true,))
    safe_false = s.logloss([(0.0, False)])
    assert (safe_false is not None and abs(safe_false - near) < 1e-12), (
        "a read of 0.0 on a hand that was LOST was as right as a probability can "
        "be and costs -ln(1 - 1e-6) = 1.0000005e-06 nats, not 0 \u2014 only the side "
        "the model got wrong is clipped up to the ceiling, got %r" % (safe_false,))
    safe_true = s.logloss([(1.0, True)])
    assert (safe_true is not None and abs(safe_true - near) < 1e-12), (
        "a read of 1.0 on a hand that was won is the same near-perfect prediction "
        "and costs 1.0000005e-06 nats, got %r" % (safe_true,))

    # ---------------------------------------------------------------- None ---
    for name, score in (("brier", s.brier), ("logloss", s.logloss), ("auc", s.auc)):
        value = score([])
        assert value is None, (
            "no data is not a score: %s of an empty pair list is None, not 0.0 — a "
            "0.0 reads as 'never wrong' on the Brier/loss scale and would put a "
            "model that was never asked a single read above every model that was, "
            "got %r" % (name, value))
    assert s.reliability([]) == [], (
        "no data is an empty table, not a table of zero-filled bins: a bin nothing "
        "landed in is not an observation, got %r" % (s.reliability([]),))

    # -------------------------------------------------- AUC: the ordering ---
    perfect = [(0.9, True), (0.8, True), (0.1, False), (0.2, False)]
    assert s.auc(perfect) == 1.0, (
        "every winning hand read above every losing one is an AUC of 1.0: this is "
        "the discrimination question and it is about the ORDER of the numbers, not "
        "their size, got %r" % (s.auc(perfect),))
    backwards = [(0.1, True), (0.2, True), (0.9, False), (0.8, False)]
    assert s.auc(backwards) == 0.0, (
        "a model that ranks every losing hand above every winning one has an AUC of "
        "0.0: the score is oriented so that a BETTER ranker scores HIGHER, and 1 - "
        "AUC is the same numbers read the wrong way round, got %r"
        % (s.auc(backwards),))
    mixed = [(0.9, True), (0.4, True), (0.3, True), (0.5, False), (0.1, False)]
    assert abs(s.auc(mixed) - 2.0 / 3.0) < 1e-12, (
        "the AUC is the mean over every (positive, negative) PAIR: 3 winning reads "
        "x 2 losing reads = 6 comparisons, and this model ordered 4 of them right "
        "(0.9 beats both losing reads, while 0.4 and 0.3 each beat the 0.1 and lose "
        "to the 0.5) — so dividing by the five ROWS mixes a pair count with a row "
        "count and turns a 2/3 ranking into 4/5, got %r" % (s.auc(mixed),))
    assert s.auc(coinflip) == 0.5, (
        "ten reads all at 0.5 order nothing, and a tie is half credit: counting a "
        "tie as a win scores a model whose read is one constant at 1.0 — a perfect "
        "ranker that ranks nothing, got %r" % (s.auc(coinflip),))
    for one_class in ([(0.3, True), (0.6, True)], [(0.3, False), (0.6, False)]):
        value = s.auc(one_class)
        assert value is None, (
            "discrimination needs both classes present: with one class there is no "
            "pair to order, so the number is not estimable and 0.5 would claim the "
            "model's ordering of two classes is a coin flip — a statement about a "
            "game that was never played, got %r" % (value,))

    # ------------------------------------------------------ strict input ---
    for bad in (True, False):
        for name, score in (("brier", s.brier), ("logloss", s.logloss),
                            ("auc", s.auc), ("reliability", s.reliability)):
            try:
                score([(bad, True)])
            except ValueError:
                continue
            raise AssertionError(
                "a bool was accepted as a probability by %s: `True` IS 1 to Python, "
                "so a read of `True` would score as a model that was certain and "
                "right, and a read of `False` as one that was certain and wrong — "
                "neither is a probability the model ever produced, got no error for "
                "p=%r" % (name, bad))
    for bad in (1.5, -0.1, 1.0000001):
        for name, score in (("brier", s.brier), ("logloss", s.logloss),
                            ("auc", s.auc), ("reliability", s.reliability)):
            try:
                score([(bad, True)])
            except ValueError:
                continue
            raise AssertionError(
                "p=%r was accepted as a probability by %s: a probability outside "
                "[0, 1] is a bug in the caller (a percentage that was never divided "
                "by 100, a logit, a typo), and clamping it silently upstream is the "
                "habit this stage refuses — the score would then describe a number "
                "the model never produced" % (bad, name))

    # ------------------------------------------------------- reliability ---
    edges = [(0.0, False), (0.2, False), (0.4, False), (0.6, False), (0.8, False),
             (1.0, True)]
    table = s.reliability(edges)
    assert len(table) == 5, (
        "0.0, 0.2, 0.4, 0.6, 0.8 and 1.0 fall in five different bins of five (a bin "
        "is the left-closed interval [i/bins, (i+1)/bins), so 0.2 opens the 0.2-0.4 "
        "bin and 1.0 closes the last one), got %r" % (table,))
    assert table[0]["bin"] == "0-0.2", (
        "the label is the bin's own edges: the bottom bin is 0-0.2 at five bins, "
        "got %r" % (table[0]["bin"],))
    assert table[-1]["bin"] == "0.8-1", (
        "p == 1.0 belongs to the LAST bin and its label says so (0.8-1 at five "
        "bins): 1.0 * 5 = 5 is not an index into five bins, so without the clamp "
        "the model's most confident predictions are dropped from the table, and the "
        "top of this table is exactly where overconfidence lives, got %r"
        % (table[-1]["bin"],))
    last = table[-1]
    assert (last["n"] == 2 and abs(last["mean_p"] - 0.9) < 1e-12
            and abs(last["actual"] - 0.5) < 1e-12), (
        "the last bin holds the (0.8, False) and (1.0, True) reads: two "
        "predictions, mean_p 0.9, and the hand was won half the time — actual 0.5 "
        "against a 0.9 prediction is the miscalibration the table exists to show, "
        "got %r" % (last,))
    sparse = s.reliability([(0.1, False), (0.9, True), (0.9, False)])
    assert [row["bin"] for row in sparse] == ["0-0.2", "0.8-1"], (
        "only the bins that hold a pair are reported, in ascending order: these "
        "three reads live in two bins, and a bin reported as n: 0, actual: 0.0 is a "
        "fabricated measurement — a reader cannot tell it from a bin whose "
        "predictions all missed, and in a ten-bin table over twenty reads the "
        "fabricated rows outnumber the real ones, got %r" % (sparse,))
    assert all(row["n"] > 0 for row in sparse), (
        "a reported bin always counted at least one prediction: %r" % (sparse,))
    assert s.reliability([(1.0, True)]) == [
        {"bin": "0.8-1", "n": 1, "mean_p": 1.0, "actual": 1.0}], (
        "one read of 1.0 lands in the last bin (0.8-1) with n 1 and actual 1.0: "
        "int(1.0 * 5) is 5, one past the end, so the clamp to bins - 1 is what "
        "keeps a certain read in the table instead of raising IndexError or "
        "inventing a sixth bin, got %r" % (s.reliability([(1.0, True)]),))

    single = s.reliability(edges, bins=1)
    assert single == [{"bin": "0-1", "n": 6, "mean_p": 0.5, "actual": 0.167}], (
        "one bin is the whole sample: mean_p 0.5 (the mean of 0.0, 0.2, 0.4, 0.6, "
        "0.8 and 1.0) and actual 1/6 = 0.167 — the three-decimal rounding is what "
        "makes two tables comparable, got %r" % (single,))
    thirds = s.reliability([(0.0, False), (0.5, False), (0.9, True), (1.0, True)],
                           bins=3)
    assert [row["bin"] for row in thirds] == ["0-0.333333", "0.333333-0.666667",
                                              "0.666667-1"], (
        "the edges are the bin's own fractions printed with %%g, so a third is "
        "0.333333 and not the 0.3 a one-decimal format would show: the label is how "
        "a reader knows which slice of the sample a calibration number came from, "
        "got %r" % ([row["bin"] for row in thirds],))

    try:
        s.reliability(edges, 5)
    except TypeError:
        pass
    else:
        raise AssertionError(
            "`bins` is keyword-only: `reliability(pairs, 5)` reads as if 5 were the "
            "pairs' own argument, and the frozen surface is `reliability(pairs, *, "
            "bins=5)`")
    try:
        s.reliability(edges, bins=0)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "bins=0 was accepted: a table with no bins holds no information and a "
            "bin width of 1/0 is not a width — that is a bug in the caller, not a "
            "table to print")

def check_9():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    REQUIRED_KEYS = ("label", "matches", "publishable", "degraded", "hands",
                     "piedras_for", "piedras_against", "piedras_per_hand",
                     "vacas_for", "vacas_against", "wins", "losses", "ties")

    LABELS = {"alpha", "beta", "gamma", "delta", "epsilon", "errored", "quiet",
              "yankee", "xray", "shared", "quebec", "romeo", "papa", "uniform",
              "victor"}

    def match(matchup="alpha vs beta", seed=0, teams=("alpha", "beta"),
              status="done", hands=10, llm_turns=100, fallbacks=0, turns=300,
              vacas_a=1, vacas_b=0, hand_gain_a=0, hand_gain_b=0, **over):
        """One match row in the frozen shape (`f1-contract.md` §2), every field
        filled by hand. `teams` is the pair the match was scheduled as: the two
        labels the leaderboard groups the row under."""
        row = {"matchup": matchup, "seed": seed, "teams": list(teams),
               "names": ["a", "b", "c", "d"], "llm": [True, False, True, False],
               "status": status, "hands": hands, "turns": turns,
               "llm_turns": llm_turns, "fallbacks": fallbacks, "rejections": 0,
               "vacas_a": vacas_a, "vacas_b": vacas_b, "hand_wins_a": 0,
               "hand_wins_b": 0, "hand_gain_a": hand_gain_a,
               "hand_gain_b": hand_gain_b, "deals": []}
        row.update(over)
        return row

    import stage_09 as s

    # --- the gate ----------------------------------------------------------
    assert s.MIN_LLM_CALLS == 50, (
        "the course gates every run at 50 model decisions, and this module "
        "ships a different floor: a 20-call match would be admitted as a "
        "season")
    assert abs(s.MAX_FALLBACK_RATIO - 0.15) < 1e-12, (
        "the fallback ceiling is 15 in 100 decisions, and this module ships a "
        "different ceiling: a rate-limit cascade would pass its gate")

    healthy = match(teams=("alpha", "beta"), hands=10, llm_turns=100,
                    fallbacks=0, vacas_a=2, vacas_b=1)
    assert s.is_publishable_match(healthy) is True, (
        "a finished match with 100 real model decisions, no fallback and a "
        "recorded score is exactly the evidence the leaderboard exists to rank")

    diluted = match(teams=("gamma", "beta"), hands=8, llm_turns=60, fallbacks=20,
                    turns=300, vacas_a=3, vacas_b=0)
    assert s.is_publishable_match(diluted) is False, (
        "a degraded model makes 20 fallbacks in its own 80 decisions — 25% — "
        "and the 220 baseline turns around it are other seats playing while it "
        "waited, so dividing by the match's 300 turns reads the same cascade as "
        "6.7% and publishes it at any ceiling")

    thin = match(teams=("uniform", "victor"), hands=8, llm_turns=20,
                 fallbacks=1, turns=300, vacas_a=1, vacas_b=0)
    assert s.is_publishable_match(thin) is False, (
        "20 model decisions is under the floor of 50 however clean the ratio "
        "looks, because a match that barely ran cannot rank a model")

    assert s.is_publishable_match(match(llm_turns=85, fallbacks=15)) is True, (
        "85 decisions with 15 fallbacks is exactly 15 in 100, and a match "
        "sitting on the ceiling is at it, not over it")
    assert s.is_publishable_match(match(llm_turns=84, fallbacks=15)) is False, (
        "84 decisions with 15 fallbacks is 15 in 99 — over the ceiling — and a "
        "ceiling that only bites at 16% lets the cascade through")

    assert s.is_publishable_match(match(llm_turns=50, fallbacks=0)) is True, (
        "50 decisions is the floor itself, and the published side starts there")
    assert s.is_publishable_match(match(llm_turns=49, fallbacks=0)) is False, (
        "49 decisions is one short of the floor, and one decision is the "
        "difference between a ranked match and an unranked one")

    no_vacas = match(teams=("delta", "epsilon"), hands=10, llm_turns=120,
                     fallbacks=0, vacas_a=None, vacas_b=None)
    assert s.is_publishable_match(no_vacas) is False, (
        "a match that never recorded its vacas has no score to compare: there "
        "is no win, no loss and no 0-0, so it cannot be published as a tie")

    assert s.is_publishable_match(match(status="degraded", hands=10,
                                        llm_turns=200, fallbacks=0, vacas_a=4,
                                        vacas_b=0)) is False, (
        "the harness marked this session degraded itself, and healthy counters "
        "do not overrule the verdict that its numbers are noise")
    assert s.is_publishable_match(match(status="error", hands=10,
                                        llm_turns=200, fallbacks=0, vacas_a=4,
                                        vacas_b=0)) is False, (
        "an errored job has no result to rank, whatever counters survived in "
        "its row")

    assert s.is_publishable_match(match(hands=0, llm_turns=100, fallbacks=0,
                                        vacas_a=0, vacas_b=0)) is False, (
        "a match with no scored hand has no per-hand number, and publishing it "
        "puts a zero or an invented edge under the divider")
    assert s.is_publishable_match(match(hands=10, llm_turns=0, fallbacks=0,
                                        vacas_a=0, vacas_b=0)) is False, (
        "no model decision and no fallback is 0/0 rather than a rate of 0%, and "
        "a match where the model never played measures nothing")

    # --- the table ---------------------------------------------------------
    rows = [
        # alpha vs beta: two clean matches, 10 + 6 hands, a win and a tie
        match(teams=("alpha", "beta"), seed=1, hands=10, llm_turns=100,
              fallbacks=0, vacas_a=2, vacas_b=1, hand_gain_a=30,
              hand_gain_b=10),
        match(teams=("alpha", "beta"), seed=2, hands=6, llm_turns=80,
              fallbacks=2, vacas_a=1, vacas_b=1, hand_gain_a=12,
              hand_gain_b=18),
        # gamma vs beta: a rate-limit cascade that still finished "done"
        match(teams=("gamma", "beta"), seed=3, hands=8, llm_turns=20,
              fallbacks=8, turns=300, vacas_a=3, vacas_b=0, hand_gain_a=40,
              hand_gain_b=5),
        # delta vs epsilon: interrupted before its vacas were recorded
        match(teams=("delta", "epsilon"), seed=4, hands=10, llm_turns=120,
              fallbacks=0, vacas_a=None, vacas_b=None, hand_gain_a=5,
              hand_gain_b=5),
        # a job that errored out of alpha's group
        match(teams=("errored", "alpha"), seed=5, status="error", hands=None,
              llm_turns=None, fallbacks=None, turns=None, vacas_a=None,
              vacas_b=None, hand_gain_a=None, hand_gain_b=None),
        # a degraded session that would look healthy by its counters alone
        match(teams=("quiet", "alpha"), seed=6, status="degraded", hands=10,
              llm_turns=200, fallbacks=0, vacas_a=4, vacas_b=0, hand_gain_a=60,
              hand_gain_b=0),
        # yankee and xray: identical numbers against the same opponent
        match(teams=("yankee", "shared"), seed=7, hands=10, llm_turns=100,
              fallbacks=0, vacas_a=2, vacas_b=1, hand_gain_a=20,
              hand_gain_b=10),
        match(teams=("xray", "shared"), seed=8, hands=10, llm_turns=100,
              fallbacks=0, vacas_a=2, vacas_b=1, hand_gain_a=20,
              hand_gain_b=10),
        # quebec and romeo: the same per-hand edge, different vaca differences
        match(teams=("quebec", "papa"), seed=9, hands=10, llm_turns=100,
              fallbacks=0, vacas_a=1, vacas_b=0, hand_gain_a=20,
              hand_gain_b=10),
        match(teams=("romeo", "papa"), seed=10, hands=10, llm_turns=100,
              fallbacks=0, vacas_a=2, vacas_b=0, hand_gain_a=20,
              hand_gain_b=10),
        # a clean match that never reached the call floor
        match(teams=("uniform", "victor"), seed=11, hands=8, llm_turns=20,
              fallbacks=1, vacas_a=1, vacas_b=0, hand_gain_a=20,
              hand_gain_b=10),
    ]

    assert s.leaderboard([]) == [], (
        "no matches is an empty table rather than an exception: the live table "
        "is built before the first match has finished")

    table = s.leaderboard(rows)
    by_label = {}
    for entry in table:
        by_label[entry.get("label")] = entry

    assert set(by_label) == LABELS, (
        "a match is two teams' result: the same row puts BOTH of its labels in "
        "the table, so every label that played appears exactly once — got %r"
        % (sorted(by_label),))

    for label, entry in sorted(by_label.items()):
        missing = [key for key in REQUIRED_KEYS if key not in entry]
        assert not missing, (
            "an entry carries every column the table prints, and %r is missing "
            "%r" % (label, missing))
        per_hand = entry["piedras_per_hand"]
        assert per_hand is None or (isinstance(per_hand, (int, float))
                                    and not isinstance(per_hand, bool)), (
            "the per-hand edge is a number or None, and %r carries %r"
            % (label, per_hand))

    # --- what the gate rejected is not scored ------------------------------
    alpha = by_label["alpha"]
    assert alpha["ties"] == 1, (
        "a rejected row is not a tie: alpha's errored job has no vacas at all "
        "and its degraded session is a loss the gate threw away, so the 1-1 "
        "alpha actually played is its only draw")
    assert alpha["wins"] == 1, (
        "alpha won the 2-1 match it published and lost none of them: a win "
        "count read from the other team's end, or with the comparison turned "
        "around, charges the wrong team")

    delta = by_label["delta"]
    assert delta["publishable"] == 0, (
        "a match whose vacas were never recorded is no 0-0 tie: delta played "
        "one match and it is not evidence, so it publishes nothing")
    assert delta["ties"] == 0, (
        "reading a missing vaca as zero hands delta a draw it never played")

    quiet = by_label["quiet"]
    assert quiet["publishable"] == 0, (
        "the harness marked quiet's session degraded itself, so it is not "
        "published and the 4-0 inside it is not a win")

    gamma = by_label["gamma"]
    assert gamma["publishable"] == 0, (
        "gamma's only match is the cascade — 8 fallbacks in its own 28 "
        "decisions is 29% — and that is the row this gate exists to catch")
    assert gamma["hands"] == 0 and gamma["piedras_per_hand"] is None, (
        "gamma published nothing, so it has no hands and no per-hand edge: "
        "summing the 8 hands of its rejected cascade under the divider is how a "
        "discarded row's piedras come back as a number")

    uniform = by_label["uniform"]
    assert uniform["publishable"] == 0 and uniform["degraded"] == 1, (
        "uniform's match is clean but has 20 model decisions, under the floor "
        "of 50, so it is rejected for too little play rather than for noise")

    # --- what the published rows add up to ---------------------------------
    assert alpha["hands"] == 16, (
        "alpha's published hands are the 10 + 6 hands of its two published "
        "matches; its errored and its degraded row played 10 more, and those "
        "hands belong to sessions nobody may rank")
    assert alpha["piedras_for"] == 42 and alpha["piedras_against"] == 28, (
        "each label is credited with its own end of the match: alpha took "
        "30 + 12 piedras and gave up 10 + 18")
    assert alpha["piedras_per_hand"] == 0.875, (
        "the edge per hand is the ratio of the sums — 16 hands under 14 total "
        "edge — and not the mean of each match's own edge per hand, which "
        "weights a 6-hand match like a 10-hand one and gives 0.5")
    assert alpha["vacas_for"] == 3 and alpha["vacas_against"] == 2, (
        "alpha's published vacas are the 2-1 and the 1-1 it actually played, "
        "and the rejected rows contribute none")
    assert (alpha["matches"], alpha["publishable"], alpha["degraded"]) == (4, 2, 2), (
        "a degraded row is not a published row: alpha's errored job and its "
        "degraded session are the two matches the gate rejected, and a table "
        "that counts them as published carries their vacas into the record")

    beta = by_label["beta"]
    assert (beta["piedras_for"], beta["piedras_against"]) == (28, 42), (
        "the same row is a win for one label and a loss for the other, so "
        "beta's piedras are alpha's read from the other end: 10 + 18 taken and "
        "30 + 12 given up")
    assert beta["piedras_per_hand"] == -0.875, (
        "the away side of alpha's +0.875 is -0.875: the same 16 hands under the "
        "divider and the edge negated")
    assert (beta["losses"], beta["ties"]) == (1, 1), (
        "the vaca comparison belongs to each label's own side: alpha's 2-1 win "
        "is beta's 1-2 loss and the 1-1 is both teams' tie")
    assert (beta["matches"], beta["publishable"], beta["degraded"]) == (3, 2, 1), (
        "beta played three rows and the rate-limit cascade against gamma is the "
        "one the gate rejected")

    # --- the order ---------------------------------------------------------
    labels = [entry["label"] for entry in table]
    measured = [label for label in labels
                if by_label[label]["piedras_per_hand"] is not None]
    unmeasured = [label for label in labels
                  if by_label[label]["piedras_per_hand"] is None]
    assert labels.index(measured[-1]) < labels.index(unmeasured[0]), (
        "None is not 0.0: a label nobody has a published hand for is not "
        "measured at all, while beta's -0.875 is a measured loss, and a "
        "leaderboard that reads the missing number as zero puts a label with no "
        "data above a label that actually played")
    assert labels.index("romeo") < labels.index("quebec"), (
        "romeo's +1.0 per hand came with a +2 vaca difference and quebec's with "
        "+1, so the tie on the edge is broken by the coarser scoreboard")
    assert labels.index("shared") < labels.index("papa"), (
        "shared and papa both sit at -1.0 per hand, and what separates them is "
        "the -2 against the -3, not the alphabet")
    assert labels.index("xray") < labels.index("yankee"), (
        "xray and yankee agree on every number the table carries, so the label "
        "decides: an order that follows the rows instead reshuffles itself "
        "whenever the table is regenerated")
    assert labels == ["romeo", "quebec", "xray", "yankee", "alpha", "beta",
                      "shared", "papa", "delta", "epsilon", "errored", "gamma",
                      "quiet", "uniform", "victor"], (
        "the order is the per-hand edge descending, then every label with no "
        "published hand (None is not a number and cannot outrank a measured "
        "loss), then the vaca difference, then the label — got %r" % (labels,))

def check_10():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _row(m0, m1, seed, gain_a, gain_b, hands=4, status="done"):
        return {"teams": [m0, m1], "seed": seed, "status": status, "hands": hands,
                "hand_gain_a": gain_a, "hand_gain_b": gain_b}

    import stage_10 as s
    from mus import heuristic_policy, random_policy, self_play

    # --- the schedule -------------------------------------------------------
    pairings = [("heur", "rand"), ("heur", "choice")]
    seeds = [3, 4]
    jobs = s.build_jobs(pairings, seeds)
    assert len(jobs) == 8, (
        "two pairings under two seeds, each played in both directions, is eight "
        "jobs, got %r" % (jobs,))
    offset = 0
    for seed in seeds:
        for model_a, model_b in pairings:
            assert jobs[offset] == (model_a, model_b, seed) \
                and jobs[offset + 1] == (model_b, model_a, seed), (
                "the schedule is seed-major and the two halves of a pair are "
                "adjacent on the SAME seed (that is what puts them on the same "
                "cards), got %r" % (jobs[offset:offset + 2],))
            offset += 2
    flat = s.build_jobs(pairings, seeds, mirror=False)
    assert len(flat) == 4, (
        "without the mirror every pairing is played once per seed — the run still "
        "looks complete, and the other orientation is missing: %r" % (flat,))
    assert flat[0] == ("heur", "rand", 3), (
        "and the one orientation it keeps is the pairing's own order: %r"
        % (flat,))
    for broken in ([("a", "b", "c")], [("a", "b"), ("b", "a")],
                   [("a", "b"), ("a", "b")]):
        try:
            s.build_jobs(broken, [1])
        except ValueError as exc:
            assert "pairing" in str(exc), (
                "a pairing is two labels and is unordered: %r must be refused by "
                "the schedule's own rule, not by an unpacking error somewhere "
                "downstream — got %r" % (broken, str(exc)))
        else:
            raise AssertionError(
                "a pairing is two labels and is unordered: %r would run the same "
                "matchup twice from one schedule" % (broken,))

    # --- the pair -----------------------------------------------------------
    entries = [
        _row("heur", "rand", 7, 10, 4),          # heur in a: +6
        _row("rand", "heur", 7, 3, 7),           # heur in b: +4
        _row("heur", "rand", 8, 8, 2, hands=3),  # heur in a: +6, three hands
        _row("rand", "heur", 8, 2, 6, hands=4),  # heur in b: +4, four hands
        _row("heur", "choice", 7, 2, 6),         # a half pair
    ]
    pairs = s.paired_rows(entries)
    assert len(pairs) == 2, (
        "one comparison per matchup and seed; the half pair is not one: %r"
        % (pairs,))
    both = {entry["seed"]: entry for entry in pairs}
    pair = both[7]
    assert pair["models"] == ["heur", "rand"] and pair["seed"] == 7, (
        "the pair is identified by the sorted matchup and the seed: %r" % (pair,))
    assert pair["piedra_diff_seat_a"] == 6 and pair["piedra_diff_seat_b"] == 4, (
        "both halves are expressed from ONE model's view (heur's): +6 with heur "
        "in the a seats and +4 with heur in b. The two numbers straddle the true "
        "difference of 5 — the seat was worth a piedra per hand, and a single-"
        "orientation reading would have published 6 or 4 as if it were skill: %r"
        % (pair,))
    assert pair["paired_diff"] == 10, (
        "the seat advantage appears in the two halves with opposite signs, so the "
        "sum is twice the skill and the bias is gone: %r" % (pair,))
    assert pair["hands"] == 8, (
        "the hands are summed over BOTH matches — eight hands were played to "
        "produce this difference, not four: %r" % (pair["hands"],))
    assert pair["per_hand"] == round(10 / 8, 3) == 1.25, (
        "and the per-hand number divides by the hands actually played, or every "
        "per-hand figure in the report is doubled: %r" % (pair["per_hand"],))
    seven = both[8]
    assert seven["hands"] == 7 and seven["per_hand"] == round(10 / 7, 3) == 1.429, (
        "a difference that does not divide cleanly is reported to three decimals: "
        "ten piedras over seven hands is 1.429, not the raw float, or two runs of "
        "the same seed disagree in the digits nobody re-checks: %r"
        % (seven["per_hand"],))

    # --- a degraded half is not a measurement ------------------------------
    degraded = s.paired_rows([
        _row("heur", "rand", 7, 10, 4),
        _row("rand", "heur", 7, 3, 7, status="degraded"),
    ])
    assert degraded == [], (
        "a match that degraded to fallbacks measured the harness, not the model: "
        "the pair has no seat-balanced number and disappears rather than falling "
        "back to the one half it has, got %r" % (degraded,))

    # --- the same orientation twice is a broken schedule --------------------
    try:
        s.paired_rows([_row("heur", "rand", 7, 10, 4),
                       _row("heur", "rand", 7, 1, 1)])
    except ValueError:
        pass
    else:
        raise AssertionError(
            "the same orientation twice for one matchup and seed means the "
            "schedule ran one job twice; the pair is not a pair and the run is "
            "not comparable")

    # --- the vantage is the sorted-first label ------------------------------
    flipped = s.paired_rows([
        _row("rand", "heur", 9, 7, 3),       # heur in b: 3 - 7 = -4
        _row("heur", "rand", 9, 2, 6),       # heur in a: 2 - 6 = -4
        {"teams": ["heur", "rand"], "seed": 10, "status": "done", "hands": 0,
         "hand_gain_a": 0, "hand_gain_b": 0},
        {"teams": ["rand", "heur"], "seed": 10, "status": "done", "hands": 0,
         "hand_gain_a": 0, "hand_gain_b": 0},
    ])
    assert len(flipped) == 2, (
        "seeds are separate comparisons: %r" % (flipped,))
    assert flipped[0]["models"] == ["heur", "rand"] \
        and flipped[0]["piedra_diff_seat_a"] == -4 \
        and flipped[0]["piedra_diff_seat_b"] == -4 \
        and flipped[0]["paired_diff"] == -8, (
        "the vantage is fixed by the sorted matchup, not by the order the rows "
        "arrive in, or two runs of the same seed would disagree on the sign: %r"
        % (flipped[0],))
    assert flipped[1]["hands"] == 0 and flipped[1]["per_hand"] is None, (
        "a per-hand number with no hands played is None, never a division or a "
        "zero that reads like a measurement: %r" % (flipped[1],))
    assert s.paired_rows([]) == [], "no rows, no comparisons"

    # --- the seed is what deals the cards ----------------------------------
    def seats(offset):
        return [random_policy(100 + offset), heuristic_policy(200 + offset),
                random_policy(300 + offset), heuristic_policy(400 + offset)]

    first = self_play(7, hands=3, policies=seats(0), record_deals=True)
    second = self_play(7, hands=3, policies=seats(1), record_deals=True)
    other = self_play(8, hands=3, policies=seats(0), record_deals=True)
    assert len(first["deals"]) == 3 == len(second["deals"]), (
        "three hands means three deals, got %r" % (first["deals"],))
    assert first["deals"] == second["deals"], (
        "the cards a seed deals must NOT depend on who is playing: fork the deal "
        "stream from the seed before the first decision, or the two halves of a "
        "mirrored pair are playing different cards and the pairing measures the "
        "deal — %r vs %r" % (first["deals"], second["deals"]))
    assert first["deals"] != other["deals"], (
        "and a different seed deals different cards: the two halves of a pair "
        "being on the same cards must come from the seed, not from a fixed deck: "
        "%r" % (first["deals"],))

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The engine is the only gate, and a refusal is not a turn",
        tags=["turn-gate", "refusals"],
        action="Write `STATS_KEYS`, `new_stats` and `gate` in stage_01.py.",
        predict="What the match's counters hold after four actions of which two "
                "were refused, what `turn` a refusal reports, and what a table "
                "that raises something other than `IllegalAction` does.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The match loop: what counts as a turn, and when to stop",
        tags=["match-loop", "degradation"],
        action="Write `FALLBACK_WARMUP`, `DegradedMatch` and `run_match` in "
               "stage_02.py.",
        predict="Where `status` lands when a seat answers nonsense three times "
                "with `retries=2`, whether the fallback counts in `llm_turns`, "
                "and what `deals` holds for a hand that was abandoned mid-play.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="One record per turn, taken before the action landed",
        tags=["ground-truth", "logging"],
        action="Write `SNAPSHOT_KEYS`, `truth_snapshot`, `decision_line` and "
               "`DecisionLog` in stage_03.py.",
        predict="What `stake` and `facing_bet` the record of an envido shows "
                "after the engine has already collected it, what a `True` "
                "confidence does, and what a record that cannot be serialised "
                "leaves behind.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="Linking an aggression to the answer it got",
        tags=["lances", "linking"],
        action="Write `AGGRESSIVE`, `RESPONSES` and `link_responses` in "
               "stage_04.py.",
        predict="In a hand where you raise, your partner y-yo's and one rival "
                "folds once, how many links come back, whether each carries the "
                "same answer, and what `fold_gain` is when nobody had staked.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The reference is the hands that faced a bet, not every hand",
        tags=["strength", "terciles"],
        action="Write `MIN_REFERENCE`, `can_bet`, `strength_terciles` and "
               "`strength_band` in stage_05.py.",
        predict="With eight bet-capable Grande hands spread 0.1..0.8, the two "
                "cuts, whether the hand exactly on the bottom cut is weak, and "
                "what a lance with five measured hands gets.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="A bluff is a weak hand that bet, never a bet that lost",
        tags=["bluffs", "fold-equity"],
        action="Write `scorecard` in stage_06.py.",
        predict="`bluff_rate` for a model whose eight strong bets all lost the "
                "lance, `stake_lost_called_bluffs` for a weak bet that was "
                "called and won, and which rates are None with no data.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The outcome is the piedras, and they survive the vaca reset",
        tags=["outcome", "resets"],
        action="Write `outcome` in stage_07.py.",
        predict="The piedras of a six-hand match whose vaca fired at hand four, "
                "what the point counters add up to instead, and what a tied hand "
                "does to the wins.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="Probe the read: Brier, log-loss, AUC, calibration",
        tags=["calibration", "discrimination"],
        action="Write `EPS`, `brier`, `logloss`, `auc` and `reliability` in "
               "stage_08.py.",
        predict="The Brier and log-loss of a ten-read coin flip, what `auc` "
                "returns when one class is absent, and where a read of exactly "
                "1.0 lands in a five-bin table.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="Which matches may be published, and the leaderboard they build",
        tags=["publishability", "leaderboard"],
        action="Write `MIN_LLM_CALLS`, `MAX_FALLBACK_RATIO`, "
               "`is_publishable_match` and `leaderboard` in stage_09.py.",
        predict="A row of 20 model calls and 8 fallbacks over 300 turns: "
                "publishable or not, and which denominator the ratio uses; then "
                "whether a label with no data outranks a measured loss.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The mirrored pair: one seed, both orientations, one comparison",
        tags=["pairing", "variance"],
        action="Write `build_jobs` and `paired_rows` in stage_10.py.",
        predict="The `paired_diff` and `per_hand` of a pair whose halves read "
                "+6 and +4 over 4 and 4 hands, how many hands the pair counts, "
                "and what happens to a matchup whose second half degraded.",
        check=check_10,
    ),
]
