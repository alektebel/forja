"""Blockchain From Scratch — stage 8: Fork choice from any node's own view.

A node with multiple chain candidates must choose which one to follow.
This stage implements the fork choice rule: the chain with the most honest
stake-weighted blocks wins.  Ties are broken by the lowest block hash.

The fork choice rule is a **pure function** of the node's view:
given the same set of chain candidates and stake weights, it always
returns the same head.  There is no randomness, no clock, no state
that changes between calls.

The node's view consists of:
- A set of known block hashes (from all chains the node has seen).
- For each chain, the list of block headers with their stake weights.
- The honest weight for each chain (sum of attested block weights).

The fork choice function:
1. For each chain candidate, compute its honest weight.
2. Select the chain with the highest honest weight.
3. Ties are broken by the lowest block hash (lexicographic comparison).

    FORK_KEYS                     the four fork choice fields, in order
    ForkError                     the refusal this stage raises
    head(chain_candidates, view)  -> the chosen chain (list of headers)
    honest_weight(chain, attestations)
                                  -> total honest stake weight for a chain

DESIGN DECISION — why use honest weight rather than chain length?
Because a longer chain with no honest attestations is suspect.  The
honest weight measures how many validators have confirmed each block,
making it a more reliable indicator of consensus than mere length.

DESIGN DECISION — why break ties by lowest block hash?
Because block hashes are deterministic and provide an arbitrary but
consistent tiebreaker.  Using the lowest hash prevents "most recent wins" bias.

DESIGN DECISION — why is fork choice a pure function?
Because if the function's output depends on time, random numbers,
or internal state, two nodes with the same view could disagree.

TODO: implement ``FORK_KEYS``, ``ForkError``, ``head``, and
``honest_weight`` in this file.  The function must be pure: same
chain candidates + same view → same head, every time.
"""

import ledger
from ledger import LedgerError


FORK_KEYS = ("total_weight", "chain_length", "final_hash", "chosen")

_FORK_ERROR_NAME = "fork"


class ForkError(LedgerError):
    """The refusal this stage raises: something that cannot be a fork choice."""


def honest_weight(chain, attestations):
    """Compute the honest stake weight of a chain."""
    if not chain:
        return 0
    block_hashes = {b.get("block_hash") for b in chain if "block_hash" in b}
    if not block_hashes:
        return 0
    total_weight = 0
    for attn in attestations:
        if attn.get("block_id") in block_hashes:
            total_weight += 1
    return total_weight


def head(chain_candidates, view):
    """Choose the head chain from candidates based on honest weight."""
    if not chain_candidates:
        raise ForkError("no chain candidates provided")
    attestations = view.get("attestations", [])
    best = None
    best_weight = -1
    best_final_hash = None
    for chain in chain_candidates:
        w = honest_weight(chain, attestations)
        final_hash = chain[-1].get("block_hash", "") if chain else ""
        if w > best_weight or (w == best_weight and (best_final_hash is None or final_hash < best_final_hash)):
            best = chain
            best_weight = w
            best_final_hash = final_hash
    return best


def verify_purity(head_fn, view):
    """Verify that head_fn is pure: same view → same answer."""
    result1 = head_fn(view)
    result2 = head_fn(view)
    return result1 == result2


if __name__ == "__main__":
    """Demo: fork choice between two chains."""
    chain_a = [{"block_hash": "aaa", "height": 10}, {"block_hash": "bbb", "height": 11}]
    chain_b = [{"block_hash": "ccc", "height": 5}, {"block_hash": "ddd", "height": 6}]
    view = {"attestations": [{"block_id": "bbb", "signer": "alpha"}],
            "stakes": {"alpha": 50, "beta": 30, "gamma": 20}}
    chosen = head([chain_a, chain_b], view)
    print("Chosen chain final block:", chosen[-1]["block_hash"] if chosen else "none")
    print("Pure:", verify_purity(lambda v: head([chain_a, chain_b], v), view))