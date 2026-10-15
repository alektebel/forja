# Phase 06 — Storage: Block Devices, VFS, Filesystems, Crash Consistency

**14 exercises.** Persistence, and the fact that the machine can lose power in
the middle of anything you do.

---

## The failure that got you here

Everything your kernel knows dies at reboot. Programs come from an initrd you
baked into the image; there is nowhere to *put* anything. And your phase-03
swap-out path has no device to swap to.

But the real difficulty is not reading and writing blocks. It is this: a disk
guarantees that a single sector write is atomic, and guarantees nothing whatsoever
about the order or completion of any two. **Every filesystem is a scheme for
building a consistent structure out of a device that can stop, at any instant,
between any two writes.**

---

## Design decisions

> **DESIGN DECISION — which block device driver first?**
> ATA PIO is 40 lines, works on everything, and moves data through the CPU one
> 16-bit word at a time. virtio-blk is a queue in shared memory, fast, and only
> exists under a hypervisor. AHCI is what real hardware has and is a substantial
> specification.
> **Chosen:** ATA PIO (06.1) to get bytes moving, virtio-blk (06.2) once you want
> them to move quickly, AHCI noted and deferred to phase 12. Cost: ATA PIO is
> effectively obsolete. Benefit: it is the only storage interface you can fully
> understand in one sitting, and it makes the *cost* of PIO viscerally clear
> when you measure it against virtio.

> **DESIGN DECISION — write your own filesystem, or implement ext2?**
> Your own means you design the on-disk layout and meet every trade-off yourself.
> ext2 means your files are readable by Linux, `dumpe2fs` becomes a debugger, and
> you get a specification to be wrong about.
> **Chosen:** your own first (06.6–06.8), ext2 second (06.9). The second is much
> easier after the first, and the ability to mount your image on Linux and see
> your files is worth a great deal when the alternative is a hex editor.

> **DESIGN DECISION — journaling or soft updates?**
> Journaling writes everything twice and is comparatively simple to reason about.
> Soft updates never write twice and require a dependency-tracking scheme that is
> famously hard `[P-SOFTUPD94]`.
> **Chosen:** journaling (06.11), with `[P-JOURNVS00]` read afterwards so you know
> what the alternative bought and cost. Cost: half your write bandwidth, which
> you will measure.

---

## The exercises

### 06.1 — ATA PIO: bytes off a disk
**Build:** identify the drive, LBA28/LBA48 read and write of sectors, status
polling, error handling.
**Limit case:** poll the status register in a tight loop and measure throughput.
Then compute how many CPU cycles you spent per byte. This number is why DMA
exists, and you should have it before anyone tells you so. Also handle the drive
being absent — the float-return-0xFF case, which otherwise presents as a drive
full of `0xFF`.
**Done when:** a sector written and read back matches, and you have printed
MiB/s and cycles-per-byte.
**Read:** `[OSDEV]` ATA PIO Mode, ATA read/write sectors; `[ATA]` §7 (command
descriptions); `[LDD3]` ch. 16 (Block Drivers).

### 06.2 — virtio-blk, and what a queue buys
**Build:** virtqueue setup (descriptor table, available ring, used ring), feature
negotiation, request submission, and completion by interrupt.
**Limit case:** submit one request and wait, then submit 32 and wait for all.
Measure both. The gap is queue depth — the difference between latency-bound and
throughput-bound I/O, and the reason every storage stack since 1990 is
asynchronous. Then handle the used-ring wrap and the notification-suppression
flags, which are where virtio implementations usually break.
**Done when:** throughput is an order of magnitude above 06.1's, and deep queues
beat shallow ones by a measured factor.
**Read:** `[VIRTIO]` §2.7 (Split Virtqueues) and §5.2 (Block Device);
`[P-VIRTIO08]`; `[OSDEV]` Virtio.

### 06.3 — A block layer
**Build:** a device-independent block interface: `submit_bio`-style requests,
completion callbacks, a request queue with merging of adjacent requests, and a
simple elevator.
**Limit case:** issue 1000 random single-sector reads, then the same 1000 sorted
and merged. Measure both on a simulated seeking device. Sorting is worth an order
of magnitude on rotational media and roughly nothing on an SSD — so your elevator
must be a *policy*, selectable, not a law. That realisation is why Linux has
`noop`, `deadline`, `bfq` and `mq-deadline` rather than one scheduler.
**Done when:** merging is observable in your statistics, and you can print
requests-issued versus requests-submitted.
**Read:** `[LKD3]` ch. 14 (The Block I/O Layer) in full; `[LDD3]` ch. 16;
`[KDOC]` `Documentation/block/`.

### 06.4 — A buffer cache
**Build:** a cache of disk blocks keyed by (device, block), with dirty tracking,
pinning, an LRU list, and writeback.
**Limit case:** two callers reading the same block must get the *same* buffer, or
one's modification vanishes when the other writes back. Construct that loss.
Then: a dirty buffer whose device is unplugged, and a writeback that fails —
decide what happens, because "nothing" means silent data loss.
**Done when:** identity is guaranteed per block, and you can print hit rate, dirty
count, and writeback throughput.
**Read:** `[BACH]` ch. 3 (The Buffer Cache) — this chapter is precisely this
exercise; `[XV6]` ch. 8 (`bio.c`); `[UTLK]` ch. 15.

### 06.5 — Ordering, barriers, and the lying disk
**Build:** `flush()` / FUA support, and an explicit ordering primitive your
filesystem can rely on.
**Limit case:** the disk has a volatile write cache and reports completion when
the bytes are in *its* RAM. Write A, write B, lose power: you may find B without
A. Your journal in 06.11 is worthless without a real barrier. Demonstrate the
reordering with a simulated cache, then show the flush preventing it — and
measure what the flush costs, because that cost is why everyone is tempted to
skip it.
**Done when:** you can show ordering violated without the barrier and preserved
with it, plus the throughput penalty.
**Read:** `[P-IRONFS05]` — the paper about disks not doing what they said;
`[KDOC]` `Documentation/block/writeback_cache_control.rst`; `[P-PILLAI14]`.

### 06.6 — Design your on-disk format
**Build:** a written specification, before any code: superblock, inode layout,
block allocation strategy, directory format, and the exact byte offsets.
**Limit case:** answer four questions in the document. (a) Maximum file size —
derive it from your inode's block pointers. (b) Maximum filename length, and what
happens at length+1. (c) Where free-space information lives, and what it costs to
find a free block. (d) What is inconsistent, and for how long, if power fails
between any two of your writes. Question (d) is the one that matters.
**Done when:** the spec exists, is version-stamped with a magic number, and
answers all four.
**Read:** `[P-FFS84]` — read this before designing, it is the canonical
argument about layout and locality; `[BACH]` ch. 4; `[OSTEP]` ch. 40 (File System
Implementation).

### 06.7 — Implement it: read path
**Build:** mount, superblock validation, inode lookup, path resolution, block
mapping, `read`, and directory listing.
**Limit case:** path resolution across `.`, `..`, a symlink loop, and a path
longer than any buffer you allocated. The symlink loop must terminate — pick a
limit and enforce it, because the alternative is a kernel hang from a userspace
`ln -s`. Also: resolving `..` out of the root must stay at the root.
**Done when:** you can `cat` a file placed there by a host-side image builder, and
a symlink loop returns `ELOOP`.
**Read:** `[XV6]` ch. 8; `[UTLK]` ch. 12 (The Virtual Filesystem), path lookup;
`[TLPI]` ch. 18.

### 06.8 — Implement it: write path
**Build:** block allocation, inode allocation, `write`, `create`, `unlink`,
`mkdir`, truncate, and free-space accounting.
**Limit case:** `unlink` on a file that is still open. Unix semantics say the name
disappears and the data survives until the last descriptor closes — so the inode
needs a link count *and* an open count, and deletion happens on neither alone.
Build it, then use it: write to a file you have already unlinked, and read it
back. This is how every temp file in Unix works.
**Done when:** a full create/write/read/delete cycle leaves free-block counts
exactly where they started, and the unlinked-but-open case works.
**Read:** `[BACH]` ch. 4 (inode assignment, block allocation); `[TLPI]` ch. 18
(`unlink` semantics); `[OSTEP]` ch. 39–40.

### 06.9 — A VFS layer
**Build:** the abstraction — `superblock`, `inode`, `dentry`, `file` with
operation tables — then port your filesystem behind it and mount two filesystem
types at once.
**Limit case:** a mount point. A lookup crossing into a mounted filesystem must
switch to a different superblock mid-path, and `..` from a mount root must escape
upward into the parent filesystem. Then: unmount with a file still open, which
must fail with `EBUSY` rather than free the superblock.
**Done when:** two different filesystem implementations are mounted
simultaneously, paths cross between them, and busy unmount is refused.
**Read:** `[P-VNODE86]` — the original design, and still the clearest statement of
why the layer exists; `[LKD3]` ch. 13; `[UTLK]` ch. 12; `[FBSD]` ch. 7.

### 06.10 — ext2, and a filesystem Linux can read
**Build:** an ext2 driver — block groups, the group descriptor table, inode
bitmaps, indirect blocks (single, double, triple), and directory entries.
**Limit case:** the triple-indirect block. Compute the file offset at which each
level engages, then create a file that crosses each boundary and verify against
Linux's own reader. Then mount your image with `mount -o loop` on a real Linux
box and run `fsck.ext2` on it. Its complaints are your bug list, written by
someone else.
**Done when:** Linux mounts an image your kernel created, `fsck` reports it clean,
and your kernel reads a file `mkfs.ext2` created.
**Read:** `[P-EXT2]`; Poirier, D., *The Second Extended File System: Internal
Layout* **(free)**; `[UTLK]` ch. 18.

### 06.11 — A journal
**Build:** write-ahead logging for metadata: transaction begin/commit, log
records, checkpointing, and replay at mount.
**Limit case:** crash at every point. Instrument your code to abort after the
Nth block write, then sweep N from 1 to the length of an operation, rebooting and
replaying each time. Every N must yield a consistent filesystem. This sweep is
the exercise; a journal tested only on clean shutdown is decoration. Then measure
the write amplification you have just accepted.
**Done when:** the full crash sweep passes `fsck` at every N, and you can state
your journaling mode (metadata-only vs full-data) and what it does not protect.
**Read:** `[P-CEDAR87]`; `[P-EXT3]`; `[OSTEP]` ch. 42 (Crash Consistency: FSCK
and Journaling) — it constructs this exact sweep; `[P-JOURNVS00]` afterwards.

### 06.12 — The page cache, and unifying it with the buffer cache
**Build:** a cache of file pages keyed by (inode, offset), readahead on
sequential access, and writeback by a flusher task.
**Limit case:** you now have two caches for the same bytes — 06.4's buffer cache
and this one. A write through one and a read through the other will disagree.
Unify them or define the coherence rule; Linux unified them, and this is why.
Then: sequential read with and without readahead, measured.
**Done when:** coherence is guaranteed by construction, and readahead shows a
measured speedup on sequential reads and no penalty on random.
**Read:** `[LKD3]` ch. 16 (The Page Cache and Page Writeback); `[GORMAN]` ch. 10;
`[UTLK]` ch. 15–16.

### 06.13 — `mmap`
**Build:** file-backed mappings — shared and private — via demand paging into the
page cache, with `msync` and correct `MAP_PRIVATE` copy-on-write.
**Limit case:** `MAP_SHARED` between two processes, where a write through one
mapping must be visible through the other *and* eventually on disk; and
`MAP_PRIVATE`, where it must be visible through neither. Same mechanism, opposite
answers, one flag apart. Then: mapping past end-of-file, which must `SIGBUS`
rather than extend.
**Done when:** shared and private mappings behave differently and correctly, and
`mmap` reads reach the same page-cache pages `read` does.
**Read:** `[TLPI]` ch. 49 in full; `[UTLK]` ch. 16; `[LDD3]` ch. 15.

### 06.14 — Measure the storage stack
**Build:** benchmarks for sequential/random read/write at several queue depths,
cache hit rate, and the journal's write amplification.
**Limit case:** predict every number before printing it. Then run the same
benchmark against Linux on the same virtual disk and account for each difference.
Where you are 10× slower, name the mechanism — no readahead? synchronous journal
commits? no request merging? A number you cannot attribute is a subsystem you do
not understand.
**Done when:** you have the table, the comparison, and an explanation per row.
**Read:** `[P-FFS84]` §Performance for the original of exactly this table;
`[HP6]` App. D on storage; `fio`'s documentation for what the standard workloads
are and why.

---

## Where this phase stops

- **No RAID, no LVM, no device mapper.** One device, one filesystem.
- **No log-structured or copy-on-write filesystem.** `[P-LFS92]` and `[P-BTRFS13]`
  are the reading if you want the other tradition — where the journal *is* the
  filesystem.
- **No extents, no B-trees.** ext2's indirect blocks are what you implement; ext4
  extents and btrfs B-trees are the modern answer to the same problem.
- **No `fsck` of your own.** You lean on `fsck.ext2` in 06.10. Writing a checker
  for your own format in 06.6 is an excellent optional exercise.
- **No quotas, no ACLs, no extended attributes.** Permissions arrive in phase 10.
- **No network filesystems.** NFS needs phase 09 and is a project of its own.

---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
