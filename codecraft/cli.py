#!/usr/bin/env python3
"""codecraft — author and work through build-from-scratch courses.

    python3 codecraft/cli.py                      # your learning board
    python3 codecraft/cli.py path                 # the ordered plan, with progress
    python3 codecraft/cli.py run llm-from-scratch # run a course, get coached
    python3 codecraft/cli.py stage <course> [n]   # one stage: what you write, what it costs
    python3 codecraft/cli.py next                 # just the next action
    python3 codecraft/cli.py hint <course>        # one rung lower down the ladder
    python3 codecraft/cli.py explain [<course>]   # NAN model: what you're getting wrong
    python3 codecraft/cli.py ask "why ..."        # ask the NAN mentor about this stage
    python3 codecraft/cli.py review               # concepts still unretired
    python3 codecraft/cli.py status [<course>]    # mastery map
    python3 codecraft/cli.py publish [<course>]   # push the last run to the live page
    python3 codecraft/cli.py web                  # the skill tree in a browser
    python3 codecraft/cli.py config --style deep --mentor auto --model glm5.3
    python3 codecraft/cli.py self-test
"""

import json
import os
import sys
import urllib.error
import urllib.request

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from codecraft import (adapt, contract, manifests, mentor, patterns, progress,
                           render, scaffold, serve, stats, store, style)
    from codecraft import path as pathmod
else:                                                          # pragma: no cover
    from . import (adapt, contract, manifests, mentor, patterns, progress, render,
                   scaffold, serve, stats, store, style)
    from . import path as pathmod

HELP = __doc__


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _ink(colour):
    return render.Ink(colour)


def _load_or_die(name):
    course = manifests.load(name)
    if course is None:
        print(f"  no course named {name!r}. Try: python3 codecraft/cli.py list")
        sys.exit(2)
    return course


def _current_course(profile, courses, explicit=None):
    if explicit:
        return _load_or_die(explicit)
    names = [c["name"] for c in courses]
    last = None
    for name in names:
        c = profile["courses"].get(name)
        if c:
            ts = c.get("last_run", 0)
            if last is None or ts > last[0]:
                last = (ts, name)
    return _load_or_die(last[1]) if last else None


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_dashboard(profile, courses, ink):
    if not courses:
        print("  no courses found. Author one: python3 codecraft/cli.py new x")
        return
    print(render.render_dashboard(profile, courses, ink))


def cmd_path(profile, courses, ink):
    print(pathmod.render_path(profile, courses, ink))
    return 0


def cmd_run(profile, rest, ink, courses):
    brief = "--brief" in rest or "--quiet" in rest
    no_mentor = "--no-mentor" in rest
    flags = ("--brief", "--quiet", "--no-mentor")
    rest = [a for a in rest if a not in flags]
    if not rest:
        print("  usage: python3 codecraft/cli.py run <course> [checker args]")
        return 1
    course = _load_or_die(rest[0])
    checker_args = rest[1:] or None

    prior = profile["courses"].get(course["name"], {}).get("stages", {})
    before_status = {sid: row.get("last_status") for sid, row in prior.items()}

    result = contract.run_attempt(course, args=checker_args, echo=not brief)

    newly_passed, regressed = [], []
    for st in result["stages"]:
        prev = before_status.get(str(st["id"]))
        if st["status"] == "PASS" and prev != "PASS":
            newly_passed.append(st)
        elif st["status"] != "PASS" and prev == "PASS":
            regressed.append(st)

    attempt = {"course": course["name"], "title": course["title"],
               "mode": course["mode"], "ts": store.now(), **result}
    store.append_history({
        "ts": attempt["ts"], "course": course["name"], "mode": course["mode"],
        "passed": result["passed"], "failed": result["failed"],
        "todo": result["todo"], "next_step": result["next_step"],
        "stages": [{"id": s["id"], "status": s["status"]} for s in result["stages"]],
    })
    store.record_attempt(profile, attempt, manifests.stage_meta(course))
    store.save_profile(profile)

    advice = adapt.decide(profile, course, result, all_courses=courses)

    complete = bool(result["total"]) and result["passed"] == result["total"]
    failed_stage = next((s for s in result["stages"]
                         if s["status"] in ("FAIL", "ERROR")), None)

    if complete:
        print(style.course_complete(ink, course["title"], result["total"]))
    else:
        for st in newly_passed:
            row = profile["courses"][course["name"]]["stages"].get(str(st["id"]), {})
            print(style.stage_passed(
                ink, course["title"], st["id"], st["file"], st["title"],
                result["passed"], result["total"],
                first_try=row.get("attempts_to_pass") == 1))
        for st in regressed:
            print(style.regression(ink, st["id"], st["file"]))
        if failed_stage is not None:
            print(style.fail_header(ink, failed_stage["id"], failed_stage["file"],
                                    failed_stage["title"]))

    # The explanation comes immediately after the error, before any advice:
    # "here is what you got wrong", then "here is what to do".
    if failed_stage is not None and _mentor_should_fire(profile, advice, no_mentor):
        _mentor(profile, course, failed_stage["id"],
                failed_stage.get("detail", ""), ink)

    _publish_attempt(profile, course, result)
    print(render.render_advice(advice, course["stages"].get(advice["stage"], {}), ink))
    return 0 if result["failed"] == 0 else 1


def _publish_attempt(profile, course, result) -> None:
    """Push one finished attempt to the live page, silently when it is not up."""
    endpoint = profile["config"].get("publish", "").rstrip("/")
    if not endpoint:
        return
    payload = json.dumps({
        "course": course["name"], "title": course["title"],
        "passed": result["passed"], "total": result["total"],
        "failed": result["failed"], "todo": result["todo"],
        "next_step": result.get("next_step"),
        "stages": [{"id": s["id"], "file": s["file"], "title": s["title"],
                    "status": s["status"]} for s in result["stages"]],
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint + "/api/run", data=payload, method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("ok"):
                print(f"\n  \033[90m→ live on {endpoint}\033[0m")
    except (urllib.error.URLError, OSError, ValueError):
        pass        # no page listening; publishing is a bonus, never a failure


def cmd_publish(profile, rest, ink, courses):
    """Re-post a course's current state to the live page."""
    endpoint = profile["config"].get("publish", "").rstrip("/")
    if not endpoint:
        print("  no publish endpoint configured. `codecraft config --publish <url>`")
        return 2
    name = next((a for a in rest if not a.startswith("-")), None)
    target = _load_or_die(name) if name else _current_course(profile, courses)
    if target is None:
        print("  no course to publish. Run one first.")
        return 2
    outcome = contract.run_attempt(target, echo=False)
    _publish_attempt(profile, target, outcome)
    print(f"  {target['title']}: {outcome['passed']}/{outcome['total']} passing"
          f" → {endpoint}")
    return 0


def _mentor_should_fire(profile, advice, no_mentor):
    if no_mentor:
        return False
    mode = profile["config"].get("mentor", "auto")
    if mode == "auto":       # any failure, immediately
        return True
    if mode == "stuck":      # only when the history says you are circling
        return bool(advice.get("mentor"))
    return False             # manual | off


def _mentor(profile, course, stage_id, error, ink, force=False):
    usable, reason = mentor.available(profile)
    if not usable:
        if force or not reason.startswith("mentor is off"):
            print(f"\n  {ink('mentor unavailable:', render.YELLOW)} {reason}")
        return
    try:
        sections, model, cached = mentor.diagnose(profile, course, stage_id, error)
    except RuntimeError as exc:
        print(f"\n  {ink('mentor error:', render.RED)} {exc}")
        return
    label = model + (" \u00b7 cached" if cached else "")
    print("\n" + style.mentor_box(ink, sections, label))


def cmd_explain(profile, rest, ink, courses):
    positional = [a for a in rest if not a.startswith("-")]
    course = _current_course(profile, courses, positional[0] if positional else None)
    if course is None:
        print("  no course in progress. Run one first.")
        return 2
    stage = None
    for a in positional[1:]:
        if a.isdigit():
            stage = int(a)
    advice = adapt.decide(profile, course, all_courses=courses)
    stage = stage or advice.get("stage") or min(course["stages"] or {1: {}})
    error = profile["courses"].get(course["name"], {}).get("stages", {}) \
        .get(str(stage), {}).get("last_detail", "(no recorded failure)")
    print(style.fail_header(ink, stage,
                            course["stages"].get(stage, {}).get("file", ""),
                            course["stages"].get(stage, {}).get("title", "")))
    _mentor(profile, course, stage, error, ink, force=True)
    return 0


def cmd_ask(profile, rest, ink, courses):
    positional = [a for a in rest if not a.startswith("-")]
    if not positional:
        print('  usage: python3 codecraft/cli.py ask "your question" [course]')
        return 2
    question = positional[0]
    course = _current_course(profile, courses,
                             positional[1] if len(positional) > 1 else None)
    if course is None:
        print("  no course in progress. Run one first.")
        return 2
    advice = adapt.decide(profile, course, all_courses=courses)
    stage = advice.get("stage") or min(course["stages"] or {1: {}})
    usable, reason = mentor.available(profile)
    if not usable:
        print(f"  mentor unavailable: {reason}")
        return 2
    try:
        sections, model = mentor.ask(profile, course, stage, question)
    except RuntimeError as exc:
        print(f"  mentor error: {exc}")
        return 2
    print("\n" + style.mentor_box(ink, sections, model))
    return 0


def cmd_next(profile, rest, ink, courses):
    explicit = next((a for a in rest if not a.startswith("-")), None)
    course = _current_course(profile, courses, explicit)
    if course is None:
        return cmd_dashboard(profile, courses, ink) or 0
    advice = adapt.decide(profile, course, all_courses=courses)
    meta = course["stages"].get(advice["stage"], {})
    print(render.render_advice(advice, meta, ink))
    return 0


def cmd_hint(profile, rest, ink, courses):
    explicit = next((a for a in rest if not a.startswith("-")), None)
    course = _current_course(profile, courses, explicit)
    if course is None:
        print("  no course in progress. Run one first.")
        return
    advice = adapt.decide(profile, course, all_courses=courses)
    stage = advice["stage"] or min(course["stages"] or {1: {}})
    meta = course["stages"].get(stage, {})
    level = min(3, store.hint_level(profile, course["name"], stage) + 1)
    store.set_hint_level(profile, course["name"], stage, level)
    store.save_profile(profile)
    ladder = adapt.hints_for(advice, meta, level)
    print(render.render_hint(advice, meta, ladder, ink))


def cmd_status(profile, rest, ink, courses):
    explicit = next((a for a in rest if not a.startswith("-")), None)
    if not explicit:
        return cmd_dashboard(profile, courses, ink) or 0
    course = _load_or_die(explicit)
    cstate = profile["courses"].get(course["name"], {})
    rows = cstate.get("stages", {})
    print("")
    print(ink(f"  {course['title']}  \u2014  {course['description']}", render.BOLD))
    print("")
    for sid in sorted(course["stages"]):
        meta = course["stages"][sid]
        row = rows.get(str(sid), {})
        status = row.get("last_status")
        mark = {"PASS": ink("pass", render.GREEN),
                "FAIL": ink("fail", render.RED),
                "ERROR": ink("error", render.RED),
                "TODO": ink("todo", render.GREY)}.get(status, ink("\u2014", render.GREY))
        extra = ""
        if row:
            extra = (f"  attempts {row.get('attempts', 0)}"
                     f"  hints {row.get('hint_level', 0)}")
            if row.get("attempts_to_pass"):
                extra += f"  passed in {row['attempts_to_pass']}"
        print(f"  {sid:>2}. {meta['file']:<18} {meta['title'][:38]:<38} "
              f"{mark}{ink(extra, render.GREY)}")
    concepts = cstate.get("concepts", {})
    if concepts:
        print("")
        print(ink("  concepts", render.BOLD))
        for tag, c in sorted(concepts.items()):
            print(f"    {tag:<26} box {c.get('box', 0)}/3"
                  f"  ({render.store_label(c)})  fails {c.get('fails', 0)}")
    return 0


def cmd_stage(profile, rest, ink, courses):
    """One stage's page: the file, what you write in it, what the tester costs."""
    positional = [a for a in rest if not a.startswith("-")]
    name = positional[0] if positional else None
    want = None
    if len(positional) > 1:
        try:
            want = int(positional[1])
        except ValueError:
            print(f"  a stage is a number, not {positional[1]!r}")
            return 2

    course = manifests.load(name) if name else _current_course(profile, courses)
    if course is None:
        if not name:
            print("  no course to show. Name one: python3 codecraft/cli.py "
                  "stage <course>")
            return 2
        letter, phase, entry = pathmod.find(name)
        if entry is not None:
            course = manifests.load(entry["course"]) if entry.get("course") else None
            if course is None:
                print(render.render_plan(letter, phase, entry, ink))
                return 0
    if course is None:
        print(f"  no course named {name!r}. Try: python3 codecraft/cli.py list")
        return 2

    ids = sorted(course["stages"])
    if not ids:
        print(f"  {course['name']} has no stages yet.")
        return 1
    stages = profile["courses"].get(course["name"], {}).get("stages", {})
    statuses = {i: stages.get(str(i), {}).get("last_status", "TODO") for i in ids}
    if want is None:
        want = next((i for i in ids if statuses[i] != "PASS"), ids[-1])
    if want not in course["stages"]:
        print(f"  {course['name']} has stages 1..{ids[-1]}")
        return 2

    print(render.render_stage(
        course, want, course["stages"][want],
        stats.for_course(course["name"]).get(want),
        stages.get(str(want), {}), statuses, ink,
        f"python3 codecraft/cli.py run {course['name']}"))
    return 0


def cmd_review(profile, ink, courses):
    items = adapt._due_review(profile, limit=8)
    print(render.render_review(profile, items, ink))
    # re-running a course whose concepts are due is how you retire them
    return 0


def cmd_list(courses, ink):
    print("")
    for c in courses:
        print(f"  {c['name']:<24} {c['title']:<30} "
              f"{ink(c['mode'], render.GREY):<22} {ink(c['description'][:44], render.GREY)}")
    print("")


def cmd_new(rest, ink):
    positional = [a for a in rest if not a.startswith("-")]
    if not positional:
        print("  usage: python3 codecraft/cli.py new <slug> [--title T] "
              "[--stages N] [--force]")
        return 2

    def opt(flag, default=None):
        if flag in rest:
            i = rest.index(flag)
            if i + 1 < len(rest):
                return rest[i + 1]
        return default

    try:
        target = scaffold.create(
            positional[0], title=opt("--title", ""),
            description=opt("--description", ""),
            stages=int(opt("--stages", 2)), force="--force" in rest)
    except (FileExistsError, ValueError) as exc:
        print(f"  {exc}")
        return 2
    rel = os.path.relpath(target, manifests.REPO_ROOT)
    print(f"""
  created {rel}/
    course.py        the manifest: metadata + one check per stage
    stage_01.py ...  templates (raise NotImplementedError)
    solutions/       where the finished version goes
    README.md

  next:
    1. edit course.py and write the real assertions in each check
    2. python3 codecraft/cli.py run {rel}
    3. implement the stage, re-run; the tool adapts from there

  A course is its tests. Make the checks catch the mistakes that are easy to
  make and hard to notice — not line coverage.
""")


def cmd_config(profile, rest, ink):
    cfg = profile["config"]
    changed = False
    for flag, key, allowed in (("--style", "style", {"deep", "balanced", "fast"}),
                               ("--mentor", "mentor",
                                {"auto", "stuck", "manual", "off"})):
        if flag in rest:
            i = rest.index(flag)
            if i + 1 < len(rest) and rest[i + 1] in allowed:
                cfg[key] = rest[i + 1]
                changed = True
    if "--model" in rest:
        i = rest.index("--model")
        if i + 1 < len(rest):
            cfg["model"] = rest[i + 1]
            changed = True
    if "--publish" in rest:
        i = rest.index("--publish")
        if i + 1 < len(rest):
            cfg["publish"] = rest[i + 1]
            changed = True
    if changed:
        store.save_profile(profile)
    usable, reason = mentor.available(profile)
    status = ink("ready", render.GREEN) if usable else ink(reason, render.YELLOW)
    print(f"""
  style   {ink(cfg['style'], render.BOLD)}   deep = slower, more prediction; fast = accelerate sooner
  mentor  {ink(cfg['mentor'], render.BOLD)}   auto = explain every failure; stuck = only when circling; manual | off
  model   {ink(cfg['model'], render.BOLD)}
  status  {status}{ink('  (NAN_API_KEY / ' + mentor.endpoint(profile) + ')', render.GREY)}
  publish {ink(cfg.get('publish', '—'), render.BOLD)}   where `cz publish` POSTs run events (empty string = off)
""")
    return 0


# ---------------------------------------------------------------------------
# self-test
# ---------------------------------------------------------------------------

_SAMPLE = """
\033[1mLLM From Scratch \u2014 progress check\033[0m
  \033[32m\u2713\033[0m  1. tokenizer.py      pair counts
  \033[31m\u2717\033[0m  2. tokenizer.py      deterministic training
      training must be deterministic. Ties need an explicit rule.
      Got {1: 3}
  \033[90m\u00b7\033[0m  3. attention.py        stable softmax
      not implemented yet \u2014 attention.py:40 in softmax()

  1/13 passing, 1 failing, 1 to write

  \033[1mNext:\033[0m step 2 \u2014 deterministic training (tokenizer.py)
"""


def self_test() -> int:
    failures = []

    def ok(cond, msg):
        if cond:
            print(f"  ok   {msg}")
        else:
            failures.append(msg)
            print(f"  FAIL {msg}")

    print("\n  codecraft self-test\n")
    parsed = contract.parse_check_output(_SAMPLE)
    ok(parsed["passed"] == 1, "parses a passing stage")
    ok(parsed["failed"] == 1, "parses a failing stage")
    ok(parsed["todo"] == 1, "parses a TODO stage")
    ok(parsed["next_step"] == 2, "reads the next step")
    ok(parsed["stages"][1]["detail"].startswith("training must be"),
       "captures multi-line detail")

    ok(patterns.classify("top-p must keep the token that CROSSES the threshold")
       == "boundary/off-by-one", "classifies a boundary bug")
    ok(patterns.classify("exp(1000) overflowed") == "numerical stability",
       "classifies a stability bug")
    ok(patterns.signature("Got 42 from foo.py") ==
       patterns.signature("Got 99 from bar.py"),
       "signature ignores numbers and filenames")

    # decision logic on a synthetic story: same failure 3 runs running
    profile = {"config": {"style": "balanced"}, "patterns": {}, "courses": {}}
    course = {"name": "demo", "title": "Demo", "mode": "check", "dir": ".",
              "order": 1, "stages": {1: {"file": "a.py", "title": "t",
                                         "tags": ["boundary"], "action": "do x",
                                         "predict": "p", "hints": [],
                                         "solution": ""}}}
    attempt = {"course": "demo", "title": "Demo", "mode": "check",
               "ts": store.now(), "total": 1, "passed": 0, "failed": 1,
               "todo": 0, "next_step": 1,
               "stages": [{"id": 1, "file": "a.py", "title": "t",
                           "status": "FAIL",
                           "detail": "top-p must keep the crossing token"}]}
    for _ in range(3):
        store.record_attempt(profile, attempt, manifests.stage_meta(course))
    advice = adapt.decide(profile, course, attempt)
    ok(advice["kind"] == "stuck", "3 identical failures -> stuck")
    ok(advice["hint_level"] >= 1, "stuck raises the hint level")
    ok(profile["patterns"]["boundary/off-by-one"]["count"] == 3,
       "recurring category is recorded")

    # first-try streak -> accelerate
    profile2 = {"config": {"style": "balanced"}, "patterns": {}, "courses": {}}
    for sid in (1, 2):
        pass_attempt = {"course": "demo2", "title": "D", "mode": "check",
                        "ts": store.now(), "total": 3, "passed": sid,
                        "failed": 0, "todo": 3 - sid, "next_step": sid + 1,
                        "stages": [{"id": i, "file": f"{i}.py", "title": "t",
                                    "status": "PASS" if i <= sid else "TODO",
                                    "detail": ""} for i in (1, 2, 3)]}
        store.record_attempt(profile2, pass_attempt, {})
    cur = {"name": "demo2", "course": "demo2", "title": "D", "mode": "check",
           "dir": ".", "order": 1,
           "stages": {3: {"file": "3.py", "title": "t", "tags": [],
                          "action": "a", "predict": "p", "hints": [],
                          "solution": ""}}}
    advice2 = adapt.decide(profile2, cur, None)
    ok(advice2["kind"] in ("accelerate", "focused"),
       "clean streak yields accelerate/focused")

    print("")
    if failures:
        print(f"  {len(failures)} self-test failure(s)\n")
        return 1
    print("  all self-tests pass\n")
    return 0


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

def main(argv) -> int:
    colour = sys.stdout.isatty() and "--no-color" not in argv
    argv = [a for a in argv if a != "--no-color"]
    ink = _ink(colour)

    if not argv:
        argv = ["board"]
    if argv[0] in ("-h", "--help", "help"):
        print(HELP)
        return 0

    cmd, rest = argv[0], argv[1:]
    if cmd == "self-test":
        return self_test()

    profile = store.load_profile()
    courses = manifests.discover()

    if cmd == "list":
        cmd_list(courses, ink)
        return 0
    if cmd in ("board", "dashboard"):
        return cmd_dashboard(profile, courses, ink) or 0
    if cmd == "path":
        return cmd_path(profile, courses, ink) or 0
    if cmd == "progress":
        print(progress.render(courses, ink))
        return 0
    if cmd in ("web", "serve"):
        return serve.serve(rest)
    if cmd == "publish":
        return cmd_publish(profile, rest, ink, courses) or 0
    if cmd == "new":
        return cmd_new(rest, ink)
    if cmd == "config":
        return cmd_config(profile, rest, ink) or 0
    if cmd == "review":
        return cmd_review(profile, ink, courses) or 0
    if cmd == "run":
        return cmd_run(profile, rest, ink, courses) or 0
    if cmd == "next":
        return cmd_next(profile, rest, ink, courses) or 0
    if cmd == "hint":
        return cmd_hint(profile, rest, ink, courses) or 0
    if cmd == "status":
        return cmd_status(profile, rest, ink, courses) or 0
    if cmd == "stage":
        return cmd_stage(profile, rest, ink, courses) or 0
    if cmd == "explain":
        return cmd_explain(profile, rest, ink, courses) or 0
    if cmd == "ask":
        return cmd_ask(profile, rest, ink, courses) or 0

    print(f"  unknown command {cmd!r}\n")
    print(HELP)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
