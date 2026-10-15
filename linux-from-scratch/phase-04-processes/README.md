# Phase 04 — Processes, Syscalls, Scheduling

**13 exercises.** Where the kernel stops being the program and starts being the
thing that runs other programs.

---

## The failure that got you here

You have address spaces and nothing to put in them. Everything runs in ring 0,
which means every line of code you will ever run can write to `CR3`, mask
interrupts, and halt the machine. There is exactly one thread of control, so a
loop that does not return never returns.

**A process is two inventions at once:** a saved execution context you can switch
between, and a privilege boundary that makes the switch enforceable.

---

## Design decisions

> **DESIGN DECISION — `syscall/sysret`, or a software interrupt?**
> `int 0x80` reuses the IDT machinery you already have — no new concepts, and it
> costs roughly 3–5× more cycles because it does a full descriptor-based entry.
> `syscall` is a fast path with MSR-configured entry, and it hands you a
> genuinely dangerous detail: it does not switch the stack for you.
> **Chosen:** `int` first (04.4) so a syscall works in an afternoon, then
> `syscall` (04.5) once you have something to measure. Measure both. The ratio is
> a number you should carry.

> **DESIGN DECISION — kernel threads and user threads, or processes only?**
> A separate `thread` concept sharing an address space is more machinery; Linux's
> answer is that there is no distinction — `clone()` takes flags and a "process"
> is just a task that did not share.
> **Chosen:** one `task` type with sharing flags, as Linux does. Cost: you must
> get the refcounting right on every shared resource from the start, which is
> harder than two types would have been. Benefit: you will understand what
> `clone(CLONE_VM|CLONE_FILES|...)` actually means.

> **DESIGN DECISION — cooperative or preemptive?**
> Cooperative scheduling needs no locking discipline and dies to one infinite
> loop. Preemption means your kernel can be interrupted between any two
> instructions, which is where every race you will ever have comes from.
> **Chosen:** cooperative in 04.6, preemptive in 04.9, *deliberately in that
> order* — so that the first race you debug is one you caused on purpose.

---

## The exercises

### 04.1 — The task structure and the kernel stack
**Build:** a `task` struct (id, state, address space, kernel stack, saved
context, parent, exit code) and a per-task kernel stack with a guard page.
**Limit case:** overflow the kernel stack on purpose. With the guard page it is a
clean `#PF`; without it, it silently overwrites the adjacent task's struct — the
classic "impossible" bug. Size the stack, and justify the size.
**Done when:** overflow faults with a recognisable message naming the task.
**Read:** `[LKD3]` ch. 3 (Process Management), `task_struct` and `thread_info`;
`[XV6]` ch. 7; `[UTLK]` ch. 3.

### 04.2 — Context switch
**Build:** `switch_to(prev, next)` in assembly: save callee-saved registers and
`RSP` into `prev`, load from `next`, return into a different stack.
**Limit case:** the first switch into a *brand new* task, which has no saved
frame to return to. You must forge one — hand-build the stack so that `ret` lands
at the entry point with plausible registers. Getting this wrong yields a jump to
a garbage address with no clue why, which is why you build it with GDB attached.
**Done when:** two kernel tasks alternate through 10,000 switches, and you can
print the cycle cost of one switch.
**Read:** `[XV6]` `swtch.S` and ch. 7 — the clearest 20 lines on this anywhere;
`[LKD3]` ch. 3 (Process Switching); `[SDM3]` ch. 7 for the parts you are *not*
using (hardware task switching, dead since the 386).

### 04.3 — Ring 3
**Build:** a TSS with `RSP0`, a user code/data descriptor pair in the GDT, and an
`iretq` that drops to CPL 3 with a user stack and user page tables.
**Limit case:** from ring 3, attempt `cli`, `hlt`, an `in` from a port, and a
write to a supervisor page. Each must produce `#GP` or `#PF`. If any *succeeds*,
your descriptors or your page flags are wrong, and everything downstream of this
phase is built on sand. Verify all four.
**Done when:** user code runs, cannot escape, and the fault for each attempt names
the right cause.
**Read:** `[SDM3]` ch. 6.14 (interrupt stack switching), ch. 5.6 (User/Supervisor
paging), ch. 7.2 (TSS); `[OSDEV]` Getting to Ring 3.

### 04.4 — The first syscall, via `int`
**Build:** a syscall gate (DPL 3), a dispatch table, argument marshalling in
registers, and `write` and `exit`.
**Limit case:** a user process passes a pointer. Validate it: is it in user
range? mapped? writable if you will write to it? Then have the user *unmap* it
between your check and your use, and observe your kernel fault at CPL 0 with a
user-supplied address. **Every syscall taking a pointer is an attack surface** —
this is the TOCTOU that `copy_from_user` exists to contain.
**Done when:** a ring-3 program prints via `write` and terminates via `exit`, and
a hostile pointer returns `-EFAULT` rather than panicking.
**Read:** `[TLPI]` ch. 3 (System Programming Concepts); `[LKD3]` ch. 5 (System
Calls) — especially "Verifying the Parameters"; `[LDD3]` ch. 6 on user-space
access.

### 04.5 — `syscall`/`sysret`, and what it does not do for you
**Build:** `STAR`, `LSTAR`, `SFMASK` MSRs, and an entry stub.
**Limit case:** `syscall` does **not** switch `RSP`. On entry you are running
kernel code on the *user's* stack, at CPL 0. A malicious user sets `RSP` to a
kernel address and your first push corrupts the kernel. Swap to a per-CPU kernel
stack via `swapgs` before touching the stack — and note that `swapgs` on the
return path has its own famous race. Measure `int` versus `syscall` in cycles.
**Done when:** both paths work, the ratio is printed, and a hostile `RSP` is
harmless.
**Read:** `[SDM3]` ch. 6.14.3 and the `SYSCALL`/`SWAPGS` entries in `[SDM2]`;
`[KDOC]` `Documentation/arch/x86/entry_64.rst`; `[LWN]` on the `swapgs`
speculation fix.

### 04.6 — A round-robin scheduler, cooperative
**Build:** a run queue, `yield()`, and a scheduler picking the next runnable task.
**Limit case:** one task with `while(1);`. The machine is gone. This is not a bug
to fix here — it is the specification for 04.9. Confirm the failure, then move on
deliberately.
**Done when:** N tasks interleave in a documented order, and the hang is
reproducible on demand.
**Read:** `[OSTEP]` ch. 7 (Scheduling: Introduction); `[XV6]` ch. 7; `[MOS4]`
ch. 2.4.

### 04.7 — Blocking, wait queues, and sleep
**Build:** task states (RUNNING / READY / BLOCKED / ZOMBIE), a wait queue, and
`sleep_on()` / `wake_up()`.
**Limit case:** the lost-wakeup race. Check a condition, find it false, and get
preempted before you enqueue — the waker fires in between and you sleep forever.
Reproduce it (a `yield()` in the window makes it deterministic), then fix it, and
write down *why* the fix works. This race is the reason condition variables have
the API they have.
**Done when:** a task blocks on a timer and wakes exactly once, and your
reproduction of the lost wakeup no longer reproduces.
**Read:** `[OSTEP]` ch. 30 (Condition Variables) — the "Producer/Consumer"
section is this exact bug; `[LKD3]` ch. 4 on wait queues; `[P-MON74]`.

### 04.8 — `fork`, `exec`, `wait`, `exit`
**Build:** `fork` (duplicate the task, CoW the address space via 03.12), `exec`
(replace it — full ELF loading lands in phase 07), `wait`, `exit`, reparenting.
**Limit case:** the zombie. A child exits and its parent never waits: the exit
status must survive somewhere, so the task cannot be fully freed. Then kill the
parent first and confirm the orphan is reparented to init rather than leaked.
Build both, and print your process table showing a zombie.
**Done when:** `fork` returns twice with the right values, a shared page copies
on first write, and orphans and zombies are both handled and observable.
**Read:** `[TLPI]` ch. 24–26 in full; `[BACH]` ch. 7; `[APUE]` ch. 8; `[P-UNIX74]`
— the original description of this design, four pages long.

### 04.9 — Preemption
**Build:** the timer interrupt calling the scheduler, a time slice, and a
`need_resched` flag consumed on the return-to-user path.
**Limit case:** now preempt in *kernel* mode. Your allocator from 03.9 has a
non-atomic free-list update, and two tasks can now be inside it. Find the
corruption. Decide: non-preemptible kernel (simple, worse latency) or preemptible
(needs locks everywhere — phase 05). Whichever you choose, say what it costs.
**Done when:** 04.6's infinite loop no longer hangs the machine, and you have
either demonstrated the allocator race or documented why it cannot occur.
**Read:** `[LKD3]` ch. 4 (Preemption and Context Switching) and ch. 9; `[OSTEP]`
ch. 6 (Limited Direct Execution); `[UTLK]` ch. 7.

### 04.10 — Priorities and MLFQ
**Build:** multiple run queues by priority, with tasks demoted on slice exhaustion
and promoted on I/O block; periodic boosting.
**Limit case:** starvation. Construct a CPU-bound low-priority task that never
runs, then show your boost rule rescuing it. Then construct the *gaming* attack:
a task that yields just before its slice expires stays at top priority forever.
The fix — account total time consumed, not time-since-last-yield — is exactly the
history MLFQ rules were patched into having.
**Done when:** an interactive task keeps low latency under CPU-bound load, the
starvation case is fixed, and the gaming attack fails.
**Read:** `[OSTEP]` ch. 8 (MLFQ) in full — it develops these rules by exactly this
method; `[P-MLFQ]`; `[MOS4]` ch. 2.4.

### 04.11 — Fair-share scheduling
**Build:** a proportional-share scheduler — either lottery/stride, or a virtual-
runtime scheduler with a red-black tree in the manner of CFS.
**Limit case:** two tasks with weights 1 and 4 must receive 20%/80% of CPU, and
you must *measure* it rather than assert it. Then add a task that sleeps 99% of
the time and check it is not penalised for the CPU it did not use — the vruntime
handling of a waking task is the subtlest part of CFS and the source of most of
its historical bugs.
**Done when:** measured CPU shares match weights within a few percent, over a run
long enough to be meaningful.
**Read:** `[P-LOTTERY94]`; `[KDOC]` `Documentation/scheduler/sched-design-CFS.rst`;
`[LKD3]` ch. 4; `[P-WASTED16]` — read this one carefully, it is four real bugs in
a production scheduler and each is a scheduler-design lesson.

### 04.12 — Signals
**Build:** signal delivery — pending masks, handler registration, building a
signal frame on the user stack, `sigreturn`, default actions, and blocking.
**Limit case:** a signal arriving while the task is blocked in a syscall. You must
either restart the syscall or return `EINTR` — and which one is correct depends
on the syscall and on `SA_RESTART`. Build both paths and demonstrate each.
Then: a signal handler that itself is interrupted by the same signal.
**Done when:** a user handler runs and returns correctly via `sigreturn`, a
blocked read is interrupted with `EINTR`, and a restartable one restarts.
**Read:** `[TLPI]` ch. 20–22 — three chapters, all necessary; `[APUE]` ch. 10;
`[LKD3]` ch. 10; `[KDOC]` `Documentation/kernel-hacking/` on signal frames.

### 04.13 — Measure the process abstraction
**Build:** benchmarks printing: null syscall latency, context switch cost
(same-address-space and cross), `fork+exec` cost, and signal delivery round-trip.
**Limit case:** compare cross-address-space switching to same-address-space, and
attribute the difference. Most of it is TLB, not registers — and that is *the*
argument for threads existing. Then compare your numbers against Linux on the
same machine (`lat_syscall`, `lat_ctx` from lmbench). Being 5× slower is fine;
not knowing *where* is not.
**Done when:** you have a table of four numbers with an explanation for each gap.
**Read:** `[P-SCHEDACT91]`; `[HP6]` ch. 2 on the memory-hierarchy costs you are
measuring; lmbench's paper (McVoy & Staelin, USENIX 1996).

---

## Where this phase stops

- **Single CPU still.** The scheduler has one run queue. Load balancing, per-CPU
  queues, and affinity are phase 05.
- **No real-time classes.** No `SCHED_FIFO`/`SCHED_DEADLINE`. `[P-DEADLINE]` is
  the entry point if you want them.
- **`exec` is a stub.** It replaces the address space but does not parse ELF
  properly until phase 07.
- **No threads in userspace.** No TLS, no futexes, no pthread. Futexes arrive in
  phase 05; TLS in phase 07.
- **No process groups, sessions, or job control.** They need a TTY, which is
  phase 07.

---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
