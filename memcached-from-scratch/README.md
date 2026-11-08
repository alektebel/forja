# Memcached From Scratch

Build the ops-at-scale internals of the largest cache fleet ever run: ten
graded stages, from a hash ring that must never move to a capstone whose two
runs produce one identical byte string. Standard library only — no threads, no
asyncio, no wall clock, no `random`, and no `hash()`.

memcached is usually taught as a client library — "put a cache in front". This
course teaches the other memcached: the one the ops teams at Danga, LiveJournal
and Facebook had to write into the daemon and its clients to survive
petabyte-scale reads. A ring that routes without a mapping. A slab allocator
that never splits a value. An LRU that evicts a whole page — and buries a hot
key with it. A protocol whose byte counts are verified before anything is
stored. And then the four client-side defences the NSDI'13 paper measured: tail
tolerance, statistical herding, single-flight, warm restart.

The thesis every check asserts: **the cache is a data structure, not a thread
pool.** Because the clock is injected and moves only by integer costs, and
every coin is `stable_hash` of names and ticks, a race is provable with
arithmetic, a tail is reproducible, and determinism is not a property you hope
for — the capstone check reads it off two digests.

## The stages

| # | File | The mechanism | The thing people get wrong |
|---|---|---|---|
| 1 | `stage_01.py` | Consistent hashing with 150 virtual nodes per machine | Routing with `hash()` (process-salted — two clients disagree) or one point per node (one machine takes 147% over its fair share) |
| 2 | `stage_02.py` | The slab ladder: smallest class that fits, holes before pages | Rounding to the nearest class, or splitting an oversized value — the daemon refuses both; 1 MB is a ceiling, not a suggestion |
| 3 | `stage_03.py` | Per-page LRU, whole-page recycle, expiry frees its slot | A global per-item LRU; and believing a hot key survives — it dies with its page and its stale neighbours, in one event |
| 4 | `stage_04.py` | The ASCII protocol, byte-exact: verbs, chunks, CAS tokens | Checking the byte count after the store (the half-write), answering EXISTS for a missing key, counting hits per command instead of per key |
| 5 | `stage_05.py` | Get-with-backup on a hashed slow slice, one shared clock | A `random()` tail nobody can replay; a client that hides the abandoned backup's origin query and fudges the ledger |
| 6 | `stage_06.py` | Statistical herding: a ramp-priced coin per cache per tick | A fixed jitter offset — it moves the death spike but never thins it; and an unpriced coin that re-pays an expensive rebuild sooner |
| 7 | `stage_07.py` | Single-flight (depth) and herding (width), measured apart | Claiming the mutex fixes thundering herds: it folds 200 cold queries to 20 and leaves the death column at 200 untouched |
| 8 | `stage_08.py` | Replication to the ring's successors; refill on read, keep the exptime | Random-peer replicas (the failover target holds nothing); refills that restart the ttl and resurrect expired data |
| 9 | `stage_09.py` | `stats` as a pure function of counters and the store | Storing a `hit_rate` beside its two ints; keeping a second copy of `evictions` the allocator never consulted |
| 10 | `stage_10.py` | The capstone: frontends over a node tier over one origin, canonical JSON | One timeline for arrivals and busy time; a float or a salt leaking into the report so two runs differ while every field looks fine |

Stages 5–10 compose the earlier ones (stage 8 routes through stage 1's ring
into stage 3's stores, stage 10 runs all of it), so they are meant to be done
in order — each check imports the files of the stages it builds on.

## The provided world

`world.py` is given and is not part of the exercise: `CacheError`, the integer
`Clock` (moved only by injected costs; refuses bools, floats, negatives),
`stable_hash` (md5 of the text as one int), and the `Origin` of record whose
`queries` counter is what every protection stage is finally measured against.

## What the course refuses to hide

- **The bill for every defence.** Hedging cuts the mean and the check pins the
  origin's ledger rising by exactly the backups sent (62 reads, 56 won).
  Herding thins the 1,000-deep death column to 150 and the total stays exactly
  2,000 — work relocated, never removed. A protection that appears free is a
  bug in the measurement.
- **The shape each defence cannot fix.** The mutex answers *depth* (ten
  clients, one cold key: 200 queries → 20). The coin answers *width* (ten
  frontends, one synchronized death: the tick-50 column 200 → 0). Production
  needs both because neither touches the other's case, and the check proves it
  by measuring both shapes under both protections.
- **Where the numbers come from.** `evictions` is the store's ledger — a
  whole-page recycle kills two items at once and a parallel counter misses
  it. `hit_rate` is recomputed at report time or not at all. The counters must
  satisfy `hits + misses == cmd_get`, and a report that accepts a bag where
  they disagree is reporting a fiction.
- **Determinism as a claim with a digest.** 744 script rows through the whole
  machine, twice, byte-identical:
  `1a8e93c17be92c60e573add8bbd8cc0a3be0b288d35670860a6905b250abcf06`. Every
  choice is a function of (name, key, tick); `hash()`, `random`, float
  timestamps or threads each turn the capstone into a story about a system.

## A correction the repo owed

memcached was **not** built at Facebook. Brad Fitzpatrick wrote it in 2003 at
Danga Live Support for LiveJournal, and the daemon's core — slab classes,
per-page LRU, the ASCII protocol — is that era's engineering for a
memory-starved PHP/MySQL stack. What Facebook (2010 onward, Nishtala et al.,
*Scaling Memcache at Facebook*, NSDI'13) contributed was the **ops-at-scale**
half: the measurements and client-side defences this course's stages 5–10
reproduce — tail tolerance, statistical herding, single-flight, backup
replication, warm restart. The course keeps both halves straight: stages 1–4
are the daemon, stages 5–10 are the fleet.

## How to use this directory

```bash
python3 codecraft/cli.py run memcached-from-scratch    # grade all ten
python3 codecraft/cli.py smoke memcached-from-scratch  # status without hints
```

Implement the templates at the top level; finished versions are in
`solutions/`. Copy a solution over its template to compare (`cp
solutions/stage_05.py stage_05.py`), and put the template back to try again.
Each solution file runs its own demo standalone:

```bash
cd memcached-from-scratch && PYTHONPATH=. python3 solutions/stage_07.py
```

## Prerequisites

Nothing before it. Basic Python (classes, sorting, hashing) is enough; the
parts that usually trip people up — bisect on a tuple list, a flat index that
decodes to (page, slot), a coin salted with the cache's name — are introduced
where they are used. No dependencies outside the standard library, no network.

## Where this stops

Deliberately left out, so you know the boundary:

- **No sockets, no binary protocol.** `Ascii.handle` takes a request text and
  returns a response text; the wire, the event loop and the UDP stats port are
  I/O, and the hard parts of the protocol — framing, the chunk check, the CAS
  token — are all decided before any byte moves.
- **No real threads, and that is the point.** A flight here is a rule about
  when the leader's value lands, expressed on one integer clock. Reproduce it
  with a mutex and a condvar and the race is real but unprovable; this
  formulation is what makes the checks arithmetic.
- **The hash ring is not a database.** No rebalancing protocol, no
  membership gossip, no persistence. When a node dies, `crash()` forgets it
  and the ring re-routes — which is exactly the moment stages 1 and 8 pay
  attention to.
- **Consistency is cache-shaped.** Values expire, get evicted, and are
  re-fetched; nothing here makes two replicas agree on the *current* value.
  That is `dynamo-paper/`'s problem, and this course borrows its ring, not
  its vector clocks.

## See also

- `infrastructure-from-scratch/docs/moderate/caching-layer.md` — the prose
  version of this territory; stages 5–9 are its measured internals
- `system-design/solutions/consistent_hash.py` — the ring at stage 1's size,
  without the vnode lesson proved against 12,000 keys
- `dynamo-paper/` — the failure half of the fleet, from the other side
