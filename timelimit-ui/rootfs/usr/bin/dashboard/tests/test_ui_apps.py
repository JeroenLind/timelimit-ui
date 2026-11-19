"""Plan step E7, browser half: apps per category (FR-403..405)."""

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


def family(fake: Any) -> Any:
    return next(iter(fake.world.families.values()))


def give_apps(fake: Any) -> None:
    fam = family(fake)
    fam.devices["dtablet"].installed_apps = [
        {
            "packageName": p,
            "title": t,
            "isLaunchable": True,
            "recommendation": "none",
        }
        for p, t in (
            ("com.game.one", "Alpha game"),
            ("com.chat.app", "Chat"),
            ("com.school.tool", "School tool"),
        )
    ]
    fam.devices["dtablet"].apps_version = version_id()
    fam.categories["cgames"].apps = ["com.game.one"]
    fam.categories["cgames"].apps_version = version_id()


def start(factory: Any, fake: Any, apps: bool) -> Any:
    live = factory()
    if apps:
        give_apps(fake)
        backend = live.app.extensions["dashboard"]["backend"]
        link = backend.links.get(fake.url)
        backend.puller(fake.url).pull(fake.url, link.device_token, link.family_id)
    return live


def open_apps(page: Page, live: Any, category: str) -> None:
    page.goto(live.url + "/")
    page.click('#overview-list a:has-text("Anna")')
    expect(page.locator("#categories-body tr")).to_have_count(2)
    page.get_by_role("button", name=f"Apps {category}").click()
    expect(page.locator("#apps-dialog")).to_be_visible()


def test_titles_and_package_names_show_and_a_moving_app_is_labelled(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = start(live_app_factory, fake_server, True)
    open_apps(page, live, "Social")
    available = page.locator("#apps-available")
    expect(available).to_contain_text("Chat (com.chat.app)")
    expect(available).to_contain_text("Alpha game (com.game.one)")
    expect(available).to_contain_text("will be moved")
    expect(page.locator("#apps-unknown")).to_be_hidden()


def test_selected_apps_are_assigned_to_the_category(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = start(live_app_factory, fake_server, True)
    open_apps(page, live, "Social")
    page.check('#apps-available input[value="com.chat.app"]')
    page.check('#apps-available input[value="com.school.tool"]')
    page.click("#apps-add")
    expect(page.locator("#apps-assigned")).to_contain_text("School tool")
    assert set(family(fake_server).categories["csocia"].apps) == {
        "com.chat.app",
        "com.school.tool",
    }


def test_an_assigned_app_can_be_removed(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = start(live_app_factory, fake_server, True)
    open_apps(page, live, "Games")
    page.check('#apps-assigned input[value="com.game.one"]')
    page.click("#apps-remove")
    dialog = page.locator("#confirm-dialog")
    expect(dialog).to_contain_text("Remove 1 app(s)")
    dialog.get_by_role("button", name="Remove selected").click()
    expect(page.locator("#apps-assigned input")).to_have_count(0)
    assert family(fake_server).categories["cgames"].apps == []


def test_cancelling_the_removal_keeps_the_app(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = start(live_app_factory, fake_server, True)
    open_apps(page, live, "Games")
    page.check('#apps-assigned input[value="com.game.one"]')
    page.click("#apps-remove")
    page.locator("#confirm-dialog").get_by_role("button", name="Cancel").click()
    expect(page.locator("#apps-assigned input")).to_have_count(1)
    assert family(fake_server).categories["cgames"].apps == ["com.game.one"]


def test_without_an_app_list_the_dialog_explains_and_manual_names_work(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = start(live_app_factory, fake_server, False)
    open_apps(page, live, "Social")
    expect(page.locator("#apps-unknown")).to_be_visible()
    page.fill("#apps-manual", "com.example.manual")
    page.click("#apps-add")
    expect(page.locator("#apps-assigned")).to_contain_text("com.example.manual")
    assert family(fake_server).categories["csocia"].apps == ["com.example.manual"]


def test_a_bad_package_name_shows_an_error(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = start(live_app_factory, fake_server, False)
    open_apps(page, live, "Social")
    page.fill("#apps-manual", "bad name!")
    page.click("#apps-add")
    expect(page.locator("#apps-error")).to_be_visible()
