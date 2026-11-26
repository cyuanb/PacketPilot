"""Check that candidate public files contain product material rather than internal workspace records."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PREFIXES = (
    "plan/",
    "plans/",
    "status/",
    "research/",
    "development/",
    "decisions/",
    "evaluation/",
    "business/",
    "local-data/",
    "docs/plans/",
    "docs/adr/",
    "docs/evidence/",
    "docs/evaluation/",
)
PRIVATE_FILES = {
    "docs/evaluation.md",
    "docs/iteration-progress.md",
    "docs/release-checklist.md",
    "docs/browser-checklist.md",
}
INTERNAL_MARKERS = re.compile(r"\bPP-\d{3}\b|\bR\d{2}\b|plan-\d{6}|ModernWebDevelopment|实践作业|实验报告")


def violations(name, text):
    normalized = name.replace("\\", "/")
    if normalized in PRIVATE_FILES or normalized.startswith(PRIVATE_PREFIXES):
        return ["internal workspace path"]
    if normalized.endswith((".md", ".rst", ".txt")) and INTERNAL_MARKERS.search(text):
        return ["internal planning or assignment content"]
    return []


def main():
    files = (
        subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT
        )
        .decode("utf-8")
        .split("\0")
    )
    failures = {}
    for name in sorted(set(filter(None, files))):
        path = ROOT / name
        texts = []
        if path.is_file():
            try:
                texts.append(path.read_text(encoding="utf-8"))
            except UnicodeError:
                pass
        staged = subprocess.run(["git", "show", ":" + name], cwd=ROOT, capture_output=True, check=False)
        if staged.returncode == 0:
            try:
                texts.append(staged.stdout.decode("utf-8"))
            except UnicodeError:
                pass
        reasons = set(violations(name, "\n".join(texts)))
        if reasons:
            failures[name] = sorted(reasons)
    if failures:
        for name, reasons in failures.items():
            print(name + ": " + ", ".join(reasons))
        raise SystemExit(1)
    print("Public content policy passed.")


if __name__ == "__main__":
    main()
