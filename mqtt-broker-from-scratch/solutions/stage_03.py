"""MQTT Broker From Scratch — stage 3: The topic filter, and the trie that matches it.

See `stage_01.py` for the surface and the design decisions; this is the matcher
every later stage routes a message through.
"""

import stage_01

MAX_TOPIC_BYTES = 65_535

WILDCARDS = ("+", "#")


class TopicError(stage_01.ProtocolError):
    """A topic name or a filter that can never be matched the way it was written.

    A `TopicError` is a shape mismatch, so it is raised and never returned: the
    caller wrote a topic or a filter this matcher cannot mean, and the message
    names the level, the length or the type that arrived. It is a `ValueError`
    like every other refusal in this course — and a `ProtocolError`, because the
    matcher is judging a name that came off the wire.
    """


def is_wildcard(level):
    """Whether `level` is one of `WILDCARDS`, and so means more than itself.

    Only a whole level can be a wildcard: `+b` is text, and a topic may hold it.
    """
    return level in WILDCARDS


def levels(name):
    """`name` split on `/`, as a tuple, with empty levels kept.

    `a//b` is three levels and the middle one is empty; `a/` is two, the second
    empty. Dropping the empty ones would make `a//b` and `a/b` the same topic — a
    different subscription, silently answered by the wrong set of messages.
    """
    return tuple(name.split("/"))


def _check_name(name, what):
    """The bytes of `name` when it could be a name at all, refused otherwise.

    The `what` in every message is the word the caller used — "topic" or
    "filter" — so a refusal from either one still says which it was.
    """
    if not isinstance(name, str):
        raise TopicError("a %s must be a str, not %s"
                         % (what, type(name).__name__,))
    payload = name.encode("utf-8")
    if len(payload) > MAX_TOPIC_BYTES:
        raise TopicError("a %s of %d bytes is above the maximum %d"
                         % (what, len(payload), MAX_TOPIC_BYTES))
    if not name:
        raise TopicError("a %s of %r is empty" % (what, name))
    return payload


def validate_topic(name):
    """`name` as a topic a client may publish to: no wildcard, not empty.

    Returns the name itself when it is one; a name that is not a `str`, is empty,
    is longer than `MAX_TOPIC_BYTES` bytes, or holds a wildcard level is a
    `TopicError` naming what arrived. A level that merely contains a `+`, such as
    `+b`, is text and is left alone: only a whole level can be a wildcard.
    """
    _check_name(name, "topic")
    for level in levels(name):
        if is_wildcard(level):
            raise TopicError("a topic may not hold the wildcard %r" % (level,))
    return name


def validate_filter(filter):
    """`filter` as a filter a client may subscribe to.

    Returns the filter itself when it is one. `#` is legal only as the last
    level, `+` only as a whole level (`a/+b` is a refusal naming the level), the
    filter may not be empty or over `MAX_TOPIC_BYTES` bytes, and a non-`str` is
    refused naming its type.
    """
    _check_name(filter, "filter")
    parts = levels(filter)
    for at, level in enumerate(parts):
        if is_wildcard(level):
            if level == "#" and at != len(parts) - 1:
                raise TopicError(
                    "a '#' must be the last level, and it was level %d of %d"
                    % (at, len(parts)))
            continue
        if "+" in level or "#" in level:
            raise TopicError("a wildcard must be a whole level (the level was %r)"
                             % (level,))
    return filter


def _matches(flevels, tlevels):
    """Whether the filter's levels match the topic's, component by component.

    `#` matches its own level and everything under it, so `a/#` matches `a`; `+`
    matches exactly one level, empty or not, so `a/+` matches `a/` and `sport/+`
    does not match `sport`. A filter whose first level is a wildcard does not
    reach a topic whose first level begins with `$`.
    """
    if (flevels and is_wildcard(flevels[0])
            and tlevels and tlevels[0].startswith("$")):
        return False
    for at, level in enumerate(flevels):
        if level == "#":
            return at == len(flevels) - 1
        if at >= len(tlevels):
            return False
        if level != "+" and level != tlevels[at]:
            return False
    return len(flevels) == len(tlevels)


class Trie:
    """The subscriptions a broker holds, and the clients a topic reaches.

    The filters are kept in the order they were first subscribed, and the clients
    on each in the order they arrived: `match` answers in that first order and
    names each client once, at the highest QoS it holds for the topic.
    """

    def __init__(self):
        """An empty trie: no filter held, and nobody on anything."""
        self._order = []
        self._who = {}

    def subscribe(self, filter, who, qos):
        """Put `who` on `filter` at `qos`, and return the filter.

        A filter `validate_filter` refuses is refused here the same way and with
        the same message. A client that is already on the filter is moved to
        `qos` without losing its place, because the filter's place is what
        `match` answers in.
        """
        validate_filter(filter)
        if filter not in self._who:
            self._order.append(filter)
            self._who[filter] = {}
        self._who[filter][who] = qos
        return filter

    def unsubscribe(self, filter, who):
        """Take `who` off `filter`: `True` if it was there, `False` if not.

        A client that was never on the filter is not an error — it is the answer
        `False`. The filter is dropped from `filters()` once nobody is left on
        it, so a later subscribe inserts it again, at the end.
        """
        on = self._who.get(filter)
        if not on or who not in on:
            return False
        del on[who]
        if not on:
            del self._who[filter]
            self._order.remove(filter)
        return True

    def match(self, topic):
        """Every client `topic` reaches, as `[(who, qos)]`.

        One entry per client at its highest QoS, in the order the matching
        filters were inserted: the filters are walked in that order and a client
        already seen keeps the place it was first seen in, whatever the filter
        that would have named it a second time happens to be.
        """
        parts = levels(topic)
        best = {}
        answer = []
        for filter in self._order:
            if not _matches(levels(filter), parts):
                continue
            for who, qos in self._who[filter].items():
                if who not in best:
                    answer.append(who)
                    best[who] = qos
                elif qos > best[who]:
                    best[who] = qos
        return [(who, best[who]) for who in answer]

    def filters(self):
        """The filters still held, in the order they were first subscribed."""
        return tuple(self._order)

    def subscribers(self, filter):
        """The clients on one filter, as `(who, qos)`, in the order they joined.

        A filter nobody is on — never held, or unsubscribed down to empty — is
        an empty tuple, not an error.
        """
        return tuple(self._who.get(filter, {}).items())
