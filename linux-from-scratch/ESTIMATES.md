# Time Estimates

**Median: ~2,100 hours of hands-on work.** Range 1,600–2,800 depending on how
much you cut and how fast you debug.

At the commitment most people can actually sustain alongside a job — **10 hours a
week — that is about four years.** At 20 hours a week, two. Full time, one.

That number is large and it is not padded. Read the rest of this page before
reacting to it: the milestones deliver value long before the end, phase 11 gives
you a real Linux you built in under two weeks, and the section on trimming cuts
roughly 450 hours without gutting the project.

---

## What these estimates cover

**Included:** designing, writing, and *debugging* the code. Debugging dominates —
budget roughly half of every number below for it. Also included is the targeted
reading each exercise needs (the specific SDM section, the RFC, the paper).

**Not included:**

- **Reading the core books cover to cover.** OSTEP, TLPI, LKD3, LDD3 and
  `[CSAPP]` add roughly **150–250 hours** if you read them properly rather than
  as reference. Worth it, and not counted here.
- **The prerequisite gap.** If C, the linker, or x86 assembly are shaky, phase
  00's prerequisites section suggests three weeks of `[CSAPP]` first. That is
  ~60 hours before hour zero.
- **Calendar time you are not working.** 14.13 is a *thirty-day* run — about 25
  hands-on hours spread over a month you spend mostly waiting. Phase 11 has long
  compile waits you can walk away from.
- **Rework.** Estimates assume you build each thing roughly once. In practice
  03.6 (higher-half) and 06.6 (on-disk format) get redone. The high column
  absorbs some of this; a genuine restart does not.

---

## By phase

| Phase | Ex | Low | **Median** | High | Cumulative (median) |
|---|---:|---:|---:|---:|---:|
| [00  Toolchain](phase-00-toolchain/README.md) | 6 | 20 | **26** | 35 | 26 |
| [01  Boot](phase-01-boot/README.md) | 10 | 50 | **65** | 90 | 91 |
| [02  Kernel core](phase-02-kernel-core/README.md) | 12 | 70 | **90** | 120 | 181 |
| [03  Memory](phase-03-memory/README.md) | 13 | 90 | **115** | 150 | 296 |
| [04  Processes](phase-04-processes/README.md) | 13 | 110 | **145** | 190 | 441 |
| [05  Concurrency / SMP](phase-05-concurrency-smp/README.md) | 12 | 110 | **150** | 200 | 591 |
| [06  Storage / FS](phase-06-storage-fs/README.md) | 14 | 140 | **180** | 240 | 771 |
| [07  Userspace](phase-07-userspace/README.md) | 14 | 150 | **195** | 260 | 966 |
| [08  Drivers (model)](phase-08-drivers/README.md) | 11 | 90 | **115** | 150 | 1,081 |
| [09  Networking](phase-09-networking/README.md) | 14 | 160 | **210** | 280 | 1,291 |
| [10  Security / isolation](phase-10-security-isolation/README.md) | 12 | 110 | **145** | 190 | 1,436 |
| [11  LFS (Track D)](phase-11-real-linux-lfs/README.md) | 10 | 45 | **60** | 90 | 1,496 |
| [12  Integration](phase-12-integration/README.md) | 6 | 80 | **110** | 150 | 1,606 |
| [13  Real hardware](phase-13-real-hardware/README.md) | 15 | 230 | **310** | 420 | 1,916 |
| [14  Daily driver](phase-14-daily-driver/README.md) | 14 | 130 | **175** | 230 | 2,091 |
| **Total** | **176** | **1,585** | **2,091** | **2,795** | |

Average is about 12 hours per exercise, but the distribution is nothing like
flat — see [the big rocks](#the-big-rocks) below.

**Phase 13 is the largest single phase**, at 310 hours — larger than networking,
larger than the filesystem. That is the honest price of "write my own drivers and
actually use the machine": xHCI alone is ~50 hours and an AML interpreter is
~60. It is also the phase most people underestimate by the widest margin,
because from the outside "write a USB driver" sounds like one task.

---

## Calendar

| Hours per week | Weeks | Elapsed | What that commitment is |
|---|---:|---|---|
| 5 h | 418 | **8.0 years** | an evening a week — realistically, too slow to hold context |
| 10 h | 209 | **4.0 years** | two evenings plus half a weekend day |
| 20 h | 105 | **2.0 years** | a serious second job |
| 40 h | 52 | **1.0 year** | full time |

**Below about 8 hours a week this project does not work**, and the reason is not
arithmetic. Kernel debugging requires holding a lot of state in your head, and a
90-minute session spends most of itself reloading context you had last week.
Fewer, longer sessions beat more, shorter ones by a wide margin here — one
6-hour Saturday is worth considerably more than six 1-hour evenings.

---

## Milestones: where the value actually lands

You do not wait 2,000 hours for a payoff. Each of these is a genuine, working,
demonstrable thing:

| Milestone | Phases | Median h | At 10 h/wk |
|---|---|---:|---|
| Boots, prints, takes interrupts | 00–02 | 181 | 4 months |
| Multitasking kernel: processes, syscalls, a scheduler | 00–04 | 441 | 10 months |
| Multi-core, with a filesystem that survives crashes | 00–06 | 771 | 1.5 yr |
| **A self-contained Unix in QEMU: shell, files, userspace** | 00–07 | 966 | 1.9 yr |
| Networked, with a driver model and isolation | 00–10 | 1,436 | 2.8 yr |
| Runs on metal, runs foreign software, compiles itself | 00–12 | 1,606 | 3.1 yr |
| Every driver your machine needs | 00–13 | 1,916 | 3.7 yr |
| **In real service for thirty days** | 00–14 | 2,091 | 4.0 yr |

**And separately: phase 11 costs 60 hours and can be done at any point after
phase 02.** That is a real Linux distribution, compiled from source by you, every
binary accounted for — the thing you originally described — in about six weeks of
evenings. *Do it first.* It is by far the best hours-to-payoff ratio in the
project, and it gives you a reference system to compare your kernel against for
the remaining three years.

The bolded row at 00–07 is the other one to note. A working Unix in an emulator
is a complete, satisfying, finished-feeling artifact. If you stop there you have
built something real.

---

## The big rocks

Fifteen exercises account for roughly 500 hours — a quarter of the project:

| Exercise | h | Why |
|---|---:|---|
| 13.12 AML interpreter | ~60 | A bytecode VM inside your kernel; ACPICA exists for a reason |
| 13.4 xHCI | ~50 | Rings, contexts, cycle bits, BIOS handoff — and nothing works until it does |
| 13.13 Power / S3 suspend | ~45 | Every driver needs suspend+resume callbacks that actually work |
| 07.13 Port musl | ~40 | Every wrong `errno` in nine phases surfaces here at once |
| 09.10 TCP reliable transfer | ~40 | RTT estimation, Karn's algorithm, retransmission under real loss |
| 12.3 Self-hosting | ~40 | Stresses phases 03, 06 and 07 harder than any test you wrote |
| 06.11 Journal + crash sweep | ~35 | The sweep (crash at every Nth write) *is* the exercise |
| 06.10 ext2 | ~35 | Triple-indirect blocks, and `fsck.ext2` grading your work |
| 07.12 Dynamic linking | ~35 | A loader that must relocate itself before it can call anything |
| 09.9 TCP connection management | ~35 | Eleven states; every missing edge is a hang |
| 09.11 Congestion control | ~35 | Plus the collapse experiment that motivates it |
| 13.5 USB enumeration | ~35 | Hubs, timing, recursion, hotplug |
| 12.1 Boot on real hardware | ~35 | Finding everything QEMU forgave |
| 14.9 Remote access / SSH | ~35 | A network-facing parser you wrote, so 10.5's fuzzing applies |
| 13.2 AHCI / 13.3 NVMe | ~30 ea | Two more ring-based drivers, two more phase/cycle-bit traps |

If a big rock is going badly, the correct move is usually to cut it (below), not
to grind. 13.12 in particular has an explicit escape hatch: port ACPICA.

---

## Calibrate against yourself after phase 02

**These numbers are for a competent programmer who has not written an OS before.**
Your actual multiplier is personal and you can measure it cheaply.

Phases 00–02 are 181 hours of the estimate. Track your real hours through them,
then:

```
your multiplier = your actual hours / 181
```

Apply it to everything after. A multiplier of 1.5 turns the median into 3,100
hours; 0.7 turns it into 1,500. Both are common. **Do this at hour ~180, not at
hour ~1,000** — it is the cheapest possible course correction, and phases 00–02
are representative enough (assembly, hardware manuals, debugging blind) to
predict the rest.

The things that move the multiplier most, in order:

1. **How fast you debug without a debugger.** Half of every number above.
2. **Whether you read the manual or guess.** Guessing at the SDM is the single
   most expensive habit available in this project.
3. **Session length.** See the calendar section.
4. **Whether you accept a fix you cannot explain.** Those come back, compounded.

---

## Where projects die, and what to do about it

Hobby OS projects overwhelmingly die in two places, and both are predictable:

**Around phase 04–05 (hours 400–600).** The kernel is complex enough to be hard
and not yet useful enough to be rewarding. Everything is a race condition. The
counter is 07 — get to a shell prompt. Consider pulling 07.1–07.4 forward and
running a trivial ELF binary right after 04.8, before doing phase 05 properly.
Seeing your own program print something is worth more than the ordering purity.

**Around phase 13 (hours 1,100–1,900).** Long, unglamorous, spec-heavy driver
work with no new concepts — just detail. The counter is 13.1: rank the drivers by
what your chosen job actually needs, and write only those. A headless server does
not need audio, a framebuffer, HID, or S3 suspend.

Two structural defences, both cheap:

- **Commit after every exercise with what broke in the message** (a ground rule
  in the main README). Progress becomes visible on weeks it does not feel like it.
- **Tick [PROGRESS.md](PROGRESS.md).** 176 boxes is a lot of boxes, and that is
  the point.

---

## Trimming: ~450 hours of legitimate cuts

None of these break the project. Each loses something specific, stated:

| Cut | Saves | You lose |
|---|---:|---|
| Skip your own bootloader; start at Multiboot2 (01.1–01.6) | 50 | Real mode, A20, the mode switches — 01.7 already tells you to throw this away |
| Skip UEFI (01.9) | 20 | Booting on post-2015 hardware — **do not cut if you plan phase 12** |
| Skip RCU (05.11) | 30 | The read-mostly scaling curve; rwlocks still work |
| Skip ext2 (06.10) | 35 | `fsck.ext2` as a free grader, and Linux being able to read your disk |
| Skip dynamic linking (07.12) | 35 | Shared libraries; static binaries are fine for your own userland |
| Skip the musl port (07.13) | 40 | The honest audit of your syscall semantics — **the most expensive cut on this list** |
| Skip namespaces/cgroups/containers (10.6–10.9) | 85 | Isolation beyond Unix permissions |
| Skip audio (13.15) | 30 | Sound |
| Skip AML/battery/thermal (13.12) | 60 | Laptop use — fine on a desktop or headless box |
| Skip S3 suspend (13.13, keep C-states) | 30 | Suspend/resume; idle power still improves |
| Skip the framebuffer work (13.9) if headless | 20 | A local display; serial + SSH instead |
| **Total** | **~435** | |

**A headless appliance path** — take every cut above except UEFI — lands at
roughly **1,650 hours median**, about 3.2 years at 10 h/week, and still produces
a machine that boots on metal, serves a real job on your network, and runs for
thirty days. That is the cheapest version of the thing you asked for.

**What not to cut:** phase 05 (concurrency bugs you skip do not go away, they
just find you later), 06.11's crash sweep (an untested journal is decoration),
14.3's restore drill (an untested backup is a belief), and 14.13's thirty-day run
(it is the only exercise that proves any of the rest).

---

## Assumptions

- One person, part time, no prior OS development.
- x86-64 only, QEMU until phase 12, C and assembly.
- Solutions are not available to copy from — you are writing them. Working from
  an existing codebase (xv6, for instance) roughly halves phases 01–07 and
  changes what you learn.
- Estimates were built bottom-up per exercise from the limit cases each one
  specifies, then rounded per phase. They are calibrated against published
  course loads (MIT 6.1810 is ~180 hours *with* xv6 provided) and against the
  reported experience of hobby OS projects reaching comparable milestones.
- **This is an estimate for a project no one has run end to end.** The honest
  error bar on the total is wider than the low–high columns suggest — those
  describe variation in execution, not the possibility that a whole phase turns
  out harder than modelled. 13.12 is the most likely candidate.

---

Checklist: [PROGRESS.md](PROGRESS.md). Frame and both tracks: [README.md](README.md).
Sources per exercise: [REFERENCES.md](REFERENCES.md).
