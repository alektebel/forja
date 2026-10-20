"""linux-device-driver-from-scratch — stage 12 solution: synchronization primitives

Implements kernel synchronization: spinlocks, mutexes, semaphores, and RCU.
A driver that accesses shared data without proper synchronization corrupts state.
"""

from kernel import LinuxKernel


def spin_lock(kernel, name: str) -> dict:
    """Acquire a spinlock."""
    result = kernel.sync.spin_lock(name)
    kernel.log.print("info", f"Spinlock '{name}' acquired", "sync")
    return result


def spin_unlock(kernel, name: str) -> dict:
    """Release a spinlock."""
    result = kernel.sync.spin_unlock(name)
    kernel.log.print("info", f"Spinlock '{name}' released", "sync")
    return result


def mutex_lock(kernel, name: str) -> dict:
    """Acquire a mutex."""
    result = kernel.sync.mutex_lock(name)
    kernel.log.print("info", f"Mutex '{name}' acquired", "sync")
    return result


def mutex_unlock(kernel, name: str) -> dict:
    """Release a mutex."""
    result = kernel.sync.mutex_unlock(name)
    kernel.log.print("info", f"Mutex '{name}' released", "sync")
    return result


def sema_init(kernel, name: str, value: int = 1) -> dict:
    """Initialize a semaphore."""
    result = kernel.sync.sema_init(name, value)
    kernel.log.print("info", f"Sema '{name}' initialized with value {value}", "sync")
    return result


def sema_down(kernel, name: str) -> dict:
    """Down (wait on) a semaphore."""
    result = kernel.sync.sema_down(name)
    if result.get("status") == "down":
        kernel.log.print("info", f"Sema '{name}' down (value={result['value']})", "sync")
    return result


def sema_up(kernel, name: str) -> dict:
    """Up (signal) a semaphore."""
    result = kernel.sync.sema_up(name)
    if result.get("status") == "up":
        kernel.log.print("info", f"Sema '{name}' up (value={result['value']})", "sync")
    return result


def verify_sync(kernel, name: str, lock_type: str,
                expected_pairs: int) -> dict:
    """Verify that sync primitives have correct pair usage."""
    kernel.log.print("info", f"Verifying sync: {lock_type} '{name}', {expected_pairs} pairs", "sync")

    # Clear any previous state for this primitive name
    if lock_type == "spinlock":
        kernel.sync.spins.pop(name, None)
    elif lock_type == "mutex":
        kernel.sync.mutexes.pop(name, None)
    elif lock_type == "semaphore":
        kernel.sync.semaphores.pop(name, None)

    results = {
        "lock_type": lock_type,
        "name": name,
        "expected_pairs": expected_pairs,
        "operations": [],
    }

    # Perform the expected pairs of lock/unlock operations
    for i in range(expected_pairs):
        pair_ops = []

        if lock_type == "spinlock":
            lock_r = spin_lock(kernel, name)
            pair_ops.append({"op": "lock", "status": lock_r["status"]})
            unlock_r = spin_unlock(kernel, name)
            pair_ops.append({"op": "unlock", "status": unlock_r["status"]})

        elif lock_type == "mutex":
            lock_r = mutex_lock(kernel, name)
            pair_ops.append({"op": "lock", "status": lock_r["status"]})
            unlock_r = mutex_unlock(kernel, name)
            pair_ops.append({"op": "unlock", "status": unlock_r["status"]})

        elif lock_type == "semaphore":
            if i == 0:
                init_r = sema_init(kernel, name, value=expected_pairs)
                pair_ops.append({"op": "init", "value": expected_pairs})

            down_r = sema_down(kernel, name)
            pair_ops.append({"op": "down", "status": down_r["status"], "value": down_r.get("value")})
            up_r = sema_up(kernel, name)
            pair_ops.append({"op": "up", "status": up_r["status"], "value": up_r.get("value")})

        results["operations"].append(pair_ops)

    # Gather final stats
    sync_stats = kernel.sync.stats()
    results["final_stats"] = sync_stats

    # Verify correct pairs were made
    all_success = all(
        all(op.get("status") in ("locked", "unlocked", "down", "up", "initialized")
            for op in pair)
        for pair in results["operations"]
    )
    results["all_operations_success"] = all_success

    return results


if __name__ == "__main__":
    kernel = LinuxKernel()

    # 1) Spinlock
    sl_lock = spin_lock(kernel, "my_spinlock")
    print(f"[stage 12] Spinlock: {sl_lock['status']}")

    sl_unlock = spin_unlock(kernel, "my_spinlock")
    print(f"[stage 12] Spinlock unlocked: {sl_unlock['status']}")

    # Try double lock (should fail)
    sl_lock2 = spin_lock(kernel, "my_spinlock")
    print(f"[stage 12] Double lock: {sl_lock2['status']} ({sl_lock2.get('reason', '')})")

    # 2) Mutex
    m_lock = mutex_lock(kernel, "my_mutex")
    print(f"[stage 12] Mutex: {m_lock['status']}")

    m_unlock = mutex_unlock(kernel, "my_mutex")
    print(f"[stage 12] Mutex unlocked: {m_unlock['status']}")

    # 3) Semaphore
    s_init = sema_init(kernel, "my_sema", value=2)
    print(f"[stage 12] Sema init: {s_init['status']}, value={s_init['value']}")

    s_down1 = sema_down(kernel, "my_sema")
    print(f"[stage 12] Sema down 1: {s_down1['status']}, value={s_down1['value']}")

    s_down2 = sema_down(kernel, "my_sema")
    print(f"[stage 12] Sema down 2: {s_down2['status']}, value={s_down2['value']}")

    s_down3 = sema_down(kernel, "my_sema")  # should fail (count=0)
    print(f"[stage 12] Sema down 3 (expect fail): {s_down3['status']}")

    s_up1 = sema_up(kernel, "my_sema")
    print(f"[stage 12] Sema up 1: {s_up1['status']}, value={s_up1['value']}")

    # 4) RCU
    rcu_lock = kernel.sync.rcu_read_lock()
    print(f"[stage 12] RCU read lock: {rcu_lock['status']}, readers={rcu_lock['readers']}")

    rcu_unlock = kernel.sync.rcu_read_unlock()
    print(f"[stage 12] RCU read unlock: {rcu_unlock['status']}, readers={rcu_unlock['readers']}")

    # 5) Verify synchronization patterns
    sl_verify = verify_sync(kernel, "verified_spinlock", "spinlock", 3)
    print(f"[stage 12] Spinlock verify: {sl_verify['expected_pairs']} pairs, "
          f"all_success={sl_verify['all_operations_success']}")

    m_verify = verify_sync(kernel, "verified_mutex", "mutex", 3)
    print(f"[stage 12] Mutex verify: {m_verify['expected_pairs']} pairs, "
          f"all_success={m_verify['all_operations_success']}")

    s_verify = verify_sync(kernel, "verified_sema", "semaphore", 3)
    print(f"[stage 12] Semaphore verify: {s_verify['expected_pairs']} pairs, "
          f"all_success={s_verify['all_operations_success']}")

    # 6) Final sync stats
    sync_stats = kernel.sync.stats()
    print(f"[stage 12] Final sync stats: {sync_stats}")

    print(f"\n[stage 12] measurement: history_entries={sync_stats['total_history']}, "
          f"spinlocks_total={sync_stats['spinlocks_total']}, "
          f"mutexes_total={sync_stats['mutexes_total']}")