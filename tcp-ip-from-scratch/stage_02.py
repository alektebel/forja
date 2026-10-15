"""TCP/IP From Scratch — stage 2: ARP, and the address that ages out.

A frame can only be addressed to a MAC, and a MAC is the one thing a peer is
never told. So the first thing every stack does on a new link is ask the whole
link a question it can only answer once: *who has this address?* The question
goes to `BROADCAST_MAC`, because nobody knows who to ask; the answer goes back to
the one host that asked, because a broadcast that carries an answer is an answer
every host on the link now believes.

The ARP message is 28 bytes with no length field of its own — `htype | ptype |
hlen | plen | op | sha | spa | tha | tpa` — which is why this stage has to say
what the frame it arrives in does *not*: a padded frame hands up its padding as
payload, and only the layer that knows `ARP_LENGTH` can cut the message out of
it. The message is not the frame, and the frame is not the message.

The second half of the stage is the cache, and it is where the stage's title
comes from. An address that is learned and never ages is an address the stack
will keep using after the machine behind it has moved, been replaced or been
taken over; an entry that ages out but is still returned by `lookup` is the same
lie with better bookkeeping. So an entry lives `CACHE_TICKS` ticks, a `lookup`
after that lifetime is `None` *and takes the entry away*, and `expire` is the
purge a caller with its own clock runs. Time comes from the caller or from the
wire — never from a clock inside this module — so every one of these numbers is
a number a check can predict.

DESIGN DECISION — why does `request` wrap its own frame and read the answer out
of the host's box, instead of being handed a callback to run while it waits?
Because a callback is a second way for a stack to be driven, and this course has
exactly one: time passes when a caller says so. `request` sends the question,
advances the wire by the ticks it promises to wait, and looks at what arrived —
which means the peer's answer has to be on the link before the wait begins, and
that is a fact about a one-tick link, not a limitation of the stage. The test of
the design is that the unanswered case is a *result* — `mac` is `None` — rather
than a stack that spins forever.

DESIGN DECISION — why must a reply carry the asker's MAC and address in `tha`/
`tpa` and the answer in `sha`/`spa`?
Because that is what makes a reply learnable by the peer that asked *without*
that peer keeping a list of questions it once sent. The asker learns the pair
out of the message's own sender fields, and it can check that the pair is about
the address it asked for; a reply that puts the answer in `tpa` teaches the
asker nothing it can verify, and a reply addressed to the broadcast address
teaches every host on the link at once, including the hosts that never asked.

DESIGN DECISION — why does `lookup` remove an entry it finds expired, when
`expire` exists for the same job?
Because the two callers are different. `expire` is for a stack that has a clock
of its own and wants to sweep on a schedule; `lookup` is for a stack that has
none and is about to answer a question about a peer *right now*. If `lookup`
returned a stale address and left it in the table, a caller that never sweeps
would use it forever — the table would be a cache with no memory of time at all.
Removing on read means the stale answer can never be used twice.

DESIGN DECISION — why does `reply_to` refuse a request aimed at somebody else
rather than stay silent?
Silence is indistinguishable from a host that is down, and a stack that answers
every request it overhears is a stack that poisons caches: any host could claim
any address by answering for it. A refusal is loud, names the pair it was asked
about, and is what lets a check prove that exactly one host answered.

    ARP_LENGTH    the 28 bytes of an ARP message, which is what makes it
                  readable inside a padded frame
    ARP_REQUEST   who has this address?
    ARP_REPLY     I do, and here is my pair
    CACHE_TICKS   how long an answer is believed
    build_message the 28 bytes, from one operation and two address pairs
    parse_message the message's five facts, refusing anything it cannot be
    request       the whole exchange: ask everybody, wait, believe one answer
    reply_to      the answer, only for a request that was aimed at this pair
    Cache         learned addresses, with a lifetime

`ArpError` is the family, and every refusal names the offender: the operation
nobody knows, the message that is not 28 bytes, the MAC that is not six bytes,
the address that is not four octets, and the `hlen`/`plen`/`ptype` that say this
is a message this stack cannot honour.

TODO: implement `build_message`, `parse_message`, `request`, `reply_to` and every
method of `Cache`.
"""

import stage_01
from wire import BROADCAST_MAC, mac_text

ARP_LENGTH = 28
ARP_REQUEST, ARP_REPLY = 1, 2
CACHE_TICKS = 8


class ArpError(ValueError):
    """An ARP message this stack cannot build or read, named as what is wrong."""


def build_message(op, sender, sender_ip, target_mac, target_ip):
    """The 28 bytes: `htype | ptype | hlen | plen | op | sha | spa | tha | tpa`.

    `op` is `ARP_REQUEST` or `ARP_REPLY`; the two addresses are the pair the
    message is *from* and the two targets are the pair it is *about*, each MAC in
    either form `mac_text` takes and each address as text or as four octets. A
    request puts `BROADCAST_MAC` in `tha`, because nobody knows the address it is
    asking about yet.
    """
    raise NotImplementedError("stage 2: implement build_message()")


def parse_message(message):
    """The message's five facts: `{"op", "sender", "sender_ip", "target",
    "target_ip"}`, with both addresses in their text forms and `op` as the
    number the wire carries.

    Anything that cannot be this message raises, naming it: a length that is not
    `ARP_LENGTH`, a hardware type or protocol that is not the one this course
    speaks, an `hlen`/`plen` that is not 6/4, and an operation nobody knows.
    """
    raise NotImplementedError("stage 2: implement parse_message()")


def request(wire, host, ip, now=None):
    """The whole exchange: `{"ip", "mac", "sent", "received", "ticks"}`.

    A request for `ip` crosses the wire to `BROADCAST_MAC`, the wire is advanced
    by the ticks this call waits — counted from `now` when one was given and from
    the wire's own clock otherwise — and the first reply in this host's box that
    names this host's pair and answers for `ip` is the answer. Nothing else in
    the box counts: not a frame that is not ARP, not a message that is not a
    message, and not a reply about somebody else. Nobody answering is
    `mac=None` with `received=False`, and `sent` is the send ordinal the wire
    gave the question.
    """
    raise NotImplementedError("stage 2: implement request()")


def reply_to(message, my_mac, my_ip):
    """The reply to a request aimed at this pair, as a 28-byte message.

    Only a request is answered, and only when its target fields are this MAC and
    this address (a request sent to `BROADCAST_MAC` names no single target, so it
    is aimed at everybody). The asker's own pair goes into `tha`/`tpa` and this
    pair into `sha`/`spa`, which is what lets the asker learn the answer. The
    caller wraps the message in a frame with stage 1's `build`, addressed to the
    asker.
    """
    raise NotImplementedError("stage 2: implement reply_to()")


class Cache:
    """Learned addresses, each with the tick it was learned and the one it dies.

    A `Cache` has no clock: `learn`, `lookup` and `expire` are handed the tick
    they happen at, and the same call at the same tick gives the same answer.
    """

    def __init__(self, ticks=CACHE_TICKS):
        """A cache whose entries live `ticks` ticks, and an empty log."""
        raise NotImplementedError("stage 2: implement Cache.__init__()")

    def learn(self, ip, mac, now):
        """Believe `mac` for `ip` from `now`: `{"ip", "mac", "fresh",
        "expires"}`.

        Learning an address that is already known refreshes it and reports
        `fresh=True`; learning it with a different MAC replaces the MAC, and that
        replacement is a decision the log records.
        """
        raise NotImplementedError("stage 2: implement Cache.learn()")

    def lookup(self, ip, now):
        """The MAC believed for `ip`, or `None` — an expired entry is gone.

        An entry whose lifetime has run out is `None` *and* is taken out of the
        table, so the same question at the same tick cannot be asked twice.
        """
        raise NotImplementedError("stage 2: implement Cache.lookup()")

    def expire(self, now):
        """The entries that ran out, as `(ip, mac, expires)`, in the order they
        were learned, removed from the table as they are reported."""
        raise NotImplementedError("stage 2: implement Cache.expire()")

    def entries(self, now):
        """The live entries, as `(ip, mac, expires)`, sorted by address."""
        raise NotImplementedError("stage 2: implement Cache.entries()")

    def log(self):
        """Every decision this cache made, in order, as dicts."""
        raise NotImplementedError("stage 2: implement Cache.log()")
