"""Public starter files for the browser's AWS exercise workspace.

Only course templates and the stage checker are exposed. Reference solutions,
local profiles, and repository metadata never enter this bundle.
"""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent / "aws-from-scratch"
EDITABLE = (
    "iam.py", "s3.py", "sqs.py", "dynamodb.py", "lambda_svc.py",
    "sns.py", "kms.py", "vpc.py", "capstone.py",
)


def aws_bundle() -> dict:
    files = {name: (ROOT / name).read_text(encoding="utf-8") for name in EDITABLE}
    files["stage_checks.py"] = (ROOT / "stage_checks.py").read_text(encoding="utf-8")
    lessons = json.loads((ROOT / "lessons.json").read_text(encoding="utf-8"))
    learning = {str(row["id"]): row["learning"] for row in lessons if row.get("learning")}
    return {"course": "aws-from-scratch", "editable": list(EDITABLE),
            "files": files, "learning": learning}
