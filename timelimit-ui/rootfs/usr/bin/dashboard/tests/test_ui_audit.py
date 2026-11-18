"""Plan step E12, browser half: the tab "Changes"."""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui


@pytest.fixture
def page(browser: Any) -> Any:
    page = browser.new_context(locale="en-US").new_page()
    page.set_default_timeout(8000)
    return page


def test_the_tab_shows_the_session_newest_first(
    page: Page, live_app_factory: Any
) -> None:
    live = live_app_factory()
    page.goto(live.url + "/")
    page.click('#overview-list a:has-text("Anna")')
    page.click("#tab-changes")
    expect(page.locator("#audit-empty")).to_be_visible()
    child = page.url.rstrip("/").rsplit("/", 1)[-1]
    base = f"/api/children/{child}/categories/cgames"
    for path, method, body in (
        (f"{base}/extra-time", "PUT", {"mode": "add", "minutes": 5}),
        (f"{base}/temp-block", "PUT", {"minutes": 30}),
    ):
        status = page.evaluate(
            """async ([p, m, b]) => (await fetch(p, {method: m, headers: {"Content-Type": "application/json"}, body: JSON.stringify(b)})).status""",
            [path, method, body],
        )
        assert status == 200
    page.click("#tab-devices")
    page.click("#tab-changes")
    rows = page.locator("#audit-body tr")
    expect(rows).to_have_count(2)
    expect(rows.nth(0)).to_contain_text("Category blocked or unblocked")
    expect(rows.nth(1)).to_contain_text("Extra time added")
    expect(rows.nth(0)).to_contain_text("Games")
    expect(rows.nth(0)).to_contain_text("Confirmed")
    expect(rows.nth(0)).to_have_attribute("data-result", "confirmed")
