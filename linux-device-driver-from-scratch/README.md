# Linux Device Driver From Scratch

A complete Linux device driver course covering 12 stages from kernel module lifecycle to network device drivers.

## Overview

This course teaches Linux device driver development by building each subsystem from scratch. You start with loadable kernel modules and progress through character devices, memory management, ioctl, interrupts, platform drivers, sysfs, wait queues, workqueues, network devices, and synchronization primitives.

The world is provided: `kernel.py` simulates the Linux kernel's driver APIs. Your code (the "driver") interacts with it through the documented interfaces. The kernel records every call — your job is to make the right ones.

## Prerequisites

- Python 3.10+
- Familiarity with C and Linux kernel concepts helps but is not required

## Stages

| # | Stage | Description |
|---|-------|-------------|
| 1 | Kernel Module Lifecycle | `module_init`, `module_exit`, module parameters, module states |
| 2 | Character Device Driver | `cdev`, `file_operations`, `open/read/write/release` |
| 3 | Kernel Memory Management | `kmalloc`, `kfree`, `mmap`, memory lifecycle |
| 4 | ioctl Commands | `_IO`, `_IOW`, `_IOR`, `_IOWR` encoding and decoding |
| 5 | Interrupt Handling | `request_irq`, `free_irq`, handler registration and firing |
| 6 | Platform Driver Model | `platform_driver`, `platform_device`, probe-remove lifecycle |
| 7 | Device Resources | `platform_get_resource`, memory and IRQ resource management |
| 8 | sysfs and Device Attributes | Device attributes, kobject hierarchy, `/sys/class` |
| 9 | Wait Queues and Polling | `poll`, `wait_event`, `wake_up`, `POLLIN/POLLOUT` masks |
| 10 | Kernel Threading and Workqueues | `queue_work`, `work_struct`, `kthread_create` |
| 11 | Network Device Driver | `alloc_netdev`, `ndo_open`, `ndo_start_xmit`, packet TX/RX |
| 12 | Synchronization Primitives | Spinlocks, mutexes, semaphores, RCU |

## How to Run

```bash
# Run all stages
python3 codecraft/cli.py run linux-device-driver-from-scratch

# Run a specific stage
python3 codecraft/cli.py run linux-device-driver-from-scratch --start N

# Run all stages including failed ones
python3 codecraft/cli.py run linux-device-driver-from-scratch --all
```

## Design Decisions

### Why simulate the kernel instead of building on real hardware?

Real hardware introduces non-determinism, hardware dependencies, and environment setup complexity. A simulator lets you verify every call, every return value, and every state transition. The simulator is small enough to hold in your head — 870 lines of Python.

### Why Python for driver development?

Linux drivers are written in C, but the concepts — file_operations, ioctl encoding, interrupt registration, platform device matching — are language-independent. Python lets you focus on the patterns without fighting pointer arithmetic and memory management bugs that aren't the learning objective.

### Why build up from modules to netdevices?

Each stage builds on the previous one:
- Modules are the container for all driver code
- Character devices are the simplest device type
- Memory management is needed by every device
- ioctl provides device-specific commands
- Interrupts are how hardware talks to the driver
- Platform drivers are how the kernel discovers hardware
- sysfs is how the driver exposes state
- Wait queues are how the driver handles blocking
- Workqueues are how the driver does deferred work
- Netdevices are the most complex device type, combining everything above

## Repository Structure

```
linux-device-driver-from-scratch/
  kernel.py          # The kernel simulator (world, never changes)
  course.py          # Course manifest with 12 graded checks
  stage_01.py .. stage_12.py   # Stage stubs (NotImplemented)
  solutions/         # Working implementations
  README.md          # This file
```

## Learning Path

1. **Read the stage docstring** — understand what you need to build
2. **Implement the function** — use `kernel.py`'s API
3. **Run the check** — verify with `python3 codecraft/cli.py run linux-device-driver-from-scratch`
4. **Compare with solution** — if stuck, check `solutions/stage_XX.py`

## Limits

- No actual Linux kernel headers required
- No compilation, no `make modules`, no `insmod`
- The simulator is 870 lines; it models the API surface, not the implementation
- All tests are deterministic — no randomness, no wall clock