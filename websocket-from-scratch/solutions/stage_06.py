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
"""


class UTF8Error(ValueError):
    """Bytes that are not UTF-8, with the offset of the first bad byte."""

    def __init__(self, reason, offset):
        self.reason = reason
        self.offset = offset
        super().__init__("%s at byte %d" % (reason, offset))


def _decode(data, final):
    """Decode as much of `data` as is complete; return (text, consumed).

    When `final` is false, a truncated sequence at the end is returned as
    pending bytes instead of being judged. When it is true, those bytes are the
    error the caller was waiting to hear about.
    """
    text = []
    index = 0
    size = len(data)
    while index < size:
        first = data[index]
        if first <= 0x7F:
            text.append(chr(first))
            index += 1
            continue
        if 0xC2 <= first <= 0xDF:
            need = 1
            ranges = ((0x80, 0xBF),)
        elif first == 0xE0:
            need = 2
            ranges = ((0xA0, 0xBF), (0x80, 0xBF))
        elif 0xE1 <= first <= 0xEC:
            need = 2
            ranges = ((0x80, 0xBF), (0x80, 0xBF))
        elif first == 0xED:
            need = 2
            ranges = ((0x80, 0x9F), (0x80, 0xBF))
        elif 0xEE <= first <= 0xEF:
            need = 2
            ranges = ((0x80, 0xBF), (0x80, 0xBF))
        elif first == 0xF0:
            need = 3
            ranges = ((0x90, 0xBF), (0x80, 0xBF), (0x80, 0xBF))
        elif 0xF1 <= first <= 0xF3:
            need = 3
            ranges = ((0x80, 0xBF), (0x80, 0xBF), (0x80, 0xBF))
        elif first == 0xF4:
            need = 3
            ranges = ((0x80, 0x8F), (0x80, 0xBF), (0x80, 0xBF))
        else:
            raise UTF8Error("invalid UTF-8 start byte 0x%02X" % (first,), index)

        if index + 1 + need > size:
            available = size - index - 1
            for offset, (low, high) in enumerate(ranges, start=1):
                if offset > available:
                    break
                byte = data[index + offset]
                if not low <= byte <= high:
                    raise UTF8Error("invalid UTF-8 continuation byte 0x%02X"
                                    % (byte,), index + offset)
            if final:
                raise UTF8Error("truncated UTF-8 sequence", index)
            return "".join(text), index
        for offset, (low, high) in enumerate(ranges, start=1):
            byte = data[index + offset]
            if not low <= byte <= high:
                raise UTF8Error("invalid UTF-8 continuation byte 0x%02X"
                                % (byte,), index + offset)

        if need == 1:
            codepoint = ((first & 0x1F) << 6) | (data[index + 1] & 0x3F)
        elif need == 2:
            codepoint = (((first & 0x0F) << 12)
                         | ((data[index + 1] & 0x3F) << 6)
                         | (data[index + 2] & 0x3F))
        else:
            codepoint = (((first & 0x07) << 18)
                         | ((data[index + 1] & 0x3F) << 12)
                         | ((data[index + 2] & 0x3F) << 6)
                         | (data[index + 3] & 0x3F))
        text.append(chr(codepoint))
        index += 1 + need
    return "".join(text), size


def validate_utf8(data):
    """The whole of `data` as text, or the first invalid byte named."""
    if not isinstance(data, (bytes, bytearray)):
        raise UTF8Error("a text payload is bytes, not %s"
                        % (type(data).__name__,), 0)
    text, consumed = _decode(bytes(data), True)
    if consumed != len(data):
        raise UTF8Error("truncated UTF-8 sequence", consumed)
    return text


class UTF8Stream:
    """A UTF-8 decoder that accepts one fragment at a time.

    `feed` may be given a fragment that ends in the middle of a character; the
    incomplete bytes are kept for the next call. `finish` is the moment those
    bytes have to be a whole character: a truncated sequence is an error there,
    even if every earlier fragment was fine.
    """

    def __init__(self):
        self._buffer = b""
        self._parts = []
        self._base = 0
        self._finished = False

    def feed(self, data):
        """Accept a fragment, decoding everything that is now complete."""
        if self._finished:
            raise UTF8Error("a UTF-8 stream cannot be fed after finish",
                            self._base + len(self._buffer))
        if not isinstance(data, (bytes, bytearray)):
            raise UTF8Error("a text fragment is bytes, not %s"
                            % (type(data).__name__,), self._base)
        buffer = self._buffer + bytes(data)
        try:
            text, consumed = _decode(buffer, False)
        except UTF8Error as exc:
            raise UTF8Error(exc.reason, self._base + exc.offset)
        self._parts.append(text)
        self._buffer = buffer[consumed:]
        self._base += consumed
        return None

    def finish(self):
        """The whole message as text, or the truncated bytes named."""
        if self._finished:
            raise UTF8Error("a UTF-8 stream cannot be finished twice",
                            self._base + len(self._buffer))
        self._finished = True
        try:
            text, consumed = _decode(self._buffer, True)
        except UTF8Error as exc:
            raise UTF8Error(exc.reason, self._base + exc.offset)
        if consumed != len(self._buffer):
            raise UTF8Error("truncated UTF-8 sequence", self._base + consumed)
        self._parts.append(text)
        self._buffer = b""
        return "".join(self._parts)

    def reset(self):
        """Forget the text and any pending bytes; the stream is usable again."""
        self._buffer = b""
        self._parts = []
        self._base = 0
        self._finished = False
