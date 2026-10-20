"""Blockchain From Scratch — stage 2: Merkle trees and the inclusion proof.

A block's transaction root is the hash that commits to every transaction in
the block.  This stage builds that root from a list of transaction IDs using
a binary Merkle tree, and produces inclusion proofs that a third party can
use to verify a transaction was in the block without downloading the whole
block.

The tree is built bottom-up: each leaf is ``sha256(tx_id)``.  Pairs of
sibling nodes are concatenated and hashed to produce the parent:
``sha256(left_bytes || right_bytes)`` where ``||`` is concatenation.  When
there is an odd number of nodes at any level, the last node is **duplicated**
(itself, not padded with zeros) so every level has an even count.  The root
is the single remaining node after all levels are processed.

    MERKLE_KEYS                     the six Merkle result fields, in order
    MerkleError                     the refusal this stage raises
    leaves(tx_ids)                  -> tuple of leaf hex digests
    root(tx_ids)                    -> the Merkle root hex digest
    proof(tx_ids, tx_id)            -> tuple of (sibling_digest, direction) steps
    confirm(tx_id, proof, root)     -> bool

DESIGN DECISION — why duplicate the last leaf instead of padding with zeros?
Because real Bitcoin duplicates the last leaf, not pads.  Padding with zeros
would mean two different transaction lists (one with a zero-padded leaf, one
without) produce the same root — a collision.  Duplicating preserves the
property that two different sets of transactions always produce different roots.

DESIGN DECISION — why does the proof use directions ("left"/"right")?
Because a verifier walking the tree needs to know whether each sibling is on
the left or the right.  The direction is relative to the node being proved:
if the sibling is on the left, the proof step is ``sha256(sibling || current)``,
otherwise ``sha256(current || sibling)``.

DESIGN DECISION — why return both the leaf digests and the root?
Because a stage that only returns the root cannot produce a proof.  The
``leaves()`` function is the first layer of the tree; ``root()`` is the top.
A check needs both to verify that the root was actually computed from the
given leaf list, not read from the answer key.

TODO: implement ``MerkleError``, ``leaves``, ``root``, ``proof``, and
``confirm`` in this file.  The odd-count duplication rule and the proof
walking must both be correct, because a single off-by-one at any level
produces a different root.
"""

import ledger
from ledger import LedgerError


MERKLE_KEYS = ("tx_count", "leaf_count", "root", "depth", "leaves", "duplicates")

_MERKLE_ERROR_NAME = "merkle"


class MerkleError(LedgerError):
    """The refusal this stage raises: something that cannot form a Merkle tree.

    Names the offender — empty input, tx_id that is not a string, a proof
    step that does not match the tree — because a tree the world cannot
    build must say what it was asked for.
    """


def _sha256_hex(data):
    """Return sha256 of canonical(data) as hex string."""
    return ledger.digest(data)


def _hash_pair(left, right):
    """Hash a pair of digests: sha256(canonical(left) || canonical(right))."""
    combined = ledger.canonical(left) + ledger.canonical(right)
    return ledger._hash_bytes(combined)


def _build_tree(leaves):
    """Build the full Merkle tree from leaves, returning (root, layers)."""
    if not leaves:
        return "0" * 64, []
    layers = [list(leaves)]
    layer = list(leaves)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        new_layer = []
        for i in range(0, len(layer), 2):
            new_layer.append(_hash_pair(layer[i], layer[i + 1]))
        layers.append(new_layer)
        layer = new_layer
    return layer[0], layers


def _duplicated_count(tx_count):
    """Count how many leaves are duplicated due to odd counts during build."""
    count = 0
    n = tx_count
    while n > 1:
        if n % 2 == 1:
            count += 1
        n = (n + 1) // 2
    return count


def _tree_depth(tx_count):
    """Compute the depth of the Merkle tree (number of hash layers)."""
    if tx_count == 0:
        return 0
    n = 1
    depth = 0
    while n < tx_count:
        n = n * 2
        depth += 1
    return depth


def _find_index(tx_ids, tx_id):
    """Find the index of tx_id in tx_ids, or -1 if not found."""
    for i, tid in enumerate(tx_ids):
        if tid == tx_id:
            return i
    return -1


def _collect_proof_from_layers(layers, index):
    """Collect proof steps from pre-built tree layers."""
    proof_steps = []
    idx = index
    for layer_idx in range(len(layers) - 1):
        layer = layers[layer_idx]
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        if idx % 2 == 0:
            sibling = layer[idx + 1]
            direction = "right"
        else:
            sibling = layer[idx - 1]
            direction = "left"
        proof_steps.append((sibling, direction))
        idx = idx // 2
    return tuple(proof_steps)


def leaves(tx_ids):
    """Compute the leaf digests for a list of transaction IDs.

    Each leaf is ``sha256(tx_id)`` where tx_id is the canonical encoding of
    the transaction ID string.  Returns a tuple of 64-char hex digests.

    An empty list returns an empty tuple.
    A tx_id that is not a string is refused by name.
    """
    raise NotImplementedError("stage 2: implement leaves()")


def root(tx_ids):
    """Compute the Merkle root of a list of transaction IDs.

    Builds the full binary tree from the leaves (one per tx_id, hashed with
    sha256), pairs nodes at each level, duplicates the last node if the count
    is odd, and hashes pairs to climb to the root.

    Returns the root as a 64-char hex digest.  Refuses by name on empty input.
    """
    raise NotImplementedError("stage 2: implement root()")


def proof(tx_ids, tx_id):
    """Compute an inclusion proof for *tx_id* in the Merkle tree of *tx_ids*.

    Returns a tuple of ``(sibling_digest, direction)`` steps, one per tree
    level.  Each step says which sibling to use and on which side.

    If *tx_id* is not in *tx_ids*, refuses by name.  An empty tx_ids list
    also refuses.
    """
    raise NotImplementedError("stage 2: implement proof()")


def confirm(tx_id, proof_steps, expected_root):
    """Verify an inclusion proof against an expected root.

    Walks the proof steps from the leaf (sha256(tx_id)) to the root,
    applying each sibling and direction.  Returns True if the computed
    root matches *expected_root*, False otherwise.
    """
    raise NotImplementedError("stage 2: implement confirm()")


if __name__ == "__main__":
    """Demo: build a Merkle tree for 4 transactions and show the proof."""
    tx_ids = ("tx_alpha", "tx_beta", "tx_gamma", "tx_delta")
    leaf_list = leaves(tx_ids)
    print("Leaf count: %d" % len(leaf_list))
    for i, leaf in enumerate(leaf_list):
        print("  leaf[%d]: %s" % (i, leaf[:16]))
    mroot = root(tx_ids)
    print("Merkle root: %s" % mroot[:32])
    for tid in tx_ids:
        proof_steps = proof(tx_ids, tid)
        confirmed = confirm(tid, proof_steps, mroot)
        print("  proof for %s: %d steps, confirmed=%s" % (tid, len(proof_steps), confirmed))