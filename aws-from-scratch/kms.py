"""
KMS — envelope encryption. Starter template.

DESIGN DECISION — encrypt data with the master key, or with a data key?
  Encrypting directly with the KMS key means every byte crosses the network to
  a service that caps payloads at 4KB, and rotating the key means re-encrypting
  everything you own.
  CHOSEN: ENVELOPE encryption. KMS generates a random data key, hands you it
  twice — plaintext and encrypted-under-the-master-key — and forgets it. You
  encrypt locally with the plaintext copy, throw it away, and store the
  encrypted copy next to the ciphertext.
  The consequences are the whole lesson: unlimited data size, one network call
  per object rather than per byte, and key rotation that re-encrypts KEYS
  rather than DATA.

DESIGN DECISION — what is "rotation"?
  The intuitive answer is "make a new key and re-encrypt everything".
  CHOSEN: model what actually happens — a new key VERSION is created for new
  encryptions, and old versions are retained so old ciphertext still decrypts.
  Rotation that broke old data would not be rotation, it would be an outage.

The cipher here is XOR. It is NOT encryption and the file says so loudly. The
structure — data keys, wrapping, context, rotation — is the lesson; substitute
AES-GCM and nothing about the shape changes.
"""

import hashlib
import os
import secrets
from typing import Any, Dict, List, NamedTuple, Optional, Tuple


class KMSError(Exception):
    pass


def _xor(data: bytes, key: bytes) -> bytes:
    """A stand-in cipher, NOT encryption.

    XOR with a repeating key is trivially broken and is used here only so the
    file has no dependencies and every step stays inspectable. Everything
    around it — envelope structure, wrapping, encryption context, rotation — is
    exactly what you would build with AES-GCM. Do not ship this.
    """
    return bytes(byte ^ key[index % len(key)] for index, byte in enumerate(data))


class KeyVersion(NamedTuple):
    version: int
    material: bytes


class MasterKey:
    """A CMK never leaves the service. You cannot export its material."""

    def __init__(self, key_id: str, description: str = ""):
        self.key_id = key_id
        self.description = description
        self.versions: List[KeyVersion] = [KeyVersion(1, secrets.token_bytes(32))]
        self.policy_principals: List[str] = []
        self.grants: Dict[str, Dict[str, Any]] = {}
        self.stats = {"encrypts": 0, "decrypts": 0, "data_keys": 0, "rotations": 0}

    @property
    def current(self) -> KeyVersion:
        return self.versions[-1]

    def rotate(self) -> int:
        """New material for NEW encryptions. Old versions are retained.

        This is why rotation is cheap: it re-encrypts nothing. Every existing
        ciphertext still names the version it was wrapped under, and that
        version still exists.
        """
        raise NotImplementedError

    def _version(self, number: int) -> KeyVersion:
        for version in self.versions:
            if version.version == number:
                return version
        raise KMSError(f"missing key version {number}")


class EncryptedDataKey(NamedTuple):
    key_id: str
    version: int
    wrapped: bytes
    context: Dict[str, str]


class DataKey(NamedTuple):
    plaintext: bytes                  # use it, then forget it
    encrypted: EncryptedDataKey       # store this next to the ciphertext


class KMS:
    def __init__(self):
        self.keys: Dict[str, MasterKey] = {}

    def create_key(self, key_id: str, description: str = "") -> MasterKey:
        key = MasterKey(key_id, description)
        self.keys[key_id] = key
        return key

    def _key(self, key_id: str) -> MasterKey:
        if key_id not in self.keys:
            raise KMSError(f"no such key {key_id!r}")
        return self.keys[key_id]

    @staticmethod
    def _context_bytes(context: Dict[str, str]) -> bytes:
        """Encryption context is AAD: not secret, but authenticated.

        It is bound into the wrap, so decrypting requires supplying exactly the
        same context. That turns "who may use this key" into "who may use this
        key FOR THIS PURPOSE", and it is what lets an IAM condition say
        kms:EncryptionContext:tenant = ${aws:PrincipalTag/tenant}.
        """
        canonical = "&".join(f"{key}={value}" for key, value in sorted(context.items()))
        return hashlib.sha256(canonical.encode()).digest()

    def generate_data_key(self, key_id: str,
                          context: Optional[Dict[str, str]] = None) -> DataKey:
        """The heart of envelope encryption: one key, returned twice.
        TODO: generate a random 32-byte key, then return it TWICE —
        plaintext, and wrapped under the master key's CURRENT version with the
        encryption context bound in.

        The caller encrypts locally with the plaintext copy and throws it away;
        the wrapped copy is stored next to the ciphertext. That is envelope
        encryption, and it is why a 2GB object is no harder than a 2KB one.
        """
        raise NotImplementedError

    def decrypt_data_key(self, encrypted: EncryptedDataKey,
                         context: Optional[Dict[str, str]] = None) -> bytes:
        """Unwrap. The context must match exactly, or this fails."""
        raise NotImplementedError


class EnvelopeCipher:
    """The pattern you would actually use, built on the primitives above."""

    def __init__(self, kms: KMS, key_id: str):
        self.kms = kms
        self.key_id = key_id

    def encrypt(self, plaintext: bytes,
                context: Optional[Dict[str, str]] = None
                ) -> Tuple[bytes, EncryptedDataKey]:
        """One KMS call per OBJECT, not per byte. The data never leaves you."""
        raise NotImplementedError

    def decrypt(self, ciphertext: bytes, encrypted_key: EncryptedDataKey,
                context: Optional[Dict[str, str]] = None) -> bytes:
        raise NotImplementedError


def _demo() -> None:
    """Once the checks pass, write a demo that PRINTS the behaviour.

    The solution's demo is the reference — but write yours first and predict
    the numbers before running it. A result that surprises you is a gap in your
    model that passing tests did not reveal.
    """
    raise NotImplementedError


if __name__ == "__main__":
    _demo()
