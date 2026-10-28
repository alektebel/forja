#!/usr/bin/env python3
"""Bake the codecraft engine state into the static data the /forja page serves.

    python3 scripts/forja_data.py [output.json]

Reads the plan, manifests and checker status through codecraft (the same code
the CLI and `cz web` use) and writes one JSON file with:

  phases   — the ordered plan; each item is a plan id
  courses  — per plan id: title, kind, prereqs, stage metadata (id, file,
             title, tags, action, predict), the baked checker status, and the
             file list the browser runner needs (check.py + every template)

The page at diegoatencia.dev/forja fetches this file, renders the map from it,
and re-runs the checkers live in the browser via Pyodide against the templates
on raw.githubusercontent.com. localStorage holds the visitor's own results;
the baked `status` is the engine's ground truth at bake time.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from codecraft import manifests, serve  # noqa: E402


def main() -> int:
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        HERE, "site-dist", "forja", "data.json")

    state = serve.build_state()
    courses_meta = {c["name"]: c for c in manifests.discover()}

    data = {"generated": state["generated_at"],
            "repo": "alektebel/forja", "ref": "main",
            "phases": [], "courses": {}}

    for ph in state["phases"]:
        data["phases"].append({"code": ph["code"], "title": ph["title"],
                               "items": [i["id"] for i in ph["items"]]})
        for it in ph["items"]:
            checks = it.get("checks") or {}
            stages = it.get("stages") or []
            meta = courses_meta.get(it["course"]) if it["course"] else None
            files = sorted({s["file"] for s in stages if s.get("file")}) if meta else []
            if meta:
                files = sorted(set(os.listdir(meta["dir"])) &
                               {f for f in files} | {"check.py"})
            data["courses"][it["id"]] = {
                "id": it["id"], "title": it["title"], "kind": it["kind"],
                "why": it["why"], "prereq": it["prereq"],
                "course": it["course"], "command": it["command"],
                "state": it["state"],
                "checks": {"passed": checks.get("passed", 0),
                           "total": checks.get("total", 0)},
                "stages": stages,
                "files": files,
            }

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
