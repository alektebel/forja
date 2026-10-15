# References

Every exercise in this directory cites its sources by the tags below. The rule
of thumb: **a book teaches you the shape, a paper teaches you the decision.**
When an exercise cites both, read the book section first and the paper after you
have written the code — the paper is arguing with alternatives you will only
recognise once you have picked one.

Freely available items are marked **(free)**.

---

## Core books — operating systems

| Tag | Work |
|---|---|
| `[OSTEP]` | Arpaci-Dusseau, R. & A., *Operating Systems: Three Easy Pieces*, 1.10 (2023). **(free)** The single best starting text; virtualization / concurrency / persistence. |
| `[XV6]` | Cox, R., Kaashoek, F., Morris, R., *xv6: a simple, Unix-like teaching operating system* (RISC-V ed., MIT 6.1810). **(free)** A complete, readable Unix in ~9k lines, with a book that annotates it line by line. |
| `[MOS4]` | Tanenbaum, A. & Bos, H., *Modern Operating Systems*, 4th ed. (2014). |
| `[OSDI]` | Tanenbaum, A. & Woodhull, A., *Operating Systems: Design and Implementation*, 3rd ed. (2006). MINIX 3; the microkernel counter-argument. |
| `[OSC]` | Silberschatz, Galvin, Gagne, *Operating System Concepts*, 10th ed. (2018). Reference-grade; use for definitions. |
| `[LIONS]` | Lions, J., *A Commentary on the Sixth Edition UNIX Operating System* (1976). The original "read the source" book. |
| `[BACH]` | Bach, M., *The Design of the UNIX Operating System* (1986). Why Unix is shaped like that. |
| `[FBSD]` | McKusick, Neville-Neil, Watson, *The Design and Implementation of the FreeBSD Operating System*, 2nd ed. (2014). The best-documented production kernel. |

## Core books — Linux specifically

| Tag | Work |
|---|---|
| `[LKD3]` | Love, R., *Linux Kernel Development*, 3rd ed. (2010). Start here for Linux internals. |
| `[UTLK]` | Bovet, D. & Cesati, M., *Understanding the Linux Kernel*, 3rd ed. (2005). Dated (2.6) but unmatched on the data structures. |
| `[MAUERER]` | Mauerer, W., *Professional Linux Kernel Architecture* (2008). |
| `[LDD3]` | Corbet, Rubini, Kroah-Hartman, *Linux Device Drivers*, 3rd ed. (2005). **(free)** |
| `[ELDD]` | Venkateswaran, S., *Essential Linux Device Drivers* (2008). The subsystem-by-subsystem companion to `[LDD3]` — input, USB, storage, audio. |
| `[USBCIN]` | Axelson, J., *USB Complete*, 5th ed. (2015). The readable path into `[USB]`. |
| `[PCIESA]` | Budruk, Anderson, Shanley, *PCI Express System Architecture* (2003). |
| `[GORMAN]` | Gorman, M., *Understanding the Linux Virtual Memory Manager* (2004). **(free)** |
| `[KNUTSHELL]` | Kroah-Hartman, G., *Linux Kernel in a Nutshell* (2006). **(free)** Kernel configuration and build. |
| `[LINSIDES]` | *Linux Inside* (0xAX). **(free)** A walk through modern boot and init code. |
| `[KDOC]` | The kernel's own `Documentation/` tree and the source. **(free)** The only reference that is never out of date. |
| `[LWN]` | LWN.net kernel index and Corbet's articles. **(free)** How each subsystem actually got that way. |

## Core books — userland, systems programming, machine

| Tag | Work |
|---|---|
| `[TLPI]` | Kerrisk, M., *The Linux Programming Interface* (2010). The syscall surface you are implementing. |
| `[APUE]` | Stevens, W. R. & Rago, S., *Advanced Programming in the UNIX Environment*, 3rd ed. (2013). |
| `[CSAPP]` | Bryant, R. & O'Hallaron, D., *Computer Systems: A Programmer's Perspective*, 3rd ed. (2015). |
| `[LINKLOAD]` | Levine, J., *Linkers and Loaders* (1999). |
| `[AMPP]` | Herlihy, M. & Shavit, N., *The Art of Multiprocessor Programming*, 2nd ed. (2020). |
| `[PMCCC]` | Sorin, Hill, Wood, *A Primer on Memory Consistency and Cache Coherence*, 2nd ed. (2020). |
| `[HP6]` | Hennessy & Patterson, *Computer Architecture: A Quantitative Approach*, 6th ed. (2017). |

## Networking

| Tag | Work |
|---|---|
| `[TCPIP1]` | Fall, K. & Stevens, W. R., *TCP/IP Illustrated, Volume 1: The Protocols*, 2nd ed. (2011). |
| `[TCPIP2]` | Wright, G. & Stevens, W. R., *TCP/IP Illustrated, Volume 2: The Implementation* (1995). An actual stack, annotated. |
| `[UNP]` | Stevens, Fenner, Rudoff, *UNIX Network Programming, Vol 1*, 3rd ed. (2003). |

## Distribution building (Track D)

| Tag | Work |
|---|---|
| `[LFS]` | Beekmans, G. et al., *Linux From Scratch*, current stable (systemd and SysV editions). **(free)** |
| `[BLFS]` | *Beyond Linux From Scratch*. **(free)** X, networking, desktop, package sets. |
| `[CLFS]` | *Cross Linux From Scratch*. **(free)** The cross-compilation path; read for *why* the two-pass toolchain exists. |
| `[MELP]` | Simmonds, C., *Mastering Embedded Linux Programming*, 3rd ed. (2021). Boot, init, initramfs, root filesystems. |
| `[BELS]` | Yaghmour et al., *Building Embedded Linux Systems*, 2nd ed. (2008). |
| `[BOOTLIN]` | Bootlin training materials and kernel-source cross-reference. **(free)** |
| `[SAGE]` | Nemeth et al., *UNIX and Linux System Administration Handbook*, 5th ed. (2017). |

## Specifications and manuals

| Tag | Work |
|---|---|
| `[SDM3]` | Intel, *64 and IA-32 Architectures Software Developer's Manual, Vol. 3 (System Programming Guide)*. **(free)** The authority for everything in phases 01–05. |
| `[SDM2]` | Intel, *SDM Vol. 2 (Instruction Set Reference)*. **(free)** |
| `[APM2]` | AMD, *AMD64 Architecture Programmer's Manual, Vol. 2: System Programming*. **(free)** Often clearer than the SDM on long mode. |
| `[ELF]` | *System V ABI*, generic ELF spec + x86-64 psABI supplement. **(free)** |
| `[DWARF]` | *DWARF Debugging Information Format*, v5. **(free)** |
| `[MB2]` | *Multiboot2 Specification*, GNU. **(free)** |
| `[UEFI]` | *UEFI Specification*, current. **(free)** |
| `[ACPI]` | *ACPI Specification*, current. **(free)** Tables, MADT, power states. |
| `[VIRTIO]` | *Virtual I/O Device (VIRTIO) Specification*, OASIS, v1.2. **(free)** |
| `[ATA]` | *AT Attachment with Packet Interface* (ATA/ATAPI-8). |
| `[AHCI]` | Intel, *Serial ATA Advanced Host Controller Interface (AHCI) Specification*, 1.3.1. **(free)** |
| `[NVME]` | *NVM Express Base Specification*, current. **(free)** |
| `[SCSI]` | INCITS, *SCSI Primary Commands* (SPC-4) and *SCSI Block Commands* (SBC-3). |
| `[USB]` | *Universal Serial Bus Specification* 2.0 (ch. 9, 11) and *USB 3.2*. **(free)** |
| `[XHCI]` | Intel, *eXtensible Host Controller Interface for USB xHCI*, 1.2. **(free)** |
| `[HID]` | USB-IF, *Device Class Definition for Human Interface Devices*, 1.11. **(free)** |
| `[HIDUT]` | USB-IF, *HID Usage Tables*, current. **(free)** |
| `[USBMSC]` | USB-IF, *Mass Storage Class — Bulk-Only Transport*, 1.0. **(free)** |
| `[HDA]` | Intel, *High Definition Audio Specification*, 1.0a. **(free)** |
| `[VTD]` | Intel, *Virtualization Technology for Directed I/O Architecture Specification*. **(free)** |
| `[PCI]` | *PCI Local Bus Specification* 3.0 and *PCI Express Base Specification*. |
| `[POSIX]` | IEEE Std 1003.1, *POSIX.1-2017*. **(free)** |
| `[RFC]` | IETF RFCs, cited individually (e.g. `[RFC 793]`). **(free)** |

## Tutorial traditions (use as maps, not as texts)

| Tag | Work |
|---|---|
| `[OSDEV]` | The OSDev Wiki. **(free)** Indispensable and occasionally wrong; verify against `[SDM3]`. |
| `[LITTLEBOOK]` | Helin, E. & Renberg, A., *The Little Book About OS Development* (2015). **(free)** |
| `[OS01]` | Do Hoang Tu, *Operating Systems: From 0 to 1* (2017). **(free)** |
| `[BLOGOS]` | Oppermann, P., *Writing an OS in Rust*. **(free)** Best modern write-up of x86-64 boot, IDT and paging, even if you write C. |
| `[BRAN]` | Friesen, B., *Bran's Kernel Development Tutorial* and Molloy's *JamesM's kernel development tutorials*. **(free)** Historical; where most of the folklore comes from. |

---

## Papers

Cited by tag. Where the paper is the origin of a mechanism you are building, the
exercise says to read it *after* your first attempt.

### Foundations

| Tag | Paper |
|---|---|
| `[P-UNIX74]` | Ritchie, D. & Thompson, K., "The UNIX Time-Sharing System", *CACM* 17(7), 1974. |
| `[P-UNIXEV]` | Ritchie, D., "The Evolution of the Unix Time-sharing System", 1984. |
| `[P-THE68]` | Dijkstra, E. W., "The Structure of the 'THE'-Multiprogramming System", *CACM* 11(5), 1968. |
| `[P-COOP65]` | Dijkstra, E. W., "Cooperating Sequential Processes", EWD123, 1965. |
| `[P-MULTICS72]` | Bensoussan, Clingen, Daley, "The Multics Virtual Memory: Concepts and Design", *CACM* 15(5), 1972. |
| `[P-PROT75]` | Saltzer, J. & Schroeder, M., "The Protection of Information in Computer Systems", *Proc. IEEE* 63(9), 1975. |
| `[P-WORTH]` | Lampson, B., "Hints for Computer System Design", *SOSP* 1983. |

### Memory

| Tag | Paper |
|---|---|
| `[P-WS68]` | Denning, P., "The Working Set Model for Program Behavior", *CACM* 11(5), 1968. |
| `[P-BELADY66]` | Belady, L., "A Study of Replacement Algorithms for a Virtual-Storage Computer", *IBM Systems Journal*, 1966. |
| `[P-CLOCK]` | Corbató, F., "A Paging Experiment with the Multics System", 1968. Origin of CLOCK. |
| `[P-SLAB94]` | Bonwick, J., "The Slab Allocator: An Object-Caching Kernel Memory Allocator", *USENIX Summer* 1994. |
| `[P-VMEM01]` | Bonwick, J. & Adams, J., "Magazines and Vmem: Extending the Slab Allocator to Many CPUs and Arbitrary Resources", *USENIX* 2001. |
| `[P-BUDDY]` | Knowlton, K., "A Fast Storage Allocator", *CACM* 8(10), 1965. |
| `[P-TLB]` | Bhattacharjee, A. & Lustig, D., *Architectural and Operating System Support for Virtual Memory* (synthesis lecture), 2017. |

### Concurrency and scheduling

| Tag | Paper |
|---|---|
| `[P-MON74]` | Hoare, C.A.R., "Monitors: An Operating System Structuring Concept", *CACM* 17(10), 1974. |
| `[P-BAKERY74]` | Lamport, L., "A New Solution of Dijkstra's Concurrent Programming Problem", *CACM* 17(8), 1974. |
| `[P-FASTMX87]` | Lamport, L., "A Fast Mutual Exclusion Algorithm", *TOCS* 5(1), 1987. |
| `[P-SPINLOCK90]` | Anderson, T., "The Performance of Spin Lock Alternatives for Shared-Memory Multiprocessors", *TPDS* 1(1), 1990. |
| `[P-MCS91]` | Mellor-Crummey, J. & Scott, M., "Algorithms for Scalable Synchronization on Shared-Memory Multiprocessors", *TOCS* 9(1), 1991. |
| `[P-RCU01]` | McKenney, P. & Slingwine, J., "Read-Copy Update: Using Execution History to Solve Concurrency Problems", 1998/2001; and McKenney, *Is Parallel Programming Hard?* **(free)** |
| `[P-SCHEDACT91]` | Anderson, Bershad, Lazowska, Levy, "Scheduler Activations", *SOSP* 1991. |
| `[P-LOTTERY94]` | Waldspurger, C. & Weihl, W., "Lottery Scheduling: Flexible Proportional-Share Resource Management", *OSDI* 1994. |
| `[P-MLFQ]` | Corbató, Merwin-Daggett, Daley, "An Experimental Time-Sharing System", 1962. Origin of multi-level feedback. |
| `[P-WASTED16]` | Lozi et al., "The Linux Scheduler: a Decade of Wasted Cores", *EuroSys* 2016. |
| `[P-SCALE10]` | Boyd-Wickizer et al., "An Analysis of Linux Scalability to Many Cores", *OSDI* 2010. |
| `[P-DEADLINE]` | Liu, C. & Layland, J., "Scheduling Algorithms for Multiprogramming in a Hard-Real-Time Environment", *JACM* 20(1), 1973. |

### Storage and filesystems

| Tag | Paper |
|---|---|
| `[P-FFS84]` | McKusick, Joy, Leffler, Fabry, "A Fast File System for UNIX", *TOCS* 2(3), 1984. |
| `[P-VNODE86]` | Kleiman, S., "Vnodes: An Architecture for Multiple File System Types in Sun UNIX", *USENIX* 1986. |
| `[P-LFS92]` | Rosenblum, M. & Ousterhout, J., "The Design and Implementation of a Log-Structured File System", *TOCS* 10(1), 1992. |
| `[P-CEDAR87]` | Hagmann, R., "Reimplementing the Cedar File System Using Logging and Group Commit", *SOSP* 1987. |
| `[P-SOFTUPD94]` | Ganger, G. & Patt, Y., "Metadata Update Performance in File Systems", *OSDI* 1994. |
| `[P-JOURNVS00]` | Seltzer et al., "Journaling Versus Soft Updates: Asynchronous Meta-data Protection in File Systems", *USENIX* 2000. |
| `[P-EXT2]` | Card, Ts'o, Tweedie, "Design and Implementation of the Second Extended Filesystem", 1994. |
| `[P-EXT3]` | Tweedie, S., "Journaling the Linux ext2fs Filesystem", *LinuxExpo* 1998. |
| `[P-BTRFS13]` | Rodeh, Bacik, Mason, "BTRFS: The Linux B-Tree Filesystem", *TOS* 9(3), 2013. |
| `[P-IRONFS05]` | Prabhakaran et al., "IRON File Systems", *SOSP* 2005. What filesystems do when the disk lies. |
| `[P-PILLAI14]` | Pillai et al., "All File Systems Are Not Created Equal: On the Complexity of Crafting Crash-Consistent Applications", *OSDI* 2014. |
| `[P-CORRUPT08]` | Bairavasundaram et al., "An Analysis of Data Corruption in the Storage Stack", *FAST* 2008. Silent corruption, measured in the field. |
| `[P-DISKFAIL07]` | Pinheiro, Weber, Barroso, "Failure Trends in a Large Disk Drive Population", *FAST* 2007. |
| `[P-STREAMS84]` | Ritchie, D., "A Stream Input-Output System", *AT&T Bell Labs Tech. J.*, 1984. |

### Devices, drivers, I/O

| Tag | Paper |
|---|---|
| `[P-LIVELOCK96]` | Mogul, J. & Ramakrishnan, K., "Eliminating Receive Livelock in an Interrupt-Driven Kernel", *TOCS* 15(3), 1997. Why NAPI exists. |
| `[P-DRIVERS12]` | Kadav, A. & Swift, M., "Understanding Modern Device Drivers", *ASPLOS* 2012. |
| `[P-NOOKS03]` | Swift, Bershad, Levy, "Improving the Reliability of Commodity Operating Systems", *SOSP* 2003. |
| `[P-VIRTIO08]` | Russell, R., "virtio: towards a de-facto standard for virtual I/O devices", *OSR* 42(5), 2008. |
| `[P-ENERGY07]` | Barroso, L. & Hölzle, U., "The Case for Energy-Proportional Computing", *IEEE Computer* 40(12), 2007. Why idle power is the number that matters. |

### Networking

| Tag | Paper |
|---|---|
| `[P-CERF74]` | Cerf, V. & Kahn, R., "A Protocol for Packet Network Intercommunication", *IEEE Trans. Comm.*, 1974. |
| `[P-CLARK88]` | Clark, D., "The Design Philosophy of the DARPA Internet Protocols", *SIGCOMM* 1988. |
| `[P-JACOBSON88]` | Jacobson, V., "Congestion Avoidance and Control", *SIGCOMM* 1988. |
| `[P-KARN87]` | Karn, P. & Partridge, C., "Improving Round-Trip Time Estimates in Reliable Transport Protocols", *SIGCOMM* 1987. |
| `[P-MTCP]` | Clark, D., "Window and Acknowledgement Strategy in TCP", RFC 813, 1982. Silly window syndrome. |

### Virtualization, isolation, security

| Tag | Paper |
|---|---|
| `[P-POPEK74]` | Popek, G. & Goldberg, R., "Formal Requirements for Virtualizable Third Generation Architectures", *CACM* 17(7), 1974. |
| `[P-XEN03]` | Barham et al., "Xen and the Art of Virtualization", *SOSP* 2003. |
| `[P-KVM07]` | Kivity et al., "kvm: the Linux Virtual Machine Monitor", *OLS* 2007. |
| `[P-UKERNEL95]` | Liedtke, J., "On µ-Kernel Construction", *SOSP* 1995. |
| `[P-EXOKERNEL95]` | Engler, Kaashoek, O'Toole, "Exokernel: An Operating System Architecture for Application-Level Resource Management", *SOSP* 1995. |
| `[P-MACH86]` | Accetta et al., "Mach: A New Kernel Foundation for UNIX Development", *USENIX* 1986. |
| `[P-SEL4]` | Klein et al., "seL4: Formal Verification of an OS Kernel", *SOSP* 2009. |
| `[P-LSM02]` | Wright et al., "Linux Security Modules: General Security Support for the Linux Kernel", *USENIX Security* 2002. |
| `[P-SYSTRACE03]` | Provos, N., "Improving Host Security with System Call Policies", *USENIX Security* 2003. Ancestor of seccomp. |
| `[P-CGROUPS07]` | Menage, P., "Adding Generic Process Containers to the Linux Kernel", *OLS* 2007. |
| `[P-MELTDOWN18]` | Lipp et al., "Meltdown: Reading Kernel Memory from User Space", *USENIX Security* 2018. Why KPTI exists. |
| `[P-SPECTRE19]` | Kocher et al., "Spectre Attacks: Exploiting Speculative Execution", *IEEE S&P* 2019. |
| `[P-SMASH96]` | Aleph One, "Smashing the Stack for Fun and Profit", *Phrack* 49, 1996. |
| `[P-TRUST84]` | Thompson, K., "Reflections on Trusting Trust", *CACM* 27(8), 1984. Read before phase 11. |

### Reliability and operating a system you depend on

| Tag | Paper |
|---|---|
| `[P-GRAY85]` | Gray, J., "Why Do Computers Stop and What Can Be Done About It?", Tandem TR 85.7, 1985. The framing for phase 14. |
| `[P-CRASHONLY03]` | Candea, G. & Fox, A., "Crash-Only Software", *HotOS* 2003. |
| `[P-ROC02]` | Patterson et al., "Recovery-Oriented Computing (ROC): Motivation, Definition, Techniques, and Case Studies", UC Berkeley TR, 2002. |
| `[P-E2E84]` | Saltzer, J., Reed, D., Clark, D., "End-to-End Arguments in System Design", *TOCS* 2(4), 1984. Why the checksum belongs at the top. |
| `[P-SSLCCS12]` | Georgiev et al., "The Most Dangerous Code in the World: Validating SSL Certificates in Non-Browser Software", *CCS* 2012. |

### Build, reproducibility, distribution

| Tag | Paper |
|---|---|
| `[P-REPRO]` | Lamb, C. & Zacchiroli, S., "Reproducible Builds: Increasing the Integrity of Software Supply Chains", *IEEE Software* 39(2), 2022. |
| `[P-NIX06]` | Dolstra, E., de Jonge, M., Visser, E., "Nix: A Safe and Policy-Free System for Software Deployment", *LISA* 2004; and Dolstra's thesis, 2006. |
| `[P-DDC]` | Wheeler, D., "Countering Trusting Trust through Diverse Double-Compiling", *ACSAC* 2005. |
