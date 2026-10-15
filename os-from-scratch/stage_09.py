"""OS From Scratch — stage 9: The format, and the write that was not ordered.

`Disk.write` puts bytes in a buffer and `Disk.read` answers with the durable
image, so a write is not a fact until a barrier. A whole year of real filesystem
bugs is that sentence, and this stage is the one where it stops being a footnote:
every sector of `OSFS` is written in an order chosen so that *any prefix* of the
writes is either a filesystem somebody can still mount, or one nobody can.

The format is `OSFS`, version 1, one sector each: the superblock, the data
sector's free bitmap, the inode table, one directory sector per inode slot, and
the file data in whole sectors. Every sector the format owns ends with a 4-byte
checksum over its own bytes mixed with its own sector index, so a torn sector is
*detected* rather than trusted. The superblock is written **last**, after a
barrier of its own: an interrupted format therefore leaves no valid superblock and
`mount` refuses it, which is a better outcome than mounting a half-written tree.

    MAGIC, FORMAT_VERSION, NAMES_MAX   the format's frozen vocabulary
    PROBLEMS                           the closed words fsck may say
    checksum                           the sum a sector carries, mixed with its index
    layout                             the geometry of a tree, without a disk
    format_disk                        the tree on a disk, in the survivable order
    mount                              the superblock read back, or a refusal
    lookup                             a path resolved component by component
    read_file                          a file's bytes, never a directory's
    write_file                         data and map first, the inode after
    create                             a new entry in a directory, its inode first
    sync                               a barrier, and how many sectors it made durable
    fsck                               every inconsistency the image can be shown to have

`FsError` is the family every refusal in this stage belongs to, and it names its
offender: the sector that failed its checksum, the path that is relative, the
component that is not in the directory, the inode that is a directory, the block
that is outside its region.

DESIGN DECISION — why is the superblock written last, after its own barrier?
Because the superblock is the one sector that says "there is a filesystem here",
and it is the only sector whose presence is a *claim about the other sectors*. If
it is written first, a power failure between it and the data leaves a mountable
filesystem that points at sectors nobody wrote — the worst of all outcomes,
because it mounts. Writing it last makes every earlier prefix unmountable, and the
check reads that fact out of `Disk.log()` rather than taking this stage's word.

DESIGN DECISION — why does every sector carry a checksum mixed with its own
index?
A tear is not a lost write, it is half of one: the device keeps the first half of
the new sector and the rest of the old one. A sum over the sector's own bytes
catches that, and mixing in the sector index means a sector copied to another
offset — the other classic failure — is caught too, because its checksum belongs
to the place it came from. A checksum that is not mixed with the index accepts a
sector that arrived from somewhere else, which is exactly the mistake the index
is there to refuse.

DESIGN DECISION — why is the data written and barriered *before* the inode?
An inode names the sectors its file lives in. If the inode lands first and the
crash happens before the data, the filesystem has a file pointing at a sector
nobody ever wrote — a read of it returns whatever the sector happens to hold, and
a filesystem that returns data nobody wrote is worse than one that returns
nothing. Data first, then the free map, then the inode: a crash between the two
barriers leaves the *old* file intact and leaks at most the new blocks, and a leak
is something `fsck` can name.

DESIGN DECISION — why is there a directory sector per *inode slot* rather than
one per directory?
Because a directory's sector is where its entries live, and an inode that becomes
a directory at runtime — which is what `create` does — needs a sector that was
reserved before anybody knew it would. Laying out `n_inodes` directory sectors
makes every inode able to be a directory, makes `create` a pure allocation, and
makes the geometry a function of the table size alone, which is why `layout` can
compute it from the tree without touching a disk.

DESIGN DECISION — why does `..` pop the walk instead of being rewritten away?
A path is a walk, not a string. `os.path`-style surgery removes the component
before `..` *without ever looking it up*, so `/nope/../etc` silently resolves to
`/etc` — a path that names something that does not exist, treated as if it did.
Popping the stack the walk itself built can only undo a descent that really
happened, and the fixture that tells the two apart is a path whose middle
component is missing.

DESIGN DECISION — why is an inconsistency a *word* while a caller's mistake is a
refusal?
The two are not the same kind of error. A caller that asks for a relative path,
or reads a directory, has made a mistake the kernel cannot absorb, and raising
names it. An image with a torn sector is a *decision* — mount it and lie, or
refuse it — and a decision that arrives as an exception cannot be reported to
anybody, which is why `fsck` answers with a closed vocabulary of words and an
`ok` flag instead.

TODO: implement `checksum`, `layout`, `format_disk`, `mount`, `lookup`,
`read_file`, `write_file`, `create`, `sync` and `fsck`.
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


class FsError(ValueError):
    """Anything a caller of this filesystem got wrong."""


def checksum(data, index):
    """The 4-byte sum of `data`, mixed with the index of the sector it lands in.

    Refuses a sector index that is not a non-negative int, naming it. The index
    is mixed in first so that the same bytes at two offsets carry two sums.
    """
    raise NotImplementedError("stage 9: implement checksum()")



def layout(files=userland.FILES, inodes=8, sectors=64):
    """The geometry a disk of `sectors` sectors gets, without touching a disk.

    The inode table is at least as large as `inodes` and always large enough for
    one inode per entry in `files`; the directory region has one sector per inode
    slot; the inode table starts at sector 2 and the free map is sector 1. A tree
    that cannot be laid out — a relative path, a duplicate, a child before its
    parent, an unknown kind, a directory with content, an over-long name, a file
    too big for an inode — is refused naming the entry.
    """
    raise NotImplementedError("stage 9: implement layout()")



def format_disk(disk, files=userland.FILES, inodes=8):
    """Write the whole filesystem, in the one order a power failure survives.

    Data sectors, a barrier, directory sectors, a barrier, inode sectors, a
    barrier, the free map, a barrier, the superblock, a barrier. Returns exactly
    the geometry `layout` computed for the same tree and disk.
    """
    raise NotImplementedError("stage 9: implement format_disk()")



def mount(disk):
    """The superblock read back, or a refusal naming what cannot be mounted.

    A bad magic, a version this kernel does not know, a checksum that fails, a
    geometry that does not fit the disk and a root inode that is not a directory
    are the five refusals; the answer is `{"super": geometry, "fs": fs}` and the
    `fs` is what every other function of this stage takes.
    """
    raise NotImplementedError("stage 9: implement mount()")



def lookup(fs, path):
    """Resolve an absolute path to its inode, one component at a time.

    `.` is skipped and `..` pops the walk's own stack, so a name a path walked
    through is a name that exists in that directory. An empty or relative path,
    an over-long name, a missing component and a file in the middle of a path are
    each refused naming the offender.
    """
    raise NotImplementedError("stage 9: implement lookup()")



def read_file(fs, ino):
    """The bytes of a file inode, or a refusal naming what it is instead.

    A directory and a free inode are both refused by name: a read of either is a
    reader that does not know what it is reading.
    """
    raise NotImplementedError("stage 9: implement read_file()")



def write_file(fs, ino, data):
    """Write a whole file, its data and its free map first and its inode after.

    Returns `{"ino", "size", "blocks", "durable"}`. A file too large for an
    inode's block count, or for the data region left on the disk, is refused
    naming the numbers; a directory and a free inode are refused by name.
    """
    raise NotImplementedError("stage 9: implement write_file()")



def create(fs, path, kind, mode, uid):
    """Add an entry to a directory, writing the inode before the entry.

    Refuses a duplicate name and a directory with no room left, naming both the
    name and the directory; refuses a relative path, an unknown kind and an
    over-long name by name.
    """
    raise NotImplementedError("stage 9: implement create()")



def sync(fs):
    """Barrier the device and answer how many sectors that made durable."""
    raise NotImplementedError("stage 9: implement sync()")



def fsck(disk):
    """Read the durable image and report every inconsistency it can name.

    Answers `{"ok": bool, "problems": (words,)}` with the words of `PROBLEMS`: a
    checksum that fails, a magic that is not `OSFS`, an unknown version, a
    geometry that does not fit, an inode whose blocks leave its region, a block
    two inodes claim, a block the free map calls free, a directory entry naming
    an inode outside the table or a free one, a size that does not match a file's
    block count, and a root that is not a directory.
    """
    raise NotImplementedError("stage 9: implement fsck()")
