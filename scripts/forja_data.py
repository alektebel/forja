#!/usr/bin/env python3
"""Bake the legacy data.json the /forja page (and older consumers) read.

Prefer `scripts/forja_site.py` — that builds the full static tree
(index/css/js/logos + state.json + data.json) for GitHub Pages.

    python3 scripts/forja_data.py [output.json]
"""

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

_SITE = os.path.join(HERE, "scripts", "forja_site.py")
_spec = importlib.util.spec_from_file_location("forja_site", _SITE)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

from codecraft import serve  # noqa: E402


def main() -> int:
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        HERE, "site-dist", "forja", "data.json")

    state = serve.build_state()
    data = _mod.bake_data(state)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    n = len(data["courses"])
    runnable = sum(1 for c in data["courses"].values() if c["files"])
    print(f"forja data: {len(data['phases'])} phases, {n} courses "
          f"({runnable} with a runnable checker) -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
