"""Extract the request/response JSON schemas of the TimeLimit server (read-only).

    py -3 tools/extract_server_schemas.py <path-to-timelimit-server> [output.json]

The server compiles its strict ajv schemas from ``src/api/validator.ts`` (generated from the
TypeScript interfaces, ``additionalProperties: false``). This script copies them into one JSON file,
used by the fake server and the contract tests (plan A5, TR-501). The server checkout is only read.
The schemas are data of the server (AGPL-3.0); the source commit is recorded in the output.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "rootfs/usr/bin/dashboard/tests/fakeserver/server_schemas.json"
)


def _balanced_object(text: str, start: int) -> tuple[str, int]:
    """The ``{...}`` starting at ``start`` (string- and escape-aware) and the index after it."""
    depth = 0
    in_string = False
    index = start
    while index < len(text):
        char = text[index]
        if in_string:
            if char == "\\":
                index += 1
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1], index + 1
        index += 1
    raise ValueError("unbalanced braces")


def extract(validator_ts: str) -> tuple[dict, dict]:
    marker = "const definitions = "
    start = validator_ts.index(marker) + len(marker)
    body, end = _balanced_object(validator_ts, validator_ts.index("{", start))
    definitions = json.loads(body)

    validators: dict[str, dict] = {}
    cursor = end
    while True:
        found = validator_ts.find("export const is", cursor)
        if found < 0:
            break
        name = validator_ts[
            found + len("export const ") : validator_ts.index(":", found)
        ]
        compile_at = validator_ts.index("ajv.compile(", found) + len("ajv.compile(")
        body, cursor = _balanced_object(
            validator_ts, validator_ts.index("{", compile_at)
        )
        schema = json.loads(
            body.replace('"definitions": definitions', '"definitions": {}')
        )
        schema.pop("definitions", None)
        schema.pop("$schema", None)
        validators[name] = schema
    return definitions, validators


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    server = Path(argv[0])
    output = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUTPUT
    definitions, validators = extract(
        (server / "src/api/validator.ts").read_text(encoding="utf-8")
    )
    commit = subprocess.run(
        ["git", "-C", str(server), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    document = {
        "source": f"timelimit-server src/api/validator.ts @ {commit or 'unknown'}",
        "definitions": definitions,
        "validators": validators,
    }
    output.write_text(
        json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"{len(definitions)} definitions, {len(validators)} validators -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
