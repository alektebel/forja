"""The brief for one row of the registry: what to write, and to what bar.

`codecraft path` says what to build and in what order; `codecraft dag` says what
must come first. Neither says how a course in this repository is written, and
that is what a brief is for: the house rules every course here is under, the
documents the row's own words point at, and the checklist a finished course has
to clear before the row is flipped to `ready`.

Nothing here is invented. The guidelines are the rules the courses that pass the
audit are written under — read off `os-from-scratch/course.py` and its ten
stages, off the seventeen courses beside it, and off the `audit_course.py` that
enforces them stage by stage (`.g4-dev/audit_course.py`, copied into every dev
directory since). The bar is read off `codecraft/README.md`, `codecraft/api.py`,
`codecraft/stats.py` and the workflow `NEXT-SESSION.md` records.

`brief` and `briefs` return plain data — dicts, tuples and strings — and never
print anything: `render.render_brief` is the console form.
"""

import os
import re

from . import dag, manifests
from . import path as pathmod

# Where the authoring scratch directories sit: beside the repository, never
# inside it. `../.l1-dev/CONTRACT.md` is what a row with a frozen plan owns.
BESIDE = os.path.dirname(manifests.REPO_ROOT)

# The rows whose plan was frozen in a contract document before stage 1, and
# where to find it. The directory is named for the slot the plan gave the course
# when the plan was written — A8's is `.h2-dev` — so the mapping is spelled out
# rather than derived. `brief` reports a document only when it is really there.
CONTRACTS = {
    "G4": ".g4-dev/CONTRACT.md",
    "H1": ".h1-dev/CONTRACT.md",
    "A8": ".h2-dev/CONTRACT.md",
    "I9": ".i9-dev/CONTRACT.md",
    "J1": ".j1-dev/CONTRACT.md",
    "J2": ".j2-dev/CONTRACT.md",
    "J3": ".j3-dev/CONTRACT.md",
    "J4": ".j4-dev/CONTRACT.md",
    "K6": ".fde-dev/CONTRACT.md",
    "J5": ".j5-dev/CONTRACT.md",
    "L1": ".l1-dev/CONTRACT.md",
    "L2": ".l2-dev/CONTRACT.md",
    "L3": ".l3-dev/CONTRACT.md",
}

# ---------------------------------------------------------------------------
# the guidelines — one statement of the house rules, for every course here
# ---------------------------------------------------------------------------

GUIDELINES = (
    ("stdlib",
     "Standard library only, and nothing to install: a course runs on `python3` "
     "alone, the way `codecraft` itself does."),
    ("floats",
     "No float anywhere — not in a template, a solution, a fixture or a check. "
     "Every count, size, tick, side and ratio is an `int` (a ratio is an exact "
     "pair), and the audit fails a stage that carries a float literal."),
    ("clock",
     "Deterministic and offline, with the clock injected: no wall clock, no "
     "sleeps, no polling, no `random`. Time is a number the world hands in "
     "(a `Clock`, an `advance`, a tick argument), so a run is a function of its "
     "inputs and a check asserts a number instead of timing something."),
    ("state",
     "No module-level mutable state: fixtures are built inside the check, so "
     "nothing a stage does changes what the next one sees, and two runs of one "
     "fixture are byte-identical."),
    ("banned",
     "Banned imports, on the template *and* the solution, by the audit: `time`, "
     "`threading`, `asyncio`, `random`, `os`, `uuid`, `socket`, `subprocess`, "
     "`secrets`, `shutil`, `tempfile`, `pathlib`, `math`, `statistics`, "
     "`decimal`, `fractions`."),
    ("imports",
     "A stage imports the provided world and *earlier* stages only — the audit "
     "refuses a later one by name. If a stage looks like it needs a sibling that "
     "is not earlier, build the fixture by hand from the world's frozen shapes "
     "instead."),
    ("template",
     "A template ships the surface, never the answer: its first docstring "
     "paragraph is exactly `<TITLE> \u2014 stage NN: <title>`, then three to six "
     "`DESIGN DECISION \u2014 ` blocks, then a `TODO: implement` line. Public "
     "constants carry their real values and every public function or method is a "
     "docstring followed by exactly one "
     "`raise NotImplementedError(\"stage NN: implement f()\")`."),
    ("solution",
     "The solution — `solutions/stage_NN.py` — declares *every* public name the "
     "template declares and no fewer, and it is dropped over the template rather "
     "than merged with it: the template in the course directory stays the "
     "exercise."),
    ("check",
     "One check per stage, declared in the manifest as `check_N` and developed "
     "standalone as `check_NN.py`: assertions whose messages name the mistake and "
     "the value that arrived, every refusal pinned by its wording, and "
     "`NotImplementedError` let escape — a broad `except` re-raises it first — so "
     "an untouched template reports `not implemented yet` instead of a wrong "
     "failure. `check()` never prints; `check_NN: PASS` is `_main()`'s line."),
    ("mutants",
     "At least 34 mutations per stage: a plausible mistake from the stage's own "
     "mistake catalogue, planted as a minimal edit to the solution text, and the "
     "check catches every one of them (`MISSED OR BROKEN: 0`). A mutant that "
     "hangs counts as caught, and a rule no run can reach is dead weight — cut "
     "the rule, not the mutation."),
    ("audit",
     "A dev-side `audit_course.py` (in the course's `<row>-dev` directory beside "
     "the repository) enforces all of that on each stage's template *and* "
     "solution: the title paragraph, the design-decision blocks, the `TODO`, the "
     "stubs, the public-name parity, no banned import, no float literal, and "
     "earlier stages only. When it speaks, fix the file, never the audit."),
)

# What a finished course clears. Generic on purpose: every row in the registry
# is a course the same way, and the row's own words say what it is about.
REQUIREMENTS = (
    "`course.py` carries the manifest: `TITLE`, `DESCRIPTION`, `LEVEL`, `ORDER` "
    "\u2014 the row's position in the plan \u2014 and a `STAGES` list of ten "
    "`stage(...)` entries (the ladder every course built this way has), each with "
    "`file`, `title`, `tags`, `action`, `predict` and `check`. Its docstring "
    "states this course's thesis, the world it is handed, the ladder of stages "
    "and the rules it keeps \u2014 the shape of `os-from-scratch/course.py`'s head.",
    "One template per stage: `stage_NN.py` in the course directory, first "
    "docstring paragraph exactly `<TITLE> \u2014 stage NN: <title>`, three to six "
    "`DESIGN DECISION \u2014 ` blocks, a `TODO: implement` line, real public "
    "constants, and every public function or method stubbed as "
    "`raise NotImplementedError`.",
    "One solution per stage in `solutions/stage_NN.py`, declaring every public "
    "name the template declares \u2014 no fewer \u2014 and dropped over the "
    "template rather than merged with it.",
    "One check per stage, in the manifest as `check_N` and standalone as "
    "`check_NN.py`: assertions whose messages name the mistake and the value that "
    "arrived, every refusal pinned by its wording, and `NotImplementedError` let "
    "escape, so an untouched template reports `not implemented yet` rather than "
    "failing for the wrong reason.",
    "No float literal and none of the banned imports, in a template or a "
    "solution: stdlib only, offline, deterministic, no module-level mutable state "
    "and no wall clock. The audit is what enforces the first two.",
    "At least 34 mutations per stage \u2014 each a plausible mistake from the "
    "stage's own mistake catalogue, planted as a minimal edit to the solution "
    "\u2014 and every one is caught: `MISSED OR BROKEN: 0`. A mutant that hangs "
    "counts as caught; a rule no run can reach is dead weight and is cut.",
    "`./cz run <slug>` is green from an unrelated working directory: the ten "
    "stages pass with `solutions/` over the templates, from a cwd that has "
    "nothing to do with the repository \u2014 nothing in a course may assume "
    "where the repo is (`__file__`, never a root written down).",
    "`./cz self-test` is green, and `./cz stage <slug> <n>` prints the stage's "
    "page with its assert and mutation counts.",
    "The row is flipped to `ready` in `codecraft/path.py` and its per-stage "
    "counts are recorded in `codecraft/stats.py` (`tests` recomputable from "
    "`course.py`, `mutants` measured by the dev harness that plants them), with "
    "`ROADMAP.md` and the course's own `README.md` saying so.",
)

# ---------------------------------------------------------------------------
# reading the row's own words
# ---------------------------------------------------------------------------

_SLUG_NAMED = re.compile(r"[Aa]uthors?\s+([a-z0-9]+(?:-[a-z0-9]+)+)")
_SLUG_HOUSE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*-from-scratch")
_MD = re.compile(r"`([A-Za-z0-9_.-]+\.md)`")
_HEADING = re.compile(r"^#{2,3} +(.+?)\s*$", re.M)


def slug_of(entry) -> str:
    """What the row's course is called: its own slug when it has a directory.

    For a row still to author, `Author mqtt-broker-from-scratch` is the house's way
    of naming the thing to write; where a row does not name one, its title's own
    slug is the name a `codecraft new` would give it.
    """
    if entry.get("course"):
        return entry["course"]
    named = _SLUG_NAMED.search(entry["why"])
    if named:
        return named.group(1)
    house = set(_SLUG_HOUSE.findall(entry["why"]))
    if len(house) == 1:
        return house.pop()
    return re.sub(r"[^a-z0-9]+", "-", entry["title"].lower()).strip("-")


def _named(entry) -> bool:
    """True when the name is the row's own rather than a title doing the job."""
    return bool(entry.get("course")) \
        or _SLUG_NAMED.search(entry["why"]) is not None \
        or len(set(_SLUG_HOUSE.findall(entry["why"]))) == 1


def _docs(entry):
    """The documents at the repository root the row's own words name."""
    out = []
    for name in _MD.findall(entry["why"]):
        if name not in out:
            out.append(name)
    return tuple(out)


def _section(rid, letter):
    """The ROADMAP section that states this row: by id first, by phase second."""
    path = os.path.join(manifests.REPO_ROOT, "codecraft", "ROADMAP.md")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    heads = [h.strip() for h in _HEADING.findall(text)]
    for head in heads:
        if re.search(r"\b%s\b" % (rid,), head):
            return head
    for head in heads:
        if "phase %s" % (letter.lower(),) in head.lower():
            return head
    return None


def _imitate(entry, g):
    """The courses this row is built on, and the one whose form to copy."""
    by_id = {n["id"]: n for n in g["nodes"]}
    built = ["%s `%s`" % (rid, by_id[rid]["course"]) for rid in entry["prereq"]
             if by_id.get(rid, {}).get("course")]
    head = ("the courses this row is built on: " + ", ".join(built)) if built \
        else "no course comes before it in the registry"
    return (head + ". For the form, read `os-from-scratch`: `stage_06.py` and "
            "`solutions/stage_06.py` are a template and a solution in their final "
            "form, and the courses are the voice to match, not the content.")


def _spec(entry):
    """The row's own frozen plan, or the honest absence of one."""
    shape = ("the unit and its thesis, the conventions, the provided world and "
             "its API, the execution model, one section per stage with its surface "
             "and its mistake catalogue, the acceptance bar, and an amendments "
             "table for the places the course knew better (the course wins, the "
             "plan is amended)")
    rel = CONTRACTS.get(entry["id"])
    if rel and os.path.exists(os.path.join(BESIDE, rel)):
        return ("spec",
                "frozen before stage 1: `../%s` \u2014 read it first. It is the "
                "model for how specific a brief has to be: %s." % (rel, shape))
    return ("spec",
            "no contract document yet \u2014 the row's own words in "
            "`codecraft/path.py` are the spec until one exists, and the document "
            "is written before stage 1, never after. `tcp-ip-from-scratch`'s "
            "(`../%s`) is the model: %s." % (CONTRACTS["L1"], shape))


def _resources(entry, letter, g):
    """Where to read before writing: the row, the plan, the workflow, the API."""
    out = []
    section = _section(entry["id"], letter)
    out.append(("roadmap",
                "codecraft/ROADMAP.md"
                + (" \u00b7 \u00a7 %s" % (section,) if section else "")
                + " \u2014 the plan this row is a slot in, and the phase table it "
                  "came from."))
    out.append(("session",
                "codecraft/NEXT-SESSION.md \u2014 the workflow that built the "
                "courses beside it: recon, freeze a contract, one delegate per "
                "stage with four files, then the parent re-runs every verdict "
                "before registering; its closing ground rules are the short form "
                "of the guidelines above."))
    out.append(("api",
                "codecraft/README.md \u00b7 authoring a course, and "
                "codecraft/api.py \u2014 the manifest API (`stage(...)`) and what "
                "a course looks like to codecraft."))
    for doc in _docs(entry):
        out.append(("doc",
                    "%s at the repository root \u2014 the row's own words name it "
                    "as the project this course is written from." % (doc,)))
    out.append(("imitate", _imitate(entry, g)))
    return tuple(out)


def _facts(entry, letter, phase, g):
    """The row's identity, the one line it is, and where it sits."""
    by_id = {n["id"]: n for n in g["nodes"]}
    wave = g["levels"].get(entry["id"], 0)
    before = dag.before(entry["id"], g)
    facts = [("phase", "%s \u2014 %s \u00b7 %s" % (letter, phase, entry["kind"])),
             ("wave", "wave %d of %d \u00b7 %d row%s must come first"
                      % (wave, len(g["waves"]) - 1, len(before),
                         "" if len(before) == 1 else "s"))]
    if entry["prereq"]:
        facts.append(("needs", ", ".join(
            "%s %s" % (rid, by_id.get(rid, {}).get("title", "?"))
            for rid in entry["prereq"])))
    else:
        facts.append(("needs", "nothing \u2014 this row is a root"))
    slug = slug_of(entry)
    if entry.get("course"):
        facts.append(("name", "`%s` \u2014 the directory is there." % (entry["course"],)))
    elif _named(entry):
        facts.append(("name", "`%s`, the name the row's own words give it \u2014 "
                              "start with: python3 codecraft/cli.py new %s "
                              "--stages 10" % (slug, slug)))
    else:
        facts.append(("name", "the row names no slug: `%s` is the title's own "
                              "\u2014 start with: python3 codecraft/cli.py new %s "
                              "--stages 10" % (slug, slug)))
    facts.append(("why", entry["why"]))
    return tuple(facts)


# ---------------------------------------------------------------------------
# the brief
# ---------------------------------------------------------------------------

def brief(name):
    """One row's brief, or None when the registry has no such row.

    Plain data: `row`, `facts`, `guidelines`, `resources`, `spec` and
    `requirements`, each a tuple of `(label, text)` pairs or of strings.
    """
    letter, phase, entry = pathmod.find(name)
    if entry is None:
        return None
    g = dag.graph()
    row = dict(entry)
    row["letter"] = letter
    row["phase"] = phase
    row["symbol"] = pathmod.SYMBOL.get(entry["kind"], "\u00b7")
    return {
        "row": row,
        "name": slug_of(entry),
        "facts": _facts(entry, letter, phase, g),
        "guidelines": GUIDELINES,
        "resources": _resources(entry, letter, g),
        "spec": _spec(entry),
        "requirements": REQUIREMENTS,
    }


def briefs():
    """Every row still to author, terse, in plan order — what `cz brief` lists."""
    out = []
    for row in dag.rows():
        if row["kind"] != "author":
            continue
        out.append({"id": row["id"], "title": row["title"], "letter": row["letter"],
                    "phase": row["phase"], "symbol": row["symbol"],
                    "name": slug_of(row), "named": _named(row)})
    return tuple(out)
