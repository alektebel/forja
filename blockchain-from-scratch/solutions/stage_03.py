"""Blockchain From Scratch — stage 3: Addresses and the signature that binds.

A transaction is only valid if its inputs are signed by the owner of the
spending address.  This stage wires the public-key primitives from the
keys world into the transaction model: derive an address from a public key,
attach a signature to a transaction, and verify that the signature commits
to the exact transaction content.

The address scheme:
- A private key *priv* is an integer in ``[1, P-2]`` (from ``keygen``).
- The public key is ``pub = pow(5, priv, P)`` where P = 2^61 - 1.
- The address is ``"addr_"`` + the first 40 hex chars of ``sha256(canonical(pub))``.

The signing scheme (toy Schnorr, provided by keys.world):
- ``sign(msg_obj, priv)`` returns ``(R, s)``.
- ``verify(msg_obj, pub, (R, s))`` checks ``pow(5, s, P) == R * pow(pub, e, P) mod P``.
- The challenge ``e = sha256(R, pub, msg)`` commits to the public key and the message,
  so a signature for one message cannot be reused on another.

The stage's job is to:
1. Derive addresses from public keys (passing through the world's function).
2. Build a transaction with signed inputs, attaching ``(R, s)`` per input.
3. Verify each input's signature against the transaction content.

    ADDR_KEYS                     the two address fields, in order
    SIGN_KEYS                     the four signature fields, in order
    BindingError                  the refusal this stage raises
    _wallet(pub)                  -> address string from public key
    witness(tx, priv, pub)        -> attach signature to transaction and return
    verify_input(tx, index, pub, sig) -> bool

DESIGN DECISION — why does the stage derive addresses through the world?
Because the address is ``sha256(canonical(pub))`` truncated and prefixed.
A stage that implements its own hashing or truncation would produce a
different address for the same public key, and the signature verification
would silently fail (wrong address → wrong pub).  The stage must never
re-implement the world's address function.

DESIGN DECISION — why does ``witness`` attach signatures rather than just
verify?
Because the template asks you to *build* a signed transaction.  The
signature proves ownership; attaching it is how the stage exercises the
construction.  The check then calls ``verify_input`` to confirm the
signature is valid and that changing the transaction breaks it.

DESIGN DECISION — why does the challenge commit to the public key?
Because without ``pub`` in the challenge, an attacker could take a
signature made for one public key and attach it to a transaction under
a different public key (the "key replacement attack").  Including the
public key in ``e = sha256(R, pub, msg)`` binds the signature to both
the message and the specific key.

TODO: implement ``ADDR_KEYS``, ``SIGN_KEYS``, ``BindingError``, ``_wallet``,
``witness``, and ``verify_input`` in this file.  A signature made for one
transaction must be refused when attached to a different transaction.
"""

import ledger
from ledger import LedgerError
import keys


ADDR_KEYS = ("address", "pub_hex")

SIGN_KEYS = ("R", "s", "tx_id", "signer")

_BINDING_ERROR_NAME = "binding"


class BindingError(LedgerError):
    """The refusal this stage raises: something that cannot be a signed transaction.

    Names the offender — the address that does not match the public key, the
    signature that does not verify, the private key that does not correspond
    to the public key — because a signed transaction the world cannot validate
    must say what it was asked for.
    """


def _wallet(pub):
    """Derive the address for a public key through the world's function.

    Passes *pub* to ``keys.address(pub)`` and returns the string.
    """
    return keys.address(pub)


def _compute_tx_id(tx):
    """Compute a transaction ID: sha256 of the canonical encoding."""
    return ledger.digest(tx)


def _tx_for_signing(tx):
    """Return the transaction content suitable for signing.

    Returns a copy of the transaction dict with the signature fields removed.
    """
    return {k: v for k, v in tx.items() if k not in ("signatures",)}


def witness(tx, priv, pub):
    """Attach a signature to a transaction and return the signed transaction.

    Computes the tx_id, signs the unsigned transaction content using the
    world's ``keys.sign()`` with the provided private key, and stores
    the signature ``(R, s)`` in the transaction under the key
    ``signatures[address]`` where address comes from ``_wallet(pub)``.

    A private key not in [1, P-2] is refused by name.
    A public key that does not match the private key is refused by name.
    """
    if isinstance(priv, bool) or not isinstance(priv, int):
        raise BindingError("private key %r is not an integer" % (priv,))
    if priv < 1 or priv >= keys.P:
        raise BindingError("private key %d is outside [1, P-2=%d]" % (priv, keys.P - 2))
    if isinstance(pub, bool) or not isinstance(pub, int):
        raise BindingError("public key %r is not an integer" % (pub,))
    if keys.pubkey(priv) != pub:
        raise BindingError("public key %d does not match private key" % (priv,))
    addr = _wallet(pub)
    signing_tx = _tx_for_signing(tx)
    R, s = keys.sign(signing_tx, priv)
    signed_tx = dict(tx)
    if "signatures" not in signed_tx:
        signed_tx["signatures"] = {}
    signed_tx["signatures"][addr] = {"R": R, "s": s, "pub": pub}
    return signed_tx


def verify_input(tx, index, pub, sig):
    """Verify a single input's signature against the transaction.

    Looks up the signature stored for the address derived from *pub* and
    calls ``keys.verify(tx_content, pub, sig)`` where *tx_content* is the
    transaction with signatures removed.
    """
    signing_tx = _tx_for_signing(tx)
    return keys.verify(signing_tx, pub, sig)


if __name__ == "__main__":
    """Demo: create a keypair, sign a transaction, and verify."""
    priv = keys.keygen(12345)
    pub = keys.pubkey(priv)
    addr = _wallet(pub)
    print("Private key: %d" % priv)
    print("Public key: %d" % pub)
    print("Address: %s" % addr)
    tx = {"tx_id": "demo_tx", "inputs": [{"prev_tx_id": "gen", "prev_index": 0}],
          "outputs": [{"address": addr, "amount_cents": 100}]}
    signed_tx = witness(tx, priv, pub)
    print("Transaction signed with R=%d, s=%d" % (signed_tx["signatures"][addr]["R"],
                                                     signed_tx["signatures"][addr]["s"]))
    verified = verify_input(signed_tx, 0, pub, signed_tx["signatures"][addr])
    print("Verification result: %s" % verified)