"""
S3 — object storage. Starter template.

DESIGN DECISION — a filesystem, or a flat key-value store?
  S3 looks like it has folders. It does not. `reports/2024/q1.csv` is one
  opaque key that happens to contain slashes; "folders" are an illusion the
  console builds by splitting on a delimiter at list time.
  CHOSEN: a flat dict, with prefix/delimiter emulated in list_objects. Building
  it flat is what makes the consequences obvious — renaming a "folder" is
  O(objects), not O(1), and there is no such thing as an empty one.

DESIGN DECISION — how to model versioning?
  Simplest is a per-key list of versions with a pointer to the current one.
  CHOSEN: that, plus the detail that makes versioning surprising: DELETE does
  not delete. It pushes a DELETE MARKER on top. The data is still billed for,
  still there, and a plain GET now 404s while a versioned GET succeeds. That
  single behaviour explains most "why is my bucket still huge" tickets.
"""

import hashlib
import time
from typing import Any, Dict, Iterator, List, NamedTuple, Optional, Tuple


class S3Error(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


class Version(NamedTuple):
    version_id: str
    body: Optional[bytes]        # None means this is a delete marker
    etag: str
    size: int
    last_modified: float
    metadata: Dict[str, str]

    @property
    def is_delete_marker(self) -> bool:
        return self.body is None


def compute_etag(body: bytes, parts: Optional[List[bytes]] = None) -> str:
    """S3's ETag is an MD5 — except for multipart uploads.

    A multipart ETag is the MD5 of the concatenated part MD5s, followed by
    "-<part count>". That is why you cannot verify a multipart object by
    md5-ing the file you uploaded: the ETag is not the object's MD5, and the
    part size changes the answer.
    """
    raise NotImplementedError


class Bucket:
    def __init__(self, name: str, versioning: bool = False):
        self.name = name
        self.versioning = versioning
        self.objects: Dict[str, List[Version]] = {}
        self.uploads: Dict[str, Dict[int, bytes]] = {}
        self._counter = 0

    def _next_version(self) -> str:
        self._counter += 1
        return f"v{self._counter:06d}"


class S3:
    """A tiny object store with versioning, prefixes and multipart upload."""

    def __init__(self):
        self.buckets: Dict[str, Bucket] = {}
        self.stats = {"puts": 0, "gets": 0, "deletes": 0, "lists": 0}

    # -- buckets ------------------------------------------------------------

    def create_bucket(self, name: str, versioning: bool = False) -> Bucket:
        if name in self.buckets:
            raise S3Error("BucketAlreadyExists", name)
        self.buckets[name] = Bucket(name, versioning)
        return self.buckets[name]

    def _bucket(self, name: str) -> Bucket:
        if name not in self.buckets:
            raise S3Error("NoSuchBucket", name)
        return self.buckets[name]

    def set_versioning(self, bucket: str, enabled: bool) -> None:
        """Versioning can be suspended but never turned OFF — existing versions
        stay, and stay billable. Modelled here because it is the part that
        surprises people on the invoice."""
        raise NotImplementedError
    # -- objects ------------------------------------------------------------

    def put_object(self, bucket: str, key: str, body: bytes,
                   metadata: Optional[Dict[str, str]] = None) -> str:
        raise NotImplementedError

    def get_object(self, bucket: str, key: str,
                   version_id: Optional[str] = None) -> Version:
        raise NotImplementedError

    def delete_object(self, bucket: str, key: str,
                      version_id: Optional[str] = None) -> Optional[str]:
        """Unversioned: really deletes. Versioned: pushes a delete marker.

        Deleting a specific version_id in a versioned bucket is the only way to
        actually remove bytes — which is why "empty the bucket" scripts that
        only issue plain DELETEs leave the storage bill untouched.
        """
        raise NotImplementedError

    def list_object_versions(self, bucket: str, key: str) -> List[Version]:
        raise NotImplementedError
    # -- listing ------------------------------------------------------------

    def list_objects(self, bucket: str, prefix: str = "", delimiter: str = "",
                     max_keys: int = 1000,
                     continuation_token: Optional[str] = None
                     ) -> Dict[str, Any]:
        """Prefix and delimiter listing, with pagination.

        The delimiter is what invents folders: keys sharing a prefix up to the
        next delimiter are collapsed into one "common prefix". No directory
        exists anywhere — which is why you cannot have an empty one, and why
        listing a huge "folder" costs the same as listing the bucket.
        """
        raise NotImplementedError
    # -- multipart ----------------------------------------------------------

    def create_multipart_upload(self, bucket: str, key: str) -> str:
        raise NotImplementedError

    def upload_part(self, bucket: str, upload_id: str, part_number: int,
                    body: bytes) -> str:
        raise NotImplementedError

    def complete_multipart_upload(self, bucket: str, key: str,
                                  upload_id: str) -> str:
        raise NotImplementedError

    def abandoned_uploads(self, bucket: str) -> Dict[str, int]:
        """Incomplete uploads still occupy storage and are still billed.

        Nothing lists them by default, which is why a lifecycle rule to abort
        them is close to mandatory on any bucket that takes large uploads.
        """
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
