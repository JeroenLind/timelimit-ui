"""Plan step E2, browser half: children overview and child detail (FR-700..702, UI-001)."""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect

from .conftest import seed_children  # noqa: F401 (the factory seeds the family)
from .fakeserver.state import version_id

pytestmark = pytest.mark.ui

PHONE = {"width": 390, "height": 800}


@pytest.fixture
def page(browser: Any) -> Any:
    page = browser.new_context(locale="en-US").new_page()
    page.set_default_timeout(5000)
    return page


def open_overview(page: Page, live: Any) -> None:
    page.goto(live.url + "/")
    expect(page.locator("#overview-list li")).to_have_count(2)


def test_overview_shows_the_children_with_numbers(
    page: Page, live_app_factory: Any
) -> None:
    open_overview(page, live_app_factory())
    anna = page.locator('#overview-list li:has-text("Anna")')
    expect(anna).to_contain_text("1 h 05 min")
    expect(anna).to_contain_text("2 categories")
    expect(anna).to_contain_text("1 devices")
    expect(anna.locator(".badge")).to_have_text("OK")
    expect(page.locator('#overview-list li:has-text("Ben")')).to_contain_text("0 min")


def test_child_detail_shows_categories_and_devices(
    page: Page, live_app_factory: Any
) -> None:
    open_overview(page, live_app_factory())
    page.click('#overview-list a:has-text("Anna")')
    expect(page.locator("#child-name")).to_have_text("Anna")
    rows = page.locator("#categories-body tr")
    expect(rows).to_have_count(2)
    expect(rows.nth(0)).to_contain_text("Games")
    expect(rows.nth(0)).to_contain_text("1 h 05 min")
    expect(rows.nth(0)).to_contain_text("+15 min")
    expect(rows.nth(1).locator("td").first).to_have_attribute("data-depth", "1")
    expect(page.locator("#panel-devices")).to_be_hidden()
    page.click("#tab-devices")
    expect(page.locator("#panel-categories")).to_be_hidden()
    expect(page.locator("#devices-body tr")).to_have_count(1)
    expect(page.locator("#devices-body")).to_contain_text("Pixel Tablet")


def test_tabs_work_with_the_arrow_keys(page: Page, live_app_factory: Any) -> None:
    live = live_app_factory()
    open_overview(page, live)
    page.click('#overview-list a:has-text("Anna")')
    expect(page.locator("#tab-categories")).to_be_visible()  # data loaded, script ready
    expect(page.locator("#tab-categories")).to_have_attribute("aria-selected", "true")
    page.focus("#tab-categories")
    page.keyboard.press("ArrowRight")
    expect(page.locator("#tab-rules")).to_have_attribute("aria-selected", "true")
    page.keyboard.press("ArrowRight")
    expect(page.locator("#tab-blocked")).to_have_attribute("aria-selected", "true")
    page.keyboard.press("ArrowRight")
    expect(page.locator("#tab-devices")).to_have_attribute("aria-selected", "true")
    expect(page.locator("#panel-devices")).to_be_visible()
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#tab-categories")).to_have_attribute("aria-selected", "true")


def tell_the_device(live: Any, fake_server: Any) -> None:
    """What the real server does after a change by someone else: send "should sync" to the device.

    The device may still be logging in on its socket, so the message is repeated for a few seconds
    (extra pulls are harmless)."""
    import threading
    import time

    backend = live.app.extensions["dashboard"]["backend"]
    token = backend.links.get(fake_server.url).device_token.reveal()

    def repeat() -> None:
        end = time.monotonic() + 4
        while time.monotonic() < end:
            if fake_server.socket_clients >= 1:
                fake_server.should_sync(token)
            time.sleep(0.25)

    threading.Thread(target=repeat, daemon=True).start()


def test_a_child_removed_on_the_server_shows_the_state_not_an_error(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory(poll_interval=0.3)
    open_overview(page, live)
    family = next(iter(fake_server.world.families.values()))
    ben_id = next(u.user_id for u in family.users.values() if u.name == "Ben")
    page.click('#overview-list a:has-text("Ben")')
    expect(page.locator("#child-gone")).to_be_hidden()
    del family.users[ben_id]
    family.user_list_version = version_id()
    tell_the_device(live, fake_server)
    expect(page.locator("#child-gone")).to_be_visible()  # live update, no reload
    assert page.locator("#child-error").is_hidden()
    page.reload()
    expect(page.locator("#child-gone")).to_be_visible()
    expect(page.locator("#child-name")).to_have_text("Ben")


def test_an_unknown_child_shows_a_clear_message(
    page: Page, live_app_factory: Any
) -> None:
    live = live_app_factory()
    page.goto(live.url + "/children/doesnotexist")
    expect(page.locator("#child-unknown")).to_be_visible()
    expect(page.locator("#child-content")).to_be_hidden()


def test_the_overview_follows_changes_made_elsewhere(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory(poll_interval=0.3)
    open_overview(page, live)
    family = next(iter(fake_server.world.families.values()))
    games = family.categories["cgames"]
    (day,) = games.used_times
    games.used_times[day] = {(0, 1439): 125 * 60000}
    games.used_times_version = version_id()
    tell_the_device(live, fake_server)
    expect(page.locator('#overview-list li:has-text("Anna")')).to_contain_text(
        "2 h 05 min"
    )


def test_durations_follow_the_language(browser: Any, live_app_factory: Any) -> None:
    page = browser.new_context(locale="nl-NL").new_page()
    page.set_default_timeout(5000)
    open_overview(page, live_app_factory())
    expect(page.locator('#overview-list li:has-text("Anna")')).to_contain_text(
        "1 u 05 min"
    )
    expect(page.locator('#overview-list li:has-text("Anna")')).to_contain_text(
        "2 categorieën"
    )


@pytest.mark.parametrize("path", ["/", "/children/{anna}"])
def test_no_horizontal_scroll_at_phone_width(
    browser: Any, live_app_factory: Any, path: str
) -> None:
    live = live_app_factory()
    ids = live.app.extensions["dashboard"]["children"].overview()["children"]
    anna = next(c["id"] for c in ids if c["name"] == "Anna")
    page = browser.new_context(locale="en-US", viewport=PHONE).new_page()
    page.set_default_timeout(5000)
    page.goto(live.url + path.format(anna=anna))
    expect(page.locator("#overview-list li, #categories-body tr").first).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
