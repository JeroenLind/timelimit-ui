"""Plan step G2, browser half: quick actions on the overview (FR-700)."""

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


def family(fake: Any) -> Any:
    return next(iter(fake.world.families.values()))


def open_quick(page: Page, live: Any, child: str = "Anna") -> None:
    page.goto(live.url + "/")
    page.locator(f'#overview-list li:has-text("{child}") [data-quick]').click()
    expect(page.locator("#quick-dialog")).to_be_visible()


def test_extra_time_for_a_chosen_category_from_the_overview(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    open_quick(page, live)
    expect(page.locator("#quick-title")).to_contain_text("Anna")
    page.select_option("#quick-category", label="Games")
    page.click("[data-quick-extra='30']")
    expect(page.locator("#quick-done")).to_be_visible()
    assert family(fake_server).categories["cgames"].extra_time == 45 * 60000


def test_block_and_unblock_from_the_overview(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    open_quick(page, live)
    page.select_option("#quick-category", label="Games")
    page.click("[data-quick-block='60']")
    expect(page.locator("#quick-done")).to_be_visible()
    assert family(fake_server).categories["cgames"].temp_blocked is True
    page.click("#quick-unblock")
    expect(page.locator("#quick-done")).to_be_visible()
    assert family(fake_server).categories["cgames"].temp_blocked is False


def test_the_dialog_closes_and_other_pages_are_not_affected(
    page: Page, live_app_factory: Any
) -> None:
    live = live_app_factory()
    open_quick(page, live)
    page.click("#quick-close")
    expect(page.locator("#quick-dialog")).not_to_be_visible()
    page.goto(live.url + "/settings")
    expect(page.locator("#quick-dialog")).to_have_count(0)
