"""linux-device-driver-from-scratch — stage 11 solution: network device driver

Implements network device lifecycle: allocation, bring-up/down,
packet transmission, packet reception, and full lifecycle verification.
"""

from kernel import LinuxKernel, NetDevice


def alloc_netdevice(kernel, name: str, mac: str, mtu: int = 1500) -> dict:
    """Allocate a net_device (alloc_netdev simulation)."""
    result = kernel.netdevices.allocate(name, mac, mtu)
    kernel.log.print("info", f"Network device '{name}' allocated: MAC={mac}, MTU={mtu}", "net")
    return result


def open_netdevice(kernel, name: str) -> dict:
    """Bring a network device UP (ndo_open simulation)."""
    result = kernel.netdevices.open(name)
    if result.get("status") == "opened":
        kernel.log.print("info", f"Network device '{name}' brought UP", "net")
    else:
        kernel.log.print("err", f"Failed to bring '{name}' UP: {result.get('reason')}", "net")
    return result


def stop_netdevice(kernel, name: str) -> dict:
    """Bring a network device DOWN (ndo_stop simulation)."""
    result = kernel.netdevices.stop(name)
    if result.get("status") == "stopped":
        kernel.log.print("info", f"Network device '{name}' brought DOWN", "net")
    else:
        kernel.log.print("err", f"Failed to stop '{name}': {result.get('reason')}", "net")
    return result


def transmit_packet(kernel, name: str, data: bytes) -> dict:
    """Transmit a packet on a network device (ndo_start_xmit simulation)."""
    result = kernel.netdevices.transmit(name, data)
    if result.get("status") == "transmitted":
        kernel.log.print("info", f"TX: {result['bytes']} bytes on '{name}' (packets={result['packets']})", "net")
    else:
        kernel.log.print("err", f"TX failed on '{name}': {result.get('reason')}", "net")
    return result


def receive_packet(kernel, name: str, data: bytes) -> dict:
    """Receive a packet on a network device (simulated rx simulation)."""
    result = kernel.netdevices.receive(name, data)
    if result.get("status") == "received":
        kernel.log.print("info", f"RX: {result['bytes']} bytes on '{name}' (packets={result['packets']})", "net")
    else:
        kernel.log.print("err", f"RX failed on '{name}': {result.get('reason')}", "net")
    return result


def verify_netdevice(kernel, name: str) -> dict:
    """Verify the full network device lifecycle."""
    stats = {
        "device": name,
        "steps": [],
    }

    # 1) Allocate
    alloc_result = alloc_netdevice(kernel, name, "aa:bb:cc:dd:ee:ff")
    stats["steps"].append({"step": "alloc", "status": alloc_result["status"]})

    # 2) Open
    open_result = open_netdevice(kernel, name)
    stats["steps"].append({"step": "open", "status": open_result["status"]})

    # 3) Transmit packets
    tx_results = []
    for i in range(3):
        pkt = f"hello_world_{i}".encode()
        tx = transmit_packet(kernel, name, pkt)
        tx_results.append(tx["status"])
    stats["steps"].append({"step": "transmit", "count": 3, "statuses": tx_results})

    # 4) Receive packets
    rx_results = []
    for i in range(2):
        pkt = f"response_{i}".encode()
        rx = receive_packet(kernel, name, pkt)
        rx_results.append(rx["status"])
    stats["steps"].append({"step": "receive", "count": 2, "statuses": rx_results})

    # 5) Stop
    stop_result = stop_netdevice(kernel, name)
    stats["steps"].append({"step": "stop", "status": stop_result["status"]})

    # 6) Try transmitting while down (should fail)
    tx_down = transmit_packet(kernel, name, b"should_fail")
    stats["steps"].append({"step": "transmit_down", "status": tx_down["status"]})

    # 7) Gather final stats
    nd_stats = kernel.netdevices.stats()
    dev_info = None
    for d in nd_stats["devices"]:
        if d["name"] == name:
            dev_info = d
            break

    stats["final_device"] = dev_info
    stats["registry_stats"] = nd_stats

    # Verify: device should be DOWN based on state
    device_state = dev_info["state"] if dev_info else ""
    stats["final_state"] = device_state
    stats["lifecycle_complete"] = (device_state == "DOWN")

    return stats


if __name__ == "__main__":
    kernel = LinuxKernel()

    # 1) Allocate a network device
    alloc_result = alloc_netdevice(kernel, "eth0", "de:ad:be:ef:ca:fe", mtu=1500)
    print(f"[stage 11] Allocated: {alloc_result['status']}, "
          f"MAC={alloc_result['mac']}, MTU={alloc_result['mtu']}")

    # 2) Open the device
    open_result = open_netdevice(kernel, "eth0")
    print(f"[stage 11] Opened: {open_result['status']}, state={open_result['state']}")

    # 3) Transmit packets
    tx_result = transmit_packet(kernel, "eth0", b"Hello World!")
    print(f"[stage 11] Transmitted: {tx_result['status']}, "
          f"bytes={tx_result['bytes']}, packets={tx_result['packets']}")

    # 4) Receive packets
    rx_result = receive_packet(kernel, "eth0", b"Response!")
    print(f"[stage 11] Received: {rx_result['status']}, "
          f"bytes={rx_result['bytes']}, packets={rx_result['packets']}")

    # 5) Stop the device
    stop_result = stop_netdevice(kernel, "eth0")
    print(f"[stage 11] Stopped: {stop_result['status']}, state={stop_result['state']}")

    # 6) Full lifecycle verification
    lifecycle = verify_netdevice(kernel, "eth1")
    print(f"[stage 11] Lifecycle: {lifecycle['steps']}")
    print(f"[stage 11] Final state: {lifecycle['final_state']}, "
          f"complete={lifecycle['lifecycle_complete']}")

    # 7) Network device stats
    net_stats = kernel.netdevices.stats()
    print(f"[stage 11] Registry: {net_stats['device_count']} device(s)")
    for d in net_stats["devices"]:
        print(f"  - {d['name']}: state={d['state']}, "
              f"rx={d['rx_packets']}p/{d['rx_bytes']}b, "
              f"tx={d['tx_packets']}p/{d['tx_bytes']}b")

    print(f"\n[stage 11] measurement: {net_stats['device_count']} devices, "
          f"lifecycle_complete={lifecycle['lifecycle_complete']}")