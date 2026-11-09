#!/usr/bin/env python3
"""Build the static /forja site tree that GitHub Pages serves.

    python3 scripts/forja_site.py [outdir]

Writes:

  outdir/
    index.html styles.css app.js   — the CodeCrafters-shaped catalog
    logos/*.svg                    — challenge + brand marks
    state.json                     — full codecraft serve.build_state() payload
    data.json                      — legacy map shape (files list for Pyodide /
                                     anything still reading the old schema)

CI copies this tree into alektebel/alektebel.github.io/forja on every push
to main (see .github/workflows/forja.yml).
"""

from __future__ import annotations

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from codecraft import manifests, serve, showcase, workspace  # noqa: E402

WEB = os.path.join(HERE, "codecraft", "web")
LOGOS = os.path.join(WEB, "logos")


def bake_data(state: dict) -> dict:
    """Legacy data.json shape used by older /forja consumers."""
    courses_meta = {c["name"]: c for c in manifests.discover()}
    data = {
        "generated": state["generated_at"],
        "repo": "alektebel/forja",
        "ref": "main",
        "brand": state.get("brand"),
        "showcase": state.get("showcase"),
        "next": state.get("next"),
        "totals": state.get("totals"),
        "phases": [],
        "courses": {},
    }
    for ph in state["phases"]:
        data["phases"].append({
            "code": ph["code"], "title": ph["title"],
            "items": [i["id"] for i in ph["items"]],
        })
        for it in ph["items"]:
            checks = it.get("checks") or {}
            stages = it.get("stages") or []
            meta = courses_meta.get(it["course"]) if it["course"] else None
            files = sorted({s["file"] for s in stages if s.get("file")}) if meta else []
            if meta:
                files = sorted(set(os.listdir(meta["dir"])) & set(files) | {"check.py"})
            data["courses"][it["id"]] = {
                "id": it["id"], "title": it["title"], "kind": it["kind"],
                "why": it["why"], "prereq": it["prereq"],
                "course": it["course"], "command": it["command"],
                "state": it["state"],
                "showcase": bool(it.get("showcase") or (
                    it["course"] and showcase.is_showcase(it["course"]))),
                "checks": {"passed": checks.get("passed", 0),
                           "total": checks.get("total", 0)},
                "stages": stages,
                "files": files,
            }
    return data


def bake_state(state: dict) -> dict:
    """state.json — what codecraft/web/app.js loads on the static host."""
    out = dict(state)
    out["repo"] = "alektebel/forja"
    out["ref"] = "main"
    out["generated"] = state["generated_at"]
    return out


def build(outdir: str) -> dict:
    os.makedirs(outdir, exist_ok=True)
    logos_out = os.path.join(outdir, "logos")
    os.makedirs(logos_out, exist_ok=True)

    for name in ("index.html", "styles.css", "app.js", "learning.js", "review.js", "editor.js", "py-worker.mjs"):
        src = os.path.join(WEB, name)
        if not os.path.isfile(src):
            raise SystemExit(f"missing web asset: {src}")
        shutil.copy2(src, os.path.join(outdir, name))

    vendor_src = os.path.join(WEB, "vendor")
    if os.path.isdir(vendor_src):
        shutil.copytree(vendor_src, os.path.join(outdir, "vendor"), dirs_exist_ok=True)

    for name in os.listdir(LOGOS):
        if name.endswith(".svg"):
            shutil.copy2(os.path.join(LOGOS, name), os.path.join(logos_out, name))

    state = serve.build_state()
    state_payload = bake_state(state)
    data_payload = bake_data(state)

    with open(os.path.join(outdir, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(state_payload, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(outdir, "data.json"), "w", encoding="utf-8") as fh:
        json.dump(data_payload, fh, ensure_ascii=False, indent=1)

    with open(os.path.join(outdir, "workspace.json"), "w", encoding="utf-8") as fh:
        json.dump(workspace.aws_bundle(), fh, ensure_ascii=False)

    return {
        "outdir": outdir,
        "phases": len(state["phases"]),
        "courses": sum(len(p["items"]) for p in state["phases"]),
        "showcase": len((state.get("showcase") or {}).get("track") or []),
        "logos": len([n for n in os.listdir(logos_out) if n.endswith(".svg")]),
    }


def main() -> int:
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        HERE, "site-dist", "forja")
    info = build(outdir)
    print(
        f"forja site: {info['showcase']} challenges, {info['courses']} path rows, "
        f"{info['logos']} logos -> {info['outdir']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
