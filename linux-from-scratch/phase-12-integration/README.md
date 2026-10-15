# Phase 12 — Integration: Real Hardware, Real Software, Real Numbers

**6 exercises.** The two tracks meet. Your kernel runs the userland you built,
on a machine you can touch, and you find out what QEMU was forgiving.

---

## The failure that got you here

Nothing broke, exactly. But three claims remain untested:

1. **Your kernel has only ever run software you wrote.** Every syscall's
   semantics have been checked against your own expectations. Phase 07.13 started
   the real test with musl; this phase finishes it.
2. **Your kernel has only ever run under QEMU**, which is more forgiving than
   silicon in specific documented ways, and does not have your machine's chipset,
   its timing, or its firmware's opinions.
3. **You have measured your kernel against itself.** A number with nothing to
   compare it to is not a measurement.

---

## The exercises

### 12.1 — Boot on real hardware
**Build:** a bootable USB stick, and your kernel running on a physical machine —
a spare laptop, an old desktop, or a single-board x86 machine. **Not** a machine
whose disk you need.
**Limit case:** everything you got away with. Expect at least: a real UEFI that
does not present the memory map you assumed; a serial port that does not exist
(so your only debug channel is gone — plan for that before you need it); ACPI
tables that are subtly non-conforming; a timer that calibrates differently; and a
disk controller that is AHCI, not the ATA PIO you wrote in 06.1. Each of these
is a real bug that QEMU hid, and finding them is the exercise.
**Done when:** your kernel boots to a shell on physical hardware, and each QEMU-
only assumption you had to fix is written up.
**Read:** `[UEFI]` §2 and §7; `[ACPI]` §5; `[OSDEV]` Real Hardware, Troubleshooting;
`[SDM3]` ch. 9.1 and 9.11 (microcode, and the state you actually start in).

### 12.2 — Run software you did not write
**Build:** enough syscall compatibility to run real, unmodified programs — start
with BusyBox, then a small compiler (`tcc`), then something with threads.
**Limit case:** every program is a test suite for your kernel written by someone
who has never heard of it. Keep the break log from 07.13 going. The pattern to
watch for: your kernel does something *plausible* rather than what Linux does —
a slightly different `errno`, a `read` that returns short when Linux would not, a
`stat` field left zero. These are the hardest to find because nothing crashes;
something merely behaves oddly, three layers up.
**Done when:** BusyBox's applets run, `tcc` compiles a program on your OS, and the
break log is complete.
**Read:** `[TLPI]` as the reference for every semantic in dispute; `[POSIX]` where
TLPI is silent; the Linux Test Project's test descriptions for what a real
conformance suite checks.

### 12.3 — Self-hosting
**Build:** a toolchain running *on* your OS that can compile your OS.
**Limit case:** this is the closing of the loop, and it demands more than any
previous exercise: `fork`/`exec` under load, a filesystem that survives thousands
of file creations, `mmap` correctness (compilers map their inputs), signals,
enough memory management to survive a link, and a `make` that runs jobs in
parallel. It will find bugs in phases 03, 06 and 07 that nothing else did.
**Done when:** your kernel, built on your kernel, boots.
**Read:** `[LINKLOAD]` ch. 11 on the bootstrap; `[P-TRUST84]` — for the last time,
and now it is about *your* compiler; `[c-compiler/](../../c-compiler/)` in this
repo if you want the toolchain to be yours too.

### 12.4 — Benchmark against Linux, honestly
**Build:** the full comparison — syscall latency, context switch, `fork`+`exec`,
page-fault cost, file I/O at several patterns, network throughput and latency —
your kernel versus the Linux you built in phase 11, on the same hardware.
**Limit case:** you will lose everywhere, by between 2× and 100×. The exercise is
not the ratio; it is the *attribution*. For each row, name the mechanism Linux
has that you do not — batched TLB flushes, per-CPU caches, readahead, GSO, a
better allocator, lazy FPU state, `vDSO`. Where you cannot explain a gap, that is
a subsystem you do not yet understand, and it is the most useful output of the
entire project.
**Done when:** the table exists, every row has a named mechanism, and the
unexplained rows are listed as open questions.
**Read:** `[HP6]` ch. 1.9 on measurement; lmbench (McVoy & Staelin, 1996);
`[deploy-and-debug/](../../deploy-and-debug/)` in this repo on reading
percentiles; `[P-SCALE10]`.

### 12.5 — Close the biggest gap
**Build:** pick the single worst row from 12.4 and fix it properly — implement the
mechanism Linux has, measure again, and write up the before/after.
**Limit case:** most candidates are not local changes. A `vDSO` needs a shared
mapping and a userspace-visible clock; readahead needs I/O pattern detection;
per-CPU slab caches need 05.8's infrastructure everywhere. Choosing well matters
more than executing well: pick the one where the mechanism is understandable and
the measurement is unambiguous. Then confirm you actually moved the number you
aimed at, and that you did not move others in the wrong direction.
**Done when:** one benchmark row improves by a factor you predicted in advance,
with no regressions you did not accept deliberately.
**Read:** whichever subsystem you chose — `[LKD3]`, `[UTLK]` and `[KDOC]` for how
Linux does it; `[P-WORTH]` (Lampson's "Hints for Computer System Design") before
you start, because it is about exactly this kind of choice.

### 12.6 — Write it down
**Build:** the document — architecture, every design decision with its
alternatives and its cost, the measurements, the bug log, and the list of what
you would do differently.
**Limit case:** the section that is hard to write is "what I got wrong". Write it
anyway, and be specific: the abstraction you introduced too early, the lock you
made too coarse, the on-disk format you cannot change now, the syscall you cannot
un-ship. Then the counterpart: which of the ninety-odd limit cases in this
curriculum actually changed your design, and which you handled and forgot. That
distinction tells you what to keep for the next system.
**Done when:** someone else could read it and understand both what you built and
why it is shaped that way.
**Read:** `[P-UNIX74]` — five pages describing a whole operating system, and the
model for what you are writing; `[P-WORTH]`; `[LIONS]` for the annotated-source
tradition; `[PHILOSOPHY.md](../../PHILOSOPHY.md)` in this repo.

---

## Where this phase stops

You have a Unix-like operating system that boots on metal, runs software you did
not write, and compiles itself. It is not Linux, it is slower than Linux, and you
know precisely where and why. That last clause is the whole return so far.

What it is *not* yet is a machine you would use. On the hardware from 12.1 you
are almost certainly running with: no USB (so no keyboard on most machines built
after ~2010), no NVMe (so no disk on most machines built after ~2016), a
framebuffer at whatever mode the firmware happened to pick, no power management
(the fans are at full speed and the battery is draining at idle), and no
protection against a malicious device. Those are phase 13.

And even with every driver written, "it boots" and "I use it" are different
claims — separated by uptime, crash recovery, backups, upgrades, and a real job
the machine does. That is phase 14.

- **Next: [phase-13-real-hardware/](../phase-13-real-hardware/)** — the drivers
  your actual machine needs.
- **Then: [phase-14-daily-driver/](../phase-14-daily-driver/)** — running it for
  real, and the honest verdict on what it can and cannot do.

Deliberately still out of scope after this phase:

- **Another architecture** (ARM64, RISC-V). Nothing exposes an accidental x86
  assumption like a weak memory model and no I/O ports. `[PMCCC]` ch. 5 first.
- **Virtualization.** A hypervisor with VT-x, or your kernel as a KVM guest.
  `[P-POPEK74]`, `[P-XEN03]`, `[P-KVM07]`.
- **A different kernel structure.** Rebuild as a microkernel and measure the IPC
  cost you were told about. `[P-UKERNEL95]`, `[P-EXOKERNEL95]`, `[OSDI]`.
- **Formal methods.** `[P-SEL4]`, and [lean-proofs/](../../lean-proofs/) in this
  repo for the tooling.


---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
