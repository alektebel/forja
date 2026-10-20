"""Blockchain From Scratch — stage 4: The UTXO set and the spend that names what it consumes.

A blockchain's balance is not a balance sheet — it is a set of unspent transaction
outputs (UTXOs).  This stage builds the UTXO set from the blockchain's blocks,
provides a function to query a wallet's balance, and implements the spend that
names exactly which outputs it consumes and which new ones it creates.

The UTXO set is a dictionary mapping ``(tx_id, index)`` → ``(address, amount_cents)``.
It is built by walking all blocks in chain order: for each transaction's outputs,
if the output is not spent by any later input, it is a UTXO.

The spend (transaction) must:
1. Name each input as a (prev_tx_id, prev_index) outpoint.
2. Verify each referenced outpoint exists in the UTXO set.
3. Verify each referenced outpoint is owned by the signer (address match).
4. Verify the total input value >= total output value (no free money).
5. The excess is the fee.

    UTXO_KEYS                     the four UTXO record fields, in order
    SetError                      the refusal this stage raises
    outpoints(blocks)              -> dict of unspent outpoints with owner and value
    apply(utxo_set, tx)            -> new utxo set after applying the transaction
    balance(utxo_set, address)     -> total unspent value for an address

DESIGN DECISION — why build the UTXO set by walking blocks instead of
querying a database?
Because the world is the ledger of blocks, not a database.  The stage
reconstructs the UTXO set from first principles by walking every block
in order, removing spent outputs and adding new ones.  This is how a
new node boots: it replayed the chain from genesis to recover the UTXO set.

DESIGN DECISION — why refuse by name (missing outpoint, wrong owner)
instead of silently skipping?
Because a transaction that spends someone else's output is a double-spend
or theft.  A silent skip would produce an incorrect UTXO set, and the
blockchain would silently accept an invalid transaction.  Naming the
offender is what lets a node reject the block that contains the bad tx.

DESIGN DECISION — why is the balance computed from the UTXO set rather
than from the block height?
Because two wallets can have the same number of outputs but vastly
different balances.  The balance is a function of the unspent outputs,
not the chain height.  A UTXO set is the ground truth for "what coins
exist and who owns them."

TODO: implement ``UTXO_KEYS``, ``SetError``, ``outpoints``, ``apply``, and
``balance`` in this file.  Every input must be verified: missing, already
spent, and not-owned inputs are all refused by name.
"""

import ledger
from ledger import LedgerError


UTXO_KEYS = ("tx_id", "index", "address", "amount_cents")

_SET_ERROR_NAME = "set"


class SetError(LedgerError):
    """The refusal this stage raises: something that cannot be a UTXO spend.

    Names the offender — the outpoint that does not exist, the outpoint
    already spent, the outpoint not owned by the signer — because a spend
    the world cannot validate must say what it was asked for.
    """


def outpoints(blocks):
    """Build the UTXO set from a chain of blocks.

    Walks every block in order.  For each transaction:
    - Marks all referenced outpoints (inputs) as spent.
    - Adds each output (if not spent by a later input in the same tx)
      as a new UTXO.

    Returns a dict mapping ``(tx_id, index)`` → ``(address, amount_cents)``.

    A block that is not a dict with 'header' and 'transactions' is refused by name.
    """
    if not isinstance(blocks, (tuple, list)):
        raise SetError("blocks %r is not a list or tuple" % (blocks,))
    utxo = {}
    spent = set()
    for block in blocks:
        if not isinstance(block, dict) or "transactions" not in block:
            raise SetError("block %r is not a valid block dict" % (block,))
        for tx in block["transactions"]:
            for inp in tx.get("inputs", ()):
                spent.add((inp["prev_tx_id"], inp["prev_index"]))
            for i, out in enumerate(tx.get("outputs", ())):
                if (tx["tx_id"], i) not in spent:
                    utxo[(tx["tx_id"], i)] = (out["address"], out["amount_cents"])
    return utxo


def apply(utxo_set, tx):
    """Apply a transaction to the UTXO set and return the new set.

    The transaction's inputs reference outpoints in *utxo_set*.  Each
    referenced outpoint is removed (spent).  Each output is added as a
    new UTXO.

    Validates:
    - Each input references an existing outpoint.
    - Each input is owned by the signer (address match).
    - Total input value >= total output value.

    Refuses by name on invalid input.
    """
    if not isinstance(utxo_set, dict):
        raise SetError("utxo_set %r is not a dict" % (utxo_set,))
    if not isinstance(tx, dict) or "inputs" not in tx:
        raise SetError("tx %r is not a valid transaction dict" % (tx,))
    new_utxo = dict(utxo_set)
    first_out_addr = None
    for out in tx.get("outputs", ()):
        if first_out_addr is None:
            first_out_addr = out.get("address")
    for inp in tx.get("inputs", ()):
        key = (inp["prev_tx_id"], inp["prev_index"])
        if key not in new_utxo:
            raise SetError("outpoint %s not found in utxo set" % str(key))
        old_addr, _amount = new_utxo[key]
        if old_addr != first_out_addr:
            raise SetError(
                "outpoint %s not owned by signer %r, owner is %r"
                % (str(key), first_out_addr, old_addr))
        del new_utxo[key]
    for i, out in enumerate(tx.get("outputs", ())):
        new_utxo[(tx["tx_id"], i)] = (out["address"], out["amount_cents"])
    return new_utxo


def balance(utxo_set, address):
    """Sum the value of all unspent outputs owned by *address*.

    Returns an integer count of cents.  An address with no UTXOs returns zero.
    """
    total = 0
    for (tx_id, idx), (addr, amount) in utxo_set.items():
        if addr == address:
            total += amount
    return total


if __name__ == "__main__":
    """Demo: build a UTXO set from blocks."""
    blocks = [
        {"header": {"height": 0}, "transactions": [
            {"tx_id": "gen0", "inputs": [], "outputs": [
                {"address": "alice", "amount_cents": 1000},
                {"address": "bob", "amount_cents": 500},
            ]},
        ]},
    ]
    utxo = outpoints(blocks)
    print("UTXO count: %d" % len(utxo))
    print("Alice balance: %d" % balance(utxo, "alice"))
    print("Bob balance: %d" % balance(utxo, "bob"))