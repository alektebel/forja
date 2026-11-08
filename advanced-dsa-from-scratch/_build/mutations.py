"""Planted bugs for advanced-dsa-from-scratch, one catalogue of classic
mistakes per stage, each a minimal edit to a solution.

Run: python3 _build/run_mutations.py
Every entry must print CAUGHT. A MISSED entry is a weak check, not a weak
mutation: strengthen the check, never drop the bug.
"""

MUTATIONS = [
    # --- stage 1: binary heap -------------------------------------------------
    ("sift-down scans 2i/2i+1 instead of its children",
     "stage_01.py",
     "            child = 2 * i + 1\n",
     "            child = 2 * i\n",
     "1"),
    ("pop forgets to sift the last element into the hole",
     "stage_01.py",
     "            self.swaps += 1          # the last element into the hole\n"
     "            self._sift_down(0)",
     "            self.swaps += 1          # the last element into the hole",
     "1"),
    ("the comparison counter counts each comparison twice",
     "stage_01.py",
     "    def _less(self, x, y):\n        self.cmp += 1\n",
     "    def _less(self, x, y):\n        self.cmp += 2\n",
     "1"),

    # --- stage 2: d-ary heap --------------------------------------------------
    ("the build starts at n//D - 1, so the last internal node is never sifted",
     "stage_02.py",
     "            for i in range((len(self._a) - 2) // D, -1, -1):\n",
     "            for i in range(len(self._a) // D - 1, -1, -1):\n",
     "2"),
    ("the parent formula is i//D instead of (i-1)//D",
     "stage_02.py",
     "            parent = (i - 1) // D\n",
     "            parent = i // D\n",
     "2"),
    ("_place never writes the shared position map",
     "stage_02.py",
     "        if self._pos is not None:\n"
     "            self._pos[self.payload_of(item)] = i\n",
     "        if self._pos is not None:\n            pass\n",
     "2"),

    # --- stage 3: lazy merge --------------------------------------------------
    ("ring join crosses the links instead of splicing",
     "stage_03.py",
     "    a.right, b.left = b, a\n    u.right, r.left = r, u\n",
     "    a.right, b.left = r, u\n    u.right, r.left = b, a\n",
     "3"),
    ("union costs two comparisons, not one",
     "stage_03.py",
     "            _join(self.min, other.min)\n            self.work += 1\n",
     "            _join(self.min, other.min)\n"
     "            self.work += 1\n            self.work += 1\n",
     "3"),
    ("union leaves the donor heap alive",
     "stage_03.py",
     "        other.min = None\n        other.n = 0\n",
     "        pass\n        pass\n",
     "3"),

    # --- stage 4: consolidation ----------------------------------------------
    ("consolidation hangs the smaller key under the bigger",
     "stage_04.py",
     "                if y.key < x.key:         # x keeps the smaller key; the\n"
     "                    x, y = y, x           # loser is the tree that hangs\n",
     "                if y.key > x.key:         # x keeps the smaller key; the\n"
     "                    x, y = y, x           # loser is the tree that hangs\n",
     "4"),
    ("extract-min orphans the children instead of splicing them in",
     "stage_04.py",
     "            _join(z, z.child)             # children into the root ring\n",
     "            pass\n",
     "4"),

    # --- stage 5: the cut rule ------------------------------------------------
    ("the cascade marks a root",
     "stage_05.py",
     "        if parent.parent is not None:\n            parent.mark = True",
     "        parent.mark = True",
     "5"),
    ("_move_up does not repair the parent's child entry",
     "stage_05.py",
     "        if parent.child is node:\n            parent.child = successor\n",
     "        if False:\n            parent.child = successor\n",
     "5"),
    ("decrease_key accepts a key that is not smaller",
     "stage_05.py",
     "        if new_key >= node.key:\n",
     "        if new_key > node.key + 10:\n",
     "5"),

    # --- stage 6: Dijkstra ----------------------------------------------------
    ("the lazy engine does not skip stale entries",
     "stage_06.py",
     "        if d > dist[u]:                 # stale: a better way arrived later\n"
     "            skipped += 1\n            continue\n",
     "        if False:\n            skipped += 1\n            continue\n",
     "6"),
    ("a negative weight is accepted",
     "stage_06.py",
     "        if isinstance(w, bool) or not isinstance(w, int) or w < 0:\n",
     "        if isinstance(w, bool) or not isinstance(w, int):\n",
     "6"),

    # --- stage 7: union-find --------------------------------------------------
    ("find stops refusing an unknown element",
     "stage_07.py",
     "        if x not in self.parent:\n"
     "            raise UnionFindError(\"find of an unknown element %r\" % (x,))\n",
     "        if False:\n"
     "            raise UnionFindError(\"find of an unknown element %r\" % (x,))\n",
     "7"),
    ("union never links the two roots",
     "stage_07.py",
     "        self.parent[rb] = ra\n",
     "        self.parent[rb] = rb\n",
     "7"),
    ("Kruskal sorts the edges heaviest-first",
     "stage_07.py",
     "    order = sorted(((w, u, v) for u, v, w in edges))\n",
     "    order = sorted(((w, u, v) for u, v, w in edges), reverse=True)\n",
     "7"),

    # --- stage 8: trie --------------------------------------------------------
    ("autocomplete visits children in reverse lexical order",
     "stage_08.py",
     "            for ch in sorted(n.children):\n",
     "            for ch in sorted(n.children, reverse=True):\n",
     "8"),
    ("a duplicate word is inserted twice",
     "stage_08.py",
     "        if existing is not None and existing.ends:\n"
     "            raise TrieError(\"word %r is already in the trie\" % (word,))\n",
     "        if False:\n"
     "            raise TrieError(\"word %r is already in the trie\" % (word,))\n",
     "8"),
    ("longest_prefix_of returns the first terminal, not the deepest",
     "stage_08.py",
     "            if node.ends:\n                best = current\n",
     "            if node.ends and best == \"\":\n                best = current\n",
     "8"),

    # --- stage 9: LFU ---------------------------------------------------------
    ("the coldest scan keeps the hottest key",
     "stage_09.py",
     "            if rank < best_rank:\n",
     "            if rank > best_rank:\n",
     "9"),
    ("a put refresh does not count as a use",
     "stage_09.py",
     "            self._value[key] = value\n            self._touch(key)\n",
     "            self._value[key] = value\n",
     "9"),
    ("a miss is counted as a hit",
     "stage_09.py",
     "            self.misses += 1\n            return None\n",
     "            self.hits += 1\n            return None\n",
     "9"),

    # --- stage 10: k-d tree and the audit ------------------------------------
    ("the prune uses gap < worst, losing a tied point",
     "stage_10.py",
     "        if len(best) < k or gap * gap <= best[-1][0]:\n",
     "        if len(best) < k or gap * gap < best[-1][0]:\n",
     "10"),
    ("the prune never prunes",
     "stage_10.py",
     "        if len(best) < k or gap * gap <= best[-1][0]:\n",
     "        if True:\n",
     "10"),
    ("the distance ignores the y axis",
     "stage_10.py",
     "    return (point[0] - query[0]) ** 2 + (point[1] - query[1]) ** 2\n",
     "    return (point[0] - query[0]) ** 2\n",
     "10"),
    ("the audit quietly drops one bar",
     "stage_10.py",
     "    return {k: (measured[k], WORK_BARS[k]) for k in sorted(WORK_BARS)}\n",
     "    return {k: (measured[k], WORK_BARS[k]) for k in sorted(WORK_BARS)\n"
     "            if k != \"trie_visits\"}\n",
     "10"),
]
