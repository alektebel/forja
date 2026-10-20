"""
Leaderboard — From Scratch
============================
Build a leaderboard system to understand:
- Sorted sets (like Redis ZSET) for O(log N) rank queries
- Real-time rank updates as scores change
- Windowed leaderboards (daily, weekly, all-time)
- Top-K queries
- Pagination through rank ranges
- Score delta tracking (show change in rank)

Learning Path:
1. Implement SortedSet (the core data structure) with O(log N) operations
2. Implement Leaderboard using SortedSet
3. Add windowed leaderboards (daily/weekly keys)
4. Add rank delta tracking (rank change since last snapshot)
5. Think about: how would you scale to 100M users?
   - Redis ZADD/ZREVRANK (O(log N))
   - Shard by game/region if one leaderboard won't fit in one Redis
   - Approximate top-K using count-min sketch or HyperLogLog

Redis Sorted Set commands (for reference):
  ZADD leaderboard 1500 "user:42"         # set score
  ZINCRBY leaderboard 100 "user:42"       # increment score
  ZREVRANK leaderboard "user:42"          # 0-based rank (high score = rank 0)
  ZSCORE leaderboard "user:42"            # get score
  ZREVRANGE leaderboard 0 9 WITHSCORES   # top 10 with scores
  ZRANGEBYSCORE leaderboard 1000 +inf     # users above score 1000
"""

import bisect
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Step 1: SortedSet (core data structure)
# ---------------------------------------------------------------------------

@dataclass(order=True)
class _Entry:
    """An entry in the sorted set. Sorted by (score DESC, member ASC) for tie-breaking."""
    score: float
    member: str

    def __eq__(self, other):
        return self.member == other.member

    def __hash__(self):
        return hash(self.member)


class SortedSet:
    """A sorted set (like Redis ZSET) supporting O(log N) rank and score queries.

    Members are sorted by score (descending). Ties broken by member name ascending.

    TODO:
    1. _scores: dict mapping member → score (for O(1) score lookup)
    2. _sorted: sorted list of _Entry, ordered by (-score, member) for rank queries
       Use the `sortedcontainers.SortedList` approach, or maintain a manually sorted list.
       Hint: since Python's `bisect` works on ascending lists, store (-score, member) tuples.

    Implement:
    - zadd(member, score): set the score for member; update if exists
    - zincrby(member, delta): increment score by delta; add with score=delta if new
    - zscore(member) → float or None: return score for member
    - zrevrank(member) → int or None: 0-based rank (highest score = 0)
    - zrevrange(start, stop) → List[Tuple[str, float]]: members with scores in rank range
    - zrangebyscore(min_score, max_score) → List[Tuple[str, float]]: members in score range
    - zcard() → int: number of members
    """

    def __init__(self):
        self._scores: Dict[str, float] = {}
        # Store as sorted list of (-score, member) so bisect gives us rank order
        self._sorted: List[Tuple[float, str]] = []

    def zadd(self, member: str, score: float) -> None:
        """Set the score for member. If member exists, update its score.

        TODO:
        1. If member already in _scores: remove old (-score, member) from _sorted
        2. Insert new (-score, member) into _sorted using bisect.insort
        3. Update _scores[member] = score
        """
        # TODO: implement zadd
        raise NotImplementedError("Implement SortedSet.zadd")

    def zincrby(self, member: str, delta: float) -> float:
        """Increment member's score by delta. Add member with score=delta if new.

        Returns the new score.

        TODO: get current score (default 0), add delta, call zadd, return new score
        """
        # TODO: implement zincrby
        raise NotImplementedError("Implement SortedSet.zincrby")

    def zscore(self, member: str) -> Optional[float]:
        """Return the score for member, or None if not a member."""
        # TODO: implement zscore
        raise NotImplementedError("Implement SortedSet.zscore")

    def zrevrank(self, member: str) -> Optional[int]:
        """Return the 0-based rank of member (highest score = rank 0).

        TODO:
        1. Look up score in _scores; return None if not member
        2. Find position of (-score, member) in _sorted (use bisect_left)
        3. That position IS the rank (0-based)
        """
        # TODO: implement zrevrank
        raise NotImplementedError("Implement SortedSet.zrevrank")

    def zrevrange(self, start: int, stop: int) -> List[Tuple[str, float]]:
        """Return members ranked [start, stop] inclusive (0-based, highest score first).

        TODO:
        1. Slice _sorted[start:stop+1]
        2. Return list of (member, score) — remember _sorted stores (-score, member)
        """
        # TODO: implement zrevrange
        raise NotImplementedError("Implement SortedSet.zrevrange")

    def zrangebyscore(self, min_score: float, max_score: float) -> List[Tuple[str, float]]:
        """Return all members with min_score <= score <= max_score, highest score first.

        TODO: filter _scores items by score range and sort descending
        """
        # TODO: implement zrangebyscore
        raise NotImplementedError("Implement SortedSet.zrangebyscore")

    def zcard(self) -> int:
        """Return the number of members in the set."""
        return len(self._scores)


# ---------------------------------------------------------------------------
# Step 2: Leaderboard
# ---------------------------------------------------------------------------

@dataclass
class LeaderboardEntry:
    rank: int             # 1-based rank
    member: str
    score: float
    rank_delta: Optional[int] = None   # positive = moved up, negative = dropped


class Leaderboard:
    """A leaderboard backed by SortedSet.

    TODO:
    - Wrap SortedSet for a named leaderboard
    - add_score(member, score): set member's score
    - increment_score(member, delta): add delta to member's score
    - get_rank(member): return 1-based rank
    - get_top(n): return top n LeaderboardEntry objects
    - get_around(member, n): return n entries centered on member's rank (for "you and nearby")
    """

    def __init__(self, name: str):
        self.name = name
        self._set = SortedSet()
        self._snapshot: Dict[str, int] = {}  # member → previous rank for delta calc

    def add_score(self, member: str, score: float) -> None:
        """Set member's score. Overwrites previous score.

        TODO: call _set.zadd
        """
        # TODO: implement add_score
        raise NotImplementedError("Implement Leaderboard.add_score")

    def increment_score(self, member: str, delta: float) -> float:
        """Add delta to member's current score. Return new score.

        TODO: call _set.zincrby
        """
        # TODO: implement increment_score
        raise NotImplementedError("Implement Leaderboard.increment_score")

    def get_rank(self, member: str) -> Optional[int]:
        """Return the 1-based rank of member, or None if not on leaderboard."""
        # TODO: call _set.zrevrank and add 1 for 1-based
        raise NotImplementedError("Implement Leaderboard.get_rank")

    def get_score(self, member: str) -> Optional[float]:
        """Return member's score, or None."""
        # TODO: call _set.zscore
        raise NotImplementedError("Implement Leaderboard.get_score")

    def get_top(self, n: int) -> List[LeaderboardEntry]:
        """Return the top n members as LeaderboardEntry objects (rank 1 = highest score).

        TODO:
        1. Call _set.zrevrange(0, n-1)
        2. Build LeaderboardEntry for each: rank = index + 1
        3. Compute rank_delta from _snapshot if available
        """
        # TODO: implement get_top
        raise NotImplementedError("Implement Leaderboard.get_top")

    def get_around(self, member: str, n: int = 5) -> List[LeaderboardEntry]:
        """Return n entries centered on member's rank (n//2 above, n//2 below).

        Useful for "You and players near you" feature.

        TODO:
        1. Get member's rank (0-based via zrevrank)
        2. start = max(0, rank - n // 2)
        3. stop = start + n - 1
        4. Adjust start if we'd go past end of leaderboard
        5. Return _set.zrevrange(start, stop) as LeaderboardEntry list
        """
        # TODO: implement get_around
        raise NotImplementedError("Implement Leaderboard.get_around")

    def snapshot_ranks(self) -> None:
        """Take a snapshot of current ranks for delta calculation.

        Call this periodically (e.g., daily) to compute rank changes.

        TODO: store {member: rank} for all current members in _snapshot
        """
        # TODO: implement snapshot_ranks
        raise NotImplementedError("Implement Leaderboard.snapshot_ranks")

    @property
    def size(self) -> int:
        return self._set.zcard()


# ---------------------------------------------------------------------------
# Step 3: Windowed Leaderboard (discussion + skeleton)
# ---------------------------------------------------------------------------

class WindowedLeaderboard:
    """Maintains separate leaderboards for different time windows.

    Pattern: use time-bucketed keys
      - all-time:    "leaderboard:all"
      - daily:       "leaderboard:daily:2024-01-15"
      - weekly:      "leaderboard:weekly:2024-W03"

    When a score event comes in, update ALL active windows simultaneously.

    TODO: implement add_score(member, delta) that updates all_time, daily, weekly boards
    """

    def __init__(self):
        self._all_time = Leaderboard("all-time")
        self._daily: Dict[str, Leaderboard] = {}    # date_str → Leaderboard
        self._weekly: Dict[str, Leaderboard] = {}   # week_str → Leaderboard

    def _date_key(self) -> str:
        return time.strftime("%Y-%m-%d")

    def _week_key(self) -> str:
        t = time.gmtime()
        return f"{t.tm_year}-W{t.tm_yday // 7:02d}"

    def add_score(self, member: str, delta: float) -> None:
        """Add delta to member's score in all active windows.

        TODO:
        1. Get or create daily leaderboard for today's date key
        2. Get or create weekly leaderboard for this week's key
        3. Increment all-time, daily, weekly by delta
        """
        # TODO: implement add_score for windowed leaderboard
        raise NotImplementedError("Implement WindowedLeaderboard.add_score")

    def get_top_daily(self, n: int) -> List[LeaderboardEntry]:
        """Return top n for today's daily leaderboard."""
        key = self._date_key()
        board = self._daily.get(key)
        return board.get_top(n) if board else []

    def get_top_weekly(self, n: int) -> List[LeaderboardEntry]:
        """Return top n for this week's leaderboard."""
        key = self._week_key()
        board = self._weekly.get(key)
        return board.get_top(n) if board else []

    def get_top_all_time(self, n: int) -> List[LeaderboardEntry]:
        return self._all_time.get_top(n)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing SortedSet...")
    ss = SortedSet()
    ss.zadd("alice", 1500)
    ss.zadd("bob", 1200)
    ss.zadd("charlie", 1800)
    ss.zadd("diana", 1500)  # tie with alice, breaks alphabetically

    assert ss.zscore("charlie") == 1800
    assert ss.zrevrank("charlie") == 0     # highest score = rank 0
    assert ss.zrevrank("alice") == 1       # 1500, "alice" < "diana" so alice is rank 1
    assert ss.zrevrank("diana") == 2       # 1500, diana after alice alphabetically
    assert ss.zrevrank("bob") == 3
    assert ss.zcard() == 4

    top2 = ss.zrevrange(0, 1)
    assert top2[0][0] == "charlie"
    assert top2[1][0] == "alice"

    # Update score
    ss.zadd("bob", 2000)
    assert ss.zrevrank("bob") == 0  # now highest

    # Increment
    new_score = ss.zincrby("charlie", 500)
    assert new_score == 2300
    assert ss.zrevrank("charlie") == 0

    # Range by score
    in_range = ss.zrangebyscore(1500, 2000)
    members = {m for m, _ in in_range}
    assert "alice" in members
    assert "diana" in members
    assert "bob" in members
    print("  SortedSet: OK")

    print("Testing Leaderboard...")
    lb = Leaderboard("game-1")
    lb.add_score("player1", 100)
    lb.add_score("player2", 200)
    lb.add_score("player3", 150)

    assert lb.get_rank("player2") == 1
    assert lb.get_rank("player3") == 2
    assert lb.get_rank("player1") == 3

    top = lb.get_top(3)
    assert [e.member for e in top] == ["player2", "player3", "player1"]
    assert top[0].rank == 1

    lb.snapshot_ranks()
    lb.increment_score("player1", 200)  # player1 now 300 → rank 1
    around = lb.get_around("player2", 3)
    assert len(around) > 0
    print("  Leaderboard: OK")

    print("Testing rank delta...")
    lb2 = Leaderboard("game-2")
    lb2.add_score("a", 100)
    lb2.add_score("b", 200)
    lb2.add_score("c", 300)
    lb2.snapshot_ranks()
    lb2.increment_score("a", 300)  # a jumps to rank 1 (score 400)
    top = lb2.get_top(3)
    a_entry = next(e for e in top if e.member == "a")
    assert a_entry.rank_delta is not None and a_entry.rank_delta > 0, \
        f"a should have moved up, delta={a_entry.rank_delta}"
    print("  rank delta: OK")

    print("\nAll leaderboard tests passed!")


if __name__ == "__main__":
    _test()
