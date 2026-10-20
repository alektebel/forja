"""
Capacity Planner — Complete Solution
"""

import math
from dataclasses import dataclass
from typing import Optional

SECONDS_PER_DAY = 86_400
SECONDS_PER_YEAR = 86_400 * 365
BYTES_PER_KB = 1_024
BYTES_PER_MB = 1_024 ** 2
BYTES_PER_GB = 1_024 ** 3
BYTES_PER_TB = 1_024 ** 4
PEAK_MULTIPLIER = 3


def human_bytes(n: float) -> str:
    for unit, divisor in [("TB", BYTES_PER_TB), ("GB", BYTES_PER_GB),
                           ("MB", BYTES_PER_MB), ("KB", BYTES_PER_KB)]:
        if n >= divisor:
            return f"{n / divisor:.1f} {unit}"
    return f"{n:.0f} B"


def human_num(n: float) -> str:
    for suffix, divisor in [("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if n >= divisor:
            return f"{n / divisor:.1f}{suffix}"
    return str(int(n))


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
    daily = dau * actions_per_user_per_day
    avg = daily / SECONDS_PER_DAY
    return QPSResult(average_qps=avg, peak_qps=avg * PEAK_MULTIPLIER, daily_requests=daily)


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
    per_day = write_qps * bytes_per_write * SECONDS_PER_DAY * replication_factor
    per_year = per_day * 365
    return StorageResult(bytes_per_day=per_day, bytes_per_year=per_year, bytes_5_years=per_year * 5)


@dataclass
class BandwidthResult:
    ingress_bps: float
    egress_bps: float

    def __str__(self) -> str:
        return (
            f"  Ingress: {human_bytes(self.ingress_bps)}/s\n"
            f"  Egress:  {human_bytes(self.egress_bps)}/s"
        )


def compute_bandwidth(read_qps: float, read_payload_bytes: int,
                      write_qps: float, write_payload_bytes: int) -> BandwidthResult:
    return BandwidthResult(
        ingress_bps=write_qps * write_payload_bytes,
        egress_bps=read_qps * read_payload_bytes,
    )


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
    db_qps = total_read_qps * (1 - cache_hit_ratio)
    cache_qps = total_read_qps * cache_hit_ratio
    return CacheImpactResult(
        db_qps_without_cache=total_read_qps,
        db_qps_with_cache=db_qps,
        cache_qps=cache_qps,
        reduction_percent=cache_hit_ratio * 100,
    )


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
    concurrent = peak_qps * (avg_latency_ms / 1000.0)
    servers = math.ceil(concurrent / threads_per_server)
    servers = math.ceil(servers * 1.2)  # 20% headroom
    servers = max(servers, 1)
    return ServerEstimate(servers_needed=servers, qps_per_server=peak_qps / servers)


def capacity_plan(name: str, dau: int, reads_per_user_per_day: float,
                  writes_per_user_per_day: float, read_payload_bytes: int,
                  write_payload_bytes: int, cache_hit_ratio: float = 0.8,
                  avg_latency_ms: float = 10.0) -> None:
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
        name="URL Shortener",
        dau=1_000_000,
        reads_per_user_per_day=10,
        writes_per_user_per_day=1,
        read_payload_bytes=200,
        write_payload_bytes=500,
        cache_hit_ratio=0.80,
        avg_latency_ms=5,
    )
