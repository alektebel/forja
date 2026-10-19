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

import corpus
import inflate
import lz4ref
import zstdref
import stage_01 as s1
import stage_02 as s2
import stage_03 as s3
import stage_06 as s6
import stage_07 as s7
import stage_08 as s8
import stage_09 as s9

PROOF_KEYS = ("ratios", "verdicts", "round_trips")
AUDIT_KEYS = ("verdict", "reasons")

#: the codecs the proof runs, as the ratios' and verdicts' keys spell them
CODECS = ("rle", "huffman", "lz4", "deflate", "fse", "frame")

#: the codecs whose judge is a reference decoder — the verdict is the
#: reference's acceptance, not the stage's own round-trip
JUDGED = ("lz4", "deflate", "frame")

#: the codecs whose judge is the stage's own decode — the round-trip
#: IS the verdict, recorded as such
SELF_JUDGED = ("rle", "huffman", "fse")

#: the verdict strings: a reference decoder accepts or refuses, a
#: self-judged codec rides its round-trip, and the flipped bit is
#: noticed or it is not
VERDICT_ACCEPTED = "accepted"
VERDICT_REFUSED = "refused"
VERDICT_ROUND_TRIP = "round_trip"
VERDICT_BROKEN = "broken"
VERDICT_NOTICED = "noticed"
VERDICT_UNNOTICED = "unnoticed"


def _per_mille(compressed, original):
    """The ratio in int per-mille; an empty corpus's ratio is 0."""
    if not original:
        return 0
    return compressed * 1000 // original


def _counts(data):
    """The per-byte frequencies fse_encode's surface asks for."""
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    return tuple(counts)


def _self_codec(proof, name, encoded, decoded, data):
    """A codec judged by its own decode: the round-trip IS the verdict."""
    proof["ratios"][name] = _per_mille(len(encoded), len(data))
    exact = decoded == data
    proof["round_trips"][name] = exact
    proof["verdicts"][name] = VERDICT_ROUND_TRIP if exact else VERDICT_BROKEN


def _reference_codec(proof, name, encoded, data, judge):
    """A codec judged by a reference decoder: acceptance is the verdict."""
    proof["ratios"][name] = _per_mille(len(encoded), len(data))
    try:
        decoded = judge(encoded)
    except ValueError:
        proof["verdicts"][name] = VERDICT_REFUSED
        proof["round_trips"][name] = False
        return
    exact = decoded == data
    proof["round_trips"][name] = exact
    proof["verdicts"][name] = VERDICT_ACCEPTED if exact else VERDICT_REFUSED


def _flipped_bit_verdict(data):
    """One flipped bit in a raw frame's content, both readers asked:
    the checksum's refusal is the one case that proves the check."""
    frame = s9.frame_encode(data, "raw")
    if len(frame) > 13:
        # index 13 is the first block's first content byte: the flip
        # lands in the cargo, the checksum's own law fires
        flipped = frame[:13] + bytes([frame[13] ^ 1]) + frame[14:]
    else:
        # an empty corpus's frame has no content: the checksum's own
        # byte takes the flip, and the disagreement is the same one
        flipped = frame[:-1] + bytes([frame[-1] ^ 1])
    noticed = True
    for reader in (s9.frame_decode, zstdref.frame_decode):
        try:
            reader(flipped)
        except ValueError:
            continue
        noticed = False
    return noticed


def prove(corpus_name):
    """Every codec over one corpus: the ratio, the verdict, the round-trip."""
    if corpus_name not in corpus.CORPORA:
        raise s1.EncodeError(
            "prove: the corpus %r is not the world's" % (corpus_name,))
    data = getattr(corpus, corpus_name)
    counts = _counts(data)
    proof = {"ratios": {}, "verdicts": {}, "round_trips": {}}

    # rle — the stage's own decode is the judge
    encoded = s2.rle_encode(data)
    _self_codec(proof, "rle", encoded, s2.rle_decode(encoded), data)

    # huffman — the stage's own decode is the judge
    encoded, lengths = s3.huffman_encode(data)
    decoded = s3.huffman_decode(encoded, lengths, len(data))
    _self_codec(proof, "huffman", encoded, decoded, data)

    # lz4 — lz4ref is the judge
    encoded = s6.lz4_block_encode(data)
    _reference_codec(proof, "lz4", encoded, data, lz4ref.lz4_block_decode)

    # deflate — inflate is the judge
    encoded = s7.deflate(data)
    decoded, _bits = inflate.inflate(encoded)
    proof["ratios"]["deflate"] = _per_mille(len(encoded), len(data))
    exact = decoded == data
    proof["round_trips"]["deflate"] = exact
    proof["verdicts"]["deflate"] = VERDICT_ACCEPTED if exact \
        else VERDICT_REFUSED

    # fse — the stage's own decode is the judge
    encoded, _out_counts = s8.fse_encode(data, counts)
    decoded = s8.fse_decode(encoded, counts, len(data))
    _self_codec(proof, "fse", encoded, decoded, data)

    # frame — compressed mode rides the ratio and the stage's own
    # round-trip; the reference reader judges the RAW mode's frame
    # (the reference does not carry the course's compressed blocks)
    compressed = s9.frame_encode(data, "compressed")
    proof["ratios"]["frame"] = _per_mille(len(compressed), len(data))
    proof["round_trips"]["frame"] = s9.frame_decode(compressed) == data
    raw = s9.frame_encode(data, "raw")
    try:
        accepted = zstdref.frame_decode(raw) == data
    except ValueError:
        accepted = False
    proof["verdicts"]["frame"] = VERDICT_ACCEPTED if accepted \
        else VERDICT_REFUSED

    # the flipped bit: the checksum must notice, or the frame's
    # integrity is a hope and the proof says so
    proof["verdicts"]["flipped_bit"] = VERDICT_NOTICED \
        if _flipped_bit_verdict(data) else VERDICT_UNNOTICED

    return {key: proof[key] for key in PROOF_KEYS}


def audit(proofs):
    """The world's grade: pass, or the reasons naming what failed."""
    reasons = []
    for corpus_name in proofs:
        proof = proofs[corpus_name]
        for bar_corpus, codec, bar in corpus.BARS:
            if bar_corpus != corpus_name:
                continue
            if codec not in proof["ratios"]:
                reasons.append("%s/%s: no ratio was measured" %
                               (corpus_name, codec))
                continue
            ratio = proof["ratios"][codec]
            if ratio > bar:
                reasons.append("%s/%s: ratio %d clears not the bar %d" %
                               (corpus_name, codec, ratio, bar))
        for codec in ("lz4", "deflate", "frame"):
            if proof["verdicts"].get(codec) != VERDICT_ACCEPTED:
                reasons.append("%s/%s: the reference decoder's verdict "
                               "is %r, not acceptance" %
                               (corpus_name, codec,
                                proof["verdicts"].get(codec)))
        for codec in ("rle", "huffman", "fse"):
            if proof["verdicts"].get(codec) != VERDICT_ROUND_TRIP:
                reasons.append("%s/%s: the round-trip is the verdict and "
                               "it is %r" %
                               (corpus_name, codec,
                                proof["verdicts"].get(codec)))
        for codec, exact in proof["round_trips"].items():
            if not exact:
                reasons.append("%s/%s: the round-trip is not exact" %
                               (corpus_name, codec))
        if proof["verdicts"].get("flipped_bit") != VERDICT_NOTICED:
            reasons.append("%s/flipped_bit: the checksum did not notice "
                           "the flipped bit" % (corpus_name,))
    return {"verdict": "pass" if not reasons else "fail",
            "reasons": tuple(reasons)}
