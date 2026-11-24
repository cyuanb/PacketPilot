"""Check candidate Git files without printing any matching credential."""

import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
local = dotenv_values(ROOT / ".env")
private_values = [local.get(k) for k in ("LLM_API_KEY", "OWNER_PASSWORD", "DATABASE_URL")]
private_values = [v for v in private_values if v and len(v) > 10]
files = (
    subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT)
    .decode()
    .split("\0")
)
failures = []
for relative in set(files):
    if not relative:
        continue
    path = ROOT / relative
    if not path.is_file():
        continue
    if path.name == ".env" or relative.startswith(
        ("data/", ".venv/", "node_modules/", "frontend/node_modules/")
    ):
        failures.append(relative)
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeError, OSError):
        continue
    if re.search(r"sk-[A-Za-z0-9]{24,}", text) or any(secret in text for secret in private_values):
        failures.append(relative)
if failures:
    print("Credential or private runtime content found in:", ", ".join(sorted(set(failures))))
    raise SystemExit(1)
print("Credential scan passed for", len(set(files)) - 1, "candidate Git files.")
