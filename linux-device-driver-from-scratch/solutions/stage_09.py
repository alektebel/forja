"""linux-device-driver-from-scratch — stage 9 solution: wait queues and polling

Implements wait queue polling, event waking, and the full poll-wake-poll cycle
that userspace drivers use to avoid busy-waiting.
"""

from kernel import LinuxKernel


def poll_device(kernel, fd: int, expected_mask: str) -> dict:
    """Check if a device is ready for the expected operation (poll simulation)."""
    result = kernel.waitqueue.poll(fd, expected_mask)
    kernel.log.print("info", f"poll(fd={fd}, {expected_mask}): "
                     f"{'ready' if result['ready'] else 'not ready'}", "waitqueue")
    return result


def wake_event(kernel, event: str) -> dict:
    """Wake the wait queue with an event (wake_up simulation)."""
    result = kernel.waitqueue.wake(event)
    kernel.log.print("info", f"Wake event: {event}", "waitqueue")
    return result


def verify_poll_wake_cycle(kernel, fd: int, expected_mask: str,
                           wake_event_name: str) -> dict:
    """Verify the full poll-wake cycle: poll -> wait -> wake -> poll."""
    # Clear any previous state
    kernel.waitqueue.events.clear()
    kernel.waitqueue.poll_calls.clear()

    steps = []

    # Step 1: Poll before wake (should be not ready)
    poll_before = poll_device(kernel, fd, expected_mask)
    steps.append({
        "step": "poll_before_wake",
        "ready": poll_before["ready"],
    })

    # Step 2: Wake the event
    wake_result = wake_event(kernel, wake_event_name)
    steps.append({
        "step": "wake_event",
        "event": wake_event_name,
    })

    # Step 3: Poll after wake (should be ready)
    poll_after = poll_device(kernel, fd, expected_mask)
    steps.append({
        "step": "poll_after_wake",
        "ready": poll_after["ready"],
    })

    # Gather stats
    waitqueue_stats = kernel.waitqueue.stats()

    return {
        "fd": fd,
        "expected_mask": expected_mask,
        "wake_event": wake_event_name,
        "steps": steps,
        "poll_won": not poll_before["ready"] and poll_after["ready"],
        "waitqueue_stats": waitqueue_stats,
    }


if __name__ == "__main__":
    kernel = LinuxKernel()

    # 1) Poll before wake (should fail)
    poll1 = poll_device(kernel, 3, "POLLIN")
    print(f"[stage 9] Poll (no wake yet): fd=3, POLLIN, ready={poll1['ready']}")

    # 2) Wake the event
    wake1 = wake_event(kernel, "data_ready")
    print(f"[stage 9] Woke: {wake1['event']}")

    # 3) Poll after wake (should succeed)
    poll2 = poll_device(kernel, 3, "POLLIN")
    print(f"[stage 9] Poll (after wake): fd=3, POLLIN, ready={poll2['ready']}")

    # 4) Full poll-wake cycle verification
    cycle = verify_poll_wake_cycle(kernel, 7, "POLLOUT", "buffer_available")
    print(f"[stage 9] Cycle: poll_before={cycle['steps'][0]['ready']}, "
          f"poll_after={cycle['steps'][2]['ready']}, "
          f"poll_won={cycle['poll_won']}")

    # 5) Check waitqueue stats
    wq_stats = kernel.waitqueue.stats()
    print(f"[stage 9] Waitqueue stats: {wq_stats['wake_count']} wakes, "
          f"{wq_stats['poll_calls']} polls, "
          f"events={wq_stats['pending_events']}")

    print(f"\n[stage 9] measurement: {wq_stats['wake_count']} wake events, "
          f"{wq_stats['poll_calls']} poll calls, "
          f"poll success rate: {cycle['poll_won']}")