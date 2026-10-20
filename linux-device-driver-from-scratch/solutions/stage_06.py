"""linux-device-driver-from-scratch — stage 6 solution: platform driver model

Implements the platform bus: creating platform devices and drivers,
binding (probe) and unbinding (remove), and full lifecycle verification.
"""

from kernel import LinuxKernel, PlatformDevice, PlatformDriver


def create_platform_device(name: str, resource_addrs: list = None,
                                                     resource_sizes: list = None, irq: int = 0) -> dict:
        """Create a platform device specification."""
        dev =    PlatformDevice(
                name=name,
                resource_addrs=resource_addrs or [],
                resource_sizes=resource_sizes or [],
                irq=irq,
        )
        return {
                "name": dev.name,
                "resource_addrs": dev.resource_addrs,
                "resource_sizes": dev.resource_sizes,
                "irq": dev.irq,
        }


def create_platform_driver(name: str, probe_fn=None, remove_fn=None,
                                                     supported_ids: list = None) -> dict:
        """Create a platform driver specification."""
        def default_probe(driver, dev):
                return {"probed": True, "device": dev.name}

        def default_remove(driver, dev):
                return {"removed": True, "device": dev.name if dev else ""}

        driver =    PlatformDriver(
                name=name,
                probe_fn=default_probe if probe_fn is None else probe_fn,
                remove_fn=default_remove if remove_fn is None else remove_fn,
                supported_ids=supported_ids or [],
        )
        return {
                "name": driver.name,
                "supported_ids": driver.supported_ids,
        }


def probe_device(kernel, driver_name: str, device_name: str) -> dict:
        """Probe (bind) a driver to a device."""
        result = kernel.platform.probe(driver_name, device_name)
        if result.get("status") == "probed":
                kernel.log.print("info", f"Driver {driver_name} probed device {device_name}", "platform")
        elif result.get("status") == "bound":
                kernel.log.print("info", f"Driver {driver_name} bound to {device_name}", "platform")
        else:
                kernel.log.print("err", f"Probe failed: {result}", "platform")
        return result


def remove_driver(kernel, driver_name: str) -> dict:
        """Remove (unbind) a driver from its device."""
        result = kernel.platform.remove(driver_name)
        if result.get("status") == "removed":
                kernel.log.print("info", f"Driver {driver_name} removed from its device", "platform")
        return result


def verify_probe_remove(kernel, driver_name: str, device_name: str) -> dict:
        """Verify the full platform driver lifecycle: register -> probe -> remove."""
        lifecycle = {
                "driver": driver_name,
                "device": device_name,
                "steps": [],
        }

        # Register device
        dev_result = kernel.platform.register_device(
                 PlatformDevice(name=device_name, resource_addrs=[0x1000], resource_sizes=[256])
        )
        lifecycle["steps"].append({"step": "register_device", "result": dev_result["status"]})

        # Register driver
        drv_result = kernel.platform.register_driver(
                 PlatformDriver(name=driver_name, probe_fn=lambda d, v: {"probed": True},
                                             remove_fn=lambda d, v: {"removed": True})
        )
        lifecycle["steps"].append({"step": "register_driver", "result": drv_result["status"]})

        # Probe
        probe_result = probe_device(kernel, driver_name, device_name)
        lifecycle["steps"].append({
                "step": "probe",
                "status": probe_result["status"],
        })

        # Verify binding
        stats_before = kernel.platform.stats()
        bound_before = len(stats_before.get("bound_pairs", []))

        # Remove
        remove_result = remove_driver(kernel, driver_name)
        lifecycle["steps"].append({
                "step": "remove",
                "status": remove_result["status"],
        })

        # Verify unbinding
        stats_after = kernel.platform.stats()
        bound_after = len(stats_after.get("bound_pairs", []))

        lifecycle["bound_pairs_before"] = bound_before
        lifecycle["bound_pairs_after"] = bound_after
        lifecycle["final_stats"] = stats_after

        return lifecycle


if __name__ == "__main__":
        kernel = LinuxKernel()

        # 1) Create platform device
        dev = create_platform_device("my_device", [0x1000, 0x2000], [256, 128], irq=5)
        print(f"[stage 6] Device created: {dev['name']}, "
                    f"addrs={dev['resource_addrs']}, irqs={dev['irq']}")

        # 2) Register device
        dev_result = kernel.platform.register_device( PlatformDevice(
                name="my_device", resource_addrs=[0x1000, 0x2000], resource_sizes=[256, 128], irq=5
        ))
        print(f"[stage 6] Device registered: {dev_result['status']}")

        # 3) Create and register platform driver
        drv = create_platform_driver("my_driver")
        print(f"[stage 6] Driver created: {drv['name']}")

        drv_result = kernel.platform.register_driver( PlatformDriver(
                name="my_driver",
                probe_fn=lambda d, v: {"probed": True, "device": v.name},
                remove_fn=lambda d, v: {"removed": True, "device": v.name if v else ""},
        ))
        print(f"[stage 6] Driver registered: {drv_result['status']}")

        # 4) Probe: bind driver to device
        probe_result = probe_device(kernel, "my_driver", "my_device")
        print(f"[stage 6] Probed: {probe_result['status']}, "
                    f"device={probe_result.get('device')}")

        # 5) Check binding stats
        stats = kernel.platform.stats()
        print(f"[stage 6] Bound pairs: {stats['bound_pairs']}")

        # 6) Remove: unbind driver
        remove_result = remove_driver(kernel, "my_driver")
        print(f"[stage 6] Removed: {remove_result['status']}")

        # 7) Full lifecycle verification
        lifecycle = verify_probe_remove(kernel, "test_driver", "test_device")
        print(f"[stage 6] Lifecycle: {lifecycle['steps']}")

        print(f"\n[stage 6] measurement: platform stats = "
                    f"{kernel.platform.stats()['device_count']} devices, "
                    f"{kernel.platform.stats()['driver_count']} drivers, "
                    f"{len(kernel.platform.stats()['bound_pairs'])} bound pairs")