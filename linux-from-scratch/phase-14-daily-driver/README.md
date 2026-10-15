# Phase 14 — Daily Driver: Actually Using It

**14 exercises.** The difference between an operating system that boots and one
you depend on. This is the capstone, and it is mostly not about kernels.

---

## First, an honest scope discussion

"Use my own OS" has two defensible meanings, and they have very different price
tags. Decide which one you are doing before 14.1, because the whole phase
branches on it.

| | **Option A — daily-drive your LFS system** | **Option B — your kernel does a real job** |
|---|---|---|
| The system | Phase 11's Linux, built from source by you | Phases 00–13's kernel, on the machine from 12.1 |
| Realistic use | A general-purpose workstation. Browser, editor, compiler, mail — everything | A dedicated machine doing one job continuously |
| Achievable? | **Yes, completely.** It is a real Linux distribution | **Yes, for the right job.** Not as a general desktop |
| The work | Package selection, config, upgrades, maintenance | Everything in this phase, plus a job chosen to fit |
| Timeline | Weeks | Months, on top of everything before it |

**Do both.** Option A first — it gives you a machine to work on and to compare
against, and it is the fastest path to "nothing on this computer is here without
me having put it there", which is what you originally asked for. Option B is the
harder and more interesting claim, and this phase is written for it.

#### The wall, stated plainly

You are not going to browse the web on your own kernel. A modern browser needs
roughly: full POSIX threads, a working `futex` under heavy contention, GPU
acceleration or a very fast software rasteriser, fontconfig and FreeType,
a complete TLS stack, JIT-compatible `mmap` (W^X toggling), sandboxing
primitives, audio and video codecs, and a C++ runtime — plus tens of millions of
lines that have never been run against a kernel other than Linux, Windows or
Darwin. Porting one is a multi-year project by a team, not a phase.

Everything else is negotiable. **So the trick is to pick a job that does not need
a browser** — and there are many jobs like that, several of which are genuinely
useful:

- **A router or firewall** for a segment of your network. Uses phase 09 hard, and
  [firewall-from-scratch/](../../firewall-from-scratch/) in this repo.
- **A file server** on your LAN. Uses phase 06 and 13.2/13.3 hard.
- **A build machine** that compiles this repository's projects on a schedule.
  Uses phase 07 self-hosting hard, and it is a brutal stress test.
- **A monitoring or logging box** that collects from other machines and serves a
  status page over HTTP.
- **A terminal workstation** — editor, compiler, shell, over SSH from a real
  laptop, with the display used only for the console. This is the closest to
  "I use my own OS" and is genuinely reachable.
- **A dedicated appliance**: a clock, a display panel, a DNS server (see
  [dns-server/](../../dns-server/)), a backup target.

The job is not a consolation prize. **A machine that does one real thing
continuously will find more bugs in your kernel in a month than every test you
have written**, because it runs the paths you never thought to test, for longer
than you ever ran them, on data you did not choose.

---

## The failure that got you here

Phases 12 and 13 got the machine working. Nothing in them establishes that it
*keeps* working.

Everything so far was validated in sessions: boot, run the test, read the
numbers, power off. A machine you use runs for weeks, accumulates state, gets
software installed on it, loses power at bad moments, sits on a network with
hostile traffic, and holds data you would be upset to lose. Every one of those is
a category of failure your kernel has never seen — and the most common way a
hobby OS dies is not a crash, it is that the author was afraid to keep anything
important on it and therefore never used it.

**Uptime is a different property from correctness, and only running it proves
it.**

---

## Design decisions

> **DESIGN DECISION — repair on crash, or avoid crashing?**
> Making a kernel that never panics is not achievable. Making one that recovers
> in seconds, always, from any state, is — and it changes what a crash costs from
> "a bad day" to "a log line".
> **Chosen:** crash-only design (14.2) — treat restart as the only recovery path,
> make it fast, and make every component tolerate its dependencies restarting.
> Cost: you must give up "I will find and fix every panic first", which is the
> instinct this phase most needs you to drop. `[P-CRASHONLY03]` is the argument.

> **DESIGN DECISION — do you keep real data on it?**
> Keeping nothing important on the machine makes it safe and makes it a toy: you
> will never exercise the paths that matter, and you will never find out whether
> your filesystem is trustworthy.
> **Chosen:** keep real data, and make losing it survivable — checksums,
> off-machine backups, and a *tested restore* (14.3). Cost: a restore drill you
> must actually run, because an untested backup is a belief rather than a backup.

> **DESIGN DECISION — how do you upgrade a system you are using?**
> `make install` over a running system is how phase 11 built everything, and it
> is unrecoverable when the new kernel does not boot.
> **Chosen:** A/B slots with an automatic fallback (14.11) — two kernel images
> and two root filesystems, boot the new one, and roll back automatically if it
> fails to check in. Cost: double the storage, and a boot protocol you must get
> right. Benefit: you can upgrade a machine you cannot physically reach, which is
> the only way you will keep upgrading it.

---

## The exercises

### 14.1 — Choose the job, and set the bar
**Build:** a one-page written commitment: which system (A or B above), what the
machine does, what it holds, who depends on it, the uptime you are aiming for,
and the failure you are *not* willing to accept.
**Limit case:** the bar has to be real enough to fail. "Reliable" is not a bar;
"it serves my LAN's DNS, and I will notice within a minute if it stops" is. Then
name the escape hatch honestly — what you do when it breaks and you need it
working right now — because if there is no fallback you will unconsciously avoid
depending on it, and the phase will not happen.
**Done when:** the commitment is committed to the repo, with the bar stated as
something measurable.
**Read:** `[P-GRAY85]` — "Why Do Computers Stop and What Can Be Done About It?",
which is about exactly this framing; `[deploy-and-debug/](../../deploy-and-debug/)`
in this repo on error budgets.

### 14.2 — Crash-only: recovery as the normal path
**Build:** a hardware watchdog (from 13.12's platform devices) that reboots an
unresponsive machine, a panic path that writes the log to persistent storage
before resetting, automatic reboot on panic, and a boot-time report of why the
last boot ended.
**Limit case:** measure your reboot time and then attack it. If a crash costs
three minutes you will avoid crashing; if it costs eight seconds you will stop
caring, and you will start running the machine hard enough to find real bugs.
Then verify the log actually survives: panic inside the filesystem code, and
inside the disk driver — the two cases where "write the log to disk" is exactly
the thing that is broken. That is why the panic path must reach the storage
device without going through the block layer.
**Done when:** an injected panic produces a readable log after the reboot, from
inside the block layer, and the watchdog recovers a deliberate hang.
**Read:** `[P-CRASHONLY03]`; `[P-GRAY85]`; `[KDOC]`
`Documentation/admin-guide/kdump/` for how Linux does this; `[LKD3]` ch. 18.

### 14.3 — Data you cannot lose
**Build:** a checker for your own filesystem (the `fsck` you skipped in 06.6), a
checksum on data blocks, off-machine backups on a schedule, and a **tested**
restore.
**Limit case:** run the restore drill. Wipe the disk — actually wipe it — and
rebuild the machine from the backup. Time it. Almost every backup scheme that has
never been restored is broken in some specific way (the metadata was not
included, the restore needs a tool that only exists on the dead machine, the
archive was truncated silently), and you find out which only by doing it. Then
corrupt a block on purpose and confirm the checksum catches it rather than
returning wrong data — silent corruption is the failure mode `[P-CORRUPT08]`
found in the field.
**Done when:** the machine has been destroyed and restored from backup at least
once, and a corrupted block is detected rather than served.
**Read:** `[P-E2E84]` — the end-to-end argument, which is *the* justification for
checksumming at the top rather than trusting the disk; `[P-CORRUPT08]`;
`[P-DISKFAIL07]`; `[P-IRONFS05]`.

### 14.4 — Time that is actually correct
**Build:** the RTC read at boot, a monotonic clock separated from wall-clock
time, an NTP client, timezone handling, and a `vDSO`-style fast `gettimeofday`.
**Limit case:** the distinction between monotonic and realtime is not pedantry —
when NTP steps the clock backwards, any code that measured a duration by
subtracting two realtime values computes a negative interval, and timeouts
either fire instantly or never. Audit every timeout in your kernel and userland
for which clock it uses. Then handle the leap second and the clock-step-at-boot
case, when the RTC was hours wrong and every timestamp before the correction is
a lie.
**Done when:** the machine keeps correct time across reboots and network
outages, and no timeout in the system uses the wall clock.
**Read:** `[RFC 5905]` (NTP); `[TLPI]` ch. 10 and 23; `[KDOC]`
`Documentation/timers/timekeeping.rst`; `[LKD3]` ch. 11.

### 14.5 — A terminal you can work in
**Build:** pseudo-terminal pairs (`/dev/ptmx` and the slave side), a terminal
emulator on 13.9's framebuffer with a scrollback buffer, ANSI/VT100 escape
sequence handling, and full integration with phase 07's TTY layer and job
control.
**Limit case:** run a full-screen program — an editor, or anything using
ncurses — and watch it discover every escape sequence you did not implement.
Then resize the terminal and confirm `SIGWINCH` propagates and the program
redraws; then run it over the serial console at 115200 baud and see the same
program behave completely differently because the terminal is slow. Each of
these is a real bug class in the TTY layer you wrote in 07.6 and could not fully
test then.
**Done when:** a full-screen ncurses-style program runs correctly, resizes, and
`^C`/`^Z`/`fg` all work through the pty.
**Read:** `[TLPI]` ch. 62 and 64 (pseudoterminals) in full; `[APUE]` ch. 19; the
`xterm` control sequences document (Moy, Gildea, Dickey) **(free)** — this is
the specification you are implementing.

### 14.6 — The tools to do work
**Build:** the software you need on the machine to use it for the job — at
minimum an editor, the toolchain from 12.3, `make`, and a version-control client
or a way to move code on and off.
**Limit case:** port something you did not write and did not choose — `vi` or
`kilo`, `git` or a subset, BusyBox's remaining applets. Each will demand syscalls
and semantics you have not implemented, and the demands are no longer
hypothetical because you cannot do the job without them. Keep the break log from
07.13 and 12.2 running; by now it is the definitive specification of your
kernel's remaining gaps.
**Done when:** you can edit, build, and commit code on the machine itself,
without moving files to another computer to do it.
**Read:** `[TLPI]` as the reference for whatever breaks; `[POSIX]` where TLPI is
silent; `[c-compiler/](../../c-compiler/)` and
`[bash-from-scratch/](../../bash-from-scratch/)` in this repo.

### 14.7 — The network as it actually is
**Build:** a DHCP client, a DNS resolver (stub, with caching), default-route and
interface configuration, and path-MTU discovery.
**Limit case:** the network is not the clean link you tested phase 09 on. The
lease expires and must be renewed before it does; DNS servers time out and you
must fail over; the link flaps; the MTU on some path is smaller than yours and
the "black hole" case — where an ICMP Fragmentation Needed is filtered by a
firewall — makes large packets vanish while small ones work, which is the most
confusing network failure there is. Construct that one deliberately.
**Done when:** the machine configures itself on your network from cold boot,
survives a DHCP lease renewal and a cable flap unattended, and handles a
reduced-MTU path.
**Read:** `[RFC 2131]` (DHCP); `[RFC 1034]`/`[RFC 1035]` (DNS); `[RFC 8899]` and
`[RFC 1191]` (PMTU discovery and its failure modes); `[TCPIP1]` ch. 4, 11, 13;
`[dns-server/](../../dns-server/)` in this repo.

### 14.8 — TLS, and reaching the modern internet
**Build:** a TLS 1.3 client — port a library (BearSSL and mbedTLS are small and
portable) or use [cryptographic-library/](../../cryptographic-library/) from this
repo — plus certificate validation and a trust store.
**Limit case:** certificate validation is the part everyone gets wrong, and
getting it wrong is invisible because everything still works. Test the failures
explicitly: an expired certificate, a hostname mismatch, an untrusted issuer, a
revoked certificate, and a valid certificate for the wrong host. Each must be
*rejected*. A TLS client that connects successfully to every server including
the bad ones has implemented encryption without authentication, which is worth
approximately nothing against an active attacker.
**Done when:** you can fetch an HTTPS URL from your OS, and all five invalid-
certificate cases are refused with distinct errors.
**Read:** `[RFC 8446]` (TLS 1.3); `[RFC 5280]` §6 (certification path
validation) — the algorithm you must implement; Georgiev et al., "The Most
Dangerous Code in the World: Validating SSL Certificates in Non-Browser
Software", *CCS* 2012.

### 14.9 — Remote access
**Build:** a way to reach the machine from another computer — an SSH server
(port one, or implement the transport and userauth layers) or, at minimum, an
authenticated shell over your own protocol on a private network.
**Limit case:** this is what makes the machine usable, because it lets you work
from a laptop with a browser while the job runs on your OS. It is also a service
listening on a network, which makes every parsing bug in it remotely reachable —
so the protocol parser is the most security-sensitive code you have written, and
10.5's fuzzing discipline applies to it directly. Then handle the case that
matters at 3am: you are locked out because the network config broke. That is
what the serial console and 14.2's watchdog are for.
**Done when:** you can log in remotely, run a full-screen program over the
connection, and you have a tested path back in when the network is broken.
**Read:** `[RFC 4251]`–`[RFC 4254]` (SSH architecture, transport, auth,
connection); `[TLPI]` ch. 61; `[UNP]` ch. 30 on server design.

### 14.10 — Know what it is doing
**Build:** metrics the machine exports (uptime, memory, per-subsystem counters
from phases 02–13, disk and network rates), a health endpoint served over HTTP,
persistent logs with rotation, and an alert that reaches you when the bar from
14.1 is missed.
**Limit case:** the alert must fire when the machine is *dead*, which is exactly
when the machine cannot send it. So the check has to come from outside —
something else polls it, and alerts on silence. Build it that way, then test it
by pulling the power. Then tune it: an alert that fires on every transient blip
gets ignored within a week, and an ignored alert is worse than none because it
is a false sense of coverage.
**Done when:** you find out about a failure from the alert rather than by
noticing, and a deliberate hard power-off pages you.
**Read:** `[deploy-and-debug/](../../deploy-and-debug/)` in this repo — it is
about exactly this; `[P-GRAY85]`; `[http-server/](../../http-server/)` for the
endpoint.

### 14.11 — Upgrade without reinstalling
**Build:** A/B slots — two kernel images and two root filesystems, a bootloader
that picks the active one, a "new image must check in within N seconds or we
roll back" protocol, and a way to push an upgrade remotely.
**Limit case:** deliberately ship a kernel that does not boot. The machine must
come back on the old one, unattended, without you touching it — that is the whole
mechanism, and it is untested until you break it on purpose. Then ship one that
boots but is *subtly* broken (a driver that fails after ten minutes): the check-in
protocol must be long enough or deep enough to catch it, and finding that it is
not is the more valuable failure.
**Done when:** a bad kernel is automatically rolled back with no console access,
twice — once for a boot failure and once for a late failure.
**Read:** `[P-NIX06]` on atomic upgrade and rollback as a design property;
`[MELP]` ch. 10 (Updating Software in the Field) — the best practical treatment;
`[P-CRASHONLY03]`.

### 14.12 — Security posture for a machine on a real network
**Build:** apply phase 10 to the running system — no unnecessary services
listening, unprivileged service accounts, seccomp filters on network-facing
code, the IOMMU from 13.14 enabled, and a firewall.
**Limit case:** port-scan and fuzz your own machine from another host. Every
listening port is an entry point written by you, and the parsers behind them
(DHCP, DNS, HTTP, SSH, TLS) all consume attacker-controlled input before any
authentication happens. Fuzz each one. Then re-run 10.5's syscall audit, because
phases 11–13 added syscalls and drivers since. Then write down what an attacker
on your LAN can reach, and what one with physical access can (which, with a
locked-down IOMMU and no disk encryption, is still everything on the disk).
**Done when:** the fuzzers run clean, the listening surface is minimal and
documented, and the threat model is written.
**Read:** `[TLPI]` ch. 38; `[P-PROT75]`; `[firewall-from-scratch/](../../firewall-from-scratch/)`
in this repo; `[P-SYSTRACE03]`.

### 14.13 — The thirty-day run
**Build:** the actual dogfooding. Put the machine into service on the job from
14.1 and keep it there for thirty days, with a defect log: every failure, every
restart, its cause, and its fix.
**Limit case:** this is the exercise, and it cannot be shortened. Expect the
failure distribution to surprise you: the bugs that show up will mostly *not* be
in the kernel mechanisms you worried about, but in resource leaks that need a
week to become visible, timer arithmetic that wraps, an allocator that fragments
under a workload you never simulated, a log that fills the disk, and error paths
that were never taken in testing because errors never happened in testing. Track
mean time between failures per week — if it is not rising, you are fixing
symptoms rather than causes.
**Done when:** thirty days have passed with the machine in service, and the
defect log with MTBF-per-week is committed.
**Read:** `[P-GRAY85]` — this exercise is his paper, performed; `[P-CRASHONLY03]`;
`[deploy-and-debug/](../../deploy-and-debug/)` on reading the resulting numbers.

### 14.14 — The verdict
**Build:** the final write-up, extending 12.6: what the machine does, what it
cannot do, the thirty-day reliability numbers, the complete list of what you
still depend on that you did not write (firmware blobs, the CPU's microcode, the
UEFI implementation, the toolchain's own history), and what you would build
differently.
**Limit case:** answer the question you started with — *"am I in complete control
of what is happening in my machine?"* — precisely rather than rhetorically. The
true answer is "more than almost anyone, and still not completely", and the value
is in enumerating the remainder: every blob from 13.11, the management engine you
cannot disable, the firmware that ran before your first instruction, and the
compiler bootstrap from 11.1. That enumeration is the most honest and most useful
document in this entire project.
**Done when:** someone could read it and know exactly what you built, what it is
good for, and where the floor of your control actually is.
**Read:** `[P-TRUST84]` a fifth and final time; `[P-UNIX74]` as the model for
describing a whole system briefly; `[PHILOSOPHY.md](../../PHILOSOPHY.md)` in this
repo.

---

## Where this phase stops

- **No graphical desktop, and no browser.** See the scope discussion above. A
  compositor is reachable on top of 13.9 if you want one; the browser is not.
- **No multi-machine anything.** One box. Clustering, replication and consensus
  are [dynamo-paper/](../../dynamo-paper/) and
  [system-design/](../../system-design/) in this repo.
- **No disk encryption.** Which means physical access defeats everything in
  14.12. dm-crypt-equivalent is a good follow-on using
  [cryptographic-library/](../../cryptographic-library/).
- **No printing, no scanning, no peripherals beyond phase 13.**
- **No third-party software ecosystem.** Everything running on the machine is
  something you wrote or explicitly ported. That is the point, and it is also the
  ceiling.
- **The thirty days is a floor, not a finish.** The interesting failures start
  around month three.

---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
