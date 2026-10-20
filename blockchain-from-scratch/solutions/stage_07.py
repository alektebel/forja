"""Blockchain From Scratch — stage 7: Proof-of-stake's slots and attestations.

Proof of stake selects block proposers and validators from a staking table,
weighted by their stake.  This stage implements the proposer selection,
attestation creation, and stake-weighted score computation.

Proposer selection:
- Walk the stakes table in pinned order (by peer name).
- For each peer, accumulate their stake weight.
- The slot's draw (an integer from the PRNG) determines which peer
  is selected: the first peer whose cumulative weight exceeds the draw.
- This is a single pass through the table — deterministic, no sorting.

Attestation:
- A witness signs the block ID with their public key.
- The attestation record contains: block_id, slot, signer, and signature.

Stake-weighted score:
- Sum each attestation's weight (the signer's stake) and return the total.
- This is the "honest weight" a node tracks when choosing between forks.

    SLOT_KEYS                     the four slot fields, in order
    SlotError                     the refusal this stage raises
    proposer(slot_num, stakes)    -> peer name
    witness(block_id, slot, priv)  -> attestation record dict
    summed(stake, attestations)   -> total stake-weighted score

DESIGN DECISION — why walk the stakes table in pinned order?
Because real proof-of-stake systems (like Ethereum's) use a deterministic
walk through the validator set.  Sorting would introduce a tie-breaking
rule that is arbitrary.  Walking in the fixed roster order means every
node makes the same choice independently.

DESIGN DECISION — why does the draw use cumulative weight?
Because a weighted random selection means higher-stake validators are
proportionally more likely to be selected.  The cumulative sum creates
intervals where each validator's stake determines their probability.
The draw falls into one interval, and that validator is the proposer.

DESIGN DECISION — why is the attestation a signed record?
Because attestations are cryptographic commitments: a validator signs
the block ID, proving they saw and approved it.  The signature commits
to the block ID, so an attestation for one block cannot be reused on
another (preventing cross-block equivocation).

TODO: implement ``SLOT_KEYS``, ``SlotError``, ``proposer``, ``witness``,
and ``summed`` in this file.  The proposer selection must be a single
deterministic pass; the attestation must include a valid signature.
"""

import ledger
from ledger import LedgerError
import keys


SLOT_KEYS = ("slot_num", "proposer", "cumulative", "total_stake")

_SLOT_ERROR_NAME = "slot"


class SlotError(LedgerError):
    """The refusal this stage raises: something that cannot be a PoS operation.

    Names the offender — the slot number outside range, the stake table
    that sums to zero, the attestation that does not verify — because
    a PoS operation the world cannot validate must say what it was asked for.
    """


def proposer(slot_num, stakes):
    """Select the block proposer for a given slot.

    The slot's draw is computed from the slot number:
    ``draw = slot_num * 7 + 13``.

    Walks the stakes table in order, accumulating each peer's stake.
    Returns the first peer whose cumulative weight exceeds the draw.

    *stakes* is a list of dicts with keys ("peer", "stake").
    *slot_num* is a non-negative integer.

    If the total stake is zero, refuses by name.
    If no cumulative weight exceeds the draw, wraps around to the last peer.
    """
    if not stakes:
        raise SlotError("stakes table is empty, cannot select proposer")
    total = 0
    for s in stakes:
        if not isinstance(s.get("stake"), int) or s["stake"] < 0:
            raise SlotError("stake for peer %r is not a non-negative integer" % s.get("peer"))
        total += s["stake"]
    if total == 0:
        raise SlotError("total stake is zero, cannot select proposer")
    if isinstance(slot_num, bool) or not isinstance(slot_num, int):
        raise SlotError("slot_num %r is not an integer" % (slot_num,))
    if slot_num < 0:
        raise SlotError("slot_num %d is negative" % slot_num)
    draw = slot_num * 7 + 13
    cumulative = 0
    for s in stakes:
        cumulative += s["stake"]
        if cumulative > draw:
            return s["peer"]
    return stakes[-1]["peer"]


def witness(block_id, slot_num, priv):
    """Create an attestation record by signing the block ID.

    Signs ``(block_id, slot_num)`` with the provided private key using the
    world's ``keys.sign()``.  Returns a dict with block_id, slot,
    signer (address from pubkey of priv), and sig (R, s).
    """
    if isinstance(priv, bool) or not isinstance(priv, int):
        raise SlotError("private key %r is not an integer" % (priv,))
    if priv < 1 or priv >= keys.P:
        raise SlotError("private key %d is outside [1, P-2=%d]" % (priv, keys.P - 2))
    if isinstance(slot_num, bool) or not isinstance(slot_num, int):
        raise SlotError("slot_num %r is not an integer" % (slot_num,))
    sign_data = {"block_id": block_id, "slot": slot_num}
    R, s = keys.sign(sign_data, priv)
    pub = keys.pubkey(priv)
    return {
        "block_id": block_id,
        "slot": slot_num,
        "signer": keys.address(pub),
        "sig": (R, s),
    }


def summed(stake, attestations):
    """Compute the total stake-weighted score of attestations.

    *stake* is a dict mapping peer name → stake amount.
    *attestations* is a list of attestation records (dicts with "signer" key).

    Returns the sum of each attestation's signer's stake.
    """
    total = 0
    for attn in attestations:
        signer = attn.get("signer", "")
        for peer_name, stake_amount in stake.items():
            if peer_name == signer:
                total += stake_amount
                break
    return total


if __name__ == "__main__":
    """Demo: select proposer and create attestation."""
    stakes = [{"peer": "alpha", "stake": 50}, {"peer": "beta", "stake": 30},
              {"peer": "gamma", "stake": 20}]
    for slot in range(5):
        prop = proposer(slot, stakes)
        print("Slot %d proposer: %s" % (slot, prop))
    priv = keys.keygen(54321)
    attn = witness("block_001", 0, priv)
    print("Attestation: signer=%s, block=%s" % (attn["signer"], attn["block_id"]))