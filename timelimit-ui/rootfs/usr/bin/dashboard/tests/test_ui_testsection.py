"""Plan step E11, browser half: the test section."""

from __future__ import annotations

import re
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


def enable(page: Page, live: Any) -> None:
    page.goto(live.url + "/settings")
    expect(page.locator("#nav-test")).to_have_count(0)
    page.check("#test-server")
    expect(page.locator("#nav-test")).to_be_visible()


def test_the_menu_item_follows_the_switch(page: Page, live_app_factory: Any) -> None:
    live = live_app_factory()
    enable(page, live)
    page.uncheck("#test-server")
    expect(page.locator("#nav-test")).to_have_count(0)


def test_add_a_child_and_a_parent(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    enable(page, live)
    # a click on the menu item races with a second load of the page; the item itself is tested above
    expect(page.locator("#nav-test")).to_have_attribute("href", re.compile(r"/test$"))
    page.goto(live.url + "/test")
    page.fill("#test-name", "Mia")
    page.click("#test-form button[type=submit]")
    expect(
        page.locator('#test-users li:has(.card-title:text-is("Mia"))')
    ).to_have_count(1)
    expect(page.locator("#test-users li[data-pending]")).to_have_count(0)
    page.select_option("#test-type", "parent")
    expect(page.locator("#test-password-field")).to_be_visible()
    page.fill("#test-name", "Pa")
    page.fill("#test-password", "secret1")
    page.click("#test-form button[type=submit]")
    expect(page.locator('#test-users li:has(.card-title:text-is("Pa"))')).to_have_count(
        1
    )
    expect(page.locator("#test-users li[data-pending]")).to_have_count(0)
    types = {u.name: u.type for u in family(fake_server).users.values()}
    assert types["Mia"] == "child"
    assert types["Pa"] == "parent"


def test_a_short_password_shows_an_error_and_nothing_is_added(
    page: Page, live_app_factory: Any
) -> None:
    live = live_app_factory()
    enable(page, live)
    page.goto(live.url + "/test")
    page.select_option("#test-type", "parent")
    page.fill("#test-name", "Pa")
    page.fill("#test-password", "ab")
    page.click("#test-form button[type=submit]")
    expect(page.locator('[data-error-for="password"]')).to_be_visible()
    expect(page.locator('#test-users li:has(.card-title:text-is("Pa"))')).to_have_count(
        0
    )


def test_the_database_page_shows_tables(page: Page, live_app_factory: Any) -> None:
    live = live_app_factory()
    enable(page, live)
    page.goto(live.url + "/test/database")
    expect(page.locator('#database-tables details[data-table="users"]')).to_be_visible()
