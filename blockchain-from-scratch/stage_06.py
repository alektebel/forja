"""Blockchain From Scratch — stage 6: Proof-of-work's target and difficulty adjustment.

Proof of work requires a block header's seal to be numerically less than or
equal to the target.  This stage implements the PoW machinery: checking if a
digest meets the target, searching for a valid nonce, and adjusting the target
based on how long it took to mine the last interval.

The target comparison:
- Convert the 64-char hex digest to a big-endian integer.
- The digest **meets** the target iff ``int(digest, 16) <= target``.
- This is a strict "less than or equal" comparison, pinned once in the docstring
  and used by every later stage.

The miner's search:
- Start from a pinned starting nonce (0 or a given value) and increment by 1.
- For each nonce, set the header's nonce field, compute the seal, and check
  if it meets the target.
- Stop when the digest meets the target or the budget (max attempts) is reached.
- If the budget runs out, refuse by name (no infinite loop).

Difficulty adjustment:
- After every ``RETARGET_INTERVAL`` (6) blocks, adjust the target.
- The new target is proportional to the actual time taken vs expected time.
- ``retarget(prev_target, took_ticks)`` computes the new target clamped
  to a quarter-to-quadruple band: ``prev_target // 4 <= new_target <= prev_target * 4``.
- All arithmetic is integer (floor division for the adjustment).

    POW_KEYS                    the four PoW fields, in order
    PowError                    the refusal this stage raises
    meets(digest_int, target)   -> bool
    mine(header, target, budget, start_nonce=0)
                                -> (nonce, new_header) or refusal
    retarget(prev_target, took_ticks)
                                -> adjusted target

DESIGN DECISION — why is the nonce searched linearly?
Because real Bitcoin uses a 32-bit nonce field and searches 2^32 values.
In this teaching version, we keep the search simple and bounded: start
from 0 (or a given value), increment by 1, stop at budget.  A stage
that tries to use ``random`` or a more complex search is introducing
non-determinism.

DESIGN DECISION — why clamp the retarget to quarter-to-quadruple?
Because a 4x change in a single interval is the maximum speedup or
slowdown the protocol allows.  Without the clamp, a short interval
could make the target impossibly easy (instant blocks) and a long
interval could make it impossibly hard (years between blocks).  The
clamp ensures the difficulty adjusts gradually.

DESIGN DECISION — why does ``mine`` return both nonce and header?
Because the nonce is part of the header (the ``nonce`` field is set
to the found value).  The returned header is the complete, valid block
header with the correct nonce and seal.

TODO: implement ``POW_KEYS``, ``PowError``, ``meets``, ``mine``, and
``retarget`` in this file.  The ``meets`` comparison must be ``<=`` not
``<``, and ``mine`` must never loop infinitely.
"""

import ledger
from ledger import LedgerError


POW_KEYS = ("digest_int", "target", "meets", "nonce")

_POW_ERROR_NAME = "pow"


class PowError(LedgerError):
    """The refusal this stage raises: something that cannot be a PoW operation.

    Names the offender — the digest that does not meet the target, the budget
    exhausted, the retarget outside the band — because a PoW operation the
    world cannot validate must say what it was asked for.
    """


def meets(digest_int, target):
    """Check if a digest integer meets the proof-of-work target.

    Returns True iff ``digest_int <= target``.  This is a **less than or
    equal** comparison: a digest equal to the target is valid.

    Both arguments must be non-negative integers.  A boolean or negative
    value is refused by name.
    """
    raise NotImplementedError("stage 6: implement meets()")


def _hash_header(header_dict):
    """Hash a header dict's canonical encoding and return (digest_int, digest_hex)."""
    hex_str = ledger.digest(header_dict)
    return int(hex_str, 16), hex_str


def mine(header, target, budget, start_nonce=0):
    """Search for a nonce that makes the header meet the target.

    Starting from *start_nonce*, increments the header's nonce field and
    checks each candidate against *target*.  Stops when:
    - A valid nonce is found (meets the target).
    - The budget (max attempts) is exhausted.

    Returns ``(nonce, modified_header)`` if found.  Refuses by name if
    the budget is exhausted without finding a valid nonce.

    The header's nonce field is updated to the found value.  A copy is
    returned so the original header is not mutated.
    """
    raise NotImplementedError("stage 6: implement mine()")


def retarget(prev_target, took_ticks):
    """Adjust the target based on the time taken for the last interval.

    The expected time for one interval is ``RETARGET_INTERVAL * TICKS_PER_BLOCK``.
    The new target is:

        new_target = prev_target * took_ticks // expected_ticks

    Clamped to ``[prev_target // 4, prev_target * 4]`` to prevent extreme
    adjustments.  All arithmetic is integer (floor division).

    *prev_target* must be a positive integer.
    *took_ticks* must be a non-negative integer.

    Refuses by name on invalid input.
    """
    raise NotImplementedError("stage 6: implement retarget()")


if __name__ == "__main__":
    """Demo: PoW mining with an easy target."""
    header = {"height": 0, "prev_hash": "0" * 64, "tx_root": "0" * 64,
              "tick": 0, "target": ledger.MAX_TARGET}
    nonce, new_header = mine(header, ledger.MAX_TARGET, 1000)
    print("Mined block with nonce: %d" % nonce)
    print("meets():", meets(int(ledger.digest(new_header), 16), ledger.MAX_TARGET))
    old_target = 2 ** 250
    new_target = retarget(old_target, 12)  # took 12 ticks for 6 blocks (expected: 6)
    print("Retarget: %d -> %d (clamped to quarter-quadruple)" % (old_target, new_target))