"""Plan step E13, browser half: all limits of a child off for a while."""

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


def open_child(page: Page, live: Any) -> None:
    page.goto(live.url + "/")
    page.click('#overview-list a:has-text("Anna")')
    expect(page.locator("#child-limits-state")).to_contain_text("active")


def test_switch_off_with_quick_button_and_on_again(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    open_child(page, live)
    page.click("#child-limits-off")
    expect(page.locator("#child-limits-dialog")).to_be_visible()
    page.click("[data-child-limit-minutes='180']")
    page.click("#child-limits-form button[type=submit]")
    expect(page.locator("#child-limits-state")).to_contain_text("off until")
    anna = next(u for u in family(fake_server).users.values() if u.name == "Anna")
    assert anna.disable_limits_until > 0
    expect(page.locator("#child-limits-on")).to_be_visible()
    page.click("#child-limits-on")
    expect(page.locator("#child-limits-state")).to_contain_text("active")
    assert anna.disable_limits_until == 0


def test_invalid_minutes_show_a_field_message(
    page: Page, live_app_factory: Any
) -> None:
    live = live_app_factory()
    open_child(page, live)
    page.click("#child-limits-off")
    page.fill("#child-limits-minutes", "0")
    page.click("#child-limits-form button[type=submit]")
    expect(page.locator('[data-error-for="child_limit_minutes"]')).to_be_visible()
    expect(page.locator("#child-limits-dialog")).to_be_visible()
