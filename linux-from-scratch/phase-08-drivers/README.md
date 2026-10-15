# Phase 08 — Devices and Drivers

**11 exercises.** The kernel discovers hardware it was not compiled to know
about, and you find out why 60% of Linux's source tree is drivers.

---

## The failure that got you here

Every device you have touched — PIT, PS/2, serial, ATA — lives at a fixed legacy
port you hardcoded. That worked because those addresses were fixed in 1984. Every
device made since is on a bus, at an address assigned at boot, with an interrupt
line the firmware chose, and your kernel has no idea it exists.

Worse: your ATA driver in 06.1 moved every byte through the CPU. And your serial,
keyboard and disk drivers each independently reimplemented device registration,
interrupt handling and buffering — three times, three ways, three sets of bugs.

**A driver model is not bureaucracy. It is the observation that the third driver
is where you start paying for having no abstraction.**

---

## Design decisions

> **DESIGN DECISION — PIO or DMA?**
> PIO is simple and costs one CPU instruction per word. DMA is a device writing
> directly into your RAM, which means cache coherence, physical addresses, memory
> the allocator must not move or free, and a device that can scribble anywhere if
> you program it wrong.
> **Chosen:** DMA from 08.4, with 06.1's measured cycles-per-byte as the
> justification. Cost: an entire class of bug where the corruption appears in
> memory belonging to something else entirely.

> **DESIGN DECISION — drivers in the kernel, or in userspace?**
> In-kernel drivers are fast and share the kernel's address space, so a driver
> bug is a kernel bug — `[P-DRIVERS12]` found drivers to be the dominant source
> of kernel faults. Userspace drivers (microkernel style, or UIO/VFIO) isolate
> failures at the cost of context switches per operation.
> **Chosen:** in-kernel, as Linux does, with 08.10 building one userspace driver
> so the comparison is measured rather than asserted. Read `[P-UKERNEL95]` and
> `[P-NOOKS03]` and hold an opinion you can defend.

> **DESIGN DECISION — how do drivers get bound to devices?**
> Static tables are simple and require recompiling to support new hardware.
> Dynamic matching on (vendor, device, class) IDs with a driver registry is how
> real systems work and needs a device model with lifetimes and refcounts.
> **Chosen:** dynamic matching (08.3), because 08.2 will enumerate devices you did
> not anticipate and you should be able to handle that.

---

## The exercises

### 08.1 — PCI configuration space
**Build:** enumerate buses/devices/functions via port `0xCF8`/`0xCFC` (and MMIO
ECAM from ACPI's MCFG), read vendor/device/class, and print a `lspci`-style table.
**Limit case:** brute-force scanning all 256 buses reads config space for devices
that do not exist, and some chipsets misbehave. Do it properly: recurse through
PCI-to-PCI bridges from bus 0, and check the header type for multifunction
devices — a single-function scan misses half the devices on a modern machine.
**Done when:** your table matches `lspci` run against the same QEMU machine.
**Read:** `[PCI]` ch. 6 (Configuration Space); `[LDD3]` ch. 12 (PCI Drivers);
`[OSDEV]` PCI, PCI Express.

### 08.2 — BARs, MMIO, and resource assignment
**Build:** decode base address registers (size them by writing all-ones), map MMIO
regions into kernel virtual space with the right caching attributes, and handle
I/O-space BARs and 64-bit BARs.
**Limit case:** map a device's MMIO region as normal cacheable memory. Writes sit
in the cache and never reach the device; reads return stale values. The region
must be uncacheable or write-combining (`PAT`/`MTRR`), and your `map_page` from
03.4 has no flag for that yet. Add it. This bug looks exactly like a broken
device.
**Done when:** you can read a device register through MMIO and get the same value
as through I/O ports, and a deliberate cacheable mapping demonstrably fails.
**Read:** `[SDM3]` ch. 11 (Memory Cache Control), especially 11.3 (Methods of
Caching) and 11.12 (PAT); `[LDD3]` ch. 9 (Communicating with Hardware);
`[PCI]` ch. 6.2.5.

### 08.3 — A device model
**Build:** `struct device`, `struct driver`, a bus type with a `match` function,
probe/remove, refcounted lifetimes, and a registry.
**Limit case:** a driver module removed while a file it owns is still open. The
refcount must keep the device alive; getting it wrong is a use-after-free in the
most confusing possible place. Then: two drivers matching one device — pick a
policy and make it explicit. Now retrofit serial, keyboard and disk into this
model and count how much duplicated code disappears.
**Done when:** all your existing drivers are registered through the model, and a
device with no driver is enumerated but unbound rather than ignored.
**Read:** `[LDD3]` ch. 14 (The Linux Device Model) in full; `[LKD3]` ch. 17;
`[KDOC]` `Documentation/driver-api/driver-model/`.

### 08.4 — DMA
**Build:** DMA-capable buffer allocation (physically contiguous, from 03.10's
`kmalloc` path), scatter-gather lists, a mapping API, and cache management.
**Limit case:** the device writes into your buffer while the CPU holds an old copy
in cache. On x86 the DMA is coherent and you get away with it; on ARM you do not.
Write the sync API anyway and document that x86 makes it a no-op — because
"it works on my machine" here means "it works on this architecture". Then: a
device programmed with a virtual address, which will DMA to whatever physical page
happens to be there. Do it once, in a VM, and watch what breaks.
**Done when:** a virtio device transfers via a scatter-gather list you built, and
your DMA API refuses a `vmalloc` buffer.
**Read:** `[LDD3]` ch. 15 (Memory Mapping and DMA); `[KDOC]`
`Documentation/core-api/dma-api.rst` and `dma-api-howto.rst`; `[PCI]` ch. 3 on
bus mastering.

### 08.5 — MSI and MSI-X
**Build:** the MSI/MSI-X capability structures, vector allocation, per-vector
handlers, and per-CPU interrupt routing.
**Limit case:** legacy PCI interrupts are level-triggered and *shared* — your
handler must determine whether its device actually raised the interrupt and
return "not mine" if not, or a shared line will livelock. Build a shared-IRQ
handler chain first and construct the storm. MSI removes sharing entirely by
giving each source its own vector, which is the argument for it.
**Done when:** a device delivers interrupts by MSI to a CPU you selected, and a
shared legacy line with two devices is handled without livelock.
**Read:** `[PCI]` ch. 6.8 (MSI); `[SDM3]` ch. 12.11 (Message Signalled
Interrupts); `[LDD3]` ch. 10; `[KDOC]` `Documentation/PCI/msi-howto.rst`.

### 08.6 — Character devices and `/dev`
**Build:** major/minor numbers, a character-device registry, `open/read/write/
ioctl/mmap` file operations, and a `devtmpfs` populating `/dev` from the device
model.
**Limit case:** `ioctl` is an untyped escape hatch: an arbitrary number and an
arbitrary pointer. Every argument is user-controlled, and every `ioctl` you define
is ABI forever. Define the encoding (direction, size, type, number) before you
define the first one, and validate size against the encoding — this is the
mechanism `_IOR`/`_IOW` exist for, and skipping it is how drivers get CVEs.
**Done when:** `/dev/null`, `/dev/zero`, `/dev/console` and your serial port are
real files, and a malformed `ioctl` is rejected on the encoding alone.
**Read:** `[LDD3]` ch. 3 (Char Drivers) and ch. 6 (Advanced Char Driver
Operations); `[TLPI]` ch. 14; `[KDOC]` `Documentation/driver-api/ioctl.rst`.

### 08.7 — Loadable modules
**Build:** a relocatable-ELF loader inside the kernel: allocate, apply
relocations, resolve against a kernel symbol table, run an init function, and
support unloading with refcounts.
**Limit case:** unload a module while one of its functions is on another CPU's
stack. The refcount protects the *device*, not the code. This is genuinely hard —
Linux's answer involves `try_module_get` and a stop-the-world check — and it is
worth understanding why "just free it" is wrong. Then: a module relocation type
you have not implemented, which must fail the load rather than jump somewhere
arbitrary.
**Done when:** a driver loads at runtime, binds a device, works, and unloads
cleanly; an unsupported relocation is refused by name.
**Read:** `[LDD3]` ch. 2 (Building and Running Modules); `[LKD3]` ch. 17;
`[LINKLOAD]` ch. 8 on relocatable objects; `[ELF]` §Relocation.

### 08.8 — A framebuffer and a graphics console
**Build:** the linear framebuffer from `boot_info`, pixel plotting, a bitmap font,
a scrolling text console, and double buffering.
**Limit case:** scrolling now means moving several megabytes per line, over an
uncached (or write-combining) MMIO region, which is dramatically slower than the
VGA text mode you replaced. Measure it and be shocked. Then fix it the way real
consoles do — write-combining plus a back buffer in normal RAM — and measure
again. This is 02.6's lesson at 1000× the scale.
**Done when:** text renders at a usable rate, and you have before/after numbers
for the write-combining and double-buffering changes.
**Read:** `[SDM3]` ch. 11.3.1 on write-combining; `[OSDEV]` Drawing In Protected
Mode, VESA Video Modes; `[KDOC]` `Documentation/fb/`.

### 08.9 — Hotplug, power, and the device lifecycle
**Build:** device add/remove at runtime, a uevent-style notification to userspace,
and suspend/resume callbacks in the driver model.
**Limit case:** remove a device that has open file descriptors and in-flight DMA.
Every one of those must be resolved before the memory is freed, and the DMA is the
hard one — the device may still write to that buffer. This is the surprise-removal
problem (unplugging a USB stick mid-write) and there is no clean answer, only a
protocol.
**Done when:** a device added and removed under QEMU is handled without a leak or
a crash, and the removal path is documented as a sequence.
**Read:** `[LDD3]` ch. 14 on hotplug; `[KDOC]`
`Documentation/driver-api/pm/devices.rst`; `[ACPI]` §7 on device power states.

### 08.10 — A userspace driver, for comparison
**Build:** expose a device's MMIO and interrupts to userspace (UIO-style: `mmap`
the BARs, deliver interrupts as readable events on a file descriptor), and rewrite
one existing driver against it.
**Limit case:** measure the same workload through the in-kernel and userspace
versions. The userspace one costs a context switch per interrupt and gains fault
isolation. Then crash the userspace driver on purpose and observe the system
survive; crash the in-kernel one and observe it not. You now have both numbers and
both failure modes, which is the only honest basis for the microkernel argument.
**Done when:** both versions work, with a measured throughput gap and a
demonstrated isolation difference.
**Read:** `[P-UKERNEL95]`; `[P-NOOKS03]`; `[P-DRIVERS12]`; `[KDOC]`
`Documentation/driver-api/uio-howto.rst`; `[OSDI]` ch. 1 for Tanenbaum's side of
the argument.

### 08.11 — Measure the I/O path
**Build:** interrupt latency by source, DMA versus PIO throughput on the same
device, MSI versus legacy interrupt cost, and per-driver interrupt counts.
**Limit case:** re-run 06.1's ATA PIO benchmark against your DMA path and compute
the CPU cycles reclaimed per megabyte. Then compute what fraction of a core your
06.1 driver would have consumed at a modern SSD's throughput. The answer (more
than one core) is why PIO storage no longer exists.
**Done when:** the table exists, and the "cycles per MiB" column is filled in for
every path.
**Read:** `[P-LIVELOCK96]` again — now you have the hardware to reproduce it;
`[HP6]` ch. 1.9 on measurement methodology; `[LDD3]` ch. 1 for the taxonomy.

---

## Where this phase stops

Everything below is deferred to **[phase-13-real-hardware/](../phase-13-real-hardware/)**,
where the target is the machine on your desk rather than QEMU. Listed here so you
know what your phase-08 kernel cannot yet talk to:

- **No USB.** A full stack — host controller, hubs, enumeration, endpoints,
  classes. On a machine with no PS/2 emulation this means no keyboard at all.
  Phase 13.4–13.7. `[LDD3]` ch. 13 is the entry point.
- **No AHCI/NVMe.** virtio-blk covers the emulated case; real storage is
  phase 13.2–13.3.
- **No GPU beyond a framebuffer.** No mode setting, no command submission, no
  acceleration. Phase 13.9 improves the framebuffer; DRM/KMS stays out of scope.
- **No sound, no Bluetooth, no Wi-Fi.** Audio is phase 13.15; the other two stay
  out of scope entirely.
- **No firmware loading.** Many real devices need a vendor blob — phase 13.11,
  which is also where the trust question gets answered.
- **No IOMMU.** Any device with DMA can read all of memory, and your 08.4 driver
  trusts the hardware completely. Phase 10 discusses it; phase 13.14 builds it.
- **No power management.** No C-states, no frequency scaling, no suspend.
  Phase 13.13.


---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
