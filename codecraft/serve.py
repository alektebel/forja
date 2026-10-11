#!/usr/bin/env python3
"""codecraft web — the skill tree and the next action, in a browser.

A read-only view over the same engine the CLI uses. It runs the same checkers,
reads the same curriculum, and shows the exact command to run in your terminal:
the CLI is the interface, this is the map.

    python3 codecraft/serve.py            # http://127.0.0.1:8766
    python3 codecraft/serve.py --json     # print the state and exit
    python3 codecraft/serve.py --port 9000 --open

Nothing here writes `profile.json` or `history.jsonl`; looking is free.
"""

import argparse
import datetime
import http.server
import json
import os
import sys
import threading
import time
import webbrowser
from urllib.parse import urlparse

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from codecraft import contract, manifests, progress, store
    from codecraft import path as pathmod
else:                                                           # pragma: no cover
    from . import contract, manifests, progress, store
    from . import path as pathmod

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")

MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8", ".svg": "image/svg+xml",
        ".json": "application/json; charset=utf-8", ".ico": "image/x-icon"}

# Long-poll: wait up to this many seconds for the next run event before
# answering /api/events with an empty batch. Long-polling rather than SSE so a
# static-host mirror (GitHub Pages) can consume the same client code.
POLL_TIMEOUT = 25.0
# Events older than this are dropped from the queue: a viewer that reconnects
# wants the current state, not a replay of stale runs.
EVENT_TTL = 120.0

_lock = threading.Lock()
_events: list = []          # [{...run event...}], newest last, TTL-pruned
_wake = threading.Condition(_lock)
_seq = 0


def _prune_locked(now: float) -> None:
    global _events
    _events = [e for e in _events if now - e["ts"] <= EVENT_TTL]


def publish_run(event: dict) -> dict:
    """Record one checker run (from `cz publish` or anything else) for the page."""
    global _seq
    now = time.time()
    with _lock:
        _seq += 1
        event = dict(event)
        event["ts"] = now
        event["seq"] = _seq
        _prune_locked(now)
        _events.append(event)
        _wake.notify_all()
    return event


def events_since(since: float, timeout: float = POLL_TIMEOUT) -> list:
    """Run events newer than `since` (a client-visible seq), blocking briefly."""
    deadline = time.monotonic() + timeout
    with _lock:
        while True:
            _prune_locked(time.time())
            fresh = [e for e in _events if e["seq"] > since]
            if fresh or time.monotonic() >= deadline:
                return fresh
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return []
            _wake.wait(remaining)


def recent_events(limit: int = 20) -> list:
    with _lock:
        _prune_locked(time.time())
        return list(_events[-limit:])

_SYMBOL = {"complete": "\u2713", "doing": "\u25cf", "ready": "\u25cb",
           "author": "\u270e", "salvage": "\u21bb", "legacy": "\u00b7",
           "missing": "\u2205"}


# ---------------------------------------------------------------------------
# the state the page renders
# ---------------------------------------------------------------------------

def _item_view(item, course, checks, repo, dir_exists=False) -> dict:
    kind = item["kind"]
    total = (checks or {}).get("total") or (len(course["stages"]) if course else 0)
    passed = (checks or {}).get("passed") or 0

    if kind == "ready" and course is None:
        state = "legacy" if dir_exists else "missing"
    elif kind == "ready" and checks and total and passed == total:
        state = "complete"
    elif kind == "ready" and ((checks and passed) or
                              (repo and repo["remaining"] < repo["baseline"])):
        state = "doing"
    elif kind == "ready":
        state = "ready"
    else:
        state = kind

    stages = []
    if course:
        stage_rows = (checks or {}).get("stages", {})
        for sid in sorted(course["stages"]):
            meta = course["stages"][sid]
            row = stage_rows.get(str(sid), {})
            stages.append({
                "id": sid, "file": meta.get("file", ""),
                "title": meta.get("title", ""), "tags": list(meta.get("tags", [])),
                "status": row.get("status", "TODO"),
                "action": meta.get("action", ""), "predict": meta.get("predict", ""),
            })

    return {
        "id": item["id"], "title": item["title"], "kind": kind,
        "why": item["why"], "prereq": item["prereq"], "state": state,
        "symbol": _SYMBOL.get(state, "\u00b7"),
        "course": item["course"],
        "command": f"cz run {item['course']}" if (item["course"] and course) else None,
        "checks": checks and {"passed": passed, "total": total,
                              "fraction": round(passed / total, 4) if total else 0.0},
        "repo": repo,
        "next_step": (checks or {}).get("next_step"),
        "stages": stages,
    }


def _next_action(phases) -> dict:
    """The first ready course in plan order that still has a check to pass."""
    for phase in phases:
        for item in phase["items"]:
            if item["kind"] != "ready" or item["state"] in ("complete", "missing"):
                continue
            course = item["course"]
            step = item["next_step"] or 1
            meta = next((s for s in item["stages"] if s["id"] == step), None)
            return {
                "id": item["id"], "title": item["title"], "course": course,
                "command": f"cz run {course}",
                "checks": item["checks"], "repo": item["repo"],
                "stage": step, "file": (meta or {}).get("file", ""),
                "stage_title": (meta or {}).get("title", ""),
                "action": (meta or {}).get("action", ""),
                "predict": (meta or {}).get("predict", ""),
            }
    return None


def _concepts(profile) -> list:
    out = []
    for name, cstate in profile.get("courses", {}).items():
        for tag, row in cstate.get("concepts", {}).items():
            box = row.get("box", 0)
            out.append({"course": name, "tag": tag, "box": box,
                        "fails": row.get("fails", 0),
                        "label": store.BOX_LABELS.get(box, "")})
    out.sort(key=lambda c: (c["box"], -c["fails"], c["tag"]))
    return out


def build_state(profile=None, courses=None) -> dict:
    profile = store.load_profile() if profile is None else profile
    courses = manifests.discover() if courses is None else courses
    by_name = {c["name"]: c for c in courses}

    rows = progress.build(courses)
    row_by_name = {r["name"]: r for r in rows}
    checks_by_name = {r["name"]: r["checks"] for r in rows}
    repo_by_name = {r["name"]: r["repo"] for r in rows}

    totals = {"courses": 0, "complete": 0, "doing": 0, "ready": 0, "missing": 0,
              "checks_passed": 0, "checks_total": 0,
              "repo_remaining": 0, "repo_baseline": 0}

    phases = []
    for code, title, items in pathmod.PHASES:
        view_items = []
        for item in items:
            name = item["course"]
            course = by_name.get(name) if name else None
            dir_exists = bool(name) and os.path.isdir(os.path.join(manifests.REPO_ROOT, name))
            view = _item_view(item, course, checks_by_name.get(name),
                              repo_by_name.get(name), dir_exists)
            if item["kind"] == "ready":
                state = view["state"]
                if state in ("complete", "doing", "ready"):
                    totals["courses"] += 1
                    totals[state] += 1
                    if view["checks"]:
                        totals["checks_passed"] += view["checks"]["passed"]
                        totals["checks_total"] += view["checks"]["total"]
                    if view["repo"]:
                        totals["repo_remaining"] += view["repo"]["remaining"]
                        totals["repo_baseline"] += view["repo"]["baseline"]
                else:
                    totals[state] = totals.get(state, 0) + 1
            view_items.append(view)
        phases.append({"code": code, "title": title, "items": view_items})

    written = totals["repo_baseline"] - totals["repo_remaining"]
    totals["repo_fraction"] = (round(written / totals["repo_baseline"], 4)
                               if totals["repo_baseline"] else 0.0)

    return {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "order": ("AWS, LLM internals, RAG, evals + agents, MCP, harness, "
                  "benchmark, eval, then the machine stack"),
        "totals": totals,
        "next": _next_action(phases),
        "phases": phases,
        "concepts": _concepts(profile),
        "courses": rows,
    }


# ---------------------------------------------------------------------------
# the server
# ---------------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    state = None

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    def _send(self, code, body, content_type):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload, code=200):
        self._send(code, json.dumps(payload), MIME[".json"])

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._file("index.html")
        if path == "/api/state":
            Handler.state = build_state()
            return self._json(Handler.state)
        if path == "/api/health":
            return self._json({"ok": True})
        if path == "/api/events":
            query = urlparse(self.path).query
            since = 0.0
            for part in query.split("&"):
                if part.startswith("since="):
                    try:
                        since = float(part[6:])
                    except ValueError:
                        since = 0.0
            got = events_since(since)
            return self._json({"events": got, "now": time.time()})
        if path == "/api/runs":
            return self._json({"events": recent_events()})
        return self._file(path.lstrip("/"))

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/run":
            return self._send(404, "not found", "text/plain; charset=utf-8")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            event = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (ValueError, UnicodeDecodeError):
            return self._send(400, "bad json", "text/plain; charset=utf-8")
        # Only accept runs whose course the local repo actually knows; anything
        # else is a typo or an attack, and either way it renders as nothing.
        allowed = {c["name"] for c in manifests.discover()}
        if event.get("course") not in allowed:
            return self._json({"ok": False, "error": "unknown course"}, code=422)
        stored = publish_run({
            "course": event["course"],
            "title": str(event.get("title") or event["course"])[:120],
            "passed": int(event.get("passed") or 0),
            "total": int(event.get("total") or 0),
            "failed": int(event.get("failed") or 0),
            "todo": int(event.get("todo") or 0),
            "next_step": event.get("next_step"),
            "stages": [
                {"id": int(s.get("id") or 0), "file": str(s.get("file") or "")[:80],
                 "title": str(s.get("title") or "")[:160],
                 "status": s.get("status") if s.get("status") in ("PASS", "FAIL", "ERROR", "TODO") else "TODO"}
                for s in (event.get("stages") or [])
            ][:400],
        })
        return self._json({"ok": True, "seq": stored["seq"]})

    def _file(self, rel):
        target = os.path.normpath(os.path.join(WEB, rel))
        if not target.startswith(WEB) or not os.path.isfile(target):
            return self._send(404, "not found", "text/plain; charset=utf-8")
        with open(target, "rb") as fh:
            body = fh.read()
        ext = os.path.splitext(target)[1]
        self._send(200, body, MIME.get(ext, "application/octet-stream"))


def serve(argv) -> int:
    parser = argparse.ArgumentParser(prog="codecraft web", add_help=True)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--open", action="store_true", help="open a browser")
    parser.add_argument("--json", action="store_true",
                        help="print the state as JSON and exit")
    args = parser.parse_args(argv)

    if args.json:
        print(json.dumps(build_state(), indent=2))
        return 0

    Handler.state = build_state()
    httpd = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"\n  codecraft web \u2014 {url}")
    print("  live: every `cz publish` updates the page. Ctrl-C to stop.")
    if args.open:
        try:
            webbrowser.open(url)
        except Exception:                                      # noqa: BLE001
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(serve(sys.argv[1:]))
