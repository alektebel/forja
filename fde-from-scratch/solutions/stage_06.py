"""FDE From Scratch — stage 6: Mask, forward, restore, and prove nothing leaked.

The stage's own reading of the contract, in the shape the template described: a
closed table of patterns whose candidates are resolved leftmost-longest, a checksum
in exact integer arithmetic, a masker whose placeholders carry a kind and a counter,
and a `forward` that refuses to send a payload in which a `scan` of the outbound text
still finds a value.

Nothing here reads a clock, nothing is random, and nothing is kept outside the
objects the caller can see: two runs of one fixture are the same bytes, and the only
record of a call is the estate's own audit log.
"""

import re

import estate

KINDS = ("ssn", "card", "email", "phone")

DETECTION_KEYS = ("kind", "start", "end", "value")

PLACEHOLDER = "[[%s:%d]]"

GUARD_KEYS = ("masked", "mapping", "kinds", "leaks")

GUARD_ERROR = "the guardrails refuse: %s"

DIGITS = "0123456789"

ACTOR = "guardrail"

CARD_DIGITS = 16

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")

_SSN = re.compile(r"[0-9]{3}-[0-9]{2}-[0-9]{4}")

_INTL_PHONE = re.compile(r"\+[0-9]{1,3}[ -]?[0-9]{3}[ -]?[0-9]{3}[ -]?[0-9]{3}")

_LOCAL_PHONE = re.compile(r"[0-9]{3}[ -][0-9]{3}[ -][0-9]{3}")

_RUN = re.compile(r"[0-9]+(?:[ -][0-9]+)*")


class GuardError(estate.EstateError):
    """The guardrail's refusal: a shape it cannot accept, or a payload it will not send."""


def _text(value, what):
    """`value` as a string, or a refusal naming what arrived instead."""
    if not isinstance(value, str):
        raise GuardError(GUARD_ERROR % ("%s is a %s, not a string"
                                        % (what, type(value).__name__)))
    return value


def _whole(value, what):
    """`value` as a whole number, or a refusal naming it (a `bool` is not one here)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise GuardError(GUARD_ERROR % ("%s is %r, not a whole number" % (what, value)))
    return value


def _names(kinds):
    """The kinds of an audit line's reason: comma-joined, or `none` when there are none."""
    return ",".join(kinds) if kinds else "none"


def _reason(kinds, masked, put_back, leaks):
    """An audit line's reason: the kinds and the counts, and never a value."""
    return "kinds=%s; masked=%d; restored=%d; leaks=%d" % (_names(kinds), masked,
                                                           put_back, leaks)


def digits(text):
    """The digits of `text`, in order, with everything else dropped."""
    _text(text, "the text")
    found = []
    for character in text:
        if character in DIGITS:
            found.append(character)
    return "".join(found)


def luhn(number):
    """Whether the digit run `number` passes its own check digit, in exact integers."""
    _text(number, "the number")
    for position, character in enumerate(number):
        if character not in DIGITS:
            raise GuardError(GUARD_ERROR % ("the digit run carries %r at %d, which is "
                                            "not a digit" % (character, position)))
    if len(number) < 2:
        return False
    total = 0
    for position, character in enumerate(reversed(number)):
        value = int(character)
        if position % 2 == 1:
            value = value * 2
            if value > 9:
                value = value - 9
        total = total + value
    return total % 10 == 0


def _candidates(text):
    """Every shape the text offers, as `(kind, start, end)`, in a fixed order.

    A card is a run of exactly `CARD_DIGITS` digits — separators allowed, and no
    longer run counts — whose check digit adds up; a run that fails it is not offered
    as a card at all, so a mistyped card is not a card with a problem.
    """
    found = []
    for match in _EMAIL.finditer(text):
        found.append(("email", match.start(), match.end()))
    for match in _SSN.finditer(text):
        found.append(("ssn", match.start(), match.end()))
    for match in _INTL_PHONE.finditer(text):
        found.append(("phone", match.start(), match.end()))
    for match in _LOCAL_PHONE.finditer(text):
        found.append(("phone", match.start(), match.end()))
    for match in _RUN.finditer(text):
        run = digits(match.group(0))
        if len(run) == CARD_DIGITS and luhn(run):
            found.append(("card", match.start(), match.end()))
    return found


def detect(text):
    """Every detection in `text`, leftmost-longest, never overlapping."""
    _text(text, "the text")
    found = []
    last_end = 0
    for kind, start, end in sorted(_candidates(text),
                                   key=lambda item: (item[1], -item[2])):
        if start < last_end:
            continue
        found.append({"kind": kind, "start": start, "end": end,
                      "value": text[start:end]})
        last_end = end
    return tuple(found)


class Masker:
    """One masker: the placeholders it has handed out, and the values behind them."""

    def __init__(self):
        """A masker that has seen nothing: no pairs, no counters, no kinds."""
        self._pairs = {}
        self._counters = {}
        self._seen = []

    def _placeholder(self, kind, value):
        """The placeholder of `value`: the one it already has, or the next of its kind.

        The counter is kept per kind and never reused, so two values of one kind are
        two different tokens and a token is the same string every time that value
        comes back — which is what makes a restore of an hour-old text exact.
        """
        known = self._pairs.get(value)
        if known is not None:
            return known
        counter = self._counters.get(kind, 0) + 1
        self._counters[kind] = counter
        placeholder = PLACEHOLDER % (kind, counter)
        self._pairs[value] = placeholder
        if kind not in self._seen:
            self._seen.append(kind)
        return placeholder

    def mask(self, text):
        """`text` with every detection replaced by its placeholder, and the pairs used."""
        _text(text, "the text")
        pieces = []
        made = {}
        cursor = 0
        for detection in detect(text):
            placeholder = self._placeholder(detection["kind"], detection["value"])
            pieces.append(text[cursor:detection["start"]])
            pieces.append(placeholder)
            cursor = detection["end"]
            made[placeholder] = detection["value"]
        pieces.append(text[cursor:])
        return "".join(pieces), tuple(sorted(made.items()))

    def restore(self, text):
        """`text` with this masker's placeholders replaced by the values behind them."""
        _text(text, "the text")
        restored = text
        for placeholder, value in self.mapping():
            restored = restored.replace(placeholder, value)
        return restored

    def mapping(self):
        """Every pair this masker has made, as `(placeholder, value)`, sorted."""
        return tuple(sorted((placeholder, value)
                            for value, placeholder in self._pairs.items()))

    def seen(self):
        """The kinds this masker has masked at least one value of, sorted."""
        return tuple(sorted(self._seen))


def scan(text, mapping):
    """The values of `mapping` that are still in `text`, in `mapping`'s own order."""
    _text(text, "the text")
    if not isinstance(mapping, (tuple, list)):
        raise GuardError(GUARD_ERROR % ("the mapping is a %s, not a sequence of pairs"
                                        % (type(mapping).__name__,)))
    found = []
    for pair in mapping:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise GuardError(GUARD_ERROR % ("the mapping carries %r, not a "
                                            "(placeholder, value) pair" % (pair,)))
        placeholder, value = pair
        if not isinstance(value, str):
            raise GuardError(GUARD_ERROR % ("the pair for %r carries a %s, not a value"
                                            % (placeholder, type(value).__name__)))
        if value in text:
            found.append(value)
    return tuple(found)


def forward(text, model, masker, estate, tick):
    """Mask `text`, send it to `model`, and answer what the wire carried."""
    _text(text, "the text")
    if not callable(model):
        raise GuardError(GUARD_ERROR % ("the model is a %s, not something to call"
                                        % (type(model).__name__,)))
    if not isinstance(masker, Masker):
        raise GuardError(GUARD_ERROR % ("the masker is a %s, not a Masker"
                                        % (type(masker).__name__,)))
    if not callable(getattr(estate, "audit", None)):
        raise GuardError(GUARD_ERROR % ("the estate is a %s, and there is no audit "
                                        "line to write" % (type(estate).__name__,)))
    _whole(tick, "the tick")
    target = getattr(model, "__name__", "model")
    masked, mapping = masker.mask(text)
    kinds = masker.seen()
    leaks = scan(masked, mapping)
    if leaks:
        estate.audit(ACTOR, "forward", target, "refused",
                     _reason(kinds, len(mapping), 0, len(leaks)), tick)
        raise GuardError(GUARD_ERROR % ("%d value(s) of the kinds %s survived into the "
                                        "text sent to %s, so it was not sent"
                                        % (len(leaks), _names(kinds), target)))
    answer = model(masked)
    if not isinstance(answer, str):
        raise GuardError(GUARD_ERROR % ("the model answered a %s, not a string"
                                        % (type(answer).__name__,)))
    restored = masker.restore(answer)
    put_back = 0
    for placeholder, value in mapping:
        if placeholder in restored:
            raise GuardError(GUARD_ERROR % ("the answer still carries %s, which this "
                                            "masker could not put back" % (placeholder,)))
        if placeholder in answer:
            put_back = put_back + 1
    estate.audit(ACTOR, "forward", target, "sent",
                 _reason(kinds, len(mapping), put_back, 0), tick)
    return {"masked": masked, "mapping": mapping, "kinds": kinds, "leaks": leaks}
