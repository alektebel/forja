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
        # TODO: children dict, ends flag, passes and visits counters.
        raise NotImplementedError("Trie.__init__")

    def _route(self, word, create):
        # TODO: walk/create the path; a miss on create=False is None, not an exception.
        raise NotImplementedError("Trie._route")

    def insert(self, word):
        # TODO: non-empty str; refuse a duplicate terminal.
        raise NotImplementedError("Trie.insert")

    def walk(self, prefix):
        """The node that owns `prefix`, or None — no exception, because
        autocomplete asks this on every keystroke."""
        # TODO: the node owning the prefix, or None.
        raise NotImplementedError("Trie.walk")

    def __contains__(self, word):
        # TODO: walk, then check the terminal flag.
        raise NotImplementedError("Trie.__contains__")

    def autocomplete(self, prefix):
        """Words under `prefix`, lexical order, `prefix` itself included
        when it is a word."""
        # TODO: the prefix's subtree in lexical order, counting visits.
        raise NotImplementedError("Trie.autocomplete")

    def longest_prefix_of(self, word):
        """The deepest terminal node crossed while walking `word` — the
        tokenizer's query, and the reason `walk` hands out nodes."""
        # TODO: deepest terminal crossed while walking the word.
        raise NotImplementedError("Trie.longest_prefix_of")


def build(words):
    # TODO: insert the words in order.
    raise NotImplementedError("build")

#: the prefixes the bar measures: one hot, one cold, one miss.
PREFIXES = ("car", "ce", "dij", "zz")


def measure():
    """The measured bars for this stage: the autocomplete walks over the
    fixture's words. `visits` counts the nodes the PREFIXES walks touched
    — the fan-out price of the hot keys, deterministic to the node."""
    # TODO: count the visits of the pinned prefix walks.
    raise NotImplementedError("measure")


if __name__ == "__main__":
    print("stage 8 — trie:", measure())
