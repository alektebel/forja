"""TCP/IP From Scratch — the wire.

A frame is bytes, and this module is the link they cross. It is *provided*, and
it is complete: you never write a socket, a thread or a sleep. You write a
*script* of link behaviour instead, and the wire keeps one ordered log of what
actually happened — which is the record this whole course is graded against, and
the reason a stack written here can be asked exactly which segment was
retransmitted and which one was never acknowledged.

    w = Wire(rules={"order": "in_order", "loss": [2], "delay": {4: 3}})
    w.send("10:00:00:00:00:01", "ff:ff:ff:ff:ff:ff", b"...")   # send ordinal 1
    w.advance(3)
    w.deliver()      # what the link hands over at this tick, in order
    w.log()          # every send, drop, hold, duplicate and delivery, ordered

Rules, all of them data:

    order      "in_order"   a frame is never delivered before an earlier one,
                            even when the link is holding that one back
               "swapped"    the same promise of order, except that the first two
                            frames handed over at a tick are exchanged, so a
                            stack that trusts arrival order is caught
    loss       the 1-based send ordinals the link drops, on purpose
    duplicate  the ordinals delivered twice
    delay      {ordinal: ticks} — the frame waits that long *on top of* the
               link's own one tick before it arrives

Every frame takes **one tick** to cross the link, and the tick only passes when a
caller advances it: a send at tick 3 arrives during tick 4, and `delay` makes it
later than that.

DESIGN DECISION — why is a loss an ordinal and not a probability?
Because a check has to be able to say *which* segment the link loses, and the
same run has to come out the same way twice. A course that grades a stack on its
retransmissions cannot have the loss be a coin.

DESIGN DECISION — why does the wire carry bytes instead of frames?
The frame format is the subject of stage 1, the header of stage 3, the segment of
stage 5. If the link parsed them, the interesting half of this course would be
provided instead of written — and a stack could not be asked what it thought it
sent, because the link would have decided that for it.

DESIGN DECISION — why is the log the only evidence?
A stack reports what it believes; the wire reports what crossed it. The capstone
reconciles the two, and every stage in between can be read against the same log:
what was sent, what was dropped, what was held, what arrived twice.
"""

ORDER_IN_ORDER = "in_order"
ORDER_SWAPPED = "swapped"
ORDERS = (ORDER_IN_ORDER, ORDER_SWAPPED)

BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"


class WireError(ValueError):
    """A rule the wire cannot honour, named as the rule that is wrong."""


def mac_text(mac):
    """The wire's spelling of a MAC: six two-digit lowercase groups, colon-joined.

    Refused rather than normalized: `AA:BB:...`, `aa-bb-...` and a 6-byte
    `bytes` are three different things, and a link that silently accepts the
    first two hides a stack that emits them.
    """
    if isinstance(mac, bytes):
        if len(mac) != 6:
            raise WireError("a MAC is 6 bytes, not %d: %r" % (len(mac), mac))
        return ":".join("%02x" % byte for byte in mac)
    if not isinstance(mac, str):
        raise WireError("a MAC is a string or 6 bytes, not %r" % (mac,))
    parts = mac.split(":")
    if len(parts) != 6 or any(len(p) != 2 for p in parts):
        raise WireError("a MAC has six two-digit groups: %r" % (mac,))
    for part in parts:
        if part != part.lower() or any(c not in "0123456789abcdef" for c in part):
            raise WireError("a MAC's groups are lowercase hex: %r" % (mac,))
    return mac


class Wire:
    """The link: frames in, deliveries out, one ordered log of both."""

    def __init__(self, rules=None):
        rules = dict(rules or {})
        order = rules.get("order", ORDER_IN_ORDER)
        if order not in ORDERS:
            raise WireError("order is %r, not one of %r" % (order, ORDERS))
        self._order = order
        self._loss = frozenset(int(n) for n in rules.get("loss") or ())
        self._duplicate = frozenset(int(n) for n in rules.get("duplicate") or ())
        self._delay = {int(k): int(v) for k, v in (rules.get("delay") or {}).items()}
        for ordinal in sorted(self._loss | self._duplicate | set(self._delay)):
            if ordinal < 1:
                raise WireError("a send ordinal starts at 1, not %d" % (ordinal,))
        for ordinal, ticks in sorted(self._delay.items()):
            if ticks < 0:
                raise WireError("a delay is ticks, not %d" % (ticks,))
        self._rules = rules
        self._now = 0
        self._sends = 0
        self._pending = []
        self._log = []
        self._deliveries = 0
        self._dropped = 0

    # -- the clock ---------------------------------------------------------

    def tick(self):
        """The current tick. Time passes only when a caller advances it."""
        return self._now

    def advance(self, ticks=1):
        """Move the clock forward; frames that fall due are delivered.

        Returns the tick you land on. This is the only thing that makes time pass
        and the only thing that hands frames over, so a check reads the wire's
        log (or a host's inbox) after it, rather than stepping the link by hand.
        """
        ticks = int(ticks)
        if ticks < 0:
            raise WireError("time does not run backwards: %d" % (ticks,))
        self._now += ticks
        self._collect()
        return self._now

    # -- the rules ---------------------------------------------------------

    def rules(self):
        """The rules this wire was built with, as they were given."""
        return dict(self._rules)

    def order(self):
        return self._order

    def losses(self):
        """The send ordinals this link drops, ascending."""
        return sorted(self._loss)

    def duplicates(self):
        """The send ordinals this link delivers twice, ascending."""
        return sorted(self._duplicate)

    # -- the traffic -------------------------------------------------------

    def send(self, src, dst, data):
        """Put `data` on the link from `src` to `dst`; return its send ordinal.

        Every send is logged, including the ones this wire is going to drop: a
        send the link ate is not a send that did not happen.
        """
        src, dst = mac_text(src), mac_text(dst)
        if not isinstance(data, bytes):
            raise WireError("the wire carries bytes, not %r" % (type(data).__name__,))
        self._sends += 1
        ordinal = self._sends
        record = {"tick": self._now, "event": "send", "src": src, "dst": dst,
                  "data": data, "ordinal": ordinal}
        self._log.append(record)
        if ordinal in self._loss:
            self._dropped += 1
            self._log.append({"tick": self._now, "event": "drop", "src": src,
                              "dst": dst, "data": data, "ordinal": ordinal})
            return ordinal
        extra = self._delay.get(ordinal, 0)
        due = self._now + 1 + extra
        copies = 2 if ordinal in self._duplicate else 1
        if copies == 2:
            self._log.append({"tick": self._now, "event": "duplicate", "src": src,
                              "dst": dst, "data": data, "ordinal": ordinal})
        if extra:
            self._log.append({"tick": self._now, "event": "hold", "src": src,
                              "dst": dst, "data": data, "ordinal": ordinal,
                              "due": due})
        self._pending.append({"due": due, "ordinal": ordinal, "src": src,
                              "dst": dst, "data": data, "copies": copies})
        return ordinal

    def _ready(self):
        """The pending frames that are due, in the order this link hands them over.

        `in_order` is a promise: a frame is never delivered before one that was
        sent earlier, so a frame the link is holding holds everything sent after
        it. That is what a real link does, and it is what makes a stack's
        retransmission story mean something. `swapped` hands over the same
        prefix with its first two frames exchanged.
        """
        ready = []
        for pending in sorted(self._pending, key=lambda p: p["ordinal"]):
            if pending["due"] > self._now:
                break
            ready.append(pending)
        if self._order == ORDER_SWAPPED and len(ready) > 1:
            ready = ready[1:2] + ready[:1] + ready[2:]
        return ready

    def _collect(self):
        """Hand over everything now due: into the log, out of the queue."""
        for pending in self._ready():
            for copy in range(1, pending["copies"] + 1):
                self._log.append({"tick": self._now, "event": "deliver",
                                  "src": pending["src"], "dst": pending["dst"],
                                  "data": pending["data"],
                                  "ordinal": pending["ordinal"], "copy": copy})
            self._pending.remove(pending)
            self._deliveries += pending["copies"]

    def deliver(self):
        """The frames this link handed over at the current tick, in order.

        A *read*: calling it twice says the same thing, and nothing is consumed.
        Each record is `{"tick", "src", "dst", "data", "ordinal", "copy"}` — the
        ordinal is the send it came from and `copy` is 1 or 2, which is how a
        stack learns to tell a duplicate from a new segment.
        """
        return [{key: record[key] for key in
                 ("tick", "src", "dst", "data", "ordinal", "copy")}
                for record in self._log
                if record["event"] == "deliver" and record["tick"] == self._now]

    def pending(self):
        """What the link is still holding, in queue order (the order it was sent),
        each with the tick it becomes due."""
        return [{"ordinal": p["ordinal"], "due": p["due"], "src": p["src"],
                 "dst": p["dst"]} for p in sorted(self._pending,
                                                  key=lambda p: p["ordinal"])]

    # -- the record --------------------------------------------------------

    def log(self):
        """Every event this link saw, in order: the only evidence there is."""
        return [dict(record) for record in self._log]

    def events(self, event):
        """The log's records of one kind, in order: "send", "drop", "hold",
        "duplicate" or "deliver"."""
        return [dict(r) for r in self._log if r["event"] == event]

    def sent(self):
        """How many sends the stack made, dropped ones included."""
        return self._sends

    def dropped(self):
        """How many sends the link did not deliver."""
        return self._dropped

    def delivered(self):
        """How many frames the link handed over, duplicates counted twice."""
        return self._deliveries

    def reset(self):
        """Forget the traffic and the log; keep the rules and the clock."""
        self._pending = []
        self._log = []
        self._sends = 0
        self._deliveries = 0
        self._dropped = 0
