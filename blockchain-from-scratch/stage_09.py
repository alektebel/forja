"""Blockchain From Scratch — stage 9: The network of peers, node by node.

Each node in the network processes messages independently: receiving
transactions (admitting them to its mempool) and receiving blocks
(validating and appending them to its chain).  The network is unreliable:
the delivery log determines which messages reach which nodes.

This stage implements the node's message handling logic.  Each node
maintains its own chain, mempool, and UTXO view, updated only by
the messages it actually receives.

When a node receives a transaction:
1. Verify the transaction's inputs against its UTXO view.
2. Verify signatures (from stage 3).
3. Admit to its mempool if valid (from stage 5 rules).
4. Refuse by name if invalid: bad signature, missing outpoint,
   double-spend, or insufficient fee.

When a node receives a block:
1. Verify the block's prev_hash matches the node's known chain tip.
2. Verify all transactions in the block (from the node's state
   before the block's inclusion).
3. Verify the PoW seal meets the block's target (from stage 6).
4. Append the block to the chain.
5. Remove spent transactions from the mempool.
6. Refuse by name if invalid: unknown parent, bad PoW, invalid tx,
   or the block contains a double-spend.

When a node receives an attestation:
1. Verify the signature commits to the block ID.
2. Record the attestation for fork choice (from stage 7, 8).

    NODE_KEYS                     the five node fields, in order
    NodeError                     the refusal this stage raises
    receive(node, message)         -> response dict with status and reason
    admit_tx(node, tx)             -> True if admitted, False otherwise
    consider_block(node, block)    -> True if block appended, False otherwise
    audit(node)                    -> log of what arrived, what was refused

DESIGN DECISION — why does each node maintain its own state?
Because the network is unreliable: messages are dropped, delayed,
and some nodes may never see certain blocks.  Each node's state
is its "view" of the network.  The fork choice (stage 8) reconciles
differences between views.

DESIGN DECISION — why refuse by name at every step?
Because a node that silently accepts an invalid block or transaction
compromises the entire network.  Naming the offender (bad signature,
missing outpoint, unknown parent) lets the node's operator diagnose
the problem and the check verify that the refusal was correct.

DESIGN DECISION — why is the audit a separate function?
Because the audit produces a report of every message the node
processed, what it accepted, and what it refused and why.  This
is how the capstone (stage 10) compares each node's state against
the world's answer key.

TODO: implement ``NODE_KEYS``, ``NodeError``, ``receive``, ``admit_tx``,
``consider_block``, and ``audit`` in this file.
"""

import ledger
from ledger import LedgerError
import keys


NODE_KEYS = ("name", "chain_length", "mempool_size", "utxo_count", "known_hashes")

_NODE_ERROR_NAME = "node"


class NodeError(LedgerError):
    """The refusal this stage raises: something that cannot be a node operation.

    Names the offender — the message that was dropped by the network,
    the transaction that was invalid, the block whose parent was unknown —
    because a node operation the world cannot validate must say what it was asked for.
    """


def _verify_tx_inputs(node, tx, utxo_set):
    """Verify a transaction's inputs against the node's UTXO view.

    Returns (bool, reason) — True and empty string on success,
    False and error message on failure.
    """
    raise NotImplementedError("stage 9: internal _verify_tx_inputs() stub")


def _verify_tx_signature(node, tx):
    """Verify a transaction's signatures using the keys world."""
    raise NotImplementedError("stage 9: internal _verify_tx_signature() stub")


def admit_tx(node, tx):
    """Try to admit a transaction to the node's mempool.

    Verifies inputs against the node's UTXO view and signatures.
    Refuses by name if invalid.  Returns True if admitted, False otherwise.
    """
    raise NotImplementedError("stage 9: implement admit_tx()")


def consider_block(node, block):
    """Try to append a block to the node's chain.

    Verifies: prev_hash matches known tip, all transactions are valid,
    PoW seal is valid.  Refuses by name if invalid.
    Returns True if the block was appended, False otherwise.
    """
    raise NotImplementedError("stage 9: implement consider_block()")


def receive(node, message):
    """Process a message received by the node.

    The message has a "type" key: "tx", "block", or "attn".
    Dispatches to the appropriate handler and records the result.

    Returns a dict with "status" and "reason" fields.
    """
    raise NotImplementedError("stage 9: implement receive()")


def audit(node):
    """Produce an audit log of the node's activity.

    Returns a dict with:
    - "messages_received" — list of (tick, type, source) records.
    - "messages_accepted" — list of accepted messages.
    - "messages_refused" — list of (reason, type) refusal records.
    """
    raise NotImplementedError("stage 9: implement audit()")


if __name__ == "__main__":
    """Demo: create a node and process a block."""
    node = {"name": "test", "chain": [], "utxo": {}, "mempool_ids": set(),
            "messages_received": [], "messages_accepted": [], "messages_refused": []}
    block = {"header": {"prev_hash": ledger.GENESIS_HASH, "height": 1,
                        "tx_root": "0" * 64, "tick": 0, "target": ledger.MAX_TARGET},
             "transactions": []}
    ok, reason = consider_block(node, block)
    print("Block result: %s (%s)" % (ok, reason))
    print("Chain length:", audit(node)["chain_length"])