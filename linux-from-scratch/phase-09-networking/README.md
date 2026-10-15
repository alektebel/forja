# Phase 09 — Networking: NIC to TCP to Sockets

**14 exercises.** The first subsystem where the other end of the interface is a
machine you do not control, running software you did not write, that may be
hostile, and that will not wait for you.

---

## The failure that got you here

Your machine is alone. Everything it knows came from its own disk. There is no
way to fetch a package, serve a request, or talk to anything.

And networking breaks an assumption that has held through eight phases: until
now, every input came from a device you programmed or a program you loaded. Now
input arrives unsolicited, at a rate you do not control, from a source that may be
lying about who it is, and *dropping it is a normal, expected outcome* rather than
a failure.

**Every layer you are about to build exists to convert one unreliable thing into
a slightly less unreliable thing.**

---

## Design decisions

> **DESIGN DECISION — copy packets between layers, or pass a shared buffer?**
> Copying at each layer boundary is simple and costs a memcpy per layer per
> packet. A single buffer with headroom, passed by reference and adjusted at each
> layer, is what every real stack does — Linux calls it `sk_buff`, BSD calls it
> `mbuf` — and it requires every layer to agree about ownership.
> **Chosen:** a shared buffer (09.3), because the copying version's cost is
> measurable and because ownership rules are the actual lesson. Cost: a
> use-after-free per layer boundary you get wrong.

> **DESIGN DECISION — interrupt per packet, or polling?**
> An interrupt per packet is correct and, under load, catastrophic: at line rate
> the machine does nothing but take interrupts and never runs the code that
> drains the queue. This is receive livelock `[P-LIVELOCK96]`.
> **Chosen:** interrupt-driven first (09.1), then reproduce livelock deliberately
> (09.12), then implement interrupt mitigation the way NAPI does. You should see
> throughput *fall* as offered load rises before you fix it.

> **DESIGN DECISION — how faithful is your TCP?**
> A TCP that works between two of your own machines on a clean link is a weekend.
> A TCP that interoperates with Linux, under loss, is the phase.
> **Chosen:** interoperability with a real stack is the acceptance criterion for
> every exercise from 09.7 onward. Cost: you cannot fudge anything, because the
> other end implements the RFC and you do not get a vote.

---

## The exercises

### 09.1 — A NIC driver
**Build:** virtio-net (or e1000): receive and transmit rings, buffer replenishment,
interrupt handling, MAC address discovery, and link state.
**Limit case:** the receive ring runs out of buffers. Packets are dropped by the
hardware, silently, and your only evidence is a counter. Replenish eagerly, track
the drop counter, and *print it* — because for the rest of this phase, "the packet
never arrived" will be your most common symptom and this counter is the first
thing to check.
**Done when:** you can receive a raw frame and transmit one, verified with
`tcpdump` on the host side of a QEMU tap.
**Read:** `[VIRTIO]` §5.1 (Network Device); Intel *82540EM Developer's Manual* if
using e1000; `[LDD3]` ch. 17 (Network Drivers); `[OSDEV]` Network Stack.

### 09.2 — Ethernet
**Build:** frame parsing and construction, MAC addressing, EtherType demux,
broadcast handling, and a promiscuous-mode switch.
**Limit case:** you will receive frames not addressed to you (broadcasts, and
everything if promiscuous), frames with a payload below the 46-byte minimum that
were padded, and frames whose EtherType you do not handle. Each must be dropped
cleanly and counted, not passed upward. The padding case matters: an IP packet's
real length comes from the IP header, not the frame length, and trusting the
frame length puts padding bytes into your data.
**Done when:** your stack correctly demuxes ARP and IPv4, ignores everything else,
and handles a padded minimum-size frame without trailing garbage.
**Read:** `[TCPIP1]` ch. 3; IEEE 802.3 framing; `[TCPIP2]` ch. 4 for the
implementation shape.

### 09.3 — A packet buffer
**Build:** an `sk_buff`-equivalent: a data buffer with headroom and tailroom,
push/pull/reserve operations, layer header pointers, refcounts, and cloning.
**Limit case:** transmitting requires prepending TCP, IP and Ethernet headers to
a payload the application gave you. Without headroom that is three copies of the
entire payload. Reserve headroom at allocation and measure the difference. Then:
a broadcast packet delivered to two sockets — one buffer, two consumers, one of
which modifies it. Clone-on-write or copy; decide and enforce.
**Done when:** transmit does zero payload copies from socket to NIC, provably, and
multi-delivery is safe.
**Read:** `[LKD3]` ch. 17 (`sk_buff` layout) — the headroom diagram is the
design; `[TCPIP2]` ch. 2 (mbufs) for the other tradition; `[KDOC]`
`Documentation/networking/skbuff.rst`.

### 09.4 — ARP
**Build:** request/reply, a cache with expiry and states (incomplete, reachable,
stale), queueing packets awaiting resolution, and gratuitous ARP.
**Limit case:** send an IP packet to an unresolved address. The packet has nowhere
to go *yet* — queue it, resolve, then send. Bound that queue, or a burst to an
unreachable address consumes all memory. Then: two replies for one request
(ARP spoofing). ARP has no authentication whatsoever; note precisely what that
means for every trust assumption in the rest of the phase.
**Done when:** you resolve a host's MAC, cache it, expire it, and a resolution
failure drops queued packets rather than hanging.
**Read:** `[RFC 826]`; `[TCPIP1]` ch. 4; `[TCPIP2]` ch. 21.

### 09.5 — IPv4
**Build:** header parsing and construction, checksum, TTL decrement, a routing
table with longest-prefix match, and a default gateway.
**Limit case:** the header checksum must be validated on receive and recomputed on
send — and it is a one's-complement sum with an end-around carry that is easy to
get subtly wrong in a way that works for most packets. Test it against known
vectors. Then: longest-prefix match with overlapping routes, and a packet for
which no route exists (which must produce ICMP, not a silent drop).
**Done when:** you can route packets to a gateway, your checksum matches
`tcpdump`'s validation on every packet, and unroutable packets generate ICMP.
**Read:** `[RFC 791]`; `[RFC 1122]` §3 — the host requirements, which tell you
what you are actually obliged to do; `[TCPIP1]` ch. 5; `[P-CERF74]` and
`[P-CLARK88]` for why it is designed this way.

### 09.6 — Fragmentation and reassembly
**Build:** fragmenting on MTU, and reassembling on receipt with a timer.
**Limit case:** this is where security bugs live. Overlapping fragments (which
overlap should win?), a fragment that never arrives (bounded timeout, then ICMP
Time Exceeded), a reassembled packet larger than 65535 bytes, and a flood of
first-fragments that never complete — an easy memory exhaustion if your table is
unbounded. Handle all four explicitly; each has a CVE history.
**Done when:** large ICMP echoes fragment, reassemble and match, and each of the
four hostile cases is handled and tested.
**Read:** `[RFC 791]` §3.2; `[RFC 1858]` (fragment filtering attacks);
`[TCPIP1]` ch. 5.4; `[TCPIP2]` ch. 10.

### 09.7 — ICMP
**Build:** echo request/reply, destination unreachable, time exceeded, and
fragmentation-needed.
**Limit case:** `ping` your kernel from Linux and `ping` Linux from your kernel.
The first is your receive path and the second is your whole transmit path — and
this is the first exercise where a *real* stack judges your work. Then implement
`traceroute` support (TTL expiry generating Time Exceeded from the right source
address) and run a real `traceroute` through your machine.
**Done when:** `ping` works in both directions with correct sequence numbers and
round-trip times, and `traceroute` sees you.
**Read:** `[RFC 792]`; `[RFC 1122]` §3.2.2 — which ICMP messages you must send and
must not; `[TCPIP1]` ch. 8.

### 09.8 — UDP and the socket API
**Build:** UDP header, checksum with the pseudo-header, port demultiplexing, and
the socket layer: `socket`, `bind`, `sendto`, `recvfrom`, `close`.
**Limit case:** the UDP checksum covers a *pseudo-header* of IP fields that are
not in the UDP packet — a layering violation baked into the protocol in 1980, and
a thing you must simply implement. Then: a receive queue that fills because the
application is slow. UDP's answer is to drop, silently. Implement that, count it,
and note that this is the entire difference between UDP and TCP in one behaviour.
**Done when:** a userspace program on your OS exchanges datagrams with `nc` on
Linux, both directions, checksums valid.
**Read:** `[RFC 768]`; `[RFC 1122]` §4.1; `[UNP]` ch. 8; `[TLPI]` ch. 56–58.

### 09.9 — TCP: connection management
**Build:** the state machine — the eleven states, three-way handshake, four-way
close, sequence-number selection, and the timers.
**Limit case:** `TIME_WAIT`. Two minutes of holding state for a connection that
is closed, which looks like pure waste until you construct the case it prevents:
a delayed duplicate segment from the old connection arriving during a new one on
the same four-tuple. Build that case. Then: simultaneous close, and a
`SYN` to a closed port (which must `RST`). Draw your state machine and check
every transition against RFC 793's diagram — every missing edge is a hang.
**Done when:** your kernel accepts a connection from Linux and initiates one to
Linux, with `tcpdump` showing a textbook handshake and close.
**Read:** `[RFC 793]` and `[RFC 9293]` (the current consolidated spec) — the state
diagram in §3.2 is the exercise; `[TCPIP1]` ch. 13; `[TCPIP2]` ch. 24–30 for a
real implementation, annotated.

### 09.10 — TCP: reliable data transfer
**Build:** send and receive buffers, sequencing, cumulative acknowledgement,
retransmission with RTO, RTT estimation (smoothed RTT + variance), and
out-of-order reassembly.
**Limit case:** Karn's algorithm. When you retransmit a segment and an ack
arrives, you cannot tell which transmission it acknowledges — so sampling RTT
from a retransmitted segment corrupts your estimator, permanently, in the
direction of collapse. `[P-KARN87]` is two pages and this exercise is why it was
written. Then: exponential backoff, and a bound on retries.
**Done when:** a multi-megabyte transfer to Linux completes correctly with 10%
simulated loss (`tc netem` on the host), and your RTT estimate tracks the real
one.
**Read:** `[P-KARN87]`; `[RFC 6298]` (RTO computation); `[TCPIP1]` ch. 14;
`[TCPIP2]` ch. 25.

### 09.11 — TCP: flow control and congestion control
**Build:** the receive window and window updates, then slow start, congestion
avoidance, fast retransmit and fast recovery.
**Limit case:** two of them. **Silly window syndrome** — a receiver advertising
tiny windows and a sender filling them, degrading to one byte per segment plus
40 bytes of header; the fix is on both sides. And **congestion collapse**: remove
your congestion control, run several flows over a bottleneck link, and measure
aggregate throughput falling as offered load rises. That measurement is the 1986
internet collapse in miniature, and `[P-JACOBSON88]` is the response to it.
**Done when:** throughput over a lossy bottleneck is stable and fair between
flows, and you have the with/without-congestion-control graph.
**Read:** `[P-JACOBSON88]` — read it properly, it is the most important paper in
this phase; `[RFC 5681]`; `[RFC 813]` for silly window; `[TCPIP1]` ch. 16.

### 09.12 — Receive livelock, and NAPI
**Build:** interrupt mitigation — on the first packet, disable the device's
interrupt and poll the ring until empty (with a budget), then re-enable.
**Limit case:** first *cause* the livelock: flood your machine at line rate and
plot throughput against offered load. It rises, peaks, and collapses toward zero
while the CPU is at 100% — the machine is taking interrupts and never running the
code that consumes packets. Then add polling and re-plot. Two curves on one graph
is the deliverable.
**Done when:** throughput saturates rather than collapsing under overload, with
both curves measured.
**Read:** `[P-LIVELOCK96]` in full — this exercise is the paper; `[LDD3]` ch. 17
on NAPI; `[KDOC]` `Documentation/networking/napi.rst`.

### 09.13 — Multiplexing: `select`, `poll`, `epoll`
**Build:** all three, with wait-queue integration so a socket becoming readable
wakes exactly the right waiters.
**Limit case:** the scaling difference is the lesson. `select` and `poll` are O(n)
per call — the application passes all n descriptors every time. Measure them at
n = 10, 100, 1000, 10000 and plot. Then `epoll`, which keeps the interest set in
the kernel and is O(active). Then implement edge-triggered mode and reproduce its
classic bug: a partial read leaves data unread and no further event ever arrives.
**Done when:** you have the three-way scaling plot, and both level- and
edge-triggered modes behave per spec.
**Read:** `[TLPI]` ch. 63 in full — it builds this comparison; `[UNP]` ch. 6;
Kegel's "The C10K problem" **(free)**; `[KDOC]` `Documentation/filesystems/epoll.rst`.

### 09.14 — A server, and the numbers
**Build:** a real application on your OS — an HTTP server serving files from your
filesystem — then benchmark it from a real client.
**Limit case:** point a real load generator (`wrk`, `ab`) at it and find the
bottleneck. It will not be where you guessed. Measure: connections/sec, latency
percentiles (p50/p99 — the tail is the interesting one), throughput, and where the
CPU goes. Then compare against nginx serving the same files on Linux on the same
virtual hardware, and account for the gap mechanism by mechanism.
**Done when:** a browser on your host loads a page served by your OS, and you have
the comparison table with an explanation per row.
**Read:** `[http-server/](../../http-server/)` in this repo; `[UNP]` ch. 30
(server design alternatives); `[deploy-and-debug/](../../deploy-and-debug/)` for
how to read the percentiles you are about to produce.

---

## Where this phase stops

- **No IPv6.** The addressing and neighbour discovery differ; the transport layer
  above is the same. `[RFC 8200]` and `[TCPIP1]` ch. 5.
- **No TCP options beyond the basics.** No SACK, no window scaling, no timestamps
  — which caps your throughput on any high-bandwidth-delay path. `[RFC 7323]`,
  `[RFC 2018]`.
- **No modern congestion control.** You implement Reno. CUBIC and BBR are the
  current reality and a good follow-on read.
- **No TLS.** [cryptographic-library/](../../cryptographic-library/) has the
  primitives; the protocol is another project.
- **No netfilter, NAT, or bridging.** [firewall-from-scratch/](../../firewall-from-scratch/)
  in this repo covers filtering.
- **No zero-copy, no offloads.** No TSO/GSO/GRO, no `sendfile`, no checksum
  offload. Each is worth measuring if you continue.
- **No DNS resolver in the kernel** (correctly — it belongs in userspace; see
  [dns-server/](../../dns-server/)).

---

Tags in **Read** lines resolve in [REFERENCES.md](../REFERENCES.md). Checklist: [PROGRESS.md](../PROGRESS.md). Frame and both tracks: [README.md](../README.md).
