# Phase 02 — Kernel Core: Interrupts, Console, Time

**12 exercises.** The kernel stops being a program that runs once and becomes a
system that responds to events.

---

## The failure that got you here

You are executing C in long mode. Now divide by zero. The CPU raises `#DE`,
looks up vector 0 in the IDT, finds an IDT you never built, raises `#GP` for the
invalid IDT, fails to deliver *that*, raises `#DF`, fails again, and triple-faults
into a reset. Your entire kernel disappears with no message.

**Until a fault has somewhere to go, every bug is the same bug.** This phase is
about making the machine able to tell you what went wrong.

---

## Design decisions

> **DESIGN DECISION — legacy 8259 PIC, or APIC?**
> The PIC is 1981 hardware, has 15 usable lines, cannot do SMP, and takes twenty
> lines of code to program. The local APIC + I/O APIC is what any machine built
> since 1997 actually uses, requires parsing ACPI tables to find, and is the only
> path to a second CPU.
> **Chosen:** PIC first (02.4) to get *any* interrupt working with minimal
> surface, then APIC in 02.10 once you have ACPI parsing. Cost: you write the
> interrupt-controller layer twice. The second time you will design it as an
> interface rather than a driver, which is the actual lesson.

> **DESIGN DECISION — how much work happens inside an interrupt handler?**
> Doing the work in the handler is simple and blocks every other interrupt on
> that line for its duration. Deferring it needs a queue, a context to run in,
> and an answer to "what if it is deferred forever".
> **Chosen:** handlers do the minimum and defer, from 02.9 onward — because
> 02.8's keyboard handler will demonstrate the alternative failing. Linux calls
> the two halves *hardirq* and *softirq*; `[LKD3]` ch. 8 is the reference.

---

## The exercises

### 02.1 — A panic you can read
**Build:** `panic()` — dump all general registers, `RIP`, `RSP`, `RFLAGS`,
`CR0/2/3/4`, a message and a file:line, then halt with interrupts disabled.
**Limit case:** call it from an interrupt handler with a corrupt stack. If your
panic path allocates, takes a lock, or touches a subsystem that may be the thing
that failed, it will fault inside the fault. Make it depend on nothing but the
serial port.
**Done when:** a deliberate `panic("test")` prints a complete machine state and
halts, and it still works when called with `RSP` pointing at unmapped memory.
**Read:** `[LKD3]` ch. 18 (Debugging), `oops` output format; `[XV6]` `panic()`;
`[SDM3]` ch. 6.15 for what each fault's error code means.

### 02.2 — The IDT and the first 32 exceptions
**Build:** a 64-bit IDT, 256 gate descriptors, stubs for vectors 0–31 that push
the vector number (and a dummy error code where the CPU does not push one) and
land in one common C handler.
**Limit case:** the CPU pushes an error code for some vectors and not others —
8, 10, 11, 12, 13, 14, 17, 21 do; the rest do not. If your stubs are uniform,
your stack frame is misaligned for half of them and your `RIP` reporting is
garbage exactly when you need it. Handle it in the stub, not the handler.
**Done when:** `int $0x3`, a `#DE`, a `#UD` and a `#PF` each print the correct
vector, error code and faulting `RIP`.
**Read:** `[SDM3]` ch. 6 (Interrupt and Exception Handling), especially 6.12–6.15;
`[OSDEV]` Interrupt Descriptor Table, Exceptions; `[BLOGOS]` "CPU Exceptions".

### 02.3 — Fault handlers that diagnose, not just report
**Build:** dedicated handlers for `#PF` (decode `CR2` and the error-code bits:
present / write / user / reserved / instruction-fetch), `#GP` (decode the
selector index in the error code), and `#DF`.
**Limit case:** a `#DF` means the fault handler itself faulted, and by then your
kernel stack may be the problem. Give `#DF` its own stack via the IST mechanism in
the TSS. Then deliberately overflow the kernel stack and confirm the double-fault
handler still runs and reports.
**Done when:** an unmapped write prints "write to non-present page at 0x…", a bad
segment load names the offending selector, and a stack overflow reports rather
than resets.
**Read:** `[SDM3]` ch. 6.14.5 (Interrupt Stack Table), ch. 4.7 (Page-Fault
Exceptions); `[OSDEV]` Task State Segment, Double Fault.

### 02.4 — Remap the PIC and take your first hardware IRQ
**Build:** 8259A initialisation (ICW1–ICW4), remapping IRQs 0–15 to vectors
32–47, the mask register, and end-of-interrupt handling.
**Limit case:** *do not* remap, and enable interrupts. IRQ 0 arrives as vector 8
— `#DF`. This collision is why remapping exists, and seeing it makes the ritual
memorable rather than copied. Then: forget an EOI on the slave PIC and watch
every subsequent IRQ above 7 vanish.
**Done when:** you receive an interrupt from real hardware, acknowledge it, and
keep receiving them.
**Read:** Intel 8259A datasheet §Programming; `[OSDEV]` 8259 PIC; `[LITTLEBOOK]`
ch. 7.

### 02.5 — The PIT, and the invention of a tick
**Build:** program channel 0 of the 8253/8254 to a frequency you choose, count
interrupts, and expose `uptime_ms()`.
**Limit case:** pick 1000 Hz, then measure the actual interval against QEMU's
wall clock. It is not exactly 1 ms — the divisor is an integer and the input
clock is 1.193182 MHz. Compute your real tick length and the drift per hour. Every
timekeeping bug in this project descends from ignoring this.
**Done when:** `uptime_ms()` agrees with a stopwatch to within your computed
drift, and you can state that drift in ppm.
**Read:** `[OSDEV]` Programmable Interval Timer; `[LKD3]` ch. 11 (Timers and Time
Management); `[UTLK]` ch. 6.

### 02.6 — A real console
**Build:** VGA text mode (or the boot framebuffer from 01.10): a character cell
writer, scrolling, cursor position, colour, and `putchar`.
**Limit case:** scrolling in text mode is a `memmove` of 4000 bytes on every
newline, done inside whatever context printed. Measure how long that takes; then
print from a timer interrupt at 1000 Hz and watch the machine spend all its time
scrolling. Note it. It is the first performance failure of the project and the
shape of many later ones.
**Done when:** text wraps, scrolls, and survives being written from both normal
and interrupt context.
**Read:** `[OSDEV]` VGA Hardware, Text Mode Cursor; `[LITTLEBOOK]` ch. 6.

### 02.7 — `printf` for a kernel
**Build:** `kprintf` with `%d %u %x %p %s %c`, width and zero-padding, writing to
both console and serial.
**Limit case:** it must work with no heap (you have none), be re-entrant enough to
call from an interrupt, and never itself allocate. Then try calling it from two
contexts at once — an interrupt during a `kprintf` — and watch the output
interleave mid-line. You have just found the need for a lock, three phases before
you build one. Write down the interim fix (disable interrupts around it) and its
cost.
**Done when:** formatted output is correct, and interleaving is either impossible
or documented as a known hazard with a plan.
**Read:** `[LKD3]` ch. 18 on `printk` and its ring buffer; `[KDOC]`
`Documentation/core-api/printk-basics.rst`; `[CSAPP]` ch. 8.

### 02.8 — Keyboard: your first stateful device
**Build:** a PS/2 keyboard driver — scancode set 1, make/break codes, modifier
state, a scancode-to-ASCII map, and a ring buffer the interrupt fills.
**Limit case:** do the translation and the echo *inside* the handler, then hold a
key down while a slow operation runs. Characters are lost, because IRQ 1 is
masked while you are in it. Move the work to a buffer consumed outside interrupt
context. This is the concrete case that motivates 02.9.
**Done when:** typing fast loses nothing, modifiers work, and the handler itself
does nothing but read the port and enqueue.
**Read:** `[OSDEV]` PS/2 Keyboard, "8042" PS/2 Controller; `[LDD3]` ch. 10
(Interrupt Handling), "top and bottom halves"; `[P-LIVELOCK96]` — read it now,
because 02.8 is a miniature of exactly the failure it describes.

### 02.9 — Deferred work: your softirq
**Build:** a mechanism for interrupt handlers to queue work that runs later with
interrupts enabled — a bitmask of pending handlers, drained on the way out of the
interrupt path.
**Limit case:** work queued from within deferred work. If you drain in a loop, a
device that keeps queueing starves everything else; if you drain once, latency
grows unboundedly. Pick a policy, and construct the workload that makes it behave
badly. (Linux's answer is `ksoftirqd`, and it exists for this exact reason.)
**Done when:** the keyboard handler is three lines, and you can show deferred work
running with `IF=1` and being preempted by a new interrupt.
**Read:** `[LKD3]` ch. 8 (Bottom Halves and Deferring Work) in full; `[UTLK]`
ch. 4; `[P-LIVELOCK96]` again, now that you have built it.

### 02.10 — ACPI tables, the APIC, and the modern interrupt path
**Build:** find the RSDP, walk RSDT/XSDT, validate checksums, parse the MADT to
enumerate local APICs and I/O APICs; then initialise the local APIC, mask the
PIC, and route IRQs through the I/O APIC with the interrupt source overrides the
MADT specifies.
**Limit case:** the MADT's *Interrupt Source Override* entries exist because IRQ
0 is usually not GSI 0 and the PIT is often on GSI 2. Ignore them and your timer
silently never fires, or fires as the wrong device. Handle them, and print the
resulting IRQ→GSI map.
**Done when:** the timer and keyboard work with the PIC fully masked, and you
have a printed table of every interrupt source the firmware declared.
**Read:** `[ACPI]` §5.2.12 (MADT); `[SDM3]` ch. 12 (APIC) in full; `[OSDEV]`
APIC, IOAPIC, RSDP, MADT.

### 02.11 — The local APIC timer and a calibrated clock
**Build:** the LAPIC timer in periodic and one-shot mode, calibrated against the
PIT (or HPET), plus `rdtsc` with the invariant-TSC check.
**Limit case:** the LAPIC timer counts at the bus frequency, which you are not
told. Calibrate it: run it against a known PIT interval, twice, and compare. Then
find the case where `rdtsc` is *not* a valid clock — a CPU without invariant TSC,
or across a frequency change — and decide what your `now()` does about it.
**Done when:** you have a per-CPU timer with a known frequency, and a `now()` you
have justified.
**Read:** `[SDM3]` ch. 12.5 (APIC Timer), ch. 17.17 (Time-Stamp Counter);
`[KDOC]` `Documentation/timers/timekeeping.rst`; `[LKD3]` ch. 11.

### 02.12 — Measure the interrupt path
**Build:** an instrumented count of interrupts per source (an `/proc/interrupts`
in miniature), plus a measured cost in cycles for entry, handler, and return.
**Limit case:** measure with `rdtsc` inside the handler, and then measure again
with the *deferred* path from 02.9 in use. Predict both numbers before you print
them. If entry costs more than you expected, find out how much of it is the CPU's
own state save and how much is yours.
**Done when:** you can state, in cycles, what one interrupt costs your kernel —
and you will quote this number for the rest of the project.
**Read:** `[SDM3]` ch. 6.12 for what the CPU saves; `[HP6]` App. C on pipeline
flush costs; `[P-SCALE10]` for how these numbers behave at scale.

---

## Where this phase stops

- **No SMP.** One CPU, one interrupt controller, no locking. The other cores are
  sitting in a halt loop and stay there until phase 05.
- **No MSI/MSI-X.** PCI message-signalled interrupts wait for phase 08, where
  there is a PCI bus to attach them to.
- **No timer wheel or high-resolution timers.** You get a tick, not `hrtimers`.
  Phase 04 needs the tick; phase 08 will want better.
- **No power management.** No C-states, no idle governor. Your idle loop is `hlt`.
- **No `#MC`, no NMI handling.** Machine checks and NMIs are real, rare, and a
  distraction here.

---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
