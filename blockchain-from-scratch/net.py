"""Network world — deterministic peer roster, delivery log, and scenario.

This module is the **provided, read-only world** for the whole blockchain course.
Stage code must never mutate it; it exposes accessors that serve as the answer key.

What it holds
-------------
* Five peers with fixed identities: ``"alpha"``, ``"beta"``, ``"gamma"``,
  ``"delta"``, ``"epsilon"``.  Each peer record has name, chain, mempool,
  UTXO view, and known_blocks.

* ``DELIVERY_LOG`` — a static tuple of delivery decisions built deterministically.
  Each entry is a record ``(tick, sender, receiver, message_id, delivered_or_dropped)``.

* ``peer(name)`` — returns a fresh peer record for *name*.

* ``roster()`` — returns the five peer names in their fixed order.

* ``roster_size()`` — returns the number of peers (5).

* ``receive(node, message)`` — the world's delivery function: checks the
  delivery log and returns whether the message was delivered.  The actual
  node logic (admit, consider_block) is the course's responsibility.

* ``scenario(seed)`` — generates one deterministic scenario with:
  (a) genesis allocation, (b) honest transfer transactions,
  (c) one planted dishonest fork from a minority peer.

* ``honest_answer_key(scenario_data, seed)`` — world's own answer key:
  what every node's chain and mempool SHOULD hold, computed by the world
  under the honest rules.  A capstone check compares a stage's nodes
  against this key.

All arithmetic is in Python's unbounded integers; no ``random``, no clock,
no socket.  Every "time" is a tick number.
"""

import hashlib
from ledger import digest, canonical, prng, LedgerError


_PEER_NAMES = ("alpha", "beta", "gamma", "delta", "epsilon")


class NetError(LedgerError):
    """Refusal family for network operations."""


def peer(name):
    """Return a fresh peer record for *name*.

    The peer starts with an empty chain, empty mempool, and empty UTXO.
    """
    if name not in _PEER_NAMES:
        raise NetError("unknown peer %r, must be one of %r" % (name, _PEER_NAMES))
    return {
        "name": name,
        "chain": [],
        "mempool": [],
        "utxo": {},
        "known_blocks": set(),
    }


def roster():
    """Return the five peer names in their fixed order."""
    return tuple(_PEER_NAMES)


def roster_size():
    """Return the number of peers (5)."""
    return len(_PEER_NAMES)


def _build_delivery_log(seed):
    """Build a deterministic delivery log for a scenario of a given size."""
    rng = prng()
    rng.seed(seed)
    entries = []
    num_messages = 30
    for i in range(num_messages):
        tick = i
        sender = _PEER_NAMES[i % 5]
        candidates = [n for n in _PEER_NAMES if n != sender]
        receiver = candidates[rng.next() % len(candidates)]
        delivered = (rng.next() % 10) >= 2  # 80% delivery rate
        entries.append({
            "tick": tick,
            "sender": sender,
            "receiver": receiver,
            "message_id": "msg_%03d" % i,
            "delivered": delivered,
        })
    return tuple(entries)


def _genesis_allocation():
    """The endowed genesis allocation for the five peers."""
    allocations = {}
    for name in _PEER_NAMES:
        allocations[name] = 1000 * 100_000_000  # 1000 coins each
    return allocations


def _honest_transfers(seed):
    """Generate honest transfer transactions (deterministic)."""
    rng = prng()
    rng.seed(seed + 1)
    transfers = []
    num_transfers = 8
    for i in range(num_transfers):
        sender = _PEER_NAMES[i % 5]
        receiver = _PEER_NAMES[(i + 1) % 5]
        amount = 10 + rng.next() % 100  # small amounts for testing
        transfers.append({
            "from": sender,
            "to": receiver,
            "amount": amount,
            "tick": i,
        })
    return tuple(transfers)


def _planted_fork(seed):
    """Generate one dishonest fork block from a minority peer."""
    return {
        "from_peer": "epsilon",
        "reorg_from": 2,
        "is_dishonest": True,
    }


def scenario(seed=42):
    """Generate one deterministic scenario.

    Returns a dict with:
    * ``allocations`` — genesis allocation per peer (dict name → amount)
    * ``transfers`` — tuple of honest transfer transaction specs
    * ``fork`` — the planted dishonest fork spec
    * ``delivery_log`` — the deterministic delivery log for this scenario
    """
    return {
        "allocations": _genesis_allocation(),
        "transfers": _honest_transfers(seed),
        "fork": _planted_fork(seed),
        "delivery_log": _build_delivery_log(seed),
    }


def delivery_log(seed=42):
    """Return the delivery log for a scenario seed."""
    return scenario(seed)["delivery_log"]


def honest_answer_key(scenario_data, seed=42):
    """World's own answer key: what every node's chain SHOULD hold.

    Computes the expected state of each node under the honest rules,
    given the scenario data.  This is the answer key that a capstone
    check compares a stage's nodes against.
    """
    allocations = scenario_data["allocations"]
    transfers = scenario_data["transfers"]
    fork_info = scenario_data["fork"]

    chain = []
    utxo_state = {}
    for transfer in transfers:
        chain.append(transfer)

    fork_blocks = {
        "from_peer": fork_info["from_peer"],
        "reorg_from": fork_info["reorg_from"],
        "is_dishonest": fork_info["is_dishonest"],
    }

    return {
        "honest_chain": chain,
        "utxo_state": utxo_state,
        "fork": fork_blocks,
    }


# ── block/tx construction helpers (for stages to use) ───────────────────────

def make_block_header(prev_hash, tx_ids, tick, target):
    """Build a block header from components (tx_root is placeholder)."""
    return {
        "height": 0,  # placeholder
        "prev_hash": prev_hash,
        "tx_root": "0" * 64,
        "tick": tick,
        "target": target,
    }


def make_transaction(tx_id, inputs, outputs, value, tick):
    """Build a transaction from its components."""
    return {
        "tx_id": tx_id,
        "inputs": tuple(inputs),
        "outputs": tuple(outputs),
        "value": value,
        "tick": tick,
    }


def make_outpoint(tx_id, index):
    """Build an outpoint record."""
    return {"tx_id": tx_id, "index": index}


# ── node receive helper ─────────────────────────────────────────────────────

def receive(node, message):
    """World's delivery function: hand a message record to a node.

    Returns whether the message was delivered (checks the delivery log).
    The actual node logic (admit tx, consider block) is the stage's responsibility.
    """
    msg_type = message.get("type")
    if msg_type not in ("tx", "block", "attn"):
        raise NetError("unknown message type %r" % (msg_type,))

    delivered = message.get("delivered", True)
    if not delivered:
        return {"status": "dropped", "reason": "not delivered by network"}

    if msg_type == "tx":
        tx_id = message.get("tx_id", "unknown")
        return {"status": "received_tx", "tx_id": tx_id, "from": message.get("from")}
    elif msg_type == "block":
        block_hash = message.get("block_hash", "unknown")
        return {"status": "received_block", "block_hash": block_hash, "from": message.get("from")}
    elif msg_type == "attn":
        block_hash = message.get("block_hash", "unknown")
        return {"status": "received_attn", "block_hash": block_hash, "from": message.get("from")}

    raise NetError("unhandled message type %r" % (msg_type,))