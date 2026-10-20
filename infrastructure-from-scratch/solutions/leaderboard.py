"""
Leaderboard — Complete Solution
"""

import bisect
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class LeaderboardEntry:
    rank: int
    member: str
    score: float
    rank_delta: Optional[int] = None


class SortedSet:
    """Sorted set with O(log N) operations. Sorted by (-score, member) ascending."""

    def __init__(self):
        self._scores: Dict[str, float] = {}
        # sorted list of (-score, member) tuples
        self._sorted: List[Tuple[float, str]] = []

    def zadd(self, member: str, score: float) -> None:
        if member in self._scores:
            old_score = self._scores[member]
            old_entry = (-old_score, member)
            idx = bisect.bisect_left(self._sorted, old_entry)
            if idx < len(self._sorted) and self._sorted[idx] == old_entry:
                self._sorted.pop(idx)
        new_entry = (-score, member)
        bisect.insort(self._sorted, new_entry)
        self._scores[member] = score

    def zincrby(self, member: str, delta: float) -> float:
        new_score = self._scores.get(member, 0.0) + delta
        self.zadd(member, new_score)
        return new_score

    def zscore(self, member: str) -> Optional[float]:
        return self._scores.get(member)

    def zrevrank(self, member: str) -> Optional[int]:
        if member not in self._scores:
            return None
        score = self._scores[member]
        entry = (-score, member)
        idx = bisect.bisect_left(self._sorted, entry)
        if idx < len(self._sorted) and self._sorted[idx] == entry:
            return idx
        return None

    def zrevrange(self, start: int, stop: int) -> List[Tuple[str, float]]:
        slice_ = self._sorted[start:stop + 1]
        return [(member, -neg_score) for neg_score, member in slice_]

    def zrangebyscore(self, min_score: float, max_score: float) -> List[Tuple[str, float]]:
        result = [
            (member, score)
            for member, score in self._scores.items()
            if min_score <= score <= max_score
        ]
        result.sort(key=lambda x: -x[1])
        return result

    def zcard(self) -> int:
        return len(self._scores)


class Leaderboard:
    def __init__(self, name: str):
        self.name = name
        self._set = SortedSet()
        self._snapshot: Dict[str, int] = {}

    def add_score(self, member: str, score: float) -> None:
        self._set.zadd(member, score)

    def increment_score(self, member: str, delta: float) -> float:
        return self._set.zincrby(member, delta)

    def get_rank(self, member: str) -> Optional[int]:
        rank = self._set.zrevrank(member)
        return rank + 1 if rank is not None else None

    def get_score(self, member: str) -> Optional[float]:
        return self._set.zscore(member)

    def get_top(self, n: int) -> List[LeaderboardEntry]:
        entries = self._set.zrevrange(0, n - 1)
        result = []
        for i, (member, score) in enumerate(entries):
            rank = i + 1
            delta = None
            if member in self._snapshot:
                old_rank = self._snapshot[member]
                delta = old_rank - rank  # positive = moved up
            result.append(LeaderboardEntry(rank=rank, member=member, score=score,
                                           rank_delta=delta))
        return result

    def get_around(self, member: str, n: int = 5) -> List[LeaderboardEntry]:
        rank0 = self._set.zrevrank(member)
        if rank0 is None:
            return []
        start = max(0, rank0 - n // 2)
        stop = start + n - 1
        total = self._set.zcard()
        if stop >= total:
            stop = total - 1
            start = max(0, stop - n + 1)
        entries = self._set.zrevrange(start, stop)
        result = []
        for i, (m, score) in enumerate(entries):
            rank = start + i + 1
            delta = None
            if m in self._snapshot:
                delta = self._snapshot[m] - rank
            result.append(LeaderboardEntry(rank=rank, member=m, score=score,
                                           rank_delta=delta))
        return result

    def snapshot_ranks(self) -> None:
        self._snapshot = {}
        for i, (member, _) in enumerate(self._set.zrevrange(0, self._set.zcard() - 1)):
            self._snapshot[member] = i + 1

    @property
    def size(self) -> int:
        return self._set.zcard()


class WindowedLeaderboard:
    def __init__(self):
        self._all_time = Leaderboard("all-time")
        self._daily: Dict[str, Leaderboard] = {}
        self._weekly: Dict[str, Leaderboard] = {}

    def _date_key(self) -> str:
        return time.strftime("%Y-%m-%d")

    def _week_key(self) -> str:
        t = time.gmtime()
        return f"{t.tm_year}-W{t.tm_yday // 7:02d}"

    def add_score(self, member: str, delta: float) -> None:
        date_key = self._date_key()
        week_key = self._week_key()
        if date_key not in self._daily:
            self._daily[date_key] = Leaderboard(f"daily:{date_key}")
        if week_key not in self._weekly:
            self._weekly[week_key] = Leaderboard(f"weekly:{week_key}")
        self._all_time.increment_score(member, delta)
        self._daily[date_key].increment_score(member, delta)
        self._weekly[week_key].increment_score(member, delta)

    def get_top_daily(self, n: int) -> List[LeaderboardEntry]:
        board = self._daily.get(self._date_key())
        return board.get_top(n) if board else []

    def get_top_weekly(self, n: int) -> List[LeaderboardEntry]:
        board = self._weekly.get(self._week_key())
        return board.get_top(n) if board else []

    def get_top_all_time(self, n: int) -> List[LeaderboardEntry]:
        return self._all_time.get_top(n)


def _test():
    print("Testing SortedSet...")
    ss = SortedSet()
    ss.zadd("alice", 1500)
    ss.zadd("bob", 1200)
    ss.zadd("charlie", 1800)
    ss.zadd("diana", 1500)

    assert ss.zscore("charlie") == 1800
    assert ss.zrevrank("charlie") == 0
    assert ss.zrevrank("alice") == 1
    assert ss.zrevrank("diana") == 2
    assert ss.zrevrank("bob") == 3
    assert ss.zcard() == 4

    top2 = ss.zrevrange(0, 1)
    assert top2[0][0] == "charlie"
    assert top2[1][0] == "alice"

    ss.zadd("bob", 2000)
    assert ss.zrevrank("bob") == 0

    new_score = ss.zincrby("charlie", 500)
    assert new_score == 2300
    assert ss.zrevrank("charlie") == 0

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
    lb.increment_score("player1", 200)
    around = lb.get_around("player2", 3)
    assert len(around) > 0
    print("  Leaderboard: OK")

    print("Testing rank delta...")
    lb2 = Leaderboard("game-2")
    lb2.add_score("a", 100)
    lb2.add_score("b", 200)
    lb2.add_score("c", 300)
    lb2.snapshot_ranks()
    lb2.increment_score("a", 300)
    top = lb2.get_top(3)
    a_entry = next(e for e in top if e.member == "a")
    assert a_entry.rank_delta is not None and a_entry.rank_delta > 0
    print("  rank delta: OK")

    print("\nAll leaderboard tests passed!")


if __name__ == "__main__":
    _test()
