"""Plan step A1: every Must requirement has a row with a step in docs/plan/traceability.md."""

from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2]
ID = r"(?:FR|TR|UI|SEC|NFR)-\d+"


def _must_ids() -> set[str]:
    text = (APP / "docs/requirements/requirements.md").read_text(encoding="utf-8")
    return set(re.findall(rf"^\| ({ID}) \| M \|", text, flags=re.MULTILINE))


def _rows() -> dict[str, str]:
    text = (APP / "docs/plan/traceability.md").read_text(encoding="utf-8")
    rows = {}
    for match in re.finditer(
        rf"^\| ({ID}) \|[^|]*\| ([^|]*) \|", text, flags=re.MULTILINE
    ):
        rows[match.group(1)] = match.group(2).strip()
    return rows


def test_every_must_requirement_has_a_row() -> None:
    must = _must_ids()
    assert len(must) > 50
    missing = sorted(must - set(_rows()))
    assert missing == [], f"not in traceability.md: {missing}"


def test_every_row_names_a_step() -> None:
    steps = {
        rid: step for rid, step in _rows().items() if not re.search(r"\b[A-G]\d", step)
    }
    assert steps == {}, f"rows without a plan step: {steps}"
