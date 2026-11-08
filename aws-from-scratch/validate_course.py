"""Check that the executable AWS ladder and its generated guides agree."""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from codecraft.guide import guide_path, render_stage, render_start  # noqa: E402
from codecraft.manifests import load  # noqa: E402
from check import CHECKS, LESSONS  # noqa: E402
from stage_checks import CHECKS as STAGE_CHECKS  # noqa: E402


def main() -> None:
    course = load("aws-from-scratch")
    assert len(LESSONS) == len(CHECKS) == len(STAGE_CHECKS) == len(course["stages"]) == 63
    assert [row["id"] for row in LESSONS] == list(range(1, 64))
    assert (ROOT / "START.md").read_text() == render_start(course)
    for number, (lesson, (file, title, check)) in enumerate(zip(LESSONS, CHECKS), 1):
        assert check.__name__ == f"s{number:02d}"
        assert (file, title) == (lesson["file"], lesson["title"])
        assert lesson["context"] and lesson["task"] and lesson["predict"]
        path = guide_path(course, number)
        assert path, f"missing stage {number} page"
        assert pathlib.Path(path).read_text() == render_stage(course, number), path
    assert len(list((ROOT / "stages").glob("*.md"))) == 63
    print("63 checks, lesson records, and generated guides agree")


if __name__ == "__main__":
    main()
