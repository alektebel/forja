"""Blockchain From Scratch — stage 1: The header and the digest that seals it.

Every later stage builds on hash-links: block N references block N-1 by digest,
and the chain is only as strong as the hash function that binds them.  This stage
mechanises the first link — a header record, the ``seal()`` digest, and the
genesis invariant that block 0's previous-hash is the all-zeros constant the
world carries.

A block header carries five fields: height (integer), prev_hash (64-char hex),
tx_root (placeholder Merkle root, set to all-zeros until stage 2), tick
(deterministic time-step), and target (proof-of-work difficulty, integer).
``seal(header)`` hashes the canonical encoding of the header dict and returns
the SHA-256 hexdigest.  The first block (height 0) uses ``ledger.GENESIS_HASH``
as its prev_hash; every later block uses the seal of its parent.

    HEADER_KEYS                     the five header fields, in order
    GENESIS_HASH                    the all-zeros constant (from ledger world)
    BlockError                      the refusal this stage raises
    spawn(prev_digest, tx_ids, tick, target)
                                    -> a header dict with height, prev digest, tx root slot, target, tick
    seal(header)                    -> SHA-256 hexdigest of the header's canonical form
    link(parent_digest, tx_ids, tick, target)
                                    -> a header dict that chains to parent_digest (height auto-increments)

DESIGN DECISION — why is tx_root all-zeros until stage 2?
Because the Merkle tree is a separate mechanism: hashing a list of tx_ids is
not the same as building a binary tree and taking the root.  The all-zeros
placeholder makes it explicit that this stage only seals the header's own
fields; stage 2 plugs in the real tx_root.  A stage that tried to hash the
tx_ids directly here would produce a different digest than the Merkle root,
and the chain would be irreparably wrong.

DESIGN DECISION — why does ``seal`` hash the entire header dict?
Because the digest is the chain-link: every field matters.  If a stage
changed the height but not the digest, the link is broken.  Hashing the
whole canonical dict means any field change is reflected in the seal, and
a verification step can check each field independently of the hash.

DESIGN DECISION — why is height automatic in ``link`` but explicit in
``spawn``?
Because ``spawn`` is the base-case constructor (block 0, or a bare header)
and ``link`` is the chain-step.  ``link`` knows the parent's height so it
can increment; ``spawn`` is used when you want full control over the height
field (e.g. for a genesis block or a test fixture).

TODO: implement ``BlockError``, ``spawn``, ``seal``, and ``link`` in this file:
the header constructor, the seal digest, and the chain-link function.
"""

import ledger
from ledger import LedgerError


HEADER_KEYS = ("height", "prev_hash", "tx_root", "tick", "target")

GENESIS_HASH = ledger.GENESIS_HASH

_BLOCK_ERROR_NAME = "block"


class BlockError(LedgerError):
    """The refusal this stage raises: something that cannot be a header.

    Names the offender — the height below zero, the prev_hash not 64 hex chars,
    the tick not an integer, the target not an integer — because a header the
    world cannot seal must say what it was asked for.
    """


def _check_header_fields(height, prev_hash, tx_root, tick, target):
    """Validate all fields of a block header."""
    if isinstance(height, bool) or not isinstance(height, int):
        raise BlockError("height %r is not an integer" % (height,))
    if height < 0:
        raise BlockError("height %d is below zero" % (height,))
    if not isinstance(prev_hash, str) or len(prev_hash) != 64:
        raise BlockError(
            "prev_hash %r is not a 64-character hex digest" % (prev_hash,))
    if not isinstance(tx_root, str) or len(tx_root) != 64:
        raise BlockError(
            "tx_root %r is not a 64-character hex digest" % (tx_root,))
    if isinstance(tick, bool) or not isinstance(tick, int):
        raise BlockError("tick %r is not an integer" % (tick,))
    if tick < 0:
        raise BlockError("tick %d is negative" % (tick,))
    if isinstance(target, bool) or not isinstance(target, int):
        raise BlockError("target %r is not an integer" % (target,))
    if target < 0:
        raise BlockError("target %d is negative" % (target,))


def spawn(height, prev_hash, tx_root, tick, target):
    """Create a block header record with explicit fields.

    *height* must be >= 0 (block 0 is genesis).
    *prev_hash* is the 64-char hex digest of the parent header (``GENESIS_HASH``
    for the first block).
    *tx_root* is the Merkle root of transactions (all-zeros until stage 2).
    *tick* is the deterministic time-step.
    *target* is the proof-of-work target (difficulty boundary).

    Validates all fields and returns a header dict.  Refuses by name on
    invalid input.
    """
    _check_header_fields(height, prev_hash, tx_root, tick, target)
    return {
        "height": height,
        "prev_hash": prev_hash,
        "tx_root": tx_root,
        "tick": tick,
        "target": target,
    }


def seal(header):
    """Compute the SHA-256 digest (seal) of a header record.

    The seal is ``ledger.digest()`` over the canonical encoding of the
    header dict.  This digest links the header to the chain: block N's seal
    is block N+1's prev_hash.

    A header that is not a dict with the right keys is refused by name.
    """
    if not isinstance(header, dict):
        raise BlockError("header %r is not a dict" % (header,))
    for key in HEADER_KEYS:
        if key not in header:
            raise BlockError("header %r is missing key %r" % (header, key))
    return ledger.digest(header)


def link(parent_digest, tx_ids, tick, target):
    """Chain a new header to a parent by digest.

    Creates a header whose prev_hash is *parent_digest* and whose height is
    parent_height + 1.  The tx_root is set to all-zeros (stage 2 will fill
    it with the Merkle root).  The tick and target are forwarded.

    *parent_digest* must be the seal (64-char hex) of the parent header.
    Returns the new header dict.

    A parent digest that is not a valid 64-char hex string is refused by name.
    """
    if not isinstance(parent_digest, str) or len(parent_digest) != 64:
        raise BlockError(
            "parent_digest %r is not a 64-character hex digest" % (parent_digest,))
    if parent_digest not in link._registry:
        raise BlockError(
            "parent_digest %r is not a known parent header" % (parent_digest,))
    parent_height = link._registry[parent_digest]["height"]
    new_height = parent_height + 1
    new_header = spawn(
        height=new_height,
        prev_hash=parent_digest,
        tx_root="0" * 64,
        tick=tick,
        target=target,
    )
    seal_val = seal(new_header)
    link._registry[seal_val] = new_header
    return new_header


link._registry = {}


if __name__ == "__main__":
    """Demo: build a two-block chain and show the seal."""
    genesis = spawn(0, GENESIS_HASH, "0" * 64, 0, ledger.MAX_TARGET)
    print("Block 0 (genesis) created")
    print("  height: %d, prev_hash: %s" % (genesis["height"], genesis["prev_hash"][:16]))
    seal_0 = seal(genesis)
    print("  seal: %s" % seal_0[:32])

    link._registry[seal_0] = genesis

    block1 = link(seal_0, ["tx1", "tx2"], 1, ledger.MAX_TARGET)
    print("Block 1 created")
    print("  height: %d, prev_hash: %s" % (block1["height"], block1["prev_hash"][:32]))
    seal_1 = seal(block1)
    print("  seal: %s" % seal_1[:32])
    print("\nChain verified: block 1's prev_hash == block 0's seal = %s"
          % (seal_0 == block1["prev_hash"]))