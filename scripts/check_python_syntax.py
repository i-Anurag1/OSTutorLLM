"""Fast local project checks. Does not replace pytest or a live Docker acceptance run."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
files = sorted((ROOT / "backend").rglob("*.py"))
errors: list[str] = []
for path in files:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        errors.append(f"{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")
if errors:
    print("\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
print(f"Python syntax: PASS ({len(files)} files)")
