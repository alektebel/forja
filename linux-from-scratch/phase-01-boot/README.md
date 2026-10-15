# Phase 01 — Boot: From Power-On to Your Code

**10 exercises.** The first byte the CPU executes, and the four escalating
environments it must pass through before C is even possible.

---

## The failure that got you here

Your toolchain produces a perfectly good ELF file and the machine has no idea
what an ELF file is. At reset, an x86 CPU is a 1978 8086: 16-bit real mode, 1 MiB
of addressable memory, segment:offset addressing, no protection, no paging, and a
single instruction pointer at `0xFFFF0`. Everything you know about how programs
run is a service that does not exist yet.

Boot is the process of building, in stages, the environment your compiler already
assumed.

---

## Design decisions

> **DESIGN DECISION — write your own bootloader, or use GRUB?**
> Writing your own teaches you real mode, the BIOS disk interface, the A20 line,
> and the protected-mode switch — genuinely foundational, and a stack of details
> that stopped mattering to anyone in about 2005. Using GRUB with Multiboot2
> hands you a 32-bit environment, a memory map, and your kernel loaded from ELF,
> in exchange for learning none of that.
> **Chosen:** both, in order. Exercises 01.1–01.6 write your own to the point of
> executing 32-bit C; 01.7 then switches to Multiboot2 and *deletes* that code.
> Cost: you throw away a week of work on purpose. That is the cheapest possible
> version of a lesson every OS project learns eventually — the boot path is not
> where your kernel's value is.

> **DESIGN DECISION — BIOS/MBR or UEFI?**
> BIOS is simpler, universally emulated, and dead. UEFI is what your actual
> hardware runs, gives you a memory map and a framebuffer without touching
> hardware, and is a large specification.
> **Chosen:** BIOS for the learning path, UEFI as exercise 01.9 — because phase
> 12 boots on real hardware, and that machine is very unlikely to offer CSM.

---

## The exercises

### 01.1 — A boot sector that prints one character
**Build:** 512 bytes of 16-bit assembly ending in `0x55AA`, using BIOS `int 0x10`
to print a character, then halting.
**Limit case:** count your bytes. Print a whole string and you are already
noticeably closer to 510. This constraint is the entire lesson of the phase:
**the first stage cannot contain your kernel, so it must be able to load code.**
**Done when:** QEMU shows the character, and `xxd` of your image shows the
signature at offset 510.
**Read:** `[OSDEV]` Boot Sequence, Real Mode, BIOS; `[OS01]` ch. on the boot
sector; `[SDM3]` ch. 9.1 (Processor State After Reset).

### 01.2 — Real-mode addressing, and the 1 MiB wall
**Build:** routines that read and write memory above 64 KiB using explicit
segment registers, and a print-hex routine you will use for the rest of the phase.
**Limit case:** compute the physical address for `0xFFFF:0xFFFF`. It exceeds 1 MiB.
Find out what the 8086 did, what the 80286 did differently, and why a wire called
A20 exists at all.
**Done when:** you can print an arbitrary physical address's contents from real
mode, and you can explain segment:offset aliasing (many pairs, one address).
**Read:** `[SDM3]` ch. 20 (8086 Emulation) and ch. 3.3; `[OSDEV]` A20 Line,
Segmentation.

### 01.3 — Load a second stage from disk
**Build:** BIOS `int 0x13` (LBA extension, function `0x42`) reading sectors into
memory and jumping to them.
**Limit case:** ask for more sectors than fit under the 64 KiB segment boundary,
or across a track boundary on the CHS interface. Handle the short read. A loader
that reads "usually the right amount" corrupts your kernel intermittently, which
is the worst class of bug you can give yourself this early.
**Done when:** stage 2 is >512 bytes, prints from an address you chose, and you
verify the loaded bytes against the image with a checksum computed both sides.
**Read:** `[OSDEV]` ATA in x86 RealMode (BIOS), Disk access using the BIOS;
Phoenix *EDD* specification §Extended Read.

### 01.4 — Query the memory map before you can trust memory
**Build:** an `int 0x15, eax=0xE820` loop collecting the E820 memory map, printed
as a table of base/length/type.
**Limit case:** the map is not sorted, not contiguous, may contain overlapping
entries, and reserved regions sit in the middle of what looks like plain RAM.
Write down which regions you must never allocate — you will need this exact table
in phase 03 and getting it wrong there presents as random corruption.
**Done when:** your printed map matches QEMU's `-m` setting, accounts for the
hole below 1 MiB, and you have identified the ACPI-reclaimable regions.
**Read:** `[OSDEV]` Detecting Memory (x86); `[ACPI]` §15 (System Address Map
Interfaces); `[SDM3]` ch. 11.11 (MTRRs) for why some ranges behave differently.

### 01.5 — Enable A20, build a GDT, enter protected mode
**Build:** the A20 enable (try the fast gate, verify it, fall back), a flat GDT
with a code and a data descriptor, `lgdt`, set `CR0.PE`, and the far jump that
reloads `CS`.
**Limit case:** *do not* do the far jump. Observe what executes. The pipeline is
still decoding with the old segment semantics — this is the concrete reason the
manual says the jump is required, and it is worth seeing once.
**Done when:** you are executing 32-bit instructions, `CR0.PE=1`, and GDB (with
`set architecture i386`) disassembles correctly.
**Read:** `[SDM3]` ch. 9.9 (Mode Switching) — this is a procedure, follow it
exactly — and ch. 3.4 (Segment Descriptors); `[OSDEV]` Protected Mode, GDT
Tutorial, A20 Line.

### 01.6 — Enter long mode, and reach C
**Build:** identity-mapped page tables (PML4 → PDPT → PD, 2 MiB pages are fine),
`CR4.PAE`, `EFER.LME`, `CR0.PG`, a 64-bit GDT, the far jump, a stack, `.bss`
zeroed, then `call kmain`.
**Limit case:** long mode requires paging *before* it will engage. You are
building a page table while you have no memory allocator, no C, and no printf.
Notice that this is the only place in the entire OS where that ordering is
forced — and that it is why the first page tables are always statically allocated.
**Done when:** a C function runs in 64-bit mode, writes to a global in `.bss`,
reads it back, and you confirm `CR0.PG`, `CR4.PAE` and `EFER.LMA` from GDB.
**Read:** `[SDM3]` ch. 9.8.5 (Initializing IA-32e Mode) and ch. 5 (Paging);
`[APM2]` ch. 14.6 — often clearer here; `[BLOGOS]` "A Minimal Rust Kernel" and
"Introduction to Paging" for the clearest modern walkthrough of this exact
sequence.

### 01.7 — Throw it away: Multiboot2 and GRUB
**Build:** a Multiboot2 header, a kernel GRUB loads directly as ELF64, and code
that reads the boot information tags GRUB provides.
**Limit case:** compare, item by item, what you spent 01.1–01.6 building against
what GRUB handed you in one struct. Then find the things GRUB does *not* give you
and you still must do yourself. That list is the real boundary of a bootloader.
**Done when:** `grub-mkrescue` produces an ISO that boots your kernel, and you
print the memory map from the Multiboot2 tags instead of your E820 code.
**Read:** `[MB2]` in full — it is short; `[OSDEV]` Multiboot; GRUB manual,
"Multiboot2 Specification".

### 01.8 — Serial output, because the screen is not a debugger
**Build:** a 16550 UART driver (COM1, `0x3F8`): initialise the divisor, poll LSR,
write bytes. Route a minimal `printf` to it.
**Limit case:** call it from inside the mode-switch code, before you have a
stack. Then call it from an interrupt handler. A logging path with a dependency
on the thing you are debugging is not a logging path.
**Done when:** `qemu -serial file:serial.log` captures output from your earliest
code, and `printf("%p")` works.
**Read:** `[OSDEV]` Serial Ports; National Semiconductor PC16550D datasheet
(register map, §Line Status); `[LDD3]` ch. 4 (Debugging Techniques) for the
argument about printk-style debugging in general.

### 01.9 — Boot the same kernel under UEFI
**Build:** a UEFI application entry point that obtains the memory map, calls
`ExitBootServices()`, and jumps into your kernel — either via GNU-EFI/POSIX-UEFI
or by targeting the loader protocol from GRUB's EFI build.
**Limit case:** `GetMemoryMap()` invalidates its own map key if anything allocates
in between, so `ExitBootServices()` fails and you must retry the whole sequence.
Build the retry loop and force it to trigger. This is the single most common UEFI
boot bug.
**Done when:** the same kernel image boots under both OVMF and BIOS QEMU, having
detected which environment it is in.
**Read:** `[UEFI]` §2 (Overview), §7.2 (Memory Allocation Services), §7.4
(`ExitBootServices`); `[OSDEV]` UEFI, GNU-EFI.

### 01.10 — Boot-time state, written down
**Build:** a single `boot_info` struct your kernel receives, normalised across
BIOS/Multiboot2/UEFI, containing the memory map, the framebuffer, ACPI RSDP,
command line, and initrd location.
**Limit case:** three boot paths, one struct. Each gives you a different subset,
in a different format, with different lifetimes — the UEFI map is only valid
before `ExitBootServices`, the Multiboot2 tags live in memory you are about to
allocate over. Copy what you need before it dies.
**Done when:** `kmain` has one parameter, and nothing after it knows how you
booted.
**Read:** `[LINSIDES]` "Kernel booting process" — Linux does exactly this and
calls it `boot_params`; `[KDOC]` `Documentation/arch/x86/boot.rst`.

---

## Where this phase stops

- **No chainloading, no partition tables, no filesystem in the bootloader.**
  Your stage 2 reads raw LBAs. GRUB does the rest from 01.7 onward.
- **No Secure Boot, no shim, no signed kernels.** A real concern for a real
  distribution; it belongs to phase 11's discussion, not here.
- **No 32-bit protected-mode kernel.** You pass through protected mode and leave;
  everything after this is long mode. If you want to write a 32-bit kernel, this
  is the branch point.
- **Real-mode BIOS services are gone after 01.6.** Once you leave real mode you
  cannot call `int 0x10` or `int 0x13` again. Everything from here — disk,
  screen, keyboard — you write yourself. That is the deal.

---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
