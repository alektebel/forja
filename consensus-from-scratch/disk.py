"""disk.py — durable storage that can lose its last write (provided world).

A node's term, vote and log live on a disk the world owns. The disk is
deliberately small and deliberately treacherous: `write` records the bytes,
`read` answers the last record, and `crash` returns everything *except* the
last record — the torn write every replication protocol must survive. There
is no filesystem here: the disk is a list of byte strings and `crash` is one
slice, so the scenario is reproducible and a stage never opens a file.

The record's ENCODING is the student's business (stage 7's `persist`); the
world only stores and loses bytes.
"""


class DiskError(ValueError):
    """The disk's own refusal: a record that is not bytes."""


class Disk:
    """A node's durable storage: append-only records, and one crash mode."""

    def __init__(self, node_id):
        if not isinstance(node_id, str) or not node_id:
            raise DiskError("disk: a node id must be a non-empty string, "
                            "got %r" % (node_id,))
        self.node_id = node_id
        self._records = ()

    def write(self, record):
        """Append one durable record. Returns the record's index."""
        if not isinstance(record, bytes):
            raise DiskError("disk.write: a record must be bytes, got %r"
                            % (type(record).__name__,))
        self._records = self._records + (record,)
        return len(self._records) - 1

    def read(self):
        """The last record written — b'' before anything was ever written."""
        if not self._records:
            return b""
        return self._records[-1]

    def records(self):
        """Every record ever written, oldest first: the disk's full truth."""
        return self._records

    def crash(self):
        """The torn write: everything that survived is every record minus
        the last one. Returns the bytes a recovering node can still read,
        which is `read()` of the crashed disk — the last record is gone."""
        if not self._records:
            self._records = ()
            return b""
        self._records = self._records[:-1]
        if not self._records:
            return b""
        return self._records[-1]
