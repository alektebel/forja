# Infrastructure From Scratch — Graded Course

This is the graded course for learning the 20 core building blocks of
distributed systems. Each component is a stage with:

- `templates/<component>.py` — template (stub with `raise NotImplementedError`)
- `solutions/<component>.py` — solution (working implementation)
- `check_<N>.py` — checker (must fail on template, pass on solution)
- `mutate_<N>.py` — mutator (plants ≥34 mutations, every one caught)

## Current Status

| Stage | Component | Difficulty | Template | Check | Mutate |
|---|---|---|---|---|---|
| 1 | Load Balancer | simple | templates/consistent_hash.py | check_01.py ✅ | mutate_01.py ✅ |
| 2 | CDN — Simple | simple | templates/cdn_caching.py | check_02.py ✅ | mutate_02.py ✅ |
| 3 | Object Storage — Simple | simple | templates/cache.py | check_03.py ✅ | mutate_03.py ✅ |
| 4 | Reverse Proxy — Simple | simple | templates/url_shortener.py | check_04.py ✅ | mutate_04.py ✅ |
| 5 | API Gateway — Simple | simple | templates/request_batching.py | check_05.py ✅ | mutate_05.py ✅ |
| 6 | Caching Layer (Redis) | moderate | templates/cache.py | check_06.py ✅ | mutate_06.py ✅ |
| 7 | Message Queue | moderate | templates/message_queue.py | check_07.py ✅ | mutate_07.py ✅ |
| 8 | Rate Limiter | moderate | templates/rate_limiter.py | check_08.py ✅ | mutate_08.py ✅ |
| 9 | Read Replicas | moderate | templates/leaderboard.py | check_09.py ✅ | mutate_09.py ✅ |
| 10 | Service Discovery | moderate | templates/consistent_hash.py | check_10.py ✅ | mutate_10.py ✅ |
| 11 | Database Sharding | complex | templates/hot_partition_mitigation.py | check_11.py ✅ | mutate_11.py ✅ |
| 12 | Event-Driven Architecture | complex | templates/eventual_consistency.py | check_12.py ✅ | mutate_12.py ✅ |
| 13 | Search Index | complex | templates/data_locality.py | check_13.py ✅ | mutate_13.py ✅ |
| 14 | Service Mesh | complex | templates/edge_computing.py | check_14.py ✅ | mutate_14.py ✅ |
| 15 | Cache Invalidation | complex | templates/capacity_planner.py | check_15.py ✅ | mutate_15.py ✅ |
| 16 | Sagas | extremely-complex | templates/connection_pooling.py | check_16.py ✅ | mutate_16.py ✅ |
| 17 | Consensus (Raft/Paxos) | extremely-complex | templates/session_stickiness.py | check_17.py ✅ | mutate_17.py ✅ |
| 18 | Exactly-Once Delivery | extremely-complex | templates/idempotency_keys.py | check_18.py ✅ | mutate_18.py ✅ |
| 19 | Global Rate Limiting | extremely-complex | templates/throttling.py | check_19.py ✅ | mutate_19.py ✅ |
| 20 | Multi-Region Active-Active | extremely-complex | templates/cdn_caching.py | check_20.py ✅ | mutate_20.py ✅ |

## How to Create a Stage

Each stage consists of:
1. `check_NN.py` — verifies correctness against the solution
2. `mutate_NN.py` — plants ≥34 mutations in the template, every one caught

### check_NN.py structure

```python
"""check_NN — <component name>.

Catches:
- Mutation 1: <description>
- Mutation 2: <description>
- ...
"""

import sys
import os

def _check_abc(s):
    """Test abc behavior."""
    # Test implementation
    assert condition, "Expected condition to be true"

def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "<component>.py")
    spec = importlib.util.spec_from_file_location("module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _check_abc(mod)
    # ... more checks ...

if __name__ == "__main__":
    try:
        check()
        print("check_NN: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"<component>: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"<component>: FAIL — {e}")
        sys.exit(1)
```

### mutate_NN.py structure

```python
"""mutate_NN — <component name>.

Plants ≥34 mutations in the template. Each mutation is:
  (target_line, replacement_line, label)
"""

import sys
import os
import tempfile
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))


def _m(template_text, replacement_text, label=""):
    return (template_text, replacement_text, label)


def main():
    import importlib.util

    # Load solution
    solution_path = os.path.join(HERE, "solutions", "<component>.py")
    if not os.path.exists(solution_path):
        solution_path = os.path.join(HERE, "<component>.py")

    with open(solution_path) as f:
        solution_content = f.read()

    # Define mutations to plant
    mutations = [
        _m("target_text", "replacement_text", "Mutation label"),
        # ... 34+ mutations ...
    ]

    caught = 0
    missed = 0

    for i, (template, replacement, label) in enumerate(mutations):
        tmpdir = tempfile.mkdtemp(prefix=f"mutate-NN-{i}-")
        try:
            mutated_content = solution_content.replace(template, replacement, 1)
            tmp_path = os.path.join(tmpdir, "<component>.py")
            with open(tmp_path, "w") as f:
                f.write(mutated_content)

            spec = importlib.util.spec_from_file_location(f"mutated_{i}", tmp_path)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                if hasattr(mod, "_test"):
                    mod._test()
                missed += 1
                print(f"  MUTATE {i+1:03d}: MISSED  {label}")
            except Exception:
                caught += 1
                print(f"  MUTATE {i+1:03d}: CAUGHT  {label}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"  MUTATE: CAUGHT {caught} / {caught + missed}  MISSED {missed}")
    return 0 if caught > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

## Verification

```bash
# Run all checks
python3 run_all.py

# Run all mutations
python3 mutate_all.py

# Check specific stages
python3 run_all.py 1 2 3

# Mutate specific stages
python3 mutate_all.py 6 7 8
```

## Complete Inventory (all 20 stages)

**Everything is built.** All check and mutate files are in place:

- `contract.md` — Course contract (laws, stage definitions, world/estate)
- `course.py` — Course manifest (20 stages with metadata)
- `check.py` — Main checker (imports all stages, runs _test())
- `check_01.py` through `check_20.py` — One per stage, each imports the template and runs assertions
- `mutate_01.py` through `mutate_20.py` — One per stage, each plants ~20 mutations in the solution
- `run_all.py` — Run all checks via subprocess
- `mutate_all.py` — Run all mutations via subprocess
- `templates/` — 18 template files (from system-design/)
- `solutions/` — 18 solution files (from system-design/)
- `docs/` — 20 learning docs across 4 difficulty tiers
- `codecrafters-reference/` — Links to real implementations (Nginx, Redis, Kafka, Raft, etc.)

## Verification

```bash
# Run all checks (imports each template, runs _test())
cd infrastructure-from-scratch
python3 run_all.py

# Run all mutations (plants mutations, checks each is caught)
python3 mutate_all.py

# Check or mutate specific stages
python3 run_all.py 1 2 3
python3 mutate_all.py 6 7 8
```

## How Each Check Works

Each `check_NN.py`:
1. Imports the template/solution via `importlib.util`
2. Runs assertions that verify correct behavior (classes exist, methods work)
3. Exits `0` if all pass, `2` if template is stub (NotImplementedError), `1` on error

## How Each Mutate Works

Each `mutate_NN.py`:
1. Reads the solution file
2. Plants mutations (text replacements that break behavior)
3. For each mutation: applies it in a temp dir, imports, runs `_test()`, verifies it's caught
4. Reports: `MUTATE: CAUGHT N / TOTAL  MISSED M`

## Resources

- `docs/simple/` — Learning docs for simple tier (what problem, how it works, real implementations, trade-offs)
- `docs/moderate/` — Learning docs for moderate tier
- `docs/complex/` — Learning docs for complex tier
- `docs/extremely-complex/` — Learning docs for extremely complex tier
- `codecrafters-reference/` — Links to real implementations (Nginx, Redis, Kafka, etc.)