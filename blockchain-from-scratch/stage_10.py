"""Blockchain From Scratch — stage 10: The capstone — convergence.

All five nodes process only the messages the network actually delivered.
They must land on one head — the world's own answer key.  The planted
dishonest fork (from stage 7's fork spec) is lost exactly where the
world's key says it is lost.

This stage ties every previous stage together: headers, Merkle roots,
signatures, UTXOs, mempool, PoW, PoS, and fork choice.  A node that
implements all stages correctly will convergege on the same chain.

The convergence check:
1. Replay the scenario's delivery log: for each delivered message,
   call ``receive()`` on the appropriate node.
2. After all messages are processed, check that all five nodes
   have the same chain head.
3. Verify the head equals the world's answer key.
4. Verify the planted fork is not on any node's chain (unless the
   fork's honest weight was sufficient to win — which it should not be).

The per-node audit:
- Each node's audit log reports what arrived, what was accepted,
  what was refused, and why.
- The stage's own audit function compares each node's state against
  the world's answer key and names discrepancies.

    CONVERGE_KEYS                   the five convergence fields, in order
    ConvergeError                   the refusal this stage raises
    converge(net, scenario)          -> dict with convergence results
    verify_against_key(nodes, key)  -> dict per node: match or discrepancy
    audit_convergence(nodes, key)   -> per-node audit report

DESIGN DECISION — why does convergence depend on every previous stage?
Because a bug in any stage (wrong hash, broken signature, missing
UTXO check, incorrect fork choice) will cause nodes to diverge.
The convergence test is a comprehensive integration test: it does
not test each mechanism in isolation but tests the whole system
working together.

DESIGN DECISION — why compare against the world's answer key?
Because the world's own computation (``honest_answer_key``) is the
ground truth.  A stage that converges to a different chain than
the answer key has a bug, even if all nodes agree.  Agreement
without correctness is a coordinated failure, not convergence.

DESIGN DECISION — why does the planted fork need less honest weight?
Because a fork with enough honest weight could legitimately win
(51% attack scenario).  The planted fork is designed to have less
weight, so its loss demonstrates that the protocol correctly
rejects minority forks.  A majority fork's victory is a security
limitation, not a bug.

TODO: implement ``CONVERGE_KEYS``, ``ConvergeError``, ``converge``,
``verify_against_key``, and ``audit_convergence`` in this file.  Every
node must land on the same head, and that head must match the answer key.
"""

import ledger
from ledger import LedgerError
import keys


CONVERGE_KEYS = ("all_nodes_same", "matches_key", "fork_lost", "node_count", "head")

_CONVERGE_ERROR_NAME = "converge"


class ConvergeError(LedgerError):
    """The refusal this stage raises: something that cannot converge.

    Names the offender — the nodes that disagree on the head, the node
    that disagrees with the answer key, the fork that was not lost —
    because convergence the world cannot validate must say what it was asked for.
    """


def converge(net, scenario_data):
    """Run the full convergence test on all five nodes.

    1. Create five peer nodes (from net.py's roster).
    2. Replay the scenario's delivery log: for each delivered message,
       call ``receive()`` on the receiving node.
    3. After all messages, check that all nodes have the same chain head.
    4. Verify the head equals the world's answer key.
    5. Verify the planted fork is lost.

    Returns a dict with convergence results.
    """
    raise NotImplementedError("stage 10: implement converge()")


def verify_against_key(nodes, answer_key):
    """Verify each node's state against the world's answer key.

    For each node, check:
    - The chain head matches the answer key's expected head.
    - The UTXO set is consistent.
    - The mempool is empty (all valid txs were included in blocks).

    Returns a dict mapping node name → {"match": bool, "reason": str}.
    """
    raise NotImplementedError("stage 10: implement verify_against_key()")


def audit_convergence(nodes, answer_key):
    """Produce a per-node audit report.

    For each node, report:
    - What messages were received.
    - What was accepted and what was refused (and why).
    - Comparison with the answer key.

    Returns a list of audit dicts, one per node.
    """
    raise NotImplementedError("stage 10: implement audit_convergence()")


if __name__ == "__main__":
    """Demo: convergence of five nodes."""
    scenario = net.scenario(42)
    result = converge(net, scenario)
    print("All nodes same head:", result.get("all_nodes_same"))
    print("Matches key:", result.get("matches_key"))
    print("Nodes involved:", result.get("node_count"))