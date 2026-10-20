# Database Sharding — Complex

## 1. What problem does it solve?

A single database can handle limited writes per second.
When writes become the bottleneck (not reads), you can't just add more replicas
— only the primary accepts writes.

Sharding splits the data across multiple DBs:
- Shard 0: users with IDs 0–999
- Shard 1: users with IDs 1000–1999
- Shard N: users with IDs N*1000 – (N+1)*1000 – 1

Each shard is an independent database. Writes go to the right shard.

**The job:** spread writes across machines while keeping lookups efficient
and rebalancing manageable.

## 2. How does it work?

### Sharding strategies

| Strategy | How it works | Pros | Cons |
|---|---|---|---|
| **Range** | Shard by range of key (e.g. A–M, N–Z) | Good for range queries; easy to understand | Hot shards (new data goes to last shard); rebalance = move entire shard |
| **Hash** | `hash(key) % N` → shard N | Even distribution | Range queries require querying all shards; rebalance = remap all keys |
| **Consistent hash** | Ring of virtual nodes; key maps to nearest node | Adding/removing shard moves only a fraction of keys | Skewed keys can still cause hotspots |
| **Directory-based** | Lookup a directory service: key → shard mapping | Flexible; can move individual keys | Directory service is a bottleneck; adds latency |
| **Geographic** | Shard by region (EU data stays in EU) | Compliance (GDPR); low latency per region | Uneven load; complex cross-region queries |

### Consistent hashing

The key insight: when you add/remove a shard, only a fraction of keys
need to move (O(K/N) where K = total keys, N = shards).

```
Ring: [node_0] → [node_1] → [node_2] → [node_0]  (3 nodes, 160 vnodes each)

Key "user_42" → hash("user_42") = 73 → falls between node_1 and node_2
→ assigned to node_2

Add node_3:
  node_3 → hash("node_3_v0") = 50 → falls between node_0 and node_1
  → keys assigned to node_1 move to node_3 (about 1/3 of keys)
```

Implementation: use a balanced BST (red-black tree) or sorted array of
virtual node positions for efficient lookup.

### Rebalancing

When shards change (add/remove):
1. **Consistent hash**: only O(K/N) keys need to move; use background transfer
2. **Range**: move entire ranges; can use two-phase approach (dual-write)
3. **Dual-write**: write to old + new shard during transition; backfill old → new; switch reads

### Cross-shard queries

- **Local join**: join within the same shard (fast, no cross-network)
- **Global join**: join across shards (slow, requires collecting data)
- **Denormalization**: store redundant data on each shard to avoid cross-shard joins
- **Shard by foreign key**: ensure related entities live on the same shard

## 3. Real implementations

| System | Sharding | Strategy | Notes |
|---|---|---|---|
| **MongoDB** | Auto-sharding | Range, hashed, or manual; config servers + mongos routers | Automatic; supports range queries on range-sharded data |
| **Cassandra** | Ring-based | Consistent hash (Murmur3) | No single point of failure; every node is equal |
| **Vitess** | MySQL sharding | Consistent hash or range; vtgate routes queries | Facebook-scale; MySQL-compatible |
| **CockroachDB** | Auto-sharding | Range-based; automatic rebalance | PostgreSQL-compatible; built-in |
| **YugabyteDB** | Auto-sharding | Consistent hash via YB-Tserver | PostgreSQL-compatible; Raft-based |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Sharding strategy | Range (ordered) | Hash (even) | Need range queries → range; need even distribution → hash |
| Rebalancing | Manual | Automatic | Large cluster → automatic; small → manual |
| Cross-shard join | Denormalize | Query all shards | Read-heavy + joins → denormalize; occasional → query all |
| Number of shards | Few large shards | Many small shards | Small dataset → few; large → many (easier rebalance) |
| Shard key | User ID | Tenant ID | Multi-tenant → tenant-ID; general → user-ID |

## 5. Exercises

1. **Range sharding**: Implement shard selection by `hash(key) % N` → assign to shard.
2. **Consistent hash ring**: Virtual nodes (160 per physical); add/remove shards; only O(K/N) keys move.
3. **Dual-write migration**: Write to old + new shard; backfill old → new; switch reads atomically.
4. **Cross-shard query**: Given a key, determine which shard to query; support scanning all shards.
5. **Load balancer**: Route writes to the shard with fewest active connections.

## 6. References

- [Consistent hashing: "Consistent Hashing and Random Trees" (Karger et al., 1997)](https://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.31.7207)
- [Vitess: Database Sharding](https://vitess.io/docs/user-guides/sharding/overview/)
- [MongoDB sharding](https://www.mongodb.com/docs/manual/sharding/)
- [Cassandra hashing](https://cassandra.apache.org/doc/latest/cassandra/data-model/partitioning.html)
- [Sharding strategies (Martin Kleppmann)](https://martin.kleppmann.com/2016/02/08/how-to-partitioning.html)