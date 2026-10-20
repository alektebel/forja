"""linux-device-driver-from-scratch — stage 5 solution: interrupt handling

Implements interrupt registration, freeing, hardware interrupt simulation,
and full interrupt lifecycle verification.
"""

from kernel import LinuxKernel


def request_irq(kernel, irq: int, handler_name: str, flags: str = "",
                device: str = "") -> dict:
    """Register an interrupt handler (request_irq simulation)."""
    # Create a simple handler function
    def handler(irq_num, dev_name=""):
        kernel.log.print("info", f"IRQ {irq_num} triggered{f' on {dev_name}' if dev_name else ''}", "irq")

    result = kernel.irqs.request_irq(irq, handler, handler_name, flags, device)
    kernel.log.print("info", f"IRQ {irq} registered as '{handler_name}'{f' ({flags})' if flags else ''}", "irq")
    return result


def free_irq(kernel, irq: int, name: str) -> dict:
    """Unregister an interrupt handler (free_irq simulation)."""
    result = kernel.irqs.free_irq(irq, name)
    kernel.log.print("info", f"IRQ {irq} freed '{name}': {result.get('status')}", "irq")
    return result


def raise_irq(kernel, irq: int) -> dict:
    """Simulate hardware interrupt firing."""
    result = kernel.irqs.raise_irq(irq)
    if result.get("status") == "routed":
        kernel.log.print("info", f"IRQ {irq} fired, {result['handlers_called']} handler(s) called", "irq")
    else:
        kernel.log.print("err", f"IRQ {irq} raise failed: {result.get('reason')}", "irq")
    return result


def verify_irq_lifecycle(kernel, irq: int, sequence: list) -> dict:
    """Verify the full interrupt lifecycle: register -> fire -> unregister."""
    results = []

    for step in sequence:
        action = step["action"]

        if action == "request":
            name = step.get("handler_name", f"handler_{irq}")
            flags = step.get("flags", "")
            device = step.get("device", "")
            r = request_irq(kernel, irq, name, flags, device)
            results.append({"step": "request_irq", "result": r})

        elif action == "raise":
            r = raise_irq(kernel, irq)
            results.append({"step": "raise_irq", "result": r})

        elif action == "free":
            name = step.get("handler_name", f"handler_{irq}")
            r = free_irq(kernel, irq, name)
            results.append({"step": "free_irq", "result": r})

    # Gather final stats
    irq_stats = kernel.irqs.stats()

    return {
        "irq": irq,
        "sequence_results": results,
        "final_stats": irq_stats,
        "total_routed": irq_stats.get("total_routed", 0),
    }


if __name__ == "__main__":
    kernel = LinuxKernel()

    # 1) Register an interrupt handler
    req_result = request_irq(kernel, 5, "my_irq_handler", device="mydev")
    print(f"[stage 5] IRQ 5 registered: {req_result['status']}")

    # 2) Raise the interrupt (simulate hardware)
    raise_result = raise_irq(kernel, 5)
    print(f"[stage 5] IRQ 5 fired: {raise_result['status']}, "
          f"{raise_result['handlers_called']} handler(s) called")

    # 3) Raise again
    raise_result2 = raise_irq(kernel, 5)
    print(f"[stage 5] IRQ 5 fired again: {raise_result2['status']}")

    # 4) Free the interrupt
    free_result = free_irq(kernel, 5, "my_irq_handler")
    print(f"[stage 5] IRQ 5 freed: {free_result['status']}")

    # 5) Try raising a freed IRQ (should fail)
    raise_freed = raise_irq(kernel, 5)
    print(f"[stage 5] Raise freed IRQ: {raise_freed['status']} ({raise_freed['reason']})")

    # 6) Full lifecycle verification
    lifecycle_result = verify_irq_lifecycle(kernel, 10, [
        {"action": "request", "handler_name": "lifecycle_handler", "flags": ""},
        {"action": "raise"},
        {"action": "raise"},
        {"action": "free", "handler_name": "lifecycle_handler"},
    ])
    print(f"[stage 5] Lifecycle: {lifecycle_result['total_routed']} IRQs routed "
          f"across {len(lifecycle_result['sequence_results'])} steps")

    # 7) Check final stats
    final_stats = kernel.irqs.stats()
    print(f"[stage 5] Final IRQ stats: {final_stats}")

    print(f"\n[stage 5] measurement: total_routed={final_stats['total_routed']}, "
          f"per_irq={final_stats['per_irq']}")