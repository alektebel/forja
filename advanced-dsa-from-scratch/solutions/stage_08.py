"""The trie: counted nodes, deterministic suggestions.

La Rocca, ch. 6 — the prefix tree earns its keep on exactly one query no
hash map can answer: "everything that starts with this". This trie's
autocomplete walks to the prefix node and lists the words beneath it in
LEXICAL order by walking children in sorted key order — a trie that sorted
its children at query time re-sorted the whole subtree on every keystroke,
so children live in ordinary dicts and the walk sorts the keys it reads.

DESIGN DECISION — a word that is a prefix of another word is stored, not
flagged-away: `car` and `cargo` coexist, `"car" in trie` stays True, and
the terminal marker is a bool on the node, so "has children" and "is a
word" stay orthogonal. `passes` (words routed through this node) is a
counter maintained on insert, which is what lets a prefix's fan-out be
answered without a subtree walk.

DESIGN DECISION — insert refuses a duplicate word BEFORE it mutates
anything, and an empty word at all: the two silent corruptions of a trie
are an indexed word that raises `passes` twice, and a zero-length word that
makes every node terminal. A refusal that leaves the ledger half-updated
is worse than a slow one, so the duplicate is detected by a membership
walk first — one pass over the string that the insert costs anyway.
"""

from graphs import WORDS

#: the prefixes the bar measures: one hot, one cold, one miss.
PREFIXES = ("car", "ce", "dij", "zz")

class TrieError(Exception):
    """Refusal: a word the trie will not lie about."""


class Trie:
    """children dicts, one `ends` bool per real word, one `passes` count.
    `visits` accumulates the nodes every autocomplete walk touched: the
    fan-out price of a prefix, which is the whole cost of the query."""

    def __init__(self):
        self.children = {}
        self.ends = False
        self.passes = 0            # words routed through this node
        self.visits = 0            # nodes touched by autocomplete walks

    def _route(self, word, create):
        node = self
        if create:
            node.passes += 1
        for ch in word:
            if create:
                nxt = node.children.get(ch)
                if nxt is None:
                    nxt = Trie()
                    node.children[ch] = nxt
            else:
                nxt = node.children.get(ch)
            if nxt is None:
                return None
            node = nxt
            if create:
                node.passes += 1
        return node

    def insert(self, word):
        if not isinstance(word, str) or word == "":
            raise TrieError("words are non-empty strings, not %r" % (word,))
        existing = self._route(word, create=False)
        if existing is not None and existing.ends:
            raise TrieError("word %r is already in the trie" % (word,))
        node = self._route(word, create=True)
        node.ends = True

    def walk(self, prefix):
        """The node that owns `prefix`, or None — no exception, because
        autocomplete asks this on every keystroke."""
        return self._route(prefix, create=False)

    def __contains__(self, word):
        node = self.walk(word)
        return node is not None and node.ends

    def autocomplete(self, prefix):
        """Words under `prefix`, lexical order, `prefix` itself included
        when it is a word."""
        node = self.walk(prefix)
        if node is None:
            return ()
        out = []

        def visit(n, text):
            self.visits += 1       # the bar counts the walk, not the result
            if n.ends:
                out.append(text)
            for ch in sorted(n.children):
                visit(n.children[ch], text + ch)

        visit(node, prefix)
        return tuple(out)

    def longest_prefix_of(self, word):
        """The deepest terminal node crossed while walking `word` — the
        tokenizer's query, and the reason `walk` hands out nodes."""
        node = self
        best = ""
        current = ""
        for ch in word:
            current += ch
            nxt = node.children.get(ch)
            if nxt is None:
                break
            node = nxt
            if node.ends:
                best = current
        return best


def build(words):
    t = Trie()
    for w in words:
        t.insert(w)
    return t

#: the prefixes the bar measures: one hot, one cold, one miss.
PREFIXES = ("car", "ce", "dij", "zz")


def measure():
    """The measured bars for this stage: the autocomplete walks over the
    fixture's words. `visits` counts the nodes the PREFIXES walks touched
    — the fan-out price of the hot keys, deterministic to the node."""
    t = build(WORDS)
    assert t.autocomplete("car") == ("car", "card", "care", "cargo")
    assert t.autocomplete("dij") == ("dijkstra",)
    assert t.autocomplete("zz") == ()
    assert "chaos" in t and t.longest_prefix_of("catchup") == "catch"
    for p in PREFIXES:
        t.autocomplete(p)
    return {"trie_visits": t.visits}


if __name__ == "__main__":
    print("stage 8 — trie:", measure())
