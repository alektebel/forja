"""linux-device-driver-from-scratch — stage 3 solution: kernel memory management

Implements kernel memory allocation (kmalloc), freeing (kfree), read/write
access, and memory statistics.
"""

from kernel import LinuxKernel


def allocate_memory(kernel, size: int, name: str = "anon") -> dict:
    """Allocate kernel memory (kmalloc simulation)."""
    result = kernel.memory.allocate(size, name)
    if result.get("status") == "allocated":
        kernel.log.print("info", f"Allocated {size} bytes at 0x{result['addr']:x} ({name})", "memory")
    else:
        kernel.log.print("err", f"Memory allocation failed: {result}", "memory")
    return result


def free_memory(kernel, name: str) -> dict:
    """Free kernel memory (kfree simulation)."""
    result = kernel.memory.free(name)
    if result.get("status") == "freed":
        kernel.log.print("info", f"Freed memory '{name}'", "memory")
    else:
        kernel.log.print("err", f"Free failed: {result.get('reason', 'unknown')}", "memory")
    return result


def read_write_memory(kernel, name: str, offset: int,
                      write_data: str = "", read_len: int = 0) -> dict:
    """Read from or write to a memory allocation."""
    result = {}

    if write_data:
        bytes_written = kernel.memory.write(name, offset, write_data)
        if bytes_written == -1:
            result = {"status": "error", "reason": "memory_not_found_or_freed"}
        else:
            result = {"status": "written", "bytes": bytes_written, "offset": offset}
            kernel.log.print("info", f"Wrote {bytes_written} bytes to '{name}' at offset {offset}", "memory")
    else:
        hex_data = kernel.memory.read(name, offset, read_len)
        if not hex_data:
            result = {"status": "error", "reason": "memory_not_found_or_freed"}
        else:
            result = {"status": "read", "data": hex_data, "offset": offset, "length": read_len}
            kernel.log.print("info", f"Read {len(hex_data)//2} bytes from '{name}' at offset {offset}", "memory")

    return result


def get_memory_stats(kernel) -> dict:
    """Get memory manager statistics."""
    stats = kernel.memory.stats()
    kernel.log.print("info", f"Memory stats: {stats['region_count']} regions, "
                     f"{stats['total_allocated']} bytes allocated", "memory")
    return stats


if __name__ == "__main__":
    kernel = LinuxKernel()

    # 1) Allocate memory
    alloc1 = allocate_memory(kernel, 64, "buffer1")
    print(f"[stage 3] Allocated buffer1: addr=0x{alloc1['addr']:x}, size={alloc1['size']}")

    alloc2 = allocate_memory(kernel, 128, "buffer2")
    print(f"[stage 3] Allocated buffer2: addr=0x{alloc2['addr']:x}, size={alloc2['size']}")

    alloc3 = allocate_memory(kernel, 32, "buffer3")
    print(f"[stage 3] Allocated buffer3: addr=0x{alloc3['addr']:x}, size={alloc3['size']}")

    # 2) Write and read data
    hw = "deadbeef"  # hex data
    write_result = read_write_memory(kernel, "buffer1", 0, write_data=hw)
    print(f"[stage 3] Write result: {write_result}")

    read_result = read_write_memory(kernel, "buffer1", 0, read_len=4)
    print(f"[stage 3] Read result: {read_result}")

    # 3) Check stats
    stats = get_memory_stats(kernel)
    print(f"[stage 3] Memory: {stats['region_count']} regions, "
          f"{stats['total_allocated']} bytes total")

    # 4) Free one buffer and verify
    free_result = free_memory(kernel, "buffer2")
    print(f"[stage 3] Freed buffer2: {free_result['status']}")

    stats_after = get_memory_stats(kernel)
    print(f"[stage 3] After free: {stats_after['region_count']} regions, "
          f"{stats_after['total_allocated']} bytes total")

    # 5) Verify double-free protection
    double_free = free_memory(kernel, "buffer2")
    print(f"[stage 3] Double-free protection: {double_free['status']} ({double_free['reason']})")

    # 6) Read from freed memory (should fail)
    read_freed = read_write_memory(kernel, "buffer2", 0, read_len=4)
    print(f"[stage 3] Read after free: {read_freed['status']}")

    print(f"\n[stage 3] measurement: final allocated={stats_after['total_allocated']} bytes, "
          f"regions={stats_after['region_count']}")