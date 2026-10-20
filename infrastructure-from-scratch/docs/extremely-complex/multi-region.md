# Multi-Region Active-Active — Extremely Complex

## 1. What problem does it solve?

A single-region database serves users from one data center:
- Good latency for local users
- Bad latency for users in other regions (100–200ms RTT)
- Data center outage → entire system down

Active-active solves both:
- Each region serves its own users (low latency)
- All regions accept writes (active-active, not active-passive)
- Writes replicate across regions

**The job:** let users write from anywhere, replicate changes globally,
and resolve conflicts when two users modify the same data concurrently.

## 2. How does it work?

### Replication models

| Model | How it works | Consistency | Availability |
|---|---|---|---|
| **Active-Active** | All regions accept reads AND writes | Eventual (conflicts need resolution) | High (region can fail, others serve) |
| **Active-Passive** | One region accepts writes; others are read-only | Strong (single source of truth) | Medium (failover required) |
| **Leader-Follower** | Region A writes; regions B, C replicate | Strong (until leader fails) | Medium (leader is single point of failure) |

### Conflict resolution

When the same key is modified in two regions simultaneously:

| Strategy | How it works | Pros | Cons |
|---|---|---|---|
| **Last-Writer-Wins (LWW)** | Later timestamp wins | Simple; fast | Data loss (old value silently overwritten) |
| **Vector clocks** | Track causality; detect concurrent writes | Correctly identifies conflicts | Requires manual merge |
| **CRDT** | Commutative operations (set merge, counter increment) | No conflicts (by design) | Limited data types; complex to implement |
| **Operational transform** | Transform operations (like Google Docs) | Preserves both writes | Extremely complex |
| **Custom merge function** | Application-specific merge | Can preserve both values | Requires code per data type |

### Conflict-free Replicated Data Types (CRDTs)

CRDTs guarantee that all replicas converge to the same state,
no matter the order of operations:

| Type | Use case | Commutative property |
|---|---|---|
| **G-Counter** (Grow-only counter) | Increment counters | `max(a, b)` |
| **PN-Counter** (Grow + shrink) | Increment/decrement | `max(a, b)` |
| **G-Set** (Grow-only set) | Add to set | `union(a, b)` |
| **LWW-Register** | Last-write-wins register | `max(timestamp, value)` |
| **OR-Set** (Observed-remove set) | Add/remove from set | Union + observed removals |

### Partition tolerance

In a network partition (A can't reach B):
- If partition is temporary: replicas diverge; merge on reconnect
- If partition is permanent: choose which region stays active
- Must handle: duplicate messages, lost messages, clock drift

### Clock drift

Without synced clocks, LWW is unreliable:
- Region A: timestamp 12:00:01
- Region B: timestamp 12:00:02 (but it's actually 11:59:58 in real time)
- B's write wins (later timestamp) even though A's write happened first

Solutions:
- **NTP**: synchronise clocks (imperfect; 10–50ms error)
- **HyLogical clocks**: hybrid logical clocks (HLC) — combine physical + logical
- **Vector clocks**: track causality regardless of clock drift

## 3. Real implementations

| System | Replication | Conflict resolution | Notes |
|---|---|---|---|
| **CockroachDB** | Raft-based multi-region | Strong (Raft consensus); single region per range | Leader per region; replicas in other regions |
| **YugabyteDB** | Multi-region Raft | Strong (Raft consensus) | PostgreSQL-compatible; per-region leader |
| **DynamoDB Global Tables** | Multi-region active-active | LWW or custom | AWS; eventual consistency |
| **Firebase Realtime DB** | Multi-region active-active | LWW + CRDT (for arrays) | Google; mobile-first |
| **RethinkDB** | Multi-region active-active | LWW; manual conflict handling | Real-time; open-source |
| **CouchDB** | Multi-region active-active | LWW + revision IDs | Apple/Couchbase; document database |
| **Riak** | Multi-region active-active | LWW; read-your-wins; custom | Amazon; object store |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Consistency | Strong (Raft) | Eventual (CRDT) | Financial data → Raft; user profile → CRDT |
| Conflict resolution | LWW | CRDT | Simple data → LWW; concurrent edits → CRDT |
| Region topology | All-region (every region is leader) | Hub-and-spoke (one leader region) | Equal load → all-region; hub data → hub-and-spoke |
| Partition handling | Automatic (merge on reconnect) | Manual (stop writes during partition) | Availability matters → automatic; correctness → manual |
| Data placement | Global (every region has all data) | Localised (data lives in one region) | Latency-sensitive → global; compliance (GDPR) → localised |

## 5. Exercises

1. **Two-region replication**: Region A and Region B replicate writes to each other using a message queue.
2. **LWW conflict resolution**: When two regions write the same key, the later timestamp wins.
3. **Vector clocks**: Track causality; detect concurrent writes; resolve conflicts.
4. **CRDT counter**: Implement a PN-counter (grow + shrink) that converges across regions.
5. **Partition simulation**: Simulate a network partition; merge replicas on reconnect; detect conflicts.

## 6. References

- [CockroachDB multi-region docs](https://www.cockroachlabs.com/docs/stable/multi-region-overview.html)
- [CRDTs: "A comprehensive study of CRDTs" (Shapiro et al., 2011)](https://hal.inria.fr/inria-00555588/document)
- [DynamoDB Global Tables docs](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GlobalTables.html)
- [Firebase Realtime DB docs](https://firebase.google.com/docs/database/web/start)
- [Partition tolerance: CAP theorem](https://en.wikipedia.org/wiki/CAP_theorem)
- [Hybrid Logical Clocks (Shanbloom et al., 2018)](https://www.vulcandrs.com/post/hybrid-logical-clocks)