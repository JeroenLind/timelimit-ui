"""Plan step E10, browser half: parents and change password in the settings page."""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect

from ..domain import passwords
from .conftest import PARENT_PASSWORD

pytestmark = pytest.mark.ui


@pytest.fixture
def page(browser: Any) -> Any:
    page = browser.new_context(locale="en-US").new_page()
    page.set_default_timeout(8000)
    return page


def family(fake: Any) -> Any:
    return next(iter(fake.world.families.values()))


def open_settings(page: Page, live: Any) -> None:
    page.goto(live.url + "/settings")
    expect(page.locator("#parents-section")).to_be_visible()


def test_the_section_lists_parents_and_the_dashboard_state(
    page: Page, live_app_factory: Any
) -> None:
    live = live_app_factory()
    open_settings(page, live)
    expect(page.locator("#parents-list li")).to_have_count(2)
    expect(page.locator("#parents-dashboard")).to_have_attribute("data-state", "ok")


def test_change_a_password_in_the_dialog(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    open_settings(page, live)
    page.get_by_role("button", name="Change password Dashboard").click()
    page.fill("#pw-current", PARENT_PASSWORD)
    page.fill("#pw-new", "fresh pass 1")
    page.fill("#pw-repeat", "fresh pass 1")
    page.click("#password-form-change button[type=submit]")
    expect(page.locator("#parents-note")).to_contain_text("was changed")
    expect(page.locator("#password-dialog")).not_to_be_visible()
    dash = next(u for u in family(fake_server).users.values() if u.name == "Dashboard")
    assert passwords.password_matches("fresh pass 1", dash.password_hash)


def test_a_wrong_current_password_and_a_mismatch_show_errors(
    page: Page, live_app_factory: Any
) -> None:
    live = live_app_factory()
    open_settings(page, live)
    page.get_by_role("button", name="Change password Dashboard").click()
    page.fill("#pw-current", "wrong")
    page.fill("#pw-new", "fresh pass 1")
    page.fill("#pw-repeat", "other")
    page.click("#password-form-change button[type=submit]")
    expect(page.locator('[data-error-for="repeat_password"]')).to_be_visible()
    page.fill("#pw-repeat", "fresh pass 1")
    page.click("#password-form-change button[type=submit]")
    expect(page.locator('[data-error-for="current_password"]')).to_be_visible()
    expect(page.locator("#password-dialog")).to_be_visible()
