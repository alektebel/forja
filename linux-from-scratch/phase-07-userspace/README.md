# Phase 07 — Userspace: ELF, libc, init, Shell, TTY

**14 exercises.** The kernel gets out of the way and something else runs. This
is the phase where your project starts looking like a computer.

---

## The failure that got you here

Your `exec` from 04.8 replaces an address space with a blob you hand-placed.
There is no way to run a program someone else compiled, no C library, no standard
input, no shell. The kernel is complete enough to be useless: it can host
programs and has none.

**A kernel's users are programs, and its interface is the syscall table.** From
here, every design decision is judged by whether real software can be built
against it.

---

## Design decisions

> **DESIGN DECISION — your own libc, or port musl?**
> Writing one teaches you exactly which syscalls a program actually needs, and
> stops at "enough for my shell". Porting musl gets you a real, complete,
> standards-conforming library and turns your project into a syscall-compatibility
> exercise — every missing syscall is a link error or a runtime abort.
> **Chosen:** your own minimal libc (07.3), then port musl (07.13) once your
> syscall surface is broad enough that it is plausible. The port is the honest
> test of the kernel: nothing accepts excuses like your own libc does.

> **DESIGN DECISION — static or dynamic linking?**
> Static is one file and no loader. Dynamic requires a program interpreter,
> relocation processing, PLT/GOT, symbol resolution, and a lazy-binding scheme.
> **Chosen:** static first (07.1), dynamic in 07.12 — because the dynamic loader
> is a userspace program that must run before any userspace program can run, and
> that bootstrapping puzzle is worth meeting deliberately.

> **DESIGN DECISION — how much POSIX?**
> Every syscall you add is permanent: something will depend on it and you can
> never change it. (Linux's rule is absolute — "we do not break userspace".)
> **Chosen:** the subset a shell, coreutils and a compiler need, and no more.
> Cost: you will discover the subset is larger than you think. That discovery is
> the point of 07.13.

---

## The exercises

### 07.1 — An ELF loader
**Build:** parse the ELF64 header, validate it, walk program headers, map each
`PT_LOAD` at its `p_vaddr` with permissions from `p_flags`, zero the
`p_memsz - p_filesz` tail, set up the stack, and jump to `e_entry`.
**Limit case:** `p_filesz < p_memsz` is `.bss`, and the tail must be zeroed — a
loader that skips it works on every program until one relies on a zeroed global,
then fails inexplicably. Also handle a segment whose `p_vaddr` is not page-aligned
(the file offset and virtual address are congruent modulo the page size, not
equal), and reject a malformed ELF rather than mapping garbage.
**Done when:** a statically-linked binary compiled by your cross-toolchain runs,
and a truncated or corrupt ELF is refused with an error.
**Read:** `[ELF]` generic spec §Program Header and the x86-64 psABI; `[LINKLOAD]`
ch. 3 and 5; `[CSAPP]` ch. 7.

### 07.2 — The initial process stack
**Build:** the exact layout `_start` expects: `argc`, `argv[]`, `NULL`, `envp[]`,
`NULL`, the auxiliary vector, then the string data — with correct alignment.
**Limit case:** the ABI requires 16-byte alignment of `RSP` at entry, and an
SSE instruction in any libc startup path will fault if you are 8 bytes off. The
failure is a `#GP` deep inside code you did not write. Get the alignment right,
then break it on purpose once to see the signature. Also: `AT_PHDR`, `AT_PHNUM`,
`AT_ENTRY` and `AT_RANDOM` in the auxv are not optional — the dynamic loader and
stack protector need them in 07.12.
**Done when:** a program prints its own `argv` and `environ`, and dumps the auxv.
**Read:** `[ELF]` x86-64 psABI §3.4 (Process Initialization) — this figure is the
specification; `[LINKLOAD]` ch. 8; glibc's `dl-support.c` for what consumes auxv.

### 07.3 — A minimal libc
**Build:** `_start` (align the stack, call `main`, `exit`), syscall wrappers,
`errno`, `memcpy/memset/strlen/strcmp`, `malloc` over `brk`/`mmap`, and enough
`stdio` for `printf`, `fopen`, `fread`.
**Limit case:** `malloc` must ask the kernel for memory. Implement `brk` first,
then discover why `free` cannot usually return memory to the kernel (a freed
block in the middle of the heap), then implement the `mmap` path for large
allocations, which *can*. This is why real allocators have two paths.
**Done when:** `printf("%d\n", 42)` works in a program you compiled and your
kernel loaded, and `malloc`/`free` cycles do not grow RSS without bound.
**Read:** `[TLPI]` ch. 7 (Memory Allocation); `[CSAPP]` ch. 9.9 — implementing
malloc is its major exercise; musl's source, which is small enough to read.

### 07.4 — File descriptors
**Build:** a per-process descriptor table over phase 06's `file` objects, with
`open`, `close`, `read`, `write`, `lseek`, `dup`, `dup2`, and a shared open-file
description carrying the offset.
**Limit case:** the three-level structure is not decoration. `dup` shares the
*offset*; a second `open` of the same file does not. Construct both and show
their different behaviour — then `fork` and show that the child shares offsets
with its parent. Programs depend on all three behaviours.
**Done when:** the offset-sharing matrix (dup / reopen / fork) matches Linux's,
tested case by case.
**Read:** `[TLPI]` ch. 5.4 — Figure 5-2 is the diagram you are implementing;
`[APUE]` ch. 3; `[LKD3]` ch. 13.

### 07.5 — Pipes
**Build:** an anonymous pipe: a ring buffer, blocking reads on empty, blocking
writes on full, and readers/writers tracked by refcount.
**Limit case:** close the read end and write. `SIGPIPE`, and `EPIPE` if blocked
— which is how `yes | head` terminates rather than running forever. Then: close
the write end and read, which must return 0 (EOF) rather than block. Both
directions are load-bearing for shell pipelines. Finally, `PIPE_BUF`: writes below
that size must be atomic against other writers.
**Done when:** a two-process pipeline works, both close-cases behave, and
concurrent small writes never interleave within a message.
**Read:** `[TLPI]` ch. 44; `[BACH]` ch. 5.12; `[APUE]` ch. 15; `[P-STREAMS84]`
for the more general idea Unix nearly adopted instead.

### 07.6 — A TTY layer
**Build:** the line discipline: canonical mode with line buffering and backspace,
raw mode, echo, control characters (`^C` → `SIGINT`, `^D` → EOF, `^Z`), and
`termios` via `ioctl`.
**Limit case:** canonical mode means a program blocked in `read` gets nothing
until Enter — even though the characters have arrived. Then in raw mode it gets
each keystroke. Same device, same syscall, opposite behaviour, and every editor
and shell depends on switching between them. Build both, then handle a program
that crashes while in raw mode and leaves the terminal unusable — and decide who
restores it.
**Done when:** line editing works, `^C` interrupts the foreground program, `^D`
gives EOF at a line start, and raw mode delivers per-keystroke.
**Read:** `[TLPI]` ch. 62 (Terminals) in full — this is the reference; `[APUE]`
ch. 18; `[BACH]` ch. 10; `[KDOC]` `Documentation/driver-api/tty/`.

### 07.7 — Sessions, process groups, job control
**Build:** `setsid`, `setpgid`, a controlling terminal, a foreground process
group, and `SIGTTIN`/`SIGTTOU` for background access.
**Limit case:** a background process reads from the terminal. It must be *stopped*
with `SIGTTIN`, not allowed to steal input from the foreground job. Construct it.
Then: the controlling terminal is lost (hangup) and every process in the session
gets `SIGHUP` — which is why `nohup` exists. This machinery looks baroque until
you build the shell in 07.9 and find you need all of it.
**Done when:** background jobs are stopped on terminal read, foreground group
changes with the job, and hangup propagates.
**Read:** `[TLPI]` ch. 34 in full; `[APUE]` ch. 9 — the diagrams are worth
copying; `[POSIX]` §11.1.

### 07.8 — init: PID 1
**Build:** the first user process — mount the root filesystem, spawn a shell,
reap orphans forever, and never exit.
**Limit case:** kill PID 1. The kernel must panic rather than continue — there is
no one left to reap, and the system has no meaning. Make that explicit rather
than accidental. Then: `init` must survive a child crashing, an fd exhaustion,
and a full disk, because there is no one to restart it.
**Done when:** the system boots to a shell prompt with no hand-holding, and
orphan reaping is demonstrable via a printed process table.
**Read:** `[TLPI]` ch. 34.7; `[MELP]` ch. 13 (Starting Up — the init Program);
`[SAGE]` ch. 2; the original `/etc/inittab` documentation for the SysV model.

### 07.9 — A shell
**Build:** parse a command line, `fork`+`exec`, `wait`, redirection (`<`, `>`,
`>>`), pipelines, `&`, and builtins (`cd`, `exit`, `export`, `jobs`, `fg`, `bg`).
**Limit case:** `cd` cannot be an external program — it would change the child's
directory and exit. Deriving *why* certain things must be builtins is the lesson.
Then build an N-stage pipeline and get the fd bookkeeping right: every process
must close every descriptor it does not need, or the pipeline never sees EOF and
hangs. That hang is the classic shell bug.
**Done when:** `cat f | grep x | wc -l > out &` works, `fg` brings it back, and no
descriptor leaks (check by listing open fds per process).
**Read:** `[TLPI]` ch. 27; `[APUE]` ch. 9; `[bash-from-scratch/](../../bash-from-scratch/)`
in this repo; `[POSIX]` §2 (Shell Command Language) for how much you are *not*
implementing.

### 07.10 — Coreutils, enough of them
**Build:** `cat`, `ls`, `echo`, `cp`, `mv`, `rm`, `mkdir`, `ps`, `kill`, `sh`-
callable, plus a `/proc`-like interface for `ps` to read.
**Limit case:** `ls -l` needs `stat`, which needs a metadata structure you must
now freeze into your ABI. Design `struct stat` once, knowing you cannot change it
— Linux has three generations of `stat` syscalls for exactly this reason. Then
implement `ps` and discover it needs kernel data no syscall exposes; that is the
argument for `/proc` and you should feel it before you build it.
**Done when:** the shell can drive a real session: list, copy, inspect, kill.
**Read:** `[TLPI]` ch. 15 (File Attributes), ch. 18 (Directories); `[KDOC]`
`Documentation/filesystems/proc.rst`; `[LKD3]` ch. 17 on kobjects and sysfs.

### 07.11 — `/proc` and `/sys`
**Build:** a synthetic filesystem behind the VFS from 06.9: `/proc/<pid>/`
(status, maps, fd), `/proc/meminfo`, `/proc/interrupts`, `/proc/cpuinfo`.
**Limit case:** these files have no blocks and no size. `read` must generate
content on demand, and the content can change between two reads of the same file
— so `lseek` semantics are strange and a partial read can see a torn view. Decide
your policy (snapshot at open, as Linux does with `seq_file`) and implement it.
**Done when:** `cat /proc/self/maps` prints your address space, and `ps` reads
`/proc` rather than a private syscall.
**Read:** `[LKD3]` ch. 17; `[UTLK]` App. A; `[KDOC]`
`Documentation/filesystems/seq_file.rst`; `[TLPI]` ch. 12.

### 07.12 — Dynamic linking
**Build:** a program interpreter (`ld.so`): map the ELF, process `PT_DYNAMIC`,
resolve dependencies, apply relocations (`R_X86_64_RELATIVE`, `GLOB_DAT`,
`JUMP_SLOT`), fill the GOT, and implement lazy binding through the PLT.
**Limit case:** the loader is itself a program that needs relocating, and it must
relocate itself before it can call any function through the GOT — including its
own. That self-bootstrapping constraint is why `ld.so` is written the way it is,
with a hand-written self-relocation stub. Then: symbol interposition — two
libraries defining the same symbol, first-wins, which is what `LD_PRELOAD`
exploits.
**Done when:** a dynamically-linked "hello world" runs, `ldd`-equivalent output is
correct, and lazy binding is provable (a function resolved only on first call).
**Read:** Drepper, U., *How To Write Shared Libraries* **(free)** — the definitive
document, read §1–3 at minimum; `[LINKLOAD]` ch. 9–10; `[ELF]` §Dynamic Linking;
`[CSAPP]` ch. 7.10–7.13.

### 07.13 — Port musl, and let it judge your kernel
**Build:** enough syscall surface, with correct semantics and error codes, that
musl libc builds and runs against your kernel.
**Limit case:** musl does not care what you meant. Every wrong `errno`, every
missing `AT_` auxv entry, every syscall that returns a plausible-but-wrong value
becomes a failure somewhere unrelated. Keep a log of each break and its cause —
that log is the most accurate description of your kernel's gaps that will ever
exist. Expect `clock_gettime`, `readv`/`writev`, `set_tid_address`, `futex`,
`rt_sigprocmask` and TLS setup (`arch_prctl`) to be the ones that bite.
**Done when:** a musl-linked binary you did not write runs unmodified, and the
break log is committed.
**Read:** musl's source and its `arch/x86_64/syscall_arch.h`; `[TLPI]` as
reference for every semantic you have to get exactly right; `[POSIX]` for the
ones TLPI leaves ambiguous.

### 07.14 — Measure the userspace boundary
**Build:** numbers for: process startup (static vs dynamic), lazy versus eager
binding, `printf` through your libc versus a direct `write`, and shell pipeline
throughput.
**Limit case:** static versus dynamic startup — predict the ratio, then explain
it in terms of relocation count. Then measure a `fork`-heavy shell script and
compare against Linux. Where you lose, attribute it: CoW fault storms? No
`vfork`? Address-space teardown cost?
**Done when:** the table exists with a mechanism named per row.
**Read:** Drepper, *How To Write Shared Libraries* §1.5 on startup cost; `[TLPI]`
ch. 28 on process creation cost; lmbench's `lat_proc`.

---

## Where this phase stops

- **No threads in userspace yet.** `clone` with `CLONE_VM` exists from phase 04,
  but TLS, `pthread_*` and cancellation are musl's problem in 07.13 and you will
  implement only what it demands.
- **No `epoll`/`select`/`poll`.** Deferred to phase 09, where there is something
  worth multiplexing.
- **No shared memory or SysV IPC.** `mmap(MAP_SHARED)` from 06.13 covers the case
  you need; `shmget`, message queues and semaphores are `[TLPI]` ch. 45–48.
- **No terminal emulator or framebuffer console.** Your TTY is serial and VGA
  text. A pty pair is a good stretch exercise and is what a terminal emulator
  needs.
- **No compiler running natively.** Self-hosting is phase 12.

---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
