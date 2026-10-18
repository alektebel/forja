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
import objects as ob
import stage_03 as s3

_INDEX_MAGIC = b"DIRC"
_INDEX_VERSION = 2
_FLAG_CAP = 0xFFF


def read_index(repo):
    """The entries as `(mode, sha, path)`, the format verified."""
    path = repo.git_dir + "/index"
    if not repo.fs.exists(path):
        return ()
    raw = repo.fs.read(path)
    if raw[:4] != _INDEX_MAGIC:
        raise rp.GitError("read_index: the magic is %r, not DIRC"
                          % (raw[:4],))
    version = int.from_bytes(raw[4:8], "big")
    if version != _INDEX_VERSION:
        raise rp.GitError("read_index: version %d, not %d"
                          % (version, _INDEX_VERSION))
    count = int.from_bytes(raw[8:12], "big")
    entries = []
    at = 12
    for _i in range(count):
        mode = int.from_bytes(raw[at + 24:at + 28], "big")
        sha = raw[at + 40:at + 60].hex()
        flags = int.from_bytes(raw[at + 60:at + 62], "big")
        name_len = flags & _FLAG_CAP
        name = raw[at + 62:at + 62 + name_len].decode()
        entries.append((("%o" % mode), sha, name))
        entry_len = 62 + name_len
        pad = 8 - (entry_len % 8) or 8
        at += entry_len + pad
    return tuple(entries)


def write_index(repo, entries):
    """The entries in git's index format; the record is the file."""
    body = _INDEX_MAGIC + _INDEX_VERSION.to_bytes(4, "big") \
        + len(entries).to_bytes(4, "big")
    for (mode, sha, name) in entries:
        name_bytes = name.encode()
        if len(name_bytes) > _FLAG_CAP:
            raise rp.GitError("write_index: %r is longer than the flag cap "
                              "(%d)" % (name, len(name_bytes)))
        # ctime(8) mtime(8) dev(4) ino(4) zeroed; then mode, uid, gid,
        # size; then the sha, the flags, the path, the pad
        entry = bytes(24) \
            + int(mode, 8).to_bytes(4, "big") \
            + bytes(8) \
            + len(repo.fs.read(name)).to_bytes(4, "big") \
            + bytes.fromhex(sha) \
            + len(name_bytes).to_bytes(2, "big") \
            + name_bytes
        entry_len = len(entry)          # 62 + the name
        pad = 8 - (entry_len % 8) or 8
        body += entry + bytes(pad)
    checksum = ob.sha1(body)
    repo.fs.write(repo.git_dir + "/index",
                  body + bytes.fromhex(checksum))


def add(repo, paths):
    """The paths staged (directories recursively); the record answered."""
    fs = repo.fs
    existing = {path: (mode, sha, path)
                for (mode, sha, path) in read_index(repo)}
    for one in paths:
        if one.endswith("/"):
            for name in fs.list(one.rstrip("/")):
                full = one.rstrip("/") + "/" + name
                if name.endswith("/"):
                    continue
                mode = "100755" if fs.is_exec(full) else "100644"
                sha = s3.hash_object(repo, fs.read(full))
                existing[full] = (mode, sha, full)
        else:
            mode = "100755" if fs.is_exec(one) else "100644"
            sha = s3.hash_object(repo, fs.read(one))
            existing[one] = (mode, sha, one)
    ordered = sorted(existing.values(), key=lambda e: e[2])
    write_index(repo, ordered)
    stats = {"staged": len(ordered), "written": repo.counters()["written"]}
    return {"entries": tuple(ordered), "stats": stats}
