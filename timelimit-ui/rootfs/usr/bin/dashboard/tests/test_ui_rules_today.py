"""Plan step E3a, browser half: rule off for today (FR-307)."""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect

from .fakeserver.state import version_id

pytestmark = pytest.mark.ui


@pytest.fixture
def page(browser: Any) -> Any:
    page = browser.new_context(locale="en-US").new_page()
    page.set_default_timeout(5000)
    return page


def open_rules(page: Page, live: Any) -> None:
    page.goto(live.url + "/")
    page.click('#overview-list a:has-text("Anna")')
    page.click("#tab-rules")
    expect(page.locator('#rules-list tr[data-rule-id="rule01"]')).to_be_visible()


def games(fake: Any) -> Any:
    return next(iter(fake.world.families.values())).categories["cgames"]


def test_off_for_today_and_on_again(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    open_rules(page, live_app_factory())
    row = page.locator('#rules-list tr[data-rule-id="rule01"]')
    row.locator(".off-today").click()
    expect(row).to_contain_text("Off for today, back at")
    expect(row.locator(".off-today")).to_have_text("On again")
    assert games(fake_server).rules["rule01"].day_mask != 127
    row.locator(".off-today").click()
    expect(row.locator(".off-today")).to_have_text("Off for today")
    expect(row).not_to_contain_text("back at")
    assert games(fake_server).rules["rule01"].day_mask == 127


def test_the_button_is_disabled_when_the_rule_does_not_apply_today(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    import time

    live = live_app_factory()
    weekday = time.gmtime().tm_wday
    category = games(fake_server)
    category.rules["rule01"].day_mask = 127 & ~(1 << weekday)
    category.rules_version = version_id()
    backend = live.app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake_server.url)
    backend.puller(fake_server.url).pull(
        fake_server.url, link.device_token, link.family_id
    )
    open_rules(page, live)
    button = page.locator('#rules-list tr[data-rule-id="rule01"] .off-today')
    expect(button).to_be_disabled()
    expect(button).to_have_attribute("title", "This rule does not apply today.")


def test_a_restore_notice_can_be_dismissed(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    live = live_app_factory()
    backend = live.app.extensions["dashboard"]["backend"]
    service = live.app.extensions["dashboard"]["rule_today"]
    open_rules(page, live)
    row = page.locator('#rules-list tr[data-rule-id="rule01"]')
    row.locator(".off-today").click()
    expect(row.locator(".off-today")).to_have_text("On again")
    pending = backend.restores.get(fake_server.url, "rule01")
    service.ended_by_change(pending)  # as an edit of the rule would
    page.reload()
    banner = page.locator('[data-notice="RULE_OFF_ENDED"]')
    expect(banner).to_contain_text("Anna")
    banner.locator(".dismiss-notice").click()
    expect(banner).to_have_count(0)
