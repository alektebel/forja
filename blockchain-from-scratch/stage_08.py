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
1. For each chain candidate, compute its honest weight (sum of stakes
   from attestations on each block).
2. Select the chain with the highest honest weight.
3. Ties are broken by the lowest block hash (lexicographic comparison
   of the chain's final block hash).

    FORK_KEYS                     the four fork choice fields, in order
    ForkError                     the refusal this stage raises
    head(chain_candidates, view)  -> the chosen chain (list of headers)
    head(view)                    -> pure function: same view = same answer
    honest_weight(chain, attestations)
                                  -> total honest stake weight for a chain

DESIGN DECISION — why use honest weight rather than chain length?
Because a longer chain with no honest attestations is suspect.  The
honest weight measures how many validators have confirmed each block,
making it a more reliable indicator of consensus than mere length.
A 10-block chain with 0 attestations should lose to a 2-block chain
with 100 attestations.

DESIGN DECISION — why break ties by lowest block hash?
Because block hashes are deterministic and provide an arbitrary but
consistent tiebreaker.  Using the lowest hash means both nodes that
have seen the same chains will pick the same one, and it prevents
a "most recent wins" bias.

DESIGN DECISION — why is fork choice a pure function?
Because if the function's output depends on time, random numbers,
or internal state, two nodes with the same view could disagree.
A pure function guarantees that same inputs always produce the same
output, which is essential for consensus.

TODO: implement ``FORK_KEYS``, ``ForkError``, ``head``, and
``honest_weight`` in this file.  The function must be pure: same
chain candidates + same view → same head, every time.
"""

import ledger
from ledger import LedgerError


FORK_KEYS = ("total_weight", "chain_length", "final_hash", "chosen")

_FORK_ERROR_NAME = "fork"


class ForkError(LedgerError):
    """The refusal this stage raises: something that cannot be a fork choice.

    Names the offender — the chain that has no candidates, the view that
    is inconsistent, the fork choice that is not a pure function — because
    a fork choice the world cannot validate must say what it was asked for.
    """


def honest_weight(chain, attestations):
    """Compute the honest stake weight of a chain.

    *chain* is a list of block header dicts (each with a "block_hash" key).
    *attestations* is a list of attestation records (each with a "block_id"
    and "signer" key).

    For each block in the chain, look up attestations for that block and
    sum the signers' stake weights.  Returns the total honest weight.

    An empty chain returns 0.
    """
    raise NotImplementedError("stage 8: implement honest_weight()")


def head(chain_candidates, view):
    """Choose the head chain from candidates based on honest weight.

    *chain_candidates* is a list of chain lists (each chain is a list of
    block header dicts with "block_hash" keys).

    *view* is a dict with keys:
    - "attestations" — list of attestation records.
    - "stakes" — dict mapping peer name → stake amount.

    Returns the chain with the highest honest weight.  Ties broken by
    the lowest final block hash (lexicographic).

    If no candidates, refuses by name.
    """
    raise NotImplementedError("stage 8: implement head()")


def verify_purity(head_fn, view):
    """Verify that a head function is pure: same view → same answer.

    Calls head_fn twice with the same view and checks the results match.
    Returns True if the function is pure, False otherwise.
    """
    raise NotImplementedError("stage 8: implement verify_purity()")


if __name__ == "__main__":
    """Demo: fork choice between two chains."""
    chain_a = [{"block_hash": "aaa", "height": 10}, {"block_hash": "bbb", "height": 11}]
    chain_b = [{"block_hash": "ccc", "height": 5}, {"block_hash": "ddd", "height": 6}]
    view = {"attestations": [{"block_id": "bbb", "signer": "alpha"}],
            "stakes": {"alpha": 50, "beta": 30, "gamma": 20}}
    chosen = head([chain_a, chain_b], view)
    print("Chosen chain final block:", chosen[-1]["block_hash"] if chosen else "none")
    print("Pure:", verify_purity(lambda v: head([chain_a, chain_b], v), view))