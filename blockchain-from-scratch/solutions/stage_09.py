"""Blockchain From Scratch — stage 9: The network of peers, node by node.

Each node in the network processes messages independently: receiving
transactions (admitting them to its mempool) and receiving blocks
(validating and appending them to its chain).  The network is unreliable:
the delivery log determines which messages reach which nodes.

This stage implements the node's message handling logic.  Each node
maintains its own chain, mempool, and UTXO view, updated only by
the messages it actually receives.

    NODE_KEYS                     the five node fields, in order
    NodeError                     the refusal this stage raises
    receive(node, message)         -> response dict with status and reason
    admit_tx(node, tx)             -> True if admitted, False otherwise
    consider_block(node, block)    -> True if block appended, False otherwise
    audit(node)                    -> log of what arrived, what was refused

DESIGN DECISION — why does each node maintain its own state?
Because the network is unreliable: messages are dropped, delayed,
and some nodes may never see certain blocks.  Each node's state
is its "view" of the network.

DESIGN DECISION — why refuse by name at every step?
Because a node that silently accepts an invalid block or transaction
compromises the entire network.  Naming the offender lets the operator
diagnose the problem.

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
    the transaction that was invalid, the block whose parent was unknown.
    """


def _verify_tx_inputs(node, tx, utxo_set):
    """Verify a transaction's inputs against the node's UTXO view.

    Returns (bool, reason) — True and empty string on success.
    """
    for inp in tx.get("inputs", ()):
        prev_id = inp.get("prev_tx_id")
        prev_idx = inp.get("prev_index")
        if (prev_id, prev_idx) not in utxo_set:
            return False, "outpoint %s not found" % str((prev_id, prev_idx))
    return True, ""


def _verify_tx_signature(node, tx):
    """Verify a transaction's signatures using the keys world.

    Returns (bool, reason) — True and empty string on success.
    """
    for addr, sig_data in tx.get("signatures", {}).items():
        pub = sig_data.get("pub")
        sig = sig_data.get("sig")
        if pub is None or sig is None:
            return False, "missing signature data for %s" % addr
        signing_tx = {k: v for k, v in tx.items() if k not in ("signatures",)}
        if not keys.verify(signing_tx, pub, sig):
            return False, "signature invalid for %s" % addr
    return True, ""


def admit_tx(node, tx):
    """Try to admit a transaction to the node's mempool.

    Verifies inputs against the node's UTXO view and signatures.
    Returns True if admitted, False otherwise.
    """
    utxo_set = node.get("utxo", {})
    valid, reason = _verify_tx_inputs(node, tx, utxo_set)
    if not valid:
        node.setdefault("messages_refused", []).append(("tx", reason))
        return False

    if tx.get("tx_id") in node.get("mempool_ids", set()):
        node.setdefault("messages_refused", []).append(("tx", "transaction already in mempool"))
        return False

    fee = 0
    for inp in tx.get("inputs", ()):
        key = (inp["prev_tx_id"], inp["prev_index"])
        if key in utxo_set:
            fee += utxo_set[key][1]
    for out in tx.get("outputs", ()):
        fee -= out.get("amount_cents", 0)

    if fee <= 0:
        node.setdefault("messages_refused", []).append(("tx", "fee not positive"))
        return False

    node.setdefault("mempool", []).append(tx)
    node.setdefault("mempool_ids", set()).add(tx.get("tx_id"))
    node.setdefault("messages_accepted", []).append(("tx", tx.get("tx_id")))
    return True


def consider_block(node, block):
    """Try to append a block to the node's chain.

    Verifies: prev_hash matches known tip, PoW seal is valid.
    Returns True if the block was appended, False otherwise.
    """
    chain = node.get("chain", [])
    if not chain:
        expected_prev = ledger.GENESIS_HASH
    else:
        expected_prev = chain[-1]["header"]["prev_hash"]
    header = block.get("header", {})
    if header.get("prev_hash") != expected_prev:
        node.setdefault("messages_refused", []).append(
            ("block", "unknown parent: expected %s, got %s" % (expected_prev[:16], header.get("prev_hash", "")[:16])))
        return False

    target = header.get("target", ledger.MAX_TARGET)
    if header.get("nonce") is None:
        node.setdefault("messages_refused", []).append(("block", "missing nonce"))
        return False

    header_with_nonce = dict(header)
    header_with_nonce["nonce"] = header.get("nonce", 0)
    digest_int = int(ledger.digest(header_with_nonce), 16)
    if digest_int > target:
        node.setdefault("messages_refused", []).append(("block", "PoW seal invalid"))
        return False

    node.setdefault("chain", []).append(block)
    node.setdefault("known_blocks", set()).add(header.get("block_hash", ""))
    node.setdefault("messages_accepted", []).append(("block", header.get("block_hash", "")))
    return True


def receive(node, message):
    """Process a message received by the node.

    The message has a "type" key: "tx", "block", or "attn".
    """
    msg_type = message.get("type")
    node.setdefault("messages_received", []).append(
        (message.get("tick", 0), msg_type, message.get("from", "unknown")))

    if msg_type == "tx":
        ok = admit_tx(node, message)
        return {"status": "accepted" if ok else "refused", "reason": "admitted"} if ok else {"status": "refused"}
    elif msg_type == "block":
        ok = consider_block(node, message)
        return {"status": "accepted" if ok else "refused", "reason": "appended"} if ok else {"status": "refused"}
    elif msg_type == "attn":
        return {"status": "received_attn", "block_hash": message.get("block_hash", "")}
    else:
        return {"status": "dropped", "reason": "unknown message type"}


def audit(node):
    """Produce an audit log of the node's activity."""
    return {
        "name": node.get("name", "unknown"),
        "chain_length": len(node.get("chain", [])),
        "mempool_size": len(node.get("mempool", [])),
        "utxo_count": len(node.get("utxo", {})),
        "known_hashes": len(node.get("known_blocks", set())),
        "messages_received": node.get("messages_received", []),
        "messages_accepted": node.get("messages_accepted", []),
        "messages_refused": node.get("messages_refused", []),
    }


if __name__ == "__main__":
    """Demo: create a node and process a block."""
    node = {"name": "test", "chain": [], "utxo": {}, "mempool_ids": set(),
            "messages_received": [], "messages_accepted": [], "messages_refused": []}
    block = {"header": {"prev_hash": ledger.GENESIS_HASH, "height": 1,
                        "tx_root": "0" * 64, "tick": 0, "target": ledger.MAX_TARGET,
                        "nonce": 0},
             "transactions": []}
    ok, reason = consider_block(node, block)
    print("Block result: %s (%s)" % (ok, reason))
    print("Chain length:", audit(node)["chain_length"])