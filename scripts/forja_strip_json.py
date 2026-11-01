#!/usr/bin/env python3
"""Canonical JSON without wall-clock fields — used by the bake workflow."""

import json
import os
import sys


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    if not path or not os.path.isfile(path):
        print("")
        return 0
    data = json.load(open(path, encoding="utf-8"))
    data.pop("generated", None)
    data.pop("generated_at", None)
    print(json.dumps(data, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
