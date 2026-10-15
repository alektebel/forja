# Phase 00 — Toolchain and Ground Truth

**6 exercises.** Before you write a single instruction that runs on bare metal,
you need a compiler that does not secretly assume Linux is underneath it, an
emulator you can stop mid-instruction, and a way to see what the machine actually
did rather than what you believe it did.

Skip this phase and you will spend phase 01 debugging your kernel when the bug is
in your linker script.

---

## The failure that got you here

Nothing yet. This is the ground floor. But here is the failure it prevents: you
write `hello.c`, compile it with your system `gcc`, and it does not boot. It
cannot boot. Your `gcc` emitted a dynamically-linked ELF that expects `ld.so`, a
`_start` from `crt1.o`, a stack set up by the kernel, and a `write(2)` behind
`printf`. Every one of those is a thing you have not built yet.

**A hosted toolchain compiles programs for an OS. You are writing the OS.**

---

## Design decisions

> **DESIGN DECISION — cross-compiler, or `-ffreestanding` on the host compiler?**
> The host compiler with `-ffreestanding -nostdlib` mostly works, and every
> tutorial that takes this shortcut eventually hits a case where the host's
> default target leaks in: a libgcc built for the wrong ABI, a linker that
> silently inserts a `.note.gnu.property`, a stack-protector reference to a
> symbol that does not exist. The failures are late and confusing.
> **Chosen:** build a real `x86_64-elf` cross-compiler. It costs an afternoon and
> it removes an entire category of bug that you would otherwise misdiagnose as a
> kernel bug. Cost: an afternoon, and a build you must repeat if you change host.

> **DESIGN DECISION — emulator or real hardware?**
> Real hardware is the honest target and gives you nothing to debug with: a
> triple fault is a reboot, with no register dump.
> **Chosen:** QEMU throughout, real hardware in phase 12. Cost: QEMU is more
> forgiving than a real machine in specific, documented ways (it tolerates some
> illegal descriptor states, its timing is not real). Phase 12 exists precisely
> to find what you got away with.

---

## The exercises

### 00.1 — Build an `x86_64-elf` cross-toolchain
**Build:** binutils and GCC configured `--target=x86_64-elf --without-headers
--disable-nls --enable-languages=c`, installed to a prefix on your `PATH`.
**Limit case:** try to compile a trivial `.c` with your *host* gcc and `-nostdlib`,
then compare `readelf -h` output and the symbols pulled in from `libgcc` against
the cross-compiler's. Name every difference.
**Done when:** `x86_64-elf-gcc -v` reports your target, and `x86_64-elf-gcc
-ffreestanding -c` on a file calling `__udivti3` links against your `libgcc`
without touching `/usr/lib`.
**Read:** `[OSDEV]` GCC Cross-Compiler; `[CLFS]` ch. on the cross toolchain — read
it *now* even though it is Track D, because it explains the two-pass bootstrap you
are doing a one-pass version of; `[LINKLOAD]` ch. 1–3.

### 00.2 — A linker script you can defend
**Build:** an `ld` script placing `.text`, `.rodata`, `.data`, `.bss` at a load
address you chose, with symbols marking the start and end of each and of the
kernel image as a whole.
**Limit case:** put an initialised global and an uninitialised global in the same
program. Find both in the ELF. Explain why one occupies file bytes and the other
does not, and what must therefore happen before `main` runs.
**Done when:** `readelf -S` and `objdump -h` on your output match the addresses
you specified, and `nm` shows your `__bss_start` / `__bss_end` symbols bracketing
exactly the `.bss` section.
**Read:** `[LINKLOAD]` ch. 3, 7; `[ELF]` §Sections, §Program Header; GNU `ld`
manual, "Scripts".

### 00.3 — Freestanding C, and what you just lost
**Build:** a `.c` file compiled `-ffreestanding -fno-stack-protector -fno-pic
-mno-red-zone -mcmodel=kernel` that produces a flat binary.
**Limit case:** write a struct copy and a large `memset`-shaped loop, compile at
`-O2`, and find where GCC emitted a call to `memcpy`/`memset` you never wrote.
This is the freestanding contract: the compiler still assumes those four
functions exist. Note which four.
**Done when:** you can state, from the disassembly, why `-mno-red-zone` is
mandatory for any code an interrupt can land on.
**Read:** GCC manual, `-ffreestanding` and "Standards"; `[ELF]` x86-64 psABI
§3.2.2 (the red zone); `[OSDEV]` Red Zone, Libgcc.

### 00.4 — QEMU as an instrument
**Build:** a `make run` target booting your (still empty) image under QEMU, plus
`make debug` with `-s -S`, and a `-d int,cpu_reset -D qemu.log` variant.
**Limit case:** cause a deliberate triple fault (jump to address 0 with no IDT).
Read the reset loop in `qemu.log`, and identify from the log which fault escalated
to which.
**Done when:** you can single-step from the first instruction the CPU executes,
and you can dump control registers at any point.
**Read:** QEMU documentation, "System Emulation" and the `-d` option list;
`[SDM3]` ch. 6.15 (Exception and Interrupt Reference), double fault conditions.

### 00.5 — GDB against a machine with no OS
**Build:** a `.gdbinit` that connects to `:1234`, sets the architecture correctly
across the 16→32→64-bit transitions, and defines helpers to dump the GDT, IDT,
and current `CR0/CR3/CR4/EFER`.
**Limit case:** the transition itself. Set a breakpoint in 16-bit real mode, step
through the switch to protected mode, and watch GDB start disassembling garbage
because it is still decoding 16-bit. Fix it with `set architecture`. You will hit
this again in phase 01 and it will cost you a day if you have not seen it.
**Done when:** you can break on a physical address, print a descriptor's fields
by hand from memory, and confirm they match what you wrote.
**Read:** GDB manual, "Remote Debugging" and "Architectures"; `[SDM3]` ch. 3
(Protected-Mode Memory Management) for the descriptor layout you are decoding.

### 00.6 — Build system, image, and reproducibility
**Build:** a Makefile producing a bootable disk image from sources, with a
`clean` that really is clean, and dependency tracking that rebuilds on header
changes.
**Limit case:** build twice and `cmp` the two images. If they differ, find why
(timestamps, build paths, `__DATE__`, linker ordering) and eliminate it. A kernel
whose image changes when nothing changed is a kernel whose bugs you cannot bisect.
**Done when:** two clean builds are byte-identical, and touching one header
rebuilds exactly the objects that include it.
**Read:** `[P-REPRO]`; GNU Make manual, "Automatic Prerequisites"; `[P-TRUST84]`
— read this once now, and again before phase 11.

---

## Where this phase stops

- **No `configure`/autotools of your own.** You are consuming a build system in
  00.1, not writing one.
- **No LLVM path.** `clang -target x86_64-elf` is a legitimate alternative and
  needs no cross-build; it is left as a variation, not the main line, because
  every reference text you will read assumes the GNU toolchain's behaviour.
- **No reproducible-build infrastructure.** 00.6 gets you byte-identical local
  builds, not a verifiable supply chain. That argument returns in phase 11.

---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
