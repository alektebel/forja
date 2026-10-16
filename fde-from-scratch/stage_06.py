"""FDE From Scratch — stage 6: Mask, forward, restore, and prove nothing leaked.

Stages 1 to 5 kept the customer's data behind a boundary they own: a session, a
namespace, a store with permissions, a retriever that filters before it answers, a
tool that spends a lease. This one is the boundary that has to hold when the data
leaves the building entirely — a raw account number, a national identity number or a
mailbox in the prompt you hand to a model hosted somewhere else, on a wire you do not
control and in a log you cannot delete. One PII token on that wire ends the deal, so
the question is not whether the model is polite about it: the question is what the
outbound bytes actually contained, and whether anybody can *prove* it after the fact.

The stage's answer is a masker and a scan, and the scan is the part that matters. A
masker that says "I masked it" is a claim; `scan` takes the text that was sent and the
mapping that was used and *looks* — the values it finds are the leak, computed from the
bytes rather than asserted about them. So `forward` does not return "nothing leaked"
as a verdict it believes: it returns the values that were still there, and empty is a
measurement. The masking itself is a substitution the caller can undo: a placeholder
carries the kind of the thing it replaces and a counter of the masker's own, and never
the value's digits, its length or its order, because a placeholder is a token that
travels to a third party, and a token that leaks the value it hides is decoration.

Detection is leftmost-longest and never overlapping, which is a rule about *this*
text and not about the patterns: a 16-digit run that contains an identity number's
shape is one card, not a card with three holes in it, and a run that fails its own
checksum is not the kind of thing it looks like at all. Everything here is exact
integer arithmetic on digits — this course never divides, and a checksum is a sum.

    KINDS              the four kinds this estate's traffic carries, in order
    DETECTION_KEYS     one detection: kind, start, end and the value it found
    PLACEHOLDER        the shape of a placeholder: the kind and a counter, nothing else
    GUARD_KEYS         what a forwarded call carries back: masked, mapping, kinds, leaks
    GuardError         this stage's refusal, a kind of estate.EstateError
    digits(text)       -> the digits of a text, in order, everything else dropped
    luhn(number)       -> bool: whether a digit run passes its own check digit
    detect(text)       -> the detections, leftmost-longest, never overlapping
    Masker()           one masker, stable for its own life
    Masker.mask(text)  -> (the text with every detection replaced, the pairs it replaced)
    Masker.restore(text) -> the text with this masker's placeholders put back
    Masker.mapping()   -> every pair this masker has ever made, sorted by placeholder
    Masker.seen()      -> the kinds it has masked, sorted
    scan(text, mapping) -> the values of `mapping` still present in `text`, mapping order
    forward(text, model, masker, estate, tick) -> GUARD_KEYS, answered from the bytes sent

DESIGN DECISION — why is a leak *computed* over the outbound text instead of being a
verdict the stage asserts?
Because a verdict is a belief and a scan is a measurement. If `forward` answered
`{"leaks": ()}` because its own masker promised to have replaced everything, then the
one bug this stage exists to catch — a pattern that does not match what the masking
thinks it matched — would be invisible: the masker and the claim would come from the
same hand. Scanning the text that was *sent*, with the mapping that was used, makes the
answer depend on the bytes rather than on the masker's opinion of them, and it makes
the guard actionable: a leak is not a log line to be read later, it is a reason not to
send the call at all.

DESIGN DECISION — why is the mapping returned by `mask` the pairs *this* call replaced,
while `mapping()` is everything the masker ever did?
Because the two questions are different and both get asked. `mask` answers what it did
to this text, which is what a caller needs to put the text back together, to count what
was hidden, and to scan this exact outbound payload against exactly the pairs that
produced it — nothing else can be present in it. `mapping()` answers what this masker
knows, which is what a long-lived session needs: the same value must come back as the
same placeholder for the life of the masker, and a text masked an hour ago must still
restore. One answer for both would mean either a restore that forgets, or a scan that
searches for values that were never in the payload.

DESIGN DECISION — why does a placeholder carry a per-kind counter rather than the
value's length, a hash of it, or the value's own digits?
Because a placeholder travels to a party the customer does not trust, and every one of
those is more information than the token needs to do its job. The job is to be a
distinct, stable, reversible label: distinct so that two values never collapse into
one, stable so that the same value is the same token twice, reversible so that the
answer can be given back in the customer's own words. A counter satisfies all three and
carries nothing else — not how long the value was (a nine-digit run is an identity
number, and a length is a fact about the customer's data), not its digits, and not its
position in the text.

DESIGN DECISION — why are detections leftmost-longest, and why is that not a
preference about which kind wins?
Because the alternative is worse than a wrong label: it is a hole. A naive matcher
that takes whatever it finds first produces an identity number *inside* a card number,
and then the masked text carries the pieces of the card around the token — the value is
not hidden, it is fragmented, and it is still on the wire. Taking the leftmost position
and, at that position, the longest candidate means a run is classified as the thing
that covers it, and a candidate that overlaps an accepted detection is simply dropped.
The rule is decided by the text's own geometry, not by a priority between kinds, so
there is no ordering of `KINDS` that could change what a card is.

DESIGN DECISION — why is the record of a forwarded call the *wire*, and not the
answer?
Because the record is what an auditor reads and the answer is what the customer reads.
`masked` is the exact text that left the building — the only bytes worth auditing — and
the answer to it is restored with the same masker so that a model which echoed a
placeholder gives the customer their own words back. The count of placeholders put back
is on the audit line; the answer itself is not, because the record must be safe to
write down and the answer is not.

DESIGN DECISION — why is every number in this stage a count of digits or of pairs?
Because this course has no floats, and because money and checksums are exact. A Luhn
check is a sum of doubled and undoubled digits reduced modulo ten, done on the digits
themselves, and a length is an `int` comparison — nothing here is estimated, rounded or
scaled, so a card that fails its checksum fails it for every caller on every run.

TODO: implement `digits`, `luhn`, `detect`, `Masker`, `scan` and `forward` in this
file: the digits of a text, the checksum in exact integer arithmetic, the leftmost-
longest detection over a closed table of patterns, the stable masker with its
kind-and-counter placeholders, the scan of an outbound text against its own mapping,
and the forward that refuses to send a payload in which anything survived.
"""

import estate

KINDS = ("ssn", "card", "email", "phone")

DETECTION_KEYS = ("kind", "start", "end", "value")

PLACEHOLDER = "[[%s:%d]]"

GUARD_KEYS = ("masked", "mapping", "kinds", "leaks")


class GuardError(estate.EstateError):
    """The guardrail's refusal: a shape it cannot accept, or a payload it will not send."""


def digits(text):
    """The digits of `text`, in order, with everything else dropped.

    The one place where "a number" becomes a fact: every pattern, checksum and
    comparison in this stage is done on what this answers, so a card written with
    spaces, a card written with dashes and a card written as sixteen characters all
    become the same sixteen digits before anything is decided about them.

    A text that is not a string is refused, naming the type that arrived.
    """
    raise NotImplementedError("stage 6: implement digits()")


def luhn(number):
    """Whether the digit run `number` passes its own check digit, in exact integers.

    Every second digit counted from the right, the last one included, is doubled and
    the digits of the double are added (which is `d * 2 - 9` when the double is more
    than one digit); the sum is a multiple of ten exactly when the run is well formed.
    The comparison is on the digits, never on the text: a run that arrives with
    spaces in it is checked the same way after `digits`, and a run that carries
    something that is not a digit is refused, naming the character and where it sat.

    A run too short to carry a check digit is `False`: there is nothing to check, and
    a checksum of nothing must never come back as a pass.
    """
    raise NotImplementedError("stage 6: implement luhn()")


def detect(text):
    """Every detection in `text`, leftmost-longest, never overlapping.

    Each of `KINDS` has one shape, and a candidate that fails the kind's own test —
    a sixteen-digit run whose check digit does not add up — is not a candidate at
    all, so a mistyped card is not a card rather than a card with a problem. The
    candidates are then resolved against each other: the leftmost start wins, and at
    one start the longest wins, so a run that contains another kind's shape is
    classified as the thing that covers it and the smaller candidate is dropped
    instead of being masked out of the middle of it.

    The answer is a tuple of `DETECTION_KEYS` records in start order, and `value` is
    exactly `text[start:end]` — what a caller can quote as evidence, and what the
    masker replaces. A text that is not a string is refused, naming the type.
    """
    raise NotImplementedError("stage 6: implement detect()")


class Masker:
    """One masker: the placeholders it has handed out, and the values behind them.

    A masker is stable for its own life and holds nothing outside itself. The same
    value is the same placeholder on the second text it appears in, two different
    values never share one, and the placeholder of a value depends on nothing but its
    kind and the order the masker met it — not on the length of the value, not on the
    text it arrived in, and not on any state of the process outside this object.
    """

    def __init__(self):
        """A masker that has seen nothing: no pairs, no counters, no kinds."""
        self._pairs = {}
        self._counters = {}
        self._seen = []

    def mask(self, text):
        """`text` with every detection replaced by its placeholder, and the pairs used.

        The answer is `(masked, mapping)` where `masked` holds no detection's value
        any more and `mapping` is the tuple of `(placeholder, value)` pairs *this
        call* made, sorted by placeholder. The pairs are the ones a caller needs to
        scan the payload it is about to send and to count what was hidden, and each
        value keeps whatever placeholder the masker gave it the first time it was
        seen — masking the same text twice answers the same bytes twice.

        A text that is not a string is refused, naming the type.
        """
        raise NotImplementedError("stage 6: implement Masker.mask()")

    def restore(self, text):
        """`text` with this masker's placeholders replaced by the values behind them.

        The inverse of `mask` for anything this masker masked, and nothing else: a
        placeholder this masker never handed out is left exactly as it stands, and so
        is every value that was never masked, so restoring a text twice and restoring
        a text that was never masked are both well defined. A text that is not a
        string is refused, naming the type.
        """
        raise NotImplementedError("stage 6: implement Masker.restore()")

    def mapping(self):
        """Every pair this masker has made, as `(placeholder, value)`, sorted.

        The whole of what it knows, in one fixed order, so that two maskers that saw
        the same values answer the same tuple and a caller can compare them.
        """
        raise NotImplementedError("stage 6: implement Masker.mapping()")

    def seen(self):
        """The kinds this masker has masked at least one value of, sorted."""
        raise NotImplementedError("stage 6: implement Masker.seen()")


def scan(text, mapping):
    """The values of `mapping` that are still in `text`, in `mapping`'s own order.

    This is the stage's proof of work: it does not ask the masker anything, it looks
    at the text, and everything it answers is a value that survived into the bytes
    being examined. The order is the mapping's and not the text's, so a caller that
    sends this tuple to a log or a comparison gets the same tuple however the values
    happened to be arranged in the text.

    A text that is not a string is refused, naming the type, and a `mapping` that is
    not a sequence of `(placeholder, value)` pairs is refused naming what arrived.
    """
    raise NotImplementedError("stage 6: implement scan()")


def forward(text, model, masker, estate, tick):
    """Mask `text`, send it to `model`, and answer what the wire carried.

    The order is the whole of the stage. The text is masked by `masker`, the masked
    text is scanned against the pairs that produced it, and a payload in which a
    value survived is refused *before* the model is called — the leak is on the wire
    in that case, and no amount of politeness from the model makes it gone. The
    audit line for a refused call names the kinds and the count, never the values.
    Only when nothing survived does `model` see the masked text; its answer is
    restored with the same masker so the customer reads their own words, a
    placeholder that came back and could not be put back is itself a refusal, and
    the call writes one audit line carrying the kinds, the number of distinct values
    masked and the number put back — kinds and counts only, never a value.

    The answer is a `GUARD_KEYS` record: `masked` is exactly what was sent, `mapping`
    the pairs used, `kinds` the kinds masked, sorted, and `leaks` what `scan` found
    in the outbound text, which is empty when the call was allowed to happen.
    """
    raise NotImplementedError("stage 6: implement forward()")
