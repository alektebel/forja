# Consensus (Raft/Paxos) — Extremely Complex

## 1. What problem does it solve?

In a distributed system, nodes can fail, messages can be lost, and clocks drift.
When multiple nodes have a copy of the same data, they must agree on:
- The order of operations (so everyone sees the same data)
- Which node is the leader (so only one node accepts writes)
- When a write has "committed" (survived a node failure)

Without consensus, you get inconsistency:
```
Node A:  writes "x=1" → commits (thinks it succeeded)
Node B:  receives nothing → "x" is still undefined
```

Consensus algorithms solve this: a protocol by which N nodes agree
on a single value despite crashes and network partitions.

**The job:** a set of nodes agrees on a sequence of values (a log),
even when some nodes are unreachable or slow, and even when the
leader crashes.

## 2. How does it work?

### Raft (simpler than Paxos; the one to understand first)

Raft divides the problem into three sub-problems:
1. **Leader election**: nodes elect a leader
2. **Log replication**: leader replicates log entries to followers
3. **Safety**: followers accept only entries from the current leader;
   leader never commit an entry until it's replicated to a majority

### Leader election

```
All nodes start as FOLLOWER

1. Leader sends Heartbeat every T ms
2. If a follower doesn't receive a heartbeat for election timeout:
   - Increment term number
   - Vote for itself (first vote)
   - Ask others for votes
3. If a candidate receives votes from a majority:
   - Become LEADER
   - Send AppendEntries (heartbeat) to all followers
4. If no candidate wins (split vote):
   - Wait for random election timeout → try again
```

Key invariant: at most one leader per term.
A vote is granted if the candidate's log is at least as up-to-date as the voter's.

### Log replication

```
Leader receives write "x=1":
  1. Append to leader's log: [entry: x=1, term: 3]
  2. Send AppendEntries to all followers (with new entry)
  3. Followers append to their logs; respond OK
  4. When majority respond OK:
     - Leader commits: "x=1"
     - Apply to state machine
     - Send committed entries to followers
```

Safety:
- A leader only commits entries from its own term
- A leader only appends entries that match its own log (never overwrite)
- Followers reject entries from non-leaders or older terms

### Index vs. Apply vs. Committed

| Concept | Meaning |
|---|---|
| **Index** | Position in the log (1, 2, 3, ...) |
| **Append** | Follower received the entry (not yet committed) |
| **Committed** | Entry is on a majority of nodes (safe to apply) |
| **Apply** | Entry applied to state machine (visible to clients) |

```
Index 1: [x=1, term=3]  ← committed, applied (visible)
Index 2: [y=2, term=3]  ← committed, applied
Index 3: [z=3, term=4]  ← appended by new leader, not yet committed
```

### The Raft log compaction (snapshot)

Logs grow unbounded. Snapshots:
1. Leader takes a snapshot of state machine at index N
2. Stores: `state_at_index_N` + `last_log_index = N` + `last_log_term`
3. Followers can ask for a snapshot instead of requesting every log entry

### What Paxos is (and why Raft was invented)

Paxos was the first practical consensus algorithm, but it's notoriously
hard to understand and implement. Raft was designed to be as powerful
as Paxos but comprehensible:
- Paxos: abstract protocol; many interpretations
- Raft: specific algorithm with clear roles (leader, follower, candidate)

## 3. Real implementations

| Implementation | Consensus | Notes |
|---|---|---|
| **etcd** | Multi-Raft | Raft-based; key-value store; Kubernetes uses it |
| **Consul** | Raft | Raft-based; service discovery, KV store |
| **ZooKeeper** | Zab (ZooKeeper Atomic Broadcast) | Like Paxos; used by Kafka; strong consistency |
| **CockroachDB** | Raft | Raft-based; SQL layer on top; multi-region |
| **TiKV** | Raft | Raft-based; NewSQL; HTAP; TiDB's storage engine |
| **RocksDB + Raft** | Custom | RocksDB is the store; Raft replicates |
| **Hashicorp Raft** | Raft library | Go library; used by Consul, Nomad, etc. |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Consensus algorithm | Raft (comprehensible) | Paxos (mature, many implementations) | New → Raft; existing Paxos deployment → Paxos |
| Number of nodes | 3 (minimum for single failure) | 5 (two failures tolerated) | Small cluster → 3; large → 5+ |
| Leader | Single leader (simpler) | Multi-leader (higher throughput) | Simple → single leader; throughput → multi-leader (e.g. Tendermint) |
| Log compaction | Snapshot (every N entries) | Always retain full log | Disk space matters → snapshot; debugging → full log |
| Client reads | Through leader (consistent) | Read-your-writes only (leader); linearizable reads (expensive) | Read-heavy → read from follower (may be stale) |

## 5. Exercises

1. **Leader election**: Implement Raft leader election (term numbers, voting, majority quorum).
2. **Log replication**: Leader accepts writes; replicates to followers; commits when majority OK.
3. **Log compaction**: Take snapshots when log reaches N entries; compact log to save disk.
4. **Follower catch-up**: New follower asks leader for entries starting from index X.
5. **Multi-Raft**: Multiple independent Raft groups (one per range/shard) for parallelism.

## 6. References

- [The Raft Paper (Ongaro & Ousterhout, 2014)](https://raft.github.io/raft.pdf) — **READ THIS FIRST**
- [Raft visualizer](https://raft.github.io/raft.pdf) — interactive simulation
- [etcd documentation](https://etcd.io/docs/)
- [Zab protocol (ZooKeeper)](https://zookeeper.apache.org/doc/r3.4.14/zookeeperObserver.html)
- [CockroachDB Raft](https://www.cockroachlabs.com/docs/stable/replication.html)
- [Multi-Raft in CockroachDB](https://www.cockroachlabs.com/docs/stable/multi-raft.html)