"""OS From Scratch — stage 9: The format, and the write that was not ordered.

The disk in this course tells the truth twice: `Disk.write` puts bytes in a
*buffer*, and `Disk.read` answers with the *durable* image. That is not an
inconvenience, it is the whole stage. Between a write and a barrier the write has
not happened, and a power failure is exactly the moment that matters, so every
piece of this filesystem is written in an order chosen so that any prefix of the
writes is a filesystem somebody can still mount — or one nobody can, which is
better than a filesystem that mounts and lies.

`OSFS` is that format: one sector each, every owned sector carrying a checksum
over its own bytes mixed with its own index, the data first, the free map and the
inode table after, and the superblock **last** — so an interrupted format leaves
no valid superblock and `mount` refuses it, which is the correct outcome. Inodes
hold their blocks, directories are a sector of `ino`/name pairs, and the free map
is one byte per data sector where `1` means free.
"""

import devices
import machine
import userland

MAGIC = 0x4F534653
FORMAT_VERSION = 1
NAMES_MAX = 24
SECTOR = devices.SECTOR
PROBLEMS = (
    "bad_checksum", "bad_geometry", "bad_magic", "bad_version",
    "block_marked_free", "block_out_of_range", "block_shared",
    "entry_not_allocated", "entry_out_of_range", "root_not_directory",
    "size_mismatch",
)


class FsError(ValueError):
    """Anything a caller of this filesystem got wrong."""


_CHECKSUM = 4
_USABLE = SECTOR - _CHECKSUM
_ENTRY_BYTES = 2 + NAMES_MAX
_MAX_ENTRIES = _USABLE // _ENTRY_BYTES
_MAX_BLOCKS = 24
_FREE, _FILE, _DIR = 0, 1, 2
_KINDS = {_FREE: "free", _FILE: "file", _DIR: "dir"}
_GEOM_KEYS = ("magic", "version", "sector", "sectors", "inodes_start", "n_inodes",
              "dir_start", "n_dirs", "data_start", "n_data", "root_ino",
              "free_map_sector")


def checksum(data, index):
    """The 4-byte sum of `data`, mixed with the index of the sector it lands in."""
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise FsError("a sector index is a non-negative int, not %r" % (index,))
    total = index & 0xFFFFFFFF
    for byte in bytes(data):
        total = (total * 31 + byte) & 0xFFFFFFFF
    return total


def _stamp(payload, index):
    """A whole sector: the payload, then its own checksum."""
    return bytes(payload) + checksum(payload, index).to_bytes(_CHECKSUM, "big")


def _verify(sector, index):
    """The payload of a sector whose checksum is its own, or a refusal by name."""
    if len(sector) != SECTOR:
        raise FsError("sector %d is %d bytes, not %d" % (index, len(sector), SECTOR))
    payload = bytes(sector[:_USABLE])
    stored = int.from_bytes(bytes(sector[_USABLE:]), "big")
    if checksum(payload, index) != stored:
        raise FsError("sector %d fails its checksum: it is torn or stale" % (index,))
    return payload


def _get(payload, offset, width):
    return int.from_bytes(bytes(payload[offset:offset + width]), "big")


def _put(payload, offset, width, value):
    payload[offset:offset + width] = value.to_bytes(width, "big")


def _name_of(path):
    return path.rsplit("/", 1)[1]


def _parent_of(path):
    return path.rsplit("/", 1)[0] or "/"


def _tree(files):
    """The file list as fresh inode entries in table order, or a refusal."""
    if isinstance(files, bool) or not isinstance(files, (list, tuple)):
        raise FsError("a file list is a list of entries, not %s"
                      % (type(files).__name__,))
    if not files:
        raise FsError("an empty tree has no root")
    out = []
    seen = {}
    for index, entry in enumerate(files):
        if not isinstance(entry, (list, tuple)) or len(entry) != 5:
            raise FsError("entry %d is not (path, kind, mode, uid, content): %r"
                          % (index, entry))
        path, kind, mode, uid, content = entry
        if not isinstance(path, str) or not path.startswith("/"):
            raise FsError("entry %d has the path %r, and a path is absolute"
                          % (index, path))
        if path != "/" and len(_name_of(path)) > NAMES_MAX:
            raise FsError("the name %r is longer than %d bytes"
                          % (_name_of(path), NAMES_MAX))
        if kind not in ("file", "dir"):
            raise FsError("entry %d is a %r, and a kind is \"file\" or \"dir\""
                          % (index, kind))
        if kind == "dir" and content:
            raise FsError("the directory %r carries content" % (path,))
        if path in seen:
            raise FsError("the path %r appears twice (inodes %d and %d)"
                          % (path, seen[path], index))
        if path != "/" and _parent_of(path) not in seen:
            raise FsError("the path %r comes before its parent %r"
                          % (path, _parent_of(path)))
        seen[path] = index
        out.append({"ino": index, "path": path, "kind": kind, "mode": mode,
                    "uid": uid, "size": len(content), "content": bytes(content),
                    "blocks": ()})
    root = out[0]
    if root["path"] != "/" or root["kind"] != "dir":
        raise FsError("the first entry is %r and a table starts at its root "
                      "directory" % (root["path"],))
    return out


def _plan(entries, geom):
    """Lay every file's data out in the data region, in table order."""
    next_free = geom["data_start"]
    for entry in entries:
        if entry["kind"] == "dir":
            entry["blocks"] = (geom["dir_start"] + entry["ino"],)
            continue
        need = (entry["size"] + _USABLE - 1) // _USABLE
        if need > _MAX_BLOCKS:
            raise FsError("the file %r needs %d sectors and an inode names %d"
                          % (entry["path"], need, _MAX_BLOCKS))
        if next_free + need > geom["data_start"] + geom["n_data"]:
            raise FsError("the tree needs %d data sectors past %d and the disk "
                          "has %d" % (next_free + need - geom["data_start"],
                                      geom["n_data"], geom["n_data"]))
        entry["blocks"] = tuple(range(next_free, next_free + need))
        next_free += need
    return next_free


def _inode_payload(entry):
    payload = bytearray(_USABLE)
    payload[0] = {"free": _FREE, "file": _FILE, "dir": _DIR}[entry["kind"]]
    _put(payload, 1, 2, entry["mode"])
    _put(payload, 3, 2, entry["uid"])
    _put(payload, 5, 4, entry["size"])
    payload[9] = len(entry["blocks"])
    for slot, block in enumerate(entry["blocks"]):
        _put(payload, 10 + 2 * slot, 2, block)
    return payload


def _decode_inode(ino, payload):
    blocks = tuple(_get(payload, 10 + 2 * slot, 2)
                   for slot in range(payload[9]))
    return {"ino": ino, "kind": _KINDS.get(payload[0], "free"),
            "mode": _get(payload, 1, 2), "uid": _get(payload, 3, 2),
            "size": _get(payload, 5, 4), "blocks": blocks}


def _dir_names(payload):
    """The (name, ino) pairs of a directory sector, in order, empty slots gone."""
    pairs = []
    for slot in range(_MAX_ENTRIES):
        offset = slot * _ENTRY_BYTES
        ino = _get(payload, offset, 2)
        raw = bytes(payload[offset + 2:offset + _ENTRY_BYTES])
        name = raw.split(b"\0", 1)[0].decode("utf-8", "replace")
        if ino or name:
            pairs.append((name, ino))
    return tuple(pairs)


def _super_payload(geom):
    payload = bytearray(_USABLE)
    _put(payload, 0, 4, geom["magic"])
    _put(payload, 4, 4, geom["version"])
    _put(payload, 8, 2, geom["inodes_start"])
    _put(payload, 10, 2, geom["n_inodes"])
    _put(payload, 12, 2, geom["data_start"])
    _put(payload, 14, 2, geom["n_data"])
    _put(payload, 16, 2, geom["root_ino"])
    _put(payload, 18, 2, geom["free_map_sector"])
    return payload


def _decode_super(payload, sectors):
    inodes_start = _get(payload, 8, 2)
    n_inodes = _get(payload, 10, 2)
    data_start = _get(payload, 12, 2)
    n_data = _get(payload, 14, 2)
    dir_start = inodes_start + n_inodes
    return {"magic": _get(payload, 0, 4), "version": _get(payload, 4, 4),
            "sector": SECTOR, "sectors": sectors, "inodes_start": inodes_start,
            "n_inodes": n_inodes, "dir_start": dir_start,
            "n_dirs": data_start - dir_start, "data_start": data_start,
            "n_data": n_data, "root_ino": _get(payload, 16, 2),
            "free_map_sector": _get(payload, 18, 2)}


def _fits(geom):
    """Whether the superblock's numbers can describe a disk of this size."""
    return (geom["inodes_start"] >= 2 and geom["n_inodes"] >= 1
            and geom["dir_start"] <= geom["data_start"]
            and geom["data_start"] + geom["n_data"] <= geom["sectors"])


def layout(files=userland.FILES, inodes=8, sectors=64):
    """The geometry a disk of `sectors` sectors gets, without touching a disk.

    The inode table holds one inode per entry in `files` even when `inodes`
    asks for fewer, so the frozen default of eight can format the course's own
    nine-entry tree; the directory region then has one sector per inode slot, so
    any inode can become a directory. A tree, a table or a disk that cannot be
    laid out is refused, naming which.
    """
    if isinstance(inodes, bool) or not isinstance(inodes, int) or inodes < 1:
        raise FsError("a table holds at least one inode, not %r" % (inodes,))
    if isinstance(sectors, bool) or not isinstance(sectors, int) or sectors < 1:
        raise FsError("a disk has at least one sector, not %r" % (sectors,))
    entries = _tree(files)
    n_inodes = max(inodes, len(entries))
    inodes_start = 2
    dir_start = inodes_start + n_inodes
    data_start = dir_start + n_inodes
    if data_start >= sectors:
        raise FsError("a table of %d inodes needs %d sectors and the disk has %d"
                      % (n_inodes, data_start + 1, sectors))
    geom = {"magic": MAGIC, "version": FORMAT_VERSION, "sector": SECTOR,
            "sectors": sectors, "inodes_start": inodes_start,
            "n_inodes": n_inodes, "dir_start": dir_start, "n_dirs": n_inodes,
            "data_start": data_start, "n_data": sectors - data_start,
            "root_ino": 0, "free_map_sector": 1}
    _plan(entries, geom)
    return geom


def format_disk(disk, files=userland.FILES, inodes=8):
    """Write the whole filesystem in the one order a power failure survives.

    Data sectors, a barrier, directory sectors, a barrier, inode sectors, a
    barrier, the free map, a barrier, and the superblock **last**, after its own
    barrier. Any prefix of that sequence is unmountable, which is the point: a
    half-written filesystem that mounts is a filesystem that lies.
    """
    if disk.sector_size != SECTOR:
        raise FsError("this format is %d bytes per sector and the disk is %d"
                      % (SECTOR, disk.sector_size))
    geom = layout(files, inodes, disk.sectors)
    entries = _tree(files)
    _plan(entries, geom)
    table = {entry["ino"]: entry for entry in entries}
    used = set()
    for entry in entries:
        for block in entry["blocks"]:
            used.add(block)
    for entry in entries:
        if entry["kind"] != "file":
            continue
        for slot, block in enumerate(entry["blocks"]):
            piece = entry["content"][slot * _USABLE:(slot + 1) * _USABLE]
            payload = bytearray(_USABLE)
            payload[0:len(piece)] = piece
            disk.write(block, _stamp(payload, block))
    disk.barrier()
    for entry in entries:
        if entry["kind"] != "dir":
            continue
        payload = bytearray(_USABLE)
        slot = 0
        for other in entries:
            if other["ino"] == entry["ino"] or _parent_of(other["path"]) != entry["path"]:
                continue
            offset = slot * _ENTRY_BYTES
            _put(payload, offset, 2, other["ino"])
            raw = _name_of(other["path"]).encode("utf-8")
            payload[offset + 2:offset + 2 + len(raw)] = raw
            slot += 1
        sector = geom["dir_start"] + entry["ino"]
        disk.write(sector, _stamp(payload, sector))
    disk.barrier()
    for ino in range(geom["n_inodes"]):
        entry = table.get(ino, {"kind": "free", "mode": 0, "uid": 0, "size": 0,
                               "blocks": ()})
        sector = geom["inodes_start"] + ino
        disk.write(sector, _stamp(_inode_payload(entry), sector))
    disk.barrier()
    bitmap = bytearray(_USABLE)
    for index in range(geom["n_data"]):
        bitmap[index] = 0 if geom["data_start"] + index in used else 1
    disk.write(geom["free_map_sector"], _stamp(bitmap, geom["free_map_sector"]))
    disk.barrier()
    disk.write(0, _stamp(_super_payload(geom), 0))
    disk.barrier()
    return geom


def mount(disk):
    """Read the superblock, or refuse what cannot be mounted, naming it.

    A bad magic, a version this kernel does not know, a checksum that fails (a
    torn superblock), a geometry that does not fit the disk, and a root inode
    that is not a directory are five refusals, and each names its offender.
    """
    payload = _verify(disk.read(0), 0)
    magic = _get(payload, 0, 4)
    if magic != MAGIC:
        raise FsError("the superblock says magic %#x and OSFS is %#x"
                      % (magic, MAGIC))
    version = _get(payload, 4, 4)
    if version != FORMAT_VERSION:
        raise FsError("this filesystem is version %d and this kernel knows %d"
                      % (version, FORMAT_VERSION))
    geom = _decode_super(payload, disk.sectors)
    if not _fits(geom):
        raise FsError("the superblock's geometry does not fit %d sectors: %r"
                      % (disk.sectors, {key: geom[key] for key in _GEOM_KEYS}))
    fs = {"disk": disk, "super": geom, "root_ino": geom["root_ino"]}
    root = _inode_at(fs, geom["root_ino"])
    if root["kind"] != "dir":
        raise FsError("the root inode %d is a %s, and a root is a directory"
                      % (geom["root_ino"], root["kind"]))
    return {"super": geom, "fs": fs}


def _inode_at(fs, ino):
    """One inode, read from its own sector, or a refusal naming the inode."""
    geom = fs["super"]
    if isinstance(ino, bool) or not isinstance(ino, int):
        raise FsError("an inode number is an int, not %r" % (ino,))
    if not 0 <= ino < geom["n_inodes"]:
        raise FsError("inode %d is outside a table of %d"
                      % (ino, geom["n_inodes"]))
    sector = geom["inodes_start"] + ino
    return _decode_inode(ino, _verify(fs["disk"].read(sector), sector))


def _dir_at(fs, ino):
    geom = fs["super"]
    sector = geom["dir_start"] + ino
    return _verify(fs["disk"].read(sector), sector)


def _bitmap(fs):
    geom = fs["super"]
    payload = _verify(fs["disk"].read(geom["free_map_sector"]),
                      geom["free_map_sector"])
    return bytearray(payload[:geom["n_data"]])


def lookup(fs, path):
    """Resolve an absolute path to its inode, one component at a time.

    `.` is skipped and `..` pops the walk's own stack, so a path is never
    rewritten as a string: a name that walked through a directory is a name that
    exists in it. A missing name is refused naming the component and the
    directory it was looked for in, a file in the middle of a path is refused
    naming it, and an empty, relative or over-long name is refused too.
    """
    if not isinstance(path, str) or not path:
        raise FsError("a path is a non-empty string, not %r" % (path,))
    if not path.startswith("/"):
        raise FsError("the path %r is relative, and this filesystem walks "
                      "absolute paths" % (path,))
    geom = fs["super"]
    stack = [geom["root_ino"]]
    parts = []
    for component in path.split("/"):
        if component in ("", "."):
            continue
        if component == "..":
            if len(stack) > 1:
                stack.pop()
                parts.pop()
            continue
        if len(component) > NAMES_MAX:
            raise FsError("the name %r is longer than %d bytes"
                          % (component, NAMES_MAX))
        here = stack[-1]
        node = _inode_at(fs, here)
        if node["kind"] != "dir":
            raise FsError("the path %r walks through %r, which is a %s in the "
                          "middle of a path" % (path, component, node["kind"]))
        pairs = _dir_names(_dir_at(fs, here))
        found = None
        for name, ino in pairs:
            if name == component:
                found = ino
                break
        if found is None:
            where = "/" + "/".join(parts)
            names = tuple(name for name, _ino in pairs)
            near = machine._near(component, names) if names else None
            hint = " (did you mean %r?)" % (near,) if near else ""
            raise FsError("there is no %r in the directory %r%s"
                          % (component, where, hint))
        stack.append(found)
        parts.append(component)
    return _inode_at(fs, stack[-1])


def read_file(fs, ino):
    """The bytes of a file inode, or a refusal naming what it is instead."""
    entry = _inode_at(fs, ino)
    if entry["kind"] == "free":
        raise FsError("inode %d is free" % (ino,))
    if entry["kind"] == "dir":
        raise FsError("inode %d is a directory, and read_file reads files"
                      % (ino,))
    out = bytearray()
    for block in entry["blocks"]:
        out += _verify(fs["disk"].read(block), block)
    return bytes(out[:entry["size"]])


def write_file(fs, ino, data):
    """Write a whole file: its data sectors and free map, then its inode.

    The data and the free map are made durable before the inode is written, so a
    crash between the two barriers leaves the *old* file intact and never a file
    pointing at a sector nobody wrote.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise FsError("a file's bytes are bytes, not %s" % (type(data).__name__,))
    data = bytes(data)
    entry = _inode_at(fs, ino)
    if entry["kind"] == "free":
        raise FsError("inode %d is free" % (ino,))
    if entry["kind"] == "dir":
        raise FsError("inode %d is a directory, and write_file writes files"
                      % (ino,))
    geom = fs["super"]
    disk = fs["disk"]
    need = (len(data) + _USABLE - 1) // _USABLE
    if need > _MAX_BLOCKS:
        raise FsError("a file of %d bytes needs %d sectors and an inode names %d"
                      % (len(data), need, _MAX_BLOCKS))
    bitmap = _bitmap(fs)
    for block in entry["blocks"]:
        bitmap[block - geom["data_start"]] = 1
    chosen = []
    for index in range(geom["n_data"]):
        if bitmap[index] and len(chosen) < need:
            bitmap[index] = 0
            chosen.append(geom["data_start"] + index)
    if len(chosen) < need:
        raise FsError("a file of %d bytes needs %d sectors and the data region "
                      "has %d free" % (len(data), need, len(chosen)))
    for slot, block in enumerate(chosen):
        piece = data[slot * _USABLE:(slot + 1) * _USABLE]
        payload = bytearray(_USABLE)
        payload[0:len(piece)] = piece
        disk.write(block, _stamp(payload, block))
    map_payload = bytearray(_USABLE)
    map_payload[:geom["n_data"]] = bitmap
    disk.write(geom["free_map_sector"],
               _stamp(bytes(map_payload), geom["free_map_sector"]))
    durable = disk.barrier()
    sector = geom["inodes_start"] + ino
    entry["size"] = len(data)
    entry["blocks"] = tuple(chosen)
    disk.write(sector, _stamp(_inode_payload(entry), sector))
    durable += disk.barrier()
    return {"ino": ino, "size": len(data), "blocks": tuple(chosen),
            "durable": durable}


def create(fs, path, kind, mode, uid):
    """Add an entry to a directory, refusing a duplicate name or a full one.

    The inode is written and made durable *before* the directory entry, so a
    crash leaves a free inode and never an entry pointing at one.
    """
    if not isinstance(path, str) or not path.startswith("/") or path == "/":
        raise FsError("a new entry needs an absolute path below the root, not %r"
                      % (path,))
    if kind not in ("file", "dir"):
        raise FsError("%r is not a kind, and a kind is \"file\" or \"dir\""
                      % (kind,))
    name = _name_of(path)
    if len(name) > NAMES_MAX:
        raise FsError("the name %r is longer than %d bytes" % (name, NAMES_MAX))
    parent_path = _parent_of(path)
    parent = lookup(fs, parent_path)
    if parent["kind"] != "dir":
        raise FsError("%r is a %s, and an entry goes in a directory"
                      % (parent_path, parent["kind"]))
    geom = fs["super"]
    disk = fs["disk"]
    payload = bytearray(_dir_at(fs, parent["ino"]))
    pairs = _dir_names(payload)
    for present, _ino in pairs:
        if present == name:
            raise FsError("the directory %r already has %r" % (parent_path, name))
    if len(pairs) >= _MAX_ENTRIES:
        raise FsError("the directory %r is full at %d entries"
                      % (parent_path, len(pairs)))
    ino = None
    for candidate in range(geom["n_inodes"]):
        if _inode_at(fs, candidate)["kind"] == "free":
            ino = candidate
            break
    if ino is None:
        raise FsError("the inode table is full at %d inodes" % (geom["n_inodes"],))
    entry = {"ino": ino, "kind": kind, "mode": mode, "uid": uid, "size": 0,
             "blocks": ()}
    if kind == "dir":
        entry["blocks"] = (geom["dir_start"] + ino,)
        sector = geom["dir_start"] + ino
        disk.write(sector, _stamp(bytearray(_USABLE), sector))
    sector = geom["inodes_start"] + ino
    disk.write(sector, _stamp(_inode_payload(entry), sector))
    disk.barrier()
    offset = len(pairs) * _ENTRY_BYTES
    _put(payload, offset, 2, ino)
    raw = name.encode("utf-8")
    payload[offset + 2:offset + 2 + len(raw)] = raw
    parent_sector = geom["dir_start"] + parent["ino"]
    disk.write(parent_sector, _stamp(payload, parent_sector))
    disk.barrier()
    return entry


def sync(fs):
    """Make every buffered write durable, and say how many became so."""
    return fs["disk"].barrier()


def fsck(disk):
    """Every inconsistency the image can be shown to have, as words.

    A bad checksum, an inode whose blocks leave its region, a block two inodes
    claim, a block an inode claims that the free map calls free, a directory
    entry naming an inode outside the table or a free one, a size that does not
    match a file's block count, and a root that is not a directory.
    """
    problems = []

    def note(word):
        if word not in problems:
            problems.append(word)

    try:
        payload = _verify(disk.read(0), 0)
    except FsError:
        return {"ok": False, "problems": ("bad_checksum",)}
    if _get(payload, 0, 4) != MAGIC:
        return {"ok": False, "problems": ("bad_magic",)}
    if _get(payload, 4, 4) != FORMAT_VERSION:
        note("bad_version")
    geom = _decode_super(payload, disk.sectors)
    if not _fits(geom):
        note("bad_geometry")
        return {"ok": False, "problems": tuple(problems)}

    def sector_of(index):
        try:
            return _verify(disk.read(index), index)
        except FsError:
            note("bad_checksum")
            return None

    table = {}
    for ino in range(geom["n_inodes"]):
        raw = sector_of(geom["inodes_start"] + ino)
        table[ino] = _decode_inode(ino, raw) if raw else None
    root = table.get(geom["root_ino"])
    if root is None or root["kind"] != "dir":
        note("root_not_directory")
    if sector_of(geom["free_map_sector"]) is None:
        bitmap = None
    else:
        bitmap = bytearray(_verify(disk.read(geom["free_map_sector"]),
                                   geom["free_map_sector"])[:geom["n_data"]])
    claimed = {}
    for ino in range(geom["n_inodes"]):
        entry = table[ino]
        if entry is None or entry["kind"] == "free":
            continue
        for block in entry["blocks"]:
            if block in claimed:
                note("block_shared")
            else:
                claimed[block] = ino
            if entry["kind"] == "dir":
                inside = geom["dir_start"] <= block < geom["data_start"]
            else:
                inside = geom["data_start"] <= block < geom["data_start"] + geom["n_data"]
            if not inside:
                note("block_out_of_range")
                continue
            if entry["kind"] == "file" and sector_of(block) is None:
                continue
            if bitmap is not None and entry["kind"] == "file" \
                    and bitmap[block - geom["data_start"]]:
                note("block_marked_free")
        if entry["kind"] == "file":
            need = (entry["size"] + _USABLE - 1) // _USABLE
            if need != len(entry["blocks"]):
                note("size_mismatch")
    for ino in range(geom["n_inodes"]):
        entry = table[ino]
        if entry is None or entry["kind"] != "dir":
            continue
        for block in entry["blocks"]:
            if not geom["dir_start"] <= block < geom["data_start"]:
                continue
            payload = sector_of(block)
            if payload is None:
                continue
            for name, child in _dir_names(payload):
                if child >= geom["n_inodes"]:
                    note("entry_out_of_range")
                elif table[child] is None or table[child]["kind"] == "free":
                    note("entry_not_allocated")
    return {"ok": not problems, "problems": tuple(problems)}
