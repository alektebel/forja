# OS From Scratch

Build the kernel that runs on a machine you did not write. `machine.py` is
provided complete: RAM as 256 frames of 4096 bytes, a real two-level page walk
with the four permission bits, a TLB that only `MMU.invalidate` empties, traps
carrying the x86-shaped error bits, a `Timer`, and the six boot maps — including
the ones where the firmware lies. `devices.py` is provided complete: a console
that keeps every byte it was handed, and a disk whose writes are buffered,
whole-sector, and durable only at a `barrier`, with `power_fail(tear=True)` as
the fixture a filesystem exists to survive. `userland.py` is provided complete:
the programs as scripts of ops, the closed op vocabulary, the filesystem tree
the course's formatter is asked to build, and what a shell would type.

What is *not* here is the kernel. An operating system is what you write after
the hardware breaks your last promise: the map you were handed is not a map
until you have validated it, a map with no allocator cannot be used twice, an
address space you never invalidate serves the translation you removed, a fault
with nowhere to go kills the kernel, a syscall that trusts a user pointer
dereferences anything, a process that forgets one frame leaks it forever, a task
that checks a condition and then sleeps loses a wakeup, two CPUs in one critical
section lose an update, a write that was not ordered is a write that never
happened, and a userland is the only thing that ever proves any of it. This is
the other half of `cpu-from-scratch/`, which builds a machine that stops on a
fault and has no supervisor mode — the machine this kernel is asked to run on.

Every one of the failures below is a check here, and every one of them is easy to
make and hard to notice:

- a region ending at `0x80000` counted as owning frame 128 (`end // PAGE_SIZE`)
  where `[start, end)` means `(end - 1) // PAGE_SIZE`, so every region owns one
  frame too many and the extra frame is the next region's first;
- `usable_frames` handing out a `kernel`, `boot_info` or `firmware` frame, or
  filling the gap between two usable regions — a gap a firmware makes by marking
  a hole `reserved` and *ending* the usable region there, which is why the frames
  in between belong to nobody;
- an overlap refused without naming both regions and the frames they share, an
  unknown kind refused without the suggestion within edit distance 2 (or a
  suggestion offered for a kind nowhere near a real one), an unaligned end
  rounded instead of refused;
- `validate` handing back the caller's own dicts, so one check's edit of the
  answer edits the fixture the next check reads; a map refused for being
  unsorted instead of sorted; a map that does not reach the end of the machine
  accepted;
- `summary` missing a kind that has no frames, reporting `frames` as the map's
  total instead of the machine's 256, or a hole count that disagrees with
  `holes()`; `holes` counting a frame a region claims, or coming back
  unsorted;
- a bitmap kept in a Python list beside the pool: `bits()` agrees with the
  allocator to the last bit and RAM says otherwise, which is a record the next
  boot cannot read;
- the bitmap handed out as a normal frame, the bitmap's own frame counted as
  free, or the bitmap's frame left unzeroed so a fresh pool starts out holding
  whoever used that frame last;
- the byte/bit split written the wrong way round — `% 8` for the byte and `// 8`
  for the bit — or the frame's *number* used as its position in the pool, so a
  frame is lost as soon as the pool is not contiguous: the clean map leaves 175
  handable frames out of the machine's 256, and it leaves them as `0..127` and
  `193..239`, not as one range;
- an `alloc(5)` that hands back the four frames the pool had: a refusal that
  leaves half a grant behind, so the caller writes past the end of what it got
  and the pool is short frames nobody notices are gone;
- `free` accepting a double free, a frame it never handed out, or the bitmap's
  own frame, and `state` raising at a frame the pool does not hold instead of
  answering `outside` (a negative frame and a frame past the machine are outside
  too); `alloc` descending or returning duplicates; `free_count`
  that forgets the bitmap; a reserved frame whose bit is set by somebody; a fresh
  pool whose bitmap is not all free whatever the frame held;
- `map_page` writing the mirror and not the tables, or the tables and not the
  mirror, so the kernel believes one translation and the machine walks another
  (and the entry, `(frame << 4) | flags`, is written as if it were a frame
  number);
- a second-level table taken from the pool and not zeroed, so a later walk reads
  entries nobody installed, or entered under the wrong first-level index, or not
  counted in the space at all so `free_space` leaks it;
- `unmap_page` and `protect` changing the tables and not invalidating: the
  entries are gone and `MMU.translate` still answers out of the TLB, with no
  walk, no fault and no sign that anything changed, which `MMU.log()`'s `hits`
  and `cached` are the world's record of;
- `unmap_page` freeing the frame the caller owns (the classic unmap-then-fault
  that hands one frame to two owners), or dropping the table it just emptied so
  the next mapping allocates a second one;
- a page mapped without `PRESENT`, a caller's `PRESENT` bit accepted, an unknown
  flag bit accepted, `WRITE | EXEC` accepted, and a `protect` that reports new
  flags the walk never sees, so the kernel cannot write the page it just made
  writable;
- `space_frames` missing the root or a table; `free_space` leaving frames in the
  pool's hands or translations in the TLB; a `vaddr` at or past `ADDRESS_WIDTH`
  (two levels of 512 entries over pages of 4096 bytes) mapped anyway, because the
  walk reads whatever entries sit next to a table rather than refusing a virtual
  page outside the space;
- the user bit treated as a *reason*, so a page fault with the user bit clear is
  demand-paged for the kernel and a kernel bug silently allocates a page;
- `read_only` and `protected` swapped, or `decode` reading `PageFault.reason`
  instead of the three error bits a handler is allowed to read — the machine's
  five reasons have to collapse onto the handler's three, and the user bit is
  context, never one of them;
- a handler installed for the double fault (vector 8), for a vector this machine
  does not have, or twice over; `in_handler` ignored, so a fault inside a handler
  is resolved a second time instead of panicking; a vector this machine does not
  have named as anything but `unknown`;
- a resolved page fault mapped without `WRITE`, at the vpage of the walk's
  choosing rather than the faulting one, or with the table written where the walk
  looks and the mirror left behind;
- the pool refusing mid-resolution and the refusal travelling out of `handle` as
  an exception while the frames already taken for the mapping in progress are
  neither mapped nor counted, instead of a panic with cause `out_of_memory`;
- the timer (vector 32) routed to a panic instead of the honest
  `unhandled_irq`; a user exception with no handler panicked where the kernel
  has a supervisor that can kill the task;
- a refused fault that still took a frame or installed an entry; a panic record
  missing its cause, naming the handler that was never installed, or naming no
  handler when there was none;
- `user_range` checking the first page and assuming the rest, so a range whose
  last page is unmapped has its bytes read out of the next frame — or the access
  not checked (a write into a read-only page succeeds), or the user bit not
  checked (a supervisor page served to a user);
- a negative address, a bool, or an address at `ADDRESS_WIDTH` treated as a
  range, because this walk does not refuse a virtual page outside the space;
- the length checked and the pointer not, the pointer dereferenced before the
  check, or `copy_out` moving a byte of the first page before it decides the
  range is not one;
- a call answering with a value *and* an errno; `ENOSYS` for a call that exists
  but was given the wrong arity; a pointer checked before the descriptor or the
  length, so a call with two things wrong answers `EFAULT` where `EBADF` was
  due; an argument that is not an int answered as a pointer fault instead of
  `EINVAL`;
- the audit line written after the act, or only for the calls that acted, so a
  refused call leaves no promise to compare against anything;
- a promise that is not the answer: `predict` the value the call meant to return
  rather than the one it returned, or an `act` line promising a value for a call
  that was refused;
- a write refused as a pointer fault that had already reached the console; a
  write of no bytes treated as a refusal; a user allowed to write to the console
  out of a page it may only read;
- `fork` copying the parent's table *entry* instead of the frame, so child and
  parent share one frame and the first write in the child appears in the parent;
- `exit` releasing the mapped pages but not the tables and the root: one frame
  per dead task that nobody ever gives back, and a ledger that cannot see it;
- a frame limit checked *after* the allocation, so a refused `spawn`, `fork` or
  `exec` has already moved a frame — a limit is refused before the pool changes
  or it is not a limit;
- an `exec` that re-allocates the tables it already had, and so fails on a pool
  that had room for everything it actually needed;
- a zombie that keeps its frames or stops being counted, a wait that reaps the
  child that is still alive, a wait for a stranger answered as `blocked`, a reap
  that leaves the ledger's free count behind the pool's, and a dying task's
  children forgotten instead of reparented to pid 0;
- a task's limits shared with the task it was copied for, so bending one task's
  limits bends another's; `images()` out of order, or a child whose own tables
  map vpage 1 to the parent's frame, so a walk faults in a task that looks
  fine;
- a ledger that reports the kernel's belief instead of the pool's own
  `free_count`, so the leak proof compares a belief with itself;
- `block` used instead of `wait_on`: a wakeup that lands between the caller's
  own condition check and the sleep finds nobody waiting, and the task sleeps
  forever with nothing left to wake it;
- `wait_on` enqueueing before it checks, or evaluating the condition only once,
  so the wakeup that arrives during the enqueue is lost after all;
- a woken task left in the queue, so a later `wake` wakes it a second time and a
  task woken once runs twice;
- the quantum reset on every tick, so nothing is ever preempted; a run queue
  that is not FIFO among equals; a pid removed and added again treated as the
  same arrival instead of a switch;
- ageing missing, so a priority-8 task beside a priority-0 one waits out the
  whole run and `starved` names it; a tick on which nothing ran missing from the
  trace; a blocked, zombie or dead task scheduled;
- `per_pid` not summing to the ticks that ran; `step` reading the task dict it
  stored instead of the one it was handed; a task this scheduler does not hold
  blocking, being removed, or being picked;
- a deferred CPU's tail run early — deferring nothing, or deferring only the
  `lock` step — so the lost update comes out right for the wrong reason;
- a deferred `lock` treated as acquired while somebody else holds it; a release
  by a CPU that does not own the lock accepted, so two CPUs own it; a recursive
  acquire allowed silently, and a step that is not a triple, an op outside `OPS`,
  or a lock name that is empty or not a word, taken for a legal step;
- the deadlock cycle returned rotated or as an open path, so two descriptions of
  one deadlock are different tuples; a cycle of one missed; a wait on a lock
  nobody holds, or a chain that ends at a CPU doing nothing, reported as a
  deadlock;
- `audit_holds` reporting a lock held across a `load` as a finding (it is not
  one — the holder is making progress), or missing the lock that was never
  released at the end of the trace;
- the superblock written before its data, so a format interrupted half-way
  leaves a mountable filesystem; a data sector written and the inode that claims
  it written without a barrier between them;
- no checksum on an owned sector, or a checksum that is not mixed with the
  sector's own index, so a torn sector is trusted and two sectors with the same
  bytes share one sum;
- the free map not updated, or the blocks a rewritten file gave up left marked
  used; two inodes given the same block; a block an inode claims that the map
  calls free;
- `layout` and `format_disk` disagreeing about where the data region starts, or
  a table size that does not fit the disk named by neither;
- `lookup` resolving `..` by string surgery instead of popping the walk, an
  absolute path treated as relative, `.` counting as a component, a name longer
  than `NAMES_MAX` truncated instead of refused, a duplicate name accepted;
- `fsck` reporting `ok` for an image whose checksum fails, reporting a problem
  word outside the closed vocabulary, or missing a block two inodes claim;
- `mount` accepting a foreign magic or an unknown version without naming both
  what arrived and what the format is, or mounting a root inode that is a file;
- a syscall that returns both a value and an errno, one whose audit line is
  written for the act but not for the refusal, or a promise that is not the
  errno the call is about to return;
- the pointer check kept for `write` and skipped for `read`, or `open`
  returning a value for a file the mode forbids;
- the uid check comparing the task's uid to the file's *mode* instead of its
  uid, so uid 1001 reads root's `0600` file, which is the one security fact this
  course insists on;
- `admit` called after the frames moved, so a refused `anon` leaves the pool
  short by exactly what it took and the leak proof fails where nobody looks;
- a pipe that loses the byte it already accepted, a write to a full pipe that
  succeeds, or an empty read that blocks instead of answering `EAGAIN`;
- the report counted from the kernel's beliefs as it goes instead of recomputed
  from the log, `cross_check` comparing a key that is not in both records, and a
  leak proof that passes because the ledger stopped counting at the last fork.

Nothing here runs on a thread, a wall clock or a `random`: the machine is a pure
function of its inputs, so two runs of one check are the same run, and
`machine.Timer` is the only way time passes — who advances it is the caller.
Where a decision was a judgement call, it is written down in the template's own
docstring as a DESIGN DECISION, and the check asserts the consequence.

## The provided world

| Module | What it is |
|---|---|
| `machine.py` | `PAGE_SIZE` 4096, `FRAME_COUNT` 256, `ENTRIES` 512 per level, an entry of `(frame << 4) \| flags` with the four permission bits, `RAM`, `MMU` (a walk, a TLB with `invalidate`, and `log()`'s `walks`/`hits`/`cached`), `Trap`/`PageFault` with the machine's own `reason` and the x86 error bits, `Timer`, and six `BOOT_MAPS` fixtures including `overlap`, `unknown_kind`, `unaligned`, `unordered` and `too_big` |
| `devices.py` | `SECTOR` 512, `Console` (every byte kept, `text()` and `log()`), `Disk` (whole-sector writes into a buffer, reads that see only the durable image, `barrier`, `power_fail(tear=True)` which tears the sector it was writing, and `log()`/`counters()`) |
| `userland.py` | `PROGRAMS` (eight programs, `echo`, `cat`, `spawn`, `hog`, `greedy`, `nosy`, `piped`, `unknown`), `SHELL` (five `(program, uid)` pairs), `FILES` (a nine-entry tree), `OPS` (the thirteen ops), `RESOURCES` (`frames`, `children`, `ticks`) and `ROOT_UID` |

Four properties of the world are load-bearing. The walk and the handler speak
different vocabularies: `PageFault.reason` is the walk's own fine word
(`not_present`, `supervisor`, `read_only`, `no_execute`, `not_user`) and the
error code is three bits, so a handler that reads the reason works here and not
on a real CPU. The disk keeps only what a barrier made durable, so the order of
a format is a fact the device can prove. The boot maps are fixtures *and*
defects, which is what makes a validating kernel testable without a firmware.
The programs are data, too — dicts with an `op` and operands that are literals
or slot names — so a kernel that meets an op it does not have refuses the program
rather than raising at itself.

## The stages

| # | File | The stage | The mechanism |
|---|---|---|---|
| 1 | `stage_01.py` | the map you were handed | `region_frames`, `validate`, `usable_frames`, `region_at`, `summary`, `holes` |
| 2 | `stage_02.py` | the frame allocator, and the bitmap inside it | `Frames` — `state`, `alloc`, `free`, `free_count`, `used`, `bitmap_bytes`, `bits`, `log` |
| 3 | `stage_03.py` | the address space, and the translation you forgot to invalidate | `ADDRESS_WIDTH`, `new_space`, `map_page`, `unmap_page`, `protect`, `lookup`, `mapped`, `space_frames`, `free_space` |
| 4 | `stage_04.py` | the trap table, and the fault as data | `FAULT_WORDS`, `ACTIONS`, `CAUSES`, `decode`, `classify`, `TrapTable`, `handle`, `panic_record` |
| 5 | `stage_05.py` | the syscall boundary, and the pointer you did not check | `SYSCALLS`, `ERRNOS`, `number`, `user_range`, `copy_in`, `copy_out`, `dispatch`, `audit_line` |
| 6 | `stage_06.py` | the process, and the frame nobody gave back | `USER_BASE`, `STATES`, `TASK_KEYS`, `DEFAULT_LIMITS`, `new_task`, `images`, `Processes` |
| 7 | `stage_07.py` | the scheduler, and the wakeup that never came | `AGEING`, `Scheduler`, `wait_on` |
| 8 | `stage_08.py` | two CPUs, and the critical section nobody guarded | `OPS`, `Lock`, `serialize`, `run_schedule`, `detect_deadlock`, `audit_holds` |
| 9 | `stage_09.py` | the format, and the write that was not ordered | `MAGIC`, `FORMAT_VERSION`, `NAMES_MAX`, `SECTOR`, `PROBLEMS`, `checksum`, `layout`, `format_disk`, `mount`, `lookup`, `read_file`, `write_file`, `create`, `sync`, `fsck` |
| 10 | `stage_10.py` | the capstone: the userland, and the kernel's own ledger | `TABLE_KEYS`, `syscall_table`, `limits_of`, `apply_limit`, `admit`, `fds`, `run`, `report`, `cross_check` |

The stages are cumulative in the only direction that matters: a stage imports
the world and the earlier stages it needs, and nothing from a later one. Stage 2
through stage 9 import stage 1 (stage 6 also imports stage 3, because a `fork`
that copies a page has to install it), and stage 10 composes stages 2, 3, 5, 6,
7 and 9. That is what lets the stages be built in parallel and still checked in
any order.

## How to use this directory

```bash
python3 codecraft/cli.py run os-from-scratch    # what to build next, and why
```

Or without codecraft: the templates are ordinary modules, and an unimplemented
one raises `NotImplementedError`. Implement them at the top level; finished
versions are in `solutions/`. The templates fail and the solutions pass, and
that is the whole grading loop — this course is checker-driven and there is no
test framework anywhere. The ten checks are assembled into `course.py`, and every
one of them is a module-level `def check():` of bare
`assert <condition>, "<message>"` statements, where the message names the
mistake rather than the symptom; an untouched template reports as not
implemented yet rather than failing for the wrong reason. Every check is
mutation-tested: `641` plausible wrong implementations from the
catalogue above — a bitmap kept in a list instead of in RAM, a table written but
not zeroed, a TLB not invalidated, a lost wakeup, a deferred step run early, a
superblock written first — are each planted into the solutions, and the stage's
check must fail. A mutant that hangs its check counts as caught, because a wrong
implementation that never terminates anything is not a passing implementation.

## Prerequisites

Standard library only. `machine.py`, `devices.py`, `userland.py` and the ten
stages import nothing but each other — no numpy, no binary dependency, no
network, no threads. There is no clock and there is no randomness: `time`,
`threading` and `random`, like `socket` and `os`, are imports no stage may make,
and `machine.Timer` is a counter the caller advances — a stage that read a clock
would be a different function each run. There are no floats
anywhere — not in a template, not in a solution, not in a check — because the
two things this course decides by hand are which page a byte belongs to and how
a ratio is spelled, and both of them are integers: `addr // PAGE_SIZE` is the
page and `addr % PAGE_SIZE` is the byte inside it, and a ratio is the two counts
it is made of, never a value that rounds.

You should be comfortable with integer masking and bit fields, with records as
tuples and dicts, with `try`/`except`, and with reading a failure line and
knowing whether it is the caller's mistake or a decision the kernel made. The
arithmetic is written out by hand, on purpose.

## Design decisions

- **A refusal raises and a decision is data.** A *caller's* mistake — a number
  that is not a call, an argument list that is not a tuple, a queue name that is
  not a word, a limit that is not a count — raises, because there is nobody to
  hand an errno to. A user program's mistake is *returned*: `EFAULT`, `EBADF`,
  `EINVAL`, `ENOSYS`, `EPERM`, `EAGAIN`, `{"blocked": True}`, a `panic` with a
  cause, `{"allowed": False, "reason": word}`. A program's failure is never an
  exception, which is why `dispatch` has exactly one exit and why `wait` answers
  instead of sleeping.
- **The cache is an optimisation that must never change an answer.**
  `MMU.translate` remembers what it walked and `MMU.invalidate` is the only way
  to forget, so a kernel that removes a page from the tables and does not
  invalidate it has removed nothing: the next access is answered with no walk
  and no fault. `map_page` installs a translation that did not exist, so nothing
  can be remembered; `unmap_page` and `protect` change a page the machine may be
  serving, so they invalidate — and the check reads the world's own count of
  hits to prove which one answered.
- **The ledger lives where the machine can see it.** The frame allocator's
  bitmap is written into one of the frames of the pool it tracks, indexed by a
  frame's *position* in that pool, and `bits()` reads the bytes back out of RAM.
  A list beside the pool answers every question a caller can ask and none of the
  questions the next boot asks: the frames it forgot are, to the hardware, free.
- **A fork copies frames, and a mirror stores only permissions.** `fork` gives
  every mapped page of the parent a frame of its own and the parent's bytes,
  because sharing is the one promise a process makes that cannot be taken back —
  and copy-on-write costs a fault path and a reference count this course does not
  have. In the tables, `PRESENT` is the kernel's bit: the caller passes
  permissions, and presence is what "this page is mapped" means, never a flag
  borrowed from a caller.
- **Order is the format.** A disk keeps only what a barrier made durable, so
  `format_disk` writes data, barriers, directories, barriers, inodes, barriers,
  the free map, barriers, and writes the superblock **last**; `write_file`
  writes its data sectors and the map, barriers, and only then the inode. A
  format interrupted anywhere leaves no superblock to mount and a file that
  never points at a sector nobody wrote — an unbarriered write is a write that
  never happened, and tearing is how the course proves it.
- **The kernel is checked against the world, not against itself.** `report`
  recomputes the six numbers from the kernel's own log and audit — written
  *before* each act, as a promise — and `cross_check` reads the machine's
  records: `RAM` and `Console` logs, `Disk.durable_sha`, the pool's own count.
  The frames are the leak proof (`pool.free_count()` comes back where it
  started once every task is reaped) and the console is the output proof. A
  counter incremented during the run agrees with itself by construction, which
  is exactly the comparison worth nothing.
- **Two CPUs are graded by a schedule, not by a spin.** A blocked CPU's *whole*
  tail defers to the release rather than spinning, because a spin is timing and
  timing is not something a check can pin; the same schedule with and without
  the lock then loses an update the first time and not the second, and it does
  so on every machine. The same rule decides the scheduler: the tick is handed
  to `step`, and `wait_on` checks, enqueues and checks again, because a check
  and an enqueue that can be separated are a wakeup that can be lost.
- **Snapshots and logs are values.** A check reads a space's mirror, a pool's
  bits, a scheduler's ledger, a kernel's log; each of those is a tuple or a
  fresh dict built for the answer, so a comparison cannot pass because two names
  point at the same mutable thing.

## Where this stops

Deliberately left out, so you know the boundary:

- **No threads, no interrupts with real devices, no preemption by hardware.**
  There is one timer vector and a tick handed in by the caller; two CPUs exist
  as a schedule and a lock, which is what makes the lost update reproducible.
- **No copy-on-write, no swapping, no demand paging for the kernel.** `fork`
  copies, and a page fault with the user bit clear is a kernel bug that panics
  rather than a page the kernel silently allocates for itself.
- **No init process.** pid 0 is the kernel, and a dying task's children go to
  it, because an orphan nobody records is a task whose frames can never be
  accounted for.
- **No blocking read.** An empty pipe is `EAGAIN` and a full one is `EAGAIN`:
  blocking is the scheduler's business, at the task level, between ops, and a
  syscall that blocked inside the kernel would need a wakeup path this course
  does not build.
- **No floating point.** Every number here is a count of bytes, frames, ticks
  or sectors, and every one of them is an exact integer.
