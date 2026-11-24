import json
import sys
from pathlib import Path

from .parsing import parse_file

if __name__ == "__main__":
    try:
        result = parse_file(Path(sys.argv[1]))
    except Exception as error:
        result = {"status": "failed", "pages": [], "note": str(error)[:300]}
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
