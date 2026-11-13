"""Plan step E4, browser half: waiting marker, conflict warning, clean-up (FR-205, FR-206, FR-208, UI-007)."""

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


def open_rules(page: Page, live: Any) -> Any:
    page.goto(live.url + "/")
    page.click('#overview-list a:has-text("Anna")')
    page.click("#tab-rules")
    games = page.locator('#rules-list section[data-category-id="cgames"]')
    expect(games.locator("tbody tr")).to_have_count(1)
    return games


def test_a_new_rule_shows_waiting_for_server_until_confirmed(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    games = open_rules(page, live_app_factory())
    games.locator(".add-rule").click()
    page.fill("#rule-minutes", "20")
    fake_server.faults.delay_seconds = (
        0.6  # the server is slow (below the dashboard timeout)
    )
    page.click("#rule-save")
    pending = games.locator("tr[data-pending]")
    expect(pending).to_have_count(1)
    expect(pending).to_contain_text("waiting for server")
    expect(page.locator("#action-status")).to_contain_text("Waiting for the server")
    fake_server.faults.delay_seconds = 0
    expect(pending).to_have_count(0, timeout=15000)
    expect(games.locator("tbody tr")).to_have_count(2)
    expect(page.locator("#action-status")).to_contain_text("Done.")


def test_a_rejected_new_rule_disappears_with_the_reason(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    games = open_rules(page, live_app_factory())
    del family(fake_server).categories[
        "cgames"
    ]  # gone on the server, the cache does not know yet
    games.locator(".add-rule").click()
    page.fill("#rule-minutes", "20")
    page.click("#rule-save")
    expect(page.locator("#action-status")).to_contain_text("Not done.")
    expect(games.locator("tr[data-pending]")).to_have_count(0)
    expect(page.locator("#rules-error")).to_be_visible()


def test_a_change_made_elsewhere_asks_before_overwriting(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    games = open_rules(page, live)
    games.locator(".edit-rule").click()
    # meanwhile someone else changes the rule on the server
    category = family(fake_server).categories["cgames"]
    category.rules["rule01"].max_time = 30 * 60000
    category.rules_version = version_id()
    backend = live.app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake_server.url)
    backend.puller(fake_server.url).pull(
        fake_server.url, link.device_token, link.family_id
    )
    # the dialog was opened with the old version
    page.fill("#rule-minutes", "45")
    page.click("#rule-save")
    dialog = page.locator("#confirm-dialog")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("changed on the server")
    assert category.rules["rule01"].max_time == 30 * 60000  # nothing sent yet
    dialog.get_by_role("button", name="Save anyway").click()
    expect(page.locator("#action-status")).to_contain_text("Done.", timeout=15000)
    assert category.rules["rule01"].max_time == 45 * 60000


def test_cancelling_the_conflict_warning_sends_nothing(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    games = open_rules(page, live)
    games.locator(".edit-rule").click()
    category = family(fake_server).categories["cgames"]
    category.rules["rule01"].max_time = 30 * 60000
    category.rules_version = version_id()
    backend = live.app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake_server.url)
    backend.puller(fake_server.url).pull(
        fake_server.url, link.device_token, link.family_id
    )
    page.fill("#rule-minutes", "45")
    page.click("#rule-save")
    page.locator("#confirm-dialog").get_by_role("button", name="Cancel").click()
    expect(games.locator("tr[data-pending]")).to_have_count(0)
    assert category.rules["rule01"].max_time == 30 * 60000


def test_clean_up_removes_children_the_server_no_longer_reports(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    page.goto(live.url + "/")
    expect(page.locator("#overview-list li")).to_have_count(2)
    fam = family(fake_server)
    ben = next(u.user_id for u in fam.users.values() if u.name == "Ben")
    del fam.users[ben]
    fam.user_list_version = version_id()
    backend = live.app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake_server.url)
    backend.puller(fake_server.url).pull(
        fake_server.url, link.device_token, link.family_id
    )
    page.reload()
    banner = page.locator('[data-notice="ITEMS_MISSING"]')
    expect(banner).to_be_visible()
    expect(page.locator("#overview-list li")).to_have_count(2)  # kept, flagged
    banner.locator(".clean-up").click()
    expect(page.locator("#overview-list li")).to_have_count(1)
    expect(banner).to_have_count(0)
