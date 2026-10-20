"""linux-device-driver-from-scratch — stage 2 solution: character device driver

Implements character device creation, registration, file_operations wiring,
operation invocation, and stats collection.
"""

from kernel import LinuxKernel, CharacterDevice


def create_char_device(name: str, major: int, minor: int) -> dict:
        """Create a character device specification."""
        dev =    CharacterDevice(name=name, major=major, minor=minor)
        return {
                "name": dev.name,
                "major": dev.major,
                "minor": dev.minor,
                "key": f"{dev.major}:{dev.minor}",
        }


def register_device(kernel, dev_spec: dict) -> dict:
        """Register a character device with the kernel."""
        dev =    CharacterDevice(
                name=dev_spec["name"],
                major=dev_spec["major"],
                minor=dev_spec["minor"],
        )
        result = kernel.devices.register(dev)
        kernel.log.print("info", f"Char device {dev.name} registered at {dev_spec['key']}", dev.name)
        return result


def set_file_operations(kernel, dev_key: str, operations: dict) -> dict:
        """Attach file_operations to a registered device."""
        dev = kernel.devices.get(dev_key)
        if dev is None:
                return {"status": "error", "reason": "device_not_found", "key": dev_key}

        for op_name, fn in operations.items():
                dev.set_op(op_name, fn)

        kernel.log.print("info", f"Attached {len(operations)} file_operations to {dev.name}", dev.name)
        return {
                "status": "ok",
                "device": dev_key,
                "operations_attached": list(operations.keys()),
        }


def invoke_ops(kernel, dev_key: str, operations: list) -> list:
        """Invoke file_operations on a device, in order, and return results."""
        dev = kernel.devices.get(dev_key)
        if dev is None:
                return [{"status": "error", "reason": "device_not_found"}]

        results = []
        for op in operations:
                result = dev.call(op)
                results.append(result)

        return results


def get_device_stats(kernel, dev_key: str) -> dict:
        """Get statistics for a character device."""
        dev = kernel.devices.get(dev_key)
        if dev is None:
                return {"status": "error", "reason": "device_not_found"}
        return dev.stats()


if __name__ == "__main__":
        kernel = LinuxKernel()

        # 1) Create and register a character device
        spec = create_char_device("mydev", 60, 0)
        print(f"[stage 2] Device spec: {spec}")

        reg_result = register_device(kernel, spec)
        print(f"[stage 2] Device registered: {reg_result['status']} at {reg_result['key']}")

        # 2) Define file_operations
        def dev_open(**kwargs):
                return {"status": "opened"}

        def dev_read(**kwargs):
                return {"data": "hello from device"}

        def dev_write(data="", **kwargs):
                return {"bytes_written": len(data)}

        def dev_release(**kwargs):
                return {"status": "closed"}

        ops = {
                "open": dev_open,
                "read": dev_read,
                "write": dev_write,
                "release": dev_release,
        }

        set_result = set_file_operations(kernel, spec["key"], ops)
        print(f"[stage 2] Operations attached: {set_result['operations_attached']}")

        # 3) Invoke operations
        trace_result = invoke_ops(kernel, spec["key"], ["open", "write", "read", "release"])
        for r in trace_result:
                print(f"[stage 2] Op {r['op']}: {r['result']}")

        # 4) Get device stats
        stats = get_device_stats(kernel, spec["key"])
        print(f"[stage 2] Device stats: opens={stats['open_count']}, "
                    f"reads={stats['read_count']}, writes={stats['write_count']}, "
                    f"closes={stats['close_count']}")

        # 5) Verify device registry stats
        dev_stats = kernel.devices.stats()
        print(f"[stage 2] Registry: {dev_stats['device_count']} device(s), "
                    f"{dev_stats['major_count']} major(s)")

        print(f"\n[stage 2] measurement: total traces recorded="
                    f"{stats.get('open_count', 0) + stats.get('read_count', 0) + stats.get('write_count', 0)}")