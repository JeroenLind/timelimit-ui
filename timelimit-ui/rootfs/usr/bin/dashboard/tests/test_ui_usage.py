"""Plan step E9, browser half: the Usage tab."""

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


def open_usage(page: Page, live: Any) -> None:
    page.goto(live.url + "/")
    page.click('#overview-list a:has-text("Anna")')
    page.click("#tab-usage")
    expect(page.locator("#panel-usage")).to_be_visible()


def test_today_shows_used_time_against_the_limit(
    page: Page, live_app_factory: Any
) -> None:
    live = live_app_factory()
    open_usage(page, live)
    row = page.locator('#usage-today tr[data-category-id="cgames"]')
    expect(row).to_contain_text("1 h 05 min")
    expect(row).to_contain_text("1 h 15 min")
    expect(row.locator("progress.over")).to_have_count(0)
    expect(page.locator('#usage-today tr[data-category-id="csocia"]')).to_contain_text(
        "No limit"
    )


def test_the_chart_and_list_follow_category_and_period(
    page: Page, live_app_factory: Any
) -> None:
    live = live_app_factory()
    open_usage(page, live)
    page.select_option("#usage-category", "cgames")
    expect(page.locator("#usage-chart rect.usage-bar")).to_have_count(7)
    page.select_option("#usage-range", "30")
    expect(page.locator("#usage-chart rect.usage-bar")).to_have_count(30)
    expect(page.locator("#usage-history tr")).to_have_count(30)
    page.select_option("#usage-range", "7")
    expect(page.locator("#usage-chart rect.usage-bar")).to_have_count(7)
    expect(page.locator("#usage-history tr").first).to_contain_text("1 h 05 min")
    page.select_option("#usage-category", "csocia")
    expect(page.locator("#usage-history tr").first).to_contain_text("0 min")
