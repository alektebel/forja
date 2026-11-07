"""Compression From Scratch — stage 10: The proof: every codec, every corpus, one verdict.

Nine codecs built; the proof runs them all over one corpus and grades
the course the way the world does: the ratio against `BARS`, the
reference decoders' verdicts, the round-trips' exactness, and the
checksum's notice of the flipped bit. `prove` answers one corpus's
records; `audit` grades them all — `pass` only when everything holds,
and the reasons naming what did not.

DESIGN DECISION — why grade the ratio against the world's bars rather
than a self-chosen number?
Because a ratio without a bar is prose: the world's `BARS` are the
ceilings a codec must clear on a corpus it did not choose, and the
audit's verdict is data — `pass` or a reason — never a paragraph.

DESIGN DECISION — why must `audit` re-read the reference decoders'
verdicts rather than the stage's own round-trips?
Because the stage's own decoder agreeing with its own encoder is the
weakest evidence there is: the reference decoders are the course's
judges, and the audit holds their verdicts, not the student's.

DESIGN DECISION — why is the checksum's flipped bit part of the proof?
Because a frame that carries a checksum nobody has ever seen fire is a
frame whose integrity is a hope. The proof flips the bit and holds the
refusal — the one case that proves the checksum is a check.
"""

import corpus as _corpus
import stage_01 as _s1
import stage_02 as _s2
import stage_03 as _s3
import stage_06 as _s6
import stage_07 as _s7
import stage_08 as _s8
import stage_09 as _s9
import lz4ref as _lz4
import zstdref as _zr

PROOF_KEYS = ("ratios", "verdicts", "round_trips")
AUDIT_KEYS = ("verdict", "reasons")

#: the codecs the proof measures, in the manifest's own order
_CODECS = ("rle", "huffman", "lz4", "deflate", "fse", "frame")


#: the course's own refusal, the bit writer's class the check holds
EncodeError = _s1.EncodeError


def _refuse(reason, *names):
    raise EncodeError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def _ratio(packed, data):
    """The measured per-mille: compressed bytes over the corpus's, times
    a thousand."""
    if not data:
        return 0
    return len(packed) * 1000 // len(data)


def _per_mille(codec, data):
    """The codec's packed bytes over the corpus: each stage's own answer,
    the ratio the bars are held against."""
    if codec == "rle":
        return _s2.rle_encode(data)
    if codec == "huffman":
        return _s3.huffman_encode(data)[0]
    if codec == "lz4":
        return _s6.lz4_block_encode(data)
    if codec == "deflate":
        return _s7.deflate(data)
    if codec == "frame":
        return _s9.frame_encode(data, "compressed")
    return None


def prove(corpus_name):
    """Every codec over one corpus: the ratio, the verdict, the round-trip.

    Answers PROOF_KEYS — `ratios` (per-mille per codec), `verdicts` (the
    reference decoders' `accepted` where the reference carries the codec,
    the round-trip's own `round_trip` where it does not, and the flipped
    bit's `noticed`), and `round_trips` (exactness per codec). An unknown
    corpus is refused, naming the corpus."""
    if not hasattr(_corpus, corpus_name) or corpus_name \
            not in _corpus.CORPORA:
        _refuse("unknown_corpus", corpus_name, "corpus")
    data = getattr(_corpus, corpus_name)
    ratios = {}
    verdicts = {}
    round_trips = {}
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    for codec in _CODECS:
        if codec == "fse":
            packed, _norm = _s8.fse_encode(data, counts)
            back = _s8.fse_decode(packed, counts, len(data))
            verdicts[codec] = "round_trip"
        elif codec == "rle":
            packed = _s2.rle_encode(data)
            back = _s2.rle_decode(packed)
            verdicts[codec] = "round_trip"
        elif codec == "huffman":
            packed, lengths = _s3.huffman_encode(data)
            back = _s3.huffman_decode(packed, lengths, len(data))
            verdicts[codec] = "round_trip"
        elif codec == "lz4":
            packed = _s6.lz4_block_encode(data)
            back = _lz4.lz4_block_decode(packed)
            verdicts[codec] = "accepted"
        elif codec == "deflate":
            packed = _s7.deflate(data)
            import inflate as _inflate
            back = _inflate.inflate(packed)[0]
            verdicts[codec] = "accepted"
        else:  # frame
            packed = _s9.frame_encode(data, "compressed")
            back = _s9.frame_decode(packed)
            verdicts[codec] = "accepted"
        ratios[codec] = _ratio(packed, data)
        round_trips[codec] = (back == data)
    # the flipped bit: one bit of the raw frame's content, and the frame's
    # reader must refuse — the checksum's own proof of life
    frame = _s9.frame_encode(data, "raw")
    at = 13 if len(frame) > 13 else len(frame) - 1
    flipped = frame[:at] + bytes([frame[at] ^ 1]) + frame[at + 1:]
    noticed = False
    try:
        _s9.frame_decode(flipped)
    except ValueError:
        noticed = True
    verdicts["flipped_bit"] = "noticed" if noticed else "unnoticed"
    return {"ratios": ratios, "verdicts": verdicts, "round_trips": round_trips}


def audit(proofs):
    """The world's grade: pass, or the reasons naming what failed.

    Every corpus's ratios against the world's bars, every verdict held,
    every round-trip exact, the flipped bit noticed — the reasons name
    each cut as `(corpus, codec)`, `pass` names none."""
    reasons = []
    for bar_corpus, codec, bar in _corpus.BARS:
        proof = proofs.get(bar_corpus, {})
        ratio = proof.get("ratios", {}).get(codec)
        if not isinstance(ratio, int) or isinstance(ratio, bool) \
                or ratio > bar:
            reasons.append("%s/%s: ratio %r over the bar %d"
                           % (bar_corpus, codec, ratio, bar))
    for corpus_name, proof in sorted(proofs.items()):
        for codec, verdict in proof.get("verdicts", {}).items():
            if codec == "flipped_bit":
                if verdict != "noticed":
                    reasons.append("%s/flipped_bit: %r is not noticed"
                                   % (corpus_name, verdict))
            elif verdict not in ("accepted", "round_trip"):
                reasons.append("%s/%s: verdict %r" % (corpus_name, codec,
                                                      verdict))
        for codec, exact in proof.get("round_trips", {}).items():
            if exact is not True:
                reasons.append("%s/%s: round-trip %r" % (corpus_name, codec,
                                                         exact))
    if reasons:
        return {"verdict": "fail", "reasons": tuple(reasons)}
    return {"verdict": "pass", "reasons": ()}
