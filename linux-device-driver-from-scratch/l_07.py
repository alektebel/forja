"""linux-device-driver-from-scratch — stage 7 solution: device resources and memory mapping

Implements platform device resource management: creating devices with resources,
looking up resources by type and index, and verifying device resource configuration.
"""

from kernel import LinuxKernel, PlatformDevice


def create_platform_device_with_resources(kernel, name: str, resources: list,
                                                                                     irq: int = 0) -> dict:
        """Create a platform device with memory/register resources."""
        # Extract addresses and sizes from resource dicts
        resource_addrs = []
        resource_sizes = []
        for res in resources:
                if "addr" in res:
                        resource_addrs.append(res["addr"])
                if "size" in res:
                        resource_sizes.append(res["size"])

        dev =    PlatformDevice(
                name=name,
                resource_addrs=resource_addrs,
                resource_sizes=resource_sizes,
                irq=irq,
        )

        # Store resource metadata for lookup by type
        dev.data = resources    # platform device data field stores resource details

        result = kernel.platform.register_device(dev)

        kernel.log.print("info", f"Platform device {name} created with {len(resources)} resources", "platform")
        return {
                "status": result["status"],
                "device": name,
                "resource_count": len(resources),
                "resources": resources,
                "irq": irq,
        }


def get_resource(kernel, device_name: str, res_type: str, index: int = 0) -> dict:
        """Get a resource from a platform device (platform_get_resource simulation)."""
        dev = kernel.platform.devices.get(device_name)
        if dev is None:
                return {"status": "error", "reason": "device_not_found", "device": device_name}

        resources = dev.data
        if resources is None:
                return {"status": "error", "reason": "no_resources", "device": device_name}

        # Filter resources by type
        matching = [r for r in resources if r.get("type") == res_type]

        if index >= len(matching):
                return {
                        "status": "error",
                        "reason": "index_out_of_range",
                        "device": device_name,
                        "type": res_type,
                        "index": index,
                        "available": len(matching),
                }

        resource = matching[index]
        kernel.log.print("info", f"Got {res_type} resource[{index}] from {device_name}: "
                                         f"addr=0x{resource.get('addr', 0):x}, size={resource.get('size', 0)}", "platform")
        return {
                "status": "found",
                "device": device_name,
                "type": res_type,
                "index": index,
                "resource": resource,
        }


def verify_device_resources(kernel, device_name: str,
                                                        expected_resources: list) -> dict:
        """Verify that a device has the expected resources."""
        dev = kernel.platform.devices.get(device_name)
        if dev is None:
                return {
                        "status": "error",
                        "reason": "device_not_found",
                        "device": device_name,
                }

        actual_resources = dev.data
        if actual_resources is None:
                return {
                        "status": "error",
                        "reason": "no_resources_found",
                        "device": device_name,
                }

        # Verify each expected resource exists
        checks = []
        all_match = True

        for expected in expected_resources:
                found = False
                for actual in actual_resources:
                        if (actual.get("type") == expected.get("type") and
                                        actual.get("addr") == expected.get("addr") and
                                        actual.get("size") == expected.get("size")):
                                found = True
                                break

                checks.append({
                        "expected": expected,
                        "found": found,
                })
                if not found:
                        all_match = False

        return {
                "status": "verified" if all_match else "mismatch",
                "device": device_name,
                "expected_count": len(expected_resources),
                "actual_count": len(actual_resources),
                "all_match": all_match,
                "checks": checks,
        }


if __name__ == "__main__":
        kernel = LinuxKernel()

        # 1) Create a platform device with resources
        resources = [
                {"type": "mem", "addr": 0x1000, "size": 256},
                {"type": "mem", "addr": 0x2000, "size": 128},
                {"type": "irq", "addr": 5, "size": 0},
        ]

        dev_result = create_platform_device_with_resources(kernel, "mydev", resources, irq=5)
        print(f"[stage 7] Device created: {dev_result['status']}, "
                    f"{dev_result['resource_count']} resources")

        # 2) Get first memory resource
        mem_res = get_resource(kernel, "mydev", "mem", index=0)
        print(f"[stage 7] mem[0]: addr=0x{mem_res['resource']['addr']:x}, "
                    f"size={mem_res['resource']['size']}")

        # 3) Get first IRQ resource
        irq_res = get_resource(kernel, "mydev", "irq", index=0)
        print(f"[stage 7] irq[0]: addr={irq_res['resource'].get('addr')}, "
                    f"size={irq_res['resource'].get('size')}")

        # 4) Verify all expected resources
        verify_result = verify_device_resources(kernel, "mydev", resources)
        print(f"[stage 7] Verification: {verify_result['status']}, "
                    f"all_match={verify_result['all_match']}")

        # 5) Check device in registry
        dev_stats = kernel.platform.stats()
        print(f"[stage 7] Platform stats: {dev_stats['device_count']} devices, "
                    f"{dev_stats['driver_count']} drivers")

        print(f"\n[stage 7] measurement: {dev_result['resource_count']} resources verified, "
                    f"device={dev_result['device']}")