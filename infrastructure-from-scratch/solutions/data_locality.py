"""
Data Locality — Complete Solution
"""

import hashlib
import time
import threading
from typing import Any, Dict, List, Optional, Tuple


class ShardRouter:
    def __init__(self, num_shards: int):
        self.num_shards = num_shards
        self._shards: Dict[int, Any] = {}

    def get_shard_id(self, partition_key: str) -> int:
        return int(hashlib.md5(partition_key.encode()).hexdigest(), 16) % self.num_shards

    def add_shard(self, shard_id: int, shard: Any) -> None:
        self._shards[shard_id] = shard

    def route(self, partition_key: str) -> Any:
        return self._shards[self.get_shard_id(partition_key)]


class CoLocationStore:
    def __init__(self, router: ShardRouter):
        self._router = router
        for shard_id in range(router.num_shards):
            router.add_shard(shard_id, {})

    def put(self, entity_type: str, entity_id: str, partition_key: str, data: Any) -> None:
        shard = self._router.route(partition_key)
        shard.setdefault(entity_type, {})[entity_id] = data

    def get(self, entity_type: str, entity_id: str, partition_key: str) -> Optional[Any]:
        shard = self._router.route(partition_key)
        return shard.get(entity_type, {}).get(entity_id)

    def get_all(self, entity_type: str, partition_key: str) -> List[Any]:
        shard = self._router.route(partition_key)
        return list(shard.get(entity_type, {}).values())


class DenormalizedOrderView:
    def __init__(self):
        self._orders: Dict[str, Dict] = {}
        self._user_orders: Dict[str, List[str]] = {}

    def create_order(self, order_id: str, user_id: str, product_id: str,
                     user_name: str, product_name: str, quantity: int) -> None:
        self._orders[order_id] = {
            "order_id": order_id,
            "user_id": user_id,
            "product_id": product_id,
            "user_name": user_name,
            "product_name": product_name,
            "quantity": quantity,
        }
        self._user_orders.setdefault(user_id, []).append(order_id)

    def get_order(self, order_id: str) -> Optional[Dict]:
        return self._orders.get(order_id)

    def update_user_name(self, user_id: str, new_name: str) -> int:
        order_ids = self._user_orders.get(user_id, [])
        for oid in order_ids:
            if oid in self._orders:
                self._orders[oid]["user_name"] = new_name
        return len(order_ids)


class LocalityAwareCache:
    def __init__(self, router: ShardRouter):
        self._router = router
        import time as _time
        self._time = _time
        self._caches: Dict[int, Dict[str, Tuple[Any, float]]] = {
            i: {} for i in range(router.num_shards)
        }

    def _shard_cache(self, partition_key: str) -> Dict[str, Tuple[Any, float]]:
        shard_id = self._router.get_shard_id(partition_key)
        return self._caches[shard_id]

    def get(self, partition_key: str, entity_key: str) -> Optional[Any]:
        cache = self._shard_cache(partition_key)
        entry = cache.get(entity_key)
        if entry is None:
            return None
        value, expires_at = entry
        if self._time.time() > expires_at:
            del cache[entity_key]
            return None
        return value

    def put(self, partition_key: str, entity_key: str, value: Any,
            ttl: float = 60.0) -> None:
        cache = self._shard_cache(partition_key)
        cache[entity_key] = (value, self._time.time() + ttl)

    def invalidate(self, partition_key: str, entity_key: str) -> None:
        cache = self._shard_cache(partition_key)
        cache.pop(entity_key, None)


def _test():
    print("Testing ShardRouter...")
    router = ShardRouter(num_shards=4)
    for i in range(4):
        router.add_shard(i, {"shard_id": i})
    assert router.route("user:42") is not None
    assert router.get_shard_id("user:42") == router.get_shard_id("user:42")
    ids = {router.get_shard_id(f"user:{i}") for i in range(20)}
    assert len(ids) > 1
    print("  ShardRouter: OK")

    print("Testing CoLocationStore...")
    router2 = ShardRouter(num_shards=4)
    store = CoLocationStore(router2)
    store.put("user", "u1", "user:1", {"name": "Alice"})
    store.put("order", "o1", "user:1", {"product": "book", "qty": 2})
    store.put("order", "o2", "user:1", {"product": "pen", "qty": 5})
    assert store.get("user", "u1", "user:1") == {"name": "Alice"}
    orders = store.get_all("order", "user:1")
    assert len(orders) == 2
    print("  CoLocationStore: OK")

    print("Testing DenormalizedOrderView...")
    view = DenormalizedOrderView()
    view.create_order("ord1", "u1", "p1", "Alice", "Book", 2)
    view.create_order("ord2", "u1", "p2", "Alice", "Pen", 1)
    record = view.get_order("ord1")
    assert record["user_name"] == "Alice"
    assert record["product_name"] == "Book"
    updated = view.update_user_name("u1", "Alicia")
    assert updated == 2
    assert view.get_order("ord1")["user_name"] == "Alicia"
    assert view.get_order("ord2")["user_name"] == "Alicia"
    print("  DenormalizedOrderView: OK")

    print("Testing LocalityAwareCache...")
    router3 = ShardRouter(num_shards=4)
    lc = LocalityAwareCache(router3)
    lc.put("user:5", "profile", {"age": 30}, ttl=2.0)
    assert lc.get("user:5", "profile") == {"age": 30}
    lc.invalidate("user:5", "profile")
    assert lc.get("user:5", "profile") is None
    lc.put("user:5", "profile2", {"age": 31}, ttl=0.1)
    time.sleep(0.15)
    assert lc.get("user:5", "profile2") is None
    print("  LocalityAwareCache: OK")

    print("\nAll data locality tests passed!")


if __name__ == "__main__":
    _test()
