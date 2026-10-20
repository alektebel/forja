"""linux-device-driver-from-scratch — stage 1 solution: module lifecycle

Implements loadable kernel module management: creating module specs,
registering them with the kernel, and running the full init→run→exit lifecycle.
"""

from kernel import LinuxKernel, Module


def create_module(name: str, init_fn: str = "", exit_fn: str = "",
                                    author: str = "", license: str = "", version: str = "") -> dict:
        """Create a kernel module specification."""
        return {
                "name": name,
                "init_fn": init_fn,
                "exit_fn": exit_fn,
                "author": author,
                "license": license,
                "version": version,
        }


def register_module(kernel, module_spec: dict, init_fn=None,
                                        exit_fn=None, params: dict[str, str] | None = None) -> dict:
        """Register a module with the kernel."""
        kernel.log.print("info", f"Loading module {module_spec.get('name', 'unknown')}", module_spec.get("name", "unknown"))
        load_result = kernel.modules.load(
                module_spec.get("name", "unknown"), init_fn, exit_fn, params or {}
        )
        return load_result


def run_lifecycle(kernel, module_name: str, do_unload: bool = False) -> dict:
        """Run the full module lifecycle: load -> init -> (run) -> unload -> exit."""
        module = kernel.modules.get(module_name)
        if module is None:
                return {
                        "status": "error",
                        "reason": "module_not_found",
                        "name": module_name,
                }

        lifecycle = {
                "module": module_name,
                "steps": [],
        }

        # Module is already loaded (loaded by register_module)
        lifecycle["steps"].append({
                "step": "loaded",
                "state": module.state.name,
        })

        if do_unload:
                kernel.log.print("info", f"Unloading module {module_name}", module_name)
                unload_result = kernel.modules.unload(module_name)
                lifecycle["steps"].append({
                        "step": "unloaded",
                        "result": unload_result,
                        "state": module.state.name,
                })

        lifecycle["final_state"] = module.state.name
        lifecycle["init_call_count"] = module.init_call_count
        lifecycle["exit_call_count"] = module.exit_call_count

        return lifecycle


if __name__ == "__main__":
        kernel = LinuxKernel()

        # Create a simple init/exit function
        def my_init(module, params):
                kernel.log.print("info", f"Module {module.name} initializing", module.name)
                kernel.log.print("info", f"    params: {params}", module.name)

        def my_exit(module):
                kernel.log.print("info", f"Module {module.name} cleaning up", module.name)

        # 1) Create module spec
        spec = create_module(
                name="my_driver",
                init_fn="my_init",
                exit_fn="my_exit",
                author="Diego",
                license="GPL",
                version="1.0",
        )
        print(f"[stage 1] Module spec created: {spec['name']}")

        # 2) Register with kernel
        result = register_module(kernel, spec, my_init, my_exit, {"param1": "hello"})
        print(f"[stage 1] Module loaded: {result['load']['status']}")

        # 3) Verify module exists
        module = kernel.modules.get("my_driver")
        print(f"[stage 1] Module state: {module.state.name}, init calls: {module.init_call_count}")

        # 4) Run full lifecycle with unload
        lifecycle = run_lifecycle(kernel, "my_driver", do_unload=True)
        print(f"[stage 1] Lifecycle steps: {[s['step'] for s in lifecycle['steps']]}")

        # 5) Verify module is gone
        remaining = kernel.modules.list()
        print(f"[stage 1] Remaining modules: {remaining}")

        print(f"\n[stage 1] measurement: lifecycle completed with "
                    f"init_call_count={lifecycle['init_call_count']}, "
                    f"exit_call_count={lifecycle['exit_call_count']}")