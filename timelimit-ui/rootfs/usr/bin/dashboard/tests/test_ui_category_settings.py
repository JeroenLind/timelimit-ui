"""Plan step E6b, browser half: the category settings dialog (FR-402)."""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect

from .fakeserver.state import version_id

pytestmark = pytest.mark.ui


@pytest.fixture
def page(browser: Any) -> Any:
    page = browser.new_context(locale="en-US").new_page()
    page.set_default_timeout(8000)
    return page


def games(fake: Any) -> Any:
    return next(iter(fake.world.families.values())).categories["cgames"]


def open_settings(page: Page, live: Any) -> None:
    page.goto(live.url + "/")
    page.click('#overview-list a:has-text("Anna")')
    expect(page.locator("#categories-body tr")).to_have_count(2)
    page.get_by_role("button", name="Settings Games").click()
    expect(page.locator("#settings-dialog")).to_be_visible()


def test_change_all_settings_at_once(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    open_settings(page, live_app_factory())
    page.check("#set-notifications")
    page.fill("#set-delay", "5")
    page.check('#set-warnings input[value="5"]')
    page.check('#set-warnings input[value="15"]')
    page.fill("#set-battery-charging", "10")
    page.fill("#set-battery-mobile", "30")
    page.check("#set-network-list")
    page.locator('#settings-form button[type="submit"]').click()
    expect(page.locator("#action-status")).to_contain_text("Done.")
    cat = games(fake_server)
    assert (cat.block_all_notifications, cat.block_notification_delay) == (True, 300000)
    assert cat.time_warnings == 0b10100
    assert (cat.min_battery_charging, cat.min_battery_mobile, cat.flags) == (10, 30, 1)
    page.get_by_role("button", name="Settings Games").click()
    expect(page.locator("#set-notifications")).to_be_checked()
    expect(page.locator("#set-delay")).to_have_value("5")
    expect(page.locator('#set-warnings input[value="15"]')).to_be_checked()
    expect(page.locator('#set-warnings input[value="1"]')).not_to_be_checked()
    expect(page.locator("#set-battery-mobile")).to_have_value("30")


def test_only_changed_parts_are_sent(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    open_settings(page, live_app_factory())
    before = len(fake_server.world.action_types)
    page.fill("#set-battery-mobile", "25")
    page.locator('#settings-form button[type="submit"]').click()
    expect(page.locator("#action-status")).to_contain_text("Done.")
    assert fake_server.world.action_types[before:] == ["UPDATE_CATEGORY_BATTERY_LIMIT"]


def test_an_out_of_range_value_is_refused_in_the_dialog(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    open_settings(page, live_app_factory())
    pushes = fake_server.world.push_requests
    page.fill("#set-battery-charging", "150")
    page.locator('#settings-form button[type="submit"]').click()
    expect(page.locator('[data-error-for="charging"]')).to_be_visible()
    expect(page.locator("#settings-dialog")).to_be_visible()
    assert fake_server.world.push_requests == pushes


def test_saved_networks_can_be_forgotten(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    games(fake_server).networks = [{"itemId": "net001", "hashedNetworkId": "a" * 40}]
    games(fake_server).base_version = version_id()
    backend = live.app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake_server.url)
    backend.puller(fake_server.url).pull(
        fake_server.url, link.device_token, link.family_id
    )
    open_settings(page, live)
    expect(page.locator("#set-network-count")).to_contain_text("1 network(s)")
    page.click("#set-network-reset")
    page.locator("#confirm-dialog").get_by_role(
        "button", name="Forget saved networks"
    ).click()
    expect(page.locator("#action-status")).to_contain_text("Done.")
    assert games(fake_server).networks == []
    page.get_by_role("button", name="Settings Games").click()
    expect(page.locator("#set-network-reset")).to_be_disabled()


def test_cancel_sends_nothing(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    open_settings(page, live_app_factory())
    pushes = fake_server.world.push_requests
    page.check("#set-notifications")
    page.click("#settings-cancel")
    expect(page.locator("#settings-dialog")).to_be_hidden()
    assert fake_server.world.push_requests == pushes
