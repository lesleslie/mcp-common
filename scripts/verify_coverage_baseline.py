"""Verify the current measured coverage meets the ratchet floor.

Re-runs pytest with coverage, parses the JSON report, and asserts that
the total line coverage is at or above `.coverage-ratchet.json`'s
`current_minimum`. Exits 0 on pass, 1 on fail.

Usage: python scripts/verify_coverage_baseline.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    ratchet_path = repo_root / ".coverage-ratchet.json"
    coverage_json = repo_root / ".tmp-coverage.json"

    ratchet = json.loads(ratchet_path.read_text())
    floor = ratchet["current_minimum"]

    subprocess.run(
        [
            sys.executable, "-m", "coverage", "run",
            "-m", "pytest", "tests/", "-q", "--no-header",
        ],
        cwd=repo_root,
        check=False,
    )
    subprocess.run(
        [
            sys.executable, "-m", "coverage", "json",
            "-o", str(coverage_json),
        ],
        cwd=repo_root,
        check=False,
    )
    if not coverage_json.exists():
        print("FAIL: coverage JSON not produced", file=sys.stderr)
        return 1
    data = json.loads(coverage_json.read_text())
    measured = data["totals"]["percent_covered"]
    coverage_json.unlink()
    print(f"Measured coverage: {measured:.2f}% (floor: {floor}%)")
    return 0 if measured >= floor else 1


if __name__ == "__main__":
    sys.exit(main())
