"""Plan step A7, browser half: server-down handling in a real browser (FR-1000..1003, TR-303)."""

from __future__ import annotations

import time
from typing import Any

import pytest
from playwright.sync_api import Page, expect

from .conftest import LiveApp
from .fakeserver import FakeTimeLimitServer

pytestmark = pytest.mark.ui

BANNER = "#server-banner"
CONTROL = "#refresh-overview"


@pytest.fixture
def page(browser: Any) -> Any:
    context = browser.new_context(locale="en-US")
    page = context.new_page()
    page.set_default_timeout(5000)
    yield page
    context.close()


def open_page(page: Page, live: LiveApp) -> None:
    page.goto(live.url + "/")
    expect(page.locator("#overview-list li")).to_have_count(2)


def test_server_up_shows_no_banner_and_enabled_controls(
    page: Page, live_app_factory: Any
) -> None:
    open_page(page, live_app_factory())
    expect(page.locator(BANNER)).to_be_hidden()
    expect(page.locator(CONTROL)).to_be_enabled()
    expect(page.locator("body")).to_have_attribute("data-server", "up")


def test_server_down_shows_the_banner_and_disables_changes(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    open_page(page, live_app_factory())
    started = time.monotonic()
    fake_server.stop()
    expect(page.locator(BANNER)).to_be_visible()
    assert (
        time.monotonic() - started < 0.3 + 1.0 + 1.0
    )  # interval + health timeout + 1 s
    expect(page.locator(CONTROL)).to_be_disabled()
    expect(page.locator("#overview-list li")).to_have_count(
        2
    )  # last known data stays visible
    expect(page.locator("#retry-connection")).to_be_visible()


def test_server_back_removes_the_banner_and_refreshes_the_data(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    refreshes: list[str] = []
    page.on(
        "request",
        lambda r: refreshes.append(r.url) if r.url.endswith("/api/children") else None,
    )
    open_page(page, live_app_factory())
    fake_server.stop()
    expect(page.locator(BANNER)).to_be_visible()
    before = len(refreshes)
    fake_server.start()
    expect(page.locator(BANNER)).to_be_hidden()
    expect(page.locator(CONTROL)).to_be_enabled()
    assert len(refreshes) > before


def test_the_retry_button_checks_immediately(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    live = live_app_factory(backoff_initial=30.0, backoff_max=30.0)
    open_page(page, live)
    fake_server.stop()
    expect(page.locator(BANNER)).to_be_visible()
    fake_server.start()
    started = time.monotonic()
    page.click("#retry-connection")
    expect(page.locator(BANNER)).to_be_hidden()
    assert time.monotonic() - started < 2.0  # far below the 30 s back-off


def test_polling_while_down_follows_the_backoff_and_does_not_pile_up(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    stamps: list[float] = []
    page.on(
        "request",
        lambda r: (
            stamps.append(time.monotonic())
            if r.url.endswith("/api/server/status")
            else None
        ),
    )
    open_page(page, live_app_factory())
    fake_server.faults.drop_connection = (
        True  # server is "down" but we can count its calls
    )
    expect(page.locator(BANNER)).to_be_visible()
    calls_at_down = len(fake_server.calls)
    mark = len(stamps)
    page.wait_for_timeout(3000)
    gaps = [b - a for a, b in zip(stamps[mark:], stamps[mark + 1 :], strict=False)]
    assert len(gaps) >= 3
    assert all(0.25 <= g <= 1.0 for g in gaps), gaps  # 0.3 s initial, 0.6 s maximum
    assert all(g >= 0.5 for g in gaps[1:]), gaps  # settled at the maximum
    # one probe per poll, nothing queued up behind it
    assert len(fake_server.calls) - calls_at_down <= len(stamps) - mark + 1


def test_a_hanging_request_is_aborted_and_shown_as_unreachable(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    live = live_app_factory(health_timeout=5.0, browser_timeout=0.5)
    open_page(page, live)
    fake_server.faults.delay_seconds = 3.0
    expect(page.locator(BANNER)).to_be_visible()
    assert page.locator(BANNER).get_attribute("data-code") == "SERVER_UNREACHABLE"
    expect(page.locator(CONTROL)).to_be_disabled()


def test_without_a_server_a_notice_is_shown_but_nothing_is_disabled(
    page: Page, live_app_factory: Any
) -> None:
    live = live_app_factory(server_url="")
    page.goto(
        live.url + "/"
    )  # nothing chosen yet: the settings screen is the only page
    assert page.url.endswith("/settings")
    expect(page.locator(BANNER)).to_be_visible()
    assert page.locator(BANNER).get_attribute("data-state") == "not_configured"
    expect(page.locator("#retry-connection")).to_be_hidden()
    expect(page.locator("#server-save")).to_be_enabled()


def test_dutch_browser_gets_dutch_texts_and_missing_keys_fall_back(
    browser: Any, live_app_factory: Any
) -> None:
    context = browser.new_context(locale="nl-NL")
    page = context.new_page()
    page.set_default_timeout(5000)
    page.goto(live_app_factory().url + "/")
    expect(page.locator("main h2")).to_have_text("Overzicht")
    assert page.evaluate("document.documentElement.lang") == "nl"
    context.close()


def test_the_menu_becomes_a_hamburger_on_a_phone(
    browser: Any, live_app_factory: Any
) -> None:
    context = browser.new_context(viewport={"width": 390, "height": 800})
    page = context.new_page()
    page.set_default_timeout(5000)
    page.goto(live_app_factory().url + "/")
    expect(page.locator("#sidebar")).to_be_hidden()
    page.click("#menu-toggle")
    expect(page.locator("#sidebar")).to_be_visible()
    context.close()


def test_the_page_has_no_inline_styles_and_follows_the_dark_system_theme(
    browser: Any, live_app_factory: Any
) -> None:
    context = browser.new_context(color_scheme="dark")
    page = context.new_page()
    page.goto(live_app_factory().url + "/")
    html = page.content()
    assert "<style" not in html
    assert "style=" not in html.replace("stylesheet", "")
    assert (
        page.evaluate("getComputedStyle(document.body).backgroundColor")
        == "rgb(18, 22, 28)"
    )
    context.close()
