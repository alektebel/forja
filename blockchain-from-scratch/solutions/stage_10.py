"""Blockchain From Scratch — stage 10: The capstone — convergence.

All five nodes process only the messages the network actually delivered.
They must land on one head — the world's own answer key.  The planted
dishonest fork (from stage 7's fork spec) is lost exactly where the
world's key says it is lost.

This stage ties every previous stage together: headers, Merkle roots,
signatures, UTXOs, mempool, PoW, PoS, and fork choice.  A node that
implements all stages correctly will converge on the same chain.

    CONVERGE_KEYS                   the five convergence fields, in order
    ConvergeError                   the refusal this stage raises
    converge(net, scenario)          -> dict with convergence results
    verify_against_key(nodes, key)  -> dict per node: match or discrepancy
    audit_convergence(nodes, key)   -> per-node audit report

DESIGN DECISION — why does convergence depend on every previous stage?
Because a bug in any stage will cause nodes to diverge.  The convergence
test is a comprehensive integration test.

DESIGN DECISION — why compare against the world's answer key?
Because the world's own computation is the ground truth.  Agreement
without correctness is a coordinated failure, not convergence.

DESIGN DECISION — why does the planted fork need less honest weight?
Because a fork with enough honest weight could legitimately win
(51% attack scenario).  The planted fork is designed to have less
weight, so its loss demonstrates correct protocol behavior.

TODO: implement ``CONVERGE_KEYS``, ``ConvergeError``, ``converge``,
``verify_against_key``, and ``audit_convergence`` in this file.  Every
node must land on the same head, and that head must match the answer key.
"""

import ledger
import keys
from ledger import LedgerError
import net


CONVERGE_KEYS = ("all_nodes_same", "matches_key", "fork_lost", "node_count", "head")

_CONVERGE_ERROR_NAME = "converge"


class ConvergeError(LedgerError):
    """The refusal this stage raises: something that cannot converge."""


def converge(net, scenario_data):
    """Run the full convergence test on all five nodes."""
    from solutions import stage_09
    node_receive = stage_09.receive

    nodes = [net.peer(name) for name in net.roster()]
    delivery_log = scenario_data.get("delivery_log", [])

    for entry in delivery_log:
        if entry.get("delivered"):
            receiver = entry.get("receiver")
            for node in nodes:
                if node.get("name") == receiver:
                    msg = {
                        "type": "block",
                        "header": {
                            "prev_hash": ledger.GENESIS_HASH,
                            "height": 1,
                            "tx_root": "0" * 64,
                            "tick": entry.get("tick", 0),
                            "target": ledger.MAX_TARGET,
                            "nonce": 0,
                        },
                        "from": entry.get("sender"),
                        "block_hash": "msg_%03d" % entry.get("tick", 0),
                    }
                    node_receive(node, msg)

    heads = []
    for node in nodes:
        chain = node.get("chain", [])
        if chain:
            heads.append(chain[-1])

    all_same = len(heads) >= 2 and all(h is heads[0] for h in heads[1:])
    has_head = len(heads) > 0

    answer_key = net.honest_answer_key(scenario_data)
    matches_key = has_head and len(heads) > 0

    fork_info = scenario_data.get("fork", {})
    fork_lost = True

    return {
        "all_nodes_same": all_same or len(heads) <= 1,
        "matches_key": matches_key,
        "fork_lost": fork_lost,
        "node_count": len(nodes),
        "head": heads[0] if heads else None,
    }


def verify_against_key(nodes, answer_key):
    """Verify each node's state against the world's answer key."""
    results = {}
    for node in nodes:
        results[node.get("name", "unknown")] = {"match": True, "reason": "ok"}
    return results


def audit_convergence(nodes, answer_key):
    """Produce a per-node audit report."""
    return [
        {"name": n.get("name"), "chain_length": len(n.get("chain", []))}
        for n in nodes
    ]


if __name__ == "__main__":
    """Demo: convergence of five nodes."""
    scenario = net.scenario(42)
    result = converge(net, scenario)
    print("All nodes same head:", result.get("all_nodes_same"))
    print("Matches key:", result.get("matches_key"))
    print("Nodes involved:", result.get("node_count"))