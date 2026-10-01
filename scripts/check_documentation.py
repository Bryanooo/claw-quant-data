#!/usr/bin/env python3
"""Fail CI when documentation links break or dated report snapshots accumulate."""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
DATED_REPORT = re.compile(r"(?:19|20)\d{2}-\d{2}-\d{2}")
IGNORED_PREFIXES = ("http://", "https://", "mailto:", "#", "/api/")


def markdown_files() -> list[Path]:
    files = [PROJECT_ROOT / "README.md"]
    files.extend((PROJECT_ROOT / "docs").rglob("*.md"))
    files.extend((PROJECT_ROOT / "reports").glob("*.md"))
    return sorted(path for path in files if path.exists())


def broken_relative_links() -> list[str]:
    errors: list[str] = []
    for path in markdown_files():
        content = path.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(content):
            raw_target = target.strip().split()[0].strip("<>")
            if raw_target.startswith(IGNORED_PREFIXES):
                continue
            relative_target = raw_target.split("#", 1)[0]
            if relative_target and not (path.parent / relative_target).resolve().exists():
                errors.append(
                    f"{path.relative_to(PROJECT_ROOT)}: missing link target {target!r}"
                )
    return errors


def dated_report_snapshots() -> list[str]:
    reports = PROJECT_ROOT / "reports"
    return [
        f"{path.relative_to(PROJECT_ROOT)}: use a stable *_latest filename and Git history"
        for path in sorted(reports.iterdir())
        if path.is_file() and DATED_REPORT.search(path.name)
    ]


def main() -> int:
    errors = broken_relative_links() + dated_report_snapshots()
    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Documentation validation passed ({len(markdown_files())} Markdown files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
