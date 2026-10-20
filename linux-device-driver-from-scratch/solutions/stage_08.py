"""linux-device-driver-from-scratch — stage 8 solution: sysfs and device attributes

Implements sysfs device creation, attribute management (add, read, list),
and verification of sysfs attribute configuration.
"""

from kernel import LinuxKernel


def create_device_sysfs(kernel, device_name: str) -> dict:
    """Create a sysfs entry for a device."""
    result = kernel.sysfs.create_device(device_name)
    kernel.log.print("info", f"sysfs device '{device_name}' created", "sysfs")
    return result


def add_attribute(kernel, device: str, name: str, value: str) -> dict:
    """Add a sysfs attribute to a device."""
    result = kernel.sysfs.add_attribute(device, name, value)
    if result.get("status") == "added":
        kernel.log.print("info", f"sysfs attribute '{name}' added to '{device}': {value}", "sysfs")
    return result


def read_attribute(kernel, device: str, name: str) -> dict:
    """Read a sysfs attribute value."""
    value = kernel.sysfs.get_value(device, name)
    return {
        "device": device,
        "attribute": name,
        "value": value,
    }


def list_attributes(kernel, device: str) -> list:
    """List all attributes of a device."""
    return kernel.sysfs.list_attributes(device)


def verify_sysfs(kernel, device_name: str,
                 expected_attrs: list) -> dict:
    """Verify that a device has all expected sysfs attributes."""
    actual_attrs = list_attributes(kernel, device_name)

    checks = []
    all_present = True
    for attr in expected_attrs:
        present = attr in actual_attrs
        checks.append({"attribute": attr, "expected": True, "actual": present})
        if not present:
            all_present = False

    missing = [a for a in expected_attrs if a not in actual_attrs]
    extra = [a for a in actual_attrs if a not in expected_attrs]

    return {
        "status": "verified" if all_present else "missing_attributes",
        "device": device_name,
        "expected": expected_attrs,
        "actual": actual_attrs,
        "all_present": all_present,
        "missing": missing,
        "extra": extra,
        "checks": checks,
    }


if __name__ == "__main__":
    kernel = LinuxKernel()

    # 1) Create a sysfs device
    create_result = create_device_sysfs(kernel, "my_sensor")
    print(f"[stage 8] sysfs device created: {create_result['status']}")

    # 2) Add attributes
    add_attribute(kernel, "my_sensor", "temperature", "42")
    add_attribute(kernel, "my_sensor", "humidity", "60")
    add_attribute(kernel, "my_sensor", "status", "active")

    # 3) Read attributes
    temp = read_attribute(kernel, "my_sensor", "temperature")
    print(f"[stage 8] Read temperature: {temp['value']}")

    hum = read_attribute(kernel, "my_sensor", "humidity")
    print(f"[stage 8] Read humidity: {hum['value']}")

    # 4) List all attributes
    attrs = list_attributes(kernel, "my_sensor")
    print(f"[stage 8] All attributes: {attrs}")

    # 5) Verify expected attributes
    expected = ["temperature", "humidity", "status"]
    verify_result = verify_sysfs(kernel, "my_sensor", expected)
    print(f"[stage 8] Verification: {verify_result['status']}, "
          f"all_present={verify_result['all_present']}")

    # 6) Check sysfs stats
    sysfs_stats = kernel.sysfs.stats()
    print(f"[stage 8] sysfs stats: {sysfs_stats['device_count']} devices, "
          f"{sysfs_stats['total_attributes']} attributes")

    print(f"\n[stage 8] measurement: {len(attrs)} attributes, "
          f"{sysfs_stats['total_attributes']} total across sysfs")