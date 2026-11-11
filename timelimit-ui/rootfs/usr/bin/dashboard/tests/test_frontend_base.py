"""Plan step D1, unit half: i18n files and templates (UI-002..006, TR-311)."""

from __future__ import annotations

import json
import re
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parents[1]
I18N = DASHBOARD / "static" / "i18n"


def keys(lang: str) -> set[str]:
    return set(json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8")))


def test_nl_and_en_have_exactly_the_same_keys() -> None:
    en, nl = keys("en"), keys("nl")
    assert en == nl, (
        f"missing in nl: {sorted(en - nl)}; missing in en: {sorted(nl - en)}"
    )


def test_every_key_used_in_templates_exists() -> None:
    used: set[str] = set()
    for template in (DASHBOARD / "templates").glob("*.html"):
        used |= set(
            re.findall(r'data-i18n(?:-aria)?="([^"]+)"', template.read_text("utf-8"))
        )
    assert used - keys("en") == set()


def test_no_inline_style_attribute_in_any_template() -> None:
    for template in (DASHBOARD / "templates").glob("*.html"):
        assert "style=" not in template.read_text("utf-8"), template.name


def test_no_inline_style_set_by_the_scripts() -> None:
    for script in (DASHBOARD / "static" / "js").glob("*.js"):
        assert ".style." not in script.read_text("utf-8"), script.name
