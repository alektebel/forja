# Progress

176 exercises, ~2,100 hours ([ESTIMATES.md](ESTIMATES.md)). Tick as you go. The last line of each phase is for the graded
checker you write once that phase is complete — see
[README.md](README.md#verification).

Track K is the kernel (phases 00–10, 12–14). Track D is the distribution
(phase 11), and is best done early, in parallel with phase 02.

Phases 13 and 14 are the ones that turn a kernel that boots into a machine you
use: every driver your actual hardware needs, then thirty days of real service.
Read [phase-14-daily-driver/README.md](phase-14-daily-driver/README.md)'s scope
discussion before starting phase 13 — it decides what you are aiming at.

## Phase 00 — Toolchain and Ground Truth

[phase-00-toolchain/README.md](phase-00-toolchain/README.md) — 6 exercises

- [ ] 00.1 — Build an `x86_64-elf` cross-toolchain
- [ ] 00.2 — A linker script you can defend
- [ ] 00.3 — Freestanding C, and what you just lost
- [ ] 00.4 — QEMU as an instrument
- [ ] 00.5 — GDB against a machine with no OS
- [ ] 00.6 — Build system, image, and reproducibility

- [ ] `check.py` for this phase

## Phase 01 — Boot: From Power-On to Your Code

[phase-01-boot/README.md](phase-01-boot/README.md) — 10 exercises

- [ ] 01.1 — A boot sector that prints one character
- [ ] 01.2 — Real-mode addressing, and the 1 MiB wall
- [ ] 01.3 — Load a second stage from disk
- [ ] 01.4 — Query the memory map before you can trust memory
- [ ] 01.5 — Enable A20, build a GDT, enter protected mode
- [ ] 01.6 — Enter long mode, and reach C
- [ ] 01.7 — Throw it away: Multiboot2 and GRUB
- [ ] 01.8 — Serial output, because the screen is not a debugger
- [ ] 01.9 — Boot the same kernel under UEFI
- [ ] 01.10 — Boot-time state, written down

- [ ] `check.py` for this phase

## Phase 02 — Kernel Core: Interrupts, Console, Time

[phase-02-kernel-core/README.md](phase-02-kernel-core/README.md) — 12 exercises

- [ ] 02.1 — A panic you can read
- [ ] 02.2 — The IDT and the first 32 exceptions
- [ ] 02.3 — Fault handlers that diagnose, not just report
- [ ] 02.4 — Remap the PIC and take your first hardware IRQ
- [ ] 02.5 — The PIT, and the invention of a tick
- [ ] 02.6 — A real console
- [ ] 02.7 — `printf` for a kernel
- [ ] 02.8 — Keyboard: your first stateful device
- [ ] 02.9 — Deferred work: your softirq
- [ ] 02.10 — ACPI tables, the APIC, and the modern interrupt path
- [ ] 02.11 — The local APIC timer and a calibrated clock
- [ ] 02.12 — Measure the interrupt path

- [ ] `check.py` for this phase

## Phase 03 — Memory: Frames, Pages, Address Spaces, Heap

[phase-03-memory/README.md](phase-03-memory/README.md) — 13 exercises

- [ ] 03.1 — A physical memory map you trust
- [ ] 03.2 — A bitmap frame allocator
- [ ] 03.3 — Read the page tables that are already there
- [ ] 03.4 — Map and unmap, with the invalidation you will forget
- [ ] 03.5 — Permissions, and W^X
- [ ] 03.6 — Move the kernel to the higher half
- [ ] 03.7 — Address spaces as objects
- [ ] 03.8 — A buddy allocator
- [ ] 03.9 — A slab allocator
- [ ] 03.10 — `kmalloc`, `vmalloc`, and why both exist
- [ ] 03.11 — Demand paging
- [ ] 03.12 — Copy-on-write
- [ ] 03.13 — Eviction policy, and the honest version of LRU

- [ ] `check.py` for this phase

## Phase 04 — Processes, Syscalls, Scheduling

[phase-04-processes/README.md](phase-04-processes/README.md) — 13 exercises

- [ ] 04.1 — The task structure and the kernel stack
- [ ] 04.2 — Context switch
- [ ] 04.3 — Ring 3
- [ ] 04.4 — The first syscall, via `int`
- [ ] 04.5 — `syscall`/`sysret`, and what it does not do for you
- [ ] 04.6 — A round-robin scheduler, cooperative
- [ ] 04.7 — Blocking, wait queues, and sleep
- [ ] 04.8 — `fork`, `exec`, `wait`, `exit`
- [ ] 04.9 — Preemption
- [ ] 04.10 — Priorities and MLFQ
- [ ] 04.11 — Fair-share scheduling
- [ ] 04.12 — Signals
- [ ] 04.13 — Measure the process abstraction

- [ ] `check.py` for this phase

## Phase 05 — Concurrency and SMP

[phase-05-concurrency-smp/README.md](phase-05-concurrency-smp/README.md) — 12 exercises

- [ ] 05.1 — Boot the other CPUs
- [ ] 05.2 — Atomics and barriers
- [ ] 05.3 — Spinlocks, and their cost
- [ ] 05.4 — A big kernel lock, and an audit
- [ ] 05.5 — Measure the BKL, then break it
- [ ] 05.6 — Deadlock, on purpose and then never again
- [ ] 05.7 — Sleeping locks: mutexes, semaphores, rwlocks
- [ ] 05.8 — Per-CPU data
- [ ] 05.9 — SMP scheduling and load balancing
- [ ] 05.10 — Futexes
- [ ] 05.11 — RCU
- [ ] 05.12 — Concurrency testing that actually finds bugs

- [ ] `check.py` for this phase

## Phase 06 — Storage: Block Devices, VFS, Filesystems

[phase-06-storage-fs/README.md](phase-06-storage-fs/README.md) — 14 exercises

- [ ] 06.1 — ATA PIO: bytes off a disk
- [ ] 06.2 — virtio-blk, and what a queue buys
- [ ] 06.3 — A block layer
- [ ] 06.4 — A buffer cache
- [ ] 06.5 — Ordering, barriers, and the lying disk
- [ ] 06.6 — Design your on-disk format
- [ ] 06.7 — Implement it: read path
- [ ] 06.8 — Implement it: write path
- [ ] 06.9 — A VFS layer
- [ ] 06.10 — ext2, and a filesystem Linux can read
- [ ] 06.11 — A journal
- [ ] 06.12 — The page cache, and unifying it with the buffer cache
- [ ] 06.13 — `mmap`
- [ ] 06.14 — Measure the storage stack

- [ ] `check.py` for this phase

## Phase 07 — Userspace: ELF, libc, init, Shell, TTY

[phase-07-userspace/README.md](phase-07-userspace/README.md) — 14 exercises

- [ ] 07.1 — An ELF loader
- [ ] 07.2 — The initial process stack
- [ ] 07.3 — A minimal libc
- [ ] 07.4 — File descriptors
- [ ] 07.5 — Pipes
- [ ] 07.6 — A TTY layer
- [ ] 07.7 — Sessions, process groups, job control
- [ ] 07.8 — init: PID 1
- [ ] 07.9 — A shell
- [ ] 07.10 — Coreutils, enough of them
- [ ] 07.11 — `/proc` and `/sys`
- [ ] 07.12 — Dynamic linking
- [ ] 07.13 — Port musl, and let it judge your kernel
- [ ] 07.14 — Measure the userspace boundary

- [ ] `check.py` for this phase

## Phase 08 — Devices and Drivers

[phase-08-drivers/README.md](phase-08-drivers/README.md) — 11 exercises

- [ ] 08.1 — PCI configuration space
- [ ] 08.2 — BARs, MMIO, and resource assignment
- [ ] 08.3 — A device model
- [ ] 08.4 — DMA
- [ ] 08.5 — MSI and MSI-X
- [ ] 08.6 — Character devices and `/dev`
- [ ] 08.7 — Loadable modules
- [ ] 08.8 — A framebuffer and a graphics console
- [ ] 08.9 — Hotplug, power, and the device lifecycle
- [ ] 08.10 — A userspace driver, for comparison
- [ ] 08.11 — Measure the I/O path

- [ ] `check.py` for this phase

## Phase 09 — Networking: NIC to TCP to Sockets

[phase-09-networking/README.md](phase-09-networking/README.md) — 14 exercises

- [ ] 09.1 — A NIC driver
- [ ] 09.2 — Ethernet
- [ ] 09.3 — A packet buffer
- [ ] 09.4 — ARP
- [ ] 09.5 — IPv4
- [ ] 09.6 — Fragmentation and reassembly
- [ ] 09.7 — ICMP
- [ ] 09.8 — UDP and the socket API
- [ ] 09.9 — TCP: connection management
- [ ] 09.10 — TCP: reliable data transfer
- [ ] 09.11 — TCP: flow control and congestion control
- [ ] 09.12 — Receive livelock, and NAPI
- [ ] 09.13 — Multiplexing: `select`, `poll`, `epoll`
- [ ] 09.14 — A server, and the numbers

- [ ] `check.py` for this phase

## Phase 10 — Security and Isolation

[phase-10-security-isolation/README.md](phase-10-security-isolation/README.md) — 12 exercises

- [ ] 10.1 — Users, groups, credentials
- [ ] 10.2 — File permissions
- [ ] 10.3 — `setuid` binaries, and their entire problem
- [ ] 10.4 — Resource limits
- [ ] 10.5 — Audit the syscall boundary
- [ ] 10.6 — Namespaces: PID and mount
- [ ] 10.7 — Namespaces: user, network, UTS, IPC
- [ ] 10.8 — cgroups
- [ ] 10.9 — A container, from your own parts
- [ ] 10.10 — Capabilities and a security hook layer
- [ ] 10.11 — Kernel hardening
- [ ] 10.12 — Seccomp: a syscall filter

- [ ] `check.py` for this phase

## Phase 11 — Track D: A Real Linux System, Built From Source

[phase-11-real-linux-lfs/README.md](phase-11-real-linux-lfs/README.md) — 10 exercises

- [ ] 11.1 — The host, and what you are trusting
- [ ] 11.2 — Cross-toolchain, pass 1
- [ ] 11.3 — glibc and libstdc++, and the toolchain's second pass
- [ ] 11.4 — Temporary tools, and `chroot`
- [ ] 11.5 — The final system: ~80 packages
- [ ] 11.6 — Configure a real kernel and boot it
- [ ] 11.7 — Boot to userspace: init, mounts, devices
- [ ] 11.8 — Beyond LFS: make it useful
- [ ] 11.9 — Package management: the problem you have been ignoring
- [ ] 11.10 — Audit: what is running, and why

- [ ] `check.py` for this phase

## Phase 12 — Integration: Real Hardware, Real Software, Real Numbers

[phase-12-integration/README.md](phase-12-integration/README.md) — 6 exercises

- [ ] 12.1 — Boot on real hardware
- [ ] 12.2 — Run software you did not write
- [ ] 12.3 — Self-hosting
- [ ] 12.4 — Benchmark against Linux, honestly
- [ ] 12.5 — Close the biggest gap
- [ ] 12.6 — Write it down

- [ ] `check.py` for this phase

## Phase 13 — Drivers for Real Hardware

[phase-13-real-hardware/README.md](phase-13-real-hardware/README.md) — 15 exercises

- [ ] 13.1 — Inventory the machine, then plan the work
- [ ] 13.2 — AHCI: the SATA disk
- [ ] 13.3 — NVMe: the SSD
- [ ] 13.4 — xHCI: the USB host controller
- [ ] 13.5 — USB enumeration
- [ ] 13.6 — USB HID: a keyboard you can type on
- [ ] 13.7 — USB mass storage
- [ ] 13.8 — An input subsystem
- [ ] 13.9 — The display: a framebuffer worth looking at
- [ ] 13.10 — The real network interface
- [ ] 13.11 — Firmware loading, and what you are trusting
- [ ] 13.12 — ACPI beyond the tables: AML, battery, lid, thermal
- [ ] 13.13 — Power management: idle, frequency, and suspend
- [ ] 13.14 — The IOMMU
- [ ] 13.15 — Audio

- [ ] `check.py` for this phase

## Phase 14 — Daily Driver: Actually Using It

[phase-14-daily-driver/README.md](phase-14-daily-driver/README.md) — 14 exercises

- [ ] 14.1 — Choose the job, and set the bar
- [ ] 14.2 — Crash-only: recovery as the normal path
- [ ] 14.3 — Data you cannot lose
- [ ] 14.4 — Time that is actually correct
- [ ] 14.5 — A terminal you can work in
- [ ] 14.6 — The tools to do work
- [ ] 14.7 — The network as it actually is
- [ ] 14.8 — TLS, and reaching the modern internet
- [ ] 14.9 — Remote access
- [ ] 14.10 — Know what it is doing
- [ ] 14.11 — Upgrade without reinstalling
- [ ] 14.12 — Security posture for a machine on a real network
- [ ] 14.13 — The thirty-day run
- [ ] 14.14 — The verdict

- [ ] `check.py` for this phase

