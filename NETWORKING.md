# Networking — three C/C++ project lists, and where this repository stands

A list of C/C++ networking projects arrived from the user, kept here **verbatim**
because it is the requirement and not a summary of it: three tutorial series that
build a TCP/IP stack, four kinds of concurrent server, and an MQTT broker, each
linked part by part.

The repository's rule for a list like this — the same rule `AGENT-INFRA.md` keeps
for the twelve-item Agent Infra list and `AI-ENGINEER.md` for the interview and
build lists — is: **the list stays as written, the analysis around it is English,
and a gap is stated as work or not stated at all.** "Covered" below means *a stage
builds the mechanism and a check catches the mistake*, not that a course mentions
it.

Phase **L** of `codecraft/ROADMAP.md`; `path.py` carries L1, L2 and L3 as
`ready`.

---

## 1. The list (verbatim)

### List of C/C++ Project Ideas in Networking Programming

**1. Let's Code a TCP/IP Stack**

- Part 1: Ethernet & ARP — saminiir.com/lets-code-tcp-…
- Part 2: IPv4 & ICMPv4 — saminiir.com/lets-code-tcp-…
- Part 3: TCP Basics & Handshake — saminiir.com/lets-code-tcp-…
- Part 4: TCP Data Flow & Socket API — saminiir.com/lets-code-tcp-…
- Part 5: TCP Retransmission — saminiir.com/lets-code-tcp-…

**2. Programming concurrent servers**

- Part 1 - Introduction — eli.thegreenplace.net/2017/concurren…
- Part 2 - Threads — eli.thegreenplace.net/2017/concurren…
- Part 3 - Event-driven — eli.thegreenplace.net/2017/concurren…
- Part 4 - libuv — eli.thegreenplace.net/2017/concurren…
- Part 5 - Redis case study — eli.thegreenplace.net/2017/concurren…
- Part 6 - Callbacks, Promises and async/await — eli.thegreenplace.net/2018/concurren…

**3. MQTT Broker from scratch**

- Part 1 - The protocol — codepr.github.io/posts/sol-mqtt…
- Part 2 - Networking — codepr.github.io/posts/sol-mqtt…
- Part 3 - Server — codepr.github.io/posts/sol-mqtt…
- Part 4 - Data structures — codepr.github.io/posts/sol-mqtt…
- Part 5 - Topic abstraction — codepr.github.io/posts/sol-mqtt…
- Part 6 - Handlers — codepr.github.io/posts/sol-mqtt…
- Bonus - Multithreading — codepr.github.io/posts/sol-mqtt…

The links arrived elided. The three series are saminiir's *Let's code a TCP/IP
stack* (entry point `https://www.saminiir.com/lets-code-tcp-ip-stack-1-ethernet-arp`),
Eli Bendersky's *Programming concurrent servers* (`eli.thegreenplace.net`,
2017–2018) and codepr's *MQTT broker from scratch* (entry point
`https://codepr.github.io/posts/sol-mqtt-broker`, with the broker itself at
`https://github.com/codepr/sol`). Only the two entry points above were verified
here; the rest of the slugs were not resolved.

---

## 2. What is already here, and what each series adds

| The series | Already in the repo | What is genuinely missing |
|---|---|---|
| **A TCP/IP stack** | `communication-protocols` (legacy C, phase G6) designs a protocol over real sockets; `http-server` and `dns-server` (legacy C) write application protocols on top of one; `interconnects-from-scratch` (I9) models the *shape* of a collective's traffic and what it costs; `cpu-from-scratch` (G3) is the house's example of a **provided simulator** a course is written against | The stack itself: a frame, a header, a checksum, a routing table, a sequence number, a window and a retransmission timer, with a lossy link the check controls. Nothing here parses a wire format byte by byte, and nothing here has a *wire* as the record of what happened. |
| **Concurrent servers** | `queue-and-workers-from-scratch` (J1) builds the queueing half as data — admission, leases, backoff, dead letters, all on an injected clock — and says out loud that threads are not the subject; `orchestration-from-scratch` (J2) and `durable-execution-from-scratch` (J3) run concurrent-looking work deterministically | The four *models* and their trade-offs: blocking, thread-per-connection, an event-driven reactor, and the callback/future/async layer that libuv and every modern runtime hide. The Redis case study is the one place where the model meets a real command loop. |
| **An MQTT broker** | The same legacy C slots; `interconnects-from-scratch` for a broker's fan-out measured rather than asserted | A broker's own subject: the fixed header and its variable-length integer, a topic trie with `+` and `#`, QoS 1 and 2 as *state* (packet ids, redelivery, the four-way handshake), retained messages, the last will, and a session that survives a reconnect. |

Two things the repo does **not** have and this list does not ask for: a *socket*,
and a *thread*. Both are banned by the authoring rules — the audit refuses
`threading`, `socket`, `asyncio`, `os`, `time` and any float literal in a stage —
so each course below is written the way J1/J3/J4 are: **the link, the clock and
the failure are data**, and the checks drive them. That is also what makes the
interesting question answerable: a stack that is a pure function of its frames
can be asked *exactly* which segment was retransmitted, and a benchmark can
report a scheduler-step count instead of a wall clock.

---

## 3. The three gaps — phase L (three courses)

All three are authorable in the house style: a provided simulator, ten graded
stages, a check per stage, and at least thirty-four planted mutations behind
every check.

All three are built now (`path.py` carries L1, L2 and L3 as `ready`); the chains
below are the plans the courses were written against, and each course's own
`README.md` carries what shipped and where it differs.

| Slot | Course to author | The mechanism | After |
|---|---|---|---|
| L1 | `tcp-ip-from-scratch` | The stack as data, against a provided `wire.py` that delivers frames in order, loses them, duplicates them or reorders them on command, and a `hosts.py` of peers, a router and a name table. Chain: 1 the Ethernet frame and its type field → 2 ARP and the cache that ages out → 3 IPv4, the routing table and the TTL that must be decremented rather than ignored → 4 ICMP echo and the checksum that has to be recomputed over the header → 5 the handshake as a state machine (SYN, SYN-ACK, ACK, and where the sequence number comes from) → 6 the data flow and the window that must not be overrun, with cumulative acknowledgements → 7 the socket API as a table (`listen`/`accept`/`read`/`write` over a modelled connection) → 8 retransmission on the injected clock (one timer, a doubling backoff, and a segment the link drops exactly once) → 9 the close (FIN, half-open, and `TIME_WAIT` as a state and not a sleep) → 10 a session: two hosts, a lossy link, a request and a response, with the **wire's own segment log as the tie-breaker** — the audit answers what was sent, what was resent and what was never acknowledged | G3, J4 |
| L2 | `concurrent-servers-from-scratch` | Four models for one server, over a provided in-memory `link.py` (a queue with readiness) on J1's `fleet.py` and the injected clock. Chain: 1 a server as a state machine (accept, read, write, close as data) → 2 the blocking server, and the one slow client that stops everyone → 3 thread-per-connection over J1's scheduler, with the interleaving the *check* chooses → 4 the reactor: readiness as a set, a poll loop that never busy-waits → 5 the event loop and its timers (a monotonic queue on the clock) → 6 callbacks as data (a handle table, cancellation, and a callback that must not run for a closed connection) → 7 futures and `async`/`await` as a desugaring — a coroutine is a step function and a loop that drives it → 8 backpressure: a bounded outbox, the write that must be deferred, and head-of-line blocking made visible → 9 the Redis case study as a command loop with per-connection state → 10 one workload through all four models, with **identical answers and a counted number of scheduler steps** as the only honest way to compare them | J1, J3 |
| L3 | `mqtt-broker-from-scratch` | The wire format itself, against a provided byte-pipe transport (`streams.py`: named streams, a `CHUNK` a step, `send` that returns what it took, a log `stats()` recomputes from, and a `cut` that counts what it lost) and a provided policy table (`grants.py`) whose six reasons and decision line are the vocabulary a refusal arrives in. Chain: 1 the fixed header and the variable-length integer → 2 CONNECT/CONNACK and the session flags → 3 SUBSCRIBE/SUBACK and the topic trie (`+` and `#` matched by *components*, never by prefix string) → 4 PUBLISH and delivery to every matching subscriber → 5 QoS 1 as state: the packet id, the PUBACK and the redelivery deadline → 6 QoS 2 as a four-way handshake, and why an id may not be reused before PUBCOMP → 7 retained messages and the last will → 8 a session that survives a reconnect (queued messages and the clean-session flag) → 9 the broker loop: five clients, one event loop, the wire's byte log as the tie-breaker → 10 a publish/ack trace replayed twice, **byte-identical**, with every frame the broker wrote accepted by the course's own reader — the writer and the reader are inverses, or the test is a lie | L1, J4 |

What has **no slot**: the blog posts themselves (this file keeps the links and the
reasoning), the C implementations (the house writes Python; the C versions are
what the legacy `communication-protocols`/`http-server`/`dns-server` slots are
for), and the MQTT *client* — a client is the broker's protocol seen from the
other side, so it is the other end of L3's own wire rather than a course: the
provided transport carries the client's bytes and the course's reader never has to
guess which end wrote them.
