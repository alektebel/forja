"""Git From Scratch — stage 7: The index: staging is a record, not a
copy.

The index is the one file where git's binary format meets the working
tree: `DIRC`, version 2, the entry count, then one entry per staged file —
ten fixed fields (ctime, mtime, dev, ino, mode, uid, gid, size), the mode
and size the only honest ones in a deterministic course, the 20 raw sha,
flags (the path length, capped), the path, NUL-padded to a multiple of
eight. `git add` is the command over it, and the discipline is that
staging is a *record*: a file staged twice answers one entry, a directory
staged recursively stages sorted, and the mode travels with the entry.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why zero the stat fields instead of reading them?
Because the course is deterministic: ctime and mtime are clock facts, dev
and ino are machine facts, and either would make the index's bytes — and
so real git's reading of them — unreproducible. Real git itself treats
zeroed stat data as "racy, re-stat me"; the format survives, the law holds.

DESIGN DECISION — why is the flags cap a law rather than an accident?
Because the field is sixteen bits wide and git spends the top bit on the
extended flag: a path of 4096 bytes would silently overflow into it, and
an index that writes a flag real git reads as "extended" is an index real
git misparses. The cap (0xFFF) is the contract with the format, and the
check plants the too-long path.

DESIGN DECISION — why pad with NULs to a multiple of eight and write the
checksum?
Because real git reads this exact file: `git ls-files --stage` over the
exported repo is the judge, and the padding plus the trailing SHA-1 over
the whole content is what the format's reader requires. The stage that
skipped it would write an index only it could read — the failure the
whole course exists to prevent.
"""

import repo as rp

INDEX_KEYS = ("entries", "stats")


def read_index(repo):
    """The entries as `(mode, sha, path)`, the format verified."""
    raise NotImplementedError("stage 7: implement read_index()")


def write_index(repo, entries):
    """The entries in git's index format; the record is the file."""
    raise NotImplementedError("stage 7: implement write_index()")


def add(repo, paths):
    """The paths staged (directories recursively); the record answered."""
    raise NotImplementedError("stage 7: implement add()")
