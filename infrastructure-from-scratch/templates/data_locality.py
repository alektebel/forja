"""
Data Locality — From Scratch
==============================
Build data locality primitives to understand:
- Co-locating related data on the same shard to avoid cross-shard joins
- Partition-aware query routing (send query to the right shard)
- Denormalization: duplicate data to keep reads local
- Locality-aware cache placement (cache on the same node that owns the data)
- Multi-tenant data isolation with per-tenant sharding

Data locality: the principle that computation is cheapest when the data it
needs is physically nearby (same process, same machine, same rack, same DC).
Every cross-shard join, cross-node RPC, or cross-DC read adds latency and load.

Learning Path:
1. Implement a shard-aware router that routes queries to the correct shard
2. Implement co-location: store related entities on the same shard
3. Implement a denormalized read model (pre-joined view)
4. Implement a locality-aware cache that keeps cache entries with their shard
5. Think about: how does Spanner co-locate interleaved tables?
   - Parent-child tables share the same Paxos group and physical directory
   - A User and all their Orders live on the same Spanner server
"""

import hashlib
import threading
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Step 1: Shard Router
# ---------------------------------------------------------------------------

class ShardRouter:
    """Routes requests to the correct shard based on a partition key.

    Uses modulo hashing: shard_id = hash(partition_key) % num_shards

    TODO:
    - get_shard(partition_key): return 0-based shard index for the key
    - add_shard(shard_id, shard): register a shard backend
    - route(partition_key): return the shard object for this key
    """

    def __init__(self, num_shards: int):
        self.num_shards = num_shards
        self._shards: Dict[int, Any] = {}

    def get_shard_id(self, partition_key: str) -> int:
        """Compute shard index for a partition key.

        TODO:
        - Use: int(hashlib.md5(partition_key.encode()).hexdigest(), 16) % num_shards
        """
        # TODO: implement get_shard_id
        raise NotImplementedError("Implement ShardRouter.get_shard_id")

    def add_shard(self, shard_id: int, shard: Any) -> None:
        """Register a shard backend at the given index.

        TODO: self._shards[shard_id] = shard
        """
        # TODO: implement add_shard
        raise NotImplementedError("Implement ShardRouter.add_shard")

    def route(self, partition_key: str) -> Any:
        """Return the shard for this partition key.

        TODO: return self._shards[self.get_shard_id(partition_key)]
        """
        # TODO: implement route
        raise NotImplementedError("Implement ShardRouter.route")


# ---------------------------------------------------------------------------
# Step 2: Co-Location Store
# ---------------------------------------------------------------------------

class CoLocationStore:
    """Store that keeps related entities on the same shard by derived key.

    Pattern: all entities belonging to a tenant/user share the same partition key.
    Example: orders for user_id=42 are stored under partition key "user:42".

    Tables:
      users:    partition_key = user_id
      orders:   partition_key = user_id  ← same shard as the user!
      products: partition_key = product_id (different shard family)

    This allows reading a user + all their orders in a single shard query.

    TODO:
    - put(entity_type, entity_id, partition_key, data): store entity on the shard
      determined by partition_key
    - get(entity_type, entity_id, partition_key): retrieve entity from its shard
    - get_all(entity_type, partition_key): return all entities of a type on this shard
    """

    def __init__(self, router: ShardRouter):
        self._router = router
        # Each shard is a dict: entity_type → {entity_id → data}
        for shard_id in range(router.num_shards):
            router.add_shard(shard_id, {})

    def put(self, entity_type: str, entity_id: str, partition_key: str,
            data: Any) -> None:
        """Store an entity on the shard determined by partition_key.

        TODO:
        1. shard = self._router.route(partition_key)  (a plain dict)
        2. shard.setdefault(entity_type, {})[entity_id] = data
        """
        # TODO: implement put
        raise NotImplementedError("Implement CoLocationStore.put")

    def get(self, entity_type: str, entity_id: str, partition_key: str) -> Optional[Any]:
        """Retrieve an entity from its shard.

        TODO:
        1. shard = self._router.route(partition_key)
        2. return shard.get(entity_type, {}).get(entity_id)
        """
        # TODO: implement get
        raise NotImplementedError("Implement CoLocationStore.get")

    def get_all(self, entity_type: str, partition_key: str) -> List[Any]:
        """Return all entities of a type on the shard for partition_key.

        TODO: return list of values from shard[entity_type]
        """
        # TODO: implement get_all
        raise NotImplementedError("Implement CoLocationStore.get_all")


# ---------------------------------------------------------------------------
# Step 3: Denormalized Read Model
# ---------------------------------------------------------------------------

class DenormalizedOrderView:
    """Pre-joined read model: order + user name + product name in one record.

    Instead of 3 separate shard lookups (user, product, order), we store a
    flattened view at write time so reads are a single key lookup.

    Pattern: on order creation, write the denormalized view.
             On user/product update, update all affected order views (fan-out).

    TODO:
    - create_order(order_id, user_id, product_id, user_name, product_name, qty):
      store a denormalized record under order_id
    - get_order(order_id): return the full denormalized record
    - update_user_name(user_id, new_name): update all order views for this user
    """

    def __init__(self):
        self._orders: Dict[str, Dict] = {}          # order_id → record
        self._user_orders: Dict[str, List[str]] = {}  # user_id → [order_ids]

    def create_order(self, order_id: str, user_id: str, product_id: str,
                     user_name: str, product_name: str, quantity: int) -> None:
        """Create a denormalized order view.

        TODO: store all fields in self._orders[order_id];
              append order_id to self._user_orders[user_id]
        """
        # TODO: implement create_order
        raise NotImplementedError("Implement DenormalizedOrderView.create_order")

    def get_order(self, order_id: str) -> Optional[Dict]:
        """Return the denormalized order record.

        TODO: return self._orders.get(order_id)
        """
        # TODO: implement get_order
        raise NotImplementedError("Implement DenormalizedOrderView.get_order")

    def update_user_name(self, user_id: str, new_name: str) -> int:
        """Update user_name on all order views for this user.

        Returns the number of order views updated.

        TODO:
        1. Look up all order_ids for user_id in self._user_orders
        2. For each order: self._orders[order_id]["user_name"] = new_name
        3. Return count
        """
        # TODO: implement update_user_name (fan-out write)
        raise NotImplementedError("Implement DenormalizedOrderView.update_user_name")


# ---------------------------------------------------------------------------
# Step 4: Locality-Aware Cache
# ---------------------------------------------------------------------------

class LocalityAwareCache:
    """Cache that is co-located with the shard it serves.

    Each shard has its own in-memory cache. Cache entries are placed on
    the same shard as the data they cache — no cross-shard cache lookups.

    TODO:
    - get(partition_key, entity_key): check cache on the shard for partition_key
    - put(partition_key, entity_key, value, ttl): store in the shard's local cache
    - invalidate(partition_key, entity_key): remove from shard-local cache
    """

    def __init__(self, router: ShardRouter):
        self._router = router
        import time as _time
        self._time = _time
        # Initialize per-shard caches: shard_id → {entity_key → (value, expires_at)}
        self._caches: Dict[int, Dict[str, Tuple[Any, float]]] = {
            i: {} for i in range(router.num_shards)
        }

    def _shard_cache(self, partition_key: str) -> Dict[str, Tuple[Any, float]]:
        """Return the local cache for the shard that owns partition_key."""
        shard_id = self._router.get_shard_id(partition_key)
        return self._caches[shard_id]

    def get(self, partition_key: str, entity_key: str) -> Optional[Any]:
        """Return cached value or None if missing/expired.

        TODO:
        1. cache = self._shard_cache(partition_key)
        2. If entity_key not in cache: return None
        3. value, expires_at = cache[entity_key]
        4. If time.time() > expires_at: del cache[entity_key]; return None
        5. Return value
        """
        # TODO: implement get
        raise NotImplementedError("Implement LocalityAwareCache.get")

    def put(self, partition_key: str, entity_key: str, value: Any,
            ttl: float = 60.0) -> None:
        """Store value in the shard-local cache with TTL.

        TODO:
        1. cache = self._shard_cache(partition_key)
        2. cache[entity_key] = (value, time.time() + ttl)
        """
        # TODO: implement put
        raise NotImplementedError("Implement LocalityAwareCache.put")

    def invalidate(self, partition_key: str, entity_key: str) -> None:
        """Remove a cache entry from the appropriate shard cache.

        TODO: del from shard_cache if present
        """
        # TODO: implement invalidate
        raise NotImplementedError("Implement LocalityAwareCache.invalidate")


# ---------------------------------------------------------------------------
# Step 5: Cross-Shard Queries (discussion)
# ---------------------------------------------------------------------------

"""
Cross-Shard Query Patterns:

1. Fan-out Query (Scatter-Gather):
   - Send query to all N shards in parallel
   - Collect and merge results (sort, paginate, aggregate)
   - Cost: O(N) latency (bounded by slowest shard), O(N) network
   - Use when: global search, leaderboard, aggregation queries

2. Secondary Index Shard:
   - Maintain a separate shard that maps secondary key → primary shard ID
   - Two-step: lookup secondary index shard → fetch from primary shard
   - Cost: 2 round trips; consistent index maintenance complexity

3. Dual-Write Co-location:
   - Store the same data under two different partition keys
   - Example: tweet → stored under author_id AND under follower feed (fan-out on write)
   - Cost: write amplification proportional to fan-out factor
   - Twitter's home timeline: fan-out on write for <10M follower accounts

4. Avoiding Cross-Shard Joins:
   - Design partition keys to keep related entities together
   - Use compound partition keys: (tenant_id, entity_id)
   - Store foreign keys, not joined data (unless denormalization is justified)
   - Example: orders table partition key = customer_id, not order_id

5. Spanner Interleaved Tables:
   - Child rows are physically stored within parent rows (same Paxos group)
   - CREATE TABLE Orders (...) INTERLEAVE IN PARENT Users
   - User + Orders read in a single RPC with no cross-node join
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    import time

    print("Testing ShardRouter...")
    router = ShardRouter(num_shards=4)
    for i in range(4):
        router.add_shard(i, {"shard_id": i})
    shard = router.route("user:42")
    assert shard is not None
    # Same key always routes to same shard
    assert router.get_shard_id("user:42") == router.get_shard_id("user:42")
    # Different keys may land on different shards
    ids = {router.get_shard_id(f"user:{i}") for i in range(20)}
    assert len(ids) > 1, "keys should be distributed across multiple shards"
    print("  ShardRouter: OK")

    print("Testing CoLocationStore...")
    router2 = ShardRouter(num_shards=4)
    store = CoLocationStore(router2)
    # User and their orders co-located under partition key "user:1"
    store.put("user", "u1", "user:1", {"name": "Alice"})
    store.put("order", "o1", "user:1", {"product": "book", "qty": 2})
    store.put("order", "o2", "user:1", {"product": "pen", "qty": 5})
    assert store.get("user", "u1", "user:1") == {"name": "Alice"}
    orders = store.get_all("order", "user:1")
    assert len(orders) == 2, f"expected 2 orders, got {orders}"
    print("  CoLocationStore: OK")

    print("Testing DenormalizedOrderView...")
    view = DenormalizedOrderView()
    view.create_order("ord1", "u1", "p1", "Alice", "Book", 2)
    view.create_order("ord2", "u1", "p2", "Alice", "Pen", 1)
    record = view.get_order("ord1")
    assert record is not None
    assert record["user_name"] == "Alice"
    assert record["product_name"] == "Book"

    updated = view.update_user_name("u1", "Alicia")
    assert updated == 2, f"expected 2 orders updated, got {updated}"
    assert view.get_order("ord1")["user_name"] == "Alicia"
    assert view.get_order("ord2")["user_name"] == "Alicia"
    print("  DenormalizedOrderView: OK")

    print("Testing LocalityAwareCache...")
    router3 = ShardRouter(num_shards=4)
    lc = LocalityAwareCache(router3)
    lc.put("user:5", "profile", {"age": 30}, ttl=2.0)
    assert lc.get("user:5", "profile") == {"age": 30}
    lc.invalidate("user:5", "profile")
    assert lc.get("user:5", "profile") is None, "invalidated entry should be gone"
    # TTL expiry
    lc.put("user:5", "profile2", {"age": 31}, ttl=0.1)
    time.sleep(0.15)
    assert lc.get("user:5", "profile2") is None, "expired entry should be gone"
    print("  LocalityAwareCache: OK")

    print("\nAll data locality tests passed!")


if __name__ == "__main__":
    _test()
