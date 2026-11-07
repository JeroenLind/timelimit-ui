"""Check the old dashboardV2 suite against the recorded baseline (plan step A1).

    py -3 tools/baseline.py            # run the old suite (about 3 minutes) and compare
    py -3 tools/baseline.py --collect  # only compare the number of collected tests (seconds)
    py -3 tools/baseline.py --record   # write this machine's result into docs/plan/baseline.json

"baseline OK" means: the same number of tests is collected and no test fails that is not in the
recorded failure list of this platform. On a platform without a record only the count is compared.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
OLD_SUITE = APP / "rootfs/usr/bin/dashboardV2"
BASELINE = APP / "docs/plan/baseline.json"


def platform_key() -> str:
    return "windows" if sys.platform.startswith("win") else "linux"


def parse_collected(output: str) -> int | None:
    match = re.search(r"(\d+) tests? collected", output)
    return int(match.group(1)) if match else None


def parse_failed(output: str) -> list[str]:
    return sorted(
        set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", output, flags=re.MULTILINE))
    )


def parse_passed(output: str) -> int | None:
    match = re.search(r"(\d+) passed", output)
    return int(match.group(1)) if match else None


def _pytest(*args: str) -> str:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "-q",
            "-p",
            "no:cacheprovider",
            *args,
        ],
        cwd=OLD_SUITE,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr


def compare(
    baseline: dict, collected: int | None, failed: list[str] | None
) -> list[str]:
    """Return a list of differences; empty means baseline OK."""
    problems = []
    if collected != baseline["collected"]:
        problems.append(f"collected {collected}, expected {baseline['collected']}")
    known = baseline["platforms"].get(platform_key())
    if failed is not None and known is not None:
        new = sorted(set(failed) - set(known["failed"]))
        if new:
            problems.append(f"new failures: {new}")
    return problems


def main(argv: list[str]) -> int:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    if "--collect" in argv:
        problems = compare(baseline, parse_collected(_pytest("--co")), None)
    else:
        output = _pytest("-rf")
        collected = None
        passed = parse_passed(output)
        failed = parse_failed(output)
        if passed is not None:
            collected = passed + len(failed)
        if "--record" in argv:
            baseline["collected"] = collected
            baseline["platforms"][platform_key()] = {
                "recorded": "recorded by tools/baseline.py --record",
                "passed": passed,
                "failed": failed,
            }
            BASELINE.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
            print(f"recorded: {passed} passed, {len(failed)} failed")
            return 0
        problems = compare(baseline, collected, failed)
        print(f"{passed} passed, {len(failed)} failed")
    if problems:
        print("baseline DIFFERS:\n  " + "\n  ".join(problems))
        return 1
    print("baseline OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
