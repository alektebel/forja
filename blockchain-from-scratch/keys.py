"""Keys world — toy Schnorr signatures over a 61-bit Mersenne prime.

This module is the **provided, read-only world** for the whole blockchain course.
Stage code must never mutate it; it exposes accessors that serve as the answer key.

Cryptographic note
------------------
This is a **teaching scheme**, not a production-grade signature system.  The
prime is 2^61 - 1 = 2 305 843 009 213 693 951, small enough that a reviewer
can recompute the arithmetic by hand in a couple of lines.  It does **not**
provide security against brute-force, discrete-log, or side-channel attacks.
Use only for learning.

What it holds
-------------
* ``P`` — the 61-bit Mersenne prime (2^61 - 1).

* ``G`` — the generator, fixed at 5.

* ``keygen(seed)`` — deterministic private key from a 48-bit seed via the
  ledger PRNG.  The private key is in ``[1, P - 2]``.

* ``pubkey(priv)`` → ``pow(G, priv, P)``.

* ``sign(msg_obj, priv)`` → ``(R, s)`` where
  ``R = pow(G, k, P)``,
  ``e = int(digest(R, pubkey, msg), 16) % (P - 1)``  (exponent mod P-1),
  ``s = (k + priv * e) % (P - 1)``.
  The nonce ``k`` comes from the PRNG seeded by ``priv % 2^48``.

* ``verify(msg_obj, pub, sig)`` → ``True`` iff
  ``pow(G, s, P) == R * pow(pub, e, P) % P`` with the same challenge ``e``.
  The exponent ``s`` is mod P-1 (Fermat's little theorem).

* ``address(pub)`` → ``"addr_"`` + first 40 hex chars of ``sha256(canonical(pub))``.

All arithmetic is in Python's unbounded integers; no ``float``.
"""

from ledger import digest, canonical, prng, _hash_bytes, LedgerError

import hashlib


P = (1 << 61) - 1  # 2^61 - 1, a Mersenne prime
G = 5              # generator


class KeysError(LedgerError):
    """Refusal family for key operations."""


def keygen(seed):
    """Derive a private key from a 48-bit seed.

    Uses the ledger PRNG seeded by ``seed`` and returns an integer in
    ``[1, P - 2]``.  Same seed always produces the same key.
    """
    rng = prng()
    rng.seed(seed)
    priv = rng.next() % (P - 2) + 1
    return priv


def pubkey(priv):
    """Derive the public key: G^priv mod P."""
    if isinstance(priv, bool) or not isinstance(priv, int):
        raise KeysError("private key %r is not an integer" % (priv,))
    if priv < 1 or priv >= P:
        raise KeysError("private key %d is outside [1, P-2=%d]" % (priv, P - 2))
    return pow(G, priv, P)


def sign(msg_obj, priv):
    """Sign a message object with a private key (toy Schnorr).

    Returns ``(R, s)``:

    * ``k`` is a nonce from the PRNG seeded by ``priv % 2^48``.
    * ``R = pow(G, k, P)``
    * ``e = int(digest((R, pubkey(priv), msg_obj)), 16) % (P - 1)``
      (exponent reduced mod P-1 per Fermat's little theorem)
    * ``s = (k + priv * e) % (P - 1)``

    The challenge ``e`` commits to the public key and the message, so a
    signature for one message cannot be reused on another.
    """
    if isinstance(priv, bool) or not isinstance(priv, int):
        raise KeysError("private key %r is not an integer" % (priv,))
    if priv < 1 or priv >= P:
        raise KeysError("private key %d is outside [1, P-2=%d]" % (priv, P - 2))
    pub = pubkey(priv)
    seed = priv % (1 << 48)
    rng = prng()
    rng.seed(seed)
    k = rng.next() % (P - 2) + 1
    R = pow(G, k, P)
    e_bytes = digest((R, pub, msg_obj))
    e = int(e_bytes, 16) % (P - 1)
    s = (k + priv * e) % (P - 1)
    return (R, s)


def verify(msg_obj, pub, sig):
    """Verify a toy Schnorr signature.

    Returns ``True`` iff ``pow(G, s, P) == R * pow(pub, e, P) % P``
    where ``e`` is computed the same way as in ``sign()``.
    """
    if isinstance(pub, bool) or not isinstance(pub, int):
        raise KeysError("public key %r is not an integer" % (pub,))
    if not isinstance(sig, tuple) or len(sig) != 2:
        raise KeysError("signature %r is not a (R, s) tuple" % (sig,))
    R, s = sig
    if not isinstance(R, int) or not isinstance(s, int):
        raise KeysError("signature values %r are not integers" % (sig,))
    if R < 0 or R >= P or s < 0 or s >= P:
        raise KeysError("signature values outside [0, P)")
    e_bytes = digest((R, pub, msg_obj))
    e = int(e_bytes, 16) % (P - 1)
    lhs = pow(G, s, P)
    rhs = (R * pow(pub, e, P)) % P
    return lhs == rhs


def address(pub):
    """Derive a readable address from a public key.

    Returns ``"addr_"`` + first 40 hex chars of ``sha256(canonical(pub))``.
    """
    if isinstance(pub, bool) or not isinstance(pub, int):
        raise KeysError("public key %r is not an integer" % (pub,))
    h = hashlib.sha256(canonical(pub)).hexdigest()
    return "addr_" + h[:40]