#!/usr/bin/env python3
"""Scan staged content, outgoing commit history, or all reachable history."""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--pre-push", action="store_true")
    mode.add_argument("--all", action="store_true")
    args = parser.parse_args()
    executable = shutil.which("gitleaks")
    if not executable:
        print("Secret scan requires Gitleaks 8.30.1 or newer. Install with brew install gitleaks.", file=sys.stderr)
        return 2
    repo = Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True,
    ).strip())
    common = [executable, "git", "--redact=100", "--no-banner",
              "--ignore-gitleaks-allow", "--gitleaks-ignore-path=/dev/null",
              "--config", str(repo / ".gitleaks.toml")]
    if args.staged:
        scans = [["--pre-commit", "--staged"]]
    elif args.all:
        scans = [["--log-opts=--all"]]
    else:
        revisions = set()
        for line in sys.stdin:
            fields = line.split()
            if len(fields) != 4 or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", fields[1]):
                print("Invalid pre-push input. Push stopped.", file=sys.stderr)
                return 2
            if set(fields[1]) != {"0"}:
                revisions.add(fields[1])
        scans = [["--log-opts=" + revision] for revision in sorted(revisions)]
    for options in scans:
        result = subprocess.run(common + options + [str(repo)], check=False)
        if result.returncode:
            print("Secret scan failed. Remove credentials from the staged content or outgoing history.", file=sys.stderr)
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
