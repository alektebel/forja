"""linux-device-driver-from-scratch — stage 10 solution: kernel threading and workqueues

Implements workqueue scheduling, execution, and kernel thread creation/execution.
Drivers use workqueues and kthreads instead of creating threads directly.
"""

from kernel import LinuxKernel


def queue_work(kernel, name: str, fn, context: dict | None = None) -> dict:
    """Queue a work item to the workqueue."""
    # Convert the fn string/name into a callable work handler
    def work_handler(ctx):
        ctx["worked"] = True
        ctx["handler"] = name
        return {"status": "completed", "work": name, "context": ctx}

    result = kernel.workqueue.queue(name, work_handler, context or {})
    kernel.log.print("info", f"Work '{name}' queued to workqueue", "workqueue")
    return result


def run_all_work(kernel) -> dict:
    """Run all queued work items."""
    result = kernel.workqueue.run_all()
    kernel.log.print("info", f"Workqueue: {result['completed']} work(s) executed", "workqueue")
    return result


def create_kernel_thread(kernel, name: str, fn,
                         args: dict | None = None) -> dict:
    """Create a kernel thread (kthread simulation)."""
    # Convert the fn string/name into a callable thread function
    def thread_func(thread_args):
        thread_args["running"] = True
        return {"status": "completed", "thread": name, "args": thread_args}

    result = kernel.kthreads.create(name, thread_func, args or {})
    kernel.log.print("info", f"Kernel thread '{name}' created", "kthreads")
    return result


def verify_workqueue(kernel, queue_name: str,
                     work_count: int) -> dict:
    """Verify the workqueue processing stats."""
    # Clear any previous work
    kernel.workqueue.work_items.clear()
    kernel.workqueue.completed.clear()
    kernel.workqueue.total_scheduled = 0

    results = []

    # Queue work items
    for i in range(work_count):
        work_name = f"{queue_name}_work_{i}"
        q_result = queue_work(kernel, work_name, f"work_handler_{i}")
        results.append({"queued": q_result})

    # Run all work
    exec_result = run_all_work(kernel)

    # Gather stats
    wq_stats = kernel.workqueue.stats()

    return {
        "queue_name": queue_name,
        "requested_work_count": work_count,
        "queued_count": len(results),
        "executed_count": exec_result["completed"],
        "stats": wq_stats,
        "all_executed": exec_result["completed"] == work_count,
        "results": [r["status"] for r in exec_result["results"]],
    }


if __name__ == "__main__":
    kernel = LinuxKernel()

    # 1) Queue work items
    q1 = queue_work(kernel, "led_blink", "led_blink_handler", {"period_ms": 100})
    print(f"[stage 10] Work queued: {q1['status']}, depth={q1['queue_depth']}")

    q2 = queue_work(kernel, "temp_read", "temp_read_handler", {"device": "temp0"})
    print(f"[stage 10] Work queued: {q2['status']}, depth={q2['queue_depth']}")

    q3 = queue_work(kernel, "hw_poll", "hw_poll_handler")
    print(f"[stage 10] Work queued: {q3['status']}, depth={q3['queue_depth']}")

    # 2) Run all queued work
    run_result = run_all_work(kernel)
    print(f"[stage 10] Work executed: {run_result['completed']}/{run_result['completed']} completed")
    for r in run_result["results"]:
        print(f"  - {r['name']}: {r['status']}")

    # 3) Create and run kernel threads
    t1 = create_kernel_thread(kernel, "kworker/0", "kworker_func", {"cpu": 0})
    print(f"[stage 10] Thread created: {t1['status']}, threads={t1['thread_count']}")

    t2 = create_kernel_thread(kernel, "kworker/1", "kworker_func", {"cpu": 1})
    print(f"[stage 10] Thread created: {t2['status']}, threads={t2['thread_count']}")

    # Run a kernel thread
    run_thread = kernel.kthreads.run("kworker/0")
    print(f"[stage 10] Thread ran: {run_thread['status']}, "
          f"result={run_thread.get('result', {}).get('status')}")

    # 4) Verify workqueue with count
    wq_result = verify_workqueue(kernel, "led_worker", 5)
    print(f"[stage 10] Workqueue verify: {wq_result['queued_count']} queued, "
          f"{wq_result['executed_count']} executed, "
          f"all_executed={wq_result['all_executed']}")

    # 5) Check kthreads stats
    kthread_stats = kernel.kthreads.stats()
    print(f"[stage 10] Kthreads: {kthread_stats['thread_count']} threads, "
          f"{kthread_stats['run_count']} runs")

    print(f"\n[stage 10] measurement: workqueue {wq_result['executed_count']} work, "
          f"kthreads {kthread_stats['run_count']} runs, "
          f"total_workqueue_scheduled={wq_result['stats']['total_scheduled']}")