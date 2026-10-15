# Phase 05 — Concurrency and SMP

**12 exercises.** A second CPU, and the discovery that most of what you have
written so far is only correct because there was one.

---

## The failure that got you here

Preemption in 04.9 already gave you interleaving; disabling interrupts made it go
away. That trick dies the moment a second core exists, because the other CPU is
not interrupted by your `cli` — it is running, right now, in your allocator.

**Concurrency is not a feature you add. It is a property you either preserve or
destroy in every line already written.** This phase is mostly an audit.

---

## Design decisions

> **DESIGN DECISION — big kernel lock, or fine-grained locking?**
> One global lock makes the whole kernel correct in an afternoon and scales to
> approximately 1.2 CPUs. Fine-grained locking scales and introduces lock
> ordering, which introduces deadlock.
> **Chosen:** BKL first (05.4), *then* measure it (05.5), then break it apart
> where the measurement says to. Cost: you write it twice. Linux did exactly
> this, took eleven years to finish removing it, and the measurement is the only
> honest justification for the pain.

> **DESIGN DECISION — do you need a memory model, or will `volatile` do?**
> `volatile` prevents the *compiler* reordering. It does nothing about the CPU or
> the cache coherence protocol. On x86-64 (TSO) you get away with this
> surprisingly often, which is worse than not getting away with it.
> **Chosen:** explicit atomics and barriers from 05.2 onward, with the x86
> guarantees written down so you know which ones you are relying on. Cost: more
> care per line. Benefit: your code is correct on ARM64, and you will know why
> that is a different question.

> **DESIGN DECISION — how do you handle read-mostly data?**
> A reader-writer lock still writes a shared cache line per read, so N readers on
> N cores is a coherence storm. RCU makes readers free and makes reclamation the
> hard problem instead.
> **Chosen:** rwlocks in 05.7, RCU in 05.11, with the same workload measured under
> both. The point is the graph, not the mechanism.

---

## The exercises

### 05.1 — Boot the other CPUs
**Build:** parse the MADT's CPU list, send INIT–SIPI–SIPI from the BSP, a
real-mode trampoline for each AP that walks it up to long mode on the shared
kernel page tables, and a per-CPU structure reachable through `GS`.
**Limit case:** all APs execute the same trampoline at the same physical address
simultaneously. They cannot share a stack. Each must find its own — from its
LAPIC ID, before it has any per-CPU pointer set up. This bootstrapping order is
the whole difficulty of SMP bring-up.
**Done when:** every core prints its APIC ID, and `smp_cpu_count()` matches
QEMU's `-smp`.
**Read:** `[SDM3]` ch. 9.4 (Multiple-Processor Initialization) — follow the MP
protocol exactly; `[OSDEV]` Symmetric Multiprocessing, APIC; `[ACPI]` §5.2.12.

### 05.2 — Atomics and barriers
**Build:** `atomic_read/set/add/sub/inc/dec`, compare-and-swap, `xchg`, and
`smp_mb/rmb/wmb` plus `barrier()`.
**Limit case:** write a non-atomic `counter++` incremented by all cores and print
the shortfall. Then implement Dekker's/Peterson's algorithm and watch it fail on
x86 *despite* TSO — because store-buffer forwarding permits `store; load`
reordering, the one relaxation x86 has. Insert `mfence` and watch it pass. This
is the single experiment that makes memory models real rather than academic.
**Done when:** the lost-update count is zero with atomics, and you can state
exactly which reorderings x86-64 permits.
**Read:** `[SDM3]` ch. 9.2 (Memory Ordering) — Section 9.2.3's examples are the
ones to run; `[PMCCC]` ch. 3–4; `[AMPP]` ch. 3; `[KDOC]`
`Documentation/memory-barriers.txt` — long, essential, read twice.

### 05.3 — Spinlocks, and their cost
**Build:** a test-and-set spinlock, then test-and-test-and-set, then a ticket
lock.
**Limit case:** measure all three under 2, 4, 8 contending cores and plot
throughput. TAS degrades because every spin is a write that invalidates the line
on every other core; TTAS spins on a read; the ticket lock adds fairness and
still has the same cache-line problem. Then note what an MCS lock changes and why
`[P-MCS91]` exists.
**Done when:** you have a measured contention curve for three lock designs and
can explain the shape of each.
**Read:** `[P-SPINLOCK90]` and `[P-MCS91]` — read both, they are short and they
*are* this exercise; `[AMPP]` ch. 7; `[LKD3]` ch. 10.

### 05.4 — A big kernel lock, and an audit
**Build:** a single lock taken on every kernel entry, plus an audit list of every
shared structure you have written since phase 02.
**Limit case:** enumerate honestly — frame allocator bitmap, slab free lists, run
queue, wait queues, console cursor, PID counter, task table. For each, name what
happens if two cores touch it at once. This list is the work of the rest of the
phase, and writing it is more valuable than any single lock.
**Done when:** the kernel survives all cores running tasks, and the audit list
exists in the repo.
**Read:** `[LKD3]` ch. 9 (Kernel Synchronization Introduction) — "what needs
locking" is the section; `[LWN]` on the BKL removal, for how long this takes in
practice.

### 05.5 — Measure the BKL, then break it
**Build:** a scalability benchmark (N cores doing syscall-heavy work) and a
per-subsystem lock split driven by where the benchmark says time goes.
**Limit case:** plot throughput against core count under the BKL. It flattens,
then falls. Predict where before measuring. Then split *one* lock — the one the
data indicts — and re-measure. Resist splitting the rest until the graph says to.
**Done when:** you have a before/after scalability curve and a lock-ordering
document listing every lock and its rank.
**Read:** `[P-SCALE10]` — this is the paper-length version of this exercise;
`[LKD3]` ch. 9; `[FBSD]` ch. 4 on their equivalent effort.

### 05.6 — Deadlock, on purpose and then never again
**Build:** a lock-ordering rule, plus a debug mode that records acquisition order
and screams on a violation (a `lockdep` in miniature).
**Limit case:** deliberately take locks A→B on one core and B→A on another.
Confirm the hang, confirm your detector catches it *before* the hang, then fix
the ordering. Also construct the single-core version: taking a non-recursive lock
you already hold.
**Done when:** the detector reports the inversion with both call sites, and the
kernel is clean under it.
**Read:** `[P-COOP65]` (Dijkstra's original deadlock conditions); `[OSTEP]` ch. 32
(Concurrency Bugs); `[KDOC]` `Documentation/locking/lockdep-design.rst`.

### 05.7 — Sleeping locks: mutexes, semaphores, rwlocks
**Build:** a mutex that blocks rather than spins, counting semaphores, and
reader-writer locks.
**Limit case:** taking a sleeping lock in interrupt context. There is no task to
put to sleep — the machine deadlocks or panics. Add the assertion that catches
this at acquire time, and write down the rule: *what may sleep, and where.* Then:
writer starvation in a naive rwlock under continuous readers. Construct it, then
decide your policy.
**Done when:** the sleep-in-atomic assertion fires on a deliberate violation, and
you can show writer starvation and your chosen fix.
**Read:** `[LKD3]` ch. 10 (Kernel Synchronization Methods) — the "what to use
when" table; `[OSTEP]` ch. 28, 31; `[P-THE68]` for semaphores at their origin.

### 05.8 — Per-CPU data
**Build:** per-CPU variables via the `GS` base, per-CPU run queues, per-CPU slab
magazines, and per-CPU interrupt statistics.
**Limit case:** a per-CPU variable accessed with preemption enabled — you read
CPU 0's copy, get migrated, and write CPU 1's. Build `get_cpu()`/`put_cpu()` that
pins you, and construct the corruption first so the discipline is motivated. Then
measure the allocator with and without per-CPU magazines under contention.
**Done when:** per-CPU counters sum correctly, the migration bug is reproducible
without the pinning, and you have the allocator's contention numbers.
**Read:** `[P-VMEM01]` (magazines are exactly this); `[LKD3]` ch. 12 on per-CPU
allocation; `[KDOC]` `Documentation/core-api/this_cpu_ops.rst`.

### 05.9 — SMP scheduling and load balancing
**Build:** per-CPU run queues, periodic load balancing, task affinity masks, and
IPI-based wakeup of an idle core.
**Limit case:** cache affinity versus balance. Migrating a task to an idle core
costs its entire warm cache and TLB; measure that cost, then find the load
imbalance at which migrating is nevertheless a win. Then construct the pathology:
two cores ping-ponging one task back and forth every tick.
**Done when:** load spreads across cores, ping-ponging is bounded, and you can
print the measured migration cost.
**Read:** `[P-WASTED16]` — every bug in it is a load-balancing bug and you are
about to write all four; `[KDOC]` `Documentation/scheduler/`; `[LKD3]` ch. 4.

### 05.10 — Futexes
**Build:** the fast path entirely in userspace via CAS, with a syscall only on
contention: `FUTEX_WAIT` / `FUTEX_WAKE`, hashed on the physical address of the
word.
**Limit case:** the race between the userspace CAS failing and the `FUTEX_WAIT`
enqueue. Between those two instructions the holder may release and wake nobody —
so `FUTEX_WAIT` must take the expected value and re-check it under the kernel's
lock. Getting this wrong loses wakeups under contention only, which is the worst
possible failure schedule. Then measure: uncontended lock cost with and without a
syscall.
**Done when:** an uncontended lock/unlock does zero syscalls (prove it by
counting), contended ones block correctly, and no wakeup is ever lost across a
million iterations.
**Read:** Franke, Russell, Kirkwood, "Fuss, Futexes and Furwocks: Fast Userlevel
Locking in Linux", *OLS* 2002; `[TLPI]` ch. 53; `[KDOC]`
`Documentation/locking/futex-requeue-pi.rst` for how much harder it gets.

### 05.11 — RCU
**Build:** read-side critical sections with no atomic operations at all, updates
by publish-then-replace, and reclamation deferred until every pre-existing reader
has finished (a quiescent-state or grace-period detector).
**Limit case:** the whole difficulty is *when is it safe to free*. Free too early
and a reader dereferences freed memory — intermittently, under load, on one core.
Build the grace-period detector, then deliberately shorten it and reproduce the
use-after-free so you can recognise the signature. Then measure read throughput
against your rwlock from 05.7 at 1/2/4/8 cores.
**Done when:** a read-mostly structure scales linearly with cores under RCU and
sub-linearly under rwlock, on your own graph.
**Read:** `[P-RCU01]` and McKenney's *Is Parallel Programming Hard, And, If So,
What Can You Do About It?* ch. 9 **(free)**; `[KDOC]` `Documentation/RCU/`
— `whatisRCU.rst` first; `[LKD3]` ch. 10.

### 05.12 — Concurrency testing that actually finds bugs
**Build:** a stress harness — randomised interleavings, injected preemption
points, a delay injector inside critical sections — plus assertions on invariants
rather than on outputs.
**Limit case:** every bug in this phase is schedule-dependent, so a test that
passes proves almost nothing. Make interleavings *worse* deliberately: preempt on
every Nth kernel entry, delay inside every lock acquire. Then re-run the whole
phase's tests and count what you find. Anything you find here was already in your
kernel.
**Done when:** the harness reproduces 04.7's lost wakeup and 05.8's migration bug
on demand, and the current kernel survives a long run under it.
**Read:** `[OSTEP]` ch. 32; `[AMPP]` ch. 4 (correctness conditions —
linearizability is the property your assertions are checking); `[KDOC]`
`Documentation/dev-tools/kcsan.rst`.

---

## Where this phase stops

- **x86-64's TSO is assumed.** Your barriers are correct here and would be
  under-specified on ARM64/RISC-V. `[PMCCC]` ch. 5 is the generalisation; noting
  the difference is required, porting is not.
- **No formal model.** No litmus tests against a machine-checked model. The
  `herd7`/`litmus7` tools and `[KDOC]` `tools/memory-model/` are the next step if
  you want it.
- **No NUMA-aware balancing.** One node, so migration cost is uniform. It is not,
  on real multi-socket machines.
- **No lock-free data structures beyond RCU.** Lock-free queues and hazard
  pointers are `[AMPP]` ch. 10–11 and a project of their own.
- **No priority inheritance.** Priority inversion is real, `SCHED_DEADLINE` cares,
  and this kernel does not.

---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
