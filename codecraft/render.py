"""Terminal rendering. The point is the *smallest* useful thing to read.

Default output after a run is the checker's own block plus three or four
coach lines. Detail escalates only when the history says you are stuck.
"""

import re
import textwrap

GREEN, RED, YELLOW, GREY, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[1m", "\033[0m")

# one glyph per stage state — the same four the web page draws
_STAGE_SYMBOL = {"PASS": "\u2713", "FAIL": "\u2717", "ERROR": "\u2717",
                 "TODO": "\u00b7"}
_STAGE_COLOUR = {"PASS": GREEN, "FAIL": RED, "ERROR": RED, "TODO": GREY}


class Ink:
    def __init__(self, colour: bool):
        self.colour = colour

    def __call__(self, text, code=""):
        if not self.colour or not code:
            return text
        return f"{code}{text}{RESET}"

    def bold(self, t):
        return self(t, BOLD)

    def grey(self, t):
        return self(t, GREY)


def _wrap(label, text, ink, width=76):
    if not text:
        return []
    head = textwrap.wrap(text, width=width) or [""]
    lines = [f"  {ink(label.ljust(7) + ' ', BOLD)}{head[0]}"]
    for extra in head[1:]:
        lines.append(f"  {' ' * 8}{extra}")
    return lines


def render_advice(advice, meta, ink: Ink):
    kind = advice["kind"]
    stage = advice.get("stage")
    where = ""
    if stage:
        where = (f"stage {stage}  {advice.get('file', '')}"
                 f"  \u2014 {advice.get('stage_title', '')}")
    lines = ["", ink(f"  codecraft \u00b7 {advice['title']}"
                     + (f" \u00b7 {where}" if where else ""), BOLD)]

    if kind == "not-started":
        lines += _wrap("start", advice["action"], ink)
        lines += _wrap("run", advice["pace"], ink)
        return "\n".join(lines)

    if kind == "done":
        lines += _wrap("done", advice["pace"], ink)
        if advice.get("pattern"):
            lines += _wrap("pattern", advice["pattern"], ink)
        if advice.get("review"):
            labels = ", ".join(f"{t} ({n})" for n, t, _ in advice["review"])
            lines += _wrap("review", f"still unretired: {labels}. "
                                     f"run: python3 codecraft/cli.py review", ink)
        return "\n".join(lines)

    lines += _wrap("cause", advice["cause"] or "no detail captured", ink)

    if kind == "accelerate":
        lines += _wrap("pace", advice["pace"], ink)
        lines += _wrap("next", f"open stage {stage} ({advice['file']}) and "
                               f"implement it without hints.", ink)
        return "\n".join(lines)

    lines += _wrap("now", advice["action"] or "re-read the stage docstring.", ink)

    if advice.get("hint_level", 0) >= 1 and kind in ("stuck", "flailing"):
        lines += _wrap("pace", advice["pace"], ink)
        lines += _wrap("try", advice["experiment"], ink)
    elif kind == "focused":
        lines += _wrap("pace", advice["pace"], ink)

    if advice.get("predict"):
        lines += _wrap("predict", advice["predict"], ink)
    if advice.get("pattern"):
        lines += _wrap("pattern", advice["pattern"], ink)
    if advice.get("reference") and advice.get("hint_level", 0) >= 2:
        lines += _wrap("ref", advice["reference"], ink)
    if advice.get("hint_hint"):
        lines += [f"  {ink(advice['hint_hint'], GREY)}"]
    return "\n".join(lines)


def render_hint(advice, meta, ladder, ink: Ink):
    lines = ["", ink(f"  codecraft \u00b7 hint ladder for stage "
                     f"{advice.get('stage')} ({advice.get('file')})", BOLD)]
    for i, hint in enumerate(ladder):
        lines += _wrap(f"hint {i}", hint, ink)
    lines += [f"  {ink('read top-down; stop as soon as you can act.', GREY)}"]
    return "\n".join(lines)


def render_dashboard(profile, courses, ink: Ink):
    lines = ["", ink("  codecraft \u00b7 your learning board", BOLD), ""]
    for course in courses:
        cstate = profile["courses"].get(course["name"], {})
        total = cstate.get("total") or len(course["stages"])
        passed = cstate.get("last_passed", 0)
        if not cstate:
            state = ink("not started", GREY)
            nxt = f"start stage {min(course['stages']) if course['stages'] else 1}"
        elif passed == total and total:
            state = ink("complete", GREEN)
            nxt = "author or pick the next course"
        else:
            state = ink(f"{passed}/{total}", YELLOW if passed else GREY)
            nxt = f"stage {cstate.get('next_step')} " \
                  f"({course['stages'].get(cstate.get('next_step'), {}).get('file', '')})"
        lines.append(f"  {course['title']:<32} {state:<20} {ink(nxt, GREY)}")
    pats = profile.get("patterns", {})
    top = sorted(pats.items(), key=lambda kv: kv[1].get("count", 0), reverse=True)[:3]
    if top:
        lines.append("")
        lines.append(ink("  recurring mistakes", BOLD))
        for label, row in top:
            lines.append(f"    {label:<26} {row['count']}x across "
                         f"{len(row['courses'])} courses")
    lines.append("")
    lines.append(ink("  next: python3 codecraft/cli.py run <course>", GREY))
    lines.append(ink("  plan: python3 codecraft/cli.py path", GREY))
    return "\n".join(lines)


def render_review(profile, items, ink: Ink):
    lines = ["", ink("  codecraft \u00b7 review queue", BOLD), ""]
    if not items:
        lines.append("  nothing due \u2014 concepts you stumble on surface here.")
        return "\n".join(lines)
    for name, tag, c in items:
        lines.append(f"  {ink(tag, BOLD)}  {ink('(' + name + ')', GREY)}")
        lines.append(f"    failed {c.get('fails', 0)}x, "
                     f"{store_label(c)}. Re-derive it from memory, then re-run "
                     f"the course to retire it.")
    return "\n".join(lines)


def _stage_slug(entry):
    return entry.get("course") or re.sub(r"[^a-z0-9]+", "-",
                                         entry["title"].lower()).strip("-")


def render_stage(course, sid, meta, size, live, statuses, ink: Ink, command):
    """One stage as a page: what you write, what it costs, where you are."""
    ids = sorted(statuses)
    lines = ["", ink(f"  codecraft \u00b7 {course['title']} \u00b7 stage {sid} "
                     f"of {len(ids)}", BOLD), ""]
    lines.append(f"  {ink(meta.get('file') or '\u2014', BOLD)}"
                 f"  \u2014 {meta.get('title') or ''}")

    status = live.get("last_status", "TODO")
    attempts = live.get("attempts", 0)
    note = ("nothing has run this stage yet" if not attempts else
            f"{attempts} attempt{'' if attempts == 1 else 's'}")
    lines.append(f"  {ink('status'.ljust(8), BOLD)}"
                 f"{ink(status, _STAGE_COLOUR.get(status, GREY))}  {note}")
    if live.get("last_detail"):
        lines += _wrap("last", live["last_detail"], ink)
    if size:
        tests, mutants = size
        text = f"{tests} asserts"
        text += (f" \u00b7 {mutants} planted mutations the check must catch"
                 if mutants is not None else
                 " \u00b7 mutations not measured for this course")
        lines += _wrap("size", text, ink)
    else:
        lines += _wrap("size", "not measured \u2014 this course predates the "
                               "count", ink)
    if meta.get("tags"):
        lines += _wrap("tags", ", ".join(meta["tags"]), ink)

    lines.append("")
    lines += _wrap("what", meta.get("action") or "read the stage docstring.", ink)
    if meta.get("predict"):
        lines += _wrap("predict", meta["predict"], ink)
    for hint in meta.get("hints") or []:
        lines += _wrap("hint", hint, ink)
    if meta.get("solution"):
        lines += _wrap("solve", meta["solution"], ink)

    passed = sum(1 for i in ids if statuses[i] == "PASS")
    bar = "".join(ink(_STAGE_SYMBOL.get(statuses[i], "\u00b7"),
                      _STAGE_COLOUR.get(statuses[i], GREY)) for i in ids)
    lines.append("")
    lines.append(f"  {ink('run'.ljust(8), BOLD)}{command}")
    lines.append(f"  {ink('ladder'.ljust(8), BOLD)}{bar}  {passed} of "
                 f"{len(ids)} passed")
    lines.append(ink("  stops at the first stage that fails; add --brief to "
                     "keep it to one", GREY))
    return "\n".join(lines)


def render_plan(letter, phase, entry, ink: Ink):
    """A registered course with no directory yet: the row, and how to start it."""
    slug = _stage_slug(entry)
    lines = ["", ink(f"  codecraft \u00b7 {entry['title']} \u00b7 not authored yet",
                     BOLD), ""]
    lines += _wrap("phase", f"{letter} \u2014 {phase} \u00b7 {entry['kind']}", ink)
    lines += _wrap("needs", ", ".join(entry["prereq"]) or "nothing", ink)
    lines += [""]
    lines += _wrap("why", entry["why"], ink)
    lines += [""]
    lines.append(f"  {ink('start'.ljust(8), BOLD)}"
                 f"python3 codecraft/cli.py new {slug} --stages 10")
    lines.append(ink(f"  then: python3 codecraft/cli.py run {slug}", GREY))
    return "\n".join(lines)


def _title(text, width=34):
    """A row title squeezed into the DAG's column, with a visible cut."""
    return text if len(text) <= width else text[:width - 1] + "\u2026"


def render_dag(g, ink: Ink):
    """The registry as one DAG: waves of work, then the advisory layer."""
    edges = sum(len(v) for v in g["edges"].values())
    lines = ["", ink(f"  codecraft \u00b7 the dependency DAG \u00b7 {len(g['ids'])} "
                     f"projects \u00b7 {edges} hard edges \u00b7 {len(g['waves'])} "
                     f"waves", BOLD),
             ink("  a row appears once, in the wave its longest path puts it in; "
                 "only `prereq` is an edge", GREY)]
    if g["cycles"]:
        lines += _wrap("cycle", " | ".join("\u2192".join(c) for c in g["cycles"]),
                       ink)
    if g["dangles"]:
        lines += _wrap("dangling", ", ".join(g["dangles"]) + " \u2014 named as a "
                       "prereq, no such row", ink)
    by_id = {n["id"]: n for n in g["nodes"]}
    for n, wave in enumerate(g["waves"]):
        after = "nothing must come first" if not n else (
            "after 1 wave" if n == 1 else f"after {n} waves")
        lines.append("")
        lines.append(ink(f"  wave {n} \u00b7 {after}", YELLOW))
        for rid in wave:
            node = by_id[rid]
            opens = g["dependents"].get(rid) or []
            tail = ("unlocks " + " ".join(opens)) if opens else "unlocks nothing yet"
            lines.append(f"  {ink(node['symbol'], GREY)} {rid:<4}"
                         f"{_title(node['title']):<36}{node['kind']:<8}"
                         f"{ink(tail, GREY)}")
    lines.append("")
    lines.append(ink("  good first \u00b7 nothing forces these, a thesis asks for "
                     "them", YELLOW))
    for rid in g["ids"]:
        for other, reason in g["advice"].get(rid, ()):
            lines.append(f"  {ink('\u00b7', GREY)} {rid:<4}after {other}")
            lines += _wrap("", reason, ink)
    lines.append("")
    lines.append(ink("  \u25cb ready  \u270e to author  \u00b7 legacy, no checker  "
                     "\u21bb port a branch", GREY))
    lines.append(ink(f"  zoom on one row: python3 codecraft/cli.py dag <course>",
                     GREY))
    return "\n".join(lines)


def render_dag_row(info, g, ink: Ink):
    """One row: everything that must come first, in wave order, and what it opens."""
    node = info["node"]
    by_id = {n["id"]: n for n in g["nodes"]}
    head = f"{node['id']} \u00b7 {node['title']}"
    head += f" \u00b7 {node['course']}" if node.get("course") else " \u00b7 not authored yet"
    lines = ["", ink("  codecraft \u00b7 " + head, BOLD), ""]
    lines += _wrap("phase", f"{node['letter']} \u2014 {node['phase']}", ink)
    lines += _wrap("wave", f"{info['wave']} of {info['waves'] - 1} \u00b7 "
                           f"{node['kind']} \u00b7 {len(info['before'])} row"
                           f"{'' if len(info['before']) == 1 else 's'} before it", ink)
    if info["needs"]:
        lines += _wrap("needs", ", ".join(
            f"{rid} {by_id.get(rid, {}).get('title', '?')}" for rid in info["needs"]),
            ink)
    else:
        lines += _wrap("needs", "nothing", ink)

    for title, ids in (("everything that must come first, in wave order",
                        info["before"]),
                       ("what it opens, transitively", info["after"])):
        if not ids:
            continue
        lines.append("")
        lines.append(ink("  " + title, YELLOW))
        for rid in ids:
            other = by_id.get(rid)
            lines.append(f"  {ink(other['symbol'], GREY)} {rid:<4}"
                         f"{_title(other['title']):<36}"
                         f"{ink('wave ' + str(g['levels'].get(rid, 0)), GREY)}")

    lines.append("")
    if info["advice"]:
        for other, reason in info["advice"]:
            lines.append(f"  {ink('advice'.ljust(8), BOLD)}after {other}")
            lines += _wrap("", reason, ink)
    else:
        lines += _wrap("advice", "nothing extra \u2014 the prereqs are the whole "
                                 "story", ink)
    lines += _wrap("why", node["why"], ink)
    lines.append("")
    lines.append(f"  {ink('next'.ljust(8), BOLD)}python3 codecraft/cli.py stage "
                 f"{node['id']}")
    return "\n".join(lines)


def render_briefs(rows, ink: Ink):
    """The rows still to author, one line each: what `cz brief` opens with."""
    lines = ["", ink(f"  codecraft \u00b7 {len(rows)} rows still to author", BOLD),
             ink("  each row carries its own thesis in codecraft/path.py; "
                 "`brief <row>` reads one in full", GREY), ""]
    for row in rows:
        lines.append(f"  {ink(row['symbol'], GREY)} {row['id']:<4}"
                     f"{_title(row['title']):<36}{ink(row['name'], GREY)}")
    lines.append("")
    first = rows[0]["id"] if rows else "L2"
    lines.append(ink("  one in full: python3 codecraft/cli.py brief %s" % first,
                     GREY))
    return "\n".join(lines)


def render_brief(brief, ink: Ink):
    """One row's brief: the row and its place, the house rules, the reading, the bar."""
    row = brief["row"]
    head = f"{row['id']} \u00b7 {row['title']}"
    head += f" \u00b7 {row['course']}" if row.get("course") else " \u00b7 not authored yet"
    lines = ["", ink("  codecraft \u00b7 authoring brief \u00b7 " + head, BOLD), ""]
    for label, text in brief["facts"]:
        if label == "why":
            lines.append("")
        lines += _wrap(label, text, ink)

    lines.append("")
    lines.append(ink("  guidelines \u00b7 every course here is written under these",
                     YELLOW))
    for label, text in brief["guidelines"]:
        lines += _wrap(label, text, ink)

    lines.append("")
    lines.append(ink("  read first", YELLOW))
    for label, text in brief["resources"]:
        lines += _wrap(label, text, ink)

    lines.append("")
    lines.append(ink("  the bar \u00b7 a finished course clears all of it", YELLOW))
    label, text = brief["spec"]
    lines += _wrap(label, text, ink)
    lines.append("")
    for number, req in enumerate(brief["requirements"], start=1):
        body = textwrap.wrap(req, width=72) or [""]
        lines.append(f"  {ink(str(number).rjust(2) + '.', BOLD)} {body[0]}")
        for extra in body[1:]:
            lines.append(f"      {extra}")

    lines.append("")
    lines.append(ink(f"  next: python3 codecraft/cli.py stage {brief['name']} "
                     f"\u2014 the row, its prereqs and where to start", GREY))
    return "\n".join(lines)


def store_label(c):
    return {0: "shaky", 1: "learning", 2: "getting there",
            3: "solid"}.get(c.get("box", 0), "learning")
