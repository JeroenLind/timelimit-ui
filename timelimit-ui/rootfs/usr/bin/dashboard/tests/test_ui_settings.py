"""Plan step E1, browser half: the settings and link screen (FR-100..104)."""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect

from .conftest import PARENT_MAIL, PARENT_PASSWORD, link_app, make_family
from .fakeserver import FakeTimeLimitServer

pytestmark = pytest.mark.ui


@pytest.fixture
def page(browser: Any) -> Any:
    page = browser.new_context(locale="en-US").new_page()
    page.set_default_timeout(5000)
    return page


def log_in_with_mail(page: Page, fake: FakeTimeLimitServer, mail: str) -> None:
    expect(page.locator("#link-state")).to_have_attribute("data-state", "not_linked")
    page.fill("#link-mail", mail)
    page.click("#mail-send")
    expect(page.locator("#code-form")).to_be_visible()
    page.fill("#link-code", fake.inbox[-1][1])
    page.click("#code-confirm")
    expect(page.locator("#password-form")).to_be_visible()


def test_first_start_goes_to_settings_and_joining_loads_the_overview(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    make_family(fake_server)
    live = live_app_factory(linked=False)
    page.goto(live.url + "/")
    assert page.url.endswith("/settings")
    log_in_with_mail(page, fake_server, PARENT_MAIL)
    expect(page.locator("#link-submit")).to_have_text("Link")
    page.fill("#link-password", PARENT_PASSWORD)
    page.click("#link-submit")
    expect(page.locator("#link-state")).to_have_attribute("data-state", "ready")
    assert page.input_value("#link-password") == ""  # not kept in the form
    expect(page.locator("#linked-box")).to_be_visible()
    page.click('a[href="/"]')
    expect(
        page.locator("#overview-empty")
    ).to_be_visible()  # a new family has no children yet


def test_a_wrong_password_shows_an_error_and_stays_on_the_form(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    make_family(fake_server)
    live = live_app_factory(linked=False)
    page.goto(live.url + "/settings")
    log_in_with_mail(page, fake_server, PARENT_MAIL)
    page.fill("#link-password", "wrong")
    page.click("#link-submit")
    expect(page.locator("#settings-error")).to_have_attribute(
        "data-code", "INVALID_PASSWORD"
    )
    expect(page.locator("#password-form")).to_be_visible()


def test_create_family_is_offered_only_with_the_test_server_switch(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    live = live_app_factory(linked=False)
    page.goto(live.url + "/settings")
    page.fill("#link-mail", "fresh@example.org")
    page.click("#mail-send")
    expect(page.locator("#code-form")).to_be_visible()
    page.fill("#link-code", fake_server.inbox[-1][1])
    page.click("#code-confirm")
    expect(
        page.locator("#password-form")
    ).to_be_hidden()  # switch off: no create family
    page.check("#test-server")
    expect(page.locator("#password-form")).to_be_visible()
    expect(page.locator("#link-submit")).to_have_text("Create family")
    page.fill("#link-password", "a password")
    page.click("#link-submit")
    expect(page.locator("#link-state")).to_have_attribute("data-state", "ready")
    family = next(iter(fake_server.world.families.values()))
    assert [u.name for u in family.users.values()] == ["Dashboard"]


def test_alternative_server_asks_for_protocol_address_and_port(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    live = live_app_factory(linked=False, server_url="")
    page.goto(live.url + "/settings")
    expect(page.locator("#alt-fields")).to_be_hidden()
    page.select_option("#server-mode", "alternative")
    expect(page.locator("#alt-fields")).to_be_visible()
    assert page.input_value("#server-protocol") == "http"  # default
    page.fill("#server-address", "127.0.0.1")
    page.fill("#server-port", str(fake_server.port))
    page.click("#server-save")
    expect(page.locator("#server-url")).to_have_text(
        f"http://127.0.0.1:{fake_server.port}"
    )
    page.reload()
    expect(page.locator("#server-address")).to_have_value("127.0.0.1")
    page.fill("#server-address", "http://bad")
    page.click("#server-save")
    expect(page.locator("#settings-error")).to_have_attribute(
        "data-code", "INVALID_INPUT"
    )


def test_untested_api_level_shows_a_banner_but_stays_usable(
    page: Page, live_app_factory: Any
) -> None:
    with FakeTimeLimitServer(api_level=8) as fake:
        make_family(fake)
        live = live_app_factory(linked=False, server_url=fake.url)
        link_app(live.app, fake)
        page.goto(live.url + "/")
        banner = page.locator('[data-notice="VERSION_UNTESTED"]')
        expect(banner).to_be_visible()
        expect(banner).to_contain_text("8")
        expect(page.locator("#refresh-overview")).to_be_enabled()


def test_tested_api_level_shows_no_banner(page: Page, live_app_factory: Any) -> None:
    live = live_app_factory()
    page.goto(live.url + "/")
    expect(page.locator("#overview-list li")).to_have_count(2)
    expect(page.locator("#notices .banner")).to_have_count(0)


def test_debug_export_shows_the_warning_first_and_downloads(
    page: Page, live_app_factory: Any
) -> None:
    live = live_app_factory()
    page.goto(live.url + "/settings")
    expect(page.locator("#info-version")).not_to_be_empty()
    page.click("#debug-export")
    dialog = page.locator("#confirm-dialog")
    expect(dialog).to_be_visible()
    expect(dialog.locator("[data-dialog-message]")).not_to_be_empty()
    page.click("[data-dialog-cancel]")  # cancelling downloads nothing
    expect(dialog).to_be_hidden()
    page.click("#debug-export")
    with page.expect_download() as download:
        page.click("[data-dialog-ok]")
    assert download.value.suggested_filename == "dashboard-debug.txt"


def test_unlink_asks_for_confirmation(page: Page, live_app_factory: Any) -> None:
    live = live_app_factory()
    page.goto(live.url + "/settings")
    expect(page.locator("#link-state")).to_have_attribute("data-state", "ready")
    page.click("#unlink")
    page.click("[data-dialog-cancel]")
    expect(page.locator("#link-state")).to_have_attribute("data-state", "ready")
    page.click("#unlink")
    page.click("[data-dialog-ok]")
    expect(page.locator("#link-state")).to_have_attribute("data-state", "not_linked")
