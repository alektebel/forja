"""The Linux Kernel simulator — the world a driver is written against.

This module is the kernel: it provides the public API that device drivers use,
and it records every call so the checks can verify correctness. A driver is
what a kernel looks like from the outside: the device is the data, the API
is the contract, and every sysfs entry, ioctls, poll, and interrupt is a
promise the driver makes.

Nothing here knows anything about the course: it has no idea what a driver
is. It keeps its own records — `DeviceList` counts registered devices,
`Memory` refuses double free, `InterruptController` counts irqs — and
those records are the tie-breaker a stage's report has to agree with.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Module lifecycle
# ---------------------------------------------------------------------------

class ModuleState(Enum):
    LOADING = auto()
    LOADED = auto()
    RUNNING = auto()
    UNLOADING = auto()
    UNLOADED = auto()


@dataclass
class Module:
    name: str
    init_fn: Callable | None = None
    exit_fn: Callable | None = None
    state: ModuleState = ModuleState.UNLOADED
    params: dict[str, str] = field(default_factory=dict)
    author: str = ""
    license: str = ""
    version: str = ""
    init_call_count: int = 0
    exit_call_count: int = 0


class ModuleRegistry:
    """kernel module registry: init_module, delete_module."""

    def __init__(self) -> None:
        self.modules: dict[str, Module] = {}

    def register(self, module: Module) -> dict:
        self.modules[module.name] = module
        return {"status": "registered", "name": module.name, "total": len(self.modules)}

    def load(self, name: str, init: Callable, exit_fn: Callable, params: dict[str, str] | None = None) -> dict:
        if name in self.modules:
            return {"status": "error", "reason": "module_already_loaded", "name": name}
        module = Module(name=name, init_fn=init, exit_fn=exit_fn, params=params or {})
        self.modules[name] = module
        module.state = ModuleState.LOADING
        if init:
            init(module, module.params)
            module.init_call_count += 1
        module.state = ModuleState.LOADED
        return {"status": "loaded", "name": name}

    def unload(self, name: str) -> dict:
        if name not in self.modules:
            return {"status": "error", "reason": "module_not_found", "name": name}
        module = self.modules[name]
        if module.init_fn:
            module.exit_fn(module)
            module.exit_call_count += 1
        module.state = ModuleState.UNLOADED
        del self.modules[name]
        return {"status": "unloaded", "name": name}

    def get(self, name: str) -> Module | None:
        return self.modules.get(name)

    def list(self) -> list[str]:
        return list(self.modules.keys())


# ---------------------------------------------------------------------------
# Memory management
# ---------------------------------------------------------------------------

@dataclass
class MemoryRegion:
    name: str
    size: int
    addr: int
    data: bytearray
    mapped: bool = False
    flags: str = "rw"  # "rw", "ro", "dma"


class MemoryManager:
    """kmalloc / vmalloc / mmap simulation with bookkeeping."""

    def __init__(self) -> None:
        self.regions: list[MemoryRegion] = []
        self.used: list[int] = []
        self.next_addr: int = 0x10000000  # kernel virtual space start
        self.mmap_regions: list[MemoryRegion] = []
        self.total_allocated: int = 0

    def allocate(self, size: int, name: str = "anon") -> dict:
        """Allocate kernel memory (kmalloc simulation)."""
        if size <= 0:
            return {"status": "error", "reason": "invalid_size", "size": size}
        if name in self.used:
            return {"status": "error", "reason": "duplicate_name", "name": name}
        addr = self.next_addr
        self.next_addr += (size + 4095) & ~4095  # page-aligned
        data = bytearray(size)
        region = MemoryRegion(name=name, size=size, addr=addr, data=data, flags="rw")
        self.regions.append(region)
        self.used.append(name)
        self.total_allocated += size
        return {"status": "allocated", "addr": addr, "size": size, "name": name, "total_allocated": self.total_allocated}

    def free(self, name: str) -> dict:
        """Free kernel memory (kfree simulation)."""
        if name not in self.used:
            return {"status": "error", "reason": "not_allocated", "name": name}
        region = None
        for r in self.regions:
            if r.name == name:
                region = r
                break
        if region:
            if region.mapped:
                return {"status": "error", "reason": "mapped_still_referenced", "name": name}
            self.regions.remove(region)
            self.used.remove(name)
            self.total_allocated -= region.size
        return {"status": "freed", "name": name, "total_allocated": self.total_allocated}

    def mmap(self, name: str, vaddr: int = 0) -> dict:
        """Map kernel memory into userspace (mmap simulation)."""
        if name not in self.used:
            return {"status": "error", "reason": "not_allocated", "name": name}
        region = None
        for r in self.regions:
            if r.name == name:
                region = r
                break
        if region and not region.mapped:
            region.mapped = True
            self.mmap_regions.append(region)
        return {"status": "mapped", "name": name, "mapped_count": len(self.mmap_regions)}

    def read(self, name: str, offset: int, length: int) -> str:
        """Read data from allocated memory."""
        if name not in self.used:
            return ""
        region = None
        for r in self.regions:
            if r.name == name:
                region = r
                break
        if region is None:
            return ""
        end = min(offset + length, region.size)
        return region.data[offset:end].hex()

    def write(self, name: str, offset: int, data: str) -> int:
        """Write hex-encoded data to allocated memory."""
        if name not in self.used:
            return -1
        region = None
        for r in self.regions:
            if r.name == name:
                region = r
                break
        if region is None:
            return -1
        raw = bytes.fromhex(data)
        for i, b in enumerate(raw):
            if offset + i < region.size:
                region.data[offset + i] = b
        return len(raw)

    def stats(self) -> dict:
        return {
            "total_allocated": self.total_allocated,
            "region_count": len(self.regions),
            "mapped_count": len(self.mmap_regions),
            "regions": [{"name": r.name, "size": r.size, "mapped": r.mapped} for r in self.regions],
        }


# ---------------------------------------------------------------------------
# Character device driver (cdev / file_operations)
# ---------------------------------------------------------------------------

@dataclass
class FileOpTrace:
    """Record of a file_operations call."""
    operation: str  # open, read, write, release, llseek, ioctl, poll
    args: dict = field(default_factory=dict)
    result: Any = None
    buffer: str = ""


class CharacterDevice:
    """cdev simulation: major, minor, name, file_operations."""

    def __init__(self, name: str, major: int, minor: int) -> None:
        self.name = name
        self.major = major
        self.minor = minor
        self.ops: dict[str, Callable] = {}
        self.traces: list[FileOpTrace] = []
        self.open_count: int = 0
        self.close_count: int = 0
        self.read_count: int = 0
        self.write_count: int = 0
        self.ioctl_count: int = 0

    def set_op(self, op: str, fn: Callable) -> None:
        self.ops[op] = fn

    def call(self, op: str, **kwargs) -> dict:
        if op not in self.ops:
            return {"status": "error", "reason": "no_such_operation", "op": op}
        trace = FileOpTrace(operation=op, args=kwargs)
        try:
            trace.result = self.ops[op](**kwargs)
        except Exception as e:
            trace.result = {"error": str(e)}
        self.traces.append(trace)
        if op == "open":
            self.open_count += 1
        elif op == "release":
            self.close_count += 1
        elif op == "read":
            self.read_count += 1
        elif op == "write":
            self.write_count += 1
        elif op == "ioctl":
            self.ioctl_count += 1
        return {"op": op, "result": trace.result, "traces": len(self.traces)}

    def get_trace(self, index: int) -> FileOpTrace | None:
        if 0 <= index < len(self.traces):
            return self.traces[index]
        return None

    def stats(self) -> dict:
        return {
            "name": self.name,
            "major": self.major,
            "minor": self.minor,
            "open_count": self.open_count,
            "close_count": self.close_count,
            "read_count": self.read_count,
            "write_count": self.write_count,
            "ioctl_count": self.ioctl_count,
        }


class DeviceRegistry:
    """Major/minor device number management."""

    def __init__(self) -> None:
        self.devices: dict[str, CharacterDevice] = {}
        self.majors: dict[int, str] = {}
        self.minors_used: set[int] = set()

    def register(self, dev: CharacterDevice) -> dict:
        key = f"{dev.major}:{dev.minor}"
        if key in self.devices:
            return {"status": "error", "reason": "device_number_taken", "key": key}
        if dev.major not in self.majors:
            self.majors[dev.major] = dev.name
        self.minors_used.add(dev.minor)
        self.devices[key] = dev
        return {"status": "registered", "key": key, "major": dev.major, "minor": dev.minor}

    def unregister(self, key: str) -> dict:
        if key not in self.devices:
            return {"status": "error", "reason": "device_not_found", "key": key}
        dev = self.devices[key]
        self.minors_used.discard(dev.minor)
        del self.devices[key]
        return {"status": "unregistered", "key": key}

    def get(self, key: str) -> CharacterDevice | None:
        return self.devices.get(key)

    def get_by_major(self, major: int) -> list[CharacterDevice]:
        return [d for d in self.devices.values() if d.major == major]

    def stats(self) -> dict:
        return {
            "device_count": len(self.devices),
            "major_count": len(self.majors),
            "devices": list(self.devices.keys()),
        }


# ---------------------------------------------------------------------------
# ioctl
# ---------------------------------------------------------------------------

_IOC_TYPES = {
    'n': 0x00, 'r': 0x40, 'w': 0x80, 'rw': 0xC0,
}


def make_ioctl_cmd(direction: str, group: int, number: int, size: int = 0) -> int:
    """Encode an ioctl command number (Linux-style _IO / _IOW / _IOR / _IOWR)."""
    type_byte = _IOC_TYPES.get(direction, 0)
    return (type_byte << 24) | (size << 16) | (group << 8) | number


def decode_ioctl_cmd(cmd: int) -> dict:
    """Decode an ioctl command number back into components."""
    direction_byte = (cmd >> 24) & 0xFF
    size = (cmd >> 16) & 0xFFFF
    group = (cmd >> 8) & 0xFF
    number = cmd & 0xFF

    direction = {
        0x00: "n",  # no transfer
        0x40: "r",  # read
        0x80: "w",  # write
        0xC0: "rw",  # read/write
    }.get(direction_byte, "?")

    return {"direction": direction, "group": group, "number": number, "size": size}


class IoctlHandler:
    """Handle ioctl commands with _IO, _IOW, _IOR, _IOWR encoding."""

    def __init__(self) -> None:
        self.handlers: dict[int, Callable] = {}
        self.call_count: int = 0
        self.errors: list[str] = []

    def register(self, cmd: int, handler: Callable) -> None:
        self.handlers[cmd] = handler

    def execute(self, cmd: int, arg: Any = None) -> dict:
        self.call_count += 1
        if cmd not in self.handlers:
            self.errors.append(f"unregistered ioctl {cmd:#x}")
            return {"status": "error", "reason": "unregistered", "cmd": cmd}
        try:
            result = self.handlers[cmd](arg)
            return {"status": "ok", "cmd": cmd, "result": result}
        except Exception as e:
            self.errors.append(f"ioctl failed: {e}")
            return {"status": "error", "reason": "handler_error", "error": str(e)}

    def stats(self) -> dict:
        return {"call_count": self.call_count, "errors": len(self.errors)}


# ---------------------------------------------------------------------------
# Interrupt controller
# ---------------------------------------------------------------------------

@dataclass
class IRQRegistration:
    name: str
    handler: Callable
    flags: str = ""  # "SHARED", "DISABLED", etc.
    device: str = ""


class InterruptController:
    """Kernel interrupt controller: request_irq, free_irq, raise_irq."""

    def __init__(self) -> None:
        self.registrations: dict[int, list[IRQRegistration]] = {}
        self.routed: list[int] = []
        self.handler_calls: dict[int, int] = {}

    def request_irq(self, irq: int, handler: Callable, name: str,
                    flags: str = "", device: str = "") -> dict:
        if irq not in self.registrations:
            self.registrations[irq] = []
        for reg in self.registrations[irq]:
            if reg.name == name and reg.flags != "SHARED":
                return {"status": "error", "reason": "already_bound", "irq": irq, "name": name}
        self.registrations[irq].append(IRQRegistration(name=name, handler=handler, flags=flags, device=device))
        self.handler_calls[irq] = self.handler_calls.get(irq, 0)
        return {"status": "registered", "irq": irq, "name": name}

    def free_irq(self, irq: int, name: str) -> dict:
        if irq not in self.registrations:
            return {"status": "error", "reason": "irq_not_bound", "irq": irq, "name": name}
        before = len(self.registrations[irq])
        self.registrations[irq] = [r for r in self.registrations[irq] if r.name != name]
        if len(self.registrations[irq]) == 0:
            del self.registrations[irq]
        return {"status": "freed", "irq": irq, "name": name, "remaining": len(self.registrations.get(irq, []))}

    def raise_irq(self, irq: int) -> dict:
        """Simulate hardware interrupt: call all registered handlers."""
        self.routed.append(irq)
        if irq not in self.registrations:
            return {"status": "error", "reason": "unregistered", "irq": irq}
        for reg in self.registrations[irq]:
            try:
                reg.handler(irq, reg.device)
            except Exception as e:
                return {"status": "error", "reason": "handler_error", "irq": irq, "handler": reg.name, "error": str(e)}
        self.handler_calls[irq] = self.handler_calls.get(irq, 0) + 1
        return {"status": "routed", "irq": irq, "handlers_called": len(self.registrations[irq])}

    def stats(self) -> dict:
        return {
            "total_irqs": len(self.registrations),
            "total_routed": len(self.routed),
            "per_irq": dict(self.handler_calls),
        }


# ---------------------------------------------------------------------------
# Platform driver model
# ---------------------------------------------------------------------------

@dataclass
class PlatformDevice:
    name: str
    resource_addrs: list[int] = field(default_factory=list)
    resource_sizes: list[int] = field(default_factory=list)
    irq: int = 0
    data: Any = None  # driver can attach data


@dataclass
class PlatformDriver:
    name: str
    probe_fn: Callable | None = None
    remove_fn: Callable | None = None
    supported_ids: list[str] = field(default_factory=list)
    bound_device: str = ""


class PlatformBus:
    """Linux platform bus: platform_driver_probe, platform_device_register."""

    def __init__(self) -> None:
        self.devices: dict[str, PlatformDevice] = {}
        self.drivers: dict[str, PlatformDriver] = {}
        self.bound_pairs: list[tuple[str, str]] = []  # (driver_name, device_name)

    def register_device(self, dev: PlatformDevice) -> dict:
        self.devices[dev.name] = dev
        return {"status": "registered", "device": dev.name}

    def register_driver(self, driver: PlatformDriver) -> dict:
        self.drivers[driver.name] = driver
        return {"status": "registered", "driver": driver.name}

    def probe(self, driver_name: str, device_name: str) -> dict:
        if driver_name not in self.drivers:
            return {"status": "error", "reason": "no_driver", "driver": driver_name}
        if device_name not in self.devices:
            return {"status": "error", "reason": "no_device", "device": device_name}
        driver = self.drivers[driver_name]
        dev = self.devices[device_name]
        if driver.probe_fn:
            result = driver.probe_fn(driver, dev)
            driver.bound_device = device_name
            self.bound_pairs.append((driver_name, device_name))
            return {"status": "probed", "driver": driver_name, "device": device_name, "result": result}
        return {"status": "bound", "driver": driver_name, "device": device_name}

    def remove(self, driver_name: str) -> dict:
        if driver_name not in self.drivers:
            return {"status": "error", "reason": "no_driver", "driver": driver_name}
        driver = self.drivers[driver_name]
        if driver.bound_device:
            if driver.remove_fn:
                result = driver.remove_fn(driver, self.devices.get(driver.bound_device))
            self.bound_pairs = [(d, dev) for d, dev in self.bound_pairs if d != driver_name]
            driver.bound_device = ""
            return {"status": "removed", "driver": driver_name, "device": driver.bound_device}
        return {"status": "no_binding", "driver": driver_name}

    def stats(self) -> dict:
        return {
            "device_count": len(self.devices),
            "driver_count": len(self.drivers),
            "bound_pairs": list(self.bound_pairs),
        }


# ---------------------------------------------------------------------------
# sysfs / kobject
# ---------------------------------------------------------------------------

class SysFS:
    """Simulated sysfs: device attributes, kobject hierarchy."""

    def __init__(self) -> None:
        self.attributes: dict[str, dict[str, str]] = {}  # path -> {attr: value}
        self.devices: dict[str, list[str]] = {}  # device -> [attribute names]

    def create_device(self, device_name: str) -> dict:
        if device_name in self.devices:
            return {"status": "error", "reason": "device_exists", "device": device_name}
        self.devices[device_name] = []
        self.attributes[device_name] = {}
        return {"status": "created", "device": device_name}

    def add_attribute(self, device: str, name: str, value: str) -> dict:
        if device not in self.devices:
            return {"status": "error", "reason": "device_not_found", "device": device}
        if device not in self.attributes:
            self.attributes[device] = {}
        self.attributes[device][name] = value
        if name not in self.devices[device]:
            self.devices[device].append(name)
        return {"status": "added", "device": device, "attribute": name}

    def get_value(self, device: str, name: str) -> str:
        if device not in self.attributes:
            return ""
        return self.attributes[device].get(name, "")

    def list_attributes(self, device: str) -> list[str]:
        return list(self.attributes.get(device, {}).keys())

    def stats(self) -> dict:
        return {
            "device_count": len(self.devices),
            "total_attributes": sum(len(v) for v in self.attributes.values()),
        }


# ---------------------------------------------------------------------------
# Wait queue / poll / async notification
# ---------------------------------------------------------------------------

class WaitQueue:
    """Kernel wait queue: wait_event, wake_up, poll."""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.poll_calls: list[dict] = []
        self.wake_count: int = 0
        self.wakers: list[str] = []

    def poll(self, fd: int, expected_mask: str) -> dict:
        """Check if the expected POLLIN/POLLOUT/POLLERR is ready."""
        for event in reversed(self.events):
            if event == expected_mask:
                self.poll_calls.append({"fd": fd, "mask": expected_mask, "ready": True})
                return {"ready": True, "fd": fd, "mask": expected_mask}
        self.poll_calls.append({"fd": fd, "mask": expected_mask, "ready": False})
        return {"ready": False, "fd": fd, "mask": expected_mask}

    def wake(self, event: str) -> dict:
        self.events.append(event)
        self.wake_count += 1
        self.wakers.append(event)
        return {"status": "woken", "event": event}

    def stats(self) -> dict:
        return {
            "poll_calls": len(self.poll_calls),
            "wake_count": self.wake_count,
            "pending_events": list(self.events),
        }


# ---------------------------------------------------------------------------
# Kernel thread / workqueue
# ---------------------------------------------------------------------------

class WorkQueue:
    """Kernel workqueue: queue_work, schedule_work, work_struct."""

    def __init__(self) -> None:
        self.work_items: list[dict] = []
        self.completed: list[dict] = []
        self.total_scheduled: int = 0

    def queue(self, name: str, fn: Callable, context: dict | None = None) -> dict:
        item = {"name": name, "fn": fn, "context": context or {}, "scheduled": True}
        self.work_items.append(item)
        self.total_scheduled += 1
        return {"status": "queued", "name": name, "queue_depth": len(self.work_items)}

    def run_all(self) -> dict:
        results = []
        for item in self.work_items[:]:
            try:
                result = item["fn"](item["context"])
                results.append({"name": item["name"], "status": "completed", "result": result})
                self.completed.append(item)
            except Exception as e:
                results.append({"name": item["name"], "status": "failed", "error": str(e)})
        self.work_items.clear()
        return {"completed": len(results), "results": results}

    def stats(self) -> dict:
        return {
            "total_scheduled": self.total_scheduled,
            "completed": len(self.completed),
            "pending": len(self.work_items),
        }


class KernelThread:
    """Simulated kernel threads (kthread)."""

    def __init__(self) -> None:
        self.threads: list[dict] = []
        self.run_count: int = 0

    def create(self, name: str, fn: Callable, args: dict | None = None) -> dict:
        self.threads.append({"name": name, "fn": fn, "args": args or {}, "running": False})
        return {"status": "created", "name": name, "thread_count": len(self.threads)}

    def run(self, name: str) -> dict:
        for t in self.threads:
            if t["name"] == name:
                t["running"] = True
                try:
                    result = t["fn"](t["args"])
                    t["running"] = False
                    self.run_count += 1
                    return {"status": "completed", "name": name, "result": result}
                except Exception as e:
                    t["running"] = False
                    return {"status": "error", "name": name, "error": str(e)}
        return {"status": "error", "reason": "thread_not_found", "name": name}

    def stats(self) -> dict:
        return {"thread_count": len(self.threads), "run_count": self.run_count}


# ---------------------------------------------------------------------------
# Netdevice
# ---------------------------------------------------------------------------

@dataclass
class NetDevice:
    name: str
    mac: str
    mtu: int = 1500
    state: str = "DOWN"
    rx_packets: int = 0
    tx_packets: int = 0
    rx_bytes: int = 0
    tx_bytes: int = 0
    hw_features: str = ""
    ops: dict[str, Callable] = field(default_factory=dict)
    promisc: bool = False
    up_since: str = ""


class NetDeviceRegistry:
    """Linux net_device management: alloc_netdev, register_netdev, ndo_open/ndo_stop/ndo_start_xmit."""

    def __init__(self) -> None:
        self.devices: dict[str, NetDevice] = {}
        self.allocated: list[str] = []

    def allocate(self, name: str, mac: str, mtu: int = 1500) -> dict:
        if name in self.devices:
            return {"status": "error", "reason": "device_exists", "name": name}
        dev = NetDevice(name=name, mac=mac, mtu=mtu)
        self.devices[name] = dev
        self.allocated.append(name)
        return {"status": "allocated", "name": name, "mac": mac, "mtu": mtu}

    def open(self, name: str) -> dict:
        if name not in self.devices:
            return {"status": "error", "reason": "device_not_found", "name": name}
        dev = self.devices[name]
        dev.state = "UP"
        dev.up_since = f"pid_{dev.rx_packets}"
        return {"status": "opened", "name": name, "state": "UP", "mac": dev.mac}

    def stop(self, name: str) -> dict:
        if name not in self.devices:
            return {"status": "error", "reason": "device_not_found", "name": name}
        dev = self.devices[name]
        dev.state = "DOWN"
        return {"status": "stopped", "name": name, "state": "DOWN"}

    def transmit(self, name: str, packet: bytes, dst_mac: str = "") -> dict:
        if name not in self.devices:
            return {"status": "error", "reason": "device_not_found", "name": name}
        dev = self.devices[name]
        if dev.state != "UP":
            return {"status": "error", "reason": "device_not_up", "name": name}
        dev.tx_packets += 1
        dev.tx_bytes += len(packet)
        return {"status": "transmitted", "name": name, "bytes": len(packet), "packets": dev.tx_packets}

    def receive(self, name: str, packet: bytes) -> dict:
        if name not in self.devices:
            return {"status": "error", "reason": "device_not_found", "name": name}
        dev = self.devices[name]
        dev.rx_packets += 1
        dev.rx_bytes += len(packet)
        return {"status": "received", "name": name, "bytes": len(packet), "packets": dev.rx_packets}

    def stats(self) -> dict:
        return {
            "device_count": len(self.devices),
            "devices": [
                {"name": d.name, "mac": d.mac, "state": d.state,
                 "rx_packets": d.rx_packets, "tx_packets": d.tx_packets,
                 "rx_bytes": d.rx_bytes, "tx_bytes": d.tx_bytes}
                for d in self.devices.values()
            ],
        }


# ---------------------------------------------------------------------------
# Kernel synchronization primitives
# ---------------------------------------------------------------------------

class SynchronizationPrimitives:
    """Spinlock, mutex, semaphore, RCU simulation."""

    def __init__(self) -> None:
        self.spins: dict[str, bool] = {}  # name -> is_locked
        self.mutexes: dict[str, bool] = {}
        self.semaphores: dict[str, int] = {}
        self.rcu_readers: int = 0
        self.history: list[str] = []

    def spin_lock(self, name: str) -> dict:
        if name in self.spins and self.spins[name]:
            return {"status": "error", "reason": "already_locked", "name": name, "type": "spinlock"}
        self.spins[name] = True
        self.history.append(f"spin_lock:{name}")
        return {"status": "locked", "name": name, "type": "spinlock"}

    def spin_unlock(self, name: str) -> dict:
        if name not in self.spins or not self.spins[name]:
            return {"status": "error", "reason": "not_locked", "name": name, "type": "spinlock"}
        self.spins[name] = False
        self.history.append(f"spin_unlock:{name}")
        return {"status": "unlocked", "name": name, "type": "spinlock"}

    def mutex_lock(self, name: str) -> dict:
        if name in self.mutexes and self.mutexes[name]:
            return {"status": "error", "reason": "already_locked", "name": name, "type": "mutex"}
        self.mutexes[name] = True
        self.history.append(f"mutex_lock:{name}")
        return {"status": "locked", "name": name, "type": "mutex"}

    def mutex_unlock(self, name: str) -> dict:
        if name not in self.mutexes or not self.mutexes[name]:
            return {"status": "error", "reason": "not_locked", "name": name, "type": "mutex"}
        self.mutexes[name] = False
        self.history.append(f"mutex_unlock:{name}")
        return {"status": "unlocked", "name": name, "type": "mutex"}

    def sema_init(self, name: str, value: int = 1) -> dict:
        self.semaphores[name] = value
        self.history.append(f"sema_init:{name}={value}")
        return {"status": "initialized", "name": name, "type": "semaphore", "value": value}

    def sema_down(self, name: str) -> dict:
        if name not in self.semaphores or self.semaphores[name] <= 0:
            return {"status": "error", "reason": "count_zero", "name": name, "type": "semaphore"}
        self.semaphores[name] -= 1
        self.history.append(f"sema_down:{name}={self.semaphores[name]}")
        return {"status": "down", "name": name, "type": "semaphore", "value": self.semaphores[name]}

    def sema_up(self, name: str) -> dict:
        if name not in self.semaphores:
            return {"status": "error", "reason": "not_initialized", "name": name, "type": "semaphore"}
        self.semaphores[name] += 1
        self.history.append(f"sema_up:{name}={self.semaphores[name]}")
        return {"status": "up", "name": name, "type": "semaphore", "value": self.semaphores[name]}

    def rcu_read_lock(self) -> dict:
        self.rcu_readers += 1
        self.history.append("rcu_read_lock")
        return {"status": "locked", "type": "rcu", "readers": self.rcu_readers}

    def rcu_read_unlock(self) -> dict:
        if self.rcu_readers <= 0:
            return {"status": "error", "reason": "no_readers", "type": "rcu"}
        self.rcu_readers -= 1
        self.history.append("rcu_read_unlock")
        return {"status": "unlocked", "type": "rcu", "readers": self.rcu_readers}

    def stats(self) -> dict:
        return {
            "spinlocks_locked": sum(1 for v in self.spins.values() if v),
            "spinlocks_total": len(self.spins),
            "mutexes_locked": sum(1 for v in self.mutexes.values() if v),
            "mutexes_total": len(self.mutexes),
            "rcu_readers": self.rcu_readers,
            "total_history": len(self.history),
        }


# ---------------------------------------------------------------------------
# Kernel logging / printk
# ---------------------------------------------------------------------------

class KernelLog:
    """Simulated printk log buffer."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def print(self, level: str, message: str, module: str = "unknown") -> dict:
        entry = {
            "level": level,
            "message": message,
            "module": module,
            "id": len(self.entries) + 1,
        }
        self.entries.append(entry)
        return {"status": "logged", "id": entry["id"], "level": level, "module": module}

    def get_entries(self, level: str | None = None, module: str | None = None) -> list[dict]:
        result = self.entries
        if level:
            result = [e for e in result if e["level"] == level]
        if module:
            result = [e for e in result if e["module"] == module]
        return result

    def stats(self) -> dict:
        counts: dict[str, int] = {}
        for e in self.entries:
            counts[e["level"]] = counts.get(e["level"], 0) + 1
        return {
            "total": len(self.entries),
            "by_level": counts,
        }


# ---------------------------------------------------------------------------
# Main kernel — the single entry point
# ---------------------------------------------------------------------------

class LinuxKernel:
    """The full kernel simulator: everything a driver needs."""

    def __init__(self) -> None:
        self.modules = ModuleRegistry()
        self.memory = MemoryManager()
        self.devices = DeviceRegistry()
        self.ioctls = IoctlHandler()
        self.irqs = InterruptController()
        self.platform = PlatformBus()
        self.sysfs = SysFS()
        self.waitqueue = WaitQueue()
        self.workqueue = WorkQueue()
        self.kthreads = KernelThread()
        self.netdevices = NetDeviceRegistry()
        self.sync = SynchronizationPrimitives()
        self.log = KernelLog()