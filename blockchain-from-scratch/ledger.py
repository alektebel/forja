"""Ledger world — hashing, encoding, block structures, and a deterministic PRNG.

This module is the **provided, read-only world** for the whole blockchain course.
Stage code must never mutate it; it exposes accessors that serve as the answer key.

What it holds
-------------
* ``canonical`` — deterministic encoding of any value built from the primitive
  types (int, bool, str, bytes, tuple, list, dict) that the block header,
  transaction, and output records use.  Every hash binds these exact bytes.

* ``digest`` — SHA-256 over the canonical bytes; returns the hexdigest string.

* ``_hash_bytes`` — internal helper: SHA-256 over raw bytes, returns hex digest.

* ``prng`` — returns a fresh SplitMix64 PRNG instance over plain integers
  (no ``random`` module).  The stages and the network use it for witness
  searches and scenario generation.

* The record constructors: ``Header``, ``Block``, ``Transaction``,
  ``TransactionInput``, ``TransactionOutput``.  Each carries a fixed
  ``*_KEYS`` tuple so a check can verify field order by ``tuple(record)``.

* Constants: ``COIN`` (smallest unit = 100 000 000), ``RETARGET_INTERVAL``
  (6 blocks), ``TICKS_PER_BLOCK`` (1), ``GENESIS_HASH`` (all-zeros), and
  ``MAX_TARGET`` (the most permissive difficulty boundary).

* ``LedgerError`` — the refusal family every stage must use.
"""

import hashlib


# ── constants ───────────────────────────────────────────────────────────────

COIN = 100_000_000
RETARGET_INTERVAL = 6
TICKS_PER_BLOCK = 1
GENESIS_HASH = (
    "0000000000000000000000000000000000000000000000000000000000000000"
)
MAX_TARGET = 2 ** 256 - 1  # most permissive boundary


# ── canonical encoding ─────────────────────────────────────────────────────

def canonical(value):
    """Deterministic encoding of a value into bytes.

    Order is fixed so every hash binds the same logical value to the exact
    same bytes regardless of construction order:

    * ``None`` → b''
    * ``bool``  → b'\\x01' or b'\\x00'  (must check before int)
    * ``int``  → signed two's-complement big-endian (smallest representation)
    * ``str``  → length-prefixed UTF-8
    * ``bytes``→ raw bytes
    * ``tuple``/``list`` → count-prefixed element encodings
    * ``dict`` → count-prefixed (key, value) pairs sorted by key
    """
    if value is None:
        return b""
    if isinstance(value, bool):
        return b"\x01" if value else b"\x00"
    if isinstance(value, int):
        if value == 0:
            return b"\x00"
        if value < 0:
            # Two's complement: get abs, invert, add 1
            abs_val = abs(value)
            byte_length = (abs_val.bit_length() + 7) // 8
            raw = abs_val.to_bytes(byte_length, byteorder="big")
            inverted = bytes(b ^ 0xFF for b in raw)
            carry = 1
            result = bytearray(len(inverted))
            for i in range(len(inverted) - 1, -1, -1):
                s = (inverted[i] & 0xFF) + carry
                result[i] = s & 0xFF
                carry = s >> 8
            while carry:
                result.append(carry & 0xFF)
                carry >>= 8
            return bytes(result)
        byte_length = (value.bit_length() + 7) // 8
        return value.to_bytes(byte_length, byteorder="big")
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        return _encode_length(len(encoded)) + encoded
    if isinstance(value, bytes):
        return _encode_length(len(value)) + value
    if isinstance(value, (tuple, list)):
        result = b""
        for item in value:
            result += canonical(item)
        return _encode_length(len(value)) + result
    if isinstance(value, dict):
        result = b""
        for key in sorted(value.keys()):
            result += canonical(key)
            result += canonical(value[key])
        return _encode_length(len(value)) + result
    raise LedgerError("unsupported type %r for canonical encoding" % type(value).__name__)


def _encode_length(length):
    """Encode a non-negative integer as a length prefix."""
    if length == 0:
        return b"\x00"
    byte_length = (length.bit_length() + 7) // 8
    return length.to_bytes(byte_length, byteorder="big")


# ── hashing ─────────────────────────────────────────────────────────────────

def digest(value):
    """SHA-256 digest of a value's canonical encoding, returned as hex string."""
    return hashlib.sha256(canonical(value)).hexdigest()


def _hash_bytes(raw_bytes):
    """SHA-256 over raw bytes, returned as hex digest."""
    return hashlib.sha256(raw_bytes).hexdigest()


# ── deterministic PRNG (SplitMix64) ─────────────────────────────────────────

class _PRNG:
    """SplitMix64 PRNG encapsulating state — deterministic, no ``random`` module."""
    MASK = (1 << 64) - 1

    def __init__(self):
        self._state = 0

    def seed(self, seed_value):
        """Reset PRNG state from an integer seed (masked to 64 bits)."""
        self._state = seed_value & self.MASK

    def next(self):
        """Return the next pseudo-random 64-bit unsigned integer."""
        z = self._state
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9 & self.MASK
        z = (z ^ (z >> 27)) * 0x94D049BB133111EB & self.MASK
        z = (z ^ (z >> 31)) & self.MASK
        self._state = z
        return z


def prng():
    """Return a fresh, stateless PRNG instance."""
    return _PRNG()


# ── record constructors ─────────────────────────────────────────────────────

_HEADER_KEYS = ("height", "prev_hash", "tx_root", "tick", "target")


def Header(height, prev_hash, tx_root, tick, target):
    """Construct a block header record (dict with fixed key order)."""
    return {"height": height, "prev_hash": prev_hash, "tx_root": tx_root,
            "tick": tick, "target": target}


def header_keys():
    """The fixed key order of a header record."""
    return _HEADER_KEYS


_BLOCK_KEYS = ("header", "transactions")


def Block(header, transactions):
    """Construct a block record (dict)."""
    return {"header": header, "transactions": tuple(transactions)}


def block_keys():
    """The fixed key order of a block record."""
    return _BLOCK_KEYS


_TX_KEYS = ("tx_id", "inputs", "outputs", "value", "tick")


def Transaction(tx_id, inputs, outputs, value, tick):
    """Construct a transaction record (dict)."""
    return {"tx_id": tx_id, "inputs": tuple(inputs), "outputs": tuple(outputs),
            "value": value, "tick": tick}


def tx_keys():
    """The fixed key order of a transaction record."""
    return _TX_KEYS


_TX_INPUT_KEYS = ("prev_tx_id", "prev_index")


def TransactionInput(prev_tx_id, prev_index):
    """Construct a transaction input record."""
    return {"prev_tx_id": prev_tx_id, "prev_index": prev_index}


def tx_input_keys():
    """The fixed key order of a transaction input record."""
    return _TX_INPUT_KEYS


_TX_OUTPUT_KEYS = ("address", "amount_cents")


def TransactionOutput(address, amount_cents):
    """Construct a transaction output record."""
    return {"address": address, "amount_cents": amount_cents}


def tx_output_keys():
    """The fixed key order of a transaction output record."""
    return _TX_OUTPUT_KEYS


_OUTPOINT_KEYS = ("tx_id", "index")


def Outpoint(tx_id, index):
    """Construct an outpoint record (dict)."""
    return {"tx_id": tx_id, "index": index}


def outpoint_keys():
    """The fixed key order of an outpoint record."""
    return _OUTPOINT_KEYS


# ── ledger errors ───────────────────────────────────────────────────────────

class LedgerError(Exception):
    """The base refusal family for ledger-world operations.

    Subclasses are defined in each stage's template to carry the specific
    domain name.  Every refusal must name the offender in its message so
    checks can verify ``offender_name in str(exc)``.
    """


class _LedgerStats:
    """Internal counter that stages can read to prove they don't cheat."""

    def __init__(self):
        self._counts = {"headers": 0, "blocks": 0, "transactions": 0,
                        "outpoints": 0, "utxos": 0}

    def inc(self, kind):
        self._counts[kind] = self._counts.get(kind, 0) + 1

    def get(self):
        return dict(self._counts)


_STATS = _LedgerStats()


def stats():
    """Return a copy of the internal accessor counters."""
    return dict(_STATS._counts)


def reset_stats():
    """Reset all counters (used by checks before each run)."""
    _STATS._counts = {"headers": 0, "blocks": 0, "transactions": 0,
                       "outpoints": 0, "utxos": 0}