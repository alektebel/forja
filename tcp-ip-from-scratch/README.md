# TCP/IP From Scratch

Build the stack that runs on a link you did not write. `wire.py` is provided
complete: a `Wire(rules)` that carries `bytes` from one MAC to another, one tick
of latency to cross, exactly one delivery per frame except when a rule says
otherwise — `loss` names the send ordinals that never arrive, `duplicate` the
ones that arrive twice, `delay` the ones that arrive late, and `order` decides
whether the frames handed over at a tick keep the order they were sent
(`in_order`, the default, holds a frame sent later behind a delayed earlier one;
`swapped` exchanges the first two of the due prefix and nothing else) — and a
full event log (`send`, `drop`, `hold`, `duplicate`, `deliver`) that every stage
is graded against. `hosts.py` is provided complete: four `Host`s and a `Router`
on the same link, each `Host` a name, an address, a MAC and a box of frames
addressed to it or to everybody, the `Router` a set of named ports each answering
to its own MAC and to `BROADCAST_MAC`, a `Clock`, and the name table (`router`,
`web`, `dns`, `db`, `client`) with the resolution the checks use.

What is *not* here is the stack. A network stack is what you write after the link
loses the frame you assumed arrived: a frame is a type field and nothing more, so
a peer has to be asked for an address before it can be addressed; an address that
never ages is an address that lies; a datagram with no hop limit circulates
forever; an error with no message is an error nobody learns about; a connection
whose state machine is not a state machine answers segments it never agreed to; a
window with no cumulative acknowledgement loses data the sender believed was
sent; an API whose calls are not a table cannot answer a call it does not have; a
timer that does not double floods the link it is trying to help; a connection
that never closes holds a socket the other side has already released; and a
session is the only thing that ever proves any of it. This is the repository's
second principle — *MVP first, then complicate, driven by limit cases* — applied
to a network, and it is the same ladder the salvaged curriculum in
`linux-from-scratch/` is built on; that directory is 176 exercises on real
hardware and cannot ship a checker, and this course is the checker its README
asks for, on a link small enough to grade.

Every one of the failures below is a check here, and every one of them is a
mistake that leaves the stage's own output unchanged and is only visible through
the wire:

- the padding a builder added counted as payload, so a frame the wire carried as
  60 bytes describes 28 of them as if it had carried 60;
- an ARP entry that has aged out but is still returned by `lookup`, so the stack
  addresses a peer that moved;
- the checksum field not zeroed while the header's checksum is summed, so the sum
  counts the value it is about to write;
- a checksum that does not check out returned as an exception instead of as a
  verdict, so the stack dies on a hostile packet;
- a duplicate `SYN` resetting a connection that is already established;
- an acknowledgement that covers the last segment received rather than the
  contiguous run behind it, so the sender discards bytes it was told arrived;
- a descriptor reused while it is still in use, so one socket's data lands in
  another's;
- a retransmission timeout that never doubles, so the retransmissions are evenly
  spaced and the tick arithmetic that relies on the backoff is wrong;
- a `TIME_WAIT` deadline measured from the connection's creation instead of the
  tick the state was entered;
- a ledger that stops counting at the last retransmission, so `cross_check`
  passes because both sides stopped at the same place.

Nothing here runs on a thread, a wall clock or a `random`: the wire is this
course's clock, every fixture is deterministic, and time passes only when a
caller calls `Wire.advance` or hands a stage a `now`. Where a decision was a
judgement call it is written down in the template's own docstring as a DESIGN
DECISION, and the check asserts the consequence.

## The provided world

| Module | What it is |
|---|---|
| `wire.py` | The link: `Wire(rules)` with `tick`/`advance`, `send` (returns the 1-based send ordinal), `deliver` (a read: the frames handed over at the current tick, in order), `pending`, `log`/`events`/`sent`/`dropped`/`delivered`, `rules`/`order`/`losses`/`duplicates`, `reset`, and `mac_text`, the one address parser; `ORDER_IN_ORDER`/`ORDER_SWAPPED`/`ORDERS`, `BROADCAST_MAC`, `WireError` |
| `hosts.py` | The peers: `Host` (`name`, `ip`, `mac`, `wire`, `clock`, `send`, `sent`, `inbox`, `recv`, `tick`), `Router` (`ports`, `mac`, `send`, `recv`, `sent`), `Clock` (`now`, `advance`, `advanced`), the name table `NAMES`/`MACS` (`router`, `web`, `dns`, `db`, `client`) with `mac_of` and `ip_of`, and `HostsError`; `mac_text` and `BROADCAST_MAC` are re-exported from `wire` |

The wire carries bytes and never parses them, so **the frame, the ARP message,
the IPv4 header, the ICMP message and the TCP segment are the course's own**,
frozen before stage 1 and agreed byte for byte by every stage that reads or
writes one; network order is big-endian everywhere and every field's width is
pinned. A rule list the wire cannot honour — an unknown order, a loss ordinal
below 1, a negative delay, a non-int — raises from the constructor, and `rules()`
hands back what it accepted. A `Router` port answers to its own MAC and to
`BROADCAST_MAC`, exactly like a host: a frame addressed to somebody else is not
the port's. The wire's log, `pending()` and a host's box are the records the
stack's own ledger is checked against; a stage never trusts the caller's count of
what it did, and the capstone compares both against each other.

## The stages

| # | File | The stage | The mechanism |
|---|---|---|---|
| 1 | `stage_01.py` | The frame, and the type field that says what is inside | `ETHERNET_HEADER`, `MIN_FRAME`, `TYPES`, `mac_bytes`, `build`, `parse`, `type_name`, `type_number`, `is_broadcast`, `describe` |
| 2 | `stage_02.py` | ARP, and the address that ages out | `ARP_LENGTH`, `ARP_REQUEST`, `ARP_REPLY`, `CACHE_TICKS`, `build_message`, `parse_message`, `request`, `reply_to`, `Cache` |
| 3 | `stage_03.py` | IPv4, and the hop that was one too many | `IPV4_HEADER`, `IPV4_VERSION`, `DEFAULT_TTL`, `MAX_TTL`, `IDENT_MAX`, `PROTOCOLS`, `parse_ip`, `ip_text`, `mask_of`, `network_of`, `checksum`, `checksum_ok`, `pack_header`, `unpack_header`, `build`, `route`, `forward` |
| 4 | `stage_04.py` | ICMP, and the checksum over the whole message | `ICMP_HEADER`, `ERROR_QUOTE`, `ICMP_TYPES`, `build`, `parse`, `echo_reply`, `error_message`, `answer`, `ping` |
| 5 | `stage_05.py` | The handshake, and the state machine that has to know where it is | `TCP_HEADER`, `TCP_OFFSET`, `SEQ_MAX`, `SEQ_HALF`, `WINDOW_MAX`, the flag bits, `STATES`, `WELL_KNOWN`, `flags_text`, `pack`, `unpack`, `seq_add`, `seq_before`, `initial_seq`, `Connection` |
| 6 | `stage_06.py` | The window, and the acknowledgement that covers everything behind it | `MSS`, `Receiver` (`accept`, `window`, `buffered`, `delivered`, `log`), `Sender` (`queue`, `next_segments`, `acknowledge`, `in_flight`, `sent`, `log`) |
| 7 | `stage_07.py` | The socket API, as a table of calls | `CALLS`, `ERRNOS`, `arity`, `call_name`, `Sockets` (`call`, `state`, `fds`, `log`) |
| 8 | `stage_08.py` | The retransmission, and the timer that doubles | `INITIAL_TIMEOUT`, `MAX_TIMEOUT`, `MAX_TRIES`, `BACKOFF`, `Timer`, `Reliable`, `run` |
| 9 | `stage_09.py` | The close, and the state you wait in | `TIME_WAIT_TICKS`, `CLOSE_STATES`, `close`, `step_close`, `half_open`, `time_wait_over` |
| 10 | `stage_10.py` | The session, and the wire's own log as the tie-breaker | `SESSION_KEYS`, `plan`, `open_session`, `run`, `report`, `cross_check` |

The stages are cumulative in the only direction that matters: a stage imports the
world and the earlier stages it needs, and nothing from a later one. Stages 2, 3
and 5 import stage 1 and the world only; stage 4 imports stage 3; stage 6 imports
stage 5; stages 7, 8 and 9 import stages 5 and 6; stage 10 composes stages 1, 2,
3, 4, 5, 6, 7, 8 and 9. That is what lets the first three slices be built at once
— and why the last two need the middle of the course to exist before their checks
can run.

## How to use this directory

```bash
python3 codecraft/cli.py run tcp-ip-from-scratch      # what to build next, and why
python3 codecraft/cli.py stage tcp-ip-from-scratch 3  # one stage: the file, what you write, what the tester costs
```

Or without codecraft: the templates are ordinary modules, and an unimplemented
one raises `NotImplementedError`. Implement them at the top level; finished
versions are in `solutions/`, and nothing beyond `solutions/` ships a solution or
a hint in this directory. The templates fail and the solutions pass, and that is
the whole grading loop — this course is checker-driven and there is no test
framework anywhere. The ten checks are assembled into `course.py`, and every one
of them is a module-level `def check():` of bare
`assert <condition>, "<message>"` statements, where the message names the mistake
rather than the symptom; an untouched template reports as not implemented yet
rather than failing for the wrong reason, because the check lets
`NotImplementedError` escape before any broad `except` catches it.

One fact about the world that the stages are written around: **the peers are
passive.** A `Host` keeps a box of the frames addressed to it and hands them
back when asked; nothing in `hosts.py` ever answers anything. A stage that
performs an exchange (`request` in stage 2, `ping` in stage 4) therefore *sends
and reads*, and the caller is the peer — a check proves the answered path by
putting the reply on the wire itself, and the capstone scripts both sides of its
session for the same reason. That is what makes every stage a function of what
the link did rather than a process that runs.

Every check is mutation-tested: at least 34 plausible wrong implementations per
stage, each a minimal edit to the solution — a type field read as little-endian,
an ARP entry that never expires, a checksum field not zeroed while summing, a TTL
checked after it was already decremented, a reply built for a message that was
already a reply, a state left alone when a segment was rejected, a window
reported in segments where its unit is bytes, a descriptor reused while it is
still in use, a timeout not capped at `MAX_TIMEOUT`, a `TIME_WAIT` deadline
compared against the wrong tick, a ledger counted from the stack's beliefs
instead of the wire's log — are each planted into the solutions, and the stage's
check must fail. A mutant that hangs its check counts as caught, because a wrong
implementation that never terminates anything is not a passing implementation.
The audit reads each template and its solution and refuses them unless the first
docstring paragraph is exactly `TCP/IP From Scratch — stage NN: <title>`, the
template carries 3–6 `DESIGN DECISION — ` blocks and a `TODO: implement` line,
the solution declares every public name the template declares, and neither
imports a banned module (a clock, a thread, a `random`, a socket, an `os`) or
contains a float literal.

## Prerequisites

Standard library only. `wire.py`, `hosts.py` and the ten stages import nothing but
each other — no numpy, no binary dependency, no network, no threads. There is no
clock and there is no randomness: `time`, `threading` and `asyncio` are banned
because the wire is this course's clock, `random` because every fixture is
deterministic, and `os`, `socket`, `subprocess`, `secrets`, `shutil`, `tempfile`,
`pathlib` and `uuid` are imports no stage may make either; time passes only
through `Wire.advance` and the `now` a stage is handed, and a stage that read a
clock would be a different function each run. There are no floats anywhere — not
in a template, not in a solution, not in a check — and `math`, `statistics`,
`decimal` and `fractions` are banned too, because the two things this course
decides by hand are the one's-complement sum and how a window that moved by three
segments is spelled, and both of them are integers: every port, sequence number,
acknowledgement, tick, window, length, checksum and address is an `int`. Bytes
are built by hand with `int.to_bytes(…, "big")` and `int.from_bytes(…, "big")`,
never `struct`, so the packing is visible in the source.

You should be comfortable with integer masking and bit fields, with records as
tuples and dicts, with `try`/`except`, and with reading a failure line and
knowing whether it is the caller's mistake or a decision the stack made. The
arithmetic is written out by hand, on purpose.

## Design decisions

- **A mismatch of shape raises, a verdict about content is returned.** Anything
  that cannot be the thing at all — a frame shorter than its header, an unknown
  type or protocol number, a payload longer than the wire allows, a call with the
  wrong arity, a segment whose flag combination this state cannot have — raises,
  naming the offender. Anything that is the stack's own decision about a peer —
  a checksum that does not check out, a segment outside the window, a duplicate
  acknowledgement, a destination with no route, a sequence number behind the one
  already acknowledged — is returned as data, because a receiver's whole job is
  to decide, and a decision that arrives as an exception cannot be reported to
  anybody. `unpack_header` is the clearest case: a header too short to be a
  header raises, a header whose checksum is wrong comes back with
  `"checksum_ok": False`, and the caller drops it.
- **Every refusal names the offender, and nothing is looked up by a name a
  reader might misspell.** There is no suggestion machinery in this course: the
  name table is a fixture the checks resolve against, and a suggestion nobody can
  reach is a rule nobody can test. A refusal about a name says which name; a
  refusal about a type says which number.
- **The wire is the tie-breaker.** Every stage keeps a log of what it did and the
  capstone's `cross_check` compares it against the world's own record —
  `Wire.sent()`, `Wire.dropped()`, `Wire.delivered()`, the deliveries' ordinals,
  and the peer's `recv()` — key by key, returning the disagreements rather than
  hiding them. A ledger counted from the stack's beliefs agrees with itself by
  construction, which is exactly the comparison worth nothing.
- **The formats are frozen because a format decided twice is a format that
  disagrees once.** The frame, the ARP message, the IPv4 header, the ICMP message
  and the TCP segment are pinned width by width before stage 1, so ten stages and
  their checks can compare each other's bytes and the wire's; the addresses are
  text on the outside of a stage and four bytes inside a header, and nothing in
  between is ever anything else.
- **The padding a real NIC adds is the next layer's problem.** A builder pads a
  short frame out to `MIN_FRAME` and a parser hands the payload back exactly as
  it got it, because every next layer has a length field — which is the first
  real decision of the course and the reason a padded frame describes fewer bytes
  than the wire carried.
- **Time is a counter, and a wait is a state, not a sleep.** A retransmission is
  a timer a check advances by hand, `TIME_WAIT` is a state with a deadline and a
  question rather than a timer, and a session ends because the fixtures end.
  Nothing in this course loops forever, sleeps, polls or times out.

## Where this stops

Deliberately left out, so you know the boundary:

- **No real NIC, no real sockets, no real timing.** The wire is a list of frames
  with a tick each, and every network here is the five named peers and a router
  with ports; a stage takes the bytes it was handed and returns what it decided,
  rather than being a process that runs.
- **No UDP.** `PROTOCOLS` names it nowhere this course builds (`icmp` and `tcp`
  only), and the transport half of the course is TCP end to end. UDP is a real
  protocol with its own datagram semantics and no connection at all, and a reader
  should know they are getting the connection-oriented half without it.
- **No IPv6.** Addresses are four octets and the header is the fixed 20 bytes of
  IPv4; the 128-bit address, the extension-header chain and the different
  checksum rules are a second format this course does not build.
- **No IP options and no fragmentation.** The header's IHL is fixed at 5 and its
  flags/fragment field is zero, because a datagram here is never split and
  reassembled; fragmentation is a real mechanism a host owes the links below it,
  and reassembly is where a stack's memory bounds are actually tested.
- **No TCP options, no window scaling, no selective acknowledgement.** The data
  offset is fixed at `TCP_OFFSET = 5`, so the window field is 16 bits and an
  acknowledgement is always cumulative; a real stack negotiates a scaled window,
  and SACK is what a modern sender uses to avoid retransmitting what already
  arrived — both are extensions this course names and does not implement.
- **No congestion control.** Nothing here changes the rate it sends at in
  response to a loss; the retransmission timer doubles, and that is the only
  feedback the sender has. Slow start, congestion avoidance and the whole
  question of what to do with a dropped packet in the middle are a real stack's
  largest piece and are not in this one.
- **No DNS.** The name table is a fixture, not a service — a resolver is a
  subject the repository keeps for the `dns-server` legacy slot — and `hosts.py`
  exists so a stage can be asked to turn a name into an address without one.
- **No clocks, no threads, no blocking.** A stage that read a clock would decide
  differently twice; there is no socket, no thread, no signal, and a call that
  has nothing to hand back answers `EAGAIN` rather than blocking, because
  blocking is a scheduler's business and this course has no scheduler.

## Where this sits

This is the first slot in the repository's L phase, *Programs that talk*, and it
comes after G3 `cpu-from-scratch` and J4 `os-from-scratch` — whose ledger
discipline it inherits: every stage keeps a log and every log is checked against
the world's record. Before it a wire is a thing the repository has never built;
after it, a wire is a thing built from the type field up, and the phase-09
courses that put *real* sockets on a real network can say what they stand on. The
salvaged `linux-from-scratch/` curriculum is the other half of the unit: 176
exercises on real hardware whose own README says it cannot ship a checker and
asks you to write one as you finish each phase. This course is that checker, on a
link small enough to grade.
