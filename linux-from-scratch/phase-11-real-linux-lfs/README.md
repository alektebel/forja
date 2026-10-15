# Phase 11 — Track D: A Real Linux System, Built From Source

**10 exercises.** The other project. Not "write a kernel" but "account for every
single binary on a working Linux machine, because you compiled all of them".

---

## Why this is a separate track

Phases 00–10 answer *why is an operating system shaped like this*. This phase
answers a different question, and it is the one in your original request:
**what is actually on my machine, and who put it there?**

You can do this phase at any point after phase 02. It is short — a first pass is
a few weekends — and having a real Linux system you built yourself is
extraordinarily useful as a reference for every remaining phase: when your kernel
disagrees with Linux about a syscall, you now have a Linux whose source you have
already read and can rebuild with a printf in it.

**Do it early. Do it before you need it.**

The canonical guide is the *Linux From Scratch* book `[LFS]`, and this phase does
not attempt to reproduce it — it is excellent and freely available. What follows
is the division of the work and the questions to hold in mind, because it is
entirely possible to type every command in the book and learn nothing.

---

## Design decisions

> **DESIGN DECISION — follow the book, or improvise?**
> The book's ordering is not arbitrary: it is a dependency graph, resolved, with
> the circularities broken in specific places. Improvising means re-deriving that
> graph the hard way.
> **Chosen:** follow the book exactly on the first pass, and *annotate* — for
> every package, write one line on why it is at that position. Then deviate on the
> second pass. Cost: the first pass feels like transcription. The annotation is
> what converts it into understanding, and skipping the annotation wastes the
> entire phase.

> **DESIGN DECISION — glibc or musl?**
> glibc is what the book uses, what nearly all binary software expects, and is
> large and complicated. musl is small enough to read in an afternoon, strictly
> conforming, and breaks a long tail of software that depends on glibc
> extensions.
> **Chosen:** glibc first (follow the book), musl as the 11.9 variant — partly
> because you will have already ported musl in 07.13 and can compare what a libc
> looks like from both sides of the syscall boundary.

> **DESIGN DECISION — systemd or SysV init?**
> LFS ships both editions. SysV init is shell scripts you can read end to end.
> systemd is a large, integrated system that does dependency-based parallel
> startup, socket activation, cgroup-based service tracking, and much else.
> **Chosen:** SysV first, because you can read all of it and because you built
> the process model it uses in phase 07. Then read systemd's design and form a
> view. Cost: SysV is not what modern distributions run, so your knowledge of it
> is historical — which is precisely why understanding *what problems systemd
> solves* requires having lived with the alternative.

---

## The exercises

### 11.1 — The host, and what you are trusting
**Build:** a verified host environment (the book's `version-check.sh`), a
dedicated partition, and a written inventory of every host tool the build will
use.
**Limit case:** you are about to compile a compiler using a compiler you did not
build, on a kernel you did not build. `[P-TRUST84]` is four pages and is
*directly* about this situation — a compiler backdoor that reproduces itself
through a clean recompile and is invisible in all source. Read it now, then read
`[P-DDC]` for the only known defence. Then decide what your trust boundary
actually is and write it down. This is not paranoia theatre; it is the honest
answer to "complete control of my machine".
**Done when:** the host passes the checks, and your trust inventory is written.
**Read:** `[LFS]` ch. 2; `[P-TRUST84]`; `[P-DDC]`; `[P-REPRO]`.

### 11.2 — Cross-toolchain, pass 1
**Build:** binutils, a bootstrap GCC, and the kernel headers, targeting an LFS
triplet distinct from the host's.
**Limit case:** the circularity. GCC needs a libc to build; the libc needs a
compiler to build; both need binutils. The book breaks the loop with a
*static, C-only, no-headers* GCC that can compile glibc and nothing else. Trace
exactly which of GCC's own features are absent at this stage and why each is not
needed yet. This is the same bootstrap problem you solved once in 00.1 without
noticing.
**Done when:** the cross-compiler produces a working object for the target
triplet.
**Read:** `[LFS]` ch. 5; `[CLFS]` — its whole purpose is explaining this
sequence; the GCC installation manual on bootstrapping.

### 11.3 — glibc and libstdc++, and the toolchain's second pass
**Build:** glibc against the cross-compiler, then libstdc++, then the pass-2
toolchain.
**Limit case:** the sanity check the book insists on — compile a trivial program
and check `readelf -l` names the *correct* dynamic linker
(`/lib64/ld-linux-x86-64.so.2` under your new prefix, not the host's). If it
names the host's, everything after this point is silently linking against the
host and you will not find out for eight hours. Run the check. Understand each
field in its output.
**Done when:** the sanity check passes and you can explain every line of it.
**Read:** `[LFS]` ch. 5–6 and the "Toolchain Technical Notes" section — read that
section twice, it is the conceptual core of the entire book; `[LINKLOAD]` ch. 9.

### 11.4 — Temporary tools, and `chroot`
**Build:** the minimal cross-compiled toolset, then enter `chroot` and rebuild
the system from inside it.
**Limit case:** the moment of `chroot` is the moment your build stops depending
on the host. Verify it: from inside, confirm that nothing on `PATH` resolves
outside, that no library loads from the host, and that removing the host's
`/usr/bin` from the mount would change nothing. Then ask what *still* comes from
outside — the kernel, `/dev`, `/proc`, the CPU microcode — and note it.
**Done when:** the chroot is self-hosting for the build, and the residual host
dependencies are listed.
**Read:** `[LFS]` ch. 7; `[TLPI]` ch. 18.12 on `chroot`'s (weak) isolation —
which you now know from 10.6, having built the stronger version.

### 11.5 — The final system: ~80 packages
**Build:** the full package set — glibc, binutils, GCC, coreutils, bash, and the
rest — each with a one-line annotation of why it exists.
**Limit case:** most of these are not obvious. Why does the system need both
`bash` and `dash`? What does `gettext` do that nothing else does? Why is `perl`
required for a *C* toolchain? Which of these are needed only to *build* the
others? Answer for each. The list you produce is the actual content of "what is
on a Linux system", and it is roughly 80 lines long — which is itself the most
surprising finding of this phase.
**Done when:** every package has an annotation, and you can identify the ones you
could remove.
**Read:** `[LFS]` ch. 8 (its per-package descriptions are the seed for your
annotations); `[SAGE]` ch. 2, 5, 6.

### 11.6 — Configure a real kernel and boot it
**Build:** the kernel from source: `menuconfig` starting from
`make localmodconfig`, an initramfs, and a bootloader entry.
**Limit case:** boot it, then *strip it*. Remove drivers, filesystems and
subsystems until it stops booting, and note precisely what was required. The
minimum is far smaller than the default. Then find the two classic failures:
built-in versus module for the root filesystem's driver (a module in an initramfs
you forgot to include = "unable to mount root fs"), and a missing `CONFIG` your
userland silently depended on. Both teach more than a successful boot.
**Done when:** you boot a kernel you configured, and you have a minimal `.config`
plus a list of what each removal broke.
**Read:** `[KNUTSHELL]` — this is the book for this exercise **(free)**; `[LFS]`
ch. 10; `[MELP]` ch. 4; `[LINSIDES]` for what the kernel does before your init
runs.

### 11.7 — Boot to userspace: init, mounts, devices
**Build:** the boot scripts, `/etc/fstab`, `udev`/`eudev` rules, console and
network setup, and a login.
**Limit case:** trace the boot end to end and account for *every* process
started, in order, with the thing that started it. Any process you cannot explain
is something running on your machine that you did not put there — which is
precisely the state you set out to eliminate. Then break it: give `/etc/fstab` a
wrong UUID and recover from the resulting emergency shell, without rebooting into
a rescue image.
**Done when:** you boot to a login prompt, and your process-tree annotation is
complete.
**Read:** `[LFS]` ch. 9; `[MELP]` ch. 13; `[SAGE]` ch. 2; `[LDD3]` ch. 14 on how
udev and the device model connect (which you built in 08.3).

### 11.8 — Beyond LFS: make it useful
**Build:** a compiler toolchain that can rebuild itself, networking utilities,
`git`, an editor, and enough to develop *on* the system — then rebuild your
phase 00–10 kernel on it.
**Limit case:** self-hosting. Rebuild the system's own toolchain using itself,
and compare the result against the original binaries. They should match; where
they do not, find out why (timestamps, build paths, `__FILE__`, ordering). You
have just performed one round of a reproducible-build check, and it connects
directly back to 11.1.
**Done when:** the system rebuilds its own compiler, and your OS kernel from
phases 00–10 compiles on it.
**Read:** `[BLFS]` — pick packages deliberately, not by browsing; `[P-REPRO]`;
`[P-DDC]` again, now that you have the machinery to attempt it.

### 11.9 — Package management: the problem you have been ignoring
**Build:** a way to install, list, upgrade and *remove* packages — at minimum,
per-package `DESTDIR` installs with a manifest; better, a content-addressed store
in the manner of Nix.
**Limit case:** you have installed 80 packages with `make install` and have no
record of which file came from which. Now upgrade one. Now remove one. Both are
impossible — and this is exactly the problem package managers exist for, met
after you have earned it. Then find the harder one: two packages needing
different versions of the same library, which the filesystem hierarchy cannot
represent. That constraint is the entire argument of `[P-NIX06]`.
**Done when:** you can install, list the contents of, upgrade and cleanly remove
a package, and you can state what your scheme does about conflicting versions.
**Read:** `[P-NIX06]` and Dolstra's thesis ch. 2–3; `[LFS]` ch. 8.2 (Package
Management) — a short section that lays out the options honestly; the Debian
Policy Manual §7 on dependencies for how a mature system states this.

### 11.10 — Audit: what is running, and why
**Build:** a complete inventory of the finished system — every file, its package,
its purpose; every running process; every listening socket; every kernel module.
**Limit case:** find something you cannot account for. There will be something.
Then answer the question that started this project: *is this machine doing
anything you did not ask it to?* Compare the answer against your daily-driver
distribution — count the processes, the units, the listening ports and the
modules on each. The difference is what "complete control" costs and buys.
**Done when:** the inventory is complete, and the comparison table with a stock
distribution is written up.
**Read:** `[SAGE]` ch. 4 (process control), ch. 13 (networking); `[TLPI]` ch. 12;
`[KDOC]` `Documentation/filesystems/proc.rst`; `[P-TRUST84]` a third time.

---

## Where this phase stops

- **No distribution infrastructure.** No build farm, no repository, no signing,
  no release process. You built a system, not a distribution.
- **No X11, no Wayland, no desktop.** `[BLFS]` covers it; it is a large amount of
  work with a low learning-per-hour ratio compared to everything else here.
- **No cross-compilation to another architecture.** `[CLFS]` is the path; an
  ARM64 build on x86-64 is an excellent second pass.
- **No hardened build.** No compiler hardening flags by default, no
  `Hardened LFS`. Phase 10's mitigations were in *your* kernel, not this one.
- **No automation.** ALFS/jhalfs exists and would rob you of the phase.
- **Reproducibility is demonstrated once (11.8), not achieved.** A genuinely
  reproducible distribution is an ongoing engineering programme; `[P-REPRO]` is
  the state of the art.

---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
