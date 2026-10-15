# Phase 10 — Security and Isolation

**12 exercises.** Until now, every program on your OS could do everything. This
phase is about making that false, and finding out how much of your kernel assumed
otherwise.

---

## The failure that got you here

Your kernel has exactly one privilege boundary: ring 0 versus ring 3, built in
04.3. Above that line, nothing. Any process can open any file, signal any process,
see every other process in `/proc`, exhaust all memory, and consume every CPU. A
program you download is a program you have handed the machine to.

And nine phases of code were written assuming the caller was you. Every syscall
that takes a pointer, a length, a path, or a file descriptor is now an interface
to an adversary. **Security is not a phase you add; it is an audit of everything
before it** — which is why it is placed here, where there is something to audit.

---

## Design decisions

> **DESIGN DECISION — discretionary or mandatory access control?**
> DAC (Unix permissions) lets the file's owner decide, which means a compromised
> process runs with all of its user's authority — including the authority to give
> the file away. MAC (SELinux, AppArmor) enforces a system policy the process
> cannot alter, and requires someone to write and maintain that policy.
> **Chosen:** DAC (10.1–10.3) as the base, an LSM-style hook layer (10.10) so MAC
> is possible, and no policy language. Cost: your system is exactly as secure as
> its least careful `setuid` binary. Read `[P-PROT75]` for why that was already
> known in 1975.

> **DESIGN DECISION — isolate with virtualization, or with namespaces?**
> A VM gives strong isolation, a separate kernel, and a large resource cost.
> Namespaces give each process a different *view* of one kernel's resources —
> cheap, and only as strong as the kernel's own bug-freeness.
> **Chosen:** namespaces and cgroups (10.6–10.9), because containers are the
> mechanism you actually meet, and because implementing them makes clear exactly
> how much shared attack surface they leave. `[P-XEN03]` versus `[P-CGROUPS07]`
> is the reading.

> **DESIGN DECISION — do you implement speculative-execution mitigations?**
> KPTI costs a `CR3` switch and a TLB flush on every syscall — measurably, 5–30%.
> Not implementing it means user code can read kernel memory on affected hardware.
> **Chosen:** implement it (10.11) and *measure* the cost, because that number is
> the most concrete thing anyone can say about the price of security.

---

## The exercises

### 10.1 — Users, groups, credentials
**Build:** uid/gid/euid/egid/suid/sgid and supplementary groups on the task
struct, inherited across `fork`, plus `setuid`/`setgid`/`getuid` and friends.
**Limit case:** the saved-set-uid exists so a privileged program can drop
privilege *temporarily* and regain it. Which means "dropping privilege" is
usually reversible, and a program that intended to drop permanently must do it in
a specific order (groups first, then uid) — get it backwards and the drop
silently fails. Construct both, and check the return value of every `setuid`,
because ignoring it is the classic root exploit.
**Done when:** transitions match Linux's semantics case by case, and an
unprivileged process cannot regain privilege it never had.
**Read:** `[TLPI]` ch. 9 — the state diagrams for set-user-ID are the
specification; `[APUE]` ch. 8.11; Chen, Wagner, Dean, "Setuid Demystified",
*USENIX Security* 2002.

### 10.2 — File permissions
**Build:** mode bits, ownership, the three-class check (owner/group/other),
`chmod`, `chown`, `umask`, and the sticky bit on directories.
**Limit case:** permission checks happen at `open`, not at `read`. A descriptor
opened before a `chmod` stays usable — so revoking access does not revoke existing
access, and passing a descriptor passes authority. Demonstrate it. Then: the
sticky bit on `/tmp`, without which any user can delete any other user's temp
file; construct that deletion, then fix it.
**Done when:** the full permission matrix is enforced, `/tmp` semantics work, and
the open-descriptor-survives-chmod case is demonstrated and documented.
**Read:** `[TLPI]` ch. 15.4; `[BACH]` ch. 4; `[P-PROT75]` §I — the taxonomy of
protection mechanisms this implements.

### 10.3 — `setuid` binaries, and their entire problem
**Build:** the set-user-ID bit honoured by `exec`, with the environment sanitised
across the privilege transition.
**Limit case:** a `setuid` program inherits, from an untrusted caller: the
environment, open file descriptors 0/1/2 (or their absence!), resource limits,
the umask, signal dispositions, and the current directory. Each has been a real
exploit. The fd-0-closed case is the elegant one: close stdin, exec a setuid
program, and the first file it opens becomes fd 0 — which it then writes its
output to. Construct that. Then decide, per item, what you sanitise.
**Done when:** a `setuid` binary works, and each of the six inherited-state
attacks is either blocked or documented as accepted.
**Read:** "Setuid Demystified" (above); `[TLPI]` ch. 38 (Writing Secure
Privileged Programs) — the checklist is the exercise; `[P-SMASH96]`.

### 10.4 — Resource limits
**Build:** `rlimit`s — address space, open files, processes per user, CPU time,
core size — enforced at the point of allocation.
**Limit case:** the fork bomb. Run one, watch the machine die, then set
`RLIMIT_NPROC` and watch it not. Then find where limits are *not* enforced:
kernel memory allocated on behalf of a process (page tables, socket buffers,
dentries) is not covered by any rlimit, and a process can consume unbounded
kernel memory through legal syscalls. That gap is precisely what cgroups exist to
close, and you should find it yourself before 10.8.
**Done when:** a fork bomb and an allocation bomb are both contained, and you can
name at least two kernel allocations no rlimit bounds.
**Read:** `[TLPI]` ch. 36; `[LKD3]` ch. 3; `[P-CGROUPS07]` §1 for the motivation.

### 10.5 — Audit the syscall boundary
**Build:** a systematic review of every syscall you have written, plus a fuzzer
that calls each with hostile arguments.
**Limit case:** for each syscall, check: unvalidated user pointers; integer
overflow in a size computation (`count * size`, `offset + len`); TOCTOU between
validation and use; missing permission check; error path leaking a reference or a
lock; and a signed/unsigned confusion in a length. Fuzz with garbage pointers,
`SIZE_MAX` lengths, negative fds and huge offsets. **Expect to find real bugs.**
Write down each one — this list is the honest state of your kernel.
**Done when:** the fuzzer runs for an hour without a panic or a leak, and the bug
list is committed.
**Read:** `[LKD3]` ch. 5 "Verifying the Parameters"; `[TLPI]` ch. 38; `[KDOC]`
`Documentation/process/adding-syscalls.rst`; the syzkaller documentation for what
systematic kernel fuzzing looks like.

### 10.6 — Namespaces: PID and mount
**Build:** `clone` flags creating a new PID namespace (with its own PID 1 and a
translation between namespace-local and global IDs) and a new mount namespace
(a private mount table).
**Limit case:** a process must see *different* PIDs for the same task depending
on which namespace asks — so every place a PID crosses the kernel/user boundary
needs translation, and missing one leaks information across the boundary. Then:
PID 1 in a namespace dying must kill the namespace, not the machine. And a mount
namespace must be able to see a subtree without seeing its parent — build
`pivot_root` and confirm `..` cannot escape.
**Done when:** a process sees itself as PID 1 with its own filesystem root, and
cannot observe or signal anything outside.
**Read:** `[TLPI]` ch. 28.2 and the namespaces chapters of the online TLPI
supplement; `[KDOC]` `Documentation/admin-guide/namespaces/`; Kerrisk's LWN
namespaces series **(free)**.

### 10.7 — Namespaces: user, network, UTS, IPC
**Build:** the remaining namespace types, especially the user namespace with uid
mapping.
**Limit case:** the user namespace is the dangerous one: it lets an unprivileged
user become root *inside* the namespace, which grants capabilities over
namespaced resources — and every kernel bug reachable from that expanded surface
becomes exploitable by any user. This is a real and repeated CVE pattern. Build
the uid-mapping check carefully, then write down what a root-in-namespace process
can still reach in *your* kernel.
**Done when:** uid mapping works, a namespaced root cannot affect the host, and
you have enumerated the surface it can still reach.
**Read:** Kerrisk, "User namespaces progress", LWN **(free)**; `[KDOC]`
`Documentation/admin-guide/namespaces/`; the CVE history of `user_namespaces` as
a case study.

### 10.8 — cgroups
**Build:** hierarchical resource control: CPU shares wired into your phase-04/05
scheduler, a memory limit enforced at allocation with an OOM action, and PID
counts.
**Limit case:** the memory limit must apply to kernel memory allocated *on behalf
of* the process, which is the gap you found in 10.4. Then: what happens at the
limit? Killing is brutal; failing the allocation means a syscall returns `ENOMEM`
in a path that may not handle it; throttling can deadlock if the process holds a
lock. Pick a policy, construct the case where it behaves badly, and document it.
**Done when:** a cgroup with a 64 MiB limit contains a process that tries to
allocate 1 GiB, and CPU shares are measurably enforced between two groups.
**Read:** `[P-CGROUPS07]`; `[KDOC]` `Documentation/admin-guide/cgroup-v2.rst` —
the "Memory" and "CPU" sections; `[LWN]` on the v1→v2 redesign and why it
happened.

### 10.9 — A container, from your own parts
**Build:** a `run` tool combining namespaces, cgroups, `pivot_root`, capability
dropping and a seccomp filter — a container runtime in a few hundred lines.
**Limit case:** enumerate what your container still shares with the host: the
kernel itself, the scheduler, the page cache, `/dev` entries you passed through,
the clock, and every syscall you did not filter. A container is a *configuration*
of isolation mechanisms, not an isolation boundary — this exercise is where that
stops being a slogan. Then break out of your own container deliberately by
exploiting one thing you left shared.
**Done when:** a process runs isolated with a resource budget, and you have both
a written share-surface list and a demonstrated escape from a misconfiguration.
**Read:** `[P-XEN03]` for the contrast; the OCI runtime specification;
`[P-CGROUPS07]`; Kerrisk's namespaces series again, now as reference.

### 10.10 — Capabilities and a security hook layer
**Build:** split root into capabilities (`CAP_NET_ADMIN`, `CAP_SYS_ADMIN`, …),
check them where you currently check `uid == 0`, and add LSM-style hooks at every
security decision point.
**Limit case:** `CAP_SYS_ADMIN` is a joke in the security community because it
guards so many unrelated operations that holding it is equivalent to root. As you
assign capabilities, watch yourself create the same problem — the temptation to
put every new check behind one capability is enormous. Resist it, and see how
many you end up with. Then: capability inheritance across `exec`, which has its
own rules and its own exploit history.
**Done when:** no code path tests `uid == 0` directly, and a process with exactly
one capability can do exactly one privileged thing.
**Read:** `[TLPI]` ch. 39 in full; `[P-LSM02]`; `[KDOC]`
`Documentation/security/`; `capabilities(7)`.

### 10.11 — Kernel hardening
**Build:** KASLR (randomise the kernel's base at boot), KPTI (separate user and
kernel page tables), SMEP/SMAP, stack canaries, and guard pages on kernel stacks.
**Limit case:** measure KPTI's cost — syscall latency with and without, from
04.13's benchmark. It is 5–30%, and it exists because of `[P-MELTDOWN18]`. That
trade is the clearest example in the whole project of security having a price you
can put a number on. Then test SMAP: have the kernel dereference a user pointer
without the explicit `stac`/`clac` window and confirm it faults.
**Done when:** each mitigation is enabled and *demonstrated* by an attack that
now fails, and the KPTI cost is measured.
**Read:** `[P-MELTDOWN18]` and `[P-SPECTRE19]`; `[SDM3]` ch. 5.6 (SMEP/SMAP);
`[KDOC]` `Documentation/arch/x86/pti.rst`; `[LWN]` on the KAISER/KPTI
development.

### 10.12 — Seccomp: a syscall filter
**Build:** a per-process syscall filter — a whitelist mode and a small
bytecode-filter mode — with kill/errno/trap actions, inherited across `fork` and
`exec` and irrevocable once set.
**Limit case:** irrevocability is the whole security property, and it must hold
across `exec` of a `setuid` binary — otherwise the filter is escapable by design.
Then: filtering on syscall *arguments* is unsound when the argument is a pointer,
because the memory can change between the filter's read and the kernel's use
(TOCTOU again, from 04.4). This is why seccomp only inspects register values and
never dereferences. Derive that restriction yourself before reading why.
**Done when:** a filtered process is killed on a forbidden syscall, cannot lift
the filter, and the filter survives `exec`.
**Read:** `[P-SYSTRACE03]` — the paper whose weaknesses seccomp-bpf was designed
around; `[KDOC]` `Documentation/userspace-api/seccomp_filter.rst`; `[TLPI]`
ch. 38 for the surrounding discipline.

---

## Where this phase stops

- **No SELinux/AppArmor policy language.** You build the hook layer in 10.10;
  writing a policy engine and a policy is another project.
- **No IOMMU.** Phase 08's DMA still trusts every device completely. On real
  hardware (phase 12) that is a genuine hole — a malicious PCIe device or
  Thunderbolt peripheral reads all of memory.
- **No secure boot, no measured boot, no TPM.** Which means all of this defends
  against a compromised *process*, not a compromised *boot chain*. Phase 11's
  reading includes `[P-TRUST84]` for a reason.
- **No cryptography in the kernel.** No dm-crypt, no keyring.
  [cryptographic-library/](../../cryptographic-library/) has the primitives.
- **No formal guarantees.** `[P-SEL4]` proves a kernel correct; you have tested
  one. Know the difference between the two claims.
- **No exploit mitigation for userspace beyond W^X and ASLR-by-KASLR.** No CFI,
  no shadow stacks.

---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
