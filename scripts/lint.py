from __future__ import annotations

import ast
import sys
from pathlib import Path


CHECKED_DIRS = ("mini_exchange", "scripts", "tests")


def main() -> int:
    failures: list[str] = []
    for directory in CHECKED_DIRS:
        for path in sorted(Path(directory).rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            try:
                ast.parse(source, filename=str(path))
            except SyntaxError as exc:
                failures.append(f"{path}: syntax error: {exc}")
            for line_number, line in enumerate(source.splitlines(), start=1):
                if "\t" in line:
                    failures.append(f"{path}:{line_number}: tab character found")
                if line.rstrip() != line:
                    failures.append(f"{path}:{line_number}: trailing whitespace")

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("lint ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
