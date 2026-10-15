# Phase 03 — Memory: Frames, Pages, Address Spaces, Heap

**13 exercises.** The single largest conceptual jump in the project: from "the
machine has memory" to "each program has its own memory, and that is a lie the
kernel maintains".

---

## The failure that got you here

Your kernel has one address space, statically mapped, and every pointer is a
physical address. That is survivable for one program. It is not survivable for
two: they will both want to be loaded at their link address, both want a stack,
and neither may read the other's data. And you cannot even load one program of
unknown size, because you have no way to answer "give me some memory".

**Virtual memory is not an optimisation. It is the mechanism that makes more than
one program possible.**

---

## Design decisions

> **DESIGN DECISION — where does the kernel live in the address space?**
> Identity-mapped low memory is what you have now and it collides with every user
> program's link address. A *higher-half* kernel (at `0xFFFF800000000000`+) puts
> the kernel above all user addresses, so switching address spaces need not
> unmap the kernel — which means an interrupt during a context switch does not
> fault.
> **Chosen:** higher-half, in 03.6. Cost: a painful transition where your code is
> running at one address and about to exist at another, and every physical
> pointer you already stored is wrong. Do it early; it only gets worse.

> **DESIGN DECISION — one physical allocator or two?**
> A single free-list allocator handles arbitrary sizes badly, fragmenting until
> a 2 MiB request fails while 100 MiB is free. A buddy allocator gives you
> power-of-two blocks with cheap coalescing; a slab allocator on top gives you
> cheap fixed-size objects with no fragmentation at all.
> **Chosen:** bitmap → buddy → slab, each introduced by the failure of the last
> (03.2, 03.8, 03.9). Cost: three allocators. This is also what Linux has, for
> the same reasons `[P-SLAB94]` gives.

> **DESIGN DECISION — do you support demand paging and swap?**
> Demand paging (allocate on fault) is where virtual memory stops being
> bookkeeping and starts being a policy problem: what to evict, when, based on
> what evidence.
> **Chosen:** demand paging and CoW yes (03.11, 03.12); swap to disk yes but
> minimal (03.13), since it needs phase 06's block layer. Cost: 03.13 is the one
> exercise in this phase that must wait.

---

## The exercises

### 03.1 — A physical memory map you trust
**Build:** from `boot_info`'s memory map: total RAM, usable regions with the
kernel image, initrd, and ACPI regions excluded, all aligned to 4 KiB.
**Limit case:** an available region that partially overlaps your kernel. Splitting
it is fiddly and skipping it wastes memory; getting it wrong means the allocator
hands out the page containing your own page tables. Construct the overlap
deliberately and confirm your splitter handles it.
**Done when:** printed usable total matches QEMU's `-m` minus known holes, and
the kernel's own pages are provably excluded.
**Read:** `[GORMAN]` ch. 2 (Describing Physical Memory); `[LKD3]` ch. 12; `[ACPI]`
§15.

### 03.2 — A bitmap frame allocator
**Build:** `alloc_frame()` / `free_frame()` over a bitmap, one bit per 4 KiB page.
**Limit case:** allocate every frame, free every other one, then request two
contiguous frames. It fails with half of memory free. Note the number; you will
fix it in 03.8, and you should feel the fragmentation before you are handed the
buddy allocator as a solution.
**Done when:** you can allocate and free all of RAM in a loop without leaking, and
double-free is detected rather than silently corrupting.
**Read:** `[OSTEP]` ch. 17 (Free-Space Management); `[GORMAN]` ch. 5; `[OSDEV]`
Page Frame Allocation.

### 03.3 — Read the page tables that are already there
**Build:** a walker that, given a virtual address, prints each level of the
4-level translation (PML4 → PDPT → PD → PT), the entry at each, and the flags.
**Limit case:** walk an address inside a 2 MiB page from your boot mapping and
notice the walk terminates a level early (`PS` bit). Then walk an unmapped
address and terminate cleanly rather than dereferencing a non-present entry.
**Done when:** your walker's answer for any address matches what the CPU does —
verify by faulting on an address you predicted would fault.
**Read:** `[SDM3]` ch. 5 (Paging), especially 5.5 (4-Level Paging) and Figure
5-22; `[APM2]` ch. 5; `[OSDEV]` Paging.

### 03.4 — Map and unmap, with the invalidation you will forget
**Build:** `map_page(va, pa, flags)`, `unmap_page(va)`, allocating intermediate
tables on demand, with `invlpg` after every change.
**Limit case:** unmap a page and *skip* the `invlpg`. Read it. It still works —
the translation is cached in the TLB. This is the bug that only appears under
memory pressure, weeks later, as impossible-looking corruption. Reproduce it
deliberately once, so that you recognise it.
**Done when:** mapping, reading, unmapping, and faulting on read all behave, and
you can state when a full `CR3` reload is needed instead of `invlpg`.
**Read:** `[SDM3]` ch. 5.10 (Caching Translation Information) — the whole
section; `[P-TLB]` ch. 3; `[LKD3]` ch. 12 on `flush_tlb_*`.

### 03.5 — Permissions, and W^X
**Build:** per-page `PRESENT / WRITE / USER / NX` flags applied to the kernel's
own sections: `.text` read-execute, `.rodata` read-only-NX, `.data`/`.bss`
read-write-NX.
**Limit case:** after applying them, try to write to `.rodata` and try to execute
from the stack. Both must fault. If executing from the stack works, `EFER.NXE` is
not set — check it. A kernel whose stack is executable is one buffer overflow
away from being someone else's kernel.
**Done when:** each violation faults with the expected `#PF` error code, and
`.text` is not writable.
**Read:** `[SDM3]` ch. 5.13 (NX bit); `[P-SMASH96]` — read it once, in full;
`[CSAPP]` ch. 3.10.

### 03.6 — Move the kernel to the higher half
**Build:** a new PML4 mapping the kernel at `0xFFFFFFFF80000000` (or
`0xFFFF800000000000`), a linker script to match, a direct physical map region,
and the jump that transfers execution from the identity mapping to the new one.
**Limit case:** the moment after you load `CR3`, your `RIP` still points at the
old address. Keep the identity mapping alive across the switch, jump, *then* tear
it down. Get this wrong and the machine triple-faults with no explanation — which
is why 02.1 and 00.5 came first.
**Done when:** every kernel symbol is above the canonical hole, the identity map
is gone, and `phys_to_virt`/`virt_to_phys` are the only place the offset appears.
**Read:** `[OSDEV]` Higher Half Kernel, Higher Half x86-64; `[LINSIDES]` "Kernel
booting process, part 6"; `[GORMAN]` ch. 4 on Linux's address-space layout.

### 03.7 — Address spaces as objects
**Build:** an `address_space` type owning a PML4, with create / destroy / switch,
where every new space shares the kernel's higher-half entries and has its own
lower half.
**Limit case:** destroy an address space and free its page tables. Free the shared
kernel PML4 entries by accident and the *next* process dies. Then: switch to an
address space and take an interrupt immediately. If the kernel were not mapped in
every space, that interrupt would fault — this is the payoff for 03.6, and you
should verify it rather than believe it.
**Done when:** two spaces map different data at the same virtual address, and
switching between them repeatedly leaks no frames.
**Read:** `[XV6]` ch. 3 (Page tables); `[UTLK]` ch. 9 (Process Address Space);
`[MOS4]` ch. 3.

### 03.8 — A buddy allocator
**Build:** power-of-two block allocation with splitting on allocate and
coalescing on free, orders 0 through ~10.
**Limit case:** re-run 03.2's fragmentation experiment. Then find the case buddy
still fails: allocate order-0 blocks at every other buddy position and request an
order-5. Coalescing cannot happen. **External fragmentation is reduced, not
solved** — this is why 03.9 exists and why Linux has compaction.
**Done when:** free/alloc cycles return the allocator to its exact initial state,
and you can print a per-order free-block histogram.
**Read:** `[P-BUDDY]`; `[GORMAN]` ch. 6 (Physical Page Allocation); `[OSTEP]`
ch. 17.6; `[LKD3]` ch. 12 on zones and the buddy system.

### 03.9 — A slab allocator
**Build:** caches of fixed-size objects carved from buddy pages, with a free list
per slab, per-cache constructors, and statistics.
**Limit case:** allocate a million 48-byte objects through buddy alone and
measure the waste (each rounds to 64 or 4096). Then through the slab and measure
again. Print both numbers. Then find slab's own failure: one live object pinning
an entire page — the reason `slabinfo` shows caches that will not shrink.
**Done when:** `kmalloc`/`kfree` are backed by size-classed slabs, and you can
print utilisation per cache.
**Read:** `[P-SLAB94]` in full — it is the origin, and readable; `[P-VMEM01]` for
the per-CPU extension you will want in phase 05; `[GORMAN]` ch. 8.

### 03.10 — `kmalloc`, `vmalloc`, and why both exist
**Build:** `kmalloc` (physically contiguous, slab-backed) and `vmalloc`
(virtually contiguous, physically scattered), and a policy for choosing.
**Limit case:** DMA. A device programmed with a physical address cannot use a
`vmalloc` buffer — it sees physical memory, not your page tables. Write down which
of your future drivers therefore need `kmalloc`. (Phase 08 will make this
concrete, painfully, if you skip it.)
**Done when:** a 4 MiB `vmalloc` succeeds under fragmentation where `kmalloc`
fails, and you can print the physical scatter list proving they differ.
**Read:** `[LKD3]` ch. 12 (`kmalloc` vs `vmalloc`); `[LDD3]` ch. 8 (Allocating
Memory) and ch. 15 (Memory Mapping and DMA); `[GORMAN]` ch. 7.

### 03.11 — Demand paging
**Build:** a fault handler that distinguishes a legal fault (an address in a
mapped region with no frame yet) from an illegal one, and allocates on demand.
**Limit case:** a region description that says a range is valid before any frame
exists. Now you need per-address-space region metadata — Linux calls it a
`vm_area_struct`, and you have just derived why it must exist. Also: a fault on a
guard page must stay illegal.
**Done when:** a 1 GiB anonymous mapping succeeds on a 128 MiB machine and
consumes frames only as pages are touched, provably.
**Read:** `[OSTEP]` ch. 21–22; `[UTLK]` ch. 9 on `vm_area_struct` and
`do_page_fault`; `[GORMAN]` ch. 4.

### 03.12 — Copy-on-write
**Build:** map shared frames read-only in two address spaces with a per-frame
refcount; on a write fault, copy, remap writable, drop the refcount.
**Limit case:** three-way sharing where one writer copies. If you decrement to 1
and leave the last holder read-only, its next write copies pointlessly and
forever. Handle the refcount-reaches-one optimisation, and construct the case
that proves it fires.
**Done when:** two spaces share frames until written, a shared counter shows the
saving, and repeated write cycles do not leak.
**Read:** `[OSTEP]` ch. 22; `[BACH]` ch. 6–7 on `fork`; `[UTLK]` ch. 9;
`[P-MULTICS72]` for where the idea comes from.

### 03.13 — Eviction policy, and the honest version of LRU
**Build:** a page-replacement policy — start with FIFO, implement CLOCK using the
accessed bit, and a swap-out path to a block device (returns here after phase 06).
**Limit case:** construct Belady's anomaly for FIFO — a reference string where
*more* frames cause *more* faults. Then measure your CLOCK against optimal
(offline) on the same trace and print the gap. This is the exercise where you
find out that a policy is a claim about the future, and that "LRU" in a real
kernel is always an approximation because tracking true LRU costs a bus
transaction per access.
**Done when:** you can print fault counts for FIFO / CLOCK / OPT on one trace, and
explain the ordering.
**Read:** `[P-BELADY66]`; `[P-WS68]`; `[P-CLOCK]`; `[OSTEP]` ch. 22 (Swapping
Policies) — it builds exactly this comparison; `[GORMAN]` ch. 10.

---

## Where this phase stops

- **No NUMA.** One memory node. Real kernels have per-node zones and allocation
  policy; the mechanism you built generalises, and `[LKD3]` ch. 12 describes how.
- **No huge-page support beyond the boot mapping.** 2 MiB pages appear in 01.6 and
  are then ignored. Transparent huge pages are a phase-12 stretch.
- **No memory cgroup accounting.** Deferred to phase 10.
- **No KASAN/KMSAN, no page poisoning.** Worth adding when your allocator starts
  lying to you; not a lesson in itself.
- **Swap is minimal.** 03.13 gives you the policy and a single backing device, not
  swap files, priorities, or readahead.

---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
