"""Blockchain From Scratch — stage 5: The mempool and the double-spend the ordering kills.

The mempool is a holding area for transactions that nodes have seen but not
yet included in a block.  This stage implements the mempool's rules:
admit a transaction if its inputs are unspent and its fee is sufficient,
reject a double-spend (two transactions spending the same outpoint), and
rank pending transactions by fee for block packing.

The mempool is a list of admitted transactions.  A transaction is admitted
if:
1. All its inputs reference outpoints that are currently unspent (in the
   mempool or in the UTXO set).
2. No other admitted transaction in the mempool spends the same outpoint.
3. The fee (input_value - output_value) is positive.

Replacement by fee: if an existing transaction in the mempool can be
replaced by a new one that spends the same outpoint(s), the new one must
have a **strictly higher fee** to be admitted.  Equal fee is a tie — refuse.

The rank function orders pending transactions by fee descending, with
tx_id as tiebreaker (lexicographic).  This is the packing order blocks
use: highest fee first.

    POOL_KEYS                     the three mempool fields, in order
    PoolError                     the refusal this stage raises
    admit(pool, tx, utxo, prev_txs)
                                  -> True if admitted, False otherwise
    rank(pool)                    -> list of tx_ids sorted by fee then tx_id
    is_double_spend(pool, tx)     -> bool

DESIGN DECISION — why does the mempool track its own spending to catch
double-spends?
Because the UTXO set alone does not know about pending transactions.
Two transactions in the mempool could both spend the same outpoint.
The mempool must track which outpoints it has admitted to prevent this.

DESIGN DECISION — why does replacement require strictly higher fee?
Because equal fee gives no incentive to replace, and a lower fee is a
regression.  Only strictly higher fee creates a clear economic signal:
the new transaction pays more, so it should be prioritised.

DESIGN DECISION — why is the double-spend determined by ordering?
Because the first transaction to arrive and be admitted "wins".  A
later transaction spending the same outpoint is a double-spend and
is refused.  The ordering is the consensus: what the node saw first
is what matters, not what a central authority says.

TODO: implement ``POOL_KEYS``, ``PoolError``, ``admit``, ``rank``, and
``is_double_spend`` in this file.  The double-spend must be killed by
first arrival.
"""

import ledger
from ledger import LedgerError


POOL_KEYS = ("tx_count", "total_fee", "tx_ids")

_POOL_ERROR_NAME = "pool"


class PoolError(LedgerError):
    """The refusal this stage raises: something that cannot be a mempool operation.

    Names the offender — the transaction that double-spends, the outpoint
    already in the pool, the fee that is not higher enough — because a
    mempool operation the world cannot validate must say what it was asked for.
    """


def _tx_fee(utxo_set, tx):
    """Compute the fee of a transaction: input_value - output_value."""
    total_in = 0
    for inp in tx.get("inputs", ()):
        key = (inp["prev_tx_id"], inp["prev_index"])
        if key in utxo_set:
            total_in += utxo_set[key][1]
    total_out = sum(o.get("amount_cents", 0) for o in tx.get("outputs", ()))
    return total_in - total_out


def _outpoints_in_tx(tx):
    """Return set of outpoints referenced by a transaction."""
    return {(i["prev_tx_id"], i["prev_index"]) for i in tx.get("inputs", ())}


def admit(pool, tx, utxo_set, prev_txs):
    """Try to admit a transaction to the mempool.

    Returns True if the transaction is admitted (added to pool),
    False if it is rejected.

    Checks:
    - All inputs reference outpoints that exist (in pool or utxo_set).
    - No input is already spent in the pool by a different tx.
    - The transaction's fee is positive.
    """
    raise NotImplementedError("stage 5: implement admit()")


def rank(pool):
    """Rank transactions in the pool by fee (descending), then by tx_id (ascending).

    Returns a list of tx_id strings in packing order.
    """
    raise NotImplementedError("stage 5: implement rank()")


def is_double_spend(pool, tx):
    """Check if *tx* is a double-spend of any transaction in *pool*.

    Returns True if any of *tx*'s inputs reference outpoints already
    spent by a transaction already in the pool.
    """
    raise NotImplementedError("stage 5: implement is_double_spend()")


if __name__ == "__main__":
    """Demo: admit transactions and rank them."""
    pool = []
    utxo_set = {("gen0", 0): ("alice", 1000)}
    tx1 = {"tx_id": "tx1", "inputs": [{"prev_tx_id": "gen0", "prev_index": 0}],
           "outputs": [{"address": "bob", "amount_cents": 900}]}
    tx2 = {"tx_id": "tx2", "inputs": [{"prev_tx_id": "gen0", "prev_index": 0}],
           "outputs": [{"address": "charlie", "amount_cents": 800}]}
    print("Admit tx1:", admit(pool, tx1, utxo_set, {}))
    print("Admit tx2 (double-spend):", admit(pool, tx2, utxo_set, {}))
    print("Pool size:", len(pool))
    print("Rank:", rank(pool))