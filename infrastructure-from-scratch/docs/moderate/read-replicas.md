# Read Replicas — Moderate

## 1. What problem does it solve?

A single database server can handle limited reads per second.
When you have 10,000 reads and 100 writes, the DB can't serve all reads
fast enough.

Read replicas solve this by copying data from the primary (master) to
secondary (slave) nodes:
- Primary: accepts reads AND writes
- Replicas: accept reads only; replicate from primary

**The job:** scale reads horizontally while accepting bounded staleness
(replication lag) and handling replica failover when the primary crashes.

## 2. How does it work?

### Replication methods

| Method | How it works | Lag | Overhead |
|---|---|---|---|
| **Synchronous** | Primary waits for replica ACK before confirming write | Near-zero | High (slower writes) |
| **Asynchronous** | Primary doesn't wait; replica catches up later | Bounded by network + query time | Low (fast writes) |
| **Semi-synchronous** | Primary waits for at least one replica | Small (one ACK) | Moderate |

### Replication modes

| Mode | Description |
|---|---|
| **Statement-based** | Replicate the SQL statement | Fast; but dangerous with non-deterministic functions (`NOW()`, `UUID()`) |
| **Row-based** | Replicate the changed rows (before/after images) | Larger binary log but safe; MySQL/PostgreSQL default |
| **Mixed** | Statement by default; row when needed (non-deterministic functions) |

### Read routing

The application must decide which reads go to the primary and which go to replicas:

```python
def get_user(user_id):
    # Most reads go to replica
    return db_replica.query("SELECT * FROM users WHERE id = ?", user_id)

def create_user(name, email):
    # Writes go to primary
    db_primary.execute("INSERT INTO users (name, email) VALUES (?, ?)", name, email)
    return db_primary.query("SELECT * FROM users WHERE email = ?", email)  # read-after-write
```

### Replication lag problem

After a write, a read on a replica may return stale data:

```
Time 0ms:  Primary: INSERT user
Time 10ms: Replica: still has old state → returns stale data
Time 50ms: Replica: catches up → returns current data
```

**Solutions:**
1. **Read-your-writes:** track the write timestamp; read from primary until replica is caught up
2. **Session consistency:** all reads in a session go to primary until replica lag is known
3. **Accept eventual consistency:** for non-critical reads (analytics, caching)

### Failover

When the primary crashes:
1. Detect failure (heartbeat miss, TCP connection closed)
2. Promote the latest replica (or one with most recent data)
3. Update DNS or connection pool to point to the new primary
4. Reconfigure other replicas to replicate from the new primary

## 3. Real implementations

| System | Replication | Lag | Notes |
|---|---|---|---|
| **PostgreSQL** | Async via WAL | Seconds to minutes | Streaming replication; logical replication for specific tables |
| **MySQL** | Async / semi-sync | Seconds to minutes | Binlog-based; group replication for synchronous |
| **MongoDB** | Async (primary-replica) | Seconds | Oplog-based; reads from secondaries can be configured with read preferences |
| **Amazon RDS** | Async / synchronous (read replicas) | Seconds | Managed; automated failover for Aurora |
| **CockroachDB** | Synchronous (Raft) | Near-zero | Multi-region; strong consistency across regions |
| **YugabyteDB** | Synchronous (Raft) | Near-zero | PostgreSQL-compatible; multi-region by default |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Replication | Asynchronous | Synchronous | Strong consistency → sync; scale reads → async |
| Read routing | App-level (code) | Proxy-level (HAProxy, PgBouncer) | Simple → app; complex → proxy |
| Failover | Manual | Automated (orchestrator) | Simple → manual; critical → automated |
| Read preference | Always primary (strongest consistency) | Read from replica (weakest, most scale) | Always read from replica unless read-after-write required |
| Replication lag handling | Accept lag (eventual) | Force primary read (strong) | User sees own data → force primary; analytics → accept lag |

## 5. Exercises

1. **Primary + replica**: Simulate a primary and replica DB; all writes go to primary; reads go to replica.
2. **Replication lag simulator**: Introduce random delay on replica reads; test read-after-write consistency.
3. **Read-after-write fix**: For reads immediately after writes, route to primary.
4. **Failover test**: Kill the primary; promote the replica; verify reads still work.
5. **Read routing proxy**: A proxy that routes all writes to primary and all reads to replica.

## 6. References

- [PostgreSQL documentation: Streaming replication](https://www.postgresql.org/docs/current/warm-standby.html)
- [MySQL documentation: Replication](https://dev.mysql.com/doc/refman/8.0/en/replication.html)
- [MongoDB documentation: Replica Sets](https://www.mongodb.com/docs/manual/replication/)
- [Read-after-write consistency](https://www.mongodb.com/docs/manual/core/read-preference/#read-your-writes)
- [Failover in distributed databases](https://cloud.google.com/architecture/replication-and-failover-patterns)