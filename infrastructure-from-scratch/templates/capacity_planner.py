"""
Capacity Planner — From Scratch
=================================
An interactive capacity math calculator for system design interviews.
Learn to estimate:
- Queries per second (QPS) from DAU and usage patterns
- Peak vs average load
- Storage requirements (per day, per year)
- Bandwidth (ingress + egress)
- Cache hit ratio impact on DB load
- Number of servers needed

Learning Path:
1. Implement compute_qps() from DAU and actions/user/day
2. Implement compute_storage() from QPS and payload size
3. Implement compute_bandwidth() from QPS and payload sizes
4. Implement cache_impact() to see how caching reduces DB load
5. Implement server_count() to estimate how many servers you need
6. Run the examples and do capacity math for common system designs
"""

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Constants (memorize these for interviews)
# ---------------------------------------------------------------------------

SECONDS_PER_DAY = 86_400
SECONDS_PER_YEAR = 86_400 * 365
BYTES_PER_KB = 1_024
BYTES_PER_MB = 1_024 ** 2
BYTES_PER_GB = 1_024 ** 3
BYTES_PER_TB = 1_024 ** 4

# Rule of thumb: peak traffic ≈ 3× average (accounts for daily peaks)
PEAK_MULTIPLIER = 3


def human_bytes(n: float) -> str:
    """Format bytes as a human-readable string."""
    for unit, divisor in [("TB", BYTES_PER_TB), ("GB", BYTES_PER_GB),
                           ("MB", BYTES_PER_MB), ("KB", BYTES_PER_KB)]:
        if n >= divisor:
            return f"{n / divisor:.1f} {unit}"
    return f"{n:.0f} B"


def human_num(n: float) -> str:
    """Format a large number with K/M/B suffix."""
    for suffix, divisor in [("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if n >= divisor:
            return f"{n / divisor:.1f}{suffix}"
    return str(int(n))


# ---------------------------------------------------------------------------
# Step 1: QPS Calculator
# ---------------------------------------------------------------------------

@dataclass
class QPSResult:
    average_qps: float
    peak_qps: float
    daily_requests: float

    def __str__(self) -> str:
        return (
            f"  Daily requests:  {human_num(self.daily_requests)}\n"
            f"  Average QPS:     {self.average_qps:.1f}\n"
            f"  Peak QPS (~{PEAK_MULTIPLIER}x): {self.peak_qps:.1f}"
        )


def compute_qps(dau: int, actions_per_user_per_day: float) -> QPSResult:
    """Compute average and peak QPS from daily active users.

    TODO:
    1. daily_requests = dau * actions_per_user_per_day
    2. average_qps = daily_requests / SECONDS_PER_DAY
    3. peak_qps = average_qps * PEAK_MULTIPLIER
    4. Return QPSResult
    """
    # TODO: implement compute_qps
    raise NotImplementedError("Implement compute_qps")


# ---------------------------------------------------------------------------
# Step 2: Storage Calculator
# ---------------------------------------------------------------------------

@dataclass
class StorageResult:
    bytes_per_day: float
    bytes_per_year: float
    bytes_5_years: float

    def __str__(self) -> str:
        return (
            f"  Storage/day:    {human_bytes(self.bytes_per_day)}\n"
            f"  Storage/year:   {human_bytes(self.bytes_per_year)}\n"
            f"  Storage/5 years: {human_bytes(self.bytes_5_years)}"
        )


def compute_storage(write_qps: float, bytes_per_write: int,
                    replication_factor: int = 3) -> StorageResult:
    """Compute storage needs from write QPS and payload size.

    TODO:
    1. raw_bytes_per_day = write_qps * bytes_per_write * SECONDS_PER_DAY
    2. total_bytes_per_day = raw_bytes_per_day * replication_factor
    3. Compute per_year and 5_years
    4. Return StorageResult
    """
    # TODO: implement compute_storage
    raise NotImplementedError("Implement compute_storage")


# ---------------------------------------------------------------------------
# Step 3: Bandwidth Calculator
# ---------------------------------------------------------------------------

@dataclass
class BandwidthResult:
    ingress_bps: float   # bytes per second (writes coming in)
    egress_bps: float    # bytes per second (reads going out)

    def __str__(self) -> str:
        return (
            f"  Ingress: {human_bytes(self.ingress_bps)}/s\n"
            f"  Egress:  {human_bytes(self.egress_bps)}/s"
        )


def compute_bandwidth(read_qps: float, read_payload_bytes: int,
                      write_qps: float, write_payload_bytes: int) -> BandwidthResult:
    """Compute network bandwidth requirements.

    TODO:
    1. ingress_bps = write_qps * write_payload_bytes
    2. egress_bps = read_qps * read_payload_bytes
    3. Return BandwidthResult
    """
    # TODO: implement compute_bandwidth
    raise NotImplementedError("Implement compute_bandwidth")


# ---------------------------------------------------------------------------
# Step 4: Cache Impact
# ---------------------------------------------------------------------------

@dataclass
class CacheImpactResult:
    db_qps_without_cache: float
    db_qps_with_cache: float
    cache_qps: float
    reduction_percent: float

    def __str__(self) -> str:
        return (
            f"  Without cache:  {self.db_qps_without_cache:.1f} QPS to DB\n"
            f"  With cache:     {self.db_qps_with_cache:.1f} QPS to DB\n"
            f"  Served by cache:{self.cache_qps:.1f} QPS\n"
            f"  DB load reduced:{self.reduction_percent:.0f}%"
        )


def cache_impact(total_read_qps: float, cache_hit_ratio: float) -> CacheImpactResult:
    """Show how a cache hit ratio reduces DB load.

    TODO:
    1. db_qps_with_cache = total_read_qps * (1 - cache_hit_ratio)
    2. cache_qps = total_read_qps * cache_hit_ratio
    3. reduction_percent = cache_hit_ratio * 100
    4. Return CacheImpactResult
    """
    # TODO: implement cache_impact
    raise NotImplementedError("Implement cache_impact")


# ---------------------------------------------------------------------------
# Step 5: Server Count Estimator
# ---------------------------------------------------------------------------

@dataclass
class ServerEstimate:
    servers_needed: int
    qps_per_server: float

    def __str__(self) -> str:
        return (
            f"  QPS per server: {self.qps_per_server:.0f}\n"
            f"  Servers needed: {self.servers_needed}"
        )


def estimate_servers(peak_qps: float, avg_latency_ms: float,
                     threads_per_server: int = 100) -> ServerEstimate:
    """Estimate number of API servers needed using Little's Law.

    Little's Law: N = λ × W
      N = number of requests in system (concurrent)
      λ = arrival rate (QPS)
      W = time each request spends in system (latency in seconds)

    Concurrency needed = peak_qps * (avg_latency_ms / 1000)
    Servers = ceil(concurrency / threads_per_server)

    TODO:
    1. concurrent_requests = peak_qps * (avg_latency_ms / 1000)
    2. servers = ceil(concurrent_requests / threads_per_server)
    3. Add 20% headroom buffer: servers = ceil(servers * 1.2)
    4. Return ServerEstimate(servers, peak_qps / servers)
    """
    import math
    # TODO: implement estimate_servers using Little's Law
    raise NotImplementedError("Implement estimate_servers")


# ---------------------------------------------------------------------------
# Step 6: Full capacity plan example
# ---------------------------------------------------------------------------

def capacity_plan(name: str, dau: int, reads_per_user_per_day: float,
                  writes_per_user_per_day: float, read_payload_bytes: int,
                  write_payload_bytes: int, cache_hit_ratio: float = 0.8,
                  avg_latency_ms: float = 10.0) -> None:
    """Run a complete capacity plan and print the results.

    This calls all the functions above in sequence.
    Use this as your interview checklist.
    """
    print(f"\n{'='*60}")
    print(f"Capacity Plan: {name}")
    print(f"{'='*60}")
    print(f"Inputs: {human_num(dau)} DAU, "
          f"{reads_per_user_per_day} reads/user/day, "
          f"{writes_per_user_per_day} writes/user/day")

    read_qps = compute_qps(dau, reads_per_user_per_day)
    write_qps = compute_qps(dau, writes_per_user_per_day)

    print(f"\nRead QPS:\n{read_qps}")
    print(f"\nWrite QPS:\n{write_qps}")

    storage = compute_storage(write_qps.average_qps, write_payload_bytes)
    print(f"\nStorage (writes, 3× replication):\n{storage}")

    bw = compute_bandwidth(read_qps.average_qps, read_payload_bytes,
                           write_qps.average_qps, write_payload_bytes)
    print(f"\nBandwidth:\n{bw}")

    cache = cache_impact(read_qps.average_qps, cache_hit_ratio)
    print(f"\nCache Impact ({cache_hit_ratio*100:.0f}% hit ratio):\n{cache}")

    servers = estimate_servers(read_qps.peak_qps, avg_latency_ms)
    print(f"\nAPI Servers (for peak read load):\n{servers}")


# ---------------------------------------------------------------------------
# Self-test + example runs
# ---------------------------------------------------------------------------

def _test():
    print("Testing compute_qps...")
    r = compute_qps(dau=10_000_000, actions_per_user_per_day=10)
    assert abs(r.average_qps - 10_000_000 * 10 / SECONDS_PER_DAY) < 1
    assert abs(r.peak_qps - r.average_qps * PEAK_MULTIPLIER) < 1
    print("  compute_qps: OK")

    print("Testing compute_storage...")
    s = compute_storage(write_qps=116, bytes_per_write=1024, replication_factor=3)
    expected_day = 116 * 1024 * SECONDS_PER_DAY * 3
    assert abs(s.bytes_per_day - expected_day) < 1
    print("  compute_storage: OK")

    print("Testing compute_bandwidth...")
    b = compute_bandwidth(1160, 1024, 116, 1024)
    assert b.egress_bps == 1160 * 1024
    assert b.ingress_bps == 116 * 1024
    print("  compute_bandwidth: OK")

    print("Testing cache_impact...")
    c = cache_impact(1160, 0.8)
    assert abs(c.db_qps_with_cache - 1160 * 0.2) < 0.1
    assert c.reduction_percent == 80.0
    print("  cache_impact: OK")

    print("Testing estimate_servers...")
    sv = estimate_servers(peak_qps=3000, avg_latency_ms=50, threads_per_server=100)
    assert sv.servers_needed > 0
    print("  estimate_servers: OK")

    print("\nAll capacity planner tests passed!")


if __name__ == "__main__":
    _test()

    # Example capacity plans for common interview problems
    capacity_plan(
        name="Twitter-like Feed",
        dau=10_000_000,
        reads_per_user_per_day=20,
        writes_per_user_per_day=1,
        read_payload_bytes=500,
        write_payload_bytes=300,
        cache_hit_ratio=0.85,
        avg_latency_ms=20,
    )

    capacity_plan(
        name="YouTube-like Video Platform",
        dau=50_000_000,
        reads_per_user_per_day=5,
        writes_per_user_per_day=0.01,  # 1 upload per 100 users per day
        read_payload_bytes=5 * BYTES_PER_MB,  # 5 MB video chunks
        write_payload_bytes=500 * BYTES_PER_MB,  # 500 MB average video
        cache_hit_ratio=0.90,
        avg_latency_ms=50,
    )

    capacity_plan(
        name="URL Shortener",
        dau=1_000_000,
        reads_per_user_per_day=10,
        writes_per_user_per_day=1,
        read_payload_bytes=200,
        write_payload_bytes=500,
        cache_hit_ratio=0.80,
        avg_latency_ms=5,
    )
