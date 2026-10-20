"""mutate_01 — load balancer: consistent hash ring, rendezvous hash.

Plants mutations in the solution. Each mutation is a text replacement
that breaks behavior. Uses check functions to verify each is caught.
"""

import sys
import os
import tempfile
import shutil
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path):
    spec = importlib.util.spec_from_file_location("mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _verify(s):
    """Run checks that should fail on broken code."""
    # HashRing basic operations
    ring = s.HashRing(virtual_nodes=50)
    ring.add_node("A")
    ring.add_node("B")
    ring.add_node("C")
    assert len(ring.nodes) == 3, f"Expected 3 nodes, got {len(ring.nodes)}"

    # Routing consistency
    node1 = ring.get_node("key:1")
    node2 = ring.get_node("key:1")
    assert node1 == node2, "Same key must route to same node"

    # All keys must route to existing nodes
    for i in range(20):
        n = ring.get_node(f"key:{i}")
        assert n in ("A", "B", "C"), f"key:{i} routed to {n}"

    # Distribution should be roughly even
    dist = ring.distribution(2000)
    for node, count in dist.items():
        assert 200 < count < 1500, f"distribution off for {node}: {count}"

    # RendezvousHash basic operations
    rh = s.RendezvousHash()
    rh.add_node("X")
    rh.add_node("Y")
    rh.add_node("Z")
    assert len(rh.nodes) == 3, f"Expected 3 nodes, got {len(rh.nodes)}"
    n = rh.get_node("key:1")
    assert n in ("X", "Y", "Z"), f"Rendezvous routed to {n}"

    # Remove node
    ring.remove_node("A")
    assert len(ring.nodes) == 2, f"Expected 2 nodes after remove, got {len(ring.nodes)}"


def _m(template_text, replacement_text, label=""):
    return (template_text, replacement_text, label)


def _is_caught(tmp_path):
    """Check if a mutation is caught by running checks."""
    try:
        mod = _load(tmp_path)
        _verify(mod)
        return False  # NOT caught (checks passed on broken code)
    except Exception:
        return True  # CAUGHT (checks failed on broken code)


def main():
    solution_path = os.path.join(HERE, "solutions", "consistent_hash.py")

    with open(solution_path) as f:
        solution_content = f.read()

    mutations = [
        # HashRing mutations
        _m("self._nodes.add(node)", "pass  # no add", "add_node no-op"),
        _m("self._nodes.discard(node)", "pass  # no discard", "remove_node no-op"),
        _m("return self._ring[idx][1]", "return None", "get_node always None"),
        _m("return set(self._nodes)", "return set()", "nodes always empty"),
        _m("counts: Dict[str, int] = {n: 0 for n in self._nodes}", "counts = {}", "Distribution empty"),
        _m("counts[node] = counts.get(node, 0) + 1", "pass  # broken", "Distribution count broken"),
        _m("return self._ring", "return []", "Ring always empty"),
        _m("bisect.insort(self._ring, (pos, node))", "pass  # broken", "insort broken"),
        _m("self._ring = [(pos, n) for pos, n in self._ring if n != node]", "pass  # broken", "remove filter broken"),
        _m("if not self._ring:", "if False:", "Empty ring check broken"),
        _m("if idx == len(self._ring):", "if False:", "Ring wrap broken"),
        _m("pos = _hash(f'{node}#vnode{i}')", "pos = 0", "Vnode hash broken"),

        # RendezvousHash mutations
        _m("self._nodes.append(node)", "pass  # broken", "RH add_node no-op"),
        _m("self._nodes.remove(node)", "pass  # broken", "RH remove_node no-op"),
        _m("return max(self._nodes, key=lambda n: _hash(f'{n}:{key}'))", "return self._nodes[0] if self._nodes else None", "RH always returns first"),
        _m("return list(self._nodes)", "return []", "RH nodes always empty"),
        _m("if not self._nodes:", "if False:", "RH empty check broken"),

        # Common mutations
        _m("virtual_nodes: int = 150", "virtual_nodes: int = 0", "Vnodes zeroed"),
        _m("self._ring: List[Tuple[int, str]] = []", "pass  # broken init", "Ring init broken"),
        _m("self._nodes: set = set()", "pass  # broken init", "Nodes init broken"),
        _m("self._nodes: List[str] = []", "pass  # broken init", "RH nodes init broken"),
        _m("return int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)", "return 0", "Hash always 0"),
        _m("for i in range(self.virtual_nodes):", "pass  # broken loop", "Vnode loop no-op"),
        _m("for i in range(self.virtual_nodes):", "i = 0  # no loop", "Vnode loop broken"),
        _m("positions = [p for p, _ in self._ring]", "positions = []", "Positions empty"),
        _m("idx = bisect.bisect_left(positions, pos)", "idx = 0  # always first", "Index always 0"),
        _m("for i in range(num_keys):", "i = 0  # single iter", "Distribution single iter"),
        _m("self._nodes.remove(node)", "pass  # RH no-op", "RH remove no-op"),
        _m("return len(self._ring) == 0", "return True", "is_empty always True"),
        _m("if self.get_node(key) != old_ring.get_node(key):", "if False:  # broken", "Migration check broken"),
    ]

    caught = 0
    missed = 0

    for i, (template, replacement, label) in enumerate(mutations):
        if template not in solution_content:
            missed += 1
            print(f"  MUTATE {i+1:03d}: SKIP  (not found)  {label}")
            continue

        tmpdir = tempfile.mkdtemp(prefix=f"mutate01-{i}-")
        try:
            mutated_content = solution_content.replace(template, replacement, 1)
            tmp_path = os.path.join(tmpdir, "consistent_hash.py")
            with open(tmp_path, "w") as f:
                f.write(mutated_content)

            if _is_caught(tmp_path):
                caught += 1
                print(f"  MUTATE {i+1:03d}: CAUGHT  {label}")
            else:
                missed += 1
                print(f"  MUTATE {i+1:03d}: MISSED  {label}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"\nMUTATE: CAUGHT {caught} / {caught + missed}  MISSED {missed}")
    return 0 if missed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())