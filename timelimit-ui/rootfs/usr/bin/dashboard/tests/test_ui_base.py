"""Plan step D1, browser half: theme, language, navigation, dialog (UI-002..006)."""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect

from .conftest import LiveApp

pytestmark = pytest.mark.ui

DESKTOP = {"width": 1280, "height": 800}
PHONE = {"width": 390, "height": 800}


def make_page(browser: Any, **options: Any) -> Any:
    options.setdefault("locale", "en-US")
    context = browser.new_context(**options)
    page = context.new_page()
    page.set_default_timeout(5000)
    return page


def open_app(page: Page, live: LiveApp) -> None:
    page.goto(live.url + "/")
    expect(page.locator("#overview-list li")).to_have_count(2)


def test_desktop_shows_the_sidebar_and_no_hamburger(
    browser: Any, live_app_factory: Any
) -> None:
    page = make_page(browser, viewport=DESKTOP)
    open_app(page, live_app_factory())
    expect(page.locator("#sidebar")).to_be_visible()
    expect(page.locator("#menu-toggle")).to_be_hidden()
    assert page.locator("#sidebar").get_attribute("aria-hidden") == "false"


def test_phone_hamburger_opens_and_closes_all_four_ways(
    browser: Any, live_app_factory: Any
) -> None:
    page = make_page(browser, viewport=PHONE)
    open_app(page, live_app_factory())
    sidebar, toggle = page.locator("#sidebar"), page.locator("#menu-toggle")
    expect(sidebar).to_be_hidden()
    expect(toggle).to_be_visible()
    assert toggle.get_attribute("aria-expanded") == "false"
    assert sidebar.get_attribute("aria-hidden") == "true"

    def opened() -> None:
        toggle.click()
        expect(sidebar).to_be_visible()
        assert toggle.get_attribute("aria-expanded") == "true"
        assert sidebar.get_attribute("aria-hidden") == "false"
        assert page.evaluate("document.activeElement.id") == "nav-close"

    def closed() -> None:
        expect(sidebar).to_be_hidden()
        assert toggle.get_attribute("aria-expanded") == "false"
        assert sidebar.get_attribute("aria-hidden") == "true"
        assert page.evaluate("document.activeElement.id") == "menu-toggle"

    opened()
    toggle.click()  # 1. the button again
    closed()
    opened()
    page.locator("#nav-close").click()  # 2. close button
    closed()
    opened()
    page.mouse.click(380, 600)  # 3. overlay (right of the 260 px sidebar)
    closed()
    opened()
    page.keyboard.press("Escape")  # 4. Escape
    closed()


def test_resizing_to_desktop_closes_the_menu_state(
    browser: Any, live_app_factory: Any
) -> None:
    page = make_page(browser, viewport=PHONE)
    open_app(page, live_app_factory())
    page.locator("#menu-toggle").click()
    page.set_viewport_size(DESKTOP)
    expect(page.locator("#sidebar")).to_be_visible()
    expect(page.locator("#nav-overlay")).to_be_hidden()


def test_dark_system_theme_is_followed(browser: Any, live_app_factory: Any) -> None:
    live = live_app_factory()
    dark = make_page(browser, color_scheme="dark")
    open_app(dark, live)
    assert (
        dark.evaluate("getComputedStyle(document.body).backgroundColor")
        == "rgb(18, 22, 28)"
    )
    light = make_page(browser, color_scheme="light")
    open_app(light, live)
    assert (
        light.evaluate("getComputedStyle(document.body).backgroundColor")
        == "rgb(246, 247, 249)"
    )


def test_manual_theme_wins_and_is_remembered(
    browser: Any, live_app_factory: Any
) -> None:
    page = make_page(browser, color_scheme="dark")
    live = live_app_factory()
    open_app(page, live)
    page.select_option("#theme-select", "light")
    assert (
        page.evaluate("getComputedStyle(document.body).backgroundColor")
        == "rgb(246, 247, 249)"
    )
    page.reload()
    expect(page.locator("#overview-list li")).to_have_count(2)
    assert page.evaluate("document.documentElement.dataset.theme") == "light"
    assert page.locator("#theme-select").input_value() == "light"
    page.select_option("#theme-select", "auto")
    page.reload()
    assert page.evaluate("document.documentElement.dataset.theme") is None


def test_language_defaults_to_the_browser_and_switches(
    browser: Any, live_app_factory: Any
) -> None:
    live = live_app_factory()
    dutch = make_page(browser, locale="nl-NL")
    open_app(dutch, live)
    expect(dutch.locator("main h2")).to_have_text("Overzicht")
    german = make_page(browser, locale="de-DE")
    open_app(german, live)
    expect(german.locator("main h2")).to_have_text("Overview")  # not nl or en: English

    page = make_page(browser)
    open_app(page, live)
    expect(page.locator("main h2")).to_have_text("Overview")
    page.select_option("#language-select", "nl")
    expect(page.locator("main h2")).to_have_text("Overzicht")
    expect(page.locator("#refresh-overview")).not_to_have_text("Refresh from server")
    assert page.evaluate("document.documentElement.lang") == "nl"
    page.reload()
    expect(page.locator("main h2")).to_have_text("Overzicht")


def test_a_missing_key_shows_the_english_text(
    browser: Any, live_app_factory: Any
) -> None:
    page = make_page(browser, locale="nl-NL")
    live = live_app_factory()

    def drop_key(route: Any) -> None:
        import json

        data = json.loads(route.fetch().text())
        data.pop("overview.title")
        route.fulfill(json=data)

    page.route("**/static/i18n/nl.json", drop_key)
    open_app(page, live)
    expect(page.locator("main h2")).to_have_text("Overview")
    expect(page.locator("#refresh-overview")).not_to_have_text("Refresh from server")


def test_confirmation_dialog_confirms_cancels_and_traps_focus(
    browser: Any, live_app_factory: Any
) -> None:
    page = make_page(browser)
    open_app(page, live_app_factory())
    ask = """() => import('/static/js/dialog.js').then(m =>
        { window.answer = m.confirmDialog({title: 'Delete?', message: 'Sure?', danger: true})
            .then(v => { window.result = v; }); })"""
    dialog = page.locator("#confirm-dialog")
    page.locator("#refresh-overview").focus()

    page.evaluate(ask)
    expect(dialog).to_be_visible()
    expect(dialog.locator("[data-dialog-title]")).to_have_text("Delete?")
    for _ in range(6):  # focus never leaves the dialog
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.closest('dialog') !== null")
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    page.wait_for_function("window.result === false")
    assert page.evaluate("document.activeElement.id") == "refresh-overview"

    page.evaluate("window.result = undefined")
    page.evaluate(ask)
    dialog.locator("[data-dialog-ok]").click()
    page.wait_for_function("window.result === true")
