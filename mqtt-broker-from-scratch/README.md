# MQTT Broker From Scratch

Build a broker whose every frame its own reader takes back. `streams.py` is
provided complete: a `Transport(rules)` that carries bytes on named streams one
`CHUNK = 16` at a time, whose `step()` is the only thing that moves a byte or a
tick, whose `send`/`answer` return *how many bytes they took* so the tail stays
the caller's to keep, whose `close` refuses while a byte is still in flight,
whose `cut` never refuses and counts what it lost, and whose `stats()` recomputes
every number it reports from its own log. `grants.py` is provided complete as
well: a `Grants(table, ceiling)` — topics per client, a ceiling no grant can ever
widen — a closed vocabulary of six reasons, and `line(decision)`, the decision
written before the act it allows.

The thesis of the whole course is one sentence: **a broker is a reader that never
guesses and a writer that never improvises — every byte it accepts is a frame the
format allows, and every byte it sends is one its own reader takes back.** Each
stage exists because the one before it left a hole: a packet's own length is
written in a variable-width integer, so nothing can be read before that field is;
a flags nibble decides whether four of the packet types are even legal, so it is
refused rather than ignored; a two-byte string with a length in front of it is the
only way a topic, a client id or a will ever arrives; a subscription is a filter
matched *by components*, so a trie is the data structure rather than a string
prefix; a QoS is a promise, so the id a message is waited on must outlive the
sending, and a QoS 2 id may not be reused until PUBCOMP arrives; a session is
something a socket does not have, so the queue, the keep-alive and the will belong
to the client rather than to the connection; and a policy decision has to be
written down before the act, because a denial nobody can read is not a denial.

What is *not* here is the broker. Between the format and the capstone are the
mechanics every real one has: the fixed header read once and handed down, the
variable-length integer that says how long the rest of the packet is, CONNECT and
the four session flags, the topic trie with `+` and `#`, SUBSCRIBE and the QoS
actually granted, PUBLISH routed to real subscribers and retained for the next
one, QoS 1 as state on the injected clock, QoS 2 as a four-way handshake, a
session that outlives the socket, and a capstone that runs one scenario twice,
re-reads its own trace with the course's own reader, and holds its report against
the transport's log key by key. This is the repository's second principle — *MVP
first, then complicate, driven by limit cases* — applied to a wire protocol, and
the ladder is the one L1's stack sits on: there, a wire that loses frames; here, a
transport that loses nothing and a format that can still refuse you.

The world is refused the two things that would make the answer unfalsifiable.
There is no wall clock: `time`, `threading` and `asyncio` are banned, and a
deadline is `k + k//2` ticks of a clock the caller moves, so "the message was
re-sent" is a count rather than a duration. There is no randomness: a transport is
a function of its rules and the number of times it was stepped, so two runs of one
scenario are one run.

Every one of the failures below is a check here, and every one of them leaves the
stage's own output unchanged and is only visible through the transport's log:

- the continuation bit folded into the number it continues, so a two-byte length
  reads as one and the packet's body starts in the wrong place;
- a fifth continuation group accepted, so an integer that cannot fit is read
  anyway and the refusal that names the maximum never happens;
- a truncated packet reported as malformed instead of incomplete, so a caller
  cannot tell *wait for more bytes* from *this will never parse*;
- the reserved nibbles of SUBSCRIBE, UNSUBSCRIBE and PUBREL ignored, so a frame
  the format forbids is answered as if it were legal;
- a string's length read as signed, so a length with its high bit set becomes
  negative and the topic's bytes are taken from the wrong end;
- CONNECT's flags byte read as a number instead of a set of bits, so a clean
  start and a will are confused and a session outlives nothing;
- the will kept when the connection ended cleanly, so a client that said goodbye
  still speaks from the grave;
- a topic filter matched by string prefix, so `a/+` matches `a/b/c` and `a/#`
  matches `ab`;
- `#` bound anywhere but the last level, so `a/#/b` is accepted as a filter;
- a leading wildcard matching a `$`-topic, so a subscriber to `#` receives the
  broker's own topics;
- one client counted once per matching filter, so a client subscribed to both
  `a/b` and `a/+` is handed the same message twice;
- the granted QoS taken from the broker's maximum instead of the request, so a
  subscriber that asked for QoS 0 is sent a handshake it cannot answer;
- a PUBLISH's QoS read from the body instead of the header nibble, so the id
  that must follow the topic is not read at all;
- the retained message delivered as if it were live — or the live one as if it
  were retained — so the flag a subscriber acts on describes the wrong act;
- an id taken before the refusal that spends nothing, so a refused write leaks an
  id and the space runs out for reasons nobody can see;
- a record re-sent without the DUP bit, so the receiver cannot tell a repeat from
  a new message;
- the deadline measured from the wrong tick, so a re-send happens twice on one
  tick or never;
- a QoS 2 id released at PUBREC instead of PUBCOMP, so a duplicate PUBLISH
  arriving afterwards is delivered a second time;
- a PUBREL re-sent with DUP, so a frame the format forbids leaves the broker;
- the session's queue kept as a second copy of the message, so `pending` counts
  something other than what was dropped;
- a keep-alive expiry checked against a wall clock rather than the caller's tick,
  so the answer depends on the machine;
- a clean start that keeps the subscriptions, so a session that asked to start
  over resumes instead;
- a grant's denial answered with a generic error instead of the reason the
  vocabulary already has, so the line written before the act cannot be read;
- the ceiling widened by a client's own grant, so the broker's own limit is
  something a table can raise;
- the report counted from the broker's beliefs rather than from the trace, so a
  broker that thinks it answered while the transport carried less is graded as
  correct;
- `cross_check` returning no disagreements because it compared nothing, which is
  the comparison worth nothing dressed as the comparison worth everything.

Nothing here runs on a thread, a wall clock or a `random`. Where a decision was a
judgement call it is written down in the template's own docstring as a DESIGN
DECISION, and the check asserts the consequence.

## The provided world

| Module | What it is |
|---|---|
| `streams.py` | The transport and its streams: `Transport(rules)` with `tick`, `step`, `steps`, `listen`, `listeners`, `connect`, `streams`, `open_streams`, `stream`, `send`, `to_server`, `answer`, `to_client`, `waiting`, `waiting_at`, `close`, `cut`, `log`, `events`, `stats`, `rules`, `reset`; `Stream` with `id`, `client`, `server`, `state`; `CHUNK = 16`, `BACKLOG = 4`, `OPEN`, `CLOSED`, `CUT`, `EVENTS`, `StreamsError` |
| `grants.py` | The policy, complete: `Grants(table, ceiling)` with `client`, `ceiling`, `clients`; `line(decision)`, the decision rendered as the world's own line; `ACTIONS`, `ALLOWED`, `REASONS` (six of them), `DECISION_KEYS`, `GrantsError` |

The transport carries bytes and never looks inside them, so **the format is the
course's own work**: a packet is a fixed header — a type nibble, a flags nibble
and a variable-length integer saying how long the rest is — followed by a body
whose shape the type decides. The transport is the record every claim is checked
against and it is never written by the broker it grades: `send` returns what it
took, one `step` carries one `CHUNK` per direction, a `close` with bytes owed is
refused and a `cut` counts what it lost, `stats()` recomputes every counter from
the log, and the capstone's report is compared against both — a report counted
from the broker's own beliefs agrees with itself by construction, which is exactly
the comparison worth nothing. A decision is written by the world rather than by
the course: `grants.line(decision)` is the same string a `Ledger` records before
the act, so a denial the broker cannot spell is a denial it cannot make.

## The stages

| # | File | The stage | The mechanism |
|---|---|---|---|
| 1 | `stage_01.py` | The fixed header and the variable-length integer | `TYPE_NAMES`, `REQUIRED_FLAGS`, `RESERVED_TYPES`, `MAX_REMAINING_LENGTH`, `ProtocolError`, `Incomplete`, `read_varint`, `write_varint`, `read_header` |
| 2 | `stage_02.py` | The two-byte string and the CONNECT | `PROTOCOL_NAME`, `PROTOCOL_LEVEL`, `MAX_STRING_BYTES`, `CONNECT_KEYS`, `WILL_KEYS`, `CLIENT_TYPES`, `CONNACK_CODES`, `read_string`, `write_string`, `read_payload`, `read_connect`, `connack_code`, `write_connack` |
| 3 | `stage_03.py` | The topic filter, and the trie that matches it | `MAX_TOPIC_BYTES`, `WILDCARDS`, `TopicError`, `levels`, `validate_topic`, `validate_filter`, `is_wildcard`, `Trie` (`subscribe`, `unsubscribe`, `match`, `filters`, `subscribers`) |
| 4 | `stage_04.py` | SUBSCRIBE, SUBACK and the granted QoS | `SUBSCRIBE_FLAGS`, `MAX_QOS`, `SUBACK_FAILURE`, `SUBSCRIBE_KEYS`, `read_subscribe`, `read_unsubscribe`, `granted_qos`, `grant_codes`, `write_suback`, `write_unsuback` |
| 5 | `stage_05.py` | PUBLISH, routing, and what is retained | `PUBLISH_KEYS`, `DUP_BIT`, `QOS_BITS`, `RETAIN_BIT`, `read_publish`, `write_publish`, `Retained` (`store`, `lookup`, `topics`), `route`, `deliveries` |
| 6 | `stage_06.py` | QoS 1, the packet id, and the PUBACK | `MIN_PACKET_ID`, `MAX_PACKET_ID`, `DEFAULT_DEADLINE`, `ACK_FLAGS`, `INFLIGHT_KEYS`, `PacketIds` (`take`, `release`, `in_flight`, `free`), `read_ack`, `write_puback`, `write_ack`, `InFlight` (`add`, `settle`, `due`, `again`, `records`) |
| 7 | `stage_07.py` | QoS 2, the four-way handshake | `PUBREL_FLAGS`, `HANDSHAKE_KEYS`, `Sender(ids)` (`start`, `received`, `records`, `due`), `Receiver` (`took`, `released`, `held`), `write_pubrec`, `write_pubrel`, `write_pubcomp` |
| 8 | `stage_08.py` | The session that outlives the socket | `SESSION_KEYS`, `QUEUE_MAX`, `KEEP_ALIVE_NUMERATOR`, `KEEP_ALIVE_DENOMINATOR`, `deadline_from`, `Sessions` (`attach`, `detach`, `touch`, `expired`, `queue_for`, `take_queued`, `sessions`) |
| 9 | `stage_09.py` | Grants, denials, and the line written before the act | `DECISION_KEYS`, `allowed_publish`, `allowed_subscribe`, `decide`, `Ledger` (`before`, `lines`, `denials`, `allowed`, `report`) |
| 10 | `stage_10.py` | One scenario, twice, and the reader's verdict | `BROKER_KEYS`, `REPORT_KEYS`, `Trace` (`wrote`, `frames`, `bytes`), `read_frames`, `cross_check`, `replay`, `Broker` (`accepted`, `receive`, `step`, `report`, `trace`) |

The stages are cumulative in the only direction that matters: a stage imports the
world and the earlier stages it needs, and nothing from a later one. Stage 1
imports nothing at all — and neither does any other stage: the ten solutions'
only imports are `streams`, `grants` and stages 1 to 9. Stage 1 owns the header, so
every other stage writes a *body* and reads one; stage 3 gives every later stage
its topic rules; stage 6 owns the id space the two handshakes spend; stage 8 owns
what survives a socket; stage 9 owns the vocabulary a refusal arrives in; and
stage 10 composes all nine, because a broker is exactly the sum of them.

## How to use this directory

```bash
python3 codecraft/cli.py run mqtt-broker-from-scratch      # what to build next, and why
python3 codecraft/cli.py stage mqtt-broker-from-scratch 4  # one stage: the file, what you write, what the tester costs
```

Or without codecraft: the templates are ordinary modules, and an unimplemented one
raises `NotImplementedError`. Implement them at the top level; finished versions
are in `solutions/`, and nothing beyond `solutions/` ships a solution or a hint in
this directory. The templates fail and the solutions pass, and that is the whole
grading loop — this course is checker-driven and there is no test framework
anywhere. The ten checks are assembled into `course.py`, and every one of them is
a module-level `def check():` of bare `assert <condition>, "<message>"` statements,
where the message names the mistake rather than the symptom; an untouched template
reports as not implemented yet rather than failing for the wrong reason, because
the check lets `NotImplementedError` escape before any broad `except` catches it.
Every check builds its own transport and never mutates a module-level object, and
the last section of every check runs its own work twice and compares the two runs
byte for byte, because determinism here is asserted rather than assumed.

Every check is mutation-tested: **600 plausible wrong implementations** across the
ten stages, between 40 and 86 per stage, each a minimal edit to that stage's
solution, and the stage's check must fail. A mutant that hangs its check counts as
caught, because a wrong implementation that never terminates anything is not a
passing implementation. The audit reads each template and its solution and refuses
them unless the first docstring paragraph is exactly
`MQTT Broker From Scratch — stage NN: <title>.`, the template carries 3–6
`DESIGN DECISION — ` blocks and a `TODO: implement` line, the solution declares
every public name the template declares, the template imports nothing from a later
stage, and neither contains a float literal or imports a banned module (a clock, a
thread, an `asyncio`, a `random`, an `os`, a socket, a `subprocess`).

## Prerequisites

Standard library only, and in practice nothing at all: not one of the ten stages
imports a module that is not `streams`, `grants` or an earlier stage. No numpy, no
network, no threads, no sockets, no `heapq` — a redelivery deadline here is a pair
of ticks the caller hands in, not a timer queue. `time`, `threading` and `asyncio`
are banned because a tick counted by the transport is this course's unit and a wall
clock would make the number a machine's opinion; `random` because every fixture is
deterministic and a transport is a function of its rules; and `os`, `socket`,
`subprocess`, `secrets`, `shutil`, `tempfile`, `pathlib`, `uuid`, `math`,
`statistics`, `decimal` and `fractions` are imports no stage may make either. There
are no floats anywhere — not in a template, not in a solution, not in a check — so
every tick, byte count, packet id, length, offset and deadline is an `int`, and the
arithmetic is written out by hand on purpose.

You should be comfortable with bytes and byte-level arithmetic, with dicts as
records, with tuples as answers, with `try`/`except` and with a state machine whose
transitions are data. Some of the later stages are easier if you have met a
variable-length encoding and a retransmission deadline before, but nothing here
assumes it: stage 1 builds the encoding and stage 6 builds the deadline, which is
the point.

## Design decisions

- **A packet's fixed header is read once, by stage 1, and handed down.** Every
  `write_*` returns the *body* — `write_connack(0, 0)` is `b"\x00\x00"`, not a
  CONNACK frame — and every reader takes a body at a position, because the caller
  already has the header. The one place a frame is read whole is stage 10's
  `read_frames`, which is exactly the broker's own reader reading its own output;
  a PUBLISH decides from the flags whether an id follows its topic, which is why
  `read_publish(data, pos=0, flags=0)` is the one reader that is handed them.
- **The clock is always the caller's.** `InFlight.add(message, packet_id, now)`,
  `Sender.start(message, now)`, `due(now, deadline)`, `Sessions.expired(now)` — a
  deadline is `k + k//2` ticks and the only thing that moves a tick is
  `Transport.step()`. Nothing in the course can wait, so nothing in it can be
  slow: "the message was re-sent" is a count, and "the session expired" is a tick
  the check chose.
- **The transport is the tie-breaker, and the broker's own report is the claim.**
  `cross_check(report, transport)` holds one against the other — the frames and
  bytes the broker says it wrote against the trace it wrote them to, and the trace
  against the log the transport kept — and returns the disagreements key by key
  rather than hiding them. The capstone's own check proves the tie-breaker is real
  by doctoring the report and asserting the disagreement is named.
- **A mismatch of shape raises; a verdict about policy is returned.** Anything that
  cannot be the thing at all — a type byte that is not a packet, a flags nibble the
  format forbids, a length that cannot fit, a buffer that is not bytes, a tick that
  is not a whole number — raises, naming the offender and, where there is one, both
  numbers. Anything that is a decision about a client — a filter the broker will
  not route, a publish the grants do not allow, a queue that is full, a will that
  is owed — is returned as data, because a broker's whole job is to decide, and a
  denial that arrives as an exception cannot be written into the ledger.
- **The QoS a client gets is the lower of what it asked and what it may have.**
  `granted_qos(requested, cap=2)` is the whole of that rule, and a filter the
  broker refuses is a `SUBACK` with `0x80` in its place rather than a dropped
  subscription — the client is told, in the only vocabulary the format has.
- **Retained is the caller's word, not the message's.** The same publish is handed
  over twice in a broker's life — once live, once out of the store when somebody
  subscribes — and the wire flag differs while the bytes do not, so
  `deliveries(publish, subscribers, retained=False)` takes the flag from the call.
  A live delivery says `retain=False` even when the publish that caused it carried
  the bit, which is the mistake the flag exists to make visible.
- **A session owns what a socket does not.** Subscriptions, the queue and the
  keep-alive outlive the stream; the will belongs to the connection, so it is owed
  by a `cut` and by an expiry and never by an agreed `close`. `pending` is the
  count of messages a full queue *dropped*, not a second copy of the queue, because
  a number that can be recounted from the queue is a number nobody needs to keep.

## Where this stops

Deliberately left out, so you know the boundary:

- **No sockets, no TCP, no TLS.** This broker is handed a transport whose streams
  are already open; the wire *below* it — the handshake, the window, the
  retransmission timer, the close — is L1's course, and TLS is neither.
- **No MQTT 5.** No properties, no reason codes beyond the six the vocabulary has,
  no topic aliases, no flow control, no subscription options, no shared
  subscriptions. The format built here is the 3.1.1 shape: a header, a body, a
  two-byte string, a topic filter, four QoS levels of *behaviour* with three of
  them legal.
- **No durability.** The retained store, the sessions and the in-flight records
  live as long as the run; what survives a crash — the log, the sync, the replay —
  is J3's course, and this one hands it a broker with nothing to write to.
- **No clustering, no bridges, no broker-to-broker anything.** One transport, one
  broker, and no second machine to disagree with it.
- **No performance tuning of any kind.** Latency, throughput and the shape of the
  curve under load are not measured, because a machine's speed is not a course's
  unit; the only numbers this course compares are ticks, frames and bytes, and
  they are counted by the transport.
- **No authentication beyond the table.** Who a client *is* arrives in its CONNECT
  and what it may do comes from `grants.py`; there is no password, no certificate,
  no token and no session takeover, because the interesting half of that question
  is J4's.

## Where this sits

This is the third slot in the repository's L phase, *Programs that talk*, and it
closes it: L1 `tcp-ip-from-scratch` builds the wire this course refuses to look
inside — a link that loses, duplicates and reorders, and a stack whose ledger is
cross-checked against what the wire kept — and J4
`sandbox-capabilities-from-scratch` is where the policy that decides who may
publish where is the subject rather than a provided table. It also inherits the
discipline of J1's clock and J3's log: the transport here is the same trick as L2's
`link.py`, applied to a format that can refuse a frame rather than to a server that
must not block. Before it, a protocol is something the repository has only ever
framed; after it, every frame a broker writes is a frame the course's own reader
takes back, and the one comparison that cannot lie — the transport's log — is the
one the capstone's verdict is made of. L4 `git-from-scratch` is next: the other
artefact in this repository that another program validates.

