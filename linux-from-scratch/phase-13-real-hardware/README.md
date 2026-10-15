# Phase 13 — Drivers for Real Hardware

**15 exercises.** Every device on the machine in front of you, written by you.
This is the phase that converts "it boots on metal" into "it can be used".

---

## The failure that got you here

12.1 got your kernel onto a physical machine. Then you found out what that
machine actually contains, and almost none of it is what you wrote drivers for
in phase 08.

Concretely, on any laptop or desktop built in the last decade:

| You wrote (phase 06/08) | The machine actually has |
|---|---|
| PS/2 keyboard (02.8) | USB keyboard behind an xHCI controller — **there is no PS/2 port** |
| ATA PIO / virtio-blk | NVMe, or AHCI-attached SATA |
| VGA text mode (02.6) | A framebuffer only, at whatever mode the firmware chose |
| e1000/virtio-net (09.1) | Realtek or Intel silicon with a different register map, or Wi-Fi |
| Nothing | A battery, thermal zones, fans, and a lid switch |
| Nothing | Devices that can DMA anywhere in RAM |

The PS/2 line is not a footnote. On a machine with no PS/2 emulation in
firmware, **you cannot type anything into your OS until the USB stack works**,
which makes 13.4–13.6 a hard dependency for everything else and is the single
biggest reason this phase exists as its own phase.

---

## Design decisions

> **DESIGN DECISION — write drivers for one machine, or a class of machines?**
> Targeting exactly the hardware you own means hardcoding a device ID and never
> handling a variant. Targeting a class means reading a specification rather
> than a datasheet, handling capability bits you cannot test, and being wrong in
> ways you cannot observe.
> **Chosen:** write to the *specification* (xHCI, NVMe, AHCI, HDA are all
> published, vendor-neutral standards) and test on one machine. Cost: you will
> implement capability paths you cannot exercise. Benefit: this is the entire
> reason those specifications exist, and it is why a single `nvme` driver serves
> every NVMe SSD ever made while every Wi-Fi chip needs its own.

> **DESIGN DECISION — a GPU driver, or a framebuffer?**
> A real GPU driver means mode setting, memory management, command submission,
> and per-vendor documentation of wildly varying quality — Intel publishes
> thousands of pages of PRM, AMD publishes headers, Nvidia publishes very
> little. It is a multi-year project and it is *not* on the critical path to
> using the machine.
> **Chosen:** a good software framebuffer (13.9), and mode setting only as an
> optional stretch on documented Intel hardware. Cost: no acceleration, no
> external display hotplug, no changing resolution after boot. This is the
> largest deliberate gap in the phase and you should know it going in.

> **DESIGN DECISION — port ACPICA, or write a minimal AML interpreter?**
> ACPI's tables you already parse (02.10). But the battery, the lid, the thermal
> zones and S3 suspend are all behind *AML bytecode* in the DSDT, which requires
> an interpreter. ACPICA is the reference implementation, ~100k lines, and
> portable. Writing your own minimal subset is a compiler project inside an OS
> project.
> **Chosen:** a minimal interpreter for the subset your machine's DSDT actually
> uses (13.12), with ACPICA named as the escape hatch. Cost: it will break on
> the next machine. That fragility *is* the lesson about why ACPI is disliked.

> **DESIGN DECISION — when do you turn on the IOMMU?**
> Every driver in this phase programs a device with a physical address and
> trusts it. Without an IOMMU, a buggy NVMe controller or a malicious USB-C
> device reads all of memory, including your kernel.
> **Chosen:** IOMMU in 13.14, *after* the drivers work — because enabling it
> first means every driver bug presents as a DMA fault and you cannot tell which
> layer is wrong. Cost: a window where the machine is trivially DMA-attackable,
> which is fine on a lab machine and is not fine on the daily driver of phase 14.

---

## The exercises

### 13.1 — Inventory the machine, then plan the work
**Build:** a complete hardware inventory of your target machine and a written
driver plan ordered by dependency — taken from Linux, on that machine, before
you write a line: `lspci -nnvv`, `lsusb -tv`, `dmesg`, `/proc/interrupts`,
`/sys/firmware/acpi/tables`, `lsmod`.
**Limit case:** count the drivers Linux loaded. It will be dozens. Now mark each
one **required to use the machine at all**, **required for the job in phase
14.1**, or **ignorable**. Almost everything is ignorable, and finding the
genuinely required ten is the entire value of this exercise — the alternative is
discovering the missing one after a week on something optional. Dump the DSDT
(`acpidump`) and skim it now; its size tells you what 13.12 costs.
**Done when:** the inventory and the ranked plan are committed, and every entry
names the specification you will implement it from.
**Read:** `[LDD3]` ch. 12; `[ELDD]` ch. 1–2 for the subsystem map; `[KDOC]`
`Documentation/admin-guide/` on the diagnostic tools you are using.

### 13.2 — AHCI: the SATA disk
**Build:** the HBA from BAR5 — port enumeration, the command list, command
tables with PRDTs, the received-FIS area, an H2D Register FIS to issue
READ/WRITE DMA EXT, and interrupt-driven completion.
**Limit case:** port reset and error recovery. A command that times out leaves
the port in a state where every subsequent command also fails, so a driver
without a working COMRESET path works exactly once per boot and then bricks the
disk until reboot. Force the failure (issue a malformed FIS), then recover.
Then implement NCQ and measure queue depth 1 versus 32 — the same lesson as
06.2, on hardware that makes it matter more.
**Done when:** your kernel reads and writes sectors on a real SATA disk, survives
an injected command failure, and you have the NCQ depth curve.
**Read:** `[AHCI]` §3 (HBA registers) and §5 (software specifics) — §5.5 is the
command issue sequence; `[ATA]` for the command set; `[OSDEV]` AHCI.

### 13.3 — NVMe: the SSD
**Build:** the controller from BAR0 — CAP/CC/CSTS, the admin submission and
completion queues, doorbell writes with the capability-declared stride, Identify
Controller and Identify Namespace, I/O queue creation, and read/write commands
with PRPs.
**Limit case:** the completion queue has no head pointer you can read; you know
an entry is new because its **phase tag** flipped, and the tag inverts each time
the queue wraps. Get that wrong and the driver works until the first wrap, then
either hangs or processes stale completions forever — a bug that appears exactly
once per queue-length of I/O. Construct the wrap deliberately with a short
queue. Then create one I/O queue per CPU and measure against one shared queue.
**Done when:** you read and write a real NVMe namespace, the phase-tag wrap is
handled and tested, and you have the per-CPU-queue scaling numbers.
**Read:** `[NVME]` §3 (controller registers), §4 (queue model — read §4.1 and
§4.6 carefully), §5 (admin commands), §6 (I/O commands); `[OSDEV]` NVMe.

### 13.4 — xHCI: the USB host controller
**Build:** capability/operational/runtime register discovery, the Device Context
Base Address Array, the command ring, the event ring with its ERST, TRB
construction, and the doorbell registers.
**Limit case:** xHCI is ring-based like virtio (06.2) and NVMe (13.3), and this
is the third time you have implemented producer/consumer rings against
hardware — so build it as such and notice how much the three have in common.
Its specific trap is the **cycle bit**: like NVMe's phase tag, it inverts on
wrap, and both the software and hardware sides of every ring have one. Also:
the firmware may still own the controller (the BIOS handoff capability) and you
must request ownership or the controller silently ignores you.
**Done when:** the controller resets, runs, and delivers a Command Completion
event for a No-Op command you posted.
**Read:** `[XHCI]` §4.9 (TRB rings — the cycle-bit rules), §4.2 (host controller
initialization), §7.1.1 (BIOS handoff); `[OSDEV]` xHCI.

### 13.5 — USB enumeration
**Build:** port status and reset, Enable Slot, Address Device, control transfers
on endpoint 0, the descriptor hierarchy (device → configuration → interface →
endpoint), string descriptors, Set Configuration, and hub support.
**Limit case:** enumeration is a fixed choreography with mandatory delays — a
port must settle after reset (the spec says 10 ms; real devices want more), and
a device that is addressed too early enumerates intermittently, which looks like
a flaky cable. Then handle the hub: your keyboard may be behind two of them, so
enumeration must recurse, and a device attached *later* must be noticed via the
hub's status-change endpoint rather than a poll.
**Done when:** a tree of USB devices enumerates correctly, matches `lsusb -t` on
the same hardware, and hotplug of a device on a downstream hub is detected.
**Read:** `[USB]` ch. 9 (Device Framework) — the enumeration state machine and
the descriptor layouts; ch. 11 (Hub Specification); `[USBCIN]` ch. 3–5 for the
readable version; `[LDD3]` ch. 13.

### 13.6 — USB HID: a keyboard you can type on
**Build:** the HID class — SET_PROTOCOL(boot) and the fixed 8-byte boot keyboard
report first, then report-descriptor parsing for the general case, and an
interrupt IN endpoint polled at the endpoint's declared interval.
**Limit case:** the boot protocol report holds **at most six simultaneous
keycodes**, and overflow is signalled by a rollover code rather than by
truncation — so a driver that ignores it produces phantom keys under fast
typing. Then handle the real problem: a key held down produces *one* report and
then nothing; auto-repeat is entirely the operating system's job, and its
absence looks like a broken keyboard. Both belong here, not in 13.8.
**Done when:** you can type into your OS's shell on real hardware, with
modifiers, rollover handled, and repeat working.
**Read:** `[HID]` §5–6 (report descriptors) and Appendix B (boot protocol);
`[HIDUT]` §10 (keyboard usage IDs); `[USBCIN]` ch. 11–12; `[ELDD]` ch. 7.

### 13.7 — USB mass storage
**Build:** the Bulk-Only Transport — Command Block Wrapper, data phase, Command
Status Wrapper — carrying SCSI commands: INQUIRY, READ CAPACITY(10), READ(10),
WRITE(10), TEST UNIT READY.
**Limit case:** a stalled bulk endpoint mid-transfer. Recovery is a specified
sequence (clear the feature on both endpoints, then a class-specific reset) and
skipping it leaves the device wedged until it is physically unplugged. Force a
stall with a bad CBW and recover. Then: a device that reports a 4096-byte
logical block size, which breaks every assumption your block layer inherited
from 512-byte sectors in phase 06.
**Done when:** you mount a filesystem from a USB stick, and stall recovery is
demonstrated.
**Read:** `[USBMSC]` (Bulk-Only Transport, §5–6); `[SCSI]` SBC-3 for the command
set; `[USBCIN]` ch. 6.

### 13.8 — An input subsystem
**Build:** a device-independent input layer — event devices with a
timestamp/type/code/value record, keycode mapping separated from scancode
handling, a keymap, and `/dev/input/eventN` character devices from 08.6.
**Limit case:** you now have two keyboards (USB from 13.6, PS/2 from 02.8 if the
machine has one) and possibly a mouse and a lid switch, all needing to reach one
consumer. Without this layer every application binds to a specific device; with
it, unplugging one keyboard mid-session must not disconnect the console. Test
exactly that. Then: which process receives input? You built the answer in 07.7 —
the foreground process group of the controlling terminal — and this is where it
gets wired to real hardware.
**Done when:** both keyboards drive the same console, hotplug is transparent, and
the keymap is data rather than code.
**Read:** `[ELDD]` ch. 7 (Input Drivers) — the best treatment of this subsystem;
`[KDOC]` `Documentation/input/input-programming.rst` and `event-codes.rst`.

### 13.9 — The display: a framebuffer worth looking at
**Build:** the firmware-provided framebuffer (GOP from 01.9), a proper font
renderer, damage/dirty-rectangle tracking, double buffering in normal RAM, and
write-combining on the MMIO aperture.
**Limit case:** measure a full-screen redraw over the PCIe aperture. It is
dramatically slower than you expect, and it is why every real console tracks
damage rather than repainting — 08.8 showed this at low resolution; at
1920×1080×32bpp it is the difference between usable and not. Then find the
tearing: without vertical-blank synchronisation you will see it, and without a
GPU driver you cannot easily get a vblank interrupt. Decide what you do about
that, and be honest in writing that it is a limitation rather than a solution.
**Done when:** a full-resolution text console scrolls smoothly with measured
before/after numbers for damage tracking and write-combining.
**Read:** `[SDM3]` ch. 11.3.1 (write-combining); `[UEFI]` §12.9 (GOP); `[KDOC]`
`Documentation/gpu/` for what a real mode-setting driver has to do; Intel's
public PRMs if you attempt the stretch goal.

### 13.10 — The real network interface
**Build:** a driver for the NIC actually in your machine — most likely Realtek
RTL8168/8169 or an Intel e1000e/igb — with descriptor rings, buffer management,
MSI-X, link-state detection and PHY handling.
**Limit case:** the link goes down and comes back (unplug the cable). The ring
must be quiesced, the PHY re-negotiated, and in-flight buffers accounted for —
and every driver that skips this leaks buffers on every cable event until it
runs out. Do it ten times in a loop and check your buffer count returns to
baseline. Then run 09.12's livelock experiment again on hardware that can
actually saturate you.
**Done when:** your TCP stack from phase 09 works over real Ethernet, cable
flapping is clean, and you have hardware throughput numbers.
**Read:** the vendor datasheet for your part (Intel publishes theirs; Realtek's
are semi-public); `[LDD3]` ch. 17; `[ELDD]` ch. 15; `[P-LIVELOCK96]`.

### 13.11 — Firmware loading, and what you are trusting
**Build:** a `request_firmware` equivalent — locate a blob on the filesystem,
load it into a DMA-capable buffer, hand it to the device, and handle the
device's post-load re-initialisation.
**Limit case:** many devices in your machine — Wi-Fi, GPU, sometimes the NIC and
the SSD — do not function without a vendor binary blob you cannot read, running
on a processor you cannot inspect, with DMA access to your memory. This is the
hard boundary on "complete control of what is happening in my machine", and it
is worth stating precisely rather than glossing: list every device on your
machine that requires firmware, and what each blob's processor can reach. Then
note which are loaded by *you* versus which are already resident in flash and
running before your kernel starts.
**Done when:** a device that needs firmware works, and the trust inventory from
11.1 is updated with everything you found.
**Read:** `[KDOC]` `Documentation/driver-api/firmware/`; `[P-TRUST84]` — a fourth
time, and this time the untrusted compiler is a peripheral's CPU; the
linux-firmware repository's licence files, which say plainly what you may know.

### 13.12 — ACPI beyond the tables: AML, battery, lid, thermal
**Build:** an interpreter for the AML subset your machine's DSDT actually uses,
plus the platform devices behind it: the power button and lid as GPE events,
thermal zones (`_TMP`, `_AC0`) with fan control, and the battery (`_BIF`,
`_BST`).
**Limit case:** run the machine on battery with no thermal management and watch
the temperature. This is the first exercise in the project where a software bug
damages hardware, so put a hard shutdown threshold in *before* the first test.
Then find the AML feature your DSDT uses that you did not implement — there will
be one, it will be obscure, and this is exactly why everyone ships ACPICA
instead. Deciding to stop and port ACPICA is a legitimate outcome here.
**Done when:** the power button initiates a clean shutdown, the battery
percentage is readable and correct, and a thermal threshold triggers a response.
**Read:** `[ACPI]` §5.6 (events and GPEs), §10 (power source devices), §11
(thermal management), §19–20 (ASL/AML) — the bytecode reference; ACPICA's
documentation for the reference implementation.

### 13.13 — Power management: idle, frequency, and suspend
**Build:** C-states via `MWAIT` in the idle loop, P-state control
(`IA32_PERF_CTL` or HWP), and suspend-to-RAM (S3): quiesce devices, save
processor state, write the ACPI waking vector, enter the sleep state, and
resume.
**Limit case:** measure idle power draw before and after C-states — on a laptop,
from the battery's own current reading via 13.12. A kernel whose idle loop is a
busy `hlt` without deeper C-states costs multiple watts, which is the difference
between eight hours and three. Then attempt S3, and discover the real
difficulty: **every driver in this phase needs a suspend and a resume callback**,
the resume path runs with hardware in an undefined state, and one driver that
forgets to re-initialise takes the whole machine down on wake. Build the
callbacks into 08.3's device model, not into each driver.
**Done when:** idle power is measurably reduced, frequency scales with load, and
the machine suspends and resumes with every device working.
**Read:** `[ACPI]` §16 (sleeping states) and §7 (device power management);
`[SDM3]` ch. 15 (power and thermal management), the `MWAIT` description in
`[SDM2]`; `[KDOC]` `Documentation/power/` — `suspend-and-cpuhotplug.rst`;
`[P-ENERGY07]`.

### 13.14 — The IOMMU
**Build:** DMAR table parsing, root and context tables, second-level page tables
per device, and a DMA API (from 08.4) that maps buffers into a device's own
address space rather than handing out physical addresses.
**Limit case:** enable it and watch several of your drivers break at once, each
with a DMA fault naming a device and an address. That is the point: every fault
is a place where a driver was DMAing somewhere it never declared, and some of
those were latent corruption you had not yet observed. Fix each. Then verify the
protection actually works — program a device to DMA outside its mapping and
confirm the transaction is blocked rather than silently succeeding.
**Done when:** every driver runs with the IOMMU enforcing, and an out-of-bounds
DMA is demonstrably blocked.
**Read:** `[VTD]` §3 (DMA remapping), §8 (DMAR ACPI tables); `[KDOC]`
`Documentation/arch/x86/iommu.rst`; `[P-DRIVERS12]` for why device isolation is
worth the cost.

### 13.15 — Audio
**Build:** Intel HD Audio — CORB/RIRB command transport, codec and widget
enumeration, a stream descriptor with a buffer descriptor list, and playback
from a ring buffer with the position register driving refill.
**Limit case:** underrun. The hardware plays the buffer whether or not you
refilled it, so a late refill produces an audible click and a *late* refill under
load produces continuous clicking — the classic symptom of an audio path with
insufficient scheduling priority. Measure how much buffer you need for your
scheduler's worst-case latency (from 04.13 and 05.9), and note that this makes
audio the first genuinely latency-critical workload on your OS. Then find the
codec widget graph on your machine, which is a directed graph you must traverse
to discover which pin goes to the speakers.
**Done when:** a WAV file plays without clicks under load, and you can state the
buffer size your scheduler requires.
**Read:** `[HDA]` §3 (register interface), §4 (codec), §7.3 (widget parameters);
`[ELDD]` ch. 13; `[KDOC]` `Documentation/sound/` on the ALSA model.

---

## Where this phase stops

- **No GPU driver.** No mode setting, no acceleration, no external display
  hotplug, no vblank. The framebuffer is what the firmware gave you. This is the
  largest gap in the phase and the main reason a graphical desktop is out of
  reach — see phase 14's honest scope discussion.
- **No Wi-Fi.** The 802.11 stack (association, WPA supplicant, regulatory
  domains) plus a per-chip driver plus a firmware blob is a phase of its own.
  Phase 14 assumes Ethernet, or a USB Ethernet adapter.
- **No Bluetooth, no webcam, no fingerprint reader, no touchpad gestures.**
  Basic touchpad input arrives as a mouse via 13.6/13.8 and nothing more.
- **No hibernate (S4).** S3 only. Writing memory to disk and restoring it is a
  different problem from suspending devices.
- **No Thunderbolt/USB4 device authorization.** 13.14 protects memory from a
  device; deciding whether an unknown device may attach at all is a policy layer
  above it.
- **No SMBIOS/DMI, no EDID parsing.** You will hardcode the panel's resolution
  rather than reading it from the monitor.
- **No CPU microcode loading.** Your CPU runs whatever the firmware installed.

---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
