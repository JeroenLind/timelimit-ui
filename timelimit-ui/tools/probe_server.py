"""Probe a TimeLimit server twice per round: over a reused connection and over a fresh one.

Usage:  py -3 tools/probe_server.py http://192.168.68.30:8080 [--minutes 60] [--interval 5] [--timeout 3]

Writes ``probe-<start>.csv`` (one row per probe) in the current directory and prints a summary.
If only the "reused" rows fail, quickly (elapsed_ms near 0), the dropouts come from connection reuse;
if both fail alike, the network path is the cause. Only GET /time is used; nothing is changed.
"""

from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime, timezone

import requests


def probe(session: requests.Session, url: str, timeout: float) -> tuple[str, int]:
    started = time.monotonic()
    try:
        status = session.get(url, timeout=timeout).status_code
        outcome = "ok" if status == 200 else f"http{status}"
    except requests.Timeout:
        outcome = "timeout"
    except requests.RequestException as exc:
        outcome = f"error:{type(exc).__name__}"
    return outcome, round((time.monotonic() - started) * 1000)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("server")
    parser.add_argument("--minutes", type=float, default=60)
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--timeout", type=float, default=3)
    args = parser.parse_args()
    url = args.server.rstrip("/") + "/time"
    name = f"probe-{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.csv"
    reused = requests.Session()
    last_ok = time.monotonic()
    failures = {"reused": 0, "fresh": 0}
    total = 0
    end = time.monotonic() + args.minutes * 60
    with open(name, "w", newline="", encoding="utf-8") as handle:
        out = csv.writer(handle)
        out.writerow(["utc", "mode", "outcome", "elapsed_ms", "idle_s"])
        while time.monotonic() < end:
            round_start = time.monotonic()
            total += 1
            for mode in ("reused", "fresh"):
                idle = round(time.monotonic() - last_ok, 1)
                if mode == "reused":
                    outcome, ms = probe(reused, url, args.timeout)
                else:
                    with requests.Session() as session:
                        outcome, ms = probe(session, url, args.timeout)
                if outcome == "ok":
                    last_ok = time.monotonic()
                else:
                    failures[mode] += 1
                    print(f"{datetime.now():%H:%M:%S} {mode} {outcome} {ms} ms")
                stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                out.writerow([stamp, mode, outcome, ms, idle])
                handle.flush()
            time.sleep(max(0.0, args.interval - (time.monotonic() - round_start)))
    print(
        f"{total} rounds; failures reused={failures['reused']} fresh={failures['fresh']}; file {name}"
    )


if __name__ == "__main__":
    main()
