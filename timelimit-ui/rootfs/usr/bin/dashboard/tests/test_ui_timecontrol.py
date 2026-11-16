"""Plan step E8, browser half: extra time and temporary blocking dialog."""

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


def open_time(page: Page, live: Any, category: str = "Games") -> None:
    page.goto(live.url + "/")
    page.click('#overview-list a:has-text("Anna")')
    expect(page.locator("#categories-body tr")).to_have_count(2)
    page.get_by_role("button", name=f"Time {category}").click()
    expect(page.locator("#time-dialog")).to_be_visible()


def test_quick_buttons_add_extra_time_and_the_summary_follows(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    open_time(page, live)
    expect(page.locator("#time-summary")).to_contain_text("15")
    page.click("[data-extra-add='30']")
    expect(page.locator("#time-summary")).to_contain_text("45")
    assert family(fake_server).categories["cgames"].extra_time == 45 * 60000


def test_subtract_and_reset(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    open_time(page, live)
    page.fill("#time-minutes", "5")
    page.click("#time-subtract")
    expect(page.locator("#time-summary")).to_contain_text("10")
    page.click("#time-reset")
    expect(page.locator("#time-summary")).to_contain_text("none")
    assert family(fake_server).categories["cgames"].extra_time == 0


def test_block_for_an_hour_and_unblock(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    open_time(page, live)
    expect(page.locator("#block-end")).to_be_disabled()
    page.click("[data-block='60']")
    expect(page.locator("#time-summary")).to_contain_text("Blocked until")
    assert family(fake_server).categories["cgames"].temp_blocked is True
    page.click("#block-end")
    expect(page.locator("#time-summary")).not_to_contain_text("Blocked")
    assert family(fake_server).categories["cgames"].temp_blocked is False


def test_a_bad_amount_shows_an_error(page: Page, live_app_factory: Any) -> None:
    live = live_app_factory()
    open_time(page, live)
    page.fill("#block-minutes", "0")
    page.click("#block-custom")
    expect(page.locator("#time-error")).to_be_visible()
