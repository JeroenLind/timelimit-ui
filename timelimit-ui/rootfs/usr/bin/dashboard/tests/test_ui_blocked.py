"""Plan step E5, browser half: the weekly blocked-times grid (FR-304)."""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect

from ..domain.bitmask import parse_blocked_times
from .fakeserver.state import version_id

pytestmark = pytest.mark.ui


@pytest.fixture
def page(browser: Any) -> Any:
    page = browser.new_context(locale="en-US").new_page()
    page.set_default_timeout(8000)
    return page


def games(fake: Any) -> Any:
    return next(iter(fake.world.families.values())).categories["cgames"]


def open_blocked(page: Page, live: Any) -> None:
    page.goto(live.url + "/")
    page.click('#overview-list a:has-text("Anna")')
    page.click("#tab-blocked")
    expect(page.locator("#blocked-grid .blocked-cell")).to_have_count(336)


def cell(page: Page, day: int, hour: int, half: int = 0) -> Any:
    return page.locator(f'[data-cell="{day * 48 + hour * 2 + half}"]')


def drag(page: Page, day: int, start_hour: int, end_hour: int) -> None:
    """Paint the cells from start_hour up to (not including) end_hour on one day."""
    cell(page, day, start_hour).scroll_into_view_if_needed()
    first = cell(page, day, start_hour).bounding_box()
    last = cell(page, day, end_hour - 1, 1).bounding_box()
    assert first and last
    page.mouse.move(first["x"] + 5, first["y"] + 5)
    page.mouse.down()
    page.mouse.move(last["x"] + 5, last["y"] + 5, steps=8)
    page.mouse.up()


def test_block_monday_to_friday_nights_by_dragging_over_the_grid(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    open_blocked(page, live_app_factory())
    for day in range(5):
        drag(page, day, 22, 24)
        drag(page, day, 0, 7)
    expect(page.locator("#blocked-save")).to_be_enabled()
    page.click("#blocked-save")
    expect(page.locator("#action-status")).to_contain_text("Done.")
    intervals = parse_blocked_times(games(fake_server).blocked_times)
    assert intervals[0] == (0, 420)
    assert (1320, 1440 + 420) in intervals  # 22:00 until 07:00 the next morning, merged
    assert (4 * 1440 + 1320, 5 * 1440) in intervals
    page.reload()
    page.click("#tab-blocked")
    expect(cell(page, 2, 23)).to_have_attribute("aria-pressed", "true")
    expect(cell(page, 2, 12)).to_have_attribute("aria-pressed", "false")
    expect(cell(page, 6, 23)).to_have_attribute(
        "aria-pressed", "false"
    )  # Sunday untouched


def test_click_and_space_toggle_one_cell(page: Page, live_app_factory: Any) -> None:
    open_blocked(page, live_app_factory())
    target = cell(page, 1, 9)
    target.click()
    expect(target).to_have_attribute("aria-pressed", "true")
    target.click()
    expect(target).to_have_attribute("aria-pressed", "false")
    target.focus()
    page.keyboard.press("Space")
    expect(target).to_have_attribute("aria-pressed", "true")
    page.keyboard.press("ArrowRight")
    expect(cell(page, 1, 9, 1)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(cell(page, 2, 9, 1)).to_be_focused()


def test_a_schedule_made_elsewhere_is_shown(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    games(fake_server).blocked_times = "1320,1440"  # Monday 22:00-24:00
    games(fake_server).base_version = version_id()
    backend = live.app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake_server.url)
    backend.puller(fake_server.url).pull(
        fake_server.url, link.device_token, link.family_id
    )
    open_blocked(page, live)
    expect(cell(page, 0, 22)).to_have_attribute("aria-pressed", "true")
    expect(cell(page, 0, 23, 1)).to_have_attribute("aria-pressed", "true")
    expect(cell(page, 0, 21, 1)).to_have_attribute("aria-pressed", "false")


def test_reset_drops_unsaved_changes_and_day_buttons_fill_a_day(
    page: Page, live_app_factory: Any
) -> None:
    open_blocked(page, live_app_factory())
    page.get_by_role("button", name="All Wed").click()
    expect(cell(page, 2, 0)).to_have_attribute("aria-pressed", "true")
    expect(cell(page, 2, 47 // 2, 1)).to_have_attribute("aria-pressed", "true")
    page.click("#blocked-reset")
    expect(cell(page, 2, 0)).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#blocked-save")).to_be_disabled()


def test_no_horizontal_scroll_at_phone_width(
    browser: Any, live_app_factory: Any
) -> None:
    live = live_app_factory()
    page = browser.new_context(
        locale="en-US", viewport={"width": 390, "height": 800}
    ).new_page()
    page.set_default_timeout(8000)
    open_blocked(page, live)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
