"""The look of the thing.

codecraft shows two layers, never one:

  * the course's own `check.py` output — the raw, diagnostic truth, untouched;
  * a small layer of ceremony and coaching on top.

Ceremony is not decoration here. A stage landing is the moment the learning
consolidates, so it gets a banner and a count. A failure gets a quiet header and
a mentor, because the useful part of failing is the diagnosis, not the red text.
"""

import random
import re
import textwrap

ANSI = re.compile(r"\x1b\[[0-9;]*m")

GREEN, RED, YELLOW, BLUE, MAGENTA, CYAN, GREY, BOLD, DIM, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[34m", "\033[35m", "\033[36m",
    "\033[90m", "\033[1m", "\033[2m", "\033[0m")

FULL, EMPTY = "\u2588", "\u2591"
SPARKLES = ["\u2726", "\u2727", "\u2735", "\u2736", "\u2737", "\u2738", "\u2739"]

# CodeCrafters-shaped celebration mark — printed green on every stage land.
FORJA_ASCII = r"""
  █████╗  ██████╗ ██████╗      ██╗ █████╗
 ██╔══██╗██╔═══██╗██╔══██╗     ██║██╔══██╗
 ███████║██║   ██║██████╔╝     ██║███████║
 ██╔══██║██║   ██║██╔══██╗██   ██║██╔══██║
 ██║  ██║╚██████╔╝██║  ██║╚█████╔╝██║  ██║
 ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚════╝ ╚═╝  ╚═╝
""".strip("\n")

FORJA_ASCII_SMALL = r"""
  █▀▀ █▀█ █▀█ ░░░█ ▄▀█
  █▀  █▄█ █▀▄ █▄▄█ █▀█
""".strip("\n")


def _visible(text: str) -> int:
    return len(ANSI.sub("", text))


def forja_banner(ink, big=False):
    """Green ASCII `forja` — the pass moment CodeCrafters sells with colour."""
    art = FORJA_ASCII if big else FORJA_ASCII_SMALL
    return "\n".join(ink(line, GREEN) for line in art.splitlines())


def box(lines, ink, colour="", min_width=0):
    """A rounded box around already-coloured lines, padding on visible width."""
    width = max([_visible(l) for l in lines] + [min_width])
    top = ink("\u256d" + "\u2500" * (width + 2) + "\u256e", colour)
    bot = ink("\u2570" + "\u2500" * (width + 2) + "\u256f", colour)
    out = [top]
    for line in lines:
        pad = " " * (width - _visible(line))
        out.append(ink("\u2502", colour) + " " + line + pad + " " + ink("\u2502", colour))
    out.append(bot)
    return out


def progress_bar(passed, total, width=26):
    if total <= 0:
        return ""
    filled = int(round(width * passed / total))
    return f"{FULL * filled}{EMPTY * (width - filled)}  {passed}/{total}"


def sparkle(ink, n=7, seed=None):
    rng = random.Random(seed if seed is None else str(seed))
    colours = [GREEN, CYAN, MAGENTA, YELLOW]
    return "  " + " ".join(
        ink(rng.choice(SPARKLES), colours[rng.randrange(len(colours))])
        for _ in range(n))


def stage_passed(ink, course_title, stage, file, title, passed, total,
                 first_try=False, colour=True):
    head = f"{ink('\u2713', GREEN)}  {ink('Stage ' + str(stage) + ' passed', BOLD)}" \
           f"{ink('  \u2014  ' + file, GREY)}"
    body = [head, "   " + ink(title, DIM if not colour else "")]
    if first_try:
        body.append("   " + ink("first try \u2014 no hints", GREEN))
    body.append("   " + ink(progress_bar(passed, total), CYAN))
    lines = [forja_banner(ink, big=False), ""] + box(body, ink, GREEN)
    if first_try:
        lines.append(sparkle(ink, n=5, seed=(stage, title)))
    return "\n".join(lines)


def course_complete(ink, course_title, total):
    stars = f"{ink('\u2605', YELLOW)}"
    lines = box([
        f"   {stars}  {ink('COURSE COMPLETE', BOLD)}  {stars}",
        f"      {ink(course_title, BOLD)}",
        f"      {ink(str(total) + '/' + str(total) + ' stages, built from scratch', GREY)}",
    ], ink, YELLOW, min_width=36)
    return "\n".join(
        [forja_banner(ink, big=True), ""]
        + lines
        + [sparkle(ink, n=11), sparkle(ink, n=9, seed=7)])


def fail_header(ink, stage, file, title):
    return (f"  {ink('\u2717', RED)} {ink('Stage ' + str(stage), BOLD)}"
            f"{ink('  \u2014  ' + file + '  ', GREY)}"
            f"{ink(title, DIM if title else '')}")


def regression(ink, stage, file):
    msg = (f" \u2014 stage {stage} ({file}) passed before and no longer does.")
    return (f"  {ink('!', YELLOW)} {ink('regression', BOLD)}"
            f"{ink(msg, YELLOW)}")


def mentor_box(ink, sections, model=""):
    """sections: list of (label, text)."""
    lines = [f"  {ink('\u2726 mentor', MAGENTA)}"
             f"{ink('  (' + model + ')' if model else '', GREY)}", ""]
    width = max([len(label) for label, _ in sections] + [12]) + 2
    for label, text in sections:
        wrapped = textwrap.wrap(" ".join(text.split()), width=74) or [""]
        lines.append(f"  {ink(label.ljust(width), BOLD)}{wrapped[0]}")
        for extra in wrapped[1:]:
            lines.append(f"  {' ' * width}{extra}")
    return "\n".join(lines)
