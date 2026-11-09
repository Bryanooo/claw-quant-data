#!/usr/bin/env python3
"""Install this repository's commit and push secret checks."""
from pathlib import Path
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[1]
    if not shutil.which("gitleaks"):
        raise SystemExit("Install Gitleaks first with brew install gitleaks.")
    configured = subprocess.run(
        ["git", "config", "--local", "--get", "core.hooksPath"],
        cwd=root, text=True, capture_output=True, check=False,
    ).stdout.strip()
    if configured and configured != ".githooks":
        raise SystemExit("A custom core.hooksPath already exists. Integrate these checks with the current hooks first.")
    for name in ("pre-commit", "pre-push"):
        path = root / ".githooks" / name
        path.chmod(path.stat().st_mode | 0o111)
    subprocess.run(["git", "config", "--local", "core.hooksPath", ".githooks"], cwd=root, check=True)
    print("Commit and push secret checks installed.")


if __name__ == "__main__":
    main()
