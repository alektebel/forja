"""WebSocket From Scratch — stage 6: UTF-8, including across fragments.

A text message is not bytes that happen to look like text: it must be valid
UTF-8, and so must the reason in a close frame. A receiver that only calls
``bytes.decode()`` at the end of a message gets two things wrong. First, a
fragment boundary may fall in the middle of a multi-byte character, so a decoder
called on each fragment separately rejects valid text. Second, an overlong
encoding, a surrogate or a code point above U+10FFFF must be rejected even
though a permissive decoder might produce a character anyway.

This stage writes the validator by hand so the rules are visible, then wraps it
in a stream that can be fed one fragment at a time. The stream keeps only the
bytes that could still become a character; everything it has accepted is
decoded and cannot be taken back.

    UTF8Error       invalid bytes, with `.offset` naming the first bad byte
    validate_utf8   bytes -> str, or the first invalid byte named
    UTF8Stream      feed(fragment) ... finish(), with a character split allowed

DESIGN DECISION — why hand-roll UTF-8 instead of using `codecs`? Because the
boundary cases are the lesson: C0 and C1 are overlong starts, ED A0..BF is a
surrogate, F4 90..BF is above U+10FFFF, and a truncated sequence is not the same
mistake as an invalid one. A library hides all four behind one exception, which
is fine in production and useless in a course about what the bytes mean.

TODO: implement `_decode`, `validate_utf8` and `UTF8Stream`.
"""


class UTF8Error(ValueError):
    """Bytes that are not UTF-8, with the offset of the first bad byte."""

    def __init__(self, reason, offset):
        self.reason = reason
        self.offset = offset
        super().__init__("%s at byte %d" % (reason, offset))


def validate_utf8(data):
    """The whole of `data` as text, or the first invalid byte named."""
    raise NotImplementedError("stage 6: implement validate_utf8()")


class UTF8Stream:
    """A UTF-8 decoder that accepts one fragment at a time.

    `feed` may be given a fragment that ends in the middle of a character; the
    incomplete bytes are kept for the next call. `finish` is the moment those
    bytes have to be a whole character: a truncated sequence is an error there,
    even if every earlier fragment was fine.
    """

    def __init__(self):
        raise NotImplementedError("stage 6: implement UTF8Stream.__init__()")

    def feed(self, data):
        """Accept a fragment, decoding everything that is now complete."""
        raise NotImplementedError("stage 6: implement UTF8Stream.feed()")

    def finish(self):
        """The whole message as text, or the truncated bytes named."""
        raise NotImplementedError("stage 6: implement UTF8Stream.finish()")

    def reset(self):
        """Forget the text and any pending bytes; the stream is usable again."""
        raise NotImplementedError("stage 6: implement UTF8Stream.reset()")
