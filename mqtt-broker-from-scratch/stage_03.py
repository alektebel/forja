"""MQTT Broker From Scratch — stage 3: The topic filter, and the trie that matches it.

Two clients are joined by a string. A publisher names the topic it published to, a
subscriber names the filter it wants, and the broker's whole routing decision is
whether those two strings match. Not whether one contains the other, and not
whether one begins the other: MQTT matches **level by level**, where a level is
the text between two slashes, and the two wildcards mean "exactly one level" and
"my own level and everything under it".

That sounds small, and it is not. `a/b` must not match `a/bc` — the `startswith`
mistake, one character wide, which delivers somebody else's messages to the wrong
client and does it silently. `a/#` **does** match `a`, because `#` covers its own
parent level and the parent is not an exception to it but its first case.
`sport/+` does not match `sport`: `+` is exactly one level, and a filter with a
level to spare has nothing to spend it on. `a/+` matches `a/` — the trailing level
is empty, and empty is a level, which is why the split may not drop it.

The trie is a trie in name only. A broker with a few hundred subscriptions does
not need a tree, and what is worth getting right is the bookkeeping above the
match: one client that reached a topic through three filters is one delivery, at
the highest QoS it was granted, and the answers come back in the order the filters
were inserted, so a test can tell a match from a lucky set.

    MAX_TOPIC_BYTES   65_535: the ceiling a two-byte length can carry, for the name too
    WILDCARDS         ("+", "#"): the two levels a filter may not mean literally
    TopicError        the family every refusal in this stage belongs to
    levels            (name) -> tuple of levels, empty levels kept
    validate_topic    (name) -> the name; refuses a wildcard or an empty topic
    validate_filter   (filter) -> the filter; refuses an empty or misplaced wildcard
    is_wildcard       (level) -> bool: whether the level is "+" or "#"
    Trie.subscribe    (filter, who, qos) -> the filter; refuses what validate_filter refuses
    Trie.unsubscribe  (filter, who) -> True if it was there, False if not
    Trie.match        (topic) -> [(who, qos)], one entry per client
    Trie.filters      () -> the filters held, in insertion order
    Trie.subscribers  (filter) -> the clients on one filter, as (who, qos)

A topic name may not hold a wildcard level and may not be empty; a filter may not
be empty, may not exceed the same ceiling, may put `#` only in its last level, and
may not glue `+` or `#` to other text (`a/+b` is not a level with a wildcard in
it, it is a level nobody can write). A filter whose **first** level is a wildcard
does not match a topic whose first level begins with `$`: `$SYS` and its
neighbours are the broker's own topics, and a subscriber to `#` has not asked for
them.

DESIGN DECISION — why is a name split into levels before anything is compared?
Because a topic is a sequence of levels and not a string, and every rule in this
stage is a statement about one level. A comparator that asks whether the topic
starts with the filter's text answers `yes` for the filter `a/b` and the topic
`a/bc`, and then keeps answering `yes` for that topic's whole subtree — the one
mistake here that delivers a stranger's messages and never announces itself.
Splitting on `/` costs one call and makes `a/b` mean the two levels `a` and `b`,
which is what the wire meant.

DESIGN DECISION — why does `a/#` match `a`, and not only `a/` and below?
Because `#` means "my own level and everything under it", and `a` is the level `#`
belongs to. A subscriber to `a/#` is asking for the `a` subtree *including its
root*, which is how MQTT spells "everything about `a`" in one filter. An
implementation that treats `#` as "one or more levels below" silently strands the
one message a client most expects — a status published directly at `a` — and
nothing else in the system will look wrong.

DESIGN DECISION — why does the `$` rule look only at the first level, and only at
a filter that starts with a wildcard?
Because that is the whole of the rule: a filter that begins with `+` or `#` is a
filter about *any* topic, and topics whose first level begins with `$` are the
broker's own, so the wildcard does not reach them — while the literal filter
`$SYS/#` is precisely the subscription that asks for them. Applying the rule to
every level would break `a/$x`, a perfectly ordinary topic a wildcard filter is
supposed to match; applying it to the whole filter text would break `+/+`. One
level, one comparison.

DESIGN DECISION — why does one client come back once, at its highest QoS, instead
of once per matching filter?
Because a delivery is one delivery. A client subscribed to `a/#` at QoS 0 and to
`a/b` at QoS 2 has said two things about the same message, and the answer is not
two messages: the highest number is the one the client asked to be told at, and
the safer reading of two promises is the stronger one. Returning both would put
two lines on the wire for one publish and break every count that follows.

DESIGN DECISION — why is a refusal an exception while `unsubscribe` answers
`True`/`False`?
Because they are different questions. A filter with `#` in the middle or a level
`+b` is not a filter at all — it is a shape the caller got wrong, and a shape
mismatch raises. Whether *this* client is still on *that* filter is a question
about content, and content is answered with a value: `False` for a name that was
never there is a fact, not a failure, and a caller that has to catch an exception
to learn a client had already left will eventually swallow a real error with it.

TODO: implement
"""

import stage_01

MAX_TOPIC_BYTES = 65_535

WILDCARDS = ("+", "#")


class TopicError(stage_01.ProtocolError):
    """A topic name or a filter that can never be matched the way it was written.

    A `TopicError` is a shape mismatch, so it is raised and never returned: the
    caller wrote a topic or a filter this matcher cannot mean, and it names the
    level or the length that arrived. It is a `ValueError` like every other
    refusal in this course, so one `except` still catches both.
    """


def levels(name):
    """`name` split on `/`, as a tuple, with empty levels kept.

    `a//b` is three levels and the middle one is empty; `a/` is two, the second
    empty. Dropping the empty ones would make `a//b` and `a/b` the same topic.
    """
    raise NotImplementedError("stage 3: implement levels()")


def validate_topic(name):
    """`name` as a topic a client may publish to: no wildcard, not empty.

    Returns the name itself when it is one; a name that is not a `str`, is empty,
    is longer than `MAX_TOPIC_BYTES` bytes, or holds a wildcard level is a
    `TopicError` naming what arrived.
    """
    raise NotImplementedError("stage 3: implement validate_topic()")


def validate_filter(filter):
    """`filter` as a filter a client may subscribe to.

    Returns the filter itself when it is one. `#` is legal only as the last
    level, `+` only as a whole level (`a/+b` is a refusal naming the level), the
    filter may not be empty or over `MAX_TOPIC_BYTES` bytes, and a non-`str` is
    refused naming its type.
    """
    raise NotImplementedError("stage 3: implement validate_filter()")


def is_wildcard(level):
    """Whether `level` is one of `WILDCARDS`, and so means more than itself."""
    raise NotImplementedError("stage 3: implement is_wildcard()")


class Trie:
    """The subscriptions a broker holds, and the clients a topic reaches.

    The filters are kept in the order they were first subscribed, and the clients
    on each in the order they arrived: `match` answers in that first order and
    names each client once, at the highest QoS it holds for the topic.
    """

    def subscribe(self, filter, who, qos):
        """Put `who` on `filter` at `qos`, and return the filter.

        A filter `validate_filter` refuses is refused here the same way and with
        the same message. A client that is already on the filter is moved to
        `qos` without losing its place.
        """
        raise NotImplementedError("stage 3: implement Trie.subscribe()")

    def unsubscribe(self, filter, who):
        """Take `who` off `filter`: `True` if it was there, `False` if not."""
        raise NotImplementedError("stage 3: implement Trie.unsubscribe()")

    def match(self, topic):
        """Every client `topic` reaches, as `[(who, qos)]`.

        One entry per client at its highest QoS, in the order the matching
        filters were inserted.
        """
        raise NotImplementedError("stage 3: implement Trie.match()")

    def filters(self):
        """The filters still held, in the order they were first subscribed."""
        raise NotImplementedError("stage 3: implement Trie.filters()")

    def subscribers(self, filter):
        """The clients on one filter, as `(who, qos)`, in the order they joined."""
        raise NotImplementedError("stage 3: implement Trie.subscribers()")
